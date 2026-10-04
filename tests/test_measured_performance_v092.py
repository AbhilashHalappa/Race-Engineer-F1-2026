import unittest
from types import SimpleNamespace as N
from src.measured_performance import MeasuredPerformanceRecorder, radio_summary
from src.voice_commands import parse_intent, VoiceIntent

def state():
    tele=N(speed_kph=200, throttle=1.0, brake=0.0, steering=0.0, gear=6, rpm=11000)
    lap=N(current_lap=1, lap_distance_m=0.0, current_lap_time_s=0.0, previous_lap_time_s=None, lap_valid=True)
    car=N(lap=lap, telemetry=tele, energy=N(store_j=3e6), fuel=N(remaining_mass=30.0))
    return N(player=car, player_index=0, extended={})

class PerformanceV092Tests(unittest.TestCase):
    def test_natural_performance_intents(self):
        self.assertEqual(parse_intent('where am I losing time'), VoiceIntent.PERFORMANCE_COMPARE)
        self.assertEqual(parse_intent('braking info'), VoiceIntent.BRAKING_COMPARE)
        self.assertEqual(parse_intent('traction compare'), VoiceIntent.TRACTION_COMPARE)

    def test_completed_lap_measured_comparison(self):
        s=state(); r=MeasuredPerformanceRecorder()
        for lap, offset in ((1,0.0),(2,0.2)):
            s.player.lap.current_lap=lap
            for i in range(30):
                s.player.lap.lap_distance_m=i*5.0
                s.player.lap.current_lap_time_s=i*.1+offset
                s.player.telemetry.brake=.8 if 8<=i<=12 else 0
                s.player.telemetry.throttle=1.0 if i>=15 else .5
                r.observe(s)
            s.player.lap.previous_lap_time_s=3.1+offset
        # trigger completion of lap 2
        s.player.lap.current_lap=3; s.player.lap.lap_distance_m=0; s.player.lap.current_lap_time_s=0; s.player.lap.previous_lap_time_s=3.3
        r.observe(s)
        p=s.extended['measured_performance']
        self.assertEqual(len(p['completed_laps']),2)
        self.assertAlmostEqual(p['latest_comparison']['finish_observed_delta_s'], .2, places=6)
        self.assertIn('slower', radio_summary(s))

    def test_no_prediction_without_two_laps(self):
        s=state(); r=MeasuredPerformanceRecorder(); r.observe(s)
        self.assertIn('Two sufficiently sampled', radio_summary(s))

if __name__=='__main__': unittest.main()
