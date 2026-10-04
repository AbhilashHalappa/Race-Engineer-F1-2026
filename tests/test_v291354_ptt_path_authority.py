from pathlib import Path

def test_ptt_default_uses_canonical_user_data_path():
    from src.ptt import PTTConfig
    from src.app_paths import PTT_LOGS
    assert Path(PTTConfig().output_dir) == PTT_LOGS

def test_bulk_migration_still_skips_ptt_wav():
    from src.bulk_migration import BulkDataMigrator
    assert BulkDataMigrator()._skip(Path('user_data/logs/ptt/ptt_20261001_120000.wav'))
