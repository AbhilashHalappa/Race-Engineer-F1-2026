from types import SimpleNamespace
import sqlite3, zipfile
import pytest

from src.diagnostics import latency_health, export_bundle
from src.dashboard_server import dashboard_payload
from src.overlay.track_maps import TRACK_MAPS
from src.track_geometry import PHYSICAL_TURN_COUNTS
from src.telemetry.header import decode_header, InvalidHeader, HEADER_STRUCT


def _packet(game_year):
    return HEADER_STRUCT.pack(2026, game_year, 1, 0, 1, 0, 123, 1.0, 1, 1, 0, 255)


def test_f1_2026_season_pack_accepts_game_year_25_and_26():
    decode_header(_packet(25)); decode_header(_packet(26))
    with pytest.raises(InvalidHeader): decode_header(_packet(24))


def test_every_supported_physical_track_has_closed_fallback_map():
    missing=set(PHYSICAL_TURN_COUNTS)-set(TRACK_MAPS)
    assert not missing
    for name in PHYSICAL_TURN_COUNTS:
        pts=TRACK_MAPS[name]
        assert len(pts)>=5, name
        assert pts[0]==pts[-1], name


def test_dashboard_payload_preserves_native_coaching_state():
    snap=SimpleNamespace(coaching_mode='time_trial',coaching_verbosity='detailed',dashboard_focus_page='map')
    p=dashboard_payload(snap)
    assert p['coaching_mode']=='time_trial'
    assert p['coaching_verbosity']=='detailed'
    assert p['dashboard_focus_page']=='map'


def test_latency_health_boundary():
    assert latency_health({'ui_latency_ms':99.9})['ok'] is True
    assert latency_health({'ui_latency_ms':100.1})['ok'] is False


def test_diagnostics_uses_consistent_sqlite_backup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db=tmp_path/'analysis/performance_history_live.sqlite3'; db.parent.mkdir(parents=True)
    con=sqlite3.connect(db); con.execute('create table t(v integer)'); con.execute('insert into t values(7)'); con.commit()
    out=export_bundle(tmp_path/'diag.zip')
    con.close()
    with zipfile.ZipFile(out) as z:
        assert 'analysis/performance_history_live.sqlite3' in z.namelist()
        extracted=tmp_path/'copy.sqlite3'; extracted.write_bytes(z.read('analysis/performance_history_live.sqlite3'))
    chk=sqlite3.connect(extracted); assert chk.execute('select v from t').fetchone()[0]==7; chk.close()


def _corner_section():
    return {"id":1,"start_m":100.0,"brake_release_m":155.0,"brake_duration_m":55.0,"turn_in_m":130.0,"trail_brake_m":25.0,"min_speed_m":165.0,"min_speed_kph":130.0,"apex_method":"min_speed_proxy","throttle_pickup_m":175.0,"full_throttle_m":195.0,"pickup_to_full_throttle_m":20.0,"coasting_m":10.0,"end_m":220.0,"exit_speed_kph":185.0,"peak_brake":0.90,"entry_gear":6,"apex_gear":4,"exit_gear":5,"gear_shift_count":3,"peak_abs_steering":0.45,"steering_reversals":0,"max_slip":0.10,"analysis_sample_count":25}


def _corner_lap(section, delay_after_m=None, delay_s=0.0):
    samples={}
    for d in range(0,401,5):
        delay=delay_s if delay_after_m is not None and d>=delay_after_m else 0.0
        samples[float(d)]={"d":float(d),"t":d/50.0+delay,"speed":200.0,"throttle":1.0,"brake":0.0,"steering":0.0,"gear":6}
    return {"lap":2,"valid":True,"lap_time_s":8.0+max(0.0,delay_s),"sections":[section],"_samples":samples}


def test_known_corner_expected_result_fixture():
    import json
    from pathlib import Path
    from src.coaching_analysis import build_corner_analyses
    expected=json.loads((Path(__file__).parent/'fixtures/known_corner_expected.json').read_text())
    ref=_corner_section()
    cur=dict(ref,start_m=85.0,brake_duration_m=70.0)
    a=build_corner_analyses(_corner_lap(cur,50,0.10),_corner_lap(ref))[0]
    e=expected['early_braking']
    assert a.diagnosis==e['diagnosis'] and a.diagnosis_label==e['label']
    assert a.diagnosis_confidence>e['min_confidence'] and a.issue_candidates[0]['code']==e['primary_code']
    cur=dict(ref,throttle_pickup_m=195.0,full_throttle_m=215.0)
    a=build_corner_analyses(_corner_lap(cur,180,0.10),_corner_lap(ref))[0]
    e=expected['late_throttle']; assert a.diagnosis==e['diagnosis'] and a.issue_candidates[0]['phase']==e['primary_phase']
    cur=dict(ref,exit_speed_kph=175.0)
    a=build_corner_analyses(_corner_lap(cur,180,0.009),_corner_lap(ref))[0]
    e=expected['below_deadband']; assert a.diagnosis is e['diagnosis']; assert a.coaching_eligible is e['coaching_eligible']; assert a.coaching_suppression_reason==e['suppression_reason']
