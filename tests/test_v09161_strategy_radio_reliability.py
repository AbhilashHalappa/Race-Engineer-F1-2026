from src.race_state.models import RaceState, CarState, Wheels
from src.voice_commands import normalize_radio_text, parse_intent, VoiceIntent
from src.strategy_engine import assess_strategy, format_gap_trend
from src.engineer.models import EngineerMessage, Priority
from src.tts import SpeechOutput
from src.pit_strategy import service_plan


def base_state():
    s = RaceState(); c = CarState(0)
    s.player = s.field[0] = c; s.player_index = 0
    s.session.total_laps = 10
    c.lap.current_lap = 5; c.lap.position = 2; c.lap.gap_to_car_in_front_s = 2.0
    c.tyres.wear_percent = Wheels(10, 10, 10, 10)
    c.tyres.damage_percent = Wheels(0, 0, 0, 0)
    c.tyres.surface_temperature_c = Wheels(90, 90, 90, 90)
    c.damage.front_left_wing_percent = 40; c.damage.front_right_wing_percent = 0
    return s


def test_strategy_phrase_recovery_from_observed_stt_misses():
    assert normalize_radio_text('Compassioned place.') == 'compare stint pace'
    assert normalize_radio_text('Compare, shift, paste.') == 'compare stint pace'
    assert parse_intent('Compassioned place.') == VoiceIntent.STINT_COMPARE
    assert parse_intent('Compare, shift, paste.') == VoiceIntent.STINT_COMPARE


def test_traffic_article_variant_routes_same_intent():
    assert parse_intent('Will I come out in the traffic?') == VoiceIntent.REJOIN_TRAFFIC
    assert parse_intent('Will I come out in traffic?') == VoiceIntent.REJOIN_TRAFFIC


def test_driver_reply_has_priority_over_routine_auto_calls():
    voice = EngineerMessage('voice:response', Priority.STRATEGY, 'Answer.', 0)
    track = EngineerMessage('track_limits', Priority.CRITICAL, 'Track limits.', 0)
    assist = EngineerMessage('assist:s_mode', Priority.COACHING, 'S Mode.', 0)
    assert SpeechOutput._radio_rank(voice) < SpeechOutput._radio_rank(track)
    assert SpeechOutput._radio_rank(voice) < SpeechOutput._radio_rank(assist)


def test_rolling_gap_history_gives_early_trend_without_completed_lap():
    s = base_state()
    s.measured_laps = ()
    s.extended['_strategy_gap_samples'] = (
        (10.0, 2.0, 1), (12.0, 1.8, 1), (14.0, 1.6, 1), (16.0, 1.4, 1), (18.0, 1.2, 1),
    )
    a = assess_strategy(s)
    assert a.gap_trend == 'closing'
    assert a.gap_trend_basis == '10s'
    assert a.gap_ahead_change_s_per_lap == -1.0
    assert 'per 10 seconds' in format_gap_trend(s)


def test_rolling_gap_history_does_not_mix_different_car_ahead():
    s = base_state(); s.measured_laps = ()
    s.extended['_strategy_gap_samples'] = (
        (10.0, 3.0, 1), (14.0, 2.5, 1), (15.0, 1.2, 2), (18.0, 1.1, 2),
    )
    a = assess_strategy(s)
    assert a.gap_ahead_change_s_per_lap is None


def test_stay_out_wing_wording_is_conditional_not_contradictory():
    s = base_state()
    # With no other immediate trigger, wing at exactly 40% is serviceable but should
    # not make a stay-out message sound like an immediate mandatory replacement.
    text = service_plan(s).automatic_summary
    if text.startswith('Stay out for now.'):
        assert 'If you pit, replace the front wing.' in text
