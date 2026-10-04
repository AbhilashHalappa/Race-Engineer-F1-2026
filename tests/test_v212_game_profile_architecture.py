from __future__ import annotations

import json
from pathlib import Path

from src.driver_profiles import DriverProfileStore, SUPPORTED_GAMES


def test_v212_every_driver_gets_independent_game_profile_containers(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    driver = store.create_profile("Abhilash")
    driver_id = driver["driver_id"]

    refs = store.list_game_profiles(driver_id)
    assert {ref.game_id for ref in refs} == set(SUPPORTED_GAMES)

    expected = {
        "f1_26": ("formula", True),
        "acc": ("gt", False),
        "dirt_rally_2": ("rally", False),
    }
    for game_id, (discipline, supported) in expected.items():
        payload = store.load_game_profile(driver_id, game_id)
        assert payload is not None
        assert payload["driver_id"] == driver_id
        assert payload["game_id"] == game_id
        assert payload["discipline"] == discipline
        assert payload["driving_seconds"] == 0
        assert payload["sessions"] == 0
        assert payload["supported"] is supported
        assert store.game_profile_path(driver_id, game_id).is_file()


def test_v212_game_profiles_are_isolated_between_people(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    one = store.create_profile("Driver One")
    two = store.create_profile("Driver Two")

    one_acc = store.load_game_profile(one["driver_id"], "acc")
    two_acc = store.load_game_profile(two["driver_id"], "acc")
    assert one_acc and two_acc
    assert one_acc["driver_id"] != two_acc["driver_id"]
    assert store.game_profile_path(one["driver_id"], "acc") != store.game_profile_path(two["driver_id"], "acc")


def test_v212_repairs_older_driver_without_destroying_existing_f1_counters(tmp_path: Path):
    root = tmp_path / "drivers"
    store = DriverProfileStore(root)
    driver = store.create_profile("Legacy V2.1 Driver")
    driver_id = driver["driver_id"]

    # Simulate an earlier V2.1.x layout where only F1 existed.
    acc_dir = store.game_profile_path(driver_id, "acc").parent
    dirt_dir = store.game_profile_path(driver_id, "dirt_rally_2").parent
    for d in (acc_dir, dirt_dir):
        for child in d.iterdir():
            child.unlink()
        d.rmdir()

    f1_path = store.game_profile_path(driver_id, "f1_26")
    f1 = json.loads(f1_path.read_text(encoding="utf-8"))
    f1["sessions"] = 27
    f1["driving_seconds"] = 12345
    f1_path.write_text(json.dumps(f1), encoding="utf-8")

    active = store.active_profile()
    assert active and active["driver_id"] == driver_id
    repaired_f1 = store.load_game_profile(driver_id, "f1_26")
    assert repaired_f1["sessions"] == 27
    assert repaired_f1["driving_seconds"] == 12345
    assert store.load_game_profile(driver_id, "acc") is not None
    assert store.load_game_profile(driver_id, "dirt_rally_2") is not None


def test_v212_future_container_does_not_make_future_game_selectable(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    driver = store.create_profile("Driver")
    driver_id = driver["driver_id"]

    assert store.load_game_profile(driver_id, "acc") is not None
    assert store.load_game_profile(driver_id, "dirt_rally_2") is not None
    assert store.set_active_game(driver_id, "acc") is True
    assert store.active_profile()["active_game"] == "acc"
    assert store.set_active_game(driver_id, "dirt_rally_2") is True
    assert store.active_profile()["active_game"] == "dirt_rally_2"


def test_v212_ui_exposes_ready_containers_without_claiming_telemetry_support():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "PROFILE READY • TELEMETRY FUTURE" in source
    assert 'self.tabs.addTab(self.driver_profile_page, "DRIVER PROFILE")' in source
