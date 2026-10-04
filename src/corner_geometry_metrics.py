"""V1.8.0.0 geometry-first corner measurement helpers.

Physical corner numbering comes from measured/stored circuit geometry.  Driver
inputs are attached to that geometry; they never create or renumber corners.
All metrics are deterministic and carry explicit availability/quality flags.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Any, Iterable


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _rows(lap: dict[str, Any], lo: float, hi: float) -> list[dict[str, Any]]:
    out=[]
    for raw_d,row in (lap.get("_samples") or {}).items():
        try: d=float(raw_d)
        except (TypeError,ValueError): continue
        if not (_num(d) and lo-1e-6 <= d <= hi+1e-6 and isinstance(row,dict)): continue
        r=dict(row); r["d"]=d; out.append(r)
    out.sort(key=lambda r:r["d"])
    return reject_sample_outliers(out)


def _mad(values: Iterable[float]) -> tuple[float,float] | None:
    vals=[float(v) for v in values if _num(v)]
    if len(vals)<5: return None
    m=median(vals); dev=median(abs(v-m) for v in vals)
    return m,dev


def reject_sample_outliers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject isolated telemetry spikes without smoothing genuine driver actions.

    Rejection is deliberately conservative: impossible fields are removed first,
    then isolated speed/steering spikes and non-monotonic timestamp samples are
    discarded. Sustained braking/steering changes survive because adjacent points
    support them.
    """
    if not rows: return []
    cleaned=[]; prev_t=None; prev_d=None
    for row0 in rows:
        row=dict(row0)
        d=row.get("d"); t=row.get("t")
        if not _num(d): continue
        if _num(t):
            tf=float(t)
            # A completed-lap corner trace must progress in time. Tiny duplicate
            # timestamps are allowed; backward jumps indicate packet-family jitter.
            if prev_t is not None and tf+0.020 < prev_t: continue
            prev_t=max(prev_t,tf) if prev_t is not None else tf
        if prev_d is not None and float(d)+1e-6 < prev_d: continue
        prev_d=float(d)
        for key in ("throttle","brake"):
            v=row.get(key)
            if _num(v) and not (-0.02 <= float(v) <= 1.02): row.pop(key,None)
        v=row.get("steering")
        if _num(v) and abs(float(v))>1.25: row.pop("steering",None)
        v=row.get("speed")
        if _num(v) and not (0.0 <= float(v) <= 420.0): row.pop("speed",None)
        if _num(t) and float(t)<-0.1: row.pop("t",None)
        cleaned.append(row)
    # Local isolated spike rejection for speed and steering. Use neighbours rather
    # than global statistics so hairpins and rapid direction changes remain valid.
    for key,base_limit in (("speed",35.0),("steering",0.45)):
        for i in range(1,len(cleaned)-1):
            a,b,c=cleaned[i-1],cleaned[i],cleaned[i+1]
            if all(_num(x.get(key)) for x in (a,b,c)):
                av,bv,cv=float(a[key]),float(b[key]),float(c[key])
                interp=(av+cv)*0.5
                neighbour_change=abs(cv-av)
                limit=max(base_limit,neighbour_change*2.5+(10.0 if key=="speed" else 0.08))
                if abs(bv-interp)>limit: b.pop(key,None)
    # Distance/time implied speed sanity. Remove only the suspect speed field,
    # never the entire row, so other channels remain usable.
    for a,b in zip(cleaned,cleaned[1:]):
        if _num(a.get("t")) and _num(b.get("t")):
            dt=float(b["t"])-float(a["t"]); dd=float(b["d"])-float(a["d"])
            if 0.002<dt and 0.0<=dd:
                implied=dd/dt*3.6
                if implied>450.0:
                    b.pop("speed",None)
    return cleaned


def _attach_measurement_time(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach `_mt` used by time-domain metrics.

    Prefer measured packet/lap timestamps when they progress normally. Older
    recordings can contain repeated timestamps after distance resampling; in
    that case integrate *measured distance and speed* instead. This is still a
    deterministic observation, not a predicted lap time.
    """
    if not rows:
        return []
    out=[dict(r) for r in rows]
    timed=[r for r in out if _num(r.get("t"))]
    positive=0; pairs=0
    if len(timed)>=2:
        for a,b in zip(timed,timed[1:]):
            dt=float(b["t"])-float(a["t"]); pairs+=1
            if dt>0.001: positive+=1
    span=(float(timed[-1]["t"])-float(timed[0]["t"])) if len(timed)>=2 else 0.0
    timestamp_ok=len(timed)>=max(3,int(len(out)*0.70)) and pairs>0 and positive/max(1,pairs)>=0.60 and span>0.05
    if timestamp_ok:
        t0=float(timed[0]["t"])
        for r in out:
            if _num(r.get("t")): r["_mt"]=float(r["t"])-t0
        return out

    # Fallback from measured path progress and speed. Require enough speed
    # evidence; never substitute a nominal/expected corner speed.
    out[0]["_mt"]=0.0
    elapsed=0.0
    usable=0
    for a,b in zip(out,out[1:]):
        dd=max(0.0,float(b["d"])-float(a["d"]))
        speeds=[float(x["speed"]) for x in (a,b) if _num(x.get("speed")) and float(x["speed"])>2.0]
        if dd<=0.0:
            b["_mt"]=elapsed
            continue
        if not speeds:
            b.pop("_mt",None)
            continue
        v=sum(speeds)/len(speeds)/3.6
        if v<=0.5:
            b.pop("_mt",None)
            continue
        elapsed += dd/v; usable+=1; b["_mt"]=elapsed
    if usable < max(2,int((len(out)-1)*0.50)):
        for r in out: r.pop("_mt",None)
    return out


def _nearest(rows: list[dict[str, Any]], d: float, key: str, tol: float=15.0):
    valid=[r for r in rows if _num(r.get(key))]
    if not valid: return None
    r=min(valid,key=lambda x:abs(float(x["d"])-d))
    return float(r[key]) if abs(float(r["d"])-d)<=tol else None


def _time_at(rows: list[dict[str, Any]], d: float) -> float | None:
    valid=[r for r in rows if _num(r.get("_mt"))]
    if not valid: return None
    r=min(valid,key=lambda x:abs(float(x["d"])-d))
    return float(r["_mt"]) if abs(float(r["d"])-d)<=15.0 else None


def _sustained_first(rows: list[dict[str, Any]], pred, count: int=2) -> dict[str, Any] | None:
    run=[]
    for r in rows:
        if pred(r):
            run.append(r)
            if len(run)>=count: return run[0]
        else: run=[]
    return None


def _sustained_last(rows: list[dict[str, Any]], pred, count: int=2) -> dict[str, Any] | None:
    run=[]; last=None
    for r in rows:
        if pred(r):
            run.append(r)
            if len(run)>=count: last=run[-1]
        else: run=[]
    return last


def path_curvature_apex(rows: list[dict[str, Any]], start_m: float, end_m: float, *, fallback_m: float | None=None) -> tuple[float|None,float|None,float]:
    """Return (apex distance, curvature score, confidence) from measured X/Z path."""
    pts=[r for r in rows if start_m<=float(r["d"])<=end_m and _num(r.get("world_x")) and _num(r.get("world_z"))]
    if len(pts)<5:
        return (float(fallback_m),None,0.45) if _num(fallback_m) else (None,None,0.0)
    vals=[]
    # Five-metre live bins can leave short physical corners with only 5-6
    # geometry samples at the first exit packet.  Use a one-sample chord for
    # those short corners so apex evidence is available immediately; retain the
    # wider two-sample chord for denser traces where it is more noise-resistant.
    look=1 if len(pts)<7 else 2
    for i in range(look,len(pts)-look):
        p0,p1,p2=pts[i-look],pts[i],pts[i+look]
        v1=(float(p1["world_x"])-float(p0["world_x"]),float(p1["world_z"])-float(p0["world_z"]))
        v2=(float(p2["world_x"])-float(p1["world_x"]),float(p2["world_z"])-float(p1["world_z"]))
        l1=math.hypot(*v1); l2=math.hypot(*v2)
        if l1<1.0 or l2<1.0: continue
        angle=abs(math.atan2(v1[0]*v2[1]-v1[1]*v2[0],v1[0]*v2[0]+v1[1]*v2[1]))
        # Angle per travelled metre is stable across sampling density.
        vals.append((angle/max(1.0,(l1+l2)*0.5),float(p1["d"])))
    if not vals:
        return (float(fallback_m),None,0.55) if _num(fallback_m) else (None,None,0.0)
    # Smooth in distance-index space, then take the strongest sustained curvature.
    smooth=[]
    for i,(v,d) in enumerate(vals):
        block=[vals[j][0] for j in range(max(0,i-2),min(len(vals),i+3))]
        smooth.append((sum(block)/len(block),d))
    max_score=max(v for v,_ in smooth)
    # On a constant-radius corner there is no unique single-sample curvature
    # maximum. Use the curvature-weighted centre of the sustained high-curvature
    # plateau instead of an arbitrary edge sample. This is substantially more
    # stable than selecting the slowest point or one noisy curvature peak.
    plateau=[(v,d) for v,d in smooth if v>=max_score*0.82]
    if plateau:
        total=sum(v for v,_ in plateau)
        d=sum(v*d for v,d in plateau)/max(1e-9,total)
        score=sum(v for v,_ in plateau)/len(plateau)
    else:
        score,d=max(smooth,key=lambda x:x[0])
    coverage=min(1.0,len(pts)/max(5.0,(end_m-start_m)/5.0))
    base_conf=0.62 if look==1 else 0.70
    conf=max(0.58,min(0.99,base_conf+0.25*coverage))
    return d,score,conf


def _steering_shape(rows: list[dict[str, Any]], start_m: float, end_m: float) -> dict[str, Any]:
    r=[x for x in rows if start_m<=float(x["d"])<=end_m and _num(x.get("steering")) and _num(x.get("_mt"))]
    if len(r)<4:
        return {"steering_rate_mean_per_s":None,"steering_rate_peak_per_s":None,"steering_corrections":None,
                "steering_smoothness":None,"steering_unwind_s":None,"steering_unwind_m":None,"steering_unwind_monotonicity":None}
    rates=[]
    for a,b in zip(r,r[1:]):
        dt=float(b["_mt"])-float(a["_mt"])
        if 0.005<=dt<=0.5:
            rates.append((float(b["steering"])-float(a["steering"]))/dt)
    abs_rates=[abs(x) for x in rates]
    mean_rate=sum(abs_rates)/len(abs_rates) if abs_rates else None
    peak_rate=max(abs_rates) if abs_rates else None
    # Correction = derivative direction reversal while meaningful steering load exists.
    corrections=0; prev=0
    for i,v in enumerate(rates):
        sign=1 if v>0.10 else (-1 if v<-0.10 else 0)
        steer=abs(float(r[min(i+1,len(r)-1)]["steering"]))
        if sign and prev and sign!=prev and steer>=0.06: corrections+=1
        if sign: prev=sign
    peak_i=max(range(len(r)),key=lambda i:abs(float(r[i]["steering"])))
    peak=abs(float(r[peak_i]["steering"]))
    # Smoothness 100% means little derivative variation relative to peak input.
    if len(rates)>=2 and peak>0.02:
        rate_tv=sum(abs(b-a) for a,b in zip(rates,rates[1:]))
        smooth=max(0.0,min(1.0,1.0-rate_tv/max(1e-6,peak*18.0)))
    else: smooth=None
    tail=r[peak_i:]
    unwind_end=_sustained_first(tail,lambda x:abs(float(x.get("steering") or 0.0))<=0.08,2)
    unwind_s=(float(unwind_end["_mt"])-float(r[peak_i]["_mt"])) if unwind_end and _num(unwind_end.get("_mt")) else None
    unwind_m=(float(unwind_end["d"])-float(r[peak_i]["d"])) if unwind_end else None
    mono=None
    if len(tail)>=3:
        changes=[]
        for a,b in zip(tail,tail[1:]):
            av=abs(float(a["steering"])); bv=abs(float(b["steering"]))
            if abs(bv-av)>=0.005: changes.append(bv<=av)
        mono=(sum(1 for x in changes if x)/len(changes)) if changes else 1.0
    return {"steering_rate_mean_per_s":mean_rate,"steering_rate_peak_per_s":peak_rate,"steering_corrections":corrections,
            "steering_smoothness":smooth,"steering_unwind_s":unwind_s,"steering_unwind_m":unwind_m,"steering_unwind_monotonicity":mono}


def _efficiency(current: float|None, reference: float|None, *, lower_is_better: bool=False) -> float | None:
    if not (_num(current) and _num(reference)) or float(current)<0 or float(reference)<0: return None
    c=float(current); r=float(reference)
    if lower_is_better:
        if c<=1e-6: return 120.0 if r>1e-6 else 100.0
        return max(0.0,min(150.0,100.0*r/c))
    if r<=1e-6: return None
    return max(0.0,min(150.0,100.0*c/r))


def measure_corner(lap: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    own_start=float(turn.get("ownership_start_m",turn.get("start_m",0.0)))
    own_end=float(turn.get("ownership_end_m",turn.get("end_m",own_start)))
    start=float(turn.get("start_m",own_start)); geom_apex=float(turn.get("apex_m",start)); end=float(turn.get("end_m",own_end))
    rows=_attach_measurement_time(_rows(lap,own_start,own_end))
    if len(rows)<3: return {"available":False,"quality":0.0,"quality_reasons":["insufficient_samples"]}

    # Geometry/path apex: current path if available, otherwise fixed physical apex.
    apex,curv,apex_conf=path_curvature_apex(rows,start,end,fallback_m=geom_apex)
    apex=float(apex) if _num(apex) else geom_apex
    approach=[r for r in rows if own_start<=float(r["d"])<=apex]
    corner=[r for r in rows if start<=float(r["d"])<=end]
    exit_rows=[r for r in rows if apex<=float(r["d"])<=own_end]

    brake=_sustained_first(approach,lambda r:_num(r.get("brake")) and float(r["brake"])>=0.10,2)
    if brake is None:
        brake=_sustained_first(approach,lambda r:_num(r.get("g_long")) and float(r["g_long"])<=-0.18,2)
    turn_dir=str(turn.get("turn_direction") or "").upper()
    def steering_in_direction(r):
        if not _num(r.get("steering")) or abs(float(r["steering"]))<0.08: return False
        # Sign can vary by wheel implementation; geometry direction is used only
        # when clearly consistent. Magnitude remains authoritative.
        return True
    turnin=_sustained_first([r for r in corner if float(r["d"])<=apex],steering_in_direction,2)
    pickup=_sustained_first(exit_rows,lambda r:_num(r.get("throttle")) and float(r["throttle"])>=0.20,2)
    full=_sustained_first(exit_rows,lambda r:_num(r.get("throttle")) and float(r["throttle"])>=0.98,2)
    # Exit is geometry end, extended to steering-unwound/full-throttle recovery but
    # never beyond this turn's ownership boundary.
    steer_clear=_sustained_first(exit_rows,lambda r:not _num(r.get("steering")) or abs(float(r.get("steering") or 0.0))<=0.08,2)
    exit_d=end
    if steer_clear: exit_d=max(exit_d,min(own_end,float(steer_clear["d"])))
    if full: exit_d=max(exit_d,min(own_end,float(full["d"])))

    min_row=min((r for r in corner if _num(r.get("speed"))),key=lambda r:float(r["speed"]),default=None)
    min_speed=float(min_row["speed"]) if min_row else None
    apex_speed=_nearest(rows,geom_apex,"speed",tol=20.0)
    path_apex_speed=_nearest(rows,apex,"speed",tol=20.0)
    exit_speed=_nearest(rows,exit_d,"speed",tol=20.0)

    # Brake release and coasting interval.
    brake_release=None
    if brake:
        after=[r for r in rows if float(r["d"])>=float(brake["d"]) and float(r["d"])<=apex+80.0]
        brake_release=_sustained_first(after,lambda r:not _num(r.get("brake")) or float(r.get("brake") or 0.0)<=0.05,2)
    coast=[]
    if brake_release and pickup:
        coast=[r for r in rows if float(brake_release["d"])<=float(r["d"])<=float(pickup["d"]) and
               (not _num(r.get("brake")) or float(r.get("brake") or 0.0)<0.05) and
               (not _num(r.get("throttle")) or float(r.get("throttle") or 0.0)<0.05)]
    coasting_m=(float(coast[-1]["d"])-float(coast[0]["d"])) if len(coast)>=2 else 0.0 if coast else None
    coasting_s=(float(coast[-1]["_mt"])-float(coast[0]["_mt"])) if len(coast)>=2 and _num(coast[0].get("_mt")) and _num(coast[-1].get("_mt")) else 0.0 if coast else None
    apex_t=_time_at(rows,geom_apex)
    pickup_t=float(pickup["_mt"]) if pickup and _num(pickup.get("_mt")) else None
    pickup_after_apex_s=max(0.0,pickup_t-apex_t) if _num(pickup_t) and _num(apex_t) else None

    steering=_steering_shape(rows,start,exit_d)
    present={
        "geometry":_num(geom_apex),"apex_speed":_num(apex_speed),"min_speed":_num(min_speed),"exit_speed":_num(exit_speed),
        "brake":brake is not None,"turn_in":turnin is not None,"pickup":pickup is not None,
        "coast_time":_num(coasting_s),"steering":_num(steering.get("steering_rate_mean_per_s")),
    }
    required=("geometry","apex_speed","min_speed","exit_speed")
    base=sum(1.0 for k in required if present[k])/len(required)
    optional=sum(1.0 for k in ("brake","turn_in","pickup","coast_time","steering") if present[k])/5.0
    expected_bins=max(8.0,(own_end-own_start)/5.0)
    density=min(1.0,len(rows)/expected_bins)
    # Timestamp continuity and distance-gap quality make sparse packet bursts
    # explicitly lower-confidence rather than silently equal to dense telemetry.
    times=[float(r["_mt"]) for r in rows if _num(r.get("_mt"))]
    time_monotonic=all(b+0.020>=a for a,b in zip(times,times[1:])) if len(times)>=2 else False
    gaps=[float(b["d"])-float(a["d"]) for a,b in zip(rows,rows[1:])]
    max_gap=max(gaps,default=0.0)
    gap_quality=max(0.0,min(1.0,1.0-max(0.0,max_gap-10.0)/40.0))
    speed_cov=sum(1 for r in rows if _num(r.get("speed")))/max(1,len(rows))
    path_cov=sum(1 for r in rows if _num(r.get("world_x")) and _num(r.get("world_z")))/max(1,len(rows))
    core=0.68*base+0.20*optional+0.12*speed_cov
    continuity=(0.94 if time_monotonic else 0.78)*gap_quality
    geometry_factor=(0.85+0.15*path_cov) if curv is not None else 0.78
    score=max(0.0,min(1.0,core*(0.78+0.22*density)*continuity*geometry_factor*apex_conf))
    reasons=[]
    for k,v in present.items():
        if not v: reasons.append(f"{k}_unavailable")
    if density<0.75: reasons.append("low_sample_density")
    if not time_monotonic: reasons.append("time_continuity_weak")
    if max_gap>20.0: reasons.append("large_distance_gap")
    if speed_cov<0.90: reasons.append("speed_coverage_low")
    if curv is None: reasons.append("path_curvature_unavailable")

    out={
        "available":True,"sample_count":len(rows),"quality":score,"quality_reasons":reasons,
        "sample_density":density,"max_distance_gap_m":max_gap,"speed_coverage":speed_cov,"path_coverage":path_cov,
        "time_monotonic":time_monotonic,
        "corner_start_m":start,"brake_onset_m":float(brake["d"]) if brake else None,
        "turn_in_m":float(turnin["d"]) if turnin else None,
        "apex_m":apex,"physical_apex_m":geom_apex,"apex_method":"path_curvature",
        "curvature_score":curv,"apex_confidence":apex_conf,
        "exit_m":exit_d,"brake_release_m":float(brake_release["d"]) if brake_release else None,
        "min_speed_m":float(min_row["d"]) if min_row else None,"min_speed_kph":min_speed,
        "apex_speed_kph":apex_speed,"path_apex_speed_kph":path_apex_speed,"exit_speed_kph":exit_speed,
        "throttle_pickup_m":float(pickup["d"]) if pickup else None,"full_throttle_m":float(full["d"]) if full else None,
        "throttle_pickup_after_apex_s":pickup_after_apex_s,
        "coasting_m":coasting_m,"coasting_s":coasting_s,
    }
    out.update(steering)
    return out


def compare_corner(current: dict[str, Any], reference: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    cur=measure_corner(current,turn); ref=measure_corner(reference,turn)
    def delta(k):
        return float(cur[k])-float(ref[k]) if _num(cur.get(k)) and _num(ref.get(k)) else None
    result={"current_metrics":cur,"reference_metrics":ref}
    keys=("brake_onset_m","turn_in_m","apex_m","exit_m","min_speed_m","min_speed_kph","apex_speed_kph","exit_speed_kph",
          "throttle_pickup_m","throttle_pickup_after_apex_s","coasting_m","coasting_s",
          "steering_rate_mean_per_s","steering_rate_peak_per_s","steering_corrections","steering_smoothness",
          "steering_unwind_s","steering_unwind_m","steering_unwind_monotonicity")
    for k in keys: result[f"{k}_delta"]=delta(k)
    # A fallback physical apex is useful for phase boundaries, but it must not be
    # presented as measured HITTING APEX evidence.  Publish apex-position delta
    # only when both driver and reference have an actual path-curvature apex.
    apex_trusted=(
        _num(cur.get("curvature_score")) and _num(ref.get("curvature_score"))
        and float(cur.get("apex_confidence") or 0.0)>=0.58
        and float(ref.get("apex_confidence") or 0.0)>=0.58
    )
    if not apex_trusted:
        result["apex_m_delta"]=None
    result["apex_position_trusted"]=bool(apex_trusted)
    # Live HITTING APEX fallback: when a curvature apex is not trustworthy but
    # both traces have a valid minimum-speed location, use that location as a
    # lower-confidence apex proxy. This is explicitly tagged as an estimate and
    # never upgrades the authoritative path-curvature evidence.
    min_speed_proxy_trusted=(
        _num(cur.get("min_speed_m")) and _num(ref.get("min_speed_m"))
        and float(cur.get("quality") or 0.0)>=0.50
        and float(ref.get("quality") or 0.0)>=0.50
    )
    result["apex_estimate_delta_m"]=(
        float(cur["min_speed_m"])-float(ref["min_speed_m"]) if min_speed_proxy_trusted else None
    )
    result["apex_estimate_trusted"]=bool(min_speed_proxy_trusted)
    result["apex_evidence_method"]=("path_curvature" if apex_trusted else ("min_speed_location" if min_speed_proxy_trusted else None))
    cq=float(cur.get("quality") or 0.0); rq=float(ref.get("quality") or 0.0)
    result["corner_quality_current"]=cq; result["corner_quality_reference"]=rq
    result["corner_confidence"]=max(0.0,min(1.0,math.sqrt(cq*rq)))
    reasons=list(cur.get("quality_reasons") or [])+[f"reference_{x}" for x in (ref.get("quality_reasons") or [])]
    result["corner_confidence_reasons"]=tuple(dict.fromkeys(reasons))
    result["minimum_speed_efficiency_pct"]=_efficiency(cur.get("min_speed_kph"),ref.get("min_speed_kph"))
    result["apex_speed_efficiency_pct"]=_efficiency(cur.get("apex_speed_kph"),ref.get("apex_speed_kph"))
    result["exit_speed_efficiency_pct"]=_efficiency(cur.get("exit_speed_kph"),ref.get("exit_speed_kph"))
    result["throttle_pickup_efficiency_pct"]=_efficiency(cur.get("throttle_pickup_after_apex_s"),ref.get("throttle_pickup_after_apex_s"),lower_is_better=True)
    return result

# Public alias used by the legacy measured-section recorder. The implementation
# remains centralized so steering-shape definitions cannot drift between offline
# analysis and live Speed Coach.
def steering_shape(rows: list[dict[str, Any]], start_m: float, end_m: float) -> dict[str, Any]:
    return _steering_shape(reject_sample_outliers([dict(r) for r in rows]), start_m, end_m)
