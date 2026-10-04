import json
from pathlib import Path
from types import SimpleNamespace
import urllib.request


def test_load_replay_seeks_to_selected_lap_start_before_play(tmp_path, monkeypatch):
    from src.dashboard_server import DashboardStateStore, RemoteDashboardServer
    from src.replay_analysis import ReplayAnalysisService
    monkeypatch.chdir(tmp_path)
    rec=tmp_path/'recordings'; rec.mkdir(); (rec/'x.areplay').write_bytes(b'x')
    monkeypatch.setattr(ReplayAnalysisService, 'build', lambda self, replay, force=False: {
        'laps':[{'lap':1,'start_packet':10},{'lap':3,'start_packet':4200}],
        'source':{'file':'x.areplay'}
    })

    class Fake:
        def __init__(self): self.loaded=None; self.paused=True; self.position=0; self.seeks=[]
        def current_file(self): return self.loaded
        def load_file(self,p,autoplay=False): self.loaded=str(p); self.paused=not autoplay; self.position=0; return 9000
        def set_paused(self,v): self.paused=bool(v)
        def toggle_paused(self): self.paused=not self.paused; return self.paused
        def set_speed(self,v): pass
        def seek(self,p): self.position=int(p); self.seeks.append(int(p))
        def status(self):
            return SimpleNamespace(position=self.position,total=9000,range_start=0,range_end=8999,speed=1.0,paused=self.paused,use_record_timestamps=True,rebuilding=False,requested_position=None,clock_drift_s=0.0)

    ctl=Fake(); mode={'active':False}
    def setter(enabled): mode['active']=bool(enabled); return True,'ok'
    server=RemoteDashboardServer(DashboardStateStore(),host='127.0.0.1',port=0,replay_controller=ctl,replay_mode_setter=setter,replay_mode_getter=lambda:mode['active'])
    info=server.start()
    try:
        req=urllib.request.Request(info.local_url+'api/replay/control',data=json.dumps({'action':'load','file':'x.areplay','lap':3}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=2) as r: payload=json.loads(r.read())
        assert payload['ok'] is True
        assert ctl.seeks[-1] == 4200
        assert ctl.position == 4200
        assert ctl.paused is False
    finally:
        server.stop()


def test_workstation_load_button_sends_selected_lap():
    from src.session_library_ui import session_library_page_html
    html=session_library_page_html()
    assert "replayControl('load',{lap:wsLap})" in html
