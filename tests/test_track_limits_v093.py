import unittest
from src.engineer import AutomaticEngineer, Priority
from src.race_state.models import CarState, RaceEvent, RaceState
from src.telemetry.enums import EnumValue


def ev(raw, name): return EnumValue(raw, name)

def base():
    s=RaceState(player_index=0); s.session.uid=93; s.session.session_time_s=10
    s.session.weather=ev(0,'Clear'); s.session.safety_car=ev(0,'None')
    c=CarState(0); c.lap.current_lap=1; c.lap.corner_cutting_warnings=0; c.lap.lap_valid=True
    c.lap.pit_status=ev(0,'None'); c.lap.driver_status=ev(4,'On track')
    s.player=c; s.field={0:c}; return s

class TrackLimitV093Tests(unittest.TestCase):
    def test_corner_warning_is_immediate_and_short(self):
        e=AutomaticEngineer(); s=base(); e.evaluate(s,1); e.drain()
        s.player.lap.corner_cutting_warnings=1
        e.evaluate(s,2); msgs=e.drain()
        self.assertTrue(any(m.text=='Track limits.' and m.priority==Priority.CRITICAL for m in msgs))
        self.assertFalse(any('warnings now' in m.text.lower() for m in msgs))

    def test_running_wide_event_short_call(self):
        e=AutomaticEngineer(); s=base(); e.evaluate(s,1); e.drain()
        s.events=(RaceEvent('PENA','Penalty',{'penaltyType':5,'infringementType':26,'vehicleIdx':0,'otherVehicleIdx':255,'time':0,'lapNum':1,'placesGained':0},11.0,2.0),)
        e.evaluate(s,2); msgs=e.drain()
        self.assertEqual([m.text for m in msgs if m.key=='track_limits'], ['Track limits.'])


    def test_physical_off_track_surface_is_immediate(self):
        e=AutomaticEngineer(); s=base()
        s.player.telemetry.surface_type = __import__('src.race_state.models', fromlist=['Wheels']).Wheels(0,0,0,0)
        e.evaluate(s,1); e.drain()
        s.player.telemetry.surface_type = __import__('src.race_state.models', fromlist=['Wheels']).Wheels(7,7,7,0)
        e.evaluate(s,1.02); msgs=e.drain()
        self.assertTrue(any(m.text=='Track limits.' and m.priority==Priority.CRITICAL for m in msgs))

    def test_single_wheel_on_grass_does_not_chatter(self):
        e=AutomaticEngineer(); s=base()
        s.player.telemetry.surface_type = __import__('src.race_state.models', fromlist=['Wheels']).Wheels(0,0,0,0)
        e.evaluate(s,1); e.drain()
        s.player.telemetry.surface_type = __import__('src.race_state.models', fromlist=['Wheels']).Wheels(7,0,0,0)
        e.evaluate(s,1.02); self.assertFalse(any(m.key=='track_limits' for m in e.drain()))

    def test_non_track_warning_keeps_specific_race_control_message(self):
        e=AutomaticEngineer(); s=base(); e.evaluate(s,1); e.drain()
        s.events=(RaceEvent('PENA','Penalty',{'penaltyType':5,'infringementType':21,'vehicleIdx':0,'otherVehicleIdx':255,'time':0,'lapNum':1,'placesGained':0},11.0,2.0),)
        e.evaluate(s,2); texts=[m.text for m in e.drain()]
        self.assertTrue(any('Warning for' in x for x in texts)); self.assertNotIn('Track limits.',texts)

if __name__=='__main__': unittest.main()
