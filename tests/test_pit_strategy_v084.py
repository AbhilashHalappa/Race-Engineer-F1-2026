import unittest
from src.voice_commands import parse_intent, VoiceIntent
from src.pit_strategy import assess_pit
from src.race_state.models import RaceState, CarState, Wheels

class TestPitV084(unittest.TestCase):
    def test_natural_pit_variants_never_unknown(self):
        phrases=["can we box this lap", "is it time to pit", "do i need to pit", "what about a pit stop",
                 "stay out or box", "when should we pit", "pit window", "should we stay out or pit", "box", "come in this lap", "make a stop now", "stop this lap"]
        for p in phrases:
            self.assertEqual(parse_intent(p), VoiceIntent.PIT_RECOMMENDATION, p)
    def test_status_stays_status(self):
        self.assertEqual(parse_intent("what is my pit status"), VoiceIntent.PIT_STATUS)
    def test_multifactor_assessment(self):
        s=RaceState(); c=CarState(index=0); s.player=c
        s.session.total_laps=50; c.lap.current_lap=20
        c.tyres.wear_percent=Wheels(50,50,50,50)
        c.tyres.damage_percent=Wheels(40,10,10,10)
        c.tyres.surface_temperature_c=Wheels(116,105,103,104)
        c.tyres.age_laps=22
        c.fuel.remaining_laps=25
        a=assess_pit(s)
        self.assertIn("tyre wear", a.factors_checked)
        self.assertIn("tyre damage", a.factors_checked)
        self.assertIn("tyre temperature", a.factors_checked)
        self.assertIn("fuel", a.factors_checked)
        self.assertTrue(any("damage" in r for r in a.reasons))
        self.assertTrue(any("temperature" in r for r in a.reasons))
        self.assertTrue(any("fuel" in r for r in a.reasons))
