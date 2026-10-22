# kbpad documentation

kbpad turns USB keyboards into virtual game controllers on Linux, one keyboard per player.
It was built for PCSX2 (PlayStation 2 emulator) co-op, but any program that supports a normal Xbox 360
controller can use it.

Version described here: **0.2.0** (see `src/kbpad/__init__.py`).

## Where to start

| You want to… | Read |
|---|---|
| Know what every file is for | [01-folder-structure.md](01-folder-structure.md) |
| Learn every button, tab and hotkey | [02-user-guide.md](02-user-guide.md) |
| Install kbpad on a new Linux PC (any distro) | [03-setup-new-linux.md](03-setup-new-linux.md) |
| See what kbpad needs (system, packages, hardware) | [05-requirements.md](05-requirements.md) |
| See features that are planned but not built | [06-roadmap.md](06-roadmap.md) |

## Words used in these docs

| Word | Meaning |
|---|---|
| **evdev** | The Linux system that delivers keyboard, mouse and gamepad events. Each device is a file like `/dev/input/event4` |
| **event node** | One of those `/dev/input/eventN` files. One USB keyboard can have several |
| **uinput** | A Linux feature that lets a program create a *virtual* input device. kbpad uses it to create the controllers (`/dev/uinput`) |
| **grab** | Exclusive access to a keyboard. While grabbed, only kbpad sees its keys; the desktop and other programs do not |
| **pad / controller** | The virtual Xbox 360 controller kbpad creates for each player (`XBOX Controller P1`, `P2`, …) |
| **SDL** | The library PCSX2 and many games use to read controllers. It names them `SDL-0`, `SDL-1`, … |
| **profile / layout / preset** | A list of which keyboard key presses which controller button |
| **SOCD** | "Simultaneous opposite cardinal directions": what happens when Left and Right (or Up and Down) are held together |
| **ghosting** | When a cheap keyboard cannot report some combinations of keys held together |
| **udev rule** | A small system file that sets device permissions, for example who may use `/dev/uinput` |
