import json
from pathlib import Path

from src.performance_history import PerformanceHistoryStore
from src.performance_review import aggregate_session_from_lap_scores


def _seed_session(store: PerformanceHistoryStore, *, stored_best: float, stored_potential: float) -> int:
    with store._connect() as con:
        now='2026-10-01T14:42:34+00:00'
        con.execute("INSERT INTO user_profiles(name,created_utc,last_used_utc) VALUES(?,?,?)",('AH',now,now))
        pid=int(con.execute('SELECT last_insert_rowid()').fetchone()[0])
        con.execute("""INSERT INTO drivers(profile_key,name,first_seen_utc,last_seen_utc,profile_json)
                       VALUES(?,?,?,?,?)""",('drv','abhilashh2411',now,now,'{}'))
        did=int(con.execute('SELECT last_insert_rowid()').fetchone()[0])
        coach={
            'lap_telemetry':{
                '2':{'lap':2,'lap_time_s':79.319,'valid':True,'sector1_time_s':23.153,'sector2_time_s':32.282,'sector3_time_s':23.883},
                '10':{'lap':10,'lap_time_s':77.489,'valid':True,'sector1_time_s':22.754,'sector2_time_s':31.631,'sector3_time_s':23.103},
                '1':{'lap':1,'lap_time_s':85.537,'valid':False,'sector1_time_s':25.637,'sector2_time_s':34.788,'sector3_time_s':25.111},
            },
            'potential':{'best_lap_s':stored_best,'potential_lap_s':stored_potential,'potential_gain_s':0.0},
            'performance_review':{
                'session_technique_score':None,'confidence':0.0,
                'lap_reviews':[
                    {'lap':2,'summary':{'score':65.0,'confidence':.95}},
                    {'lap':3,'summary':{'score':80.0,'confidence':.97}},
                    {'lap':4,'summary':{'score':60.0,'confidence':.96}},
                    {'lap':5,'summary':{'score':66.0,'confidence':.98}},
                    {'lap':7,'summary':{'score':64.0,'confidence':.99}},
                    {'lap':6,'summary':{'score':54.0,'confidence':.96}},
                    {'lap':11,'summary':{'score':57.0,'confidence':.98}},
                ],
                'data_quality':{'eligible_laps':[]},
            },
        }
        summary={'best_lap_s':stored_best,'laps_completed':11}
        con.execute("""INSERT INTO sessions(session_key,driver_fk,user_profile_fk,session_uid,created_utc,track_id,track_name,session_type,session_group,game_mode,game_mode_name,laps_completed,best_lap_s,potential_lap_s,potential_gain_s,summary_json,coach_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ('drv|tt',did,pid,'123',now,'CATALUNYA','Catalunya','Time Trial','Time Trial',5,'Time Trial',11,stored_best,stored_potential,0.0,json.dumps(summary),json.dumps(coach)))
        sid=int(con.execute('SELECT last_insert_rowid()').fetchone()[0])
        con.commit()
        return sid


def test_repair_replaces_faster_foreign_pb_with_current_session_best(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    sid=_seed_session(store,stored_best=77.212,stored_potential=77.488)
    assert store._repair_recovered_session_aggregates() == 1
    detail=store.session_detail(sid)['session']
    assert detail['best_lap_s'] == 77.489
    assert detail['summary']['best_lap_s'] == 77.489
    assert detail['coach']['potential']['best_lap_s'] == 77.489
    # Potential remains sector-derived from this same session.
    assert detail['potential_lap_s'] == 77.488
    assert round(detail['potential_gain_s'],3) == .001


def test_reference_selector_and_review_use_same_current_session_best(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    sid=_seed_session(store,stored_best=77.212,stored_potential=77.488)
    opts=store.review_reference_options(sid)
    session_best=next(x for x in opts['options'] if x['id']=='session_best')
    assert session_best['lap_time_s'] == 77.489
    review=store.review_detail(sid,reference='session_best')
    assert review['session']['best_lap_s'] == 77.489
    assert review['visual_reference']['best_lap_s'] == 77.489


def test_existing_lap_score_aggregation_contract_is_unchanged():
    review={
        'lap_reviews':[
            {'lap':2,'summary':{'score':65.0,'confidence':.95}},
            {'lap':3,'summary':{'score':80.0,'confidence':.97}},
            {'lap':4,'summary':{'score':60.0,'confidence':.96}},
            {'lap':5,'summary':{'score':66.0,'confidence':.98}},
            {'lap':7,'summary':{'score':64.0,'confidence':.99}},
            {'lap':6,'summary':{'score':54.0,'confidence':.96}},
            {'lap':11,'summary':{'score':57.0,'confidence':.98}},
        ],
        'data_quality':{'eligible_laps':[]},
    }
    out=aggregate_session_from_lap_scores(review)
    assert out['session_technique_score'] == 62.4
    assert out['confidence'] == .97
    assert out['data_quality']['scored_laps'] == [2,3,4,5,7,6,11]
    assert out['data_quality']['eligible_laps'] == [2,3,4,5,6,7,11]
