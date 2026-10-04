from pathlib import Path

SRC = Path('src/overlay/window.py').read_text(encoding='utf-8')


def test_manual_sync_wakes_background_coordinator_instead_of_running_inline():
    block = SRC.split('    def _server_sync_now(self):', 1)[1].split('    def _finish_manual_sync_ui', 1)[0]
    assert 'start_default_server_platform' in block
    assert '.wake()' in block
    assert '.run_once(' not in block
    assert 'SYNCING…' in block


def test_tab_switch_does_not_reload_webengine_pages():
    block = SRC.split('    def _tab_changed(self, index):', 1)[1].split('    def _open_performance_browser', 1)[0]
    assert '.reload()' not in block


def test_webengine_surfaces_use_dark_background():
    assert 'setBackgroundColor(QColor("#080d12"))' in SRC
    assert 'QWidget#performanceHubPage{background:#080d12;}' in SRC
    assert 'QWidget#helpPage{background:#080d12;}' in SRC
