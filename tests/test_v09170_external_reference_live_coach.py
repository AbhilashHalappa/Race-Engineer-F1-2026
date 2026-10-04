import json
from pathlib import Path

from src.measured_performance import MeasuredPerformanceRecorder
from src.reference_lap import export_reference_lap, load_reference_lap
from src.performance_coach import coaching_summary
from src.overlay.data import _reference_lap


def _lap(n=1, t=90.0, brake=100.0, full=200.0, min_speed=100.0, exit_speed=150.0):
    samples={}
    for d in range(0, 501, 5):
        samples[float(d)]={"d":float(d),"t":d/500*t,"speed":150.0,"throttle":1.0,"brake":0.0,"steering":0.0,"gear":5,"rpm":10000}
    return {"lap":n,"valid":True,"lap_time_s":t,"sections":[{"id":1,"start_m":brake,"brake_end_m":150.0,"end_m":full,"min_speed_m":150.0,"min_speed_kph":min_speed,"full_throttle_m":full,"exit_speed_kph":exit_speed,"peak_brake":0.8,"max_slip":0.05}],"_samples":samples}


def test_external_reference_survives_session_reset():
    r=MeasuredPerformanceRecorder(); ref=_lap()
    r.set_external_reference(ref,name="Fast Driver")
    r.reset()
    assert r.reference_mode == "external"
    assert r.external_reference_name == "Fast Driver"
    assert r.external_reference["lap_time_s"] == 90.0


def test_overlay_uses_external_reference_before_completed_laps():
    r=MeasuredPerformanceRecorder(); ref=_lap()
    r.set_external_reference(ref,name="Fast Driver")
    assert _reference_lap(r) is r.external_reference


def test_reference_export_roundtrip(tmp_path):
    r=MeasuredPerformanceRecorder(); r.completed=[_lap(2,89.5),_lap(3,90.0)]
    path=tmp_path/'ref.json'
    export_reference_lap(r,path)
    loaded,meta=load_reference_lap(path)
    assert loaded['lap_time_s'] == 89.5
    assert len(loaded['_samples']) > 20
    assert meta['reference_lap_number'] == 2


def test_actionable_coach_reports_measured_corner_difference():
    ref=_lap(brake=110.0,full=190.0,min_speed=108.0,exit_speed=158.0)
    cur=_lap(n=2,t=91.0,brake=90.0,full=215.0,min_speed=100.0,exit_speed=150.0)
    text=coaching_summary(cur,ref,max_actions=3)
    assert '1.000 seconds off the reference' in text
    assert ('brake about 20 metres later' in text or 'full throttle about 25 metres earlier' in text or 'carry about 8 kph more' in text)


def test_main_has_external_reference_cli_and_current_banner():
    source=Path('src/main.py').read_text(encoding='utf-8')
    assert '--reference-lap' in source
    assert '--export-reference-lap' in source
    assert 'V0.9.17.2.5 REFERENCE AUTHORITY + TRACK SYNC' in source
