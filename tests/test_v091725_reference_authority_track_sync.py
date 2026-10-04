import json
from pathlib import Path
from types import SimpleNamespace

from src.measured_performance import MeasuredPerformanceRecorder, Sample
from src.race_state_receiver import RaceStateReceiver
from src.telemetry.enums import EnumValue
from src.overlay.data import _aligned_live_trace


def _payload(track_id=0, lap_time=77.338, driver="Fast Rival"):
    return {
        "format": "RACE_ENGINEER_REFERENCE_LAP",
        "version": "1.0",
        "metadata": {"driver": driver, "source": "EA_F1_TIME_TRIAL_RIVAL", "track_id": track_id},
        "lap": {
            "lap": 2,
            "valid": True,
            "sample_count": 20,
            "lap_time_s": lap_time,
            "sections": [],
            "_samples": {
                str(float(i * 5)): {
                    "d": float(i * 5), "t": i * 0.05, "speed": 300.0,
                    "throttle": 1.0, "brake": 0.0, "steering": 0.0,
                    "gear": 8, "rpm": 11000,
                }
                for i in range(20)
            },
        },
    }


def _write_ref(tmp_path, *, track_id=0, name="ref.json"):
    p = tmp_path / name
    p.write_text(json.dumps(_payload(track_id=track_id)), encoding="utf-8")
    return p


def test_manual_reference_survives_replay_state_reset(tmp_path):
    r = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    p = _write_ref(tmp_path)
    ok, _ = r.select_reference_lap(str(p))
    assert ok
    before = r.engine.performance.external_reference["lap_time_s"]
    r.reset_replay_state()
    assert r.current_reference_selection() == str(p)
    assert r.engine.performance.reference_mode == "external"
    assert r.engine.performance.external_reference["lap_time_s"] == before


def test_clearing_manual_reference_forces_current_session_best(tmp_path):
    r = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    p = _write_ref(tmp_path)
    assert r.select_reference_lap(str(p))[0]
    ok, message = r.select_reference_lap("__SESSION_BEST__")
    assert ok
    assert "current-session best" in message
    assert r.current_reference_selection() == "__SESSION_BEST__"
    assert r.engine.performance.reference_mode == "best"
    assert r.engine.performance.external_reference is None


def test_manual_reference_rejects_different_active_track(tmp_path):
    r = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    r.engine.state.session.track = EnumValue(10, "Spa")
    p = _write_ref(tmp_path, track_id=0)
    ok, message = r.select_reference_lap(str(p))
    assert not ok
    assert "does not match Spa" in message
    assert r.engine.performance.reference_mode == "best"
    assert r.current_reference_selection() == "__SESSION_BEST__"


def test_selected_reference_suspends_on_other_track_and_restores_on_match(tmp_path):
    r = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    r.engine.state.session.track = EnumValue(0, "Melbourne")
    p = _write_ref(tmp_path, track_id=0)
    assert r.select_reference_lap(str(p))[0]
    r.engine.state.session.track = EnumValue(10, "Spa")
    r._enforce_manual_reference_track_locked()
    assert r.current_reference_selection() == str(p)
    assert r.engine.performance.reference_mode == "best"
    assert r.engine.performance.external_reference is None
    r.engine.state.session.track = EnumValue(0, "Melbourne")
    r._enforce_manual_reference_track_locked()
    assert r.engine.performance.reference_mode == "external"
    assert r.engine.performance.external_reference["lap_time_s"] == 77.338


def test_live_trace_uses_lap_clock_zero_not_first_common_bin_rezero():
    perf = MeasuredPerformanceRecorder()
    perf.current_lap_started_clean = True
    perf.samples = {
        0.0: Sample(0.0, 0.0, 300, 1.0, 0.0, 0.0, 8, 11000),
        5.0: Sample(5.0, 0.060, 300, 1.0, 0.0, 0.0, 8, 11000),
        10.0: Sample(10.0, 0.120, 300, 1.0, 0.0, 0.0, 8, 11000),
    }
    ref = {
        "lap": 2, "valid": True, "lap_time_s": 77.0, "sections": [],
        "_samples": {
            0.0: {"d": 0.0, "t": 0.0},
            5.0: {"d": 5.0, "t": 0.050},
            10.0: {"d": 10.0, "t": 0.100},
        },
    }
    trace = _aligned_live_trace(perf, ref)
    assert trace[0] == (0.0, 0.0)
    assert abs(trace[1][1] - 0.010) < 1e-9
    assert abs(trace[2][1] - 0.020) < 1e-9


def test_partial_mid_lap_trace_is_not_stitched_to_reference():
    perf = MeasuredPerformanceRecorder()
    perf.current_lap_started_clean = False
    perf.samples = {
        1000.0: Sample(1000.0, 15.0, 250, 1.0, 0.0, 0.0, 7, 10500),
        1005.0: Sample(1005.0, 15.1, 250, 1.0, 0.0, 0.0, 7, 10500),
    }
    ref = {
        "lap": 2, "valid": True, "lap_time_s": 77.0, "sections": [],
        "_samples": {0.0: {"d": 0.0, "t": 0.0}, 1000.0: {"d": 1000.0, "t": 14.0}, 1005.0: {"d": 1005.0, "t": 14.1}},
    }
    assert _aligned_live_trace(perf, ref) == []


def test_rival_capture_does_not_auto_replace_session_best_when_no_manual_reference():
    # Source-level invariant: rival/AI capture may save files but must not call
    # set_external_reference from the capture promotion branches.
    source = Path("src/race_state_receiver.py").read_text(encoding="utf-8")
    block = source[source.index("if rival_new_best is not None:"):source.index("if state_changed:", source.index("if rival_new_best is not None:"))]
    assert "set_external_reference" not in block
