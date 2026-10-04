import unittest
from src.voice_commands import VoiceIntent, parse_intent, handle_voice_request
from src.race_state.models import RaceState, CarState, Wheels

class NaturalRadioV088Tests(unittest.TestCase):
    def test_brake_short_forms(self):
        for phrase in ('Brake info','Brakes?','Brake status','Check brakes','How are the brakes?','break info'):
            self.assertEqual(parse_intent(phrase), VoiceIntent.BRAKE_STATUS, phrase)
        for phrase in ('Brake temp','Brake temps','Brake temperature','break temp'):
            self.assertEqual(parse_intent(phrase), VoiceIntent.BRAKE_TEMPERATURE, phrase)
        self.assertEqual(parse_intent('Brake damage'), VoiceIntent.BRAKE_DAMAGE)
        self.assertEqual(parse_intent('Brake bias'), VoiceIntent.BRAKE_BIAS)

    def test_short_forms_across_radio_domains(self):
        cases = {
            'Tyres?': VoiceIntent.TYRE_STATUS,
            'Tyre info': VoiceIntent.TYRE_STATUS,
            'Tyre wear': VoiceIntent.TYRE_WEAR,
            'Tyre pressure': VoiceIntent.TYRE_PRESSURE,
            'Fuel?': VoiceIntent.FUEL_STATUS,
            'Fuel info': VoiceIntent.FUEL_STATUS,
            'ERS?': VoiceIntent.ERS_STATUS,
            'Battery info': VoiceIntent.ERS_STATUS,
            'Position?': VoiceIntent.POSITION,
            'Gap front': VoiceIntent.GAP_AHEAD,
            'Gap rear': VoiceIntent.GAP_BEHIND,
            'Lap info': VoiceIntent.LAP_TIME,
            'Best lap': VoiceIntent.BEST_LAP,
            'Laps left': VoiceIntent.LAPS_REMAINING,
            'Damage info': VoiceIntent.DAMAGE,
            'Penalties?': VoiceIntent.PENALTIES,
            'Weather info': VoiceIntent.WEATHER,
            'Pit info': VoiceIntent.PIT_STATUS,
            'Race control': VoiceIntent.RACE_CONTROL,
            'Setup': VoiceIntent.SETUP,
            'Slip info': VoiceIntent.WHEEL_SLIP,
            'G info': VoiceIntent.G_FORCE,
            'Telemetry info': VoiceIntent.MATH_STATUS,
        }
        for phrase, intent in cases.items():
            self.assertEqual(parse_intent(phrase), intent, phrase)

    def test_generic_brake_answer_is_short_and_specific_requests_are_numeric(self):
        state=RaceState(player=CarState(index=0))
        state.player.telemetry.brakes_temperature_c=Wheels(800,805,700,705)
        state.player.damage.brakes_percent=Wheels(0,0,0,0)
        self.assertEqual(handle_voice_request('brake info', state).response, 'Brakes are good.')
        self.assertEqual(handle_voice_request('brake temp', state).response, 'Brake temperatures are good.')
        self.assertIn('front left 800 degrees', handle_voice_request('brake temp more detail', state).response)
        state.player.damage.brakes_percent=Wheels(0,12,0,0)
        self.assertEqual(handle_voice_request('brakes?', state).response, 'Brakes: front right damage 12 percent.')

    def test_unknown_noise_stays_unknown(self):
        self.assertEqual(parse_intent('with their updates'), VoiceIntent.UNKNOWN)
        self.assertEqual(parse_intent('random radio noise'), VoiceIntent.UNKNOWN)

if __name__ == '__main__': unittest.main()
