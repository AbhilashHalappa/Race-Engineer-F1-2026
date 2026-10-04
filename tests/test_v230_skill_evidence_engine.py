from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.skill_evidence import SkillEvidenceStore


def _coach():
    return {
        "created_utc": "2026-09-30T05:00:00+00:00",
        "event_context": {"profile": "time_trial", "equal_car_performance": 1, "network_game": False},
        "performance_review": {
            "confidence": 0.8,
            "reference": {"lap": 2, "lap_time_s": 82.5, "identity": "reference"},
            "laps": [
                {"lap": 1, "lap_time_s": 84.0, "score": 78.0},
                {"lap": 2, "lap_time_s": 83.0, "score": 81.0},
                {"lap": 3, "lap_time_s": 83.5, "score": 80.0},
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


def test_session_evidence_contains_roadmap_fields(tmp_path):
    ds, p = _driver(tmp_path)
    store = SkillEvidenceStore(ds)
    payload = store.capture_f1_session(
        {"session_uid": 123, "track": "Melbourne", "session_type": "Time Trial"}, _coach()
    )
    assert payload is not None
    assert payload["career_skill_score"] is None
    assert payload["measurement_count"] >= 8
    required = {"skill", "value", "confidence", "sample_count", "track", "conditions", "session_type", "timestamp", "reference_quality"}
    for row in payload["measurements"]:
        assert required <= row.keys()
        assert row["track"] == "Melbourne"
    skills = {row["skill"] for row in payload["measurements"]}
    assert {"pace", "consistency", "braking", "corner_entry", "apex_minimum_speed", "traction_exit", "car_control"} <= skills


def test_session_capture_is_idempotent(tmp_path):
    ds, p = _driver(tmp_path)
    store = SkillEvidenceStore(ds)
    summary = {"session_uid": 456, "track": "Spa", "session_type": "Time Trial"}
    store.capture_f1_session(summary, _coach())
    store.capture_f1_session(summary, _coach())
    s = store.summary(p["driver_id"])
    assert s["session_count"] == 1
    root = store.root(p["driver_id"])
    assert len(list((root / "sessions").glob("*.json"))) == 1


def test_non_f1_active_profile_does_not_receive_f1_evidence(tmp_path):
    ds, p = _driver(tmp_path)
    assert ds.set_active_game(p["driver_id"], "acc")
    store = SkillEvidenceStore(ds)
    assert store.capture_f1_session({"session_uid": 1, "track": "Monza", "session_type": "Race"}, _coach()) is None
    assert not store.index_path(p["driver_id"]).exists()


def test_insufficient_evidence_is_not_fabricated(tmp_path):
    ds, p = _driver(tmp_path)
    coach = {
        "created_utc": "2026-09-30T05:00:00+00:00",
        "event_context": {"profile": "practice"},
        "performance_review": {
            "confidence": 0.0,
            "reference": {"lap_time_s": None},
            "laps": [{"lap": 1, "lap_time_s": 90.0}],
            "technique_groups": [{"name": "Braking", "score": None, "sample_count": 1, "status": "n/a"}],
        },
    }
    payload = SkillEvidenceStore(ds).capture_f1_session(
        {"session_uid": 9, "track": "Monaco", "session_type": "Practice"}, coach
    )
    assert payload is not None
    assert payload["measurements"] == []
    assert payload["career_skill_score"] is None


def test_game_profile_exposes_evidence_metadata_without_skill_score(tmp_path):
    ds, p = _driver(tmp_path)
    SkillEvidenceStore(ds).capture_f1_session(
        {"session_uid": 777, "track": "Silverstone", "session_type": "Time Trial"}, _coach()
    )
    gp = ds.load_game_profile(p["driver_id"], "f1_26")
    assert gp["skill_evidence"]["session_count"] == 1
    assert gp["skill_evidence"]["measurement_count"] > 0
    assert gp["skill_evidence"]["career_skill_score"] is None


def test_historical_live_sessions_backfill_into_evidence_idempotently(tmp_path):
    from src.performance_history import PerformanceHistoryStore

    ds, p = _driver(tmp_path)
    history = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    game_driver = {"name": "Tester", "driver_id": 1, "race_number": 99, "team_id": 1, "game_year": 2026}
    summary = {
        "session_uid": 9001,
        "track": "Melbourne",
        "session_type": "Time Trial",
        "laps_completed": 3,
        "best_lap_s": 83.0,
    }
    history.record_session(game_driver, summary, _coach())
    pid = history.active_user_profile_id()
    assert pid is not None
    assert ds.set_compatibility_value(p["driver_id"], "performance_history_profile_id", pid)

    store = SkillEvidenceStore(ds, history)
    first = store.backfill_f1_history(driver_id=p["driver_id"])
    assert first["available"] is True
    assert first["scanned"] == 1
    assert first["written"] == 1
    assert first["measurement_count"] > 0
    ev = store.summary(p["driver_id"])
    assert ev["session_count"] == 1
    assert ev["measurement_count"] > 0

    second = store.backfill_f1_history(driver_id=p["driver_id"])
    assert second["already_current"] is True
    assert second["written"] == 0
    assert store.summary(p["driver_id"])["session_count"] == 1


def test_historical_backfill_keeps_insufficient_session_as_zero_measurement(tmp_path):
    from src.performance_history import PerformanceHistoryStore

    ds, p = _driver(tmp_path)
    history = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    game_driver = {"name": "Tester", "driver_id": 1, "race_number": 99, "team_id": 1, "game_year": 2026}
    summary = {"session_uid": 9002, "track": "Monaco", "session_type": "Practice", "laps_completed": 1}
    weak_coach = {
        "created_utc": "2026-09-30T05:00:00+00:00",
        "event_context": {"profile": "practice"},
        "performance_review": {"confidence": 0.0, "reference": {"lap_time_s": None}, "laps": [], "technique_groups": []},
    }
    history.record_session(game_driver, summary, weak_coach)
    pid = history.active_user_profile_id()
    assert ds.set_compatibility_value(p["driver_id"], "performance_history_profile_id", pid)

    store = SkillEvidenceStore(ds, history)
    result = store.backfill_f1_history(driver_id=p["driver_id"])
    assert result["written"] == 1
    assert result["zero_measurement_sessions"] == 1
    assert store.summary(p["driver_id"])["session_count"] == 1
    assert store.summary(p["driver_id"])["measurement_count"] == 0

def test_reconcile_unknown_track_evidence_from_exact_history_row_id(tmp_path):
    import json
    from src.performance_history import PerformanceHistoryStore
    from src.track_skill import TrackSkillStore

    ds, p = _driver(tmp_path)
    history = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    game_driver = {"name": "Tester", "driver_id": 1, "race_number": 99, "team_id": 1, "game_year": 2026}
    sid = history.record_session(game_driver, {
        "session_uid": 5555, "track": "Sakhir (Bahrain)", "session_type": "Time Trial",
        "laps_completed": 2, "best_lap_s": 94.4,
    }, _coach())
    pid = history.active_user_profile_id()
    assert ds.set_compatibility_value(p["driver_id"], "performance_history_profile_id", pid)

    store = SkillEvidenceStore(ds, history)
    payload = store.capture_f1_session({
        "session_uid": 5555, "track": "Unknown", "session_type": "Unknown",
        "performance_history_session_id": sid,
    }, _coach(), driver_id=p["driver_id"])
    root = store.root(p["driver_id"])
    index = json.loads(store.index_path(p["driver_id"]).read_text())
    assert index["sessions"][0]["track"] == "Unknown"

    result = store.reconcile_with_performance_history(driver_id=p["driver_id"])
    assert result["available"] is True
    index = json.loads(store.index_path(p["driver_id"]).read_text())
    assert index["sessions"][0]["track"] == "Sakhir (Bahrain)"
    session_payload = json.loads((root / index["sessions"][0]["path"]).read_text())
    assert session_payload["track"] == "Sakhir (Bahrain)"
    assert all(m["track"] == "Sakhir (Bahrain)" for m in session_payload["measurements"])
    assert "Unknown" not in TrackSkillStore(ds).available_tracks(p["driver_id"])
    assert "Sakhir (Bahrain)" in TrackSkillStore(ds).available_tracks(p["driver_id"])

def test_reconcile_prunes_derived_evidence_after_history_session_delete(tmp_path):
    import json
    from src.performance_history import PerformanceHistoryStore
    from src.track_skill import TrackSkillStore

    ds, p = _driver(tmp_path)
    history = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    game_driver = {"name": "Tester", "driver_id": 1, "race_number": 99, "team_id": 1, "game_year": 2026}
    sid = history.record_session(game_driver, {
        "session_uid": 7777, "track": "Sakhir (Bahrain)", "session_type": "Time Trial",
        "laps_completed": 2, "best_lap_s": 94.4,
    }, _coach())
    pid = history.active_user_profile_id()
    assert ds.set_compatibility_value(p["driver_id"], "performance_history_profile_id", pid)

    store = SkillEvidenceStore(ds, history)
    store.capture_f1_session({
        "session_uid": 7777, "track": "Sakhir (Bahrain)", "session_type": "Time Trial",
        "performance_history_session_id": sid,
    }, _coach(), driver_id=p["driver_id"])
    assert "Sakhir (Bahrain)" in TrackSkillStore(ds).available_tracks(p["driver_id"])

    assert history.delete_session(sid) is True
    result = store.reconcile_with_performance_history(driver_id=p["driver_id"])
    assert result["available"] is True
    assert result["orphaned"] == 1
    index = json.loads(store.index_path(p["driver_id"]).read_text())
    assert index["session_count"] == 0
    assert "Sakhir (Bahrain)" not in TrackSkillStore(ds).available_tracks(p["driver_id"])
