from pathlib import Path
import json
import os
import socket

from src.bulk_migration import BulkDataMigrator
from src.server_platform import ReferenceTrackMigrator
from src.server_sync import ServerSyncConfig, ServerSyncWorker
from src.storage_manager import StorageManager
from src.sync_lock import SyncOwnershipLock


def _manager(tmp_path: Path) -> StorageManager:
    m = StorageManager(project_root=tmp_path, local_root=tmp_path / "user_data")
    m.ensure_layout()
    return m


def _write_live_owner(m: StorageManager, operation: str = "other_process") -> Path:
    path = m.server_sync_root / "sync_owner.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": 1,
        "token": "external-owner",
        "pid": os.getpid(),
        "hostname": socket.gethostname() or "gaming-pc",
        "operation": operation,
        "acquired_at_utc": "2026-10-01T10:00:00+00:00",
    }), encoding="utf-8")
    return path


def test_sync_now_returns_busy_without_touching_queue_or_status(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "share"; share.mkdir()
    source = tmp_path / "session.json"; source.write_text("payload", encoding="utf-8")
    m.queue_upload(source, category="sessions", remote_relpath="data/sessions/session.json")
    m._write_json_atomic(m.sync_state_path, {"state": "REMOTE", "pending": 7, "sentinel": "unchanged"})
    lock = _write_live_owner(m, "gui_background_sync")

    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, enabled=True), create_initial_backup=False, enable_bulk_migration=False)
    result = worker.run_once()

    assert result["state"] == "SYNC_BUSY"
    assert result["attempted"] == 0 and result["synced"] == 0 and result["failed"] == 0
    assert result["owner"]["operation"] == "gui_background_sync"
    assert len(m.pending_items()) == 1
    assert not (share / "data/sessions/session.json").exists()
    assert json.loads(m.sync_state_path.read_text(encoding="utf-8"))["sentinel"] == "unchanged"
    lock.unlink()


def test_bulk_migration_respects_cross_process_owner(tmp_path: Path):
    m = _manager(tmp_path)
    source = m.local_path("logs") / "history.log"; source.write_text("x", encoding="utf-8")
    lock = _write_live_owner(m, "cli_sync")
    result = BulkDataMigrator(m, recording_stable_age_s=0).scan_and_queue()
    assert result["state"] == "SYNC_BUSY"
    assert result["queued"] == 0
    assert m.pending_items() == []
    lock.unlink()


def test_reference_track_scan_respects_cross_process_owner(tmp_path: Path):
    m = _manager(tmp_path)
    ref = m.local_path("references") / "ref.json"; ref.write_text("{}", encoding="utf-8")
    lock = _write_live_owner(m, "cli_sync")
    result = ReferenceTrackMigrator(m).scan_and_queue()
    assert result["state"] == "SYNC_BUSY"
    assert result["queued"] == 0
    assert m.pending_items() == []
    lock.unlink()


def test_stale_dead_owner_lock_is_reclaimed(tmp_path: Path):
    m = _manager(tmp_path)
    lock_path = m.server_sync_root / "sync_owner.lock"
    lock_path.write_text(json.dumps({
        "version": 1,
        "token": "dead",
        "pid": 2147483647,
        "hostname": socket.gethostname() or "gaming-pc",
        "operation": "dead_sync",
    }), encoding="utf-8")
    guard = SyncOwnershipLock(lock_path, operation="replacement")
    assert guard.acquire(timeout_s=0.0) is True
    try:
        owner = json.loads(lock_path.read_text(encoding="utf-8"))
        assert owner["operation"] == "replacement"
        assert owner["pid"] == os.getpid()
    finally:
        guard.release()
    assert not lock_path.exists()
