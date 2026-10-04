"""Continuous distance-based reference-lap performance model.

Pipeline:
    reference lap -> distance interpolation -> full-track local gain/loss map
    -> physical reference turn boundaries -> per-turn loss aggregation

This module deliberately stops before diagnosis/language. ``coaching_analysis``
adds deterministic *why* diagnoses using measured brake/steering/throttle data.
All time values here are observed lap-clock differences, never predictions.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
import math
from typing import Any

from .track_geometry import physical_turns_from_lap


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _field(sample: Any, key: str):
    return sample.get(key) if isinstance(sample, dict) else getattr(sample, key, None)


def _sample_rows(lap: dict[str, Any]) -> list[tuple[float, dict[str, Any]]]:
    rows: list[tuple[float, dict[str, Any]]] = []
    for raw_d, sample in (lap.get("_samples") or {}).items():
        try:
            d = float(raw_d)
        except (TypeError, ValueError):
            continue
        if not (_num(d) and _num(_field(sample, "t"))):
            continue
        rows.append((d, sample))
    rows.sort(key=lambda row: row[0])
    # Keep the newest value for duplicate distance bins while preserving order.
    dedup: dict[float, Any] = {}
    for d, sample in rows:
        dedup[d] = sample
    return sorted(dedup.items())


def _interp(rows: list[tuple[float, Any]], distances: list[float], distance: float, key: str) -> float | None:
    if not rows:
        return None
    ds = distances
    i = bisect_left(ds, distance)
    if i <= 0:
        value = _field(rows[0][1], key)
        return float(value) if _num(value) else None
    if i >= len(rows):
        value = _field(rows[-1][1], key)
        return float(value) if _num(value) else None
    d0, s0 = rows[i - 1]
    d1, s1 = rows[i]
    v0, v1 = _field(s0, key), _field(s1, key)
    if not (_num(v0) and _num(v1)):
        # For non-time supporting channels, nearest valid endpoint is preferable
        # to inventing a value across missing telemetry.
        nearest = v0 if distance - d0 <= d1 - distance else v1
        return float(nearest) if _num(nearest) else None
    if d1 <= d0:
        return float(v1)
    alpha = max(0.0, min(1.0, (distance - d0) / (d1 - d0)))
    return float(v0) + (float(v1) - float(v0)) * alpha


def _physical_turn_boundaries_uncached(reference: dict[str, Any], *, track_name: object = None) -> list[dict[str, Any]]:
    """Return physical T1..Tn regions and measured approach anchors.

    Geometry defines the corner. Reference braking/turn-in events are attached to
    that physical corner afterwards and can begin on the preceding straight. This
    keeps T numbering independent of the driver's braking behaviour while still
    letting diagnosis explain approach losses.
    """
    sections=[dict(x) for x in (reference.get("sections") or ()) if isinstance(x,dict)]
    sections=[x for x in sections if _num(x.get("min_speed_m")) or _num(x.get("start_m"))]
    sections.sort(key=lambda x:float(x.get("min_speed_m") if _num(x.get("min_speed_m")) else x.get("start_m")))

    resolved_track_name=track_name or reference.get("track_name")
    physical=list(physical_turns_from_lap(reference, track_name=resolved_track_name))
    physical_source="reference_world_geometry" if physical else None

    # External references (especially EA Time Trial rivals) may contain a complete
    # distance/input trace but no reliable world X/Z channel.  The dashboard map,
    # however, already owns the learned circuit geometry and authoritative physical
    # T1..Tn numbering.  Reuse that exact per-track turn model instead of falling
    # back to detector/braking sections, otherwise the coach can call "Turn 5"
    # while the car is physically at T11.  Import lazily to keep the performance
    # core independent of the optional overlay at module-import time.
    stored_length=None
    if not physical and resolved_track_name:
        try:
            from .overlay.track_maps import ensure_physical_turn_markers, get_track_length
            physical=list(ensure_physical_turn_markers(
                resolved_track_name, track_length_m=reference.get("track_length_m")
            ) or ())
            stored_length=get_track_length(resolved_track_name)
            if physical:
                physical_source="stored_track_map"
        except Exception:
            # Coaching must remain usable in headless/minimal deployments where the
            # overlay package or persistent map store is unavailable.
            physical=[]

    rows=_sample_rows(reference)
    length=reference.get("track_length_m")
    if not (_num(length) and float(length)>1000.0) and _num(stored_length) and float(stored_length)>1000.0:
        length=float(stored_length)
    if not (_num(length) and float(length)>1000.0):
        length=rows[-1][0] if rows else None
    if physical and _num(length) and float(length)>1000.0:
        length=float(length)
        physical.sort(key=lambda x:float(x.get("lap_distance_m",0.0)))
        apexes=[float(x.get("lap_distance_m",0.0)) for x in physical]
        ownership_starts=[0.0]+[(apexes[i-1]+apexes[i])*0.5 for i in range(1,len(apexes))]
        ownership_ends=[(apexes[i]+apexes[i+1])*0.5 for i in range(len(apexes)-1)]+[length]

        # Geometry-derived start/end boundaries are preferred. Older V4 map/reference
        # material may contain only apex markers, in which case a conservative local
        # corner envelope is derived from the adjacent apex spacing rather than using
        # the whole midpoint-to-midpoint ownership interval as "the corner".
        geom=[]
        for i,marker in enumerate(physical):
            apex=apexes[i]; own_lo=ownership_starts[i]; own_hi=ownership_ends[i]
            mstart=marker.get("start_m"); mend=marker.get("end_m")
            if _num(mstart) and _num(mend):
                start_f=float(mstart); end_f=float(mend)
                if end_f>length: end_f=length
                if not (own_lo-1e-6 <= start_f <= apex <= end_f <= own_hi+1e-6):
                    start_f=max(own_lo,apex-min(90.0,max(25.0,(apex-own_lo)*0.70)))
                    end_f=min(own_hi,apex+min(110.0,max(30.0,(own_hi-apex)*0.70)))
            else:
                start_f=max(own_lo,apex-min(90.0,max(25.0,(apex-own_lo)*0.70)))
                end_f=min(own_hi,apex+min(110.0,max(30.0,(own_hi-apex)*0.70)))
            if end_f<=start_f:
                start_f=own_lo; end_f=own_hi
            geom.append((start_f,apex,end_f,own_lo,own_hi))

        # Guarantee non-overlap so physical turns and straights form one partition.
        for i in range(len(geom)-1):
            a=list(geom[i]); b=list(geom[i+1])
            if a[2] > b[0]:
                split=(a[1]+b[1])*0.5
                a[2]=max(a[1],split); b[0]=min(b[1],split)
                geom[i]=tuple(a); geom[i+1]=tuple(b)

        assigned={}; used=set()
        for idx,(start_f,apex,end_f,own_lo,own_hi) in enumerate(geom):
            candidates=[]
            for sec_i,section in enumerate(sections):
                if sec_i in used: continue
                anchor=section.get("min_speed_m") if _num(section.get("min_speed_m")) else section.get("start_m")
                if _num(anchor) and own_lo <= float(anchor) <= own_hi:
                    candidates.append((abs(float(anchor)-apex),sec_i,section))
            if candidates:
                _,sec_i,section=min(candidates,key=lambda x:x[0]); assigned[idx]=section; used.add(sec_i)

        out=[]
        for idx,marker in enumerate(physical):
            start_f,apex,end_f,own_lo,own_hi=geom[idx]
            section=assigned.get(idx); raw_id=section.get("id") if section else None
            brake=section.get("start_m") if section else None
            turn_in=section.get("turn_in_m") if section else None
            # A reference may have a complete measured distance trace without a
            # detector-section list. In that case attach the first measured brake
            # and steering events to the already-established physical turn rather
            # than falling back to the geometry start marker.
            local=[(d,s) for d,s in rows if own_lo<=d<=apex]
            if not _num(brake):
                brake=next((d for d,s in local if _num(s.get("brake")) and float(s["brake"])>=0.10),None)
            if not _num(turn_in):
                turn_in=next((d for d,s in local if d>=start_f and _num(s.get("steering")) and abs(float(s["steering"]))>=0.08),None)
            # Brake onset is allowed on the approach straight but never before this
            # turn's ownership midpoint. Turn-in should remain within the physical arc.
            brake_f=float(brake) if _num(brake) and own_lo<=float(brake)<=apex else start_f
            turn_in_f=float(turn_in) if _num(turn_in) and start_f<=float(turn_in)<=apex else max(start_f,(start_f+apex)*0.5)
            item={
                "corner_id":int(marker.get("corner_id") or idx+1),
                "label":str(marker.get("label") or f"T{idx+1}"),
                "reference_section_id":raw_id,
                "ownership_start_m":own_lo,
                "ownership_end_m":own_hi,
                "start_m":start_f,
                "geometry_start_m":start_f,
                "brake_m":max(own_lo,min(apex,brake_f)),
                "turn_in_m":max(start_f,min(apex,turn_in_f)),
                "apex_m":apex,
                "end_m":end_f,
                "geometry_end_m":end_f,
                "exit_m":end_f,
                "turn_direction":marker.get("turn_direction"),
                "physical_geometry":True,
                "physical_source":physical_source,
                "apex_method":"path_curvature",
            }
            # V1.8 attaches measured driver-action boundaries to the immutable
            # physical geometry.  Braking/turn-in/exit may move with the driver;
            # T numbering and geometric start/end never do.
            try:
                from .corner_geometry_metrics import measure_corner
                mm=measure_corner(reference,item)
            except Exception:
                mm={}
            if mm.get("available"):
                if _num(mm.get("brake_onset_m")): item["brake_m"]=max(own_lo,min(apex,float(mm["brake_onset_m"])))
                if _num(mm.get("turn_in_m")): item["turn_in_m"]=max(start_f,min(apex,float(mm["turn_in_m"])))
                if _num(mm.get("apex_m")):
                    item["apex_m"]=max(start_f,min(end_f,float(mm["apex_m"])))
                if _num(mm.get("exit_m")): item["exit_m"]=max(item["apex_m"],min(own_hi,float(mm["exit_m"])))
                item["segmentation_quality"]=float(mm.get("quality") or 0.0)
                item["segmentation_quality_reasons"]=tuple(mm.get("quality_reasons") or ())
                item["apex_method"]="path_curvature"
            out.append(item)
        return out

    # Compatibility path when world geometry is absent. Detector sections are all
    # that exists, so keep their lap order but explicitly flag non-physical authority.
    out=[]
    for i,section in enumerate(sections,1):
        start=section.get("start_m"); turn_in=section.get("turn_in_m"); apex=section.get("min_speed_m")
        end=section.get("end_m") if _num(section.get("end_m")) else section.get("full_throttle_m")
        if not _num(end): end=apex
        if not _num(start): start=turn_in if _num(turn_in) else apex
        if not (_num(start) and _num(end) and float(end)>float(start)): continue
        apex_f=float(apex) if _num(apex) else (float(start)+float(end))*0.5
        turn_in_f=float(turn_in) if _num(turn_in) else (float(start)+apex_f)*0.5
        turn_in_f=max(float(start),min(apex_f,turn_in_f)); apex_f=max(turn_in_f,min(float(end),apex_f))
        out.append({
            "corner_id":i,"label":f"T{i}","reference_section_id":section.get("id"),
            "ownership_start_m":float(start),"ownership_end_m":float(end),
            "start_m":float(start),"brake_m":float(start),"turn_in_m":turn_in_f,
            "apex_m":apex_f,"end_m":float(end),"turn_direction":None,"physical_geometry":False,
        })
    return out


# Reference laps are immutable once accepted. Physical turn derivation scans and
# smooths a full world trace, so cache the completed boundary table. The strong
# reference pointer prevents Python id reuse; the stored-map signature invalidates
# the cache if physical map turns are changed during the same process.
_PHYSICAL_BOUNDARY_CACHE: dict[int, tuple[object, tuple[Any, ...], tuple[dict[str, Any], ...]]] = {}
_PHYSICAL_BOUNDARY_CACHE_ORDER: list[int] = []
_PHYSICAL_BOUNDARY_CACHE_MAX = 32

def _physical_boundary_signature(reference: dict[str, Any], track_name: object) -> tuple[Any, ...]:
    samples = reference.get("_samples") or {}
    sections = reference.get("sections") or ()
    section_sig = tuple(
        (x.get("id"), x.get("start_m"), x.get("turn_in_m"), x.get("min_speed_m"), x.get("end_m"))
        for x in sections if isinstance(x, dict)
    )
    resolved = str(track_name or reference.get("track_name") or "").upper()
    marker_sig: tuple[Any, ...] = ()
    if resolved:
        try:
            from .overlay.track_maps import get_track_turn_markers
            marker_sig = tuple(
                (m.get("corner_id"), m.get("lap_distance_m"), m.get("start_m"), m.get("end_m"))
                for m in (get_track_turn_markers(resolved) or ())
            )
        except Exception:
            marker_sig = ()
    return (resolved, id(samples), len(samples), reference.get("track_length_m"), section_sig, marker_sig)

def clear_physical_turn_boundary_cache() -> None:
    _PHYSICAL_BOUNDARY_CACHE.clear()
    _PHYSICAL_BOUNDARY_CACHE_ORDER.clear()

def physical_turn_boundaries(reference: dict[str, Any], *, track_name: object = None) -> list[dict[str, Any]]:
    if not isinstance(reference, dict):
        return []
    key = id(reference)
    signature = _physical_boundary_signature(reference, track_name)
    cached = _PHYSICAL_BOUNDARY_CACHE.get(key)
    if cached is not None and cached[0] is reference and cached[1] == signature:
        return [dict(row) for row in cached[2]]
    result = _physical_turn_boundaries_uncached(reference, track_name=track_name)
    frozen = tuple(dict(row) for row in result)
    _PHYSICAL_BOUNDARY_CACHE[key] = (reference, signature, frozen)
    if key in _PHYSICAL_BOUNDARY_CACHE_ORDER:
        _PHYSICAL_BOUNDARY_CACHE_ORDER.remove(key)
    _PHYSICAL_BOUNDARY_CACHE_ORDER.append(key)
    while len(_PHYSICAL_BOUNDARY_CACHE_ORDER) > _PHYSICAL_BOUNDARY_CACHE_MAX:
        old = _PHYSICAL_BOUNDARY_CACHE_ORDER.pop(0)
        _PHYSICAL_BOUNDARY_CACHE.pop(old, None)
    return [dict(row) for row in frozen]

def _value_at_axis(points: list[dict[str, Any]], distances: list[float], distance: float, key: str = "delta_s") -> float | None:
    if not points:
        return None
    i = bisect_left(distances, float(distance))
    if i <= 0:
        v = points[0].get(key)
        return float(v) if _num(v) else None
    if i >= len(points):
        v = points[-1].get(key)
        return float(v) if _num(v) else None
    p0, p1 = points[i - 1], points[i]
    d0, d1 = distances[i - 1], distances[i]
    v0, v1 = p0.get(key), p1.get(key)
    if not (_num(v0) and _num(v1)):
        return None
    if d1 <= d0:
        return float(v1)
    a = (float(distance) - d0) / (d1 - d0)
    return float(v0) + (float(v1) - float(v0)) * a


def _value_at_map(points: list[dict[str, Any]], distance: float, key: str = "delta_s") -> float | None:
    # Compatibility wrapper. Performance-critical callers build the axis once.
    return _value_at_axis(points,[float(p["distance_m"]) for p in points],distance,key)


def _phase_loss_axis(points: list[dict[str, Any]], distances: list[float], start_m: float, end_m: float) -> float | None:
    if end_m <= start_m:
        return None
    a = _value_at_axis(points,distances,start_m)
    b = _value_at_axis(points,distances,end_m)
    return (b - a) if _num(a) and _num(b) else None


def _phase_loss(points: list[dict[str, Any]], start_m: float, end_m: float) -> float | None:
    return _phase_loss_axis(points,[float(p["distance_m"]) for p in points],start_m,end_m)

def _gain_loss_zones(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compress the 5 m local map into contiguous GAIN/LOSS/NEUTRAL zones."""
    if not points:
        return []
    zones=[]; begin=0; state=str(points[0].get("gain_loss") or "NEUTRAL")
    for i in range(1,len(points)+1):
        next_state=str(points[i].get("gain_loss") or "NEUTRAL") if i<len(points) else None
        if next_state==state:
            continue
        block=points[begin:i]
        start_m=float(block[0]["distance_m"]); end_m=float(block[-1]["distance_m"])
        net=float(block[-1]["delta_s"])-float(block[0]["delta_s"]) if len(block)>1 else float(block[0].get("local_delta_s") or 0.0)
        peak=max((abs(float(x.get("window_delta_s") or 0.0)) for x in block),default=0.0)
        zones.append({
            "start_m":start_m,"end_m":end_m,"state":state,
            "net_delta_s":net,"peak_window_delta_s":peak,
        })
        begin=i; state=next_state or "NEUTRAL"
    return zones


def _segment_stats(points: list[dict[str, Any]], start_m: float, end_m: float, point_distances: list[float] | None = None) -> dict[str, Any]:
    ds=point_distances if point_distances is not None else [float(p["distance_m"]) for p in points]
    lo=bisect_right(ds,float(start_m)); hi=bisect_right(ds,float(end_m))
    rows=points[lo:hi]
    if not rows:
        return {"complete":False,"net_loss_s":None,"gross_loss_s":None,"gross_gain_s":None}
    net=_phase_loss_axis(points,ds,start_m,end_m)
    return {
        "complete":_num(net),
        "net_loss_s":net,
        "gross_loss_s":sum(max(0.0,float(p["local_delta_s"])) for p in rows),
        "gross_gain_s":sum(max(0.0,-float(p["local_delta_s"])) for p in rows),
    }


def _physical_partition(points: list[dict[str, Any]], boundaries: list[dict[str, Any]], track_length: float, point_distances: list[float] | None = None) -> list[dict[str, Any]]:
    """Partition a lap into non-overlapping STRAIGHT/TURN regions."""
    if not points or not boundaries or track_length<=0:
        return []
    coverage_start=float(points[0]["distance_m"]); coverage_end=float(points[-1]["distance_m"])
    rows=[]; cursor=0.0; straight_no=0
    ordered=sorted(boundaries,key=lambda x:float(x["start_m"]))
    for turn in ordered:
        start=max(cursor,float(turn["start_m"])); end=max(start,float(turn["end_m"]))
        if start-cursor >= 7.5:
            straight_no+=1
            complete=cursor>=coverage_start-1e-6 and start<=coverage_end+1e-6
            stats=_segment_stats(points,cursor,start,point_distances) if complete else {"complete":False,"net_loss_s":None,"gross_loss_s":None,"gross_gain_s":None}
            rows.append({
                "segment_kind":"straight","number":straight_no,"label":f"S{straight_no}",
                "start_m":cursor,"end_m":start,**stats,
            })
        complete=start>=coverage_start-1e-6 and end<=coverage_end+1e-6
        stats=_segment_stats(points,start,end,point_distances) if complete else {"complete":False,"net_loss_s":None,"gross_loss_s":None,"gross_gain_s":None}
        rows.append({
            "segment_kind":"turn","number":int(turn["corner_id"]),"label":str(turn["label"]),
            "start_m":start,"apex_m":float(turn["apex_m"]),"end_m":end,**stats,
        })
        cursor=max(cursor,end)
    if track_length-cursor >= 7.5:
        straight_no+=1
        complete=cursor>=coverage_start-1e-6 and track_length<=coverage_end+1e-6
        stats=_segment_stats(points,cursor,track_length,point_distances) if complete else {"complete":False,"net_loss_s":None,"gross_loss_s":None,"gross_gain_s":None}
        rows.append({
            "segment_kind":"straight","number":straight_no,"label":f"S{straight_no}",
            "start_m":cursor,"end_m":track_length,**stats,
        })
    return rows


def build_distance_performance_model(
    current: dict[str, Any],
    reference: dict[str, Any],
    *,
    step_m: float = 5.0,
    local_window_m: float = 25.0,
    physical_boundaries: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    include_channel_deltas: bool = True,
) -> dict[str, Any]:
    """Build the authoritative continuous current-vs-reference distance model.

    Positive delta means current is slower. The returned object contains the raw
    5 m trace, compact gain/loss zones, physical T1..Tn aggregates, and a complete
    non-overlapping turn/straight partition for lap-delta reconciliation.
    """
    cur=_sample_rows(current); ref=_sample_rows(reference)
    empty={"available":False,"points":[],"gain_loss_zones":[],"turns":[],"segments":[]}
    if len(cur)<2 or len(ref)<2:
        return {**empty,"reason":"insufficient_samples"}
    if step_m<=0: step_m=5.0
    coverage_start=max(cur[0][0],ref[0][0]); coverage_end=min(cur[-1][0],ref[-1][0])
    if coverage_end-coverage_start<step_m:
        return {**empty,"reason":"insufficient_overlap"}
    cur_ds=[x[0] for x in cur]; ref_ds=[x[0] for x in ref]
    grid_start=math.ceil(coverage_start/step_m)*step_m; grid_end=math.floor(coverage_end/step_m)*step_m
    count=int(round((grid_end-grid_start)/step_m))+1
    points=[]; prev_delta=None
    for i in range(max(0,count)):
        dist=grid_start+i*step_m
        ct=_interp(cur,cur_ds,dist,"t"); rt=_interp(ref,ref_ds,dist,"t")
        if not (_num(ct) and _num(rt)): continue
        delta=float(ct)-float(rt); local=(delta-prev_delta) if _num(prev_delta) else 0.0
        row={
            "distance_m":round(dist,3),"current_time_s":float(ct),"reference_time_s":float(rt),
            "delta_s":delta,"local_delta_s":local,"local_rate_s_per_100m":local*(100.0/step_m),
            "speed_delta_kph":None,"throttle_delta":None,"brake_delta":None,"steering_delta":None,"slip_delta":None,
        }
        # CORNER COACH already compares the live/reference input channels directly
        # for its bars and deterministic diagnosis.  Its high-frequency timing map
        # therefore skips five extra interpolation pairs per 5 m sample.  Offline
        # analysis and legacy callers keep the richer channel-delta model by default.
        if include_channel_deltas:
            for key,out_key in (("speed","speed_delta_kph"),("throttle","throttle_delta"),("brake","brake_delta"),("steering","steering_delta"),("slip","slip_delta")):
                cv=_interp(cur,cur_ds,dist,key); rv=_interp(ref,ref_ds,dist,key)
                if _num(cv) and _num(rv): row[out_key]=float(cv)-float(rv)
        points.append(row); prev_delta=delta
    if len(points)<2:
        return {**empty,"reason":"interpolation_failed"}

    window_bins=max(1,int(round(local_window_m/step_m)))
    for i,row in enumerate(points):
        j=max(0,i-window_bins)
        window=float(row["delta_s"])-float(points[j]["delta_s"])
        row["window_delta_s"]=window
        row["gain_loss"]="LOSS" if window>0.003 else ("GAIN" if window<-0.003 else "NEUTRAL")

    point_distances=[float(p["distance_m"]) for p in points]
    def phase_loss(a,b):
        return _phase_loss_axis(points,point_distances,a,b)

    track_length=reference.get("track_length_m")
    if not (_num(track_length) and float(track_length)>1000.0):
        track_length=max(ref[-1][0],cur[-1][0])
    track_length=float(track_length)
    boundaries=(list(physical_boundaries) if physical_boundaries is not None
                else physical_turn_boundaries(reference,track_name=current.get("track_name") or reference.get("track_name")))
    turns=[]
    for idx,boundary in enumerate(boundaries):
        start=float(boundary["start_m"]); brake=float(boundary["brake_m"]); turn_in=float(boundary["turn_in_m"])
        apex=float(boundary["apex_m"]); end=float(boundary["end_m"])
        own_lo=float(boundary.get("ownership_start_m",start)); own_hi=float(boundary.get("ownership_end_m",end))
        # Coaching attribution includes the approach that can causally create the
        # loss for this turn. Geometry-derived turns own the approach back to the
        # midpoint with the previous turn. Old/external references do not have
        # physical geometry, so preserve the historical non-overlapping midpoint
        # attribution (T1 owns S/F -> T1) instead of starting at the brake marker.
        if boundary.get("physical_geometry"):
            analysis_start=max(float(points[0]["distance_m"]),min(start,brake,own_lo))
        elif idx == 0:
            analysis_start=max(float(points[0]["distance_m"]),0.0)
        else:
            prev_end=float(boundaries[idx-1]["end_m"])
            analysis_start=(prev_end+start)*0.5
            analysis_start=max(float(points[0]["distance_m"]),min(start,analysis_start))
        analysis_end=end
        complete=analysis_start>=grid_start-1e-6 and end<=grid_end+1e-6
        base={**boundary,"analysis_start_m":analysis_start,"analysis_end_m":analysis_end,"complete":complete}
        if not complete:
            turns.append({**base,"net_loss_s":None,"assigned_loss_s":None,"physical_net_loss_s":None,"gross_loss_s":None,"gross_gain_s":None,
                          "entry_loss_s":None,"mid_loss_s":None,"exit_loss_s":None,"peak_local_window_loss_s":None})
            continue
        attrib=[p for p in points if analysis_start<float(p["distance_m"])<=analysis_end]
        phys=[p for p in points if start<float(p["distance_m"])<=end]
        physical_net=phase_loss(start,end)
        turns.append({
            **base,
            "net_loss_s":phase_loss(analysis_start,analysis_end),
            "assigned_loss_s":physical_net,
            "physical_net_loss_s":physical_net,
            "gross_loss_s":sum(max(0.0,float(p["local_delta_s"])) for p in attrib),
            "gross_gain_s":sum(max(0.0,-float(p["local_delta_s"])) for p in attrib),
            "physical_gross_loss_s":sum(max(0.0,float(p["local_delta_s"])) for p in phys),
            "physical_gross_gain_s":sum(max(0.0,-float(p["local_delta_s"])) for p in phys),
            "entry_loss_s":phase_loss(analysis_start,max(analysis_start,brake)),
            "mid_loss_s":phase_loss(max(analysis_start,brake),apex),
            "exit_loss_s":phase_loss(apex,analysis_end),
            "peak_local_window_loss_s":max((float(p["window_delta_s"]) for p in attrib),default=0.0),
        })

    segments=_physical_partition(points,boundaries,track_length,point_distances)
    full_net=float(points[-1]["delta_s"])-float(points[0]["delta_s"])
    complete_segment_losses=[float(x["net_loss_s"]) for x in segments if x.get("complete") and _num(x.get("net_loss_s"))]
    all_partition_complete=bool(segments) and all(x.get("complete") for x in segments)
    partition_sum=sum(complete_segment_losses) if all_partition_complete else None
    reconciliation=(full_net-partition_sum) if _num(partition_sum) else None
    return {
        "available":True,"version":2,"step_m":float(step_m),"local_window_m":float(local_window_m),
        "coverage_start_m":float(points[0]["distance_m"]),"coverage_end_m":float(points[-1]["distance_m"]),
        "track_length_m":track_length,"full_track_net_delta_s":full_net,
        "partition_net_delta_s":partition_sum,"reconciliation_error_s":reconciliation,
        "points":points,"gain_loss_zones":_gain_loss_zones(points),"turns":turns,"segments":segments,
    }

def turn_losses_by_reference_section(model: dict[str, Any]) -> dict[Any, dict[str, Any]]:
    """Index complete turn aggregates by raw reference section ID."""
    out = {}
    for turn in model.get("turns", ()) if isinstance(model, dict) else ():
        if isinstance(turn, dict) and turn.get("complete"):
            rid=turn.get("reference_section_id")
            if rid is not None:
                out[rid] = turn
    return out
