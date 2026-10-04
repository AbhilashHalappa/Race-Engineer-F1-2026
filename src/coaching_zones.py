"""Hybrid physical-corner + reference-driver event segmentation for CORNER COACH."""
from __future__ import annotations

from bisect import bisect_left
import math
from typing import Any

from .corner_coach_models import CoachingZone, DrivingEvent, PhysicalCorner


def _num(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v))


def _samples_between(samples,start,end):
    return [r for r in samples if start <= float(r.get("d",-1)) <= end]


def _nearest(samples,d,key):
    rows=[r for r in samples if _num(r.get("d")) and _num(r.get(key))]
    if not rows:return None
    row=min(rows,key=lambda r:abs(float(r["d"])-float(d)))
    return row.get(key)


def _events_for_span(events,start,end,padding=35.0):
    return [e for e in events if e.end_m >= start-padding and e.start_m <= end+padding]


def _brake_event_before(events,start,end):
    candidates=[e for e in events if e.kind in {"brake","deceleration"} and e.start_m <= end and e.end_m >= start-220.0]
    if not candidates:return None
    candidates.sort(key=lambda e:(abs(min(e.end_m,start)-start),-e.peak_value if _num(e.peak_value) else 0))
    return candidates[0]


def _full_throttle_recovery(samples,start,end):
    rows=_samples_between(samples,start,end)
    if not rows:return False
    full=[r for r in rows if _num(r.get("throttle")) and float(r["throttle"])>=0.98 and (not _num(r.get("brake")) or float(r.get("brake") or 0)<0.05)]
    # >=25 m at the normalized 5 m trace is a meaningful reset between corners.
    return len(full)>=5


def _continuous_steering(samples,start,end):
    rows=_samples_between(samples,start,end)
    if not rows:return False
    active=sum(1 for r in rows if _num(r.get("steering")) and abs(float(r["steering"]))>=0.06)
    return active/max(1,len(rows))>=0.45


def _reference_time_at(samples,d):
    rows=[r for r in samples if _num(r.get("d")) and _num(r.get("t"))]
    if not rows:return None
    ds=[float(r["d"]) for r in rows]; i=bisect_left(ds,float(d))
    if i<=0:return float(rows[0]["t"])
    if i>=len(rows):return float(rows[-1]["t"])
    a,b=rows[i-1],rows[i]; d0,d1=float(a["d"]),float(b["d"])
    if d1<=d0:return float(a["t"])
    f=(float(d)-d0)/(d1-d0)
    return float(a["t"])+(float(b["t"])-float(a["t"]))*f


def _should_merge(a:PhysicalCorner,b:PhysicalCorner,events,samples)->bool:
    gap=max(0.0,b.start_m-a.end_m)
    if gap>140.0:
        return False
    # A real acceleration reset creates a separate coaching opportunity.
    if gap>=25.0 and _full_throttle_recovery(samples,a.end_m,b.start_m):
        return False
    ta=_reference_time_at(samples,a.end_m); tb=_reference_time_at(samples,b.start_m)
    gap_time=(tb-ta) if _num(ta) and _num(tb) else None
    event_a=_brake_event_before(events,a.start_m,a.end_m)
    event_b=_brake_event_before(events,b.start_m,b.end_m)
    shared_brake=event_a is not None and event_b is not None and event_a.event_id==event_b.event_id
    steering_link=_continuous_steering(samples,max(a.apex_m,a.end_m-30.0),min(b.apex_m,b.start_m+60.0))
    short_gap=gap<=55.0
    no_pre_window=_num(gap_time) and float(gap_time)<2.0
    # Hybrid decision: two independent signals normally required. Very short
    # same-driving sequences are also merged even when a single packet family is
    # sparse, but physical corner IDs remain intact inside the zone.
    signals=sum((bool(shared_brake),bool(steering_link),bool(short_gap),bool(no_pre_window)))
    return signals>=2 or (gap<=25.0 and (shared_brake or steering_link))


def _zone_from_group(index:int,group:list[PhysicalCorner],events:tuple[DrivingEvent,...],samples:tuple[dict[str,Any],...],previous_end:float|None,track_length_m:float)->CoachingZone:
    start=group[0].start_m; end=group[-1].end_m
    relevant=_events_for_span(events,start,end,padding=120.0)
    ids=tuple(c.corner_id for c in group)
    id_set=set(ids)

    def owned(e:DrivingEvent)->bool:
        """Do not let an event from the previous physical corner leak zones.

        Pace-derived events carry ``metadata.corner_id`` and can therefore be
        associated exactly.  Legacy/input-derived events do not always carry a
        corner id; for those, a separately coachable zone may only own an event
        that starts after the previous zone's physical end.
        """
        meta=e.metadata if isinstance(e.metadata,dict) else {}
        cid=meta.get("corner_id")
        if isinstance(cid,int):
            return cid in id_set
        return previous_end is None or float(e.start_m)>=float(previous_end)-1e-6

    owned_events=[e for e in relevant if owned(e)]
    brake_candidates=[e for e in owned_events if e.kind in {"brake","deceleration"} and e.start_m<=end and e.end_m>=start-220.0]
    brake=min(brake_candidates,key=lambda e:e.start_m) if brake_candidates else None
    steer=[e for e in owned_events if e.kind in {"steering","steering_reversal"}]
    limit=end+100.0
    pickups=[e for e in owned_events if e.kind in {"throttle_pickup","acceleration_recovery"} and group[0].apex_m-20.0<=e.start_m<=limit]
    full=[e for e in owned_events if e.kind=="full_throttle" and group[0].apex_m-20.0<=e.start_m<=limit]
    throttle_event=min(pickups,key=lambda e:e.start_m) if pickups else (min(full,key=lambda e:e.start_m) if full else None)
    full_after=[e for e in full if throttle_event is None or e.start_m>=throttle_event.start_m]
    full_event=min(full_after,key=lambda e:e.start_m) if full_after else None
    # The approach may begin before geometric corner start because early braking
    # can create the loss. Never overlap the previous zone's physical region.
    approach=brake.start_m if brake is not None else max(0.0,start-120.0)
    if previous_end is not None:
        approach=max(approach,previous_end)
    # A CoachingZone must never begin after its first physical corner has
    # already started. This was visible at Melbourne T8 (2795 m vs 2785 m).
    approach=min(float(start),float(approach))
    apex=group[0].apex_m if len(group)==1 else max(group,key=lambda c:c.curvature_score or 0.0).apex_m
    block=_samples_between(samples,start,end)
    speeds=[float(r["speed"]) for r in block if _num(r.get("speed"))]
    min_speed=min(speeds) if speeds else None
    apex_speed=_nearest(samples,apex,"speed")
    exit_speed=_nearest(samples,end,"speed")
    apex_gear=_nearest(samples,apex,"gear")
    label=f"T{ids[0]}" if len(ids)==1 else f"T{ids[0]}–T{ids[-1]}"
    event_ids=tuple(e.event_id for e in owned_events if e.kind in {"brake","deceleration","brake_release","lift","steering","steering_reversal","minimum_speed","throttle_pickup","acceleration_recovery","full_throttle"})
    confidence=1.0 if brake is not None or steer else 0.75
    return CoachingZone(
        zone_id=f"Z{index}",start_m=float(start),end_m=float(end),approach_start_m=float(approach),corner_ids=ids,event_ids=event_ids,
        brake_start_m=float(brake.start_m) if brake else None,brake_release_m=float(brake.end_m) if brake else None,apex_m=float(apex),
        throttle_start_m=float(throttle_event.start_m) if throttle_event else None,full_throttle_m=float(full_event.start_m) if full_event else None,
        reference_min_speed_kph=min_speed,reference_apex_speed_kph=float(apex_speed) if _num(apex_speed) else None,
        reference_exit_speed_kph=float(exit_speed) if _num(exit_speed) else None,
        reference_gear=int(round(float(apex_gear))) if _num(apex_gear) else None,label=label,confidence=confidence,
    )


def build_coaching_zones(corners:tuple[PhysicalCorner,...],events:tuple[DrivingEvent,...],samples:tuple[dict[str,Any],...],*,track_length_m:float)->tuple[CoachingZone,...]:
    """Fuse stable physical corners and measured rival events into coachable zones."""
    if not corners:
        return ()
    ordered=sorted(corners,key=lambda c:c.apex_m)
    groups=[]; current=[ordered[0]]
    for nxt in ordered[1:]:
        if _should_merge(current[-1],nxt,events,samples):
            current.append(nxt)
        else:
            groups.append(current); current=[nxt]
    groups.append(current)
    zones=[]; prev_end=None
    for i,group in enumerate(groups,1):
        z=_zone_from_group(i,group,events,samples,prev_end,float(track_length_m))
        zones.append(z); prev_end=z.end_m
    return tuple(zones)


def active_zone(zones:tuple[CoachingZone,...]|list[CoachingZone],distance_m:float|None,*,pre_margin_m:float=0.0)->CoachingZone|None:
    if not _num(distance_m):return None
    d=float(distance_m)
    for z in zones:
        lo=max(0.0,z.approach_start_m-pre_margin_m)
        if lo<=d<=z.end_m:
            return z
    return None


def _delta_at_sorted_points(rows, distances, distance_m):
    """Interpolate delta on a pre-sorted point axis without rebuilding it.

    V1.1.0.2 hot-path note: the old zone attribution helper rebuilt and sorted
    the complete distance model for every zone *and* every straight.  A 14-turn
    track could therefore sort the same ~1000 rows dozens of times per update.
    """
    if not rows or not _num(distance_m):
        return None
    i=bisect_left(distances,float(distance_m))
    if i<=0:
        return float(rows[0]["delta_s"])
    if i>=len(rows):
        return float(rows[-1]["delta_s"])
    a,b=rows[i-1],rows[i];d0,d1=distances[i-1],distances[i]
    if d1<=d0:
        return float(a["delta_s"])
    f=(float(distance_m)-d0)/(d1-d0)
    return float(a["delta_s"])+(float(b["delta_s"])-float(a["delta_s"]))*f


def _delta_at_points(points, distance_m):
    """Compatibility wrapper used by tests/older callers."""
    rows=[p for p in (points or ()) if isinstance(p,dict) and _num(p.get("distance_m")) and _num(p.get("delta_s"))]
    rows.sort(key=lambda p:float(p["distance_m"]))
    return _delta_at_sorted_points(rows,[float(p["distance_m"]) for p in rows],distance_m)


def attribute_zone_and_straight_loss(zones, performance_model:dict[str,Any], *, track_length_m:float):
    """Partition the circuit into hybrid CoachingZones and the straights between.

    The partition uses each zone's non-overlapping approach start through exit.
    This lets early-braking loss belong to the relevant coaching problem while
    preserving a complete lap reconciliation. Positive net values mean slower.
    """
    points=[p for p in ((performance_model or {}).get("points") or ()) if isinstance(p,dict) and _num(p.get("distance_m")) and _num(p.get("delta_s"))]
    if not points or not zones or not _num(track_length_m) or float(track_length_m)<=0:
        return {"available":False,"zones":[],"straights":[],"segments":[],"reconciliation_error_s":None}
    # Build the interpolation axis once per attribution pass.  This replaces the
    # previous O(segment_count * point_count log point_count) repeated sorting.
    points.sort(key=lambda p:float(p["distance_m"]))
    point_distances=[float(p["distance_m"]) for p in points]
    coverage_start=point_distances[0];coverage_end=point_distances[-1]
    ordered=sorted(zones,key=lambda z:z.approach_start_m)
    segments=[];zone_rows=[];straight_rows=[];cursor=0.0;straight_no=0

    def add(kind,label,start,end,zone=None):
        nonlocal straight_no
        if end<=start+1e-9:
            return
        complete=start>=coverage_start-1e-6 and end<=coverage_end+1e-6
        a=_delta_at_sorted_points(points,point_distances,start) if complete else None
        b=_delta_at_sorted_points(points,point_distances,end) if complete else None
        net=(b-a) if _num(a) and _num(b) else None
        row={"segment_kind":kind,"label":label,"start_m":float(start),"end_m":float(end),"complete":bool(complete),"net_loss_s":net}
        if zone is not None:
            row.update({"zone_id":zone.zone_id,"corner_ids":list(zone.corner_ids)})
            zone_rows.append(row)
        else:
            straight_rows.append(row)
        segments.append(row)

    for z in ordered:
        start=max(cursor,float(z.approach_start_m));end=max(start,float(z.end_m))
        if start>cursor+1e-6:
            straight_no+=1;add("straight",f"S{straight_no}",cursor,start)
        add("zone",z.public_label,start,end,z)
        cursor=max(cursor,end)
    length=float(track_length_m)
    if length>cursor+1e-6:
        straight_no+=1;add("straight",f"S{straight_no}",cursor,length)

    full_net=(float(points[-1]["delta_s"])-float(points[0]["delta_s"]))
    all_complete=bool(segments) and all(x["complete"] for x in segments)
    partition=sum(float(x["net_loss_s"]) for x in segments) if all_complete and all(_num(x.get("net_loss_s")) for x in segments) else None
    reconciliation=(full_net-partition) if _num(partition) else None
    return {"available":True,"zones":zone_rows,"straights":straight_rows,"segments":segments,"full_track_net_delta_s":full_net,"partition_net_delta_s":partition,"reconciliation_error_s":reconciliation}
