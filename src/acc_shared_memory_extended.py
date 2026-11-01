"""ACC Shared Memory v1.8.12 decoders.

Layouts are transcribed from the ACC shared-memory specification (pack=4).
Fields marked unused by ACC are retained for offset correctness but are not
presented as live telemetry. Wheel order is FL, FR, RL, RR.
"""
from __future__ import annotations

import ctypes
import math


class _Physics(ctypes.LittleEndianStructure):
    _pack_ = 4
    _fields_ = [
        ("packet_id", ctypes.c_int32), ("throttle", ctypes.c_float),
        ("brake", ctypes.c_float), ("fuel_kg", ctypes.c_float),
        ("gear_raw", ctypes.c_int32), ("rpm", ctypes.c_int32),
        ("steering", ctypes.c_float), ("speed_kph", ctypes.c_float),
        ("velocity", ctypes.c_float * 3), ("acc_g", ctypes.c_float * 3),
        ("wheel_slip", ctypes.c_float * 4), ("wheel_load", ctypes.c_float * 4),
        ("tyre_pressure_psi", ctypes.c_float * 4), ("wheel_angular_speed", ctypes.c_float * 4),
        ("tyre_wear_unused", ctypes.c_float * 4), ("tyre_dirty", ctypes.c_float * 4),
        ("tyre_core_temp_c", ctypes.c_float * 4), ("camber_unused", ctypes.c_float * 4),
        ("suspension_travel", ctypes.c_float * 4), ("drs_unused", ctypes.c_float),
        ("tc", ctypes.c_float), ("heading", ctypes.c_float), ("pitch", ctypes.c_float),
        ("roll", ctypes.c_float), ("cg_height_unused", ctypes.c_float),
        ("car_damage", ctypes.c_float * 5), ("tyres_out_unused", ctypes.c_int32),
        ("pit_limiter_on", ctypes.c_int32), ("abs", ctypes.c_float),
        ("kers_charge_unused", ctypes.c_float), ("kers_input_unused", ctypes.c_float),
        ("autoshifter_on", ctypes.c_int32), ("ride_height_unused", ctypes.c_float * 2),
        ("turbo_boost", ctypes.c_float), ("ballast_unused", ctypes.c_float),
        ("air_density_unused", ctypes.c_float), ("air_temp_c", ctypes.c_float),
        ("road_temp_c", ctypes.c_float), ("local_angular_velocity", ctypes.c_float * 3),
        ("final_ff", ctypes.c_float), ("performance_meter_unused", ctypes.c_float),
        ("engine_brake_unused", ctypes.c_int32), ("ers_recovery_unused", ctypes.c_int32),
        ("ers_power_unused", ctypes.c_int32), ("ers_heat_unused", ctypes.c_int32),
        ("ers_charging_unused", ctypes.c_int32), ("kers_current_unused", ctypes.c_float),
        ("drs_available_unused", ctypes.c_int32), ("drs_enabled_unused", ctypes.c_int32),
        ("brake_temp_c", ctypes.c_float * 4), ("clutch", ctypes.c_float),
        ("tyre_temp_i_unused", ctypes.c_float * 4), ("tyre_temp_m_unused", ctypes.c_float * 4),
        ("tyre_temp_o_unused", ctypes.c_float * 4), ("is_ai_controlled", ctypes.c_int32),
        ("tyre_contact_point", ctypes.c_float * 12), ("tyre_contact_normal", ctypes.c_float * 12),
        ("tyre_contact_heading", ctypes.c_float * 12), ("brake_bias", ctypes.c_float),
        ("local_velocity", ctypes.c_float * 3), ("p2p_activation_unused", ctypes.c_int32),
        ("p2p_status_unused", ctypes.c_int32), ("current_max_rpm_unused", ctypes.c_float),
        ("fx_unused", ctypes.c_float * 4), ("fy_unused", ctypes.c_float * 4),
        ("slip_ratio", ctypes.c_float * 4), ("slip_angle", ctypes.c_float * 4),
        ("tc_in_action_unused", ctypes.c_int32), ("abs_in_action_unused", ctypes.c_int32),
        ("suspension_damage_unused", ctypes.c_float * 4), ("tyre_temp_unused", ctypes.c_float * 4),
        ("water_temp_c", ctypes.c_float), ("brake_pressure", ctypes.c_float * 4),
        ("front_brake_compound", ctypes.c_int32), ("rear_brake_compound", ctypes.c_int32),
        ("pad_life", ctypes.c_float * 4), ("disc_life", ctypes.c_float * 4),
        ("ignition_on", ctypes.c_int32), ("starter_engine_on", ctypes.c_int32),
        ("engine_running", ctypes.c_int32), ("kerb_vibration", ctypes.c_float),
        ("slip_vibration", ctypes.c_float), ("g_vibration", ctypes.c_float),
        ("abs_vibration", ctypes.c_float),
    ]


class _Graphics(ctypes.LittleEndianStructure):
    _pack_ = 4
    _fields_ = [
        ("packet_id", ctypes.c_int32), ("status", ctypes.c_int32),
        ("session", ctypes.c_int32), ("current_time", ctypes.c_uint16 * 15),
        ("last_time", ctypes.c_uint16 * 15), ("best_time", ctypes.c_uint16 * 15),
        ("split", ctypes.c_uint16 * 15), ("completed_laps", ctypes.c_int32),
        ("position", ctypes.c_int32), ("current_time_ms", ctypes.c_int32),
        ("last_time_ms", ctypes.c_int32), ("best_time_ms", ctypes.c_int32),
        ("session_time_left_s", ctypes.c_float), ("distance_traveled_m", ctypes.c_float),
        ("is_in_pit", ctypes.c_int32), ("sector", ctypes.c_int32),
        ("last_sector_time_ms", ctypes.c_int32), ("number_of_laps", ctypes.c_int32),
        ("tyre_compound", ctypes.c_uint16 * 33), ("replay_multiplier_unused", ctypes.c_float),
        ("normalized_car_position", ctypes.c_float), ("active_cars", ctypes.c_int32),
        ("car_coordinates", ctypes.c_float * 180), ("car_ids", ctypes.c_int32 * 60),
        ("player_car_id", ctypes.c_int32), ("penalty_time_s", ctypes.c_float),
        ("flag", ctypes.c_int32), ("penalty", ctypes.c_int32),
        ("ideal_line_on", ctypes.c_int32), ("is_in_pit_lane", ctypes.c_int32),
        ("surface_grip", ctypes.c_float), ("mandatory_pit_done", ctypes.c_int32),
        ("wind_speed", ctypes.c_float), ("wind_direction", ctypes.c_float),
        ("setup_menu_visible", ctypes.c_int32), ("main_display_index", ctypes.c_int32),
        ("secondary_display_index", ctypes.c_int32), ("tc_level", ctypes.c_int32),
        ("tc_cut", ctypes.c_int32), ("engine_map", ctypes.c_int32), ("abs_level", ctypes.c_int32),
        ("fuel_per_lap", ctypes.c_float), ("rain_lights", ctypes.c_int32),
        ("flashing_lights", ctypes.c_int32), ("lights_stage", ctypes.c_int32),
        ("exhaust_temp_c", ctypes.c_float), ("wiper_level", ctypes.c_int32),
        ("driver_stint_total_ms", ctypes.c_int32), ("driver_stint_left_ms", ctypes.c_int32),
        ("rain_tyres", ctypes.c_int32), ("session_index", ctypes.c_int32),
        ("used_fuel_l", ctypes.c_float), ("delta_lap_time", ctypes.c_uint16 * 15),
        ("delta_lap_time_ms", ctypes.c_int32), ("estimated_lap_time", ctypes.c_uint16 * 15),
        ("estimated_lap_time_ms", ctypes.c_int32), ("delta_positive", ctypes.c_int32),
        ("split_ms", ctypes.c_int32), ("is_valid_lap", ctypes.c_int32),
        ("fuel_estimated_laps", ctypes.c_float), ("track_status", ctypes.c_uint16 * 33),
        ("missing_mandatory_pits", ctypes.c_int32), ("clock_s", ctypes.c_float),
        ("direction_left", ctypes.c_int32), ("direction_right", ctypes.c_int32),
        ("global_yellow", ctypes.c_int32), ("global_yellow_1", ctypes.c_int32),
        ("global_yellow_2", ctypes.c_int32), ("global_yellow_3", ctypes.c_int32),
        ("global_white", ctypes.c_int32), ("global_green", ctypes.c_int32),
        ("global_chequered", ctypes.c_int32), ("global_red", ctypes.c_int32),
        ("mfd_tyre_set", ctypes.c_int32), ("mfd_fuel_to_add", ctypes.c_float),
        ("mfd_pressure_fl", ctypes.c_float), ("mfd_pressure_fr", ctypes.c_float),
        ("mfd_pressure_rl", ctypes.c_float), ("mfd_pressure_rr", ctypes.c_float),
        ("track_grip_status", ctypes.c_int32), ("rain_intensity", ctypes.c_int32),
        ("rain_10min", ctypes.c_int32), ("rain_30min", ctypes.c_int32),
        ("current_tyre_set", ctypes.c_int32), ("strategy_tyre_set", ctypes.c_int32),
        ("gap_ahead_ms", ctypes.c_int32), ("gap_behind_ms", ctypes.c_int32),
    ]


class _Static(ctypes.LittleEndianStructure):
    _pack_ = 4
    _fields_ = [
        ("sm_version", ctypes.c_uint16 * 15), ("ac_version", ctypes.c_uint16 * 15),
        ("number_of_sessions", ctypes.c_int32), ("num_cars", ctypes.c_int32),
        ("car_model", ctypes.c_uint16 * 33), ("track", ctypes.c_uint16 * 33),
        ("player_name", ctypes.c_uint16 * 33), ("player_surname", ctypes.c_uint16 * 33),
        ("player_nickname", ctypes.c_uint16 * 33), ("sector_count", ctypes.c_int32),
        ("max_torque_unused", ctypes.c_float), ("max_power_unused", ctypes.c_float),
        ("max_rpm", ctypes.c_int32), ("max_fuel_kg", ctypes.c_float),
        ("suspension_max_travel_unused", ctypes.c_float * 4),
        ("tyre_radius_unused", ctypes.c_float * 4), ("max_turbo_unused", ctypes.c_float),
        ("deprecated_1", ctypes.c_float), ("deprecated_2", ctypes.c_float),
        ("penalties_enabled", ctypes.c_int32), ("aid_fuel_rate", ctypes.c_float),
        ("aid_tyre_rate", ctypes.c_float), ("aid_mechanical_damage", ctypes.c_float),
        ("tyre_blankets", ctypes.c_float), ("aid_stability", ctypes.c_float),
        ("aid_autoclutch", ctypes.c_int32), ("aid_autoblip", ctypes.c_int32),
        ("has_drs_unused", ctypes.c_int32), ("has_ers_unused", ctypes.c_int32),
        ("has_kers_unused", ctypes.c_int32), ("kers_max_unused", ctypes.c_float),
        ("engine_brake_count_unused", ctypes.c_int32), ("ers_power_count_unused", ctypes.c_int32),
        ("track_spline_length_unused", ctypes.c_float), ("track_configuration_unused", ctypes.c_uint16 * 33),
        ("ers_max_unused", ctypes.c_float), ("timed_race_unused", ctypes.c_int32),
        ("extra_lap_unused", ctypes.c_int32), ("car_skin_unused", ctypes.c_uint16 * 33),
        ("reversed_grid_unused", ctypes.c_int32), ("pit_window_start", ctypes.c_int32),
        ("pit_window_end", ctypes.c_int32), ("is_online", ctypes.c_int32),
        ("dry_tyres_name", ctypes.c_uint16 * 33), ("wet_tyres_name", ctypes.c_uint16 * 33),
    ]


PHYSICS_SIZE = ctypes.sizeof(_Physics)
GRAPHICS_SIZE = ctypes.sizeof(_Graphics)
STATIC_SIZE = ctypes.sizeof(_Static)


def _finite(v):
    v = float(v)
    return v if math.isfinite(v) else None


def _array(values):
    return tuple(_finite(v) for v in values)


def _positive_array(values):
    return tuple(
        (value if value is not None and value > 0 else None)
        for value in (_finite(v) for v in values)
    )


def _matrix4x3(values):
    flat = tuple(values)
    return tuple(tuple(_finite(flat[i * 3 + j]) for j in range(3)) for i in range(4))


def _wide(values):
    raw = bytes().join(int(v).to_bytes(2, "little") for v in values)
    return raw.decode("utf-16-le", errors="ignore").split("\x00", 1)[0].strip()


def decode_physics_extended(data: bytes) -> dict:
    if len(data) < PHYSICS_SIZE:
        raise ValueError(f"ACC physics page too short: {len(data)} < {PHYSICS_SIZE}")
    p = _Physics.from_buffer_copy(data[:PHYSICS_SIZE])
    return {
        "packet_id": int(p.packet_id), "throttle": _finite(p.throttle),
        "brake": _finite(p.brake), "fuel_kg": _finite(p.fuel_kg),
        "gear_raw": int(p.gear_raw), "rpm": int(p.rpm),
        "steering": _finite(p.steering), "speed_kph": _finite(p.speed_kph),
        "velocity": _array(p.velocity), "acc_g": _array(p.acc_g),
        "heading": _finite(p.heading), "pitch": _finite(p.pitch), "roll": _finite(p.roll),
        "final_ff": _finite(p.final_ff), "autoshifter_on": bool(p.autoshifter_on),
        "tyre_contact_point": _matrix4x3(p.tyre_contact_point),
        "tyre_contact_normal": _matrix4x3(p.tyre_contact_normal),
        "tyre_contact_heading": _matrix4x3(p.tyre_contact_heading),
        "wheel_slip": _array(p.wheel_slip), "wheel_load": None,  # ACC marks wheelLoad as unused
        "tyre_pressure_psi": _positive_array(p.tyre_pressure_psi),
        "wheel_angular_speed": _array(p.wheel_angular_speed),
        "tyre_dirty": None,  # ACC marks tyreDirtyLevel as unused
        "tyre_core_temp_c": _positive_array(p.tyre_core_temp_c),
        "suspension_travel": _array(p.suspension_travel), "tc": _finite(p.tc),
        "car_damage": _array(p.car_damage), "pit_limiter_on": bool(p.pit_limiter_on),
        "abs": _finite(p.abs), "turbo_boost": _finite(p.turbo_boost),
        "air_temp_c": _finite(p.air_temp_c), "road_temp_c": _finite(p.road_temp_c),
        "local_angular_velocity": _array(p.local_angular_velocity),
        "brake_temp_c": _positive_array(p.brake_temp_c), "clutch": _finite(p.clutch),
        "is_ai_controlled": bool(p.is_ai_controlled), "brake_bias": _finite(p.brake_bias),
        "local_velocity": _array(p.local_velocity), "slip_ratio": _array(p.slip_ratio),
        "slip_angle": _array(p.slip_angle), "water_temp_c": _finite(p.water_temp_c),
        "brake_pressure": _array(p.brake_pressure), "front_brake_compound": int(p.front_brake_compound),
        "rear_brake_compound": int(p.rear_brake_compound), "pad_life": _array(p.pad_life),
        "disc_life": _array(p.disc_life), "ignition_on": bool(p.ignition_on),
        "starter_engine_on": bool(p.starter_engine_on), "engine_running": bool(p.engine_running),
        "kerb_vibration": _finite(p.kerb_vibration), "slip_vibration": _finite(p.slip_vibration),
        "g_vibration": _finite(p.g_vibration), "abs_vibration": _finite(p.abs_vibration),
    }


def decode_graphics_extended(data: bytes) -> dict:
    if len(data) < GRAPHICS_SIZE:
        raise ValueError(f"ACC graphics page too short: {len(data)} < {GRAPHICS_SIZE}")
    g = _Graphics.from_buffer_copy(data[:GRAPHICS_SIZE])
    coords = tuple(
        tuple(_finite(g.car_coordinates[i * 3 + axis]) for axis in range(3))
        for i in range(max(0, min(60, int(g.active_cars))))
    )
    ids = tuple(int(g.car_ids[i]) for i in range(max(0, min(60, int(g.active_cars)))))
    player_position = None
    if int(g.player_car_id) in ids:
        player_position = coords[ids.index(int(g.player_car_id))]
    return {
        "packet_id": int(g.packet_id), "status": int(g.status), "session": int(g.session),
        "current_time_str": _wide(g.current_time), "last_time_str": _wide(g.last_time),
        "best_time_str": _wide(g.best_time), "split_time_str": _wide(g.split),
        "current_time_ms": int(g.current_time_ms), "last_time_ms": int(g.last_time_ms),
        "best_time_ms": int(g.best_time_ms), "session_time_left_s": _finite(g.session_time_left_s),
        "distance_traveled_m": _finite(g.distance_traveled_m), "completed_laps": int(g.completed_laps),
        "position": int(g.position), "is_in_pit": bool(g.is_in_pit),
        "sector": int(g.sector), "last_sector_time_ms": int(g.last_sector_time_ms),
        "number_of_laps": int(g.number_of_laps), "tyre_compound": _wide(g.tyre_compound),
        "normalized_car_position": _finite(g.normalized_car_position),
        "active_cars": int(g.active_cars), "player_car_id": int(g.player_car_id),
        "car_ids": ids, "car_coordinates": coords, "player_world_position": player_position,
        "penalty_time_s": _finite(g.penalty_time_s), "flag": int(g.flag),
        "penalty": int(g.penalty), "ideal_line_on": bool(g.ideal_line_on),
        "is_in_pit_lane": bool(g.is_in_pit_lane),
        "surface_grip": _finite(g.surface_grip), "mandatory_pit_done": bool(g.mandatory_pit_done),
        "wind_speed": _finite(g.wind_speed), "wind_direction": _finite(g.wind_direction),
        "setup_menu_visible": bool(g.setup_menu_visible),
        "main_display_index": int(g.main_display_index),
        "secondary_display_index": int(g.secondary_display_index),
        "tc_level": int(g.tc_level), "tc_cut": int(g.tc_cut), "engine_map": int(g.engine_map),
        "abs_level": int(g.abs_level), "fuel_per_lap": _finite(g.fuel_per_lap),
        "rain_lights": bool(g.rain_lights), "flashing_lights": bool(g.flashing_lights),
        "lights_stage": int(g.lights_stage), "exhaust_temp_c": _finite(g.exhaust_temp_c),
        "wiper_level": int(g.wiper_level), "driver_stint_total_ms": int(g.driver_stint_total_ms),
        "driver_stint_left_ms": int(g.driver_stint_left_ms), "rain_tyres": bool(g.rain_tyres),
        "session_index": int(g.session_index), "used_fuel_l": _finite(g.used_fuel_l),
        "delta_lap_time_ms": int(g.delta_lap_time_ms), "estimated_lap_time_ms": int(g.estimated_lap_time_ms),
        "is_valid_lap": bool(g.is_valid_lap), "fuel_estimated_laps": _finite(g.fuel_estimated_laps),
        "track_status": _wide(g.track_status), "missing_mandatory_pits": int(g.missing_mandatory_pits),
        "clock_s": _finite(g.clock_s), "global_yellow": bool(g.global_yellow),
        "global_yellow_1": bool(g.global_yellow_1), "global_yellow_2": bool(g.global_yellow_2),
        "global_yellow_3": bool(g.global_yellow_3), "global_white": bool(g.global_white),
        "global_green": bool(g.global_green), "global_chequered": bool(g.global_chequered),
        "global_red": bool(g.global_red), "rain_lights": bool(g.rain_lights),
        "flashing_lights": bool(g.flashing_lights), "lights_stage": int(g.lights_stage),
        "wiper_level": int(g.wiper_level), "surface_grip": _finite(g.surface_grip),
        "delta_lap_time_ms": int(g.delta_lap_time_ms),
        "estimated_lap_time_ms": int(g.estimated_lap_time_ms),
        "delta_positive": bool(g.delta_positive), "split_ms": int(g.split_ms),
        "session_index": int(g.session_index), "active_cars": int(g.active_cars),
        "player_car_id": int(g.player_car_id), "mfd_tyre_set": int(g.mfd_tyre_set),
        "mfd_fuel_to_add": _finite(g.mfd_fuel_to_add),
        "mfd_tyre_pressures": _positive_array((g.mfd_pressure_fl, g.mfd_pressure_fr, g.mfd_pressure_rl, g.mfd_pressure_rr)),
        "direction_left": bool(g.direction_left), "direction_right": bool(g.direction_right),
        "track_grip_status": int(g.track_grip_status), "rain_intensity": int(g.rain_intensity),
        "rain_10min": int(g.rain_10min), "rain_30min": int(g.rain_30min),
        "current_tyre_set": int(g.current_tyre_set), "strategy_tyre_set": int(g.strategy_tyre_set),
        "gap_ahead_ms": int(g.gap_ahead_ms), "gap_behind_ms": int(g.gap_behind_ms),
    }


def decode_static_extended(data: bytes) -> dict:
    if len(data) < STATIC_SIZE:
        raise ValueError(f"ACC static page too short: {len(data)} < {STATIC_SIZE}")
    s = _Static.from_buffer_copy(data[:STATIC_SIZE])
    return {
        "sm_version": _wide(s.sm_version), "ac_version": _wide(s.ac_version),
        "number_of_sessions": int(s.number_of_sessions), "num_cars": int(s.num_cars),
        "car_model": _wide(s.car_model), "track": _wide(s.track),
        "player_name": _wide(s.player_name), "player_surname": _wide(s.player_surname),
        "player_nickname": _wide(s.player_nickname), "sector_count": int(s.sector_count),
        "max_rpm": int(s.max_rpm), "max_fuel_kg": _finite(s.max_fuel_kg),
        "penalties_enabled": bool(s.penalties_enabled), "aid_fuel_rate": _finite(s.aid_fuel_rate),
        "aid_tyre_rate": _finite(s.aid_tyre_rate), "aid_mechanical_damage": _finite(s.aid_mechanical_damage),
        "tyre_blankets": bool(s.tyre_blankets), "aid_stability": _finite(s.aid_stability),
        "aid_autoclutch": bool(s.aid_autoclutch), "aid_autoblip": bool(s.aid_autoblip),
        "pit_window_start": int(s.pit_window_start), "pit_window_end": int(s.pit_window_end),
        "track_configuration": _wide(s.track_configuration_unused),
        "is_online": bool(s.is_online), "dry_tyres_name": _wide(s.dry_tyres_name),
        "wet_tyres_name": _wide(s.wet_tyres_name),
    }
