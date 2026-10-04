from src.pit_strategy import assess_pit
from src.strategy_engine import assess_strategy
from src.engineer.engine import AutomaticEngineer
from src.race_state.models import RaceState, CarState, Wheels, MeasuredLapFact, RaceEvent
from src.telemetry.enums import EnumValue
from src.voice_commands import is_likely_stt_hallucination


def ev(name): return EnumValue(0, name)

def state(lap=2):
    s=RaceState(); s.session.uid=11; s.session.session_type=ev('Race'); s.session.total_laps=20
    s.session.weather=ev('Clear'); s.session.safety_car=ev('None')
    s.player_index=0; s.player=CarState(0); s.field[0]=s.player
    c=s.player; c.lap.current_lap=lap; c.lap.lap_valid=True
    c.tyres.wear_percent=Wheels(2.1,2.0,1.8,1.9); c.tyres.damage_percent=Wheels(0,0,0,0)
    c.tyres.surface_temperature_c=Wheels(90,90,90,90); c.tyres.fitted_set_index=1; c.tyres.age_laps=1
    c.tyres.visual_compound=ev('Medium'); c.damage.front_left_wing_percent=0; c.damage.front_right_wing_percent=0
    return s


def test_real_race_shape_does_not_box_from_standing_start_degradation():
    s=state(2)
    # Reproduces the bad shape from the supplied recording: one completed start lap
    # with a large apparent wear delta must not extrapolate to 100%+ at the finish.
    s.measured_laps=(MeasuredLapFact(1,93.885, tyre_wear_delta=Wheels(6.5,6.2,6.0,6.1), fitted_tyre_set_index=1),)
    a=assess_pit(s)
    assert a.recommendation_hint == 'stay_out'
    assert not any('projects' in r for r in a.reasons)
    assert assess_strategy(s).tyre_wear_rate_pct_per_lap is None


def test_projection_needs_two_clean_same_stint_laps_and_rejects_compromised():
    s=state(6); s.player.tyres.wear_percent=Wheels(30,29,28,28); s.player.tyres.age_laps=5
    s.measured_laps=(
        MeasuredLapFact(2,90,tyre_wear_delta=Wheels(3,3,3,3),fitted_tyre_set_index=1,pit_lap=True),
        MeasuredLapFact(3,90,tyre_wear_delta=Wheels(3,3,3,3),fitted_tyre_set_index=1,race_control_compromised=True),
        MeasuredLapFact(4,90,tyre_wear_delta=Wheels(3,3,3,3),fitted_tyre_set_index=1),
    )
    assert assess_strategy(s).tyre_wear_rate_pct_per_lap is None
    s.measured_laps += (MeasuredLapFact(5,90,tyre_wear_delta=Wheels(3,3,3,3),fitted_tyre_set_index=1),)
    assert assess_strategy(s).tyre_wear_rate_pct_per_lap == 3.0


def test_pit_call_semantic_repeat_is_suppressed_for_two_minutes():
    s=state(5); s.player.damage.front_left_wing_percent=90
    e=AutomaticEngineer(); e._event_context=__import__('src.event_context',fromlist=['build_event_context']).build_event_context(s)
    e._pit_strategy_rule(s,100.0); first=[m.text for m in e.drain()]
    assert any('Box this lap' in x for x in first)
    s.player.damage.front_left_wing_percent=91
    e._pit_strategy_rule(s,140.0); assert not e.drain()
    e._pit_strategy_rule(s,221.0); assert e.drain()


def test_position_events_suppressed_in_pit_and_same_driver_flap_debounced():
    s=state(6); e=AutomaticEngineer(position_updates=True); e.evaluate(s,0)
    s.player.lap.pit_lane_timer_active=True
    s.events=(RaceEvent('OVTK','Overtake',{'overtakingVehicleIdx':1,'beingOvertakenVehicleIdx':0},10.0,10.0),)
    assert not any('passed you' in m.text for m in e.evaluate(s,10))
    s.player.lap.pit_lane_timer_active=False
    s.events=s.events+(RaceEvent('OVTK','Overtake',{'overtakingVehicleIdx':1,'beingOvertakenVehicleIdx':0},20.0,20.0),)
    assert any('passed you' in m.text for m in e.evaluate(s,20))
    s.events=s.events+(RaceEvent('OVTK','Overtake',{'overtakingVehicleIdx':0,'beingOvertakenVehicleIdx':1},22.0,22.0),)
    assert not any('Overtake complete' in m.text for m in e.evaluate(s,22))


def test_social_ptt_fillers_are_silent_noise():
    for text in ('Thank you very much', 'Bye-bye', 'Can I ask you a question?'):
        assert is_likely_stt_hallucination(text)
