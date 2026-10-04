import json
from pathlib import Path

from src.replay_analysis import ReplayAnalysisService
from src.session_library_ui import session_library_page_html


def _service(tmp_path: Path):
    rec=tmp_path/'recordings'; cache=tmp_path/'cache'; reports=tmp_path/'reports'; cc=tmp_path/'cc'
    for p in (rec,cache,reports,cc): p.mkdir(parents=True,exist_ok=True)
    replay=rec/'sample.areplay'; replay.write_bytes(b'x')
    samples=[]
    for i,d in enumerate(range(0,501,50)):
        samples.append({'packet':100+i,'session_time_s':10+i,'lap_time_s':i*.5,'distance_m':float(d),'speed_kph':220-abs(250-d)//2,'brake':0.8 if 100<=d<=200 else 0.0,'throttle':0.2 if d<250 else 1.0,'steer':0.1,'gear':5,'ers_percent':70.0,'rpm':11000,'g_lateral':1.2,'g_longitudinal':-1.1 if d<220 else .5,'g_vertical':1.0,'x':float(d),'z':float(d)/3})
    idx={'format':'race_engineer_replay_index','version':2,'source':{'file':replay.name,'path':str(replay),'size':1,'mtime_ns':replay.stat().st_mtime_ns},'session_uid':1,'packet_count':200,'session':{'track_id':3,'track_length_m':500,'session_type':12},'laps':[{'lap':1,'lap_time_s':80.0,'valid':True,'trace_samples':len(samples)}],'best_lap':1,'best_trace_lap':1,'navigation':[{'packet':s['packet'],'session_time_s':s['session_time_s'],'lap':1,'distance_m':s['distance_m']} for s in samples],'traces':{'1':samples},'associations':{'corner_validation':[]}}
    (cache/(replay.name+'.index.json')).write_text(json.dumps(idx),encoding='utf-8')
    return ReplayAnalysisService(rec,cache,reports,cc),replay


def test_workstation_exposes_extended_channels_and_packet_link(tmp_path):
    svc,replay=_service(tmp_path)
    out=svc.workstation(replay,1,1)
    assert out['lap']==1 and out['reference_lap']==1
    assert out['samples'][0]['packet']==100
    row=out['series'][0]
    for key in ('speed_kph','brake','throttle','steer','gear','ers_percent','rpm','g_lateral','g_longitudinal'):
        assert key in row


def test_replay_session_ui_exposes_synchronized_workstation_controls():
    html=session_library_page_html()
    for text in ['REPLAY-LINKED TELEMETRY WORKSTATION','SHARED DISTANCE CURSOR','MORE TELEMETRY','BRAKE POINT','THROTTLE PICKUP','EVENT ▶','/api/replay/control','/api/replay/workstation']:
        assert text in html
    for label in ['Speed','Brake','Throttle','Steering','Gear','ERS','Delta','RPM','Lat G','Long G']:
        assert label in html


def test_workstation_uses_shared_physical_turns_when_legacy_replay_has_no_corner_trace(tmp_path, monkeypatch):
    svc,replay=_service(tmp_path)
    import src.replay_analysis as ra
    monkeypatch.setattr(ra, 'persisted_physical_turns', lambda name, length: (
        {'corner_id':1,'label':'T1','apex_m':150.0,'start_m':100.0,'end_m':200.0},
        {'corner_id':2,'label':'T2','apex_m':350.0,'start_m':300.0,'end_m':400.0},
    ))
    out=svc.workstation(replay,1,1)
    assert [c['corner_id'] for c in out['corners']]==[1,2]
    assert out['corners'][0]['packet'] is not None


def test_dashboard_replay_controls_have_path_runtime_dependency():
    import src.dashboard_server as ds
    assert ds.Path('sample.areplay').name == 'sample.areplay'
