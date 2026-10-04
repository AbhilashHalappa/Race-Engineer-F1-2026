from types import SimpleNamespace

from src.measured_performance import Sample
from src.overlay.data import build_overlay_snapshot
from src.race_state.models import CarState, RaceState


def _lap(num, lap_time, *, valid=True, shift=0.0):
    samples = {
        0.0: {"d":0.0,"t":0.00+shift,"speed":200,"throttle":1.0,"brake":0.0,"steering":0.0,"gear":7,"rpm":11000},
        100.0: {"d":100.0,"t":1.00+shift,"speed":250,"throttle":1.0,"brake":0.0,"steering":0.0,"gear":8,"rpm":12000},
        200.0: {"d":200.0,"t":2.00+shift,"speed":120,"throttle":0.1,"brake":1.0,"steering":0.3,"gear":4,"rpm":9000},
        300.0: {"d":300.0,"t":3.00+shift,"speed":170,"throttle":1.0,"brake":0.0,"steering":0.1,"gear":5,"rpm":10000},
        500.0: {"d":500.0,"t":5.00+shift,"speed":260,"throttle":1.0,"brake":0.0,"steering":-0.2,"gear":8,"rpm":12000},
    }
    return {
        "lap":num,"valid":valid,"lap_time_s":lap_time,
        "sections":[{"id":1,"start_m":160.0,"min_speed_m":200.0,"min_speed_kph":120,"full_throttle_m":300.0,"exit_speed_kph":170,"peak_brake":1.0,"max_slip":0.05}],
        "_samples":samples,
    }


def test_overlay_snapshot_uses_best_valid_reference_and_live_delta():
    state=RaceState(player_index=0, player=CarState(index=0))
    state.player.telemetry.speed_kph=287
    state.player.telemetry.gear=8
    state.player.telemetry.throttle=.82
    state.player.telemetry.brake=.15
    state.player.lap.current_lap=3
    state.player.lap.lap_distance_m=200.0
    state.player.lap.current_lap_time_s=2.10
    state.player.lap.lap_valid=True

    best=_lap(1,70.0)
    slower=_lap(2,70.5)
    slower["sections"][0] = {**slower["sections"][0], "start_m":175.0, "min_speed_kph":114, "full_throttle_m":315.0, "exit_speed_kph":162}
    current={
        0.0:Sample(0.0,0.0,200,1.0,0.0,0.0,7,11000),
        100.0:Sample(100.0,1.05,245,1.0,0.0,0.0,8,12000),
        200.0:Sample(200.0,2.10,118,0.1,1.0,0.3,4,9000),
    }
    perf=SimpleNamespace(completed=[best,slower],samples=current,reference_mode="best",manual_reference_lap=None,event_context={"profile":"time_trial"})
    snap=build_overlay_snapshot(state,perf,connected=True)
    assert snap.event_profile == "TIME TRIAL"
    assert snap.reference_lap == 1
    assert snap.best_lap_time_s == 70.0
    assert abs(snap.live_delta_s - 0.10) < 1e-9
    assert snap.active_section == 1
    assert snap.speed_kph == 287 and snap.gear == 8
    # V0.9.9.2 coaching is current-lap live, not the last completed lap.
    assert snap.coach_live is True
    assert snap.comparison_lap == 3
    assert snap.coach_metrics[0].value == "40m later"
    assert snap.coach_metrics[1].status == "WAIT"
    assert snap.coach_metrics[2].status == "WAIT"
    assert snap.coach_metrics[3].status == "WAIT"


def test_overlay_snapshot_clamps_inputs_and_waits_without_reference():
    state=RaceState(player_index=0, player=CarState(index=0))
    state.player.telemetry.throttle=1.2
    state.player.telemetry.brake=-.2
    state.player.lap.current_lap=1
    state.player.lap.lap_distance_m=10.0
    perf=SimpleNamespace(completed=[],samples={},reference_mode="best",manual_reference_lap=None,event_context={"profile":"practice"})
    snap=build_overlay_snapshot(state,perf,connected=False)
    assert snap.throttle == 1.0
    assert snap.brake == 0.0
    assert snap.live_delta_s is None
    assert snap.reference_lap is None
    assert snap.event_profile == "PRACTICE"
    assert snap.connected is False
