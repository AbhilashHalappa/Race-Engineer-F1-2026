from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WheelTelemetrySnapshot:
    speed: int = 0
    gear: int = 0
    position: int = 0
    rpm_percent: int = 0
    shift_light: int = 0
    flag_status: int = 0
    ers_mode: int = 0
    status_bits: int = 0


@dataclass(frozen=True, slots=True)
class WheelLinkHealth:
    serial_connected: bool = False
    port: str | None = None
    status_fresh: bool = False
    status_protocol_version: int = 0
    extended_status_active: bool = False
    wheel_connected: bool = False
    pedals_connected: bool = False
    motor_temp_connected: bool = False
    receiver_has_pc_telemetry: bool = False
    wheel_age_ms: int | None = None
    pedals_age_ms: int | None = None
    motor_temp_age_ms: int | None = None
    pc_telemetry_age_ms: int | None = None
    wheel_packets: int = 0
    pedal_packets: int = 0
    motor_temp_packets: int = 0
    pedal_throttle_raw: int | None = None
    pedal_brake_raw: int | None = None
    pedal_clutch_raw: int | None = None
    handbrake_raw: int | None = None
    pedal_throttle_percent: float | None = None
    pedal_brake_percent: float | None = None
    pedal_clutch_percent: float | None = None
    handbrake_percent: float | None = None
    clutch_supported: bool = False
    handbrake_supported: bool = False
    motor_temp_c: float | None = None
    frames_sent: int = 0
    status_frames_received: int = 0
    live_value_frames_received: int = 0
    reconnects: int = 0
    link_losses: int = 0
    last_error: str | None = None
    last_status_monotonic: float | None = None
    last_live_values_monotonic: float | None = None

    @property
    def all_peripherals_connected(self) -> bool:
        return bool(
            self.status_fresh
            and self.wheel_connected
            and self.pedals_connected
            and self.motor_temp_connected
        )


@dataclass(frozen=True, slots=True)
class LiveTelemetry:
    udp_connected: bool = False
    source: str = "--"
    packets_per_second: float = 0.0
    total_packets: int = 0
    invalid_packets: int = 0
    speed_kph: int = 0
    gear: int = 0
    engine_rpm: int = 0
    rpm_percent: int = 0
    throttle_percent: int = 0
    brake_percent: int = 0
    steering_percent: int = 0
    drs_active: bool = False
    drs_available: bool = False
    position: int = 0
    lap_number: int = 0
    fuel_percent: float | None = None
    ers_percent: float | None = None
    ers_mode: int = 0
    flag_status: int = 0
    session_uid: int = 0
    game_year: int = 0
    last_packet_monotonic: float | None = None
