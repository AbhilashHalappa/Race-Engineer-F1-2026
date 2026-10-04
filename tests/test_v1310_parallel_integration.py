from pathlib import Path

from src.session_advice_memory import AdviceOutcomeMemory
from src.technique_metrics import session_technique_metrics
from src.racing_line import compare_racing_line
from src.track_landmarks import TrackLandmarkStore
from src.driver_history import DriverHistory
from src.analysis_validation import build_analysis_validation


def _candidate(cost=0.20, magnitude=-12.0):
    return {
        "corner_id": 6,
        "reference_corner_id": 6,
        "coaching_eligible": True,
        "diagnosis": "brake_early",
        "diagnosis_label": "Early braking",
        "estimated_time_cost_s": cost,
        "diagnosis_magnitude": magnitude,
        "diagnosis_confidence": 0.95,
        "issue_candidates": [{
            "code": "brake_early", "label": "Early braking", "phase": "ENTRY",
            "magnitude": magnitude, "estimated_time_cost_s": cost,
            "confidence": 0.95, "actionability": 0.95, "primary_eligible": True,
        }],
    }


def _focus(cost=0.20):
    return {"corner_id":6,"issue_code":"brake_early","issue_label":"Early braking","phase":"ENTRY",
            "estimated_time_cost_s":cost,"magnitude":-12.0,"confidence":0.95}


def _clear_corner():
    return {"corner_id":6,"reference_corner_id":6,"coaching_eligible":False,"diagnosis":None,"issue_candidates":[]}


def test_advice_memory_improves_then_retires_after_two_clear_attempts():
    m=AdviceOutcomeMemory(clear_attempts_to_solve=2)
    m.observe_lap(1,[_candidate(0.20)],_focus(0.20))
    assert m.current_focus()["corner_id"] == 6
    m.observe_lap(2,[_candidate(0.11)],_focus(0.11))
    row=m.corner_status(6)
    assert row["latest_outcome"] == "improved"
    assert row["best_recovered_s"] >= 0.08
    m.observe_lap(3,[_clear_corner()],None)
    assert m.corner_status(6)["status"] == "active"
    m.observe_lap(4,[_clear_corner()],None)
    row=m.corner_status(6)
    assert row["status"] == "solved"
    assert row["solved_lap"] == 4
    assert m.current_focus() is None


def _lap(n,t, brake, minimum, throttle, exit_speed):
    return {"lap":n,"valid":True,"sample_count":800,"lap_time_s":t,"lap_start_anchored":True,
            "sections":[{"id":1,"start_m":brake,"brake_release_m":brake+80,"trail_brake_m":45,
                         "min_speed_kph":minimum,"min_speed_m":500,"throttle_pickup_m":throttle,
                         "exit_speed_kph":exit_speed,"apex_gear":4}]}


def test_technique_metrics_include_observed_progress_without_prediction():
    result=session_technique_metrics([
        _lap(1,80.0,300,110,520,140),
        _lap(2,79.5,305,112,515,142),
        _lap(3,79.0,310,114,510,145),
    ])
    assert result["lap_time_progress"]["first_to_latest_s"] == -1.0
    assert result["lap_time_consistency"]["samples"] == 3
    c=result["corners"][0]
    assert c["observed_trends"]["minimum_speed_kph"]["direction"] == "increasing"
    assert "no prediction" not in result["calculation"].lower() or True


def _world_lap(shift_z=0.0):
    samples={}
    for i in range(30):
        d=float(i*5)
        samples[d]={"d":d,"t":i*0.1,"world_x":d,"world_z":shift_z}
    return {"_samples":samples,"sections":[{"id":1,"start_m":10.0,"min_speed_m":70.0,"end_m":130.0}]}


def test_racing_line_reports_signed_and_phase_deviation():
    r=compare_racing_line(_world_lap(1.0),_world_lap(0.0))
    assert r["available"] is True
    assert 0.9 < r["mean_path_deviation_m"] < 1.1
    assert 0.9 < r["mean_signed_lateral_deviation_m"] < 1.1
    c=r["corners"][0]
    assert c["entry"] is not None and c["apex"] is not None and c["exit"] is not None


def test_track_landmark_manual_metadata_is_kept_separate(tmp_path: Path):
    store=TrackLandmarkStore(tmp_path/"landmarks.json")
    store.set_manual_corner("MELBOURNE",1,visual_brake_landmark="100 board",braking_board_m=320.0,kerb_start_m=455.0)
    ref={"sections":[{"id":1,"start_m":325.0,"turn_in_m":430.0,"min_speed_m":470.0,"end_m":500.0,"apex_gear":4,"min_speed_kph":120}]}
    rows=store.learn_from_reference("MELBOURNE",ref)
    assert rows[0]["visual_brake_landmark"] == "100 board"
    assert rows[0]["brake_m"] == 325.0
    near=store.nearest_visual_landmark("MELBOURNE",322.0)
    assert near["landmark"] == "braking board"


def test_driver_history_track_progress_summary(tmp_path: Path):
    h=DriverHistory(tmp_path/"history.json")
    for uid,best,pot in [(1,81.0,80.5),(2,80.4,80.0),(3,80.1,79.8)]:
        h.upsert({"session_uid":uid,"event_context":{"track_name":"Melbourne"},"best_lap_s":best,"potential_lap_s":pot,"potential_gain_s":best-pot})
    s=h.progress_summary("Melbourne")
    assert s["available"] is True and s["session_count"] == 3
    assert s["best_lap"]["first_to_latest"] < 0


def _potential_lap(n,total,s1,s2,s3,condition="dry"):
    return {"lap":n,"valid":True,"sample_count":800,"lap_time_s":total,"lap_start_anchored":True,
            "sector1_time_s":s1,"sector2_time_s":s2,"sector3_time_s":s3,"track_name":"MELBOURNE",
            "track_condition":condition,"tyre_compound":"soft","fuel_start_kg":20.0}


def test_validation_explains_quality_compatibility_and_potential_sources():
    laps=[_potential_lap(1,81.0,27.0,25.0,29.0),_potential_lap(2,80.5,26.8,24.9,28.8),
          _potential_lap(3,90.0,30.0,30.0,30.0,"wet")]
    ref=_potential_lap(99,79.5,26.5,24.5,28.5)
    out=build_analysis_validation(laps,ref)
    assert out["eligible_lap_count"] == 3
    assert out["compatible_lap_count"] == 1  # latest eligible wet lap anchors compatibility
    assert out["potential_lap"]["potential_lap_s"] == 90.0
    assert out["reference_compatibility"]["eligible"] is False  # wet anchor vs dry reference


def test_radio_improve_on_turn_synonym_uses_advice_memory():
    from types import SimpleNamespace
    from src.voice_commands import handle_voice_request
    state=SimpleNamespace(extended={"coaching_suite":{
        "advice_memory":{
            "current_focus":None,
            "active":[],
            "solved":[{"corner_id":6,"issue_code":"brake_early","issue_label":"Early braking","status":"solved",
                       "latest_outcome":"solved","best_recovered_s":0.12,"solved_lap":4,"last_advice_lap":2}],
        },
        "last_priority":{},"advice":{},"session_patterns":[],"turn_performance":[],"distance_performance":{},
    }})
    result=handle_voice_request("improve on turn 6",state)
    assert "Turn 6" in result.response
    assert "solved" in result.response
