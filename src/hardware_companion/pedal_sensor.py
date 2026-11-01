"""Runtime three-pedal sensor configuration protocol (LC/LS V2)."""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct

FRAME = struct.Struct("<5BH7B10fBiiiHHHB")
FRAME_SIZE = FRAME.size
MAGIC_COMMAND = b"LC"
MAGIC_STATUS = b"LS"
VERSION = 2
KIND_COMMAND = 1
KIND_STATUS = 2

CMD_GET_STATUS = 1
CMD_SET_CONFIG = 2
CMD_TARE_THROTTLE = 3
CMD_TARE_BRAKE = 4
CMD_TARE_BOTH = 5
CMD_CALIBRATE_THROTTLE = 6
CMD_CALIBRATE_BRAKE = 7
CMD_RESET_DEFAULTS = 8
CMD_SET_THROTTLE_CONFIG = 9
CMD_SET_BRAKE_CONFIG = 10
CMD_SET_CLUTCH_CONFIG = 11
CMD_TARE_CLUTCH = 12
CMD_CALIBRATE_CLUTCH = 13

MODE_ANALOG = 1
MODE_HX711 = 2

RESULT_TEXT = {
    0: "OK", 1: "Invalid frame", 2: "Invalid configuration",
    3: "HX711 ready timeout", 4: "No load detected",
    5: "Invalid calibration force", 6: "Command unsupported for selected sensor",
    7: "Could not verify saved pedal settings; previous values restored",
}


def crc8_atm(data: bytes) -> int:
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


@dataclass(frozen=True, slots=True)
class PedalSensorConfig:
    throttle_mode: int = MODE_ANALOG
    brake_mode: int = MODE_HX711
    clutch_mode: int = MODE_ANALOG
    flags: int = 0
    throttle_filter_divisor: int = 1
    brake_filter_divisor: int = 1
    clutch_filter_divisor: int = 1
    throttle_capacity_kg: float = 200.0
    brake_capacity_kg: float = 200.0
    clutch_capacity_kg: float = 200.0
    throttle_max_force_kg: float = 10.0
    brake_max_force_kg: float = 40.0
    clutch_max_force_kg: float = 10.0
    throttle_counts_per_kg: float = 25000.0
    brake_counts_per_kg: float = 25000.0
    clutch_counts_per_kg: float = 25000.0


@dataclass(frozen=True, slots=True)
class PedalSensorStatus:
    sequence: int
    config: PedalSensorConfig
    calibration_force_kg: float
    result: int
    throttle_raw_delta: int
    brake_raw_delta: int
    clutch_raw_delta: int
    throttle_output: int
    brake_output: int
    clutch_output: int

    @property
    def result_text(self) -> str:
        return RESULT_TEXT.get(self.result, f"Unknown result ({self.result})")


def _pack_frame(*, kind: int, command: int, sequence: int, config: PedalSensorConfig,
                calibration_force_kg: float = 0.0, result: int = 0,
                throttle_raw_delta: int = 0, brake_raw_delta: int = 0,
                clutch_raw_delta: int = 0, throttle_output: int = 0,
                brake_output: int = 0, clutch_output: int = 0) -> bytes:
    body = FRAME.pack(
        ord("L"), ord("C") if kind == KIND_COMMAND else ord("S"), VERSION,
        kind, int(command) & 0xFF, int(sequence) & 0xFFFF,
        int(config.throttle_mode), int(config.brake_mode), int(config.clutch_mode), int(config.flags) & 0x07,
        max(1, min(255, int(config.throttle_filter_divisor))),
        max(1, min(255, int(config.brake_filter_divisor))),
        max(1, min(255, int(config.clutch_filter_divisor))),
        float(config.throttle_capacity_kg), float(config.brake_capacity_kg), float(config.clutch_capacity_kg),
        float(config.throttle_max_force_kg), float(config.brake_max_force_kg), float(config.clutch_max_force_kg),
        float(config.throttle_counts_per_kg), float(config.brake_counts_per_kg), float(config.clutch_counts_per_kg),
        float(calibration_force_kg), int(result) & 0xFF,
        int(throttle_raw_delta), int(brake_raw_delta), int(clutch_raw_delta),
        max(0, min(4095, int(throttle_output))), max(0, min(4095, int(brake_output))), max(0, min(4095, int(clutch_output))), 0,
    )
    return body[:-1] + bytes((crc8_atm(body[:-1]),))


def encode_command(command: int, config: PedalSensorConfig | None = None, *, sequence: int = 0,
                   calibration_force_kg: float = 0.0) -> bytes:
    return _pack_frame(kind=KIND_COMMAND, command=command, sequence=sequence,
                       config=config or PedalSensorConfig(), calibration_force_kg=calibration_force_kg)


def encode_axis_config_command(axis: str, config: PedalSensorConfig, *, sequence: int = 0) -> bytes:
    command = {"throttle": CMD_SET_THROTTLE_CONFIG, "brake": CMD_SET_BRAKE_CONFIG,
               "clutch": CMD_SET_CLUTCH_CONFIG}.get(axis.strip().lower())
    if command is None:
        raise ValueError("axis must be 'throttle', 'brake', or 'clutch'")
    return encode_command(command, config, sequence=sequence)


def decode_status_frame(frame: bytes) -> PedalSensorStatus | None:
    if len(frame) != FRAME_SIZE or frame[:2] != MAGIC_STATUS or frame[2] != VERSION or frame[3] != KIND_STATUS:
        return None
    if crc8_atm(frame[:-1]) != frame[-1]:
        return None
    values = FRAME.unpack(frame)
    (_m0, _m1, _version, _kind, _command, sequence,
     throttle_mode, brake_mode, clutch_mode, flags,
     throttle_filter, brake_filter, clutch_filter,
     throttle_capacity, brake_capacity, clutch_capacity,
     throttle_max_force, brake_max_force, clutch_max_force,
     throttle_counts, brake_counts, clutch_counts,
     calibration_force, result, throttle_delta, brake_delta, clutch_delta,
     throttle_output, brake_output, clutch_output, _crc) = values
    floats = (throttle_capacity, brake_capacity, clutch_capacity,
              throttle_max_force, brake_max_force, clutch_max_force,
              throttle_counts, brake_counts, clutch_counts, calibration_force)
    if not all(math.isfinite(value) for value in floats):
        return None
    config = PedalSensorConfig(
        throttle_mode=throttle_mode, brake_mode=brake_mode, clutch_mode=clutch_mode, flags=flags,
        throttle_filter_divisor=throttle_filter, brake_filter_divisor=brake_filter,
        clutch_filter_divisor=clutch_filter,
        throttle_capacity_kg=throttle_capacity, brake_capacity_kg=brake_capacity,
        clutch_capacity_kg=clutch_capacity,
        throttle_max_force_kg=throttle_max_force, brake_max_force_kg=brake_max_force,
        clutch_max_force_kg=clutch_max_force,
        throttle_counts_per_kg=throttle_counts, brake_counts_per_kg=brake_counts,
        clutch_counts_per_kg=clutch_counts,
    )
    return PedalSensorStatus(
        sequence=sequence, config=config, calibration_force_kg=calibration_force,
        result=result, throttle_raw_delta=throttle_delta, brake_raw_delta=brake_delta,
        clutch_raw_delta=clutch_delta, throttle_output=throttle_output,
        brake_output=brake_output, clutch_output=clutch_output,
    )
