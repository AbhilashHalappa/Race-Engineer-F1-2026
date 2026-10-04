from src.overlay.data import build_overlay_snapshot
from tests.test_v09110_race_engineer_overlay import race_state, performance


def test_final_lap_forces_finish_the_race_and_suppresses_normal_pit_decision():
    state = race_state()
    state.player.lap.current_lap = state.session.total_laps
    state.player.lap.position = 2
    state.player.tyres.age_laps = 4
    state.player.fuel.remaining_laps = 1.80

    snap = build_overlay_snapshot(state, performance("race"), connected=True)
    re = snap.race_engineer

    assert snap.session_finished is False
    assert re.laps_remaining == 0
    assert re.decision == "FINISH THE RACE"
    assert re.confidence == "high"
    assert re.reason == "final lap — no strategic stop remaining"


def test_finished_race_overrides_final_lap_state():
    state = race_state()
    state.player.lap.current_lap = state.session.total_laps
    state.player.lap.position = 1
    state.session.ended = True

    snap = build_overlay_snapshot(state, performance("race"), connected=True)
    re = snap.race_engineer

    assert snap.session_finished is True
    assert re.session_finished is True
    assert re.decision == "FINISHED"
    assert re.reason == "race finished"
