from pathlib import Path
from src.server_sync import ServerSyncConfig, ServerSyncWorker
from src.storage_manager import StorageManager


def _manager(tmp_path: Path) -> StorageManager:
    m = StorageManager(project_root=tmp_path, local_root=tmp_path / 'user_data')
    m.ensure_layout()
    return m


def test_background_batch_limits_one_pass_and_leaves_remaining(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / 'share'; share.mkdir()
    for i in range(5):
        src = tmp_path / f'f{i}.txt'; src.write_text(f'payload-{i}', encoding='utf-8')
        m.queue_upload(src, category='logs', remote_relpath=f'data/logs/f{i}.txt')
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, enabled=True, retention_interval_s=1800, background_batch_size=2), create_initial_backup=False, enable_bulk_migration=False)
    out = worker.run_once(max_items=2)
    assert out['attempted'] == 2 and out['synced'] == 2 and out['failed'] == 0
    assert out['pending'] == 3


def test_retention_is_not_called_while_queue_remains(tmp_path: Path):
    m = _manager(tmp_path)
    share = tmp_path / 'share'; share.mkdir()
    for i in range(3):
        src = tmp_path / f'f{i}.txt'; src.write_text('x', encoding='utf-8')
        m.queue_upload(src, category='logs', remote_relpath=f'data/logs/f{i}.txt')
    worker = ServerSyncWorker(m, ServerSyncConfig(share_root=share, enabled=True), create_initial_backup=False, enable_bulk_migration=False)
    calls=[]
    worker.bulk_migrator.apply_local_retention=lambda *a, **k: calls.append(1) or {}
    out=worker.run_once(max_items=1)
    assert out['pending'] == 2 and calls == []


def test_platform_coordinator_preserves_fresh_transport_authority():
    source = Path('src/server_platform.py').read_text(encoding='utf-8')
    assert 'transport = transport_worker.run_once()' in source
    assert 'transport = transport_worker.status()' not in source


def test_staged_queue_uses_manifest_hash_but_remote_temp_is_verified():
    source = Path('src/server_sync.py').read_text(encoding='utf-8')
    assert 'int(item.get("queue_version") or 0) < 2' in source
    assert 'if temp.stat().st_size != expected_size or _hash_file(temp) != expected_hash:' in source
    assert '_hash_file(destination) != expected_hash' not in source
