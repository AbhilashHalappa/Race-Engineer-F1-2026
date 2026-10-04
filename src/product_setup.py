"""Device discovery and safe first-run product setup helpers."""
from __future__ import annotations

from pathlib import Path
import os
import platform
import subprocess

from .product_settings import ProductSettingsStore
from .product_readiness import first_run_check, windows_firewall_command
from .windows_validation import display_environment


def safe_audio_devices() -> dict:
    try:
        from .audio_devices import input_devices, output_devices
        conv=lambda d:{"index":int(d.index),"name":d.name,"sample_rate":float(d.default_samplerate)}
        return {"inputs":[conv(d) for d in input_devices()],"outputs":[conv(d) for d in output_devices()]}
    except Exception as error:
        return {"inputs":[],"outputs":[],"error":str(error)}


def safe_wheel_ports() -> list[dict]:
    try:
        from serial.tools import list_ports
        return [{"device":p.device,"description":p.description,"vid":p.vid,"pid":p.pid,
                 "manufacturer":p.manufacturer,"product":p.product} for p in list_ports.comports()]
    except Exception:
        return []


def safe_hid_devices() -> list[dict]:
    try:
        import hid
        out=[]
        for d in hid.enumerate():
            page=int(d.get("usage_page") or 0); usage=int(d.get("usage") or 0)
            if page != 0x01 or usage not in (0x04,0x05):
                continue
            out.append({"vendor_id":int(d.get("vendor_id") or 0),"product_id":int(d.get("product_id") or 0),
                        "usage_page":page,"usage":usage,"product":str(d.get("product_string") or "Game Controller"),
                        "manufacturer":str(d.get("manufacturer_string") or "")})
        return out
    except Exception:
        return []


def setup_snapshot(*, root: str | Path = ".") -> dict:
    store=ProductSettingsStore(Path(root)/"settings"/"product.json")
    readiness=first_run_check(udp_port=store.settings.udp_port,root=root).to_dict()
    return {"settings":store.settings.to_dict(),"readiness":readiness,"audio":safe_audio_devices(),
            "wheel_ports":safe_wheel_ports(),"hid_devices":safe_hid_devices(),"platform":platform.platform(),
            "display":display_environment()}


def apply_setup(changes: dict, *, root: str | Path = ".") -> dict:
    store=ProductSettingsStore(Path(root)/"settings"/"product.json")
    settings=store.set(**changes)
    return {"settings":settings.to_dict(),"restart_required":True}


def firewall_status(rule_name: str = "Race Engineer") -> dict:
    if os.name != "nt":
        return {"supported":False,"installed":False,"message":"Windows only"}
    proc=subprocess.run(["netsh","advfirewall","firewall","show","rule",f"name={rule_name}"],capture_output=True,text=True,timeout=5)
    text=(proc.stdout or "")+(proc.stderr or "")
    installed=proc.returncode==0 and "No rules match" not in text
    return {"supported":True,"installed":installed,"returncode":proc.returncode}


def install_private_firewall_rule(exe_path: str | Path) -> dict:
    if os.name != "nt":
        return {"ok":False,"error":"Windows only"}
    exe=str(Path(exe_path).resolve())
    cmd=["netsh","advfirewall","firewall","add","rule","name=Race Engineer","dir=in","action=allow",f"program={exe}","enable=yes","profile=private"]
    try:
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
        ok=proc.returncode==0
        elevated=False
        combined=((proc.stdout or '')+(proc.stderr or '')).lower()
        if not ok and ('access is denied' in combined or 'requires elevation' in combined or proc.returncode in (5,740)):
            # Explicit user action from the setup page: request UAC only here.
            args='advfirewall firewall add rule name="Race Engineer" dir=in action=allow program="'+exe+'" enable=yes profile=private'
            ps=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',
                'Start-Process -FilePath netsh.exe -ArgumentList '+repr(args)+' -Verb RunAs -Wait']
            elevated_proc=subprocess.run(ps,capture_output=True,text=True,timeout=60)
            elevated=elevated_proc.returncode==0
            ok=bool(firewall_status().get('installed'))
        if ok:
            ProductSettingsStore().set(firewall_private_enabled=True)
        return {"ok":ok,"elevation_requested":elevated,"returncode":proc.returncode,"stdout":proc.stdout[-4000:],"stderr":proc.stderr[-4000:],"command":windows_firewall_command(exe)}
    except Exception as error:
        return {"ok":False,"error":str(error),"command":windows_firewall_command(exe)}
