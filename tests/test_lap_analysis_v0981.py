from src.lap_analysis import build_driving_analysis
from tests.test_lap_analysis_v098 import lap


def multi_lap(n, slow=False):
    x=lap(n,slow)
    x['sections']=[
        {'id':1,'start_m':200.0,'brake_end_m':260.0,'end_m':340.0,'min_speed_m':280.0,'min_speed_kph':120,'full_throttle_m':340.0,'exit_speed_kph':160,'peak_brake':.8,'max_slip':.05},
        {'id':2,'start_m':600.0,'brake_end_m':680.0,'end_m':760.0,'min_speed_m':700.0,'min_speed_kph':100,'full_throttle_m':760.0,'exit_speed_kph':150,'peak_brake':.9,'max_slip':.06},
    ]
    return x


def test_regions_are_contiguous_non_overlapping_and_cover_common_lap():
    r=build_driving_analysis(multi_lap(2,True),multi_lap(1,False))
    rows=r['corner_phase_analysis']
    assert r['regions_non_overlapping'] is True
    assert rows[0]['region_start_m']==r['first_common_m']
    assert rows[-1]['region_end_m']==r['last_common_m']
    for a,b in zip(rows,rows[1:]):
        assert a['region_end_m']==b['region_start_m']


def test_region_deltas_reconcile_to_finish_delta():
    r=build_driving_analysis(multi_lap(2,True),multi_lap(1,False))
    assert abs(r['region_delta_sum_s']-r['finish_normalized_delta_s']) <= 0.002
    assert abs(r['region_reconciliation_error_s']) <= 0.002


def test_phases_do_not_escape_their_region():
    r=build_driving_analysis(multi_lap(2,True),multi_lap(1,False))
    for row in r['corner_phase_analysis']:
        for p in row['phases']:
            assert row['region_start_m'] <= p['start_m'] <= p['end_m'] <= row['region_end_m']
