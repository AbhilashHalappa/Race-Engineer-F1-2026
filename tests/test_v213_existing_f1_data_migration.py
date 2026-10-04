from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.f1_profile_migration import attach_existing_f1_history
from src.performance_history import PerformanceHistoryStore


def _game_driver():
    return {"name": "F1 Driver", "race_number": 44, "platform_id": 1, "game_year": 2026}


def _coach(track: str, lap: int):
    return {
        "event_context": {"track_name": track, "session_type": "Time Trial", "session_uid": f"s{lap}"},
        "reference_mode": "external",
        "potential": {"best_lap_s": 90.0 + lap, "reference_lap_s": 89.5},
        "lap_telemetry": {
            str(lap): {
                "lap": lap,
                "lap_time_s": 90.0 + lap,
                "telemetry": {"speed_kph": {"driver": [100, 110], "reference": [102, 112]}},
            }
        },
        "telemetry_overlay": {"speed_kph": {"driver": [100, 110], "reference": [102, 112]}},
        "lap_facts": [{"lap": lap, "assists": {"traction_control": 1}}],
        "performance_review": {"corners": [{"corner": 1, "loss_s": 0.2}], "lap_reviews": [{"lap": lap}]},
        "technique_metrics": {"braking": 0.7},
    }


def _summary(track: str, lap: int):
    return {
        "session_uid": f"s{lap}",
        "track": track,
        "session_type": "Time Trial",
        "laps_completed": lap,
        "best_lap_s": 90.0 + lap,
    }


def test_v213_logically_attaches_existing_history_without_rewriting_sessions(tmp_path: Path):
    history = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    pid = history.create_user_profile("Abhilash H")
    history.record_session(_game_driver(), _summary("Melbourne", 1), _coach("Melbourne", 1))
    history.record_session(_game_driver(), _summary("Silverstone", 2), _coach("Silverstone", 2))

    with sqlite3.connect(history.path) as con:
        before = con.execute("SELECT id,session_key,summary_json,coach_json FROM sessions ORDER BY id").fetchall()

    drivers = DriverProfileStore(tmp_path / "drivers")
    person = drivers.create_profile("Abhilash H", compatibility={"performance_history_profile_id": pid})
    binding = attach_existing_f1_history(drivers, history, person["driver_id"])

    with sqlite3.connect(history.path) as con:
        after = con.execute("SELECT id,session_key,summary_json,coach_json FROM sessions ORDER BY id").fetchall()
    assert after == before

    assert binding["status"] == "linked"
    assert binding["storage_mode"] == "logical_link"
    assert binding["performance_history_profile_id"] == pid
    assert binding["inventory"]["sessions"] == 2
    assert binding["inventory"]["tracks"] == 2
    assert binding["inventory"]["laps"] == 3
    assert binding["inventory"]["evidence"]["telemetry_sessions"] == 2
    assert binding["inventory"]["evidence"]["reference_sessions"] == 2
    assert binding["inventory"]["evidence"]["corner_performance_sessions"] == 2
    assert binding["inventory"]["evidence"]["assist_sessions"] == 2

    game = drivers.load_game_profile(person["driver_id"], "f1_26")
    assert game["sessions"] == 2
    assert game["history_laps"] == 3
    assert game["history_tracks"] == 2
    assert game["driving_seconds"] == 0
    assert game["history_binding"]["content_scope"][-1] == "recorded_history"

    career = drivers.load_career_summary(person["driver_id"])
    assert career["total_sessions"] == 2
    assert career["total_laps"] == 3
    assert career["total_driving_seconds"] == 0


def test_v213_reverification_is_idempotent_and_preserves_first_attachment_time(tmp_path: Path):
    history = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    pid = history.create_user_profile("Driver")
    history.record_session(_game_driver(), _summary("Monza", 1), _coach("Monza", 1))
    drivers = DriverProfileStore(tmp_path / "drivers")
    person = drivers.create_profile("Driver", compatibility={"performance_history_profile_id": pid})

    first = attach_existing_f1_history(drivers, history, person["driver_id"])
    second = attach_existing_f1_history(drivers, history, person["driver_id"])
    assert second["attached_at"] == first["attached_at"]
    assert second["inventory"]["sessions"] == 1


def test_v213_inventory_reports_empty_history_safely(tmp_path: Path):
    history = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    pid = history.create_user_profile("New Driver")
    inventory = history.profile_inventory(pid)
    assert inventory["available"] is True
    assert inventory["sessions"] == 0
    assert inventory["tracks"] == 0
    assert inventory["laps"] == 0


def test_v213_runtime_performs_f1_history_attachment():
    source = Path("src/overlay/runtime.py").read_text(encoding="utf-8")
    assert "attach_existing_f1_history" in source
    migration = Path("src/f1_profile_migration.py").read_text(encoding="utf-8")
    assert '"storage_mode": "logical_link"' in migration
    assert '"driver_game_information"' in migration
    assert '"recorded_history"' in migration
