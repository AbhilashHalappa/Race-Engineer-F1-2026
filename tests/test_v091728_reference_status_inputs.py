from pathlib import Path


def test_current_banner_v091728():
    source = Path('src/main.py').read_text(encoding='utf-8')
    assert 'V0.9.17.2.9.6 DISTANCE-ALIGNED INPUT GRAPH AXES' in source


def test_control_center_has_active_pending_reference_indicator():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'def set_reference_status' in source
    assert 'ACTIVE:' in source
    assert 'PENDING:' in source
    assert 'next lap' in source


def test_reference_inputs_overlay_and_launcher_exist():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'class ReferenceInputsOverlayWindow' in source
    assert '("RI", "Reference Inputs — throttle / brake / ERS"' in source
    assert ('self.reference_driver.update_snapshot(snapshot)' in source or 'self.reference_driver.update_snapshot(snapshot, append_sample=progressed)' in source)


def test_overlay_snapshot_exposes_reference_inputs():
    source = Path('src/overlay/data.py').read_text(encoding='utf-8')
    for field in ('reference_throttle', 'reference_brake', 'reference_ers_store_j',
                  'reference_speed_kph', 'reference_gear', 'reference_time_s', 'reference_name'):
        assert field in source
