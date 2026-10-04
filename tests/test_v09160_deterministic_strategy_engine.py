from src.race_state.models import RaceState, CarState, Wheels, TyreSet, MeasuredLapFact
from src.telemetry.enums import EnumValue
from src.strategy_engine import assess_strategy, format_tyre_life, format_fuel_to_finish
from src.pit_strategy import choose_tyre
from src.voice_commands import parse_intent, answer_intent, VoiceIntent


def ev(name): return EnumValue(0, name)


def state():
    s=RaceState(); c=CarState(0); s.player=s.field[0]=c; s.player_index=0
    s.session.total_laps=20; s.session.weather=ev('Clear'); s.session.safety_car=ev('None')
    c.lap.current_lap=10; c.lap.position=4; c.lap.gap_to_car_in_front_s=2.0
    c.fuel.remaining_laps=0.8
    c.tyres.fitted_set_index=3; c.tyres.visual_compound=ev('Medium')
    c.tyres.wear_percent=Wheels(40,39,38,38)
    c.tyres.damage_percent=Wheels(0,0,0,0); c.tyres.surface_temperature_c=Wheels(90,90,90,90)
    c.damage.front_left_wing_percent=0; c.damage.front_right_wing_percent=0
    c.tyres.sets=(
        TyreSet(4,ev('Soft'),ev('Soft'),0,True,ev('Race'),0,6,-.2,False),
        TyreSet(5,ev('Hard'),ev('Hard'),4,True,ev('Race'),0,18,.1,False),
    )
    s.measured_laps=(
        MeasuredLapFact(7,90.0,1.0,Wheels(2,2,2,2),4,4,0,3.0,2.7,-.3, fitted_tyre_set_index=3),
        MeasuredLapFact(8,89.8,1.0,Wheels(2.2,2.0,2.0,2.0),4,4,0,2.7,2.4,-.3, fitted_tyre_set_index=3),
        MeasuredLapFact(9,89.7,1.0,Wheels(1.8,2.0,2.0,2.0),4,4,0,2.4,2.0,-.4, fitted_tyre_set_index=3),
    )
    return s


def test_strategy_projects_measured_tyre_life_only_from_completed_laps():
    a=assess_strategy(state())
    assert a.tyre_wear_rate_pct_per_lap == 2.0
    assert a.projected_finish_wear_percent == 60.0
    assert a.tyres_can_finish is True
    assert 'should make the finish' in format_tyre_life(state()).lower()


def test_fuel_margin_uses_game_remaining_laps_margin():
    assert format_fuel_to_finish(state()) == 'Fuel margin 0.8 laps.'


def test_gap_trend_is_measured_from_completed_laps():
    a=assess_strategy(state())
    assert a.gap_trend == 'closing'
    assert a.gap_ahead_change_s_per_lap == -0.3


def test_tyre_choice_prefers_game_usable_life_that_covers_distance():
    x=choose_tyre(state())
    assert x.set_index == 5
    assert 'covers the remaining distance' in x.reason


def test_specific_strategy_radio_intents_are_deterministic():
    pairs={
        'can i make these tyres last': VoiceIntent.TYRE_LIFE,
        'how much fuel margin do i have': VoiceIntent.FUEL_TO_FINISH,
        'am i catching the car ahead': VoiceIntent.GAP_TREND,
        'will i come out in traffic': VoiceIntent.REJOIN_TRAFFIC,
        'can i undercut the car ahead': VoiceIntent.UNDERCUT,
        'strategy update': VoiceIntent.STRATEGY_STATUS,
    }
    s=state()
    for text,intent in pairs.items():
        assert parse_intent(text) == intent
        assert answer_intent(intent,s)


def test_rejoin_and_undercut_refuse_to_invent_pit_loss():
    s=state()
    assert 'pit-loss' in answer_intent(VoiceIntent.REJOIN_TRAFFIC,s)
    assert 'pit-loss' in answer_intent(VoiceIntent.UNDERCUT,s)


def test_why_should_i_box_stays_in_deterministic_pit_engine():
    assert parse_intent('why should i box') == VoiceIntent.PIT_RECOMMENDATION


def test_measured_finish_wear_can_create_deterministic_pit_trigger():
    from src.pit_strategy import assess_pit
    s=state(); s.player.tyres.wear_percent=Wheels(72,70,70,70)
    a=assess_pit(s)
    assert a.recommendation_hint in {'box_now','box_soon'}
    assert any('projects' in r and 'finish' in r for r in a.reasons)


def test_can_i_make_it_to_end_routes_to_strategy_status():
    assert parse_intent('can i make it to the end') == VoiceIntent.STRATEGY_STATUS
