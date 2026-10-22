"""Hardware-free tests: profile files, key names, pad state logic."""

import unittest

from evdev import ecodes as e

from kbpad import profiles
from kbpad.keynames import code_to_name, name_to_code, pretty, short
from kbpad.pad import compute_state


class ProfileTest(unittest.TestCase):
    def test_builtins_load(self):
        built = profiles.builtin_profiles()
        for pid in ("default-p1", "default-p2", "xbox-360", "ps2-dualshock2"):
            self.assertIn(pid, built)
        p1 = built["default-p1"]
        self.assertEqual(p1.key_for("BTN_SOUTH"), "KEY_K")
        self.assertEqual(p1.key_for("LS_LEFT"), "KEY_A")
        self.assertEqual(p1.key_for("DPAD_UP"), "KEY_UP")

    def test_roundtrip(self):
        import tomllib
        p = profiles.builtin_profiles()["default-p2"]
        again = profiles.Profile.from_dict(tomllib.loads(p.to_toml()))
        self.assertEqual(again.keys, p.keys)
        self.assertEqual(again.label_set, p.label_set)

    def test_bind_moves_key(self):
        p = profiles.builtin_profiles()["default-p1"].copy()
        moved = p.bind("BTN_EAST", "KEY_K")          # K was Cross
        self.assertEqual(moved, "BTN_SOUTH")
        self.assertEqual(p.key_for("BTN_SOUTH"), "")
        self.assertEqual(p.key_for("BTN_EAST"), "KEY_K")

    def test_unknown_key_ignored(self):
        p = profiles.Profile.from_dict({"buttons": {"BTN_SOUTH": "KEY_NOPE"}})
        self.assertEqual(p.key_for("BTN_SOUTH"), "")

    def test_newer_schema_rejected(self):
        with self.assertRaises(profiles.ProfileError):
            profiles.Profile.from_dict({"schema_version": 99})


class Kb2xboxImportTest(unittest.TestCase):
    CFG = """# P2 bloody
NAME=XBOX Controller
VENDOR=0x045e
BTN_SOUTH=KEY_8
BTN_EAST=KEY_9
BTN_NORTH=KEY_7
BTN_WEST=KEY_0
BTN_TL=KEY_U
ABS_Z=KEY_6
ABS_HAT0X=KEY_F,KEY_H
ABS_HAT0Y=KEY_T,KEY_G
ABS_X=KEY_J,KEY_L
BTN_START=KEY_RIGHTSHIFT,KEY_KPENTER
ABS_RX=KEY_NOPE
FF_RUMBLE=KEY_Q
"""

    def test_import(self):
        p, notes = profiles.import_kb2xbox(self.CFG, "x", "x")
        self.assertEqual(p.key_for("BTN_SOUTH"), "KEY_8")
        self.assertEqual(p.key_for("DPAD_LEFT"), "KEY_F")      # first key = negative
        self.assertEqual(p.key_for("DPAD_RIGHT"), "KEY_H")
        self.assertEqual(p.key_for("DPAD_UP"), "KEY_T")
        self.assertEqual(p.key_for("LS_RIGHT"), "KEY_L")
        self.assertEqual(p.key_for("ABS_Z"), "KEY_6")
        self.assertEqual(p.alt_for("BTN_START"), "KEY_KPENTER")
        self.assertTrue(any("KEY_NOPE" in n for n in notes))
        self.assertTrue(any("FF_RUMBLE" in n for n in notes))


class AlternateKeyTest(unittest.TestCase):
    def test_alt_roundtrip_and_promote(self):
        import tomllib
        p = profiles.builtin_profiles()["default-p1"].copy()
        p.bind("BTN_SOUTH", "KEY_P", "alt")
        again = profiles.Profile.from_dict(tomllib.loads(p.to_toml()))
        self.assertEqual(again.alt_for("BTN_SOUTH"), "KEY_P")
        again.bind("BTN_SOUTH", "")                    # clearing main promotes the alternate
        self.assertEqual(again.key_for("BTN_SOUTH"), "KEY_P")
        self.assertEqual(again.alt_for("BTN_SOUTH"), "")

    def test_key_unique_across_slots(self):
        p = profiles.builtin_profiles()["default-p1"].copy()
        moved = p.bind("BTN_EAST", "KEY_K", "alt")     # K was Cross main
        self.assertEqual(moved, "BTN_SOUTH")
        self.assertEqual(p.key_for("BTN_SOUTH"), "")


class SocdTest(unittest.TestCase):
    def test_modes(self):
        both = {"LS_LEFT", "LS_RIGHT", "DPAD_UP", "DPAD_DOWN"}
        order = {"LS_LEFT": 1, "LS_RIGHT": 2, "DPAD_UP": 4, "DPAD_DOWN": 3}
        n = compute_state(both, order, "neutral")
        self.assertEqual(n[(e.EV_ABS, e.ABS_X)], 0)
        last = compute_state(both, order, "last")
        self.assertEqual(last[(e.EV_ABS, e.ABS_X)], 32767)
        self.assertEqual(last[(e.EV_ABS, e.ABS_HAT0Y)], -1)
        hit = compute_state(both, order, "hitbox")
        self.assertEqual(hit[(e.EV_ABS, e.ABS_X)], 0)
        self.assertEqual(hit[(e.EV_ABS, e.ABS_HAT0Y)], -1)


class IdentityTest(unittest.TestCase):
    def kb(self, by_id, by_path, phys):
        from kbpad.devices import Keyboard
        return Keyboard(key="", name="Same", vendor=1, product=2, nodes=["/dev/input/event1"],
                        by_id=by_id, by_path=by_path, phys=phys)

    def test_identical_without_serial_use_port(self):
        from kbpad.devices import _assign_keys
        a = self.kb("usb-Same-event-kbd", "pci-0-usb-0:1:1.0-event-kbd", "usb-x-1")
        b = self.kb("", "pci-0-usb-0:2:1.0-event-kbd", "usb-x-2")   # udev gave the link to only one
        _assign_keys([a, b])
        self.assertTrue(a.key.startswith("path:") and b.key.startswith("path:"))
        self.assertNotEqual(a.key, b.key)

    def test_identical_with_serials_keep_id(self):
        from kbpad.devices import _assign_keys
        a = self.kb("usb-Same_SER1-event-kbd", "p1-event-kbd", "usb-x-1")
        b = self.kb("usb-Same_SER2-event-kbd", "p2-event-kbd", "usb-x-2")
        _assign_keys([a, b])
        self.assertEqual({a.key, b.key}, {"id:usb-Same_SER1", "id:usb-Same_SER2"})

    def test_single_keeps_id(self):
        from kbpad.devices import _assign_keys
        a = self.kb("usb-COMPANY_USB_Device-if02-event-kbd", "p-event-kbd", "usb-x-1")
        _assign_keys([a])
        self.assertEqual(a.key, "id:usb-COMPANY_USB_Device")


class Pcsx2IniTest(unittest.TestCase):
    INI = """[UI]
Theme = dark

[InputSources]
Keyboard = true
SDL = false

[Pad1]
Type = DualShock2
Cross = SDL-0/A
Deadzone = 0.1
"""

    def test_write(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from kbpad import pcsx2
        with tempfile.TemporaryDirectory() as d:
            ini = Path(d) / "PCSX2.ini"
            ini.write_text(self.INI)
            with mock.patch.object(pcsx2, "is_running", return_value=False):
                backup, style = pcsx2.write_controller_setup(ini, 2, backup_dir=Path(d) / "bk")
            text = ini.read_text()
            self.assertEqual(style, "old")                  # detected from "SDL-0/A"
            self.assertIn("SDL = true", text)
            self.assertNotIn("SDL = false", text)
            self.assertIn("Cross = SDL-0/A", text)
            self.assertIn("Deadzone = 0.1", text)           # other Pad settings kept
            self.assertIn("[Pad2]", text)
            self.assertIn("Cross = SDL-1/A", text)
            self.assertIn("L2 = SDL-1/+LeftTrigger", text)
            self.assertIn("LUp = SDL-0/-LeftY", text)
            self.assertIn("Theme = dark", text)
            self.assertEqual(backup.read_text(), self.INI)
            self.assertEqual(pcsx2.detect_style("Cross = SDL-0/FaceSouth"), "new")

    def test_refuses_while_running(self):
        from pathlib import Path
        from unittest import mock
        from kbpad import pcsx2
        with mock.patch.object(pcsx2, "is_running", return_value=True):
            with self.assertRaises(pcsx2.IniError):
                pcsx2.write_controller_setup(Path("/nonexistent"), 2)


class KeyNameTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(code_to_name(e.KEY_A), "KEY_A")
        self.assertEqual(name_to_code("KEY_SPACE"), e.KEY_SPACE)
        self.assertIsNone(name_to_code("KEY_DOES_NOT_EXIST"))
        self.assertEqual(pretty("KEY_LEFTSHIFT"), "L-Shift")
        self.assertEqual(pretty(""), "—")
        self.assertLessEqual(len(short("KEY_BACKSPACE")), 6)


class PadStateTest(unittest.TestCase):
    def test_neutral(self):
        s = compute_state(set())
        self.assertEqual(s[(e.EV_ABS, e.ABS_X)], 0)
        self.assertEqual(s[(e.EV_KEY, e.BTN_SOUTH)], 0)

    def test_directions_and_cancel(self):
        self.assertEqual(compute_state({"LS_LEFT"})[(e.EV_ABS, e.ABS_X)], -32768)
        self.assertEqual(compute_state({"LS_UP"})[(e.EV_ABS, e.ABS_Y)], -32768)
        self.assertEqual(compute_state({"LS_LEFT", "LS_RIGHT"})[(e.EV_ABS, e.ABS_X)], 0)
        self.assertEqual(compute_state({"DPAD_DOWN"})[(e.EV_ABS, e.ABS_HAT0Y)], 1)
        self.assertEqual(compute_state({"ABS_Z"})[(e.EV_ABS, e.ABS_Z)], 255)
        self.assertEqual(compute_state({"BTN_START"})[(e.EV_KEY, e.BTN_START)], 1)


if __name__ == "__main__":
    unittest.main()
