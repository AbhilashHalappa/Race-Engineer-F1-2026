from types import SimpleNamespace

from src.overlay.data import build_overlay_snapshot
from src.race_state.models import CarState, RaceState


def _lap(num, lap_time, *, valid):
    return {
        "lap": num,
        "valid": valid,
        "lap_time_s": lap_time,
        "sections": [],
        "_samples": {},
    }


def _state():
    state = RaceState(player_index=0, player=CarState(index=0))
    state.player.lap.current_lap = 2
    state.player.lap.lap_distance_m = 200.0
    return state


def test_best_reference_waits_when_only_invalid_laps_exist():
    perf = SimpleNamespace(
        completed=[_lap(1, 69.0, valid=False)],
        samples={},
        reference_mode="best",
        manual_reference_lap=None,
        event_context={"profile": "time_trial"},
    )
    snap = build_overlay_snapshot(_state(), perf, connected=True)
    assert snap.reference_lap is None
    assert snap.best_lap_time_s is None
    assert snap.live_delta_s is None


def test_best_reference_ignores_faster_invalid_lap_once_valid_exists():
    perf = SimpleNamespace(
        completed=[
            _lap(1, 69.0, valid=False),
            _lap(2, 70.2, valid=True),
        ],
        samples={},
        reference_mode="best",
        manual_reference_lap=None,
        event_context={"profile": "time_trial"},
    )
    snap = build_overlay_snapshot(_state(), perf, connected=True)
    assert snap.reference_lap == 2
    assert snap.best_lap_time_s == 70.2
