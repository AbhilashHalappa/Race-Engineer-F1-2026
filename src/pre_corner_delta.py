"""Presentation-only PRE-corner phase sequencing and driver/reference deltas.

This module does not own CORNER COACH timing, diagnosis, speech, reference
selection or scoring.  It converts already-published overlay snapshot data into
six readable driving phases and phase-specific comparisons:

    BRAKE -> ENTRY -> TURN-IN -> APEX -> EXIT -> THROTTLE

The helper intentionally stays downstream of the proven coach engine.
"""
from __future__ import annotations

import math
from typing import Any, Iterable


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def turn_in_target(
    physical_corners: Iterable[dict] | None,
    zone: dict | None,
    driving_events: Iterable[dict] | None = None,
    *,
    input_telemetry_trusted: bool = True,
) -> float | None:
    """Return the coach turn-in target without inventing reference input data."""
    if not isinstance(zone, dict):
        return None
    if input_telemetry_trusted:
        owned = set(str(x) for x in (zone.get("event_ids") or ()))
        lo = zone.get("approach_start_m")
        hi = zone.get("apex_m")
        candidates = []
        for event in driving_events or ():
            if (
                not isinstance(event, dict)
                or str(event.get("event_id")) not in owned
                or str(event.get("kind") or "") != "steering"
            ):
                continue
            start = event.get("start_m")
            if finite(start) and (not finite(lo) or float(start) >= float(lo) - 1e-6) and (
                not finite(hi) or float(start) <= float(hi) + 1e-6
            ):
                candidates.append(float(start))
        if candidates:
            return min(candidates)

    ids = tuple(zone.get("corner_ids") or ())
    first_id = ids[0] if ids else None
    corner = next(
        (c for c in (physical_corners or ()) if isinstance(c, dict) and c.get("corner_id") == first_id),
        None,
    )
    if isinstance(corner, dict) and finite(corner.get("start_m")) and finite(corner.get("apex_m")):
        return float(corner["start_m"]) + (float(corner["apex_m"]) - float(corner["start_m"])) * 0.5
    if finite(zone.get("start_m")) and finite(zone.get("apex_m")):
        return float(zone["start_m"]) + (float(zone["apex_m"]) - float(zone["start_m"])) * 0.5
    return None


def phase_target(
    physical_corners: Iterable[dict] | None,
    zone: dict | None,
    phase: str,
    driving_events: Iterable[dict] | None = None,
    *,
    input_telemetry_trusted: bool = True,
) -> tuple[str, str, float | None]:
    """Map the visible PRE phase to the matching reference event.

    Each visible phase gets its own comparison target instead of reusing whole
    corner progress:
      BRAKE      -> brake onset
      ENTRY      -> brake release
      TURN-IN    -> steering onset / geometry fallback
      APEX       -> reference apex position
      EXIT       -> throttle pickup
      THROTTLE   -> full-throttle point
    """
    phase = str(phase or "").upper()
    if not isinstance(zone, dict):
        return "delta", "DELTA", None
    if phase in {"APPROACHING", "BRAKING", "BRAKE"}:
        target = zone.get("brake_start_m") if finite(zone.get("brake_start_m")) else zone.get("start_m")
        return "brake_m", "BRAKE", float(target) if finite(target) else None
    if phase == "ENTRY":
        target = zone.get("brake_release_m")
        return "brake_release_m", "BRAKE RELEASE", float(target) if finite(target) else None
    if phase == "TURN-IN":
        return "turn_in_m", "TURN-IN", turn_in_target(
            physical_corners, zone, driving_events, input_telemetry_trusted=input_telemetry_trusted
        )
    if phase == "APEX":
        target = zone.get("apex_m")
        return "apex_m", "APEX", float(target) if finite(target) else None
    if phase == "EXIT":
        target = zone.get("throttle_start_m")
        return "throttle_m", "THROTTLE PICKUP", float(target) if finite(target) else None
    if phase == "THROTTLE":
        target = zone.get("full_throttle_m")
        return "full_throttle_m", "FULL THROTTLE", float(target) if finite(target) else None
    return "delta", "DELTA", None


def _ordered_phase_anchors(
    physical_corners: Iterable[dict] | None,
    zone: dict,
    driving_events: Iterable[dict] | None = None,
    *,
    input_telemetry_trusted: bool = True,
) -> list[float] | None:
    """Build stable reference anchors for the six display phases.

    The underlying coach has broader APPROACH/BRAKE/ENTRY/APEX/EXIT states.  The
    PRE overlay needs a readable six-step visual sequence.  We therefore use
    existing compiled reference points when available, then enforce monotonic
    spacing only for presentation so short/overlapping events cannot make a
    phase disappear instantly.
    """
    if not isinstance(zone, dict):
        return None
    brake = zone.get("brake_start_m") if finite(zone.get("brake_start_m")) else zone.get("start_m")
    start = zone.get("start_m")
    release = zone.get("brake_release_m") if finite(zone.get("brake_release_m")) else start
    turn = turn_in_target(
        physical_corners, zone, driving_events, input_telemetry_trusted=input_telemetry_trusted
    )
    apex = zone.get("apex_m")
    throttle = zone.get("throttle_start_m")
    full = zone.get("full_throttle_m") if finite(zone.get("full_throttle_m")) else zone.get("end_m")
    end = zone.get("end_m")
    if not all(finite(v) for v in (brake, start, apex, end)):
        return None

    lo = float(brake)
    hi = float(end)
    if hi <= lo + 1.0:
        return None
    span = hi - lo
    fallback = [lo + span * f for f in (0.00, 0.20, 0.38, 0.58, 0.78, 0.94)]
    raw = [
        float(brake),
        float(release) if finite(release) else fallback[1],
        float(turn) if finite(turn) else fallback[2],
        float(apex),
        float(throttle) if finite(throttle) else fallback[4],
        float(full) if finite(full) else fallback[5],
    ]

    # Blend obviously out-of-order/missing event anchors back toward stable
    # phase locations.  Minimum separation is deliberately presentation-only.
    min_sep = max(2.5, span * 0.035)
    anchors = [max(lo, min(hi, raw[0]))]
    for i in range(1, 6):
        candidate = max(lo, min(hi, raw[i]))
        if candidate <= anchors[-1] + min_sep:
            candidate = max(candidate, fallback[i], anchors[-1] + min_sep)
        anchors.append(min(hi, candidate))

    # If a very short zone still collapsed late anchors, use even spacing.
    if any(anchors[i] <= anchors[i - 1] + 0.5 for i in range(1, len(anchors))):
        anchors = fallback
    return anchors


def presentation_phase(
    physical_corners: Iterable[dict] | None,
    zone: dict | None,
    distance_m: Any,
    driving_events: Iterable[dict] | None = None,
    *,
    input_telemetry_trusted: bool = True,
) -> str:
    """Return a stable six-step PRE display phase for the current distance."""
    if not isinstance(zone, dict) or not finite(distance_m):
        return "FAR"
    anchors = _ordered_phase_anchors(
        physical_corners, zone, driving_events, input_telemetry_trusted=input_telemetry_trusted
    )
    if not anchors:
        return "FAR"
    x = float(distance_m)
    approach = zone.get("approach_start_m")
    if finite(approach) and x < float(approach):
        return "FAR"
    if x < anchors[0]:
        return "APPROACHING"

    # Midpoints give each reference event a visible window and prevent the UI
    # from skipping ENTRY/APEX/THROTTLE just because two compiled points are
    # close together.
    boundaries = [(anchors[i] + anchors[i + 1]) * 0.5 for i in range(5)]
    phases = ("BRAKE", "ENTRY", "TURN-IN", "APEX", "EXIT", "THROTTLE")
    for i, boundary in enumerate(boundaries):
        if x < boundary:
            return phases[i]
    return phases[-1]


def update_driver_events(
    events: dict[str, float] | None,
    zone: dict | None,
    distance_m: Any,
    *,
    brake: Any,
    steering: Any,
    throttle: Any,
    speed: Any = None,
) -> dict[str, float]:
    """Capture the driver's first phase events using established UI thresholds."""
    out = dict(events or {})
    if not isinstance(zone, dict) or not finite(distance_m):
        return out
    x = float(distance_m)
    apex = zone.get("apex_m") if finite(zone.get("apex_m")) else zone.get("end_m")
    approach = zone.get("approach_start_m") if finite(zone.get("approach_start_m")) else zone.get("start_m")
    start = zone.get("start_m") if finite(zone.get("start_m")) else approach
    end = zone.get("end_m")
    throttle_ref = zone.get("throttle_start_m") if finite(zone.get("throttle_start_m")) else end

    if (
        "brake_m" not in out
        and finite(approach)
        and finite(apex)
        and float(approach) <= x <= float(apex)
        and finite(brake)
        and float(brake) >= 0.10
    ):
        out["brake_m"] = x

    if (
        "brake_release_m" not in out
        and "brake_m" in out
        and finite(apex)
        and x >= float(out["brake_m"])
        and x <= float(apex) + 35.0
        and finite(brake)
        and float(brake) <= 0.05
    ):
        out["brake_release_m"] = x

    if (
        "turn_in_m" not in out
        and finite(approach)
        and finite(apex)
        and float(approach) <= x <= float(apex)
        and finite(steering)
        and abs(float(steering)) >= 0.08
    ):
        out["turn_in_m"] = x

    # APEX uses the driver's minimum-speed position in the core corner window.
    # The candidate is allowed to improve until the reference throttle region,
    # then stays fixed.  Internal speed state is overlay-local only.
    if (
        finite(speed)
        and finite(start)
        and finite(apex)
        and float(start) <= x <= (float(throttle_ref) if finite(throttle_ref) else float(apex) + 45.0)
    ):
        best = out.get("_apex_speed_kph")
        if not finite(best) or float(speed) < float(best):
            out["_apex_speed_kph"] = float(speed)
            out["apex_m"] = x

    if (
        "throttle_m" not in out
        and finite(apex)
        and finite(end)
        and float(apex) <= x <= float(end) + 40.0
        and finite(throttle)
        and float(throttle) >= 0.20
    ):
        out["throttle_m"] = x

    if (
        "full_throttle_m" not in out
        and finite(apex)
        and finite(end)
        and float(apex) <= x <= float(end) + 60.0
        and finite(throttle)
        and float(throttle) >= 0.90
    ):
        out["full_throttle_m"] = x

    return out


def phase_delta_payload(label: str, target: Any, driver: Any, current_distance: Any, phase: str) -> dict[str, Any]:
    """Return the exact driver-reference phase delta shown by the PRE comparator."""
    delta = (float(driver) - float(target)) if finite(driver) and finite(target) else None
    provisional = False
    # Once the reference point has passed without the driver action, showing the
    # growing late distance is useful and deterministic.  It freezes at the real
    # event distance as soon as that input is captured.
    if (
        delta is None
        and finite(target)
        and finite(current_distance)
        and float(current_distance) >= float(target)
        and str(phase or "").upper() not in {"APPROACHING", "FAR"}
    ):
        delta = float(current_distance) - float(target)
        provisional = True

    if not finite(target):
        status = "unavailable"
    elif finite(delta):
        status = "matched" if abs(float(delta)) <= 1.0 else ("early" if float(delta) < 0 else "late")
    else:
        status = "waiting"

    return {
        "label": str(label),
        "reference_m": float(target) if finite(target) else None,
        "driver_m": float(driver) if finite(driver) else None,
        "delta_m": float(delta) if finite(delta) else None,
        "status": status,
        "provisional": bool(provisional),
    }
