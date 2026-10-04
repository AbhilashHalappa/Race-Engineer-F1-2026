import json
from pathlib import Path
from types import SimpleNamespace
import urllib.request


def test_browser_replay_toggle_activates_worker_once(tmp_path, monkeypatch):
    from src.dashboard_server import DashboardStateStore, RemoteDashboardServer
    monkeypatch.chdir(tmp_path)
    rec=tmp_path/'recordings'; rec.mkdir(); (rec/'x.areplay').write_bytes(b'x')

    class Fake:
        def __init__(self):
            self.loaded=None; self.paused=True; self.position=0; self.toggle_calls=0
        def current_file(self): return self.loaded
        def load_file(self,p,autoplay=False):
            self.loaded=str(p); self.paused=not autoplay; self.position=0; return 10
        def set_paused(self,v): self.paused=bool(v)
        def toggle_paused(self): self.toggle_calls+=1; self.paused=not self.paused; return self.paused
        def set_speed(self,v): pass
        def seek(self,p): self.position=int(p)
        def status(self):
            return SimpleNamespace(position=self.position,total=10,range_start=0,range_end=9,speed=1.0,paused=self.paused,use_record_timestamps=True,rebuilding=False,requested_position=None,clock_drift_s=0.0)

    ctl=Fake(); mode={'active':False}; activations=[]
    def setter(enabled):
        activations.append(bool(enabled)); mode['active']=bool(enabled)
        if enabled: ctl.set_paused(False)
        return True, 'ok'
    server=RemoteDashboardServer(DashboardStateStore(),host='127.0.0.1',port=0,replay_controller=ctl,replay_mode_setter=setter,replay_mode_getter=lambda:mode['active'])
    info=server.start()
    try:
        req=urllib.request.Request(info.local_url+'api/replay/control',data=json.dumps({'action':'toggle','file':'x.areplay'}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=2) as r: payload=json.loads(r.read())
        assert payload['ok'] is True
        assert activations == [True]
        assert ctl.paused is False
        assert ctl.toggle_calls == 0, 'first PLAY click must not activate and immediately pause again'
        assert payload['status']['mode_active'] is True
    finally:
        server.stop()


def test_replay_status_reports_actual_mode_and_ui_follows_packet_cursor(tmp_path, monkeypatch):
    from src.dashboard_server import DashboardStateStore, RemoteDashboardServer
    from src.session_library_ui import session_library_page_html
    monkeypatch.chdir(tmp_path)
    class Fake:
        def current_file(self): return str(tmp_path/'x.areplay')
        def status(self):
            return SimpleNamespace(position=7,total=10,range_start=0,range_end=9,speed=1.0,paused=False,use_record_timestamps=True,rebuilding=False,requested_position=None,clock_drift_s=0.0)
    mode={'active':False}
    server=RemoteDashboardServer(DashboardStateStore(),host='127.0.0.1',port=0,replay_controller=Fake(),replay_mode_getter=lambda:mode['active'])
    info=server.start()
    try:
        with urllib.request.urlopen(info.local_url+'api/replay/status',timeout=2) as r: payload=json.loads(r.read())
        assert payload['available'] is True and payload['active'] is False
    finally:
        server.stop()
    html=session_library_page_html()
    assert 'syncCursorToReplayStatus' in html
    assert "setInterval(async()=>" in html and '},250)' in html
