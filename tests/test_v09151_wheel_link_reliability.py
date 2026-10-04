import struct

from src.wheel_telemetry import (
    STATUS_FRAME_SIZE,
    STATUS_NO_CRC,
    STATUS_MAGIC,
    STATUS_VERSION,
    HEALTH_WHEEL,
    HEALTH_PEDALS,
    HEALTH_MOTOR_TEMP,
    HEALTH_RACE_ENGINEER,
    crc8_atm,
    decode_status_frame,
)


def make_status(flags, wheel_age=10, pedal_age=20, motor_age=30, pc_age=5,
                wheel_packets=100, pedal_packets=200, motor_packets=3):
    body = STATUS_NO_CRC.pack(
        STATUS_MAGIC, STATUS_VERSION, flags,
        wheel_age, pedal_age, motor_age, pc_age,
        wheel_packets, pedal_packets, motor_packets,
    )
    return body + bytes((crc8_atm(body),))


def test_receiver_status_frame_is_fixed_25_bytes_and_decodes_all_peers():
    flags = HEALTH_WHEEL | HEALTH_PEDALS | HEALTH_MOTOR_TEMP | HEALTH_RACE_ENGINEER
    frame = make_status(flags)
    assert len(frame) == STATUS_FRAME_SIZE == 25
    status = decode_status_frame(frame)
    assert status is not None
    assert status.wheel_connected
    assert status.pedals_connected
    assert status.motor_temp_connected
    assert status.receiver_has_pc_telemetry
    assert status.wheel_age_ms == 10
    assert status.pedals_age_ms == 20
    assert status.motor_temp_age_ms == 30
    assert status.pc_telemetry_age_ms == 5
    assert status.wheel_packets == 100
    assert status.pedal_packets == 200
    assert status.motor_temp_packets == 3
    assert status.all_peripherals_connected


def test_status_frame_rejects_bad_crc():
    frame = bytearray(make_status(HEALTH_WHEEL))
    frame[-1] ^= 0x55
    assert decode_status_frame(bytes(frame)) is None


def test_unknown_age_ffff_maps_to_none():
    status = decode_status_frame(make_status(0, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF))
    assert status is not None
    assert status.wheel_age_ms is None
    assert status.pedals_age_ms is None
    assert status.motor_temp_age_ms is None
    assert status.pc_telemetry_age_ms is None
