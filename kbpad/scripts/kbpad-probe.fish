#!/usr/bin/env fish
# kbpad-probe.fish
# READ-ONLY. Changes nothing on the system. Writes ~/kbpad-probe-report.txt
# Plug in BOTH keyboards before running.

set out ~/kbpad-probe-report.txt
echo "kbpad probe "(date -Iseconds) > $out

function section
    echo "" >> $out
    echo "===== $argv =====" >> $out
end

function run
    echo "\$ $argv[1]" >> $out
    eval $argv[1] >> $out 2>&1
end

section "SYSTEM"
run 'uname -r'
run 'echo session=$XDG_SESSION_TYPE desktop=$XDG_CURRENT_DESKTOP'
run 'id'
run 'echo shell=$SHELL fish=(fish --version)'

section "TOOLCHAIN AND PACKAGES"
run 'which cargo rustc rustup'
run 'cargo --version; rustc --version'
run 'pacman -Qs "^(rust|rustup|evtest|python-evdev|python-libevdev|sdl2-jstest|flatpak|pcsx2|webkit2gtk-4.1|qt6-base)"'

section "UINPUT"
run 'ls -l /dev/uinput'
run 'lsmod | grep uinput'
run 'cat /etc/udev/rules.d/99-uinput.rules'
run 'ls -l /etc/modules-load.d/ /usr/lib/modules-load.d/ | grep -i uinput'

section "KEYBOARDS (vendor:product, by-id, by-path)"
run 'lsusb'
run 'ls -l /dev/input/by-id/ | grep -i kbd'
run 'ls -l /dev/input/by-path/ | grep -i kbd'

section "PER-NODE USB IDENTITY"
for link in /dev/input/by-id/*event-kbd
    test -e $link; or continue
    set node (readlink -f $link)
    echo "" >> $out
    echo "--- $link -> $node" >> $out
    udevadm info -q property -n $node 2>&1 | grep -E 'ID_VENDOR_ID|ID_MODEL_ID|ID_MODEL=|ID_VENDOR=|ID_SERIAL=|ID_USB_INTERFACE_NUM|ID_PATH=|ID_INPUT_KEYBOARD' >> $out
end

section "EXISTING VIRTUAL PADS"
run 'grep -i -A6 "XBOX Controller" /proc/bus/input/devices'

section "USB AUTOSUSPEND STATE"
for d in /sys/bus/usb/devices/*
    test -f $d/power/control; or continue
    set vid (cat $d/idVendor 2>/dev/null)
    set pid (cat $d/idProduct 2>/dev/null)
    set prod (cat $d/product 2>/dev/null)
    set ctl (cat $d/power/control 2>/dev/null)
    set dly (cat $d/power/autosuspend_delay_ms 2>/dev/null)
    echo (basename $d)" $vid:$pid \"$prod\" control=$ctl delay_ms=$dly" >> $out
end

section "PCSX2 INSTALL TYPE"
run 'flatpak list | grep -i pcsx2'
run 'flatpak override --user --show net.pcsx2.PCSX2'
run 'which pcsx2 pcsx2-qt'
run 'find ~/.config ~/.var -name PCSX2.ini 2>/dev/null'

section "PCSX2.ini: Pad1 / Pad2 / InputSources"
for f in ~/.config/PCSX2/inis/PCSX2.ini ~/.var/app/net.pcsx2.PCSX2/config/PCSX2/inis/PCSX2.ini
    test -f $f; or continue
    echo "" >> $out
    echo "--- $f" >> $out
    grep -n -A30 -E '^\[Pad[12]\]' $f >> $out 2>&1
    grep -n -A12 -E '^\[InputSources\]' $f >> $out 2>&1
end

section "KB2XBOX FILES"
run 'ls -la ~/kb2xbox ~/kb2xbox/config'
run 'cat ~/mksm_launch.sh'
for cfg in ~/kb2xbox/config/p1_hyperx.cfg ~/kb2xbox/config/p2_bloody.cfg
    test -f $cfg; or continue
    echo "" >> $out
    echo "--- $cfg" >> $out
    cat $cfg >> $out
end

section "KB2XBOX SOURCE (answers key-pair direction order)"
run 'wc -l ~/kb2xbox/kb2xbox.py'
if test -f ~/kb2xbox/kb2xbox.py
    set n (wc -l < ~/kb2xbox/kb2xbox.py)
    if test $n -le 600
        cat ~/kb2xbox/kb2xbox.py >> $out
    else
        echo "file longer than 600 lines, printing parsing parts only" >> $out
        grep -n -i -E 'abs_|split|min|max|neg|pos|grab|F1' ~/kb2xbox/kb2xbox.py >> $out
    end
end

echo ""
echo "Done. Report: $out"
echo "Lines: "(wc -l < $out)
echo "Upload the file here, or run: cat $out"
