from types import SimpleNamespace

from src.overlay.data import build_overlay_snapshot
from src.race_state.models import (
    CarState, Forecast, FuelState, Identity, LapState, MeasuredLapFact, RaceState,
    SessionState, TyreSet, TyreState, Wheels,
)
from src.telemetry.enums import EnumValue


def ev(raw, name):
    return EnumValue(raw, name)


def base_state(profile="practice"):
    player = CarState(index=0)
    player.identity = Identity(name="PLAYER", team=ev(1, "Ferrari"))
    player.lap = LapState(position=2, current_lap=4, current_lap_time_s=33.0, gap_to_leader_s=1.2)
    player.fuel = FuelState(remaining_mass=36.2, capacity=50.0, remaining_laps=34.5)
    player.tyres = TyreState(
        actual_compound=ev(17, "C4"), visual_compound=ev(16, "Soft"), age_laps=4,
        wear_percent=Wheels(FL=24, FR=27, RL=20, RR=17), fitted_set_index=1,
        sets=(
            TyreSet(0, ev(17,"C4"), ev(16,"Soft"), 8, True, ev(5,"Qualifying 1"), 18, 20, -0.120, False),
            TyreSet(1, ev(18,"C3"), ev(17,"Medium"), 27, True, ev(15,"Race"), 26, 30, 0.0, True),
            TyreSet(2, ev(19,"C2"), ev(18,"Hard"), 0, False, ev(15,"Race"), 35, 40, 0.250, False),
        ),
    )
    leader = CarState(index=1)
    leader.identity = Identity(name="LEADER", team=ev(0,"Mercedes"))
    leader.lap = LapState(position=1, current_lap=4, gap_to_leader_s=None)
    leader.tyres.visual_compound = ev(17,"Medium")
    behind = CarState(index=2)
    behind.identity = Identity(name="BEHIND", team=ev(2,"Red Bull Racing"))
    behind.lap = LapState(position=3, current_lap=4, gap_to_leader_s=2.0)
    behind.tyres.visual_compound = ev(16,"Soft")
    session = SessionState(
        session_type=ev(1,"Practice 1"), weather=ev(0,"Clear"), track_temperature_c=29,
        air_temperature_c=21, track_length_m=5000, forecast_accuracy=ev(0,"Perfect"),
        forecast=(
            Forecast(ev(1,"Practice 1"),0,ev(0,"Clear"),29,ev(2,"No change"),21,ev(2,"No change"),5),
            Forecast(ev(1,"Practice 1"),10,ev(3,"Light rain"),28,ev(1,"Down"),20,ev(1,"Down"),65),
        ),
    )
    state = RaceState(session=session, player_index=0, player=player, field={0:player,1:leader,2:behind}, active_car_count=3)
    state.measured_laps = (
        MeasuredLapFact(2, 90.2, 1.02, Wheels(3,3,2,2), fuel_remaining_end=38.2,
                        tyre_wear_end=Wheels(18,20,16,14), fitted_tyre_set_index=1),
        MeasuredLapFact(3, 89.8, 0.98, Wheels(3,4,2,2), fuel_remaining_end=37.2,
                        tyre_wear_end=Wheels(21,24,18,16), fitted_tyre_set_index=1),
    )
    metrics = {
        "tyre_wear_strategy": profile != "time_trial",
        "fuel_strategy": profile != "time_trial",
        "weather_strategy": profile != "time_trial",
    }
    performance = SimpleNamespace(
        completed=[
            {"lap":2,"valid":True,"lap_time_s":90.2,"sector1_time_s":22.0,"sector2_time_s":40.0,"sector3_time_s":28.2,"sections":[],"_samples":{}},
            {"lap":3,"valid":True,"lap_time_s":89.8,"sector1_time_s":21.8,"sector2_time_s":39.8,"sector3_time_s":28.2,"sections":[],"_samples":{}},
        ],
        samples={}, reference_mode="best", manual_reference_lap=None,
        event_context={"profile": profile, "metrics": metrics},
    )
    return state, performance


def test_strategy_overlay_snapshot_exposes_race_session_data():
    state, perf = base_state("practice")
    snap = build_overlay_snapshot(state, perf, connected=True)
    assert snap.tyre_wear_applicable is True
    assert snap.tyre_wear == (24.0, 27.0, 20.0, 17.0)
    assert snap.tyre_laps_remaining_estimate is not None
    assert len(snap.tyre_wear_history) == 2
    assert snap.fuel_applicable is True
    assert snap.fuel_remaining_laps == 34.5
    assert len(snap.fuel_history) == 2
    assert snap.weather_applicable is True
    assert [r.rain_percent for r in snap.weather_forecast] == [5,65]
    assert snap.standings_applicable is True
    assert [r.position for r in snap.standings] == [1,2,3]
    assert any(r.is_player for r in snap.standings)
    assert len(snap.lap_history) == 2
    assert snap.lap_history[0].best is True  # newest first: lap 3 is best
    assert snap.tyre_sets_applicable is True
    assert [r.compound for r in snap.tyre_sets] == ["Soft","Medium"]
    assert snap.tyre_sets[1].fitted is True


def test_time_trial_gates_strategy_but_keeps_raw_values():
    state, perf = base_state("time_trial")
    snap = build_overlay_snapshot(state, perf, connected=True)
    assert snap.tyre_wear_applicable is False
    assert snap.fuel_applicable is False
    assert snap.weather_applicable is False
    assert snap.standings_applicable is False
    assert snap.tyre_sets_applicable is False
    # Raw telemetry remains observable for diagnostics.
    assert snap.tyre_wear[0] == 24.0
    assert snap.fuel_remaining_mass == 36.2
    assert len(snap.weather_forecast) == 2
    assert len(snap.tyre_sets) == 2
