from pathlib import Path


def test_race_engineer_uses_single_atomic_body_and_forced_repaint():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    start = source.index('class RaceEngineerOverlayWindow')
    end = source.index('class ERSBatteryOverlayWindow', start)
    block = source[start:end]
    assert 'self.body = QLabel()' in block
    assert 'self.body.setText(html)' in block
    assert 'self.body.repaint()' in block
    assert 'self._last_render_lap = s.lap_number' in block
    # Old multi-label renderer must not remain in the class.
    assert 'self.current_values = {}' not in block
