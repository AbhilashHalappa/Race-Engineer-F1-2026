from types import SimpleNamespace

from src.overlay.data import build_overlay_snapshot
from src.pit_strategy import assess_pit
from src.race_state.models import CarState, Forecast, RaceState, TyreSet, Wheels
from src.telemetry.enums import EnumValue


def ev(raw, name):
    return EnumValue(raw, name)


def performance(profile):
    metrics = {
        "fuel_strategy": profile != "time_trial",
        "tyre_wear_strategy": profile != "time_trial",
        "weather_strategy": profile != "time_trial",
    }
    return SimpleNamespace(
        completed=[], samples={}, reference_mode="best", manual_reference_lap=None,
        event_context={"profile": profile, "metrics": metrics},
    )


def race_state():
    state = RaceState()
    car = CarState(0)
    state.player = car
    state.player_index = 0
    state.field[0] = car
    state.session.session_type = ev(15, "Race")
    state.session.total_laps = 5
    state.session.weather = ev(0, "Overcast")
    state.session.forecast = (
        Forecast(ev(15, "Race"), 0, ev(0, "Overcast"), 30, ev(2, "No change"), 21, ev(2, "No change"), 21),
    )
    car.lap.current_lap = 2
    car.lap.position = 1
    car.lap.penalties_s = 0
    car.tyres.visual_compound = ev(16, "Soft")
    car.tyres.age_laps = 1
    car.tyres.wear_percent = Wheels(5, 2, 4, 3)
    car.tyres.sets = (
        TyreSet(6, ev(17, "C4"), ev(16, "Soft"), 1, True, ev(15, "Race"), 22, 23, -0.02, False),
        TyreSet(11, ev(18, "C3"), ev(17, "Medium"), 0, True, ev(15, "Race"), 35, 35, 0.55, False),
    )
    car.fuel.remaining_laps = 1.61
    car.fuel.remaining_mass = 6.98
    car.fuel.capacity = 100.0
    car.damage.front_left_wing_percent = 0
    car.damage.front_right_wing_percent = 0
    return state


def test_pit_strategy_treats_ea_fuel_laps_as_mfd_margin():
    state = race_state()
    assessment = assess_pit(state)
    assert assessment.fuel_margin_laps == 1.61
    assert "fuel margin 1.6 laps" in assessment.reasons


def test_race_engineer_overlay_builds_deterministic_stay_out_summary():
    state = race_state()
    snap = build_overlay_snapshot(state, performance("race"), connected=True)
    r = snap.race_engineer
    assert r.applicable is True
    assert r.decision == "STAY OUT"
    assert r.position == 1
    assert r.lap_number == 2
    assert r.total_laps == 5
    assert r.laps_remaining == 3
    assert r.current_compound == "Soft"
    assert r.max_wear_percent == 5.0
    assert r.fuel_margin_laps == 1.61
    assert r.weather == "Overcast"
    assert r.rain_percent == 21
    assert r.front_wing_damage_percent == 0
    assert r.next_tyre_compound == "Medium"


def test_race_engineer_is_not_applicable_in_qualifying():
    state = race_state()
    state.session.session_type = ev(5, "Qualifying 1")
    snap = build_overlay_snapshot(state, performance("qualifying"), connected=True)
    assert snap.race_engineer.applicable is False
    assert snap.race_engineer.decision == "NOT APPLICABLE"


def test_race_engineer_finished_session_never_issues_live_strategy_call():
    state = race_state()
    state.session.ended = True
    snap = build_overlay_snapshot(state, performance("race"), connected=True)
    assert snap.race_engineer.session_finished is True
    assert snap.race_engineer.decision == "FINISHED"


def test_race_engineer_live_facts_advance_with_same_overlay_snapshot():
    state = race_state()
    # Simulate the exact shape of the reported issue: strategy window was opened
    # on lap 1, while the rest of the HUD later advanced to lap 3.
    state.player.lap.current_lap = 1
    state.player.tyres.age_laps = 0
    state.player.tyres.wear_percent = Wheels(0, 0, 0, 0)
    first = build_overlay_snapshot(state, performance("race"), connected=True)
    assert first.lap_number == 1
    assert first.tyre_age_laps == 0

    state.player.lap.current_lap = 3
    state.player.tyres.age_laps = 2
    state.player.tyres.wear_percent = Wheels(6.45, 2.86, 4.71, 3.70)
    state.player.fuel.remaining_laps = 1.66
    state.player.damage.front_left_wing_percent = 36
    later = build_overlay_snapshot(state, performance("race"), connected=True)

    # Top-level live facts are the source used by the Race Engineer CURRENT UI.
    assert later.lap_number == 3
    assert later.position == 1
    assert later.total_laps == 5
    assert later.current_compound == "Soft"
    assert later.tyre_age_laps == 2
    assert max(v for v in later.tyre_wear if v is not None) == 6.45
    assert later.fuel_remaining_laps == 1.66
    assert later.front_wing_damage_percent == 36
    # Deterministic decision data must belong to the same lap too.
    assert later.race_engineer.lap_number == later.lap_number
    assert later.race_engineer.tyre_age_laps == later.tyre_age_laps
    assert later.race_engineer.decision == "STAY OUT"
    assert later.race_engineer.reason == "no immediate serviceable pit trigger"
