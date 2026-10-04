import json
import math
from pathlib import Path

import pytest

from src.reference_model import (
    CLEAN_RIVAL_PACE_COMPILER_VERSION,
    compile_reference_model,
    load_reference_model,
    sanitize_rival_pace_reference,
    to_dict,
)


def _quantized_rival_lap(length=5200.0, lap_time=80.0):
    # Synthetic 5 m pace trace with packet-like timing quantization that would
    # create impossible speeds if differentiated one bin at a time.
    samples={}
    n=int(length//5)
    for i in range(n+1):
        d=min(length,i*5.0)
        # Smooth underlying pace plus coarse 16.7 ms packet clock quantization.
        base=(lap_time*d/length) + 0.55*math.sin(d/430.0)
        t=round(base/0.0167)*0.0167
        samples[d]={
            "d":d,"t":max(0.0,t),"speed":374.0 if i%11==0 else 110.0,
            "throttle":1.0,"brake":0.0,"steering":0.0,"gear":1,
            "world_x":d,"world_y":0.0,"world_z":40.0*math.sin(d/250.0),"yaw":0.0,
        }
    return {
        "lap":2,"valid":True,"lap_time_s":lap_time,"track_length_m":length,
        "track_name":"TESTTRACK","_samples":samples,
    }


def _meta(length=5200.0, lap_time=80.0):
    return {
        "source":"EA_F1_TIME_TRIAL_RIVAL",
        "track_length_m":length,
        "reference_lap_time_s":lap_time,
        "sector1_time_s":25.0,"sector2_time_s":24.0,"sector3_time_s":31.0,
    }


def test_clean_pace_compiler_removes_ghost_inputs_and_spikes():
    lap=_quantized_rival_lap(); meta=_meta()
    clean=sanitize_rival_pace_reference(lap,meta)
    assert clean["pace_compiler_version"] == CLEAN_RIVAL_PACE_COMPILER_VERSION
    assert clean["input_telemetry_trusted"] is False
    assert clean["speed_source"] == "local_regression_of_clean_time_distance_curve"
    rows=list(clean["_samples"].values())
    assert rows[0]["t"] == pytest.approx(0.0,abs=1e-9)
    assert rows[-1]["t"] == pytest.approx(80.0,abs=1e-9)
    assert all(b["t"]>a["t"] for a,b in zip(rows,rows[1:]))
    assert all("brake" not in r and "throttle" not in r and "steering" not in r and "gear" not in r for r in rows)
    speeds=[r["speed"] for r in rows if isinstance(r.get("speed"),(int,float))]
    assert speeds and max(speeds) <= 390.0
    assert min(speeds) >= 20.0


def test_clean_pace_curve_is_sector_and_lap_anchored():
    lap=_quantized_rival_lap(); meta=_meta()
    clean=sanitize_rival_pace_reference(lap,meta)
    rows=sorted((float(k),v) for k,v in clean["_samples"].items())
    ds=[d for d,_ in rows]
    def t_at(x):
        import bisect
        i=bisect.bisect_left(ds,x)
        if i<=0:return float(rows[0][1]["t"])
        if i>=len(rows):return float(rows[-1][1]["t"])
        d0,a=rows[i-1];d1,b=rows[i]
        return float(a["t"])+(float(b["t"])-float(a["t"]))*(x-d0)/(d1-d0)
    anchors=clean["pace_anchors"]
    assert len(anchors) == 4
    for anchor in anchors:
        assert t_at(float(anchor["distance_m"])) == pytest.approx(float(anchor["time_s"]),abs=0.010)


def test_compiled_clean_pace_model_has_exact_finish_and_strict_quality(monkeypatch):
    # Keep this test about timing/pace; geometry authority is tested elsewhere.
    import src.reference_model as rm
    monkeypatch.setattr(rm,"physical_corners_from_reference",lambda *a,**k: ())
    lap=_quantized_rival_lap(); meta=_meta()
    model=compile_reference_model(lap,meta,track_name="TESTTRACK",require_quality=False)
    assert model.samples[0]["d"] == pytest.approx(0.0)
    assert model.samples[0]["t"] == pytest.approx(0.0)
    assert model.samples[-1]["d"] == pytest.approx(lap["track_length_m"])
    assert model.samples[-1]["t"] == pytest.approx(lap["lap_time_s"])
    assert model.quality["clean_pace_physics_consistent"] is True
    assert model.quality["timing_anchor_max_error_s"] <= 0.010
    assert model.quality["speed_time_error_ratio"] <= 0.03
    assert model.quality["speed_distance_error_ratio"] <= 0.03


def test_stale_compiled_rival_model_is_rejected(tmp_path):
    payload={
        "track_name":"MELBOURNE","track_length_m":5276.0,"lap_time_s":76.435,"step_m":5.0,
        "samples":[{"d":0.0,"t":0.0,"speed":280.0},{"d":5276.0,"t":76.435,"speed":280.0}],
        "physical_corners":[{"corner_id":i,"label":f"T{i}","start_m":i*100.0,"apex_m":i*100.0+20,"end_m":i*100.0+40,"direction":"LEFT","curvature_score":1.0} for i in range(1,15)],
        "driving_events":[],"coaching_zones":[],
        "metadata":{"source":"EA_F1_TIME_TRIAL_RIVAL"},
        "quality":{"reference_trace_mode":"rival_pace","input_telemetry_trusted":False},
    }
    p=tmp_path/"reference_model.json"; p.write_text(json.dumps(payload),encoding="utf-8")
    with pytest.raises(ValueError,match="predates clean pace compiler"):
        load_reference_model(p)
