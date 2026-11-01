
import struct

from src.acc_telemetry import (
    PHYSICS_PREFIX,
    decode_physics_prefix,
)


def test_acc_physics_prefix_decodes_core_values():
    raw = PHYSICS_PREFIX.pack(
        123, 0.75, 0.25, 42.5, 2, 8120, 0.0, 176.4
    )
    values = decode_physics_prefix(raw)

    assert values["packet_id"] == 123
    assert values["throttle"] == 0.75
    assert values["brake"] == 0.25
    assert values["fuel_l"] == 42.5
    assert values["gear"] == 1
    assert values["rpm"] == 8120
    assert values["speed_kph"] == 176.4


def test_acc_reverse_and_neutral_gears():
    reverse = decode_physics_prefix(
        PHYSICS_PREFIX.pack(1, 0.0, 0.0, 30.0, 0, 2000, 0.0, 10.0)
    )
    neutral = decode_physics_prefix(
        PHYSICS_PREFIX.pack(2, 0.0, 0.0, 30.0, 1, 2000, 0.0, 10.0)
    )

    assert reverse["gear"] == -1
    assert neutral["gear"] == 0


def test_acc_pedals_and_speed_are_clamped():
    raw = PHYSICS_PREFIX.pack(
        3, 1.5, -0.2, -4.0, 1, 9000, 0.0, -1.0
    )
    values = decode_physics_prefix(raw)

    assert values["throttle"] == 1.0
    assert values["brake"] == 0.0
    assert values["fuel_l"] == 0.0
    assert values["speed_kph"] == 0.0


def test_acc_short_or_nonfinite_data_is_rejected():
    try:
        decode_physics_prefix(b"short")
    except ValueError:
        pass
    else:
        raise AssertionError("Short physics page should be rejected")

    raw = PHYSICS_PREFIX.pack(
        4, float("nan"), 0.0, 30.0, 1, 2000, 0.0, 10.0
    )
    try:
        decode_physics_prefix(raw)
    except ValueError:
        pass
    else:
        raise AssertionError("Non-finite telemetry should be rejected")
