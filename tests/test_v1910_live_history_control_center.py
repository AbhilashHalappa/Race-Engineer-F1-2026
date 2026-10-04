from pathlib import Path
from src.race_state_receiver import persistent_history_allowed
from src.performance_history import PerformanceHistoryStore


def test_performance_history_authority_is_live_only():
    assert persistent_history_allowed("live") is True
    assert persistent_history_allowed("LIVE") is True
    assert persistent_history_allowed("replay") is False
    assert persistent_history_allowed("") is False


def test_default_history_database_is_explicitly_live_only():
    store = PerformanceHistoryStore()
    assert store.path.as_posix().endswith("analysis/performance_history_live.sqlite3")


def test_receiver_gates_both_progress_and_performance_history():
    source = Path("src/race_state_receiver.py").read_text(encoding="utf-8")
    # Legacy JSON progress history remains gated inside optional coach-report
    # generation, while V1.9.2.1 deliberately persists the SQLite Performance
    # Hub independently of auto_reports. Both authorities must remain LIVE-only.
    assert 'persistent_history_allowed(self.telemetry_mode())' in source
    assert 'coach_settings.progress_history and persist_live_history' in source
    independent = source[source.index('V1.9.2.1: the Performance Hub'):source.index('if speak and not self._finish_radio_sent')]
    assert 'if persist_live_history:' in independent
    assert 'Replay session ignored (live history unchanged)' in independent


def test_control_center_is_normal_window_with_performance_tab():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    cc = source[source.index("class ControlCenterWindow"):source.index("class DriverOverlayWindow")]
    assert 'self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)' in cc
    assert 'self.tabs.addTab(self.control_page, "CONTROL")' in cc
    assert 'self.tabs.addTab(self.performance_page, "PERFORMANCE HUB")' in cc
    assert 'LIVE GAME HISTORY ONLY' in cc
    assert 'def _force_topmost(self):' in cc
    assert 'Control Center is an application window and must never force topmost' in cc


def test_browser_performance_hub_is_still_available():
    server = Path("src/dashboard_server.py").read_text(encoding="utf-8")
    assert 'if path in {"/performance", "/performance/"}' in server
    assert 'PerformanceHistoryStore().overview' in server


def test_control_center_performance_hub_has_driver_selector_and_dark_tables():
    cc = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "performance_driver_combo" in cc
    assert "set_preferred_driver" in cc
    assert "_style_performance_table" in cc
    assert "background:#0d141c" in cc
    assert "verticalHeader().setVisible(False)" in cc
