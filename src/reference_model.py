"""V1.1.0.0 rival reference compiler and deterministic driver-event detector."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import asdict
import json
import math
import hashlib
from pathlib import Path
import re
import statistics
from typing import Any, Iterable

from .corner_coach_models import CoachingZone, DrivingEvent, PhysicalCorner, ReferenceTrace, to_dict
from .distance_performance import physical_turn_boundaries


QUALITY_VALIDATOR_VERSION = 5
CLEAN_RIVAL_PACE_COMPILER_VERSION = 2
REFERENCE_MODEL_SCHEMA_VERSION = 3
REFERENCE_COMPILER_ID = "V1.1.0.13_CLEAN_RIVAL_PACE_V2_ZONE_ASSOCIATION_V2"
CLEAN_PACE_GRID_M = 5.0
CLEAN_PACE_SMOOTH_RADIUS = 4  # triangular smoothing over ~45 m of segment pace
CLEAN_SPEED_REGRESSION_WINDOW_M = 50.0
MAX_CLEAN_DERIVED_SPEED_KPH = 380.0


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _value(row: Any, key: str):
    return row.get(key) if isinstance(row, dict) else getattr(row, key, None)


def _sample_rows(lap: dict[str, Any]) -> list[tuple[float, dict[str, Any]]]:
    rows=[]
    for raw_d, raw in (lap.get("_samples") or {}).items():
        try: d=float(raw_d)
        except (TypeError, ValueError):
            d=_value(raw,"d")
        if not _num(d):
            continue
        row=dict(raw) if isinstance(raw,dict) else asdict(raw)
        row["d"]=float(d)
        rows.append((float(d),row))
    rows.sort(key=lambda x:x[0])
    return rows


def raw_reference_fingerprint(lap: dict[str, Any], metadata: dict[str, Any] | None = None) -> str:
    """Stable identity for the trustworthy part of a saved rival recording.

    The fingerprint deliberately ignores the known-unreliable Time Trial ghost
    CarTelemetry channels.  It binds a compiled model to the exact authoritative
    distance/lap-clock/world-geometry recording that produced it.
    """
    metadata=dict(metadata or {})
    rows=_sample_rows(lap)
    trusted_rows=[]
    for d,row in rows:
        item={"d":round(float(d),6)}
        for key in ("t","world_x","world_y","world_z","yaw","pitch","roll"):
            value=row.get(key)
            if _num(value):
                item[key]=round(float(value),9)
        trusted_rows.append(item)
    identity={
        "source":str(metadata.get("source") or lap.get("source") or ""),
        "track_name":str(lap.get("track_name") or metadata.get("track_name") or metadata.get("track") or "").upper(),
        "track_length_m":float(lap.get("track_length_m") or metadata.get("track_length_m") or 0.0),
        "lap_time_s":float(lap.get("lap_time_s") or metadata.get("reference_lap_time_s") or 0.0),
        "sector1_time_s":float(metadata.get("sector1_time_s") or lap.get("sector1_time_s") or 0.0),
        "sector2_time_s":float(metadata.get("sector2_time_s") or lap.get("sector2_time_s") or 0.0),
        "sector3_time_s":float(metadata.get("sector3_time_s") or lap.get("sector3_time_s") or 0.0),
        "sample_count":len(trusted_rows),
        "samples":trusted_rows,
    }
    encoded=json.dumps(identity,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _interp_numeric_axis(xs: list[float], ys: list[float], x: float) -> float:
    """Linear interpolation on a strictly increasing numeric X axis."""
    if not xs:
        raise ValueError("empty interpolation axis")
    i=bisect_left(xs,float(x))
    if i<=0:
        return float(ys[0])
    if i>=len(xs):
        return float(ys[-1])
    x0,x1=float(xs[i-1]),float(xs[i]); y0,y1=float(ys[i-1]),float(ys[i])
    if x1<=x0:
        return y1
    f=(float(x)-x0)/(x1-x0)
    return y0+(y1-y0)*f


def _inverse_monotonic_time(rows: list[tuple[float,dict[str,Any]]], target_t: float) -> float | None:
    """Return distance at a target lap-clock time from a monotonic raw trace."""
    timed=[(float(d),float(r["t"])) for d,r in rows if _num(r.get("t"))]
    if len(timed)<2:
        return None
    times=[t for _,t in timed]
    i=bisect_left(times,float(target_t))
    if i<=0:
        return timed[0][0]
    if i>=len(timed):
        return timed[-1][0]
    d0,t0=timed[i-1]; d1,t1=timed[i]
    if t1<=t0:
        return d0
    return d0+(float(target_t)-t0)/(t1-t0)*(d1-d0)


def _clean_rival_time_curve(
    rows: list[tuple[float,dict[str,Any]]],
    length: float,
    lap_time: float,
    metadata: dict[str,Any],
    *,
    step_m: float=CLEAN_PACE_GRID_M,
) -> tuple[list[float],list[float],list[tuple[float,float]]]:
    """Build a smooth monotonic t(distance) curve anchored to official timing.

    The F1 Time Trial rival lap clock is authoritative but quantized at packet
    cadence. Differentiating 5 m bins directly creates artificial 350-400+ km/h
    spikes. We therefore smooth *segment pace* (seconds/metre), integrate it back
    into a time curve, then piecewise re-anchor that curve to the official sector
    and lap times. This preserves local pace shape without inventing ghost inputs.
    """
    if len(rows)<3 or length<=0 or lap_time<=0:
        return [],[],[]

    # Keep one row per distance and make only the minimal monotonic repair needed
    # for delayed/duplicate LapData packets. The raw file remains untouched.
    uniq=[]
    for d,row in rows:
        d=max(0.0,min(float(length),float(d)))
        if not _num(row.get("t")):
            continue
        rr=dict(row); rr["t"]=float(rr["t"])
        if uniq and abs(d-uniq[-1][0])<1e-9:
            if rr["t"]>=float(uniq[-1][1]["t"]):
                uniq[-1]=(d,rr)
        else:
            uniq.append((d,rr))
    if len(uniq)<3:
        return [],[],[]
    previous=-1e30
    monotonic=[]
    for d,row in uniq:
        rr=dict(row)
        t=max(float(rr["t"]),previous)
        rr["t"]=t; previous=t
        monotonic.append((d,rr))

    src_d=[d for d,_ in monotonic]
    # Always include an exact S/F endpoint even when the final 5 m capture bin is
    # slightly before the official track length.
    grid=[i*float(step_m) for i in range(int(math.floor(length/float(step_m)))+1)]
    if not grid or grid[-1] < length-1e-9:
        grid.append(float(length))
    elif abs(grid[-1]-length)>1e-9:
        grid[-1]=float(length)

    raw_t=[]
    for d in grid:
        i=bisect_left(src_d,d)
        if i<=0:
            value=float(monotonic[0][1]["t"])
        elif i>=len(monotonic):
            value=float(monotonic[-1][1]["t"])
        else:
            d0,r0=monotonic[i-1]; d1,r1=monotonic[i]
            t0,t1=float(r0["t"]),float(r1["t"])
            value=t0 if d1<=d0 else t0+(t1-t0)*(d-d0)/(d1-d0)
        raw_t.append(value)

    # S/F is known exactly from the completed lap. The first captured packet can
    # naturally arrive 10-50 ms after the line, so do not preserve that offset.
    raw_t[0]=0.0; raw_t[-1]=float(lap_time)
    for i in range(1,len(raw_t)):
        raw_t[i]=max(raw_t[i],raw_t[i-1]+1e-6)

    # Convert packet-quantized clock increments into seconds/metre. A wide safety
    # envelope is used only to stop single-bin packet artefacts; it is not a track-
    # specific speed target (25..390 km/h corresponds to F1 raceable extremes).
    raw_pace=[]
    min_pace=3.6/390.0; max_pace=3.6/25.0
    for i in range(len(grid)-1):
        dd=float(grid[i+1])-float(grid[i]); dt=float(raw_t[i+1])-float(raw_t[i])
        pace=(dt/dd) if dd>1e-9 else max_pace
        raw_pace.append(max(min_pace,min(max_pace,pace)))

    # Median pre-filter kills isolated quantization outliers. The triangular pass
    # then gives a differentiable-enough pace curve while retaining braking shape.
    med=[]
    for i in range(len(raw_pace)):
        lo=max(0,i-2); hi=min(len(raw_pace),i+3)
        med.append(float(statistics.median(raw_pace[lo:hi])))
    smooth=[]
    radius=CLEAN_PACE_SMOOTH_RADIUS
    for i in range(len(med)):
        lo=max(0,i-radius); hi=min(len(med),i+radius+1)
        total=0.0; weight_sum=0.0
        for j in range(lo,hi):
            weight=float(radius+1-abs(j-i))
            total += med[j]*weight; weight_sum += weight
        smooth.append(total/weight_sum if weight_sum>0 else med[i])

    provisional=[0.0]
    for i,pace in enumerate(smooth):
        provisional.append(provisional[-1]+pace*(float(grid[i+1])-float(grid[i])))

    # Infer where the official sector transitions occurred from the raw lap clock,
    # then pin the clean curve to those authoritative cumulative times. This makes
    # interpolation at the inferred sector boundary reproduce the exact stored S1/S2.
    anchors=[(0.0,0.0)]
    s1=metadata.get("sector1_time_s"); s2=metadata.get("sector2_time_s"); s3=metadata.get("sector3_time_s")
    if all(_num(x) and float(x)>0 for x in (s1,s2,s3)):
        s1=float(s1); s2=float(s2); s3=float(s3)
        d1=_inverse_monotonic_time(monotonic,s1)
        d2=_inverse_monotonic_time(monotonic,s1+s2)
        if _num(d1) and _num(d2) and 50.0<float(d1)<float(d2)-50.0 and float(d2)<length-50.0:
            anchors.extend(((float(d1),s1),(float(d2),s1+s2)))
    anchors.append((float(length),float(lap_time)))

    clean_t=[]; anchor_i=0
    for d in grid:
        while anchor_i+1<len(anchors)-1 and d>anchors[anchor_i+1][0]+1e-9:
            anchor_i+=1
        da,ta=anchors[anchor_i]; db,tb=anchors[anchor_i+1]
        qa=_interp_numeric_axis(grid,provisional,da)
        qb=_interp_numeric_axis(grid,provisional,db)
        qd=_interp_numeric_axis(grid,provisional,d)
        if qb>qa+1e-12:
            f=(qd-qa)/(qb-qa)
        else:
            f=(d-da)/(db-da) if db>da else 0.0
        clean_t.append(float(ta)+(float(tb)-float(ta))*max(0.0,min(1.0,f)))
    clean_t[0]=0.0; clean_t[-1]=float(lap_time)
    for i in range(1,len(clean_t)):
        if clean_t[i]<=clean_t[i-1]:
            clean_t[i]=clean_t[i-1]+1e-6
    clean_t[-1]=float(lap_time)
    return [float(x) for x in grid],clean_t,anchors


def _pace_speed_from_time_curve(distances: list[float], times: list[float], *, window_m: float=CLEAN_SPEED_REGRESSION_WINDOW_M) -> list[float | None]:
    """Differentiate t(distance) with a local linear fit instead of 5 m deltas."""
    out=[]; half=max(10.0,float(window_m)*0.5)
    for i,d in enumerate(distances):
        lo=bisect_left(distances,d-half); hi=bisect_left(distances,d+half)
        while hi<len(distances) and distances[hi]<=d+half+1e-9:
            hi+=1
        if hi-lo<3:
            lo=max(0,i-2); hi=min(len(distances),i+3)
        xs=distances[lo:hi]; ys=times[lo:hi]
        if len(xs)<2:
            out.append(None); continue
        mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
        den=sum((x-mx)*(x-mx) for x in xs)
        slope=(sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den) if den>1e-12 else None
        speed=(3.6/float(slope)) if _num(slope) and float(slope)>1e-7 else None
        out.append(speed if _num(speed) and 5.0<=float(speed)<=390.0 else None)
    return out


def sanitize_rival_pace_reference(lap: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compile a clean Time Trial rival *pace* reference without ghost inputs.

    Live capture/save is deliberately outside this function. The raw
    ``rival_reference.json`` is the evidence copy and is never rewritten here.
    Only the post-save model compiler calls this sanitizer.
    """
    metadata=metadata or {}
    source=str(metadata.get("source") or lap.get("source") or "").upper()
    trace_mode=str(lap.get("reference_trace_mode") or metadata.get("reference_trace_mode") or "").lower()
    if source!="EA_F1_TIME_TRIAL_RIVAL" and trace_mode!="rival_pace":
        return lap

    rows=_sample_rows(lap)
    if len(rows)<3:
        return lap
    length=lap.get("track_length_m") or metadata.get("track_length_m") or rows[-1][0]
    lap_time=lap.get("lap_time_s") or metadata.get("reference_lap_time_s")
    if not (_num(length) and float(length)>1000.0 and _num(lap_time) and float(lap_time)>0.0):
        return lap
    length=float(length); lap_time=float(lap_time)

    distances,times,anchors=_clean_rival_time_curve(rows,length,lap_time,metadata)
    if len(distances)<3 or len(times)!=len(distances):
        return lap
    speeds=_pace_speed_from_time_curve(distances,times)
    raw_distances=[d for d,_ in rows]
    trusted_geometry=("world_x","world_y","world_z","yaw")
    clean=[]
    for i,d in enumerate(distances):
        out={"d":float(d),"t":float(times[i])}
        for key in trusted_geometry:
            value=_interp(rows,raw_distances,d,key)
            if _num(value):
                out[key]=float(value)
        if i<len(speeds) and _num(speeds[i]):
            out["speed"]=float(speeds[i])
        clean.append(out)

    # Derive a stable longitudinal acceleration only from the clean pace curve.
    for i,row in enumerate(clean):
        row["g_long"]=None
        j0=max(0,i-2); j1=min(len(clean)-1,i+2)
        if j1>j0 and _num(clean[j0].get("speed")) and _num(clean[j1].get("speed")):
            dt=float(clean[j1]["t"])-float(clean[j0]["t"])
            if dt>1e-4:
                dv=(float(clean[j1]["speed"])-float(clean[j0]["speed"]))/3.6
                g=dv/dt/9.80665
                if math.isfinite(g):
                    row["g_long"]=max(-6.0,min(6.0,g))

    result=dict(lap)
    result["reference_trace_mode"]="rival_pace"
    result["input_telemetry_trusted"]=False
    result["pace_compiler_version"]=CLEAN_RIVAL_PACE_COMPILER_VERSION
    result["timing_source"]="smoothed_lap_distance_clock_sector_anchored"
    result["speed_source"]="local_regression_of_clean_time_distance_curve"
    result["pace_speed_window_m"]=CLEAN_SPEED_REGRESSION_WINDOW_M
    result["pace_anchors"]=[{"distance_m":d,"time_s":t} for d,t in anchors]
    result["_samples"]={float(r["d"]):r for r in clean}
    valid_speeds=[float(r["speed"]) for r in clean if _num(r.get("speed"))]
    if valid_speeds:
        result["min_speed_kph"]=min(valid_speeds)
        result["max_speed_kph"]=max(valid_speeds)
    # Never let old ghost pedal/gear fields leak back into a pace-only model.
    for key in (
        "brake_start_m","brake_end_m","brake_distance_covered_m","peak_brake",
        "full_throttle_first_m","full_throttle_distance_m","throttle_brake_overlap_m",
        "coasting_distance_m","steering_reversals","gear_changes","sections",
    ):
        result.pop(key,None)
    return result



def validate_capture_lap(lap: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Legacy V1.1.0.5 live-capture gate.

    This intentionally preserves the proven live Time Trial capture acceptance
    behavior.  It decides only whether a completed S/F lap is worth persisting;
    it does *not* certify the ghost telemetry as a coaching model.  The stronger
    physics/integrity validator below runs only after the raw per-track file has
    been saved.
    """
    metadata=metadata or {}
    rows=_sample_rows(lap)
    length=lap.get("track_length_m") or metadata.get("track_length_m")
    if not (_num(length) and float(length)>1000.0):
        length=max((d for d,_ in rows),default=0.0)
    length=float(length or 0.0)
    distances=[d for d,_ in rows]
    start_ok=bool(rows and distances[0] <= 20.0)
    end_ok=bool(rows and length>0 and distances[-1] >= length-max(40.0,length*0.012))
    complete=bool(start_ok and end_ok)
    valid=bool(lap.get("valid",False))
    coverage=(max(0.0,min(length,distances[-1]))-max(0.0,distances[0]))/length if rows and length>0 else 0.0
    max_gap=max((b-a for a,b in zip(distances,distances[1:])),default=float("inf"))
    continuity=bool(rows and max_gap <= 30.0)
    input_rows=sum(1 for _,r in rows if _num(r.get("brake")) and _num(r.get("throttle")) and _num(r.get("steering")))
    input_coverage=input_rows/max(1,len(rows))
    motion_rows=sum(1 for _,r in rows if _num(r.get("world_x")) and _num(r.get("world_z")))
    motion_coverage=motion_rows/max(1,len(rows))
    times=[float(r.get("t")) for _,r in rows if _num(r.get("t"))]
    timing_monotonic=all(b+0.010>=a for a,b in zip(times,times[1:])) if len(times)>=2 else False
    sample_density=(len(rows)*5.0/length) if length>0 else 0.0
    accepted=bool(valid and complete and coverage>=0.985 and continuity and input_coverage>=0.95 and motion_coverage>=0.90 and timing_monotonic and sample_density>=0.85)
    reasons=[]
    if not valid: reasons.append("invalid_lap")
    if not complete: reasons.append("not_sf_to_sf")
    if coverage<0.985: reasons.append("distance_coverage")
    if not continuity: reasons.append("packet_gap")
    if input_coverage<0.95: reasons.append("input_coverage")
    if motion_coverage<0.90: reasons.append("motion_coverage")
    if not timing_monotonic: reasons.append("timing_continuity")
    if sample_density<0.85: reasons.append("sample_density")
    return {
        "capture_validator_version":1,
        "accepted":accepted,
        "valid":valid,
        "complete_sf_to_sf":complete,
        "track_length_m":length,
        "distance_coverage":coverage,
        "max_distance_gap_m":None if not math.isfinite(max_gap) else max_gap,
        "input_coverage":input_coverage,
        "motion_coverage":motion_coverage,
        "timing_monotonic":timing_monotonic,
        "sample_density":sample_density,
        "sample_count":len(rows),
        "reasons":reasons,
    }

def validate_reference_lap(lap: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a strict quality report for a candidate reference lap.

    Time Trial rivals are pace references: EA's lap clock/distance progress and
    same-frame world geometry are trusted, while ghost CarTelemetry inputs are not.
    Every reference still has to pass distance/time/speed physics consistency so a
    mixed or fabricated trace can never be compiled as authoritative.
    """
    metadata=metadata or {}
    rows=_sample_rows(lap)
    length=lap.get("track_length_m") or metadata.get("track_length_m")
    if not (_num(length) and float(length)>1000.0):
        length=max((d for d,_ in rows),default=0.0)
    length=float(length or 0.0)
    distances=[d for d,_ in rows]
    start_ok=bool(rows and distances[0] <= 20.0)
    end_ok=bool(rows and length>0 and distances[-1] >= length-max(40.0,length*0.012))
    complete=bool(start_ok and end_ok)
    valid=bool(lap.get("valid",False))
    coverage=(max(0.0,min(length,distances[-1]))-max(0.0,distances[0]))/length if rows and length>0 else 0.0
    max_gap=max((b-a for a,b in zip(distances,distances[1:])),default=float("inf"))
    continuity=bool(rows and max_gap <= 30.0)

    source=str(metadata.get("source") or lap.get("source") or "").upper()
    trace_mode=str(lap.get("reference_trace_mode") or metadata.get("reference_trace_mode") or "").lower()
    rival_pace=trace_mode=="rival_pace" or source=="EA_F1_TIME_TRIAL_RIVAL"
    input_rows=sum(1 for _,r in rows if _num(r.get("brake")) and _num(r.get("throttle")) and _num(r.get("steering")))
    input_coverage=input_rows/max(1,len(rows))
    input_required=not rival_pace
    input_trusted=bool(not rival_pace and input_coverage>=0.95)

    motion_rows=sum(1 for _,r in rows if _num(r.get("world_x")) and _num(r.get("world_z")))
    motion_coverage=motion_rows/max(1,len(rows))
    times=[float(r.get("t")) for _,r in rows if _num(r.get("t"))]
    timing_monotonic=all(b+0.010>=a for a,b in zip(times,times[1:])) if len(times)>=2 else False
    positive_steps=sum(1 for a,b in zip(times,times[1:]) if b>a+1e-6)
    timing_progress_ratio=positive_steps/max(1,len(times)-1)
    lap_time=lap.get("lap_time_s") or metadata.get("reference_lap_time_s")
    lap_time=float(lap_time) if _num(lap_time) and float(lap_time)>0 else None
    time_span=(times[-1]-times[0]) if len(times)>=2 else None
    lap_clock_error_ratio=(abs(float(time_span)-lap_time)/lap_time) if _num(time_span) and lap_time else None
    lap_clock_consistent=bool(lap_clock_error_ratio is not None and lap_clock_error_ratio<=0.06)

    # Physics consistency: integrate the stored speed over the measured lap clock
    # and independently integrate distance/speed back into a lap time. This catches
    # the exact failure where rival timing belongs to one trace and speed/inputs to
    # another. A generous 18% bound tolerates coarse legacy 5 m references.
    speed_distance=0.0; speed_time=0.0; speed_distance_covered=0.0
    speed_segments=0; usable_segments=0
    for (d0,r0),(d1,r1) in zip(rows,rows[1:]):
        if not (_num(r0.get("t")) and _num(r1.get("t"))):
            continue
        dt=float(r1["t"])-float(r0["t"]); dd=float(d1)-float(d0)
        if dt<=0 or dd<=0:
            continue
        usable_segments+=1
        v0=r0.get("speed"); v1=r1.get("speed")
        if not (_num(v0) and _num(v1)):
            continue
        vavg=(float(v0)+float(v1))*0.5/3.6
        if vavg<=1.0:
            continue
        speed_segments+=1
        speed_distance += vavg*dt
        speed_time += dd/vavg
        speed_distance_covered += dd
    speed_coverage=speed_segments/max(1,usable_segments)
    speed_distance_error_ratio=(abs(speed_distance-length)/length) if length>0 and speed_coverage>=0.80 else None
    speed_time_error_ratio=(abs(speed_time-lap_time)/lap_time) if lap_time and speed_coverage>=0.80 and speed_distance_covered>=length*0.90 else None
    speed_distance_consistent=bool(speed_distance_error_ratio is not None and speed_distance_error_ratio<=0.18)
    speed_time_consistent=bool(speed_time_error_ratio is not None and speed_time_error_ratio<=0.18)
    speed_consistent=bool(speed_distance_consistent and speed_time_consistent)

    pace_compiler_version=int(lap.get("pace_compiler_version") or 0) if str(lap.get("pace_compiler_version") or "").isdigit() else 0
    clean_pace=bool(rival_pace and pace_compiler_version>=CLEAN_RIVAL_PACE_COMPILER_VERSION)
    derived_speeds=[float(r.get("speed")) for _,r in rows if _num(r.get("speed"))]
    derived_speed_min=min(derived_speeds) if derived_speeds else None
    derived_speed_max=max(derived_speeds) if derived_speeds else None
    derived_speed_sane=bool(derived_speeds and derived_speed_min>=20.0 and derived_speed_max<=MAX_CLEAN_DERIVED_SPEED_KPH) if clean_pace else True
    clean_physics=bool(
        speed_distance_error_ratio is not None and speed_time_error_ratio is not None and
        speed_distance_error_ratio<=0.03 and speed_time_error_ratio<=0.03
    ) if clean_pace else True
    pace_anchors=[dict(x) for x in (lap.get("pace_anchors") or ()) if isinstance(x,dict) and _num(x.get("distance_m")) and _num(x.get("time_s"))]
    anchor_errors=[]
    if clean_pace and pace_anchors and rows:
        row_ds=[d for d,_ in rows]
        for anchor in pace_anchors:
            target_d=float(anchor["distance_m"]); target_t=float(anchor["time_s"])
            i=bisect_left(row_ds,target_d)
            if i<=0:
                actual=float(rows[0][1]["t"]) if _num(rows[0][1].get("t")) else None
            elif i>=len(rows):
                actual=float(rows[-1][1]["t"]) if _num(rows[-1][1].get("t")) else None
            else:
                d0,r0=rows[i-1]; d1,r1=rows[i]
                t0=r0.get("t"); t1=r1.get("t")
                actual=(float(t0)+(float(t1)-float(t0))*(target_d-d0)/(d1-d0)) if _num(t0) and _num(t1) and d1>d0 else None
            if _num(actual):
                anchor_errors.append(abs(float(actual)-target_t))
    anchor_max_error=max(anchor_errors) if anchor_errors else (0.0 if not clean_pace else None)
    anchors_consistent=bool(anchor_max_error is not None and anchor_max_error<=0.010) if clean_pace else True

    sample_density=(len(rows)*5.0/length) if length>0 else 0.0
    # Rival pace validity is about S/F-complete distance/time physics. Physical
    # geometry is a separate authority: it may come from captured rival Motion or
    # from the already learned per-track map. Do not discard a good rival pace lap
    # merely because Motion packet-family alignment was sparse. Model compilation
    # below still requires a complete physical-corner authority before MODEL READY.
    motion_required=not rival_pace
    accepted=bool(
        valid and complete and coverage>=0.985 and continuity and
        (not input_required or input_coverage>=0.95) and
        (not motion_required or motion_coverage>=0.90) and
        timing_monotonic and lap_clock_consistent and
        speed_consistent and clean_physics and derived_speed_sane and anchors_consistent and
        sample_density>=0.85
    )
    reasons=[]
    if not valid: reasons.append("invalid_lap")
    if not complete: reasons.append("not_sf_to_sf")
    if coverage<0.985: reasons.append("distance_coverage")
    if not continuity: reasons.append("packet_gap")
    if input_required and input_coverage<0.95: reasons.append("input_coverage")
    if motion_required and motion_coverage<0.90: reasons.append("motion_coverage")
    if not timing_monotonic: reasons.append("timing_continuity")
    if not lap_clock_consistent: reasons.append("lap_clock_mismatch")
    if not speed_consistent: reasons.append("speed_time_distance_mismatch")
    if clean_pace and not clean_physics: reasons.append("clean_pace_physics")
    if clean_pace and not derived_speed_sane: reasons.append("derived_speed_sanity")
    if clean_pace and not anchors_consistent: reasons.append("timing_anchor_mismatch")
    if sample_density<0.85: reasons.append("sample_density")
    return {
        "quality_validator_version":QUALITY_VALIDATOR_VERSION,
        "accepted":accepted,
        "valid":valid,
        "complete_sf_to_sf":complete,
        "track_length_m":length,
        "reference_trace_mode":"rival_pace" if rival_pace else (trace_mode or "full_inputs"),
        "input_telemetry_trusted":input_trusted,
        "input_coverage_required":input_required,
        "distance_coverage":coverage,
        "max_distance_gap_m":None if not math.isfinite(max_gap) else max_gap,
        "input_coverage":input_coverage,
        "motion_coverage":motion_coverage,
        "motion_required":motion_required,
        "timing_monotonic":timing_monotonic,
        "timing_progress_ratio":timing_progress_ratio,
        "lap_clock_span_s":time_span,
        "lap_clock_error_ratio":lap_clock_error_ratio,
        "speed_coverage":speed_coverage,
        "speed_distance_integral_m":speed_distance if speed_segments else None,
        "speed_distance_error_ratio":speed_distance_error_ratio,
        "speed_implied_lap_time_s":speed_time if speed_segments else None,
        "speed_time_error_ratio":speed_time_error_ratio,
        "speed_time_distance_consistent":speed_consistent,
        "pace_compiler_version":pace_compiler_version if clean_pace else None,
        "timing_source":lap.get("timing_source") if clean_pace else None,
        "speed_source":lap.get("speed_source") if clean_pace else None,
        "pace_speed_window_m":lap.get("pace_speed_window_m") if clean_pace else None,
        "pace_anchors":pace_anchors if clean_pace else [],
        "timing_anchor_max_error_s":anchor_max_error,
        "derived_speed_min_kph":derived_speed_min,
        "derived_speed_max_kph":derived_speed_max,
        "derived_speed_sane":derived_speed_sane,
        "clean_pace_physics_consistent":clean_physics,
        "sample_density":sample_density,
        "sample_count":len(rows),
        "reasons":reasons,
    }


def _interp(rows: list[tuple[float,dict[str,Any]]], distances: list[float], target: float, key: str):
    i=bisect_left(distances,target)
    if i<=0:
        return rows[0][1].get(key)
    if i>=len(rows):
        return rows[-1][1].get(key)
    d0,r0=rows[i-1]; d1,r1=rows[i]
    a=r0.get(key); b=r1.get(key)
    if key in {"gear","drs"}:
        return a if target-d0 <= d1-target else b
    if _num(a) and _num(b) and d1>d0:
        f=(target-d0)/(d1-d0)
        return float(a)+(float(b)-float(a))*f
    return a if a is not None else b


def normalize_reference_lap(lap: dict[str,Any], metadata: dict[str,Any] | None=None, *, step_m: float=5.0) -> tuple[dict[str,Any],...]:
    metadata=metadata or {}
    rows=_sample_rows(lap)
    if len(rows)<2:
        return ()
    length=lap.get("track_length_m") or metadata.get("track_length_m") or rows[-1][0]
    if not (_num(length) and float(length)>0):
        return ()
    length=float(length)
    distances=[d for d,_ in rows]
    source=str(metadata.get("source") or "").upper()
    trace_mode=str(lap.get("reference_trace_mode") or metadata.get("reference_trace_mode") or "").lower()
    rival_pace=trace_mode=="rival_pace" or source=="EA_F1_TIME_TRIAL_RIVAL"
    fields=("t","speed","g_long","world_x","world_y","world_z","yaw") if rival_pace else ("t","speed","throttle","brake","steering","gear","rpm","ers_j","g_lat","g_long","world_x","world_y","world_z","yaw","drs")
    out=[]
    d=0.0
    while d <= length + 1e-6:
        row={"d":round(min(d,length),3)}
        for key in fields:
            value=_interp(rows,distances,min(d,length),key)
            if value is not None:
                row[key]=value
        out.append(row)
        d+=step_m
    if out and float(out[-1]["d"]) < length-1e-6:
        row={"d":round(length,3)}
        for key in fields:
            value=_interp(rows,distances,length,key)
            if value is not None:
                row[key]=value
        out.append(row)
    return tuple(out)


def _event_regions(samples: tuple[dict[str,Any],...], predicate, *, min_span_m:float=10.0) -> list[tuple[int,int]]:
    regions=[]; start=None
    for i,row in enumerate(samples):
        if predicate(row):
            if start is None:start=i
        elif start is not None:
            if float(samples[i-1]["d"])-float(samples[start]["d"])>=min_span_m:
                regions.append((start,i-1))
            start=None
    if start is not None and float(samples[-1]["d"])-float(samples[start]["d"])>=min_span_m:
        regions.append((start,len(samples)-1))
    return regions


def detect_driving_events(samples: tuple[dict[str,Any],...]) -> tuple[DrivingEvent,...]:
    """Detect reference-driver events independently from physical corner numbering.

    These are *driver actions*, not public turn IDs.  They can later map many-to-
    many onto physical corners when the hybrid CoachingZone builder runs.
    """
    events=[]; serial=1
    brake_regions=_event_regions(samples,lambda r:_num(r.get("brake")) and float(r["brake"])>=0.10,min_span_m=10.0)
    for a,b in brake_regions:
        block=samples[a:b+1]
        peak=max(block,key=lambda r:float(r.get("brake") or 0.0))
        events.append(DrivingEvent(f"E{serial}","brake",float(block[0]["d"]),float(block[-1]["d"]),float(peak["d"]),float(peak.get("brake") or 0.0),confidence=1.0));serial+=1
        # Explicit release point makes phase matching clearer without creating a
        # fake corner. It remains attached to the parent brake event by metadata.
        events.append(DrivingEvent(f"E{serial}","brake_release",float(block[-1]["d"]),float(block[-1]["d"]),float(block[-1]["d"]),float(block[-1].get("brake") or 0.0),confidence=0.95,metadata={"brake_start_m":float(block[0]["d"])}));serial+=1

    # Time Trial rival ghosts do not provide trustworthy driver inputs. For those
    # pace references, infer approach/recovery events strictly from the derived
    # distance-time speed trace. These are deliberately named as kinematic events
    # so the UI/voice never claims we measured the rival's pedal application.
    if not brake_regions:
        decel_regions=_event_regions(samples,lambda r:_num(r.get("g_long")) and float(r["g_long"])<=-0.18,min_span_m=10.0)
        for a,b in decel_regions:
            block=samples[a:b+1]
            peak=min(block,key=lambda r:float(r.get("g_long") or 0.0))
            events.append(DrivingEvent(f"E{serial}","deceleration",float(block[0]["d"]),float(block[-1]["d"]),float(peak["d"]),float(peak.get("g_long") or 0.0),confidence=0.82,metadata={"inferred_from":"lap_distance_time"}));serial+=1
        recovery_regions=_event_regions(samples,lambda r:_num(r.get("g_long")) and float(r["g_long"])>=0.10,min_span_m=15.0)
        for a,b in recovery_regions:
            block=samples[a:b+1]
            peak=max(block,key=lambda r:float(r.get("g_long") or 0.0))
            events.append(DrivingEvent(f"E{serial}","acceleration_recovery",float(block[0]["d"]),float(block[-1]["d"]),float(peak["d"]),float(peak.get("g_long") or 0.0),confidence=0.78,metadata={"inferred_from":"lap_distance_time"}));serial+=1

    steer_regions=_event_regions(samples,lambda r:_num(r.get("steering")) and abs(float(r["steering"]))>=0.08,min_span_m=10.0)
    for a,b in steer_regions:
        block=samples[a:b+1]
        peak=max(block,key=lambda r:abs(float(r.get("steering") or 0.0)))
        val=float(peak.get("steering") or 0.0)
        direction="RIGHT" if val>0 else "LEFT"
        events.append(DrivingEvent(f"E{serial}","steering",float(block[0]["d"]),float(block[-1]["d"]),float(peak["d"]),abs(val),direction=direction,confidence=0.95));serial+=1

    # Steering sign reversals are independent point events and are crucial for
    # chicanes/esses where one braking event covers several physical corners.
    last=None
    for row in samples:
        v=row.get("steering")
        if not _num(v) or abs(float(v))<0.08:
            continue
        sign=1 if float(v)>0 else -1
        if last is not None and sign!=last[0] and float(row["d"])-last[1] <= 120.0:
            events.append(DrivingEvent(f"E{serial}","steering_reversal",float(row["d"]),float(row["d"]),float(row["d"]),abs(float(v)),direction="RIGHT" if sign>0 else "LEFT",confidence=0.90));serial+=1
        last=(sign,float(row["d"]))

    lift_regions=_event_regions(samples,lambda r:_num(r.get("throttle")) and float(r["throttle"])<=0.85 and (not _num(r.get("brake")) or float(r.get("brake") or 0.0)<0.10),min_span_m=10.0)
    for a,b in lift_regions:
        block=samples[a:b+1]
        minimum=min(block,key=lambda r:float(r.get("throttle") or 0.0))
        events.append(DrivingEvent(f"E{serial}","lift",float(block[0]["d"]),float(block[-1]["d"]),float(minimum["d"]),float(minimum.get("throttle") or 0.0),confidence=0.85));serial+=1

    # First meaningful throttle re-application after a low-throttle/braking
    # state. This is the reference pickup point used by exit coaching.
    last_throttle=None
    low_seen=False
    for row in samples:
        value=row.get("throttle")
        if not _num(value):
            continue
        throttle=float(value)
        brake=float(row.get("brake") or 0.0) if _num(row.get("brake")) else 0.0
        if throttle<=0.12 or brake>=0.10:
            low_seen=True
        if low_seen and throttle>=0.20 and (last_throttle is None or last_throttle<0.20) and brake<0.10:
            d=float(row["d"])
            events.append(DrivingEvent(f"E{serial}","throttle_pickup",d,d,d,throttle,confidence=0.95));serial+=1
            low_seen=False
        last_throttle=throttle

    throttle_regions=_event_regions(samples,lambda r:_num(r.get("throttle")) and float(r["throttle"])>=0.98 and (not _num(r.get("brake")) or float(r.get("brake") or 0.0)<0.05),min_span_m=15.0)
    for a,b in throttle_regions:
        block=samples[a:b+1]
        events.append(DrivingEvent(f"E{serial}","full_throttle",float(block[0]["d"]),float(block[-1]["d"]),float(block[0]["d"]),1.0,confidence=0.95));serial+=1

    # Geometry-independent local speed minima. Keep only clear minima separated
    # by at least 30 m so packet noise does not create dozens of pseudo-events.
    last_min_d=-1e9
    for i in range(2,max(2,len(samples)-2)):
        row=samples[i]; speed=row.get("speed")
        if not _num(speed):
            continue
        neighbours=[samples[j].get("speed") for j in (i-2,i-1,i+1,i+2)]
        if not all(_num(v) for v in neighbours):
            continue
        s=float(speed); d=float(row["d"])
        if s<=min(float(v) for v in neighbours) and max(float(v) for v in neighbours)-s>=2.0 and d-last_min_d>=30.0:
            events.append(DrivingEvent(f"E{serial}","minimum_speed",d,d,d,s,confidence=0.80));serial+=1;last_min_d=d

    events.sort(key=lambda e:(e.start_m,e.end_m,e.kind))
    # Re-number after chronological sort so IDs remain stable and readable.
    return tuple(DrivingEvent(f"E{i}",e.kind,e.start_m,e.end_m,e.peak_m,e.peak_value,e.direction,e.confidence,e.metadata) for i,e in enumerate(events,1))


def detect_pace_events(samples: tuple[dict[str,Any],...], corners: tuple[PhysicalCorner,...]) -> tuple[DrivingEvent,...]:
    """Build one compact set of kinematic events per physical corner.

    Rival ghost pedal/gear channels are not trustworthy, so these events describe
    what the rival *car pace* did (slowdown, minimum speed, acceleration recovery),
    never what pedal the rival driver pressed.
    """
    if not samples or not corners:
        return ()
    ordered=tuple(sorted(samples,key=lambda r:float(r.get("d",0.0))))
    events=[]
    sorted_corners=tuple(sorted(corners,key=lambda c:c.apex_m))

    def rows_between(lo,hi):
        return [r for r in ordered if _num(r.get("d")) and lo<=float(r["d"])<=hi and _num(r.get("speed"))]

    def sustained(rows,predicate,min_count=2):
        run=[]
        for r in rows:
            if predicate(r):
                run.append(r)
                if len(run)>=min_count:return run[0]
            else:
                run=[]
        return None

    for i,c in enumerate(sorted_corners):
        prev_end=sorted_corners[i-1].end_m if i>0 else 0.0
        next_start=sorted_corners[i+1].start_m if i+1<len(sorted_corners) else float(ordered[-1].get("d",c.end_m))
        approach_lo=max(prev_end,float(c.start_m)-260.0)
        exit_hi=min(next_start,float(c.end_m)+140.0)
        corner_rows=rows_between(float(c.start_m),float(c.end_m))
        if not corner_rows:
            continue
        min_row=min(corner_rows,key=lambda r:float(r["speed"]))
        min_d=float(min_row["d"]); min_speed=float(min_row["speed"])

        approach=rows_between(approach_lo,min_d)
        decel_start=sustained(approach,lambda r:_num(r.get("g_long")) and float(r["g_long"])<=-0.18,2)
        if decel_start is None and approach:
            peak=max(approach,key=lambda r:float(r["speed"]))
            peak_i=approach.index(peak); threshold=float(peak["speed"])-max(6.0,float(peak["speed"])*0.035)
            decel_start=sustained(approach[peak_i+1:],lambda r:float(r["speed"])<=threshold,2)
        if decel_start is not None:
            ds=float(decel_start["d"]); block=[r for r in approach if ds<=float(r["d"])<=min_d]
            peak=min(block,key=lambda r:float(r.get("g_long") or 0.0)) if block else decel_start
            events.append(DrivingEvent("","deceleration",ds,min_d,float(peak["d"]),float(peak.get("g_long") or 0.0),confidence=0.86,metadata={"inferred_from":"lap_distance_time","corner_id":c.corner_id}))

        events.append(DrivingEvent("","minimum_speed",min_d,min_d,min_d,min_speed,confidence=0.94,metadata={"inferred_from":"lap_distance_time","corner_id":c.corner_id}))

        exit_rows=rows_between(min_d,exit_hi)
        recovery=sustained(exit_rows,lambda r:_num(r.get("g_long")) and float(r["g_long"])>=0.10,2)
        if recovery is not None:
            rd=float(recovery["d"]); tail=[r for r in exit_rows if float(r["d"])>=rd]
            peak=max(tail[:max(1,min(12,len(tail)))],key=lambda r:float(r.get("g_long") or 0.0)) if tail else recovery
            events.append(DrivingEvent("","acceleration_recovery",rd,rd,float(peak["d"]),float(peak.get("g_long") or 0.0),confidence=0.80,metadata={"inferred_from":"lap_distance_time","corner_id":c.corner_id}))

    events.sort(key=lambda e:(e.start_m,e.end_m,e.kind))
    return tuple(DrivingEvent(f"E{i}",e.kind,e.start_m,e.end_m,e.peak_m,e.peak_value,e.direction,e.confidence,e.metadata) for i,e in enumerate(events,1))


def physical_corners_from_reference(lap: dict[str,Any], track_name: str | None=None) -> tuple[PhysicalCorner,...]:
    resolved_track=track_name or lap.get("track_name")
    # Prefer the shared adaptive physical-track authority when it exists.  This
    # keeps map markers, live feedback, reference compilation and review on the
    # same T1..Tn/apex model.  A reference lap is still used for driving events.
    try:
        from .track_geometry import persisted_physical_turns
        persisted=persisted_physical_turns(resolved_track,lap.get("track_length_m"))
    except Exception:
        persisted=()
    source=persisted or physical_turn_boundaries(lap,track_name=resolved_track)
    rows=[]
    for raw in source:
        if not all(_num(raw.get(k)) for k in ("start_m","apex_m","end_m")):
            continue
        cid=int(raw.get("corner_id") or len(rows)+1)
        rows.append(PhysicalCorner(cid,str(raw.get("label") or f"T{cid}"),float(raw["start_m"]),float(raw["apex_m"]),float(raw["end_m"]),str(raw.get("turn_direction")) if raw.get("turn_direction") else None,float(raw["curvature_score"]) if _num(raw.get("curvature_score")) else None))
    return tuple(rows)


def _safe_name(name: str) -> str:
    value=re.sub(r"[^A-Za-z0-9._-]+","_",str(name).strip().upper()).strip("_")
    return value or "UNKNOWN_TRACK"


def compile_reference_model(lap: dict[str,Any], metadata: dict[str,Any] | None=None, *, track_name: str | None=None, step_m:float=5.0, require_quality:bool=True) -> ReferenceTrace:
    metadata=dict(metadata or {})
    raw_lap=lap
    fingerprint=raw_reference_fingerprint(raw_lap,metadata)
    lap=sanitize_rival_pace_reference(raw_lap,metadata)
    track_name=str(track_name or lap.get("track_name") or metadata.get("track_name") or metadata.get("track") or "UNKNOWN").upper()
    quality=validate_reference_lap(lap,metadata)
    metadata=dict(metadata)
    metadata["reference_model_schema_version"]=REFERENCE_MODEL_SCHEMA_VERSION
    metadata["reference_compiler_id"]=REFERENCE_COMPILER_ID
    metadata["raw_reference_fingerprint"]=fingerprint
    quality=dict(quality)
    quality["reference_model_schema_version"]=REFERENCE_MODEL_SCHEMA_VERSION
    quality["reference_compiler_id"]=REFERENCE_COMPILER_ID
    quality["raw_reference_fingerprint"]=fingerprint
    if require_quality and not quality["accepted"]:
        raise ValueError("reference lap failed quality validation: "+", ".join(quality["reasons"]))
    samples=normalize_reference_lap(lap,metadata,step_m=step_m)
    corners=physical_corners_from_reference(lap,track_name)
    try:
        from .track_geometry import expected_turn_count
        expected=expected_turn_count(track_name)
    except Exception:
        expected=None
    quality["physical_corner_count"]=len(corners)
    quality["expected_physical_corner_count"]=expected
    quality["corner_segmentation_complete"]=(bool(corners) and (not isinstance(expected,int) or expected<=0 or len(corners)==expected))
    if corners:
        qvals=[]
        try:
            bounds=physical_turn_boundaries(lap,track_name=track_name)
            qvals=[float(x.get("segmentation_quality")) for x in bounds if isinstance(x,dict) and _num(x.get("segmentation_quality"))]
        except Exception:
            qvals=[]
        quality["corner_segmentation_confidence"]=(sum(qvals)/len(qvals) if qvals else (0.80 if quality["corner_segmentation_complete"] else 0.45))
    else:
        quality["corner_segmentation_confidence"]=0.0
    # Pace-only rival references cannot safely fall back to braking-section IDs;
    # fail closed until measured/stored physical geometry for the circuit exists.
    if require_quality and quality.get("input_telemetry_trusted") is False:
        if not corners:
            raise ValueError("reference pace is valid but physical track geometry is not ready")
        if isinstance(expected,int) and expected>0 and len(corners)!=expected:
            raise ValueError(f"physical corner model incomplete: expected {expected}, got {len(corners)}")
    events=(detect_pace_events(samples,corners) if quality.get("input_telemetry_trusted") is False else detect_driving_events(samples))
    length=float(quality.get("track_length_m") or (samples[-1]["d"] if samples else 0.0))
    lap_time=float(lap.get("lap_time_s") or metadata.get("reference_lap_time_s") or 0.0)
    # Import lazily to keep the compiler independent enough for unit tests.
    from .coaching_zones import build_coaching_zones
    zones=build_coaching_zones(corners,events,samples,track_length_m=length)
    return ReferenceTrace(track_name,length,lap_time,float(step_m),samples,corners,events,zones,metadata,quality)


def reference_trace_from_dict(payload: dict[str, Any]) -> ReferenceTrace:
    """Rehydrate a compiled ``ReferenceTrace`` without re-analysing the raw lap.

    The compiled model is the normal CORNER COACH runtime format. Raw rival
    recordings remain source material and are only needed when the model is
    rebuilt.
    """
    if not isinstance(payload, dict):
        raise ValueError("compiled reference model must be a JSON object")
    corners=[]
    for row in payload.get("physical_corners") or ():
        if not isinstance(row,dict):
            continue
        corners.append(PhysicalCorner(
            int(row["corner_id"]), str(row.get("label") or f"T{row['corner_id']}"),
            float(row["start_m"]), float(row["apex_m"]), float(row["end_m"]),
            row.get("direction"), float(row["curvature_score"]) if _num(row.get("curvature_score")) else None,
        ))
    events=[]
    for row in payload.get("driving_events") or ():
        if not isinstance(row,dict):
            continue
        events.append(DrivingEvent(
            str(row["event_id"]), str(row["kind"]), float(row["start_m"]), float(row["end_m"]),
            float(row["peak_m"]) if _num(row.get("peak_m")) else None,
            float(row["peak_value"]) if _num(row.get("peak_value")) else None,
            row.get("direction"), float(row.get("confidence",1.0)), dict(row.get("metadata") or {}),
        ))
    zones=[]
    for row in payload.get("coaching_zones") or ():
        if not isinstance(row,dict):
            continue
        zones.append(CoachingZone(
            zone_id=str(row["zone_id"]), start_m=float(row["start_m"]), end_m=float(row["end_m"]),
            approach_start_m=float(row["approach_start_m"]), corner_ids=tuple(int(x) for x in (row.get("corner_ids") or ())),
            event_ids=tuple(str(x) for x in (row.get("event_ids") or ())),
            brake_start_m=float(row["brake_start_m"]) if _num(row.get("brake_start_m")) else None,
            brake_release_m=float(row["brake_release_m"]) if _num(row.get("brake_release_m")) else None,
            apex_m=float(row["apex_m"]) if _num(row.get("apex_m")) else None,
            throttle_start_m=float(row["throttle_start_m"]) if _num(row.get("throttle_start_m")) else None,
            full_throttle_m=float(row["full_throttle_m"]) if _num(row.get("full_throttle_m")) else None,
            reference_min_speed_kph=float(row["reference_min_speed_kph"]) if _num(row.get("reference_min_speed_kph")) else None,
            reference_apex_speed_kph=float(row["reference_apex_speed_kph"]) if _num(row.get("reference_apex_speed_kph")) else None,
            reference_exit_speed_kph=float(row["reference_exit_speed_kph"]) if _num(row.get("reference_exit_speed_kph")) else None,
            reference_gear=int(row["reference_gear"]) if _num(row.get("reference_gear")) else None,
            label=str(row.get("label") or ""), confidence=float(row.get("confidence",1.0)),
        ))
    samples=tuple(dict(x) for x in (payload.get("samples") or ()) if isinstance(x,dict))
    track_name=str(payload.get("track_name") or "UNKNOWN").upper()
    length=float(payload.get("track_length_m") or 0.0)
    lap_time=float(payload.get("lap_time_s") or 0.0)
    step=float(payload.get("step_m") or 5.0)
    if not samples or length<=0:
        raise ValueError("compiled reference model is incomplete")
    return ReferenceTrace(track_name,length,lap_time,step,samples,tuple(corners),tuple(events),tuple(zones),dict(payload.get("metadata") or {}),dict(payload.get("quality") or {}))


def _assert_current_rival_model(model: ReferenceTrace, *, expected_fingerprint: str | None = None) -> None:
    """Fail closed if a rival model was not produced by this compiler build."""
    source=str(model.metadata.get("source") or "").upper()
    trace_mode=str(model.quality.get("reference_trace_mode") or model.metadata.get("reference_trace_mode") or "").lower()
    if source!="EA_F1_TIME_TRIAL_RIVAL" and trace_mode!="rival_pace":
        return
    try:
        validator_version=int(model.quality.get("quality_validator_version") or 0)
    except (TypeError,ValueError):
        validator_version=0
    try:
        pace_version=int(model.quality.get("pace_compiler_version") or 0)
    except (TypeError,ValueError):
        pace_version=0
    try:
        schema_version=int(model.quality.get("reference_model_schema_version") or model.metadata.get("reference_model_schema_version") or 0)
    except (TypeError,ValueError):
        schema_version=0
    compiler_id=str(model.quality.get("reference_compiler_id") or model.metadata.get("reference_compiler_id") or "")
    fingerprint=str(model.quality.get("raw_reference_fingerprint") or model.metadata.get("raw_reference_fingerprint") or "")
    if pace_version < CLEAN_RIVAL_PACE_COMPILER_VERSION:
        raise ValueError("compiled rival reference predates clean pace compiler; rebuild from rival_reference.json")
    if pace_version != CLEAN_RIVAL_PACE_COMPILER_VERSION:
        raise ValueError(f"compiled rival reference pace compiler mismatch: expected {CLEAN_RIVAL_PACE_COMPILER_VERSION}, got {pace_version}")
    if validator_version != QUALITY_VALIDATOR_VERSION:
        raise ValueError(f"compiled rival reference validator mismatch: expected {QUALITY_VALIDATOR_VERSION}, got {validator_version or 'missing'}")
    if schema_version != REFERENCE_MODEL_SCHEMA_VERSION:
        raise ValueError(f"compiled rival reference schema mismatch: expected {REFERENCE_MODEL_SCHEMA_VERSION}, got {schema_version or 'missing'}")
    if compiler_id != REFERENCE_COMPILER_ID:
        raise ValueError(f"compiled rival reference compiler id mismatch: expected {REFERENCE_COMPILER_ID}, got {compiler_id or 'missing'}")
    if expected_fingerprint is not None and fingerprint != expected_fingerprint:
        raise ValueError("compiled rival reference does not match sibling rival_reference.json")
    if not model.samples:
        raise ValueError("compiled rival reference has no samples")
    first,last=model.samples[0],model.samples[-1]
    if not (_num(first.get("d")) and _num(first.get("t")) and abs(float(first["d"]))<=1e-6 and abs(float(first["t"]))<=1e-6):
        raise ValueError("compiled rival reference does not start at S/F origin")
    if not (_num(last.get("d")) and abs(float(last["d"])-float(model.track_length_m))<=1e-3):
        raise ValueError("compiled rival reference does not end at exact track length")
    if not (_num(last.get("t")) and abs(float(last["t"])-float(model.lap_time_s))<=1e-3):
        raise ValueError("compiled rival reference does not end at exact authoritative lap time")
    speeds=[float(r["speed"]) for r in model.samples if _num(r.get("speed"))]
    if not speeds or min(speeds)<20.0 or max(speeds)>MAX_CLEAN_DERIVED_SPEED_KPH:
        raise ValueError("compiled rival reference derived speed trace failed sanity check")



def _apply_persisted_track_geometry(model: ReferenceTrace) -> ReferenceTrace:
    """Rebind a compiled reference to the current shared physical-track model.

    Driving-event timing remains reference-specific. Only physical T1..Tn and
    the coaching-zone geometry are refreshed, so a cleaner learned track can
    improve all consumers without rewriting the captured rival telemetry.
    """
    try:
        from .track_geometry import persisted_physical_turns
        raw=persisted_physical_turns(model.track_name,model.track_length_m)
    except Exception:
        raw=()
    if not raw:
        return model
    corners=tuple(PhysicalCorner(
        int(r['corner_id']),str(r.get('label') or f"T{r['corner_id']}"),
        float(r['start_m']),float(r['apex_m']),float(r['end_m']),
        r.get('turn_direction'),float(r['curvature_score']) if _num(r.get('curvature_score')) else None,
    ) for r in raw)
    if not corners:
        return model
    # Skip a rebuild when the stored authority is effectively identical.
    if len(corners)==len(model.physical_corners) and all(
        abs(float(a.apex_m)-float(b.apex_m))<0.25 and abs(float(a.start_m)-float(b.start_m))<0.25 and abs(float(a.end_m)-float(b.end_m))<0.25
        for a,b in zip(corners,model.physical_corners)
    ):
        return model
    try:
        from .coaching_zones import build_coaching_zones
        zones=build_coaching_zones(corners,model.driving_events,model.samples,track_length_m=model.track_length_m)
    except Exception:
        return model
    meta=dict(model.metadata);quality=dict(model.quality)
    meta['physical_geometry_authority']='adaptive_track_model'
    quality['physical_geometry_authority']='adaptive_track_model'
    quality['physical_corner_count']=len(corners)
    return ReferenceTrace(model.track_name,model.track_length_m,model.lap_time_s,model.step_m,model.samples,corners,model.driving_events,zones,meta,quality)

def apply_persisted_track_geometry(model: ReferenceTrace) -> ReferenceTrace:
    return _apply_persisted_track_geometry(model)


def load_reference_model(path: str | Path) -> ReferenceTrace:
    """Load the permanent compiled per-track CORNER COACH model."""
    path=Path(path)
    payload=json.loads(path.read_text(encoding="utf-8"))
    model=reference_trace_from_dict(payload)
    # V1.1.0.5 could persist a compiled Time Trial model whose lap clock was
    # correct while its ghost CarTelemetry stream was not. Revalidate rival pace
    # models from their compiled samples before allowing them into live coaching.
    source=str(model.metadata.get("source") or "").upper()
    trace_mode=str(model.quality.get("reference_trace_mode") or model.metadata.get("reference_trace_mode") or "").lower()
    if source=="EA_F1_TIME_TRIAL_RIVAL" or trace_mode=="rival_pace":
        sibling_raw=path.parent/"rival_reference.json"
        expected_fingerprint=None
        if sibling_raw.exists():
            try:
                raw_payload=json.loads(sibling_raw.read_text(encoding="utf-8"))
                raw_lap=raw_payload.get("lap") if isinstance(raw_payload,dict) else None
                raw_meta=raw_payload.get("metadata") if isinstance(raw_payload,dict) else None
                if isinstance(raw_lap,dict):
                    expected_fingerprint=raw_reference_fingerprint(raw_lap,raw_meta if isinstance(raw_meta,dict) else {})
            except (OSError,ValueError,TypeError,json.JSONDecodeError) as error:
                raise ValueError(f"cannot verify sibling rival_reference.json: {error}") from error
        _assert_current_rival_model(model,expected_fingerprint=expected_fingerprint)
        check_lap={
            "valid":True,
            "track_length_m":model.track_length_m,
            "lap_time_s":model.lap_time_s,
            "reference_trace_mode":"rival_pace",
            "pace_compiler_version":model.quality.get("pace_compiler_version"),
            "timing_source":model.quality.get("timing_source"),
            "speed_source":model.quality.get("speed_source"),
            "pace_speed_window_m":model.quality.get("pace_speed_window_m"),
            "pace_anchors":model.quality.get("pace_anchors") or [],
            "_samples":{float(r["d"]):dict(r) for r in model.samples if _num(r.get("d"))},
        }
        quality=validate_reference_lap(check_lap,model.metadata)
        if not quality.get("accepted"):
            raise ValueError("compiled rival reference failed integrity validation: "+", ".join(quality.get("reasons") or ("unknown",)))
        try:
            from .track_geometry import expected_turn_count
            expected=expected_turn_count(model.track_name)
        except Exception:
            expected=None
        if not model.physical_corners:
            raise ValueError("compiled rival reference has no physical corner model")
        if isinstance(expected,int) and expected>0 and len(model.physical_corners)!=expected:
            raise ValueError(f"compiled rival reference corner count mismatch: expected {expected}, got {len(model.physical_corners)}")
    return _apply_persisted_track_geometry(model)


def compiled_model_for_source(source_file: str | Path | None) -> Path | None:
    """Return a sibling compiled model for a stored rival reference, if present."""
    if not source_file:
        return None
    path=Path(source_file)
    candidate=path.parent / "reference_model.json"
    return candidate if candidate.exists() else None


def save_raw_reference(lap: dict[str,Any], metadata: dict[str,Any] | None=None, *, root: str|Path="references", track_name: str|None=None, raw_payload:dict[str,Any]|None=None) -> Path:
    """Persist a completed rival pace lap before geometry/model compilation.

    This deliberately mirrors the long-standing ``references/<TRACK>`` layout.
    A valid pace capture is never lost just because physical map geometry becomes
    available a few seconds later than the rival crosses S/F.
    """
    metadata=dict(metadata or {})
    resolved=str(track_name or lap.get("track_name") or metadata.get("track_name") or metadata.get("track") or "UNKNOWN").upper()
    folder=Path(root)/_safe_name(resolved)
    folder.mkdir(parents=True,exist_ok=True)
    raw_path=folder/"rival_reference.json"
    payload=raw_payload or {"metadata":metadata,"lap":lap}
    tmp=raw_path.with_suffix(raw_path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    tmp.replace(raw_path)
    return raw_path


def save_reference_bundle(lap: dict[str,Any], metadata: dict[str,Any] | None=None, *, root: str|Path="references", track_name: str|None=None, raw_payload:dict[str,Any]|None=None) -> dict[str,Path]:
    """Persist raw capture first, then build a compiler-authenticated model.

    A newly saved raw lap invalidates any previous model immediately. This makes
    it impossible for an old validator-v3/v4 model to masquerade as the model
    for a freshly recorded rival lap. The old files are kept as ``.stale`` only
    for diagnosis and are never discovered by normal runtime loading.
    """
    metadata=dict(metadata or {})
    resolved=str(track_name or lap.get("track_name") or metadata.get("track_name") or metadata.get("track") or "UNKNOWN").upper()
    raw_path=save_raw_reference(lap,metadata,root=root,track_name=resolved,raw_payload=raw_payload)
    expected_fingerprint=raw_reference_fingerprint(lap,metadata)
    folder=Path(root)/_safe_name(resolved)
    folder.mkdir(parents=True,exist_ok=True)
    model_path=folder/"reference_model.json"
    zones_path=folder/"coaching_zones.json"

    stale_paths=[]
    for target in (model_path,zones_path):
        stale=target.with_suffix(target.suffix+".stale")
        if stale.exists():
            stale.unlink()
        if target.exists():
            target.replace(stale)
            stale_paths.append(stale)

    try:
        model=compile_reference_model(lap,metadata,track_name=resolved,require_quality=True)
        _assert_current_rival_model(model,expected_fingerprint=expected_fingerprint)
        model_tmp=model_path.with_suffix(model_path.suffix+".tmp")
        zones_tmp=zones_path.with_suffix(zones_path.suffix+".tmp")
        model_tmp.write_text(json.dumps(to_dict(model),indent=2),encoding="utf-8")
        zones_tmp.write_text(json.dumps({"track_name":model.track_name,"track_length_m":model.track_length_m,"lap_time_s":model.lap_time_s,"reference_compiler_id":REFERENCE_COMPILER_ID,"raw_reference_fingerprint":expected_fingerprint,"coaching_zones":[to_dict(x) for x in model.coaching_zones]},indent=2),encoding="utf-8")
        model_tmp.replace(model_path)
        zones_tmp.replace(zones_path)
        # Disk-level verification is intentional: MODEL READY means the exact
        # file runtime will later load has passed compiler/version/fingerprint checks.
        verified=load_reference_model(model_path)
        _assert_current_rival_model(verified,expected_fingerprint=expected_fingerprint)
    except Exception:
        for target in (model_path,zones_path):
            try:
                if target.exists():
                    target.unlink()
            except OSError:
                pass
        for tmp in (model_path.with_suffix(model_path.suffix+".tmp"),zones_path.with_suffix(zones_path.suffix+".tmp")):
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
        raise
    else:
        for stale in stale_paths:
            try:
                stale.unlink()
            except OSError:
                pass
    return {"raw":raw_path,"model":model_path,"zones":zones_path}
