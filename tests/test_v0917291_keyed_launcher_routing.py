from pathlib import Path


def _source():
    return Path('src/overlay/window.py').read_text(encoding='utf-8')


def test_control_center_uses_direct_bound_callbacks():
    source = _source()
    assert 'button.setProperty("overlayKey", key)' in source
    assert 'button.clicked.connect(partial(self._launch_overlay, key, tip, callback))' in source
    assert 'def _launch_overlay(self, key, description, callback' in source
    cc = source.split('class ControlCenterWindow', 1)[1].split('class DriverOverlayWindow', 1)[0]
    assert 'on_show_overlay=None' not in cc
    assert 'self._dispatch_overlay' not in cc


def test_expected_direct_routes_are_explicit():
    source = _source()
    assert '("RE", "Race / Qualifying Engineer",              on_show_race_engineer' in source
    assert '("RI", "Reference Inputs — throttle / brake / ERS", on_show_reference_driver' in source
    assert '("W",  "Weather",                                 on_show_weather' in source


def test_launcher_grid_labels_and_positions_are_fixed():
    source = _source()
    assert 'on_show_race_engineer,      0, 1)' in source
    assert 'on_show_reference_driver, 1, 1)' in source
    assert 'on_show_weather,            2, 1)' in source
