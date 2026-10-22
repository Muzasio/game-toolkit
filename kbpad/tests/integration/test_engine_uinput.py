"""End-to-end engine test with a fake keyboard (uinput). Never touches real keyboards.

Run: python3 -m unittest discover -s tests -t .   (from the repo root, with src on PYTHONPATH)
"""

import os
import time
import unittest

from evdev import InputDevice, UInput, ecodes as e, list_devices

from kbpad import engine as eng
from kbpad.profiles import builtin_profiles

HAVE_UINPUT = os.access("/dev/uinput", os.W_OK)
KEYS = [e.KEY_A, e.KEY_D, e.KEY_W, e.KEY_S, e.KEY_K, e.KEY_Z, e.KEY_SPACE, e.KEY_ENTER, e.KEY_P,
        e.KEY_LEFTCTRL, e.KEY_LEFTSHIFT, e.KEY_F1, e.KEY_F12, e.KEY_UP, e.KEY_LEFT, e.KEY_PAUSE]


def wait(cond, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


@unittest.skipUnless(HAVE_UINPUT, "needs writable /dev/uinput")
class EngineTest(unittest.TestCase):
    def setUp(self):
        self.kbd = UInput({e.EV_KEY: KEYS}, name="kbpad-test-keyboard", phys="kbpad-test-usb/input0",
                          bustype=e.BUS_USB, vendor=0x1234, product=0x5678)
        time.sleep(0.3)
        self.engine = eng.Engine()
        self.assertTrue(self.engine.create_pads(2), self.engine.pad_error)
        self.engine.set_profile(1, builtin_profiles()["default-p1"])
        self.engine.rescan(force=True)
        self.key = next(k for k, kb in self.engine.keyboards.items() if kb.name == "kbpad-test-keyboard")
        self.engine.assign(self.key, 1)
        path = next(p for p in list_devices() if InputDevice(p).name == "XBOX Controller P1")
        self.pad = InputDevice(path)

    def tearDown(self):
        self.engine.stop()
        self.kbd.close()

    def tap(self, *codes, value=None):
        for c in codes:
            self.kbd.write(e.EV_KEY, c, 1 if value is None else value)
        self.kbd.syn()

    def release(self, *codes):
        for c in codes:
            self.kbd.write(e.EV_KEY, c, 0)
        self.kbd.syn()

    def view(self):
        return next(v for v in self.engine.views() if v.key == self.key)

    def test_button_and_axis(self):
        self.tap(e.KEY_K)
        self.assertTrue(wait(lambda: self.pad.active_keys() == [e.BTN_SOUTH]))
        self.release(e.KEY_K)
        self.assertTrue(wait(lambda: self.pad.active_keys() == []))
        self.tap(e.KEY_A)
        self.assertTrue(wait(lambda: self.pad.absinfo(e.ABS_X).value == -32768))
        self.tap(e.KEY_D)       # opposite held together -> centre
        self.assertTrue(wait(lambda: self.pad.absinfo(e.ABS_X).value == 0))
        self.release(e.KEY_A)
        self.assertTrue(wait(lambda: self.pad.absinfo(e.ABS_X).value == 32767))
        self.release(e.KEY_D)
        self.tap(e.KEY_SPACE)
        self.assertTrue(wait(lambda: self.pad.absinfo(e.ABS_RZ).value == 255))
        self.release(e.KEY_SPACE)
        self.tap(e.KEY_UP)
        self.assertTrue(wait(lambda: self.pad.absinfo(e.ABS_HAT0Y).value == -1))
        self.release(e.KEY_UP)

    def test_ctrl_f1_grabs_after_release_and_toggles_back(self):
        self.tap(e.KEY_LEFTCTRL)
        self.tap(e.KEY_F1)
        self.assertTrue(wait(lambda: self.view().state == eng.WAITING))
        self.release(e.KEY_F1, e.KEY_LEFTCTRL)
        self.assertTrue(wait(lambda: self.view().state == eng.GRABBED))
        self.tap(e.KEY_LEFTCTRL); self.tap(e.KEY_F1); self.release(e.KEY_F1, e.KEY_LEFTCTRL)
        self.assertTrue(wait(lambda: self.view().state == eng.FREE))

    def test_gui_grab_and_panic(self):
        self.engine.grab(self.key)
        self.assertTrue(wait(lambda: self.view().state == eng.GRABBED))
        self.tap(e.KEY_LEFTCTRL); self.tap(e.KEY_LEFTSHIFT); self.tap(e.KEY_F12)
        self.assertTrue(wait(lambda: self.view().state == eng.FREE))
        self.release(e.KEY_F12, e.KEY_LEFTSHIFT, e.KEY_LEFTCTRL)

    def test_capture_consumes_key(self):
        self.engine.begin_capture()
        self.tap(e.KEY_K)
        self.assertTrue(wait(lambda: self.engine._capture_result is not None))
        kb_key, code, _held = self.engine.poll_capture()
        self.assertEqual((kb_key, code), (self.key, e.KEY_K))
        time.sleep(0.1)
        self.assertEqual(self.pad.active_keys(), [])     # captured key did not press Cross
        self.release(e.KEY_K)

    def test_unplug_keeps_pad(self):
        pad_path = self.pad.path
        self.tap(e.KEY_K)
        self.assertTrue(wait(lambda: self.pad.active_keys() == [e.BTN_SOUTH]))
        self.kbd.close()
        self.assertTrue(wait(lambda: self.pad.active_keys() == []))   # no stuck button
        self.engine.rescan()
        self.assertTrue(wait(lambda: self.view().state == eng.DISCONNECTED))
        self.assertTrue(os.path.exists(pad_path))
        self.kbd = UInput({e.EV_KEY: KEYS}, name="kbpad-test-keyboard", phys="kbpad-test-usb/input0",
                          bustype=e.BUS_USB, vendor=0x1234, product=0x5678)
        time.sleep(0.3)
        self.engine.rescan()
        self.assertTrue(wait(lambda: self.view().state == eng.FREE))
        self.tap(e.KEY_K)
        self.assertTrue(wait(lambda: self.pad.active_keys() == [e.BTN_SOUTH]))
        self.release(e.KEY_K)

    def test_custom_hotkey(self):
        self.engine.set_hotkeys(["KEY_PAUSE"], ["CTRL", "SHIFT", "KEY_F12"])
        self.tap(e.KEY_LEFTCTRL); self.tap(e.KEY_F1); self.release(e.KEY_F1, e.KEY_LEFTCTRL)
        time.sleep(0.2)
        self.assertEqual(self.view().state, eng.FREE)          # old hotkey no longer grabs
        self.tap(e.KEY_PAUSE); self.release(e.KEY_PAUSE)
        self.assertTrue(wait(lambda: self.view().state == eng.GRABBED))
        self.tap(e.KEY_PAUSE); self.release(e.KEY_PAUSE)
        self.assertTrue(wait(lambda: self.view().state == eng.FREE))

    def test_socd_last_pressed_wins(self):
        self.engine.set_socd(1, "last")
        self.tap(e.KEY_A)
        self.tap(e.KEY_D)
        self.assertTrue(wait(lambda: self.pad.absinfo(e.ABS_X).value == 32767))   # D pressed last
        self.release(e.KEY_D)
        self.assertTrue(wait(lambda: self.pad.absinfo(e.ABS_X).value == -32768))  # A still held
        self.release(e.KEY_A)
        self.assertTrue(wait(lambda: self.pad.absinfo(e.ABS_X).value == 0))

    def test_alternate_key(self):
        prof = builtin_profiles()["default-p1"].copy()
        prof.bind("BTN_SOUTH", "KEY_P", "alt")
        self.engine.set_profile(1, prof)
        self.tap(e.KEY_P)
        self.assertTrue(wait(lambda: self.pad.active_keys() == [e.BTN_SOUTH]))
        self.tap(e.KEY_K)                   # both keys for Cross held
        self.release(e.KEY_P)
        time.sleep(0.15)
        self.assertEqual(self.pad.active_keys(), [e.BTN_SOUTH])   # K still holds it
        self.release(e.KEY_K)
        self.assertTrue(wait(lambda: self.pad.active_keys() == []))

    def test_ghost_counter(self):
        self.tap(e.KEY_A); self.tap(e.KEY_D); self.tap(e.KEY_K)
        self.assertTrue(wait(lambda: self.engine.held_keys(self.key)[1] == 3))
        self.release(e.KEY_A, e.KEY_D, e.KEY_K)
        self.assertTrue(wait(lambda: self.engine.held_keys(self.key)[0] == []))
        self.engine.reset_max_held(self.key)
        self.assertEqual(self.engine.held_keys(self.key)[1], 0)


@unittest.skipUnless(HAVE_UINPUT, "needs writable /dev/uinput")
class IdenticalKeyboardsTest(unittest.TestCase):
    """Two keyboards of the same model drive two different players."""

    def setUp(self):
        self.kbds = [UInput({e.EV_KEY: KEYS}, name="Same Model Keyboard", phys=f"same-usb-{i}/input0",
                            bustype=e.BUS_USB, vendor=0x4321, product=0x8765) for i in (1, 2)]
        time.sleep(0.3)
        self.engine = eng.Engine()
        self.engine.create_pads(2)
        for n in (1, 2):
            self.engine.set_profile(n, builtin_profiles()["default-p1"])
        self.engine.rescan(force=True)

    def tearDown(self):
        self.engine.stop()
        for k in self.kbds:
            k.close()

    def test_two_identical(self):
        keys = sorted(k for k, kb in self.engine.keyboards.items() if kb.name == "Same Model Keyboard")
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])
        by_phys = {self.engine.keyboards[k].phys: k for k in keys}
        self.engine.assign(by_phys["same-usb-1"], 1)
        self.engine.assign(by_phys["same-usb-2"], 2)
        pads = {InputDevice(p).name: InputDevice(p) for p in list_devices()}
        p1, p2 = pads["XBOX Controller P1"], pads["XBOX Controller P2"]
        self.kbds[1].write(e.EV_KEY, e.KEY_K, 1); self.kbds[1].syn()
        self.assertTrue(wait(lambda: p2.active_keys() == [e.BTN_SOUTH]))
        self.assertEqual(p1.active_keys(), [])
        self.kbds[1].write(e.EV_KEY, e.KEY_K, 0); self.kbds[1].syn()


if __name__ == "__main__":
    unittest.main()
