from src.lap_analysis import match_sections_by_distance, build_driving_analysis
from tests.test_lap_analysis_v0981 import multi_lap


def _sec(i,start,anchor,peak=1.0):
    return {'id':i,'start_m':start,'min_speed_m':anchor,'peak_brake':peak,'min_speed_kph':100,'end_m':anchor+100,'brake_end_m':anchor,'full_throttle_m':anchor+100,'exit_speed_kph':150,'max_slip':.05}


def test_global_match_skips_weak_extra_event_that_precedes_real_corner():
    cur={'sections':[_sec(1,175,215,.50),_sec(2,290,395,1.0),_sec(3,945,1050,1.0)]}
    ref={'sections':[_sec(1,200,365,1.0),_sec(2,965,1115,.88)]}
    pairs=match_sections_by_distance(cur,ref)
    assert [(a['id'],b['id']) for a,b in pairs] == [(2,1),(3,2)]


def test_official_lap_delta_reconciles_with_explicit_boundary_residual():
    cur=multi_lap(2,True); ref=multi_lap(1,False)
    # Deliberately create an official timing offset that normalisation cannot localise.
    cur['lap_time_s']=ref['lap_time_s']+3.25
    r=build_driving_analysis(cur,ref)
    assert abs(r['full_lap_accounted_delta_s']-3.25) <= .002
    assert abs(r['full_lap_reconciliation_error_s']) <= .002
    assert abs((r['region_delta_sum_s']+r['boundary_timing_residual_s'])-3.25) <= .002


def test_boundary_residual_is_not_assigned_to_physical_corner_regions():
    cur=multi_lap(2,True); ref=multi_lap(1,False)
    cur['lap_time_s']=ref['lap_time_s']+5.0
    r=build_driving_analysis(cur,ref)
    assert r['common_distance_fully_partitioned'] is True
    assert abs(r['region_delta_sum_s']-r['finish_normalized_delta_s']) <= .002
    assert r['boundary_timing_residual_s'] is not None
