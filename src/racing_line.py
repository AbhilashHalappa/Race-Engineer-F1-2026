"""Reference-relative racing-line measurements from EA world X/Z telemetry.

V1.3.2.0 adds conservative world-position outlier rejection, geometry-derived
apex extraction, early/late apex classification, pinched-exit detection and a
path-aware steering-correction comparison.  Every classification is evidence
bearing and is suppressed when the necessary geometry/input samples are absent.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Any


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _sample_map(lap):
    rows = lap.get("_samples") if isinstance(lap, dict) else None
    if not isinstance(rows, dict): return {}
    out = {}
    for k, row in rows.items():
        if not isinstance(row, dict): continue
        try: d = float(k)
        except (TypeError, ValueError): d = float(row.get("d")) if _num(row.get("d")) else None
        if d is None: continue
        if _num(row.get("world_x")) and _num(row.get("world_z")):
            out[round(d / 5.0) * 5.0] = row
    return out


def _signed_lateral(reference, common, i, current_row):
    if len(common) < 3: return None
    prev_d=common[max(0,i-1)]; next_d=common[min(len(common)-1,i+1)]
    a=reference[prev_d]; b=reference[next_d]; r=reference[common[i]]
    tx=float(b["world_x"])-float(a["world_x"]); tz=float(b["world_z"])-float(a["world_z"])
    norm=math.hypot(tx,tz)
    if norm<1e-6: return None
    tx/=norm; tz/=norm
    dx=float(current_row["world_x"])-float(r["world_x"]); dz=float(current_row["world_z"])-float(r["world_z"])
    return tx*dz-tz*dx


def _robust_keep(offsets: list[tuple[float,float,float|None]]) -> tuple[list[tuple[float,float,float|None]], dict[str,Any]]:
    if len(offsets)<20: return offsets,{"rejected":0,"threshold_m":None,"method":"insufficient_samples_for_robust_filter"}
    vals=[x[1] for x in offsets]; med=median(vals); mad=median(abs(x-med) for x in vals)
    threshold=max(12.0, med + max(3.0, 8.0*mad))
    kept=[x for x in offsets if x[1] <= threshold]
    # Never let filtering erase a materially large part of the lap; that would be
    # evidence of a coordinate-system mismatch rather than isolated outliers.
    if len(kept) < len(offsets)*0.80:
        return offsets,{"rejected":0,"threshold_m":threshold,"method":"filter_suppressed_coordinate_mismatch_suspected"}
    return kept,{"rejected":len(offsets)-len(kept),"threshold_m":threshold,"method":"median/MAD matched-distance path-deviation filter"}


def _phase_stats(rows,start,end):
    local=[x for x in rows if start<=x[0]<=end]
    if not local: return None
    absvals=[x[1] for x in local]; signed=[x[2] for x in local if _num(x[2])]
    return {"start_m":start,"end_m":end,"sample_count":len(local),"mean_path_deviation_m":sum(absvals)/len(absvals),
            "max_path_deviation_m":max(absvals),"mean_signed_lateral_deviation_m":sum(float(x) for x in signed)/len(signed) if signed else None}


def _heading(a,b): return math.atan2(float(b["world_z"])-float(a["world_z"]),float(b["world_x"])-float(a["world_x"]))

def _angle_delta(a,b):
    x=b-a
    while x>math.pi: x-=2*math.pi
    while x<-math.pi: x+=2*math.pi
    return x


def _geometry_apex(samples: dict[float,dict[str,Any]], start: float, end: float) -> dict[str,Any] | None:
    ds=[d for d in sorted(samples) if start<=d<=end]
    if len(ds)<5: return None
    candidates=[]
    for i in range(1,len(ds)-1):
        a,b,c=samples[ds[i-1]],samples[ds[i]],samples[ds[i+1]]
        h1=_heading(a,b); h2=_heading(b,c); turn=_angle_delta(h1,h2)
        span=max(1e-6,ds[i+1]-ds[i-1]); curvature=turn/span
        candidates.append((abs(curvature),curvature,ds[i]))
    if not candidates: return None
    strength,signed,d=max(candidates,key=lambda x:x[0])
    if strength<1e-5: return None
    return {"distance_m":d,"signed_curvature":signed,"curvature_abs":strength,"turn_direction":"left" if signed>0 else "right"}


def _steering_corrections(samples,start,end):
    rows=[]
    for d in sorted(samples):
        if start<=d<=end and _num(samples[d].get("steering")): rows.append(float(samples[d]["steering"]))
    if len(rows)<5: return None
    signs=[]
    for v in rows:
        if abs(v)<0.05: continue
        s=1 if v>0 else -1
        if not signs or s!=signs[-1]: signs.append(s)
    return max(0,len(signs)-1)


def compare_racing_line(current: dict[str,Any] | None, reference: dict[str,Any] | None) -> dict[str,Any]:
    a,b=_sample_map(current or {}),_sample_map(reference or {})
    common=sorted(set(a).intersection(b))
    if len(common)<20: return {"available":False,"reason":"insufficient_world_position_samples","sample_count":len(common)}
    raw=[]
    for i,d in enumerate(common):
        dx=float(a[d]["world_x"])-float(b[d]["world_x"]); dz=float(a[d]["world_z"])-float(b[d]["world_z"])
        raw.append((d,math.hypot(dx,dz),_signed_lateral(b,common,i,a[d])))
    offsets,quality=_robust_keep(raw)
    mean_dev=sum(x[1] for x in offsets)/len(offsets); max_row=max(offsets,key=lambda x:x[1]); signed=[x[2] for x in offsets if _num(x[2])]
    corners=[]; sections=(reference or {}).get("sections") or (current or {}).get("sections") or []
    for sec in sections:
        if not isinstance(sec,dict) or not isinstance(sec.get("id"),int): continue
        start,end=sec.get("start_m"),sec.get("end_m")
        if not _num(start) or not _num(end) or float(end)<=float(start): continue
        start=float(start); end=float(end)
        ref_geo=_geometry_apex(b,start,end); cur_geo=_geometry_apex(a,start,end)
        legacy=sec.get("min_speed_m")
        apex=float(ref_geo["distance_m"]) if ref_geo else (float(legacy) if _num(legacy) else (start+end)*0.5)
        apex=max(start,min(end,apex)); span=max(5.0,end-start); apex_half=max(10.0,min(30.0,span*0.12))
        entry_end=max(start,min(apex-apex_half,end)); exit_start=min(end,max(apex+apex_half,start))
        local=[x for x in offsets if start-20<=x[0]<=end+40]
        if not local: continue
        local_signed=[x[2] for x in local if _num(x[2])]
        apex_delta=(float(cur_geo["distance_m"])-float(ref_geo["distance_m"])) if ref_geo and cur_geo else None
        apex_class="matched"
        if _num(apex_delta):
            if apex_delta < -5.0: apex_class="early"
            elif apex_delta > 5.0: apex_class="late"
        else: apex_class="unknown"
        exit_stats=_phase_stats(offsets,exit_start,end) if end>exit_start else None
        turn_sign=(1 if ref_geo and float(ref_geo["signed_curvature"])>0 else -1) if ref_geo else None
        exit_signed=exit_stats.get("mean_signed_lateral_deviation_m") if isinstance(exit_stats,dict) else None
        pinched=None
        if turn_sign is not None and _num(exit_signed):
            inward=float(exit_signed)*turn_sign
            pinched=bool(inward>1.0)
        ref_corr=_steering_corrections(b,start,end); cur_corr=_steering_corrections(a,start,end)
        corners.append({
            "corner_id":int(sec["id"]),"mean_path_deviation_m":sum(x[1] for x in local)/len(local),"max_path_deviation_m":max(x[1] for x in local),
            "mean_signed_lateral_deviation_m":sum(float(x) for x in local_signed)/len(local_signed) if local_signed else None,"sample_count":len(local),
            "entry":_phase_stats(offsets,start,entry_end) if entry_end>start else None,
            "apex":_phase_stats(offsets,max(start,apex-apex_half),min(end,apex+apex_half)),"exit":exit_stats,
            "reference_apex_m":apex,"reference_geometric_apex_m":ref_geo.get("distance_m") if ref_geo else None,
            "driver_geometric_apex_m":cur_geo.get("distance_m") if cur_geo else None,"geometric_apex_delta_m":apex_delta,
            "apex_classification":apex_class,"turn_direction":ref_geo.get("turn_direction") if ref_geo else None,
            "pinched_exit":pinched,"pinched_exit_evidence_m":float(exit_signed)*turn_sign if turn_sign is not None and _num(exit_signed) else None,
            "driver_steering_corrections":cur_corr,"reference_steering_corrections":ref_corr,
            "excessive_steering_corrections":bool(cur_corr>ref_corr+1) if isinstance(cur_corr,int) and isinstance(ref_corr,int) else None,
        })
    return {"available":True,"sample_count":len(offsets),"raw_sample_count":len(raw),"outlier_filter":quality,
            "mean_path_deviation_m":mean_dev,"mean_signed_lateral_deviation_m":sum(float(x) for x in signed)/len(signed) if signed else None,
            "max_path_deviation_m":max_row[1],"max_deviation_at_m":max_row[0],"corners":corners,
            "coordinate_rule":"signed lateral offset uses local reference tangent; geometry apex uses peak signed path curvature inside the corner window",
            "interpretation":"descriptive matched-distance geometry; classifications are suppressed when geometry/input evidence is insufficient"}
