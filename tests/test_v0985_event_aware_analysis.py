from types import SimpleNamespace as NS

from src.event_context import build_event_context
from src.measured_performance import MeasuredPerformanceRecorder, Sample
from src.telemetry.enums import EnumValue


def make_state(session_type, *, parc=False, damage=2, safety=2, red=2, regs=True):
    session=NS(
        session_type=EnumValue(session_type, 'test'), game_mode=7, rule_set=3,
        network_game=True, formula=0, equal_car_performance=1,
        parc_ferme_rules=parc, car_damage=damage, car_damage_rate=1,
        corner_cutting_stringency=1, safety_car_setting=safety,
        red_flags_setting=red, low_fuel_mode=1,
    )
    player=NS(aero=NS(regulations_2026=regs))
    return NS(session=session, player=player)


def sample(d, *, brake=0.0, speed=200, steer=0.0, throttle=1.0):
    return Sample(d=d, t=d/100.0, speed=speed, throttle=throttle, brake=brake,
                  steering=steer, gear=6, rpm=11000)


def test_time_trial_disables_resource_and_race_strategy_but_keeps_driving_analysis():
    c=build_event_context(make_state(18)).to_dict()
    assert c['profile']=='time_trial'
    m=c['metrics']
    assert m['corner_analysis'] is True
    assert m['lap_comparison'] is True
    assert m['fuel_strategy'] is False
    assert m['ers_energy_strategy'] is False
    assert m['tyre_wear_strategy'] is False
    assert m['pit_strategy'] is False
    assert m['race_position_strategy'] is False


def test_race_enables_race_strategy_and_obeys_rules():
    c=build_event_context(make_state(15, parc=True, damage=0, safety=0, red=0)).to_dict()
    m=c['metrics']
    assert c['profile']=='race'
    assert m['fuel_strategy'] is True and m['ers_energy_strategy'] is True
    assert m['pit_strategy'] is True and m['race_position_strategy'] is True
    assert m['damage_strategy'] is False
    assert m['safety_car_strategy'] is False
    assert m['red_flag_strategy'] is False
    assert m['setup_change_advice'] is False


def test_micro_brake_tap_is_not_a_corner_section():
    r=MeasuredPerformanceRecorder()
    a=[sample(i*5.0) for i in range(20)]
    # 15 m, sub-strong tap, only 4 kph speed drop: should not become a corner.
    for i,(b,v) in {8:(0.25,200),9:(0.40,198),10:(0.20,196)}.items():
        a[i].brake=b; a[i].speed=v; a[i].throttle=0.2
    assert r._segments(a)==[]


def test_short_but_real_braking_event_is_retained():
    r=MeasuredPerformanceRecorder()
    a=[sample(i*5.0) for i in range(30)]
    for i,(b,v) in {8:(0.7,200),9:(0.8,192),10:(0.6,184)}.items():
        a[i].brake=b; a[i].speed=v; a[i].throttle=0.1
    a[11].throttle=1.0
    z=r._segments(a)
    assert len(z)==1
    assert z[0]['start_m']==40.0


def test_steering_reversal_survives_zero_crossing_deadband():
    r=MeasuredPerformanceRecorder()
    vals=[0.20,0.10,0.02,0.00,-0.02,-0.10,-0.25,-0.01,0.08,0.20]
    a=[sample(i*5.0,steer=v) for i,v in enumerate(vals)]
    assert r._steering_reversals(a)==2


def test_time_trial_comparison_omits_fuel_and_ers_deltas():
    cur={'lap':2,'lap_time_s':70.0,'fuel_used_observed':0.0,'ers_store_change_j':0.0,
         '_metric_applicability':{'fuel_strategy':False,'ers_energy_strategy':False},'_samples':{},'sections':[]}
    ref={'lap':1,'lap_time_s':71.0,'fuel_used_observed':1.2,'ers_store_change_j':-300000.0,
         '_metric_applicability':{'fuel_strategy':False,'ers_energy_strategy':False},'_samples':{},'sections':[]}
    c=MeasuredPerformanceRecorder.compare(cur,ref)
    assert 'fuel_used_observed_delta' not in c
    assert 'ers_store_change_j_delta' not in c
