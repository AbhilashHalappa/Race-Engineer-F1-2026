from pathlib import Path

from src.performance_history import PerformanceHistoryStore
from src.practice_hub_ui import practice_hub_page_html


def _game(name="Tester"):
    return {"name": name, "race_number": 1, "platform_id": 1, "team_name": "Test"}


def _summary(uid, session_type, best):
    return {
        "session_uid": uid,
        "track": "Catalunya",
        "session_type": session_type,
        "laps_completed": 4,
        "best_lap_s": best,
    }


def _coach(uid, session_type, best, weather, *, eligible=(1, 2, 3), excluded=()):
    return {
        "created_utc": f"2026-10-02T18:{uid % 60:02d}:00+00:00",
        "event_context": {
            "session_uid": uid,
            "track_name": "Catalunya",
            "track_id": 14,
            "session_type": session_type,
            "game_mode": 5 if "Trial" in session_type else 4,
        },
        "best_lap": {
            "lap": 3,
            "lap_time_s": best,
            "valid": True,
            "sample_count": 500,
            "lap_start_anchored": True,
            "track_condition": weather,
        },
        "potential": {"best_lap_s": best, "potential_lap_s": best},
        "timed_valid_lap_count": len(eligible) + len(excluded),
        "coaching_data_quality": {
            "eligible_laps": list(eligible),
            "excluded_laps": [dict(x) for x in excluded],
        },
        "recurring_patterns": [],
        "ranked_biggest_opportunities": [],
        "lap_comparisons": [],
        "performance_review": {"data_quality": {"eligible_laps": list(eligible), "excluded_laps": [dict(x) for x in excluded]}},
    }


def test_wet_practice_offers_same_condition_session_best_and_rejects_dry_rival(tmp_path: Path, monkeypatch):
    store = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    pid = store.create_user_profile("Tester")
    store.record_session(_game(), _summary(101, "Time Trial", 70.0), _coach(101, "Time Trial", 70.0, "dry"))
    wet_id = store.record_session(
        _game(),
        _summary(102, "Short Practice", 94.6),
        _coach(102, "Short Practice", 94.6, "wet", eligible=(2, 3), excluded=({"lap": 1, "eligible": False, "reasons": ["partial_lap"], "warnings": []},)),
    )

    monkeypatch.setattr(store, "_installed_review_references", lambda track: [{
        "kind": "external", "id": "external:dry", "label": "Current rival reference · QF 32",
        "lap_time_s": 70.58, "_path": "dummy.json",
    }])
    import src.reference_lap as reference_lap
    monkeypatch.setattr(reference_lap, "load_reference_lap", lambda path: ({"track_condition": "dry", "valid": True, "lap_time_s": 70.58, "sample_count": 500, "lap_start_anchored": True}, {}))

    detail = store.practice_track_detail("Catalunya", pid, reference="external:dry", condition="wet")
    assert detail["selected_condition"] == "wet"
    assert detail["selected_reference"]["id"] == f"session_best:{wet_id}"
    ids = {x["id"] for x in detail["reference_options"]}
    assert f"session_best:{wet_id}" in ids
    assert "external:dry" not in ids
    assert detail["usable_session_count"] == 1
    assert detail["practice_plan"]["status"] == "clear"
    assert detail["quality_summary"]["timed_valid_laps"] == 3
    assert detail["quality_summary"]["eligible_laps"] == 2
    assert detail["quality_summary"]["reason_counts"] == [{"reason": "partial_lap", "count": 1}]


def test_dry_condition_keeps_compatible_current_rival_as_default(tmp_path: Path, monkeypatch):
    store = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    pid = store.create_user_profile("Tester")
    store.record_session(_game(), _summary(201, "Time Trial", 79.0), _coach(201, "Time Trial", 79.0, "dry"))
    monkeypatch.setattr(store, "_installed_review_references", lambda track: [{
        "kind": "external", "id": "external:dry", "label": "Current rival reference · QF 32",
        "lap_time_s": 78.0, "_path": "dummy.json",
    }])
    import src.reference_lap as reference_lap
    monkeypatch.setattr(reference_lap, "load_reference_lap", lambda path: ({"track_condition": "dry", "valid": True, "lap_time_s": 78.0, "sample_count": 500, "lap_start_anchored": True}, {}))

    detail = store.practice_track_detail("Catalunya", pid, condition="dry")
    assert detail["selected_reference"]["id"] == "external:dry"
    assert any(x["kind"] == "session_best" for x in detail["reference_options"])


def test_practice_ui_exposes_quality_diagnostics_and_condition_scoped_reference_reset():
    html = practice_hub_page_html()
    assert "WHY VALID LAPS MAY STILL BE EXCLUDED" in html
    assert "F1 lap validity is not the same as coaching-score eligibility" in html
    assert "quality_summary" in html
    assert "||null" in html
    assert "condition:currentCondition" in html


def test_quick_glance_prefers_quality_reason_even_with_full_corner_coverage():
    from src.performance_history import _session_quick_glance
    payload = {
        "session": {"reference_lap_s": 90.0},
        "reference_mode": "recorded",
        "review": {
            "lap_reviews": [{
                "lap": 2,
                "summary": {
                    "lap": 2, "score": None, "coverage": 1.0,
                    "scored_corners": 14, "eligible_corners": 14,
                    "quality_reasons": ["traffic_compromised"],
                },
            }],
        },
    }
    coach = {"lap_facts": [{"lap": 2, "lap_time_s": 95.0, "valid": True}]}
    q = _session_quick_glance(payload, coach)
    assert q["rows"][0]["score_reason"] == "quality excluded: traffic compromised"


def test_performance_hub_data_quality_lists_exclusion_reasons():
    from src.performance_hub_ui import performance_hub_page_html
    html = performance_hub_page_html()
    assert "Why excluded:" in html
