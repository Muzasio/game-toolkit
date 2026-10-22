#!/usr/bin/env fish
# kbpad installer (CachyOS / Arch). Installs for your user only:
#   ~/.local/share/kbpad/   app code
#   ~/.local/bin/kbpad      launcher
#   app menu entry, optional autostart at login
# Every step that needs sudo shows the command and asks first.

set -l src (dirname (status --current-filename))
set -l share $HOME/.local/share/kbpad
set -l bin $HOME/.local/bin
set -l apps $HOME/.local/share/applications

function ask
    read -P "$argv[1] [y/N] " answer
    string match -qi y -- $answer
end

function step
    set_color --bold blue; echo "==> $argv"; set_color normal
end

step "1/5 Dependencies (python-evdev, pyside6)"
set -l missing
for p in python python-evdev pyside6
    pacman -Qq $p >/dev/null 2>&1; or set -a missing $p
end
if test (count $missing) -gt 0
    echo "Missing: $missing"
    echo "Command: sudo pacman -S --needed $missing"
    if ask "Install them now?"
        sudo pacman -S --needed $missing; or begin; echo "pacman failed"; exit 1; end
    else
        echo "kbpad cannot run without them. Stopping."; exit 1
    end
else
    echo "OK"
end

step "2/5 Virtual controller access (/dev/uinput)"
if not test -e /dev/uinput
    echo "uinput module not loaded."
    echo "Command: echo uinput | sudo tee /etc/modules-load.d/uinput.conf; sudo modprobe uinput"
    if ask "Load it now and at every boot?"
        echo uinput | sudo tee /etc/modules-load.d/uinput.conf >/dev/null; and sudo modprobe uinput
    end
end
if test -e /dev/uinput; and not test -w /dev/uinput
    echo "/dev/uinput is not writable for you."
    echo "Command: sudo cp $src/packaging/udev/99-kbpad-uinput.rules /etc/udev/rules.d/ ; sudo udevadm control --reload ; sudo udevadm trigger"
    if ask "Install the udev rule?"
        sudo cp $src/packaging/udev/99-kbpad-uinput.rules /etc/udev/rules.d/
        and sudo udevadm control --reload; and sudo udevadm trigger --sysname-match=uinput
    end
end
if not id -nG | string match -qr '\binput\b'
    if getent group input | string match -qr "[:,]$USER(\$|,)"
        echo "You are in the 'input' group, but this login started before that: log out and back in."
    else
        echo "You are not in the 'input' group (needed to read keyboards)."
        echo "Command: sudo usermod -aG input $USER"
        if ask "Add yourself now? (log out and back in afterwards)"
            sudo usermod -aG input $USER; and echo "Done. Log out and back in before starting kbpad."
        end
    end
else
    echo "OK"
end

step "3/5 Copying the app to $share"
rm -rf $share/kbpad
mkdir -p $share $bin $apps
cp -r $src/src/kbpad $share/kbpad
find $share -name __pycache__ -type d -prune -exec rm -rf {} +
printf '%s\n' '#!/bin/sh' \
    'PYTHONPATH="$HOME/.local/share/kbpad${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m kbpad "$@"' > $bin/kbpad
chmod +x $bin/kbpad
mkdir -p $HOME/.config/fish/completions
cp $src/packaging/completions/kbpad.fish $HOME/.config/fish/completions/kbpad.fish
echo "OK"

step "4/5 App menu entry"
set -l desktop "[Desktop Entry]
Type=Application
Name=kbpad
GenericName=Keyboard to Controller
Comment=Use keyboards as game controllers (PCSX2)
Exec=$bin/kbpad
Icon=input-gaming
Terminal=false
Categories=Game;Utility;
Keywords=gamepad;controller;keyboard;pcsx2;xbox;"
echo $desktop > $apps/kbpad.desktop
command -q update-desktop-database; and update-desktop-database $apps 2>/dev/null
echo "OK (search for 'kbpad' in the app menu)"

step "5/5 Autostart"
if ask "Start kbpad at login, minimised to the tray? (controllers ready before you open PCSX2)"
    mkdir -p $HOME/.config/autostart
    echo $desktop | string replace "Exec=$bin/kbpad" "Exec=$bin/kbpad --hidden" > $HOME/.config/autostart/kbpad.desktop
    echo "Autostart enabled"
else
    rm -f $HOME/.config/autostart/kbpad.desktop
    echo "Skipped"
end

echo ""
python3 -c "import sys; sys.path.insert(0, '$share'); import kbpad.gui.app" 2>/dev/null
and begin; set_color green; echo "Installed. Start it from the app menu, or run: kbpad"; set_color normal; end
or begin; set_color red; echo "Installed, but the app failed to import. Run 'kbpad --check' to see why."; set_color normal; end
contains $bin $PATH; or echo "Note: $bin is not in your PATH; the app menu entry still works."
