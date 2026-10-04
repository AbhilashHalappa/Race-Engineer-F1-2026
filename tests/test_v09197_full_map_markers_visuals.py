from types import SimpleNamespace

from src.dashboard_server import DASHBOARD_HTML, dashboard_payload
from src.overlay.data import build_overlay_snapshot
from src.overlay.track_maps import TRACK_MAPS
from src.telemetry.enums import TRACKS


def test_all_f126_enumerated_tracks_have_preloaded_maps():
    missing = [name for name in TRACKS.values() if name != "Unknown" and name.upper() not in TRACK_MAPS]
    assert missing == []
    assert all(len(points) >= 10 for points in TRACK_MAPS.values())


def test_dashboard_payload_exposes_reference_and_nearby_map_markers():
    marker = SimpleNamespace(kind="ahead", label="NORRIS", position=2, lap_distance_m=1234.0)
    s = SimpleNamespace(reference_map_distance_m=1180.0, map_nearby=(marker,))
    p = dashboard_payload(s)
    assert p["reference_map_distance_m"] == 1180.0
    assert p["map_nearby"] == [{"kind":"ahead","label":"NORRIS","position":2,"lap_distance_m":1234.0}]


def test_snapshot_builds_two_ahead_two_behind_markers_and_reference_distance():
    def car(pos, distance, name):
        return SimpleNamespace(lap=SimpleNamespace(position=pos, lap_distance_m=distance, gap_to_leader_s=0.0), identity=SimpleNamespace(name=name, team=None), tyres=None)
    player = SimpleNamespace(
        lap=SimpleNamespace(position=3, lap_distance_m=1000.0, current_lap_time_s=10.0, current_lap=2, gap_to_leader_s=0.0),
        telemetry=SimpleNamespace(throttle=0.0, brake=0.0), energy=None, aero=None, tyres=None, damage=None, fuel=None,
    )
    state = SimpleNamespace(
        player=player, player_index=2, session=SimpleNamespace(track_length_m=5000.0, uid=9, track=SimpleNamespace(name="Melbourne"), session_type=None, paused=False),
        field={0:car(1,1300,"A"),1:car(2,1150,"B"),2:player,3:car(4,900,"D"),4:car(5,800,"E"),5:car(6,700,"F")},
        extended={},
    )
    perf=SimpleNamespace(
        reference_mode="external",
        external_reference={"lap":1,"lap_time_s":50.0,"valid":True,"_samples":{0:{"t":0.0},1000:{"t":8.0},1500:{"t":12.0},5000:{"t":50.0}}},
        completed=[], samples={}, event_context={}, current_lap_started_clean=True,
    )
    snap=build_overlay_snapshot(state,perf,connected=True,now=0.0)
    assert 1200 < snap.reference_map_distance_m < 1400
    assert [(m.kind,m.position) for m in snap.map_nearby] == [("ahead",1),("ahead",2),("behind",4),("behind",5)]


def test_lan_uses_preloaded_map_library_and_multi_car_marker_logic():
    assert "const predefinedTracks=" in DASHBOARD_HTML
    assert "reference_map_distance_m" in DASHBOARD_HTML
    assert "map_nearby" in DASHBOARD_HTML
    assert "mkPlayer" in DASHBOARD_HTML and "mkRef" in DASHBOARD_HTML
    assert "BUILDING TRACK MAP" not in DASHBOARD_HTML


def test_native_f1_dash_uses_only_unified_overlay_chrome():
    text = open("src/overlay/window.py", encoding="utf-8").read()
    block = text.split("class F1DashOverlayWindow",1)[1].split("class OverlaySuite",1)[0]
    assert "self.header_button_bar=None" in block
    assert "self.minimize_button=None" in block
    assert "self.hide_button=None" in block
    assert "self._layout_header_buttons()" in block
