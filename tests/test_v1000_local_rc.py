import json
from pathlib import Path
from src.reference_package import build_reference_package, validate_reference, export_reference, load_reference
from src.session_library import SessionLibrary
from src.diagnostics import export_bundle
from src.potential_lap import corner_potential
from src.session_coach_report import report_html


def _lap(n=1,t=70.0):
    samples={}
    for d in range(0,501,5):
        samples[float(d)]={"d":float(d),"t":d/50.0,"speed_kph":200+d*0.01,"brake":0.5 if 100<=d<=150 else 0.0,"throttle":1.0,"gear":6}
    return {"lap":n,"valid":True,"lap_start_anchored":True,"sample_count":len(samples),"lap_time_s":t,"sector1_time_s":20.0,"sector2_time_s":25.0,"sector3_time_s":25.0,"sections":[{"id":1,"start_m":100.0,"end_m":200.0}],"_samples":samples}


def test_reference_package_roundtrip(tmp_path):
    p=tmp_path/'r.json'; export_reference(p,_lap(),metadata={"track_id":7,"game_year":2026})
    pkg=load_reference(p)
    assert validate_reference(pkg,track_id=7,game_year=2026)["valid"]
    assert not validate_reference(pkg,track_id=8)["valid"]
    assert "_samples" not in pkg["lap"]


def test_corner_potential_uses_observed_windows():
    r=corner_potential([_lap(1),_lap(2,69.9)])
    assert r["available"] and r["corner_count"]==1
    assert abs(r["corner_best_times_s"][1]-2.0)<1e-9


def test_session_library_metadata_and_archive(tmp_path):
    rec=tmp_path/'recordings'; rec.mkdir(); (rec/'a.areplay').write_bytes(b'x')
    lib=SessionLibrary(rec,tmp_path/'meta.json'); lib.update('a.areplay',favorite=True,tags=['test'])
    rows=lib.list(); assert rows[0]['favorite'] and rows[0]['tags']==['test']
    assert lib.archive('a.areplay').exists()


def test_diagnostic_bundle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p=export_bundle('bundle.zip'); assert p.exists()


def test_rich_report_html_contains_drilldown():
    lap=_lap(); report={"potential":{"best_lap_s":70.0,"potential_lap_s":69.9,"potential_gain_s":.1,"eligible_lap_count":2},"best_lap":lap,"reference_lap":lap,"technique_metrics":{"corners":[]},"recurring_patterns":[],"latest_racing_line":{"available":True,"mean_path_deviation_m":.1,"max_path_deviation_m":.2},"latest_straight_line_analysis":{"available":False}}
    h=report_html(report)
    assert "Telemetry drill-down" in h and "<svg" in h and "Technique consistency" in h
