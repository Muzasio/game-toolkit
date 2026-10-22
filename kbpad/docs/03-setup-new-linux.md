# 03 · Set up kbpad on a new Linux PC (any distro)

Two ways:

- **A. CachyOS / Arch Linux:** run `install.fish`. Tested on two CachyOS PCs.
- **B. Any other distro (or Arch without fish):** follow the numbered steps below. They use a Python
  virtual environment, so they work the same on every distro. Steps 5, 7 and 8 were run exactly as written on
  CachyOS with bash (in a test home folder). The package names in step 3 for other distros are the standard
  names but **were not tested in this project**.

Rules for whoever follows this guide (person or AI):
- Run commands **one block at a time** and check the "Expected result" before going on.
- Commands are for **bash**. If your shell is fish or zsh, type `bash` first and press Enter.
- Lines starting with `sudo` need your password and change the system.
- Never run kbpad itself with `sudo`.

---

## A. CachyOS / Arch Linux (short way)

```bash
cd ~/kbpad            # the folder that contains install.fish
fish install.fish
```

- No `fish`? Install it first: `sudo pacman -S fish`.
- Answer `y` to the questions about missing packages, uinput and the input group. Autostart is your choice.
- If pacman shows **error 404** while downloading: your package list is old. Run
  `sudo pacman -Syu python-evdev pyside6`, then `fish install.fish` again.
  Do **not** use `pacman -Sy` alone (a half-updated Arch system can break other programs).
- If it says you were added to the `input` group: log out and log back in.
- Then go to [step 8](#step-8-check-everything).

---

## B. Any distro (step by step)

### Step 0. What you need

| Need | Why |
|---|---|
| A Linux PC with a desktop (KDE, GNOME, …), Wayland or X11 | kbpad is a window program |
| systemd and udev | Normal on almost every desktop distro; used for device permissions |
| Python **3.12 or newer** | The project declares 3.12+. Only Python 3.14.7 was actually tested |
| Internet access | To download the Python packages (about 260 MB) |
| Your password (sudo) | For steps 3 and 6 |
| The `kbpad` folder | Copied from the old PC or from a backup |

### Step 1. Open a terminal and start bash

```bash
bash
```

**Expected result:** the prompt changes (or stays the same if bash is already your shell). No error.

### Step 2. Check Python

```bash
python3 --version
```

**Expected result:** `Python 3.12` or higher. If it is lower or "command not found", install Python 3 with
your distro's package manager first.

### Step 3. Install build tools (needed to build the evdev package)

The `evdev` Python package is **compiled on your PC** during step 5. It needs a C compiler, Python
development headers and the Linux input headers. Run the line for your distro:

| Distro | Command | Tested in this project? |
|---|---|---|
| Arch / CachyOS / Manjaro | `sudo pacman -S --needed python base-devel linux-api-headers` | Worked on CachyOS (these were already installed) |
| Debian / Ubuntu / Mint / Pop!_OS | `sudo apt install python3 python3-venv python3-dev build-essential linux-libc-dev` | No |
| Fedora | `sudo dnf install python3 python3-devel gcc kernel-headers` | No |
| openSUSE | `sudo zypper install python3 python3-devel gcc linux-glibc-devel` | No |

**Expected result:** the package manager finishes without errors.

### Step 4. Put the project folder in your home folder

The guide assumes the folder is at `~/kbpad`. For example, copying from another PC on the network
(run this on the **other** PC, where the folder is; replace `user@new-pc` with your login and the new PC's address):

```bash
scp -r ~/kbpad user@new-pc:~/
```

Or copy it with a USB stick. Then, on the new PC:

```bash
ls ~/kbpad
```

**Expected result:** you see `install.fish`, `requirements.txt`, `src`, `docs` and more.

### Step 5. Create the Python environment and install the packages

```bash
cd ~/kbpad
python3 -m venv ~/.local/share/kbpad-venv
~/.local/share/kbpad-venv/bin/pip install --upgrade pip
~/.local/share/kbpad-venv/bin/pip install -r requirements.txt
```

**Expected result:** the last lines say `Successfully installed … evdev-… PySide6-…`.
You may see "Building wheel for evdev": that is normal (step 3 made it possible).

If you want a smaller download, `PySide6-Essentials` is enough for kbpad (tested):
`~/.local/share/kbpad-venv/bin/pip install evdev PySide6-Essentials`

### Step 6. Allow kbpad to read keyboards and create controllers

**6a. Load the uinput module (needed for virtual controllers)**

```bash
ls -l /dev/uinput
```

If you see "No such file or directory", run:

```bash
sudo modprobe uinput
echo uinput | sudo tee /etc/modules-load.d/uinput.conf
```

The second line loads it again at every boot.

**6b. Give your user access to /dev/uinput**

```bash
sudo cp ~/kbpad/packaging/udev/99-kbpad-uinput.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger --sysname-match=uinput
```

The rule (one line) gives the `input` group and the logged-in user read/write access to `/dev/uinput`:
`KERNEL=="uinput", SUBSYSTEM=="misc", TAG+="uaccess", OPTIONS+="static_node=uinput", GROUP="input", MODE="0660"`

**6c. Join the input group (needed to read keyboards)**

```bash
sudo usermod -aG input $USER
```

**6d. Log out and log back in** (or reboot). Group changes only apply to new logins.

**Expected result after logging back in:**

```bash
id | grep -o input
ls -l /dev/uinput
```

shows `input`, and `/dev/uinput` shows the group `input` with `rw` for the group, for example `crw-rw---- … root input …`.

### Step 7. Install the program files, the `kbpad` command and the menu entry

```bash
mkdir -p ~/.local/share/kbpad ~/.local/bin ~/.local/share/applications
rm -rf ~/.local/share/kbpad/kbpad
cp -r ~/kbpad/src/kbpad ~/.local/share/kbpad/kbpad
cat > ~/.local/bin/kbpad <<'LAUNCH'
#!/bin/sh
PYTHONPATH="$HOME/.local/share/kbpad${PYTHONPATH:+:$PYTHONPATH}" exec "$HOME/.local/share/kbpad-venv/bin/python" -m kbpad "$@"
LAUNCH
chmod +x ~/.local/bin/kbpad
cat > ~/.local/share/applications/kbpad.desktop <<DESK
[Desktop Entry]
Type=Application
Name=kbpad
Comment=Use keyboards as game controllers
Exec=$HOME/.local/bin/kbpad
Icon=input-gaming
Terminal=false
Categories=Game;Utility;
DESK
~/.local/bin/kbpad --version
```

**Expected result:** `kbpad 0.2.0`.

Note: this launcher uses the virtual environment from step 5. The Arch installer (`install.fish`) makes a
different launcher that uses the system Python (`python3`) and the pacman packages.

### Step 8. Check everything

```bash
~/.local/bin/kbpad --check
```

**Expected result:** every line starts with `OK`. For example:

```text
OK   uinput device exists: /dev/uinput present
OK   uinput writable: can create virtual controllers
OK   input group: you are in the 'input' group
OK   keyboards readable: 20/20 input nodes readable
OK   keyboard remappers: keyd not running
OK   session: wayland / KDE (both work)
```

A `FAIL` line shows a `fix:` command.

Then list the keyboards:

```bash
~/.local/bin/kbpad --list
```

**Expected result:** your keyboards with their USB IDs. Mice and virtual keyboards are marked `(mouse)` / `(virtual)`.

### Step 9. Start kbpad and do the first-time setup

Start **kbpad** from the app menu (or run `~/.local/bin/kbpad` in a terminal). Then:

1. Press a key on each keyboard; the card that lights up is that keyboard.
2. Set each card to **Player 1**, **Player 2**, ….
3. Optional: Player tab → **Import kb2xbox config…** to reuse old layouts.
4. Optional: System check tab → **Keep game keyboards awake**.
5. PCSX2 tab: check **Found**. For the Flatpak, click **Allow PCSX2 Flatpak to see controllers** if shown.
6. With PCSX2 closed: **Set up PCSX2 controllers automatically** (PCSX2 must have been started once before).
7. **▶ Start PCSX2**, start a game, press **Ctrl+F1** on each keyboard.

Full details: [02-user-guide.md](02-user-guide.md).

### Step 10 (optional). Start kbpad at login, in the tray

```bash
mkdir -p ~/.config/autostart
sed 's|^Exec=.*|Exec='"$HOME"'/.local/bin/kbpad --hidden|' ~/.local/share/applications/kbpad.desktop > ~/.config/autostart/kbpad.desktop
```

### Step 11 (optional). Type `kbpad` instead of `~/.local/bin/kbpad`

Many distros already have `~/.local/bin` in `PATH`. Check with `echo $PATH`. If not, add this line to `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

---

## Updating kbpad later

1. Quit kbpad (tray icon → *Quit kbpad*).
2. Replace the `~/kbpad` folder with the new one.
3. Arch: `cd ~/kbpad && fish install.fish`. Other distros: repeat **step 7** only.

Your settings and layouts in `~/.config/kbpad/` are kept.

## Removing kbpad

Arch (installed with install.fish): `cd ~/kbpad && fish uninstall.fish`.

Other distros (installed with this guide):

```bash
pkill -f "python -m kbpad"
rm -rf ~/.local/share/kbpad ~/.local/share/kbpad-venv
rm -f ~/.local/bin/kbpad ~/.local/share/applications/kbpad.desktop ~/.config/autostart/kbpad.desktop
```

Optional, also delete settings and logs: `rm -rf ~/.config/kbpad ~/.local/state/kbpad ~/.cache/kbpad`.
The udev rule, the `uinput.conf` file and the group membership stay; remove them by hand if you want:
`sudo rm /etc/udev/rules.d/99-kbpad-uinput.rules /etc/modules-load.d/uinput.conf`
(and `/etc/udev/rules.d/70-kbpad-autosuspend.rules` if you used *Keep game keyboards awake*).

---

## Short version for an automated helper (AI)

Goal: kbpad running for the current user. Stop and report at the first failure.

1. `python3 --version` → must be ≥ 3.12.
2. Install compiler + Python headers + Linux headers (table in step 3).
3. `test -d ~/kbpad/src/kbpad` → must succeed.
4. Run the 4 commands of step 5 → must end with "Successfully installed".
5. If `/dev/uinput` is missing: step 6a. If `test -w /dev/uinput` fails: step 6b. If `id -nG` lacks `input`: step 6c, then the user must log out and in.
6. Run the block of step 7 → must print `kbpad 0.2.0`.
7. `~/.local/bin/kbpad --check` → exit code 0 and every line `OK`.
8. Tell the user to start kbpad from the app menu and follow step 9.
