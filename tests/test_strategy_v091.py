import unittest
from src.race_state.models import RaceState,CarState,TyreSet,Wheels
from src.telemetry.enums import EnumValue
from src.pit_strategy import choose_tyre,service_plan
from src.voice_commands import parse_intent,VoiceIntent,answer_intent

def ev(n): return EnumValue(0,n)
class StrategyV091(unittest.TestCase):
 def state(self):
  s=RaceState(); c=CarState(0); s.player=s.field[0]=c; s.player_index=0
  s.session.total_laps=50; c.lap.current_lap=20; c.tyres.wear_percent=Wheels(82,70,70,70); c.tyres.visual_compound=ev('Medium')
  c.tyres.sets=(TyreSet(1,ev('Soft'),ev('Soft'),8,True,ev('Race'),20,20,.1,False),TyreSet(2,ev('Hard'),ev('Hard'),2,True,ev('Race'),30,30,.2,False))
  return s
 def test_freshest_matching_dry_set(self):
  x=choose_tyre(self.state()); self.assertEqual(x.set_index,2)
 def test_natural_compound_intent(self):
  self.assertEqual(parse_intent('which compound for the pit'),VoiceIntent.TYRE_SELECTION)
  self.assertIn('set 2',answer_intent(VoiceIntent.TYRE_SELECTION,self.state()))
 def test_pit_radio_is_deterministic(self):
  self.assertIn('Box soon',answer_intent(VoiceIntent.PIT_RECOMMENDATION,self.state()))
 def test_wing_service(self):
  s=self.state(); s.player.damage.front_left_wing_percent=70
  p=service_plan(s); self.assertTrue(p.front_wing_service)
  self.assertIn('Replace front wing',answer_intent(VoiceIntent.WING_SERVICE,s))

from src.engineer.engine import AutomaticEngineer
class AutoPitV091(unittest.TestCase):
 def test_auto_pit_plan_is_single_transition_call(self):
  s=StrategyV091().state(); e=AutomaticEngineer(); e.evaluate(s,1.0)
  s.player.tyres.wear_percent=Wheels(91,70,70,70)
  msgs=e.evaluate(s,2.0)
  pit=[m for m in msgs if m.key=='pit:deterministic_plan']
  self.assertEqual(len(pit),1); self.assertIn('Box this lap',pit[0].text)
  self.assertFalse(any(m.key=='pit:deterministic_plan' for m in e.evaluate(s,3.0)))
