"""Deterministic coaching/reference quality gates.

The gates are conservative and explain every rejection.  They affect coaching
and reference comparisons only; they never rewrite official F1 results.
"""
from __future__ import annotations

import math
from typing import Any


_LAP_QUALITY_CACHE: dict[tuple, dict[str, Any]] = {}
_LAP_QUALITY_CACHE_ORDER: list[tuple] = []
_LAP_QUALITY_CACHE_MAX = 256


def _lap_cache_key(lap: dict[str, Any]) -> tuple:
    samples=lap.get("_samples") or {}
    return (id(lap),len(samples),lap.get("sample_count"),lap.get("lap_time_s"),lap.get("valid"),
            lap.get("pit_lap"),lap.get("traffic_compromised"),lap.get("race_control_compromised"),
            lap.get("damage_compromised"),lap.get("damage_coaching_override"),lap.get("pause_compromised"),lap.get("replay_seek_detected"),
            lap.get("session_restart_detected"),lap.get("missing_packet_family"),
            lap.get("lap_start_anchored"),lap.get("track_length_m"),lap.get("track_condition"),
            lap.get("weather_name"),lap.get("weather_code"),lap.get("tyre_compound"),
            lap.get("visual_tyre_compound"),lap.get("fuel_start_kg"))


def _cache_quality(key: tuple, value: dict[str, Any]) -> dict[str, Any]:
    _LAP_QUALITY_CACHE[key]=value
    _LAP_QUALITY_CACHE_ORDER.append(key)
    if len(_LAP_QUALITY_CACHE_ORDER)>_LAP_QUALITY_CACHE_MAX:
        old=_LAP_QUALITY_CACHE_ORDER.pop(0);_LAP_QUALITY_CACHE.pop(old,None)
    return value


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _sample_rows(lap: dict[str, Any]) -> list[tuple[float, dict[str, Any]]]:
    rows=[]
    for raw_d,row in (lap.get("_samples") or {}).items():
        if not isinstance(row,dict):continue
        try:d=float(row.get("d",raw_d))
        except Exception:continue
        if math.isfinite(d):rows.append((d,row))
    rows.sort(key=lambda x:x[0])
    return rows


def _sample_quality_reasons(lap: dict[str, Any]) -> list[str]:
    rows=_sample_rows(lap)
    reasons=[]
    if not rows:return reasons
    length=lap.get("track_length_m")
    # Large internal gaps are evidence of missing telemetry/seek, not a driving issue.
    gaps=[b[0]-a[0] for a,b in zip(rows,rows[1:]) if b[0]>=a[0]]
    if gaps and max(gaps)>75.0:
        reasons.append("missing_distance_packets")
    # Reject impossible recorded samples.  450 kph leaves margin above real F1 pace.
    speeds=[r.get("speed") for _,r in rows if _num(r.get("speed"))]
    if any(float(v)<-1.0 or float(v)>450.0 for v in speeds):
        reasons.append("telemetry_outlier_speed")
    times=[(d,float(r["t"])) for d,r in rows if _num(r.get("t"))]
    if any(b[1]+0.050<a[1] for a,b in zip(times,times[1:])):
        reasons.append("lap_clock_non_monotonic")
    if _num(length):
        coverage=(rows[-1][0]-rows[0][0])/max(1.0,float(length))
        if lap.get("lap_start_anchored") is True and coverage<0.90:
            reasons.append("insufficient_distance_coverage")
    if lap.get("replay_seek_detected") is True:
        reasons.append("replay_seek")
    if lap.get("session_restart_detected") is True:
        reasons.append("session_restart")
    if lap.get("pause_compromised") is True:
        reasons.append("paused_lap")
    if lap.get("missing_packet_family") is True:
        reasons.append("missing_packet_family")
    return reasons


def lap_quality(lap: dict[str, Any] | None) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    if not isinstance(lap, dict):
        return {"eligible": False, "reasons": ["missing_lap"], "warnings": []}
    cache_key=_lap_cache_key(lap)
    cached=_LAP_QUALITY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    if lap.get("valid") is not True:
        reasons.append("invalid_lap")
    if lap.get("lap_start_anchored") is False:
        reasons.append("partial_lap")
    if int(lap.get("sample_count") or 0) < 100:
        reasons.append("insufficient_samples")
    if not _num(lap.get("lap_time_s")) or float(lap.get("lap_time_s") or 0.0) <= 0:
        reasons.append("missing_lap_time")
    if lap.get("pit_lap") is True:
        reasons.append("pit_lap")
    if lap.get("traffic_compromised") is True:
        reasons.append("traffic_compromised")
    if lap.get("race_control_compromised") is True:
        reasons.append("race_control_compromised")
    if lap.get("damage_compromised") is True:
        if lap.get("damage_coaching_override") is True:
            warnings.append("damage_coaching_override")
        else:
            reasons.append("damage_compromised")
    reasons.extend(x for x in _sample_quality_reasons(lap) if x not in reasons)
    if lap.get("tyre_compound") is None:
        warnings.append("tyre_condition_unknown")
    if not _num(lap.get("fuel_start_kg")):
        warnings.append("fuel_load_unknown")
    return _cache_quality(cache_key,{"eligible": not reasons, "reasons": reasons, "warnings": warnings})


def _condition(lap: dict[str, Any]) -> str | None:
    value=lap.get("track_condition") or lap.get("weather_name") or lap.get("weather_code")
    if value is None:return None
    text=str(value).lower()
    if any(x in text for x in ("wet","rain","storm")):return "wet"
    if any(x in text for x in ("dry","clear","cloud","overcast")):return "dry"
    try:return "wet" if int(value)>=3 else "dry"
    except Exception:return text


def reference_compatible(current: dict[str, Any] | None, reference: dict[str, Any] | None) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    cq = lap_quality(current); rq = lap_quality(reference)
    reasons.extend("current:" + x for x in cq["reasons"])
    reasons.extend("reference:" + x for x in rq["reasons"])
    if isinstance(current, dict) and isinstance(reference, dict):
        for key in ("track_id", "game_version"):
            a,b=current.get(key),reference.get(key)
            if a is not None and b is not None and a!=b:reasons.append(f"mismatch:{key}")
        a,b=current.get("track_name"),reference.get("track_name")
        if a is not None and b is not None and str(a).upper()!=str(b).upper():reasons.append("mismatch:track")
        ca,cb=_condition(current),_condition(reference)
        if ca is not None and cb is not None and ca!=cb:reasons.append("mismatch:wet_dry")
        ta=current.get("tyre_compound") or current.get("visual_tyre_compound")
        tb=reference.get("tyre_compound") or reference.get("visual_tyre_compound")
        if ta is not None and tb is not None and str(ta).lower()!=str(tb).lower():warnings.append("mismatch:tyre_compound")
        fa,fb=current.get("fuel_start_kg"),reference.get("fuel_start_kg")
        if _num(fa) and _num(fb):
            gap=abs(float(fa)-float(fb))
            if gap>8.0:warnings.append("mismatch:fuel_load_large")
            elif gap>4.0:warnings.append("mismatch:fuel_load")
    return {"eligible": not reasons, "reasons": reasons, "warnings": warnings}


def live_context_blockers(
    state, *, race_mode: bool, traffic_gap_s: float = 1.2, rear_traffic_gap_s: float = 1.0,
    now: float | None = None, stale_telemetry_s: float = 1.0, stale_lap_s: float = 2.0,
    allow_damage_coaching: bool = False,
) -> list[str]:
    """Return concrete reasons why a live coaching call should be suppressed."""
    blockers: list[str] = []
    session = getattr(state, "session", None)
    player = getattr(state, "player", None)
    lap = getattr(player, "lap", None) if player is not None else None
    damage = getattr(player, "damage", None) if player is not None else None

    if now is not None and player is not None:
        updated = getattr(player, "updated", {}) or {}
        required=(("telemetry",stale_telemetry_s),("lap",stale_lap_s))
        for family,limit in required:
            fresh=updated.get(family)
            if fresh is None:
                # Do not punish old unit-test/fallback states with no freshness map.
                continue
            try:
                if fresh.age(now)>limit:blockers.append(f"stale_{family}")
            except Exception:
                blockers.append(f"missing_{family}_freshness")
    if getattr(session, "paused", False):
        blockers.append("paused")
    sc = getattr(getattr(session, "safety_car", None), "raw", None)
    sc_name = str(getattr(getattr(session, "safety_car", None), "name", "") or "").lower()
    if (isinstance(sc, int) and sc != 0) or (sc_name and "none" not in sc_name and "no safety" not in sc_name):
        blockers.append("safety_car_or_vsc")
    if lap is not None:
        pit = str(getattr(getattr(lap, "pit_status", None), "name", "") or "").lower()
        if pit and pit not in {"none", "no pit"}:blockers.append("pit_phase")
        if getattr(lap, "lap_valid", True) is False:blockers.append("invalid_lap")
        if race_mode:
            gap = getattr(lap, "gap_to_car_in_front_s", None)
            if _num(gap) and 0.0 <= float(gap) < traffic_gap_s:
                blockers.extend(("close_traffic","close_traffic_ahead"))
            gap_behind = getattr(state, "gap_behind_s", None)
            if _num(gap_behind) and 0.0 <= float(gap_behind) < rear_traffic_gap_s:blockers.append("close_traffic_behind")
    if damage is not None:
        wing=max(int(getattr(damage,"front_left_wing_percent",0) or 0),int(getattr(damage,"front_right_wing_percent",0) or 0))
        floor=int(getattr(damage,"floor_percent",0) or 0)
        if (wing>=20 or floor>=20 or getattr(damage,"engine_blown",False) or getattr(damage,"engine_seized",False)) and not allow_damage_coaching:blockers.append("significant_damage")
    for zone in getattr(session, "marshal_zones", ()) or ():
        flag=str(getattr(getattr(zone,"flag",None),"name","") or "").lower()
        if "yellow" in flag or "red" in flag:
            blockers.append("local_flag");break
    # Preserve deterministic ordering while removing duplicates.
    return list(dict.fromkeys(blockers))
