from pathlib import Path

from src.practice_planner import build_practice_plan


def _report_with_next_lap_only():
    return {
        "coaching_data_quality": {"eligible_laps": [2, 3, 4, 5, 6, 7, 11]},
        "recurring_patterns": [],
        "ranked_biggest_opportunities": [],
        "best_lap": {"lap_time_s": 77.489},
        "potential": {"potential_gain_s": 0.001},
        "lap_comparisons": [
            {
                "coaching_priority": {
                    "ranked_candidates": [
                        {
                            "rank": 1,
                            "corner_id": 1,
                            "issue_code": "braking_too_late",
                            "issue_label": "Braking too late",
                            "phase": "ENTRY",
                            "estimated_time_cost_s": 1.899,
                            "confidence": 0.97,
                        },
                        {
                            "rank": 2,
                            "corner_id": 6,
                            "issue_code": "apex_speed_too_low",
                            "issue_label": "Apex speed too low",
                            "phase": "MID",
                            "estimated_time_cost_s": 0.896,
                            "confidence": 0.86,
                        },
                    ]
                }
            }
        ],
    }


def test_next_lap_focus_becomes_provisional_practice_target_not_false_no_evidence():
    plan = build_practice_plan(_report_with_next_lap_only())
    assert plan["status"] == "provisional"
    assert plan["reason"] == "next_lap_focus_needs_repeat_validation"
    assert plan["primary_focus"]["corner_id"] == 1
    assert plan["primary_focus"]["provisional"] is True
    assert plan["primary_focus"]["authority"] == "next_lap_focus_provisional"
    assert plan["secondary_focus"]["corner_id"] == 6
    assert plan["baseline_eligible_laps"] == 7


def test_review_opportunity_is_consumed_when_report_ranking_missing():
    report = _report_with_next_lap_only()
    report["lap_comparisons"] = []
    review = {
        "opportunities": [
            {
                "corner_id": 10,
                "mean_net_loss_s": 0.183,
                "dominant_issue": "late_throttle",
                "dominant_issue_label": "Throttle pickup too late",
                "dominant_phase": "EXIT",
                "observations": 4,
                "confidence": 0.94,
            }
        ]
    }
    plan = build_practice_plan(report, review)
    assert plan["status"] == "available"
    assert plan["primary_focus"]["corner_id"] == 10
    assert plan["primary_focus"]["authority"] == "ranked_measured_opportunity"
    assert plan["primary_focus"]["provisional"] is False


def test_practice_ui_has_interactive_controls_and_ai_explanation_only():
    src = (Path(__file__).parents[1] / "src" / "performance_hub_ui.py").read_text(encoding="utf-8")
    assert "MANUAL PRACTICE TIMER" in src
    assert "USE AS FOCUS" in src
    assert "VIEW T${esc(f.corner_id)}" in src
    assert "AI PRACTICE BRIEF" in src
    assert "scope:'practice'" in src


def test_protected_scoring_files_not_touched_by_refinement():
    # Stable V2: external historical trees are no longer part of a portable
    # release.  The signed/hash source-freeze manifest is the authoritative
    # replacement and explicitly records later justified deviations.
    root = Path(__file__).parents[1]
    from src.v2_final_validation import verify_source_freeze
    result = verify_source_freeze(root)
    assert result["ok"] is True
    protected = {item["path"] for item in result["files"]}
    for name in ["performance_scoring.py", "data_quality.py", "performance_review.py", "corner_coach.py", "coaching_priority.py"]:
        assert f"src/{name}" in protected
