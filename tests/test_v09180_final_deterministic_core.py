import inspect
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.main import main
from src.measured_performance import MeasuredPerformanceRecorder, Sample
from src.overlay import data as overlay_data
from src.race_state.models import CarState, RaceState
from src.race_state_receiver import RaceStateReceiver
from src.reference_lap import load_reference_lap, validate_reference_lap
from src.rival_benchmark import TimeTrialRivalCapture


def _sample(d, t, *, speed=200.0, throttle=0.5, brake=0.0, gear=4, ers_j=None):
    return {
        "d": float(d), "t": float(t), "speed": float(speed),
        "throttle": float(throttle), "brake": float(brake),
        "steering": 0.0, "gear": int(gear), "rpm": 9000,
        "ers_j": ers_j,
    }


def test_reference_loader_drops_post_line_clock_reset_row():
    samples = {float(i * 5): _sample(i * 5, i * 0.05) for i in range(21)}
    samples[105.0] = _sample(105.0, 0.019)
    lap = validate_reference_lap({"lap_time_s": 77.338, "_samples": samples})
    assert 100.0 in lap["_samples"]
    assert 105.0 not in lap["_samples"]


def test_measured_compare_ignores_post_line_clock_reset_for_finish_delta():
    ref_samples = {float(i * 5): _sample(i * 5, i * 0.10) for i in range(21)}
    cur_samples = {float(i * 5): _sample(i * 5, i * 0.10 + 0.10) for i in range(20)}
    cur_samples[100.0] = _sample(100.0, 0.019)
    cur = {"lap": 2, "valid": True, "lap_time_s": 80.0, "sections": [], "_samples": cur_samples}
    ref = {"lap": 1, "valid": True, "lap_time_s": 79.9, "sections": [], "_samples": ref_samples}
    out = MeasuredPerformanceRecorder.compare(cur, ref)
    assert out is not None
    assert out["finish_observed_delta_s"] == pytest.approx(0.10)
    assert abs(out["finish_observed_delta_s"]) < 1.0


def test_aligned_overlay_trace_ignores_post_line_reference_clock_reset():
    current = {float(i * 5): _sample(i * 5, i * 0.10 + 0.2) for i in range(21)}
    reference = {float(i * 5): _sample(i * 5, i * 0.10) for i in range(20)}
    reference[100.0] = _sample(100.0, 0.019)
    trace = overlay_data._aligned_trace_from_maps(current, reference)
    assert trace[-1][0] == 95.0
    assert trace[-1][1] == pytest.approx(0.2)


def test_rival_cleaner_drops_post_line_clock_reset_sample():
    cap = TimeTrialRivalCapture(enabled=True)
    rows = [
        Sample(float(i * 5), i * 0.05, 250.0, 1.0, 0.0, 0.0, 7, 10500)
        for i in range(10)
    ]
    rows.append(Sample(50.0, 0.019, 250.0, 1.0, 0.0, 0.0, 7, 10500))
    clean = cap._clean_numeric_trace(rows)
    assert len(clean) == 10
    assert clean[-1].d == 45.0
    assert clean[-1].t == pytest.approx(0.45)


def test_reference_inputs_interpolate_continuous_channels_at_exact_di_distance():
    reference = {
        "_samples": {
            0.0: _sample(0, 0.0, speed=100, throttle=0.0, brake=1.0, gear=2, ers_j=1_000_000),
            10.0: _sample(10, 1.0, speed=200, throttle=1.0, brake=0.0, gear=4, ers_j=3_000_000),
        }
    }
    row = overlay_data._reference_sample_at_distance(reference, 5.0)
    assert row["d"] == pytest.approx(5.0)
    assert row["t"] == pytest.approx(0.5)
    assert row["speed"] == pytest.approx(150.0)
    assert row["throttle"] == pytest.approx(0.5)
    assert row["brake"] == pytest.approx(0.5)
    assert row["ers_j"] == pytest.approx(2_000_000)
    # Discrete state remains nearest-neighbour, never fractional.
    assert row["gear"] in {2, 4}
    assert isinstance(row["gear"], int)


def test_input_snapshot_uses_exact_driver_distance_for_reference_channels():
    state = RaceState(player_index=0, player=CarState(index=0))
    state.player.telemetry.speed_kph = 123
    state.player.telemetry.gear = 3
    state.player.telemetry.throttle = 0.25
    state.player.telemetry.brake = 0.75
    state.player.lap.current_lap = 2
    state.player.lap.current_lap_time_s = 3.0
    state.player.lap.lap_distance_m = 5.0
    state.player.energy.store_j = 2_500_000.0
    reference = {
        "lap": 1, "valid": True, "lap_time_s": 70.0,
        "_samples": {
            0.0: _sample(0, 0.0, throttle=0.0, brake=1.0, gear=2, ers_j=1_000_000),
            10.0: _sample(10, 1.0, throttle=1.0, brake=0.0, gear=4, ers_j=3_000_000),
        },
    }
    perf = SimpleNamespace(completed=[reference], reference_mode="best", manual_reference_lap=None)
    snap = overlay_data.build_input_snapshot(state, perf, connected=True)
    assert snap.lap_distance_m == 5.0
    assert snap.reference_throttle == pytest.approx(0.5)
    assert snap.reference_brake == pytest.approx(0.5)
    assert snap.reference_ers_store_j == pytest.approx(2_000_000)
    assert snap.reference_time_s == pytest.approx(0.5)


def test_high_frequency_provider_path_does_not_build_full_overlay(monkeypatch):
    state = RaceState(player_index=0, player=CarState(index=0))
    perf = SimpleNamespace(completed=[], reference_mode="best", manual_reference_lap=None)
    receiver = SimpleNamespace(engine=SimpleNamespace(state=state, performance=perf), _state_lock=threading.RLock(), last_packet_at=None)
    provider = overlay_data.OverlayDataProvider(receiver)
    monkeypatch.setattr(overlay_data, "build_overlay_snapshot", lambda *a, **k: (_ for _ in ()).throw(AssertionError("heavy path used")))
    snap = provider.input_snapshot()
    assert isinstance(snap, overlay_data.InputSnapshot)


def test_ers_trace_keeps_all_channels_one_to_one_with_distance_samples():
    source = Path("src/overlay/widgets.py").read_text(encoding="utf-8")
    block = source.split("class ERSBatteryTraceWidget", 1)[1].split("class DeltaTraceWidget", 1)[0]
    assert "self.store_values.append(mj(store_j))" in block
    assert "self.charge_values.append(mj(harvested_j, positive=True))" in block
    assert "self.discharge_values.append(mj(deployed_j, positive=True))" in block
    assert "Missing\n        # ERS counters are represented by None" in block


def test_measured_radio_reference_waits_for_start_finish_then_activates():
    r = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    try:
        r.engine.state.player_index = 0
        r.engine.state.player = CarState(index=0)
        r.engine.state.player.lap.lap_distance_m = 1500.0
        r.engine.state.player.lap.current_lap_time_s = 25.0
        r.engine.performance.completed = [
            {"lap": 1, "valid": True, "lap_time_s": 80.0, "sections": [], "_samples": {}},
            {"lap": 2, "valid": True, "lap_time_s": 79.0, "sections": [], "_samples": {}},
        ]
        ok, message = r.select_measured_reference("previous")
        assert ok and "queued" in message.lower()
        assert r.engine.performance.reference_mode == "best"
        assert r.reference_selection_status()["pending_name"] == "Previous lap"
        r.engine.state.player.lap.lap_distance_m = 5.0
        r.engine.state.player.lap.current_lap_time_s = 0.2
        applied, _ = r._apply_pending_reference_locked()
        assert applied
        assert r.engine.performance.reference_mode == "previous"
        status = r.reference_selection_status()
        assert status["active_name"] == "Previous L2"
        assert status["active_time_s"] == pytest.approx(79.0)
    finally:
        r.speech.close(wait=False)


def test_previous_reference_is_rejected_before_any_completed_lap():
    r = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    try:
        r.engine.state.player_index = 0
        r.engine.state.player = CarState(index=0)
        r.engine.state.player.lap.lap_distance_m = 1000.0
        r.engine.state.player.lap.current_lap_time_s = 20.0
        ok, message = r.select_measured_reference("previous")
        assert not ok
        assert "No completed measured lap" in message
    finally:
        r.speech.close(wait=False)


def test_llm_is_opt_in_not_a_core_runtime_dependency():
    assert inspect.signature(main).parameters["llm_enabled"].default is False
    source = Path("src/main.py").read_text(encoding="utf-8")
    assert 'parser.add_argument("--llm", action="store_true"' in source
    assert "llm_enabled=bool(args.llm and not args.no_llm)" in source
    assert "V0.9.18.0 FINAL DETERMINISTIC CORE" in source


def test_use_this_lap_queues_the_current_in_progress_lap_not_the_previous_one():
    r = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    try:
        r.engine.state.player_index = 0
        r.engine.state.player = CarState(index=0)
        r.engine.state.player.lap.current_lap = 3
        r.engine.state.player.lap.lap_distance_m = 1200.0
        r.engine.state.player.lap.current_lap_time_s = 18.0
        r.engine.performance.completed = [
            {"lap": 1, "valid": True, "lap_time_s": 81.0, "sections": [], "_samples": {}},
            {"lap": 2, "valid": True, "lap_time_s": 80.0, "sections": [], "_samples": {}},
        ]
        ok, message = r.select_measured_reference("manual")
        assert ok and "Lap 3 queued" in message
        assert r._pending_reference_meta["lap"] == 3
        assert r.reference_selection_status()["pending_name"] == "Lap 3"
    finally:
        r.speech.close(wait=False)


def test_reference_input_label_matches_measured_reference_mode():
    ref = {"lap": 4, "valid": True, "lap_time_s": 78.0, "_samples": {}}
    perf = SimpleNamespace(completed=[ref], reference_mode="manual", manual_reference_lap=4)
    assert overlay_data._reference_display_name(perf, ref) == "Measured L4"
    perf.reference_mode = "previous"
    assert overlay_data._reference_display_name(perf, ref) == "Previous L4"


def test_legacy_time_trial_rival_load_rebuilds_clean_summary_and_sections(tmp_path):
    samples = {}
    for i in range(40):
        d = float(i * 5)
        t = float(i) * 0.10
        row = _sample(d, t, speed=200.0, throttle=1.0, brake=0.0, gear=4)
        row.update({"yaw": i * 0.001, "g_lat": 0.0, "g_long": 0.0})
        if 20 <= i <= 25:
            row["brake"] = 1.0
            row["throttle"] = 0.0
            row["speed"] = 200.0 - (i - 19) * 10.0
        samples[str(d)] = row

    # Model the corruption seen in older EA Time Trial rival captures.
    for i in (10, 11, 12):
        samples[str(float(i * 5))]["speed"] = 486.0
    samples[str(50.0)]["gear"] = 8
    samples[str(60.0)]["gear"] = 2
    samples[str(200.0)] = dict(_sample(200.0, 0.019, speed=303.0, gear=8), yaw=0.050, g_lat=0.0, g_long=0.0)

    payload = {
        "format": "RACE_ENGINEER_REFERENCE_LAP",
        "version": "1.0",
        "metadata": {"source": "EA_F1_TIME_TRIAL_RIVAL"},
        "lap": {
            "lap": 2,
            "valid": True,
            "lap_time_s": 4.0,
            "sample_count": 41,
            "min_speed_kph": 140.0,
            "max_speed_kph": 486.0,
            "gear_changes": 99,
            "max_abs_lateral_g": 0.0,
            "max_braking_g": -99.0,
            "sections": [{"id": 1, "start_m": 100.0, "brake_start_speed_kph": 486.0}],
            "_samples": samples,
        },
    }
    path = tmp_path / "legacy_tt_rival.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    lap, meta = load_reference_lap(path)

    assert meta["source"] == "EA_F1_TIME_TRIAL_RIVAL"
    assert lap["sample_count"] == 40
    assert 200.0 not in lap["_samples"]
    assert lap["max_speed_kph"] <= 200.0
    assert max(row["speed"] for row in lap["_samples"].values()) <= 200.0
    assert lap["gear_changes"] == 0
    assert lap["max_abs_lateral_g"] is not None and lap["max_abs_lateral_g"] > 0.0
    assert lap["max_braking_g"] is not None and lap["max_braking_g"] > -6.1
    assert all((section.get("brake_start_speed_kph") or 0) <= 200.0 for section in lap["sections"])


def test_non_rival_reference_does_not_apply_legacy_ghost_speed_cleaner(tmp_path):
    samples = {str(float(i * 5)): _sample(i * 5, i * 0.1, speed=(390.0 if i == 10 else 200.0)) for i in range(25)}
    payload = {
        "format": "RACE_ENGINEER_REFERENCE_LAP",
        "version": "1.0",
        "metadata": {"source": "USER_REFERENCE"},
        "lap": {"lap": 1, "valid": True, "lap_time_s": 10.0, "_samples": samples},
    }
    path = tmp_path / "user_reference.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    lap, _ = load_reference_lap(path)
    assert lap["_samples"][50.0]["speed"] == pytest.approx(390.0)
