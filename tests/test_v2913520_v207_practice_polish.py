from pathlib import Path

from src.practice_planner import build_practice_plan
from src.performance_hub_ui import performance_hub_page_html


def _report():
    return {
        "coaching_data_quality": {"eligible_laps": [2, 3, 4, 5, 6]},
        "best_lap": {"lap_time_s": 77.010},
        "potential": {"potential_gain_s": 0.285},
        "recurring_patterns": [
            {"corner_id": 10, "issue_code": "late_throttle", "issue_label": "Throttle pickup too late", "phase": "EXIT", "repeat_count": 4, "mean_time_cost_s": 0.183, "recent_time_cost_s": 0.160, "mean_confidence": 0.94, "latest_observed": True, "trend": "improving", "focus_score": 0.30},
            {"corner_id": 8, "issue_code": "late_throttle", "issue_label": "Throttle pickup too late", "phase": "EXIT", "repeat_count": 3, "mean_time_cost_s": 0.138, "recent_time_cost_s": 0.145, "mean_confidence": 0.89, "latest_observed": True, "trend": "regressing", "focus_score": 0.20},
        ],
    }


def test_secondary_rule_is_explicit_and_does_not_change_current_ranked_behavior():
    plan = build_practice_plan(_report())
    assert plan["primary_focus"]["corner_id"] == 10
    assert plan["secondary_focus"]["corner_id"] == 8
    assert "same technique may appear at a different corner" in plan["secondary_selection_rule"]


def test_verification_copy_is_user_facing_without_changing_threshold():
    plan = build_practice_plan(_report())
    assert "at least 0.015 s" in plan["verification"]["rule"]
    assert ">=" not in plan["verification"]["rule"]


def test_practice_polish_ui_contract():
    html = performance_hub_page_html()
    for token in [
        "MANUAL PRACTICE TIMER", "START TIMER", "MAX TIMED LAPS",
        "pace-only ceiling", "MANUAL FOCUS", "IMMEDIATE", "RECURRING",
        "practicePhaseState", "GENERATING", "UNAVAILABLE", "practiceAiEvidence",
        "Deterministic planner remains authoritative",
    ]:
        assert token in html


def test_protected_core_stays_identical_to_519():
    # Stable V2 portable audit uses the V2 source-freeze manifest rather than
    # requiring an unpacked V2.9.1.3.5.19 sibling tree.
    root = Path(__file__).parents[1]
    from src.v2_final_validation import verify_source_freeze
    result = verify_source_freeze(root)
    assert result["ok"] is True
    protected = {item["path"] for item in result["files"]}
    for name in [
        "performance_scoring.py", "data_quality.py", "performance_review.py",
        "corner_coach.py", "coaching_priority.py",
        "lap_stint_intelligence.py", "race_state_receiver.py",
    ]:
        assert f"src/{name}" in protected
