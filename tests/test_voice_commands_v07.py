import unittest
from src.voice_commands import VoiceIntent, parse_intent, handle_voice_request
from src.race_state.models import RaceState, CarState, Wheels

class VoiceCommandsV07Tests(unittest.TestCase):
    def test_real_live_phrases(self):
        self.assertEqual(parse_intent("What about my tires?"), VoiceIntent.TYRE_STATUS)
        self.assertEqual(parse_intent("Can I box now?"), VoiceIntent.PIT_RECOMMENDATION)
        self.assertEqual(parse_intent("Gap ahead."), VoiceIntent.GAP_AHEAD)
        self.assertEqual(parse_intent("Gap behind."), VoiceIntent.GAP_BEHIND)

    def test_unknown_does_not_guess(self):
        self.assertEqual(parse_intent("with their updates"), VoiceIntent.UNKNOWN)

    def test_tyre_status_is_short_when_normal(self):
        state = RaceState(player=CarState(index=0))
        state.player.tyres.wear_percent = Wheels(12, 13, 14, 15)
        state.player.tyres.surface_temperature_c = Wheels(90, 91, 92, 93)
        result = handle_voice_request("how are my tyres", state)
        self.assertEqual(result.intent, VoiceIntent.TYRE_STATUS)
        self.assertEqual(result.response, "Tyres are good.")

    def test_tyre_status_only_calls_out_abnormal_wheel(self):
        state = RaceState(player=CarState(index=0))
        state.player.tyres.wear_percent = Wheels(12, 31, 14, 15)
        state.player.tyres.surface_temperature_c = Wheels(90, 91, 92, 93)
        result = handle_voice_request("what about my tires", state)
        self.assertEqual(result.response, "Tyres: front right wear 31 percent.")

    def test_explicit_tyre_detail_requests_return_numbers(self):
        state = RaceState(player=CarState(index=0))
        state.player.tyres.wear_percent = Wheels(12, 13, 14, 15)
        state.player.tyres.surface_temperature_c = Wheels(90, 91, 92, 93)
        self.assertEqual(parse_intent("tyre wear"), VoiceIntent.TYRE_WEAR)
        self.assertEqual(handle_voice_request("tyre wear", state).response, "Tyre wear around 13.5 percent. All four healthy.")
        self.assertEqual(parse_intent("tyre temperatures"), VoiceIntent.TYRE_TEMPERATURE)
        self.assertEqual(handle_voice_request("tyre temperatures", state).response, "Tyre temperatures are good.")
        self.assertEqual(parse_intent("tyre temperatures more detail"), VoiceIntent.TYRE_TEMPERATURE_DETAIL)
        self.assertIn("front left 90 degrees", handle_voice_request("tyre temperatures more detail", state).response)

    def test_gaps_are_direct_or_unavailable(self):
        state = RaceState(player=CarState(index=0))
        state.player.lap.gap_to_car_in_front_s = 1.234
        state.gap_behind_s = 2.345
        self.assertEqual(handle_voice_request("gap ahead", state).response, "Gap ahead 1.23 seconds.")
        self.assertEqual(handle_voice_request("gap behind", state).response, "Gap behind 2.35 seconds.")
        state.player.lap.gap_to_car_in_front_s = None
        self.assertEqual(handle_voice_request("gap ahead", state).response, "Gap ahead unavailable.")

    def test_box_now_does_not_invent_strategy(self):
        state = RaceState(player=CarState(index=0))
        result = handle_voice_request("should I box now", state)
        self.assertEqual(result.intent, VoiceIntent.PIT_RECOMMENDATION)
        self.assertIn("pit call", result.response.lower())

    def test_no_live_car_data_is_explicit(self):
        state = RaceState()
        self.assertEqual(handle_voice_request("what is my fuel", state).response, "Live car data is unavailable.")

    def test_generic_tyre_temperature_word_stays_short(self):
        state = RaceState(player=CarState(index=0))
        state.player.tyres.wear_percent = Wheels(12, 13, 14, 15)
        state.player.tyres.surface_temperature_c = Wheels(90, 91, 92, 93)
        self.assertEqual(parse_intent("how are my tyre temperatures"), VoiceIntent.TYRE_TEMPERATURE)
        self.assertEqual(handle_voice_request("how are my tyre temperatures", state).response, "Tyre temperatures are good.")
        self.assertEqual(parse_intent("give me all tyre temperatures"), VoiceIntent.TYRE_TEMPERATURE)

    def test_only_reasoning_questions_route_to_llm_intent(self):
        self.assertEqual(parse_intent("why am I losing pace"), VoiceIntent.COMPLEX_REASONING)
        self.assertEqual(parse_intent("should I box now"), VoiceIntent.PIT_RECOMMENDATION)
        self.assertEqual(parse_intent("what is my fuel"), VoiceIntent.FUEL_STATUS)
        self.assertEqual(parse_intent("random radio noise"), VoiceIntent.UNKNOWN)

if __name__ == '__main__': unittest.main()
