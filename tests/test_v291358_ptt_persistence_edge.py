from pathlib import Path

from src.bulk_migration import BulkDataMigrator


def test_bulk_migration_skips_entire_ptt_runtime_tree(tmp_path):
    class DummyStorage:
        project_root = tmp_path
        def local_path(self, name):
            p = tmp_path / 'user_data' / name
            p.mkdir(parents=True, exist_ok=True)
            return p
    m = BulkDataMigrator.__new__(BulkDataMigrator)
    m.storage = DummyStorage()
    assert m._skip(tmp_path / 'user_data' / 'logs' / 'ptt' / 'hid_mapping.json') is True
    assert m._skip(tmp_path / 'user_data' / 'logs' / 'ptt' / 'ptt_20261001.wav') is True
    assert m._skip(tmp_path / 'user_data' / 'logs' / 'other.log') is False


def test_ptt_runtime_path_guard():
    assert BulkDataMigrator._is_ptt_runtime_path(Path('user_data/logs/ptt/hid_mapping.json'))
    assert BulkDataMigrator._is_ptt_runtime_path(Path('logs/ptt/capture.wav'))
    assert not BulkDataMigrator._is_ptt_runtime_path(Path('user_data/logs/app.log'))
