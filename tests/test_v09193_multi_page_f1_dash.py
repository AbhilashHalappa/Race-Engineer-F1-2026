from types import SimpleNamespace

from src.dashboard_server import DASHBOARD_HTML, dashboard_payload
from src.overlay.data import build_overlay_snapshot
from src.telemetry.enums import EnumValue


def test_dashboard_html_has_all_pages_and_s_mode():
    for text in ("DASH", "DAMAGE", "TYRES", "PIT", "S MODE", "DAMAGE &amp; POWER UNIT", "TYRES &amp; BRAKES"):
        assert text in DASHBOARD_HTML
    assert '>DRS</div>' not in DASHBOARD_HTML


def test_payload_exposes_multi_page_channels():
    s = SimpleNamespace(
        s_mode_active=True, s_mode_available=True, active_aero_mode="Straight mode",
        front_left_wing_damage_percent=12, front_right_wing_damage_percent=23, rear_wing_damage_percent=3,
        floor_damage_percent=4, diffuser_damage_percent=5, sidepod_damage_percent=6, gearbox_damage_percent=7, engine_damage_percent=8,
        drs_fault=False, ers_fault=True, brake_damage_percent=(1,2,3,4), brake_temperatures_c=(800,810,700,710),
        tyre_damage_percent=(5,6,7,8), tyre_blisters_percent=(0,1,0,1), tyre_pressures_psi=(25.1,25.2,22.1,22.2),
        pit_stops=1, pit_speed_limit_kph=80, pit_lane_timer_active=True, pit_lane_time_s=12.3, pit_stop_time_s=2.4,
        serve_penalty=True, race_engineer=SimpleNamespace(next_tyre_compound="Medium", next_tyre_set=3),
    )
    p=dashboard_payload(s)
    assert p["s_mode_active"] is True
    assert p["front_left_wing_damage_percent"] == 12
    assert p["brake_temp_c"] == [800.0,810.0,700.0,710.0]
    assert p["pit_speed_limit_kph"] == 80
    assert p["next_tyre_compound"] == "Medium"


def test_overlay_snapshot_uses_actual_2026_active_aero_state():
    player=SimpleNamespace(
        aero=SimpleNamespace(active_aero_mode=EnumValue(1,"Straight mode"), active_aero_available=True, overtake_active=False, overtake_available=False, drs_allowed=False),
        damage=SimpleNamespace(front_left_wing_percent=10, front_right_wing_percent=20, rear_wing_percent=3, floor_percent=4, diffuser_percent=5, sidepod_percent=6, gearbox_percent=7, engine_percent=8, drs_fault=False, ers_fault=False, brakes_percent=None),
        tyres=SimpleNamespace(visual_compound=None, age_laps=2, surface_temperature_c=None, inner_temperature_c=None, pressure_psi=None, damage_percent=None, blisters_percent=None, wear_percent=None),
        fuel=SimpleNamespace(mix=EnumValue(1,"Standard")), energy=None, telemetry=None, lap=SimpleNamespace(position=1,current_lap=1,penalties_s=0,pit_stop_should_serve_penalty=False,unserved_stop_go=0,pit_status=None,driver_status=None,pit_stops=0,pit_lane_timer_active=False,pit_lane_time_s=None,pit_stop_time_s=None),
    )
    state=SimpleNamespace(player=player,player_index=0,session=SimpleNamespace(session_type=None,total_laps=5,safety_car=None,time_left_s=100,duration_s=200,pit_speed_limit_kph=80),extended={})
    performance=SimpleNamespace(samples={},completed=[],event_context={})
    snap=build_overlay_snapshot(state,performance,connected=True,now=0.0)
    assert snap.s_mode_active is True
    assert snap.s_mode_available is True
    assert snap.active_aero_mode == "Straight mode"
    assert snap.front_left_wing_damage_percent == 10
    assert snap.pit_speed_limit_kph == 80
