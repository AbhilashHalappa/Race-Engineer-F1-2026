"""Extended ACC shared-memory field decoders.

The existing Stage 1 reader is intentionally left untouched here. These
small decoders provide the ACC session/engineering layer with documented
physics and graphics fields without changing the protected F1 telemetry path.
"""
from __future__ import annotations

import math
import struct


PHYSICS_SIZE = 320
GRAPHICS_SIZE = 1024
STATIC_SIZE = 512


def _finite(value: float, default: float = 0.0) -> float:
    return float(value) if math.isfinite(float(value)) else default


def _floats(data: bytes, offset: int, count: int) -> tuple[float, ...]:
    end = offset + count * 4
    if len(data) < end:
        return ()
    return tuple(_finite(v) for v in struct.unpack_from(f"<{count}f", data, offset))


def decode_physics_extended(data: bytes) -> dict:
    if len(data) < 32:
        raise ValueError("ACC physics page is too short")
    out = {
        "velocity": _floats(data, 32, 3),
        "acc_g": _floats(data, 44, 3),
        "wheel_slip": _floats(data, 56, 4),
        "wheel_load": _floats(data, 72, 4),
        "wheel_pressure_psi": _floats(data, 88, 4),
        "wheel_angular_speed": _floats(data, 104, 4),
        "tyre_wear": _floats(data, 120, 4),
        "tyre_dirty_level": _floats(data, 136, 4),
        "tyre_core_temp_c": _floats(data, 152, 4),
        "camber_rad": _floats(data, 168, 4),
        "suspension_travel": _floats(data, 184, 4),
    }
    # Fields after suspensionTravel in the published packed layout.
    if len(data) >= 204:
        out["drs"] = _finite(struct.unpack_from("<f", data, 200)[0])
        out["tc"] = _finite(struct.unpack_from("<f", data, 204)[0])
    if len(data) >= 216:
        out["heading_rad"] = _finite(struct.unpack_from("<f", data, 208)[0])
        out["pitch_rad"] = _finite(struct.unpack_from("<f", data, 212)[0])
    if len(data) >= 220:
        out["roll_rad"] = _finite(struct.unpack_from("<f", data, 216)[0])
    if len(data) >= 248:
        out["abs"] = _finite(struct.unpack_from("<f", data, 244)[0])
    return out


def _utf16(data: bytes, offset: int, chars: int) -> str:
    size = chars * 2
    if len(data) < offset + size:
        return ""
    raw = data[offset:offset + size]
    return raw.decode("utf-16-le", errors="ignore").split("\x00", 1)[0].strip()


def decode_graphics_extended(data: bytes) -> dict:
    if len(data) < 176:
        raise ValueError("ACC graphics page is too short")
    values = {
        "status": struct.unpack_from("<i", data, 4)[0],
        "session": struct.unpack_from("<i", data, 8)[0],
        "current_time_ms": struct.unpack_from("<i", data, 140)[0],
        "last_time_ms": struct.unpack_from("<i", data, 144)[0],
        "best_time_ms": struct.unpack_from("<i", data, 148)[0],
        "session_time_left_s": _finite(struct.unpack_from("<f", data, 152)[0]),
        "distance_traveled_m": _finite(struct.unpack_from("<f", data, 156)[0]),
        "is_in_pit": bool(struct.unpack_from("<i", data, 160)[0]),
        "current_sector": struct.unpack_from("<i", data, 164)[0],
        "last_sector_time_ms": struct.unpack_from("<i", data, 168)[0],
        "number_of_laps": struct.unpack_from("<i", data, 172)[0],
        "tyre_compound": _utf16(data, 176, 33),
    }
    if len(data) >= 250:
        values["normalized_car_position"] = _finite(struct.unpack_from("<f", data, 246)[0])
    if len(data) >= 266:
        values["penalty_time_s"] = _finite(struct.unpack_from("<f", data, 262)[0])
    if len(data) >= 270:
        values["flag"] = max(0, min(8, struct.unpack_from("<i", data, 266)[0]))
    if len(data) >= 278:
        values["is_in_pit_lane"] = bool(struct.unpack_from("<i", data, 274)[0])
    return values


def decode_static_extended(data: bytes) -> dict:
    if len(data) < 418:
        raise ValueError("ACC static page is too short")
    return {
        "car_model": _utf16(data, 68, 33),
        "track": _utf16(data, 134, 33),
        "player_name": _utf16(data, 200, 33),
        "player_surname": _utf16(data, 266, 33),
        "player_nickname": _utf16(data, 332, 33),
        "sector_count": struct.unpack_from("<i", data, 398)[0],
        "max_rpm": max(0, struct.unpack_from("<i", data, 410)[0]),
        "max_fuel_l": max(0.0, _finite(struct.unpack_from("<f", data, 414)[0])),
    }
