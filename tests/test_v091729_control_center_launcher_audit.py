from pathlib import Path


def test_launcher_registry_has_expected_unique_keys():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    expected = ['C','RE','R','RT','SS','DI','RI','Δ','L','TW','F','W','S','H','TS','EB']
    for key in expected:
        assert f'("{key}",' in source
    assert 'button.setProperty("overlayKey", key)' in source


def test_launcher_positions_are_explicit_and_stable():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'on_show_race_engineer,      0, 1)' in source
    assert 'on_show_reference_driver, 1, 1)' in source
    assert 'on_show_weather,            2, 1)' in source
    assert 'buttons.insert(' not in source
    assert 'self.overlay_buttons[key] = button' in source


def test_routing_is_directly_bound_in_control_center():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'button.clicked.connect(partial(self._launch_overlay, key, tip, callback))' in source
    assert 'print(f"[UI] Launcher {key} -> {description}"' in source
