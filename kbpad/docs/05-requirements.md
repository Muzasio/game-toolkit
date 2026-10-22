# 05 · Requirements

## 1. Features in version 0.2.0

| # | Feature | How it works |
|---|---|---|
| 1 | Full GUI | PySide6 window: keyboard cards, player tabs with controller picture and key table, PCSX2, Key test, System check, Log and Settings tabs, tray icon |
| 2 | Easy installation | `install.fish` for CachyOS/Arch (checks and installs everything, asks before `sudo`); a bash guide for other distros ([03-setup-new-linux.md](03-setup-new-linux.md)) |
| 3 | Keyboards found automatically | Every keyboard is detected; no fixed list is needed |
| 4 | Ready-made layouts | Built-in layouts `Default (P1)` and `Default (P2)` |
| 5 | Xbox and PlayStation setups | `Xbox 360 preset`, `PS2 DualShock 2 preset`, and a PlayStation/Xbox button-name switch on every player tab |
| 6 | Error handling and log collection | Error codes, per-keyboard fault isolation, rotating log, crash reports, diagnostics zip, System check |
| 7 | Grab with Ctrl+F1 **and** a GUI button, no terminal | Both; the hotkey is read from each keyboard directly, and it can be changed |

Also in 0.2.0: changeable hotkeys, opposite-direction (SOCD) modes, release when PCSX2 closes,
keep-awake fix, automatic PCSX2 controller setup, restart warnings, single instance, second key per button,
Key test (ghosting), identical-keyboard support, kb2xbox import, colour themes.
Not built yet: mouse aiming and an emulators tab ([06-roadmap.md](06-roadmap.md)).

## 2. System requirements

| Item | Requirement | How to check |
|---|---|---|
| OS | Linux with a desktop, systemd and udev | |
| Kernel module | `uinput` loaded (creates the virtual controllers) | `ls -l /dev/uinput` |
| Device access | `/dev/uinput` writable by you | `kbpad --check` |
| Group | You are in `input` **in the current login** (to read keyboards) | `id` |
| Display | Wayland or X11 (both work; tested on KDE Wayland) | `echo $XDG_SESSION_TYPE` |
| Tray | Needed for "close to tray" (KDE has one) | |
| Shell | fish for `install.fish` and `scripts/kbpad-probe.fish`; bash for the generic setup guide | |

## 3. Software

### Python
Python **3.12 or newer** (declared in `pyproject.toml`). Tested with **Python 3.14.7** only.

### Python packages (from `requirements.txt`)

| Package | Why | Arch package | Versions tested |
|---|---|---|---|
| `evdev` | Read and grab keyboards, create virtual controllers (uinput) | `python-evdev` | 2.0.0 (pacman and pip) |
| `PySide6` | The window, tray icon, single-instance socket | `pyside6` | 6.11.2 (pacman), 6.12.0 (`PySide6-Essentials` from pip) |

`PySide6-Essentials` is enough (kbpad uses QtCore, QtGui, QtWidgets and QtNetwork only).
Nothing else is needed: settings use Python's built-in `tomllib`, and the tests use the built-in `unittest`.

### Build tools (only for the pip / venv install)
`evdev` is compiled during `pip install`. It needs a C compiler, Python development headers and the Linux
input headers. On Arch/CachyOS these come from `base-devel`, `python` and `linux-api-headers`.

### Optional

| Package | Why |
|---|---|
| `flatpak` | Only if PCSX2 is installed as a Flatpak |
| `pkexec` (polkit) | Password window for "Keep game keyboards awake"; without it kbpad gives you a `sudo` command instead |
| `evtest` | Manual input debugging (not used by kbpad) |

## 4. Hardware

- One keyboard per player (USB or laptop keyboard). Each must have A, Z, Space and Enter to be detected.
- A way to type while keyboards are grabbed: a spare keyboard, or the release hotkeys (Ctrl+F1 / Ctrl+Shift+F12).

## 5. PCSX2

- Any build: installed package (`pcsx2-qt` or `pcsx2` in `PATH`), Flatpak (`net.pcsx2.PCSX2`, needs device access),
  or an AppImage / custom command.
- Start PCSX2 **after** kbpad, so the controllers already exist (the **Start PCSX2** button does this).
- For the automatic controller setup: PCSX2 must have been started once (so `PCSX2.ini` exists) and be closed.

## 6. Functional requirements (what the program does)

| ID | Requirement | Status |
|---|---|---|
| F1 | Detect all keyboards, including after plugging in or out (checked every 1.5 s) | Done |
| F2 | Group all event nodes of one physical keyboard; hide mice and virtual devices by default | Done |
| F3 | Assign any keyboard to Player 1–4; remember the choice | Done |
| F4 | One virtual Xbox 360 controller per player, created once and in order | Done |
| F5 | Grab/release per keyboard by hotkey and by button; release all | Done |
| F6 | Grab waits for all keys to be released (no stuck keys) | Done |
| F7 | Changeable hotkeys | Done |
| F8 | Layouts: built-in presets, save as, delete, load, import kb2xbox | Done |
| F9 | Change any key by pressing it (works while grabbed); second key per button | Done |
| F10 | Live controller picture and key table | Done |
| F11 | Opposite-direction (SOCD) mode per player | Done |
| F12 | Key test for ghosting | Done |
| F13 | PCSX2: detect, start, Flatpak permission, automatic controller setup, watch, release on exit, restart warnings | Done |
| F14 | System checks with fix commands; keep-awake fix | Done |
| F15 | Log, crash reports, diagnostics zip | Done |
| F16 | Themes (dark, light, system); tray; single instance | Done |
| F17 | Command line: `--list`, `--check`, `--hidden`, `--debug`, `--version` | Done |

## 7. Non-functional requirements

| Requirement | How it is met |
|---|---|
| Never lock you out of a keyboard | Hotkeys, Release all, release on PCSX2 exit, release on quit; Linux drops the grab if kbpad dies |
| A broken keyboard must not break the others | Each keyboard has its own reader thread with its own error handling |
| Controllers must not change order | Created once at start, in order; unplugging a keyboard keeps its controller |
| Privacy | No network code in kbpad itself (except starting `flatpak` commands locally); typed keys are never logged; diagnostics stay on your PC and mask your username |
| No root | kbpad runs as your user; `sudo`/password only for one-time system setup |
| Damaged files must not crash kbpad | Bad settings → defaults plus a backup copy; bad layout files → skipped with a log line |
