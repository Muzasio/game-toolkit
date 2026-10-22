"""Find keyboards and group their event nodes by physical device.

A USB keyboard often exposes several event nodes (if00, if01, if02). Instead of guessing
which one carries the letter keys, kbpad reads (and grabs) every key-capable node of the
same physical device together. Gaming mice that expose a keyboard node are marked as mice.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from evdev import InputDevice, ecodes as e, list_devices

from .constants import PAD_PHYS

log = logging.getLogger(__name__)

BY_ID = Path("/dev/input/by-id")
BY_PATH = Path("/dev/input/by-path")
_IF_SUFFIX = re.compile(r"(-if\d+)?-event-(kbd|mouse|joystick)$|-event$")


@dataclass
class Keyboard:
    """One physical keyboard (possibly several event nodes)."""
    key: str                       # stable identity used to remember assignments
    name: str
    vendor: int
    product: int
    nodes: list[str] = field(default_factory=list)       # /dev/input/eventN with letter keys
    extra_nodes: list[str] = field(default_factory=list)  # other key nodes of the same device (media keys)
    by_id: str = ""
    by_path: str = ""
    phys: str = ""
    is_mouse: bool = False
    is_virtual: bool = False

    @property
    def usb_id(self) -> str:
        return f"{self.vendor:04x}:{self.product:04x}"

    @property
    def port(self) -> str:
        """Human label for the USB port, e.g. 'USB port 3' or 'USB port 3.2' (behind a hub)."""
        if self.phys.startswith("usb-") and "-" in self.phys[4:]:
            return "USB port " + self.phys.rsplit("-", 1)[-1]
        return self.phys or "virtual"

    @property
    def all_nodes(self) -> list[str]:
        return self.nodes + self.extra_nodes

    @property
    def hidden_by_default(self) -> bool:
        return self.is_mouse or self.is_virtual


def _links(directory: Path) -> dict[str, str]:
    """real event node -> link name"""
    result = {}
    if directory.is_dir():
        for link in sorted(directory.iterdir()):
            try:
                result.setdefault(os.path.realpath(link), link.name)
            except OSError:
                pass
    return result


def _is_full_keyboard(caps: dict) -> bool:
    keys = set(caps.get(e.EV_KEY, []))
    return {e.KEY_A, e.KEY_Z, e.KEY_SPACE, e.KEY_ENTER} <= keys


def _has_keys(caps: dict) -> bool:
    keys = caps.get(e.EV_KEY, [])
    return any(k < e.BTN_MISC or k >= e.KEY_OK for k in keys)


def _is_pointer(caps: dict) -> bool:
    rel = set(caps.get(e.EV_REL, []))
    return e.REL_X in rel and e.REL_Y in rel


def scan() -> list[Keyboard]:
    """Return every keyboard-like physical device. Never raises for a single bad node."""
    by_id, by_path = _links(BY_ID), _links(BY_PATH)
    groups: dict[str, dict] = {}
    own_phys = PAD_PHYS.split("{")[0]

    for path in list_devices():
        try:
            dev = InputDevice(path)
        except OSError as err:
            log.debug("cannot open %s: %s", path, err)
            continue
        try:
            caps = dev.capabilities()
            phys = dev.phys or ""
            if phys.startswith(own_phys):
                continue                      # our own virtual pads
            vendor, product = dev.info.vendor, dev.info.product
            base_phys = phys.split("/input")[0] if phys else f"virtual:{dev.name}"
            gkey = f"{base_phys}|{vendor:04x}:{product:04x}"
            g = groups.setdefault(gkey, {"name": dev.name, "vendor": vendor, "product": product,
                                         "phys": base_phys, "full": [], "extra": [],
                                         "pointer": False, "led": False,
                                         "virtual": not phys or dev.info.bustype == e.BUS_VIRTUAL})
            if _is_pointer(caps):
                g["pointer"] = True
            if _is_full_keyboard(caps):
                g["full"].append(path)
                if e.EV_LED in caps and not g["led"]:
                    g["led"] = True           # Caps Lock LED: a real keyboard, name it after this node
                    g["name"] = dev.name
                elif not g["led"] and len(g["full"]) == 1:
                    g["name"] = dev.name
            elif _has_keys(caps):
                g["extra"].append(path)
        finally:
            dev.close()

    keyboards: list[Keyboard] = []
    for g in groups.values():
        if not g["full"]:
            continue
        nodes = sorted(g["full"], key=_node_number)
        extra = sorted(g["extra"], key=_node_number)
        id_name = next((by_id[n] for n in nodes if n in by_id), "")
        path_name = next((by_path[n] for n in nodes if n in by_path), "")
        keyboards.append(Keyboard(
            key="", name=g["name"], vendor=g["vendor"], product=g["product"],
            nodes=nodes, extra_nodes=extra, by_id=id_name, by_path=path_name,
            phys=g["phys"], is_mouse=_looks_like_mouse(g),
            is_virtual=g["virtual"]))

    _assign_keys(keyboards)
    keyboards.sort(key=lambda k: (k.hidden_by_default, k.name.lower(), k.key))
    return keyboards


def _looks_like_mouse(g: dict) -> bool:
    """Gaming mice expose a keyboard node for macro keys; gaming keyboards expose a mouse node.
    A real keyboard has a Caps Lock LED, so: mouse = pointer device without keyboard LEDs."""
    if "mouse" in g["name"].lower():
        return True
    return g["pointer"] and not g["led"]


def _assign_keys(keyboards: list[Keyboard]) -> None:
    """Identity used to remember which keyboard is which player.

    Normally the by-id name (contains the serial number when the keyboard has one), so the
    keyboard keeps its player in any USB port. Two identical keyboards without serial numbers
    share one by-id name (udev keeps only one link, so it can even jump between them), so
    those use the USB port path instead: each port keeps its player."""
    def base(name: str) -> str:
        return _IF_SUFFIX.sub("", name)

    def port_key(kb: Keyboard) -> str:
        return ("path:" + base(kb.by_path)) if kb.by_path else f"phys:{kb.phys}|{kb.usb_id}"

    models: dict[tuple, list[Keyboard]] = {}
    for kb in keyboards:
        models.setdefault((kb.usb_id, kb.name), []).append(kb)
    for same in models.values():
        ids = [base(kb.by_id) for kb in same]
        unique_ids = len(same) == 1 or (all(ids) and len(set(ids)) == len(ids))
        for kb in same:
            if kb.is_virtual and not kb.by_id and not kb.by_path:
                kb.key = f"name:{kb.name}|{kb.usb_id}|{kb.phys}"
            elif unique_ids and kb.by_id:
                kb.key = "id:" + base(kb.by_id)
            else:
                kb.key = port_key(kb)
    seen: dict[str, int] = {}
    for kb in keyboards:
        seen[kb.key] = seen.get(kb.key, 0) + 1
    for kb in keyboards:
        if seen[kb.key] > 1:
            kb.key = f"{kb.key}@{kb.phys}"


def usb_sysfs_dir(node: str) -> Path | None:
    """/sys/bus/usb/devices/<x> of the USB device that owns an event node, or None."""
    try:
        p = Path(f"/sys/class/input/{Path(node).name}/device").resolve()
    except OSError:
        return None
    for parent in [p, *p.parents]:
        if (parent / "idVendor").exists() and (parent / "power" / "control").exists():
            return parent
        if parent == Path("/sys"):
            break
    return None


def power_control(kb: Keyboard) -> tuple[str, Path | None]:
    """('on' | 'auto' | '?', sysfs dir). 'auto' = USB autosuspend may put it to sleep."""
    for node in kb.nodes:
        d = usb_sysfs_dir(node)
        if d:
            try:
                return (d / "power" / "control").read_text().strip(), d
            except OSError:
                return "?", d
    return "?", None


def _node_number(path: str) -> int:
    m = re.search(r"(\d+)$", path)
    return int(m.group(1)) if m else 0
