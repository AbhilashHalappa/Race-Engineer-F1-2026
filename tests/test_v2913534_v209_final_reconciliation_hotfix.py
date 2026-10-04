from pathlib import Path
import json

from src.driver_profiles import DriverProfileStore
from src.skill_evidence import SkillEvidenceStore
from src.driver_skill_reconciliation import DriverSkillReconciliation
from src.performance_hub_ui import performance_hub_page_html


class FakeHistory:
    def __init__(self, rows=None, detail=None):
        self.rows = list(rows or [])
        self.detail = dict(detail or {})

    def skill_evidence_source_sessions(self, profile_id):
        return list(self.rows)

    def track_detail(self, track, profile_id):
        return dict(self.detail)


def _profile(tmp_path: Path):
    ds = DriverProfileStore(tmp_path / "drivers")
    profile = ds.create_profile("Driver", compatibility={"performance_history_profile_id": 7})
    ds.set_active_driver(profile["driver_id"])
    return ds, profile["driver_id"]


def _write_unlinked_evidence(ds: DriverProfileStore, did: str, track="Catalunya"):
    root = ds.root / did / "games" / "f1_26" / "skill_evidence"
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_key": "legacy-catalunya", "session_uid": "unmatched-uid",
        "timestamp": "2026-10-03T00:00:00+00:00", "track": track,
        "session_type": "Time Trial", "measurement_count": 1,
        "measurements": [{"skill":"braking","metric":"braking_execution","value":70,
                          "confidence":1.0,"sample_count":12,"track":track}],
    }
    (root / "legacy.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "index.json").write_text(json.dumps({"sessions":[{
        "path":"legacy.json", "session_key":"legacy-catalunya", "track":track,
        "session_uid":"unmatched-uid", "measurement_count":1,
    }]}), encoding="utf-8")
    return root


def test_unlinked_valid_track_evidence_is_deindexed_when_history_does_not_own_it(tmp_path):
    ds, did = _profile(tmp_path)
    root = _write_unlinked_evidence(ds, did, "Catalunya")
    history = FakeHistory(rows=[{
        "history_session_id": 101,
        "summary": {"track":"Austria", "session_type":"Time Trial", "session_uid":"owned-uid"},
        "coach": {},
    }])
    out = SkillEvidenceStore(ds, history).reconcile_with_performance_history(driver_id=did)
    idx = json.loads((root / "index.json").read_text(encoding="utf-8"))
    assert out["orphaned"] == 1
    assert out["session_count"] == 0
    assert idx["sessions"] == []
    # Non-destructive forensic artifact remains on disk.
    assert (root / "legacy.json").exists()


def test_time_recovered_reports_worsening_without_calling_it_reduction(tmp_path, monkeypatch):
    ds, did = _profile(tmp_path)
    import src.performance_history as ph

    fake = FakeHistory(detail={"sessions":[
        {"potential_gain_s":0.000}, {"potential_gain_s":0.001},
    ]})
    monkeypatch.setattr(ph, "PerformanceHistoryStore", lambda: fake)
    result = DriverSkillReconciliation(ds)._measured_time_recovered(did, "Austria")
    assert result["status"] == "available"
    assert result["direction"] == "worsened"
    assert result["value_s"] == 0.0
    assert result["raw_change_s"] == -0.001


def test_hub_copy_distinguishes_improved_worsened_and_unchanged():
    html = performance_hub_page_html()
    assert "Measured opportunity increased from" in html
    assert "recovered time remains 0.000 s" in html
    assert "Measured opportunity was unchanged" in html


def test_profile_source_labels_stored_vs_scoreable():
    src = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert '"Stored evidence sessions"' in src
    assert "scoreable evidence sessions" in src
    assert "setContentsMargins(16,14,28,16)" in src
