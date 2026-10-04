from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.skill_evidence import SkillEvidenceStore
from src.track_skill import TrackSkillStore


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


def test_track_summary_reuses_track_filtered_evidence(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    ev.capture_f1_session({"session_uid":1,"track":"Melbourne","session_type":"Time Trial"},_coach("2026-07-01T08:00:00+00:00",0.0,70.0))
    ev.capture_f1_session({"session_uid":2,"track":"Spa","session_type":"Time Trial"},_coach("2026-08-01T08:00:00+00:00",0.2,80.0))
    ev.capture_f1_session({"session_uid":3,"track":"Melbourne","session_type":"Time Trial"},_coach("2026-09-01T08:00:00+00:00",0.4,90.0))
    store=TrackSkillStore(ds)
    assert store.available_tracks(p["driver_id"])==["Melbourne","Spa"]
    mel=store.summary(p["driver_id"],"Melbourne")
    assert mel["session_count"]==2
    assert mel["skills"]["braking"]["value"] is not None
    assert mel["skills"]["braking"]["session_count"]==2
    spa=store.summary(p["driver_id"],"Spa")
    assert spa["session_count"]==1
    assert spa["skills"]["braking"]["session_count"]==1


def test_track_overall_remains_na_until_track_has_enough_evidence(tmp_path):
    ds,p=_driver(tmp_path); ev=SkillEvidenceStore(ds)
    ev.capture_f1_session({"session_uid":1,"track":"Spa","session_type":"Time Trial"},_coach("2026-08-01T08:00:00+00:00"))
    summary=TrackSkillStore(ds).summary(p["driver_id"],"Spa")
    assert summary["overall"] is None
    assert summary["session_count"]==1


def test_tracks_ui_is_card_based_and_has_detail_panel():
    source=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'self.profile_sections.addTab(tracks_tab,"TRACKS")' in source
    assert 'self.label("F1 TRACK PERFORMANCE",13,True,WHITE)' in source
    assert 'self.profile_track_cards_layout=QGridLayout' in source
    assert 'def _build_track_card(self, data):' in source
    assert 'self.label("SKILL BREAKDOWN",7,True,"#e8be58")' in source


def test_track_card_refresh_has_dynamic_layout_cleanup_helper():
    source=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'def _clear_layout_widgets(self, layout):' in source
    assert 'self._clear_layout_widgets(grid)' in source


def test_track_cards_use_progress_bars_and_valid_css_color_strings():
    source=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'def _build_track_skill_cell(self, name, value):' in source
    assert 'bar=QProgressBar(); bar.setRange(0,100)' in source
    assert 'def _track_score_color(value):' in source
    assert 'return "#8395a8"' in source
    assert '("OVERALL", self._track_skill_display(overall), "#eef6fb")' in source
    assert 'track_title.setStyleSheet("color:#4dd9ff;background:transparent;")' in source
    assert 'skills_header.setStyleSheet("color:#e8be58;background:transparent;")' in source
