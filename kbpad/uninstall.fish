#!/usr/bin/env fish
# Removes kbpad from your user account. The udev rule and group membership are left alone.

function ask
    read -P "$argv[1] [y/N] " answer
    string match -qi y -- $answer
end

pkill -f "python3 -m kbpad" 2>/dev/null; and echo "Stopped running kbpad (keyboards released)."
rm -rf $HOME/.local/share/kbpad
rm -f $HOME/.local/bin/kbpad $HOME/.local/share/applications/kbpad.desktop \
      $HOME/.config/autostart/kbpad.desktop $HOME/.config/fish/completions/kbpad.fish
echo "App removed."
if ask "Also delete your settings and key layouts (~/.config/kbpad) and logs (~/.local/state/kbpad)?"
    rm -rf $HOME/.config/kbpad $HOME/.local/state/kbpad
    echo "Settings and logs deleted."
else
    echo "Settings kept."
end
