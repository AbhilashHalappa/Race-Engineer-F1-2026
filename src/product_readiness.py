"""Local Windows product-readiness checks. No network/cloud dependency."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, platform, shutil, socket, sys

@dataclass(frozen=True, slots=True)
class ReadinessReport:
    python_ok: bool
    windows: bool
    writable_settings: bool
    recordings_dir: bool
    voices_present: bool
    udp_port_available: bool | None
    ffmpeg_available: bool
    details: dict
    def to_dict(self): return asdict(self)

def first_run_check(*,udp_port=20777,root='.'):
    root=Path(root); settings=root/'settings'; recordings=root/'recordings'; voices=root/'voices'
    try: settings.mkdir(parents=True,exist_ok=True); probe=settings/'.write_test'; probe.write_text('ok'); probe.unlink(); writable=True
    except OSError:writable=False
    recordings.mkdir(parents=True,exist_ok=True)
    voice_ok=any(voices.glob('*.onnx')) if voices.exists() else False
    available=None; sock=None
    try:
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sock.bind(('0.0.0.0',int(udp_port))); available=True
    except OSError: available=False
    finally:
        if sock:
            try:sock.close()
            except OSError:pass
    return ReadinessReport(sys.version_info>=(3,11),platform.system()=='Windows',writable,recordings.exists(),voice_ok,available,shutil.which('ffmpeg') is not None,{'udp_port':int(udp_port),'python':sys.version.split()[0],'platform':platform.platform()})

def save_first_run_report(path='analysis/diagnostics/first_run.json',**kwargs):
    r=first_run_check(**kwargs); p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(r.to_dict(),indent=2,sort_keys=True),encoding='utf-8'); return p

def windows_firewall_command(exe_path:str)->str:
    exe=str(Path(exe_path).resolve())
    return f'netsh advfirewall firewall add rule name="Race Engineer" dir=in action=allow program="{exe}" enable=yes profile=private'
