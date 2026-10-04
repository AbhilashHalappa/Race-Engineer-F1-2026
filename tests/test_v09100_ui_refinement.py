from types import SimpleNamespace

from src.measured_performance import Sample
from src.overlay.data import build_overlay_snapshot
from src.race_state.models import CarState, RaceState


def _state():
    state = RaceState(player_index=0, player=CarState(index=0))
    state.session.track_length_m = 5000
    state.player.lap.current_lap = 1
    state.player.lap.current_lap_time_s = 12.0
    state.player.lap.lap_distance_m = 700.0
    state.player.telemetry.speed_kph = 250
    state.player.energy.store_j = 3_000_000.0
    state.player.energy.harvested_mguk_j = 210_000.0
    state.player.energy.harvested_mguh_j = 90_000.0
    state.player.energy.deployed_this_lap_j = 420_000.0
    state.player.fuel.remaining_mass = 7.5
    state.player.fuel.capacity = 10.0
    state.player.fuel.remaining_laps = 1.25
    return state


def test_overlay_exposes_ers_charge_discharge_and_fuel_capacity():
    perf = SimpleNamespace(
        completed=[],
        samples={},
        reference_mode="best",
        manual_reference_lap=None,
        event_context={"profile": "race", "metrics": {}},
    )
    snap = build_overlay_snapshot(_state(), perf, connected=True)
    assert snap.ers_store_j == 3_000_000.0
    assert snap.ers_harvested_j == 300_000.0
    assert snap.ers_deployed_j == 420_000.0
    assert snap.fuel_remaining_mass == 7.5
    assert snap.fuel_capacity == 10.0


def test_s_mode_metric_exists_before_reference_lap():
    state = _state()
    perf = SimpleNamespace(
        completed=[],
        samples={
            690.0: Sample(690.0, 11.8, 250, 1.0, 0.0, 0.0, 7, 12000, s_mode_available=True, s_mode_straight=False),
            700.0: Sample(700.0, 12.0, 252, 1.0, 0.0, 0.0, 7, 12100, s_mode_available=True, s_mode_straight=True),
        },
        reference_mode="best",
        manual_reference_lap=None,
        event_context={
            "profile": "race",
            "regulations_2026": True,
            "metrics": {"active_aero_analysis": True},
        },
    )
    snap = build_overlay_snapshot(state, perf, connected=True)
    assert snap.reference_lap is None
    assert snap.s_mode_metric is not None
    assert snap.s_mode_metric.label == "S Mode Enable"
    assert snap.s_mode_metric.value == "10m late"
