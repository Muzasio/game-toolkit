"""App settings and keyboard assignments (~/.config/kbpad/config.toml)."""

from __future__ import annotations

import logging
import shutil
import tomllib
from dataclasses import dataclass, field

from .constants import CONFIG_DIR, CONFIG_FILE, DEFAULT_PLAYERS, MAX_PLAYERS

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass
class Assignment:
    key: str
    player: int
    name: str = ""


@dataclass
class Settings:
    players: int = DEFAULT_PLAYERS
    map_only_when_grabbed: bool = False
    close_to_tray: bool = True
    pcsx2_mode: str = "auto"          # auto | flatpak | native | custom
    pcsx2_command: str = ""           # used when mode = custom
    sdl_hidapi_off: bool = False
    release_on_pcsx2_exit: bool = True
    theme: str = "dark"               # dark | light | system
    hotkey_toggle: list[str] = field(default_factory=lambda: ["CTRL", "KEY_F1"])
    hotkey_panic: list[str] = field(default_factory=lambda: ["CTRL", "SHIFT", "KEY_F12"])
    socd: dict[int, str] = field(default_factory=dict)       # player -> neutral | last | hitbox
    presets: dict[int, str] = field(default_factory=dict)   # player -> preset the player started from
    assignments: list[Assignment] = field(default_factory=list)


def load() -> Settings:
    s = Settings()
    if not CONFIG_FILE.exists():
        return s
    try:
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as err:
        backup = CONFIG_FILE.with_suffix(".broken.toml")
        shutil.copy2(CONFIG_FILE, backup)
        log.error("E020 config unreadable (%s); using defaults, copy kept at %s", err, backup)
        return s
    if data.get("schema_version", 1) > SCHEMA_VERSION:
        log.error("E021 config schema is newer than this app; using defaults")
        return s
    g = data.get("general", {})
    s.players = max(1, min(MAX_PLAYERS, int(g.get("players", s.players))))
    s.map_only_when_grabbed = bool(g.get("map_only_when_grabbed", s.map_only_when_grabbed))
    s.close_to_tray = bool(g.get("close_to_tray", s.close_to_tray))
    if g.get("theme") in ("dark", "light", "system"):
        s.theme = g["theme"]
    h = data.get("hotkeys", {})
    for name in ("toggle", "panic"):
        value = h.get(name)
        if isinstance(value, list) and value and all(isinstance(t, str) for t in value):
            setattr(s, f"hotkey_{name}", value)
    for k, v in data.get("socd", {}).items():
        if k.startswith("p") and k[1:].isdigit() and v in ("neutral", "last", "hitbox"):
            s.socd[int(k[1:])] = v
    p = data.get("pcsx2", {})
    s.pcsx2_mode = p.get("mode", s.pcsx2_mode) if p.get("mode") in ("auto", "flatpak", "native", "custom") else "auto"
    s.pcsx2_command = str(p.get("command", ""))
    s.sdl_hidapi_off = bool(p.get("sdl_hidapi_off", False))
    s.release_on_pcsx2_exit = bool(p.get("release_on_exit", True))
    for k, v in data.get("presets", {}).items():
        if k.startswith("p") and k[1:].isdigit():
            s.presets[int(k[1:])] = str(v)
    for a in data.get("assignment", []):
        try:
            s.assignments.append(Assignment(key=str(a["key"]), player=int(a["player"]), name=str(a.get("name", ""))))
        except (KeyError, ValueError, TypeError):
            log.warning("skipped bad assignment entry in config")
    return s


def _q(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _b(v: bool) -> str:
    return "true" if v else "false"


def _list(v: list[str]) -> str:
    return "[" + ", ".join(_q(x) for x in v) + "]"


def save(s: Settings) -> None:
    lines = [f"schema_version = {SCHEMA_VERSION}", "",
             "[general]", f"players = {s.players}",
             f"map_only_when_grabbed = {_b(s.map_only_when_grabbed)}",
             f"close_to_tray = {_b(s.close_to_tray)}",
             f"theme = {_q(s.theme)}", "",
             "[hotkeys]", f"toggle = {_list(s.hotkey_toggle)}", f"panic = {_list(s.hotkey_panic)}", "",
             "[pcsx2]", f"mode = {_q(s.pcsx2_mode)}", f"command = {_q(s.pcsx2_command)}",
             f"sdl_hidapi_off = {_b(s.sdl_hidapi_off)}",
             f"release_on_exit = {_b(s.release_on_pcsx2_exit)}", "",
             "[socd]"]
    lines += [f"p{n} = {_q(v)}" for n, v in sorted(s.socd.items())]
    lines += ["", "[presets]"]
    lines += [f"p{n} = {_q(v)}" for n, v in sorted(s.presets.items())]
    for a in s.assignments:
        lines += ["", "[[assignment]]", f"key = {_q(a.key)}", f"player = {a.player}", f"name = {_q(a.name)}"]
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n")
    tmp.replace(CONFIG_FILE)
