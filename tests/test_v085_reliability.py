import unittest
from src.pit_strategy import assess_pit, format_pit_fallback
from src.race_state.models import RaceState, CarState, Wheels


def base_state():
    s=RaceState(); c=CarState(index=0); s.player=c
    s.session.total_laps=50; c.lap.current_lap=10
    c.tyres.wear_percent=Wheels(20,20,20,20)
    c.tyres.damage_percent=Wheels(0,0,0,0)
    c.tyres.surface_temperature_c=Wheels(95,95,95,95)
    c.tyres.age_laps=8
    return s,c

class V085ReliabilityTests(unittest.TestCase):
    def test_front_wing_damage_is_checked(self):
        s,c=base_state(); c.damage.front_left_wing_percent=45; c.damage.front_right_wing_percent=10
        a=assess_pit(s)
        self.assertIn('front wing damage', a.factors_checked)
        self.assertEqual(a.front_wing_damage_percent,45)
        self.assertIn(a.recommendation_hint, ('consider_box','box_soon'))
        self.assertTrue(any('front wing damage' in r for r in a.reasons))

    def test_heavy_front_wing_damage_forces_box(self):
        s,c=base_state(); c.damage.front_left_wing_percent=90; c.damage.front_right_wing_percent=20
        a=assess_pit(s)
        self.assertEqual(a.recommendation_hint,'box_now')
        self.assertIn('Box this lap', format_pit_fallback(s))

    def test_rear_wing_is_context_not_false_repair_claim(self):
        s,c=base_state(); c.damage.rear_wing_percent=70
        a=assess_pit(s)
        self.assertTrue(any('rear wing damage' in r for r in a.reasons))
        self.assertNotEqual(a.recommendation_hint,'box_now')
