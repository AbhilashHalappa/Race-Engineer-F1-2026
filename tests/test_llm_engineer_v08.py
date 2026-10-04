import json
import time
import unittest
from src.llm_engineer import LLMConfig, LocalLLMEngineer, build_reasoning_context
from src.race_state.models import RaceState, CarState, Wheels

class LLMEngineerV08Tests(unittest.TestCase):
    def test_context_contains_verified_normalized_values(self):
        s=RaceState(player=CarState(index=0))
        s.player.lap.position=4; s.player.lap.gap_to_car_in_front_s=1.25
        s.player.tyres.wear_percent=Wheels(10,11,12,13)
        c=build_reasoning_context(s)
        self.assertEqual(c['race']['position'],4)
        self.assertEqual(c['race']['gap_ahead_s'],1.25)
        self.assertEqual(c['tyres']['wear_percent']['RR'],13)

    def test_missing_car_is_explicit(self):
        self.assertEqual(build_reasoning_context(RaceState()), {'live_car_data': False})

    def test_worker_uses_local_transport(self):
        got=[]
        def transport(payload):
            obj=json.loads(payload); self.assertEqual(obj['model'],'test-model')
            self.assertIn('Verified RaceState', obj['messages'][1]['content'])
            return 'Stay out for now.'
        llm=LocalLLMEngineer(LLMConfig(model='test-model'), on_response=got.append, transport=transport)
        self.assertTrue(llm.submit('should I box', RaceState(player=CarState(index=0))))
        for _ in range(50):
            if got: break
            time.sleep(.01)
        llm.close()
        self.assertEqual(got, ['Stay out for now.'])

if __name__=='__main__': unittest.main()
