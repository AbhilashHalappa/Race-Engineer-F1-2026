from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.skill_evidence import SkillEvidenceStore
from src.career_history import CareerHistoryStore


def _coach(ts: str, scale=0.0, braking=82.0):
    return {
        "created_utc": ts,
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
                {"name": "Braking", "score": braking, "sample_count": 15, "status": "available"},
                {"name": "Turn-in", "score": 76.0, "sample_count": 12, "status": "available"},
                {"name": "Corner speed", "score": 79.0, "sample_count": 12, "status": "available"},
                {"name": "Throttle", "score": 84.0, "sample_count": 10, "status": "available"},
                {"name": "Exit", "score": 81.0, "sample_count": 10, "status": "available"},
                {"name": "Steering", "score": 77.0, "sample_count": 9, "status": "available"},
            ],
        },
    }


def _driver(tmp_path: Path):
    ds=DriverProfileStore(tmp_path/"drivers")
    p=ds.create_profile("Tester",active_game="f1_26")
    return ds,p


def test_history_derives_only_real_evidence_milestones(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    ev.capture_f1_session({"session_uid":1,"track":"Melbourne","session_type":"Time Trial"},_coach("2026-07-01T08:00:00+00:00",0.0,72.0))
    ev.capture_f1_session({"session_uid":2,"track":"Melbourne","session_type":"Time Trial"},_coach("2026-08-01T08:00:00+00:00",0.2,82.0))
    data=CareerHistoryStore(ds).ensure(p["driver_id"])
    assert data["version"] in {"2.6.0","2.6.1"}
    assert data["event_count"]>0
    assert all(x.get("timestamp") for x in data["events"])
    assert any(x["category"]=="skill" for x in data["events"])
    assert any(x["category"]=="track" for x in data["events"])
    assert not any("driving hour" in (x.get("title") or "").lower() for x in data["events"])


def test_history_is_idempotent_and_sorted_newest_first(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    for i in range(1,4):
        ev.capture_f1_session({"session_uid":i,"track":"Melbourne","session_type":"Time Trial"},_coach(f"2026-09-0{i}T08:00:00+00:00",i/10.0,70+i*5))
    store=CareerHistoryStore(ds)
    a=store.ensure(p["driver_id"]); b=store.ensure(p["driver_id"])
    assert [x["id"] for x in a["events"]]==[x["id"] for x in b["events"]]
    stamps=[x["timestamp"] for x in a["events"]]
    assert stamps==sorted(stamps,reverse=True)


def test_session_count_milestone_uses_fifth_session_timestamp(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    for i in range(1,6):
        ev.capture_f1_session({"session_uid":i,"track":"Track","session_type":"Time Trial"},_coach(f"2026-09-0{i}T08:00:00+00:00"))
    data=CareerHistoryStore(ds).ensure(p["driver_id"])
    event=next(x for x in data["events"] if x["id"]=="sessions_5")
    assert event["timestamp"].startswith("2026-09-05")


def test_history_ui_uses_card_timeline():
    source=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'self.label("CAREER HISTORY",13,True,WHITE)' in source
    assert 'self.profile_history_layout=QVBoxLayout' in source
    assert 'def _refresh_career_history(self):' in source
    assert 'category_colors={"skill":"#59bfe5"' in source
    assert '"career":"#e8be58"' in source
