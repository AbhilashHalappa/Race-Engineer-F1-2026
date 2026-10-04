from dataclasses import replace

from src.wheel_telemetry import WheelLinkHealth, WheelTelemetryBridge


def test_receiver_disconnect_invalidates_all_downstream_peer_health():
    bridge = WheelTelemetryBridge(enabled=True, port='COM5')
    bridge._health = WheelLinkHealth(
        serial_connected=True,
        port='COM5',
        status_fresh=True,
        wheel_connected=True,
        pedals_connected=True,
        motor_temp_connected=True,
        receiver_has_pc_telemetry=True,
        wheel_age_ms=3,
        pedals_age_ms=4,
        motor_temp_age_ms=216,
        pc_telemetry_age_ms=5,
        last_status_monotonic=1.0,
    )
    bridge._serial = None
    bridge.connected_port = None

    health = bridge.health_snapshot()
    assert health.serial_connected is False
    assert health.status_fresh is False
    assert health.wheel_connected is False
    assert health.pedals_connected is False
    assert health.motor_temp_connected is False
    assert health.receiver_has_pc_telemetry is False
    assert health.wheel_age_ms is None
    assert health.pedals_age_ms is None
    assert health.motor_temp_age_ms is None


def test_close_serial_clears_stale_peer_state():
    class FakeSerial:
        def close(self):
            pass

    bridge = WheelTelemetryBridge(enabled=True, port='COM5')
    bridge._serial = FakeSerial()
    bridge.connected_port = 'COM5'
    bridge._last_reported_peers = (True, True, True)
    bridge._health = WheelLinkHealth(
        serial_connected=True,
        port='COM5',
        status_fresh=True,
        wheel_connected=True,
        pedals_connected=True,
        motor_temp_connected=True,
        receiver_has_pc_telemetry=True,
        wheel_age_ms=2,
        pedals_age_ms=2,
        motor_temp_age_ms=200,
        pc_telemetry_age_ms=3,
        last_status_monotonic=123.0,
    )

    bridge._close_serial(count_loss=True)
    health = bridge._health
    assert health.serial_connected is False
    assert health.status_fresh is False
    assert health.wheel_connected is False
    assert health.pedals_connected is False
    assert health.motor_temp_connected is False
    assert health.last_status_monotonic is None
    assert bridge._last_reported_peers is None
