"""Deterministic physical circuit geometry helpers.

Map geometry is learned from measured world X/Z samples indexed by F1 lap
 distance.  Physical T1..Tn labels are derived from circuit curvature, never
 from the driver's braking zones.  The expected turn count is only used to
 split/merge continuous curvature into the circuit's published corner count;
 turn locations themselves always come from measured geometry.
"""
from __future__ import annotations

from bisect import bisect_left
import math
from typing import Any, Iterable
import json
from pathlib import Path

from .app_paths import TRACK_MAPS


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def canonical_track_name(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = getattr(value, "name", None) or getattr(value, "label", None) or str(value)
    name = str(value).strip().upper()
    return name or None


# Published physical corner counts for circuits currently represented by the
# Race Engineer map layer. These counts are *not* braking-zone counts.
PHYSICAL_TURN_COUNTS: dict[str, int] = {
    "MELBOURNE": 14,
    "SHANGHAI": 16,
    "SAKHIR (BAHRAIN)": 15,
    "CATALUNYA": 14,
    "MONACO": 19,
    "MONTREAL": 14,
    "SILVERSTONE": 18,
    "HUNGARORING": 14,
    "SPA": 19,
    "MONZA": 11,
    "SINGAPORE": 19,
    "SUZUKA": 18,
    "ABU DHABI": 16,
    "TEXAS": 20,
    "BRAZIL": 15,
    "AUSTRIA": 10,
    "MEXICO": 17,
    "BAKU (AZERBAIJAN)": 20,
    "ZANDVOORT": 14,
    "IMOLA": 19,
    "JEDDAH": 27,
    "MIAMI": 19,
    "LAS VEGAS": 17,
    "LOSAIL": 16,
    "MADRID": 22,
}
for _reverse, _normal in (
    ("SILVERSTONE (REVERSE)", "SILVERSTONE"),
    ("AUSTRIA (REVERSE)", "AUSTRIA"),
    ("ZANDVOORT (REVERSE)", "ZANDVOORT"),
):
    PHYSICAL_TURN_COUNTS[_reverse] = PHYSICAL_TURN_COUNTS[_normal]


def expected_turn_count(track_name: object) -> int | None:
    name = canonical_track_name(track_name)
    return PHYSICAL_TURN_COUNTS.get(name) if name else None


def _track_model_filename(track_name: object) -> str | None:
    name=canonical_track_name(track_name)
    if not name:
        return None
    chars=[];last_sep=False
    for ch in name:
        if ch.isalnum():
            chars.append(ch);last_sep=False
        elif not last_sep:
            chars.append('_');last_sep=True
    stem=''.join(chars).strip('_')
    return (stem or 'TRACK')+'.json'


def persisted_physical_turns(track_name: object, track_length_m: object=None) -> tuple[dict[str,Any], ...]:
    """Read the shared adaptive T1..Tn authority without importing the UI layer.

    The file is written by the map/geometry learner, but this lightweight reader
    lets reference compilation and CORNER COACH consume the same physical model.
    """
    filename=_track_model_filename(track_name)
    if not filename:
        return ()
    # Structured local-data root is the current authority. Keep the legacy
    # project-relative path as a read-only fallback for older installs that have
    # not completed migration yet.
    candidates=(
        Path(TRACK_MAPS)/filename,
        Path(__file__).resolve().parents[1]/'maps'/'tracks'/filename,
    )
    payload=None
    for path in candidates:
        try:
            payload=json.loads(path.read_text(encoding='utf-8'))
            break
        except (OSError,ValueError,TypeError,json.JSONDecodeError):
            continue
    if not isinstance(payload,dict):
        return ()
    if not isinstance(payload,dict):
        return ()
    stored_len=payload.get('track_length_m')
    if _num(track_length_m) and _num(stored_len):
        length=float(track_length_m)
        if abs(float(stored_len)-length)>max(20.0,length*0.006):
            return ()
    rows=[]
    for raw in payload.get('turns') or ():
        if not isinstance(raw,dict) or not all(_num(raw.get(k)) for k in ('start_m','apex_m','end_m')):
            continue
        cid=raw.get('corner_id')
        if not isinstance(cid,int) or cid<=0:
            continue
        rows.append({
            'corner_id':cid,'label':str(raw.get('label') or f'T{cid}'),
            'start_m':float(raw['start_m']),'apex_m':float(raw['apex_m']),'end_m':float(raw['end_m']),
            'lap_distance_m':float(raw.get('lap_distance_m') if _num(raw.get('lap_distance_m')) else raw['apex_m']),
            'turn_direction':raw.get('turn_direction'),
            'curvature_score':float(raw['curvature_score']) if _num(raw.get('curvature_score')) else None,
            'geometry_authority':'adaptive_track_model',
        })
    rows.sort(key=lambda r:r['apex_m'])
    expected=expected_turn_count(track_name)
    if expected and len(rows)!=expected:
        return ()
    for i,row in enumerate(rows,1):
        row['corner_id']=i;row['label']=f'T{i}'
    return tuple(rows)


def _sample_value(row: object, *keys: str):
    for key in keys:
        value = row.get(key) if isinstance(row, dict) else getattr(row, key, None)
        if _num(value):
            return float(value)
    return None


def measured_world_trace(samples: object, *, require_start: bool = True) -> list[tuple[float, float, float]]:
    """Return distance-sorted (d, world_x, world_z) samples with spike rejection.

    F1 packet families are asynchronous. Around S/F, a lap-data packet can
    advance before the next motion packet. A single stale world point must never
    create a 100-250 m diagonal chord across the learned map, so obvious isolated
    position spikes are removed before any map is rendered or persisted.
    """
    if not isinstance(samples, dict):
        return []
    rows: list[tuple[float, float, float]] = []
    for raw_d, row in samples.items():
        try:
            d = float(raw_d)
        except (TypeError, ValueError):
            continue
        if not _num(d):
            continue
        x = _sample_value(row, "world_x", "world_x_m")
        z = _sample_value(row, "world_z", "world_z_m")
        if x is None or z is None:
            continue
        rows.append((d, x, z))
    rows.sort(key=lambda r: r[0])
    if len(rows) < 3:
        return rows

    # Deduplicate equal distance bins (newest dict value has already won).
    dedup: list[tuple[float, float, float]] = []
    for row in rows:
        if dedup and abs(row[0] - dedup[-1][0]) < 1e-6:
            dedup[-1] = row
        else:
            dedup.append(row)
    rows = dedup

    def jump(a, b):
        return math.hypot(b[1] - a[1], b[2] - a[2])

    def plausible(a, b):
        dd = max(0.5, b[0] - a[0])
        # Euclidean displacement cannot materially exceed travelled distance.
        # The generous floor tolerates asynchronous packet timing and pit jitter.
        return jump(a, b) <= max(18.0, dd * 2.8)

    # Leading/trailing stale motion samples are common exactly at an S/F reset.
    while len(rows) >= 3 and not plausible(rows[0], rows[1]) and plausible(rows[1], rows[2]):
        rows.pop(0)
    while len(rows) >= 3 and not plausible(rows[-2], rows[-1]) and plausible(rows[-3], rows[-2]):
        rows.pop()

    # Remove isolated interior spikes only when bypassing the point restores a
    # physically plausible path. Never bridge a genuinely missing long section.
    cleaned: list[tuple[float, float, float]] = []
    i = 0
    while i < len(rows):
        cur = rows[i]
        if cleaned and not plausible(cleaned[-1], cur):
            # Motion packets can briefly lag lap-distance packets, especially at
            # S/F or after garage/pit transitions.  A *short* burst of stale
            # positions must not invalidate an otherwise complete measured path.
            # Scan only a few samples ahead and only across a small lap-distance
            # span; this cannot bridge a genuinely missing circuit section.
            reconnect=None
            for look_ahead in range(1, min(5, len(rows)-i)):
                candidate=rows[i+look_ahead]
                if candidate[0]-cleaned[-1][0] > 25.0:
                    break
                if plausible(cleaned[-1], candidate):
                    reconnect=i+look_ahead
                    break
            if reconnect is not None:
                i=reconnect
                continue
        if not cleaned or plausible(cleaned[-1], cur):
            cleaned.append(cur)
        else:
            # A sustained discontinuity means the trace is not safe to draw.
            return []
        i += 1

    if require_start and (not cleaned or cleaned[0][0] > 15.0):
        return []
    return cleaned


def trace_is_complete(trace: Iterable[tuple[float, float, float]], track_length_m: object) -> bool:
    rows = list(trace)
    if len(rows) < 100 or not _num(track_length_m) or float(track_length_m) <= 1000.0:
        return False
    length = float(track_length_m)
    if rows[0][0] > 15.0 or rows[-1][0] < length - max(35.0, length * 0.008):
        return False
    # A complete circuit must close spatially near S/F. This catches the exact
    # failure where a stale post-line motion point caused a long diagonal chord.
    closure = math.hypot(rows[-1][1] - rows[0][1], rows[-1][2] - rows[0][2])
    return closure <= max(35.0, length * 0.012)


def _resample_by_distance(
    points: list[tuple[float, float]],
    distances: list[float],
    track_length_m: float,
    *,
    step_m: float = 5.0,
) -> tuple[list[tuple[float, float]], list[float]]:
    if len(points) < 3 or len(points) != len(distances):
        return [], []
    rows = sorted(zip(distances, points), key=lambda x: x[0])
    ds = [float(d) for d, _ in rows]
    ps = [p for _, p in rows]
    # Add the exact lap end using the S/F point so curvature is circular.
    if ds[-1] < track_length_m - 1e-6:
        ds.append(track_length_m)
        ps.append(ps[0])
    grid = []
    out = []
    d = 0.0
    j = 1
    while d < track_length_m:
        while j < len(ds) and ds[j] < d:
            j += 1
        if j >= len(ds):
            break
        i = max(0, j - 1)
        d0, d1 = ds[i], ds[j]
        p0, p1 = ps[i], ps[j]
        if d1 <= d0:
            x, y = p1
        else:
            a = max(0.0, min(1.0, (d - d0) / (d1 - d0)))
            x = p0[0] + (p1[0] - p0[0]) * a
            y = p0[1] + (p1[1] - p0[1]) * a
        grid.append(d)
        out.append((x, y))
        d += step_m
    return out, grid


def _smooth_circular(points: list[tuple[float, float]], radius: int = 2) -> list[tuple[float, float]]:
    n = len(points)
    if n == 0:
        return []
    out = []
    for i in range(n):
        xs = ys = 0.0
        count = 0
        for off in range(-radius, radius + 1):
            x, y = points[(i + off) % n]
            xs += x; ys += y; count += 1
        out.append((xs / count, ys / count))
    return out


def _circular_smooth_scalar(values: list[float], radius: int = 2) -> list[float]:
    n = len(values)
    if n == 0:
        return []
    out=[]
    for i in range(n):
        out.append(sum(values[(i+j) % n] for j in range(-radius, radius+1)) / float(radius*2+1))
    return out


def _corner_activity_regions(
    signed_curvature: list[float],
    *,
    step_m: float,
    expected_count: int,
) -> list[tuple[int, int, float]]:
    """Return broad physical corner regions on a circular curvature trace.

    The old implementation simply selected the N largest curvature samples. On
    hairpins and long constant-radius complexes that placed several T labels on
    the same physical corner. Here we first identify *regions* of sustained
    curvature, then split only broad/high-heading-change complexes when the known
    circuit turn count requires it.
    """
    n=len(signed_curvature)
    if n == 0:
        return []
    activity=[abs(v) for v in signed_curvature]
    positive=[v for v in activity if v > 1e-9]
    if not positive:
        return []
    ordered=sorted(positive)
    q=ordered[min(len(ordered)-1, int(round((len(ordered)-1)*0.45)))]
    threshold=max(0.018, min(0.055, q*0.90))

    # Cut the circular trace at its straightest point. This prevents one physical
    # corner from being split merely because array index zero happens to fall in it.
    cut=min(range(n), key=lambda i: activity[i])
    a=activity[cut:]+activity[:cut]
    s=signed_curvature[cut:]+signed_curvature[:cut]
    active=[v >= threshold for v in a]

    # Fill tiny telemetry holes only when curvature direction agrees either side.
    max_gap=max(2, int(round(20.0 / max(1.0, step_m))))
    i=0
    while i<n:
        if active[i]:
            i+=1; continue
        j=i
        while j<n and not active[j]:
            j+=1
        if i>0 and j<n and (j-i)<=max_gap:
            left=1 if s[i-1] > 0 else (-1 if s[i-1] < 0 else 0)
            right=1 if s[j] > 0 else (-1 if s[j] < 0 else 0)
            if left and left == right:
                active[i:j]=[True]*(j-i)
        i=j

    # Reject very small wiggles/noise. Integrated curvature is intentionally used
    # rather than only peak curvature so a broad medium-speed corner survives.
    min_bins=max(3, int(round(15.0 / max(1.0, step_m))))
    min_mass=0.50
    regions=[]
    i=0
    while i<n:
        if not active[i]:
            i+=1; continue
        j=i
        while j<n and active[j]:
            j+=1
        mass=sum(a[i:j])
        if (j-i) >= min_bins and mass >= min_mass:
            regions.append([i, j-1, mass])
        i=j

    if not regions:
        # Degenerate but deterministic fallback: treat the full lap as one curved
        # region and let the expected count split it by accumulated curvature.
        regions=[[0, n-1, sum(a)]]

    # If noise still created more regions than published physical corners, remove
    # the weakest regions first. Their samples remain part of straight attribution.
    while len(regions) > expected_count:
        weakest=min(range(len(regions)), key=lambda k: regions[k][2])
        regions.pop(weakest)

    # Allocate the remaining physical turns among broad complexes. Repeatedly
    # splitting the region with the largest curvature mass per current split
    # produces well-spaced sub-turns instead of clustered local maxima.
    allocation=[1]*len(regions)
    remaining=max(0, expected_count-len(regions))
    while remaining and regions:
        scores=[]
        for idx,(lo,hi,mass) in enumerate(regions):
            length_m=(hi-lo+1)*step_m
            capacity=max(1, int(length_m // 45.0))
            score=(mass / (allocation[idx] ** 1.45)) if allocation[idx] < capacity else -1.0
            scores.append(score)
        best=max(range(len(scores)), key=scores.__getitem__)
        if scores[best] < 0:
            # Dense street circuits can contain physically distinct corners less
            # than 45 m apart. Relax capacity only after every normal split is used.
            best=max(range(len(regions)), key=lambda k: regions[k][2] / (allocation[k] ** 1.45))
        allocation[best]+=1
        remaining-=1

    out=[]
    for (lo,hi,mass), pieces in zip(regions, allocation):
        vals=a[lo:hi+1]
        cumulative=[]; total=0.0
        for v in vals:
            total+=v; cumulative.append(total)
        bounds=[lo]
        for piece in range(1,pieces):
            target=total*piece/pieces if total>0 else (hi-lo+1)*piece/pieces
            rel=0
            while rel < len(cumulative)-1 and cumulative[rel] < target:
                rel+=1
            candidate=lo+rel
            # Prefer a nearby curvature valley as the boundary between two turns
            # in one continuous complex, while retaining minimum spacing.
            radius=max(3, int(round(35.0/max(1.0,step_m))))
            search_lo=max(bounds[-1]+3, candidate-radius)
            search_hi=min(hi-3, candidate+radius)
            if search_hi >= search_lo:
                candidate=min(range(search_lo, search_hi+1), key=lambda x:a[x])
            bounds.append(candidate)
        bounds.append(hi+1)
        for piece in range(pieces):
            begin=bounds[piece]
            finish=bounds[piece+1]-1
            if finish < begin:
                continue
            peak=max(a[x] for x in range(begin,finish+1))
            high=[x for x in range(begin,finish+1) if a[x]>=peak*0.82]
            if high:
                total=sum(a[x] for x in high)
                centre=sum(x*a[x] for x in high)/max(1e-9,total)
                apex=min(high,key=lambda x:abs(x-centre))
            else:
                apex=max(range(begin, finish+1), key=lambda x:a[x])
            # Convert rotated indices back to original circular-grid indices.
            oi=lambda idx:(idx+cut)%n
            out.append((oi(begin), oi(apex), oi(finish), a[apex], 1 if s[apex]>=0 else -1))
    return out


def derive_physical_turns(
    track_name: object,
    points: Iterable[tuple[float, float]],
    *,
    point_distances_m: Iterable[float] | None = None,
    track_length_m: object = None,
    turn_count: int | None = None,
) -> tuple[dict[str, object], ...]:
    """Derive physical T1..Tn regions from measured circuit curvature.

    Each returned marker contains an apex distance plus geometry-derived start/end
    boundaries. The published circuit turn count controls only how broad curvature
    complexes are split; braking behaviour never creates or renumbers a corner.
    """
    name=canonical_track_name(track_name)
    pts=[(float(p[0]), float(p[1])) for p in points]
    if len(pts)>1 and math.hypot(pts[-1][0]-pts[0][0], pts[-1][1]-pts[0][1]) < 1e-6:
        pts=pts[:-1]
    if len(pts)<20:
        return ()
    count=int(turn_count or expected_turn_count(name) or 0)
    if count<=0:
        return ()

    raw_ds=list(point_distances_m or ())
    if len(raw_ds)==len(pts)+1:
        raw_ds=raw_ds[:-1]
    if len(raw_ds)!=len(pts) or not all(_num(x) for x in raw_ds):
        cumulative=[0.0]; total=0.0
        for a,b in zip(pts,pts[1:]):
            total+=math.hypot(b[0]-a[0], b[1]-a[1]); cumulative.append(total)
        total+=math.hypot(pts[0][0]-pts[-1][0], pts[0][1]-pts[-1][1])
        length=float(track_length_m) if _num(track_length_m) and float(track_length_m)>1000 else total
        raw_ds=[x/max(1e-9,total)*length for x in cumulative]
    length=float(track_length_m) if _num(track_length_m) and float(track_length_m)>1000 else None
    if length is None:
        length=max((float(x) for x in raw_ds), default=0.0)
        if len(pts)>=2:
            length+=math.hypot(pts[0][0]-pts[-1][0], pts[0][1]-pts[-1][1])
    if length<=1000:
        return ()

    step_m=5.0
    grid_pts,grid_ds=_resample_by_distance(pts,[float(x) for x in raw_ds],length,step_m=step_m)
    if len(grid_pts)<count*4:
        return ()
    smooth=_smooth_circular(grid_pts,2)
    n=len(smooth); look=4
    signed=[]
    for i in range(n):
        px,py=smooth[(i-look)%n]; cx,cy=smooth[i]; nx,ny=smooth[(i+look)%n]
        v1=(cx-px,cy-py); v2=(nx-cx,ny-cy)
        cross=v1[0]*v2[1]-v1[1]*v2[0]
        dot=v1[0]*v2[0]+v1[1]*v2[1]
        signed.append(math.atan2(cross,dot))
    signed=_circular_smooth_scalar(signed,2)
    regions=_corner_activity_regions(signed,step_m=step_m,expected_count=count)
    if len(regions)!=count:
        return ()

    markers=[]
    for begin_i,apex_i,end_i,peak,turn_sign in regions:
        start=float(grid_ds[begin_i]); apex=float(grid_ds[apex_i]); end=float(grid_ds[end_i])
        # A region that crosses S/F is represented with end_m > track length so
        # consumers can still reason about its width. Normal circuits place S/F on
        # a straight, but this keeps the helper mathematically complete.
        if end < start:
            end+=length
        if apex < start:
            apex+=length
        markers.append({
            "corner_id":0,
            "label":"",
            "lap_distance_m":round(apex % length,3),
            "start_m":round(start % length,3),
            "apex_m":round(apex % length,3),
            "end_m":round(end if end<=length else end,3),
            "turn_direction":"RIGHT" if turn_sign>0 else "LEFT",
            "curvature_score":float(peak),
        })
    markers.sort(key=lambda x:float(x["lap_distance_m"]))
    for idx,row in enumerate(markers,1):
        row["corner_id"]=idx; row["label"]=f"T{idx}"
    return tuple(markers)

def physical_turns_from_lap(lap: dict[str, Any], *, track_name: object = None) -> tuple[dict[str, object], ...]:
    """Derive T1..Tn directly from a measured lap's world geometry."""
    if not isinstance(lap, dict):
        return ()
    trace = measured_world_trace(lap.get("_samples") or {}, require_start=False)
    if len(trace) < 20:
        return ()
    name = track_name or lap.get("track_name")
    length = lap.get("track_length_m")
    if not _num(length):
        length = max((d for d, _, _ in trace), default=0.0)
    pts = [(x, z) for _, x, z in trace]
    ds = [d for d, _, _ in trace]
    return derive_physical_turns(name, pts, point_distances_m=ds, track_length_m=length)
