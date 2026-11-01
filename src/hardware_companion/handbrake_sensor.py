"""Handbrake C3 runtime sensor configuration protocol (HB V1)."""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct

FRAME = struct.Struct("<5BHBBBffffBiHB")
FRAME_SIZE = FRAME.size
MAGIC_COMMAND = b"HB"
MAGIC_STATUS = b"HS"
VERSION = 1
KIND_COMMAND = 1
KIND_STATUS = 2

CMD_GET_STATUS = 1
CMD_SET_CONFIG = 2
CMD_TARE = 3
CMD_CALIBRATE = 4
CMD_RESET_DEFAULTS = 5

MODE_HALL = 1
MODE_HX711 = 2

RESULT_TEXT = {
    0: "OK", 1: "Invalid frame", 2: "Invalid configuration",
    3: "HX711 ready timeout", 4: "No load detected",
    5: "Invalid calibration force", 6: "Unsupported command",
    7: "Could not verify saved settings; previous settings restored",
}


def crc8_atm(data: bytes) -> int:
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


@dataclass(frozen=True, slots=True)
class HandbrakeSensorConfig:
    mode: int = MODE_HALL
    filter_divisor: int = 4
    invert: bool = False
    capacity_kg: float = 40.0
    max_force_kg: float = 40.0
    counts_per_kg: float = 25000.0


@dataclass(frozen=True, slots=True)
class HandbrakeSensorStatus:
    sequence: int
    command: int
    config: HandbrakeSensorConfig
    result: int
    raw_delta: int
    output: int

    @property
    def result_text(self) -> str:
        return RESULT_TEXT.get(self.result, f"Unknown result ({self.result})")


def encode_command(command: int, config: HandbrakeSensorConfig | None = None,
                   *, sequence: int = 0, calibration_force_kg: float = 0.0) -> bytes:
    cfg = config or HandbrakeSensorConfig()
    if not all(math.isfinite(v) for v in (cfg.capacity_kg, cfg.max_force_kg,
                                           cfg.counts_per_kg, calibration_force_kg)):
        raise ValueError("Handbrake calibration values must be finite")
    if cfg.mode not in (MODE_HALL, MODE_HX711):
        raise ValueError("Invalid handbrake sensor mode")
    if not 1 <= int(cfg.filter_divisor) <= 32:
        raise ValueError("Filter divisor must be between 1 and 32")
    if cfg.capacity_kg <= 0 or cfg.max_force_kg <= 0 or cfg.counts_per_kg <= 0:
        raise ValueError("Load-cell settings must be positive")
    body = FRAME.pack(
        ord("H"), ord("B"), VERSION, KIND_COMMAND, int(command) & 0xFF,
        int(sequence) & 0xFFFF, int(cfg.mode), int(cfg.filter_divisor),
        1 if cfg.invert else 0, float(cfg.capacity_kg), float(cfg.max_force_kg),
        float(cfg.counts_per_kg), float(calibration_force_kg), 0, 0, 0, 0,
    )
    return body[:-1] + bytes((crc8_atm(body[:-1]),))


def decode_status_frame(frame: bytes) -> HandbrakeSensorStatus | None:
    if len(frame) != FRAME_SIZE or frame[:2] != MAGIC_STATUS:
        return None
    values = FRAME.unpack(frame)
    (_m0, _m1, version, kind, command, sequence, mode, filter_divisor, flags,
     capacity, max_force, counts_per_kg, _calibration_force, result,
     raw_delta, output, crc) = values
    if (_m0, _m1, version, kind) != (ord("H"), ord("S"), VERSION, KIND_STATUS):
        return None
    if crc8_atm(frame[:-1]) != crc:
        return None
    if not all(math.isfinite(v) for v in (capacity, max_force, counts_per_kg)):
        return None
    if mode not in (MODE_HALL, MODE_HX711) or not 1 <= filter_divisor <= 32:
        return None
    cfg = HandbrakeSensorConfig(
        mode=mode, filter_divisor=filter_divisor, invert=bool(flags & 1),
        capacity_kg=capacity, max_force_kg=max_force, counts_per_kg=counts_per_kg,
    )
    return HandbrakeSensorStatus(sequence, command, cfg, result, raw_delta, output)
