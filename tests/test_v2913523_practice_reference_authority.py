from src.practice_hub_ui import practice_hub_page_html
from src.practice_planner import build_track_practice_plan


def _row(cost=0.2):
    return {
        "session_id": 1,
        "created_utc": "2026-10-01T00:00:00+00:00",
        "track_name": "Austria",
        "best_lap_s": 71.0,
        "report": {
            "coaching_data_quality": {"eligible_laps": [1,2,3]},
            "recurring_patterns": [{
                "corner_id": 9, "issue_code": "brake_early", "issue_label": "Braking too early",
                "recent_time_cost_s": cost, "mean_time_cost_s": cost,
                "mean_confidence": 0.92, "repeat_count": 4, "latest_observed": True,
                "trend": "insufficient_history",
            }],
        },
        "review": {},
    }


def test_track_single_session_repeat_is_provisional_not_ready():
    plan=build_track_practice_plan([_row()])
    assert plan["status"] == "provisional"
    assert plan["primary_focus"]["provisional"] is True


def test_practice_ui_exposes_reference_authority_selector():
    html=practice_hub_page_html()
    assert "PRACTICE REFERENCE" in html
    assert "PRACTICE HISTORY" in html
    assert "PRACTICE BENCHMARK" in html
    assert "reference:currentReference" in html
