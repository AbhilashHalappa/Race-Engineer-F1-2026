from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, PhysicalCorner, ReferenceTrace
from src.corner_coach_validation import CornerCoachValidationRecorder, analyze_validation_file


def _model():
    corners=(
        PhysicalCorner(1,"T1",100.0,150.0,200.0,"RIGHT",1.0),
        PhysicalCorner(2,"T2",300.0,350.0,400.0,"LEFT",1.0),
    )
    zones=(
        CoachingZone("Z1",100.0,200.0,50.0,(1,),brake_start_m=80.0,apex_m=150.0,reference_min_speed_kph=150.0,label="T1"),
        CoachingZone("Z2",300.0,400.0,250.0,(2,),brake_start_m=280.0,apex_m=350.0,reference_min_speed_kph=145.0,label="T2"),
    )
    samples=tuple({"d":float(d),"t":float(d)/50.0,"speed":180.0} for d in range(0,501,5))
    return ReferenceTrace(
        track_name="TEST",track_length_m=500.0,lap_time_s=10.0,step_m=5.0,
        samples=samples,physical_corners=corners,driving_events=(),coaching_zones=zones,
        metadata={"reference_compiler_id":"TEST_COMPILER","driver":"Test Rival"},
        quality={"quality_validator_version":5,"pace_compiler_version":2,"reference_trace_mode":"rival_pace","input_telemetry_trusted":False,"raw_reference_fingerprint":"abc123"},
    )


def test_validation_trace_is_self_contained_and_analyzable(tmp_path):
    rec=CornerCoachValidationRecorder(tmp_path, sample_step_m=10.0)
    model=_model()
    path=rec.ensure_run(session_uid=42,track_name="TEST",model=model)
    assert path is not None
    rec.begin_lap(3,distance_m=0.0,session_time_s=1.0)
    rec.state_transition("zone_enter",lap=3,distance_m=50.0,session_time_s=2.0,zone_id="Z1",label="T1",corner_ids=(1,))
    rec.state_transition("physical_corner_enter",lap=3,distance_m=100.0,session_time_s=3.0,corner_id=1,label="T1")
    rec.sample(lap=3,distance_m=100.0,session_time_s=3.0,lap_time_s=2.0,delta_s=0.10,active_zone_id="Z1",physical_corner_id=1)
    rec.pre_decision(lap=3,zone_id="Z1",event="pre_emit",distance_m=60.0,session_time_s=2.2,text="Turn 1 coming up")
    rec.post_decision(lap=3,zone_id="Z1",event="post_emit",distance_m=220.0,session_time_s=4.5,diagnosis={"net_loss_s":0.12})
    msg=SimpleNamespace(key="corner:pre:3:Z1",text="Turn 1 coming up",priority="COACHING")
    rec.radio_submit(msg); rec.audio_start(msg)
    rec.finish_lap(reason="test",zone_attribution={"reconciliation_error_s":0.005},distance_status={"available":True},first_delta_s=0.0,last_delta_s=0.2)
    assert rec.flush(2.0)

    lines=[json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()]
    run=next(x for x in lines if x["event"]=="run_start")
    assert run["reference_fingerprint"]=="abc123"
    assert run["reference_checks"]["physical_corner_ids_sequential"] is True
    assert [x["corner_id"] for x in run["physical_corners"]]==[1,2]
    summary=next(x for x in lines if x["event"]=="lap_summary")
    assert summary["stats"]["pre_emitted"]==["Z1"]
    assert summary["stats"]["post_emitted"]==["Z1"]
    assert summary["checks"]["generated_not_spoken_at_lap_close"]==[]
    assert summary["checks"]["reconciliation_within_20ms"] is True

    report=analyze_validation_file(path)
    assert report["track_name"]=="TEST"
    assert report["physical_corner_count"]==2
    assert report["coaching_zone_count"]==2
    assert report["event_counts"]["audio_start"]==1
    rec.close()


def test_validation_trace_detects_generated_corner_radio_not_heard(tmp_path):
    rec=CornerCoachValidationRecorder(tmp_path)
    rec.ensure_run(session_uid=43,track_name="TEST",model=_model())
    rec.begin_lap(1,distance_m=0.0,session_time_s=0.0)
    msg=SimpleNamespace(key="corner:post:1:Z1:measured_loss",text="Turn 1 lost time",priority="COACHING")
    rec.radio_submit(msg)
    rec.finish_lap(reason="test")
    rec.flush(2.0)
    rows=[json.loads(x) for x in rec.path.read_text(encoding="utf-8").splitlines()]
    summary=next(x for x in rows if x["event"]=="lap_summary")
    assert summary["checks"]["generated_not_spoken_at_lap_close"]==[
        {"message_key":"corner:post:1:Z1","submitted":1,"audio_started":0}
    ]
    assert analyze_validation_file(rec.path)["generated_not_spoken"]==[
        {"message_key":"corner:post:1:Z1","submitted":1,"audio_started":0}
    ]
    rec.close()


def test_pace_only_diagnosis_never_uses_raw_ghost_brake_or_speed():
    engine=CornerCoachEngine()
    zone=CoachingZone(
        "Z1",100.0,200.0,50.0,(1,),brake_start_m=80.0,brake_release_m=140.0,
        apex_m=150.0,throttle_start_m=160.0,reference_min_speed_kph=150.0,label="T1",
    )
    # Clean compiled pace says 200 kph at zone exit.
    engine.reference_model=ReferenceTrace(
        "TEST",500.0,10.0,5.0,
        ({"d":0.0,"t":0.0,"speed":200.0},{"d":200.0,"t":4.0,"speed":200.0},{"d":500.0,"t":10.0,"speed":200.0}),
        (),(),(zone,),quality={"input_telemetry_trusted":False},
    )
    engine._reference_samples=engine.reference_model.samples
    engine._reference_distances=tuple(float(x["d"]) for x in engine._reference_samples)

    # Raw rival ghost is intentionally absurd. It must not influence diagnosis.
    reference={"_samples":{
        "100":{"d":100.0,"speed":999.0,"brake":1.0},
        "150":{"d":150.0,"speed":999.0,"brake":1.0},
        "200":{"d":200.0,"speed":999.0,"brake":1.0},
    }}
    current={"_samples":{
        "100":{"d":100.0,"speed":180.0,"brake":0.6},
        "150":{"d":150.0,"speed":145.0,"brake":0.3},
        "200":{"d":200.0,"speed":190.0,"brake":0.0},
    }}
    perf={
        "input_telemetry_trusted":False,
        "points":[
            {"distance_m":50.0,"delta_s":0.0},
            {"distance_m":100.0,"delta_s":0.02},
            {"distance_m":150.0,"delta_s":0.06},
            {"distance_m":200.0,"delta_s":0.12},
        ],
        "turns":[],
    }
    diag=engine._diagnose(zone,current,reference,perf)
    assert diag.measurements["peak_brake_delta"] is None
    # Uses compiled 200 kph reference, not raw 999 kph ghost speed.
    assert diag.measurements["exit_speed_delta_kph"] == -10.0
    assert diag.measurements["brake_point_delta_m"] is None
    engine.validation.close()
