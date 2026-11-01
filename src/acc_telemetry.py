
"""ACC Shared Memory telemetry reader for Wheel Companion Ultra Lite."""
from __future__ import annotations

import ctypes
import math
import os
import struct
import threading
import time

from .hardware_companion.models import LiveTelemetry, WheelTelemetrySnapshot


PHYSICS_MAP = r"Local\acpmf_physics"
GRAPHICS_MAP = r"Local\acpmf_graphics"
STATIC_MAP = r"Local\acpmf_static"

# Physics prefix:
# int packetId, float gas, float brake, float fuel,
# int gear, int rpms, float steerAngle, float speedKmh
PHYSICS_PREFIX = struct.Struct("<ifffiiff")

# ACC shared-memory structures use 4-byte packing on Windows.
# These are the minimum byte lengths needed for the fields we read.
GRAPHICS_PREFIX_SIZE = 272
STATIC_PREFIX_SIZE = 420

# Graphics-page byte offsets.
GRAPHICS_STATUS_OFFSET = 4
GRAPHICS_COMPLETED_LAPS_OFFSET = 132
GRAPHICS_POSITION_OFFSET = 136
GRAPHICS_FLAG_OFFSET = 268

# Static-page byte offsets. Windows wchar_t is 2 bytes.
STATIC_MAX_RPM_OFFSET = 412
STATIC_MAX_FUEL_OFFSET = 416

# ACC flag enum:
# 0 none, 1 blue, 2 yellow, 3 black, 4 white,
# 5 chequered, 6 penalty, 7 green, 8 orange.


def decode_physics_prefix(data: bytes) -> dict:
    """Decode the initial physics fields used by the existing ACC tests."""
    if len(data) < PHYSICS_PREFIX.size:
        raise ValueError("ACC physics page is too short")

    packet_id, gas, brake, fuel, gear, rpm, steer, speed = (
        PHYSICS_PREFIX.unpack_from(data)
    )

    if not all(
        math.isfinite(v) for v in (gas, brake, fuel, steer, speed)
    ):
        raise ValueError("ACC telemetry contains non-finite values")

    return {
        "packet_id": int(packet_id),
        "throttle": max(0.0, min(1.0, gas)),
        "brake": max(0.0, min(1.0, brake)),
        "fuel_l": max(0.0, fuel),
        # ACC: 0=reverse, 1=neutral, 2=first gear.
        # Wheel Companion convention: -1=reverse, 0=neutral, 1=first.
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
    completed_laps = struct.unpack_from(
        "<i", data, GRAPHICS_COMPLETED_LAPS_OFFSET
    )[0]
    position = struct.unpack_from(
        "<i", data, GRAPHICS_POSITION_OFFSET
    )[0]
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

    max_rpm = struct.unpack_from(
        "<i", data, STATIC_MAX_RPM_OFFSET
    )[0]
    max_fuel = struct.unpack_from(
        "<f", data, STATIC_MAX_FUEL_OFFSET
    )[0]

    if not math.isfinite(max_fuel):
        max_fuel = 0.0

    return {
        "max_rpm": max(0, int(max_rpm)),
        "max_fuel_l": max(0.0, float(max_fuel)),
    }


class _SharedMemory:
    """Read-only Windows named-memory mapping."""

    def __init__(self, name: str):
        if os.name != "nt":
            raise OSError("ACC Shared Memory requires Windows")

        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.handle = None
        self.view = None

        self.kernel32.OpenFileMappingW.argtypes = [
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_wchar_p,
        ]
        self.kernel32.OpenFileMappingW.restype = ctypes.c_void_p

        self.kernel32.MapViewOfFile.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_size_t,
        ]
        self.kernel32.MapViewOfFile.restype = ctypes.c_void_p

        self.kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        self.kernel32.UnmapViewOfFile.restype = ctypes.c_int

        self.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel32.CloseHandle.restype = ctypes.c_int

        # FILE_MAP_READ
        self.handle = self.kernel32.OpenFileMappingW(
            0x0004, 0, name
        )
        if not self.handle:
            error = ctypes.get_last_error()
            raise OSError(
                error,
                f"Cannot open {name}. Is ACC running?"
            )

        self.view = self.kernel32.MapViewOfFile(
            self.handle, 0x0004, 0, 0, 0
        )
        if not self.view:
            error = ctypes.get_last_error()
            self.kernel32.CloseHandle(self.handle)
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
        self._thread = threading.Thread(
            target=self._run,
            name="ACCSharedMemoryReader",
            daemon=True,
        )
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
        for attr in (
            "_mapping",
            "_graphics_mapping",
            "_static_mapping",
        ):
            mapping = getattr(self, attr)
            if mapping:
                try:
                    mapping.close()
                except Exception:
                    pass
                setattr(self, attr, None)

    def _read_optional_page(
        self,
        *,
        mapping_attr: str,
        map_name: str,
        size: int,
        decoder,
        now: float,
        retry_attr: str,
    ):
        """Read graphics/static data without interrupting physics telemetry."""
        mapping = getattr(self, mapping_attr)

        if mapping is None:
            if now < getattr(self, retry_attr):
                return None

            # Avoid repeatedly attempting failed mappings every frame.
            setattr(self, retry_attr, now + 1.0)

            try:
                mapping = _SharedMemory(map_name)
                setattr(self, mapping_attr, mapping)
            except OSError:
                return None

        try:
            result = decoder(mapping.read(size))
            return result
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

                values = decode_physics_prefix(
                    self._mapping.read(PHYSICS_PREFIX.size)
                )

                now = time.monotonic()

                self._graphics = self._read_optional_page(
                    mapping_attr="_graphics_mapping",
                    map_name=GRAPHICS_MAP,
                    size=GRAPHICS_PREFIX_SIZE,
                    decoder=decode_graphics_prefix,
                    now=now,
                    retry_attr="_next_graphics_retry",
                ) or self._graphics

                self._static = self._read_optional_page(
                    mapping_attr="_static_mapping",
                    map_name=STATIC_MAP,
                    size=STATIC_PREFIX_SIZE,
                    decoder=decode_static_prefix,
                    now=now,
                    retry_attr="_next_static_retry",
                ) or self._static

                # ACC updates packetId as its physics page changes.
                if values["packet_id"] != self._last_packet_id:
                    previous = self._last_update
                    self._last_packet_id = values["packet_id"]
                    self._last_update = now
                    self._publish(
                        values,
                        now,
                        previous,
                        self._graphics,
                        self._static,
                    )

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
                    self._live = LiveTelemetry(
                        source="ACC Shared Memory",
                        total_packets=old_total,
                        invalid_packets=old_invalid,
                    )
                    self._wheel = WheelTelemetrySnapshot()

            remaining = self.poll_interval - (
                time.monotonic() - started
            )
            self._stop.wait(max(0.001, remaining))

    def _publish(self, v, now, previous, graphics, static):
        speed = max(0, min(65535, int(round(v["speed_kph"]))))
        rpm = v["rpm"]
        gear = v["gear"]

        # Rev percentage uses the selected car's actual ACC redline.
        max_rpm = static["max_rpm"] if static else 0
        if max_rpm > 0:
            rpm_percent = max(
                0, min(100, int(round(rpm * 100.0 / max_rpm)))
            )
        else:
            rpm_percent = 0

        # Fuel percentage uses ACC's static tank capacity.
        max_fuel = static["max_fuel_l"] if static else 0.0
        fuel_l = v["fuel_l"]
        if max_fuel > 0:
            fuel_percent = round(
                max(0.0, min(100.0, fuel_l * 100.0 / max_fuel)),
                1,
            )
        else:
            fuel_percent = None

        if graphics:
            position = graphics["position"]
            completed_laps = graphics["completed_laps"]
            flag_status = graphics["flag_status"]

            # ACC status 2 means the game is live.
            # completedLaps counts laps already completed.
            lap_number = (
                completed_laps + 1
                if graphics["status"] == 2
                else completed_laps
            )
        else:
            position = 0
            lap_number = 0
            flag_status = 0

        # ACC steerAngle is normalized here to the wheel's percentage range.
        steering_percent = int(round(
            max(-1.0, min(1.0, v["steering_angle"])) * 100.0
        ))

        # A simple threshold indicator; rpm_percent provides the full scale.
        shift_light = int(rpm_percent >= 95) if max_rpm > 0 else 0

        wheel = WheelTelemetrySnapshot(
            speed=speed,
            gear=gear,
            position=position,
            rpm_percent=rpm_percent,
            shift_light=shift_light,
            flag_status=flag_status,
            ers_mode=0,
            status_bits=0,
        )

        rate = (
            1.0 / max(0.001, now - previous)
            if previous is not None
            else 0.0
        )

        throttle = int(round(v["throttle"] * 100))
        brake = int(round(v["brake"] * 100))

        with self._lock:
            live = LiveTelemetry(
                # Legacy UI field: true means telemetry is live.
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
                # ACC does not use F1 DRS/ERS values.
                drs_active=False,
                drs_available=False,
                position=position,
                lap_number=lap_number,
                fuel_percent=fuel_percent,
                ers_percent=None,
                ers_mode=0,
                flag_status=flag_status,
                session_uid=0,
                game_year=0,
                last_packet_monotonic=now,
            )

            self._live = live
            self._wheel = wheel

        if self.on_snapshot:
            try:
                self.on_snapshot(wheel)
            except Exception:
                # A receiver callback error must not kill the telemetry reader.
                pass
