from types import SimpleNamespace

from src.measured_performance import Sample
from src.overlay.data import build_overlay_snapshot
from src.race_state.models import CarState, RaceState


def _state(distance=110.0, track_length=4500):
    state = RaceState(player_index=0, player=CarState(index=0))
    state.session.track_length_m = track_length
    state.player.telemetry.speed_kph = 250
    state.player.telemetry.gear = 7
    state.player.telemetry.throttle = 1.0
    state.player.telemetry.brake = 0.0
    state.player.lap.current_lap = 4
    state.player.lap.lap_distance_m = distance
    state.player.lap.current_lap_time_s = 10.0
    state.player.lap.lap_valid = True
    return state


def _reference(track_length=4500):
    samples = {}
    for d in range(0, track_length + 1, 5):
        samples[float(d)] = {"t": d / 70.0, "speed": 250, "throttle": 1.0, "brake": 0.0}
    return {
        "lap": 3,
        "valid": True,
        "lap_time_s": 70.0,
        "sector1_time_s": 20.0,
        "sector2_time_s": 20.0,
        "sections": [
            {"id": 1, "start_m": 100.0, "min_speed_m": 150.0, "min_speed_kph": 150,
             "full_throttle_m": 200.0, "end_m": 220.0, "exit_speed_kph": 180},
            {"id": 2, "start_m": 1900.0, "min_speed_m": 1980.0, "min_speed_kph": 120,
             "full_throttle_m": 2080.0, "end_m": 2100.0, "exit_speed_kph": 170},
            {"id": 3, "start_m": 3500.0, "min_speed_m": 3580.0, "min_speed_kph": 130,
             "full_throttle_m": 3660.0, "end_m": 3680.0, "exit_speed_kph": 175},
        ],
        "_samples": samples,
    }


def test_track_delta_markers_follow_straight_turn_structure_not_fixed_distance():
    ref = _reference(4500)
    current = {}
    for d in range(0, 901, 5):
        # Current lap slowly loses time so completed markers should be positive.
        current[float(d)] = Sample(float(d), d / 70.0 + d / 4500.0 * 0.3, 250, 1.0, 0.0, 0.0, 7, 12000)
    perf = SimpleNamespace(
        completed=[ref], samples=current, reference_mode="best", manual_reference_lap=None,
        event_context={"profile": "time_trial", "regulations_2026": True, "metrics": {"active_aero_analysis": True}},
    )
    snap = build_overlay_snapshot(_state(distance=900.0, track_length=4500), perf, connected=True)
    # Three detected turns produce straight/turn alternation across the lap:
    # straight, turn, straight, turn, straight, turn, straight.
    assert snap.delta_dot_kinds == ("straight", "turn", "straight", "turn", "straight", "turn", "straight")
    assert len(snap.delta_dots) == 7
    assert snap.delta_dots[0] is not None and snap.delta_dots[0] > 0
    assert snap.delta_dots[1] is not None and snap.delta_dots[1] > 0
    assert any(v is None for v in snap.delta_dots[2:])  # future track structures remain neutral
    assert len(snap.delta_dot_sectors) == len(snap.delta_dots)


def test_s_mode_enable_reports_delay_and_on_spot_from_explicit_ea_states():
    perf = SimpleNamespace(
        completed=[],
        samples={
            90.0: Sample(90.0, 1.0, 250, 1.0, 0.0, 0.0, 7, 12000, s_mode_available=False, s_mode_straight=False),
            100.0: Sample(100.0, 1.1, 250, 1.0, 0.0, 0.0, 7, 12000, s_mode_available=True, s_mode_straight=False),
            110.0: Sample(110.0, 1.2, 250, 1.0, 0.0, 0.0, 7, 12000, s_mode_available=True, s_mode_straight=True),
        },
        reference_mode="best", manual_reference_lap=None,
        event_context={"profile": "time_trial", "regulations_2026": True, "metrics": {"active_aero_analysis": True}},
    )
    snap = build_overlay_snapshot(_state(distance=110.0), perf, connected=True)
    assert snap.s_mode_metric is not None
    assert snap.s_mode_metric.label == "S Mode Enable"
    assert snap.s_mode_metric.value == "10m late"
    assert snap.s_mode_metric.status == "LATER"

    perf.samples[100.0] = Sample(100.0, 1.1, 250, 1.0, 0.0, 0.0, 7, 12000, s_mode_available=True, s_mode_straight=True)
    perf.samples.pop(110.0)
    snap = build_overlay_snapshot(_state(distance=100.0), perf, connected=True)
    assert snap.s_mode_metric.value == "on spot"
    assert snap.s_mode_metric.status == "MATCH"
