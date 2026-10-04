from src.performance_review import aggregate_session_from_lap_scores
from src.performance_history import _session_quick_glance


def test_session_aggregate_inherits_lap_number_from_outer_lap_review():
    review={
        "session_technique_score":None,
        "confidence":0.0,
        "lap_reviews":[
            {"lap":2,"summary":{"score":77.0,"confidence":0.7},"corners":[]},
            {"lap":4,"summary":{"score":83.0,"confidence":0.9},"corners":[]},
            {"lap":6,"summary":{"score":None,"confidence":0.0},"corners":[]},
        ],
        "data_quality":{"eligible_laps":[]},
    }
    out=aggregate_session_from_lap_scores(review)
    assert out["session_technique_score"] == 80.0
    assert out["confidence"] == 0.8
    assert out["data_quality"]["eligible_laps"] == [2,4]
    assert out["data_quality"]["scored_laps"] == [2,4]


def test_quick_glance_exposes_existing_lap_scores_without_rescoring():
    payload={
        "session":{"reference_lap_s":70.0},
        "reference_mode":"recorded",
        "visual_reference":{},
        "review":{
            "lap_reviews":[
                {"lap":2,"summary":{"score":77.2,"confidence":0.7}},
                {"lap":4,"summary":{"score":None,"confidence":0.0}},
            ],
            "laps":[],
        },
    }
    coach={
        "lap_facts":[
            {"lap":2,"lap_time_s":79.3,"valid":True},
            {"lap":4,"lap_time_s":80.0,"valid":True},
        ]
    }
    out=_session_quick_glance(payload,coach)
    by_lap={row["lap"]:row for row in out["rows"]}
    assert by_lap[2]["score"] == 77.2
    assert by_lap[2]["score_confidence"] == 0.7
    assert by_lap[4]["score"] is None
