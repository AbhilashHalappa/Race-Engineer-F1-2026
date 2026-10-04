from pathlib import Path

from src.performance_history import PerformanceHistoryStore
from src.performance_hub_ui import performance_hub_page_html


def _game():
    return {"name":"ANTONELLI","race_number":12,"platform_id":1,"team_name":"Mercedes '26"}


def _coach(uid:int, best:float, potential:float, *, laps=(1,2,3), score=70.0):
    lap_store={}
    lap_reviews=[]
    for n in laps:
        t=best + (len(laps)-n)*0.7
        tele={k:{"driver":[[0,10+n],[100,20+n]],"reference":[]} for k in ("speed_kph","brake","throttle","gear","ers","delta_s")}
        lap_store[str(n)]={"lap":n,"lap_time_s":t,"valid":True,"quality":{"eligible":True},"telemetry":tele}
        lap_reviews.append({"lap":n,"summary":{"lap":n,"lap_time_s":t,"score":score+n,"grade":"FAIR","confidence":0.9},"corners":[{"corner_id":1,"score":score+n,"grade":"FAIR","confidence":0.9,"observations":1,"trusted_observations":1,"evidence_status":"trusted","mean_loss_s":0.1,"dominant_issue_label":"Brake later","detail":{}}]})
    review={"status":"available","score_model_version":"2.0.0","session_technique_score":score,"session_grade":"FAIR","confidence":0.9,"laps":[x["summary"] for x in lap_reviews],"lap_reviews":lap_reviews,"corners":lap_reviews[-1]["corners"],"technique_groups":[],"data_quality":{"eligible_laps":list(laps),"excluded_laps":[],"timed_valid_lap_count":len(laps)},"opportunities":[],"strengths":[]}
    return {"created_utc":f"2026-09-28T06:{uid:02d}:00+00:00","event_context":{"session_uid":uid,"track_name":"Las Vegas","track_id":16,"session_type":"Short Practice","game_mode":4},"potential":{"best_lap_s":best,"potential_lap_s":potential,"potential_gain_s":best-potential},"performance_review":review,"lap_telemetry":lap_store,"live_lap_intelligence":[],"telemetry_overlay":lap_store[str(laps[-1])]["telemetry"]}


def _summary(uid:int,best:float,laps:int):
    return {"session_uid":uid,"track":"Las Vegas","session_type":"Short Practice","laps_completed":laps,"best_lap_s":best,"position":1}


def test_same_session_laps_are_reference_options_and_lap_view_filters_review(tmp_path:Path):
    store=PerformanceHistoryStore(tmp_path/'h.sqlite3')
    store.create_user_profile('Abhilash H')
    sid=store.record_session(_game(),_summary(1,99.0,3),_coach(1,99.0,98.2))
    opts=store.review_reference_options(sid)["options"]
    ids={str(x["id"]) for x in opts}
    assert {'session_best','lap:1','lap:2','lap:3'} <= ids
    detail=store.review_detail(sid,'lap:2',view_lap=3)
    assert detail['view_lap']==3
    assert detail['review']['view_scope']=='lap'
    assert detail['review']['laps'][0]['lap']==3
    assert detail['review']['corners'][0]['corner_id']==1
    assert detail['visual_reference']['kind']=='session_lap'
    assert detail['visual_reference']['lap']==2


def test_track_summary_reports_improvement_and_predicted_potential(tmp_path:Path):
    store=PerformanceHistoryStore(tmp_path/'h.sqlite3')
    pid=store.create_user_profile('Abhilash H')
    store.record_session(_game(),_summary(1,100.0,3),_coach(1,100.0,98.8,score=65.0))
    store.record_session(_game(),_summary(2,98.5,4),_coach(2,98.5,97.9,score=72.0))
    d=store.track_detail('Las Vegas',pid)
    ts=d['track_summary']
    assert ts['best_lap_s']==98.5
    assert ts['predicted_potential_lap_s']==97.9
    assert round(ts['latest_best_change_s'],3)==-1.5
    assert round(ts['latest_technique_change'],1)==7.0
    assert 'improved' in ts['data_summary'].lower()


def test_delete_session_is_explicit_and_updates_history(tmp_path:Path):
    store=PerformanceHistoryStore(tmp_path/'h.sqlite3')
    pid=store.create_user_profile('Abhilash H')
    sid=store.record_session(_game(),_summary(1,99.0,3),_coach(1,99.0,98.2))
    assert store.overview(pid)['totals']['sessions']==1
    assert store.delete_session(sid) is True
    assert store.overview(pid)['available'] is False or store.overview(pid).get('totals',{}).get('sessions',0)==0


def test_ui_exposes_lap_selector_delete_track_summaries_and_color_key():
    html=performance_hub_page_html()
    for token in ('id=reviewLap','DELETE SESSION','OVERALL TRACK PERFORMANCE','AI TRACK SUMMARY','COLOR KEY','id=trackDataSummary','id=trackAiSummary','/api/performance/delete'):
        assert token in html
