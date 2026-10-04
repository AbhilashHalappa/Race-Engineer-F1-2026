from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_window_imports_amber_for_pending_reference_status():
    source = (ROOT / 'src' / 'overlay' / 'window.py').read_text(encoding='utf-8')
    assert '    AMBER,\n)' in source
    assert 'PENDING:' in source


def test_driver_and_reference_use_shared_distance_cursor():
    source = (ROOT / 'src' / 'overlay' / 'window.py').read_text(encoding='utf-8')
    assert source.count('self.input_trace.set_distance_cursor(s.lap_distance_m)') >= 2
    assert source.count('self.ers_trace.set_distance_cursor(s.lap_distance_m)') >= 2


def test_input_widget_uses_fixed_distance_window():
    source = (ROOT / 'src' / 'overlay' / 'widgets.py').read_text(encoding='utf-8')
    assert 'self.distance_window_m = 500.0' in source
    assert 'd0 = max(0.0, d1 - self.distance_window_m)' in source
    assert 'trailing-500m' in source


def test_banner_updated():
    source = (ROOT / 'src' / 'main.py').read_text(encoding='utf-8')
    assert ('V0.9.17.2.9.8 SHARED DISTANCE AXIS + REFERENCE STATUS HOTFIX' in source or 'V0.9.17.2.9.9 10MS DI-MASTER INPUT SAMPLING' in source)
