import unittest
from src.engineer.engine import AutomaticEngineer
from src.race_state.models import RaceState, CarState, Wheels

class AutomaticSafetyV090Tests(unittest.TestCase):
    def state(self):
        s=RaceState(player_index=0); s.session.uid=1; s.player=CarState(0); s.field[0]=s.player
        c=s.player; c.lap.current_lap=1; c.lap.lap_valid=True; c.lap.warnings=0; c.lap.corner_cutting_warnings=0
        c.tyres.surface_temperature_c=Wheels(90,90,90,90); c.tyres.blisters_percent=Wheels(0,0,0,0)
        c.telemetry.brakes_temperature_c=Wheels(700,700,700,700); c.telemetry.engine_temperature_c=100
        return s
    def messages(self,e,s,t): return [m.text for m in e.evaluate(s,t)]
    def test_temperature_crossings_auto_warn(self):
        s=self.state(); e=AutomaticEngineer(); self.assertEqual(self.messages(e,s,0),[])
        s.player.tyres.surface_temperature_c=Wheels(116,90,90,90)
        self.assertTrue(any('Tyres hot.' in x and 'FL' in x for x in self.messages(e,s,1)))
        s.player.telemetry.brakes_temperature_c=Wheels(700,1201,700,700)
        self.assertTrue(any('Brakes hot.' in x and 'FR' in x for x in self.messages(e,s,2)))
        s.player.telemetry.engine_temperature_c=131
        self.assertTrue(any('Engine temperature warning' in x for x in self.messages(e,s,3)))
    def test_blisters_engine_component_warnings_and_invalid_lap(self):
        s=self.state(); e=AutomaticEngineer(); e.evaluate(s,0)
        s.player.tyres.blisters_percent=Wheels(0,51,0,0)
        self.assertTrue(any('blistering' in x for x in self.messages(e,s,1)))
        s.player.damage.engine_wear_percent={'ICE':76,'MGUK':10}
        self.assertTrue(any('Ice wear is 76%' in x for x in self.messages(e,s,2)))
        s.player.lap.lap_valid=False
        self.assertIn('Current lap invalidated.', self.messages(e,s,3))
    def test_no_repeat_while_same_band(self):
        s=self.state(); e=AutomaticEngineer(); e.evaluate(s,0)
        s.player.tyres.surface_temperature_c=Wheels(116,90,90,90)
        self.assertTrue(self.messages(e,s,1))
        s.player.tyres.surface_temperature_c=Wheels(117,90,90,90)
        self.assertFalse(any('Tyres hot.' in x for x in self.messages(e,s,2)))

if __name__=='__main__': unittest.main()
