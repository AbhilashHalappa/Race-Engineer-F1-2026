from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.skill_evidence import SkillEvidenceStore
from src.driver_skill import F1DriverSkillModel


def _coach(scale=0.0):
    return {
        "created_utc": "2026-09-30T08:00:00+00:00",
        "event_context": {"profile": "time_trial", "equal_car_performance": 1, "network_game": False},
        "performance_review": {
            "confidence": 0.9,
            "reference": {"lap": 2, "lap_time_s": 80.0, "identity": "reference"},
            "laps": [
                {"lap": 1, "lap_time_s": 81.0 + scale},
                {"lap": 2, "lap_time_s": 80.8 + scale},
                {"lap": 3, "lap_time_s": 80.9 + scale},
            ],
            "technique_groups": [
                {"name": "Braking", "score": 82.0, "sample_count": 15, "status": "available"},
                {"name": "Turn-in", "score": 76.0, "sample_count": 12, "status": "available"},
                {"name": "Corner speed", "score": 79.0, "sample_count": 12, "status": "available"},
                {"name": "Throttle", "score": 84.0, "sample_count": 10, "status": "available"},
                {"name": "Exit", "score": 81.0, "sample_count": 10, "status": "available"},
                {"name": "Steering", "score": 77.0, "sample_count": 9, "status": "available"},
            ],
        },
    }


def _driver(tmp_path: Path):
    ds = DriverProfileStore(tmp_path / "drivers")
    p = ds.create_profile("Tester", active_game="f1_26")
    return ds, p


def test_evidence_adds_cross_track_normalized_pace_and_consistency(tmp_path):
    ds, p = _driver(tmp_path)
    payload = SkillEvidenceStore(ds).capture_f1_session(
        {"session_uid": 1, "track": "Melbourne", "session_type": "Time Trial"}, _coach()
    )
    metrics = {m["metric"] for m in payload["measurements"]}
    assert "best_lap_gap_percent_to_reference" in metrics
    assert "lap_time_coefficient_of_variation" in metrics


def test_driver_skill_is_derived_from_persisted_evidence(tmp_path):
    ds, p = _driver(tmp_path)
    ev = SkillEvidenceStore(ds)
    ev.capture_f1_session({"session_uid": 1, "track": "Melbourne", "session_type": "Time Trial"}, _coach())
    ev.capture_f1_session({"session_uid": 2, "track": "Spa", "session_type": "Time Trial"}, _coach(0.4))
    result = F1DriverSkillModel(ds).recalculate(p["driver_id"])
    assert result["overall"]["status"] == "available"
    assert 0.0 <= result["overall"]["value"] <= 100.0
    for skill in ("pace", "consistency", "braking", "corner_entry", "apex_minimum_speed", "traction_exit", "car_control"):
        assert result["skills"][skill]["status"] == "available"
        assert 0.0 <= result["skills"][skill]["value"] <= 100.0
    for skill in ("racecraft", "tyre_management", "wet_driving"):
        assert result["skills"][skill]["status"] == "n/a"
        assert result["skills"][skill]["value"] is None


def test_overall_remains_na_with_insufficient_breadth_or_sessions(tmp_path):
    ds, p = _driver(tmp_path)
    SkillEvidenceStore(ds).capture_f1_session(
        {"session_uid": 1, "track": "Melbourne", "session_type": "Time Trial"}, _coach()
    )
    result = F1DriverSkillModel(ds).recalculate(p["driver_id"])
    assert result["overall"]["status"] == "n/a"
    assert result["overall"]["value"] is None


def test_game_profile_receives_current_skill_metadata(tmp_path):
    ds, p = _driver(tmp_path)
    ev = SkillEvidenceStore(ds)
    ev.capture_f1_session({"session_uid": 1, "track": "Melbourne", "session_type": "Time Trial"}, _coach())
    ev.capture_f1_session({"session_uid": 2, "track": "Spa", "session_type": "Time Trial"}, _coach())
    result = F1DriverSkillModel(ds).recalculate(p["driver_id"])
    gp = ds.load_game_profile(p["driver_id"], "f1_26")
    assert gp["driver_skill"]["model_version"] == "2.4.1"
    assert gp["driver_skill"]["value"] == result["overall"]["value"]


def test_ui_exposes_v241_skill_rows_with_confidence_labels():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'self.label("F1 DRIVER SKILL",13,True,WHITE)' in source
    assert '"Racecraft","Tyre Management","Wet Driving"' in source
    assert 'Confidence describes evidence trust, not driving ability' in source
    assert 'Skill {skill_text}' in source


def test_ui_v2411_skill_progress_bars_and_confidence_details():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'self.profile_skill_progress_bars={}' in source
    assert 'bar=QProgressBar(); bar.setRange(0,100)' in source
    assert 'detail.setWordWrap(True)' in source
    assert 'if score < 50.0: color="#ef6764"' in source
    assert 'elif score < 70.0: color="#e8be58"' in source
    assert 'elif score < 85.0: color="#59bfe5"' in source
    assert 'else: color="#4ed282"' in source


def test_ui_v2412_card_layout_and_color_legend():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'skills_grid_layout.addWidget(card,row,col)' in source
    assert 'val.setMinimumWidth(92)' in source
    assert 'Weak <50' in source
    assert 'Developing 50–69.9' in source
    assert 'Strong 70–84.9' in source
    assert 'Excellent 85–100' in source
    assert '("N/A","#8395a8")' in source
