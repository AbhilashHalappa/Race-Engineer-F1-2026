"""External reference-lap import/export for deterministic coaching.

The reference format stores the measured 5 m trace and detected corner sections.
It is intentionally source-agnostic: a reference may be the user's own lap or a
lap recorded by another driver, provided the trace was captured for the same
track/configuration and uses compatible telemetry fields.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

FORMAT = "RACE_ENGINEER_REFERENCE_LAP"
VERSION = "1.0"


def _num(v):
    return isinstance(v, (int, float)) and math.isfinite(v)


def _normalise_samples(samples, *, lap_time_s=None):
    if not isinstance(samples, dict):
        raise ValueError("reference lap does not contain a measured sample trace")
    rows = []
    for k, row in samples.items():
        try:
            d = float(k)
        except (TypeError, ValueError):
            continue
        if not _num(d) or not isinstance(row, dict):
            continue
        clean = dict(row)
        clean["d"] = float(clean.get("d", d)) if _num(clean.get("d", d)) else d
        rows.append((d, clean))

    # Reference lap time must advance monotonically with physical lap distance.
    # EA Time Trial ghosts can publish one asynchronous post-line sample at the
    # old end-of-lap distance with the NEW lap clock (~0 s).  Keeping that row
    # makes the final straight look roughly one whole lap slower/faster.  Drop
    # only clear clock regressions; ordinary sampling jitter remains untouched.
    rows.sort(key=lambda item: item[0])
    out = {}
    last_t = None
    for d, clean in rows:
        t = clean.get("t")
        if _num(t):
            t = float(t)
            if t < 0:
                continue
            if lap_time_s is not None and t > float(lap_time_s) + 1.0:
                continue
            if last_t is not None and t + 0.050 < last_t:
                continue
            last_t = max(last_t, t) if last_t is not None else t
            clean["t"] = t
        out[d] = clean
    if len(out) < 20:
        raise ValueError("reference lap needs at least 20 valid distance samples")
    return out



def _sanitise_legacy_time_trial_rival(lap: dict) -> dict:
    """Clean known EA Time Trial ghost speed/gear corruption in stored rivals.

    Modern rival capture already performs this cleanup before saving.  This load-
    time path keeps older `tt_rival.json` files useful without touching ordinary
    user/session reference laps.  All non speed/gear telemetry fields are kept.
    """
    samples = lap.get("_samples", {}) if isinstance(lap, dict) else {}
    rows = [(float(d), dict(row)) for d, row in samples.items() if isinstance(row, dict)]
    rows.sort(key=lambda item: item[0])
    if len(rows) < 3:
        return lap

    valid = [True] * len(rows)
    last_good = 0
    max_accel = 45.0
    max_decel = 80.0
    for i in range(1, len(rows)):
        prev = rows[last_good][1]
        row = rows[i][1]
        v, pv = row.get("speed"), prev.get("speed")
        t, pt = row.get("t"), prev.get("t")
        if not (_num(v) and _num(pv) and _num(t) and _num(pt)):
            valid[i] = False
            continue
        dt = float(t) - float(pt)
        if dt <= 0 or dt > 2.0 or float(v) > 380.0:
            valid[i] = False
            continue
        accel = ((float(v) - float(pv)) / 3.6) / dt
        if accel > max_accel or accel < -max_decel:
            valid[i] = False
            continue
        last_good = i

    # Keep each physical sample and interpolate only the corrupted speed channel.
    i = 0
    while i < len(rows):
        if valid[i]:
            i += 1
            continue
        a = i - 1
        j = i
        while j < len(rows) and not valid[j]:
            j += 1
        if a >= 0 and j < len(rows) and _num(rows[a][1].get("speed")) and _num(rows[j][1].get("speed")):
            ta = float(rows[a][1].get("t") or 0.0)
            tb = float(rows[j][1].get("t") or 0.0)
            for k in range(i, j):
                tk = float(rows[k][1].get("t") or ta)
                ratio = (tk - ta) / (tb - ta) if tb > ta else (k - a) / (j - a)
                ratio = max(0.0, min(1.0, ratio))
                rows[k][1]["speed"] = float(rows[a][1]["speed"]) + (float(rows[j][1]["speed"]) - float(rows[a][1]["speed"])) * ratio
        elif a >= 0:
            for k in range(i, j):
                rows[k][1]["speed"] = rows[a][1].get("speed")
        elif j < len(rows):
            for k in range(i, j):
                rows[k][1]["speed"] = rows[j][1].get("speed")
        i = j

    # Suppress very short ghost gear flips. A candidate gear must persist across
    # three 5 m bins before it replaces the established gear.
    stable = None
    candidate = None
    candidate_indices = []
    for i, (_distance, row) in enumerate(rows):
        gear = row.get("gear")
        if not isinstance(gear, int) or gear <= 0:
            continue
        if stable is None:
            stable = gear
            continue
        if gear == stable:
            candidate = None
            candidate_indices = []
            continue
        if gear == candidate:
            candidate_indices.append(i)
        else:
            candidate = gear
            candidate_indices = [i]
        row["gear"] = stable
        if len(candidate_indices) >= 3:
            stable = candidate
            for idx in candidate_indices:
                rows[idx][1]["gear"] = stable
            candidate = None
            candidate_indices = []

    # Older rival files also contain summary/section fields calculated before
    # the corrupted speed/gear channels were cleaned.  Rebuild every derived
    # coaching field from the cleaned trace so a legacy 486 km/h ghost cannot
    # survive in section advice even though the sample itself was repaired.
    from .measured_performance import MeasuredPerformanceRecorder, Sample

    rebuilt = []
    previous = None
    for distance, row in rows:
        # Reconstruct useful G channels when EA recorded zeroes for the ghost.
        # Longitudinal G comes from speed/time; lateral G additionally uses the
        # all-car yaw samples already stored in the reference file.
        if previous is not None:
            _pd, prev = previous
            t, pt = row.get("t"), prev.get("t")
            speed, pspeed = row.get("speed"), prev.get("speed")
            if _num(t) and _num(pt) and _num(speed) and _num(pspeed):
                dt = float(t) - float(pt)
                if 0.015 <= dt <= 0.5:
                    glong = ((float(speed) - float(pspeed)) / 3.6) / dt / 9.80665
                    if abs(glong) <= 6.0 and (not _num(row.get("g_long")) or abs(float(row.get("g_long") or 0.0)) < 1e-6):
                        row["g_long"] = glong
                    yaw, pyaw = row.get("yaw"), prev.get("yaw")
                    if _num(yaw) and _num(pyaw):
                        dy = float(yaw) - float(pyaw)
                        while dy > math.pi:
                            dy -= 2 * math.pi
                        while dy < -math.pi:
                            dy += 2 * math.pi
                        glat = (float(speed) / 3.6) * (dy / dt) / 9.80665
                        if abs(glat) <= 7.0 and (not _num(row.get("g_lat")) or abs(float(row.get("g_lat") or 0.0)) < 1e-6):
                            row["g_lat"] = glat
        previous = (distance, row)

        # Keep extra rival metadata in the stored row, while feeding only the
        # measured-performance fields into the deterministic section builder.
        rebuilt.append(Sample(
            d=float(distance),
            t=float(row.get("t")) if _num(row.get("t")) else 0.0,
            speed=float(row.get("speed")) if _num(row.get("speed")) else None,
            throttle=float(row.get("throttle")) if _num(row.get("throttle")) else None,
            brake=float(row.get("brake")) if _num(row.get("brake")) else None,
            steering=float(row.get("steering")) if _num(row.get("steering")) else None,
            gear=int(row.get("gear")) if isinstance(row.get("gear"), int) else None,
            rpm=int(row.get("rpm")) if _num(row.get("rpm")) else None,
            g_lat=float(row.get("g_lat")) if _num(row.get("g_lat")) else None,
            g_long=float(row.get("g_long")) if _num(row.get("g_long")) else None,
            slip=float(row.get("slip")) if _num(row.get("slip")) else None,
            ers_j=float(row.get("ers_j")) if _num(row.get("ers_j")) else None,
            fuel=float(row.get("fuel")) if _num(row.get("fuel")) else None,
            s_mode_available=row.get("s_mode_available") if isinstance(row.get("s_mode_available"), bool) else None,
            s_mode_straight=row.get("s_mode_straight") if isinstance(row.get("s_mode_straight"), bool) else None,
            world_x=float(row.get("world_x")) if _num(row.get("world_x")) else (float(row.get("world_x_m")) if _num(row.get("world_x_m")) else None),
            world_z=float(row.get("world_z")) if _num(row.get("world_z")) else (float(row.get("world_z_m")) if _num(row.get("world_z_m")) else None),
            yaw=float(row.get("yaw")) if _num(row.get("yaw")) else None,
        ))

    summariser = MeasuredPerformanceRecorder()
    speeds = [x.speed for x in rebuilt if _num(x.speed)]
    brakes = [x for x in rebuilt if _num(x.brake) and x.brake >= summariser.BRAKE_ON]
    full = [x for x in rebuilt if _num(x.throttle) and x.throttle >= summariser.FULL_THROTTLE]
    overlap = [x for x in rebuilt if (x.brake or 0) >= summariser.OVERLAP and (x.throttle or 0) >= summariser.OVERLAP]
    coast = [x for x in rebuilt if (x.brake or 0) < summariser.COAST_BRAKE and (x.throttle or 0) < summariser.COAST_THROTTLE]

    out = dict(lap)
    out.update({
        "sample_count": len(rebuilt),
        "min_speed_kph": min(speeds) if speeds else None,
        "max_speed_kph": max(speeds) if speeds else None,
        "brake_start_m": brakes[0].d if brakes else None,
        "brake_end_m": brakes[-1].d if brakes else None,
        "brake_distance_covered_m": len(brakes) * summariser.BIN_M,
        "peak_brake": max((x.brake for x in brakes), default=None),
        "full_throttle_first_m": full[0].d if full else None,
        "full_throttle_distance_m": len(full) * summariser.BIN_M,
        "throttle_brake_overlap_m": len(overlap) * summariser.BIN_M,
        "coasting_distance_m": len(coast) * summariser.BIN_M,
        "steering_reversals": summariser._steering_reversals(rebuilt),
        "max_abs_lateral_g": max((abs(x.g_lat) for x in rebuilt if _num(x.g_lat)), default=None),
        "max_braking_g": min((x.g_long for x in rebuilt if _num(x.g_long)), default=None),
        "gear_changes": sum(
            1 for a, b in zip(rebuilt, rebuilt[1:])
            if a.gear is not None and b.gear is not None and a.gear != b.gear
        ),
        "sections": summariser._segments(rebuilt),
        "_samples": {distance: row for distance, row in rows},
    })
    return out

def validate_reference_lap(lap: dict) -> dict:
    if not isinstance(lap, dict):
        raise ValueError("reference lap must be a JSON object")
    out = dict(lap)
    if not _num(out.get("lap_time_s")) or float(out["lap_time_s"]) <= 0:
        raise ValueError("reference lap is missing a positive lap_time_s")
    out["lap_time_s"] = float(out["lap_time_s"])
    out["_samples"] = _normalise_samples(out.get("_samples"), lap_time_s=out["lap_time_s"])
    out["valid"] = True
    out.setdefault("lap", -1)
    out.setdefault("sections", [])
    return out


def load_reference_lap(path) -> tuple[dict, dict]:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = {}
    if isinstance(payload, dict) and payload.get("format") == FORMAT:
        lap = payload.get("lap")
        meta = dict(payload.get("metadata") or {})
        meta.setdefault("source_file", str(path))
    elif isinstance(payload, dict) and "_samples" in payload:
        lap = payload
        meta = {"source_file": str(path)}
    else:
        raise ValueError(
            "unsupported reference format; use a RACE_ENGINEER_REFERENCE_LAP export "
            "with the full measured sample trace"
        )
    clean_lap = validate_reference_lap(lap)
    source = str(meta.get("source") or "").upper()
    if "TIME_TRIAL_RIVAL" in source:
        clean_lap = _sanitise_legacy_time_trial_rival(clean_lap)
    return clean_lap, meta


def choose_reference_lap(performance, lap_number: int | None = None) -> dict:
    laps = list(getattr(performance, "completed", ()) or ())
    if lap_number is not None:
        found = next((lap for lap in laps if lap.get("lap") == lap_number), None)
        if found is None:
            raise ValueError(f"completed lap {lap_number} was not found")
        if not found.get("valid"):
            raise ValueError(f"lap {lap_number} is invalid and cannot be exported as a reference")
        return found
    valid = [lap for lap in laps if lap.get("valid") and _num(lap.get("lap_time_s")) and lap.get("_samples")]
    if not valid:
        raise ValueError("no valid completed measured lap is available for reference export")
    return min(valid, key=lambda lap: lap["lap_time_s"])


def export_reference_lap(performance, path, *, lap_number: int | None = None, metadata: dict | None = None) -> dict:
    path = Path(path)
    lap = choose_reference_lap(performance, lap_number)
    payload = {
        "format": FORMAT,
        "version": VERSION,
        "metadata": dict(metadata or {}),
        "lap": lap,
    }
    payload["metadata"].setdefault("reference_lap_number", lap.get("lap"))
    payload["metadata"].setdefault("reference_lap_time_s", lap.get("lap_time_s"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
