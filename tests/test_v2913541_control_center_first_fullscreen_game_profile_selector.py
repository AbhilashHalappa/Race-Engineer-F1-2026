from pathlib import Path

SOURCE = Path(__file__).parents[1] / "src" / "overlay" / "window.py"


def test_first_fullscreen_reflow_is_scheduled_after_native_layout_settles():
    source = SOURCE.read_text(encoding="utf-8")
    assert "def _schedule_control_center_reflow" in source
    assert "QEvent.WindowStateChange" in source
    assert "for delay in (0, 60, 180)" in source
    assert "QTimer.singleShot(0, self._apply_control_center_reflow)" in source


def test_game_profile_checkbox_has_explicit_dark_theme_indicator():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'setObjectName("gameProfileSelector")' in source
    assert "QCheckBox#gameProfileSelector::indicator" in source
    assert "QCheckBox#gameProfileSelector::indicator:checked" in source
    assert "background:#4dd9ff" in source
