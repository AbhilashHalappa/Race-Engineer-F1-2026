from types import SimpleNamespace

from src.overlay.qualifying import evaluate_qualifying, estimate_time_to_line_s
from src.overlay.data import build_overlay_snapshot
from src.race_state.models import CarState, LapState, RaceState, SessionState
from src.telemetry.enums import EnumValue


def ev(raw, name):
    return EnumValue(raw, name)


def perf():
    return SimpleNamespace(
        completed=[], samples={}, reference_mode="best", manual_reference_lap=None,
        event_context={"profile": "qualifying", "metrics": {}},
    )


def test_qualifying_flying_valid_lap_says_push():
    g = evaluate_qualifying(
        session_finished=False, driver_status="Flying lap", lap_valid=True,
        session_time_left_s=300, current_lap_time_s=30.0,
        lap_distance_m=1500.0, track_length_m=5000.0, best_lap_time_s=90.0,
    )
    assert g.decision == "PUSH LAP"
    assert g.confidence == "high"
    assert g.another_lap_estimate == "YES (EST.)"


def test_qualifying_invalid_flying_lap_is_explicit():
    g = evaluate_qualifying(
        session_finished=False, driver_status="Flying lap", lap_valid=False,
        session_time_left_s=120, current_lap_time_s=40.0,
        lap_distance_m=2000.0, track_length_m=5000.0, best_lap_time_s=90.0,
    )
    assert g.decision == "LAP INVALID"


def test_qualifying_out_lap_prepares_and_in_lap_boxes():
    common = dict(session_finished=False, lap_valid=True, session_time_left_s=600,
                  current_lap_time_s=20.0, lap_distance_m=1000.0,
                  track_length_m=5000.0, best_lap_time_s=90.0)
    assert evaluate_qualifying(driver_status="Out lap", **common).decision == "PREPARE LAP"
    assert evaluate_qualifying(driver_status="In lap", **common).decision == "BOX"


def test_qualifying_clock_expired_flying_lap_can_finish():
    g = evaluate_qualifying(
        session_finished=False, driver_status="Flying lap", lap_valid=True,
        session_time_left_s=0, current_lap_time_s=70.0,
        lap_distance_m=4000.0, track_length_m=5000.0, best_lap_time_s=90.0,
    )
    assert g.decision == "FINISH LAP"
    assert g.another_lap_estimate == "NO"


def test_qualifying_complete_terminal_state():
    g = evaluate_qualifying(
        session_finished=True, driver_status="On track", lap_valid=True,
        session_time_left_s=0, current_lap_time_s=None,
        lap_distance_m=None, track_length_m=None, best_lap_time_s=90.0,
    )
    assert g.decision == "QUALIFYING COMPLETE"


def test_time_to_line_current_pace_estimate():
    # 25% complete in 20s => 80s projected lap => ~60s to line.
    value = estimate_time_to_line_s(
        current_lap_time_s=20.0, lap_distance_m=1250.0,
        track_length_m=5000.0, best_lap_time_s=90.0,
    )
    assert abs(value - 60.0) < 1e-9


def test_overlay_snapshot_exposes_qualifying_clock_and_run_status():
    player = CarState(index=0)
    player.lap = LapState(current_lap=2, current_lap_time_s=12.0, lap_distance_m=700.0,
                          lap_valid=True, position=5, driver_status=ev(1, "Flying lap"))
    state = RaceState(
        session=SessionState(session_type=ev(9, "One-Shot Qualifying"), time_left_s=321, duration_s=900),
        player_index=0, player=player, field={0: player},
    )
    snap = build_overlay_snapshot(state, perf(), connected=True)
    assert snap.event_profile == "QUALIFYING"
    assert snap.driver_status == "Flying lap"
    assert snap.session_time_left_s == 321
    assert snap.session_duration_s == 900


def test_one_shot_qualifying_ignores_zero_clock_and_pushes_flying_lap():
    g = evaluate_qualifying(
        session_finished=False, driver_status="Flying lap", lap_valid=True,
        session_time_left_s=0, current_lap_time_s=30.0,
        lap_distance_m=1500.0, track_length_m=5000.0, best_lap_time_s=None,
        one_shot=True,
    )
    assert g.decision == "PUSH LAP"
    assert g.another_lap_estimate == "NO"
    assert g.time_to_line_estimate_s is None
