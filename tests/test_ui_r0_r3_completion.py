from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOW = (ROOT / "src" / "overlay" / "window.py").read_text(encoding="utf-8")
THEME = (ROOT / "src" / "ui_theme.py").read_text(encoding="utf-8")


def test_control_center_replay_uses_authoritative_recordings_path():
    assert 'from ..app_paths import RECORDINGS' in WINDOW
    block = WINDOW.split('def _replay_recording_options(self):', 1)[1].split('def _select_replay_recording', 1)[0]
    assert 'RECORDINGS.glob("*.areplay")' in block
    assert 'Path("recordings")' not in block


def test_shared_overlay_chrome_covers_r2_interactions():
    for token in (
        'def _ensure_overlay_chrome', 'self.zoom_out', 'self.zoom_in',
        'self.reset_overlay_zoom', 'def _cycle_overlay_opacity',
        'def toggle_overlay_compact', 'self.showMinimized',
        'self.on_close() if self.on_close else self.hide()',
        'self._overlay_chrome_timer.setInterval(1800)',
    ):
        assert token in WINDOW


def test_r1_low_frequency_cards_are_collapsible_and_hardware_moved_to_own_tab():
    assert 'def _enable_card_collapse' in WINDOW
    for token in (
        'self._enable_card_collapse(ref_card, ref',
        'self._enable_card_collapse(audio_card, audio',
    ):
        assert token in WINDOW
    assert 'self._enable_card_collapse(hardware_card, hardware' not in WINDOW
    assert 'self.tabs.addTab(self.hardware_page, "HARDWARE")' in WINDOW


def test_r0_has_shared_button_classes_and_density_modes():
    assert 'BUTTON_CLASSES =' in THEME
    assert 'DENSITY_MODES =' in THEME
    for name in ('primary', 'secondary', 'destructive', 'icon', 'segmented', 'toggle'):
        assert f'"{name}"' in THEME


def test_r3_exit_handoff_is_visual_only():
    block = WINDOW.split('class ProgressivePreCornerOverlayWindow', 1)[1].split('class LiveCornerFeedbackOverlayWindow', 1)[0]
    assert "if phase=='EXIT'" in block
    assert 'HANDOFF → POST CORNER FEEDBACK' in block
    assert 'speak' not in block.lower()
