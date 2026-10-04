from pathlib import Path
import io
import sqlite3
import tarfile

from src.server_platform import ServerBackupRestoreManager, ServerPlatformConfig
from src.storage_manager import StorageManager


class FakeApi:
    def __init__(self):
        self.calls=[]
    def put_snapshot(self, kind, source, sha256_hex=None):
        self.calls.append((kind, Path(source), sha256_hex))
        return {"status":"stored","kind":kind,"published":True}


def _db(path: Path, rows: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as c:
        c.execute("create table sessions(id integer primary key, track_name text)")
        c.execute("create table drivers(id integer primary key, name text)")
        for i in range(rows):
            c.execute("insert into sessions(track_name) values(?)", (f"Track{i}",))
        c.execute("insert into drivers(name) values('Driver')")
        c.commit()


def _driver_tar(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload=b'{"active_driver_id":"restored"}'
    with tarfile.open(path, "w:gz") as tf:
        info=tarfile.TarInfo("drivers/index.json")
        info.size=len(payload)
        info.mtime=1700000000
        tf.addfile(info, io.BytesIO(payload))


def test_recent_backup_list_and_one_click_restore(tmp_path):
    project=tmp_path/"project"; share=tmp_path/"share"
    storage=StorageManager(project_root=project); storage.ensure_layout()
    storage.performance_history_db.parent.mkdir(parents=True, exist_ok=True)
    _db(storage.performance_history_db, 1)
    drivers=storage.local_path("drivers"); drivers.mkdir(parents=True, exist_ok=True)
    (drivers/"index.json").write_text('{"active_driver_id":"local"}', encoding="utf-8")

    stamp="20261003T030455Z"
    root=share/"backups"/"automated"; root.mkdir(parents=True)
    _db(root/f"performance_history_live_{stamp}.sqlite3", 3)
    _driver_tar(root/f"drivers_{stamp}.tar.gz")

    api=FakeApi()
    mgr=ServerBackupRestoreManager(storage, ServerPlatformConfig(api_url="http://server", share_root=share), api)
    rows=mgr.list_recent()
    assert rows and rows[0]["stamp"] == stamp
    assert rows[0]["driver_profiles"] is True

    result=mgr.restore(stamp)
    assert result["status"] == "restored"
    assert result["verified"]["sessions"] == 3
    with sqlite3.connect(storage.performance_history_db) as c:
        assert c.execute("select count(*) from sessions").fetchone()[0] == 3
    assert 'restored' in (drivers/"index.json").read_text(encoding="utf-8")
    assert {c[0] for c in api.calls} == {"performance_history.sqlite3", "driver_profiles.zip"}
    rollback=Path(result["rollback"])
    assert (rollback/"performance_history_live.sqlite3").is_file()
    assert (rollback/"drivers"/"index.json").is_file()


def test_restore_ui_has_recent_backup_selector_and_single_action():
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "RECENT BACKUP" in text
    assert "RESTORE SELECTED" in text
    assert "ServerBackupRestoreManager().restore" in text
    assert "End or leave the live F1 session" in text
    assert "rollback snapshot" in text.lower()


def test_restore_uses_sqlite_backup_api_and_does_not_replace_live_db_file(tmp_path, monkeypatch):
    project=tmp_path/"project"; share=tmp_path/"share"
    storage=StorageManager(project_root=project); storage.ensure_layout()
    storage.performance_history_db.parent.mkdir(parents=True, exist_ok=True)
    _db(storage.performance_history_db, 1)
    stamp="20261003T104003Z"
    root=share/"backups"/"automated"; root.mkdir(parents=True)
    _db(root/f"performance_history_live_{stamp}.sqlite3", 4)

    # Simulate the exact Windows failure from .36: any attempt to replace the
    # live performance database must fail.  The hotfix must not need os.replace
    # for the SQLite DB at all.
    import src.server_platform as sp
    real_replace=sp.os.replace
    live=storage.performance_history_db.resolve()
    def guarded_replace(src, dst):
        if Path(dst).resolve() == live:
            raise PermissionError(5, "Access is denied")
        return real_replace(src, dst)
    monkeypatch.setattr(sp.os, "replace", guarded_replace)

    # Keep a reader attached while restore runs, matching Control Center / Hub.
    reader=sqlite3.connect(storage.performance_history_db)
    try:
        assert reader.execute("select count(*) from sessions").fetchone()[0] == 1
        mgr=ServerBackupRestoreManager(storage, ServerPlatformConfig(api_url="http://server", share_root=share), FakeApi())
        result=mgr.restore(stamp)
        assert result["verified"]["sessions"] == 4
        with sqlite3.connect(storage.performance_history_db) as c:
            assert c.execute("select count(*) from sessions").fetchone()[0] == 4
    finally:
        reader.close()
