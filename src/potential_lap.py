"""Deterministic potential-lap calculations from observed compatible laps.

No prediction is used here.  The module combines only segments/sectors that the
same driver has already completed on eligible laps.  Compatibility filtering is
conservative when weather/tyre/fuel context is available and backward compatible
for older recordings that do not carry the newer context fields.
"""
from __future__ import annotations

import math
from bisect import bisect_left
from statistics import median
from typing import Any

_SIGNATURE_CACHE: dict[tuple, dict[str, Any]] = {}
_ROWS_CACHE: dict[tuple, list[tuple[float, float]]] = {}
_CACHE_LIMIT = 128

from .data_quality import lap_quality


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _lap_key(lap: dict[str, Any]) -> tuple:
    samples=lap.get("_samples") or {}
    return (id(lap),len(samples),lap.get("sample_count"),lap.get("lap_time_s"),lap.get("lap"))


def _same_lap_object(anchor: dict[str, Any] | None, rows: list[dict[str, Any]]) -> bool:
    return isinstance(anchor,dict) and any(anchor is x for x in rows)


def _bounded_cache_put(cache: dict, key, value):
    if len(cache)>=_CACHE_LIMIT:
        try: cache.pop(next(iter(cache)))
        except StopIteration: pass
    cache[key]=value
    return value


def _valid_laps(laps):
    return [x for x in laps if isinstance(x, dict) and lap_quality(x)["eligible"]]


def _condition_class(lap: dict[str, Any]) -> str | None:
    raw = lap.get("track_condition") or lap.get("weather_name") or lap.get("weather_code")
    if raw is None:
        return None
    text = str(raw).lower()
    if any(x in text for x in ("wet", "rain", "storm", "heavy rain", "light rain")):
        return "wet"
    if any(x in text for x in ("dry", "clear", "cloud", "overcast")):
        return "dry"
    try:
        # EA weather values: 0 clear .. 5 storm.  3+ is wet-weather territory.
        return "wet" if int(raw) >= 3 else "dry"
    except Exception:
        return text or None


def _tyre_class(lap: dict[str, Any]) -> str | None:
    raw = lap.get("tyre_compound") or lap.get("visual_tyre_compound") or lap.get("actual_tyre_compound")
    if raw is None:
        return None
    text = str(raw).lower()
    if "inter" in text:
        return "intermediate"
    if "wet" in text:
        return "wet"
    if any(x in text for x in ("soft", "medium", "hard", "c1", "c2", "c3", "c4", "c5", "dry")):
        return "dry"
    return text or None


def _fuel_start(lap: dict[str, Any]) -> float | None:
    value = lap.get("fuel_start_kg")
    if _num(value):
        return float(value)
    samples = lap.get("_samples") or {}
    rows = []
    for raw_d, row in samples.items():
        if not isinstance(row, dict) or not _num(row.get("fuel")):
            continue
        try:
            d = float(row.get("d", raw_d))
        except Exception:
            continue
        rows.append((d, float(row["fuel"])))
    return min(rows)[1] if rows else None


def compatibility_signature(lap: dict[str, Any]) -> dict[str, Any]:
    key=_lap_key(lap)
    cached=_SIGNATURE_CACHE.get(key)
    if cached is not None:return cached
    value={
        "track": lap.get("track_id") if lap.get("track_id") is not None else lap.get("track_name"),
        "condition": _condition_class(lap),
        "tyre_class": _tyre_class(lap),
        "fuel_start_kg": _fuel_start(lap),
    }
    return _bounded_cache_put(_SIGNATURE_CACHE,key,value)


def _compatible_with(anchor: dict[str, Any], lap: dict[str, Any], *, fuel_tolerance_kg: float = 8.0) -> tuple[bool, list[str]]:
    a, b = compatibility_signature(anchor), compatibility_signature(lap)
    reasons: list[str] = []
    for key in ("track", "condition", "tyre_class"):
        if a.get(key) is not None and b.get(key) is not None and a[key] != b[key]:
            reasons.append(f"mismatch:{key}")
    if _num(a.get("fuel_start_kg")) and _num(b.get("fuel_start_kg")):
        if abs(float(a["fuel_start_kg"]) - float(b["fuel_start_kg"])) > fuel_tolerance_kg:
            reasons.append("mismatch:fuel_load")
    return not reasons, reasons


def compatible_laps(laps, *, anchor: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    valid = _valid_laps(laps)
    if not valid:
        return [], {"eligible_lap_count": 0, "compatible_lap_count": 0, "excluded": []}
    anchor = anchor if _same_lap_object(anchor, valid) else valid[-1]
    kept, excluded = [], []
    for lap in valid:
        ok, reasons = _compatible_with(anchor, lap)
        if ok:
            kept.append(lap)
        else:
            excluded.append({"lap": lap.get("lap"), "reasons": reasons})
    return kept, {
        "eligible_lap_count": len(valid),
        "compatible_lap_count": len(kept),
        "anchor_lap": anchor.get("lap"),
        "anchor_signature": compatibility_signature(anchor),
        "excluded": excluded,
    }


def sector_potential(laps, *, anchor: dict[str, Any] | None = None) -> dict[str, Any]:
    valid, compat = compatible_laps(laps, anchor=anchor)
    sectors = []
    for key in ("sector1_time_s", "sector2_time_s", "sector3_time_s"):
        vals = [float(x[key]) for x in valid if _num(x.get(key)) and float(x[key]) > 0]
        sectors.append(min(vals) if vals else None)
    value = sum(sectors) if all(_num(x) for x in sectors) else None
    return {"sector_times_s": sectors, "potential_lap_s": value, **compat}


def _sample_rows(lap: dict[str, Any]) -> list[tuple[float, float]]:
    key=_lap_key(lap)
    cached=_ROWS_CACHE.get(key)
    if cached is not None:return cached
    out=[]
    for raw_d,row in (lap.get("_samples") or {}).items():
        if not isinstance(row,dict):
            continue
        d=row.get("d",raw_d);t=row.get("t")
        try:d=float(d)
        except Exception:continue
        if _num(d) and _num(t):out.append((float(d),float(t)))
    out.sort()
    return _bounded_cache_put(_ROWS_CACHE,key,out)


def _sample_time_at(lap: dict[str, Any], distance_m: float) -> float | None:
    """Interpolate the observed lap clock at a physical distance."""
    rows=_sample_rows(lap)
    if not rows:return None
    d=float(distance_m)
    if d <= rows[0][0] + 1e-9:
        return rows[0][1] if abs(d-rows[0][0]) <= 15.0 else None
    track_len=lap.get("track_length_m")
    if _num(track_len) and d >= float(track_len)-1e-6 and _num(lap.get("lap_time_s")):
        return float(lap["lap_time_s"])
    xs=[x[0] for x in rows];i=bisect_left(xs,d)
    if i==len(rows):
        return rows[-1][1] if abs(rows[-1][0]-d)<=15.0 else None
    if abs(rows[i][0]-d)<=1e-9:return rows[i][1]
    lo=rows[i-1];hi=rows[i]
    if d-lo[0]>15.0 or hi[0]-d>15.0 or hi[0]<=lo[0]:return None
    ratio=(d-lo[0])/(hi[0]-lo[0])
    return lo[1]+ratio*(hi[1]-lo[1])


def _corner_boundaries(template: dict[str, Any]) -> list[tuple[int, float, float]]:
    sections=[s for s in (template.get("sections") or []) if isinstance(s,dict) and isinstance(s.get("id"),int)]
    anchors=[]
    for s in sections:
        a=s.get("min_speed_m") if _num(s.get("min_speed_m")) else s.get("start_m")
        if _num(a):anchors.append((int(s["id"]),float(a)))
    anchors.sort(key=lambda x:x[1])
    length=template.get("track_length_m")
    if not anchors or not _num(length):return []
    bounds=[0.0]+[(anchors[i-1][1]+anchors[i][1])*0.5 for i in range(1,len(anchors))]+[float(length)]
    return [(anchors[i][0],bounds[i],bounds[i+1]) for i in range(len(anchors)) if bounds[i+1]>bounds[i]]


def corner_potential(laps, *, anchor: dict[str, Any] | None = None) -> dict[str, Any]:
    """Best observed physical corner-ownership regions across compatible laps.

    Regions are mutually exclusive and span S/F to S/F using midpoint ownership
    around measured corner anchors.  This produces a complete observed
    corner-segment theoretical lap without fabricating straight time.
    """
    valid, compat = compatible_laps(laps, anchor=anchor)
    if not valid:
        return {"available": False, "potential_lap_s": None, "reason": "no_eligible_laps", **compat}
    template = anchor if _same_lap_object(anchor, valid) else valid[-1]
    boundaries=_corner_boundaries(template)
    if not boundaries:
        # Backward-compatible descriptive mode for legacy laps that contain
        # section windows but no track length. This is not promoted to a full
        # theoretical lap because the unmeasured straights are unknown.
        by_corner: dict[int, list[float]] = {}
        for lap in valid:
            for sec in lap.get("sections") or []:
                if not isinstance(sec,dict) or not isinstance(sec.get("id"),int):continue
                start,end=sec.get("start_m"),sec.get("end_m")
                if not (_num(start) and _num(end) and float(end)>float(start)):continue
                a,b=_sample_time_at(lap,float(start)),_sample_time_at(lap,float(end))
                if _num(a) and _num(b) and float(b)>float(a):by_corner.setdefault(int(sec["id"]),[]).append(float(b)-float(a))
        best={cid:min(vals) for cid,vals in by_corner.items() if vals}
        return {"available":bool(best),"potential_lap_s":None,"corner_segment_theoretical_best_s":None,
                "corner_best_times_s":best,"corner_window_sum_s":sum(best.values()) if best else None,
                "corner_count":len(best),"method":"legacy observed corner-window durations; not a full-lap theoretical",**compat}
    best_regions=[]
    complete=True
    for cid,start,end in boundaries:
        candidates=[]
        for lap in valid:
            a,b=_sample_time_at(lap,start),_sample_time_at(lap,end)
            if _num(a) and _num(b) and float(b)>float(a):
                candidates.append((float(b)-float(a),lap.get("lap")))
        if not candidates:
            complete=False
            best_regions.append({"corner_id":cid,"start_m":start,"end_m":end,"best_time_s":None,"source_lap":None})
            continue
        value,source=min(candidates,key=lambda x:x[0])
        best_regions.append({"corner_id":cid,"start_m":start,"end_m":end,"best_time_s":value,"source_lap":source})
    total=sum(float(x["best_time_s"]) for x in best_regions if _num(x.get("best_time_s"))) if complete else None
    return {
        "available": bool(complete and _num(total)),
        "potential_lap_s": total,
        "corner_segment_theoretical_best_s": total,
        "regions": best_regions,
        "corner_count": len(best_regions),
        "method": "best observed compatible S/F-partitioned corner ownership region durations",
        **compat,
    }


def potential_summary(laps, reference: dict[str, Any] | None = None, *, anchor: dict[str, Any] | None = None, include_corner_segments: bool = False) -> dict[str, Any]:
    valid, compat = compatible_laps(laps, anchor=anchor)
    best = min((x for x in valid if _num(x.get("lap_time_s"))), key=lambda x: float(x["lap_time_s"]), default=None)
    sec = sector_potential(valid, anchor=(anchor if _same_lap_object(anchor, valid) else (valid[-1] if valid else None)))
    cp = corner_potential(valid, anchor=(anchor if _same_lap_object(anchor, valid) else (valid[-1] if valid else None))) if include_corner_segments else {"available": False, "potential_lap_s": None, "reason": "deferred_to_session_report"}
    sector_pot = sec.get("potential_lap_s")
    corner_pot = cp.get("potential_lap_s")
    # Sector theoretical best is the conservative primary potential; the finer
    # corner-segment result is reported separately rather than silently replacing it.
    raw_potential = sector_pot if _num(sector_pot) else corner_pot
    best_time = float(best["lap_time_s"]) if best and _num(best.get("lap_time_s")) else None
    # A theoretical/potential lap is a lower bound assembled from observed
    # evidence. It can never be slower than an eligible lap the driver actually
    # completed. This guard also covers a just-finished best lap whose sector
    # splits arrived later than its lap time.
    potential = min(float(raw_potential), best_time) if _num(raw_potential) and _num(best_time) else raw_potential
    ref_time = float(reference["lap_time_s"]) if isinstance(reference, dict) and _num(reference.get("lap_time_s")) else None
    spread = None
    times = [float(x["lap_time_s"]) for x in valid if _num(x.get("lap_time_s"))]
    if len(times) >= 2:
        med = median(times)
        spread = median(abs(x - med) for x in times)
    gain=(best_time-potential) if _num(best_time) and _num(potential) else None
    return {
        "best_lap_s": best_time,
        "potential_lap_s": potential,
        "sector_theoretical_best_s": sector_pot,
        "sector_best_times_s": sec.get("sector_times_s"),
        "corner_segment_theoretical_best_s": corner_pot,
        "corner_segment_potential": cp,
        "potential_gain_s": gain,
        "realistic_available_gain_s": max(0.0,float(gain)) if _num(gain) else None,
        "reference_lap_s": ref_time,
        "potential_vs_reference_s": (potential - ref_time) if _num(potential) and _num(ref_time) else None,
        "lap_consistency_mad_s": spread,
        **compat,
        "potential_guarded_by_observed_best": bool(_num(raw_potential) and _num(best_time) and float(raw_potential) > float(best_time)),
        "raw_theoretical_lap_s": raw_potential,
        "method": "best of observed eligible lap and compatible observed-sector theoretical (primary), plus complete corner-ownership theoretical lap; no prediction",
    }
