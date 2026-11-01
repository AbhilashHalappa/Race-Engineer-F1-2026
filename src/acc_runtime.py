"""ACC runtime bridge for the existing Race Engineer radio pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
import time

from .acc_engineer import ACCRaceEngineer, ACCEngineerMessage
from .engineer.models import EngineerMessage, Priority


@dataclass(slots=True)
class ACCRuntimeStatus:
    active: bool = False
    connected: bool = False
    last_packet_monotonic: float | None = None
    lap: int = 0
    position: int = 0
    speed_kph: int = 0
    gear: int = 0
    rpm: int = 0
    throttle_percent: int = 0
    brake_percent: int = 0
    fuel_l: float | None = None
    fuel_percent: float | None = None
    flag_status: int = 0
    best_lap_time_ms: int | None = None
    last_lap_time_ms: int | None = None
    car: str = ""
    track: str = ""
    session: int | None = None
    history: list[dict] = field(default_factory=list)


class ACCRuntime:
    """Own ACC engineering state while leaving all F1 state untouched."""

    def __init__(self, *, cooldown_s: float = 8.0) -> None:
        self.engineer = ACCRaceEngineer(cooldown_s=cooldown_s)
        self.status = ACCRuntimeStatus()
        self._active = False
        self._fuel_start_l: float | None = None
        self._fuel_start_lap: int | None = None
        self._last_lap = 0

    def start(self) -> None:
        self._active = True
        self.status = ACCRuntimeStatus(active=True)
        self.engineer.reset()
        self._fuel_start_l = None
        self._fuel_start_lap = None
        self._last_lap = 0

    def stop(self) -> None:
        self._active = False
        self.status.active = False
        self.status.connected = False
        self.engineer.reset()

    @property
    def active(self) -> bool:
        return self._active

    def update(self, telemetry, now: float | None = None) -> tuple[EngineerMessage, ...]:
        if not self._active:
            return ()
        now = time.monotonic() if now is None else float(now)

        # ACC publishes through Shared Memory, so udp_connected is not required.
        self.status.connected = bool(
            getattr(telemetry, "source", "") == "ACC Shared Memory"
        )
        self.status.last_packet_monotonic = (
            getattr(telemetry, "last_packet_monotonic", None) or now
        )
        self.status.lap = int(getattr(telemetry, "lap_number", 0) or 0)
        self.status.position = int(getattr(telemetry, "position", 0) or 0)
        self.status.speed_kph = int(getattr(telemetry, "speed_kph", 0) or 0)
        self.status.gear = int(getattr(telemetry, "gear", 0) or 0)
        self.status.rpm = int(getattr(telemetry, "engine_rpm", 0) or 0)
        self.status.throttle_percent = int(getattr(telemetry, "throttle_percent", 0) or 0)
        self.status.brake_percent = int(getattr(telemetry, "brake_percent", 0) or 0)
        self.status.fuel_percent = getattr(telemetry, "fuel_percent", None)
        self.status.flag_status = int(getattr(telemetry, "flag_status", 0) or 0)
        self.status.best_lap_time_ms = getattr(telemetry, "best_lap_time_ms", None)
        self.status.last_lap_time_ms = getattr(telemetry, "last_lap_time_ms", None)
        self.status.car = str(getattr(telemetry, "car", "") or "")
        self.status.track = str(getattr(telemetry, "track", "") or "")
        self.status.session = getattr(telemetry, "session", None)

        fuel = getattr(telemetry, "fuel_l", None)
        lap = self.status.lap
        self._update_fuel_history(lap, fuel, now)

        # LiveTelemetry is immutable/slot-based, so pass a small proxy for
        # optional ACC-only engineering fields.
        class _ACCProxy:
            pass

        proxy = _ACCProxy()
        for name in (
            "lap_number", "fuel_l", "fuel_percent", "position", "speed_kph",
            "gear", "engine_rpm", "throttle_percent", "brake_percent",
            "steering_percent", "flag_status", "last_packet_monotonic",
            "best_lap_time_ms", "last_lap_time_ms", "is_in_pit", "is_in_pit_lane",
        ):
            setattr(proxy, name, getattr(telemetry, name, None))
        proxy.fuel_per_lap_l = self._learned_fuel_per_lap()

        generated = self.engineer.evaluate(proxy, now)
        return tuple(self._convert(msg, now) for msg in generated)

    def _update_fuel_history(self, lap: int, fuel, now: float) -> None:
        if not isinstance(fuel, (int, float)) or fuel < 0:
            return

        fuel = float(fuel)
        if self._fuel_start_l is None:
            self._fuel_start_l = fuel
            self._fuel_start_lap = lap
            self._last_lap = max(self._last_lap, lap)
            return

        if lap > (self._fuel_start_lap or 0):
            completed = lap - int(self._fuel_start_lap or lap)
            used = max(0.0, self._fuel_start_l - fuel)
            if completed > 0 and used > 0.05:
                per_lap = used / completed
                self.status.history.append({
                    "lap": int(lap - 1),
                    "fuel_used": per_lap,
                    "at": now,
                })
                if len(self.status.history) > 32:
                    del self.status.history[:-32]
            self._fuel_start_l = fuel
            self._fuel_start_lap = lap
        self._last_lap = max(self._last_lap, lap)
        self.status.fuel_l = fuel

    def _learned_fuel_per_lap(self) -> float | None:
        usable = [
            float(row["fuel_used"])
            for row in self.status.history[-8:]
            if isinstance(row.get("fuel_used"), (int, float)) and row["fuel_used"] > 0.05
        ]
        return (sum(usable) / len(usable)) if usable else None

    @staticmethod
    def _convert(message: ACCEngineerMessage, now: float) -> EngineerMessage:
        priority = {
            0: Priority.CRITICAL,
            1: Priority.STRATEGY,
            2: Priority.INFORMATION,
            3: Priority.COACHING,
        }.get(int(message.priority), Priority.INFORMATION)
        return EngineerMessage(
            key=f"acc:{message.key}",
            priority=priority,
            text=message.text,
            created_at=now,
            session_time_s=None,
            speak=bool(message.speak),
        )
