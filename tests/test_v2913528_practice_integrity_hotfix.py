from pathlib import Path
from types import SimpleNamespace

from src.measured_performance import MeasuredPerformanceRecorder
from src.potential_lap import potential_summary
from src.practice_planner import build_practice_plan
from src.performance_history import PerformanceHistoryStore, _session_quick_glance
from src.race_state.models import Freshness


def _enum(name="None", raw=0):
    return SimpleNamespace(name=name, raw=raw)


def _traffic_state(frame, t, *, player_d=1000.0, other_d=None, legacy_front=0.2, speed=216):
    player_lap=SimpleNamespace(pit_status=_enum(),gap_to_car_in_front_s=legacy_front,lap_distance_m=player_d,current_lap_time_s=t)
    player=SimpleNamespace(
        lap=player_lap,
        telemetry=SimpleNamespace(speed_kph=speed),
        damage=SimpleNamespace(front_left_wing_percent=0,front_right_wing_percent=0,floor_percent=0,engine_blown=False,engine_seized=False),
    )
    field={0:player}
    if other_d is not None:
        field[1]=SimpleNamespace(lap=SimpleNamespace(pit_status=_enum(),lap_distance_m=other_d))
    return SimpleNamespace(
        player=player,player_index=0,field=field,gap_behind_s=0.2,
        session=SimpleNamespace(session_time_s=t,paused=False,safety_car=_enum(),marshal_zones=(),track_length_m=4657.0),
        updated={"lap":Freshness(t,frame,t)},
    )


def test_practice_ignores_close_legacy_gap_when_only_physical_car_is_behind():
    r=MeasuredPerformanceRecorder(); r.event_context={"profile":"practice"}
    for frame,t in ((1,10.0),(2,11.0),(3,12.2),(4,13.0)):
        r._update_lap_quality_flags(_traffic_state(frame,t,other_d=970.0,legacy_front=0.2))
    assert r.current_lap_traffic_compromised is False
    assert r.current_lap_traffic_front_min_gap_s == 0.2  # diagnostic only
    assert r.current_lap_traffic_front_min_distance_m is None


def test_practice_rejects_sustained_car_physically_ahead_even_if_classification_gap_is_large():
    r=MeasuredPerformanceRecorder(); r.event_context={"profile":"practice"}
    for frame,t in ((1,20.0),(2,21.0),(3,22.1)):
        r._update_lap_quality_flags(_traffic_state(frame,t,other_d=1040.0,legacy_front=8.0))
    assert r.current_lap_traffic_compromised is True
    assert r.current_lap_traffic_trigger == "sustained_physical_front"
    assert 39.9 <= r.current_lap_traffic_front_min_distance_m <= 40.1


def test_practice_reference_uses_fastest_eligible_lap_not_faster_excluded_session_best(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    pid=store.create_user_profile('Tester')
    coach={
        'created_utc':'2026-10-03T00:00:00+00:00',
        'event_context':{'session_uid':1,'track_name':'Catalunya','track_id':14,'session_type':'Short Practice','game_mode':4},
        'best_lap':{'lap':4,'lap_time_s':96.539,'valid':True,'track_condition':'wet'},
        'lap_facts':[
            {'lap':4,'lap_time_s':96.539,'valid':True,'track_condition':'wet'},
            {'lap':5,'lap_time_s':97.189,'valid':True,'track_condition':'wet'},
        ],
        'lap_telemetry':{
            '4':{'lap':4,'lap_time_s':96.539,'valid':True,'analysis_eligible':False},
            '5':{'lap':5,'lap_time_s':97.189,'valid':True,'analysis_eligible':True},
        },
        'coaching_data_quality':{'eligible_laps':[5],'excluded_laps':[{'lap':4,'eligible':False,'reasons':['traffic_compromised']}]},
        'timed_valid_lap_count':2,'recurring_patterns':[],'ranked_biggest_opportunities':[],'lap_comparisons':[],
        'performance_review':{'data_quality':{'eligible_laps':[5],'excluded_laps':[{'lap':4,'eligible':False,'reasons':['traffic_compromised']}]}}
    }
    sid=store.record_session(
        {'name':'Tester','race_number':1,'platform_id':1,'team_name':'Test'},
        {'session_uid':1,'track':'Catalunya','session_type':'Short Practice','laps_completed':2,'best_lap_s':96.539},coach,
    )
    detail=store.practice_track_detail('Catalunya',pid,condition='wet')
    ref=next(x for x in detail['reference_options'] if x['id']==f'session_best:{sid}')
    assert ref['lap_time_s'] == 97.189
    assert ref['lap'] == 5
    assert ref['quality_eligible'] is True


def test_potential_can_never_be_slower_than_observed_best():
    laps=[
        {'lap':1,'valid':True,'lap_time_s':77.861,'sector1_time_s':None,'sector2_time_s':None,'sector3_time_s':None,'sample_count':100,'lap_start_anchored':True},
        {'lap':2,'valid':True,'lap_time_s':77.990,'sector1_time_s':23.416,'sector2_time_s':30.921,'sector3_time_s':23.652,'sample_count':100,'lap_start_anchored':True},
    ]
    out=potential_summary(laps)
    assert out['best_lap_s'] == 77.861
    assert out['potential_lap_s'] == 77.861
    assert out['potential_gain_s'] == 0.0
    assert out['potential_guarded_by_observed_best'] is True


def test_quick_glance_theoretical_can_never_be_slower_than_best_lap():
    payload={'session':{},'reference_mode':'recorded','visual_reference':{'lap_time_s':77.861},'review':{}}
    coach={'lap_facts':[
        {'lap':1,'lap_time_s':77.861,'valid':True},
        {'lap':2,'lap_time_s':77.990,'valid':True,'sector1_time_s':23.416,'sector2_time_s':30.921,'sector3_time_s':23.652},
    ]}
    q=_session_quick_glance(payload,coach)
    assert q['theoretical_lap_s'] == 77.861
    assert q['theoretical_guarded_by_best_lap'] is True


def test_session_history_sector_only_update_reconciles_completed_lap():
    r=MeasuredPerformanceRecorder()
    r.completed=[{'lap':1,'lap_time_s':77.861,'valid':True,'sector1_time_s':None,'sector2_time_s':None,'sector3_time_s':None,'_samples':{}}]
    row=SimpleNamespace(m_lapTimeInMS=77861,m_lapValidBitFlags=1,
        m_sector1TimeMinutesPart=0,m_sector1TimeMSPart=0,
        m_sector2TimeMinutesPart=0,m_sector2TimeMSPart=0,
        m_sector3TimeMinutesPart=0,m_sector3TimeMSPart=0)
    hist=SimpleNamespace(m_carIdx=0,m_numLaps=1,m_lapHistoryData=[row])
    state=SimpleNamespace(extended={'history':hist},player_index=0)
    r._sync_session_history(state)
    assert r.completed[0]['sector1_time_s'] is None
    # Lap time/validity stay unchanged; only late sector fields arrive.
    row.m_sector1TimeMSPart=23416; row.m_sector2TimeMSPart=30921; row.m_sector3TimeMSPart=23524
    r._sync_session_history(state)
    assert r.completed[0]['sector1_time_s'] == 23.416
    assert r.completed[0]['sector2_time_s'] == 30.921
    assert r.completed[0]['sector3_time_s'] == 23.524


def test_practice_secondary_is_independent_from_same_corner_phase():
    report={
        'coaching_data_quality':{'eligible_laps':[1,2,3]},
        'best_lap':{'lap_time_s':90.0},
        'recurring_patterns':[
            {'corner_id':1,'issue_code':'braking_too_early','issue_label':'Braking too early','phase':'ENTRY','repeat_count':3,'mean_time_cost_s':1.479,'recent_time_cost_s':1.479,'mean_confidence':0.92,'latest_observed':True,'focus_score':10},
            {'corner_id':1,'issue_code':'brake_pressure_low','issue_label':'Brake pressure too low','phase':'ENTRY','repeat_count':3,'mean_time_cost_s':1.479,'recent_time_cost_s':1.479,'mean_confidence':0.92,'latest_observed':True,'focus_score':9},
            {'corner_id':9,'issue_code':'throttle_slow','issue_label':'Too slow to full throttle','phase':'EXIT','repeat_count':2,'mean_time_cost_s':0.642,'recent_time_cost_s':0.642,'mean_confidence':0.90,'latest_observed':True,'focus_score':8},
        ],
        'ranked_biggest_opportunities':[], 'lap_comparisons':[],
    }
    plan=build_practice_plan(report,{})
    assert plan['primary_focus']['corner_id'] == 1
    assert plan['primary_focus']['phase'] == 'ENTRY'
    assert plan['secondary_focus']['corner_id'] == 9
    assert plan['secondary_focus']['phase'] == 'EXIT'
    assert '1.479 s' in plan['phases'][4]['evidence']
