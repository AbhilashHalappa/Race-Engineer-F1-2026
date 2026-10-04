import json
import unittest
from src.llm_engineer import LLMConfig, LocalLLMEngineer, build_reasoning_context
from src.race_state.models import RaceState, CarState, Wheels

class LLMEngineerV081Tests(unittest.TestCase):
    def test_python_derives_tyre_summary_before_llm(self):
        s=RaceState(player=CarState(index=0))
        s.player.tyres.wear_percent=Wheels(10,20,30,40)
        s.player.tyres.surface_temperature_c=Wheels(88,92,96,100)
        d=build_reasoning_context(s)['derived_by_python']
        self.assertEqual(d['max_tyre_wear_percent'],40)
        self.assertEqual(d['average_tyre_wear_percent'],25.0)
        self.assertEqual(d['tyre_wear_spread_percent'],30)
        self.assertEqual(d['surface_temp_spread_c'],12)

    def test_inference_requests_keep_model_alive_and_limit_tokens(self):
        seen=[]
        def transport(payload):
            seen.append(json.loads(payload)); return 'Stay out. Tyres are stable.'
        llm=LocalLLMEngineer(LLMConfig(model='test'), transport=transport)
        llm._request('should I box', build_reasoning_context(RaceState(player=CarState(index=0))))
        llm.close()
        self.assertEqual(seen[0]['keep_alive'],'30m')
        self.assertEqual(seen[0]['options']['num_predict'],48)
        self.assertEqual(seen[0]['options']['num_ctx'],2048)

    def test_radio_trim_caps_verbose_model_output(self):
        text=' '.join('word' for _ in range(60))
        self.assertLessEqual(len(LocalLLMEngineer._radio_trim(text).split()),28)

if __name__=='__main__': unittest.main()
