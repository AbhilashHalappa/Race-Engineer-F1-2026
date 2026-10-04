from src.performance_history import PerformanceHistoryStore
from src.practice_planner import build_track_practice_plan


def _report(issue=None, eligible=(1,2,3), weather='dry'):
    pats=[] if issue is None else [{
        'corner_id': issue[0], 'issue_code': issue[1], 'issue_label': issue[2],
        'recent_time_cost_s': issue[3], 'mean_time_cost_s': issue[3],
        'mean_confidence': .9, 'repeat_count': 2, 'latest_observed': True,
    }]
    return {
        'best_lap': {'track_condition': weather, 'valid': True, 'lap_time_s': 70.0, 'sample_count': 200},
        'coaching_data_quality': {'eligible_laps': list(eligible)},
        'recurring_patterns': pats,
    }


def test_session_policy_includes_only_tt_practice_qualifying():
    f=PerformanceHistoryStore._practice_session_policy
    assert f('Time Trial')[0]
    assert f('Practice 1')[0]
    assert f('Free Practice')[0]
    assert f('Qualifying')[0]
    assert not f('Race')[0]
    assert not f('Sprint Race')[0]
    assert not f('Replay')[0]


def test_weather_bucket_is_dry_wet_unknown():
    f=PerformanceHistoryStore._practice_weather_condition
    assert f({'best_lap': {'track_condition':'dry'}}) == 'dry'
    assert f({'best_lap': {'weather_name':'Heavy Rain'}}) == 'wet'
    assert f({}) == 'unknown'


def test_unverified_latest_session_does_not_retire_old_issue():
    old={'session_id':1,'reference_evidence_mode':'legacy_unverified','report':_report((10,'late_throttle','Throttle pickup too late',.25)),'review':{},'best_lap_s':72.0}
    latest={'session_id':2,'reference_evidence_mode':'legacy_unverified','report':_report(None),'review':{},'best_lap_s':71.0}
    p=build_track_practice_plan([old,latest])
    assert p['primary_focus'] is not None
    assert p['primary_focus']['corner_id'] == 10
    assert p['status'] == 'provisional'


def test_verified_well_measured_latest_session_can_retire_old_issue():
    old={'session_id':1,'reference_evidence_mode':'verified','report':_report((10,'late_throttle','Throttle pickup too late',.25)),'review':{},'best_lap_s':72.0}
    latest={'session_id':2,'reference_evidence_mode':'verified','report':_report(None, eligible=(1,2,3)),'review':{},'best_lap_s':71.0}
    p=build_track_practice_plan([old,latest])
    assert p['primary_focus'] is None
    assert p['status'] == 'clear'
