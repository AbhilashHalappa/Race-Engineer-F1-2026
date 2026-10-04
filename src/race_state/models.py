"""Typed consumer model. None means missing or unusable, never guessed."""

from dataclasses import dataclass, field as dc_field
from ..telemetry.enums import EnumValue


@dataclass(frozen=True, slots=True)
class Wheels:
    FL: float | int | None
    FR: float | int | None
    RL: float | int | None
    RR: float | int | None


@dataclass(frozen=True, slots=True)
class Freshness:
    received_at: float
    overall_frame: int
    session_time_s: float

    def age(self, now: float) -> float:
        return max(0.0, now - self.received_at)


@dataclass(frozen=True, slots=True)
class Forecast:
    session_type: EnumValue
    offset_minutes: int
    weather: EnumValue
    track_temperature_c: int
    track_temperature_change: EnumValue
    air_temperature_c: int
    air_temperature_change: EnumValue
    rain_percent: int


@dataclass(frozen=True, slots=True)
class MarshalZoneState:
    start_fraction: float
    flag: EnumValue


@dataclass(slots=True)
class SessionState:
    uid: int | None = None
    session_type: EnumValue | None = None
    track: EnumValue | None = None
    weather: EnumValue | None = None
    track_temperature_c: int | None = None
    air_temperature_c: int | None = None
    total_laps: int | None = None
    track_length_m: int | None = None
    time_left_s: int | None = None
    duration_s: int | None = None
    pit_speed_limit_kph: int | None = None
    pit_stop_window_ideal_lap: int | None = None
    pit_stop_window_latest_lap: int | None = None
    safety_car: EnumValue | None = None
    marshal_zones: tuple[MarshalZoneState, ...] = ()
    paused: bool | None = None
    spectating: bool | None = None
    forecast: tuple[Forecast, ...] = ()
    forecast_accuracy: EnumValue | None = None
    # Raw EA session/rules context used to decide which analyses are meaningful.
    formula: int | None = None
    network_game: bool | None = None
    game_mode: int | None = None
    rule_set: int | None = None
    equal_car_performance: int | None = None
    low_fuel_mode: int | None = None
    car_damage: int | None = None
    car_damage_rate: int | None = None
    corner_cutting_stringency: int | None = None
    parc_ferme_rules: bool | None = None
    safety_car_setting: int | None = None
    red_flags_setting: int | None = None
    ended: bool | None = None
    session_time_s: float | None = None
    packet_format: int | None = None
    game_year: int | None = None
    game_version: str | None = None
    anti_lock_brakes_assist: int | None = None
    traction_control_assist: int | None = None
    steering_assist: int | None = None
    braking_assist: int | None = None
    gearbox_assist: int | None = None
    pit_assist: int | None = None
    pit_release_assist: int | None = None
    ers_assist: int | None = None
    drs_assist: int | None = None


@dataclass(slots=True)
class Identity:
    name: str | None = None
    team: EnumValue | None = None
    ai_controlled: bool | None = None
    race_number: int | None = None
    telemetry_public: bool | None = None
    driver_id: int | None = None
    team_id: int | None = None
    nationality_id: int | None = None
    platform_id: int | None = None
    my_team: bool | None = None


@dataclass(slots=True)
class LapState:
    position: int | None = None
    current_lap: int | None = None
    current_lap_time_s: float | None = None
    previous_lap_time_s: float | None = None
    sector: int | None = None
    sector1_time_s: float | None = None
    sector2_time_s: float | None = None
    lap_distance_m: float | None = None
    total_distance_m: float | None = None
    lap_valid: bool | None = None
    pit_status: EnumValue | None = None
    pit_stops: int | None = None
    pit_lane_timer_active: bool | None = None
    pit_lane_time_s: float | None = None
    pit_stop_time_s: float | None = None
    pit_stop_should_serve_penalty: bool | None = None
    penalties_s: int | None = None
    warnings: int | None = None
    corner_cutting_warnings: int | None = None
    unserved_drive_through: int | None = None
    unserved_stop_go: int | None = None
    grid_position: int | None = None
    driver_status: EnumValue | None = None
    result_status: EnumValue | None = None
    gap_to_car_in_front_s: float | None = None
    gap_to_leader_s: float | None = None


@dataclass(slots=True)
class CarTelemetry:
    speed_kph: int | None = None
    throttle: float | None = None
    brake: float | None = None
    clutch_percent: int | None = None
    steering: float | None = None
    gear: int | None = None
    rpm: int | None = None
    drs: bool | None = None
    rev_lights_percent: int | None = None
    rev_lights_bits: int | None = None
    engine_temperature_c: int | None = None
    brakes_temperature_c: Wheels | None = None
    surface_type: Wheels | None = None


@dataclass(slots=True)
class FuelState:
    remaining_mass: float | None = None
    capacity: float | None = None
    remaining_laps: float | None = None
    mix: EnumValue | None = None
    # EA labels mass/capacity but does not specify their units in this spec.
    mass_unit: str = 'EA raw mass (unit unspecified)'


@dataclass(slots=True)
class EnergyState:
    store_j: float | None = None
    deploy_mode: EnumValue | None = None
    harvested_mguk_j: float | None = None
    harvested_mguh_j: float | None = None
    harvest_limit_j: float | None = None
    deployed_this_lap_j: float | None = None


@dataclass(slots=True)
class AeroOvertakeState:
    active_aero_mode: EnumValue | None = None
    active_aero_available: bool | None = None
    active_aero_activation_distance_m: int | None = None
    overtake_available: bool | None = None
    overtake_active: bool | None = None
    overtake_activation_distance_m: int | None = None
    regulations_2026: bool | None = None
    driving_wrong_way: bool | None = None
    drs_allowed: bool | None = None
    drs_activation_distance_m: int | None = None
    raw_flags: dict[str, int] = dc_field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TyreSet:
    index: int
    actual_compound: EnumValue
    visual_compound: EnumValue
    wear_percent: int
    available: bool | None
    recommended_session: EnumValue
    lifespan_laps: int
    usable_life_laps: int
    lap_delta_s: float
    fitted: bool | None


@dataclass(slots=True)
class TyreState:
    actual_compound: EnumValue | None = None
    visual_compound: EnumValue | None = None
    age_laps: int | None = None
    wear_percent: Wheels | None = None
    damage_percent: Wheels | None = None
    blisters_percent: Wheels | None = None
    surface_temperature_c: Wheels | None = None
    inner_temperature_c: Wheels | None = None
    pressure_psi: Wheels | None = None
    sets: tuple[TyreSet, ...] = ()
    fitted_set_index: int | None = None
    fitted_set_index_raw: int | None = None
    punctured: Wheels | None = None  # Not explicitly provided: no inference from wear.


@dataclass(slots=True)
class DamageState:
    front_left_wing_percent: int | None = None
    front_right_wing_percent: int | None = None
    rear_wing_percent: int | None = None
    floor_percent: int | None = None
    diffuser_percent: int | None = None
    sidepod_percent: int | None = None
    drs_fault: bool | None = None
    ers_fault: bool | None = None
    gearbox_percent: int | None = None
    engine_percent: int | None = None
    engine_wear_percent: dict[str, int] = dc_field(default_factory=dict)
    engine_blown: bool | None = None
    engine_seized: bool | None = None
    brakes_percent: Wheels | None = None


@dataclass(slots=True)
class CarState:
    index: int
    identity: Identity = dc_field(default_factory=Identity)
    lap: LapState = dc_field(default_factory=LapState)
    telemetry: CarTelemetry = dc_field(default_factory=CarTelemetry)
    fuel: FuelState = dc_field(default_factory=FuelState)
    energy: EnergyState = dc_field(default_factory=EnergyState)
    aero: AeroOvertakeState = dc_field(default_factory=AeroOvertakeState)
    tyres: TyreState = dc_field(default_factory=TyreState)
    damage: DamageState = dc_field(default_factory=DamageState)
    updated: dict[str, Freshness] = dc_field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RaceEvent:
    code: str
    name: str
    details: dict[str, int | float | None]
    session_time_s: float
    received_at: float


@dataclass(frozen=True, slots=True)
class MeasuredLapFact:
    """Observed facts for a completed lap. No future extrapolation."""
    lap_number: int
    lap_time_s: float | None = None
    fuel_used: float | None = None
    tyre_wear_delta: Wheels | None = None
    start_position: int | None = None
    end_position: int | None = None
    position_change: int | None = None
    start_gap_ahead_s: float | None = None
    end_gap_ahead_s: float | None = None
    gap_ahead_change_s: float | None = None
    # End-of-lap snapshots retained for deterministic overlay history.
    fuel_remaining_end: float | None = None
    tyre_wear_end: Wheels | None = None
    # Tyre set fitted at the *start* of the completed lap.  Keeping this
    # distinct from the end set prevents a pit/out lap from being attributed
    # to the newly fitted set and corrupting degradation/stint calculations.
    fitted_tyre_set_index: int | None = None
    end_tyre_set_index: int | None = None
    pit_lap: bool = False
    race_control_compromised: bool = False
    damage_compromised: bool = False
    tyre_set_changed: bool = False

@dataclass(slots=True)
class RaceState:
    session: SessionState = dc_field(default_factory=SessionState)
    player_index: int | None = None
    secondary_player_index: int | None = None
    player: CarState | None = None
    field: dict[int, CarState] = dc_field(default_factory=dict)
    active_car_count: int | None = None
    ahead_index: int | None = None
    behind_index: int | None = None
    gap_behind_s: float | None = None
    updated: dict[str, Freshness] = dc_field(default_factory=dict)
    events: tuple[RaceEvent, ...] = ()
    measured_laps: tuple[MeasuredLapFact, ...] = ()
    extended: dict[str, object] = dc_field(default_factory=dict)
