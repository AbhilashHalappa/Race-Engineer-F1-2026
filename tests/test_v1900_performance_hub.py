from pathlib import Path
from types import SimpleNamespace
import json
import urllib.request

from src.performance_history import PerformanceHistoryStore, driver_profile_from_state
from src.performance_hub_ui import performance_hub_page_html
from src.race_state.models import Identity
from src.telemetry.enums import EnumValue


def _profile():
    return {"name":"ABHILASH","driver_id":255,"race_number":7,"nationality_id":36,"platform_id":1,"team_id":8,"team_name":"McLaren","my_team":False,"ai_controlled":False,"game_year":2026,"game_version":"1.0"}


def _coach(uid=1, track="Austria", best=70.5, potential=70.1, refgap=.4):
    return {"created_utc":"2026-09-26T10:00:00+00:00","event_context":{"session_uid":uid,"track_name":track,"track_id":17,"session_type":"Race"},"potential":{"best_lap_s":best,"potential_lap_s":potential,"potential_gain_s":best-potential,"reference_lap_s":70.1,"potential_vs_reference_s":potential-70.1},"total_reference_gap_s":refgap,"ranked_biggest_opportunities":[{"corner_id":3,"mean_net_loss_s":.15,"dominant_issue_label":"Late throttle","dominant_phase":"EXIT"}],"best_strengths":[{"corner_id":1,"mean_net_loss_s":-.08}],"technique_metrics":{"corners":[]}}


def _summary(uid=1, track="Austria", best=70.5):
    return {"session_uid":uid,"track":track,"session_type":"Race","position":2,"grid_position":4,"laps_completed":18,"best_lap_s":best,"average_valid_lap_s":71.3,"warnings":1,"penalties_s":0,"pit_stops":1,"max_tyre_wear_percent":42.0,"max_tyre_temp_c":104.0}


def test_driver_profile_uses_f1_participant_identity():
    ident=Identity(name="ABHILASH",team=EnumValue(8,"McLaren"),race_number=7,driver_id=255,team_id=8,nationality_id=36,platform_id=1,my_team=False,ai_controlled=False)
    state=SimpleNamespace(player=SimpleNamespace(identity=ident),session=SimpleNamespace(game_year=2026,game_version="1.0"))
    p=driver_profile_from_state(state)
    assert p["name"]=="ABHILASH" and p["race_number"]==7 and p["team_name"]=="McLaren" and p["nationality_id"]==36


def test_sqlite_history_groups_track_and_retains_full_session(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/"history.sqlite3")
    store.record_session(_profile(),_summary(1),_coach(1))
    store.record_session(_profile(),_summary(2,best=70.2),_coach(2,best=70.2,potential=69.9,refgap=.1))
    overview=store.overview()
    assert overview["available"] and overview["totals"]["sessions"]==2 and overview["totals"]["tracks"]==1
    assert overview["driver"]["name"]=="ABHILASH"
    detail=store.track_detail("Austria")
    assert detail["session_count"]==2 and detail["sessions"][-1]["opportunities"][0]["corner_id"]==3
    one=store.session_detail(detail["sessions"][-1]["id"])
    assert one["available"] and one["session"]["coach"]["potential"]["potential_lap_s"]==69.9


def test_legacy_json_imports_to_first_real_driver(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path/"analysis").mkdir()
    (tmp_path/"analysis/driver_history.json").write_text(json.dumps([{"session_uid":99,"event_context":{"track_name":"Melbourne","track_id":0,"session_type":"Time Trial"},"best_lap_s":80.0,"potential_lap_s":79.5,"reference_gap_s":1.0}]))
    store=PerformanceHistoryStore("analysis/performance_history.sqlite3")
    store.record_session(_profile(),_summary(1),_coach(1))
    o=store.overview()
    assert o["totals"]["sessions"]==2 and {x["track"] for x in o["tracks"]}=={"Austria","Melbourne"}


def test_performance_page_contains_required_views():
    page=performance_hub_page_html()
    for token in ("DRIVER PERFORMANCE HUB","TRACK PERFORMANCE","SESSION HISTORY","/api/performance/overview","LATEST OPPORTUNITIES"):
        assert token in page


def test_dashboard_performance_routes(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store=PerformanceHistoryStore(); store.record_session(_profile(),_summary(1),_coach(1))
    from src.dashboard_server import DashboardStateStore, RemoteDashboardServer
    server=RemoteDashboardServer(DashboardStateStore(),host="127.0.0.1",port=0)
    info=server.start()
    try:
        page=urllib.request.urlopen(info.local_url+"performance",timeout=2).read().decode()
        assert "DRIVER PERFORMANCE HUB" in page
        data=json.loads(urllib.request.urlopen(info.local_url+"api/performance/overview",timeout=2).read())
        assert data["available"] and data["driver"]["name"]=="ABHILASH"
        td=json.loads(urllib.request.urlopen(info.local_url+"api/performance/track?track=Austria",timeout=2).read())
        assert td["session_count"]==1
    finally:
        server.stop()


def test_in_game_driver_changes_stay_in_one_selected_local_profile(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/"multi.sqlite3")
    pid=store.create_user_profile("ABHILASH")
    p1=_profile()
    p2=dict(p1,name="VERSTAPPEN",driver_id=1,race_number=1,team_id=9,team_name="Red Bull Racing '26")
    store.record_session(p1,_summary(77,"Melbourne",83.7),_coach(77,"Melbourne",83.7,83.1,.6))
    store.record_session(p2,_summary(78,"Melbourne",82.2),_coach(78,"Melbourne",82.2,81.9,.3))
    profiles=store.drivers()
    assert len(profiles)==1 and profiles[0]["id"]==pid
    o=store.overview(pid)
    assert o["totals"]["sessions"]==2 and o["tracks"][0]["best_lap_s"]==82.2
    detail=store.track_detail("Melbourne",pid)
    assert {x["game_driver_name"] for x in detail["sessions"]}=={"ABHILASH","VERSTAPPEN"}


def test_selected_local_profiles_keep_human_histories_independent(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/"preferred.sqlite3")
    p1=_profile(); p2=dict(p1,name="NORRIS",driver_id=4,race_number=4,team_name="McLaren")
    one=store.create_user_profile("Driver One")
    store.record_session(p1,_summary(1),_coach(1))
    two=store.create_user_profile("Driver Two")
    store.record_session(p2,_summary(2),_coach(2))
    assert store.overview()["driver"]["id"]==two
    assert store.overview(one)["totals"]["sessions"]==1
    assert store.overview(two)["totals"]["sessions"]==1
    assert store.set_preferred_driver(one)
    assert store.overview()["driver"]["name"]=="Driver One"


def test_browser_driver_selection_is_persistent():
    page=performance_hub_page_html()
    assert "driverSel" in page
    assert "raceEngineerPerformanceDriver" in page
