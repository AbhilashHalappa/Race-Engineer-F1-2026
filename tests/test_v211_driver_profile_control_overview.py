from __future__ import annotations

from pathlib import Path

from src.driver_profiles import DriverProfileStore


def test_v211_avatar_can_be_replaced_and_cleared_without_changing_identity(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    profile = store.create_profile("Abhilash")
    driver_id = profile["driver_id"]
    avatar = tmp_path / "avatar.png"
    avatar.write_bytes(b"not-a-real-image-but-valid-storage-test")

    updated = store.update_avatar(driver_id, avatar)
    assert updated is not None
    assert updated["driver_id"] == driver_id
    stored = store.avatar_path(driver_id)
    assert stored is not None and stored.is_file()
    assert stored.name == "avatar.png"

    cleared = store.update_avatar(driver_id, None)
    assert cleared is not None
    assert cleared["driver_id"] == driver_id
    assert cleared["avatar"] is None
    assert store.avatar_path(driver_id) is None


def test_v211_control_center_contains_permanent_profile_control_and_profile_workspace():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'self.profile_button.setObjectName("driverProfileControl")' in source
    assert 'outer.addLayout(self.profile_bar)' in source
    assert 'self.tabs.addTab(self.driver_profile_page, "DRIVER PROFILE")' in source
    for tab in ("OVERVIEW", "SKILLS", "TRENDS", "HISTORY", "GAME PROFILES"):
        assert tab in source
    assert 'self.profile_button.setText(f"{self._profile_initials(name)}   {name}\\n      {game_compact}  •  Skill N/A")' in source
    assert '"Driving time":"0h 00m"' in source
    assert "profile_driving_breakdown" in source


def test_v211_edit_profile_keeps_person_identity_and_updates_personal_fields(tmp_path: Path):
    store = DriverProfileStore(tmp_path / "drivers")
    profile = store.create_profile("Old Name", country_region="", units="metric")
    driver_id = profile["driver_id"]
    updated = store.update_personal_info(
        driver_id,
        display_name="New Name",
        country_region="India",
        units="imperial",
    )
    assert updated is not None
    assert updated["driver_id"] == driver_id
    assert updated["display_name"] == "New Name"
    assert updated["country_region"] == "India"
    assert updated["units"] == "imperial"
