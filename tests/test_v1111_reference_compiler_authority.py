import json
import math
from pathlib import Path

import pytest

import src.reference_model as rm
from src.corner_coach_models import PhysicalCorner


def _lap(length=5200.0, lap_time=80.0):
    samples={}
    for i in range(int(length//5)+1):
        d=min(length,i*5.0)
        t=round(((lap_time*d/length)+0.35*math.sin(d/500.0))/0.0167)*0.0167
        samples[d]={
            "d":d,"t":max(0.0,t),"speed":386.0 if i%13==0 else 120.0,
            "throttle":1.0,"brake":0.0,"steering":0.0,"gear":8,
            "world_x":d,"world_y":0.0,"world_z":30.0*math.sin(d/220.0),"yaw":0.0,
        }
    return {"lap":2,"valid":True,"lap_time_s":lap_time,"track_length_m":length,"track_name":"TESTTRACK","_samples":samples}


def _meta(length=5200.0, lap_time=80.0):
    return {
        "source":"EA_F1_TIME_TRIAL_RIVAL","track_length_m":length,
        "reference_lap_time_s":lap_time,"sector1_time_s":26.0,
        "sector2_time_s":24.0,"sector3_time_s":30.0,
    }


def _one_corner(*args, **kwargs):
    return (PhysicalCorner(1,"T1",900.0,1000.0,1100.0,"LEFT",1.0),)


def test_bundle_overwrites_stale_model_with_current_compiler_and_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(rm,"physical_corners_from_reference",_one_corner)
    lap=_lap(); meta=_meta(); folder=tmp_path/"TESTTRACK"; folder.mkdir()
    (folder/"reference_model.json").write_text(json.dumps({"quality":{"quality_validator_version":3}}),encoding="utf-8")
    (folder/"coaching_zones.json").write_text("{}",encoding="utf-8")
    paths=rm.save_reference_bundle(lap,meta,root=tmp_path,track_name="TESTTRACK",raw_payload={"metadata":meta,"lap":lap})
    payload=json.loads(paths["model"].read_text(encoding="utf-8"))
    quality=payload["quality"]
    assert quality["quality_validator_version"] == rm.QUALITY_VALIDATOR_VERSION == 5
    assert quality["pace_compiler_version"] == rm.CLEAN_RIVAL_PACE_COMPILER_VERSION == 2
    assert quality["reference_compiler_id"] == rm.REFERENCE_COMPILER_ID
    assert quality["raw_reference_fingerprint"] == rm.raw_reference_fingerprint(lap,meta)
    assert payload["samples"][0]["d"] == pytest.approx(0.0)
    assert payload["samples"][0]["t"] == pytest.approx(0.0)
    assert payload["samples"][-1]["d"] == pytest.approx(lap["track_length_m"])
    assert payload["samples"][-1]["t"] == pytest.approx(lap["lap_time_s"])
    speeds=[row["speed"] for row in payload["samples"] if isinstance(row.get("speed"),(int,float))]
    assert max(speeds) <= rm.MAX_CLEAN_DERIVED_SPEED_KPH
    assert not (folder/"reference_model.json.stale").exists()
    assert not (folder/"coaching_zones.json.stale").exists()


def test_new_raw_capture_invalidates_old_model_if_compile_fails(tmp_path, monkeypatch):
    lap=_lap(); meta=_meta(); folder=tmp_path/"TESTTRACK"; folder.mkdir()
    (folder/"reference_model.json").write_text("old model",encoding="utf-8")
    (folder/"coaching_zones.json").write_text("old zones",encoding="utf-8")
    monkeypatch.setattr(rm,"compile_reference_model",lambda *a,**k: (_ for _ in ()).throw(ValueError("forced compile failure")))
    with pytest.raises(ValueError,match="forced compile failure"):
        rm.save_reference_bundle(lap,meta,root=tmp_path,track_name="TESTTRACK",raw_payload={"metadata":meta,"lap":lap})
    assert (folder/"rival_reference.json").exists()
    assert not (folder/"reference_model.json").exists()
    assert not (folder/"coaching_zones.json").exists()
    assert (folder/"reference_model.json.stale").exists()
    assert (folder/"coaching_zones.json.stale").exists()


def test_model_is_rejected_when_sibling_raw_recording_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(rm,"physical_corners_from_reference",_one_corner)
    lap=_lap(); meta=_meta()
    paths=rm.save_reference_bundle(lap,meta,root=tmp_path,track_name="TESTTRACK",raw_payload={"metadata":meta,"lap":lap})
    changed=json.loads(paths["raw"].read_text(encoding="utf-8"))
    changed["lap"]["lap_time_s"] += 0.250
    changed["metadata"]["reference_lap_time_s"] += 0.250
    paths["raw"].write_text(json.dumps(changed,indent=2),encoding="utf-8")
    with pytest.raises(ValueError,match="does not match sibling"):
        rm.load_reference_model(paths["model"])


def test_main_runtime_self_check_points_to_same_release_compiler():
    from src.main import _verify_reference_compiler_runtime
    ok,info=_verify_reference_compiler_runtime()
    assert ok is True
    assert "reference_model.py" in info
