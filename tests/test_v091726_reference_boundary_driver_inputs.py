from pathlib import Path
from types import SimpleNamespace
import threading

from src.race_state_receiver import RaceStateReceiver


class Perf:
    def __init__(self):
        self.reference_mode = "best"
        self.external_reference = None
        self.external_reference_name = None
        self.external_reference_meta = {}
        self.manual_reference_lap = None

    def set_external_reference(self, lap, *, name=None, metadata=None):
        self.external_reference = lap
        self.external_reference_name = name
        self.external_reference_meta = dict(metadata or {})
        self.reference_mode = "external"
        return True


def make_receiver(distance, lap_time, track_id=0):
    r = RaceStateReceiver.__new__(RaceStateReceiver)
    r._state_lock = threading.RLock()
    lap = SimpleNamespace(lap_distance_m=distance, current_lap_time_s=lap_time)
    session = SimpleNamespace(track=SimpleNamespace(raw=track_id))
    r.engine = SimpleNamespace(state=SimpleNamespace(player=SimpleNamespace(lap=lap), session=session), performance=Perf())
    r._manual_reference_path = None
    r._manual_reference_lap = None
    r._manual_reference_meta = {}
    r._manual_reference_suspended_reason = None
    r._pending_reference_selection = None
    r._pending_reference_lap = None
    r._pending_reference_meta = {}
    return r


def test_reference_pending_waits_until_lap_start():
    r = make_receiver(2500.0, 40.0)
    pending = {"lap": 2, "_samples": {0.0: {"d": 0.0, "t": 0.0}}}
    r._queue_reference_selection_locked(Path("references/fast.json"), pending, {"track_id": 0, "driver": "Fast"})
    applied, _ = r._apply_pending_reference_locked()
    assert applied is False
    assert r.engine.performance.reference_mode == "best"
    assert r._pending_reference_selection is not None

    r.engine.state.player.lap.lap_distance_m = 5.0
    r.engine.state.player.lap.current_lap_time_s = 0.2
    applied, _ = r._apply_pending_reference_locked()
    assert applied is True
    assert r.engine.performance.reference_mode == "external"
    assert r.engine.performance.external_reference is pending
    assert r._pending_reference_selection is None


def test_pending_reference_track_mismatch_is_not_applied():
    r = make_receiver(5.0, 0.2, track_id=1)
    pending = {"lap": 2, "_samples": {0.0: {"d": 0.0, "t": 0.0}}}
    r._queue_reference_selection_locked(Path("references/melbourne.json"), pending, {"track_id": 0, "driver": "Fast"})
    applied, reason = r._apply_pending_reference_locked()
    assert applied is False
    assert "does not match" in reason
    assert r.engine.performance.reference_mode == "best"


def test_driver_inputs_default_placement_is_screen_clamped_and_label_is_clear():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'Driver Inputs — throttle / brake / ERS' in source
    assert 'r.bottom() - self.driver.height() - 20' in source
    assert 'self.driver.move(driver_x, driver_y)' in source


def test_current_banner():
    source = Path("src/main.py").read_text(encoding="utf-8")
    assert 'V0.9.17.2.6 LAP-BOUNDARY REFERENCE + DRIVER INPUTS VISIBILITY' in source
