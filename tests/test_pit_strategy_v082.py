import unittest
from src.pit_strategy import assess_pit
from src.voice_commands import handle_voice_request, VoiceIntent
from src.llm_engineer import build_reasoning_context
from src.race_state.models import RaceState, CarState, Wheels

class PitStrategyV082Tests(unittest.TestCase):
    def state(self, wear=(20,21,22,23)):
        s=RaceState(player=CarState(index=0)); s.session.total_laps=50; s.player.lap.current_lap=20
        s.player.tyres.wear_percent=Wheels(*wear); s.player.tyres.age_laps=12
        return s
    def test_box_question_routes_to_strategy_reasoning(self):
        r=handle_voice_request('Can I box now?', self.state())
        self.assertEqual(r.intent, VoiceIntent.PIT_RECOMMENDATION)
        self.assertIn(r.response.split('.')[0], ('Stay out for now','Box this lap','Box soon','Consider boxing','No reliable pit call yet'))
    def test_normal_wear_is_stay_out_hint(self):
        a=assess_pit(self.state())
        self.assertTrue(a.data_sufficient); self.assertEqual(a.recommendation_hint,'stay_out')
        self.assertEqual(a.laps_remaining,30)
    def test_high_wear_creates_box_signal(self):
        a=assess_pit(self.state((81,70,68,69)))
        self.assertEqual(a.recommendation_hint,'box_soon'); self.assertEqual(a.urgency,'high')
    def test_context_contains_pit_strategy(self):
        d=build_reasoning_context(self.state())
        self.assertIn('pit_strategy',d); self.assertEqual(d['pit_strategy']['laps_remaining'],30)
    def test_missing_core_data_does_not_guess(self):
        s=RaceState(player=CarState(index=0)); a=assess_pit(s)
        self.assertFalse(a.data_sufficient); self.assertEqual(a.recommendation_hint,'insufficient_data')

if __name__=='__main__': unittest.main()
