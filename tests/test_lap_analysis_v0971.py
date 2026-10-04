from src.lap_analysis import match_sections_by_distance, compare_sections

def sec(i,start,apex=None):
    return {'id':i,'start_m':start,'min_speed_m':apex if apex is not None else start+80,'min_speed_kph':100,'full_throttle_m':start+200,'exit_speed_kph':160,'peak_brake':.8,'max_slip':.1}

def test_distance_matching_does_not_shift_after_extra_section():
    cur={'sections':[sec(1,200),sec(2,300),sec(3,960),sec(4,1800)]}
    ref={'sections':[sec(1,205),sec(2,965),sec(3,1790)]}
    pairs=match_sections_by_distance(cur,ref,120)
    assert [(a['start_m'],b['start_m']) for a,b in pairs]==[(200,205),(960,965),(1800,1790)]

def test_far_sections_are_not_compared():
    cur={'sections':[sec(1,300)]}; ref={'sections':[sec(1,1000)]}
    assert compare_sections(cur,ref)==[]
