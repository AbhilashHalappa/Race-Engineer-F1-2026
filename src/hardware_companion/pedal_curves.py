from __future__ import annotations

from dataclasses import dataclass
import struct

RAW_MAX = 4095
INPUT_POINTS = (0, 20, 40, 60, 80, 100)
DEFAULT_OUTPUT = INPUT_POINTS
MAX_DEADZONE_PERCENT = 30

COMMAND_MAGIC = b"PC"
RESPONSE_MAGIC = b"PS"
VERSION_V1 = 1
VERSION_V2 = 2
VERSION_V3 = 3
VERSION = VERSION_V1
CMD_APPLY_VOLATILE = 1
CMD_SAVE = 2
CMD_REQUEST = 3
CMD_RESET_DEFAULTS = 4
FLAG_CLUTCH_ENABLED = 1 << 0
FLAG_HANDBRAKE_ENABLED = 1 << 1

# V1 is byte-for-byte Wheel Companion Lite / Receiver V8.3.4+.
COMMAND_V1_NO_CRC = struct.Struct("<2sBB16B")
COMMAND_V1_FRAME_SIZE = COMMAND_V1_NO_CRC.size + 1
RESPONSE_V1_NO_CRC = struct.Struct("<2sB16B")
RESPONSE_V1_FRAME_SIZE = RESPONSE_V1_NO_CRC.size + 1

# V2 adds one feature byte plus a third 8-byte axis. V1 remains supported.
COMMAND_V2_NO_CRC = struct.Struct("<2sBBB24B")
COMMAND_V2_FRAME_SIZE = COMMAND_V2_NO_CRC.size + 1
RESPONSE_V2_NO_CRC = struct.Struct("<2sBB24B")
RESPONSE_V2_FRAME_SIZE = RESPONSE_V2_NO_CRC.size + 1

COMMAND_V3_NO_CRC = struct.Struct("<2sBBB32B")
COMMAND_V3_FRAME_SIZE = COMMAND_V3_NO_CRC.size + 1
RESPONSE_V3_NO_CRC = struct.Struct("<2sBB32B")
RESPONSE_V3_FRAME_SIZE = RESPONSE_V3_NO_CRC.size + 1

# Backward-compatible aliases retained for existing tests/tools.
COMMAND_NO_CRC = COMMAND_V1_NO_CRC
COMMAND_FRAME_SIZE = COMMAND_V1_FRAME_SIZE
RESPONSE_NO_CRC = RESPONSE_V1_NO_CRC
RESPONSE_FRAME_SIZE = RESPONSE_V1_FRAME_SIZE


def _crc8_atm(data: bytes) -> int:
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


@dataclass(frozen=True, slots=True)
class AxisCurve:
    bottom_deadzone: int = 0
    top_deadzone: int = 0
    outputs: tuple[int, int, int, int, int, int] = DEFAULT_OUTPUT

    def sanitized(self) -> "AxisCurve":
        bottom = max(0, min(MAX_DEADZONE_PERCENT, int(self.bottom_deadzone)))
        top = max(0, min(MAX_DEADZONE_PERCENT, int(self.top_deadzone)))
        if bottom + top >= 95:
            top = max(0, 94 - bottom)
        values = []
        previous = 0
        for i, value in enumerate(self.outputs[:6]):
            value = max(0, min(100, int(value)))
            if i and value < previous:
                value = previous
            values.append(value)
            previous = value
        while len(values) < 6:
            values.append(values[-1] if values else 0)
        return AxisCurve(bottom, top, tuple(values))

    @property
    def is_linear(self) -> bool:
        clean = self.sanitized()
        return clean.bottom_deadzone == 0 and clean.top_deadzone == 0 and clean.outputs == DEFAULT_OUTPUT

    def output_percent(self, raw: int | float) -> float:
        clean = self.sanitized()
        value = max(0.0, min(float(RAW_MAX), float(raw)))
        bottom_raw = RAW_MAX * clean.bottom_deadzone / 100.0
        top_raw = RAW_MAX * (100.0 - clean.top_deadzone) / 100.0
        if value <= bottom_raw:
            x = 0.0
        elif value >= top_raw or top_raw <= bottom_raw:
            x = 100.0
        else:
            x = (value - bottom_raw) * 100.0 / (top_raw - bottom_raw)
        if x >= 100.0:
            return float(clean.outputs[-1])
        index = min(4, int(x // 20.0))
        start_x = INPUT_POINTS[index]
        t = (x - start_x) / 20.0
        y0 = clean.outputs[index]
        y1 = clean.outputs[index + 1]
        return float(y0 + (y1 - y0) * t)


@dataclass(frozen=True, slots=True)
class PedalCurveSettings:
    throttle: AxisCurve = AxisCurve()
    brake: AxisCurve = AxisCurve()
    clutch: AxisCurve = AxisCurve()
    clutch_enabled: bool = False
    handbrake: AxisCurve = AxisCurve()
    handbrake_enabled: bool = False

    def sanitized(self) -> "PedalCurveSettings":
        return PedalCurveSettings(
            self.throttle.sanitized(),
            self.brake.sanitized(),
            self.clutch.sanitized(),
            bool(self.clutch_enabled),
            self.handbrake.sanitized(),
            bool(self.handbrake_enabled),
        )


def _axis_bytes(axis: AxisCurve) -> list[int]:
    clean = axis.sanitized()
    return [clean.bottom_deadzone, clean.top_deadzone, *clean.outputs]


def encode_command(command: int, settings: PedalCurveSettings | None = None, *, version: int = VERSION_V1) -> bytes:
    clean = (settings or PedalCurveSettings()).sanitized()
    if version == VERSION_V3:
        flags = (FLAG_CLUTCH_ENABLED if clean.clutch_enabled else 0) | (FLAG_HANDBRAKE_ENABLED if clean.handbrake_enabled else 0)
        payload = _axis_bytes(clean.throttle) + _axis_bytes(clean.brake) + _axis_bytes(clean.clutch) + _axis_bytes(clean.handbrake)
        body = COMMAND_V3_NO_CRC.pack(COMMAND_MAGIC, VERSION_V3, int(command) & 0xFF, flags, *payload)
    elif version == VERSION_V2:
        flags = FLAG_CLUTCH_ENABLED if clean.clutch_enabled else 0
        payload = _axis_bytes(clean.throttle) + _axis_bytes(clean.brake) + _axis_bytes(clean.clutch)
        body = COMMAND_V2_NO_CRC.pack(COMMAND_MAGIC, VERSION_V2, int(command) & 0xFF, flags, *payload)
    else:
        payload = _axis_bytes(clean.throttle) + _axis_bytes(clean.brake)
        body = COMMAND_V1_NO_CRC.pack(COMMAND_MAGIC, VERSION_V1, int(command) & 0xFF, *payload)
    return body + bytes((_crc8_atm(body),))


def response_frame_size_for_version(version: int) -> int | None:
    if version == VERSION_V1:
        return RESPONSE_V1_FRAME_SIZE
    if version == VERSION_V2:
        return RESPONSE_V2_FRAME_SIZE
    if version == VERSION_V3:
        return RESPONSE_V3_FRAME_SIZE
    return None


def decode_response(frame: bytes) -> tuple[PedalCurveSettings, int] | None:
    if len(frame) < 4 or frame[:2] != RESPONSE_MAGIC:
        return None
    version = frame[2]
    expected = response_frame_size_for_version(version)
    if expected is None or len(frame) != expected:
        return None
    body, received_crc = frame[:-1], frame[-1]
    if _crc8_atm(body) != received_crc:
        return None
    if version == VERSION_V1:
        unpacked = RESPONSE_V1_NO_CRC.unpack(body)
        payload = list(unpacked[2:])
        throttle = AxisCurve(payload[0], payload[1], tuple(payload[2:8]))
        brake = AxisCurve(payload[8], payload[9], tuple(payload[10:16]))
        return PedalCurveSettings(throttle, brake).sanitized(), version
    if version == VERSION_V2:
        unpacked = RESPONSE_V2_NO_CRC.unpack(body)
        flags = int(unpacked[2]); payload = list(unpacked[3:])
        throttle = AxisCurve(payload[0], payload[1], tuple(payload[2:8]))
        brake = AxisCurve(payload[8], payload[9], tuple(payload[10:16]))
        clutch = AxisCurve(payload[16], payload[17], tuple(payload[18:24]))
        return PedalCurveSettings(throttle, brake, clutch=clutch, clutch_enabled=bool(flags & FLAG_CLUTCH_ENABLED)).sanitized(), version
    unpacked = RESPONSE_V3_NO_CRC.unpack(body)
    flags = int(unpacked[2]); payload = list(unpacked[3:])
    throttle = AxisCurve(payload[0], payload[1], tuple(payload[2:8]))
    brake = AxisCurve(payload[8], payload[9], tuple(payload[10:16]))
    clutch = AxisCurve(payload[16], payload[17], tuple(payload[18:24]))
    handbrake = AxisCurve(payload[24], payload[25], tuple(payload[26:32]))
    return PedalCurveSettings(throttle, brake, clutch, bool(flags & FLAG_CLUTCH_ENABLED), handbrake, bool(flags & FLAG_HANDBRAKE_ENABLED)).sanitized(), version
