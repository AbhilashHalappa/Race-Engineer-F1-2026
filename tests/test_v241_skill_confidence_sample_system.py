from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.skill_evidence import SkillEvidenceStore
from src.driver_skill import F1DriverSkillModel


def _coach(scale=0.0, sample_count=15):
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
                {"name": "Braking", "score": 82.0, "sample_count": sample_count, "status": "available"},
                {"name": "Turn-in", "score": 76.0, "sample_count": sample_count, "status": "available"},
                {"name": "Corner speed", "score": 79.0, "sample_count": sample_count, "status": "available"},
                {"name": "Throttle", "score": 84.0, "sample_count": sample_count, "status": "available"},
                {"name": "Exit", "score": 81.0, "sample_count": sample_count, "status": "available"},
                {"name": "Steering", "score": 77.0, "sample_count": sample_count, "status": "available"},
            ],
        },
    }


def _driver(tmp_path: Path):
    ds = DriverProfileStore(tmp_path / "drivers")
    p = ds.create_profile("Tester", active_game="f1_26")
    return ds, p


def test_one_session_skill_is_low_confidence_even_with_many_samples(tmp_path):
    ds, p = _driver(tmp_path)
    SkillEvidenceStore(ds).capture_f1_session(
        {"session_uid": 1, "track": "Melbourne", "session_type": "Time Trial"}, _coach(sample_count=100)
    )
    result = F1DriverSkillModel(ds).recalculate(p["driver_id"])
    braking = result["skills"]["braking"]
    assert braking["confidence"] == "LOW"
    assert braking["session_count"] == 1
    assert braking["track_count"] == 1
    assert braking["sample_count"] == 100


def test_three_session_multi_track_skill_reaches_medium_confidence(tmp_path):
    ds, p = _driver(tmp_path)
    ev = SkillEvidenceStore(ds)
    for uid, track in enumerate(("Melbourne", "Spa", "Monza"), 1):
        ev.capture_f1_session({"session_uid": uid, "track": track, "session_type": "Time Trial"}, _coach(uid / 10.0, 18))
    result = F1DriverSkillModel(ds).recalculate(p["driver_id"])
    braking = result["skills"]["braking"]
    assert braking["confidence"] == "MEDIUM"
    assert braking["session_count"] == 3
    assert braking["track_count"] == 3
    assert 0.45 <= braking["confidence_score"] < 0.75
    assert result["overall"]["confidence"] in {"LOW", "MEDIUM", "HIGH"}


def test_eight_session_four_track_skill_reaches_high_confidence(tmp_path):
    ds, p = _driver(tmp_path)
    ev = SkillEvidenceStore(ds)
    tracks=("Melbourne", "Spa", "Monza", "Silverstone")
    for uid in range(1, 9):
        ev.capture_f1_session({"session_uid": uid, "track": tracks[(uid-1)%4], "session_type": "Time Trial"}, _coach(uid / 20.0, 24))
    result = F1DriverSkillModel(ds).recalculate(p["driver_id"])
    braking = result["skills"]["braking"]
    assert braking["confidence"] == "HIGH"
    assert braking["session_count"] == 8
    assert braking["track_count"] == 4
    assert braking["confidence_score"] >= 0.75


def test_missing_skill_remains_na_confidence(tmp_path):
    ds, p = _driver(tmp_path)
    SkillEvidenceStore(ds).capture_f1_session(
        {"session_uid": 1, "track": "Melbourne", "session_type": "Time Trial"}, _coach()
    )
    result=F1DriverSkillModel(ds).recalculate(p["driver_id"])
    assert result["skills"]["wet_driving"]["value"] is None
    assert result["skills"]["wet_driving"]["confidence"] == "N/A"


def test_ui_presents_confidence_and_track_breadth():
    source=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'self.profile_skill_confidence=self.label("Confidence N/A"' in source
    assert 'Confidence {conf} • {sess} sessions • {tracks} tracks' in source
