import unittest
from src.engineer.engine import AutomaticEngineer
from src.engineer.models import EngineerMessage, Priority
from src.tts import SpeechOutput
from src.pit_strategy import choose_tyre
from src.race_state.models import RaceState, CarState, TyreSet, Wheels
from src.telemetry.enums import EnumValue

class V094FineTuneTests(unittest.TestCase):
    def test_driver_voice_response_outranks_routine_track_limits(self):
        t=EngineerMessage('track_limits',Priority.CRITICAL,'Track limits.',0)
        v=EngineerMessage('voice:response',Priority.STRATEGY,'Answer',0)
        self.assertLess(SpeechOutput._radio_rank(v), SpeechOutput._radio_rank(t))

    def test_temperature_band_rearms_after_recovery(self):
        a=AutomaticEngineer(); s=RaceState(); s.player_index=0; c=CarState(0); s.field[0]=c; s.player=c
        c.tyres.surface_temperature_c=Wheels(100,100,100,100)
        a.evaluate(s,0)
        c.tyres.surface_temperature_c=Wheels(116,100,100,100)
        self.assertTrue(any(m.key=='tyre_temp:115' for m in a.evaluate(s,1)))
        c.tyres.surface_temperature_c=Wheels(106,100,100,100)
        a.evaluate(s,22)
        c.tyres.surface_temperature_c=Wheels(116,100,100,100)
        self.assertTrue(any(m.key=='tyre_temp:115' for m in a.evaluate(s,23)))

    def test_tyre_choice_handles_unknown_wear_and_delta(self):
        s=RaceState(); s.player_index=0; c=CarState(0); s.field[0]=c; s.player=c
        # Build through the public model fields used by choose_tyre.
        ts=TyreSet(index=1, actual_compound=EnumValue(16,'C5'), visual_compound=EnumValue(16,'Soft'), wear_percent=None, available=True, recommended_session=EnumValue(0,'Unknown'), lifespan_laps=0, usable_life_laps=0, lap_delta_s=None, fitted=False)
        c.tyres.sets=(ts,)
        choice=choose_tyre(s)
        self.assertTrue(choice.available)
        self.assertEqual(choice.set_index,1)

if __name__=='__main__': unittest.main()
