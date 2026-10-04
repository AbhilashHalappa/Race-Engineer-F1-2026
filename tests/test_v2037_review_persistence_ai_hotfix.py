import queue
from types import SimpleNamespace
from pathlib import Path

from src.race_state_receiver import RaceStateReceiver
from src.session_coach_report import build_coach_report
from src.performance_review import build_performance_review


def _raw_lap(n=1,t=90.0):
    samples={float(i*50):{'d':float(i*50),'t':i*0.5,'speed':150.0,'brake':0.0,'throttle':1.0,'gear':6} for i in range(120)}
    return {'lap':n,'lap_time_s':t,'valid':True,'lap_start_anchored':True,'sample_count':120,'_samples':samples,'track_name':'LAS VEGAS','track_length_m':6000.0,'fuel_start_kg':20.0,'tyre_compound':'soft'}


def test_live_history_autosave_persists_v2_lap_corner_intelligence(monkeypatch):
    r=RaceStateReceiver.__new__(RaceStateReceiver)
    r._telemetry_mode='live'; r._history_autosave_completed_count=0; r._history_autosave_game_lap_count=0
    r._history_autosave_q=queue.Queue(maxsize=1)
    raw=_raw_lap(1,90.0)
    perf=SimpleNamespace(completed=[raw],external_reference=None,reference_mode='best',event_context={'session_uid':1,'track_name':'LAS VEGAS','session_type':'Practice'})
    v2={'lap_number':1,'lap_score':72.0,'confidence':.9,'coverage':.9,'scored_corner_count':1,'eligible_corner_count':1,'lap_valid':True,'corners':{1:{'corner_id':1,'score':72.0,'score_status':'available','confidence':.9,'estimated_loss_s':.2,'dominant_issue':'brake_early','primary_text':'Brake later','dimension_scores':{'braking_point':70.0},'brake_point_delta_m':-10.0}}}
    r.corner_coach=SimpleNamespace(_v202_accumulator=SimpleNamespace(completed=[v2]))
    state=SimpleNamespace(session=SimpleNamespace(uid=1,session_type=SimpleNamespace(name='Practice')),player=SimpleNamespace(lap=SimpleNamespace(current_lap=2),identity=None))
    r.engine=SimpleNamespace(performance=perf,state=state)
    r.session_summary_tracker=SimpleNamespace(build=lambda state,perf:{'session_uid':1,'track':'LAS VEGAS','session_type':'Practice','laps_completed':1,'best_lap_s':90.0})
    monkeypatch.setattr('src.overlay.track_maps.get_track_map', lambda track: ((0.0,0.0),(1.0,1.0)))
    monkeypatch.setattr('src.overlay.track_maps.get_track_map_distances', lambda track: (0.0,100.0))
    monkeypatch.setattr('src.track_geometry.persisted_physical_turns', lambda track: ({'corner_id':1,'start_m':0.0,'apex_m':50.0,'end_m':100.0},))
    r._queue_live_history_autosave_locked()
    _profile,_summary,frozen=r._history_autosave_q.get_nowait()
    assert frozen.live_lap_intelligence[0]['lap_score']==72.0
    assert frozen.live_lap_intelligence[0]['lap_time_s']==90.0
    assert frozen.track_geometry_snapshot['corners'][0]['corner_id']==1


def test_performance_review_uses_live_lap_intelligence_when_legacy_comparisons_absent():
    report={'reference_lap':{'lap':0,'lap_time_s':89.0},'lap_comparisons':[],
            'live_lap_intelligence':[{'lap_number':1,'lap_time_s':90.0,'lap_score':72.0,'confidence':.9,'coverage':.9,'scored_corner_count':1,'eligible_corner_count':1,'lap_valid':True,'quality':{'eligible':True,'reasons':[]},'corners':{1:{'corner_id':1,'score':72.0,'score_status':'available','confidence':.9,'estimated_loss_s':.2,'dominant_issue':'brake_early','primary_text':'Brake later','dimension_scores':{'braking_point':70.0},'brake_point_delta_m':-10.0}}}],
            'coaching_data_quality':{'eligible_laps':[1],'excluded_laps':[]},'eligible_lap_count':1,'timed_valid_lap_count':1}
    review=build_performance_review(report)
    assert len(review['laps'])==1
    assert len(review['corners'])==1
    assert review['corners'][0]['score']==72.0
    assert review['corners'][0]['detail']['brake_onset_delta_m']==-10.0


def test_performance_review_keeps_compromised_corner_observations_but_not_score():
    report={'reference_lap':{'lap':0,'lap_time_s':89.0},'lap_comparisons':[],
            'live_lap_intelligence':[{'lap_number':1,'lap_time_s':90.0,'lap_score':72.0,'confidence':.9,'coverage':.9,'scored_corner_count':1,'eligible_corner_count':1,'lap_valid':True,'quality':{'eligible':False,'reasons':['damage_compromised']},'corners':{1:{'corner_id':1,'score':72.0,'score_status':'available','confidence':.9,'estimated_loss_s':.2,'dominant_issue':'brake_early','primary_text':'Brake later','dimension_scores':{'braking_point':70.0},'brake_point_delta_m':-10.0}}}]}
    review=build_performance_review(report)
    assert review['laps'][0]['score'] is None
    assert review['corners'][0]['score'] is None
    assert review['corners'][0]['evidence_status']=='observed_compromised'
    assert review['corners'][0]['mean_loss_s']==0.2


def test_ai_summary_route_is_post_not_get():
    text=Path('src/dashboard_server.py').read_text(encoding='utf-8')
    get_block=text[text.index('def do_GET'):text.index('def do_POST')]
    post_block=text[text.index('def do_POST'):]
    assert '/api/performance/ai-summary' not in get_block
    assert '/api/performance/ai-summary' in post_block
