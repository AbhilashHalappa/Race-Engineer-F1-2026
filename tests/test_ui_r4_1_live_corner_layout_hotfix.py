from pathlib import Path

WINDOW = Path('src/overlay/window.py').read_text(encoding='utf-8')
BLOCK = WINDOW.split('class LiveCornerFeedbackOverlayWindow', 1)[1].split('class LapStintSummaryPanel', 1)[0]


def test_details_control_is_kept_out_of_shared_chrome_header():
    assert "self._details_button.move(int(round(16*scale))" in BLOCK
    assert "logical_w=max(300.0,float(self.width())/scale)" in BLOCK
    assert "selector_w=max(150,min(205,logical_w-250))" in BLOCK
    assert "self._min_button" not in BLOCK
    assert "self._close_button" not in BLOCK


def test_live_corner_feedback_height_is_content_driven_after_restore():
    assert "def _target_content_height" in BLOCK
    assert "def _sync_content_height" in BLOCK
    assert "def _logical_content_height" in BLOCK
    assert "super().showEvent(event)" in BLOCK
    assert "self._sync_content_height()" in BLOCK
    assert "R4_HEIGHT=264" in BLOCK


def test_live_corner_feedback_true_zoom_scales_painted_ui_and_child_controls():
    assert "p.scale(scale,scale)" in BLOCK
    assert "W=float(self.width())/scale; H=float(self.height())/scale" in BLOCK
    assert "self.metric_selector.setGeometry(int(round(14*scale))" in BLOCK
    assert "self._details_button.setFixedSize(int(round(58*scale))" in BLOCK
    assert "def set_overlay_scale(self,value: float)" in BLOCK


def test_live_corner_feedback_action_text_drives_height_and_wraps():
    assert "QFontMetrics(QFont('Segoe UI',10,QFont.Bold))" in BLOCK
    assert "Qt.TextWordWrap" in BLOCK
    assert "action_h=self._logical_action_height(W)" in BLOCK
    assert "Qt.AlignTop|Qt.TextWordWrap" in BLOCK
