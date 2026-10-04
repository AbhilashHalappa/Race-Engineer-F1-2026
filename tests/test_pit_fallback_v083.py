import unittest
from src.pit_strategy import format_pit_fallback
from src.race_state.models import RaceState, CarState

class PitFallbackTests(unittest.TestCase):
    def test_missing_data_is_explicit(self):
        s=RaceState(); s.player=CarState(index=0)
        msg=format_pit_fallback(s).lower()
        self.assertIn("can't make a reliable pit call", msg)
    def test_high_wear_boxes_soon(self):
        from src.race_state.models import Wheels
        s=RaceState(); s.player=CarState(index=0); s.session.total_laps=50; s.player.lap.current_lap=20
        s.player.tyres.wear_percent=Wheels(82,70,70,70)
        self.assertTrue(format_pit_fallback(s).startswith("Box soon."))
    def test_normal_wear_stays_out(self):
        from src.race_state.models import Wheels
        s=RaceState(); s.player=CarState(index=0); s.session.total_laps=50; s.player.lap.current_lap=20
        s.player.tyres.wear_percent=Wheels(20,21,19,20)
        self.assertTrue(format_pit_fallback(s).startswith("Stay out for now."))
if __name__=='__main__': unittest.main()
