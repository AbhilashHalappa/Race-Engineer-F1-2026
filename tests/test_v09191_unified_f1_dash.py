from __future__ import annotations

from types import SimpleNamespace

from src.dashboard_server import DASHBOARD_HTML, dashboard_payload
from src.overlay.data import build_overlay_snapshot


def test_web_payload_exposes_setup_strip_channels_without_inference():
    s = SimpleNamespace(connected=True, speed_kph=0, gear=0, throttle=0.0, brake=0.0, ers_store_j=None, tyre_wear=(5.0, 8.0, 6.0, 7.0), tyre_surface_temperatures_c=(None, None, None, None), tyre_inner_temperatures_c=(None, None, None, None), setup_diff_on_throttle_percent=55, setup_diff_off_throttle_percent=50, setup_brake_bias_percent=57, setup_engine_braking_percent=40, front_wing_damage_percent=0, penalties_s=0, fuel_mix="Standard")
    p = dashboard_payload(s)
    assert p["setup_diff_on_throttle_percent"] == 55
    assert p["setup_diff_off_throttle_percent"] == 50
    assert p["setup_brake_bias_percent"] == 57
    assert p["setup_engine_braking_percent"] == 40
    assert p["front_wing_damage_percent"] == 0
    assert p["tyre_wear"] == [5.0, 8.0, 6.0, 7.0]
    assert p["penalties_s"] == 0
    assert p["fuel_mix"] == "Standard"


def test_browser_dash_contains_unified_status_strip():
    for label in ("DIFF", "BBAL", "ENG BRK", "FUEL MODE", "PEN"):
        assert f">{label}<" in DASHBOARD_HTML
    for field in ("setup_diff_on_throttle_percent", "setup_diff_off_throttle_percent", "setup_brake_bias_percent", "setup_engine_braking_percent"):
        assert field in DASHBOARD_HTML
    assert "SECTOR" in DASHBOARD_HTML


def test_overlay_snapshot_reads_direct_ea_setup_packet_values():
    car_setup = SimpleNamespace(m_onThrottle=55, m_offThrottle=50, m_brakeBias=57, m_engineBraking=40)
    fuel = SimpleNamespace(mix=SimpleNamespace(name="Standard"))
    player = SimpleNamespace(fuel=fuel)
    state = SimpleNamespace(player=player, player_index=0, session=None, extended={"setups": SimpleNamespace(m_carSetupData=[car_setup])})
    performance = SimpleNamespace(samples={}, completed=[], event_context={})
    snap = build_overlay_snapshot(state, performance, connected=False, now=0.0)
    assert (snap.setup_diff_on_throttle_percent, snap.setup_diff_off_throttle_percent) == (55.0, 50.0)
    assert snap.setup_brake_bias_percent == 57.0
    assert snap.setup_engine_braking_percent == 40.0
    assert snap.fuel_mix == "Standard"


def test_setup_strip_stays_absent_without_setup_packet():
    state = SimpleNamespace(player=None, player_index=0, session=None, extended={})
    performance = SimpleNamespace(samples={}, completed=[], event_context={})
    snap = build_overlay_snapshot(state, performance, connected=False, now=0.0)
    assert snap.setup_diff_on_throttle_percent is None
    assert snap.setup_diff_off_throttle_percent is None
    assert snap.setup_brake_bias_percent is None
    assert snap.setup_engine_braking_percent is None
