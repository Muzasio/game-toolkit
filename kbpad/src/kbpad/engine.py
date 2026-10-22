"""The engine: one reader thread per physical keyboard, fixed virtual pads, grab control.

Rules that fix the old two-terminal setup:
  * Pads are created once, in order P1..Pn, and live until the app quits. A keyboard
    unplugging only detaches the keyboard, so PCSX2 never sees the pads swap or vanish.
  * Ctrl+F1 is read from the keyboard's own events, so it works on every keyboard with
    no terminal focus. The GUI button calls the same code.
  * A grab waits until every key on that keyboard is released, so Ctrl never sticks
    on the desktop after Ctrl+F1.
  * Ctrl+Shift+F12 on any keyboard releases every keyboard.
  * Leaving the app (or a crash) closes the device files, and the kernel drops the grab.
No key names or typed text are ever written to the log.
"""

from __future__ import annotations

import errno
import logging
import os
import select
import threading
import time
from dataclasses import dataclass
from typing import Callable

from evdev import InputDevice, ecodes as e

from . import devices
from .constants import MAX_PLAYERS
from .keynames import code_to_name, name_to_code, pretty
from .pad import VirtualPad
from .profiles import Profile

log = logging.getLogger(__name__)

# Hotkey chords are lists like ["CTRL", "KEY_F1"]: modifier groups plus one main key (last).
MODIFIERS = {
    "CTRL": {e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL},
    "SHIFT": {e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT},
    "ALT": {e.KEY_LEFTALT, e.KEY_RIGHTALT},
    "META": {e.KEY_LEFTMETA, e.KEY_RIGHTMETA},
}
MODIFIER_CODES = set().union(*MODIFIERS.values())
DEFAULT_TOGGLE = ["CTRL", "KEY_F1"]
DEFAULT_PANIC = ["CTRL", "SHIFT", "KEY_F12"]


class Chord:
    def __init__(self, tokens: list[str]):
        mods = [t for t in tokens if t in MODIFIERS]
        keys = [t for t in tokens if t not in MODIFIERS and name_to_code(t) is not None]
        if not keys:
            raise ValueError(f"hotkey needs one normal key: {tokens}")
        self.mods = mods
        self.key = name_to_code(keys[-1])
        self.tokens = mods + [keys[-1]]

    def matches(self, code: int, held: set[int]) -> bool:
        return code == self.key and all(held & MODIFIERS[m] for m in self.mods)

    def text(self) -> str:
        names = {"CTRL": "Ctrl", "SHIFT": "Shift", "ALT": "Alt", "META": "Super"}
        return " + ".join([names[m] for m in self.mods] + [pretty(code_to_name(self.key))])

    @staticmethod
    def from_capture(code: int, held: set[int]) -> "Chord":
        mods = [m for m, codes in MODIFIERS.items() if held & codes]
        return Chord(mods + [code_to_name(code)])

# Keyboard states shown in the GUI
DISCONNECTED = "disconnected"
FREE = "free"
WAITING = "waiting"        # grab requested, waiting for keys to be released
GRABBED = "grabbed"
ERROR = "error"


@dataclass
class KeyboardView:
    """Read-only snapshot of one keyboard for the GUI."""
    key: str
    name: str
    usb_id: str
    nodes: list[str]
    by_id: str
    present: bool
    state: str
    player: int | None
    last_key: str
    last_key_age: float
    error: str
    hidden: bool
    is_mouse: bool
    port: str = ""


class _Reader:
    """Reads all event nodes of one physical keyboard in its own thread."""

    def __init__(self, engine: "Engine", kb: devices.Keyboard):
        self.engine = engine
        self.kb = kb
        self.devs: list[InputDevice] = []
        self.held: set[int] = set()
        self.grabbed = False
        self.grab_pending = False
        self.alive = False
        self.error = ""
        self.last_key = ""
        self.last_key_time = 0.0
        self.max_held = 0                  # most keys seen down at once (ghosting test)
        self._lock = threading.RLock()
        self._wake_r, self._wake_w = os.pipe()
        self._pipe_open = True
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"kb:{kb.name}", daemon=True)

    # --- lifecycle ---------------------------------------------------------

    def start(self) -> bool:
        for node in self.kb.all_nodes:
            try:
                self.devs.append(InputDevice(node))
            except PermissionError:
                self.error = "E014 permission denied on " + node + " (add yourself to the 'input' group)"
            except OSError as err:
                log.warning("E013 cannot open %s: %s", node, err)
        if not any(d.path in self.kb.nodes for d in self.devs):
            self._close_devs()
            if not self.error:
                self.error = "E013 keyboard nodes could not be opened"
            log.error("%s (%s)", self.error, self.kb.name)
            return False
        self.alive = True
        self.thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            if self._pipe_open:
                try:
                    os.write(self._wake_w, b"x")
                except OSError:
                    pass
        if self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=2)

    def _close_devs(self) -> None:
        with self._lock:
            for d in self.devs:
                if self.grabbed:
                    try:
                        d.ungrab()
                    except OSError:
                        pass
                try:
                    d.close()
                except OSError:
                    pass
            self.devs = []
            self.grabbed = False
            self.grab_pending = False
            if self._pipe_open:
                self._pipe_open = False
                for fd in (self._wake_r, self._wake_w):
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    # --- grab --------------------------------------------------------------

    def request_grab(self) -> None:
        with self._lock:
            if self.grabbed or not self.alive:
                return
            if self.held:
                self.grab_pending = True
                self.engine._changed()
                return
            self._do_grab()

    def _do_grab(self) -> None:
        self.grab_pending = False
        done = []
        try:
            for d in self.devs:
                d.grab()
                done.append(d)
            self.grabbed = True
            self.error = ""
            log.info("grabbed %s", self.kb.name)
        except OSError as err:
            for d in done:
                try:
                    d.ungrab()
                except OSError:
                    pass
            self.error = "E011 grab failed: another program holds this keyboard" if err.errno == errno.EBUSY \
                else f"E011 grab failed: {err}"
            log.error("%s (%s)", self.error, self.kb.name)
            self.engine._message("error", self.error)
        self.engine._changed()

    def release(self) -> None:
        with self._lock:
            self.grab_pending = False
            if self.grabbed:
                for d in self.devs:
                    try:
                        d.ungrab()
                    except OSError:
                        pass
                self.grabbed = False
                log.info("released %s", self.kb.name)
                if self.engine.map_only_when_grabbed:
                    self.engine._clear_source(self.kb.key)
        self.engine._changed()

    # --- event loop --------------------------------------------------------

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                fds = {d.fd: d for d in self.devs}
                ready, _, _ = select.select(list(fds) + [self._wake_r], [], [], 1.0)
                for fd in ready:
                    if fd == self._wake_r:
                        os.read(self._wake_r, 64)
                        continue
                    try:
                        for ev in fds[fd].read():
                            if ev.type == e.EV_KEY:
                                self._on_key(ev.code, ev.value)
                    except BlockingIOError:
                        pass
        except OSError as err:
            if err.errno == errno.ENODEV:
                log.warning("E013 keyboard disconnected: %s", self.kb.name)
            else:
                log.exception("E013 read error on %s", self.kb.name)
                self.error = f"E013 read error: {err}"
        except Exception:
            log.exception("reader crashed for %s", self.kb.name)
            self.error = "E099 internal error, see log"
        finally:
            self.alive = False
            self.engine._clear_source(self.kb.key)
            self._close_devs()
            self.engine._reader_ended(self)

    def _on_key(self, code: int, value: int) -> None:
        engine = self.engine
        if value == 2:                     # autorepeat: no state change
            return
        down = value == 1
        if down:
            self.held.add(code)
            self.max_held = max(self.max_held, len(self.held))
            self.last_key = code_to_name(code)
            self.last_key_time = time.monotonic()
        else:
            self.held.discard(code)

        consumed = False
        if down and engine._offer_capture(self.kb.key, code, self.held):
            consumed = True
        elif down and engine.panic_chord.matches(code, self.held):
            consumed = True
            engine.release_all(source="panic")
        elif down and engine.toggle_chord.matches(code, self.held):
            consumed = True
            engine.toggle_grab(self.kb.key, source="hotkey")

        if not consumed:
            engine._map(self.kb.key, code, down, self.grabbed, self.held)

        if self.grab_pending and not self.held:
            with self._lock:
                if self.grab_pending:
                    self._do_grab()
        if down:
            engine._changed(throttle=True)


class Engine:
    def __init__(self, notify: Callable[..., None] | None = None):
        self._notify = notify or (lambda kind, **kw: None)
        self._lock = threading.RLock()
        self.pads: dict[int, VirtualPad] = {}
        self.pad_error = ""
        self.profiles: dict[int, Profile] = {}
        self._keymaps: dict[int, dict[int, str]] = {}
        self.assignments: dict[str, int] = {}          # keyboard key -> player
        self.known_names: dict[str, str] = {}          # keyboard key -> name (for disconnected rows)
        self.keyboards: dict[str, devices.Keyboard] = {}
        self.readers: dict[str, _Reader] = {}
        self.map_only_when_grabbed = False
        self.toggle_chord = Chord(DEFAULT_TOGGLE)
        self.panic_chord = Chord(DEFAULT_PANIC)
        self.socd: dict[int, str] = {}
        self._capture_active = False
        self._capture_chord = False
        self._capture_result: tuple[str, int, frozenset] | None = None
        self._last_changed = 0.0
        self._dev_signature = None

    # --- notifications -----------------------------------------------------

    def _changed(self, throttle: bool = False) -> None:
        now = time.monotonic()
        if throttle and now - self._last_changed < 0.05:
            return
        self._last_changed = now
        self._notify("changed")

    def _message(self, level: str, text: str) -> None:
        self._notify("message", level=level, text=text)

    # --- pads --------------------------------------------------------------

    def create_pads(self, count: int) -> bool:
        """Create pads P1..Pcount in order. Existing pads are kept (same SDL order)."""
        count = max(1, min(MAX_PLAYERS, count))
        with self._lock:
            for player in sorted(p for p in self.pads if p > count):
                self.pads.pop(player).close()
            try:
                for player in range(1, count + 1):
                    if player not in self.pads:
                        self.pads[player] = VirtualPad(player)
                        self.pads[player].set_socd(self.socd.get(player, "neutral"))
                        time.sleep(0.05)       # settle so SDL enumerates them in order
                self.pad_error = ""
            except PermissionError:
                self.pad_error = "E002 /dev/uinput is not writable (udev rule or 'input' group missing)"
            except FileNotFoundError:
                self.pad_error = "E001 /dev/uinput missing (load the uinput module)"
            except OSError as err:
                self.pad_error = f"E004 pad creation failed: {err}"
            if self.pad_error:
                log.error(self.pad_error)
                self._message("error", self.pad_error)
        self._changed()
        return not self.pad_error

    # --- profiles and assignment -------------------------------------------

    def set_profile(self, player: int, profile: Profile) -> None:
        keymap = {}
        for key, control in profile.all_bindings():     # main and alternate keys
            code = name_to_code(key)
            if code is not None:
                keymap[code] = control
        with self._lock:
            self.profiles[player] = profile
            self._keymaps[player] = keymap
            for kb_key, p in self.assignments.items():
                if p == player:
                    self._clear_source(kb_key)

    def set_socd(self, player: int, mode: str) -> None:
        self.socd[player] = mode
        pad = self.pads.get(player)
        if pad:
            pad.set_socd(mode)

    def set_hotkeys(self, toggle: list[str], panic: list[str]) -> None:
        """Raises ValueError for an invalid chord; the old hotkeys stay active then."""
        t, p = Chord(toggle), Chord(panic)
        self.toggle_chord, self.panic_chord = t, p

    def assign(self, kb_key: str, player: int | None) -> None:
        with self._lock:
            old = self.assignments.get(kb_key)
            if player is None:
                self.assignments.pop(kb_key, None)
                reader = self.readers.get(kb_key)
                if reader and (reader.grabbed or reader.grab_pending):
                    reader.release()
            else:
                self.assignments[kb_key] = player
            if old and old in self.pads:
                self.pads[old].clear_source(kb_key)
            if kb_key in self.keyboards:
                self.known_names[kb_key] = self.keyboards[kb_key].name
        log.info("assigned keyboard to %s", f"P{player}" if player else "nobody")
        self._changed()

    # --- grab --------------------------------------------------------------

    def grab(self, kb_key: str, source: str = "gui") -> None:
        reader = self.readers.get(kb_key)
        if reader is None or not reader.alive:
            self._message("warning", "That keyboard is not connected.")
            return
        if kb_key not in self.assignments:
            self._message("warning", "Assign the keyboard to a player before grabbing it.")
            return
        reader.request_grab()
        self._notify("grab", name=reader.kb.name, grabbed=True, source=source)

    def release(self, kb_key: str, source: str = "gui") -> None:
        reader = self.readers.get(kb_key)
        if reader:
            reader.release()
            self._notify("grab", name=reader.kb.name, grabbed=False, source=source)

    def toggle_grab(self, kb_key: str, source: str = "gui") -> None:
        reader = self.readers.get(kb_key)
        if reader and (reader.grabbed or reader.grab_pending):
            self.release(kb_key, source)
        else:
            self.grab(kb_key, source)

    def release_all(self, source: str = "gui") -> None:
        for reader in list(self.readers.values()):
            reader.release()
        log.info("released all keyboards (%s)", source)
        self._notify("grab", name="all keyboards", grabbed=False, source=source)

    def any_grabbed(self) -> bool:
        return any(r.grabbed or r.grab_pending for r in self.readers.values())

    # --- key capture for remapping -----------------------------------------

    def begin_capture(self, chord: bool = False) -> None:
        """Next key press on any keyboard is captured instead of used.
        chord=True: modifiers alone do not finish the capture (for hotkeys)."""
        with self._lock:
            self._capture_result = None
            self._capture_chord = chord
            self._capture_active = True

    def cancel_capture(self) -> None:
        with self._lock:
            self._capture_active = False
            self._capture_result = None

    def poll_capture(self) -> tuple[str, int, frozenset] | None:
        """(keyboard key, key code, keys held at that moment) or None."""
        with self._lock:
            result, self._capture_result = self._capture_result, None
            if result:
                self._capture_active = False
            return result

    def _offer_capture(self, kb_key: str, code: int, held: set[int]) -> bool:
        with self._lock:
            if not self._capture_active or self._capture_result is not None:
                return False
            if self._capture_chord and code in MODIFIER_CODES:
                return False
            self._capture_result = (kb_key, code, frozenset(held))
        self._notify("captured")
        return True

    # --- ghosting test -----------------------------------------------------

    def held_keys(self, kb_key: str) -> tuple[list[str], int]:
        r = self.readers.get(kb_key)
        if not r:
            return [], 0
        return [code_to_name(c) for c in sorted(r.held)], r.max_held

    def reset_max_held(self, kb_key: str) -> None:
        r = self.readers.get(kb_key)
        if r:
            r.max_held = len(r.held)

    # --- mapping (called from reader threads) ------------------------------

    def _map(self, kb_key: str, code: int, down: bool, grabbed: bool, held: set[int] = frozenset()) -> None:
        player = self.assignments.get(kb_key)
        if player is None:
            return
        if self.map_only_when_grabbed and not grabbed and down:
            return
        keymap = self._keymaps.get(player, {})
        control = keymap.get(code)
        if control and not down and any(keymap.get(c) == control for c in held):
            return                      # the other key for this button is still held
        pad = self.pads.get(player)
        if control and pad:
            try:
                pad.set_control(kb_key, control, down)
            except OSError as err:
                log.error("E004 pad write failed: %s", err)

    def _clear_source(self, kb_key: str) -> None:
        for pad in list(self.pads.values()):
            pad.clear_source(kb_key)

    # --- devices -----------------------------------------------------------

    def rescan(self, force: bool = False) -> bool:
        """Re-read the device list if /dev/input changed. Returns True when something changed."""
        try:
            signature = tuple(sorted(os.listdir("/dev/input")))
        except OSError:
            signature = None
        if not force and signature == self._dev_signature:
            return False
        self._dev_signature = signature
        try:
            found = {kb.key: kb for kb in devices.scan()}
        except Exception:
            log.exception("device scan failed")
            return False
        with self._lock:
            self.keyboards = found
            for key, kb in found.items():
                reader = self.readers.get(key)
                if reader and reader.alive and set(reader.kb.all_nodes) == set(kb.all_nodes):
                    continue
                if reader:
                    reader.stop()
                reader = _Reader(self, kb)
                self.readers[key] = reader
                if reader.start():
                    if key in self.assignments:
                        log.info("keyboard attached for P%d", self.assignments[key])
                        self.known_names[key] = kb.name
                else:
                    self._message("error", f"{kb.name}: {reader.error}")
            for key in [k for k in self.readers if k not in found]:
                self.readers.pop(key).stop()
        self._changed()
        return True

    def _reader_ended(self, reader: _Reader) -> None:
        if reader.kb.key in self.assignments and not reader._stop.is_set():
            self._message("warning", f"{reader.kb.name} disconnected. Its controller stays; plug it back in.")
        self._dev_signature = None          # force a rescan on the next poll
        self._changed()

    def views(self) -> list[KeyboardView]:
        now = time.monotonic()
        rows: list[KeyboardView] = []
        with self._lock:
            for key, kb in self.keyboards.items():
                r = self.readers.get(key)
                if r is None or not r.alive:
                    state = ERROR if r and r.error else DISCONNECTED
                elif r.grabbed:
                    state = GRABBED
                elif r.grab_pending:
                    state = WAITING
                else:
                    state = FREE
                rows.append(KeyboardView(
                    key=key, name=kb.name, usb_id=kb.usb_id, nodes=kb.all_nodes, by_id=kb.by_id,
                    present=True, state=state, player=self.assignments.get(key),
                    last_key=r.last_key if r else "", last_key_age=(now - r.last_key_time) if r and r.last_key_time else 1e9,
                    error=r.error if r else "", hidden=kb.hidden_by_default and key not in self.assignments,
                    is_mouse=kb.is_mouse, port=kb.port))
            for key, player in self.assignments.items():
                if key not in self.keyboards:
                    rows.append(KeyboardView(
                        key=key, name=self.known_names.get(key, key), usb_id="", nodes=[], by_id="",
                        present=False, state=DISCONNECTED, player=player, last_key="", last_key_age=1e9,
                        error="", hidden=False, is_mouse=False))
        return rows

    def pressed(self, player: int) -> set[str]:
        pad = self.pads.get(player)
        return pad.pressed() if pad else set()

    # --- shutdown ----------------------------------------------------------

    def stop(self) -> None:
        with self._lock:
            readers = list(self.readers.values())
            self.readers.clear()
        for r in readers:
            r.stop()
        with self._lock:
            for pad in self.pads.values():
                pad.close()
            self.pads.clear()
        log.info("engine stopped")
