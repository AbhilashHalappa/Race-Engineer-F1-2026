from pathlib import Path
import sqlite3, json, os, time
from src.storage_manager import StorageManager
from src.server_platform import ReferenceTrackMigrator, PerformanceDatabasePublisher, DriverProfilePublisher, ServerPlatformConfig, ServerPlatformCoordinator

class FakeApi:
    performance_hub_url='http://server/performance-hub'
    def __init__(self): self.calls=[]
    def health(self): return {'status':'online','hostname':'race-server','database':{'status':'online'}}
    def put_snapshot(self, kind, source, sha256_hex=None):
        self.calls.append((kind, Path(source), sha256_hex)); return {'status':'stored','kind':kind,'published':True}

def manager(tmp_path):
    m=StorageManager(project_root=tmp_path); m.ensure_layout(); return m

def test_s8_reference_track_master_queue_retains_local_cache(tmp_path):
    m=manager(tmp_path)
    ref=m.local_path('references')/'pack'/'ref.json'; ref.parent.mkdir(parents=True); ref.write_text('ref')
    track=m.local_path('tracks')/'maps'/'melbourne.json'; track.parent.mkdir(parents=True,exist_ok=True); track.write_text('track')
    mig=ReferenceTrackMigrator(m); out=mig.scan_and_queue(); assert out['queued']==2
    items=m.pending_items(); remotes={i['remote_relpath'] for i in items}
    assert 'data/references/pack/ref.json' in remotes
    assert 'data/track_maps/maps/melbourne.json' in remotes
    assert ref.exists() and track.exists()
    assert mig.status()['policy']=='SERVER_MASTER_LOCAL_CACHE'

def test_s9_performance_sqlite_published_from_consistent_snapshot(tmp_path):
    m=manager(tmp_path); m.performance_history_db=tmp_path/'analysis'/'performance_history_live.sqlite3'; m.performance_history_db.parent.mkdir()
    with sqlite3.connect(m.performance_history_db) as c:
        c.execute('create table sessions(id integer primary key, name text)'); c.execute("insert into sessions(name) values('one')"); c.commit()
    api=FakeApi(); pub=PerformanceDatabasePublisher(m,api)
    out=pub.publish_if_changed(force=True); assert out['status']=='published'; assert api.calls and api.calls[0][0]=='performance_history.sqlite3'
    snap=api.calls[0][1]
    with sqlite3.connect(snap) as c: assert c.execute('select count(*) from sessions').fetchone()[0]==1

def test_s9_offline_publish_never_raises_into_live_runtime(tmp_path):
    m=manager(tmp_path); m.performance_history_db=tmp_path/'analysis'/'performance_history_live.sqlite3'; m.performance_history_db.parent.mkdir()
    with sqlite3.connect(m.performance_history_db) as c: c.execute('create table x(v integer)'); c.commit()
    class Broken(FakeApi):
        def put_snapshot(self,*a,**k): raise OSError('server unavailable')
    out=PerformanceDatabasePublisher(m,Broken()).publish_if_changed(force=True)
    assert out['status']=='offline_fallback'

def test_s11_ui_and_s10_server_hub_markers_present():
    text=Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'self.tabs.addTab(self.server_page, "SERVER")' in text
    assert 'OPEN PERFORMANCE HUB' in text and 'SYNC NOW' in text
    assert 'ServerApiClient().performance_hub_url' in text
    assert 'LOCAL FALLBACK' in text

def test_s12_server_deploy_has_backup_timer_and_s14_backend():
    root=Path('server_deploy')
    assert (root/'install_s14.sh').exists()
    assert 'race-engineer-backup.timer' in (root/'install_s14.sh').read_text()
    main=(root/'main.py').read_text()
    assert '/api/snapshots/{kind}' in main
    assert '/performance-hub' in main
    assert 'APP_VERSION="S14.4"' in main

def test_s14_main_starts_background_platform_and_never_requires_server():
    text=Path('src/main.py').read_text()
    assert 'start_default_server_platform' in text
    assert 'Server support is optional' in text


def test_s14_server_tab_uses_defined_theme_accent_and_current_banner():
    window = Path('src/overlay/window.py').read_text(encoding='utf-8')
    main = Path('src/main.py').read_text(encoding='utf-8')
    assert 'RACE ENGINEER DATA SERVER", 13, True, TOKENS.cyan' in window
    assert 'True, CYAN' not in window
    assert 'V2.9.1.2 S13 Live Telemetry Freshness + Performance Hub Auto Refresh' in main


def test_v2902_server_status_accuracy_source_contract():
    platform = Path("src/server_platform.py").read_text(encoding="utf-8")
    window = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert '"api_latency_ms"' in platform
    assert '"pending_files"' in platform
    assert '"historical_files"' in platform
    assert '"current_transfer"' in platform
    assert '"Sync State"' in window
    assert '"Pending Files"' in window
    assert '"Pending Data"' in window
    assert '"Current Transfer"' in window
    assert 'WAITING FOR FIRST BACKUP' in window


def test_v2904_original_performance_hub_is_restored_and_server_hub_stays_separate():
    window = Path("src/overlay/window.py").read_text(encoding="utf-8")
    # Restore the exact pre-server Control Center behavior: embed the full local
    # browser Performance Hub when QtWebEngine is available.
    tab = window.split("def _build_performance_hub_tab", 1)[1].split("def _build_performance_hub_fallback", 1)[0]
    assert "QWebEngineView" in tab
    assert 'self.dashboard_url + "performance"' in tab
    assert "ServerApiClient" not in tab
    assert "return self._build_performance_hub_fallback()" in tab

    # The explicit local browser action also stays on the gaming-PC dashboard.
    local_open = window.split("def _open_performance_browser", 1)[1].split("def _performance_driver_changed", 1)[0]
    assert 'self.dashboard_url + "performance"' in local_open
    assert "ServerApiClient" not in local_open

    # Server-hosted Performance Hub remains separately launched from SERVER.
    server_open = window.split("def _open_server_performance_hub", 1)[1].split("def _open_server_folder", 1)[0]
    assert "ServerApiClient().performance_hub_url" in server_open


def test_v2904_server_status_styles_use_css_strings():
    window = Path("src/overlay/window.py").read_text(encoding="utf-8")
    refresh = window.split("def refresh_server_tab", 1)[1].split("def _build_performance_hub_tab", 1)[0]
    assert "_rgba(GREEN if state=='ONLINE' else AMBER)" in refresh
    assert "_rgba(GREEN if sync_state=='REMOTE' else TOKENS.cyan if sync_state=='SYNCING' else AMBER)" in refresh


def test_v2904_atomic_json_writer_uses_unique_temp_and_retry():
    storage = Path("src/storage_manager.py").read_text(encoding="utf-8")
    block = storage.split("def _write_json_atomic", 1)[1].split("def save_session", 1)[0]
    assert "uuid.uuid4().hex" in block
    assert "os.replace(tmp, path)" in block
    assert "except PermissionError" in block
    assert "time.sleep" in block


def test_v2905_driver_profile_publisher_builds_atomic_snapshot(tmp_path):
    m=manager(tmp_path)
    root=m.local_path('drivers'); root.mkdir(parents=True,exist_ok=True)
    did='abc123'
    (root/did/'games'/'f1_26').mkdir(parents=True)
    (root/'index.json').write_text(json.dumps({'schema_version':1,'active_driver_id':did,'drivers':[{'driver_id':did}]}),encoding='utf-8')
    (root/did/'profile.json').write_text(json.dumps({'driver_id':did,'display_name':'Abhilash H','active_game':'f1_26','time_zone':'Asia/Kolkata'}),encoding='utf-8')
    (root/did/'games'/'f1_26'/'profile.json').write_text(json.dumps({'driver_id':did,'game_id':'f1_26'}),encoding='utf-8')
    api=FakeApi(); pub=DriverProfilePublisher(m,api)
    out=pub.publish_if_changed(force=True)
    assert out['status']=='published'
    assert out['source_files']==3
    assert api.calls and api.calls[0][0]=='driver_profiles.zip'
    import zipfile
    with zipfile.ZipFile(api.calls[0][1],'r') as zf:
        names=set(zf.namelist())
    assert 'index.json' in names and f'{did}/profile.json' in names

def test_v2905_driver_profile_source_contract_and_server_publish():
    platform=Path('src/server_platform.py').read_text(encoding='utf-8')
    server=Path('server_deploy/main.py').read_text(encoding='utf-8')
    window=Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'class DriverProfilePublisher' in platform
    assert 'driver_profiles.zip' in platform
    assert 'publish_driver_profiles' in server
    assert 'ROOT/"data"/"drivers"' in server
    assert '/api/profile-drivers' in server
    assert 'c.execute("DELETE FROM profile_drivers")' in server
    assert 'CREATE TABLE IF NOT EXISTS profile_drivers' in server
    assert 'DELETE FROM drivers' not in server
    assert '"Driver Profiles"' in window


def test_v2907_backup_now_verified_restore_and_sync_state_correction_contract():
    window=Path('src/overlay/window.py').read_text(encoding='utf-8')
    platform=Path('src/server_platform.py').read_text(encoding='utf-8')
    server=Path('server_deploy/main.py').read_text(encoding='utf-8')
    backup=Path('server_deploy/race-engineer-backup.sh').read_text(encoding='utf-8')
    assert 'BACKUP NOW' in window
    assert 'def _server_backup_now' in window
    assert 'pf == 0 and state == "ONLINE"' in window
    assert 'def trigger_backup' in platform and '/api/backup' in platform
    assert 'pending_files == 0' in platform and 'StorageState.PENDING_SYNC.value' in platform
    assert '@app.post("/api/backup")' in server
    assert '"backup":backup_status' in server
    assert 'APP_VERSION="S14.4"' in server
    assert 'PRAGMA quick_check' in backup
    assert 'BACKUP_STATUS.json' in backup
    assert 'LAST_VERIFY_UTC' in backup
    assert 'tar -xzf' in backup
    assert '"daily": 7, "weekly": 4, "monthly": 3' in backup
