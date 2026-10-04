from pathlib import Path

from src.performance_history import PerformanceHistoryStore


def _profile():
    return {"name":"abhilashh2411","race_number":12,"platform_id":1,"team_name":"Mercedes '26"}


def _summary(laps_completed, best):
    return {"session_uid":4242,"track":"Catalunya","session_type":"Time Trial","laps_completed":laps_completed,"best_lap_s":best,"position":1}


def _coach(laps, best):
    lap_store={}
    facts=[]
    live=[]
    comps=[]
    for lap_no, lap_time in laps:
        lap_store[str(lap_no)]={
            "lap":lap_no,"lap_time_s":lap_time,"valid":True,
            "sector1_time_s":23.0,"sector2_time_s":32.0,"sector3_time_s":lap_time-55.0,
            "quality":{"eligible":True},
            "telemetry":{"speed_kph":{"driver":[[0,100],[100,200]],"reference":[]}},
        }
        facts.append({"lap":lap_no,"lap_time_s":lap_time,"valid":True,"analysis_eligible":True})
        live.append({"lap_number":lap_no,"lap_time_s":lap_time,"corners":[{"corner_id":1,"score":80}]})
        comps.append({"lap":lap_no,"lap_time_s":lap_time,"corner_analyses":[{"corner_id":1}]})
    return {
        "created_utc":"2026-09-29T06:00:00+00:00",
        "event_context":{"session_uid":4242,"track_name":"Catalunya","session_type":"Time Trial","game_mode":5},
        "potential":{"best_lap_s":best,"potential_lap_s":best},
        "lap_count":len(laps),"timed_valid_lap_count":len(laps),"eligible_lap_count":len(laps),
        "coaching_data_quality":{"eligible_laps":[n for n,_ in laps],"excluded_laps":[],"damage_override_laps":[]},
        "lap_telemetry":lap_store,"lap_facts":facts,"live_lap_intelligence":live,"lap_comparisons":comps,
    }


def test_same_session_garage_resume_keeps_earlier_lap_split(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    store.create_user_profile('Abhilash H')
    sid1=store.record_session(_profile(), _summary(5, 78.668), _coach([(1,83.7),(2,80.8),(3,79.4),(4,80.3),(5,78.668)],78.668))
    # Simulate returning to garage: the live performance accumulator restarts and
    # the next autosave contains only the newly driven laps 6-8, while the game's
    # logical session counter reports eight completed laps.
    sid2=store.record_session(_profile(), _summary(8, 77.212), _coach([(6,77.978),(7,78.717),(8,77.212)],77.212))
    assert sid2 == sid1

    detail=store.session_detail(sid1)['session']
    coach=detail['coach']
    assert detail['laps_completed'] == 8
    assert sorted(int(k) for k in coach['lap_telemetry']) == list(range(1,9))
    assert [x['lap'] for x in coach['lap_facts']] == list(range(1,9))
    assert [x['lap_number'] for x in coach['live_lap_intelligence']] == list(range(1,9))
    assert [x['lap'] for x in coach['lap_comparisons']] == list(range(1,9))
    # The session start time is stable across autosaves.
    assert detail['created_utc'] == '2026-09-29T06:00:00+00:00'

    opts=store.review_reference_options(sid1)['options']
    ids={x['id'] for x in opts}
    assert {f'lap:{n}' for n in range(1,9)} <= ids


def test_resumed_session_recomputes_best_and_sector_potential_from_merged_laps(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    store.create_user_profile('Abhilash H')
    sid=store.record_session(_profile(), _summary(3,79.319), _coach([(1,80.537),(2,79.319),(3,79.592)],79.319))
    # Later recovered/offline snapshot carries new laps but a stale pre-outage
    # potential aggregate. The merged completed-lap evidence must win.
    resumed=_coach([(4,79.797),(5,80.424),(6,82.960),(7,82.163),(8,79.361),(9,82.450),(10,77.489),(11,85.673)],79.319)
    resumed['potential']['potential_lap_s']=78.898
    # Match the observed best-sector combination from the S13 acceptance run.
    resumed['lap_telemetry']['10'].update(sector1_time_s=22.754,sector2_time_s=31.631,sector3_time_s=23.103)
    store.record_session(_profile(), _summary(11,79.319), resumed)
    detail=store.session_detail(sid)['session']
    assert detail['best_lap_s'] == 77.489
    assert abs(detail['potential_lap_s'] - 77.488) < 1e-9
    opts=store.review_reference_options(sid)['options']
    session_best=next(x for x in opts if x['id']=='session_best')
    assert session_best['lap_time_s'] == 77.489
    review=store.review_detail(sid, reference='session_best')
    assert review['session_quick_glance']['best_lap']['lap'] == 10
    assert review['session_quick_glance']['reference_lap_time_s'] == 77.489


def test_existing_stale_recovered_session_is_repaired_on_hub_read(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    store.create_user_profile('Abhilash H')
    sid=store.record_session(_profile(), _summary(11,77.489), _coach([(1,85.0),(2,79.319),(10,77.489)],77.489))
    # Simulate a DB produced by the pre-hotfix build: lap evidence is correct,
    # but top-level Best/Potential columns are stale.
    with store._connect() as con:
        row=con.execute('SELECT summary_json,coach_json FROM sessions WHERE id=?',(sid,)).fetchone()
        summary=__import__('json').loads(row['summary_json']); coach=__import__('json').loads(row['coach_json'])
        summary['best_lap_s']=79.319
        coach['potential']['best_lap_s']=79.319
        coach['potential']['potential_lap_s']=78.898
        con.execute('UPDATE sessions SET best_lap_s=?,potential_lap_s=?,summary_json=?,coach_json=? WHERE id=?',
                    (79.319,78.898,__import__('json').dumps(summary),__import__('json').dumps(coach),sid))
    ov=store.overview()
    session=next(x for x in ov['recent_sessions'] if x['id']==sid)
    assert session['best_lap_s']==77.489
    # _coach uses sectors 23/32/(lap-55), so lap 10 theoretical is itself.
    assert session['potential_lap_s'] <= 77.489
