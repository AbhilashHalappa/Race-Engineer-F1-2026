from types import SimpleNamespace as NS
from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, PhysicalCorner, ReferenceTrace


def _model():
    corner = PhysicalCorner(1, "T1", 80.0, 100.0, 140.0, "RIGHT", 1.0)
    zone = CoachingZone("Z1", 80.0, 140.0, 0.0, (1,), brake_start_m=80.0, apex_m=100.0,
                        reference_min_speed_kph=120.0, label="T1")
    samples = tuple({"d": float(d), "t": float(d) / 50.0, "speed": 180.0} for d in range(0, 501, 5))
    return ReferenceTrace("TEST", 500.0, 10.0, 5.0, samples, (corner,), (), (zone,),
                          metadata={}, quality={"input_telemetry_trusted": False})


class Recorder:
    reference_mode = "external"
    external_reference_meta = {"source": "EA_F1_TIME_TRIAL_RIVAL"}
    external_reference = {"lap_time_s": 10.0}
    event_context = {"profile": "time_trial"}
    def current_reference_lap(self): return self.external_reference
    def current_lap_trace_snapshot(self, state): return {"_samples": {}}


def _state(distance, lap_time, speed=80.0, lap=1):
    return NS(
        session=NS(track=NS(name="TEST"), uid=123, session_time_s=lap_time + 10.0, total_laps=3, ended=False),
        player=NS(
            lap=NS(current_lap=lap, lap_distance_m=distance, current_lap_time_s=lap_time,
                   previous_lap_time_s=None, lap_valid=True, result_status=NS(raw=2),
                   pit_status=NS(name="None"), pit_lane_timer_active=False),
            telemetry=NS(speed_kph=speed, brake=0.0, steering=0.0, throttle=1.0, gear=4),
            damage=NS(front_left_wing_percent=0, front_right_wing_percent=0, floor_percent=0,
                      engine_blown=False, engine_seized=False),
        ),
    )


def test_preline_same_number_wrap_starts_timed_lap1_instead_of_blocking_it(monkeypatch):
    engine=CornerCoachEngine(); engine.validation.close(); model=_model()
    monkeypatch.setattr(engine, "_ensure_reference", lambda *a, **k: model)
    # EA exposes lap 1 on the rolling-start/pre-line segment. Slow speed avoids
    # producing a circular T1 cue before S/F in this synthetic scenario.
    assert engine.observe(Recorder(), _state(470.0, 6.0, speed=5.0), 100.0) == []
    assert engine._lap == 1 and engine._lap_started_clean is False
    # Same lap number, clean timing anchor. This must rebase lap 1, not finalize it.
    out=engine.observe(Recorder(), _state(0.0, 0.2, speed=80.0), 101.0)
    assert engine._lap == 1
    assert engine._lap_started_clean is True
    assert engine._awaiting_lap_increment_from is None
    assert any(m.key == "corner:pre:1:Z1" for m in out)


def test_clean_lap_wrap_still_uses_normal_boundary_logic(monkeypatch):
    engine=CornerCoachEngine(); engine.validation.close(); model=_model()
    monkeypatch.setattr(engine, "_ensure_reference", lambda *a, **k: model)
    engine.observe(Recorder(), _state(0.0, 0.2, speed=80.0), 100.0)
    assert engine._lap_started_clean is True
    engine.observe(Recorder(), _state(470.0, 9.0, speed=180.0), 108.0)
    engine.observe(Recorder(), _state(0.0, 0.2, speed=80.0), 109.0)
    assert engine._awaiting_lap_increment_from == 1
