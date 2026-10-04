from pathlib import Path
import json
import zipfile

from src.server_sync import LocalBackupBuilder, ServerSyncConfig, ServerSyncWorker
from src.storage_manager import StorageManager, StorageState


def _manager(tmp_path: Path) -> StorageManager:
    m = StorageManager(project_root=tmp_path)
    m.ensure_layout()
    return m


def test_s6_queue_stages_immutable_payload_and_deduplicates(tmp_path: Path):
    m = _manager(tmp_path)
    source = tmp_path / "sample.areplay"
    source.write_bytes(b"first")
    first = m.queue_upload(source, category="recordings", remote_relpath="data/recordings/sample.areplay")
    second = m.queue_upload(source, category="recordings", remote_relpath="data/recordings/sample.areplay")
    assert first.path == second.path
    item = m.pending_items()[0]
    payload = Path(item["payload"])
    assert payload.read_bytes() == b"first"
    source.write_bytes(b"changed")
    assert payload.read_bytes() == b"first"


def test_s6_offline_fallback_preserves_pending_queue(tmp_path: Path):
    m = _manager(tmp_path)
    source = tmp_path / "session.json"
    source.write_text('{"session":1}', encoding="utf-8")
    m.queue_upload(source, category="sessions")
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=tmp_path / "missing", initial_delay_s=0), create_initial_backup=False)
    result = worker.run_once()
    assert result["state"] == StorageState.OFFLINE_FALLBACK.value
    assert result["pending"] == 1
    assert len(m.pending_items()) == 1


def test_s6_sync_verifies_remote_before_removing_pending_copy(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "server"
    share.mkdir()
    source = tmp_path / "session.json"
    source.write_bytes(b"authoritative-local-data")
    m.queue_upload(source, category="sessions", remote_relpath="data/sessions/session.json")
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, initial_delay_s=0), create_initial_backup=False)
    result = worker.run_once()
    assert result == {"state": "REMOTE", "pending": 0, "attempted": 1, "synced": 1, "failed": 0}
    assert (share / "data" / "sessions" / "session.json").read_bytes() == b"authoritative-local-data"
    assert m.pending_items() == []
    assert source.exists(), "original local authoritative source must remain"


def test_s6_existing_verified_remote_file_prevents_duplicate_copy(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "server"
    remote = share / "data" / "recordings" / "same.areplay"
    remote.parent.mkdir(parents=True)
    remote.write_bytes(b"same")
    source = tmp_path / "same.areplay"
    source.write_bytes(b"same")
    m.queue_upload(source, category="recordings", remote_relpath="data/recordings/same.areplay")
    before = remote.stat().st_mtime_ns
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, initial_delay_s=0), create_initial_backup=False)
    result = worker.run_once()
    assert result["synced"] == 1
    assert remote.stat().st_mtime_ns == before
    assert m.pending_items() == []


def test_s6_backup_builder_captures_current_local_data_and_manifest(tmp_path: Path):
    m = _manager(tmp_path)
    (m.local_path("drivers") / "driver.json").write_text('{"driver":"A"}', encoding="utf-8")
    (tmp_path / "settings").mkdir()
    (tmp_path / "settings" / "coaching.json").write_text('{"pre":true}', encoding="utf-8")
    (tmp_path / "analysis").mkdir()
    m.performance_history_db.write_bytes(b"")
    backup = LocalBackupBuilder(m).create()
    assert backup.is_file()
    with zipfile.ZipFile(backup) as z:
        names = set(z.namelist())
        assert "user_data/drivers/driver.json" in names
        assert "settings/coaching.json" in names
        assert "analysis/performance_history_live.sqlite3" in names
        manifest = json.loads(z.read("BACKUP_MANIFEST.json"))
        assert manifest["entry_count"] >= 3


def test_s6_initial_backup_is_queued_to_server_backups_and_uploaded(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "server"
    share.mkdir()
    (m.local_path("drivers") / "profile.json").write_text("profile", encoding="utf-8")
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, initial_delay_s=0), create_initial_backup=False)
    snapshot = worker.ensure_initial_backup_queued()
    assert snapshot is not None and snapshot.exists()
    pending = m.pending_items()
    assert len(pending) == 1
    assert pending[0]["category"] == "backups"
    assert pending[0]["metadata"]["kind"] == "current_local_data_backup"
    result = worker.run_once()
    assert result["synced"] == 1
    assert not snapshot.exists(), "local snapshot is cleaned only after verified server upload"
    copies = list((share / "backups" / "client_snapshots").rglob("*.zip"))
    assert len(copies) == 1
    with zipfile.ZipFile(copies[0]) as z:
        assert "user_data/drivers/profile.json" in z.namelist()


def test_s6_main_starts_background_worker_but_server_sync_not_in_telemetry_modules():
    main_text = Path("src/main.py").read_text(encoding="utf-8")
    storage_text = Path("src/storage_manager.py").read_text(encoding="utf-8")
    receiver_text = Path("src/race_state_receiver.py").read_text(encoding="utf-8")
    assert "start_default_sync_worker" in main_text
    assert "server_sync" not in receiver_text
    for forbidden in ("requests", "urllib.request", "http.client", "socket."):
        assert forbidden not in storage_text


def test_s6_worker_repairs_legacy_staged_manifest_mismatch(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "server"
    share.mkdir()
    source = tmp_path / "mutable.jsonl"
    source.write_bytes(b"snapshot-v1")
    m.queue_upload(source, category="validation", remote_relpath="data/validation/mutable.jsonl")
    item = m.pending_items()[0]
    # Simulate the pre-V2.9.1.3 race: manifest describes different live-source
    # bytes even though the staged payload itself is a complete valid snapshot.
    m.update_pending(item["manifest_path"], sha256="0" * 64, size_bytes=999)
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, initial_delay_s=0), create_initial_backup=False)
    result = worker.run_once()
    assert result == {"state": "REMOTE", "pending": 0, "attempted": 1, "synced": 1, "failed": 0}
    assert (share / "data" / "validation" / "mutable.jsonl").read_bytes() == b"snapshot-v1"


def test_s6_pending_duplicate_destination_finishes_with_newest_snapshot(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "server"
    share.mkdir()
    source = tmp_path / "mutable.txt"
    source.write_text("old", encoding="utf-8")
    first = m.queue_upload(source, category="validation", remote_relpath="data/validation/mutable.txt")
    # Force deterministic chronology independent of UUID filename ordering.
    m.update_pending(first.path, created_at_utc="2026-01-01T00:00:00+00:00")
    source.write_text("new", encoding="utf-8")
    second = m.queue_upload(source, category="validation", remote_relpath="data/validation/mutable.txt")
    m.update_pending(second.path, created_at_utc="2026-01-01T00:00:01+00:00")
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, initial_delay_s=0), create_initial_backup=False)
    result = worker.run_once()
    assert result["synced"] == 2
    assert result["failed"] == 0
    assert (share / "data" / "validation" / "mutable.txt").read_text(encoding="utf-8") == "new"
