from pathlib import Path


def test_backup_scope_excludes_runtime_and_reports_empty_setups():
    text = Path('server_deploy/race-engineer-backup.sh').read_text(encoding='utf-8')
    assert 'SETUPS_STATUS="EMPTY"' in text
    assert '"setups": {"status": "$SETUPS_STATUS", "files": $SETUPS_FILES}' in text
    assert 'backup_server_runtime' in text
    assert 'server/app/.venv' in text
    assert 'server/app/logs' in text
    assert 'REBUILD_FILES_ONLY' in text
    assert 'create_periodic_bundle' in text
    assert 'RUN_ARTIFACTS' in text
    assert 'PRAGMA quick_check' in text


def test_backup_does_not_directly_archive_entire_server_tree_for_periodic_bundle():
    text = Path('server_deploy/race-engineer-backup.sh').read_text(encoding='utf-8')
    assert 'tar -czf "$DEST/weekly_${STAMP}.tar.gz" -C "$ROOT"' not in text
    assert 'tar -czf "$DEST/monthly_${STAMP}.tar.gz" -C "$ROOT"' not in text
