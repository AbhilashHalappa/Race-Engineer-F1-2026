from __future__ import annotations

from types import SimpleNamespace
from urllib.request import urlopen
import json

from src.dashboard_server import DashboardStateStore, RemoteDashboardServer, dashboard_payload


def _snapshot(**overrides):
    base = dict(
        connected=True,
        speed_kph=287,
        gear=7,
        rpm=11840,
        rev_lights_percent=82,
        throttle=1.0,
        brake=0.0,
        drs_active=True,
        drs_allowed=True,
        overtake_active=False,
        overtake_available=True,
        ers_deploy_mode="MEDIUM",
        ers_store_j=2_000_000.0,
        fuel_remaining_mass=14.2,
        fuel_remaining_laps=7.4,
        position=3,
        lap_number=5,
        total_laps=18,
        lap_time_s=61.234,
        best_lap_time_s=78.100,
        live_delta_s=-0.125,
        lap_valid=True,
        lap_distance_m=1250.0,
        track_length_m=5276.0,
        sector=2,
        current_compound="SOFT",
        tyre_age_laps=4,
        tyre_wear=(12.0, 13.0, 15.0, 16.0),
        tyre_surface_temperatures_c=(91.0, 92.0, 87.0, 88.0),
        tyre_inner_temperatures_c=(96.0, 97.0, 93.0, 94.0),
        penalties_s=0,
        safety_car="NONE",
        pit_status="NONE",
        session_type="RACE",
        event_profile="RACE",
        reference_name="Time Trial rival",
        session_finished=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_dashboard_payload_is_compact_and_deterministic():
    p = dashboard_payload(_snapshot())
    assert p["speed_kph"] == 287
    assert p["gear"] == 7
    assert p["rpm"] == 11840
    assert p["rev_lights_percent"] == 82
    assert p["ers_percent"] == 50.0
    assert p["delta_s"] == -0.125
    assert p["tyre_surface_temp_c"] == [91.0, 92.0, 87.0, 88.0]
    assert p["reference_name"] == "Time Trial rival"


def test_dashboard_server_serves_browser_and_state():
    store = DashboardStateStore()
    store.update_snapshot(_snapshot(speed_kph=301, gear=8))
    server = RemoteDashboardServer(store, host="127.0.0.1", port=0)
    info = server.start()
    try:
        with urlopen(info.local_url, timeout=2) as response:
            html = response.read().decode("utf-8")
        assert "Race Engineer F1 Dash" in html
        assert "EventSource('/events')" in html
        with urlopen(info.local_url + "api/state", timeout=2) as response:
            state = json.loads(response.read().decode("utf-8"))
        assert state["speed_kph"] == 301
        assert state["gear"] == 8
        assert state["connected"] is True
    finally:
        server.stop()


def test_main_contains_f1_dash_cli_and_direct_launcher():
    main_source = open("src/main.py", encoding="utf-8").read()
    window_source = open("src/overlay/window.py", encoding="utf-8").read()
    assert '--dash-port' in main_source
    assert '--no-web-dash' in main_source
    assert '"FD", "F1 Dash — local window / LAN browser"' in window_source
    assert '"FD": self.show_f1_dash' in window_source
