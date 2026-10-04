import dataclasses

from src.coaching_analysis import CornerAnalysis
from src.performance_review import build_performance_review, build_selected_reference_comparison
from src.performance_hub_ui import performance_hub_page_html


def analysis_row():
    vals={f.name:None for f in dataclasses.fields(CornerAnalysis)}
    vals.update({
        'corner_id':4,'reference_corner_id':4,'apex_method':'path_curvature',
        'current_quality':.95,'reference_quality':.96,'match_quality':.92,'confidence':.9,'confidence_reasons':(),
        'brake_onset_delta_m':-12.0,'peak_brake_delta':.08,'brake_release_delta_m':-5.0,
        'brake_release_ramp_delta_s':-.12,'trail_brake_delta_m':-9.0,
        'turn_in_delta_m':3.0,'apex_delta_m':2.0,'min_speed_delta_kph':-5.0,'apex_speed_delta_kph':-4.0,
        'steering_corrections_delta':2,'steering_smoothness_delta':-.15,
        'throttle_pickup_delta_m':11.0,'throttle_pickup_after_apex_delta_s':.14,
        'pickup_to_full_throttle_delta_s':.18,'full_throttle_delta_m':15.0,'exit_speed_delta_kph':-6.0,
        'max_slip_delta':.05,'steering_unwind_delta_s':.11,
        'entry_time_loss_s':.11,'mid_time_loss_s':.07,'exit_time_loss_s':.09,'time_loss_s':.27,
        'diagnosis':'brake_early','diagnosis_label':'Brake point too early','dominant_phase':'ENTRY',
        'issue_candidates':(
            {'code':'brake_early','label':'Brake point too early','phase':'ENTRY','magnitude':-12.0,'confidence':.9,'estimated_time_cost_s':.11},
            {'code':'minimum_speed_low','label':'Minimum speed too low','phase':'MID','magnitude':-5.0,'confidence':.82,'estimated_time_cost_s':.07},
            {'code':'exit_speed_low','label':'Exit speed too low','phase':'EXIT','magnitude':-6.0,'confidence':.78,'estimated_time_cost_s':.09},
        ),
    })
    return vals


def test_v204_corner_breakdown_has_three_phases_secondary_evidence_and_measured_total():
    report={
        'reference_lap':{'lap':1,'lap_time_s':90.0},
        'lap_comparisons':[{'lap':2,'lap_time_s':90.27,'corner_analyses':[analysis_row()]}],
        'corner_drilldown':[{'corner_id':4,'mean_net_loss_s':.27,'dominant_issue':'brake_early','dominant_issue_label':'Brake point too early','dominant_phase':'ENTRY'}],
    }
    review=build_performance_review(report)
    assert review['version']=='2.0.4'
    assert review['corner_breakdown_version']=='2.0.4'
    c=review['corners'][0]
    d=c['detail']
    assert d['phase_time_cost_s']=={'braking':.11,'mid_corner':.07,'exit':.09}
    assert d['peak_brake_delta']==.08
    assert d['steering_corrections_delta']==2.0
    assert d['pickup_to_full_throttle_delta_s']==.18
    assert d['max_slip_delta']==.05
    assert c['total_measured_time_loss_s']==.27
    assert [x['code'] for x in c['secondary_evidence']]==['exit_speed_low','minimum_speed_low']
    assert all(x['review_only'] for x in c['secondary_evidence'])


def test_v204_selected_reference_adds_brake_release_full_throttle_and_phase_cost_without_faking_steering():
    payload={
        'session':{'best_lap_s':90.0},
        'track_geometry':{'corners':[{'corner_id':1,'start_m':100.0,'apex_m':150.0,'end_m':210.0}]},
        'visual_reference':{'kind':'external','label':'Rival','telemetry':{
            'speed_kph':{'driver':[[0,100],[80,180],[100,150],[150,105],[210,155],[260,190]],'reference':[[0,100],[80,182],[100,155],[150,112],[210,163],[260,194]]},
            'brake':{'driver':[[70,0],[80,.2],[100,.8],[130,.3],[145,0],[160,0]],'reference':[[70,0],[90,.2],[105,.75],[135,.25],[150,0],[165,0]]},
            'throttle':{'driver':[[150,0],[180,.25],[220,1.0]],'reference':[[150,0],[170,.25],[205,1.0]]},
        }}
    }
    comp=build_selected_reference_comparison(payload)
    c=comp['corners'][0]
    assert c['brake_onset_delta_m']==-10.0
    assert c['brake_release_delta_m']==-5.0
    assert c['full_throttle_delta_m']==15.0
    assert c['pickup_to_full_throttle_delta_m']==5.0
    assert c['peak_brake_delta']>.0
    assert c['mid_time_loss_s'] is None
    assert 'steering' in c['evidence_note']


def test_v204_ui_has_explicit_phase_cards_and_review_only_secondary_evidence():
    html=performance_hub_page_html()
    for token in ('BRAKING / ENTRY','MID-CORNER','SECONDARY EVIDENCE · REVIEW ONLY','PEAK BRAKE','TRACTION / SLIP','TOTAL TIME'):
        assert token in html
