from pathlib import Path
import tempfile

from src.performance_review import build_performance_review
from src.performance_hub_ui import performance_hub_page_html
from src.performance_history import PerformanceHistoryStore


def _analysis(cid=1, loss=.12, brake=-8.0, speed=-5.0, throttle=.15):
    # Complete enough serialized CornerAnalysis row for V2 scoring.
    from src.coaching_analysis import CornerAnalysis
    import dataclasses
    values={f.name:None for f in dataclasses.fields(CornerAnalysis)}
    values.update({
        'corner_id':cid,'reference_corner_id':cid,'apex_method':'path_curvature',
        'current_quality':1.0,'reference_quality':1.0,'match_quality':1.0,'confidence':.9,'confidence_reasons':(),
        'brake_onset_delta_m':brake,'brake_onset_m':100.0,'reference_brake_onset_m':108.0,
        'min_speed_delta_kph':speed,'min_speed_kph':120.0,'reference_min_speed_kph':125.0,
        'throttle_pickup_after_apex_delta_s':throttle,'throttle_pickup_after_apex_s':.55,'reference_throttle_pickup_after_apex_s':.40,
        'exit_speed_delta_kph':-3.0,'exit_speed_kph':180.0,'reference_exit_speed_kph':183.0,
        'time_loss_s':loss,'entry_time_loss_s':loss*.4,'mid_time_loss_s':loss*.3,'exit_time_loss_s':loss*.3,
    })
    # Required integer fields can be None; defaults added later remain okay.
    return values


def test_review_builds_session_laps_groups_and_corners():
    report={
        'reference_lap':{'lap':1,'lap_time_s':90.0},
        'lap_comparisons':[
            {'lap':2,'lap_time_s':90.5,'corner_analyses':[_analysis(1),_analysis(2,.08)]},
            {'lap':3,'lap_time_s':90.3,'corner_analyses':[_analysis(1,.09),_analysis(2,.05)]},
        ],
        'corner_drilldown':[{'corner_id':1,'mean_net_loss_s':.105,'dominant_issue_label':'Brake early','dominant_phase':'ENTRY'}, {'corner_id':2,'mean_net_loss_s':.065,'dominant_issue_label':'Throttle late','dominant_phase':'EXIT'}],
        'ranked_biggest_opportunities':[{'corner_id':1,'mean_net_loss_s':.105,'dominant_issue_label':'Brake early'}],
        'coaching_data_quality':{'eligible_laps':[2,3],'excluded_laps':[]},
        'eligible_lap_count':2,'timed_valid_lap_count':3,'telemetry_overlay':{'speed_kph':{'driver':[[0,100]],'reference':[[0,101]]}},
    }
    review=build_performance_review(report)
    assert review['format']=='RACE_ENGINEER_PERFORMANCE_REVIEW'
    assert len(review['laps'])==2
    assert len(review['corners'])==2
    assert review['session_technique_score'] is not None
    assert any(x['name']=='Braking' for x in review['technique_groups'])


def test_performance_review_ui_is_interactive_and_reference_selectable():
    page=performance_hub_page_html()
    for token in ('VISUAL REFERENCE','INTERACTIVE TRACK MAP','LINKED TELEMETRY','EVERY CORNER','reference-options','/api/performance/review','reviewRef','telemetryChart'):
        assert token in page


def test_review_reference_options_are_same_driver_track_only():
    with tempfile.TemporaryDirectory() as td:
        store=PerformanceHistoryStore(Path(td)/'perf.sqlite3')
        profile={'name':'Driver','race_number':7,'platform_id':1}
        coach={'telemetry_overlay':{'speed_kph':{'driver':[[0,100]],'reference':[]}}}
        a=store.record_session(profile,{'session_uid':'a','track':'MELBOURNE','session_type':'Practice','best_lap_s':90.0},{**coach,'potential':{'best_lap_s':90.0}})
        b=store.record_session(profile,{'session_uid':'b','track':'MELBOURNE','session_type':'Practice','best_lap_s':89.0},{**coach,'potential':{'best_lap_s':89.0}})
        store.record_session(profile,{'session_uid':'c','track':'MONZA','session_type':'Practice','best_lap_s':80.0},{**coach,'potential':{'best_lap_s':80.0}})
        opts=store.review_reference_options(a)
        ids=[x['id'] for x in opts['options'] if x.get('kind')=='session']
        assert b in ids and len(ids)==1


def test_review_reference_options_include_session_best_and_recorded_reference(tmp_path):
    store=PerformanceHistoryStore(tmp_path/'perf.sqlite3')
    profile={'name':'Driver','race_number':7,'platform_id':1}
    coach={'reference_mode':'external','telemetry_overlay':{'speed_kph':{'driver':[[0,100]],'reference':[[0,105]]}},'potential':{'best_lap_s':90.0,'reference_lap_s':88.0}}
    sid=store.record_session(profile,{'session_uid':'a','track':'MELBOURNE','session_type':'Practice','best_lap_s':90.0},coach)
    opts=store.review_reference_options(sid)['options']
    by_kind={x['kind']:x for x in opts if x['kind'] in {'session_best','recorded'}}
    assert by_kind['session_best']['lap_time_s']==90.0
    assert by_kind['recorded']['lap_time_s']==88.0
    assert 'rival/reference' in by_kind['recorded']['label'].lower()


def test_legacy_review_is_explicit_and_never_fabricates_detail(tmp_path):
    store=PerformanceHistoryStore(tmp_path/'perf.sqlite3')
    sid=store.record_session({'name':'Driver','race_number':7,'platform_id':1},
        {'session_uid':'legacy','track':'MELBOURNE','session_type':'Practice','best_lap_s':90.0},
        {'potential':{'best_lap_s':90.0}})
    detail=store.review_detail(sid,'session_best')
    assert detail['review_evidence_status']=='legacy_summary_only'
    assert detail['review']['session_technique_score'] is None
    assert detail['visual_reference']['kind']=='session_best'


def test_performance_hub_null_is_not_rendered_as_zero():
    page=performance_hub_page_html()
    assert "v!==null&&v!==undefined&&v!==''" in page
    assert 'Legacy session: per-lap review evidence was not recorded by that build.' in page


def test_v2034_review_has_detailed_corner_metrics():
    report={'reference_lap':{'lap':1,'lap_time_s':90.0},'lap_comparisons':[{'lap':2,'lap_time_s':90.5,'corner_analyses':[_analysis(1)]}],'corner_drilldown':[{'corner_id':1,'mean_net_loss_s':.12,'dominant_issue_label':'Brake early','dominant_phase':'ENTRY'}]}
    review=build_performance_review(report)
    c=review['corners'][0]
    assert 'detail' in c
    assert 'brake_onset_delta_m' in c['detail']


def test_v2034_selected_reference_comparison_changes_delta_trace():
    from src.performance_review import build_selected_reference_comparison
    payload={
        'session':{'best_lap_s':90.0},
        'review':{'corners':[]},
        'track_geometry':{'corners':[{'corner_id':1,'start_m':100.0,'apex_m':150.0,'end_m':200.0}]},
        'visual_reference':{'kind':'external','label':'Rival','lap_time_s':88.0,'best_lap_gap_s':2.0,'telemetry':{
            'speed_kph':{'driver':[[0,100],[100,150],[150,100],[200,140],[300,180]],'reference':[[0,100],[100,160],[150,110],[200,150],[300,190]]},
            'brake':{'driver':[[0,0],[70,0],[90,.2],[200,0]],'reference':[[0,0],[80,0],[100,.2],[200,0]]},
            'throttle':{'driver':[[150,0],[180,.3],[220,1]],'reference':[[150,0],[170,.3],[210,1]]},
            'delta_s':{'driver':[[0,9]],'reference':[]},
        }}
    }
    comp=build_selected_reference_comparison(payload)
    assert comp['available'] is True
    assert comp['corners'][0]['min_speed_delta_kph'] < 0
    assert payload['visual_reference']['telemetry']['delta_s']['driver'][0][1] == 0.0


def test_v2034_ui_separates_data_and_ai_summary_and_analysis_reference():
    from src.performance_hub_ui import performance_hub_page_html
    html=performance_hub_page_html()
    assert 'ANALYSIS REFERENCE' in html
    assert 'DATA-BASED SUMMARY' in html
    assert 'AI SESSION SUMMARY' in html
    assert 'AI CORNER SUMMARY' in html
    assert '/api/performance/ai-summary' in html
