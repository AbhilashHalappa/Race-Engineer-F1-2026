from pathlib import Path

from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, Diagnosis
from src.performance_scoring import build_live_corner_score_from_diagnosis, score_grade, ScoreStatus
from src.radio_controls import parse_runtime_radio_command


def _diag(**measurements):
    return Diagnosis(
        zone_id="Z4", public_label="T4", net_loss_s=0.18,
        primary_code="brake_early", primary_text="braked about 10 metres early",
        confidence=0.9, measurements={"dominant_corner":4, **measurements},
        phase_losses_s={"approach":0.08,"entry":0.06,"exit":0.04},
    )


def test_live_corner_score_is_downstream_of_existing_diagnosis_measurements():
    score=build_live_corner_score_from_diagnosis(_diag(
        brake_point_delta_m=-10.0,min_speed_delta_kph=-5.0,
        throttle_pickup_delta_s=0.20,exit_speed_delta_kph=-4.0,
    ))
    assert score.status is ScoreStatus.AVAILABLE
    assert score.corner_id == 4
    assert 0.0 <= score.score <= 100.0
    assert score.sample_count >= 4
    assert score.dimensions["braking_point"].evidence[0].source == "CornerCoach.Diagnosis"


def test_live_corner_score_missing_measurements_stays_na():
    score=build_live_corner_score_from_diagnosis(_diag())
    assert score.status is ScoreStatus.NOT_AVAILABLE
    assert score.score is None
    assert score_grade(score.score) == "N/A"


def test_grade_boundaries_are_stable():
    assert score_grade(95)=="EXCELLENT"
    assert score_grade(82)=="GOOD"
    assert score_grade(70)=="FAIR"
    assert score_grade(50)=="NEEDS WORK"


def test_track_learning_is_instructional_not_reference_judgment():
    z=CoachingZone(
        zone_id="Z4", label="T4", corner_ids=(4,),
        approach_start_m=900.0,start_m=1000.0,end_m=1100.0,apex_m=1050.0,
        brake_start_m=980.0,brake_release_m=1030.0,throttle_start_m=1060.0,
        full_throttle_m=1090.0,reference_min_speed_kph=142.0,reference_gear=4,
    )
    text=CornerCoachEngine._track_learning_pre_text(z,120.0)
    assert "Turn 4" in text and "120 metres" in text and "gear 4" in text and "142" in text
    assert "reference" not in text.lower()


def test_performance_coach_radio_alias_replaces_speed_coach_name():
    cmd=parse_runtime_radio_command("enable performance coach")
    assert cmd is not None and cmd.target == "SPEED" and cmd.value is True


def test_control_center_uses_full_overlay_names():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    for label in ("Race Engineer","Replay Controls","Radio Transcript","Driver Inputs","Reference Inputs","Performance Coach"):
        assert f'"{label}"' in text
    assert "self.setWindowTitle('PERFORMANCE COACH')" in text


def test_dedicated_live_corner_feedback_overlay_is_present_and_user_armed():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "class LiveCornerFeedbackOverlayWindow" in text
    assert '"LCF", "Live Corner Feedback"' in text
    assert "self._live_corner_feedback_armed = False" in text
    assert "def show_live_corner_feedback" in text
    assert "def hide_live_corner_feedback" in text
    assert "self._live_corner_feedback_armed = True" in text
    assert "self._live_corner_feedback_armed = False" in text


def test_live_corner_feedback_uses_existing_result_and_does_not_create_speech():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    block=text[text.index("class LiveCornerFeedbackOverlayWindow"):text.index("class CornerCoachTranscriptPanel")]
    assert "live_corner_result" in block
    assert "BRAKING POINT" in block
    assert "MIN CORNER SPEED" in block
    assert "THROTTLE PICKUP" in block
    assert "EXIT SPEED" in block
    assert "EngineerMessage(" not in block
    assert "speak(" not in block


def test_live_corner_feedback_stays_open_between_results():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    start=text.index("if self._live_corner_feedback_armed:")
    block=text[start:start+1400]
    assert "self.live_corner_feedback.set_result(None)" in block
    assert "self.live_corner_feedback.hide()" not in block
    assert "if not self.live_corner_feedback.isVisible():" in block

def test_live_corner_feedback_has_all_selectable_requested_metrics():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    block=text[text.index("class LiveCornerFeedbackOverlayWindow"):text.index("class CornerCoachTranscriptPanel")]
    for label in ("HITTING APEX","MIN CORNER SPEED","TRAIL BRAKING","THROTTLE POINTS","BRAKE POINTS"):
        assert label in block
    assert "metric_selector=QComboBox" in block


def test_live_corner_feedback_publishes_at_first_exit_sample_not_post_voice_delay():
    text=Path("src/corner_coach.py").read_text(encoding="utf-8")
    start=text.index("# V2.0.1 LIVE CORNER INTELLIGENCE")
    end=text.index("# POST is generated",start)
    block=text[start:end]
    assert "if after < 0.0:continue" in block
    assert "if after < self.POST_MIN_AFTER_M:continue" not in block


def test_live_result_exposes_requested_metric_evidence():
    text=Path("src/corner_coach.py").read_text(encoding="utf-8")
    block=text[text.index("def _publish_v201_corner_result"):text.index("def status",text.index("def _publish_v201_corner_result"))]
    for key in ("brake_release_delta_m","apex_position_delta_m","apex_speed_delta_kph"):
        assert key in block

def test_live_feedback_is_per_physical_corner_not_multi_turn_zone():
    text=Path("src/corner_coach.py").read_text(encoding="utf-8")
    start=text.index("# V2.0.1 LIVE CORNER INTELLIGENCE")
    end=text.index("# POST is generated",start)
    block=text[start:end]
    assert "self._performance_boundaries" in block
    assert 'score_key=f"T{int(cid)}"' in block
    assert "corner_end=boundary.get(\"end_m\")" in block
    assert "self._live_physical_corner_zone" in block
    assert "for z in zones:" not in block


def test_na_metric_disables_bar_and_does_not_draw_fake_center_marker():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    block=text[text.index("class LiveCornerFeedbackOverlayWindow"):text.index("class CornerCoachTranscriptPanel")]
    assert "NO VALID BRAKE POINT DATA" in block
    assert "NO VALID APEX DATA" in block
    assert "if available:" in block
    assert "omit the marker entirely" in block


def test_corner_performance_bar_uses_score_and_time_loss_is_separate():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    block=text[text.index("class LiveCornerFeedbackOverlayWindow"):text.index("class CornerCoachTranscriptPanel")]
    assert "'CORNER PERFORMANCE','NEEDS WORK','EXCELLENT',score,0.0,100.0" in block
    assert "LOST" in block and "GAINED" in block and "MATCHED REFERENCE" in block


def test_live_physical_corner_geometry_does_not_require_dominant_loss():
    text=Path("src/corner_coach.py").read_text(encoding="utf-8")
    block=text[text.index("geometry_metrics={}"):text.index("geometry_conf=", text.index("geometry_metrics={}"))]
    assert 'str(zone.zone_id).startswith("LIVE_T")' in block
    assert "geometry_corner_id=zone.corner_ids[0]" in block


def test_short_live_corner_can_measure_path_apex_from_five_samples():
    from src.corner_geometry_metrics import path_curvature_apex
    rows=[
        {"d":0.0,"world_x":0.0,"world_z":0.0},
        {"d":5.0,"world_x":5.0,"world_z":0.0},
        {"d":10.0,"world_x":9.0,"world_z":2.0},
        {"d":15.0,"world_x":11.0,"world_z":6.0},
        {"d":20.0,"world_x":11.0,"world_z":11.0},
    ]
    apex,curv,conf=path_curvature_apex(rows,0.0,20.0,fallback_m=10.0)
    assert apex is not None and curv is not None and conf>=0.58


def test_apex_position_delta_is_not_faked_from_physical_fallback():
    text=Path("src/corner_geometry_metrics.py").read_text(encoding="utf-8")
    block=text[text.index("def compare_corner"):text.index("# Public alias",text.index("def compare_corner"))]
    assert 'result["apex_m_delta"]=None' in block
    assert 'result["apex_position_trusted"]' in block


def test_hitting_apex_uses_lower_confidence_min_speed_location_fallback():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    block=text[text.index("class LiveCornerFeedbackOverlayWindow"):text.index("class LapStintSummaryPanel")]
    assert "apex_estimate_delta_m" in block
    assert "apex_estimate_trusted" in block
    assert "min_speed_location" in block


def test_geometry_compare_exports_apex_proxy_without_faking_path_apex():
    text=Path("src/corner_geometry_metrics.py").read_text(encoding="utf-8")
    block=text[text.index("def compare_corner"):text.index("# Public alias",text.index("def compare_corner"))]
    assert 'result["apex_m_delta"]=None' in block
    assert 'result["apex_estimate_delta_m"]' in block
    assert '"min_speed_location"' in block


def test_live_action_text_translates_dominant_diagnosis_not_score():
    d=_diag(brake_point_delta_m=-12.0)
    assert CornerCoachEngine._live_action_text(d)=="BRAKE ~12 m LATER"
    d2=Diagnosis(zone_id="Z4",public_label="T4",net_loss_s=0.2,primary_code="throttle_late",primary_text="throttle late",confidence=.9,measurements={"throttle_pickup_delta_s":.18},phase_losses_s={})
    assert CornerCoachEngine._live_action_text(d2)=="PICK UP THROTTLE ~0.18 s EARLIER"

def test_live_result_publishes_one_action_text():
    text=Path("src/corner_coach.py").read_text(encoding="utf-8")
    block=text[text.index("def _publish_v201_corner_result"):text.index("def status",text.index("def _publish_v201_corner_result"))]
    assert '"action_text":self._live_action_text(diag)' in block

def test_corner_performance_overlay_has_single_work_on_action_line():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    block=text[text.index("class LiveCornerFeedbackOverlayWindow"):text.index("class LapStintSummaryPanel")]
    assert "WORK ON:" in block
    assert "KEEP:" in block
    assert "action_text" in block
    assert "HEIGHT=204" in block
