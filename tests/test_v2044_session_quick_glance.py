from src.performance_history import _session_quick_glance
from src.performance_hub_ui import performance_hub_page_html


def test_quick_glance_builds_all_laps_ranked_reference_gaps_and_theoretical():
    coach={
        'lap_facts':[
            {'lap':1,'lap_time_s':83.708,'sector1_time_s':23.307,'sector2_time_s':33.474,'sector3_time_s':26.927,'valid':True,'warnings':0,'penalties_s':0,'assists':{'anti_lock_brakes':1}},
            {'lap':2,'lap_time_s':80.816,'sector1_time_s':23.768,'sector2_time_s':31.819,'sector3_time_s':25.229,'valid':True,'warnings':0,'penalties_s':0,'assists':{'anti_lock_brakes':1}},
            {'lap':3,'lap_time_s':79.483,'sector1_time_s':23.529,'sector2_time_s':31.813,'sector3_time_s':24.140,'valid':True,'warnings':0,'penalties_s':0,'assists':{'anti_lock_brakes':1}},
            {'lap':4,'lap_time_s':80.327,'sector1_time_s':23.324,'sector2_time_s':32.746,'sector3_time_s':24.256,'valid':True,'warnings':0,'penalties_s':0,'assists':{'anti_lock_brakes':1}},
            {'lap':5,'lap_time_s':78.668,'sector1_time_s':23.405,'sector2_time_s':31.991,'sector3_time_s':23.271,'valid':True,'warnings':0,'penalties_s':0,'assists':{'anti_lock_brakes':1}},
        ]
    }
    payload={'session':{},'visual_reference':{'label':'Rival','lap_time_s':78.063},'reference_mode':'external'}
    out=_session_quick_glance(payload,coach)
    assert len(out['rows'])==5
    assert round(out['rows'][3]['gap_to_selected_reference_s'],3)==2.264
    assert out['best_lap']['lap']==5
    assert out['theoretical_sectors_s']==[23.307,31.813,23.271]
    assert round(out['theoretical_lap_s'],3)==78.391


def test_quick_glance_ui_is_additive_and_visible_before_tab_content():
    html=performance_hub_page_html()
    assert 'SESSION LAP TIMES' in html
    assert 'quickGlanceRows' in html
    assert 'renderSessionQuickGlance(d)' in html
    assert html.index('id=sessionQuickGlance') < html.index('class=tabs')
    # Existing per-view summary remains in place.
    assert 'id=resultSummary' in html
    assert 'LAP TIME' in html and 'THEORETICAL / POTENTIAL' in html

def test_session_quick_glance_preserves_assist_state_for_ui_icons():
    payload={"session":{},"visual_reference":{"lap_time_s":90.0,"label":"Session best"}}
    assists={
        "traction_control":2,
        "anti_lock_brakes":1,
        "gearbox_assist":2,
        "custom_setup":1,
        "equal_car_performance":1,
    }
    coach={"lap_facts":[{"lap":3,"lap_time_s":91.2,"valid":True,"assists":assists}]}
    out=_session_quick_glance(payload,coach)
    assert out["rows"][0]["assists"] == assists
