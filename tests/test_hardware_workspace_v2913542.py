from pathlib import Path
from types import SimpleNamespace

from src.hardware_companion.integration import SharedHardwareRuntime
from src.hardware_companion.models import WheelLinkHealth
from src.wheel_telemetry import FRAME_SIZE, WheelTelemetryBridge, WheelTelemetrySnapshot, encode_frame

ROOT = Path(__file__).resolve().parents[1]
WINDOW = (ROOT / "src" / "overlay" / "window.py").read_text(encoding="utf-8")
GUI = (ROOT / "src" / "hardware_companion" / "gui_qt.py").read_text(encoding="utf-8")


def test_hardware_is_a_main_control_center_tab_not_a_control_card():
    assert 'self.tabs.addTab(self.hardware_page, "HARDWARE")' in WINDOW
    assert '_control_card("HARDWARE", "Wheel-side telemetry links")' not in WINDOW
    assert 'hardware_labels' not in WINDOW


def test_embedded_hardware_workspace_keeps_three_requested_subtabs():
    assert 'self.tabs.addTab(self.dashboard, "HARDWARE")' in GUI
    assert 'self.tabs.addTab(self.curves, "INPUT CALIBRATION")' in GUI
    assert 'self.tabs.addTab(self.input_tester, "INPUT TESTER")' in GUI


def test_embedded_hardware_workspace_does_not_create_companion_udp_runtime():
    assert 'CompanionRuntime' not in GUI
    assert 'RACE ENGINEER (SHARED)' in GUI
    assert 'No duplicate UDP listener is started.' in GUI


def test_shared_runtime_uses_existing_receiver_bridge():
    bridge = WheelTelemetryBridge(enabled=False, port="COM5")
    runtime = SharedHardwareRuntime(bridge)
    assert runtime.receiver is bridge
    assert hasattr(runtime.receiver, "pedal_settings_snapshot")
    assert hasattr(runtime.receiver, "apply_pedal_settings")
    assert hasattr(runtime.receiver, "reconfigure_port")


def test_wheel_dashboard_wire_frame_remains_proven_re_v1_15_bytes():
    frame = encode_frame(WheelTelemetrySnapshot(speed=250, gear=8, position=1, rpm_percent=90), 7)
    assert len(frame) == FRAME_SIZE == 15
    assert frame[:3] == b"RE\x01"


def test_shared_decoder_reads_race_engineer_snapshot_without_new_udp_listener():
    runtime = SharedHardwareRuntime(WheelTelemetryBridge(enabled=False))
    runtime.update_snapshot(SimpleNamespace(
        connected=True, speed_kph=210, gear=6, rpm=11000, rev_lights_percent=82,
        throttle=0.73, brake=0.12, steering=-0.25, drs_active=True, drs_allowed=True,
        position=2, lap_number=5, fuel_remaining_mass=20.0, fuel_capacity=100.0,
        ers_store_j=2_000_000.0, session_uid=123,
    ))
    live, _ = runtime.decoder.snapshots()
    assert live.udp_connected is True
    assert live.source == "RACE ENGINEER"
    assert live.speed_kph == 210
    assert live.gear == 6
    assert live.throttle_percent == 73
    assert live.brake_percent == 12
    assert live.steering_percent == -25
    assert live.ers_percent == 50.0
