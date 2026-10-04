import json
from pathlib import Path
import pytest

from src.reference_model import save_reference_bundle, validate_capture_lap


def _raw_lap_without_geometry():
    length=5000.0
    samples={}
    # Dense, complete, monotonic old-style capture. No world geometry on purpose
    # so strict model compilation has a reason to fail after persistence.
    for i in range(1001):
        d=i*5.0
        t=80.0*d/length
        samples[d]={
            "d":d,"t":t,"speed":225.0,
            "throttle":1.0,"brake":0.0,"steering":0.0,
        }
    return {
        "lap":2,"valid":True,"sample_count":len(samples),
        "lap_time_s":80.0,"track_length_m":length,"track_name":"MELBOURNE",
        "_samples":samples,
    }


def test_capture_validator_is_legacy_v1105_gate():
    lap=_raw_lap_without_geometry()
    # Add world geometry only for the legacy capture gate.
    for d,row in lap["_samples"].items():
        row["world_x"]=d
        row["world_z"]=0.0
    quality=validate_capture_lap(lap,{"track_length_m":5000.0})
    assert quality["accepted"] is True
    assert quality["reasons"] == []


def test_raw_reference_is_persisted_before_compiler_failure(tmp_path):
    lap=_raw_lap_without_geometry()
    meta={"source":"EA_F1_TIME_TRIAL_RIVAL","reference_lap_time_s":80.0,"track_length_m":5000.0}
    payload={"metadata":meta,"lap":lap}
    with pytest.raises(ValueError):
        save_reference_bundle(lap,meta,root=tmp_path,track_name="MELBOURNE",raw_payload=payload)
    raw=tmp_path/"MELBOURNE"/"rival_reference.json"
    assert raw.exists()
    saved=json.loads(raw.read_text(encoding="utf-8"))
    assert saved["lap"]["lap_time_s"] == 80.0
