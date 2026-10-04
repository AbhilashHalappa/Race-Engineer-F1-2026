from __future__ import annotations

import json
from types import SimpleNamespace as NS

import pytest

from src.coaching_zones import _zone_from_group
from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, Diagnosis, DrivingEvent, PhysicalCorner, ReferenceTrace
from src.corner_coach_validation import CornerCoachValidationRecorder
from src.engineer.models import EngineerMessage, Priority
from src.tts import SpeechOutput


def _model():
    corner=PhysicalCorner(1,"T1",100.0,150.0,200.0,"RIGHT",1.0)
    zone=CoachingZone("Z1",100.0,200.0,80.0,(1,),brake_start_m=80.0,apex_m=150.0,reference_min_speed_kph=150.0,label="T1")
    samples=tuple({"d":float(d),"t":float(d)/50.0,"speed":180.0} for d in range(0,501,5))
    return ReferenceTrace("TEST",500.0,10.0,5.0,samples,(corner,),(),(zone,),metadata={},quality={"input_telemetry_trusted":False})


def test_corner_coach_pre_and_post_get_dedicated_radio_priority():
    pre=EngineerMessage("corner:pre:2:Z1",Priority.COACHING,"pre",1.0)
    post=EngineerMessage("corner:post:1:Z1:min_speed_low",Priority.COACHING,"post",1.0)
    ordinary=EngineerMessage("coach:positive:1:T1",Priority.COACHING,"ordinary",1.0)
    assert SpeechOutput._radio_rank(pre) == -2
    assert SpeechOutput._radio_rank(post) == 0
    assert SpeechOutput._radio_rank(ordinary) == 4
    assert SpeechOutput._replaceable_family(pre.key) == "corner:pre:Z1"
    assert SpeechOutput._replaceable_family(post.key) == "corner:post:Z1"


def test_zone_event_association_does_not_reuse_previous_corner_deceleration():
    group=[
        PhysicalCorner(13,"T13",4565.0,4620.0,4690.0,"LEFT",1.0),
        PhysicalCorner(14,"T14",4700.0,4800.0,4910.0,"RIGHT",1.0),
    ]
    events=(
        DrivingEvent("E_T12","deceleration",4325.0,4390.0,4350.0,-0.5,confidence=0.9,metadata={"corner_id":12}),
        DrivingEvent("E_T13","deceleration",4530.0,4620.0,4570.0,-0.4,confidence=0.9,metadata={"corner_id":13}),
        DrivingEvent("E_MIN13","minimum_speed",4620.0,4620.0,4620.0,150.0,confidence=0.9,metadata={"corner_id":13}),
    )
    samples=tuple({"d":float(d),"t":d/60.0,"speed":200.0} for d in range(4300,5001,5))
    zone=_zone_from_group(10,group,events,samples,4470.0,5276.0)
    assert zone.brake_start_m == pytest.approx(4530.0)
    assert "E_T12" not in zone.event_ids
    assert "E_T13" in zone.event_ids
    assert zone.approach_start_m <= zone.start_m


def test_zone_approach_never_begins_after_physical_corner_start():
    group=[PhysicalCorner(8,"T8",2785.0,2860.0,2985.0,"RIGHT",1.0)]
    events=(DrivingEvent("E20","deceleration",2795.0,2850.0,2820.0,-0.2,confidence=0.9,metadata={"corner_id":8}),)
    samples=tuple({"d":float(d),"t":d/70.0,"speed":280.0} for d in range(2700,3051,5))
    zone=_zone_from_group(6,group,events,samples,2320.0,5276.0)
    assert zone.approach_start_m == pytest.approx(2785.0)


def test_exact_sf_finalization_closes_last_straight_and_reconciles():
    model=_model(); engine=CornerCoachEngine(); engine.validation.close()
    engine.reference_model=model
    engine._reference_samples=model.samples
    engine._reference_distances=tuple(float(r["d"]) for r in model.samples)
    engine._performance_boundaries=({"corner_id":1,"label":"T1","start_m":100.0,"end_m":200.0},)
    rows=[(0.0,0.0),(80.0,0.10),(100.0,0.12),(200.0,0.20),(490.0,0.40)]
    engine._live_points=[{"distance_m":d,"delta_s":delta} for d,delta in rows]
    engine._live_point_distances=[d for d,_ in rows]
    engine._first_delta_s=0.0; engine._last_delta_s=0.40; engine._last_perf_distance=490.0
    engine._complete_incremental_regions(model,490.0)
    assert not any(x["segment_kind"]=="straight" and x["end_m"]==500.0 for x in engine._live_segments)
    assert engine._finalize_lap_boundary(model,10.5) is True
    assert engine._live_point_distances[-1] == pytest.approx(500.0)
    assert engine._live_points[-1]["current_time_s"] == pytest.approx(10.5)
    assert any(x["segment_kind"]=="straight" and x["end_m"]==500.0 for x in engine._live_segments)
    assert engine._zone_attribution["reconciliation_error_s"] == pytest.approx(0.0,abs=1e-12)


def test_circular_pre_is_carried_into_next_lap_without_duplicate(tmp_path, monkeypatch):
    model=_model(); engine=CornerCoachEngine()
    engine.validation.close(); engine.validation=CornerCoachValidationRecorder(tmp_path)
    monkeypatch.setattr(engine,"_ensure_reference",lambda *a,**k:model)

    class Recorder:
        reference_mode="external"; external_reference_meta={};
        def current_reference_lap(self): return {"_samples":{}}
        def current_lap_trace_snapshot(self,state): return {"_samples":{}}
    rec=Recorder()
    def state(lap,d,lap_time,prev=None):
        return NS(
            session=NS(track=NS(name="TEST"),uid=123,session_time_s=lap_time,total_laps=3,ended=False),
            player=NS(
                lap=NS(current_lap=lap,lap_distance_m=d,current_lap_time_s=lap_time,previous_lap_time_s=prev,lap_valid=True,result_status=NS(raw=2)),
                telemetry=NS(speed_kph=100.0,brake=0.0,steering=0.0,throttle=1.0,gear=6),
            ),
        )
    out=engine.observe(rec,state(1,470.0,9.4),100.0)
    assert [m.key for m in out] == ["corner:pre:2:Z1"]
    assert "Z1" in engine._next_lap_pre_spoken
    out2=engine.observe(rec,state(2,10.0,0.2,10.0),101.0)
    assert not any(m.key.startswith("corner:pre:2:Z1") for m in out2)
    assert "Z1" in engine._pre_spoken
    engine.validation.flush(); engine.validation.close()


def test_validation_attributes_circular_pre_radio_to_target_lap(tmp_path):
    model=_model(); rec=CornerCoachValidationRecorder(tmp_path)
    rec.ensure_run(session_uid=1,track_name="TEST",model=model)
    rec.begin_lap(1,distance_m=470.0)
    rec.pre_decision(lap=1,zone_id="Z1",event="pre_emit_next_lap",target_lap=2,circular=True)
    msg=EngineerMessage("corner:pre:2:Z1",Priority.COACHING,"T1 coming up",1.0)
    rec.radio_submit(msg); rec.audio_start(msg)
    rec.finish_lap(reason="lap_advanced")
    rec.begin_lap(2,distance_m=5.0)
    rec.finish_lap(reason="test")
    rec.flush(); path=rec.path; rec.close()
    rows=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    lap2=next(r for r in rows if r.get("event")=="lap_summary" and r.get("lap")==2)
    assert "Z1" in lap2["stats"]["pre_emitted"]
    assert lap2["checks"]["generated_not_spoken_at_lap_close"] == []


def test_final_lap_wrap_detection_and_wording():
    assert CornerCoachEngine._distance_wrapped(5270.0,2.0,5276.0)
    assert CornerCoachEngine._is_final_lap(NS(total_laps=5,ended=False),NS(current_lap=5,result_status=NS(raw=2)))
    z=CoachingZone("Z1",100,200,80,(1,),label="T1")
    d=Diagnosis("Z1","T1",0.2,"min_speed_low","minimum speed was about 5 kph lower",0.9,{}, {})
    text=CornerCoachEngine._post_text(z,d)
    assert "Your minimum speed" in text
    assert "You minimum speed" not in text
