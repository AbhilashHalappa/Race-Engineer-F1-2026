from pathlib import Path
from types import SimpleNamespace
import json
import math

from src.driver_history import DriverHistory
from src.racing_line import compare_racing_line
from src.track_landmarks import TrackLandmarkStore
from src.analysis_validation import build_analysis_validation
from src.coaching_dashboard import coaching_summary_payload, coaching_page_html
import src.session_coach_report as report_mod


def _corner_metric(cid, brake_sd, min_sd):
    return {"corner_id": cid, "brake_point_consistency":{"stddev":brake_sd}, "minimum_speed_consistency":{"stddev":min_sd}}


def test_cross_session_corner_progress_and_comparison(tmp_path: Path):
    h=DriverHistory(tmp_path/'history.json')
    h.upsert({"session_uid":1,"event_context":{"track_name":"Melbourne"},"best_lap_s":81.0,"potential_lap_s":80.4,"reference_gap_s":1.2,
              "technique_metrics":{"corners":[_corner_metric(6,8.0,4.0)]},"recurring_patterns":[{"corner_id":6,"issue_code":"brake_early"}]})
    h.upsert({"session_uid":2,"event_context":{"track_name":"Melbourne"},"best_lap_s":80.2,"potential_lap_s":79.9,"reference_gap_s":0.5,
              "technique_metrics":{"corners":[_corner_metric(6,4.0,2.0)]},"recurring_patterns":[{"corner_id":6,"issue_code":"brake_early"}]})
    h.upsert({"session_uid":3,"event_context":{"track_name":"Melbourne"},"best_lap_s":79.9,"potential_lap_s":79.7,"reference_gap_s":0.2,
              "technique_metrics":{"corners":[_corner_metric(6,3.0,1.5)]},"recurring_patterns":[]})
    s=h.progress_summary('Melbourne')
    assert s['corner_progress'][0]['metrics']['brake_point_consistency']['direction']=='improving'
    assert s['resolved_recurring_issues'][0]['corner_id']==6
    c=h.compare_sessions('Melbourne',1,3)
    assert c['available'] and c['metric_deltas']['best_lap_s'] < 0
    assert c['corners'][0]['consistency']['brake_point_consistency']['delta'] < 0


def _arc_lap(apex_shift=0.0, inside_exit=0.0, steering_extra=False):
    samples={}
    # Left-hand quarter-circle-ish corner from d=20..120 with straights either side.
    for i in range(35):
        d=float(i*5)
        if d < 20:
            x,z=d,0.0
        elif d <= 120:
            u=(d-20)/100.0
            ang=(math.pi/2)*u
            x=20+60*math.sin(ang)
            z=60*(1-math.cos(ang))
            if 50 <= d <= 100:
                # Move curvature peak along the corner by changing local offset.
                z += apex_shift*math.exp(-((d-75)/16)**2)
            if d >= 90:
                # Positive local-lateral offset for left turn = inside of ref.
                x -= inside_exit
                z += inside_exit
        else:
            x=80.0; z=60+(d-120)
        steer=0.4
        if steering_extra and 40 <= d <= 100:
            steer=0.45 if (i%2)==0 else -0.25
        samples[d]={"d":d,"t":d/50.0,"world_x":x,"world_z":z,"steering":steer}
    return {"_samples":samples,"sections":[{"id":1,"start_m":20.0,"min_speed_m":70.0,"end_m":120.0}]}


def test_racing_line_geometry_classifications_are_evidence_bearing():
    ref=_arc_lap()
    cur=_arc_lap(apex_shift=5.0,inside_exit=1.5,steering_extra=True)
    out=compare_racing_line(cur,ref)
    assert out['available'] is True
    c=out['corners'][0]
    assert c['reference_geometric_apex_m'] is not None
    assert c['driver_geometric_apex_m'] is not None
    assert c['apex_classification'] in {'early','late','matched'}
    assert c['driver_steering_corrections'] >= c['reference_steering_corrections']
    assert c['pinched_exit'] in {True,False}
    assert 'outlier_filter' in out


def test_landmark_track_metadata_import_export_and_pre_call_override(tmp_path: Path):
    store=TrackLandmarkStore(tmp_path/'landmarks.json')
    store.set_track_metadata('MELBOURNE',start_finish_m=0.0,pit_entry_m=5000.0,pit_exit_m=100.0,default_pre_call_distance_m=210.0)
    store.set_manual_corner('MELBOURNE',1,board_100_m=310.0,kerb_start_m=450.0,pre_call_distance_m=175.0)
    ref={"metadata":{"track_length_m":5278},"sections":[{"id":1,"start_m":330.0,"min_speed_m":470.0,"end_m":520.0}]}
    store.learn_from_reference('MELBOURNE',ref)
    assert store.start_finish_landmark('MELBOURNE')['distance_m']==0.0
    assert store.pit_landmarks('MELBOURNE')[0]['kind']=='pit_entry'
    assert store.pre_call_distance_override('MELBOURNE',1)==175.0
    assert store.nearest_visual_landmark('MELBOURNE',311.0)['landmark']=='100 board'
    export=store.export_track('MELBOURNE',tmp_path/'melbourne_landmarks.json')
    other=TrackLandmarkStore(tmp_path/'other.json'); key=other.import_track(export)
    assert key=='MELBOURNE' and other.pre_call_distance_override('MELBOURNE',1)==175.0


def _lap(n,total,condition='dry'):
    return {"lap":n,"valid":True,"sample_count":800,"lap_time_s":total,"lap_start_anchored":True,
            "sector1_time_s":total/3,"sector2_time_s":total/3,"sector3_time_s":total/3,
            "track_name":"MELBOURNE","track_condition":condition,"tyre_compound":"soft","fuel_start_kg":20.0}


def test_validation_summarizes_rejections_and_warnings():
    invalid=_lap(2,82.0); invalid['valid']=False
    out=build_analysis_validation([_lap(1,80.0),invalid,_lap(3,85.0,'wet')],_lap(99,79.0))
    assert out['version']=='1.3.2.0'
    assert out['rejection_reason_counts']['invalid_lap'] >= 1
    assert isinstance(out['warning_counts'],dict)


def test_coaching_page_payload_uses_latest_report_and_history(tmp_path: Path):
    reports=tmp_path/'reports'; reports.mkdir()
    history=tmp_path/'history.json'
    report={"format":"RACE_ENGINEER_COACH_REPORT","event_context":{"track_name":"Melbourne"},"best_lap":{"lap_time_s":80.0},
            "potential":{"best_lap_s":80.0,"potential_lap_s":79.5,"realistic_available_gain_s":0.5},"reference_lap":{"lap_time_s":79.0},
            "total_reference_gap_s":1.0,"advice_outcomes":{"current_focus":{"corner_id":6,"issue_label":"Early braking"}},
            "ranked_biggest_opportunities":[],"best_strengths":[],"technique_metrics":{"corners":[]},"corner_drilldown":[],
            "latest_racing_line":{"available":False},"racing_line_svg":"","improvement_trend":{}}
    (reports/'coach.json').write_text(json.dumps(report),encoding='utf-8')
    h=DriverHistory(history); h.upsert({"session_uid":1,"event_context":{"track_name":"Melbourne"},"best_lap_s":80.1,"technique_metrics":{"corners":[]}})
    h.upsert({"session_uid":2,"event_context":{"track_name":"Melbourne"},"best_lap_s":80.0,"technique_metrics":{"corners":[]}})
    payload=coaching_summary_payload(reports,history)
    assert payload['available'] is True
    assert payload['summary']['current_focus']['corner_id']==6
    assert payload['session_comparison']['available'] is True
    assert '/api/coach/latest' in coaching_page_html()


def test_save_report_persists_history_and_latest_aliases(tmp_path: Path, monkeypatch):
    lap={"lap":1,"valid":True,"lap_time_s":80.0,"lap_start_anchored":True,"sample_count":100,"sections":[]}
    monkeypatch.setattr(report_mod,'lap_quality',lambda x:{"eligible":True,"reasons":[],"warnings":[]})
    monkeypatch.setattr(report_mod,'session_technique_metrics',lambda laps:{"corners":[]})
    monkeypatch.setattr(report_mod,'potential_summary',lambda *a,**k:{"best_lap_s":80.0,"potential_lap_s":79.8,"potential_gain_s":.2,"realistic_available_gain_s":.2,"reference_lap_s":80.0,"potential_vs_reference_s":-.2})
    monkeypatch.setattr(report_mod,'build_analysis_validation',lambda *a,**k:{"checks":{}})
    rec=SimpleNamespace(completed=[lap],external_reference=None,reference_mode='best',event_context={"track_name":"TEST","session_uid":123})
    # DriverHistory default is cwd-relative, so isolate cwd.
    monkeypatch.chdir(tmp_path)
    j,h,r=report_mod.save_coach_report(rec,directory='analysis/reports',stem='session')
    assert j.exists() and h.exists() and Path('analysis/reports/latest.json').exists()
    rows=DriverHistory('analysis/driver_history.json').load()
    assert rows and rows[-1]['session_uid']==123


def test_dashboard_landmark_api_get_and_post(tmp_path: Path, monkeypatch):
    import urllib.request
    from src.dashboard_server import DashboardStateStore, RemoteDashboardServer
    monkeypatch.chdir(tmp_path)
    server=RemoteDashboardServer(DashboardStateStore(),host='127.0.0.1',port=0)
    info=server.start()
    try:
        body=json.dumps({"track":"MELBOURNE","corner_id":1,"corner":{"board_100_m":320.0,"pre_call_distance_m":180.0}}).encode('utf-8')
        req=urllib.request.Request(info.local_url+'api/landmarks',data=body,headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=2) as r: posted=json.loads(r.read())
        assert posted['ok'] is True
        with urllib.request.urlopen(info.local_url+'api/landmarks?track=MELBOURNE',timeout=2) as r: got=json.loads(r.read())
        assert got['track']=='MELBOURNE'
    finally:
        server.stop()
