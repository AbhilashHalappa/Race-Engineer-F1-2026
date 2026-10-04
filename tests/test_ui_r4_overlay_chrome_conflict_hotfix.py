from pathlib import Path

TEXT = Path("src/overlay/window.py").read_text(encoding="utf-8")

def _block(start, end):
    return TEXT.split(start, 1)[1].split(end, 1)[0]

def test_di_ri_trace_buttons_live_below_title_row():
    di = _block("class DriverOverlayWindow", "class ReferenceInputsOverlayWindow")
    ri = _block("class ReferenceInputsOverlayWindow", "class SpeedDeltaOverlayWindow")
    for block in (di, ri):
        assert 'channels = QHBoxLayout()' in block
        assert 'channels.addWidget(self.label("TRACES"' in block
        assert 'channels.addStretch(1); root.addLayout(channels)' in block
        assert 'self.minimize_button = None' in block or 'self.minimize_button=None' in block

def test_live_corner_waiting_state_is_explicit_and_glanceable():
    block = _block("class LiveCornerFeedbackOverlayWindow", "class LapStintSummaryPanel")
    assert "POST-CORNER FEEDBACK" in block
    assert "WAITING FOR COMPLETED CORNER" in block
    assert "Accuracy, measured time cost and one trusted action" in block

def test_legacy_overlay_minimize_close_controls_are_not_instantiated():
    assert TEXT.count("_make_minimize_button(") == 1
    for phrase in (
        "Hide Driver Inputs overlay", "Hide Reference Inputs overlay",
        "Hide Delta overlay", "Hide Live Laptime overlay", "Hide replay controls",
        "Close F1 Dash",
    ):
        assert phrase not in TEXT
