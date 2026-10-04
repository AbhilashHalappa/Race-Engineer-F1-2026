import json, math
from pathlib import Path
import pytest

from src.reference_ecosystem import (
    compatibility_report, export_reference_package, inspect_reference_package,
    install_reference_package, list_installed_references, normalized_metadata,
    reference_quality,
)
from src.reference_lap import FORMAT, VERSION


def _lap(length=1500.0):
    samples={}
    for d in range(0,int(length)+1,5):
        samples[float(d)]={
            "d":float(d),"t":d/50.0,"speed":180.0,
            "brake":0.8 if 380<=d<=480 else 0.0,
            "throttle":0.05 if 370<=d<540 else 1.0,
            "steering":0.28 if 430<=d<=560 else 0.0,"gear":5,
            "world_x":float(d),"world_z":math.sin(d/100.0)*20.0,
        }
    return {"track_name":"TEST_TRACK","track_length_m":length,"lap_time_s":length/50.0,
            "valid":True,"lap_start_anchored":True,"sections":[],"_samples":samples}


def _source(tmp_path, *, team=10, equal=1):
    lap=_lap(); md={"track_id":7,"track_length_m":1500,"game_year":2026,"game_version":"1.0",
                    "formula":13,"team_id":team,"equal_car_performance":equal,
                    "driver":"Friend Driver","source":"FRIEND_EXPORT","traction_control":0,
                    "anti_lock_brakes":0,"gearbox_assist":0,"custom_setup_used":1,"weather":0}
    tmp_path.mkdir(parents=True,exist_ok=True)
    p=tmp_path/'reference.json'
    p.write_text(json.dumps({"format":FORMAT,"version":VERSION,"metadata":md,"lap":lap}),encoding='utf-8')
    return p


def test_formal_metadata_preserves_known_fields_and_unknowns(tmp_path):
    p=_source(tmp_path); data=json.loads(p.read_text()); md=normalized_metadata(data['metadata'],data['lap'])
    assert md['track']['id']==7 and md['track']['name']=='TEST_TRACK'
    assert md['game']['year']==2026 and md['car']['team_id']==10
    assert md['assists']['traction_control']==0 and md['setup']['custom_setup_used']==1
    assert md['tyre']=={} and md['fuel']=={}


def test_quality_accepts_dense_valid_reference(tmp_path):
    p=_source(tmp_path); data=json.loads(p.read_text())
    q=reference_quality(data['lap'],data['metadata'])
    assert q['accepted'] is True and q['score']>=75


def test_compatibility_blocks_track_and_game_mismatch_but_warns_assists(tmp_path):
    p=_source(tmp_path); data=json.loads(p.read_text()); ref=normalized_metadata(data['metadata'],data['lap'])
    ok=compatibility_report(ref,{"track_id":7,"track_length_m":1500,"game_year":2026,"formula":13,"equal_car_performance":1,"traction_control":2})
    assert ok['compatible'] is True and 'assist_traction_control_mismatch' in ok['warnings']
    bad=compatibility_report(ref,{"track_id":8,"track_length_m":1500,"game_year":2025,"formula":13,"equal_car_performance":1})
    assert bad['compatible'] is False and 'track_mismatch' in bad['blockers'] and 'game_year_mismatch' in bad['blockers']


def test_team_only_blocks_for_known_unequal_car_performance(tmp_path):
    p=_source(tmp_path,team=10,equal=0); data=json.loads(p.read_text()); ref=normalized_metadata(data['metadata'],data['lap'])
    bad=compatibility_report(ref,{"track_id":7,"track_length_m":1500,"game_year":2026,"formula":13,"equal_car_performance":0,"team_id":11})
    assert bad['compatible'] is False and 'team_mismatch' in bad['blockers']
    equal=compatibility_report(ref,{"track_id":7,"track_length_m":1500,"game_year":2026,"formula":13,"equal_car_performance":1,"team_id":11})
    assert 'team_mismatch' not in equal['blockers']


def test_friend_reference_export_inspect_install_roundtrip(tmp_path):
    source=_source(tmp_path/'src'); package=tmp_path/'friend_ref.zip'
    result=export_reference_package(source,package,author='Friend')
    assert package.exists() and result['manifest']['schema']=='RACE_ENGINEER_REFERENCE_PACKAGE'
    check=inspect_reference_package(package,context={"track_id":7,"track_length_m":1500,"game_year":2026,"formula":13,"equal_car_performance":1})
    assert check['valid'] and check['compatibility']['compatible']
    installed=install_reference_package(package,root=tmp_path/'refs',context={"track_id":7,"track_length_m":1500,"game_year":2026,"formula":13,"equal_car_performance":1})
    assert Path(installed['path']).exists()
    rows=list_installed_references(tmp_path/'refs')
    assert len(rows)==1 and rows[0]['valid'] is True and rows[0]['manifest']['author']=='Friend'


def test_package_checksum_tamper_is_rejected(tmp_path):
    from zipfile import ZipFile, ZIP_DEFLATED
    source=_source(tmp_path/'src'); package=tmp_path/'friend_ref.zip'; export_reference_package(source,package)
    with ZipFile(package,'r') as zf: files={n:zf.read(n) for n in zf.namelist()}
    files['reference.json']=files['reference.json']+b'\n '
    with ZipFile(package,'w',compression=ZIP_DEFLATED) as zf:
        for n,b in files.items(): zf.writestr(n,b)
    with pytest.raises(ValueError,match='checksum mismatch'):
        inspect_reference_package(package)
