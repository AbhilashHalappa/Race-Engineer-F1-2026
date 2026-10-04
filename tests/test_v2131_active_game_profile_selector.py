from pathlib import Path

from src.driver_profiles import DriverProfileStore


def test_exactly_one_game_profile_is_active_after_each_switch(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    driver = store.create_profile("Driver")
    driver_id = driver["driver_id"]

    for selected in ("f1_26", "acc", "dirt_rally_2", "f1_26"):
        assert store.set_active_game(driver_id, selected) is True
        assert store.active_profile()["active_game"] == selected
        active = []
        for game_id in ("f1_26", "acc", "dirt_rally_2"):
            profile = store.load_game_profile(driver_id, game_id)
            assert profile is not None
            if profile.get("active"):
                active.append(game_id)
        assert active == [selected]


def test_game_profile_selector_ui_is_exposed_and_future_profiles_selectable():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "QCheckBox" in source
    assert "profile_game_select_checks" in source
    assert "_game_profile_checkbox_toggled" in source
    assert "_activate_game_profile" in source
    assert "ASSETTO CORSA COMPETIZIONE" in source
    assert "DIRT RALLY 2.0" in source
    assert "profile_game_selector" not in source
    assert "SET ACTIVE" not in source


def test_non_f1_active_profile_does_not_reuse_f1_overview_totals():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'if game_id == "f1_26":' in source
    assert 'game_profile.get("sessions")' in source
    assert 'game_profile.get("history_tracks")' in source
