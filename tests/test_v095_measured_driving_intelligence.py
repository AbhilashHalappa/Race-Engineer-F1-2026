import unittest
from src.measured_performance import MeasuredPerformanceRecorder
from src.voice_commands import parse_intent, VoiceIntent

class V095MeasuredDrivingIntelligenceTests(unittest.TestCase):
    def test_reference_radio_intents(self):
        self.assertEqual(parse_intent('use this lap as reference'), VoiceIntent.REFERENCE_SET)
        self.assertEqual(parse_intent('compare with previous'), VoiceIntent.REFERENCE_PREVIOUS)
        self.assertEqual(parse_intent('use best lap'), VoiceIntent.REFERENCE_BEST)
    def test_issue_radio_intent(self):
        self.assertEqual(parse_intent('driving issues'), VoiceIntent.DRIVING_ISSUES)
    def test_extended_measured_deltas(self):
        base={'lap':1,'lap_time_s':90.0,'high_slip_distance_m':10,'throttle_brake_overlap_m':5,'coasting_distance_m':20,'steering_reversals':2,'sections':[], '_samples':{}}
        cur={'lap':2,'lap_time_s':91.0,'high_slip_distance_m':20,'throttle_brake_overlap_m':15,'coasting_distance_m':30,'steering_reversals':4,'sections':[], '_samples':{}}
        c=MeasuredPerformanceRecorder.compare(cur,base)
        self.assertEqual(c['high_slip_distance_m_delta'],10)
        self.assertEqual(c['throttle_brake_overlap_m_delta'],10)
        self.assertEqual(c['coasting_distance_m_delta'],10)
        self.assertEqual(c['steering_reversals_delta'],2)
    def test_section_comparison_is_measured_not_named_turn(self):
        b={'lap':1,'sections':[{'id':1,'start_m':100,'brake_start_speed_kph':250,'min_speed_kph':100,'full_throttle_m':220,'exit_speed_kph':150,'peak_brake':.8,'max_slip':.1}], '_samples':{}}
        a={'lap':2,'sections':[{'id':1,'start_m':110,'brake_start_speed_kph':245,'min_speed_kph':95,'full_throttle_m':240,'exit_speed_kph':145,'peak_brake':.9,'max_slip':.2}], '_samples':{}}
        c=MeasuredPerformanceRecorder.compare(a,b)['section_comparisons'][0]
        self.assertEqual(c['start_m_delta'],10)
        self.assertEqual(c['min_speed_kph_delta'],-5)
        self.assertEqual(c['full_throttle_m_delta'],20)
        self.assertNotIn('turn',c)
    def test_manual_reference_selection(self):
        r=MeasuredPerformanceRecorder(); r.completed=[{'lap':3},{'lap':4}]
        self.assertTrue(r.set_reference('manual',3)); self.assertEqual(r.manual_reference_lap,3)
        self.assertFalse(r.set_reference('manual',99))

if __name__=='__main__': unittest.main()
