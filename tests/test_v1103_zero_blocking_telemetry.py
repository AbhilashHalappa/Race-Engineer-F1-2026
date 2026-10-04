from pathlib import Path
from types import SimpleNamespace as NS
import inspect

from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, PhysicalCorner, ReferenceTrace


def _model():
    zone = CoachingZone("Z1", 100.0, 200.0, 70.0, (1,), brake_start_m=80.0, apex_m=150.0, label="T1")
    return ReferenceTrace(
        "TEST_TRACK", 1000.0, 25.0, 5.0,
        (
            {"d": 0.0, "t": 0.0, "speed": 200.0, "brake": 0.0, "throttle": 1.0, "steering": 0.0, "gear": 5},
            {"d": 500.0, "t": 12.5, "speed": 200.0, "brake": 0.0, "throttle": 1.0, "steering": 0.0, "gear": 5},
            {"d": 1000.0, "t": 25.0, "speed": 200.0, "brake": 0.0, "throttle": 1.0, "steering": 0.0, "gear": 5},
        ),
        (PhysicalCorner(1, "T1", 100.0, 150.0, 200.0),), (), (zone,), {}, {},
    )


def _state(distance, lap_time, lap=2):
    return NS(
        player=NS(
            lap=NS(current_lap=lap, lap_distance_m=distance, current_lap_time_s=lap_time),
            telemetry=NS(speed_kph=160.0, brake=0.0, throttle=1.0, steering=0.0, gear=5),
        ),
        session=NS(track=NS(name="TEST_TRACK"), session_time_s=lap_time),
    )


def _recorder(reference):
    return NS(
        current_reference_lap=lambda: reference,
        current_lap_snapshot=lambda state: None,
        current_lap_trace_snapshot=lambda state: None,
        reference_mode="external",
        external_reference_meta={},
    )


def _prime(engine, monkeypatch):
    model=_model()
    engine.reference_model=model
    engine._reference_samples=tuple(model.samples)
    engine._reference_distances=tuple(float(x["d"]) for x in model.samples)
    engine._zones_payload=tuple()
    engine._corners_payload=tuple()
    engine._events_payload=tuple()
    engine._performance_boundaries=({"corner_id":1,"label":"T1","start_m":100.0,"end_m":200.0},)
    monkeypatch.setattr(engine, "_ensure_reference", lambda *a, **k: model)
    return model


def test_observe_contains_no_call_to_whole_lap_distance_builder():
    source=inspect.getsource(CornerCoachEngine.observe)
    assert "build_distance_performance_model(" not in source


def test_incremental_model_updates_only_when_authoritative_lap_time_advances(monkeypatch):
    engine=CornerCoachEngine(); _prime(engine,monkeypatch)
    ref={"_samples":{0.0:{"d":0.0,"t":0.0},1000.0:{"d":1000.0,"t":25.0}}}
    rec=_recorder(ref)
    engine.observe(rec,_state(100.0,2.50),1.0)
    n=len(engine._live_points)
    # Typical telemetry packets repeat the same authoritative lap time. They must
    # not trigger performance work or create artificial timing samples.
    for d in (101.0,102.0,103.0,104.0):
        engine.observe(rec,_state(d,2.50),1.01+d/10000.0)
    assert len(engine._live_points)==n
    engine.observe(rec,_state(105.0,2.62),1.2)
    assert len(engine._live_points)==n+1
    assert engine._distance_model["available"] is True


def test_incremental_gain_loss_is_compact_and_does_not_copy_full_lap(monkeypatch):
    engine=CornerCoachEngine(); _prime(engine,monkeypatch)
    ref={"_samples":{0.0:{"d":0.0,"t":0.0},1000.0:{"d":1000.0,"t":25.0}}}
    rec=_recorder(ref)
    for i in range(1,30):
        d=float(i*10)
        # Slightly increasing deficit produces a deterministic local loss trace.
        engine.observe(rec,_state(d,d/40.0 + i*0.001),1.0+i*0.02)
    status=engine.status(rec,_state(290.0,7.4))
    perf=status["distance_performance"]
    assert perf["available"] is True
    assert "points" not in perf
    assert perf["gain_loss_zones"]


def test_corner_map_static_cache_is_not_invalidated_by_gain_loss_or_active_zone():
    source=Path("src/overlay/window.py").read_text(encoding="utf-8")
    block=source.split("class CornerCoachMapCanvas",1)[1].split("class CornerCoachDriverPanel",1)[0]
    assert "static_key=(str(track_name or ''),self.width(),self.height(),id(points),len(points),corner_sig,zone_sig)" in block
    assert "_gain_layer_key" in block
    assert "_active_layer_key" in block
    assert "_draw_scaled_axis_span" in block


def test_post_seek_expiry_does_not_require_performance_rebuild(monkeypatch):
    engine=CornerCoachEngine(); model=_prime(engine,monkeypatch)
    engine._lap=2
    engine._pre_spoken.add("Z1")
    ref={"_samples":{0.0:{"d":0.0,"t":0.0},1000.0:{"d":1000.0,"t":25.0}}}
    rec=_recorder(ref)
    # Jump far past the post window: the zone must be expired without any full
    # performance model being available/rebuilt.
    engine.observe(rec,_state(500.0,12.5),2.0)
    assert "Z1" in engine._post_spoken
