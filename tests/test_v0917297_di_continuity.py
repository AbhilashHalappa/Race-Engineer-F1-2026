from pathlib import Path


def _driver_section():
    source = Path('src/overlay/window.py').read_text()
    return source.split('class DriverOverlayWindow', 1)[1].split('class ReferenceInputsOverlayWindow', 1)[0]


def test_driver_inputs_treats_normal_next_lap_as_continuous():
    section = _driver_section()
    assert 'normal_next_lap = (s.lap_number == self._last_lap + 1)' in section
    assert 'lap_seek_or_reset = lap_changed and not normal_next_lap' in section


def test_driver_inputs_does_not_clear_on_every_lap_change():
    section = _driver_section()
    assert 'if lap_changed or rewound or distance_rewound:' not in section
    assert 'if lap_seek_or_reset or rewound or distance_rewound:' in section


def test_driver_inputs_reference_independent_comment_and_logic():
    section = _driver_section()
    assert 'intentionally independent of the coaching reference' in section
    assert 'reference_time_s' not in section


def test_banner_updated():
    source = Path('src/main.py').read_text()
    assert 'V0.9.17.2.9.7 DI CONTINUOUS ACROSS REFERENCE/LAP BOUNDARY' in source
