import json
import math
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from src.coaching_zones import build_coaching_zones, attribute_zone_and_straight_loss
from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, DrivingEvent, PhysicalCorner, ReferenceTrace
from src.reference_model import (
    compile_reference_model,
    detect_driving_events,
    load_reference_model,
    save_reference_bundle,
    validate_reference_lap,
)
import src.reference_model as reference_model
from src.race_state_receiver import RaceStateReceiver


def _samples(length=1500.0, *, brake=(380.0, 480.0), steer=(430.0, 560.0), pickup=540.0):
    out = {}
    for d in range(0, int(length) + 1, 5):
        t = d / 50.0
        b = 0.82 if brake[0] <= d <= brake[1] else 0.0
        if d < pickup:
            throttle = 0.05 if d >= brake[0] - 20 else 1.0
        else:
            throttle = min(1.0, 0.20 + (d - pickup) / 100.0)
        steering = 0.28 if steer[0] <= d <= steer[1] else 0.0
        out[float(d)] = {
            "d": float(d), "t": t, "speed": 210.0 - (80.0 if brake[0] <= d <= 520 else 0.0),
            "brake": b, "throttle": throttle, "steering": steering, "gear": 5,
            "world_x": float(d), "world_z": math.sin(d / 100.0) * 20.0,
        }
    return out


def _lap(length=1500.0):
    return {
        "track_name": "TEST_TRACK", "track_length_m": length, "lap_time_s": length / 50.0,
        "valid": True, "lap_start_anchored": True, "sections": [], "_samples": _samples(length),
    }


def test_reference_quality_accepts_complete_dense_rival_and_rejects_partial():
    good = validate_reference_lap(_lap())
    assert good["accepted"] is True
    partial = _lap()
    partial["_samples"] = {d: row for d, row in partial["_samples"].items() if 300 <= d <= 1200}
    bad = validate_reference_lap(partial)
    assert bad["accepted"] is False
    assert "not_sf_to_sf" in bad["reasons"]


def test_driver_events_include_brake_release_throttle_pickup_and_steering():
    lap = _lap()
    samples = tuple(dict(row) for _, row in sorted(lap["_samples"].items()))
    events = detect_driving_events(samples)
    kinds = {e.kind for e in events}
    assert "brake" in kinds
    assert "brake_release" in kinds
    assert "steering" in kinds
    assert "throttle_pickup" in kinds
    assert "full_throttle" in kinds
    # Event IDs are driver-event IDs only; they never imply physical turn numbers.
    assert all(e.event_id.startswith("E") for e in events)


def test_hybrid_zone_combines_short_tight_physical_corners_without_renumbering():
    corners = (
        PhysicalCorner(5, "T5", 100, 140, 180, "LEFT", 0.02),
        PhysicalCorner(6, "T6", 195, 225, 255, "RIGHT", 0.025),
        PhysicalCorner(7, "T7", 270, 300, 340, "LEFT", 0.022),
    )
    samples = []
    for d in range(0, 501, 5):
        samples.append({"d": float(d), "t": d / 40.0, "speed": 140.0,
                        "brake": 0.8 if 70 <= d <= 310 else 0.0,
                        "throttle": 0.0 if 70 <= d <= 330 else 1.0,
                        "steering": 0.35 if 100 <= d <= 340 else 0.0, "gear": 3})
    events = detect_driving_events(tuple(samples))
    zones = build_coaching_zones(corners, events, tuple(samples), track_length_m=500.0)
    assert len(zones) == 1
    assert zones[0].corner_ids == (5, 6, 7)
    assert zones[0].public_label == "T5–T7"


def test_meaningful_full_throttle_recovery_separates_coaching_zones():
    corners = (
        PhysicalCorner(1, "T1", 100, 140, 180, "LEFT", 0.02),
        PhysicalCorner(2, "T2", 270, 310, 350, "RIGHT", 0.02),
    )
    samples = []
    for d in range(0, 501, 5):
        full = 185 <= d <= 265
        samples.append({"d": float(d), "t": d / 40.0, "speed": 160.0,
                        "brake": 0.8 if 70 <= d <= 155 or 245 <= d <= 320 else 0.0,
                        "throttle": 1.0 if full or d < 70 or d > 330 else 0.0,
                        "steering": 0.3 if 100 <= d <= 175 or 275 <= d <= 345 else 0.0, "gear": 4})
    events = detect_driving_events(tuple(samples))
    zones = build_coaching_zones(corners, events, tuple(samples), track_length_m=500.0)
    assert [z.corner_ids for z in zones] == [(1,), (2,)]


def test_zone_and_straight_loss_partition_reconciles_full_lap_delta():
    zones = (
        CoachingZone("Z1", 100, 250, 80, (1,), label="T1"),
        CoachingZone("Z2", 500, 680, 460, (2, 3), label="T2–T3"),
    )
    points = []
    for d in range(0, 1001, 5):
        delta = d * 0.0002
        points.append({"distance_m": float(d), "delta_s": delta})
    model = {"points": points}
    out = attribute_zone_and_straight_loss(zones, model, track_length_m=1000.0)
    assert out["available"] is True
    assert len(out["zones"]) == 2
    assert len(out["straights"]) == 3
    assert abs(out["reconciliation_error_s"]) < 1e-12
    assert abs(out["partition_net_delta_s"] - out["full_track_net_delta_s"]) < 1e-12


def test_compiled_reference_bundle_round_trips_without_raw_reanalysis(tmp_path, monkeypatch):
    boundaries = [
        {"corner_id": 1, "label": "T1", "start_m": 360.0, "apex_m": 450.0, "end_m": 560.0,
         "turn_direction": "LEFT", "curvature_score": 0.02},
        {"corner_id": 2, "label": "T2", "start_m": 900.0, "apex_m": 980.0, "end_m": 1060.0,
         "turn_direction": "RIGHT", "curvature_score": 0.02},
    ]
    monkeypatch.setattr(reference_model, "physical_turn_boundaries", lambda lap, track_name=None: boundaries)
    lap = _lap()
    paths = save_reference_bundle(lap, {"source": "EA_F1_TIME_TRIAL_RIVAL", "driver": "FAST"}, root=tmp_path)
    assert paths["raw"].exists() and paths["model"].exists() and paths["zones"].exists()
    loaded = load_reference_model(paths["model"])
    assert loaded.track_name == "TEST_TRACK"
    assert [c.corner_id for c in loaded.physical_corners] == [1, 2]
    assert loaded.quality["accepted"] is True
    assert loaded.samples[0]["d"] == 0.0

    engine = CornerCoachEngine()
    # If compiled loading works, raw compilation can be made unavailable and the
    # engine still resolves the permanent model from the raw source's sibling.
    import src.corner_coach as cc
    monkeypatch.setattr(cc, "compile_reference_model", lambda *a, **k: (_ for _ in ()).throw(AssertionError("raw compile should not run")))
    model = engine._ensure_reference(lap, "TEST_TRACK", {"source_file": str(paths["raw"])})
    assert model is not None
    assert model.track_name == "TEST_TRACK"


def test_nested_v11_rival_reference_is_exposed_but_internal_json_is_not(tmp_path):
    receiver = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    receiver.reference_directory = tmp_path / "references"
    folder = receiver.reference_directory / "TEST_TRACK"
    folder.mkdir(parents=True)
    raw = folder / "rival_reference.json"
    payload = {"format": "RACE_ENGINEER_REFERENCE_LAP", "version": "1.0",
               "metadata": {"source": "EA_F1_TIME_TRIAL_RIVAL", "driver": "FAST"}, "lap": _lap()}
    raw.write_text(json.dumps(payload), encoding="utf-8")
    (folder / "reference_model.json").write_text("{}", encoding="utf-8")
    (folder / "coaching_zones.json").write_text("{}", encoding="utf-8")
    options = receiver.reference_lap_options()
    paths = [Path(x["path"]).name for x in options]
    assert paths == ["rival_reference.json"]
    assert "TEST TRACK" in options[0]["label"]


def test_rival_reference_recording_mode_auto_arms_without_raw_recorder():
    receiver = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    ok, message = receiver.set_recording_mode("rival_reference")
    assert ok
    assert "auto" in message.lower()
    assert receiver.recorder is None
    assert receiver.rival_benchmark.enabled is True
    assert receiver.rival_benchmark.strict_quality is True
    # REC is reserved for normal Session Recording and stays logically OFF/AUTO.
    assert receiver.runtime_feature_states()["REC"] is False
    # The normal REC toggle cannot accidentally stop rival capture.
    ok, _ = receiver.set_recording_enabled(False)
    assert ok
    assert receiver.rival_benchmark.enabled is True


def test_rival_reference_capture_status_distinguishes_armed_from_capturing():
    from src.rival_benchmark import TimeTrialRivalCapture
    capture = TimeTrialRivalCapture(enabled=True, strict_quality=True)
    status = capture.capture_status()
    assert status["phase"] == "armed_waiting_telemetry"
    capture.latest_lap = object()
    capture.latest_telemetry = object()
    capture.rival_idx = 3
    status = capture.capture_status()
    assert status["phase"] == "armed_waiting_sf"
    capture.track.anchored = True
    capture.track.samples = {0: object()}
    status = capture.capture_status()
    assert status["phase"] == "capturing"


def test_live_distance_is_authority_for_active_corner_coach_zone(monkeypatch):
    zone = CoachingZone("Z11", 4000, 4120, 3920, (11,), apex_m=4060, label="T11")
    model = ReferenceTrace("MELBOURNE", 5300.0, 96.0, 5.0, ({"d": 4060.0, "t": 72.0, "speed": 120.0,
                           "brake": 0.5, "throttle": 0.1, "steering": 0.3, "gear": 3},),
                           (PhysicalCorner(11, "T11", 4000, 4060, 4120),), (), (zone,), {}, {})
    engine = CornerCoachEngine()
    monkeypatch.setattr(engine, "_ensure_reference", lambda *args, **kwargs: (setattr(engine, "reference_model", model) or model))
    recorder = NS(current_reference_lap=lambda: {"_samples": {}}, current_lap_snapshot=lambda state: None,
                  reference_mode="external", external_reference_meta={})
    lap = NS(current_lap=2, lap_distance_m=4063.0)
    telem = NS(speed_kph=130.0, brake=0.2, throttle=0.1, steering=0.3, gear=3)
    state = NS(player=NS(lap=lap, telemetry=telem), session=NS(track=NS(name="MELBOURNE"), session_time_s=50.0))
    engine.observe(recorder, state, 1.0)
    status = engine.status(recorder, state)
    assert status["active_zone"]["corner_ids"] == [11]
    assert status["active_zone"]["label"] == "T11"


def test_corner_coach_overlay_and_controls_are_dedicated_and_resizable():
    root = Path(__file__).resolve().parents[1]
    window = (root / "src" / "overlay" / "window.py").read_text(encoding="utf-8")
    assert "class CornerCoachOverlayWindow" in window
    assert "body.addWidget(self.map_canvas,3)" in window
    assert "body.addWidget(self.driver_panel,1)" in window
    assert "self._resize_edges" in window
    assert "CORNER COACH" in window
    assert "Rival Reference Capture" in window
    assert "light red" in window.lower() or "red_start" in window
    assert "Green begins at the physical apex" in window
    assert "REAL-TIME CORNER COACHING" in window


def test_rival_reference_sampler_uses_selected_rival_not_player_car():
    from src.rival_benchmark import TimeTrialRivalCapture
    c = TimeTrialRivalCapture(enabled=True, strict_quality=True)
    c.rival_idx = 2
    c.track.anchored = True
    c.track.current_lap = 1
    c.latest_lap = NS(m_lapData=tuple(
        NS(m_currentLapNum=1, m_lapDistance=100.0 if i == 2 else 100.0,
           m_currentLapTimeInMS=2000, m_currentLapInvalid=0) for i in range(24)
    ))
    # Player car at index 0 is intentionally completely different from rival 2.
    c.latest_telemetry = NS(m_carTelemetryData=tuple(
        NS(m_speed=50 if i == 0 else (300 if i == 2 else 100),
           m_throttle=0.1 if i == 0 else (0.9 if i == 2 else 0.5),
           m_brake=1.0 if i == 0 else (0.2 if i == 2 else 0.0),
           m_steer=-0.9 if i == 0 else (0.25 if i == 2 else 0.0),
           m_gear=1 if i == 0 else (8 if i == 2 else 4), m_engineRPM=12000,
           m_drs=0, m_clutch=0, m_revLightsPercent=0,
           m_brakesTemperature=(), m_tyresSurfaceTemperature=(), m_tyresInnerTemperature=(),
           m_tyresPressure=(), m_surfaceType=()) for i in range(24)
    ))
    c._sample_rival()
    sample = c.track.samples[100.0]
    assert sample.speed == 300.0
    assert sample.throttle == 0.9
    assert sample.brake == 0.2
    assert sample.steering == 0.25
    assert sample.gear == 8


def test_pre_instruction_uses_remaining_distance_not_absolute_lap_position():
    zone = CoachingZone("Z11", 500.0, 650.0, 450.0, (11,), brake_start_m=520.0, apex_m=590.0, label="T11")
    text = CornerCoachEngine._pre_text(zone, 420.0)
    assert "Turn 11" in text
    assert "brake in about 100 metres" in text
    assert "520 metres" not in text


def test_post_window_expires_after_seek_without_stale_corner_message(monkeypatch):
    zone = CoachingZone("Z1", 100.0, 200.0, 80.0, (1,), brake_start_m=90.0, apex_m=150.0, label="T1")
    model = ReferenceTrace(
        "TEST_TRACK", 1200.0, 30.0, 5.0,
        ({"d": 0.0, "t": 0.0, "speed": 100.0, "brake": 0.0, "throttle": 1.0, "steering": 0.0, "gear": 4},
         {"d": 1200.0, "t": 30.0, "speed": 100.0, "brake": 0.0, "throttle": 1.0, "steering": 0.0, "gear": 4}),
        (PhysicalCorner(1, "T1", 100.0, 150.0, 200.0),), (), (zone,), {}, {}
    )
    engine = CornerCoachEngine()
    monkeypatch.setattr(engine, "_ensure_reference", lambda *args, **kwargs: (setattr(engine, "reference_model", model) or model))
    monkeypatch.setattr("src.corner_coach.build_distance_performance_model", lambda *args, **kwargs: {
        "available": True,
        "points": [{"distance_m": 0.0, "delta_s": 0.0}, {"distance_m": 1200.0, "delta_s": 0.1}],
        "turns": [],
    })
    recorder = NS(
        current_reference_lap=lambda: {"_samples": {0.0: {"d": 0.0, "t": 0.0}, 1200.0: {"d": 1200.0, "t": 30.0}}},
        current_lap_snapshot=lambda state: {"_samples": {0.0: {"d": 0.0, "t": 0.0}, 1200.0: {"d": 1200.0, "t": 30.1}}},
        reference_mode="external", external_reference_meta={},
    )
    lap = NS(current_lap=2, lap_distance_m=700.0)  # 500 m after T1 exit: replay seek/jump.
    telem = NS(speed_kph=180.0, brake=0.0, throttle=1.0, steering=0.0, gear=6)
    state = NS(player=NS(lap=lap, telemetry=telem), session=NS(track=NS(name="TEST_TRACK"), session_time_s=50.0))
    messages = engine.observe(recorder, state, 1.0)
    assert messages == []
    assert "Z1" in engine._post_spoken
