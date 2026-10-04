from types import SimpleNamespace

from src.race_state.models import RaceState
from src.voice_commands import handle_voice_request, VoiceIntent
import src.session_coach_report as report_mod


def _state():
    s = RaceState()
    s.extended["coaching_suite"] = {
        "last_priority": {"selected_focus": {"corner_id": 6, "issue_label": "Early braking", "estimated_time_cost_s": .22}},
        "advice": {
            "6": {"corner_id": 6, "diagnosis": "brake_early", "diagnosis_label": "Early braking", "estimated_time_cost_s": .22, "reference_brake_m": 1820.0},
            "9": {"corner_id": 9, "diagnosis": "throttle_late", "diagnosis_label": "Late throttle", "estimated_time_cost_s": .12},
        },
        "session_patterns": [{"corner_id": 6, "issue_code": "brake_early", "issue_label": "Early braking", "focus_score": .5, "trend": "improving"}],
        "potential": {"potential_lap_s": 76.100, "potential_gain_s": .250},
        "technique_metrics": {"lap_time_consistency": {"stddev": .081, "samples": 4}},
        "turn_performance": [
            {"corner_id": 6, "net_loss_s": .31},
            {"corner_id": 9, "net_loss_s": .14},
            {"corner_id": 12, "net_loss_s": -.11},
        ],
        "distance_performance": {"full_track_net_delta_s": .44},
    }
    return s


def test_interactive_where_losing_and_gaining():
    s = _state()
    r = handle_voice_request("where am I losing time", s)
    assert r.intent == VoiceIntent.PERFORMANCE_COMPARE
    assert "Turn 6" in r.response and "0.310" in r.response and "early braking" in r.response
    r = handle_voice_request("where did I gain time", s)
    assert "Turn 12" in r.response and "0.110" in r.response


def test_interactive_compare_brake_target_improvement_and_potential():
    s = _state()
    assert "0.440 seconds slower" in handle_voice_request("compare this lap with reference", s).response
    assert "1820 metres" in handle_voice_request("where should I brake for Turn 6", s).response
    assert "improving" in handle_voice_request("did I improve Turn 6", s).response
    assert "76.100" in handle_voice_request("what is my potential lap", s).response
    assert "0.081" in handle_voice_request("how consistent am I", s).response


def test_interactive_unsupported_brake_claim_is_not_invented():
    s = _state()
    s.extended["coaching_suite"]["advice"] = {"4": {"corner_id": 4, "diagnosis": "exit_speed_low", "diagnosis_label": "Low exit speed", "estimated_time_cost_s": .2}}
    assert "No current loss-supported early-braking issue" in handle_voice_request("am I braking too early", s).response


def test_report_promotes_ranked_opportunities_strengths_and_trend(monkeypatch):
    laps = [
        {"lap": 1, "valid": True, "lap_time_s": 77.0, "lap_start_anchored": True, "sample_count": 100, "sections": []},
        {"lap": 2, "valid": True, "lap_time_s": 76.7, "lap_start_anchored": True, "sample_count": 100, "sections": []},
    ]
    reference = {"lap": 99, "valid": True, "lap_time_s": 76.4, "lap_start_anchored": True, "sample_count": 100, "sections": [{}]}
    # Keep the report test focused on V1.3 aggregation rather than lap segmentation.
    monkeypatch.setattr(report_mod, "lap_quality", lambda lap: {"eligible": True})
    rows_by_lap = {
        1: [
            {"corner_id": 6, "reference_corner_id": 6, "time_loss_s": .30, "entry_time_loss_s": .20, "mid_time_loss_s": .05, "exit_time_loss_s": .05, "estimated_time_cost_s": .20, "diagnosis": "brake_early", "diagnosis_label": "Early braking", "dominant_phase": "ENTRY", "diagnosis_confidence": .9, "coaching_eligible": True},
            {"corner_id": 12, "reference_corner_id": 12, "time_loss_s": -.10, "entry_time_loss_s": -.02, "mid_time_loss_s": -.04, "exit_time_loss_s": -.04, "estimated_time_cost_s": 0.0, "diagnosis": None, "diagnosis_label": None, "dominant_phase": None, "diagnosis_confidence": .9, "coaching_eligible": False},
        ],
        2: [
            {"corner_id": 6, "reference_corner_id": 6, "time_loss_s": .20, "entry_time_loss_s": .12, "mid_time_loss_s": .04, "exit_time_loss_s": .04, "estimated_time_cost_s": .12, "diagnosis": "brake_early", "diagnosis_label": "Early braking", "dominant_phase": "ENTRY", "diagnosis_confidence": .9, "coaching_eligible": True},
            {"corner_id": 12, "reference_corner_id": 12, "time_loss_s": -.08, "entry_time_loss_s": -.01, "mid_time_loss_s": -.03, "exit_time_loss_s": -.04, "estimated_time_cost_s": 0.0, "diagnosis": None, "diagnosis_label": None, "dominant_phase": None, "diagnosis_confidence": .9, "coaching_eligible": False},
        ],
    }
    class A:
        def __init__(self, d): self.d=d
        def to_dict(self): return dict(self.d)
    monkeypatch.setattr(report_mod, "build_corner_analyses", lambda lap, ref: [A(x) for x in rows_by_lap[lap["lap"]]])
    monkeypatch.setattr(report_mod, "potential_summary", lambda *a, **k: {"best_lap_s":76.7,"potential_lap_s":76.5,"potential_gain_s":.2,"potential_vs_reference_s":.1,"eligible_lap_count":2})
    monkeypatch.setattr(report_mod, "session_technique_metrics", lambda laps: {"lap_time_consistency":None,"corners":[]})
    monkeypatch.setattr(report_mod, "compare_racing_line", lambda *a, **k: {"available":False})
    monkeypatch.setattr(report_mod, "straight_line_analysis", lambda *a, **k: {"available":False})
    rec = SimpleNamespace(completed=laps, external_reference=reference, reference_mode="external", event_context={"profile":"time_trial"})
    r = report_mod.build_coach_report(rec)
    assert r["version"] == "1.3.0.1"
    assert r["total_reference_gap_s"] == 0.29999999999999716 or abs(r["total_reference_gap_s"]-.3) < 1e-9
    assert r["ranked_biggest_opportunities"][0]["corner_id"] == 6
    assert r["best_strengths"][0]["corner_id"] == 12
    assert r["phase_loss_breakdown_s"]["ENTRY"] > 0
    assert r["improvement_trend"]["direction"] == "improving"
