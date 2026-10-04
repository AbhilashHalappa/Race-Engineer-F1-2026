from types import SimpleNamespace

from src.measured_performance import Sample
from src.overlay.data import build_overlay_snapshot
from src.race_state.models import CarState, RaceState


def _reference():
    return {
        "lap": 3,
        "valid": True,
        "lap_time_s": 70.0,
        "sections": [
            {"id": 1, "start_m": 160.0, "min_speed_m": 200.0, "min_speed_kph": 120,
             "full_throttle_m": 300.0, "end_m": 300.0, "exit_speed_kph": 170,
             "peak_brake": 1.0, "max_slip": 0.05},
        ],
        "_samples": {
            0.0: {"t": 0.0, "speed": 200, "throttle": 1.0, "brake": 0.0},
            100.0: {"t": 1.0, "speed": 250, "throttle": 1.0, "brake": 0.0},
            200.0: {"t": 2.0, "speed": 120, "throttle": 0.1, "brake": 1.0},
            300.0: {"t": 3.0, "speed": 170, "throttle": 1.0, "brake": 0.0},
        },
    }


def _state(distance=300.0):
    state = RaceState(player_index=0, player=CarState(index=0))
    state.player.telemetry.speed_kph = 170
    state.player.telemetry.gear = 5
    state.player.telemetry.throttle = 1.0
    state.player.telemetry.brake = 0.0
    state.player.lap.current_lap = 4
    state.player.lap.lap_distance_m = distance
    state.player.lap.current_lap_time_s = 3.2
    state.player.lap.lap_valid = True
    return state


def test_realtime_coach_unlocks_metrics_as_phases_are_measured():
    current = {
        0.0: Sample(0.0, 0.0, 200, 1.0, 0.0, 0.0, 7, 11000),
        100.0: Sample(100.0, 1.05, 245, 1.0, 0.0, 0.0, 8, 12000),
        200.0: Sample(200.0, 2.10, 118, 0.1, 1.0, 0.3, 4, 9000),
        300.0: Sample(300.0, 3.20, 170, 1.0, 0.0, 0.1, 5, 10000),
    }
    perf = SimpleNamespace(
        completed=[_reference()], samples=current, reference_mode="best",
        manual_reference_lap=None, event_context={"profile": "time_trial"},
    )
    snap = build_overlay_snapshot(_state(), perf, connected=True)
    assert snap.coach_live is True
    assert snap.comparison_lap == 4
    assert snap.coach_metrics[0].value == "40m later"
    assert snap.coach_metrics[1].value == "2 kph match"
    assert snap.coach_metrics[2].value == "0m match"
    assert snap.coach_metrics[3].value == "0 kph match"


def test_realtime_coach_never_predicts_unreached_min_throttle_or_exit():
    current = {
        0.0: Sample(0.0, 0.0, 200, 1.0, 0.0, 0.0, 7, 11000),
        100.0: Sample(100.0, 1.05, 245, 1.0, 0.0, 0.0, 8, 12000),
        180.0: Sample(180.0, 1.85, 210, 0.2, 1.0, 0.2, 6, 10000),
    }
    perf = SimpleNamespace(
        completed=[_reference()], samples=current, reference_mode="best",
        manual_reference_lap=None, event_context={"profile": "time_trial"},
    )
    snap = build_overlay_snapshot(_state(180.0), perf, connected=True)
    assert snap.coach_metrics[0].value == "20m later"
    assert [m.status for m in snap.coach_metrics[1:]] == ["WAIT", "WAIT", "WAIT"]
