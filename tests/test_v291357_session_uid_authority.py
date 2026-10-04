import json
from pathlib import Path
from src.performance_history import PerformanceHistoryStore


def profile():
    return {"name":"abhilashh2411","race_number":12,"platform_id":1}


def coach(uid, track_name=None, track_id=None, laps=None, session_type=None):
    laps=laps or []
    ctx={"session_uid":uid,"track_name":track_name,"track_id":track_id,"game_mode":5}
    if session_type is not None:
        ctx["session_type"]=session_type
    return {
        "created_utc":"2026-10-01T10:00:00+00:00",
        "event_context":ctx,
        "potential":{"best_lap_s":min((t for _,t in laps),default=None),"potential_lap_s":min((t for _,t in laps),default=None)},
        "lap_telemetry":{str(n):{"lap":n,"lap_time_s":t,"valid":True} for n,t in laps},
    }


def summary(uid, track, laps, session_type=None):
    d={"session_uid":uid,"track":track,"laps_completed":len(laps),"best_lap_s":min((t for _,t in laps),default=None)}
    if session_type is not None:
        d["session_type"]=session_type
    return d


def test_same_uid_missing_type_then_known_type_and_track_merges(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'h.sqlite3')
    store.create_user_profile('Abhilash H')
    store.record_session(profile(), summary(9001,None,[(1,94.411)],None), coach(9001,None,None,[(1,94.411)],None))
    sid=store.record_session(profile(), summary(9001,'Sakhir (Bahrain)',[(2,93.900)],'Time Trial'), coach(9001,'Sakhir (Bahrain)',3,[(2,93.900)],'Time Trial'))
    ov=store.overview()
    tracks={x['track']:x['sessions'] for x in ov['tracks']}
    assert 'Unknown' not in tracks
    assert tracks['Sakhir (Bahrain)']==1
    detail=store.session_detail(sid)['session']
    assert detail['session_type']=='Time Trial'
    assert sorted(int(k) for k in detail['coach']['lap_telemetry'])==[1,2]


def test_schema_v6_repairs_v5_rows_split_only_by_missing_session_type(tmp_path: Path):
    db=tmp_path/'h.sqlite3'
    store=PerformanceHistoryStore(db)
    store.create_user_profile('Abhilash H')
    known_id=store.record_session(profile(), summary(77,'Sakhir (Bahrain)',[(2,89.0)],'Time Trial'), coach(77,'Sakhir (Bahrain)',3,[(2,89.0)],'Time Trial'))
    with store._connect() as con:
        row=con.execute('SELECT user_profile_fk,driver_fk FROM sessions WHERE id=?',(known_id,)).fetchone()
        c=coach(77,None,None,[(1,90.0)],None)
        s=summary(77,None,[(1,90.0)],None)
        con.execute("INSERT INTO sessions(session_key,driver_fk,user_profile_fk,session_uid,created_utc,track_id,track_name,session_type,session_group,game_mode,game_mode_name,summary_json,coach_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f"{row['user_profile_fk']}|77|||",row['driver_fk'],row['user_profile_fk'],'77','2026-10-01T09:59:00+00:00',None,None,None,'other',5,'Time Trial',json.dumps(s),json.dumps(c)))
        con.execute("UPDATE meta SET value='5' WHERE key='schema_version'")
    reopened=PerformanceHistoryStore(db)
    tracks={x['track']:x['sessions'] for x in reopened.overview()['tracks']}
    assert 'Unknown' not in tracks
    assert tracks['Sakhir (Bahrain)']==1
    rows=reopened.track_detail('Sakhir (Bahrain)')['sessions']
    assert len(rows)==1
    detail=reopened.session_detail(rows[0]['id'])['session']
    assert detail['session_type']=='Time Trial'
    assert sorted(int(k) for k in detail['coach']['lap_telemetry'])==[1,2]
