"""Virtual Xbox 360 style gamepad (uinput) and the logic that turns pressed controls into pad state."""

from __future__ import annotations

import logging
import threading

from evdev import AbsInfo, UInput, ecodes as e

from .constants import PAD_NAME, PAD_PHYS, PAD_PRODUCT, PAD_VENDOR, PAD_VERSION

log = logging.getLogger(__name__)

STICK_MIN, STICK_MAX = -32768, 32767

BUTTONS = [e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST, e.BTN_TL, e.BTN_TR,
           e.BTN_SELECT, e.BTN_START, e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR]
BUTTON_IDS = {"BTN_SOUTH": e.BTN_SOUTH, "BTN_EAST": e.BTN_EAST, "BTN_NORTH": e.BTN_NORTH,
              "BTN_WEST": e.BTN_WEST, "BTN_TL": e.BTN_TL, "BTN_TR": e.BTN_TR,
              "BTN_SELECT": e.BTN_SELECT, "BTN_START": e.BTN_START, "BTN_MODE": e.BTN_MODE,
              "BTN_THUMBL": e.BTN_THUMBL, "BTN_THUMBR": e.BTN_THUMBR}

_STICK = AbsInfo(value=0, min=STICK_MIN, max=STICK_MAX, fuzz=16, flat=128, resolution=0)
_TRIGGER = AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
_HAT = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)

CAPABILITIES = {
    e.EV_KEY: BUTTONS,
    e.EV_ABS: [(e.ABS_X, _STICK), (e.ABS_Y, _STICK), (e.ABS_Z, _TRIGGER),
               (e.ABS_RX, _STICK), (e.ABS_RY, _STICK), (e.ABS_RZ, _TRIGGER),
               (e.ABS_HAT0X, _HAT), (e.ABS_HAT0Y, _HAT)],
}

# axis -> (negative control, positive control, minimum, maximum)
AXES = {
    e.ABS_HAT0X: ("DPAD_LEFT", "DPAD_RIGHT", -1, 1),
    e.ABS_HAT0Y: ("DPAD_UP", "DPAD_DOWN", -1, 1),
    e.ABS_X: ("LS_LEFT", "LS_RIGHT", STICK_MIN, STICK_MAX),
    e.ABS_Y: ("LS_UP", "LS_DOWN", STICK_MIN, STICK_MAX),
    e.ABS_RX: ("RS_LEFT", "RS_RIGHT", STICK_MIN, STICK_MAX),
    e.ABS_RY: ("RS_UP", "RS_DOWN", STICK_MIN, STICK_MAX),
}
TRIGGERS = {"ABS_Z": e.ABS_Z, "ABS_RZ": e.ABS_RZ}
VERTICAL = {e.ABS_Y, e.ABS_RY, e.ABS_HAT0Y}

# What happens when both opposite directions are held (SOCD):
SOCD_MODES = {
    "neutral": "Both held = centre (default)",
    "last": "Last pressed wins",
    "hitbox": "Left+Right = centre, Up wins over Down",
}


def compute_state(pressed: set[str], order: dict[str, int] | None = None,
                  socd: str = "neutral") -> dict[tuple[int, int], int]:
    """Pressed control ids -> full pad state {(ev_type, code): value}.
    order: control -> press sequence number (higher = pressed later), used by socd='last'."""
    order = order or {}
    state: dict[tuple[int, int], int] = {}
    for cid, code in BUTTON_IDS.items():
        state[(e.EV_KEY, code)] = 1 if cid in pressed else 0
    for cid, code in TRIGGERS.items():
        state[(e.EV_ABS, code)] = 255 if cid in pressed else 0
    for code, (neg, pos, lo, hi) in AXES.items():
        n, p = neg in pressed, pos in pressed
        if n and p:
            if socd == "last":
                value = lo if order.get(neg, 0) > order.get(pos, 0) else hi
            elif socd == "hitbox" and code in VERTICAL:
                value = lo                      # up wins
            else:
                value = 0
        else:
            value = lo if n else hi if p else 0
        state[(e.EV_ABS, code)] = value
    return state


class VirtualPad:
    """One uinput gamepad. Contributions are tracked per source keyboard so two keyboards
    can share a player and one unplugging never leaves a button stuck."""

    def __init__(self, player: int):
        self.player = player
        self.name = PAD_NAME.format(n=player)
        self._lock = threading.Lock()
        self._sources: dict[str, set[str]] = {}
        self._order: dict[str, int] = {}
        self._seq = 0
        self.socd = "neutral"
        self._state = compute_state(set())
        self._ui = UInput(CAPABILITIES, name=self.name, vendor=PAD_VENDOR, product=PAD_PRODUCT,
                          version=PAD_VERSION, bustype=e.BUS_USB, phys=PAD_PHYS.format(n=player))
        log.info("pad P%d created: %s", player, self.device_path)

    @property
    def device_path(self) -> str:
        dev = getattr(self._ui, "device", None)
        return dev.path if dev is not None else "?"

    def set_control(self, source: str, control: str, down: bool) -> None:
        with self._lock:
            held = self._sources.setdefault(source, set())
            if down:
                if control not in held:
                    self._seq += 1
                    self._order[control] = self._seq
                held.add(control)
            else:
                held.discard(control)
            self._flush()

    def clear_source(self, source: str) -> None:
        with self._lock:
            if self._sources.pop(source, None):
                self._flush()

    def set_socd(self, mode: str) -> None:
        with self._lock:
            self.socd = mode if mode in SOCD_MODES else "neutral"
            self._flush()

    def pressed(self) -> set[str]:
        with self._lock:
            return set().union(*self._sources.values()) if self._sources else set()

    def snapshot(self) -> dict[tuple[int, int], int]:
        with self._lock:
            return dict(self._state)

    def _flush(self) -> None:
        pressed = set().union(*self._sources.values()) if self._sources else set()
        new = compute_state(pressed, self._order, self.socd)
        changed = False
        for key, value in new.items():
            if self._state.get(key) != value:
                self._ui.write(key[0], key[1], value)
                changed = True
        if changed:
            self._ui.syn()
        self._state = new

    def close(self) -> None:
        with self._lock:
            self._sources.clear()
            try:
                self._flush()
                self._ui.close()
            except OSError:
                pass
        log.info("pad P%d closed", self.player)
