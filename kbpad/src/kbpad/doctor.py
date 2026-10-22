"""System checks shown on the 'System check' tab, each with a fix command."""

from __future__ import annotations

import grp
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .devices import power_control


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def run_checks() -> list[Check]:
    checks: list[Check] = []

    uinput = Path("/dev/uinput")
    checks.append(Check("uinput device exists", uinput.exists(),
                        "/dev/uinput present" if uinput.exists() else "/dev/uinput missing",
                        "echo uinput | sudo tee /etc/modules-load.d/uinput.conf; sudo modprobe uinput"))

    writable = uinput.exists() and os.access(uinput, os.W_OK)
    checks.append(Check("uinput writable", writable,
                        "can create virtual controllers" if writable else "cannot create virtual controllers (E002)",
                        "echo 'KERNEL==\"uinput\", GROUP=\"input\", MODE=\"0660\"' | sudo tee /etc/udev/rules.d/99-uinput.rules;"
                        " sudo udevadm control --reload; sudo udevadm trigger"))

    try:
        input_gid = grp.getgrnam("input").gr_gid
        in_session = input_gid in os.getgroups()
        members = grp.getgrnam("input").gr_mem
        user = os.environ.get("USER", "")
        on_disk = user in members
    except KeyError:
        in_session = on_disk = False
    if in_session:
        detail = "you are in the 'input' group"
    elif on_disk:
        detail = "added to 'input' but this login predates it: log out and back in (E003)"
    else:
        detail = "not in the 'input' group (E003)"
    checks.append(Check("input group", in_session, detail, "sudo usermod -aG input $USER  # then log out and in"))

    nodes = sorted(Path("/dev/input").glob("event*"))
    readable = [n for n in nodes if os.access(n, os.R_OK)]
    checks.append(Check("keyboards readable", bool(nodes) and len(readable) == len(nodes),
                        f"{len(readable)}/{len(nodes)} input nodes readable",
                        "sudo usermod -aG input $USER  # then log out and in"))

    checks.append(_keyd_check())

    session = os.environ.get("XDG_SESSION_TYPE", "unknown")
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "unknown")
    checks.append(Check("session", True, f"{session} / {desktop} (both work)"))
    return checks


def _keyd_check() -> Check:
    """keyd (and similar remappers) grab keyboards and merge them into one virtual keyboard.
    Keyboards it grabs cannot be told apart or grabbed by kbpad."""
    try:
        active = subprocess.run(["systemctl", "is-active", "keyd"], capture_output=True,
                                text=True, timeout=5).stdout.strip() == "active"
    except (OSError, subprocess.TimeoutExpired):
        active = False
    if not active:
        return Check("keyboard remappers", True, "keyd not running")
    configs = list(Path("/etc/keyd").glob("*.conf"))
    if not configs:
        return Check("keyboard remappers", True, "keyd running with no config: it holds no keyboard")
    return Check("keyboard remappers", False,
                 f"keyd running with {len(configs)} config(s): keyboards it matches show up only as "
                 "'keyd virtual keyboard' and cannot be grabbed (E011)",
                 "add the game keyboards' IDs as '-<vendor>:<product>' under [ids] in /etc/keyd/*.conf, "
                 "then: sudo systemctl restart keyd")


# --- USB autosuspend (keyboards that "drop out") ---------------------------------

AUTOSUSPEND_RULE = Path("/etc/udev/rules.d/70-kbpad-autosuspend.rules")


def autosuspend_status(keyboards) -> list[tuple[str, str, str]]:
    """[(name, usb id, 'on' | 'auto' | '?')] for the given devices.Keyboard objects."""
    return [(kb.name, kb.usb_id, power_control(kb)[0]) for kb in keyboards]


def autosuspend_script(keyboards) -> str:
    """Shell script (run as root) that keeps these keyboards awake now and after every replug."""
    rules = ["# Written by kbpad: keep game keyboards awake (no USB autosuspend)."]
    now = []
    for kb in keyboards:
        vid, pid = kb.usb_id.split(":")
        rules.append(f'ACTION=="add", SUBSYSTEM=="usb", ATTR{{idVendor}}=="{vid}", '
                     f'ATTR{{idProduct}}=="{pid}", TEST=="power/control", ATTR{{power/control}}="on"')
        _state, sysdir = power_control(kb)
        if sysdir:
            now.append(f"echo on > {shlex.quote(str(sysdir / 'power' / 'control'))}")
    text = "\n".join(rules) + "\n"
    script = [f"printf %s {shlex.quote(text)} > {AUTOSUSPEND_RULE}", "udevadm control --reload"] + now
    return " && ".join(script)


def apply_autosuspend_fix(keyboards) -> tuple[bool, str]:
    """Asks for the password through polkit (pkexec). Returns (ok, message)."""
    if not keyboards:
        return False, "Set a keyboard to a player first."
    script = autosuspend_script(keyboards)
    if not shutil.which("pkexec"):
        return False, "pkexec is not installed. Run this in a terminal instead:\nsudo sh -c " + shlex.quote(script)
    try:
        out = subprocess.run(["pkexec", "/bin/sh", "-c", script], capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, str(err)
    if out.returncode == 0:
        return True, f"Done. Rule saved to {AUTOSUSPEND_RULE}; the keyboards stay awake from now on."
    if out.returncode in (126, 127):
        return False, ("The password prompt was cancelled or no polkit agent is running "
                       "(common over remote desktop). Run this in a terminal instead:\nsudo sh -c " + shlex.quote(script))
    return False, (out.stderr or out.stdout).strip() or f"failed (exit {out.returncode})"

