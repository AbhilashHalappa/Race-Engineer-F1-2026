"""ACC runtime bridge for the existing Race Engineer radio pipeline.

ACC intentionally does not enter the F1 RaceStateEngine. This adapter owns the
ACC-only engineer/session state and converts deterministic ACC messages into the
existing EngineerMessage format used by SpeechOutput.
"""
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
        self._last_sample_at: float | None = None
        self._last_lap = 0

    def start(self) -> None:
        self._active = True
        self.status = ACCRuntimeStatus(active=True)
        self.engineer.reset()
        self._fuel_start_l = None
        self._fuel_start_lap = None
        self._last_sample_at = None
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
        self.status.connected = bool(getattr(telemetry, "udp_connected", False))
        self.status.last_packet_monotonic = getattr(telemetry, "last_packet_monotonic", None) or now
        self.status.lap = int(getattr(telemetry, "lap_number", 0) or 0)
        self.status.position = int(getattr(telemetry, "position", 0) or 0)
        self.status.speed_kph = int(getattr(telemetry, "speed_kph", 0) or 0)
        self.status.gear = int(getattr(telemetry, "gear", 0) or 0)
        self.status.rpm = int(getattr(telemetry, "engine_rpm", 0) or 0)
        self.status.throttle_percent = int(getattr(telemetry, "throttle_percent", 0) or 0)
        self.status.brake_percent = int(getattr(telemetry, "brake_percent", 0) or 0)
        self.status.fuel_percent = getattr(telemetry, "fuel_percent", None)
        self.status.flag_status = int(getattr(telemetry, "flag_status", 0) or 0)

        # Learn fuel usage from actual ACC fuel samples. This deliberately uses
        # completed-lap deltas instead of a guessed fixed GT3 consumption rate.
        fuel = getattr(telemetry, "fuel_l", None)
        lap = self.status.lap
        if isinstance(fuel, (int, float)) and fuel >= 0:
            if self._fuel_start_l is None:
                self._fuel_start_l = float(fuel)
                self._fuel_start_lap = lap
            elif lap > (self._fuel_start_lap or 0):
                completed = lap - int(self._fuel_start_lap or lap)
                if completed > 0:
                    used = max(0.0, self._fuel_start_l - float(fuel))
                    per_lap = used / completed
                    if per_lap > 0.05:
                        # The ACC engineer consumes this learned value through the
                        # standard duck-typed telemetry attribute below.
                        setattr(telemetry, "fuel_per_lap_l", per_lap) if hasattr(telemetry, "__dict__") else None
                self._fuel_start_l = float(fuel)
                self._fuel_start_lap = lap
            self.status.fuel_l = float(fuel)

        # LiveTelemetry is immutable/slot-based, so pass a tiny proxy for optional
        # ACC-only values instead of mutating the protected shared model.
        class _ACCProxy:
            pass

        proxy = _ACCProxy()
        for name in (
            "lap_number", "fuel_l", "fuel_percent", "position", "speed_kph",
            "gear", "engine_rpm", "throttle_percent", "brake_percent",
            "steering_percent", "flag_status", "last_packet_monotonic",
        ):
            setattr(proxy, name, getattr(telemetry, name, None))
        proxy.fuel_per_lap_l = self._learned_fuel_per_lap()
        proxy.is_in_pit = False
        proxy.is_in_pit_lane = False
        proxy.best_lap_time_ms = getattr(telemetry, "best_lap_time_ms", None)
        proxy.last_lap_time_ms = getattr(telemetry, "last_lap_time_ms", None)

        generated = self.engineer.evaluate(proxy, now)
        messages: list[EngineerMessage] = []
        for msg in generated:
            messages.append(self._convert(msg, now))
        self._record_lap_transition(proxy, now)
        return tuple(messages)

    def _learned_fuel_per_lap(self) -> float | None:
        samples = self.status.history
        if len(samples) < 2:
            return None
        usable = [float(x["fuel_used"]) for x in samples[-8:] if isinstance(x.get("fuel_used"), (int, float)) and x["fuel_used"] > 0.05]
        return (sum(usable) / len(usable)) if usable else None

    def _record_lap_transition(self, telemetry, now: float) -> None:
        lap = int(getattr(telemetry, "lap_number", 0) or 0)
        fuel = getattr(telemetry, "fuel_l", None)
        if lap > self._last_lap:
            self.status.history.append({"lap": lap, "fuel_used": None, "at": now})
            if len(self.status.history) > 32:
                del self.status.history[:-32]
        if self.status.history and isinstance(fuel, (int, float)):
            row = self.status.history[-1]
            if row.get("lap") == lap:
                row["fuel_now"] = float(fuel)
        self._last_lap = max(self._last_lap, lap)

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
