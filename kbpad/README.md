# kbpad

Use any USB keyboard as a game controller, one keyboard per player, from one window.
It replaces the old routine of two kb2xbox terminals, Ctrl+F1 in each terminal, then PCSX2.

- Shows every keyboard. Press a key on a keyboard to see which card lights up.
- Choose **Player 1 / Player 2** for each keyboard. Each player gets a virtual Xbox 360 controller (PCSX2 sees it as `SDL-0`, `SDL-1`).
- Default layouts are built in (`Default (P1)`, `Default (P2)`, Xbox and PS2 presets).
- Every key is visible on a controller picture and in a table. Click a button, press a new key, and it's saved.
- **Grab** a keyboard (the desktop stops seeing its keys) with **Ctrl+F1 on that keyboard** or the **Grab / Release** button. **Ctrl+Shift+F12** or **Release all keyboards** frees everything. Both hotkeys can be changed (Settings).
- A **second key** per button, and **Import kb2xbox config** to reuse your old layouts.
- **Opposite directions held** per player: centre, last pressed wins, or hitbox style (for fighting games).
- **Start PCSX2** button (native, Flatpak or AppImage), Flatpak permission fix, **automatic PCSX2 controller setup**, and every keyboard is **released when PCSX2 closes**.
- **Key test** tab (ghosting check), **Keep keyboards awake** fix, System check, log viewer and a diagnostics zip. The log never records typed keys.
- Dark, light or system theme. Opening kbpad again brings the running window forward.

Version 0.2.0. Python only (python-evdev + PySide6). Rust is not needed.
Future features: [docs/06-roadmap.md](docs/06-roadmap.md).

## Install

```fish
cd kbpad
fish install.fish
```

The installer checks `python-evdev` and `pyside6`, `/dev/uinput` access and the `input` group. It asks before every `sudo` command. It then installs to `~/.local` (menu entry **kbpad**, command `kbpad`) and can turn on autostart in the tray.

Remove it with `fish uninstall.fish`.

Run from the source folder without installing: `PYTHONPATH=src python3 -m kbpad`

## Daily use

1. Open **kbpad**. Your keyboards are already set to their players (it remembers them).
2. Click **▶ Start PCSX2**.
3. Start the game and press **Ctrl+F1** on each keyboard (or click **Grab**). The card turns green.
4. When you're done, press **Ctrl+F1** again or click **Release all keyboards**.

First time: PCSX2 tab → **Set up PCSX2 controllers automatically** (with PCSX2 closed). Or by hand in PCSX2: *Settings → Controllers*, Port 1 = `SDL-0`, Port 2 = `SDL-1`, *Automatic Mapping*.

Closing the window keeps kbpad in the tray, so the controllers stay alive. Quit from the tray icon or with *File → Quit*. Quitting, or a crash, always releases the keyboards.

## Command line

| Command | What |
|---|---|
| `kbpad` | Open the app |
| `kbpad --hidden` | Start in the tray |
| `kbpad --list` | List detected keyboards |
| `kbpad --check` | System checks with fix commands |

## Files

| Path | What |
|---|---|
| `src/kbpad/engine.py` | Keyboard readers, grab, Ctrl+F1, virtual pads |
| `src/kbpad/devices.py` | Keyboard detection (groups multi-interface keyboards, hides mice) |
| `src/kbpad/pad.py` | Virtual Xbox 360 controller |
| `src/kbpad/profiles.py` | Controller buttons and key layouts |
| `src/kbpad/gui/` | Window, keyboard cards, controller picture, key-capture dialog, themes |
| `src/kbpad/pcsx2.py` | Find, start and watch PCSX2; write its controller setup |
| `src/kbpad/doctor.py` | System checks |
| `src/kbpad/logsetup.py` | Log, crash reports, diagnostics zip |
| `src/kbpad/data/profiles/` | Built-in layouts |
| `tests/` | `PYTHONPATH=src python3 -m unittest discover -s tests -t .` |
| `scripts/kbpad-probe.fish` | Read-only machine report for troubleshooting |
| `docs/` | All documentation: start at [docs/README.md](docs/README.md) |

## Your files

| Path | What |
|---|---|
| `~/.config/kbpad/config.toml` | Settings and which keyboard is which player |
| `~/.config/kbpad/profiles/player1.toml` … | Each player's current keys; your saved presets also go here |
| `~/.local/state/kbpad/logs/` | Log (rotating, 5 × 2 MB) |
| `~/.local/state/kbpad/crashes/` | Crash reports |
| `~/.local/state/kbpad/backups/` | PCSX2.ini backups made before automatic setup |
