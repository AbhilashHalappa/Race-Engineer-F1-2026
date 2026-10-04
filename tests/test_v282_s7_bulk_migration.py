from pathlib import Path
import json
import os
import time

from src.bulk_migration import BulkDataMigrator
from src.server_sync import ServerSyncConfig, ServerSyncWorker
from src.storage_manager import StorageManager


def _manager(tmp_path: Path) -> StorageManager:
    m = StorageManager(project_root=tmp_path)
    m.ensure_layout()
    return m


def test_s7_routes_areplay_to_replays_and_retains_local_after_verified_sync(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "server"
    share.mkdir()
    replay = m.local_path("recordings") / "race.areplay"
    replay.write_bytes(b"historical replay")
    old = time.time() - 300
    os.utime(replay, (old, old))

    migrator = BulkDataMigrator(m, recording_stable_age_s=120)
    scan = migrator.scan_and_queue()
    assert scan["queued"] == 1
    item = m.pending_items()[0]
    assert item["remote_relpath"] == "data/replays/race.areplay"
    assert item["payload_staged"] is False
    assert item["metadata"]["kind"] == "bulk_migration"

    worker = ServerSyncWorker(
        m,
        ServerSyncConfig(share_root=share, initial_delay_s=0),
        create_initial_backup=False,
        enable_bulk_migration=False,
    )
    result = worker.run_once()
    assert result["synced"] == 1
    assert (share / "data" / "replays" / "race.areplay").read_bytes() == b"historical replay"
    assert replay.read_bytes() == b"historical replay", "S7 retains local compatibility copy"
    assert m.pending_items() == []


def test_s7_recent_active_recording_is_not_queued(tmp_path: Path):
    m = _manager(tmp_path)
    replay = m.local_path("recordings") / "active.areplay"
    replay.write_bytes(b"still recording")
    migrator = BulkDataMigrator(m, recording_stable_age_s=120)
    scan = migrator.scan_and_queue()
    assert scan["queued"] == 0
    assert scan["skipped_active"] == 1
    assert m.pending_items() == []


def test_s7_validation_logs_exports_and_backups_use_server_roots(tmp_path: Path):
    m = _manager(tmp_path)
    files = {
        m.local_path("validation") / "bundle.zip": "data/validation/bundle.zip",
        m.local_path("logs") / "old.log": "data/logs/old.log",
        m.local_path("exports") / "report.json": "data/exports/report.json",
        m.local_path("backups") / "manual.zip": None,
    }
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name, encoding="utf-8")

    migrator = BulkDataMigrator(m, recording_stable_age_s=0)
    scan = migrator.scan_and_queue()
    assert scan["queued"] == 4
    items = {Path(i["source"]).name: i for i in m.pending_items()}
    assert items["bundle.zip"]["remote_relpath"] == "data/validation/bundle.zip"
    assert items["old.log"]["remote_relpath"] == "data/logs/old.log"
    assert items["report.json"]["remote_relpath"] == "data/exports/report.json"
    assert items["manual.zip"]["remote_relpath"].startswith("backups/client_data/")
    assert items["manual.zip"]["remote_relpath"].endswith("/manual.zip")


def test_s7_registry_prevents_requeue_until_file_changes(tmp_path: Path):
    m = _manager(tmp_path)
    path = m.local_path("validation") / "result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("one", encoding="utf-8")
    migrator = BulkDataMigrator(m, recording_stable_age_s=0)
    first = migrator.scan_and_queue()
    second = migrator.scan_and_queue()
    assert first["queued"] == 1
    assert second["queued"] == 0
    assert second["skipped_known"] == 1
    assert len(m.pending_items()) == 1

    time.sleep(0.01)
    path.write_text("two-two", encoding="utf-8")
    third = migrator.scan_and_queue()
    assert third["queued"] == 1
    assert len(m.pending_items()) == 2


def test_s7_status_reports_classes_and_pending(tmp_path: Path):
    m = _manager(tmp_path)
    validation = m.local_path("validation") / "v.zip"
    validation.parent.mkdir(parents=True, exist_ok=True)
    validation.write_bytes(b"v")
    migrator = BulkDataMigrator(m, recording_stable_age_s=0)
    migrator.scan_and_queue()
    status = migrator.status()
    assert status["tracked_files"] == 1
    assert status["pending"] == 1
    assert status["by_class"]["validation"] == 1
    assert status["retention"] == "SERVER_MASTER_LOCAL_RETENTION"


def test_s7_storage_layout_includes_exports_and_nonstaged_queue_does_not_delete_source(tmp_path: Path):
    m = _manager(tmp_path)
    assert "exports" in m.CATEGORIES
    source = tmp_path / "historical.log"
    source.write_bytes(b"keep")
    queued = m.queue_upload(source, category="logs", remote_relpath="data/logs/historical.log", stage_payload=False)
    item = m.pending_items()[0]
    assert Path(item["payload"]) == source
    m.complete_pending(item)
    assert source.exists()
    assert not queued.path.exists()
