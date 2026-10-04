import json
from pathlib import Path
from src.performance_history import PerformanceHistoryStore


def profile():
    return {"name":"abhilashh2411","race_number":12,"platform_id":1}


def coach(uid, track_name=None, track_id=None, laps=None):
    laps=laps or []
    return {
        "created_utc":"2026-10-01T10:00:00+00:00",
        "event_context":{"session_uid":uid,"track_name":track_name,"track_id":track_id,"session_type":"Time Trial","game_mode":5},
        "potential":{"best_lap_s":min((t for _,t in laps),default=None),"potential_lap_s":min((t for _,t in laps),default=None)},
        "lap_telemetry":{str(n):{"lap":n,"lap_time_s":t,"valid":True} for n,t in laps},
    }


def summary(uid, track, laps):
    return {"session_uid":uid,"track":track,"session_type":"Time Trial","laps_completed":len(laps),"best_lap_s":min((t for _,t in laps),default=None)}


def test_same_uid_unknown_then_bahrain_merges_into_one_track_and_preserves_laps(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'h.sqlite3')
    store.create_user_profile('Abhilash H')
    # First app instance: track not decoded yet.
    sid_unknown=store.record_session(profile(), summary(9001,None,[(1,94.411)]), coach(9001,None,None,[(1,94.411)]))
    assert any(x['track']=='Unknown' for x in store.overview()['tracks'])
    # Restart, same EA session UID, now authoritative Bahrain identity is present.
    sid_known=store.record_session(profile(), summary(9001,'Sakhir (Bahrain)',[(2,93.900)]), coach(9001,'Sakhir (Bahrain)',3,[(2,93.900)]))
    ov=store.overview()
    tracks={x['track']:x['sessions'] for x in ov['tracks']}
    assert 'Unknown' not in tracks
    assert tracks['Sakhir (Bahrain)']==1
    detail=store.session_detail(sid_known)['session']
    assert detail['track_name']=='Sakhir (Bahrain)'
    assert detail['track_id']=='3'
    assert sorted(int(k) for k in detail['coach']['lap_telemetry'])==[1,2]


def test_known_row_id_is_stable_on_later_autosave(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'h.sqlite3')
    store.create_user_profile('Abhilash H')
    sid1=store.record_session(profile(), summary(42,'Sakhir (Bahrain)',[(1,90.0)]), coach(42,'Sakhir (Bahrain)',3,[(1,90.0)]))
    sid2=store.record_session(profile(), summary(42,'Sakhir (Bahrain)',[(2,89.0)]), coach(42,'Sakhir (Bahrain)',3,[(2,89.0)]))
    assert sid2==sid1


def test_schema_v5_repairs_existing_unknown_duplicate_on_open(tmp_path: Path):
    db=tmp_path/'h.sqlite3'
    store=PerformanceHistoryStore(db)
    store.create_user_profile('Abhilash H')
    # Create canonical known row, then manually inject a pre-v5 Unknown duplicate.
    sid=store.record_session(profile(), summary(77,'Sakhir (Bahrain)',[(2,89.0)]), coach(77,'Sakhir (Bahrain)',3,[(2,89.0)]))
    with store._connect() as con:
        pid=con.execute('SELECT user_profile_fk FROM sessions WHERE id=?',(sid,)).fetchone()[0]
        did=con.execute('SELECT driver_fk FROM sessions WHERE id=?',(sid,)).fetchone()[0]
        c=coach(77,None,None,[(1,90.0)])
        con.execute("INSERT INTO sessions(session_key,driver_fk,user_profile_fk,session_uid,created_utc,track_id,track_name,session_type,session_group,game_mode,game_mode_name,summary_json,coach_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f'{pid}|77||Time Trial',did,pid,'77','2026-10-01T09:59:00+00:00',None,None,'Time Trial','time_trial',5,'Time Trial',json.dumps(summary(77,None,[(1,90.0)])),json.dumps(c)))
        con.execute("UPDATE meta SET value='4' WHERE key='schema_version'")
    reopened=PerformanceHistoryStore(db)
    ov=reopened.overview()  # opening triggers schema v5 migration
    tracks={x['track']:x['sessions'] for x in ov['tracks']}
    assert 'Unknown' not in tracks
    assert tracks['Sakhir (Bahrain)']==1
    row=reopened.track_detail('Sakhir (Bahrain)')['sessions'][0]
    detail=reopened.session_detail(row['id'])['session']
    assert sorted(int(k) for k in detail['coach']['lap_telemetry'])==[1,2]
