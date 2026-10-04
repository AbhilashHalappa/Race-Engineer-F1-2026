from src.performance_review import aggregate_session_from_lap_scores


def test_session_aggregate_uses_existing_lap_scores_without_rescoring():
    review={
        "session_technique_score":None,
        "session_grade":"N/A",
        "confidence":0.0,
        "lap_reviews":[
            {"lap":1,"summary":{"lap":1,"score":78.0,"confidence":0.8},"corners":[]},
            {"lap":2,"summary":{"lap":2,"score":82.0,"confidence":0.9},"corners":[]},
            {"lap":3,"summary":{"lap":3,"score":None,"confidence":0.0},"corners":[]},
        ],
        "data_quality":{"eligible_laps":[],"excluded_laps":[3]},
    }
    out=aggregate_session_from_lap_scores(review)
    # Existing robust contract: with fewer than five values use median.
    assert out["session_technique_score"] == 80.0
    assert out["confidence"] == 0.85
    assert out["data_quality"]["eligible_laps"] == [1,2]
    assert out["data_quality"]["scored_laps"] == [1,2]
    # Per-lap values are not altered.
    assert out["lap_reviews"] == review["lap_reviews"]


def test_session_requires_two_scored_laps_and_does_not_promote_unscored_lap():
    review={
        "session_technique_score":91.0,
        "confidence":0.9,
        "lap_reviews":[
            {"lap":4,"summary":{"lap":4,"score":76.0,"confidence":0.7},"corners":[]},
            {"lap":5,"summary":{"lap":5,"score":None,"confidence":0.0},"corners":[]},
        ],
        "data_quality":{"eligible_laps":[]},
    }
    out=aggregate_session_from_lap_scores(review)
    assert out["session_technique_score"] is None
    assert out["confidence"] == 0.7
    assert out["data_quality"]["eligible_laps"] == [4]
    assert out["data_quality"]["scored_laps"] == [4]


def test_older_compact_laps_list_is_supported():
    review={
        "laps":[
            {"lap":7,"score":70.0,"confidence":0.6},
            {"lap":8,"score":90.0,"confidence":1.0},
        ],
        "data_quality":{},
    }
    out=aggregate_session_from_lap_scores(review)
    assert out["session_technique_score"] == 80.0
    assert out["confidence"] == 0.8
    assert out["data_quality"]["eligible_laps"] == [7,8]
