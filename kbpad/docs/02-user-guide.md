# 02 · User guide: every feature

This guide follows the window from top to bottom, then covers hotkeys, the tray, the command line and files.

---

## 1. The idea in 30 seconds

1. kbpad creates virtual **Xbox 360 controllers**: one per player (`XBOX Controller P1`, `XBOX Controller P2`, …).
   They exist as long as kbpad runs, even with the window closed to the tray.
2. You choose which **keyboard** is which **player**.
3. Keys pressed on that keyboard press buttons on that player's controller.
4. You **grab** the keyboard so the desktop (and PCSX2's own keyboard input) stop seeing its keys.
5. Games and emulators see normal controllers.

Daily routine:

1. Open kbpad (or it is already in the tray if you enabled autostart).
2. Click **▶ Start PCSX2**.
3. In the game, press **Ctrl+F1** on each keyboard (or click **Grab** on its card).
4. Close PCSX2 when done: every keyboard is released automatically.

---

## 2. The header (top bar)

| Part | What it shows / does |
|---|---|
| kbpad logo and title | Just the name |
| Player status, e.g. `● P1 grabbed  ● P2 ready` | One entry per controller, in the player's colour. **grabbed** = a keyboard for this player is grabbed; **ready** = a keyboard is set but not grabbed; **no keyboard** = nothing set yet. If the controllers could not be created, this area shows the error instead (E001/E002/E004) |
| `PCSX2 running` chip | Appears while PCSX2 is running (checked every 2 seconds) |
| **Release all keyboards** | Releases every grabbed keyboard. It turns **red** while any keyboard is grabbed |
| **▶ Start PCSX2** | Starts PCSX2 (same as the button in the PCSX2 tab). Greyed out if PCSX2 was not found |

Player colours: **P1 blue, P2 red, P3 green, P4 pink**. They are used on cards, tabs and the controller picture.

### The message strip (banner)
A coloured strip under the header shows important messages: setup problems (red), "restart PCSX2" warnings
(yellow, code W020) and errors. Click **✕** to hide it.

---

## 3. Keyboards panel (left side)

The text at the top reminds you of the current hotkeys.

### One card per keyboard

| Part of the card | Meaning |
|---|---|
| ⌨ Name | The name the keyboard reports, e.g. `COMPANY  USB Device` (the Bloody). 🖱 means it was detected as a mouse |
| Last-key chip | The last key pressed on this keyboard. It flashes purple for 0.6 s and disappears after 5 s. **Use it to find out which card is which keyboard**: press a key and see which card lights up |
| State chip | `Not grabbed`, `Let go of all keys…` (grab is waiting), `● GRABBED`, `Disconnected`, or `Error` |
| `USB 09da:fa28` | USB vendor:product ID |
| `USB port 3` | Shown only when two keyboards of the same model are connected, so you can tell them apart |
| ⚠ line | An error for this keyboard (for example E011 or E014), if any |
| **Player dropdown** | `Not used`, `Player 1`, `Player 2`, … Choosing a player is saved at once and remembered next time |
| **Grab / Release** | Grabs or releases this keyboard. Disabled until you choose a player |

The card's left stripe takes the player's colour. A grabbed keyboard gets a green outline.

A keyboard that is set to a player but unplugged keeps its card with **Disconnected** and the text
"Plug this keyboard back in. Its controller stays ready." To forget it, set it to **Not used**.

### Show mice and virtual devices
Tick this to also show devices hidden by default: mice that report keys (gaming mice with macro buttons)
and virtual keyboards (for example `keyd virtual keyboard`). Normally you never need it.

### Notes
- Two keyboards can be set to the same player; both then drive that one controller.
- By default keys reach the controller **even when the keyboard is not grabbed** (you can change this in Settings).

---

## 4. Player tabs (Player 1, Player 2, …)

Each player has a tab with a coloured dot. Everything you change here is **saved immediately** in
`~/.config/kbpad/profiles/playerN.toml`.

### Top row: presets

| Control | What it does |
|---|---|
| **Preset** dropdown | Lists built-in presets (`Default (P1)`, `Default (P2)`, `Xbox 360 preset`, `PS2 DualShock 2 preset`) and your own ones (marked "(yours)") |
| **Load preset** | Replaces this player's keys with the selected preset (asks first) |
| **Save as preset…** | Saves this player's current keys as a new preset with a name you type. Names starting with "player" and the built-in names are reserved |
| **Delete preset** | Deletes the selected preset if it is yours. Built-in presets cannot be deleted |
| **Import kb2xbox config…** | Opens an old kb2xbox `.cfg` file (the dialog starts in `~/kb2xbox`). Shows how many buttons were found and any lines it skipped. The layout is always saved as a preset called `kb2xbox <file name>`; answer **Yes** to also use it for this player now |

How the kb2xbox import reads lines like `ABS_X=KEY_A,KEY_D`: the **first key is the negative direction**
(left or up), the last key is the positive direction (right or down). This matches how kb2xbox itself works.
For a button line with two keys, the second key becomes the "second key". For trigger lines, the last key is used.
`NAME`, `VENDOR`, `PRODUCT` and `VERSION` lines are ignored.

### Second row

| Control | What it does |
|---|---|
| **Button names** | `PlayStation names` (Cross, Circle, L1…) or `Xbox names` (A, B, LB…). Only changes the labels, not the controller |
| **Opposite directions held** | What happens when two opposite directions are held at the same time (for the D-pad and both sticks): **Both held = centre (default)**; **Last pressed wins**; **Left+Right = centre, Up wins over Down** (hitbox style). Fighting games often feel best with *Last pressed wins*. Saved per player |

Below that, a line shows which keyboard is set to this player.

### Controller picture
- Shows every button with its key. Face buttons use PlayStation colours (△ green, ○ red, ✕ blue, □ pink)
  or Xbox colours (Y yellow, B red, A green, X blue), depending on **Button names**.
- Buttons **light up live** when you press their keys; the stick dot moves.
- **Click any button** (or a stick direction label, or the stick itself for L3/R3) to change its key.

### Key table
One row per controller input (25 rows): Group, Controller button, **Key**, **Second key**, and three buttons:

| Button | What it does |
|---|---|
| **Key** | Set the main key: a window opens, press the key you want on any keyboard |
| **2nd** | Set a second key that does the same thing as the main key |
| **Clear** | Remove both keys from this button |

Double-click a row to change the main key, or double-click the **Second key** cell to change the second key.

### The "press a key" window
- Press the key on **any** keyboard kbpad can see. It works even while the keyboard is grabbed.
- **Every** key can be used, including Esc and Enter, so cancel with the mouse: **Cancel**.
- **Unbind** removes the key from this slot. Unbinding a main key moves the second key up to main, if there is one.
- A key can belong to **one** button only. If it was used elsewhere, it moves, and the status bar tells you
  which button lost it.
- If the key is the main key of a hotkey (F1 / F12 by default), kbpad tells you: it still works as a button,
  but pressed together with the hotkey's modifiers it grabs/releases instead.

### Default layouts

| Button (PS / Xbox) | Default (P1) | Default (P2) |
|---|---|---|
| Cross ✕ / A | K | 8 |
| Circle ○ / B | L | 9 |
| Square □ / X | J | 0 |
| Triangle △ / Y | I | 7 |
| L1 / LB | Q | U |
| R1 / RB | E | O |
| L2 / LT | Left Shift | 6 |
| R2 / RT | Space | - (minus) |
| D-pad Up / Down / Left / Right | ↑ ↓ ← → | T G F H |
| Left stick Up / Down / Left / Right | W S A D | I K J L |
| Select / Back | Backspace | Right Ctrl |
| Start | Enter | Right Shift |
| L3, R3, right stick, PS/Guide | not set | not set |

`Xbox 360 preset` and `PS2 DualShock 2 preset` use the same keys as `Default (P1)`; only the button names differ.
The P2 D-pad keys (T G F H) were a guess; import your old kb2xbox P2 file to get your real keys.

---

## 5. PCSX2 tab

### Start panel

| Control | What it does |
|---|---|
| **Found** | What kbpad found: `native` (installed package `pcsx2-qt` or `pcsx2`), `flatpak` (`net.pcsx2.PCSX2`), `custom`, or a red "not found" message |
| **Start using** | `Automatic` (installed package first, then Flatpak), `Flatpak`, `Installed package`, `Custom command / AppImage` |
| **Custom command** + **Browse…** | Only active in *Custom* mode. Type a command or choose a file (for example an AppImage). Browse switches the mode to Custom |
| **Start with SDL_JOYSTICK_HIDAPI=0** | Starts PCSX2 with this setting. Try it only if PCSX2 does not list the controllers |
| **Flatpak access** | For the Flatpak: `✔ allowed` or `✘ not allowed`. **Allow PCSX2 Flatpak to see controllers** runs `flatpak override --user --device=all net.pcsx2.PCSX2` (no password needed) |
| **▶ Start PCSX2** | Starts PCSX2. It refuses if the controllers do not exist, says so if PCSX2 is already running, asks if no keyboard is set to a player, and offers the Flatpak permission if it is missing |

### Controller setup inside PCSX2
**Set up PCSX2 controllers automatically** writes the controller ports into `PCSX2.ini`:
Port 1 = DualShock 2 on `SDL-0`, Port 2 on `SDL-1`, and so on, for as many players as you have.
This is the same as PCSX2's own *Automatic Mapping*.

- **PCSX2 must be closed** (PCSX2 saves its settings when it exits and would undo the change).
- A backup is saved first in `~/.local/state/kbpad/backups/`.
- Only the button lines are changed; other settings in those sections (for example deadzones) are kept.
  It also turns on `SDL = true` under `[InputSources]`.
- It detects which naming your PCSX2 uses (new versions: `SDL-0/FaceSouth`; older versions: `SDL-0/A`).
  If the file has no SDL bindings yet, it uses the new naming.
- If `PCSX2.ini` does not exist yet, start PCSX2 once, finish its first-run setup, close it, and try again.
- If another real gamepad is plugged in, SDL numbers can shift; then choose the controllers by name in PCSX2.

### Automatic release when PCSX2 closes
When PCSX2 stops running and any keyboard is grabbed, kbpad releases every keyboard
(setting: *Release every keyboard when PCSX2 closes*, on by default).

### "Restart PCSX2" warnings (W020)
- If PCSX2 was already running when kbpad started, a banner asks you to restart PCSX2
  (PCSX2 only looks for controllers when it starts).
- If you change the number of players while PCSX2 runs, a banner asks you to restart it.

---

## 6. Key test tab (ghosting check)

1. Choose a keyboard in **Keyboard**.
2. Hold the keys you press together in a game.
3. **Keys held right now** shows every key the keyboard reports. **Most keys at once** shows the record.
4. If a key you are holding does **not** appear, the keyboard cannot report that combination (ghosting).
   Choose other keys for those buttons, or use another keyboard.
5. **Reset** sets the record back to the number of keys held right now.

Nothing on this tab is saved or logged.

---

## 7. System check tab

| Part | What it does |
|---|---|
| Checks table | ✔ / ✘ for: uinput device exists · uinput writable · input group · keyboards readable · keyboard remappers (keyd) · session (Wayland/X11, always ✔). A failed check shows the fix command |
| **Run checks again** | Repeats the checks |
| **Copy fix commands** | Copies the fix commands of failed checks to the clipboard. Run them in a terminal, then restart kbpad |
| **Keyboards dropping out?** panel | Shows each keyboard set to a player: `✔ always awake`, `⚠ may sleep`, or `? not a USB keyboard` |
| **Keep game keyboards awake** | Turns off USB power saving for every keyboard set to a player, now and after replugging. Asks for your password (polkit). If no password window can appear (common over remote desktop), it copies a `sudo sh -c …` command to the clipboard for you to paste in a terminal |

If any check fails when kbpad starts, a red banner lists the problems.

---

## 8. Log tab

| Control | What it does |
|---|---|
| Log view | The last 1500 lines of `~/.local/state/kbpad/logs/kbpad.log`. Refreshes when you open the tab |
| **Refresh** | Reload now |
| **Open log folder** | Opens `~/.local/state/kbpad/logs/` in your file manager |
| **Export diagnostics…** | Choose a folder; kbpad writes `kbpad-diagnostics-<date-time>.zip` with system info, logs, crash reports and your config. Your username is replaced by `<user>`. Nothing is sent anywhere |

The log never records which keys you type.

---

## 9. Settings tab

### Look
**Theme**: `Dark` (default), `Light`, or `Follow system`. Changes immediately.

### Hotkeys

| Setting | Default | Notes |
|---|---|---|
| Grab / release this keyboard | **Ctrl + F1** | Works on the keyboard you press it on |
| Release every keyboard | **Ctrl + Shift + F12** | Works from any keyboard kbpad reads |

- **Change…**: hold the modifiers you want (Ctrl, Shift, Alt, Super), then press the main key.
  A single key without modifiers (for example **Pause** or **Scroll Lock**) also works; kbpad asks
  you to confirm, because that key will then always grab/release.
- The two hotkeys cannot be the same.
- **Reset to defaults** restores Ctrl+F1 and Ctrl+Shift+F12.
- "Ctrl" means either Ctrl key (left or right); the same for Shift, Alt and Super.
- The hotkey's main key is never sent to the controller. The modifier keys still are (for example Left Shift is L2 on P1).
- The KDE desktop also uses Ctrl+F1 ("switch to desktop 1") while a keyboard is **not** grabbed.

### Behaviour

| Setting | Default | What it does |
|---|---|---|
| Players (controllers) + **Apply** | 2 | 1 to 4. Asks first. Fewer players: keyboards of removed players are set to *Not used* and their tabs disappear. More players: new controllers and tabs are added. Restart PCSX2 afterwards if it is running |
| Send keys to the controller only while the keyboard is grabbed | off | On = the old kb2xbox behaviour |
| Release every keyboard when PCSX2 closes | on | See the PCSX2 tab section |
| Closing the window keeps kbpad running in the tray | on | Off = closing the window quits kbpad |

---

## 10. Grabbing, in detail

- **Grab** = kbpad takes the keyboard exclusively. The desktop and other programs stop receiving its keys;
  kbpad still reads them and sends them to the controller.
- Ways to grab or release one keyboard: the hotkey on that keyboard, the card's **Grab/Release** button.
- Ways to release all: **Release all keyboards** (header, File menu, tray menu), the release-all hotkey,
  PCSX2 closing (if enabled), quitting kbpad.
- A grab waits until **every key on that keyboard is released** ("Let go of all keys…"), so the desktop
  never gets a stuck Ctrl.
- You can only grab a keyboard that is set to a player.
- If kbpad crashes or is killed, Linux releases the keyboard automatically (the grab belongs to the open device file).

---

## 11. File menu and tray icon

**File menu**: *Release all keyboards* · *Export diagnostics…* · *Quit kbpad* (**Ctrl+Q**).

**Tray icon** (if your desktop has a system tray):
- Left-click the icon: show the window.
- Right-click: *Show window* · *Release all keyboards* · *Start PCSX2* · *Quit kbpad*.
- Closing the window hides kbpad to the tray (first time, a notification says so). The controllers stay alive.
- When a keyboard is grabbed or released with a **hotkey**, or released because PCSX2 closed, a short
  notification appears.

Opening kbpad again while it is running brings the existing window to the front instead of starting a second copy.

---

## 12. Command line

| Command | What it does |
|---|---|
| `kbpad` | Start the program |
| `kbpad --hidden` | Start minimised to the tray (used by autostart). If there is no tray, the window shows |
| `kbpad --list` | Print detected keyboards (name, USB ID, identity key, event nodes) and exit |
| `kbpad --check` | Run the system checks and exit. Exit code 1 if anything failed |
| `kbpad --debug` | More detail in the log (still never typed keys) |
| `kbpad --version` | Print the version |
| `kbpad --help` | Show the options |

Without installing: `cd kbpad && PYTHONPATH=src python3 -m kbpad` (same options).

Press **Ctrl+C** in the terminal (or send SIGTERM) to quit cleanly; every keyboard is released.

---

## 13. Using kbpad with other programs

The controllers are standard Linux gamepads with the ID of a wired Xbox 360 controller, so programs
that read controllers through SDL or evdev can use them. What was actually tested in this project:
SDL3 detection on the development PC (both controllers listed as "Xbox 360 Controller", button/stick/trigger
values arrived), and version 0.1.0 with the Bloody keyboard on the gaming PC (reported by the user as
"working great"; whether that test included a game in PCSX2: not recorded). Other emulators were not tested;
see [06-roadmap.md](06-roadmap.md).
