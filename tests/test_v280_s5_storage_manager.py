from pathlib import Path

from src.storage_manager import StorageManager, StorageState


def test_s5_storage_states_are_explicit():
    assert {x.value for x in StorageState} == {
        "LOCAL", "CACHED", "REMOTE", "PENDING_SYNC", "OFFLINE_FALLBACK"
    }


def test_s5_manager_owns_local_runtime_paths(tmp_path: Path):
    m = StorageManager(project_root=tmp_path)
    m.ensure_layout()
    assert m.local_path("drivers") == tmp_path / "user_data" / "drivers"
    assert m.get_track_map() == tmp_path / "user_data" / "tracks" / "maps"
    assert m.get_reference() == tmp_path / "user_data" / "references"
    assert m.recording_path() == tmp_path / "user_data" / "recordings"
    assert m.performance_history_db == tmp_path / "analysis" / "performance_history_live.sqlite3"
    assert m.local_path("drivers").is_dir()


def test_s5_queue_upload_is_local_manifest_only(tmp_path: Path):
    m = StorageManager(project_root=tmp_path, server_url="http://race-server:8765")
    source = tmp_path / "sample.areplay"
    source.write_bytes(b"abc")
    queued = m.queue_upload(source, category="recordings", metadata={"session": "x"})
    assert queued.state is StorageState.PENDING_SYNC
    items = m.pending_items()
    assert len(items) == 1
    assert items[0]["source"] == str(source)
    result = m.sync_pending()
    assert result["pending"] == 1
    assert result["attempted"] == 0
    assert result["sync_enabled"] is False


def test_s5_save_helpers_remain_local(tmp_path: Path):
    m = StorageManager(project_root=tmp_path)
    session = m.save_session("s1.json", {"id": 1})
    performance = m.save_performance("p1.json", {"score": 80})
    recording = m.save_recording("r1.areplay", b"ARERPL")
    assert session.state is StorageState.LOCAL and session.path.exists()
    assert performance.state is StorageState.LOCAL and performance.path.exists()
    assert recording.state is StorageState.LOCAL and recording.path.read_bytes() == b"ARERPL"


def test_s5_no_network_client_dependency_in_storage_manager():
    text = Path("src/storage_manager.py").read_text(encoding="utf-8")
    for forbidden in ("requests", "urllib.request", "http.client", "socket."):
        assert forbidden not in text
