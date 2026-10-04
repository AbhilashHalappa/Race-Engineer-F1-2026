import unittest
from pathlib import Path
from src.ptt import PTTConfig, PTTController

class FakeRecorder:
    def __init__(self): self.started=0; self.stopped=0; self.aborted=0
    def start(self): self.started += 1
    def stop(self): self.stopped += 1; return Path('fake.wav')
    def abort(self): self.aborted += 1

class PTTTests(unittest.TestCase):
    def test_capture_callback_receives_completed_wav(self):
        r=FakeRecorder(); captures=[]; p=PTTController(PTTConfig(enabled=True), r, on_capture=captures.append)
        p._handle_button(True); p._handle_button(False)
        self.assertEqual(captures, [Path("fake.wav")])

    def test_press_hold_release_edges_only(self):
        r=FakeRecorder(); p=PTTController(PTTConfig(enabled=True), r)
        p._handle_button(True); p._handle_button(True); p._handle_button(False); p._handle_button(False)
        self.assertEqual((r.started,r.stopped),(1,1)); self.assertEqual(p.last_capture,Path('fake.wav'))
    def test_disabled_start_does_not_create_thread(self):
        p=PTTController(PTTConfig(enabled=False), FakeRecorder()); p.start(); self.assertIsNone(p._thread)
    def test_config_defaults_to_16khz_mono(self):
        c=PTTConfig(); self.assertEqual((c.sample_rate,c.channels),(16000,1))
    def test_main_thread_poll_entrypoint_exists(self):
        p=PTTController(PTTConfig(enabled=True), FakeRecorder())
        self.assertTrue(callable(p.run_forever))

class HIDSignatureTests(unittest.TestCase):
    def test_hid_signature_finds_stable_changed_bit(self):
        base = bytes([0x00, 0x10])
        held = bytes([0x80, 0x10])
        variable = bytes([0x00, 0x10])
        sig = PTTController._bit_signature(base, held, variable)
        self.assertEqual(sig, [(0, 0x80, 1)])
        self.assertTrue(PTTController._signature_pressed(held, sig))
        self.assertFalse(PTTController._signature_pressed(base, sig))

class HIDDeviceConfigTests(unittest.TestCase):
    def test_esp32_s3_raw_hid_defaults(self):
        c = PTTConfig()
        self.assertEqual(c.button_index, 6)
        self.assertEqual((c.hid_vendor_id, c.hid_product_id), (0x303A, 0x1001))
        self.assertEqual((c.hid_usage_page, c.hid_usage), (0x0001, 0x0005))

class HIDVerifiedCalibrationTests(unittest.TestCase):
    def test_verified_signature_rejects_axis_noise_and_finds_button(self):
        # byte0 bit2 is the button. byte1 changes like an axis/noisy report.
        released_before = [bytes([0x00, x]) for x in (100,101,99,100)]
        held = [bytes([0x04, x]) for x in (103,102,104,101)]
        released_after = [bytes([0x00, x]) for x in (98,100,101,99)]
        sig = PTTController._verified_button_signature(released_before, held, released_after)
        self.assertEqual(sig, [(0, 0x04, 1)])

    def test_verified_signature_rejects_ambiguous_two_bit_change(self):
        released_before = [bytes([0x00])] * 4
        held = [bytes([0x03])] * 4
        released_after = [bytes([0x00])] * 4
        self.assertEqual(PTTController._verified_button_signature(released_before, held, released_after), [])

    def test_verified_signature_requires_release_to_original_state(self):
        released_before = [bytes([0x00])] * 4
        held = [bytes([0x04])] * 4
        released_after = [bytes([0x04])] * 4
        self.assertEqual(PTTController._verified_button_signature(released_before, held, released_after), [])
