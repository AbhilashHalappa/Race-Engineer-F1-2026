"""ACC-specific deterministic race-engineer rules.

This module deliberately stays separate from the protected F1 engineer.  It is
fed by ACC telemetry and can later be connected to the existing radio scheduler
without changing F1 behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable


class ACCPriority(IntEnum):
    CRITICAL = 0
    STRATEGY = 1
    INFORMATION = 2
    COACHING = 3


@dataclass(frozen=True, slots=True)
class ACCEngineerMessage:
    key: str
    priority: ACCPriority
    text: str
    lap: int = 0
    speak: bool = True


@dataclass(slots=True)
class ACCLapReference:
    best_ms: int | None = None
    last_ms: int | None = None
    completed_laps: int = 0


class ACCRaceEngineer:
    """Small, deterministic ACC engineer.

    The rules use only values ACC publishes. No F1-only concepts such as ERS or
    DRS are referenced. Cooldowns and edge-triggering prevent radio spam.
    """

    def __init__(self, *, cooldown_s: float = 8.0) -> None:
        self.cooldown_s = max(1.0, float(cooldown_s))
        self.reference = ACCLapReference()
        self._last_emit: dict[str, float] = {}
        self._last_lap = 0
        self._fuel_warning = False
        self._pit_warning = False

    def reset(self) -> None:
        self.reference = ACCLapReference()
        self._last_emit.clear()
        self._last_lap = 0
        self._fuel_warning = False
        self._pit_warning = False

    def evaluate(self, telemetry, now: float) -> tuple[ACCEngineerMessage, ...]:
        """Evaluate one ACC telemetry snapshot.

        ``telemetry`` is intentionally duck-typed so this module remains usable
        with both LiveTelemetry and the richer ACC session object.
        """
        lap = int(getattr(telemetry, "lap_number", 0) or 0)
        out: list[ACCEngineerMessage] = []

        best_ms = getattr(telemetry, "best_lap_time_ms", None)
        last_ms = getattr(telemetry, "last_lap_time_ms", None)
        if best_ms and best_ms > 0:
            self.reference.best_ms = int(best_ms)
        if last_ms and last_ms > 0:
            self.reference.last_ms = int(last_ms)

        if lap > self._last_lap:
            self.reference.completed_laps = max(self.reference.completed_laps, lap - 1)
            self._last_lap = lap
            if self.reference.last_ms and self.reference.best_ms:
                delta_ms = self.reference.last_ms - self.reference.best_ms
                if delta_ms < -250:
                    out.append(self._message("lap:personal-best", ACCPriority.INFORMATION,
                                             "Personal best. Good lap.", lap, now))
                elif delta_ms > 1500:
                    out.append(self._message("lap:delta", ACCPriority.COACHING,
                                             f"Lap was {delta_ms / 1000:.1f} seconds off your best.", lap, now))

        fuel = getattr(telemetry, "fuel_l", None)
        fuel_per_lap = getattr(telemetry, "fuel_per_lap_l", None)
        if fuel is not None and fuel_per_lap and fuel_per_lap > 0:
            laps_left = float(fuel) / float(fuel_per_lap)
            if laps_left <= 1.5 and not self._fuel_warning:
                self._fuel_warning = True
                out.append(self._message("fuel:critical", ACCPriority.STRATEGY,
                                         f"Fuel for about {laps_left:.1f} laps remaining.", lap, now))
            elif laps_left > 2.5:
                self._fuel_warning = False

        is_in_pit = bool(getattr(telemetry, "is_in_pit", False))
        is_in_pit_lane = bool(getattr(telemetry, "is_in_pit_lane", False))
        if (is_in_pit or is_in_pit_lane) and not self._pit_warning:
            self._pit_warning = True
            out.append(self._message("pit:entry", ACCPriority.INFORMATION,
                                     "Pit lane. Watch the limiter and pit marks.", lap, now))
        elif not is_in_pit and not is_in_pit_lane:
            self._pit_warning = False

        return tuple(m for m in out if m is not None)

    def _message(self, key: str, priority: ACCPriority, text: str,
                 lap: int, now: float) -> ACCEngineerMessage | None:
        last = self._last_emit.get(key)
        if last is not None and now - last < self.cooldown_s:
            return None
        self._last_emit[key] = now
        return ACCEngineerMessage(key, priority, text, lap)


def evaluate_input_coaching(*, speed_kph: float, brake_percent: float,
                            throttle_percent: float, reference_speed_kph: float | None,
                            reference_brake_percent: float | None) -> tuple[str, ...]:
    """Return conservative ACC driving cues when a reference trace exists."""
    messages: list[str] = []
    if reference_speed_kph and speed_kph < reference_speed_kph - 8 and brake_percent < 20:
        messages.append("Carry more speed into the corner.")
    if reference_speed_kph and speed_kph > reference_speed_kph + 10 and brake_percent > 70:
        messages.append("Brake earlier for the corner.")
    if reference_brake_percent is not None and brake_percent > reference_brake_percent + 12:
        messages.append("Use a little less brake pressure.")
    if throttle_percent > 85 and speed_kph > 20:
        messages.append("Good exit. Stay committed.")
    return tuple(messages)
