import unittest
from src.race_state.models import RaceState, CarState, Wheels, MeasuredLapFact
from src.deterministic_facts import all_facts
from src.voice_commands import parse_intent, answer_intent, VoiceIntent

class DeterministicFactsV089Tests(unittest.TestCase):
    def state(self):
        s=RaceState(); c=CarState(0); s.player=c; s.player_index=0; s.field={0:c}
        c.lap.position=4; c.lap.current_lap=8; s.session.total_laps=20; s.session.track_length_m=5000; c.lap.lap_distance_m=2500
        c.tyres.wear_percent=Wheels(10,12,8,9); c.telemetry.brakes_temperature_c=Wheels(700,710,650,660)
        c.fuel.remaining_laps=7.5
        s.measured_laps=(MeasuredLapFact(6,90.0,1.4,start_position=5,end_position=4,position_change=1),MeasuredLapFact(7,90.5,1.5,start_position=4,end_position=4,position_change=0))
        return s
    def test_all_facts_has_current_math_and_history(self):
        f=all_facts(self.state())
        self.assertAlmostEqual(f['math']['race_progress_percent'],37.5)
        self.assertEqual(f['car']['four_corner_stats']['tyre_wear']['max_wheel'],'FR')
        self.assertEqual(f['historical']['completed_lap_count'],2)
        self.assertAlmostEqual(f['historical']['last_lap_vs_previous_s'],.5)
        self.assertAlmostEqual(f['historical']['last_fuel_vs_previous'],.1)
    def test_natural_historical_radio(self):
        s=self.state()
        self.assertEqual(parse_intent('lap delta'),VoiceIntent.LAP_COMPARISON)
        self.assertIn('0.500 seconds slower',answer_intent(VoiceIntent.LAP_COMPARISON,s))
        self.assertEqual(parse_intent('fuel used last lap'),VoiceIntent.FUEL_USED)
        self.assertIn('1.500',answer_intent(VoiceIntent.FUEL_USED,s))
        self.assertEqual(parse_intent('positions gained'),VoiceIntent.POSITION_CHANGE)
        self.assertIn('No position change',answer_intent(VoiceIntent.POSITION_CHANGE,s))
if __name__=='__main__': unittest.main()
