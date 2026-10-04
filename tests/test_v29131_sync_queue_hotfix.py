from pathlib import Path
import os, time

from src.storage_manager import StorageManager
from src.bulk_migration import BulkDataMigrator
from src.server_sync import ServerSyncConfig, ServerSyncWorker


def _manager(tmp_path: Path) -> StorageManager:
    m = StorageManager(project_root=tmp_path, local_root=tmp_path/'user_data')
    m.ensure_layout()
    return m


def test_mutable_historical_files_are_staged_immutable(tmp_path: Path):
    m=_manager(tmp_path)
    log=m.local_path('logs')/'active.log'; log.parent.mkdir(parents=True,exist_ok=True); log.write_text('one')
    BulkDataMigrator(m,recording_stable_age_s=0).scan_and_queue()
    item=m.pending_items()[0]
    assert item['metadata']['source_class']=='historical_log'
    assert item['payload_staged'] is True
    assert Path(item['payload']) != log


def test_legacy_mutable_direct_source_is_repaired_and_syncs(tmp_path: Path):
    m=_manager(tmp_path); share=tmp_path/'share'; share.mkdir()
    log=m.local_path('logs')/'changing.log'; log.parent.mkdir(parents=True,exist_ok=True); log.write_text('old')
    m.queue_upload(log,category='logs',remote_relpath='data/logs/changing.log',stage_payload=False,
                   metadata={'kind':'bulk_migration','source_class':'historical_log'})
    log.write_text('newer-current-value')
    w=ServerSyncWorker(m,ServerSyncConfig(share_root=share,enabled=True),create_initial_backup=False,enable_bulk_migration=False)
    out=w.run_once()
    assert out['failed']==0
    assert out['pending']==0
    assert (share/'data/logs/changing.log').read_text()=='newer-current-value'


def test_superseded_mutable_snapshots_are_compacted(tmp_path: Path):
    m=_manager(tmp_path); share=tmp_path/'share'; share.mkdir()
    log=m.local_path('logs')/'same.log'; log.parent.mkdir(parents=True,exist_ok=True)
    for value in ('one','two','three'):
        log.write_text(value)
        m.queue_upload(log,category='logs',remote_relpath='data/logs/same.log',stage_payload=True,
                       metadata={'kind':'bulk_migration','source_class':'historical_log'})
        time.sleep(0.002)
    assert len(m.pending_items())==3
    w=ServerSyncWorker(m,ServerSyncConfig(share_root=share,enabled=True),create_initial_backup=False,enable_bulk_migration=False)
    out=w.run_once()
    assert out['failed']==0 and out['pending']==0
    assert (share/'data/logs/same.log').read_text()=='three'


def test_platform_reuses_singleton_transport_worker_source_contract():
    source=Path('src/server_platform.py').read_text(encoding='utf-8')
    assert 'from .server_sync import start_default_sync_worker' in source
    assert 'transport_worker = start_default_sync_worker()' in source
    assert 'ServerSyncWorker(self.storage, create_initial_backup=False' not in source
