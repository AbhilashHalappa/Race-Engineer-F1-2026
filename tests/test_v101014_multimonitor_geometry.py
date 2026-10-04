from pathlib import Path


def test_control_center_avoids_fixed_native_geometry_constraints():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    cc = source.split("class ControlCenterWindow", 1)[1].split("class DriverOverlayWindow", 1)[0]
    assert "self.setMinimumSize(340, 560)" in cc
    assert "self.resize(self.WIDTH, self.HEIGHT)" in cc
    assert "self.resize(required)" in cc
    assert "self.setFixedSize(self.WIDTH, self.HEIGHT)" not in cc


def test_overlay_drag_is_clamped_to_active_screen():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    panel = source.split("class OverlayPanel", 1)[1].split("class CoachOverlayWindow", 1)[0]
    assert "def _clamp_to_available_screen" in panel
    assert "QApplication.screenAt" in panel
    assert "self._clamp_to_available_screen()" in panel


def test_default_coach_placement_uses_actual_control_center_height():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "self.control_center.height() + self.GAP" in source


def test_control_center_geometry_dependencies_are_imported():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    first_import = next(line for line in source.splitlines() if line.startswith("from PySide6.QtCore import"))
    assert "QSize" in first_import
