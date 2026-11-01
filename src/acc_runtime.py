"""ACC runtime bridge for the existing Race Engineer radio pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
import time

from .engineer import AutomaticEngineer
from .engineer.models import EngineerMessage
from .telemetry_pipeline import race_state_from_acc


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
    fuel_kg: float | None = None
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
        # Reuse the existing Race Engineer rule engine with an ACC -> RaceState adapter.
        self.engineer = AutomaticEngineer()
        self.status = ACCRuntimeStatus()
        self._active = False
        self._fuel_start_kg: float | None = None
        self._fuel_start_lap: int | None = None
        self._last_lap = 0
        self._session_uid = 1
        self._session_signature = None
        self.latest_state = None

    def start(self) -> None:
        self._active = True
        self.status = ACCRuntimeStatus(active=True)
        self.engineer.reset(self._session_uid)
        self._fuel_start_kg = None
        self._fuel_start_lap = None
        self._last_lap = 0
        self._session_signature = None
        self.latest_state = None

    def stop(self) -> None:
        self._active = False
        self.status.active = False
        self.status.connected = False
        self.engineer.reset(self._session_uid)
        self.latest_state = None

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

        signature = (
            self.status.car,
            self.status.track,
            getattr(telemetry, "session_type", self.status.session),
            getattr(telemetry, "session_index", None),
        )
        if self._session_signature is None:
            self._session_signature = signature
        elif signature != self._session_signature:
            self._session_signature = signature
            self._session_uid += 1
            self.engineer.reset(self._session_uid)
            self.status.history.clear()
            self._fuel_start_kg = None
            self._fuel_start_lap = None
            self._last_lap = 0

        fuel = getattr(telemetry, "fuel_kg", None)
        lap = self.status.lap
        self._update_fuel_history(lap, fuel, now)

        # Convert ACC values into the existing RaceState contract, then run the
        # same deterministic AutomaticEngineer used by F1. Missing ACC fields
        # remain None; no F1-only telemetry is fabricated.
        state = race_state_from_acc(
            telemetry,
            fuel_remaining_laps=self._estimated_fuel_laps(fuel),
            session_uid=1_000_000 + self._session_uid,
        )
        self.latest_state = state
        # ACC uses the shared transition/threshold rules, but deliberately
        # skips F1-only event and pit-strategy evaluation categories.
        messages = self.engineer.evaluate(state, now, changed_category="telemetry")
        # Drain the internal queue here because ACC delivers only the filtered
        # per-update messages through the existing speech path.
        self.engineer.drain()
        return tuple(
            message for message in messages
            if not str(message.key).startswith(("pit:deterministic_plan", "strategy:pit"))
        )

    def _update_fuel_history(self, lap: int, fuel, now: float) -> None:
        if not isinstance(fuel, (int, float)) or fuel < 0:
            return

        fuel = float(fuel)
        if self._fuel_start_kg is None:
            self.status.fuel_kg = fuel
            self._fuel_start_kg = fuel
            self._fuel_start_lap = lap
            self._last_lap = max(self._last_lap, lap)
            return

        if lap > (self._fuel_start_lap or 0):
            completed = lap - int(self._fuel_start_lap or lap)
            used = max(0.0, self._fuel_start_kg - fuel)
            if completed > 0 and used > 0.05:
                per_lap = used / completed
                self.status.history.append({
                    "lap": int(lap - 1),
                    "fuel_used_kg": per_lap,
                    "at": now,
                })
                if len(self.status.history) > 32:
                    del self.status.history[:-32]
            self._fuel_start_kg = fuel
            self._fuel_start_lap = lap
        self._last_lap = max(self._last_lap, lap)
        self.status.fuel_kg = fuel

    def _estimated_fuel_laps(self, fuel) -> float | None:
        """Estimate remaining laps from ACC fuel mass and learned kg-per-lap."""
        try:
            remaining_kg = float(fuel)
        except (TypeError, ValueError, OverflowError):
            return None
        if remaining_kg < 0:
            return None
        per_lap = self._learned_fuel_per_lap()
        if per_lap is None or per_lap <= 0:
            return None
        return remaining_kg / per_lap

    def _learned_fuel_per_lap(self) -> float | None:
        usable = [
            float(row["fuel_used_kg"])
            for row in self.status.history[-8:]
            if isinstance(row.get("fuel_used_kg"), (int, float)) and row["fuel_used_kg"] > 0.05
        ]
        return (sum(usable) / len(usable)) if usable else None

