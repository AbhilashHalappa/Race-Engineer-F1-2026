from pathlib import Path
import json, os, time

from src.storage_manager import StorageManager
from src.bulk_migration import BulkDataMigrator
from src.server_sync import ServerSyncWorker, ServerSyncConfig
from src.driver_retention import DriverDeletionJournal


def _touch_old(path: Path, data: bytes, age_s: int = 600):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    ts=time.time()-age_s
    os.utime(path,(ts,ts))


def test_verified_bulk_retention_keeps_latest_10_recording_sessions_and_prunes_other_classes(tmp_path):
    project=tmp_path/'project'; local=project/'user_data'; share=tmp_path/'share'; share.mkdir(parents=True)
    storage=StorageManager(project_root=project, local_root=local)
    storage.ensure_layout()
    rec=storage.local_path('recordings')
    for i in range(12):
        # unique mtimes keep deterministic latest-10 ordering
        a=rec/f'session_{i:02d}.areplay'; j=rec/f'session_{i:02d}.areplay.json'
        _touch_old(a, f'replay-{i}'.encode(), age_s=1200-i)
        _touch_old(j, f'meta-{i}'.encode(), age_s=1200-i)
    val=storage.local_path('validation')/'old_validation.json'; _touch_old(val,b'validation')
    log=storage.local_path('logs')/'old.log'; _touch_old(log,b'log')
    exp=storage.local_path('exports')/'old.txt'; _touch_old(exp,b'export')
    bak=storage.local_path('backups')/'old.zip'; _touch_old(bak,b'backup')

    migrator=BulkDataMigrator(storage,recording_stable_age_s=0)
    scan=migrator.scan_and_queue()
    assert scan['queued']==28
    worker=ServerSyncWorker(storage,ServerSyncConfig(share_root=share,enabled=True),create_initial_backup=False,enable_bulk_migration=False)
    result=worker.run_once()
    assert result['failed']==0 and result['pending']==0
    assert len(list(rec.glob('*.areplay')))==10
    assert len(list(rec.glob('*.areplay.json')))==10
    assert not val.exists() and not log.exists() and not exp.exists() and not bak.exists()
    assert len(list((share/'data'/'replays').glob('*.areplay')))==12
    assert len(list((share/'data'/'recordings').glob('*.areplay.json')))==12
    assert (share/'data'/'validation'/'old_validation.json').exists()
    status=migrator.status()
    assert status['retention']=='SERVER_MASTER_LOCAL_RETENTION'
    assert status['retention_policy']['recording_sessions_local']==10


def test_retention_never_deletes_changed_local_file(tmp_path):
    project=tmp_path/'project'; local=project/'user_data'; share=tmp_path/'share'; share.mkdir(parents=True)
    storage=StorageManager(project_root=project,local_root=local); storage.ensure_layout()
    source=storage.local_path('validation')/'changing.json'; _touch_old(source,b'first')
    m=BulkDataMigrator(storage,recording_stable_age_s=0); m.scan_and_queue()
    # change local source after queueing; retention must not remove it
    source.write_bytes(b'changed-after-queue')
    worker=ServerSyncWorker(storage,ServerSyncConfig(share_root=share,enabled=True),create_initial_backup=False,enable_bulk_migration=False)
    # V2.9.1.3.1: mutable historical artifacts are immutable staged snapshots.
    # The queued point-in-time snapshot may sync successfully, but retention must
    # still preserve the newer changed local source.
    out=worker.run_once()
    assert source.exists()
    assert out['failed']==0


def test_driver_deletion_journal_is_durable_and_30_day(tmp_path):
    storage=StorageManager(project_root=tmp_path,local_root=tmp_path/'user_data'); storage.ensure_layout()
    journal=DriverDeletionJournal(storage)
    path=journal.record({'driver_id':'abc123','display_name':'Driver','active_game':'f1_26','time_zone':'Asia/Kolkata'},deleted_sessions=5)
    payload=json.loads(path.read_text())
    assert payload['status']=='pending'
    assert payload['driver_id']=='abc123'
    assert payload['retention_days']==30
    assert payload['deleted_local_sessions']==5
    assert journal.pending_count()==1
    journal.mark_synced({**payload,'journal_path':str(path)},{'status':'retained','purge_after_utc':'future'})
    assert journal.pending_count()==0
    assert json.loads(path.read_text())['status']=='server_retained'


def test_server_backend_has_soft_delete_retention_and_separate_deleted_store():
    source=Path('server_deploy/main.py').read_text(encoding='utf-8')
    assert 'APP_VERSION="S14.4"' in source
    assert 'profile_driver_deletions' in source
    assert '/api/profile-drivers/{driver_id}/delete' in source
    assert '/api/profile-drivers/deleted' in source
    assert 'timedelta(days=retention_days)' in source
    assert 'performance_history_at_delete.sqlite3' in source
    assert 'deleted_drivers' in source


def test_client_holds_publishers_until_delete_tombstone_is_retained():
    source=Path('src/server_platform.py').read_text(encoding='utf-8')
    assert 'pending_deletions=self.driver_deletions.pending_count()' in source
    assert 'held_for_driver_retention' in source
    assert 'soft_delete_profile_driver' in source


def test_replay_selector_can_hydrate_server_master_replays():
    source=Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'available_remote_replays' in source
    assert 'hydrate_replay' in source
    assert 'SERVER' in source
