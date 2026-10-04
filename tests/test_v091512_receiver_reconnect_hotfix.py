from types import SimpleNamespace

from src.ptt import PTTConfig, PTTController
from src.wheel_telemetry import WheelTelemetryBridge


class _Recorder:
    def __init__(self):
        self.aborts = 0
    def abort(self):
        self.aborts += 1


def test_usb_identity_match_survives_com_number_change():
    identity = {"vid": 0x303A, "pid": 0x1001, "serial_number": "ABC123", "location": "1-2"}
    moved = SimpleNamespace(vid=0x303A, pid=0x1001, serial_number="ABC123", location="1-4")
    wrong = SimpleNamespace(vid=0x303A, pid=0x1001, serial_number="OTHER", location="1-4")
    assert WheelTelemetryBridge._identity_matches(moved, identity)
    assert not WheelTelemetryBridge._identity_matches(wrong, identity)


def test_usb_identity_can_fall_back_to_physical_location_without_serial():
    identity = {"vid": 0x303A, "pid": 0x1001, "serial_number": None, "location": "1-2"}
    same = SimpleNamespace(vid=0x303A, pid=0x1001, serial_number=None, location="1-2")
    other = SimpleNamespace(vid=0x303A, pid=0x1001, serial_number=None, location="1-3")
    assert WheelTelemetryBridge._identity_matches(same, identity)
    assert not WheelTelemetryBridge._identity_matches(other, identity)


def test_hid_ptt_retries_after_receiver_read_error():
    recorder = _Recorder()
    ptt = PTTController(PTTConfig(enabled=True, backend="hid"), recorder=recorder)
    calls = []
    def fake_run(external_stop=None, *, reconnect=False):
        calls.append(reconnect)
        if len(calls) == 1:
            ptt._hid_ever_opened = True
            raise OSError("read error")
        ptt._stop.set()
    ptt._run_hid = fake_run
    ptt._run()
    assert calls == [False, True]
    assert recorder.aborts == 1
    assert ptt.last_error == "read error"
