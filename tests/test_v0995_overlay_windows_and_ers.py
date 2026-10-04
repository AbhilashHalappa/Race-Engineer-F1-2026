from types import SimpleNamespace

from src.overlay.data import build_overlay_snapshot
from src.race_state.models import CarState, RaceState


def _state():
    state = RaceState(player_index=0, player=CarState(index=0))
    car = state.player
    car.telemetry.speed_kph = 250
    car.telemetry.gear = 7
    car.telemetry.throttle = 0.8
    car.telemetry.brake = 0.0
    car.energy.store_j = 3_250_000.0
    car.lap.current_lap = 4
    car.lap.current_lap_time_s = 45.0
    car.lap.lap_distance_m = 2500.0
    car.lap.lap_valid = True
    car.lap.sector = 2
    car.lap.sector1_time_s = 20.2
    car.lap.sector2_time_s = 28.9
    return state


def test_overlay_snapshot_exposes_ers_and_sector_deltas_for_new_panels():
    reference = {
        "lap": 3,
        "valid": True,
        "lap_time_s": 70.0,
        "sector1_time_s": 20.0,
        "sector2_time_s": 28.5,
        "sections": [],
        "_samples": {},
    }
    perf = SimpleNamespace(
        completed=[reference],
        samples={},
        reference_mode="best",
        manual_reference_lap=None,
        event_context={"profile": "race"},
    )
    snap = build_overlay_snapshot(_state(), perf, connected=True)
    assert snap.ers_store_j == 3_250_000.0
    assert snap.sector == 2
    assert round(snap.sector1_delta_s, 3) == 0.2
    assert round(snap.sector2_delta_s, 3) == 0.4
    assert snap.reference_lap == 3


def test_replay_checkpoint_methods_roundtrip_engine_state():
    from src.race_state_receiver import RaceStateReceiver
    r = RaceStateReceiver(tts_enabled=False)
    r.engine.state.session.uid = 123
    r.engine.state.player_index = 0
    r.engine.state.player = CarState(index=0)
    r.engine.state.player.lap.current_lap = 7
    cp = r.export_replay_checkpoint()
    r.engine.state.player.lap.current_lap = 2
    r.restore_replay_checkpoint(cp)
    assert r.engine.state.session.uid == 123
    assert r.engine.state.player.lap.current_lap == 7
    r.speech.close(wait=False)
