"""Find and launch PCSX2 (native, Flatpak or a custom command)."""

from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .constants import PCSX2_FLATPAK_ID, STATE_DIR

log = logging.getLogger(__name__)


@dataclass
class Pcsx2Install:
    kind: str            # "flatpak" | "native" | "custom" | "none"
    command: list[str]
    detail: str


def _flatpak_installed() -> bool:
    if not shutil.which("flatpak"):
        return False
    try:
        out = subprocess.run(["flatpak", "info", PCSX2_FLATPAK_ID], capture_output=True, text=True, timeout=10)
        return out.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _native_binary() -> str | None:
    for name in ("pcsx2-qt", "pcsx2", "PCSX2"):
        path = shutil.which(name)
        if path:
            return path
    return None


def detect(mode: str = "auto", custom: str = "") -> Pcsx2Install:
    if mode == "custom":
        if custom.strip():
            return Pcsx2Install("custom", shlex.split(custom), custom)
        return Pcsx2Install("none", [], "Custom command is empty")
    if mode in ("auto", "native"):
        native = _native_binary()
        if native:
            return Pcsx2Install("native", [native], native)
        if mode == "native":
            return Pcsx2Install("none", [], "pcsx2-qt not found in PATH")
    if mode in ("auto", "flatpak") and _flatpak_installed():
        return Pcsx2Install("flatpak", ["flatpak", "run", PCSX2_FLATPAK_ID], f"Flatpak {PCSX2_FLATPAK_ID}")
    return Pcsx2Install("none", [], "PCSX2 not found (install the Flatpak or pcsx2 package, or set a custom command)")


def flatpak_has_device_access() -> bool | None:
    """None = cannot tell. True when the Flatpak may see /dev/input devices."""
    try:
        user = subprocess.run(["flatpak", "override", "--user", "--show", PCSX2_FLATPAK_ID],
                              capture_output=True, text=True, timeout=10).stdout
        meta = subprocess.run(["flatpak", "info", "--show-permissions", PCSX2_FLATPAK_ID],
                              capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for text in (user, meta):
        for line in text.splitlines():
            if line.strip().startswith("devices=") and ("all" in line or "input" in line):
                if "!all" not in line:
                    return True
    return False


def grant_flatpak_device_access() -> tuple[bool, str]:
    cmd = ["flatpak", "override", "--user", "--device=all", PCSX2_FLATPAK_ID]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, str(err)
    log.info("applied flatpak device override (rc=%s)", out.returncode)
    return out.returncode == 0, (out.stderr or out.stdout).strip()


def launch(install: Pcsx2Install, hidapi_off: bool) -> subprocess.Popen:
    env = dict(os.environ)
    if hidapi_off:
        env["SDL_JOYSTICK_HIDAPI"] = "0"
    log.info("launching PCSX2 (%s, hidapi_off=%s)", install.kind, hidapi_off)
    return subprocess.Popen(install.command, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


# --- is PCSX2 running? -------------------------------------------------------

_PROCESS_NAMES = {"pcsx2-qt", "pcsx2", "PCSX2", "pcsx2-qt.AppImage"}


def running_pids() -> list[int]:
    """PIDs of running PCSX2 processes (native, Flatpak or AppImage: all visible in /proc)."""
    pids = []
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            with open(f"/proc/{entry.name}/comm") as f:
                comm = f.read().strip()
        except OSError:
            continue
        if comm in _PROCESS_NAMES or comm.lower().startswith("pcsx2"):
            pids.append(int(entry.name))
    return pids


def is_running() -> bool:
    return bool(running_pids())


# --- PCSX2.ini controller setup ----------------------------------------------

INI_PATHS = {
    "native": Path.home() / ".config/PCSX2/inis/PCSX2.ini",
    "flatpak": Path.home() / ".var/app" / PCSX2_FLATPAK_ID / "config/PCSX2/inis/PCSX2.ini",
}

# DualShock 2 binding -> SDL control. Two naming styles exist:
#   new (SDL3 builds, 2025+): FaceSouth, FaceEast, ...    old (SDL2 builds): A, B, ...
_DS2 = [
    ("Up", "DPadUp"), ("Right", "DPadRight"), ("Down", "DPadDown"), ("Left", "DPadLeft"),
    ("Triangle", "@north"), ("Circle", "@east"), ("Cross", "@south"), ("Square", "@west"),
    ("Select", "Back"), ("Start", "Start"), ("L1", "LeftShoulder"), ("L2", "+LeftTrigger"),
    ("R1", "RightShoulder"), ("R2", "+RightTrigger"), ("L3", "LeftStick"), ("R3", "RightStick"),
    ("Analog", "Guide"),
    ("LUp", "-LeftY"), ("LRight", "+LeftX"), ("LDown", "+LeftY"), ("LLeft", "-LeftX"),
    ("RUp", "-RightY"), ("RRight", "+RightX"), ("RDown", "+RightY"), ("RLeft", "-RightX"),
]
_FACE = {"new": {"@south": "FaceSouth", "@east": "FaceEast", "@west": "FaceWest", "@north": "FaceNorth"},
         "old": {"@south": "A", "@east": "B", "@west": "X", "@north": "Y"}}


class IniError(Exception):
    pass


def find_ini(kind: str) -> Path | None:
    """PCSX2.ini for this install kind; any existing one when unknown."""
    if kind in INI_PATHS and INI_PATHS[kind].exists():
        return INI_PATHS[kind]
    for path in INI_PATHS.values():
        if path.exists():
            return path
    return None


def detect_style(text: str) -> str | None:
    if "/FaceSouth" in text or "/FaceEast" in text:
        return "new"
    if re.search(r"SDL-\d+/[ABXY]\s*$", text, re.M):
        return "old"
    return None


def build_pad_bindings(sdl_index: int, style: str) -> list[tuple[str, str]]:
    out = [("Type", "DualShock2")]
    for name, control in _DS2:
        control = _FACE[style].get(control, control)
        out.append((name, f"SDL-{sdl_index}/{control}"))
    return out


def _set_section(lines: list[str], section: str, values: list[tuple[str, str]], replace: bool) -> list[str]:
    """Set keys in [section]. replace=True drops the section's old keys first."""
    start = next((i for i, l in enumerate(lines) if l.strip() == f"[{section}]"), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"[{section}]")
        lines += [f"{k} = {v}" for k, v in values]
        return lines
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    body = lines[start + 1:end]
    if replace:
        trailing_blank = bool(body) and not body[-1].strip()
        new_body = [f"{k} = {v}" for k, v in values] + ([""] if trailing_blank else [])
    else:
        new_body = list(body)
        for k, v in values:
            idx = next((i for i, l in enumerate(new_body) if l.split("=", 1)[0].strip() == k), None)
            if idx is None:
                insert_at = len(new_body)
                while insert_at > 0 and not new_body[insert_at - 1].strip():
                    insert_at -= 1
                new_body.insert(insert_at, f"{k} = {v}")
            else:
                new_body[idx] = f"{k} = {v}"
    return lines[:start + 1] + new_body + lines[end:]


def write_controller_setup(ini: Path, players: int, style: str | None = None,
                           backup_dir: Path | None = None) -> tuple[Path, str]:
    """Port N = DualShock 2 on SDL-(N-1) for N in 1..players. Backs up the file first.
    Returns (backup path, style used). Refuses while PCSX2 runs (it rewrites the file on exit)."""
    if is_running():
        raise IniError("Close PCSX2 first: it saves its settings on exit and would undo this.")
    try:
        text = ini.read_text()
    except OSError as err:
        raise IniError(f"Cannot read {ini}: {err}") from err
    if "[" not in text:
        raise IniError(f"{ini.name} does not look like a PCSX2 settings file (E032)")
    style = style or detect_style(text) or "new"
    backup_dir = backup_dir or (STATE_DIR / "backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"PCSX2.ini.{datetime.now():%Y%m%d-%H%M%S}.bak"
    backup.write_text(text)
    lines = text.splitlines()
    lines = _set_section(lines, "InputSources", [("SDL", "true")], replace=False)
    for n in range(1, players + 1):
        lines = _set_section(lines, f"Pad{n}", build_pad_bindings(n - 1, style), replace=False)
    tmp = ini.with_suffix(".kbpad.tmp")
    tmp.write_text("\n".join(lines) + "\n")
    tmp.replace(ini)
    log.info("wrote PCSX2 controller setup for %d players (%s names), backup %s", players, style, backup.name)
    return backup, style
