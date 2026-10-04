from pathlib import Path
from types import SimpleNamespace

from src.dashboard_server import DASHBOARD_HTML, dashboard_payload
from src.overlay.data import build_overlay_snapshot


def test_dashboard_payload_exposes_engine_and_map_channels():
    s = SimpleNamespace(
        engine_temperature_c=108,
        engine_ice_wear_percent=10,
        engine_ce_wear_percent=11,
        engine_mguh_wear_percent=12,
        engine_mguk_wear_percent=13,
        engine_tc_wear_percent=14,
        engine_es_wear_percent=15,
        engine_blown=False,
        engine_seized=False,
        world_position_x=123.5,
        world_position_z=-45.25,
        session_uid=999,
        track_name="Miami",
    )
    p = dashboard_payload(s)
    assert p["engine_temperature_c"] == 108
    assert p["engine_mguk_wear_percent"] == 13
    assert p["world_position_x"] == 123.5
    assert p["world_position_z"] == -45.25
    assert p["session_uid"] == 999
    assert p["track_name"] == "Miami"


def test_lan_combines_engine_health_into_damage_page_and_keeps_map():
    for text in ('data-page="damage"', 'data-page="map"', 'DAMAGE &amp; POWER UNIT', 'id="puICE"', 'id="puMGUH"', 'id="mapPage"', 'id="trackPath"', 'id="mapDot"'):
        assert text in DASHBOARD_HTML
    assert 'data-page="engine"' not in DASHBOARD_HTML
    assert "function updateTrackMap" in DASHBOARD_HTML


def test_snapshot_extracts_engine_wear_and_world_position():
    damage = SimpleNamespace(
        front_left_wing_percent=0, front_right_wing_percent=0, rear_wing_percent=0,
        floor_percent=0, diffuser_percent=0, sidepod_percent=0, gearbox_percent=8,
        engine_percent=9, drs_fault=False, ers_fault=False, brakes_percent=None,
        engine_wear_percent={"ICE":10,"CE":11,"MGUH":12,"MGUK":13,"TC":14,"ES":15},
        engine_blown=False, engine_seized=False,
    )
    player = SimpleNamespace(
        telemetry=SimpleNamespace(engine_temperature_c=107, throttle=0.0, brake=0.0),
        damage=damage, aero=None, tyres=None, fuel=None, energy=None, lap=None,
    )
    motion = SimpleNamespace(m_carMotionData=[SimpleNamespace(m_worldPositionX=101.0, m_worldPositionZ=-55.0)])
    session = SimpleNamespace(uid=123, track=SimpleNamespace(name="Miami"), track_length_m=5000)
    state = SimpleNamespace(player=player, player_index=0, session=session, extended={"motion": motion})
    performance = SimpleNamespace(samples={}, completed=[], event_context={})
    snap = build_overlay_snapshot(state, performance, connected=True, now=0.0)
    assert snap.engine_ice_wear_percent == 10
    assert snap.engine_es_wear_percent == 15
    assert snap.engine_temperature_c == 107
    assert snap.world_position_x == 101.0
    assert snap.world_position_z == -55.0
    assert snap.session_uid == 123
    assert snap.track_name == "Miami"


def test_trace_widgets_no_longer_prefill_ghost_points_and_break_gaps():
    text = Path("src/overlay/widgets.py").read_text()
    assert "deque([0.0] * samples" not in text
    assert text.count("if distance is None:\n                        started = False") >= 2


def test_shared_overlay_chrome_is_the_only_visible_minimize_close_layer():
    text = Path("src/overlay/window.py").read_text()
    assert "def _make_minimize_button(self, size=22):" in text
    assert "b.clicked.connect(self.showMinimized)" in text
    # Legacy per-overlay minimize/close controls are no longer created. The
    # unified hover chrome is authoritative across every frameless overlay.
    assert text.count("_make_minimize_button(") == 1
    assert "Hide Driver Inputs overlay" not in text
    assert "Hide Reference Inputs overlay" not in text
    assert "Hide Delta overlay" not in text
    assert "Hide Live Laptime overlay" not in text


def test_record_button_is_wired_even_when_replay_controller_exists():
    text = Path("src/overlay/window.py").read_text()
    assert 'on_toggle_recording=(receiver.set_recording_enabled if receiver is not None and hasattr(receiver, "set_recording_enabled") else None)' in text
    receiver = Path("src/race_state_receiver.py").read_text()
    assert 'if enabled and self._telemetry_mode != "live":' in receiver
