# 01 · Folder and file structure

Everything below is the real content of the `kbpad/` folder (checked against the files on disk).
Cache folders (`__pycache__`) are not listed; they are created automatically by Python and ignored by git.

## Tree

```text
kbpad/
├── README.md                     Short project overview, install, daily use, file list
├── install.fish                  Installer for CachyOS / Arch (fish shell, uses pacman)
├── uninstall.fish                Removes kbpad from your user account
├── pyproject.toml                Python package information (name, version, dependencies, entry point)
├── requirements.txt              Python packages needed to run: evdev, PySide6
├── requirements-dev.txt          Extra packages for tests (none: tests use Python's built-in unittest)
├── .gitignore                    Files git must ignore (caches, build output, diagnostics zips)
├── .git/                         Git history (version control)
│
├── src/kbpad/                    The program
│   ├── __init__.py               Version number (__version__ = "0.2.0")
│   ├── __main__.py               Lets you run `python3 -m kbpad`
│   ├── constants.py              Fixed names and paths: config/log folders, controller ID, max players
│   ├── keynames.py               Turns key codes into names (KEY_A) and short labels (A, L-Shift, Bksp)
│   ├── devices.py                Finds keyboards, groups their event nodes, hides mice, USB port and power info
│   ├── pad.py                    The virtual Xbox 360 controller and the SOCD (opposite direction) logic
│   ├── engine.py                 The core: one reader thread per keyboard, grab, hotkeys, key → controller
│   ├── profiles.py               Controller buttons, key layouts, layout files, second keys, kb2xbox import
│   ├── config.py                 Settings file (~/.config/kbpad/config.toml): read and write
│   ├── pcsx2.py                  Find, start and watch PCSX2; Flatpak permission; write PCSX2 controller setup
│   ├── doctor.py                 System checks (uinput, input group, keyd…) and the keep-awake fix
│   ├── logsetup.py               Log file, crash reports, diagnostics zip
│   ├── data/profiles/            Built-in layouts (read-only)
│   │   ├── default-p1.toml       Default layout for Player 1
│   │   ├── default-p2.toml       Default layout for Player 2
│   │   ├── xbox-360.toml         Same keys as default-p1, Xbox button names
│   │   └── ps2-dualshock2.toml   Same keys as default-p1, PlayStation button names
│   └── gui/                      The window (PySide6 / Qt)
│       ├── __init__.py           Marks the folder as a Python package (empty)
│       ├── app.py                Program start: command-line options, single instance, theme, engine, tray
│       ├── main_window.py        The main window and all tabs
│       ├── widgets.py            Keyboard card, controller picture, key-capture dialog, banner, icons
│       └── theme.py              Dark / light / system colour themes and the style sheet
│
├── tests/                        Automated tests (python3 -m unittest)
│   ├── __init__.py               (empty) marks the folder as a package
│   ├── unit/
│   │   ├── __init__.py           (empty)
│   │   └── test_profiles_and_pad.py   Tests without hardware: layouts, import, SOCD, identity, PCSX2.ini writer
│   └── integration/
│       ├── __init__.py           (empty)
│       └── test_engine_uinput.py      Tests with fake keyboards made through /dev/uinput
│
├── scripts/
│   └── kbpad-probe.fish          Read-only system report → ~/kbpad-probe-report.txt (for troubleshooting)
│
├── packaging/
│   ├── udev/99-kbpad-uinput.rules              udev rule giving you access to /dev/uinput
│   ├── udev/70-kbpad-autosuspend.rules.template Example of the keep-awake rule (the app writes the real one)
│   ├── modules-load.d/kbpad.conf               One line, "uinput": loads the uinput module at boot
│   └── completions/kbpad.fish                  Tab completion for the kbpad command in fish
│
└── docs/                         This documentation (start at docs/README.md)
    ├── README.md                 Index and word list
    ├── 01-folder-structure.md    This file
    ├── 02-user-guide.md          How to use every feature
    ├── 03-setup-new-linux.md     Setup on any Linux distro
    ├── 05-requirements.md        What kbpad needs
    └── 06-roadmap.md             Future features (not built)
```

## What each program file does, in more detail

### `constants.py`
Holds values used everywhere:
- Folders follow the XDG standard: settings in `~/.config/kbpad/`, logs in `~/.local/state/kbpad/`,
  the lock file in `$XDG_RUNTIME_DIR/kbpad.lock` (usually `/run/user/1000/`).
- The controller identity: vendor `0x045E`, product `0x028E`, version `0x110` (a wired Microsoft Xbox 360 controller),
  names `XBOX Controller P1`, `P2`, … and an internal tag `kbpad/pad1`, `kbpad/pad2`, ….
- `MAX_PLAYERS = 4`, `DEFAULT_PLAYERS = 2`, and the PCSX2 Flatpak name `net.pcsx2.PCSX2`.

### `devices.py`
- `scan()` opens every `/dev/input/event*` file, keeps devices that have the keys A, Z, Space and Enter
  (a "full keyboard"), and groups all event nodes of the same physical USB device together.
- A device is treated as a **mouse** (hidden by default) if its name contains "mouse", or it has a pointer
  (moves a cursor) and **no Caps Lock LED**. Real keyboards have that LED; gaming mice with macro keys do not.
- Each keyboard gets a stable **key** (identity) so kbpad remembers its player:
  `id:…` from `/dev/input/by-id` normally, or `path:…` (the USB port) when two identical keyboards have no serial number.
- `power_control()` reads the USB power setting (`on` or `auto`) used by the keep-awake feature.

### `pad.py`
- `VirtualPad` creates one controller through uinput with 11 buttons, 2 sticks, 2 triggers and a D-pad.
- `compute_state()` turns "which buttons are held" into stick/trigger/button values, using the chosen SOCD mode.
- Each keyboard's presses are tracked separately, so a keyboard unplugging never leaves a button stuck.

### `engine.py`
- One **reader thread** per keyboard reads its key events.
- Checks hotkeys first (grab toggle, release all), then turns keys into controller buttons.
- Controllers are created once, in order, and stay until the program quits.
- A grab waits until every key on that keyboard is released (so Ctrl never sticks on the desktop).
- Also: key capture for remapping and hotkeys, "keys held" data for the Key test tab.
- Never writes typed keys to the log.

### `profiles.py`
- `CONTROLS`: the 25 controller inputs kbpad can drive, with PlayStation and Xbox names.
- `Profile`: one layout (main key and optional second key per button). Saved as TOML files.
- `import_kb2xbox()`: converts an old kb2xbox `.cfg` file.

### `config.py`
Reads and writes `~/.config/kbpad/config.toml`: number of players, theme, hotkeys, SOCD per player,
PCSX2 options, which keyboard is which player. A broken file is copied to `config.broken.toml` and defaults are used.

### `pcsx2.py`
Detects PCSX2 (installed package, Flatpak, or your own command), starts it, checks whether it is running
(by looking at running process names), checks and grants the Flatpak device permission,
and writes the controller ports into `PCSX2.ini` (with a backup).

### `doctor.py`
The checks shown on the System check tab and by `kbpad --check`, and the "Keep game keyboards awake" fix.

### `logsetup.py`
Sets up the rotating log file (5 files × 2 MB), writes crash reports, and builds the diagnostics zip.

### `gui/app.py`
Program start. Reads command-line options, makes sure only one kbpad runs (a second start brings the
first window forward), applies the theme, creates the engine and controllers, shows the window,
and quits cleanly on Ctrl+C or SIGTERM.

### `gui/main_window.py`
The window: header, keyboard list, and the tabs Player 1…N, PCSX2, Key test, System check, Log, Settings,
plus the File menu and the tray icon. Also watches PCSX2 every 2 seconds.

### `gui/widgets.py`
`KeyboardCard` (one card per keyboard), `PadView` (the controller picture), `CaptureDialog`
("press a key" window), `Banner` (message strip), and the drawn app icon.

### `gui/theme.py`
Colours for dark, light and "follow system" themes, player colours, and the Qt style sheet.
It also draws small arrow images into `~/.cache/kbpad/` because Qt style sheets cannot draw arrows.

## Files kbpad creates on your PC while running

| Path | What |
|---|---|
| `~/.config/kbpad/config.toml` | Settings and keyboard → player choices |
| `~/.config/kbpad/config.broken.toml` | Only if the settings file was damaged: a copy of the damaged file |
| `~/.config/kbpad/profiles/player1.toml`, `player2.toml`, … | Each player's current keys |
| `~/.config/kbpad/profiles/<name>.toml` | Your saved and imported presets |
| `~/.local/state/kbpad/logs/kbpad.log` (+ `.1` … `.5`) | Log |
| `~/.local/state/kbpad/crashes/crash-<date>.txt` | Crash reports |
| `~/.local/state/kbpad/backups/PCSX2.ini.<date>.bak` | Backup made before the automatic PCSX2 setup |
| `~/.cache/kbpad/arrow-*.png` | Small arrow images for the theme |
| `$XDG_RUNTIME_DIR/kbpad.lock` | Lock file: "kbpad is running" |
| `/etc/udev/rules.d/70-kbpad-autosuspend.rules` | Only if you use "Keep game keyboards awake" (needs your password) |

## Files the installer creates (install.fish)

| Path | What |
|---|---|
| `~/.local/share/kbpad/kbpad/` | Copy of `src/kbpad` |
| `~/.local/bin/kbpad` | Launcher script (runs `python3 -m kbpad`) |
| `~/.local/share/applications/kbpad.desktop` | App menu entry |
| `~/.config/autostart/kbpad.desktop` | Only if you answered yes to autostart (starts with `--hidden`) |
| `~/.config/fish/completions/kbpad.fish` | Tab completion |
| `/etc/udev/rules.d/99-kbpad-uinput.rules` | Only if `/dev/uinput` was not writable and you agreed |
| `/etc/modules-load.d/uinput.conf` | Only if `/dev/uinput` was missing and you agreed |
