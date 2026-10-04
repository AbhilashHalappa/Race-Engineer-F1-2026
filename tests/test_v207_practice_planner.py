from src.practice_planner import build_practice_plan
from src.performance_hub_ui import performance_hub_page_html


def _report():
    return {
        "coaching_data_quality": {"eligible_laps": [2, 3, 4, 5]},
        "best_lap": {"lap": 5, "lap_time_s": 80.0},
        "potential": {"realistic_available_gain_s": 0.42, "best_lap_s": 80.0},
        "recurring_patterns": [
            {
                "corner_id": 4, "issue_code": "late_throttle", "issue_label": "Throttle pickup",
                "phase": "EXIT", "repeat_count": 3, "mean_time_cost_s": 0.18,
                "recent_time_cost_s": 0.16, "mean_confidence": 0.92, "latest_observed": True,
                "trend": "improving", "trend_delta_s": -0.03, "focus_score": 0.25,
            },
            {
                "corner_id": 10, "issue_code": "early_brake", "issue_label": "Brake point",
                "phase": "ENTRY", "repeat_count": 2, "mean_time_cost_s": 0.11,
                "recent_time_cost_s": 0.12, "mean_confidence": 0.88, "latest_observed": True,
                "trend": "stable", "trend_delta_s": 0.002, "focus_score": 0.15,
            },
        ],
        "lap_comparisons": [
            {"lap": 5, "coaching_priority": {"ranked_candidates": [
                {"rank": 1, "corner_id": 4, "issue_code": "late_throttle", "issue_label": "Throttle pickup", "phase": "EXIT", "estimated_time_cost_s": 0.16, "confidence": 0.92},
                {"rank": 2, "corner_id": 10, "issue_code": "early_brake", "issue_label": "Brake point", "phase": "ENTRY", "estimated_time_cost_s": 0.12, "confidence": 0.88},
                {"rank": 3, "corner_id": 2, "issue_code": "min_speed", "issue_label": "Minimum speed", "phase": "MID", "estimated_time_cost_s": 0.08, "confidence": 0.80},
            ]}},
        ],
    }


def test_plan_uses_existing_measured_priority_and_is_bounded_to_two_next_lap_items():
    p = build_practice_plan(_report())
    assert p["status"] == "available"
    assert p["duration_minutes"] == 20
    assert p["estimated_laps"] == 15
    assert p["primary_focus"]["corner_id"] == 4
    assert p["secondary_focus"]["corner_id"] == 10
    assert len(p["next_lap_focus"]) == 2
    assert [x["corner_id"] for x in p["next_lap_focus"]] == [4, 10]
    assert [x["name"] for x in p["phases"]] == ["Baseline", "Primary issue", "Verification", "Secondary issue", "Summary"]
    assert p["verification"]["already_improving"] is True


def test_plan_refuses_generic_issue_when_evidence_is_insufficient():
    p = build_practice_plan({"coaching_data_quality": {"eligible_laps": [1]}, "recurring_patterns": []})
    assert p["status"] == "insufficient_evidence"
    assert p["reason"] == "need_at_least_2_quality_eligible_laps"
    assert p["primary_focus"] is None


def test_practice_is_no_longer_exposed_as_session_review_tab():
    html = performance_hub_page_html()
    assert 'data-tab=practice' not in html
    # Legacy hidden pane may remain for backward-compatible JS, but there is no visible Practice tab.
    assert '<button data-tab=practice>' not in html
