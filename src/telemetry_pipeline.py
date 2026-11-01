"""Game-neutral telemetry contract and active-source pipeline.

Game adapters normalize their native telemetry at the boundary. Consumers read
one immutable frame and never need to know whether it came from F1 UDP or ACC
Shared Memory. The existing F1 RaceState remains authoritative for F1-specific
rules and is deliberately not replaced by this transport contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Optional


@dataclass(frozen=True, slots=True)
class TelemetryFrame:
    game_id: str
    source: str
    received_at: float
    session_id: str = ""
    car: str = ""
    track: str = ""
    session_type: str = ""
    lap: int | None = None
    position: int | None = None
    speed_kph: float | None = None
    gear: int | None = None
    rpm: int | None = None
    throttle: float | None = None
    brake: float | None = None
    steering: float | None = None
    fuel_l: float | None = None
    fuel_remaining_laps: float | None = None
    current_lap_time_s: float | None = None
    last_lap_time_s: float | None = None
    best_lap_time_s: float | None = None
    in_pit: bool | None = None
    in_pit_lane: bool | None = None
    flag: str | int | None = None
    tyre_pressures: tuple | None = None
    tyre_temperatures: tuple | None = None
    tyre_wear: tuple | None = None
    extras: tuple = ()


class TelemetryPipeline:
    """Single active-game telemetry path with source isolation."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_game = "f1_26"
        self._latest: TelemetryFrame | None = None
        self._sequence = 0
        self._listeners = []

    @property
    def active_game(self) -> str:
        with self._lock:
            return self._active_game

    @property
    def latest(self) -> TelemetryFrame | None:
        with self._lock:
            return self._latest

    @property
    def sequence(self) -> int:
        with self._lock:
            return self._sequence

    def select_game(self, game_id: str) -> None:
        game_id = str(game_id or "").strip().lower()
        if game_id not in {"f1_26", "acc"}:
            raise ValueError(f"Unsupported telemetry game: {game_id}")
        with self._lock:
            if game_id != self._active_game:
                self._active_game = game_id
                self._latest = None

    def subscribe(self, callback) -> None:
        if not callable(callback):
            raise TypeError("Telemetry listener must be callable")
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def unsubscribe(self, callback) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def publish(self, frame: TelemetryFrame) -> bool:
        if not isinstance(frame, TelemetryFrame):
            raise TypeError("publish expects a TelemetryFrame")
        with self._lock:
            if frame.game_id != self._active_game:
                return False
            self._latest = frame
            self._sequence += 1
            listeners = tuple(self._listeners)
        for listener in listeners:
            try:
                listener(frame)
            except Exception:
                # A consumer must never break telemetry ingestion.
                continue
        return True


def _enum_name(value) -> str:
    if value is None:
        return ""
    return str(getattr(value, "name", value))


def frame_from_acc(telemetry, *, now: float | None = None) -> TelemetryFrame:
    """Normalize the existing ACC LiveTelemetry snapshot."""
    stamp = now if now is not None else getattr(telemetry, "last_packet_monotonic", None)
    if stamp is None:
        stamp = time.monotonic()
    return TelemetryFrame(
        game_id="acc", source=str(getattr(telemetry, "source", "ACC Shared Memory")),
        received_at=float(stamp),
        car=str(getattr(telemetry, "car", "") or ""),
        track=str(getattr(telemetry, "track", "") or ""),
        session_type=_enum_name(getattr(telemetry, "session", None)),
        lap=_optional_int(getattr(telemetry, "lap_number", None)),
        position=_optional_int(getattr(telemetry, "position", None)),
        speed_kph=_optional_float(getattr(telemetry, "speed_kph", None)),
        gear=_optional_int(getattr(telemetry, "gear", None)),
        rpm=_optional_int(getattr(telemetry, "engine_rpm", None)),
        throttle=_percent_fraction(getattr(telemetry, "throttle_percent", None)),
        brake=_percent_fraction(getattr(telemetry, "brake_percent", None)),
        steering=_signed_percent_fraction(getattr(telemetry, "steering_percent", None)),
        fuel_l=_optional_float(getattr(telemetry, "fuel_l", None)),
        last_lap_time_s=_milliseconds_to_seconds(getattr(telemetry, "last_lap_time_ms", None)),
        best_lap_time_s=_milliseconds_to_seconds(getattr(telemetry, "best_lap_time_ms", None)),
        in_pit=bool(getattr(telemetry, "is_in_pit", False)),
        in_pit_lane=bool(getattr(telemetry, "is_in_pit_lane", False)),
        flag=_optional_int(getattr(telemetry, "flag_status", None)),
    )


def frame_from_f1(state, *, now: float | None = None) -> TelemetryFrame | None:
    """Normalize the F1 RaceState without changing its protected native model."""
    player = getattr(state, "player", None)
    if player is None:
        return None
    lap = player.lap
    car = player.telemetry
    fuel = player.fuel
    tyres = player.tyres
    session = state.session
    stamp = now if now is not None else time.monotonic()
    return TelemetryFrame(
        game_id="f1_26", source="F1 UDP", received_at=float(stamp),
        session_id=str(getattr(session, "uid", "") or ""),
        car=_enum_name(getattr(player.identity, "team", None)),
        track=_enum_name(getattr(session, "track", None)),
        session_type=_enum_name(getattr(session, "session_type", None)),
        lap=_optional_int(getattr(lap, "current_lap", None)),
        position=_optional_int(getattr(lap, "position", None)),
        speed_kph=_optional_float(getattr(car, "speed_kph", None)),
        gear=_optional_int(getattr(car, "gear", None)),
        rpm=_optional_int(getattr(car, "rpm", None)),
        throttle=_optional_float(getattr(car, "throttle", None)),
        brake=_optional_float(getattr(car, "brake", None)),
        steering=_optional_float(getattr(car, "steering", None)),
        # F1's fuel mass unit is unspecified; do not label it as litres.
        fuel_l=None,
        fuel_remaining_laps=_optional_float(getattr(fuel, "remaining_laps", None)),
        current_lap_time_s=_optional_float(getattr(lap, "current_lap_time_s", None)),
        last_lap_time_s=_optional_float(getattr(lap, "previous_lap_time_s", None)),
        in_pit=_enum_name(getattr(lap, "pit_status", None)) in {"Pitting", "In pit area"},
        tyre_pressures=_wheel_tuple(getattr(tyres, "pressure_psi", None)),
        tyre_temperatures=_wheel_tuple(getattr(tyres, "surface_temperature_c", None)),
        tyre_wear=_wheel_tuple(getattr(tyres, "wear_percent", None)),
        extras=(("fuel_mass_raw", _optional_float(getattr(fuel, "remaining_mass", None))),),
    )



def race_state_from_acc(telemetry, *, fuel_remaining_laps=None, session_uid=1):
    """Adapt ACC Shared Memory into the existing RaceState consumer contract.

    ACC-only measurements are also retained in RaceState.extended. Fields that
    ACC does not publish (for example tyre wear, F1 ERS/DRS and tyre surface
    temperature) remain unset rather than being inferred.
    """
    from .race_state.models import (
        CarState, CarTelemetry, DamageState, FuelState, Identity, LapState,
        RaceState, SessionState, TyreState, Wheels,
    )
    from .telemetry.enums import EnumValue

    def number(value, cast=float):
        try:
            result = cast(value)
            return result if result is not None else None
        except (TypeError, ValueError, OverflowError):
            return None

    def wheel(values):
        if not isinstance(values, (tuple, list)) or len(values) != 4:
            return None
        parsed = [number(v) for v in values]
        if all(v is None for v in parsed):
            return None
        return Wheels(*parsed)

    def enum(raw, names):
        value = number(raw, int)
        if value is None or value not in names:
            return None
        return EnumValue(value, names[value])

    def fraction_percent(value):
        result = number(value)
        if result is None:
            return None
        return max(0.0, min(1.0, result / 100.0))

    lap_number = number(getattr(telemetry, "lap_number", None), int)
    position = number(getattr(telemetry, "position", None), int)
    pit_lane = bool(getattr(telemetry, "is_in_pit_lane", False))
    in_pit = bool(getattr(telemetry, "is_in_pit", False))
    pit_status = EnumValue(1, "Pitting") if pit_lane else EnumValue(2, "In pit area") if in_pit else None

    session_type_names = {
        0: "Practice", 1: "Qualifying", 2: "Race", 3: "Hotlap",
        4: "Time attack", 5: "Drift", 6: "Drag", 7: "Hotstint",
        8: "Hotstint superpole",
    }
    rain_names = {0: "Dry", 1: "Drizzle", 2: "Light rain", 3: "Medium rain", 4: "Heavy rain", 5: "Thunderstorm"}
    grip_names = {0: "Green", 1: "Fast", 2: "Optimum", 3: "Greasy", 4: "Damp", 5: "Wet", 6: "Flooded"}

    session_type = enum(getattr(telemetry, "session_type", None), session_type_names)
    rain = enum(getattr(telemetry, "rain_intensity", None), rain_names)
    grip = enum(getattr(telemetry, "track_grip_status", None), grip_names)
    track_name = str(getattr(telemetry, "track", "") or "").strip()
    car_name = str(getattr(telemetry, "car", "") or "").strip()
    player_name = str(getattr(telemetry, "player_name", "") or "").strip()

    core_temps = wheel(getattr(telemetry, "tyre_core_temperatures_c", None))
    tyre_pressures = wheel(getattr(telemetry, "tyre_pressures_psi", None))
    brake_temps = wheel(getattr(telemetry, "brake_temperatures_c", None))
    brake_pressure = wheel(getattr(telemetry, "brake_pressures", None))
    fuel_laps = number(getattr(telemetry, "fuel_estimated_laps", None))
    if fuel_laps is None:
        fuel_laps = number(fuel_remaining_laps)

    session = SessionState(
        uid=int(session_uid),
        session_type=session_type,
        track=EnumValue(0, track_name) if track_name else None,
        track_temperature_c=number(getattr(telemetry, "track_temperature_c", None), int),
        air_temperature_c=number(getattr(telemetry, "air_temperature_c", None), int),
        time_left_s=number(getattr(telemetry, "session_time_left_s", None), int),
        total_laps=number(getattr(telemetry, "number_of_laps", None), int),
        session_time_s=None,
        weather=rain,
    )
    lap = LapState(
        position=position if position and position > 0 else None,
        current_lap=lap_number if lap_number and lap_number > 0 else None,
        current_lap_time_s=_milliseconds_to_seconds(getattr(telemetry, "current_lap_time_ms", None)),
        previous_lap_time_s=_milliseconds_to_seconds(getattr(telemetry, "last_lap_time_ms", None)),
        sector=number(getattr(telemetry, "sector", None), int),
        lap_valid=getattr(telemetry, "lap_valid", None),
        total_distance_m=None,
        pit_status=pit_status,
        penalties_s=number(getattr(telemetry, "penalty_time_s", None), int),
    )
    car = CarState(
        index=0,
        identity=Identity(name=player_name or None),
        lap=lap,
        telemetry=CarTelemetry(
            speed_kph=number(getattr(telemetry, "speed_kph", None), int),
            throttle=fraction_percent(getattr(telemetry, "throttle_percent", None)),
            brake=fraction_percent(getattr(telemetry, "brake_percent", None)),
            clutch_percent=number(getattr(telemetry, "clutch_percent", None), int),
            steering=_signed_percent_fraction(getattr(telemetry, "steering_percent", None)),
            gear=number(getattr(telemetry, "gear", None), int),
            rpm=number(getattr(telemetry, "engine_rpm", None), int),
            engine_temperature_c=number(getattr(telemetry, "water_temperature_c", None), int),
            brakes_temperature_c=brake_temps,
            brake_pressure=brake_pressure,
        ),
        fuel=FuelState(remaining_laps=fuel_laps),
        tyres=TyreState(
            actual_compound=EnumValue(0, str(getattr(telemetry, "tyre_compound", "") or "Unknown")),
            core_temperature_c=core_temps,
            pressure_psi=tyre_pressures,
        ),
        damage=DamageState(),
    )

    extended_fields = (
        "fuel_l", "fuel_percent", "clutch_percent", "tyre_compound",
        "tyre_pressures_psi", "tyre_core_temperatures_c", "tyre_dirty_level",
        "wheel_slip", "wheel_load", "wheel_angular_speed", "suspension_travel",
        "brake_temperatures_c", "brake_pressures", "brake_pad_life", "brake_disc_life",
        "car_damage", "air_temperature_c", "track_temperature_c", "water_temperature_c",
        "turbo_boost", "brake_bias", "tc_level", "tc_cut", "abs_level", "engine_map",
        "pit_limiter_on", "penalty_time_s", "penalty_type", "fuel_per_lap",
        "fuel_estimated_laps", "used_fuel_l", "track_status", "track_grip_status",
        "rain_intensity", "rain_intensity_10min", "rain_intensity_30min", "rain_tyres",
        "wind_speed_mps", "wind_direction_rad", "mandatory_pit_done",
        "missing_mandatory_pits", "driver_stint_left_ms", "driver_stint_total_ms",
        "gap_ahead_ms", "gap_behind_ms", "fuel_to_add_l", "current_tyre_set",
        "strategy_tyre_set", "exhaust_temperature_c", "engine_running", "ignition_on",
        "is_ai_controlled", "g_force", "local_velocity", "local_angular_velocity",
        "session_time_left_s", "normalized_car_position", "lap_valid", "sector",
        "current_lap_time_ms", "session_type", "number_of_laps", "position", "lap_number",
    )
    extended = {
        name: getattr(telemetry, name)
        for name in extended_fields
        if hasattr(telemetry, name) and getattr(telemetry, name) is not None
    }
    extended["game_id"] = "acc"
    extended["car_model"] = car_name
    extended["track"] = track_name
    extended["track_grip_name"] = grip.name if grip is not None else None
    extended["rain_name"] = rain.name if rain is not None else None

    return RaceState(
        session=session,
        player_index=0,
        player=car,
        extended=extended,
    )

def _optional_float(value) -> Optional[float]:
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _optional_int(value) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _percent_fraction(value) -> Optional[float]:
    result = _optional_float(value)
    return None if result is None else max(0.0, min(1.0, result / 100.0))


def _signed_percent_fraction(value) -> Optional[float]:
    result = _optional_float(value)
    return None if result is None else max(-1.0, min(1.0, result / 100.0))


def _milliseconds_to_seconds(value) -> Optional[float]:
    result = _optional_float(value)
    return None if result is None else result / 1000.0


def _wheel_tuple(wheels):
    if wheels is None:
        return None
    return tuple(getattr(wheels, name, None) for name in ("FL", "FR", "RL", "RR"))


telemetry_pipeline = TelemetryPipeline()
