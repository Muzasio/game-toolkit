"""Controller controls, key profiles and their TOML files.

Internally a profile is a flat mapping {control_id: "KEY_*"}. On disk it uses the
grouped format from the plan (buttons / triggers / dpad / left_stick / right_stick),
with axis pairs written as [negative, positive] (left/up first).
"""

from __future__ import annotations

import logging
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .constants import BUILTIN_PROFILES_DIR, USER_PROFILES_DIR
from .keynames import name_to_code

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Control:
    id: str
    xbox: str
    ps: str
    group: str


CONTROLS: list[Control] = [
    Control("BTN_SOUTH", "A", "Cross ✕", "Face buttons"),
    Control("BTN_EAST", "B", "Circle ○", "Face buttons"),
    Control("BTN_WEST", "X", "Square □", "Face buttons"),
    Control("BTN_NORTH", "Y", "Triangle △", "Face buttons"),
    Control("BTN_TL", "LB", "L1", "Shoulders"),
    Control("BTN_TR", "RB", "R1", "Shoulders"),
    Control("ABS_Z", "LT", "L2", "Shoulders"),
    Control("ABS_RZ", "RT", "R2", "Shoulders"),
    Control("DPAD_UP", "D-pad Up", "D-pad Up", "D-pad"),
    Control("DPAD_DOWN", "D-pad Down", "D-pad Down", "D-pad"),
    Control("DPAD_LEFT", "D-pad Left", "D-pad Left", "D-pad"),
    Control("DPAD_RIGHT", "D-pad Right", "D-pad Right", "D-pad"),
    Control("LS_UP", "Left stick Up", "Left stick Up", "Left stick"),
    Control("LS_DOWN", "Left stick Down", "Left stick Down", "Left stick"),
    Control("LS_LEFT", "Left stick Left", "Left stick Left", "Left stick"),
    Control("LS_RIGHT", "Left stick Right", "Left stick Right", "Left stick"),
    Control("BTN_THUMBL", "LS click", "L3", "Left stick"),
    Control("RS_UP", "Right stick Up", "Right stick Up", "Right stick"),
    Control("RS_DOWN", "Right stick Down", "Right stick Down", "Right stick"),
    Control("RS_LEFT", "Right stick Left", "Right stick Left", "Right stick"),
    Control("RS_RIGHT", "Right stick Right", "Right stick Right", "Right stick"),
    Control("BTN_THUMBR", "RS click", "R3", "Right stick"),
    Control("BTN_SELECT", "Back", "Select", "Menu"),
    Control("BTN_START", "Start", "Start", "Menu"),
    Control("BTN_MODE", "Guide", "PS / Analog", "Menu"),
]
CONTROL_IDS = [c.id for c in CONTROLS]
CONTROL_BY_ID = {c.id: c for c in CONTROLS}

# Axis pairs: (negative control, positive control) per on-disk axis.
_PAIRS = {
    "dpad": {"ABS_HAT0X": ("DPAD_LEFT", "DPAD_RIGHT"), "ABS_HAT0Y": ("DPAD_UP", "DPAD_DOWN")},
    "left_stick": {"ABS_X": ("LS_LEFT", "LS_RIGHT"), "ABS_Y": ("LS_UP", "LS_DOWN")},
    "right_stick": {"ABS_RX": ("RS_LEFT", "RS_RIGHT"), "ABS_RY": ("RS_UP", "RS_DOWN")},
}
_BUTTON_IDS = [c for c in CONTROL_IDS if c.startswith("BTN_")]
_TRIGGER_IDS = ["ABS_Z", "ABS_RZ"]


class ProfileError(Exception):
    pass


@dataclass
class Profile:
    id: str
    name: str
    label_set: str = "ps2"            # "ps2" or "xbox"
    builtin: bool = False
    keys: dict[str, str] = field(default_factory=dict)   # control id -> KEY_* ('' = unbound)
    alt: dict[str, str] = field(default_factory=dict)    # control id -> alternate KEY_* ('' = none)

    def label(self, control_id: str) -> str:
        c = CONTROL_BY_ID[control_id]
        return c.ps if self.label_set == "ps2" else c.xbox

    def key_for(self, control_id: str) -> str:
        return self.keys.get(control_id, "")

    def alt_for(self, control_id: str) -> str:
        return self.alt.get(control_id, "")

    def find_key(self, key: str) -> tuple[str, str] | None:
        """(control id, 'main' | 'alt') currently using this key."""
        for cid, k in self.keys.items():
            if k == key:
                return cid, "main"
        for cid, k in self.alt.items():
            if k == key:
                return cid, "alt"
        return None

    def control_for_key(self, key: str) -> str | None:
        found = self.find_key(key)
        return found[0] if found else None

    def bind(self, control_id: str, key: str, slot: str = "main") -> str | None:
        """Bind key to control (main or alternate slot). A key drives one control only;
        returns the control it was taken from, if any."""
        target = self.keys if slot == "main" else self.alt
        previous = None
        if key:
            found = self.find_key(key)
            if found and found != (control_id, slot):
                prev_cid, prev_slot = found
                (self.keys if prev_slot == "main" else self.alt)[prev_cid] = ""
                previous = prev_cid if prev_cid != control_id else None
        target[control_id] = key
        if slot == "main" and not key and self.alt.get(control_id):
            target[control_id], self.alt[control_id] = self.alt[control_id], ""   # promote the alternate
        return previous

    def all_bindings(self) -> list[tuple[str, str]]:
        """(key, control) for every main and alternate key."""
        out = [(k, c) for c, k in self.keys.items() if k]
        out += [(k, c) for c, k in self.alt.items() if k]
        return out

    def copy(self, **changes) -> "Profile":
        data = dict(id=self.id, name=self.name, label_set=self.label_set,
                    builtin=self.builtin, keys=dict(self.keys), alt=dict(self.alt))
        data.update(changes)
        return Profile(**data)

    # --- file format -------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict, fallback_id: str = "profile") -> "Profile":
        version = data.get("schema_version", 1)
        if version > SCHEMA_VERSION:
            raise ProfileError(f"profile schema {version} is newer than this app supports")
        keys = {cid: "" for cid in CONTROL_IDS}
        for cid, key in data.get("buttons", {}).items():
            if cid in _BUTTON_IDS:
                keys[cid] = _checked_key(key)
        for cid, key in data.get("triggers", {}).items():
            if cid in _TRIGGER_IDS:
                keys[cid] = _checked_key(key)
        for section, axes in _PAIRS.items():
            for axis, (neg, pos) in axes.items():
                pair = data.get(section, {}).get(axis)
                if pair:
                    if not isinstance(pair, list) or len(pair) != 2:
                        raise ProfileError(f"[{section}] {axis} must be [negative, positive]")
                    keys[neg], keys[pos] = _checked_key(pair[0]), _checked_key(pair[1])
        alt = {cid: "" for cid in CONTROL_IDS}
        for cid, key in data.get("alternates", {}).items():
            if cid in alt:
                alt[cid] = _checked_key(key)
        label_set = data.get("label_set", "ps2")
        if label_set not in ("ps2", "xbox"):
            label_set = "ps2"
        return cls(id=str(data.get("id", fallback_id)), name=str(data.get("name", fallback_id)),
                   label_set=label_set, builtin=bool(data.get("builtin", False)), keys=keys, alt=alt)

    def to_toml(self) -> str:
        out = [f"schema_version = {SCHEMA_VERSION}", f"id = {_q(self.id)}", f"name = {_q(self.name)}",
               f"builtin = {'true' if self.builtin else 'false'}", f"label_set = {_q(self.label_set)}", ""]
        out.append("[buttons]")
        out += [f"{cid:<11}= {_q(self.key_for(cid))}" for cid in _BUTTON_IDS]
        out += ["", "[triggers]"]
        out += [f"{cid:<7}= {_q(self.key_for(cid))}" for cid in _TRIGGER_IDS]
        out.append("")
        out.append("# Pairs are [negative, positive] = [left, right] or [up, down].")
        for section, axes in _PAIRS.items():
            out.append(f"[{section}]")
            for axis, (neg, pos) in axes.items():
                out.append(f"{axis} = [{_q(self.key_for(neg))}, {_q(self.key_for(pos))}]")
            out.append("")
        alts = [(cid, k) for cid, k in self.alt.items() if k]
        if alts:
            out.append("# Second key for the same button.")
            out.append("[alternates]")
            out += [f"{cid} = {_q(k)}" for cid, k in alts]
            out.append("")
        return "\n".join(out)


def _checked_key(key) -> str:
    if not key:
        return ""
    key = str(key)
    if name_to_code(key) is None:
        log.warning("E022 unknown key name in profile: %s (ignored)", key)
        return ""
    return key


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def load_file(path: Path) -> Profile:
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ProfileError(f"{path.name}: {e}") from e
    return Profile.from_dict(data, fallback_id=path.stem)


def builtin_profiles() -> dict[str, Profile]:
    result = {}
    for path in sorted(BUILTIN_PROFILES_DIR.glob("*.toml")):
        try:
            p = load_file(path)
            p.builtin = True
            result[p.id] = p
        except ProfileError as e:
            log.error("E020 built-in profile broken: %s", e)
    return result


def user_profiles() -> dict[str, Profile]:
    result = {}
    if USER_PROFILES_DIR.is_dir():
        for path in sorted(USER_PROFILES_DIR.glob("*.toml")):
            try:
                p = load_file(path)
                p.builtin = False
                result[p.id] = p
            except ProfileError as e:
                log.error("E020 user profile skipped: %s", e)
    return result


def all_profiles() -> dict[str, Profile]:
    profiles = builtin_profiles()
    profiles.update(user_profiles())
    return profiles


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "profile"


def save_user_profile(profile: Profile) -> Path:
    USER_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = USER_PROFILES_DIR / f"{slug(profile.id)}.toml"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(profile.to_toml())
    tmp.replace(path)
    return path


def delete_user_profile(profile_id: str) -> None:
    path = USER_PROFILES_DIR / f"{slug(profile_id)}.toml"
    path.unlink(missing_ok=True)


def player_profile_id(player: int) -> str:
    """Each player edits their own live copy: 'player1', 'player2', ..."""
    return f"player{player}"


def default_preset_for(player: int) -> str:
    return "default-p2" if player == 2 else "default-p1"


# --- kb2xbox import ----------------------------------------------------------

# kb2xbox axis lines list keys from the negative end to the positive end ("ABS_X=KEY_A,KEY_D").
_KB2XBOX_AXES = {"ABS_X": ("LS_LEFT", "LS_RIGHT"), "ABS_Y": ("LS_UP", "LS_DOWN"),
                 "ABS_RX": ("RS_LEFT", "RS_RIGHT"), "ABS_RY": ("RS_UP", "RS_DOWN"),
                 "ABS_HAT0X": ("DPAD_LEFT", "DPAD_RIGHT"), "ABS_HAT0Y": ("DPAD_UP", "DPAD_DOWN")}
_KB2XBOX_ALIASES = {"BTN_A": "BTN_SOUTH", "BTN_B": "BTN_EAST", "BTN_X": "BTN_NORTH", "BTN_Y": "BTN_WEST",
                    "BTN_GAMEPAD": "BTN_SOUTH"}


def import_kb2xbox(text: str, profile_id: str, name: str) -> tuple[Profile, list[str]]:
    """Convert a kb2xbox .cfg (NAME=value lines) into a profile. Returns (profile, notes)."""
    p = Profile(id=profile_id, name=name, label_set="ps2", keys={c: "" for c in CONTROL_IDS},
                alt={c: "" for c in CONTROL_IDS})
    notes: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if len(line) <= 1 or line.startswith("#") or "=" not in line:
            continue
        code, _, value = line.partition("=")
        code = _KB2XBOX_ALIASES.get(code.strip(), code.strip())
        keys = [k.strip() for k in value.split(",") if k.strip()]
        if code in ("NAME", "VENDOR", "PRODUCT", "VERSION") or not keys:
            continue
        bad = [k for k in keys if name_to_code(k) is None]
        if bad:
            notes.append(f"line {lineno}: unknown key {', '.join(bad)} skipped")
            keys = [k for k in keys if k not in bad]
            if not keys:
                continue
        if code in _BUTTON_IDS or code in _TRIGGER_IDS:
            # triggers: kb2xbox steps up per key; the last key is the full press
            main = keys[-1] if code in _TRIGGER_IDS else keys[0]
            p.bind(code, main)
            extra = [k for k in keys if k != main]
            if extra:
                p.bind(code, extra[0], "alt")
                if len(extra) > 1:
                    notes.append(f"line {lineno}: {code} has more than 2 keys; extra keys dropped")
        elif code in _KB2XBOX_AXES:
            neg, pos = _KB2XBOX_AXES[code]
            if len(keys) == 1:
                notes.append(f"line {lineno}: {code} has one key; used as {pos}")
                p.bind(pos, keys[0])
            else:
                p.bind(neg, keys[0])
                p.bind(pos, keys[-1])
                if len(keys) > 2:
                    notes.append(f"line {lineno}: {code} has {len(keys)} keys (partial tilt); "
                                 "kept the two outer keys")
        else:
            notes.append(f"line {lineno}: {code} is not supported, skipped")
    return p, notes
