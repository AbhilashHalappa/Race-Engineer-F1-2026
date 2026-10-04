from src.performance_history import _session_quick_glance


def _payload(summary):
    return {
        "session": {},
        "review": {"lap_reviews": [{"lap": 1, "summary": summary}]},
        "visual_reference": {"label": "Session best", "lap_time_s": 80.0},
    }


def _coach(valid=True):
    return {"lap_facts": [{"lap": 1, "lap_time_s": 82.0, "valid": valid}]}


def test_na_exposes_insufficient_corner_coverage_without_rescoring():
    q = _session_quick_glance(
        _payload({"score": None, "confidence": 0.0, "coverage": 0.5,
                  "scored_corners": 7, "eligible_corners": 14}),
        _coach(),
    )
    row = q["rows"][0]
    assert row["score"] is None
    assert row["score_scored_corners"] == 7
    assert row["score_eligible_corners"] == 14
    assert "50% coverage" in row["score_reason"]
    assert "60% required" in row["score_reason"]


def test_na_exposes_minimum_scored_corner_failure():
    q = _session_quick_glance(
        _payload({"score": None, "confidence": 0.0, "coverage": 0.08,
                  "scored_corners": 1, "eligible_corners": 14}),
        _coach(),
    )
    assert "at least 2 required" in q["rows"][0]["score_reason"]


def test_existing_numeric_score_is_preserved_exactly():
    q = _session_quick_glance(
        _payload({"score": 74.0, "confidence": 0.95, "coverage": 0.8,
                  "scored_corners": 12, "eligible_corners": 14}),
        _coach(),
    )
    row = q["rows"][0]
    assert row["score"] == 74.0
    assert row["score_reason"] is None


def test_invalid_lap_na_reason_is_explicit():
    q = _session_quick_glance(
        _payload({"score": None, "confidence": 0.0, "coverage": 0.0}),
        _coach(valid=False),
    )
    assert q["rows"][0]["score_reason"] == "invalid lap"
