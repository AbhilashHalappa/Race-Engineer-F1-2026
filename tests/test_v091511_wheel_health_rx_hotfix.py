from pathlib import Path


def test_native_usb_cdc_keeps_dtr_asserted_for_receiver_to_pc_health():
    source = Path('src/wheel_telemetry.py').read_text(encoding='utf-8')
    assert 'ser.dtr = True' in source
    assert 'ser.dtr = False' not in source


def test_health_check_distinguishes_missing_health_frames():
    source = Path('src/wheel_telemetry.py').read_text(encoding='utf-8')
    assert 'Health data  : NOT RECEIVED' in source
    assert 'Health data  : RECEIVED' in source
