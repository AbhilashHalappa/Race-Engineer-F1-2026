"""Deterministic qualifying-session guidance for the RE overlay."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class QualifyingGuidance:
    decision: str
    reason: str
    confidence: str
    time_to_line_estimate_s: float | None
    another_lap_estimate: str


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def estimate_time_to_line_s(*, current_lap_time_s, lap_distance_m, track_length_m, best_lap_time_s) -> float | None:
    if not (_finite(lap_distance_m) and _finite(track_length_m)) or float(track_length_m) <= 0:
        return None
    fraction = max(0.0, min(1.0, float(lap_distance_m) / float(track_length_m)))
    if fraction >= 0.05 and _finite(current_lap_time_s) and float(current_lap_time_s) >= 0:
        elapsed = float(current_lap_time_s)
        predicted_total = elapsed / fraction if fraction > 0 else None
        if predicted_total is not None:
            return max(0.0, predicted_total - elapsed)
    if _finite(best_lap_time_s) and float(best_lap_time_s) > 0:
        return max(0.0, float(best_lap_time_s) * (1.0 - fraction))
    return None


def evaluate_qualifying(*, session_finished: bool, driver_status: str | None, lap_valid: bool | None,
                         session_time_left_s, current_lap_time_s, lap_distance_m,
                         track_length_m, best_lap_time_s, one_shot: bool = False) -> QualifyingGuidance:
    status = (driver_status or "").strip()
    time_to_line = estimate_time_to_line_s(
        current_lap_time_s=current_lap_time_s,
        lap_distance_m=lap_distance_m,
        track_length_m=track_length_m,
        best_lap_time_s=best_lap_time_s,
    )
    if one_shot:
        another = "NO"
        time_to_line = None
    elif _finite(session_time_left_s) and time_to_line is not None:
        another = "YES (EST.)" if float(session_time_left_s) > time_to_line else "NO (EST.)"
    else:
        another = "--"
    if session_finished:
        return QualifyingGuidance("QUALIFYING COMPLETE", "session finished", "high", time_to_line, "NO")
    clock_expired = (not one_shot) and _finite(session_time_left_s) and float(session_time_left_s) <= 0
    if status == "Flying lap":
        if lap_valid is False:
            return QualifyingGuidance("LAP INVALID", "current timed lap is invalid", "high", time_to_line, another)
        if clock_expired:
            return QualifyingGuidance("FINISH LAP", "qualifying clock expired after this lap was started", "high", time_to_line, "NO")
        return QualifyingGuidance("PUSH LAP", "timed lap in progress", "high", time_to_line, another)
    if status == "Out lap":
        if clock_expired:
            return QualifyingGuidance("SESSION COMPLETE", "qualifying clock expired before a timed lap", "high", time_to_line, "NO")
        return QualifyingGuidance("PREPARE LAP", "out lap in progress", "high", time_to_line, another)
    if status == "In lap":
        return QualifyingGuidance("BOX", "in lap in progress", "high", time_to_line, another)
    if status == "In garage":
        if clock_expired:
            return QualifyingGuidance("SESSION COMPLETE", "qualifying clock expired", "high", time_to_line, "NO")
        return QualifyingGuidance("PREPARE RUN", "car is in the garage", "high", time_to_line, "--")
    if status == "On track":
        if lap_valid is False:
            return QualifyingGuidance("LAP INVALID", "current lap is invalid", "medium", time_to_line, another)
        return QualifyingGuidance("PUSH LAP", "car is on track", "medium", time_to_line, another)
    if clock_expired:
        return QualifyingGuidance("SESSION COMPLETE", "qualifying clock expired", "high", time_to_line, "NO")
    return QualifyingGuidance("NO DECISION", "waiting for qualifying run status", "low", time_to_line, another)
