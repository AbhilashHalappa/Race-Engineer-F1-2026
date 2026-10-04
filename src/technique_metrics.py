"""Explainable technique, consistency and observed progress metrics.

All metrics use quality-eligible completed laps only.  V1.3.1.0 extends the
existing consistency output with chronological observed trends; it does not turn
those trends into predictions or opaque driver scores.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from .data_quality import lap_quality


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _cv_or_spread(values: list[float]) -> dict[str, float] | None:
    if len(values) < 3:
        return None
    m = mean(values)
    sd = pstdev(values)
    return {"mean": m, "stddev": sd, "range": max(values) - min(values), "samples": len(values)}


def _trend(values: list[tuple[int | None, float]], *, deadband: float) -> dict[str, Any] | None:
    if len(values) < 2:
        return None
    first_lap, first = values[0]; last_lap, latest = values[-1]
    delta = latest - first
    direction = "stable"
    if delta <= -abs(deadband): direction = "decreasing"
    elif delta >= abs(deadband): direction = "increasing"
    return {
        "first_lap": first_lap, "latest_lap": last_lap,
        "first": first, "latest": latest, "delta": delta,
        "direction": direction, "samples": len(values),
    }


def session_technique_metrics(laps) -> dict[str, Any]:
    valid = [x for x in laps if isinstance(x, dict) and lap_quality(x)["eligible"]]
    valid.sort(key=lambda x: int(x.get("lap") or 0))
    lap_times = [float(x["lap_time_s"]) for x in valid if _num(x.get("lap_time_s"))]
    lap_time_rows = [(x.get("lap"), float(x["lap_time_s"])) for x in valid if _num(x.get("lap_time_s"))]
    by_corner: dict[int, list[tuple[int | None, dict[str, Any]]]] = {}
    for lap in valid:
        for section in lap.get("sections") or []:
            if isinstance(section, dict) and isinstance(section.get("id"), int):
                by_corner.setdefault(int(section["id"]), []).append((lap.get("lap"), section))

    corners = []
    for cid, lap_rows in sorted(by_corner.items()):
        rows = [r for _, r in lap_rows]
        def vals(key): return [float(r[key]) for r in rows if _num(r.get(key))]
        def chronological(key): return [(lap_no, float(r[key])) for lap_no, r in lap_rows if _num(r.get(key))]
        corners.append({
            "corner_id": cid,
            "observations": len(rows),
            "brake_point_consistency": _cv_or_spread(vals("start_m")),
            "brake_release_consistency": _cv_or_spread(vals("brake_release_m")),
            "trail_brake_consistency": _cv_or_spread(vals("trail_brake_m")),
            "minimum_speed_consistency": _cv_or_spread(vals("min_speed_kph")),
            "apex_consistency": _cv_or_spread(vals("apex_m")),
            "apex_speed_consistency": _cv_or_spread(vals("apex_speed_kph")),
            "coasting_time_consistency": _cv_or_spread(vals("coasting_s")),
            "throttle_pickup_consistency": _cv_or_spread(vals("throttle_pickup_m")),
            "throttle_pickup_time_consistency": _cv_or_spread(vals("throttle_pickup_after_apex_s")),
            "exit_speed_consistency": _cv_or_spread(vals("exit_speed_kph")),
            "steering_rate_consistency": _cv_or_spread(vals("steering_rate_mean_per_s")),
            "steering_correction_consistency": _cv_or_spread(vals("steering_corrections")),
            "steering_smoothness_consistency": _cv_or_spread(vals("steering_smoothness")),
            "steering_unwind_time_consistency": _cv_or_spread(vals("steering_unwind_s")),
            "gear_choice_consistency": _cv_or_spread(vals("apex_gear")),
            # Direction is deliberately descriptive. For distance metrics lower
            # or higher is not automatically "better" without a reference.
            "observed_trends": {
                "brake_point_m": _trend(chronological("start_m"), deadband=5.0),
                "brake_release_m": _trend(chronological("brake_release_m"), deadband=5.0),
                "minimum_speed_kph": _trend(chronological("min_speed_kph"), deadband=2.0),
                "apex_speed_kph": _trend(chronological("apex_speed_kph"), deadband=2.0),
                "coasting_s": _trend(chronological("coasting_s"), deadband=0.05),
                "throttle_pickup_m": _trend(chronological("throttle_pickup_m"), deadband=5.0),
                "throttle_pickup_after_apex_s": _trend(chronological("throttle_pickup_after_apex_s"), deadband=0.05),
                "exit_speed_kph": _trend(chronological("exit_speed_kph"), deadband=2.0),
                "steering_smoothness": _trend(chronological("steering_smoothness"), deadband=0.05),
            },
        })

    best_lap = min(lap_times) if lap_times else None
    latest_lap = lap_times[-1] if lap_times else None
    first_lap = lap_times[0] if lap_times else None
    return {
        "lap_time_consistency": _cv_or_spread(lap_times),
        "lap_time_progress": {
            "first_lap_s": first_lap,
            "latest_lap_s": latest_lap,
            "best_lap_s": best_lap,
            "first_to_latest_s": (latest_lap-first_lap) if _num(latest_lap) and _num(first_lap) else None,
            "best_to_latest_s": (latest_lap-best_lap) if _num(latest_lap) and _num(best_lap) else None,
            "trend": _trend(lap_time_rows, deadband=0.025),
        },
        "corners": corners,
        "eligible_laps": [x.get("lap") for x in valid],
        "minimum_samples_per_consistency_metric": 3,
        "calculation": "population standard deviation/range for consistency; first-to-latest observed change for trends; eligible valid laps only",
    }
