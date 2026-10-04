from pathlib import Path


def test_control_center_direct_one_button_one_callback():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "button.clicked.connect(partial(self._launch_overlay, key, tip, callback))" in source
    assert "def _launch_overlay(self, key, description, callback" in source
    assert "[UI] Launcher {key} -> {description}" in source
    # The Control Center no longer depends on the V0.9.17.2.9 semantic dispatch path.
    ctor = source[source.index("class ControlCenterWindow"):source.index("class DriverOverlayWindow")]
    assert "on_show_overlay=None" not in ctor
    assert "self._dispatch_overlay" not in ctor


def test_control_center_reserves_real_space_for_lower_rows():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "HEIGHT = 610" in source
    assert "grid.setRowMinimumHeight(row, 30)" in source
    assert "self.resize(required)" in source
    assert "self.setMinimumSize(340, 560)" in source


def test_every_launcher_has_explicit_direct_callback():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    expected = {
        "C": "on_show_coach", "RE": "on_show_race_engineer", "R": "on_show_replay",
        "RT": "on_show_radio_transcript", "SS": "on_show_session_summary",
        "DI": "on_show_driver", "RI": "on_show_reference_driver", "Δ": "on_show_speed_delta",
        "L": "on_show_laptime", "TW": "on_show_tyre_wear", "F": "on_show_fuel",
        "W": "on_show_weather", "S": "on_show_standings", "H": "on_show_lap_history",
        "TS": "on_show_tyre_sets", "EB": "on_show_ers_battery",
    }
    for key, callback in expected.items():
        assert f'("{key}",' in source
        assert callback in source
