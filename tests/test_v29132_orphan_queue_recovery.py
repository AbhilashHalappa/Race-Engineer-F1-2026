from pathlib import Path

from src.bulk_migration import BulkDataMigrator
from src.server_sync import ServerSyncConfig, ServerSyncWorker
from src.storage_manager import StorageManager


def _manager(tmp_path: Path) -> StorageManager:
    m = StorageManager(project_root=tmp_path, local_root=tmp_path / "user_data")
    m.ensure_layout()
    return m


def test_missing_staged_payload_is_restaged_from_existing_source(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "share"
    share.mkdir()
    source = m.local_path("validation") / "transcripts" / "one.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("line-one\n", encoding="utf-8")
    m.queue_upload(
        source,
        category="validation",
        remote_relpath="data/validation/transcripts/one.jsonl",
        stage_payload=True,
        metadata={"kind": "bulk_migration", "source_class": "validation"},
    )
    item = m.pending_items()[0]
    Path(item["payload"]).unlink()
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, enabled=True), create_initial_backup=False, enable_bulk_migration=False)
    out = worker.run_once()
    assert out["pending"] == 0
    assert out["failed"] == 0
    assert (share / "data/validation/transcripts/one.jsonl").read_text(encoding="utf-8") == "line-one\n"


def test_missing_disposable_historical_source_and_payload_is_pruned(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "share"
    share.mkdir()
    source = m.project_root / "logs" / "ptt" / "ptt.wav"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"audio")
    m.queue_upload(
        source,
        category="logs",
        remote_relpath="data/logs/legacy/ptt/ptt.wav",
        stage_payload=False,
        metadata={"kind": "bulk_migration", "source_class": "historical_log"},
    )
    source.unlink()
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, enabled=True), create_initial_backup=False, enable_bulk_migration=False)
    out = worker.run_once()
    assert out["pending"] == 0
    assert out["failed"] == 0


def test_missing_payload_completed_if_remote_copy_already_verified(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / "share"
    share.mkdir()
    source = m.local_path("validation") / "done.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"already-there")
    m.queue_upload(
        source,
        category="validation",
        remote_relpath="data/validation/done.jsonl",
        stage_payload=True,
        metadata={"kind": "bulk_migration", "source_class": "validation"},
    )
    item = m.pending_items()[0]
    remote = share / "data/validation/done.jsonl"
    remote.parent.mkdir(parents=True, exist_ok=True)
    remote.write_bytes(Path(item["payload"]).read_bytes())
    Path(item["payload"]).unlink()
    source.unlink()
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, enabled=True), create_initial_backup=False, enable_bulk_migration=False)
    out = worker.run_once()
    assert out["pending"] == 0
    assert out["failed"] == 0


def test_bulk_migrator_skips_transient_ptt_wav(tmp_path: Path):
    m = _manager(tmp_path)
    wav = m.project_root / "logs" / "ptt" / "capture.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    wav.write_bytes(b"audio")
    normal = m.project_root / "logs" / "engineer.log"
    normal.write_text("keep", encoding="utf-8")
    result = BulkDataMigrator(m, recording_stable_age_s=0).scan_and_queue()
    sources = {Path(str(item["source"])).name for item in m.pending_items()}
    assert "capture.wav" not in sources
    assert "engineer.log" in sources
