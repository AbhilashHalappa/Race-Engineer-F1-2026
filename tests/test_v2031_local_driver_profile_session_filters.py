from pathlib import Path
import sqlite3

from src.performance_history import PerformanceHistoryStore, DB_SCHEMA_VERSION


def _game(name, number=1):
    return {"name": name, "race_number": number, "platform_id": 1, "team_name": "Any Team"}


def _summary(uid, session_type):
    return {"session_uid": uid, "track": "Melbourne", "session_type": session_type,
            "laps_completed": 2, "best_lap_s": 82.0 + uid / 1000.0}


def _coach(uid, session_type, game_mode):
    return {"created_utc": f"2026-09-28T00:00:{uid:02d}+00:00",
            "event_context": {"session_uid": uid, "track_name": "Melbourne", "track_id": 0,
                              "session_type": session_type, "game_mode": game_mode},
            "potential": {}}


def test_local_profile_owns_sessions_across_different_game_drivers(tmp_path: Path):
    store = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    profile_id = store.create_user_profile("Abhilash")
    store.record_session(_game("VERSTAPPEN", 3), _summary(1, "Short Practice"), _coach(1, "Short Practice", 28))
    store.record_session(_game("ANTONELLI", 12), _summary(2, "One-Shot Qualifying"), _coach(2, "One-Shot Qualifying", 28))
    data = store.overview(profile_id)
    assert data["totals"]["sessions"] == 2
    assert data["driver"]["name"] == "Abhilash"
    detail = store.track_detail("Melbourne", profile_id)
    assert {row["game_driver_name"] for row in detail["sessions"]} == {"VERSTAPPEN", "ANTONELLI"}


def test_session_and_game_mode_filters_are_independent(tmp_path: Path):
    store = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    pid = store.create_user_profile("Driver")
    store.record_session(_game("A"), _summary(1, "Short Practice"), _coach(1, "Short Practice", 28))
    store.record_session(_game("A"), _summary(2, "Race"), _coach(2, "Race", 28))
    store.record_session(_game("A"), _summary(3, "Time Trial"), _coach(3, "Time Trial", 5))
    assert store.overview(pid, session_group_filter="Practice")["totals"]["sessions"] == 1
    assert store.overview(pid, session_group_filter="Race")["totals"]["sessions"] == 1
    assert store.overview(pid, game_mode_filter="Driver Career")["totals"]["sessions"] == 2
    assert store.overview(pid, game_mode_filter="Time Trial")["totals"]["sessions"] == 1


def test_multiple_local_profiles_are_explicitly_separate(tmp_path: Path):
    store = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    one = store.create_user_profile("Driver One")
    store.record_session(_game("VERSTAPPEN"), _summary(1, "Race"), _coach(1, "Race", 4))
    two = store.create_user_profile("Driver Two")
    store.record_session(_game("VERSTAPPEN"), _summary(2, "Race"), _coach(2, "Race", 4))
    assert store.overview(one)["totals"]["sessions"] == 1
    assert store.overview(two)["totals"]["sessions"] == 1


def test_v3_database_migrates_before_profile_index_is_created(tmp_path: Path):
    db = tmp_path / "legacy_v3.sqlite3"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        INSERT INTO meta(key,value) VALUES('schema_version','3');
        CREATE TABLE drivers(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_key TEXT NOT NULL UNIQUE,
          name TEXT, driver_id INTEGER, race_number INTEGER, nationality_id INTEGER,
          platform_id INTEGER, team_id INTEGER, team_name TEXT, my_team INTEGER,
          ai_controlled INTEGER, game_year INTEGER, game_version TEXT,
          first_seen_utc TEXT NOT NULL, last_seen_utc TEXT NOT NULL,
          profile_json TEXT NOT NULL
        );
        CREATE TABLE sessions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_key TEXT NOT NULL UNIQUE,
          driver_fk INTEGER NOT NULL,
          session_uid TEXT, created_utc TEXT NOT NULL,
          track_id TEXT, track_name TEXT, session_type TEXT,
          result_status TEXT, position INTEGER, grid_position INTEGER,
          laps_completed INTEGER, best_lap_s REAL, average_lap_s REAL,
          potential_lap_s REAL, potential_gain_s REAL, reference_lap_s REAL,
          reference_gap_s REAL, potential_vs_reference_s REAL,
          warnings INTEGER, penalties_s INTEGER, pit_stops INTEGER,
          max_tyre_wear REAL, max_tyre_temp REAL,
          summary_json TEXT NOT NULL, coach_json TEXT NOT NULL
        );
        INSERT INTO drivers(profile_key,name,first_seen_utc,last_seen_utc,profile_json)
        VALUES('old','OLD DRIVER','2026-01-01','2026-01-01','{}');
        INSERT INTO sessions(session_key,driver_fk,created_utc,track_name,session_type,summary_json,coach_json)
        VALUES('1|legacy',1,'2026-01-01','Melbourne','Race','{}','{}');
    """)
    con.commit(); con.close()

    store = PerformanceHistoryStore(db)
    profiles = store.user_profiles()
    assert len(profiles) == 1
    assert profiles[0]["name"] == "Local Driver"
    with sqlite3.connect(db) as migrated:
        cols = {r[1] for r in migrated.execute("PRAGMA table_info(sessions)")}
        assert {"user_profile_fk", "session_group", "game_mode", "game_mode_name"} <= cols
        indexes = {r[1] for r in migrated.execute("PRAGMA index_list(sessions)")}
        assert "idx_sessions_profile_track" in indexes
        assert migrated.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == str(DB_SCHEMA_VERSION)
        assert migrated.execute("SELECT user_profile_fk FROM sessions").fetchone()[0] == profiles[0]["id"]
