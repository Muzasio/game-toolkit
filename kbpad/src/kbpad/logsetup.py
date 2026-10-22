"""Logging, crash reports and the diagnostics bundle. Everything stays on this machine."""

from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import subprocess
import sys
import threading
import traceback
import zipfile
from datetime import datetime
from pathlib import Path

from . import __version__
from .constants import CONFIG_DIR, CRASH_DIR, LOG_DIR, LOG_FILE

log = logging.getLogger("kbpad")

_crash_callback = None


def setup(debug: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    try:
        fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=5)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as err:
        print(f"kbpad: cannot write log file: {err}", file=sys.stderr)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    sys.excepthook = _excepthook
    threading.excepthook = lambda a: _excepthook(a.exc_type, a.exc_value, a.exc_traceback)
    log.info("kbpad %s starting (python %s, kernel %s)", __version__, platform.python_version(), platform.release())


def on_crash(callback) -> None:
    """GUI registers a callback(text, path) to show a dialog."""
    global _crash_callback
    _crash_callback = callback


def _excepthook(exc_type, exc, tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        return
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    log.critical("uncaught exception:\n%s", text)
    path = None
    try:
        CRASH_DIR.mkdir(parents=True, exist_ok=True)
        path = CRASH_DIR / f"crash-{datetime.now():%Y%m%d-%H%M%S}.txt"
        tail = ""
        if LOG_FILE.exists():
            tail = "".join(LOG_FILE.read_text(errors="replace").splitlines(True)[-200:])
        path.write_text(f"kbpad {__version__}\n{platform.platform()}\n\n{text}\n--- last log lines ---\n{tail}")
    except OSError:
        pass
    if _crash_callback:
        try:
            _crash_callback(text, path)
        except Exception:
            pass


def _cmd(args: list[str]) -> str:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return f"$ {' '.join(args)}\n{out.stdout}{out.stderr}\n"
    except (OSError, subprocess.TimeoutExpired) as err:
        return f"$ {' '.join(args)}\n{err}\n"


def export_bundle(dest_dir: Path, redact: bool = True) -> Path:
    """Zip of logs, crash reports, config and system info. Username is masked when redact=True."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"kbpad-diagnostics-{datetime.now():%Y%m%d-%H%M%S}.zip"
    user = os.environ.get("USER", "")

    def clean(text: str) -> str:
        return text.replace(user, "<user>") if redact and user else text

    info = [f"kbpad {__version__}", platform.platform(), f"python {platform.python_version()}",
            f"session={os.environ.get('XDG_SESSION_TYPE')} desktop={os.environ.get('XDG_CURRENT_DESKTOP')}", ""]
    info += [_cmd(["id"]), _cmd(["ls", "-l", "/dev/uinput"]), _cmd(["ls", "-l", "/dev/input/by-id/"]),
             _cmd(["cat", "/proc/bus/input/devices"]), _cmd(["pacman", "-Q", "python-evdev", "pyside6"]),
             _cmd(["flatpak", "list", "--app"])]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system.txt", clean("\n".join(info)))
        for folder, arc in ((LOG_DIR, "logs"), (CRASH_DIR, "crashes"), (CONFIG_DIR, "config")):
            if folder.is_dir():
                for f in sorted(folder.rglob("*")):
                    if f.is_file():
                        z.writestr(f"{arc}/{f.relative_to(folder)}", clean(f.read_text(errors="replace")))
    log.info("diagnostics bundle written")
    return path
