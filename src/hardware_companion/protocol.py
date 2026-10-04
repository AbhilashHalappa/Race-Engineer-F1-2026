"""GamePad Pro Receiver USB protocol for Wheel Companion Ultra Lite.

Compatibility design:
- PC -> Receiver wheel telemetry remains the proven 15-byte RE/V1 frame at 50 Hz.
- Receiver -> PC always keeps the legacy 25-byte RS/V1 health frame used by the full app.
- WC/V1 + WL/V1 remain byte-for-byte compatible with Receiver V8.3.5.
- Ultra Lite additionally probes WC/V2. A V8.3.6+ Receiver answers with WL/V2,
  adding a clutch raw value without changing the legacy streams.
- Pedal settings PC/PS V1 remain exact; PC/PS V2 adds clutch curve + enable state.
- 115200 baud with automatic USB serial reconnect.
"""
from __future__ import annotations

from dataclasses import replace
import struct
import threading
import time
import queue

from .models import WheelLinkHealth, WheelTelemetrySnapshot
from .pedal_curves import (
    PedalCurveSettings, RESPONSE_MAGIC as PEDAL_SETTINGS_MAGIC,
    VERSION_V1 as PEDAL_SETTINGS_V1, VERSION_V2 as PEDAL_SETTINGS_V2, VERSION_V3 as PEDAL_SETTINGS_V3,
    decode_response as decode_pedal_settings_response,
    response_frame_size_for_version as pedal_settings_frame_size_for_version,
    encode_command as encode_pedal_settings_command,
    CMD_APPLY_VOLATILE, CMD_SAVE, CMD_REQUEST, CMD_RESET_DEFAULTS,
)

MAGIC = b"RE"
PROTOCOL_VERSION = 1
BAUDRATE = 115200
TX_HZ = 50.0
FRAME_NO_CRC = struct.Struct("<2sBHHbBBBBBB")
FRAME_SIZE = FRAME_NO_CRC.size + 1

STATUS_MAGIC = b"RS"
STATUS_VERSION = 1
STATUS_NO_CRC = struct.Struct("<2sBBHHHHIII")
STATUS_FRAME_SIZE = STATUS_NO_CRC.size + 1
# Receiver V2 extension based on the actual GamePad Pro V8.3.1 firmware:
# append the PedalPayload raw ADC values (0..4095) and MotorTempPayload
# temperature (centi-degrees C). PC->Receiver wheel telemetry stays byte-for-byte V1.
STATUS_VERSION_V2 = 2
STATUS_V2_NO_CRC = struct.Struct("<2sBBHHHHIIIHHh")
STATUS_V2_FRAME_SIZE = STATUS_V2_NO_CRC.size + 1

# V8.3.3 dual-app compatibility control. Wheel Companion refreshes an enable
# lease once per second; the Receiver stops WL output after three seconds if
# the app disappears. A normal close sends an explicit disable first.
CONTROL_MAGIC = b"WC"
CONTROL_VERSION_V1 = 1
CONTROL_VERSION_V2 = 2
CONTROL_VERSION_V3 = 3
CONTROL_VERSION = CONTROL_VERSION_V1
CONTROL_ENABLE_EXTENDED = 1
CONTROL_DISABLE_EXTENDED = 2
CONTROL_NO_CRC = struct.Struct("<2sBB")
CONTROL_FRAME_SIZE = CONTROL_NO_CRC.size + 1
CONTROL_REFRESH_S = 1.0

# Live V1 is exact V8.3.5. V2 appends clutch_raw before motor temperature.
LIVE_MAGIC = b"WL"
LIVE_VERSION_V1 = 1
LIVE_VERSION_V2 = 2
LIVE_VERSION_V3 = 3
LIVE_VERSION = LIVE_VERSION_V1
LIVE_V1_NO_CRC = struct.Struct("<2sBHHh")
LIVE_V1_FRAME_SIZE = LIVE_V1_NO_CRC.size + 1
LIVE_V2_NO_CRC = struct.Struct("<2sBHHHh")
LIVE_V2_FRAME_SIZE = LIVE_V2_NO_CRC.size + 1
LIVE_V3_NO_CRC = struct.Struct("<2sBHHHHh")
LIVE_V3_FRAME_SIZE = LIVE_V3_NO_CRC.size + 1
LIVE_NO_CRC = LIVE_V1_NO_CRC
LIVE_FRAME_SIZE = LIVE_V1_FRAME_SIZE
LIVE_STALE_S = 0.75

SERIAL_STARTUP_HANDSHAKE_TIMEOUT_S = 3.0
SERIAL_STATUS_WATCHDOG_S = 3.0

PEDAL_RAW_MAX = 4095
PEDAL_RAW_INVALID = 0xFFFF
MOTOR_TEMP_INVALID_CX100 = -32768
STATUS_STALE_S = 1.5

HEALTH_WHEEL = 1 << 0
HEALTH_PEDALS = 1 << 1
HEALTH_MOTOR_TEMP = 1 << 2
HEALTH_RACE_ENGINEER = 1 << 3

LOW_ERS = 1 << 0
LOW_FUEL = 1 << 1
DRS_SHIFT = 4
DRS_AVAILABLE = 2
DRS_ACTIVE = 3


def crc8_atm(data: bytes) -> int:
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def encode_control_frame(command: int, *, version: int = CONTROL_VERSION_V1) -> bytes:
    body = CONTROL_NO_CRC.pack(
        CONTROL_MAGIC,
        int(version) & 0xFF,
        int(command) & 0xFF,
    )
    return body + bytes((crc8_atm(body),))


def live_frame_size_for_version(version: int) -> int | None:
    if version == LIVE_VERSION_V1:
        return LIVE_V1_FRAME_SIZE
    if version == LIVE_VERSION_V2:
        return LIVE_V2_FRAME_SIZE
    if version == LIVE_VERSION_V3:
        return LIVE_V3_FRAME_SIZE
    return None


def decode_live_values_frame(frame: bytes) -> tuple[int | None, int | None, int | None, int | None, float | None, int] | None:
    if len(frame) < 4 or frame[:2] != LIVE_MAGIC:
        return None
    version = frame[2]
    expected = live_frame_size_for_version(version)
    if expected is None or len(frame) != expected:
        return None
    body, received_crc = frame[:-1], frame[-1]
    if crc8_atm(body) != received_crc:
        return None
    if version == LIVE_VERSION_V1:
        _magic, _version, throttle, brake, motor = LIVE_V1_NO_CRC.unpack(body)
        clutch = handbrake = PEDAL_RAW_INVALID
    elif version == LIVE_VERSION_V2:
        _magic, _version, throttle, brake, clutch, motor = LIVE_V2_NO_CRC.unpack(body)
        handbrake = PEDAL_RAW_INVALID
    else:
        _magic, _version, throttle, brake, clutch, handbrake, motor = LIVE_V3_NO_CRC.unpack(body)
    cv = lambda v: None if v == PEDAL_RAW_INVALID else int(v)
    temp = None if motor == MOTOR_TEMP_INVALID_CX100 else float(motor) / 100.0
    return cv(throttle), cv(brake), cv(clutch), cv(handbrake), temp, int(version)


def encode_frame(snapshot: WheelTelemetrySnapshot, sequence: int) -> bytes:
    body = FRAME_NO_CRC.pack(
        MAGIC,
        PROTOCOL_VERSION,
        sequence & 0xFFFF,
        max(0, min(9999, int(snapshot.speed))),
        max(-1, min(11, int(snapshot.gear))),
        max(0, min(99, int(snapshot.position))),
        max(0, min(100, int(snapshot.rpm_percent))),
        1 if snapshot.shift_light else 0,
        max(0, min(255, int(snapshot.flag_status))),
        max(0, min(255, int(snapshot.ers_mode))),
        max(0, min(255, int(snapshot.status_bits))),
    )
    return body + bytes((crc8_atm(body),))


def _pedal_percent(value: int) -> float | None:
    if value == PEDAL_RAW_INVALID:
        return None
    raw = max(0, min(PEDAL_RAW_MAX, int(value)))
    return (float(raw) * 100.0) / float(PEDAL_RAW_MAX)


def decode_status_frame(frame: bytes) -> WheelLinkHealth | None:
    if len(frame) not in (STATUS_FRAME_SIZE, STATUS_V2_FRAME_SIZE):
        return None
    body, received_crc = frame[:-1], frame[-1]
    if crc8_atm(body) != received_crc:
        return None
    if len(body) < 4 or body[:2] != STATUS_MAGIC:
        return None
    version = body[2]
    if version == STATUS_VERSION and len(frame) == STATUS_FRAME_SIZE:
        (magic, version, flags, wheel_age, pedal_age, motor_age, pc_age,
         wheel_packets, pedal_packets, motor_packets) = STATUS_NO_CRC.unpack(body)
        throttle_raw = brake_raw = None
        throttle = brake = motor_temp = None
    elif version == STATUS_VERSION_V2 and len(frame) == STATUS_V2_FRAME_SIZE:
        (magic, version, flags, wheel_age, pedal_age, motor_age, pc_age,
         wheel_packets, pedal_packets, motor_packets, throttle_raw, brake_raw,
         motor_temp_raw) = STATUS_V2_NO_CRC.unpack(body)
        throttle = _pedal_percent(throttle_raw)
        brake = _pedal_percent(brake_raw)
        motor_temp = (
            None
            if motor_temp_raw == MOTOR_TEMP_INVALID_CX100
            else float(motor_temp_raw) / 100.0
        )
        if throttle_raw == PEDAL_RAW_INVALID:
            throttle_raw = None
        if brake_raw == PEDAL_RAW_INVALID:
            brake_raw = None
    else:
        return None

    def age(value: int) -> int | None:
        return None if value == 0xFFFF else int(value)

    return WheelLinkHealth(
        status_fresh=True,
        status_protocol_version=int(version),
        wheel_connected=bool(flags & HEALTH_WHEEL),
        pedals_connected=bool(flags & HEALTH_PEDALS),
        motor_temp_connected=bool(flags & HEALTH_MOTOR_TEMP),
        receiver_has_pc_telemetry=bool(flags & HEALTH_RACE_ENGINEER),
        wheel_age_ms=age(wheel_age),
        pedals_age_ms=age(pedal_age),
        motor_temp_age_ms=age(motor_age),
        pc_telemetry_age_ms=age(pc_age),
        wheel_packets=int(wheel_packets),
        pedal_packets=int(pedal_packets),
        motor_temp_packets=int(motor_packets),
        pedal_throttle_raw=throttle_raw,
        pedal_brake_raw=brake_raw,
        pedal_throttle_percent=throttle,
        pedal_brake_percent=brake,
        motor_temp_c=motor_temp,
    )


def serial_ports() -> list[tuple[str, str]]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    rows = []
    for p in list_ports.comports():
        label = " | ".join(x for x in (p.description, p.manufacturer) if x)
        rows.append((str(p.device), label or "Unknown device"))
    return rows


class ReceiverBridge:
    """Non-blocking latest-state serial bridge with the proven reconnect behaviour."""

    def __init__(self, *, port: str | None = None, baudrate: int = BAUDRATE):
        self.requested_port = port or "auto"
        self.baudrate = int(baudrate)
        self._snapshot = WheelTelemetrySnapshot()
        self._lock = threading.Lock()
        self._health = WheelLinkHealth()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._serial = None
        self._sequence = 0
        self.connected_port: str | None = None
        self.last_error: str | None = None
        self.frames_sent = 0
        self._status_buffer = bytearray()
        self._ever_connected = False
        self._port_identity: dict[str, object] | None = None
        self._connected_once_port: str | None = None
        self._next_control_refresh = 0.0
        self._connected_monotonic: float | None = None
        self._command_queue: queue.SimpleQueue[bytes] = queue.SimpleQueue()
        self._pedal_settings = PedalCurveSettings()
        self._pedal_settings_received = False
        self._pedal_settings_updated_monotonic: float | None = None
        self._pedal_settings_protocol_version = 0
        self._v2_pedal_settings_requested = False

    def update(self, snapshot: WheelTelemetrySnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="wheel-companion-receiver", daemon=True)
        self._thread.start()

    def close(self, wait: bool = True) -> None:
        self._stop.set()
        if wait and self._thread:
            self._thread.join(timeout=2.0)
        # Disable both generations. V8.3.5 ignores WC/V2 and honors WC/V1.
        self._send_control(CONTROL_DISABLE_EXTENDED, version=CONTROL_VERSION_V3, suppress_errors=True)
        self._send_control(CONTROL_DISABLE_EXTENDED, version=CONTROL_VERSION_V2, suppress_errors=True)
        self._send_control(CONTROL_DISABLE_EXTENDED, version=CONTROL_VERSION_V1, suppress_errors=True)
        self._close_serial(count_loss=False)

    def pedal_settings_snapshot(self) -> tuple[PedalCurveSettings, bool, float | None, int]:
        with self._lock:
            return (
                self._pedal_settings,
                self._pedal_settings_received,
                self._pedal_settings_updated_monotonic,
                self._pedal_settings_protocol_version,
            )

    def request_pedal_settings(self, *, version: int | None = None) -> None:
        if version is None:
            with self._lock:
                version = PEDAL_SETTINGS_V3 if self._health.handbrake_supported else (PEDAL_SETTINGS_V2 if self._health.clutch_supported else PEDAL_SETTINGS_V1)
        self._command_queue.put(encode_pedal_settings_command(CMD_REQUEST, version=version))

    def apply_pedal_settings(self, settings: PedalCurveSettings, *, save: bool = False) -> None:
        command = CMD_SAVE if save else CMD_APPLY_VOLATILE
        with self._lock:
            version = PEDAL_SETTINGS_V3 if self._health.handbrake_supported else (PEDAL_SETTINGS_V2 if self._health.clutch_supported else PEDAL_SETTINGS_V1)
        self._command_queue.put(encode_pedal_settings_command(command, settings, version=version))

    def reset_pedal_settings(self) -> None:
        with self._lock:
            version = PEDAL_SETTINGS_V3 if self._health.handbrake_supported else (PEDAL_SETTINGS_V2 if self._health.clutch_supported else PEDAL_SETTINGS_V1)
        self._command_queue.put(encode_pedal_settings_command(CMD_RESET_DEFAULTS, version=version))

    def health_snapshot(self) -> WheelLinkHealth:
        with self._lock:
            health = self._health
        serial_connected = self._serial is not None
        now = time.monotonic()
        fresh = (
            serial_connected
            and health.last_status_monotonic is not None
            and (now - health.last_status_monotonic) <= STATUS_STALE_S
        )
        live_fresh = (
            serial_connected
            and health.last_live_values_monotonic is not None
            and (now - health.last_live_values_monotonic) <= LIVE_STALE_S
        )
        if not serial_connected:
            return replace(
                health,
                serial_connected=False,
                port=None,
                status_fresh=False,
                extended_status_active=False,
                wheel_connected=False,
                pedals_connected=False,
                motor_temp_connected=False,
                receiver_has_pc_telemetry=False,
                wheel_age_ms=None,
                pedals_age_ms=None,
                motor_temp_age_ms=None,
                pc_telemetry_age_ms=None,
                pedal_throttle_raw=None,
                pedal_brake_raw=None,
                pedal_clutch_raw=None,
                handbrake_raw=None,
                pedal_throttle_percent=None,
                pedal_brake_percent=None,
                pedal_clutch_percent=None,
                handbrake_percent=None,
                clutch_supported=False,
                handbrake_supported=False,
                motor_temp_c=None,
                frames_sent=self.frames_sent,
                last_error=self.last_error,
            )
        if not live_fresh:
            health = replace(
                health,
                pedal_throttle_raw=None,
                pedal_brake_raw=None,
                pedal_clutch_raw=None,
                handbrake_raw=None,
                pedal_throttle_percent=None,
                pedal_brake_percent=None,
                pedal_clutch_percent=None,
                handbrake_percent=None,
                motor_temp_c=None,
            )
        return replace(
            health,
            serial_connected=True,
            port=self.connected_port,
            status_fresh=bool(fresh),
            extended_status_active=bool(live_fresh),
            frames_sent=self.frames_sent,
            last_error=self.last_error,
        )

    def _close_serial(self, *, count_loss: bool = True) -> None:
        ser, self._serial = self._serial, None
        previous_port = self.connected_port
        self.connected_port = None
        self._connected_monotonic = None
        self._status_buffer.clear()
        if count_loss and previous_port is not None:
            with self._lock:
                self._health = replace(
                    self._health,
                    link_losses=self._health.link_losses + 1,
                    serial_connected=False,
                    port=None,
                    status_fresh=False,
                    extended_status_active=False,
                    wheel_connected=False,
                    pedals_connected=False,
                    motor_temp_connected=False,
                    receiver_has_pc_telemetry=False,
                    wheel_age_ms=None,
                    pedals_age_ms=None,
                    motor_temp_age_ms=None,
                    pc_telemetry_age_ms=None,
                    pedal_throttle_raw=None,
                    pedal_brake_raw=None,
                    pedal_clutch_raw=None,
                    pedal_throttle_percent=None,
                    pedal_brake_percent=None,
                    pedal_clutch_percent=None,
                    clutch_supported=False,
                    motor_temp_c=None,
                    last_status_monotonic=None,
                    last_live_values_monotonic=None,
                )
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    @staticmethod
    def _port_signature(info) -> dict[str, object]:
        return {
            "vid": getattr(info, "vid", None),
            "pid": getattr(info, "pid", None),
            "serial_number": getattr(info, "serial_number", None),
            "location": getattr(info, "location", None),
            "manufacturer": getattr(info, "manufacturer", None),
            "description": getattr(info, "description", None),
        }

    @staticmethod
    def _identity_matches(info, identity: dict[str, object] | None) -> bool:
        if not identity:
            return False
        serial_number = identity.get("serial_number")
        if serial_number and getattr(info, "serial_number", None) == serial_number:
            vid = identity.get("vid")
            pid = identity.get("pid")
            return (vid is None or getattr(info, "vid", None) == vid) and (
                pid is None or getattr(info, "pid", None) == pid
            )
        location = identity.get("location")
        if location and getattr(info, "location", None) == location:
            vid = identity.get("vid")
            pid = identity.get("pid")
            return (vid is None or getattr(info, "vid", None) == vid) and (
                pid is None or getattr(info, "pid", None) == pid
            )
        return False

    def _candidate_ports(self) -> list[str]:
        try:
            from serial.tools import list_ports
        except ImportError:
            self.last_error = "pyserial is not installed"
            return []
        ports = list(list_ports.comports())
        by_device = {str(p.device).lower(): p for p in ports}
        keywords = ("esp32", "espressif", "tinyusb", "usb serial", "usb jtag", "gamepad")
        preferred_infos = [
            p
            for p in ports
            if any(
                k
                in (
                    (p.description or "")
                    + " "
                    + (p.manufacturer or "")
                    + " "
                    + (getattr(p, "product", None) or "")
                ).lower()
                for k in keywords
            )
        ]

        if self.requested_port.lower() != "auto":
            exact = by_device.get(self.requested_port.lower())
            if exact is not None and (
                self._port_identity is None or self._identity_matches(exact, self._port_identity)
            ):
                return [str(exact.device)]
            identity_matches = [
                str(p.device) for p in ports if self._identity_matches(p, self._port_identity)
            ]
            if len(identity_matches) == 1:
                return identity_matches
            if len(preferred_infos) == 1:
                return [str(preferred_infos[0].device)]
            return []

        preferred = [str(p.device) for p in preferred_infos]
        return preferred if len(preferred) == 1 else []

    def _connect(self) -> bool:
        try:
            import serial
        except ImportError:
            self.last_error = "pyserial is not installed; run pip install -r requirements.txt"
            return False
        candidates = self._candidate_ports()
        if not candidates:
            if self.requested_port.lower() == "auto":
                self.last_error = "receiver COM port not uniquely detected; select the Receiver COM port"
            return False
        for port in candidates:
            try:
                ser = serial.Serial(
                    port=port,
                    baudrate=self.baudrate,
                    timeout=0,
                    write_timeout=0.05,
                )
                try:
                    ser.dtr = True
                    ser.rts = False
                except Exception:
                    pass
                try:
                    from serial.tools import list_ports

                    for info in list_ports.comports():
                        if str(info.device).lower() == str(port).lower():
                            self._port_identity = self._port_signature(info)
                            break
                except Exception:
                    pass
                self._serial = ser
                self.connected_port = port
                self._connected_monotonic = time.monotonic()
                self.last_error = None
                self._status_buffer.clear()
                with self._lock:
                    was_reconnect = self._ever_connected
                    reconnects = self._health.reconnects + (1 if was_reconnect else 0)
                    self._health = replace(
                        self._health,
                        serial_connected=True,
                        port=port,
                        reconnects=reconnects,
                        last_error=None,
                    )
                self._connected_once_port = port
                self._ever_connected = True
                self._next_control_refresh = 0.0
                self._v2_pedal_settings_requested = False
                # First enable the proven V1 live stream, then probe V2. Old
                # receivers ignore the second five-byte frame and keep WL/V1.
                self._send_control(CONTROL_ENABLE_EXTENDED, version=CONTROL_VERSION_V1, suppress_errors=True)
                self._send_control(CONTROL_ENABLE_EXTENDED, version=CONTROL_VERSION_V2, suppress_errors=True)
                self._send_control(CONTROL_ENABLE_EXTENDED, version=CONTROL_VERSION_V3, suppress_errors=True)
                self.request_pedal_settings(version=PEDAL_SETTINGS_V1)
                return True
            except Exception as error:
                self.last_error = str(error)
        return False

    def _serial_session_healthy(self) -> bool:
        """Return False when an opened COM session never handshakes or goes stale.

        Windows can occasionally leave the ESP32-S3 CDC port open but not actually
        delivering Receiver status frames during application startup. Without a
        watchdog the app would remain attached to that dead session until the USB
        cable was physically replugged.
        """
        if self._serial is None:
            return False
        now = time.monotonic()
        connected_at = self._connected_monotonic
        with self._lock:
            last_status = self._health.last_status_monotonic

        if last_status is None:
            if connected_at is not None and (now - connected_at) > SERIAL_STARTUP_HANDSHAKE_TIMEOUT_S:
                self.last_error = "Receiver startup handshake timed out; reconnecting automatically"
                return False
            return True

        if (now - last_status) > SERIAL_STATUS_WATCHDOG_S:
            self.last_error = "Receiver status stream became stale; reconnecting automatically"
            return False
        return True

    def _send_control(self, command: int, *, version: int = CONTROL_VERSION_V1, suppress_errors: bool = False) -> bool:
        ser = self._serial
        if ser is None:
            return False
        try:
            ser.write(encode_control_frame(command, version=version))
            return True
        except Exception as error:
            if not suppress_errors:
                self.last_error = str(error)
            return False


    def _read_status(self) -> None:
        ser = self._serial
        if ser is None:
            return
        waiting = int(getattr(ser, "in_waiting", 0) or 0)
        if waiting <= 0:
            return
        data = ser.read(min(waiting, 256))
        if not data:
            return
        self._status_buffer.extend(data)
        if len(self._status_buffer) > 1024:
            del self._status_buffer[:-128]

        while True:
            status_pos = self._status_buffer.find(STATUS_MAGIC)
            live_pos = self._status_buffer.find(LIVE_MAGIC)
            pedal_pos = self._status_buffer.find(PEDAL_SETTINGS_MAGIC)
            positions = [(pos, kind) for pos, kind in ((status_pos, "status"), (live_pos, "live"), (pedal_pos, "pedal_settings")) if pos >= 0]
            if not positions:
                # Keep a possible first magic byte across split serial reads.
                tail = self._status_buffer[-1:] if self._status_buffer else b""
                if tail in (STATUS_MAGIC[:1], LIVE_MAGIC[:1], PEDAL_SETTINGS_MAGIC[:1]):
                    self._status_buffer[:] = tail
                else:
                    self._status_buffer.clear()
                return

            start, kind = min(positions, key=lambda item: item[0])
            if start:
                del self._status_buffer[:start]

            if kind == "status":
                if len(self._status_buffer) < 3:
                    return
                version = self._status_buffer[2]
                frame_size = STATUS_V2_FRAME_SIZE if version == STATUS_VERSION_V2 else STATUS_FRAME_SIZE
                if len(self._status_buffer) < frame_size:
                    return
                frame = bytes(self._status_buffer[:frame_size])
                parsed = decode_status_frame(frame)
                if parsed is None:
                    del self._status_buffer[0]
                    continue
                del self._status_buffer[:frame_size]
                now = time.monotonic()
                with self._lock:
                    old = self._health
                    # RS/V1 deliberately carries no live values. Preserve a
                    # recent WL snapshot when merging the legacy health frame.
                    if parsed.status_protocol_version == STATUS_VERSION:
                        parsed = replace(
                            parsed,
                            pedal_throttle_raw=old.pedal_throttle_raw,
                            pedal_brake_raw=old.pedal_brake_raw,
                            pedal_clutch_raw=old.pedal_clutch_raw,
                            handbrake_raw=old.handbrake_raw,
                            pedal_throttle_percent=old.pedal_throttle_percent,
                            pedal_brake_percent=old.pedal_brake_percent,
                            pedal_clutch_percent=old.pedal_clutch_percent,
                            handbrake_percent=old.handbrake_percent,
                            clutch_supported=old.clutch_supported,
                            handbrake_supported=old.handbrake_supported,
                            motor_temp_c=old.motor_temp_c,
                            extended_status_active=old.extended_status_active,
                            live_value_frames_received=old.live_value_frames_received,
                            last_live_values_monotonic=old.last_live_values_monotonic,
                        )
                    else:
                        # Compatibility with the interim V8.3.2 RS/V2 build.
                        parsed = replace(
                            parsed,
                            extended_status_active=True,
                            live_value_frames_received=old.live_value_frames_received + 1,
                            last_live_values_monotonic=now,
                        )
                    self._health = replace(
                        parsed,
                        serial_connected=True,
                        port=self.connected_port,
                        frames_sent=self.frames_sent,
                        status_frames_received=old.status_frames_received + 1,
                        reconnects=old.reconnects,
                        link_losses=old.link_losses,
                        last_error=self.last_error,
                        last_status_monotonic=now,
                    )
                continue

            if kind == "pedal_settings":
                if len(self._status_buffer) < 3:
                    return
                settings_version = int(self._status_buffer[2])
                frame_size = pedal_settings_frame_size_for_version(settings_version)
                if frame_size is None:
                    del self._status_buffer[0]
                    continue
                if len(self._status_buffer) < frame_size:
                    return
                frame = bytes(self._status_buffer[:frame_size])
                decoded = decode_pedal_settings_response(frame)
                if decoded is None:
                    del self._status_buffer[0]
                    continue
                del self._status_buffer[:frame_size]
                parsed_settings, parsed_version = decoded
                with self._lock:
                    self._pedal_settings = parsed_settings
                    self._pedal_settings_received = True
                    self._pedal_settings_updated_monotonic = time.monotonic()
                    self._pedal_settings_protocol_version = parsed_version
                    if parsed_version >= PEDAL_SETTINGS_V2:
                        self._health = replace(self._health, clutch_supported=True, handbrake_supported=(parsed_version >= PEDAL_SETTINGS_V3 or self._health.handbrake_supported))
                continue

            # Wheel Companion live values. Frame size is selected by WL version.
            if len(self._status_buffer) < 3:
                return
            live_version = int(self._status_buffer[2])
            frame_size = live_frame_size_for_version(live_version)
            if frame_size is None:
                del self._status_buffer[0]
                continue
            if len(self._status_buffer) < frame_size:
                return
            frame = bytes(self._status_buffer[:frame_size])
            values = decode_live_values_frame(frame)
            if values is None:
                del self._status_buffer[0]
                continue
            del self._status_buffer[:frame_size]
            throttle_raw, brake_raw, clutch_raw, handbrake_raw, motor_temp_c, live_version = values
            now = time.monotonic()
            request_v2_settings = False
            with self._lock:
                old = self._health
                clutch_supported = old.clutch_supported or live_version >= LIVE_VERSION_V2
                handbrake_supported = old.handbrake_supported or live_version >= LIVE_VERSION_V3
                if clutch_supported and not self._v2_pedal_settings_requested:
                    self._v2_pedal_settings_requested = True
                    request_v2_settings = True
                self._health = replace(
                    old,
                    serial_connected=True,
                    port=self.connected_port,
                    extended_status_active=True,
                    pedal_throttle_raw=throttle_raw,
                    pedal_brake_raw=brake_raw,
                    pedal_clutch_raw=clutch_raw,
                    handbrake_raw=handbrake_raw,
                    pedal_throttle_percent=(None if throttle_raw is None else _pedal_percent(throttle_raw)),
                    pedal_brake_percent=(None if brake_raw is None else _pedal_percent(brake_raw)),
                    pedal_clutch_percent=(None if clutch_raw is None else _pedal_percent(clutch_raw)),
                    handbrake_percent=(None if handbrake_raw is None else _pedal_percent(handbrake_raw)),
                    clutch_supported=clutch_supported,
                    handbrake_supported=handbrake_supported,
                    motor_temp_c=motor_temp_c,
                    live_value_frames_received=old.live_value_frames_received + 1,
                    last_live_values_monotonic=now,
                    last_error=self.last_error,
                )
            if request_v2_settings:
                self.request_pedal_settings(version=PEDAL_SETTINGS_V2)

    def _run(self) -> None:
        period = 1.0 / TX_HZ
        next_tx = time.perf_counter()
        next_scan = 0.0
        while not self._stop.is_set():
            now = time.perf_counter()
            if self._serial is None:
                if now >= next_scan:
                    next_scan = now + 0.5
                    self._connect()
                self._stop.wait(0.025)
                next_tx = time.perf_counter()
                continue

            # Hold the V8.3.3 live-value lease while Wheel Companion owns the
            # COM port. The old full app never sends this command and therefore
            # receives only the exact legacy RS/V1 stream.
            if now >= self._next_control_refresh:
                if not self._send_control(CONTROL_ENABLE_EXTENDED, version=CONTROL_VERSION_V1):
                    self._close_serial()
                    next_scan = time.perf_counter() + 0.50
                    continue
                # V8.3.5 ignores this; V8.3.6+ upgrades the leased stream to WL/V2.
                self._send_control(CONTROL_ENABLE_EXTENDED, version=CONTROL_VERSION_V2, suppress_errors=True)
                self._send_control(CONTROL_ENABLE_EXTENDED, version=CONTROL_VERSION_V3, suppress_errors=True)
                self._next_control_refresh = now + CONTROL_REFRESH_S

            # Serialize configuration writes through this worker so the GUI
            # never competes with the 50 Hz telemetry writer on the COM port.
            try:
                for _ in range(4):
                    try:
                        command_frame = self._command_queue.get_nowait()
                    except queue.Empty:
                        break
                    self._serial.write(command_frame)
            except Exception as error:
                self.last_error = str(error)
                self._close_serial()
                next_scan = time.perf_counter() + 0.50
                continue

            try:
                self._read_status()
            except Exception as error:
                self.last_error = str(error)
                self._close_serial()
                next_scan = time.perf_counter() + 0.50
                continue

            if not self._serial_session_healthy():
                self._close_serial(count_loss=False)
                next_scan = time.perf_counter() + 0.40
                next_tx = time.perf_counter()
                continue

            delay = next_tx - now
            if delay > 0:
                self._stop.wait(min(delay, 0.01))
                continue
            next_tx += period
            if next_tx < now - period:
                next_tx = now + period

            with self._lock:
                snap = self._snapshot
            frame = encode_frame(snap, self._sequence)
            self._sequence = (self._sequence + 1) & 0xFFFF
            try:
                self._serial.write(frame)
                self.frames_sent += 1
            except Exception as error:
                self.last_error = str(error)
                self._close_serial()
                next_scan = time.perf_counter() + 0.50
