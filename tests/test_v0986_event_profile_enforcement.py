from src.event_context import build_event_context
from src.engineer.engine import AutomaticEngineer
from src.llm_engineer import build_reasoning_context
from src.race_state.models import RaceState, CarState, Wheels
from src.telemetry.enums import EnumValue
from src.voice_commands import handle_voice_request


def ev(raw, name):
    return EnumValue(raw, name)


def state_for(session_type=18, *, parc=True, damage=0, regs=True):
    s = RaceState(player_index=0)
    s.session.uid = 99
    names = {18: 'Time Trial', 5: 'Qualifying 1', 15: 'Race'}
    s.session.session_type = ev(session_type, names.get(session_type, 'Session'))
    s.session.game_mode = 5 if session_type == 18 else 7
    s.session.rule_set = 2 if session_type == 18 else 0
    s.session.parc_ferme_rules = parc
    s.session.car_damage = damage
    s.session.car_damage_rate = 0 if damage == 0 else 1
    s.session.safety_car_setting = 0 if session_type == 18 else 2
    s.session.red_flags_setting = 0 if session_type == 18 else 1
    s.player = CarState(0)
    s.field[0] = s.player
    c = s.player
    c.aero.regulations_2026 = regs
    c.lap.current_lap = 1
    c.lap.lap_valid = True
    c.lap.warnings = 0
    c.lap.corner_cutting_warnings = 0
    c.fuel.remaining_laps = 1.2
    c.fuel.remaining_mass = 10.0
    c.energy.store_j = 4_000_000.0
    c.tyres.wear_percent = Wheels(0, 0, 0, 0)
    c.tyres.surface_temperature_c = Wheels(90, 90, 90, 90)
    c.tyres.blisters_percent = Wheels(0, 0, 0, 0)
    c.tyres.damage_percent = Wheels(0, 0, 0, 0)
    c.telemetry.brakes_temperature_c = Wheels(700, 700, 700, 700)
    c.telemetry.engine_temperature_c = 100
    return s


def test_tt_ignores_parc_ferme_for_setup_advice():
    c = build_event_context(state_for(18, parc=True)).to_dict()
    assert c['profile'] == 'time_trial'
    assert c['parc_ferme_rules'] is True
    assert c['metrics']['setup_change_advice'] is True
    assert c['metrics']['fuel_strategy'] is False
    assert c['metrics']['ers_energy_strategy'] is False
    assert c['metrics']['pit_strategy'] is False
    assert c['metrics']['pit_lane_guidance'] is False


def test_known_session_does_not_assume_2026_systems_when_regulation_flag_unknown():
    c = build_event_context(state_for(15, damage=2, regs=None)).to_dict()['metrics']
    assert c['active_aero_analysis'] is False
    assert c['overtake_analysis'] is False
    assert c['legacy_drs_analysis'] is False


def test_qualifying_has_traffic_gaps_but_not_race_position_strategy():
    c = build_event_context(state_for(5, parc=True, damage=2)).to_dict()['metrics']
    assert c['traffic_gap_analysis'] is True
    assert c['race_position_strategy'] is False
    assert c['pit_strategy'] is False
    assert c['pit_lane_guidance'] is True
    assert c['setup_change_advice'] is False


def test_tt_automatic_engineer_suppresses_resource_and_damage_strategy_calls():
    s = state_for(18, parc=True, damage=0)
    e = AutomaticEngineer(ers_assist=False, drs_s_mode_assist=False)
    assert e.evaluate(s, 0.0) == ()
    s.player.fuel.remaining_laps = 0.1
    s.player.tyres.wear_percent = Wheels(95, 95, 95, 95)
    s.player.tyres.blisters_percent = Wheels(80, 0, 0, 0)
    s.player.damage.front_right_wing_percent = 90
    s.player.lap.lap_valid = False
    messages = e.evaluate(s, 1.0)
    assert [m.text for m in messages] == ['Current lap invalidated.']


def test_tt_voice_reports_resource_strategy_as_not_applicable_not_zero_usage():
    s = state_for(18)
    assert 'not applicable in time trial' in handle_voice_request('fuel used', s).response.lower()
    ers = handle_voice_request('ers status', s).response.lower()
    assert 'not applicable in time trial' in ers
    assert 'overtake and active aero' in ers


def test_tt_reasoning_context_excludes_race_resource_strategy_inputs():
    s = state_for(18)
    d = build_reasoning_context(s)
    assert d['event_context']['profile'] == 'time_trial'
    assert 'fuel' not in d
    assert 'ers' not in d
    assert 'damage' not in d
    assert d['pit_strategy']['recommendation_hint'] == 'not_applicable'
    assert d['aero']['overtake_available'] is None or d['event_context']['metrics']['overtake_analysis'] is True


def test_race_profile_keeps_resource_and_pit_strategy_when_rules_allow():
    c = build_event_context(state_for(15, parc=True, damage=2, regs=True)).to_dict()['metrics']
    assert c['fuel_strategy'] is True
    assert c['ers_energy_strategy'] is True
    assert c['tyre_wear_strategy'] is True
    assert c['race_position_strategy'] is True
    assert c['traffic_gap_analysis'] is True
    assert c['pit_strategy'] is True
    assert c['damage_strategy'] is True
    assert c['active_aero_analysis'] is True
    assert c['overtake_analysis'] is True
