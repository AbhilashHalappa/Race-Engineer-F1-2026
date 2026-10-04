from types import SimpleNamespace

from src.voice_commands import VoiceIntent, parse_intent, handle_voice_request, normalize_radio_text
from src.race_state.models import RaceState, CarState, Wheels
from src.radio_transcript import RadioTranscriptStore
from src.engineer.models import EngineerMessage, Priority


def ev(name):
    return SimpleNamespace(name=name)


def populated_state():
    s = RaceState(player_index=0, player=CarState(index=0))
    c = s.player
    s.field[0] = c
    s.session.total_laps = 10
    s.session.time_left_s = 245
    s.session.track_temperature_c = 31
    s.session.air_temperature_c = 22
    s.session.pit_speed_limit_kph = 80
    c.lap.current_lap = 4
    c.lap.sector = 1
    c.lap.grid_position = 7
    c.lap.pit_stops = 1
    c.lap.gap_to_leader_s = 8.432
    c.lap.corner_cutting_warnings = 2
    c.lap.warnings = 3
    c.telemetry.engine_temperature_c = 103
    c.telemetry.speed_kph = 287
    c.telemetry.rpm = 11980
    c.telemetry.gear = 7
    c.damage.engine_percent = 15
    c.damage.gearbox_percent = 10
    c.tyres.visual_compound = ev('Medium')
    c.tyres.actual_compound = ev('C3')
    c.tyres.age_laps = 3
    c.tyres.fitted_set_index = 5
    c.fuel.mix = ev('Standard')
    c.aero.drs_allowed = True
    c.aero.active_aero_available = True
    c.aero.active_aero_mode = ev('Corner mode')
    c.aero.overtake_available = True
    c.energy.harvested_mguk_j = 200000
    c.energy.harvested_mguh_j = 100000
    ahead = CarState(index=1); ahead.identity.name='Norris'; s.field[1]=ahead; s.ahead_index=1
    behind = CarState(index=2); behind.identity.name='Leclerc'; s.field[2]=behind; s.behind_index=2; s.gap_behind_s=1.92
    c.lap.gap_to_car_in_front_s=1.23
    return s


def test_stt_repetition_is_collapsed():
    text = ' '.join(['Brake temperature'] * 40)
    assert normalize_radio_text(text) == 'brake temperature'
    assert parse_intent(text) == VoiceIntent.BRAKE_TEMPERATURE


def test_observed_near_miss_commands_are_conservatively_recovered():
    assert normalize_radio_text('lap behind.') == 'gap behind'
    assert parse_intent('lap behind.') == VoiceIntent.GAP_BEHIND
    assert normalize_radio_text('style should I use?') == 'which tyres should i use'
    assert parse_intent('style should I use?') == VoiceIntent.TYRE_SELECTION


def test_garbage_is_not_forced_into_a_command():
    assert parse_intent("They're here to be.") == VoiceIntent.UNKNOWN
    assert parse_intent('Bedtime, ciao!') == VoiceIntent.UNKNOWN


def test_real_world_race_radio_command_families():
    expected = {
        'engine': VoiceIntent.ENGINE_STATUS,
        'engine temperature': VoiceIntent.ENGINE_TEMPERATURE,
        'engine wear': VoiceIntent.ENGINE_WEAR,
        'gearbox status': VoiceIntent.GEARBOX_STATUS,
        'current lap': VoiceIntent.CURRENT_LAP,
        'lap remaining': VoiceIntent.LAPS_REMAINING,
        'lap completed': VoiceIntent.LAPS_COMPLETED,
        'current sector': VoiceIntent.CURRENT_SECTOR,
        'session time remaining': VoiceIntent.SESSION_TIME,
        'gap to leader': VoiceIntent.GAP_LEADER,
        'driver ahead': VoiceIntent.DRIVER_AHEAD,
        'driver behind': VoiceIntent.DRIVER_BEHIND,
        'tyre compound': VoiceIntent.TYRE_COMPOUND,
        'tyre age': VoiceIntent.TYRE_AGE,
        'tyre set': VoiceIntent.TYRE_SET,
        'DRS status': VoiceIntent.DRS_STATUS,
        'S Mode status': VoiceIntent.S_MODE_STATUS,
        'overtake status': VoiceIntent.OVERTAKE_STATUS,
        'pit speed limit': VoiceIntent.PIT_SPEED_LIMIT,
        'pit stops': VoiceIntent.PIT_STOPS,
        'track temperature': VoiceIntent.TRACK_TEMPERATURE,
        'air temperature': VoiceIntent.AIR_TEMPERATURE,
        'rain chance': VoiceIntent.RAIN_CHANCE,
        'speed': VoiceIntent.SPEED,
        'RPM': VoiceIntent.RPM,
        'gear': VoiceIntent.GEAR,
        'fuel mix': VoiceIntent.FUEL_MIX,
        'ERS harvest': VoiceIntent.ERS_HARVEST,
        'grid position': VoiceIntent.GRID_POSITION,
        'track limits': VoiceIntent.TRACK_LIMITS,
    }
    for phrase, intent in expected.items():
        assert parse_intent(phrase) == intent, phrase


def test_new_deterministic_answers_use_live_telemetry():
    s = populated_state()
    assert handle_voice_request('engine', s).response == 'Engine: temperature 103 degrees, wear 15 percent.'
    assert handle_voice_request('gearbox', s).response == 'Gearbox wear 10 percent.'
    assert handle_voice_request('current lap', s).response == 'Lap 4 of 10.'
    assert handle_voice_request('lap completed', s).response == '3 laps completed.'
    assert handle_voice_request('driver ahead', s).response == 'NORRIS ahead, 1.23 seconds.'
    assert handle_voice_request('driver behind', s).response == 'LECLERC behind, 1.92 seconds.'
    assert handle_voice_request('tyre compound', s).response == 'Tyres Medium, actual compound C3.'
    assert handle_voice_request('pit speed limit', s).response == 'Pit speed limit 80 kilometres per hour.'
    assert handle_voice_request('speed', s).response == '287 kilometres per hour.'
    assert handle_voice_request('track limits', s).response == 'Track limits: 2 corner-cutting warnings, 3 total warnings.'


def test_transcript_visible_time_never_runs_backwards_and_keeps_interpretation():
    store = RadioTranscriptStore()
    a = store.add_driver('lap behind.', session_time_s=10.0, interpreted_text='gap behind')
    b = store.add_engineer(EngineerMessage(key='old:event', priority=Priority.INFORMATION, text='Older queued event.', created_at=0.0, session_time_s=8.0))
    assert a.interpreted_text == 'gap behind'
    assert b.session_time_s == 10.0
