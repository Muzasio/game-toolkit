# 06 · Future features (on demand)

Not built yet. Each one is independent; ask for any of them when you need it.

## Bigger features

| Feature | What it does | Why / where it helps |
|---|---|---|
| **Mouse → stick (aiming)** | A mouse set to a player moves that player's right (or left) stick; mouse buttons become controller buttons. Sensitivity, deadzone, curve, invert Y per player. Grabs and releases together with that player's keyboard. | Shooters and camera control (PS2/GameCube shooters) |
| **Emulators tab** | Dolphin, RetroArch, DuckStation, PPSSPP, RPCS3, Cemu… next to PCSX2: detect native/Flatpak, Start button, Flatpak device permission fix, setup steps per emulator | Use kbpad beyond PCSX2. The controllers already work in all of them today; this adds launch and setup help |
| **Per-emulator / per-game layouts** | The right key layout loads automatically when you start an emulator or game | Different games, different keys |
| **DSU (Cemuhook) motion server** | Keys send tilt or shake to emulators that accept DSU motion (Dolphin, Cemu, RPCS3, Switch emulators) | Wii, Switch, PS3 and Wii U games that need motion |

## Smaller features

| Feature | What it does |
|---|---|
| Walk key | Halves stick movement while held (N64, GameCube, 3D games) |
| Half-press trigger key | Trigger at 50% (GameCube racing / Sunshine) |
| Split keyboard | Left half = P1, right half = P2 on one keyboard (laptops) |
| Turbo / macro buttons | Repeat a button while held; short combos |
| Auto-grab on game start | Grab every player keyboard when PCSX2 (or another emulator) starts |
| Rumble indicator | Show when the game asks for vibration (keyboards cannot vibrate) |
| PKGBUILD / AUR | Install and update with pacman instead of `install.fish` |
| Automated GUI tests | Turn the screenshot scripts into tests |
| App icon file | Ship a proper SVG icon instead of the built-in drawing |

## Already done (v0.2.0)

Configurable hotkeys · opposite-direction modes (SOCD) · auto-release when PCSX2 closes · git repo ·
keep-keyboards-awake fix · PCSX2 controller auto-setup · restart-PCSX2 warnings · open-twice brings the window
forward · second key per button · key test (ghosting) · identical keyboards · kb2xbox config import ·
dark / light / system themes.
