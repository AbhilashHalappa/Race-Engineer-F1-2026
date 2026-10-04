"""Race Engineer <-> GamePad Pro receiver telemetry bridge.

The PC -> Receiver wheel-dashboard stream remains the proven RE/V1 15-byte
50 Hz frame.  The serial backend is shared with the embedded Hardware
workspace so Race Engineer owns exactly one Receiver COM session while also
supporting the newer live pedal / MotorTemp values and Receiver-side pedal
calibration protocol used by Wheel Companion Ultra Lite V1.5.0.
"""
from __future__ import annotations

import time

# Native ESP32-S3 USB CDC health/status RX depends on host DTR.  The shared
# protocol backend preserves the proven connection behavior: ser.dtr = True
# (never ser.dtr deassertion) before Receiver->PC health frames are consumed.

from .hardware_companion.models import WheelLinkHealth, WheelTelemetrySnapshot
from .hardware_companion.protocol import (
    BAUDRATE,
    CONTROL_DISABLE_EXTENDED,
    CONTROL_ENABLE_EXTENDED,
    CONTROL_FRAME_SIZE,
    CONTROL_MAGIC,
    CONTROL_NO_CRC,
    CONTROL_REFRESH_S,
    CONTROL_VERSION,
    CONTROL_VERSION_V1,
    CONTROL_VERSION_V2,
    CONTROL_VERSION_V3,
    DRS_ACTIVE,
    DRS_AVAILABLE,
    DRS_SHIFT,
    FRAME_NO_CRC,
    FRAME_SIZE,
    HEALTH_MOTOR_TEMP,
    HEALTH_PEDALS,
    HEALTH_RACE_ENGINEER,
    HEALTH_WHEEL,
    LIVE_FRAME_SIZE,
    LIVE_MAGIC,
    LIVE_STALE_S,
    LIVE_VERSION,
    LIVE_VERSION_V1,
    LIVE_VERSION_V2,
    LIVE_VERSION_V3,
    LOW_ERS,
    LOW_FUEL,
    MAGIC,
    PROTOCOL_VERSION,
    ReceiverBridge,
    STATUS_FRAME_SIZE,
    STATUS_MAGIC,
    STATUS_NO_CRC,
    STATUS_STALE_S,
    STATUS_VERSION,
    STATUS_VERSION_V2,
    STATUS_V2_FRAME_SIZE,
    STATUS_V2_NO_CRC,
    TX_HZ,
    crc8_atm,
    decode_live_values_frame,
    decode_status_frame,
    encode_control_frame,
    encode_frame,
    serial_ports,
)

ERS_MAX_STORE_J = 4_000_000.0
EA_TO_WHEEL_FLAG = {1: 3, 2: 1, 3: 5}


def _raw(value):
    return getattr(value, "raw", None) if value is not None else None


def _current_flag(state) -> int:
    session = state.session
    car = state.player
    if car is not None and _raw(car.lap.result_status) in (3, 4, 5, 6, 7):
        return 6
    if getattr(session, "ended", None):
        return 6
    zones = tuple(getattr(session, "marshal_zones", ()) or ())
    track_length = getattr(session, "track_length_m", None)
    lap_distance = getattr(getattr(car, "lap", None), "lap_distance_m", None) if car else None
    if not zones or not track_length or lap_distance is None or track_length <= 0:
        return 0
    fraction = (float(lap_distance) % float(track_length)) / float(track_length)
    selected = zones[-1]
    for zone in zones:
        if fraction >= float(zone.start_fraction):
            selected = zone
        else:
            break
    return EA_TO_WHEEL_FLAG.get(_raw(selected.flag), 0)


def snapshot_from_state(state) -> WheelTelemetrySnapshot:
    """Project authoritative state into the unchanged physical-wheel frame."""
    car = state.player
    if car is None:
        return WheelTelemetrySnapshot()
    telemetry = car.telemetry
    fuel = car.fuel
    energy = car.energy
    aero = car.aero

    rpm_percent = int(telemetry.rev_lights_percent or 0)
    status = 0
    if telemetry.drs is True:
        status |= DRS_ACTIVE << DRS_SHIFT
    elif aero.drs_allowed is True:
        status |= DRS_AVAILABLE << DRS_SHIFT

    if fuel.remaining_mass is not None and fuel.capacity not in (None, 0):
        if 0 < (100.0 * float(fuel.remaining_mass) / float(fuel.capacity)) <= 15.0:
            status |= LOW_FUEL
    if energy.store_j is not None:
        ers_pct = 100.0 * float(energy.store_j) / ERS_MAX_STORE_J
        if 0 < ers_pct <= 20.0:
            status |= LOW_ERS

    return WheelTelemetrySnapshot(
        speed=int(telemetry.speed_kph or 0),
        gear=int(telemetry.gear or 0),
        position=int(car.lap.position or 0),
        rpm_percent=rpm_percent,
        shift_light=1 if rpm_percent >= 95 else 0,
        flag_status=_current_flag(state),
        ers_mode=int(_raw(energy.deploy_mode) or 0),
        status_bits=status,
    )


class WheelTelemetryBridge(ReceiverBridge):
    """Single shared Receiver transport for wheel telemetry + Hardware UI.

    Compatibility contract:
    - RE/V1 PC->Receiver telemetry is unchanged and still sent at 50 Hz.
    - Existing Race Engineer public methods/attributes remain available.
    - New Wheel Companion configuration/live-value protocol shares this same
      COM handle; no second serial or UDP listener is created.
    """

    def __init__(self, *, enabled: bool = True, port: str | None = None, baudrate: int = BAUDRATE):
        self.enabled = bool(enabled)
        super().__init__(port=port, baudrate=baudrate)
        # Protected compatibility marker used by the older link-health tests.
        self._last_reported_peers: tuple[bool, bool, bool] | None = None

    def update_from_state(self, state) -> None:
        if not self.enabled:
            return
        self.update(snapshot_from_state(state))

    def start(self) -> None:
        if not self.enabled:
            return
        super().start()

    def close(self, wait: bool = True) -> None:
        if not self.enabled:
            return
        super().close(wait=wait)

    def _close_serial(self, *, count_loss: bool = True) -> None:
        super()._close_serial(count_loss=count_loss)
        self._last_reported_peers = None

    def reconfigure_port(self, port: str | None) -> None:
        """Switch Receiver COM selection without replacing the bridge object."""
        requested = str(port or "auto").strip() or "auto"
        if requested.lower() == str(self.requested_port or "auto").lower():
            return
        was_enabled = self.enabled
        if was_enabled:
            super().close(wait=True)
        self.requested_port = requested
        self._port_identity = None
        self._connected_once_port = None
        self._ever_connected = False
        self.last_error = None
        if was_enabled:
            super().start()


def list_serial_ports() -> None:
    rows = serial_ports()
    if not rows:
        print("No serial ports detected.")
        return
    print("Serial devices:")
    for device, details in rows:
        print(f"  {device}: {details}")


def run_health_check(port: str | None = None, timeout_s: float = 3.0) -> int:
    """Bench-test Receiver USB + ESP-NOW peers without starting F1 telemetry."""
    bridge = WheelTelemetryBridge(enabled=True, port=port)
    bridge.start()
    deadline = time.monotonic() + max(1.0, float(timeout_s))
    try:
        while time.monotonic() < deadline:
            health = bridge.health_snapshot()
            if health.serial_connected and health.status_fresh:
                break
            time.sleep(0.05)
        health = bridge.health_snapshot()
        print("\nGamePad Pro link health")
        print("-----------------------")
        print(
            f"Receiver USB : {'CONNECTED' if health.serial_connected else 'NOT CONNECTED'}"
            + (f" ({health.port})" if health.port else "")
        )
        known = health.status_fresh
        if known:
            print("Health data  : RECEIVED")
        else:
            print("Health data  : NOT RECEIVED")

        def peer(name, connected, age):
            state = "CONNECTED" if connected and known else ("MISSING" if known else "UNKNOWN")
            age_text = "" if age is None else f" • {age} ms"
            print(f"{name:<13}: {state}{age_text}")

        peer("Wheel", health.wheel_connected, health.wheel_age_ms)
        peer("Pedals", health.pedals_connected, health.pedals_age_ms)
        peer("MotorTemp", health.motor_temp_connected, health.motor_temp_age_ms)
        if health.last_error:
            print(f"Last error    : {health.last_error}")
        return 0 if health.serial_connected else 1
    finally:
        bridge.close(wait=True)
