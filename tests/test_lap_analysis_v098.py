from src.lap_analysis import build_driving_analysis

def samples(offset=0.0, slow_zone=False):
    out={}
    t=offset
    for d in range(0,1001,5):
        speed=200.0
        if 400<=d<=600: speed=100.0 if slow_zone else 130.0
        t += 5.0/(speed/3.6)
        out[float(d)]={'d':float(d),'t':t,'speed':speed,'throttle':1.0 if d<400 or d>600 else .3,'brake':.8 if 400<=d<500 else 0.0,'steering':0.0,'gear':6,'rpm':10000}
    return out

def lap(n,slow=False,offset=0.0):
    s=samples(offset,slow)
    return {'lap':n,'lap_time_s':list(s.values())[-1]['t']-list(s.values())[0]['t'],'_samples':s,'sections':[{'id':1,'start_m':400.0,'brake_end_m':500.0,'end_m':650.0,'min_speed_m':500.0,'min_speed_kph':100 if slow else 130,'full_throttle_m':650.0,'exit_speed_kph':160,'peak_brake':.8,'max_slip':.05}]}

def test_timing_is_normalized_so_arbitrary_start_offset_disappears():
    r=build_driving_analysis(lap(2,True,7.0),lap(1,False,0.0))
    assert r['available']
    assert r['time_delta_trace'][0]['delta_s']==0.0
    assert r['finish_normalized_delta_s'] > 0

def test_phase_analysis_finds_loss_in_slow_region():
    r=build_driving_analysis(lap(2,True),lap(1,False))
    c=r['corner_phase_analysis'][0]
    assert c['zone_time_delta_change_s'] > 0
    assert any(p['time_delta_change_s'] > 0 for p in c['phases'])

def test_boundary_guard_keeps_100m_windows_away_from_start_finish():
    r=build_driving_analysis(lap(2,True),lap(1,False))
    w=r['largest_clean_100m_loss']
    assert w['start_m'] >= 50.0  # end >=150 due to 150 m guard
    assert w['end_m'] <= 850.0
