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
    # ACC-only telemetry fields. Defaults keep every existing F1 caller intact.
    fuel_l: float | None = None
    best_lap_time_ms: int | None = None
    last_lap_time_ms: int | None = None
    is_in_pit: bool = False
    is_in_pit_lane: bool = False
    car: str = ""
    track: str = ""
    session: int | None = None
    ers_percent: float | None = None
    ers_mode: int = 0
    flag_status: int = 0
    session_uid: int = 0
    game_year: int = 0
    # Extended ACC Shared Memory v1.8.12 telemetry. None means the field
    # is unavailable; F1 callers retain their original defaults.
    clutch_percent: int | None = None
    current_lap_time_ms: int | None = None
    session_time_left_s: float | None = None
    session_type: int | None = None
    sector: int | None = None
    lap_valid: bool | None = None
    lap_distance_m: float | None = None
    normalized_car_position: float | None = None
    lap_distance_m: float | None = None
    tyre_compound: str = ""
    tyre_pressures_psi: tuple[float | None, ...] | None = None
    tyre_core_temperatures_c: tuple[float | None, ...] | None = None
    tyre_dirty_level: tuple[float | None, ...] | None = None
    wheel_slip: tuple[float | None, ...] | None = None
    wheel_load: tuple[float | None, ...] | None = None
    wheel_angular_speed: tuple[float | None, ...] | None = None
    suspension_travel: tuple[float | None, ...] | None = None
    brake_temperatures_c: tuple[float | None, ...] | None = None
    brake_pressures: tuple[float | None, ...] | None = None
    brake_pad_life: tuple[float | None, ...] | None = None
    brake_disc_life: tuple[float | None, ...] | None = None
    car_damage: tuple[float | None, ...] | None = None
    air_temperature_c: float | None = None
    track_temperature_c: float | None = None
    water_temperature_c: float | None = None
    turbo_boost: float | None = None
    brake_bias: float | None = None
    tc_level: int | None = None
    tc_cut: int | None = None
    abs_level: int | None = None
    engine_map: int | None = None
    pit_limiter_on: bool | None = None
    penalty_time_s: float | None = None
    penalty_type: int | None = None
    fuel_per_lap: float | None = None
    fuel_estimated_laps: float | None = None
    used_fuel_l: float | None = None
    track_status: str = ""
    track_grip_status: int | None = None
    rain_intensity: int | None = None
    rain_intensity_10min: int | None = None
    rain_intensity_30min: int | None = None
    rain_tyres: bool | None = None
    wind_speed_mps: float | None = None
    wind_direction_rad: float | None = None
    mandatory_pit_done: bool | None = None
    missing_mandatory_pits: int | None = None
    driver_stint_left_ms: int | None = None
    driver_stint_total_ms: int | None = None
    gap_ahead_ms: int | None = None
    gap_behind_ms: int | None = None
    fuel_to_add_l: float | None = None
    current_tyre_set: int | None = None
    number_of_laps: int | None = None
    player_name: str = ""
    strategy_tyre_set: int | None = None
    exhaust_temperature_c: float | None = None
    engine_running: bool | None = None
    ignition_on: bool | None = None
    is_ai_controlled: bool | None = None
    g_force: tuple[float | None, ...] | None = None
    local_velocity: tuple[float | None, ...] | None = None
    local_angular_velocity: tuple[float | None, ...] | None = None
    world_position_x: float | None = None
    world_position_y: float | None = None
    world_position_z: float | None = None
    surface_grip: float | None = None
    session_index: int | None = None
    active_cars: int | None = None
    player_car_id: int | None = None
    delta_lap_time_ms: int | None = None
    estimated_lap_time_ms: int | None = None
    split_time_ms: int | None = None
    delta_positive: bool | None = None
    clock_s: float | None = None
    global_yellow: bool | None = None
    global_green: bool | None = None
    global_chequered: bool | None = None
    global_red: bool | None = None
    rain_lights: bool | None = None
    flashing_lights: bool | None = None
    lights_stage: int | None = None
    wiper_level: int | None = None
    track_configuration: str = ""
    last_packet_monotonic: float | None = None
