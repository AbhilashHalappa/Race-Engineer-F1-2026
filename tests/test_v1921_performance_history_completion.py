from types import SimpleNamespace

import src.race_state_receiver as receiver_mod
from src.performance_history import PerformanceHistoryStore
from src.race_state_receiver import RaceStateReceiver


def _summary(uid=1, session_type="Race", position=1):
    return {
        "session_uid": uid,
        "track": "Austria",
        "session_type": session_type,
        "position": position,
        "grid_position": 2,
        "laps_completed": 5,
        "best_lap_s": 70.0,
        "average_valid_lap_s": 71.0,
        "warnings": 0,
        "penalties_s": 0,
        "pit_stops": 0,
        "max_tyre_wear_percent": 10.0,
        "max_tyre_temp_c": 100.0,
        "finish_call": "Finished.",
        "spoken_summary": "Summary.",
    }


def _coach(uid=1):
    return {
        "created_utc": "2026-09-27T00:00:00+00:00",
        "event_context": {"session_uid": uid, "track_name": "Austria", "track_id": 17, "session_type": "Race"},
        "potential": {"best_lap_s": 70.0, "potential_lap_s": 69.5, "potential_gain_s": 0.5},
    }


def test_wins_and_podiums_only_count_actual_race_sessions(tmp_path):
    store = PerformanceHistoryStore(tmp_path / "history.sqlite3")
    profile = {"name": "Driver", "race_number": 1, "platform_id": 1}
    store.record_session(profile, _summary(1, "Race", 1), _coach(1))
    q = _summary(2, "One-Shot Qualifying", 1)
    qc = _coach(2); qc["event_context"]["session_type"] = "One-Shot Qualifying"
    store.record_session(profile, q, qc)
    tt = _summary(3, "Time Trial", 2)
    ttc = _coach(3); ttc["event_context"]["session_type"] = "Time Trial"
    store.record_session(profile, tt, ttc)
    overview = store.overview()
    assert overview["totals"]["sessions"] == 3
    assert overview["totals"]["wins"] == 1
    assert overview["totals"]["podiums"] == 1
    assert overview["tracks"][0]["wins"] == 1
    assert overview["tracks"][0]["podiums"] == 1


def test_live_performance_history_does_not_depend_on_auto_reports(monkeypatch, tmp_path):
    receiver = RaceStateReceiver.__new__(RaceStateReceiver)
    summary = _summary(44, "Race", 2)
    receiver.session_summary_tracker = SimpleNamespace(build=lambda state, performance: dict(summary))
    receiver.engine = SimpleNamespace(
        state=SimpleNamespace(session=SimpleNamespace(uid=44), extended={}, player=None),
        performance=SimpleNamespace(completed=[], external_reference=None, reference_mode=None, event_context=None),
    )
    receiver.live_coach = SimpleNamespace(settings=SimpleNamespace(auto_reports=False, progress_history=False))
    receiver._summary_saved_for_uid = None
    receiver._coach_report_saved_for_uid = None
    receiver._coach_report_completed_count = -1
    receiver._finish_radio_sent = False
    receiver.session_summary = None
    receiver.session_summary_revision = 0
    receiver.performance_history = PerformanceHistoryStore(tmp_path / "live.sqlite3")
    receiver.telemetry_mode = lambda: "live"
    monkeypatch.setattr(receiver_mod, "save_summary", lambda summary: (tmp_path / "a.json", tmp_path / "a.txt"))
    monkeypatch.setattr(receiver_mod, "build_coach_report", lambda perf: _coach(44))

    assert receiver._publish_session_summary(0.0, authoritative=True, speak=False) == []
    overview = receiver.performance_history.overview()
    assert overview["available"] is True
    assert overview["totals"]["sessions"] == 1


def test_replay_history_remains_read_only_when_auto_reports_off(monkeypatch, tmp_path):
    receiver = RaceStateReceiver.__new__(RaceStateReceiver)
    receiver.session_summary_tracker = SimpleNamespace(build=lambda state, performance: _summary(55, "Race", 1))
    receiver.engine = SimpleNamespace(
        state=SimpleNamespace(session=SimpleNamespace(uid=55), extended={}, player=None),
        performance=SimpleNamespace(completed=[], external_reference=None, reference_mode=None, event_context=None),
    )
    receiver.live_coach = SimpleNamespace(settings=SimpleNamespace(auto_reports=False, progress_history=False))
    receiver._summary_saved_for_uid = None
    receiver._coach_report_saved_for_uid = None
    receiver._coach_report_completed_count = -1
    receiver._finish_radio_sent = False
    receiver.session_summary = None
    receiver.session_summary_revision = 0
    receiver.performance_history = PerformanceHistoryStore(tmp_path / "live.sqlite3")
    receiver.telemetry_mode = lambda: "replay"
    monkeypatch.setattr(receiver_mod, "save_summary", lambda summary: (tmp_path / "a.json", tmp_path / "a.txt"))
    monkeypatch.setattr(receiver_mod, "build_coach_report", lambda perf: _coach(55))

    receiver._publish_session_summary(0.0, authoritative=True, speak=False)
    assert receiver.performance_history.overview()["available"] is False


def test_replay_coach_report_can_be_saved_without_mutating_legacy_history(monkeypatch, tmp_path):
    import src.session_coach_report as report_mod

    calls = []
    class FakeHistory:
        def upsert(self, row):
            calls.append(row)

    monkeypatch.setattr(report_mod, "DriverHistory", FakeHistory)
    rec = SimpleNamespace(
        completed=[], external_reference=None, reference_mode=None,
        event_context={"session_uid": 77, "track_name": "Austria", "session_type": "Race"},
    )
    _, _, report = report_mod.save_coach_report(
        rec, directory=tmp_path, stem="replay", record_driver_history=False
    )
    assert calls == []
    assert report["driver_history_recorded"] is False
