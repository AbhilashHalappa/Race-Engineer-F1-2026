from pathlib import Path


def test_s_mode_visibility_initialized_before_initial_height_calculation():
    source = Path("src/overlay/window.py").read_text()
    ctor_start = source.index("class CoachOverlayWindow")
    init_pos = source.index("self._s_mode_visible = False", ctor_start)
    size_pos = source.index("self.setFixedSize(self.WIDTH, self.NO_REFERENCE_HEIGHT", ctor_start)
    assert init_pos < size_pos
