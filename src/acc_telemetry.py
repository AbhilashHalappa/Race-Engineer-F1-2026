"""ACC Shared Memory telemetry reader for Wheel Companion Ultra Lite."""
from __future__ import annotations

import ctypes
import math
import os
import struct
import threading
import time

from .hardware_companion.models import LiveTelemetry, WheelTelemetrySnapshot
from .acc_shared_memory_extended import (
    PHYSICS_SIZE, GRAPHICS_SIZE, STATIC_SIZE,
    decode_physics_extended, decode_graphics_extended, decode_static_extended,
)


PHYSICS_MAP = r"Local\acpmf_physics"
GRAPHICS_MAP = r"Local\acpmf_graphics"
STATIC_MAP = r"Local\acpmf_static"

PHYSICS_PREFIX = struct.Struct("<ifffiiff")
GRAPHICS_PREFIX_SIZE = 272
STATIC_PREFIX_SIZE = 420
GRAPHICS_STATUS_OFFSET = 4
GRAPHICS_COMPLETED_LAPS_OFFSET = 132
GRAPHICS_POSITION_OFFSET = 136
GRAPHICS_FLAG_OFFSET = 268
STATIC_MAX_RPM_OFFSET = 412
STATIC_MAX_FUEL_OFFSET = 416


def decode_physics_prefix(data: bytes) -> dict:
    """Decode the initial ACC physics fields."""
    if len(data) < PHYSICS_PREFIX.size:
        raise ValueError("ACC physics page is too short")
    packet_id, gas, brake, fuel, gear, rpm, steer, speed = PHYSICS_PREFIX.unpack_from(data)
    if not all(math.isfinite(v) for v in (gas, brake, fuel, steer, speed)):
        raise ValueError("ACC telemetry contains non-finite values")
    return {
        "packet_id": int(packet_id),
        "throttle": max(0.0, min(1.0, gas)),
        "brake": max(0.0, min(1.0, brake)),
        "fuel_l": max(0.0, fuel),
        "gear": max(-1, min(15, int(gear) - 1)),
        "rpm": max(0, int(rpm)),
        "steering_angle": float(steer),
        "speed_kph": round(max(0.0, float(speed)), 1),
    }


def decode_graphics_prefix(data: bytes) -> dict:
    """Decode position, completed laps, session status and flag."""
    if len(data) < GRAPHICS_PREFIX_SIZE:
        raise ValueError("ACC graphics page is too short")
    status = struct.unpack_from("<i", data, GRAPHICS_STATUS_OFFSET)[0]
    completed_laps = struct.unpack_from("<i", data, GRAPHICS_COMPLETED_LAPS_OFFSET)[0]
    position = struct.unpack_from("<i", data, GRAPHICS_POSITION_OFFSET)[0]
    flag = struct.unpack_from("<i", data, GRAPHICS_FLAG_OFFSET)[0]
    return {
        "status": int(status),
        "completed_laps": max(0, int(completed_laps)),
        "position": max(0, int(position)),
        "flag_status": max(0, min(8, int(flag))),
    }


def decode_static_prefix(data: bytes) -> dict:
    """Decode the car's maximum RPM and fuel tank capacity."""
    if len(data) < STATIC_PREFIX_SIZE:
        raise ValueError("ACC static page is too short")
    max_rpm = struct.unpack_from("<i", data, STATIC_MAX_RPM_OFFSET)[0]
    max_fuel = struct.unpack_from("<f", data, STATIC_MAX_FUEL_OFFSET)[0]
    if not math.isfinite(max_fuel):
        max_fuel = 0.0
    return {"max_rpm": max(0, int(max_rpm)), "max_fuel_l": max(0.0, float(max_fuel))}


class _SharedMemory:
    """Read-only Windows named-memory mapping."""

    def __init__(self, name: str):
        if os.name != "nt":
            raise OSError("ACC Shared Memory requires Windows")
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.handle = None
        self.view = None
        self.kernel32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
        self.kernel32.OpenFileMappingW.restype = ctypes.c_void_p
        self.kernel32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
        self.kernel32.MapViewOfFile.restype = ctypes.c_void_p
        self.kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        self.kernel32.UnmapViewOfFile.restype = ctypes.c_int
        self.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel32.CloseHandle.restype = ctypes.c_int
        self.handle = self.kernel32.OpenFileMappingW(0x0004, 0, name)
        if not self.handle:
            error = ctypes.get_last_error()
            raise OSError(error, f"Cannot open {name}. Is ACC running?")
        self.view = self.kernel32.MapViewOfFile(self.handle, 0x0004, 0, 0, 0)
        if not self.view:
            error = ctypes.get_last_error()
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
            raise OSError(error, f"Cannot map {name}")

    def read(self, size: int) -> bytes:
        if not self.view:
            raise OSError("Shared-memory view is closed")
        return ctypes.string_at(self.view, size)

    def close(self) -> None:
        if self.view:
            self.kernel32.UnmapViewOfFile(self.view)
            self.view = None
        if self.handle:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None


class ACCSharedMemoryReader:
    """ACC telemetry provider with the existing snapshots() interface."""

    def __init__(self, *, on_snapshot=None, poll_hz: float = 60.0):
        self.on_snapshot = on_snapshot
        self.poll_interval = 1.0 / max(10.0, min(240.0, poll_hz))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._mapping = None
        self._graphics_mapping = None
        self._static_mapping = None
        self._next_graphics_retry = 0.0
        self._next_static_retry = 0.0
        self._last_packet_id = None
        self._last_update = None
        self._last_error = None
        self._live = LiveTelemetry(source="ACC Shared Memory")
        self._wheel = WheelTelemetrySnapshot()
        self._graphics = None
        self._static = None

    @property
    def last_error(self):
        with self._lock:
            return self._last_error

    def snapshots(self):
        with self._lock:
            return self._live, self._wheel

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ACCSharedMemoryReader", daemon=True)
        self._thread.start()

    def close(self, *, wait=True):
        self._stop.set()
        if wait and self._thread:
            self._thread.join(timeout=2.0)
        self._close_all_mappings()
        with self._lock:
            self._live = LiveTelemetry(source="ACC Shared Memory")
            self._wheel = WheelTelemetrySnapshot()
            self._last_error = None
        self._last_packet_id = None
        self._last_update = None
        self._graphics = None
        self._static = None

    def _close_all_mappings(self):
        for attr in ("_mapping", "_graphics_mapping", "_static_mapping"):
            mapping = getattr(self, attr)
            if mapping:
                try:
                    mapping.close()
                except Exception:
                    pass
                setattr(self, attr, None)

    def _read_optional_page(self, *, mapping_attr, map_name, size, decoder, now, retry_attr):
        mapping = getattr(self, mapping_attr)
        if mapping is None:
            if now < getattr(self, retry_attr):
                return None
            setattr(self, retry_attr, now + 1.0)
            try:
                mapping = _SharedMemory(map_name)
                setattr(self, mapping_attr, mapping)
            except OSError:
                return None
        try:
            return decoder(mapping.read(size))
        except (OSError, ValueError, struct.error):
            try:
                mapping.close()
            except Exception:
                pass
            setattr(self, mapping_attr, None)
            setattr(self, retry_attr, now + 1.0)
            return None

    def _run(self):
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                if self._mapping is None:
                    self._mapping = _SharedMemory(PHYSICS_MAP)
                values = decode_physics_extended(self._mapping.read(PHYSICS_SIZE))
                now = time.monotonic()
                self._graphics = self._read_optional_page(
                    mapping_attr="_graphics_mapping", map_name=GRAPHICS_MAP,
                    size=GRAPHICS_SIZE, decoder=decode_graphics_extended,
                    now=now, retry_attr="_next_graphics_retry",
                ) or self._graphics
                self._static = self._read_optional_page(
                    mapping_attr="_static_mapping", map_name=STATIC_MAP,
                    size=STATIC_SIZE, decoder=decode_static_extended,
                    now=now, retry_attr="_next_static_retry",
                ) or self._static
                if values["packet_id"] != self._last_packet_id:
                    previous = self._last_update
                    self._last_packet_id = values["packet_id"]
                    self._last_update = now
                    self._publish(values, now, previous, self._graphics, self._static)
                with self._lock:
                    self._last_error = None
            except (OSError, ValueError, struct.error) as exc:
                self._close_all_mappings()
                self._last_packet_id = None
                self._graphics = None
                self._static = None
                with self._lock:
                    old_total = self._live.total_packets
                    old_invalid = self._live.invalid_packets
                    self._last_error = str(exc)
                    self._live = LiveTelemetry(source="ACC Shared Memory", total_packets=old_total, invalid_packets=old_invalid)
                    self._wheel = WheelTelemetrySnapshot()
            remaining = self.poll_interval - (time.monotonic() - started)
            self._stop.wait(max(0.001, remaining))

    def _publish(self, v, now, previous, graphics, static):
        speed = max(0, min(65535, int(round(v["speed_kph"]))))
        rpm = v["rpm"]
        gear = max(-1, min(15, int(v["gear_raw"]) - 1))
        max_rpm = static["max_rpm"] if static else 0
        rpm_percent = max(0, min(100, int(round(rpm * 100.0 / max_rpm)))) if max_rpm > 0 else 0
        max_fuel = static["max_fuel_l"] if static else 0.0
        fuel_l = max(0.0, float(v["fuel_l"] or 0.0))
        fuel_percent = round(max(0.0, min(100.0, fuel_l * 100.0 / max_fuel)), 1) if max_fuel > 0 else None
        if graphics:
            position = graphics["position"]
            completed_laps = graphics["completed_laps"]
            flag_status = graphics["flag"]
            lap_number = completed_laps + 1 if graphics["status"] == 2 else completed_laps
        else:
            position = 0
            lap_number = 0
            flag_status = 0
        steering_percent = int(round(max(-1.0, min(1.0, v["steering"])) * 100.0))
        shift_light = int(rpm_percent >= 95) if max_rpm > 0 else 0
        wheel = WheelTelemetrySnapshot(
            speed=speed, gear=gear, position=position, rpm_percent=rpm_percent,
            shift_light=shift_light, flag_status=flag_status, ers_mode=0, status_bits=0,
        )
        rate = 1.0 / max(0.001, now - previous) if previous is not None else 0.0
        throttle = int(round(v["throttle"] * 100))
        brake = int(round(v["brake"] * 100))
        with self._lock:
            live = LiveTelemetry(
                udp_connected=True,
                source="ACC Shared Memory",
                packets_per_second=rate,
                total_packets=self._live.total_packets + 1,
                invalid_packets=self._live.invalid_packets,
                speed_kph=speed,
                gear=gear,
                engine_rpm=rpm,
                rpm_percent=rpm_percent,
                throttle_percent=throttle,
                brake_percent=brake,
                steering_percent=steering_percent,
                drs_active=False,
                drs_available=False,
                position=position,
                lap_number=lap_number,
                fuel_percent=fuel_percent,
                fuel_l=fuel_l,
                ers_percent=None,
                ers_mode=0,
                flag_status=flag_status,
                session_uid=0,
                game_year=0,
                last_packet_monotonic=now,
                clutch_percent=int(round(max(0.0, min(1.0, v["clutch"] or 0.0)) * 100)),
                current_lap_time_ms=(graphics.get("current_time_ms") if graphics else None),
                session_time_left_s=(graphics.get("session_time_left_s") if graphics else None),
                session_type=(graphics.get("session") if graphics else None),
                sector=(graphics.get("sector") if graphics else None),
                lap_valid=(graphics.get("is_valid_lap") if graphics else None),
                normalized_car_position=(graphics.get("normalized_car_position") if graphics else None),
                tyre_compound=(graphics.get("tyre_compound", "") if graphics else ""),
                tyre_pressures_psi=v.get("tyre_pressure_psi"),
                tyre_core_temperatures_c=v.get("tyre_core_temp_c"),
                tyre_dirty_level=v.get("tyre_dirty"),
                wheel_slip=v.get("wheel_slip"),
                wheel_load=v.get("wheel_load"),
                wheel_angular_speed=v.get("wheel_angular_speed"),
                suspension_travel=v.get("suspension_travel"),
                brake_temperatures_c=v.get("brake_temp_c"),
                brake_pressures=v.get("brake_pressure"),
                brake_pad_life=v.get("pad_life"),
                brake_disc_life=v.get("disc_life"),
                car_damage=v.get("car_damage"),
                air_temperature_c=v.get("air_temp_c"),
                track_temperature_c=v.get("road_temp_c"),
                water_temperature_c=v.get("water_temp_c"),
                turbo_boost=v.get("turbo_boost"),
                brake_bias=v.get("brake_bias"),
                tc_level=(graphics.get("tc_level") if graphics else None),
                tc_cut=(graphics.get("tc_cut") if graphics else None),
                abs_level=(graphics.get("abs_level") if graphics else None),
                engine_map=(graphics.get("engine_map") if graphics else None),
                pit_limiter_on=v.get("pit_limiter_on"),
                penalty_time_s=(graphics.get("penalty_time_s") if graphics else None),
                penalty_type=(graphics.get("penalty") if graphics else None),
                fuel_per_lap=(graphics.get("fuel_per_lap") if graphics else None),
                fuel_estimated_laps=(graphics.get("fuel_estimated_laps") if graphics else None),
                used_fuel_l=(graphics.get("used_fuel_l") if graphics else None),
                track_status=(graphics.get("track_status", "") if graphics else ""),
                track_grip_status=(graphics.get("track_grip_status") if graphics else None),
                rain_intensity=(graphics.get("rain_intensity") if graphics else None),
                rain_intensity_10min=(graphics.get("rain_10min") if graphics else None),
                rain_intensity_30min=(graphics.get("rain_30min") if graphics else None),
                rain_tyres=(graphics.get("rain_tyres") if graphics else None),
                wind_speed_mps=(graphics.get("wind_speed") if graphics else None),
                wind_direction_rad=(graphics.get("wind_direction") if graphics else None),
                mandatory_pit_done=(graphics.get("mandatory_pit_done") if graphics else None),
                missing_mandatory_pits=(graphics.get("missing_mandatory_pits") if graphics else None),
                driver_stint_left_ms=(graphics.get("driver_stint_left_ms") if graphics else None),
                driver_stint_total_ms=(graphics.get("driver_stint_total_ms") if graphics else None),
                gap_ahead_ms=(graphics.get("gap_ahead_ms") if graphics else None),
                gap_behind_ms=(graphics.get("gap_behind_ms") if graphics else None),
                fuel_to_add_l=(graphics.get("mfd_fuel_to_add") if graphics else None),
                current_tyre_set=(graphics.get("current_tyre_set") if graphics else None),
                strategy_tyre_set=(graphics.get("strategy_tyre_set") if graphics else None),
                exhaust_temperature_c=(graphics.get("exhaust_temp_c") if graphics else None),
                engine_running=v.get("engine_running"),
                ignition_on=v.get("ignition_on"),
                is_ai_controlled=v.get("is_ai_controlled"),
                g_force=v.get("acc_g"),
                local_velocity=v.get("local_velocity"),
                local_angular_velocity=v.get("local_angular_velocity"),
                car=(static.get("car_model", "") if static else ""),
                track=(static.get("track", "") if static else ""),
            )
            self._live = live
            self._wheel = wheel
        if self.on_snapshot:
            try:
                self.on_snapshot(wheel)
            except Exception:
                pass
