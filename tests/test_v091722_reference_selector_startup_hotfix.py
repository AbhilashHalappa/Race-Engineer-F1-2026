from pathlib import Path

def test_reference_callbacks_belong_to_control_center():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    control = source.split("class ControlCenterWindow", 1)[1]
    assert "def refresh_reference_options" in control
    assert "def _reference_changed" in control
    assert "def set_reference_selection" in control

def test_current_banner_is_v091722():
    source = Path("src/main.py").read_text(encoding="utf-8")
    assert "V0.9.17.2.3 REPLAY RECORDING SELECTOR" in source
