import json, os
from pathlib import Path

from src.replay_analysis import ReplayAnalysisService
from src.session_library import SessionLibrary


def _cached(tmp_path: Path, name: str, uid: int, lap_times=(90.0, 89.0)):
    recdir=tmp_path/'recordings'; cachedir=tmp_path/'cache'; reports=tmp_path/'reports'; cc=tmp_path/'cc'
    recdir.mkdir(exist_ok=True); cachedir.mkdir(exist_ok=True); reports.mkdir(exist_ok=True); cc.mkdir(exist_ok=True)
    p=recdir/name; p.write_bytes(b'x')
    traces={}
    laps=[]
    for lap,lt in enumerate(lap_times,1):
        laps.append({'lap':lap,'lap_time_s':lt,'valid':True,'trace_samples':4,'start_packet':lap*100,'end_packet':lap*100+99})
        traces[str(lap)]=[
            {'packet':lap*100+i,'session_time_s':lap*100+i,'lap_time_s':v,'distance_m':d,'speed_kph':100+lap*10+i,'brake':0.1*i,'throttle':1-0.1*i,'gear':4+i,'ers_percent':70-i,'x':d/10,'z':lap+d/20}
            for i,(d,v) in enumerate([(0,0.0),(100,2.0),(200,4.0),(300,6.0)])
        ]
    index={'format':'race_engineer_replay_index','version':1,'source':{'file':p.name,'path':str(p),'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns},'session_uid':uid,'packet_count':500,'game':{'game_year':26},'session':{'track_id':1,'session_type':10},'laps':laps,'best_lap':2,'best_trace_lap':2,'navigation':[{'packet':101,'session_time_s':100.0,'lap':1,'distance_m':0},{'packet':130,'session_time_s':103.0,'lap':1,'distance_m':150},{'packet':201,'session_time_s':200.0,'lap':2,'distance_m':0}], 'traces':traces,'associations':{'corner_validation':[]}}
    cp=cachedir/(p.name+'.index.json'); cp.write_text(json.dumps(index))
    return ReplayAnalysisService(recdir,cachedir,reports,cc),p,index,cc,reports


def test_compare_selected_laps_produces_distance_aligned_delta(tmp_path):
    svc,p,_,_,_=_cached(tmp_path,'one.areplay',123)
    out=svc.compare_laps(p,[1,2])
    assert out['distance_m'][:3]==[0.0,10.0,20.0]
    assert [s['lap'] for s in out['series']]==[1,2]
    assert out['series'][1]['lap_delta_s']==-1.0
    assert all(v == 0.0 for v in out['series'][0]['delta_s'] if v is not None)


def test_compare_two_sessions_uses_best_trace_lap(tmp_path):
    a,pa,_,_,_=_cached(tmp_path,'a.areplay',1,(92.0,90.0))
    # share same dirs/service and create second cache there
    p2=a.recordings/'b.areplay'; p2.write_bytes(b'x')
    idx=json.loads((a.cache_dir/(pa.name+'.index.json')).read_text())
    idx['source']={'file':p2.name,'path':str(p2),'size':1,'mtime_ns':p2.stat().st_mtime_ns}; idx['session_uid']=2; idx['laps'][1]['lap_time_s']=89.5
    (a.cache_dir/(p2.name+'.index.json')).write_text(json.dumps(idx))
    out=a.compare_sessions(pa,p2)
    assert out['left']['lap']==2 and out['right']['lap']==2
    assert out['best_lap_delta_s']==-0.5
    assert len(out['right']['delta_s'])==len(out['distance_m'])


def test_coaching_timeline_and_corner_jump_packet_mapping(tmp_path):
    svc,p,index,cc,_=_cached(tmp_path,'one.areplay',123)
    trace=cc/'CORNER_COACH_TEST_123_20260101T000000Z.jsonl'
    trace.write_text('\n'.join(json.dumps(x) for x in [
        {'event':'pre_emit','session_time_s':102.9,'lap':1,'distance_m':149,'zone_id':'Z1','label':'T1','corner_ids':[1],'text':'Turn 1.'},
        {'event':'post_emit','session_time_s':103.1,'lap':1,'distance_m':151,'zone_id':'Z1','label':'T1','corner_ids':[1],'text':'Turn 1, gained.'},
    ]))
    # force cache association discovery refresh
    idx=svc.build(p); idx['associations']=svc.associations(p,session_uid=123); (svc.cache_dir/(p.name+'.index.json')).write_text(json.dumps(idx))
    timeline=svc.timeline(p); corners=svc.corners(p)
    assert len(timeline)==2
    assert timeline[0]['packet']==130
    assert corners[0]['corner_ids']==[1] and corners[0]['packet']==130


def test_session_library_search_and_explicit_artifact_link(tmp_path, monkeypatch):
    svc,p,idx,cc,reports=_cached(tmp_path,'one.areplay',123)
    meta=tmp_path/'analysis'/'session_library.json'
    lib=SessionLibrary(recordings=svc.recordings,metadata=meta,reports=reports)
    lib.replay_analysis=svc
    lib.update(p.name,name='Melbourne race',tags=['race','melbourne'],favorite=True)
    lib.link_artifacts(p.name,coach_report_json='report.json',validation_json='validation.json')
    rows=lib.search('melbourne',tags=['race'],favorites_only=True)
    assert len(rows)==1
    assert rows[0]['associations']['coach_report_json']=='report.json'
    assert lib.search('shanghai')==[]


def test_cache_invalidates_when_recording_changes(tmp_path):
    svc,p,_,_,_=_cached(tmp_path,'one.areplay',123)
    assert svc.build(p)['packet_count']==500
    p.write_bytes(b'not a replay anymore')
    try:
        svc.build(p)
    except ValueError as e:
        assert 'ARERPL01' in str(e)
    else:
        raise AssertionError('stale cache should not be reused')

def test_cross_track_session_compare_is_rejected(tmp_path):
    svc,p,idx,_,_=_cached(tmp_path,'a.areplay',1)
    p2=svc.recordings/'b.areplay'; p2.write_bytes(b'x')
    other=json.loads((svc.cache_dir/(p.name+'.index.json')).read_text())
    other['source']={'file':p2.name,'path':str(p2),'size':1,'mtime_ns':p2.stat().st_mtime_ns}; other['session']['track_id']=2
    (svc.cache_dir/(p2.name+'.index.json')).write_text(json.dumps(other))
    try: svc.compare_sessions(p,p2)
    except ValueError as e: assert 'same track' in str(e)
    else: raise AssertionError('cross-track comparison must be rejected')

def test_dashboard_jump_route_drives_replay_controller(tmp_path, monkeypatch):
    import urllib.request
    from src.dashboard_server import DashboardStateStore, RemoteDashboardServer
    monkeypatch.chdir(tmp_path); (tmp_path/'recordings').mkdir(); (tmp_path/'recordings'/'x.areplay').write_bytes(b'x')
    class Fake:
        def __init__(self): self.loaded=None; self.position=None
        def current_file(self): return self.loaded
        def load_file(self,p,autoplay=False): self.loaded=str(p); return 1
        def seek(self,p): self.position=int(p)
    ctl=Fake(); server=RemoteDashboardServer(DashboardStateStore(),host='127.0.0.1',port=0,replay_controller=ctl); info=server.start()
    try:
        req=urllib.request.Request(info.local_url+'api/replay/jump',data=json.dumps({'file':'x.areplay','packet':321}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=2) as r: payload=json.loads(r.read())
        assert payload['ok'] is True and ctl.position==321 and Path(ctl.loaded).name=='x.areplay'
    finally: server.stop()


def test_sessions_page_exposes_replay_analysis_controls():
    from src.session_library_ui import session_library_page_html
    page=session_library_page_html()
    for text in ['Compare sessions','Corner jump','Coaching timeline','Compare selected laps','delta_s']:
        assert text in page
