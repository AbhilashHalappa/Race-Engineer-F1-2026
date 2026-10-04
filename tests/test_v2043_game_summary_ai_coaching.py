import json
from types import SimpleNamespace

from src.performance_history import _review_result_summary
from src.performance_hub_ui import performance_hub_page_html
from src.performance_review_ai import generate_ai_summary


def test_game_style_lap_summary_recalculates_gap_to_selected_reference_and_keeps_facts():
    payload={
        'session':{'best_lap_s':90.0,'potential_lap_s':89.4,'potential_gain_s':.6,'summary':{'warnings':3,'penalties_s':5}},
        'reference_mode':'session_lap',
        'visual_reference':{'kind':'session_lap','label':'This session · Lap 2','lap_time_s':89.5},
    }
    coach={'lap_facts':[
        {'lap':1,'lap_time_s':90.2,'sector1_time_s':30.0,'sector2_time_s':29.8,'sector3_time_s':30.4,'valid':True,
         'warnings':1,'corner_cutting_warnings':1,'penalties_s':0,
         'assists':{'traction_control':1,'anti_lock_brakes':1,'gearbox_assist':0}},
    ],'potential':{'potential_lap_s':89.4}}
    out=_review_result_summary(payload,coach,1)
    assert out['scope']=='lap'
    assert out['sector1_time_s']==30.0
    assert out['valid'] is True
    assert out['gap_to_selected_reference_s']==0.7
    assert 'Traction Control: Medium' in out['assist_labels']
    assert out['theoretical_potential_lap_s'] is None


def test_game_style_session_summary_uses_best_lap_sectors_and_potential():
    payload={'session':{'best_lap_s':89.0,'potential_lap_s':88.5,'potential_gain_s':.5,'summary':{'warnings':2,'penalties_s':0}},
             'reference_mode':'external','visual_reference':{'kind':'external','label':'Rival reference','lap_time_s':88.0}}
    coach={'lap_facts':[{'lap':1,'lap_time_s':90.0,'sector1_time_s':30.0,'sector2_time_s':30.0,'sector3_time_s':30.0,'valid':True},
                        {'lap':2,'lap_time_s':89.0,'sector1_time_s':29.5,'sector2_time_s':29.7,'sector3_time_s':29.8,'valid':True}],
           'potential':{'potential_lap_s':88.5}}
    out=_review_result_summary(payload,coach,None)
    assert out['lap']==2
    assert out['sector3_time_s']==29.8
    assert out['gap_to_selected_reference_s']==1.0
    assert out['theoretical_potential_lap_s']==88.5


def test_performance_hub_contains_game_style_summary_and_reference_gap_binding():
    html=performance_hub_page_html()
    for token in ('SESSION SUMMARY','SECTOR 1','GAP TO SELECTED REF','THEORETICAL / POTENTIAL','renderGameSummary(d)','gap_to_selected_reference_s'):
        assert token in html


def test_ai_prompt_is_driver_facing_not_schema_explanation(monkeypatch):
    captured={}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self): return json.dumps({'message':{'content':'Brake a little later at Turn 4 and prioritise the exit.'}}).encode()
    def fake_open(req, timeout=None):
        captured['body']=json.loads(req.data.decode())
        return Response()
    monkeypatch.setattr('urllib.request.urlopen',fake_open)
    payload={
        'session':{'track_name':'CATALUNYA','session_type':'Time Trial'},
        'result_summary':{'scope':'lap','lap':2,'lap_time_s':89.0,'sector1_time_s':29.5,'sector2_time_s':29.7,'sector3_time_s':29.8,
                          'gap_to_selected_reference_s':.6,'reference_label':'Rival reference','valid':True,'warnings':0,'penalties_s':0,
                          'assist_labels':['Traction Control: Medium','ABS: On']},
        'review':{'session_technique_score':72.0,'confidence':.8,'opportunities':[{'corner_id':4,'dominant_issue_label':'Brake point too early','mean_net_loss_s':.18}]},
        'selected_reference_comparison':{},
    }
    answer=generate_ai_summary(payload,None)
    assert answer.startswith('Brake')
    messages=captured['body']['messages']
    text='\n'.join(m['content'] for m in messages)
    assert 'Do not mention JSON' in text
    assert 'focus_score' not in text
    assert 'corner_id' not in text
    assert 'Brake point too early' in text
    assert 'Turn 4' in text
