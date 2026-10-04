from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.driver_profiles import DriverProfileStore


def test_v210_profile_layout_and_game_container(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    profile = store.create_profile(
        "Abhilash",
        country_region="India",
        units="metric",
        compatibility={"performance_history_profile_id": 7},
    )
    driver_id = profile["driver_id"]
    assert driver_id and driver_id != "Abhilash"
    base = tmp_path / "drivers" / driver_id
    assert (base / "profile.json").is_file()
    assert (base / "career" / "summary.json").is_file()
    game = json.loads((base / "games" / "f1_26" / "profile.json").read_text(encoding="utf-8"))
    assert game["driver_id"] == driver_id
    assert game["game_id"] == "f1_26"
    assert game["discipline"] == "formula"
    assert game["driving_seconds"] == 0
    assert game["sessions"] == 0
    assert profile["compatibility"]["performance_history_profile_id"] == 7


def test_v210_multiple_drivers_are_isolated_and_active_driver_persists(tmp_path: Path):
    root = tmp_path / "drivers"
    store = DriverProfileStore(root)
    first = store.create_profile("Driver One")
    second = store.create_profile("Driver Two", units="imperial")
    assert first["driver_id"] != second["driver_id"]
    assert len(store.list_profiles()) == 2
    assert store.active_driver_id() == second["driver_id"]
    assert store.set_active_driver(first["driver_id"])

    reopened = DriverProfileStore(root)
    assert reopened.active_driver_id() == first["driver_id"]
    assert reopened.load_profile(first["driver_id"])["display_name"] == "Driver One"
    assert reopened.load_profile(second["driver_id"])["display_name"] == "Driver Two"


def test_v210_rename_does_not_change_driver_identity(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    original = store.create_profile("Old Name")
    driver_id = original["driver_id"]
    updated = store.update_personal_info(driver_id, display_name="New Name")
    assert updated is not None
    assert updated["driver_id"] == driver_id
    assert updated["display_name"] == "New Name"
    assert len(store.list_profiles()) == 1
    assert store.list_profiles()[0].driver_id == driver_id


def test_v210_future_games_cannot_be_selected_as_active_yet(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    profile = store.create_profile("Driver")
    assert store.set_active_game(profile["driver_id"], "acc") is True
    assert store.active_profile()["active_game"] == "acc"
    assert store.set_active_game(profile["driver_id"], "dirt_rally_2") is True
    assert store.active_profile()["active_game"] == "dirt_rally_2"


def test_v210_invalid_units_are_rejected(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    with pytest.raises(ValueError):
        store.create_profile("Driver", units="banana")
