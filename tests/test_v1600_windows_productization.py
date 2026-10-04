from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace as NS
import json
import sys
import urllib.request

from src.product_settings import ProductSettings, ProductSettingsStore, PRODUCT_SETTINGS_SCHEMA
from src.product_setup import setup_snapshot, apply_setup
from src.crash_reporting import _write_crash
from src.update_checker import _version_tuple
from src.settings_ui import lan_qr_svg


def test_product_settings_roundtrip_and_validation(tmp_path):
    store=ProductSettingsStore(tmp_path/'settings/product.json')
    s=store.set(setup_complete=True,dash_port=99999,ptt_button=300,wheel_port='auto')
    assert s.setup_complete and s.dash_port==65535 and s.ptt_button==255 and s.wheel_port is None
    assert ProductSettingsStore(store.path).settings.schema==PRODUCT_SETTINGS_SCHEMA


def test_product_settings_migrates_old_partial_file(tmp_path):
    p=tmp_path/'settings/product.json'; p.parent.mkdir(); p.write_text('{"setup_complete":true,"dash_port":9000,"unknown":42}')
    s=ProductSettingsStore(p).settings
    assert s.setup_complete and s.dash_port==9000 and not hasattr(s,'unknown')


def test_setup_snapshot_and_save_are_hardware_safe(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    snap=setup_snapshot(root='.')
    assert 'settings' in snap and 'audio' in snap and 'wheel_ports' in snap and 'hid_devices' in snap
    out=apply_setup({'setup_complete':True,'udp_port':20777},root='.')
    assert out['settings']['setup_complete'] is True and Path('settings/product.json').exists()


def test_crash_report_written(tmp_path):
    try:
        raise RuntimeError('boom-product-test')
    except RuntimeError:
        et,ev,tb=sys.exc_info()
        path=_write_crash(et,ev,tb,thread_name='test',root=tmp_path)
    text=path.read_text()
    assert 'boom-product-test' in text and 'thread' in text
    assert (tmp_path/'logs/crash/latest_crash.log').exists()


def test_update_version_comparison_normalizes_tags():
    assert _version_tuple('V1.6.0.1') > _version_tuple('1.6.0.0')
    assert _version_tuple('v1.6') == (1,6,0,0)


def test_qr_svg_is_offline_bytes():
    raw=lan_qr_svg('http://192.168.1.2:8765/')
    assert raw.startswith(b'<?xml') or b'<svg' in raw[:500]


def test_packaging_files_exist_and_preserve_user_data():
    root=Path(__file__).resolve().parents[1]
    iss=(root/'installer/RaceEngineer.iss').read_text(encoding='utf-8')
    exe_build=(root/'build_exe.ps1').read_text(encoding='utf-8')
    build=(root/'build_release.ps1').read_text(encoding='utf-8')
    assert 'PrivilegesRequired=lowest' in iss
    assert 'Excludes: "settings\\*;user_data\\*;recordings\\*;analysis\\*;logs\\*;references\\*;maps\\*;voices\\*"' in iss
    assert 'bootstrapper_windows.go' in exe_build and 'runtime_dependencies.json' in exe_build
    assert 'Compress-Archive' in build and 'ISCC' in build


def test_dashboard_setup_routes(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.dashboard_server import DashboardStateStore, RemoteDashboardServer
    server=RemoteDashboardServer(DashboardStateStore(),host='127.0.0.1',port=0)
    info=server.start()
    try:
        with urllib.request.urlopen(info.local_url+'setup',timeout=3) as r:
            html=r.read().decode(); assert 'First Run Setup' in html
        with urllib.request.urlopen(info.local_url+'api/setup',timeout=3) as r:
            data=json.loads(r.read()); assert 'settings' in data
        with urllib.request.urlopen(info.local_url+'api/lan-qr.svg',timeout=3) as r:
            raw=r.read(); assert b'<svg' in raw[:500] or raw.startswith(b'<?xml')
        req=urllib.request.Request(info.local_url+'api/setup',data=json.dumps({'action':'save','changes':{'setup_complete':True}}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=3) as r:
            data=json.loads(r.read()); assert data['ok'] is True
        assert ProductSettingsStore().settings.setup_complete
    finally:
        server.stop()


def test_upgrade_backup_preserves_user_data(tmp_path):
    from src.product_migration import create_upgrade_backup_if_needed
    (tmp_path/'settings').mkdir(); (tmp_path/'settings/coaching.json').write_text('{"x":1}')
    (tmp_path/'references').mkdir(); (tmp_path/'references/r.json').write_text('{"r":1}')
    out=create_upgrade_backup_if_needed(root=tmp_path,version='1.6.0.0')
    assert out and out.exists()
    import zipfile
    with zipfile.ZipFile(out) as z:
        names=set(z.namelist())
    assert 'settings/coaching.json' in names and 'references/r.json' in names
    assert create_upgrade_backup_if_needed(root=tmp_path,version='1.6.0.0') is None


def test_display_validation_is_safe_cross_platform():
    from src.windows_validation import display_environment
    d=display_environment(); assert 'windows' in d and 'monitor_count' in d and 'dpi' in d


def test_complete_config_export_includes_reference_and_hid_map(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path/'settings').mkdir(); (tmp_path/'settings/product.json').write_text('{}')
    (tmp_path/'maps').mkdir(); (tmp_path/'maps/cache.json').write_text('{}')
    (tmp_path/'references').mkdir(); (tmp_path/'references/ref.json').write_text('{}')
    (tmp_path/'logs/ptt').mkdir(parents=True); (tmp_path/'logs/ptt/hid_mapping.json').write_text('{}')
    from src.settings_ui import export_configuration
    import zipfile
    out=export_configuration('cfg.zip')
    with zipfile.ZipFile(out) as z: names=set(z.namelist())
    assert {'settings/product.json','maps/cache.json','references/ref.json','logs/ptt/hid_mapping.json'} <= names
