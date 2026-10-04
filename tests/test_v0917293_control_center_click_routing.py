from pathlib import Path
import ast

SOURCE_PATH = Path('src/overlay/window.py')


def _source():
    return SOURCE_PATH.read_text(encoding='utf-8')


def _class_node(name):
    tree = ast.parse(_source())
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)


def test_control_center_uses_direct_callbacks_not_semantic_dispatcher():
    source = _source()
    ctor = source[source.index('class ControlCenterWindow'):source.index('class DriverOverlayWindow')]
    assert 'on_show_overlay=None' not in ctor
    assert 'self._dispatch_overlay' not in ctor
    assert 'button.clicked.connect(partial(self._launch_overlay, key, tip, callback))' in ctor


def test_direct_launcher_helper_invokes_exact_callback():
    source = _source()
    block = source.split('def _launch_overlay(self, key, description, callback', 1)[1].split('def refresh_reference_options', 1)[0]
    assert 'callback()' in block
    assert '[UI] Launcher {key} -> {description}' in block


def test_control_center_defines_all_launcher_callbacks_explicitly():
    source = _source()
    expected = {
        'C': 'on_show_coach', 'RE': 'on_show_race_engineer', 'R': 'on_show_replay',
        'RT': 'on_show_radio_transcript', 'SS': 'on_show_session_summary',
        'DI': 'on_show_driver', 'RI': 'on_show_reference_driver', 'Δ': 'on_show_speed_delta',
        'L': 'on_show_laptime', 'TW': 'on_show_tyre_wear', 'F': 'on_show_fuel',
        'W': 'on_show_weather', 'S': 'on_show_standings', 'H': 'on_show_lap_history',
        'TS': 'on_show_tyre_sets', 'EB': 'on_show_ers_battery',
    }
    for key, callback in expected.items():
        assert f'("{key}",' in source
        assert callback in source


def test_no_stray_dispatcher_assignment_in_coach_window():
    coach = _class_node('CoachOverlayWindow')
    assert not any(
        isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == '_on_show_overlay' for t in n.targets)
        for n in ast.walk(coach)
    )
