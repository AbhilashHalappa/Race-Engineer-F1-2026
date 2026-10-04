from pathlib import Path

WINDOW = Path("src/overlay/window.py").read_text(encoding="utf-8")
BLOCK = WINDOW.split("class LiveCornerFeedbackOverlayWindow", 1)[1].split("class LapStintSummaryPanel", 1)[0]


def test_r4_uses_existing_dimension_scores_only():
    assert "dimension_scores" in BLOCK
    assert "_dimension_score" in BLOCK
    assert "normalize_metric_score" not in BLOCK
    assert "score_metric(" not in BLOCK


def test_r4_overview_shows_four_glanceable_dimensions():
    assert "'corner':('braking_point','min_apex_speed','throttle_pickup','exit_speed')" in BLOCK
    for label in ("BRAKE POINT", "APEX SPEED", "THROTTLE PICKUP", "EXIT SPEED"):
        assert label in BLOCK
    assert "_draw_accuracy_tile" in BLOCK


def test_r4_specialized_views_show_two_to_four_existing_dimensions():
    for mode in ("'apex':", "'min_speed':", "'trail':", "'throttle':", "'brake':"):
        assert mode in BLOCK
    assert "[:4]" in BLOCK


def test_r4_keeps_grade_time_cost_and_one_action_prominent():
    assert "grade_text" in BLOCK
    assert "estimated_loss_s" in BLOCK
    assert "LOST" in BLOCK and "GAINED" in BLOCK and "MATCHED REFERENCE" in BLOCK
    assert "action_text" in BLOCK and "WORK ON:" in BLOCK and "KEEP:" in BLOCK


def test_r4_has_expandable_measured_evidence_and_preserves_na():
    assert "_details_expanded" in BLOCK
    assert "MEASURED EVIDENCE" in BLOCK
    assert "NO VALID APEX DATA" in BLOCK
    assert "NO VALID BRAKE POINT DATA" in BLOCK
    assert "N/A — no trusted detail for this view" in BLOCK


def test_r4_remains_presentation_only():
    assert "EngineerMessage(" not in BLOCK
    assert "speak(" not in BLOCK
    assert "speech" not in BLOCK.lower().replace("speech or", "")
