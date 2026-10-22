"""Paths, IDs and fixed names used across kbpad."""

import os
from pathlib import Path

APP_NAME = "kbpad"

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
BUILTIN_PROFILES_DIR = DATA_DIR / "profiles"

_xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
_xdg_state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
_xdg_runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/kbpad-{os.getuid()}"))

CONFIG_DIR = _xdg_config / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.toml"
USER_PROFILES_DIR = CONFIG_DIR / "profiles"
STATE_DIR = _xdg_state / APP_NAME
LOG_DIR = STATE_DIR / "logs"
LOG_FILE = LOG_DIR / "kbpad.log"
CRASH_DIR = STATE_DIR / "crashes"
LOCK_FILE = _xdg_runtime / "kbpad.lock"

# Virtual pad identity: Microsoft Xbox 360 controller, so SDL (PCSX2) maps it automatically.
PAD_VENDOR = 0x045E
PAD_PRODUCT = 0x028E
PAD_VERSION = 0x110
PAD_NAME = "XBOX Controller P{n}"
PAD_PHYS = "kbpad/pad{n}"

MAX_PLAYERS = 4
DEFAULT_PLAYERS = 2

PCSX2_FLATPAK_ID = "net.pcsx2.PCSX2"
