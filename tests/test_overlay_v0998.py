from types import SimpleNamespace

from src.measured_performance import Sample
from src.overlay.data import build_overlay_snapshot
from src.race_state.models import CarState, RaceState


def _state(distance=1000.0):
    state = RaceState(player_index=0, player=CarState(index=0))
    state.session.track_length_m = 5000
    state.player.telemetry.speed_kph = 255
    state.player.telemetry.gear = 7
    state.player.telemetry.throttle = 1.0
    state.player.telemetry.brake = 0.0
    state.player.lap.current_lap = 4
    state.player.lap.lap_distance_m = distance
    state.player.lap.current_lap_time_s = 15.0
    state.player.lap.lap_valid = True
    return state


def _reference():
    samples = {float(d): {"t": d / 70.0, "speed": 250, "throttle": 1.0, "brake": 0.0} for d in range(0, 5001, 5)}
    return {
        "lap": 3,
        "valid": True,
        "lap_time_s": 70.0,
        "sector1_time_s": 20.0,
        "sector2_time_s": 25.0,
        "sections": [
            {"id": 1, "start_m": 500.0, "min_speed_m": 580.0, "end_m": 700.0, "full_throttle_m": 680.0, "min_speed_kph": 100, "exit_speed_kph": 150},
            {"id": 2, "start_m": 2200.0, "min_speed_m": 2280.0, "end_m": 2400.0, "full_throttle_m": 2380.0, "min_speed_kph": 110, "exit_speed_kph": 160},
            {"id": 3, "start_m": 4100.0, "min_speed_m": 4180.0, "end_m": 4300.0, "full_throttle_m": 4280.0, "min_speed_kph": 120, "exit_speed_kph": 170},
        ],
        "_samples": samples,
    }


def test_live_straight_is_coached_and_history_contains_straights_and_turns():
    ref = _reference()
    current = {}
    for d in range(0, 1001, 5):
        # Lose time gradually but carry +5 kph everywhere for deterministic straight metrics.
        current[float(d)] = Sample(float(d), d / 70.0 + d / 5000.0 * 0.25, 255, 1.0, 0.0, 0.0, 7, 12000)
    perf = SimpleNamespace(
        completed=[ref], samples=current, reference_mode="best", manual_reference_lap=None,
        event_context={"profile": "time_trial", "regulations_2026": True, "metrics": {"active_aero_analysis": True}},
    )
    snap = build_overlay_snapshot(_state(1000.0), perf, connected=True)

    assert snap.active_segment_kind == "straight"
    assert snap.active_segment_number == 2
    assert snap.active_section is None
    assert [m.label for m in snap.coach_metrics] == ["Straight Time", "Entry Speed", "Avg Speed", "Top Speed"]
    assert snap.coach_metrics[0].status == "SLOWER"
    assert snap.coach_metrics[1].status == "FASTER"
    assert [(h.kind, h.section) for h in snap.previous_sections] == [("straight", 1), ("turn", 1)]


def test_current_straight_marker_gets_live_colour_instead_of_staying_neutral():
    ref = _reference()
    current = {
        float(d): Sample(float(d), d / 70.0 + d / 5000.0 * 0.25, 250, 1.0, 0.0, 0.0, 7, 12000)
        for d in range(0, 1001, 5)
    }
    perf = SimpleNamespace(
        completed=[ref], samples=current, reference_mode="best", manual_reference_lap=None,
        event_context={"profile": "time_trial"},
    )
    snap = build_overlay_snapshot(_state(1000.0), perf, connected=True)
    # straight1, turn1 and the currently developing straight2 should all be measured.
    assert snap.delta_dot_kinds[:3] == ("straight", "turn", "straight")
    assert all(v is not None for v in snap.delta_dots[:3])
    assert snap.delta_dots[2] > 0
