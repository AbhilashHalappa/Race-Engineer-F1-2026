from pathlib import Path

from src.performance_history import PerformanceHistoryStore
from src.performance_hub_ui import performance_hub_page_html


def _game():
    return {"name":"ANTONELLI","race_number":12,"platform_id":1,"team_name":"Mercedes '26"}


def _summary(uid, track, best):
    return {"session_uid":uid,"track":track,"session_type":"Short Practice","laps_completed":2,"best_lap_s":best,"position":1}


def _coach(uid, track, best):
    tele={
        "speed_kph":{"driver":[[0,200],[100,220]],"reference":[[0,205],[100,225]]},
        "brake":{"driver":[[0,0],[100,1]],"reference":[[0,0],[100,.8]]},
        "throttle":{"driver":[[0,1],[100,.5]],"reference":[[0,1],[100,.6]]},
        "gear":{"driver":[[0,7],[100,4]],"reference":[[0,7],[100,5]]},
        "ers":{"driver":[[0,80],[100,70]],"reference":[[0,82],[100,72]]},
        "delta_s":{"driver":[[0,0],[100,.2]],"reference":[[0,0],[100,0]]},
    }
    return {"event_context":{"session_uid":uid,"track_name":track,"session_type":"Short Practice","game_mode":4},
            "potential":{"best_lap_s":best},"reference_lap_s":best-1.0,"telemetry_overlay":tele,"reference_mode":"external"}


def test_tracks_are_alphabetical_and_track_delete_is_profile_scoped(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'h.sqlite3')
    pid=store.create_user_profile('Abhilash H')
    store.record_session(_game(),_summary(1,'Las Vegas',100.0),_coach(1,'Las Vegas',100.0))
    store.record_session(_game(),_summary(2,'Melbourne',90.0),_coach(2,'Melbourne',90.0))
    store.record_session(_game(),_summary(3,'Bahrain',95.0),_coach(3,'Bahrain',95.0))
    tracks=[x['track'] for x in store.overview(pid)['tracks']]
    assert tracks==['Bahrain','Las Vegas','Melbourne']
    assert store.delete_track_sessions('Melbourne',pid)==1
    tracks=[x['track'] for x in store.overview(pid)['tracks']]
    assert tracks==['Bahrain','Las Vegas']


def test_recorded_reference_exposes_reference_trace(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'h.sqlite3')
    store.create_user_profile('Abhilash H')
    sid=store.record_session(_game(),_summary(1,'Las Vegas',100.0),_coach(1,'Las Vegas',100.0))
    d=store.review_detail(sid,'recorded')
    assert d['visual_reference']['kind']=='recorded'
    assert d['visual_reference']['telemetry']['speed_kph']['reference']==[[0,205],[100,225]]


def test_ui_has_double_confirm_track_delete_and_preserves_track_after_session_delete():
    html=performance_hub_page_html()
    assert 'DELETE TRACK DATA' in html
    assert '/api/performance/delete-track' in html
    assert 'FINAL CONFIRMATION' in html
    assert 'let keepTrack=' in html
    assert 'stillExists' in html


def test_f1_dash_has_back_button_and_reference_search_uses_structured_root():
    dash=Path('src/dashboard_server.py').read_text(encoding='utf-8')
    hist=Path('src/performance_history.py').read_text(encoding='utf-8')
    assert 'id="dashBack" class="dashBack">← BACK TO HUB<' in dash
    assert "$('dashBack').onclick=()=>{location.href='/performance'}" in dash
    assert 'list_installed_references(REFERENCES)' in hist


def test_unknown_track_detail_and_delete_handle_null_track_identity(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'unknown.sqlite3')
    pid=store.create_user_profile('Abhilash H')
    # Existing/legacy sessions can have no resolved track name/id; overview labels them Unknown.
    sid=store.record_session(_game(),_summary(10,None,88.0),_coach(10,None,88.0))
    with store._connect() as con:
        con.execute("UPDATE sessions SET track_name=NULL, track_id=NULL WHERE id=?",(sid,))
        con.commit()
    assert [x['track'] for x in store.overview(pid)['tracks']]==['Unknown']
    detail=store.track_detail('Unknown',pid)
    assert detail['available'] and detail['session_count']==1
    assert store.delete_track_sessions('Unknown',pid)==1
    assert store.overview(pid)['tracks']==[]


def test_f1_dash_back_stays_above_offline_waiting_overlay():
    from src.dashboard_server import DASHBOARD_HTML
    dash = DASHBOARD_HTML
    assert '.dashBack{position:absolute;z-index:200;' in dash
    assert 'z-index:99' in dash
    assert 'pointer-events:none' in dash
    assert dash.index('id="offline"') < dash.index('id="dashBack"')
