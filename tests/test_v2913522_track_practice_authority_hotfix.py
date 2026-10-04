from src.practice_planner import build_track_practice_plan
from src.practice_hub_ui import practice_hub_page_html
from src.performance_review_ai import generate_practice_ai_summary


def _session(patterns=None, eligible=(1,2,3), next_focus=None, best=70.0):
    return {
        "session_id": 1,
        "created_utc": "2026-10-02T10:00:00+00:00",
        "track_name": "Austria",
        "best_lap_s": best,
        "report": {
            "recurring_patterns": patterns or [],
            "coaching_data_quality": {"eligible_laps": list(eligible)},
            "coaching_priority": {"next_lap_focus": next_focus or []},
        },
        "review": {"data_quality": {"eligible_laps": list(eligible)}},
    }


def test_one_session_current_pattern_is_provisional_not_ready():
    p = build_track_practice_plan([_session([{
        "corner_id": 9, "issue_code": "brake_early", "issue_label": "Braking too early",
        "recent_time_cost_s": 1.134, "mean_confidence": .92, "repeat_count": 1,
        "latest_observed": True,
    }])])
    assert p["status"] == "provisional"
    assert p["primary_focus"]["provisional"] is True
    assert p["summary"]["current_focus_cost_s"] == 1.134


def test_no_current_issue_with_good_evidence_is_clear_not_insufficient():
    p = build_track_practice_plan([_session([], eligible=(1,2,3,4,5))])
    assert p["status"] == "clear"
    assert p["reason"] == "no_current_measured_issue"
    assert p["summary"]["current_focus_cost_s"] == 0.0


def test_practice_ui_uses_authoritative_practice_overview_and_new_states():
    html = practice_hub_page_html()
    assert "/api/practice/overview" in html
    assert "NO CURRENT ISSUE" in html
    assert "CURRENT FOCUS COST" in html
    assert "dedupeImmediate" in html
    assert "localStamp" in html


def test_ai_clear_state_does_not_call_llm_or_promote_history():
    text = generate_practice_ai_summary({
        "track": "Catalunya",
        "practice_plan": {"status": "clear", "primary_focus": None, "secondary_focus": None},
    })
    assert "No current measured practice issue" in text
    assert "Older weaknesses remain historical only" in text
