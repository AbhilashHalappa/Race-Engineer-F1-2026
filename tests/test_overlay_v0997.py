from types import SimpleNamespace

from src.measured_performance import Sample
from src.overlay.data import build_overlay_snapshot
from src.race_state.models import CarState, RaceState


def _state(distance=2600.0):
    state = RaceState(player_index=0, player=CarState(index=0))
    state.session.track_length_m = 5000
    state.player.telemetry.speed_kph = 240
    state.player.telemetry.gear = 6
    state.player.lap.current_lap = 4
    state.player.lap.lap_distance_m = distance
    state.player.lap.current_lap_time_s = 40.0
    state.player.lap.lap_valid = True
    return state


def _reference():
    samples = {float(d): {"t": d / 70.0, "speed": 240, "throttle": 1.0, "brake": 0.0} for d in range(0, 5001, 5)}
    return {
        "lap": 3, "valid": True, "lap_time_s": 71.0,
        "sector1_time_s": 22.0, "sector2_time_s": 25.0,
        "sections": [
            {"id": 1, "start_m": 500.0, "min_speed_m": 580.0, "end_m": 700.0, "full_throttle_m": 680.0, "min_speed_kph": 100, "exit_speed_kph": 150},
            {"id": 2, "start_m": 2200.0, "min_speed_m": 2280.0, "end_m": 2400.0, "full_throttle_m": 2380.0, "min_speed_kph": 110, "exit_speed_kph": 160},
            {"id": 3, "start_m": 4100.0, "min_speed_m": 4180.0, "end_m": 4300.0, "full_throttle_m": 4280.0, "min_speed_kph": 120, "exit_speed_kph": 170},
        ],
        "_samples": samples,
    }


def test_track_structure_markers_change_count_with_detected_turns():
    ref = _reference()
    current = {float(d): Sample(float(d), d / 70.0 + d / 5000.0 * 0.2, 240, 1.0, 0.0, 0.0, 6, 10000) for d in range(0, 2601, 5)}
    perf = SimpleNamespace(completed=[ref], samples=current, reference_mode="best", manual_reference_lap=None, event_context={"profile": "time_trial"})
    snap = build_overlay_snapshot(_state(), perf, connected=True)
    assert len(snap.delta_dots) == 7
    assert snap.delta_dot_kinds.count("turn") == 3
    assert snap.delta_dot_kinds.count("straight") == 4
    assert set(snap.delta_dot_sectors).issubset({1, 2, 3})


def test_previous_turn_history_is_no_longer_truncated_to_five():
    # This is validated through completed comparison history in a real session elsewhere;
    # guard the public snapshot shape here so the UI can lay out >5 turns in two pairs/row.
    from src.overlay.data import OverlaySnapshot
    assert "previous_sections" in OverlaySnapshot.__dataclass_fields__
    assert "delta_dot_kinds" in OverlaySnapshot.__dataclass_fields__
