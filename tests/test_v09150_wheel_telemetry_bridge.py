from types import SimpleNamespace

from src.wheel_telemetry import (
    FRAME_SIZE, LOW_ERS, LOW_FUEL, DRS_ACTIVE, DRS_SHIFT,
    WheelTelemetrySnapshot, crc8_atm, encode_frame, snapshot_from_state,
)


def ev(raw):
    return SimpleNamespace(raw=raw)


def test_compact_frame_is_fixed_15_bytes_and_crc_valid():
    snap = WheelTelemetrySnapshot(321, 7, 2, 88, 0, 5, 3, 0x32)
    frame = encode_frame(snap, 0x1234)
    assert len(frame) == FRAME_SIZE == 15
    assert frame[:3] == b"RE\x01"
    assert frame[-1] == crc8_atm(frame[:-1])


def test_state_projection_contains_only_wheel_needed_values():
    state = SimpleNamespace(
        session=SimpleNamespace(ended=False, marshal_zones=(), track_length_m=5000),
        player=SimpleNamespace(
            telemetry=SimpleNamespace(speed_kph=287, gear=8, rev_lights_percent=97, drs=True),
            lap=SimpleNamespace(position=1, result_status=ev(2), lap_distance_m=1000),
            fuel=SimpleNamespace(remaining_mass=5.0, capacity=50.0),
            energy=SimpleNamespace(store_j=500_000.0, deploy_mode=ev(3)),
            aero=SimpleNamespace(drs_allowed=True),
        ),
    )
    snap = snapshot_from_state(state)
    assert snap.speed == 287
    assert snap.gear == 8
    assert snap.position == 1
    assert snap.rpm_percent == 97
    assert snap.shift_light == 1
    assert snap.ers_mode == 3
    assert snap.status_bits & LOW_FUEL
    assert snap.status_bits & LOW_ERS
    assert ((snap.status_bits >> DRS_SHIFT) & 0x0F) == DRS_ACTIVE
