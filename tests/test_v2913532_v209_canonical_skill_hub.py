from pathlib import Path
import json

from src.driver_profiles import DriverProfileStore
from src.driver_skill_reconciliation import DriverSkillReconciliation
from src.performance_hub_ui import performance_hub_page_html


def _write_evidence(ds: DriverProfileStore, driver_id: str, rows):
    root=ds.root/driver_id/'games'/'f1_26'/'skill_evidence'
    root.mkdir(parents=True, exist_ok=True)
    idx=[]
    for i,row in enumerate(rows,1):
        name=f's{i}.json'
        (root/name).write_text(json.dumps(row),encoding='utf-8')
        idx.append({'path':name})
    (root/'index.json').write_text(json.dumps({'sessions':idx}),encoding='utf-8')


def _session(key, track, braking, throttle, wet='dry'):
    return {
        'session_key':key,'timestamp':f'2026-10-03T00:0{key[-1]}:00+00:00','track':track,'session_type':'Time Trial',
        'conditions':{'wet_dry':wet},
        'measurements':[
            {'skill':'braking','metric':'braking_execution','value':braking,'confidence':1.0,'sample_count':12},
            {'skill':'traction_exit','metric':'throttle_application','value':throttle,'confidence':1.0,'sample_count':12},
            {'skill':'car_control','metric':'steering_control','value':90,'confidence':1.0,'sample_count':12},
            {'skill':'apex_minimum_speed','metric':'corner_speed_execution','value':80,'confidence':1.0,'sample_count':12},
            {'skill':'corner_entry','metric':'turn_in_execution','value':75,'confidence':1.0,'sample_count':12},
            {'skill':'pace','metric':'best_lap_gap_percent_to_reference','value':1.0,'confidence':1.0,'sample_count':3},
            {'skill':'consistency','metric':'lap_time_coefficient_of_variation','value':0.5,'confidence':1.0,'sample_count':3},
        ]
    }


def test_hub_uses_canonical_driver_profile_domains_only():
    html=performance_hub_page_html()
    assert 'DRIVER PROGRESS' in html
    assert 'Canonical current' in html
    assert 'DRIVER PROFILE SYNCED' in html
    assert '<button id=openDriverProfileInfo' not in html


def test_global_values_exactly_match_driver_skill_model(tmp_path: Path):
    ds=DriverProfileStore(tmp_path/'drivers')
    p=ds.create_profile('Driver'); did=p['driver_id']; ds.set_active_driver(did)
    _write_evidence(ds,did,[_session('s1','Catalunya',60,70),_session('s2','Austria',80,90)])
    recon=DriverSkillReconciliation(ds)
    result=recon.build(did,'all')
    canonical=recon.skill_model.recalculate(did)
    assert result['overall']['value']==canonical['overall']['value']
    for key,row in canonical['skills'].items():
        assert result['domains'][key]['current']==row['value']
    assert 'trail_braking' not in result['domains']
    assert 'line_consistency' not in result['domains']


def test_track_scope_uses_track_skill_authority(tmp_path: Path):
    ds=DriverProfileStore(tmp_path/'drivers')
    p=ds.create_profile('Driver'); did=p['driver_id']; ds.set_active_driver(did)
    _write_evidence(ds,did,[_session('s1','Catalunya',55,65),_session('s2','Catalunya',75,85),_session('s3','Austria',95,95)])
    recon=DriverSkillReconciliation(ds)
    result=recon.build(did,'Catalunya')
    track=recon.track_skills.summary(did,'Catalunya')
    assert result['scope']=='track'
    assert result['overall']['value']==track['overall']
    assert result['domains']['braking']['current']==track['skills']['braking']['value']
    assert result['stored_evidence_session_count']==track['session_count']
    assert result['scoreable_snapshot_count']==track['scoreable_session_count']


def test_wet_driving_remains_na_without_dedicated_evidence(tmp_path: Path):
    ds=DriverProfileStore(tmp_path/'drivers')
    p=ds.create_profile('Driver'); did=p['driver_id']; ds.set_active_driver(did)
    _write_evidence(ds,did,[_session('s1','Catalunya',70,70,'wet'),_session('s2','Catalunya',72,72,'wet')])
    result=DriverSkillReconciliation(ds).build(did,'Catalunya')
    assert result['domains']['wet_driving']['status']=='n/a'
    assert result['evidence_diagnostics']['wet_session_count']==2
    assert 'no dedicated wet_driving' in result['evidence_diagnostics']['wet_driving']
