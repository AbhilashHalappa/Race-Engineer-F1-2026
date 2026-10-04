from types import SimpleNamespace as NS

from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, PhysicalCorner, ReferenceTrace


def _model():
    corner = PhysicalCorner(1, "T1", 80.0, 100.0, 140.0, "RIGHT", 1.0)
    zone = CoachingZone(
        "Z1", 80.0, 140.0, 0.0, (1,),
        brake_start_m=80.0, apex_m=100.0,
        reference_min_speed_kph=120.0, label="T1",
    )
    samples = tuple({"d": float(d), "t": float(d) / 50.0, "speed": 180.0} for d in range(0, 501, 5))
    return ReferenceTrace(
        "TEST", 500.0, 10.0, 5.0, samples, (corner,), (), (zone,),
        metadata={}, quality={"input_telemetry_trusted": False},
    )


class Recorder:
    reference_mode = "external"
    external_reference_meta = {"source": "EA_F1_TIME_TRIAL_RIVAL"}
    external_reference = {"lap_time_s": 10.0}

    def __init__(self, profile):
        self.event_context = {"profile": profile}

    def current_reference_lap(self):
        return self.external_reference

    def current_lap_trace_snapshot(self, state):
        return {"_samples": {}}


def _state(*, pit_name="Garage", lap=1, distance=0.0, speed=80.0):
    return NS(
        session=NS(track=NS(name="TEST"), uid=123, session_time_s=1.0, total_laps=3, ended=False),
        player=NS(
            lap=NS(
                current_lap=lap, lap_distance_m=distance, current_lap_time_s=0.5,
                previous_lap_time_s=None, lap_valid=True, result_status=NS(raw=2),
                pit_status=NS(name=pit_name), pit_lane_timer_active=False,
            ),
            telemetry=NS(speed_kph=speed, brake=0.0, steering=0.0, throttle=1.0, gear=4),
            damage=NS(front_left_wing_percent=0, front_right_wing_percent=0, floor_percent=0,
                      engine_blown=False, engine_seized=False),
        ),
    )


def test_time_trial_transient_pit_status_does_not_suppress_first_lap_pre(monkeypatch):
    model = _model()
    engine = CornerCoachEngine()
    engine.validation.close()
    monkeypatch.setattr(engine, "_ensure_reference", lambda *a, **k: model)

    out = engine.observe(Recorder("time_trial"), _state(pit_name="Garage"), 100.0)

    assert any(m.key == "corner:pre:1:Z1" for m in out)
    assert engine._outlap_lap is None
    assert engine._was_in_pit_lane is False


def test_non_time_trial_pit_status_still_blocks_outlap_coaching(monkeypatch):
    model = _model()
    engine = CornerCoachEngine()
    engine.validation.close()
    monkeypatch.setattr(engine, "_ensure_reference", lambda *a, **k: model)

    out = engine.observe(Recorder("practice"), _state(pit_name="Garage"), 100.0)

    assert out == []
    assert engine._outlap_lap == 1
    assert engine._was_in_pit_lane is True
