from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.skill_evidence import SkillEvidenceStore
from src.skill_trends import SkillTrendStore


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
    ds=DriverProfileStore(tmp_path / "drivers")
    p=ds.create_profile("Tester", active_game="f1_26")
    return ds,p


def test_trends_store_one_snapshot_per_evidence_session(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    ev.capture_f1_session({"session_uid":1,"track":"Melbourne","session_type":"Time Trial"}, _coach("2026-07-01T08:00:00+00:00"))
    ev.capture_f1_session({"session_uid":2,"track":"Spa","session_type":"Time Trial"}, _coach("2026-08-01T08:00:00+00:00",0.3))
    ev.capture_f1_session({"session_uid":3,"track":"Monza","session_type":"Time Trial"}, _coach("2026-09-01T08:00:00+00:00",0.6))
    data=SkillTrendStore(ds).ensure(p["driver_id"])
    assert data["version"] == "2.5.0"
    assert data["snapshot_count"] == 3
    assert len({x["session_key"] for x in data["snapshots"]}) == 3


def test_trend_view_supports_skill_and_ranges(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    for i in range(1,13):
        ev.capture_f1_session(
            {"session_uid":i,"track":f"Track{i%4}","session_type":"Time Trial"},
            _coach(f"2026-09-{i:02d}T08:00:00+00:00", i/20.0, 60+i),
        )
    trends=SkillTrendStore(ds)
    braking=trends.view(p["driver_id"],"braking","10_sessions")
    assert braking["point_count"] == 10
    assert braking["all_time_point_count"] == 12
    assert braking["current"] is not None
    assert braking["personal_best"] is not None
    overall=trends.view(p["driver_id"],"overall","all_time")
    assert overall["all_time_point_count"] >= 11  # first snapshot cannot publish overall


def test_trends_are_idempotent_when_session_is_refreshed(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    summary={"session_uid":1,"track":"Melbourne","session_type":"Time Trial"}
    ev.capture_f1_session(summary,_coach("2026-09-01T08:00:00+00:00"))
    first=SkillTrendStore(ds).ensure(p["driver_id"])
    ev.capture_f1_session(summary,_coach("2026-09-01T08:00:00+00:00",0.1,84.0))
    second=SkillTrendStore(ds).ensure(p["driver_id"])
    assert first["snapshot_count"] == second["snapshot_count"] == 1


def test_missing_skill_stays_without_trend_points(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    ev.capture_f1_session({"session_uid":1,"track":"Melbourne","session_type":"Time Trial"}, _coach("2026-09-01T08:00:00+00:00"))
    wet=SkillTrendStore(ds).view(p["driver_id"],"wet_driving","all_time")
    assert wet["point_count"] == 0
    assert wet["current"] is None


def test_trends_ui_exposes_filters_graph_and_stats():
    source=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'self.label("SKILL TRENDS",13,True,WHITE)' in source
    assert 'self.profile_trend_skill=QComboBox()' in source
    assert '("10 Sessions","10_sessions")' in source
    assert '("30 Sessions","30_sessions")' in source
    assert '("3 Months","3_months")' in source
    assert '("All Time","all_time")' in source
    assert 'self.profile_trend_chart=SkillTrendChart()' in source


def test_trend_view_can_filter_to_one_track(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    ev.capture_f1_session({"session_uid":1,"track":"Melbourne","session_type":"Time Trial"}, _coach("2026-07-01T08:00:00+00:00",0.0,70.0))
    ev.capture_f1_session({"session_uid":2,"track":"Spa","session_type":"Time Trial"}, _coach("2026-08-01T08:00:00+00:00",0.2,80.0))
    ev.capture_f1_session({"session_uid":3,"track":"Melbourne","session_type":"Time Trial"}, _coach("2026-09-01T08:00:00+00:00",0.4,90.0))
    trends=SkillTrendStore(ds)
    assert trends.available_tracks(p["driver_id"]) == ["Melbourne","Spa"]
    mel=trends.view(p["driver_id"],"braking","all_time","Melbourne")
    assert mel["track"] == "Melbourne"
    assert mel["all_time_point_count"] == 2
    assert all(x["track"] == "Melbourne" for x in mel["points"])
    all_tracks=trends.view(p["driver_id"],"braking","all_time","all")
    assert all_tracks["all_time_point_count"] == 3


def test_trends_ui_exposes_track_filter_and_extra_bottom_graph_margin():
    source=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'self.profile_trend_track=QComboBox(); self.profile_trend_track.addItem("All Tracks","all")' in source
    assert 'controls.addWidget(self.label("TRACK",7,True,MUTED))' in source
    assert 'self.profile_trend_track.currentIndexChanged.connect(self._refresh_skill_trends)' in source
    assert 'r=self.rect().adjusted(48,18,-18,-58)' in source
