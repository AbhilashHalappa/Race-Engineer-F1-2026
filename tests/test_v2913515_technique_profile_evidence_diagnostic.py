from pathlib import Path


def test_technique_profile_empty_state_exposes_group_sample_counts():
    ui = (Path(__file__).parents[1] / "src" / "performance_hub_ui.py").read_text(encoding="utf-8")
    assert "Technique profile unavailable" in ui
    assert "technique groups have sufficient repeated evidence" in ui
    assert "trusted sample" in ui
    assert "needs 3" in ui
    assert "Not enough multi-lap technique evidence." not in ui


def test_score_and_confidence_core_are_not_modified_by_ui_hotfix():
    ui = (Path(__file__).parents[1] / "src" / "performance_hub_ui.py").read_text(encoding="utf-8")
    # Diagnostic consumes already-produced group score/sample_count fields only.
    assert "g?.sample_count" in ui
    assert "g?.score" in ui
