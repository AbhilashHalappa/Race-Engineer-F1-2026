from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOW = (ROOT / "src" / "overlay" / "window.py").read_text(encoding="utf-8")
WIDGETS = (ROOT / "src" / "overlay" / "widgets.py").read_text(encoding="utf-8")


def _block(start, end):
    return WINDOW.split(start, 1)[1].split(end, 1)[0]


def test_shared_overlay_zoom_scales_widgets_fonts_fixed_controls_and_layout_spacing():
    block = _block("class OverlayPanel", "class CoachOverlayWindow")
    assert "def _apply_overlay_visual_scale" in block
    assert "child.setProperty('overlayVisualScale', scale)" in block
    assert "f.setPointSizeF" in block
    assert "layout.setContentsMargins" in block
    assert "layout.setSpacing" in block
    assert "def set_overlay_logical_fixed_size" in block


def test_fixed_size_overlay_windows_route_through_logical_true_zoom():
    # Direct top-level QWidget fixed sizes silently defeat shared zoom.
    for class_name, next_class in (
        ("class SpeedDeltaOverlayWindow", "class LiveLaptimeOverlayWindow"),
        ("class LiveLaptimeOverlayWindow", "class DataOverlayWindow"),
        ("class ReplayControlsWindow", "class F1DashCanvas"),
        ("class ProgressivePreCornerOverlayWindow", "class LiveCornerFeedbackOverlayWindow"),
        ("class F1DashOverlayWindow", "class OverlaySuite"),
    ):
        block = _block(class_name, next_class)
        assert "set_overlay_logical_fixed_size" in block
        assert "self.setFixedSize(" not in block


def test_pre_corner_uses_logical_painter_transform_for_true_zoom():
    block = _block("class ProgressivePreCornerOverlayWindow", "class LiveCornerFeedbackOverlayWindow")
    assert "p.scale(scale,scale)" in block
    assert "W=float(self.width())/scale" in block
    assert "W-32" in block
    assert "_close_button" not in block
    assert "_min_button" not in block


def test_f1_dash_page_controls_follow_shared_zoom_and_private_chrome_is_removed():
    block = _block("class F1DashOverlayWindow", "class OverlaySuite")
    assert "def set_overlay_scale" in block
    assert "self._layout_page_buttons()" in block
    assert "font_px=max(7,int(round(10*scale)))" in block
    assert "self.header_button_bar=None" in block
    assert "self.minimize_button=None" in block
    assert "self.hide_button=None" in block
    assert "self.canvas.update()" in block


def test_custom_painted_overlay_widgets_receive_visual_scale():
    assert "def _overlay_visual_scale(widget):" in WIDGETS
    assert "def _overlay_font(widget, size, weight=QFont.Normal):" in WIDGETS
    assert "_overlay_font(self, 10, QFont.Bold)" in WIDGETS
    assert "def _visual_font(widget, size, weight=QFont.Normal):" in WINDOW
