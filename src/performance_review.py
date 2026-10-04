"""V2.0.4 deterministic post-session Performance Review core.

Consumes the already-measured session coach report.  It does not redetect corners
or driving events and is intentionally built outside the packet-rate path.
"""
from __future__ import annotations

from dataclasses import fields
from statistics import mean, median
from typing import Any
import math

from .coaching_analysis import CornerAnalysis
from .performance_scoring import (
    CompatibilityState, ScoreStatus, build_corner_technique_score,
    build_lap_technique_score, score_grade,
)

REVIEW_MODEL_VERSION = "2.0.4"


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _corner_analysis(row: dict[str, Any]) -> CornerAnalysis | None:
    if not isinstance(row, dict):
        return None
    names = {f.name for f in fields(CornerAnalysis)}
    data = {k: v for k, v in row.items() if k in names}
    # Old serialized rows can omit fields added later only when those fields have defaults.
    try:
        if isinstance(data.get("confidence_reasons"), list):
            data["confidence_reasons"] = tuple(str(x) for x in data["confidence_reasons"])
        return CornerAnalysis(**data)
    except (TypeError, ValueError):
        return None


def _robust(values: list[float]) -> float | None:
    vals = sorted(float(x) for x in values if _num(x))
    if not vals:
        return None
    if len(vals) < 5:
        return float(median(vals))
    trim = max(1, int(len(vals) * 0.1))
    core = vals[trim:-trim] if len(vals) > trim * 2 else vals
    return float(mean(core))





def aggregate_session_from_lap_scores(review: dict[str, Any]) -> dict[str, Any]:
    """Rebuild only the session aggregate from authoritative per-lap scores.

    This intentionally does not recalculate any lap score or confidence.  It
    consumes the already-persisted per-lap scoring result and applies the same
    robust session aggregation used by build_performance_review().
    """
    if not isinstance(review, dict):
        return review
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    # lap_reviews is the authoritative persisted lap-level view used by the Hub.
    # Older persisted review rows can keep the lap number on the outer
    # lap_reviews item while the inner summary contains score/confidence only.
    # Preserve that identity so session aggregation consumes the exact same
    # per-lap score that the individual lap view displays.
    for item in review.get("lap_reviews") or []:
        if not isinstance(item, dict):
            continue
        row = dict(item.get("summary")) if isinstance(item.get("summary"), dict) else dict(item)
        lap = row.get("lap")
        if not isinstance(lap, int) and isinstance(item.get("lap"), int):
            lap = int(item["lap"])
            row["lap"] = lap
        if isinstance(lap, int) and lap not in seen:
            rows.append(row); seen.add(lap)
    # Older reviews may have only the compact laps list.
    for row in review.get("laps") or []:
        if not isinstance(row, dict):
            continue
        lap = row.get("lap")
        if isinstance(lap, int) and lap not in seen:
            rows.append(row); seen.add(lap)

    scored = [row for row in rows if _num(row.get("score"))]
    scores = [float(row["score"]) for row in scored]
    session_score = _robust(scores) if len(scores) >= 2 else None
    confs = [float(row["confidence"]) for row in scored if _num(row.get("confidence"))]
    session_conf = _robust(confs)

    out = dict(review)
    out["session_technique_score"] = round(session_score, 1) if _num(session_score) else None
    out["session_grade"] = score_grade(session_score)
    out["confidence"] = round(session_conf, 3) if _num(session_conf) else 0.0

    dq = dict(out.get("data_quality") or {})
    scored_laps = [int(row["lap"]) for row in scored if isinstance(row.get("lap"), int)]
    # A persisted per-lap score is itself the output of the existing lap
    # eligibility + scoring contract.  Keep the session eligibility display in
    # sync with those score-bearing laps without changing any lap gate.
    existing = [int(x) for x in (dq.get("eligible_laps") or []) if isinstance(x, int)]
    dq["eligible_laps"] = sorted(set(existing).union(scored_laps))
    dq["scored_laps"] = scored_laps
    out["data_quality"] = dq
    return out

def _agg(rows: list[dict[str, Any]], key: str) -> float | None:
    vals=[float(r.get(key)) for r in rows if isinstance(r,dict) and _num(r.get(key))]
    return _robust(vals) if vals else None

def _corner_detail(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate review-only technique evidence for one physical corner.

    V2.0.4 deliberately consumes measurements already produced by CornerAnalysis /
    live CORNER COACH.  It never redetects a corner or changes coaching authority.
    Missing/untrusted evidence stays N/A.
    """
    metrics=(
        # Braking phase
        'brake_onset_delta_m','peak_brake_delta','brake_release_delta_m',
        'brake_release_ramp_delta_m','brake_release_ramp_delta_s','trail_brake_delta_m',
        'brake_duration_delta_m','entry_time_loss_s',
        # Mid-corner phase
        'turn_in_delta_m','apex_delta_m','min_speed_delta_kph','apex_speed_delta_kph',
        'steering_corrections_delta','steering_smoothness_delta','mid_time_loss_s',
        # Exit phase
        'throttle_pickup_delta_m','throttle_pickup_after_apex_delta_s',
        'pickup_to_full_throttle_delta_m','pickup_to_full_throttle_delta_s',
        'full_throttle_delta_m','exit_speed_delta_kph','max_slip_delta',
        'steering_unwind_delta_s','exit_time_loss_s',
        # Whole corner
        'time_loss_s'
    )
    out={k:(round(v,4) if _num(v:=_agg(rows,k)) else None) for k in metrics}
    out['phase_time_cost_s']={
        'braking':out.get('entry_time_loss_s'),
        'mid_corner':out.get('mid_time_loss_s'),
        'exit':out.get('exit_time_loss_s'),
    }
    return out


def _secondary_evidence(rows: list[dict[str, Any]], dominant_code: str | None) -> list[dict[str, Any]]:
    """Return review-only supporting issues ranked by measured phase cost/confidence."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row,dict):
            continue
        for cand in row.get('issue_candidates') or []:
            if not isinstance(cand,dict):
                continue
            code=str(cand.get('code') or '')
            if not code or code==dominant_code:
                continue
            grouped.setdefault(code,[]).append(cand)
    out=[]
    for code, vals in grouped.items():
        costs=[float(x['estimated_time_cost_s']) for x in vals if _num(x.get('estimated_time_cost_s'))]
        confs=[float(x['confidence']) for x in vals if _num(x.get('confidence'))]
        mags=[float(x['magnitude']) for x in vals if _num(x.get('magnitude'))]
        first=vals[0]
        out.append({
            'code':code,
            'label':first.get('label') or code.replace('_',' ').title(),
            'phase':first.get('phase'),
            'mean_estimated_time_cost_s':round(_robust(costs),4) if costs and _num(_robust(costs)) else None,
            'confidence':round(_robust(confs),3) if confs and _num(_robust(confs)) else 0.0,
            'magnitude':round(_robust(mags),4) if mags and _num(_robust(mags)) else None,
            'observations':len(vals),
            'review_only':True,
        })
    out.sort(key=lambda x:(float(x.get('mean_estimated_time_cost_s') or 0.0),float(x.get('confidence') or 0.0)),reverse=True)
    return out[:5]

def _interp_series(rows: list[list[float]], d: float) -> float | None:
    pts=sorted((float(x[0]),float(x[1])) for x in rows if isinstance(x,(list,tuple)) and len(x)>=2 and _num(x[0]) and _num(x[1]))
    if not pts: return None
    if d<=pts[0][0]: return pts[0][1]
    if d>=pts[-1][0]: return pts[-1][1]
    for (a,av),(b,bv) in zip(pts,pts[1:]):
        if a<=d<=b:
            t=(d-a)/(b-a) if b>a else 0.0
            return av+(bv-av)*t
    return None

def _first_crossing(rows: list[list[float]], start: float, end: float, threshold: float, *, rising: bool=True) -> float | None:
    pts=sorted((float(x[0]),float(x[1])) for x in rows if isinstance(x,(list,tuple)) and len(x)>=2 and _num(x[0]) and _num(x[1]) and start<=float(x[0])<=end)
    if not pts: return None
    for d,v in pts:
        if (v>=threshold) if rising else (v<=threshold): return d
    return None


def _last_before_release(rows: list[list[float]], onset: float | None, end: float, threshold: float=0.05) -> float | None:
    if not _num(onset): return None
    pts=sorted((float(x[0]),float(x[1])) for x in rows if isinstance(x,(list,tuple)) and len(x)>=2 and _num(x[0]) and _num(x[1]) and float(onset)<=float(x[0])<=end)
    armed=False
    for d,v in pts:
        if v>=0.10: armed=True
        elif armed and v<=threshold: return d
    return None

def _range_peak(rows: list[list[float]], start: float, end: float) -> float | None:
    vals=[float(x[1]) for x in rows if isinstance(x,(list,tuple)) and len(x)>=2 and _num(x[0]) and _num(x[1]) and start<=float(x[0])<=end]
    return max(vals) if vals else None

def _phase_cost(delta_trace: list[list[float]], a: float, b: float) -> float | None:
    va=_interp_series(delta_trace,a); vb=_interp_series(delta_trace,b)
    return (float(vb)-float(va)) if _num(va) and _num(vb) else None

def _time_from_speed(rows: list[list[float]]) -> list[list[float]]:
    pts=sorted((float(x[0]),float(x[1])) for x in rows if isinstance(x,(list,tuple)) and len(x)>=2 and _num(x[0]) and _num(x[1]) and float(x[1])>1.0)
    if len(pts)<2: return []
    out=[[pts[0][0],0.0]]; total=0.0
    for (d0,v0),(d1,v1) in zip(pts,pts[1:]):
        ds=max(0.0,d1-d0); vm=max(1.0,(v0+v1)/2.0)/3.6
        total += ds/vm
        out.append([d1,total])
    return out

def _selected_delta_trace(driver_speed: list[list[float]], reference_speed: list[list[float]]) -> list[list[float]]:
    dt=_time_from_speed(driver_speed); rt=_time_from_speed(reference_speed)
    if len(dt)<2 or len(rt)<2: return []
    distances=sorted(set(float(x[0]) for x in dt))
    out=[]; base=None
    for d in distances:
        a=_interp_series(dt,d); b=_interp_series(rt,d)
        if not (_num(a) and _num(b)): continue
        val=float(a)-float(b)
        if base is None: base=val
        out.append([round(d,3),round(val-base,6)])
    return out

def build_selected_reference_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    """Deterministic visual-reference comparison from stored distance traces.

    This is intentionally separate from the authoritative recorded score/diagnosis.
    It lets the review visibly react when the user selects another compatible reference.
    """
    vr=payload.get('visual_reference') if isinstance(payload.get('visual_reference'),dict) else None
    if not vr: return {'available':False,'reason':'recorded_reference_analysis'}
    telem=vr.get('telemetry') if isinstance(vr.get('telemetry'),dict) else {}
    speed=telem.get('speed_kph') if isinstance(telem.get('speed_kph'),dict) else {}
    ds=[x for x in speed.get('driver') or [] if isinstance(x,(list,tuple)) and len(x)>=2 and _num(x[0]) and _num(x[1])]
    rs=[x for x in speed.get('reference') or [] if isinstance(x,(list,tuple)) and len(x)>=2 and _num(x[0]) and _num(x[1])]
    if len(ds)<3 or len(rs)<3: return {'available':False,'reason':'insufficient_selected_reference_trace'}
    selected_delta=_selected_delta_trace(ds,rs)
    if selected_delta and isinstance(vr.get('telemetry'),dict):
        vr['telemetry']['delta_s']={'driver':selected_delta,'reference':[[d,0.0] for d,_v in selected_delta]}
    geom=payload.get('track_geometry') if isinstance(payload.get('track_geometry'),dict) else {}
    corners=[]
    for c in geom.get('corners') or []:
        if not isinstance(c,dict) or not isinstance(c.get('corner_id'),int): continue
        start=c.get('start_m'); end=c.get('end_m'); apex=c.get('apex_m',c.get('lap_distance_m'))
        if not (_num(start) and _num(end)): continue
        start=float(start); end=float(end); apex=float(apex) if _num(apex) else (start+end)/2
        entry=max(start, start-0.0); exit_d=end
        dvals=[float(x[0]) for x in ds if start<=float(x[0])<=end]
        rvals=[float(x[0]) for x in rs if start<=float(x[0])<=end]
        if not dvals or not rvals: continue
        sample_d=sorted(set(dvals+rvals))
        diffs=[]
        for d in sample_d:
            a=_interp_series(ds,d); b=_interp_series(rs,d)
            if _num(a) and _num(b): diffs.append(float(a)-float(b))
        brake=telem.get('brake') if isinstance(telem.get('brake'),dict) else {}
        throttle=telem.get('throttle') if isinstance(telem.get('throttle'),dict) else {}
        dbr=brake.get('driver') or []; rbr=brake.get('reference') or []
        dth=throttle.get('driver') or []; rth=throttle.get('reference') or []
        approach=max(0,start-180)
        db=_first_crossing(dbr,approach,end,0.08); rb=_first_crossing(rbr,approach,end,0.08)
        dr=_last_before_release(dbr,db,apex+80); rr=_last_before_release(rbr,rb,apex+80)
        dp=_range_peak(dbr,approach,apex); rp=_range_peak(rbr,approach,apex)
        dt=_first_crossing(dth,apex,end+220,0.20); rt=_first_crossing(rth,apex,end+220,0.20)
        df=_first_crossing(dth,apex,end+220,0.98); rf=_first_crossing(rth,apex,end+220,0.98)
        dmin_vals=[v for d in sample_d if _num(v:=_interp_series(ds,d))]
        rmin_vals=[v for d in sample_d if _num(v:=_interp_series(rs,d))]
        dmin=min(dmin_vals) if dmin_vals else None
        rmin=min(rmin_vals) if rmin_vals else None
        dap=_interp_series(ds,apex); rap=_interp_series(rs,apex)
        dex=_interp_series(ds,exit_d); rex=_interp_series(rs,exit_d)
        entry_cost=_phase_cost(selected_delta,start,apex)
        exit_cost=_phase_cost(selected_delta,apex,end)
        total_cost=_phase_cost(selected_delta,start,end)
        # With persisted speed/brake/throttle only, a trustworthy turn-in boundary
        # is unavailable. Keep mid-corner path/steering fields N/A rather than infer.
        row={'corner_id':c['corner_id'],'mean_speed_delta_kph':round(_robust(diffs),2) if diffs else None,
             'min_speed_delta_kph':round(float(dmin)-float(rmin),2) if _num(dmin) and _num(rmin) else None,
             'apex_speed_delta_kph':round(float(dap)-float(rap),2) if _num(dap) and _num(rap) else None,
             'exit_speed_delta_kph':round(float(dex)-float(rex),2) if _num(dex) and _num(rex) else None,
             'brake_onset_delta_m':round(float(db)-float(rb),1) if _num(db) and _num(rb) else None,
             'peak_brake_delta':round(float(dp)-float(rp),3) if _num(dp) and _num(rp) else None,
             'brake_release_delta_m':round(float(dr)-float(rr),1) if _num(dr) and _num(rr) else None,
             'throttle_pickup_delta_m':round(float(dt)-float(rt),1) if _num(dt) and _num(rt) else None,
             'full_throttle_delta_m':round(float(df)-float(rf),1) if _num(df) and _num(rf) else None,
             'pickup_to_full_throttle_delta_m':round((float(df)-float(dt))-(float(rf)-float(rt)),1) if all(_num(x) for x in (df,dt,rf,rt)) else None,
             'entry_time_loss_s':round(entry_cost,4) if _num(entry_cost) else None,
             'mid_time_loss_s':None,
             'exit_time_loss_s':round(exit_cost,4) if _num(exit_cost) else None,
             'time_loss_s':round(total_cost,4) if _num(total_cost) else None,
             'confidence':0.72 if len(sample_d)>=8 else 0.58,
             'evidence_note':'distance-aligned persisted speed/brake/throttle; steering/path/slip remain N/A when not persisted'}
        corners.append(row)
    session=payload.get('session') if isinstance(payload.get('session'),dict) else {}
    gap=vr.get('best_lap_gap_s')
    return {'available':True,'kind':vr.get('kind'),'label':vr.get('label') or vr.get('session_type') or 'Selected reference',
            'lap_time_s':vr.get('lap_time_s') or vr.get('best_lap_s'),'best_lap_gap_s':gap,
            'driver_best_lap_s':session.get('best_lap_s'),'corners':corners,'delta_trace_points':len(selected_delta),
            'method':'selected-reference comparison from persisted distance-aligned telemetry; does not rewrite recorded authoritative scores'}

def deterministic_review_summary(payload: dict[str, Any], corner_id: int | None=None) -> dict[str, Any]:
    r=payload.get('review') if isinstance(payload.get('review'),dict) else {}
    comp=payload.get('selected_reference_comparison') if isinstance(payload.get('selected_reference_comparison'),dict) else {}
    if corner_id is not None:
        c=next((x for x in r.get('corners') or [] if int(x.get('corner_id') or -1)==int(corner_id)),None)
        if not c: return {'available':False,'text':'No deterministic corner evidence is available.'}
        lines=[]
        if _num(c.get('mean_loss_s')):
            loss=float(c['mean_loss_s']); lines.append(f"Measured {'loss' if loss>0 else 'gain'} {abs(loss):.3f} s versus the recorded authoritative reference.")
        if c.get('dominant_issue_label'): lines.append(str(c['dominant_issue_label'])+'.')
        detail=c.get('detail') if isinstance(c.get('detail'),dict) else {}
        for key,label,unit in [('brake_onset_delta_m','Brake point',' m'),('trail_brake_delta_m','Trail braking',' m'),('min_speed_delta_kph','Minimum speed',' km/h'),('throttle_pickup_delta_m','Throttle pickup',' m'),('exit_speed_delta_kph','Exit speed',' km/h')]:
            if _num(detail.get(key)): lines.append(f"{label}: {float(detail[key]):+.1f}{unit}.")
        sc=next((x for x in comp.get('corners') or [] if int(x.get('corner_id') or -1)==int(corner_id)),None)
        if sc:
            vals=[]
            for key,label,unit in [('brake_onset_delta_m','brake point',' m'),('min_speed_delta_kph','minimum speed',' km/h'),('throttle_pickup_delta_m','throttle pickup',' m'),('exit_speed_delta_kph','exit speed',' km/h')]:
                if _num(sc.get(key)): vals.append(f"{label} {float(sc[key]):+.1f}{unit}")
            if vals: lines.append('Selected-reference comparison: '+', '.join(vals)+'.')
        return {'available':bool(lines),'text':' '.join(lines) if lines else 'No deterministic corner differences are available.'}
    lines=[]
    if _num(r.get('session_technique_score')): lines.append(f"Session technique score {float(r['session_technique_score']):.0f}.")
    opp=[x for x in r.get('opportunities') or [] if isinstance(x,dict)]
    if opp:
        x=opp[0]; lines.append(f"Largest recorded-reference opportunity is T{x.get('corner_id')} at {float(x.get('mean_net_loss_s')):.3f} s"+(f" ({x.get('dominant_issue_label')})" if x.get('dominant_issue_label') else '')+'.')
    if comp.get('available') and _num(comp.get('best_lap_gap_s')):
        g=float(comp['best_lap_gap_s']); lines.append(f"Against the selected reference, the session best is {abs(g):.3f} s {'slower' if g>0 else 'faster'}.")
    dq=r.get('data_quality') if isinstance(r.get('data_quality'),dict) else {}; lines.append(f"Eligible laps: {len(dq.get('eligible_laps') or [])}.")
    return {'available':bool(lines),'text':' '.join(lines)}

def build_performance_review(report: dict[str, Any] | None) -> dict[str, Any]:
    report = report if isinstance(report, dict) else {}
    comparisons = [x for x in report.get("lap_comparisons") or [] if isinstance(x, dict)]
    ref = report.get("reference_lap") if isinstance(report.get("reference_lap"), dict) else {}
    ref_time = ref.get("lap_time_s")
    reference_identity = str(ref.get("lap") or ref.get("name") or "recorded-reference")

    lap_rows: list[dict[str, Any]] = []
    all_corner_scores = []
    by_corner: dict[int, list[dict[str, Any]]] = {}
    dimension_values: dict[str, list[float]] = {}

    for comp in comparisons:
        scored = []
        analyses = []
        for i, raw in enumerate(comp.get("corner_analyses") or []):
            if not isinstance(raw, dict):
                continue
            analysis = _corner_analysis(raw)
            if analysis is None:
                continue
            score = build_corner_technique_score(
                analysis,
                compatibility=CompatibilityState.COMPATIBLE,
                reference_identity=reference_identity,
                reference_version=REVIEW_MODEL_VERSION,
                evidence_prefix=f"review:l{comp.get('lap')}:c{i}",
            )
            scored.append(score)
            all_corner_scores.append(score)
            cid = score.corner_id
            if isinstance(cid, int):
                by_corner.setdefault(cid, []).append({"score": score, "analysis": raw})
            for metric, dim in score.dimensions.items():
                if dim.status is ScoreStatus.AVAILABLE and _num(dim.value):
                    dimension_values.setdefault(metric, []).append(float(dim.value))
            analyses.append(raw)
        eligible_count = max(len(analyses), len(scored))
        lap_score = build_lap_technique_score(
            scored,
            lap_number=comp.get("lap"),
            eligible_corner_count=eligible_count,
            compatibility=CompatibilityState.COMPATIBLE,
        )
        losses = [r for r in analyses if _num(r.get("time_loss_s"))]
        biggest = max(losses, key=lambda r: float(r.get("time_loss_s")), default=None)
        lap_time = comp.get("lap_time_s")
        lap_rows.append({
            "lap": comp.get("lap"),
            "lap_time_s": float(lap_time) if _num(lap_time) else None,
            "delta_to_reference_s": (float(lap_time) - float(ref_time)) if _num(lap_time) and _num(ref_time) else None,
            "score": lap_score.score,
            "grade": score_grade(lap_score.score),
            "confidence": lap_score.confidence,
            "coverage": lap_score.coverage,
            "scored_corners": lap_score.scored_corner_count,
            "eligible_corners": lap_score.eligible_corner_count,
            "biggest_loss_corner": (biggest.get("reference_corner_id") or biggest.get("corner_id")) if biggest else None,
            "biggest_loss_s": float(biggest.get("time_loss_s")) if biggest and _num(biggest.get("time_loss_s")) else None,
        })

    # V2.0.3.7: Performance Hub must consume the same authoritative live
    # lap/corner results that the Performance Coach showed on track.  The old
    # post-session path only understood legacy full-lap recorder comparisons,
    # so REC-OFF sessions could retain the lap count/trace but lose all corner
    # intelligence.  Use live_lap_intelligence as a measured fallback while
    # preserving quality gates for session scoring.
    live_laps=[x for x in report.get("live_lap_intelligence") or [] if isinstance(x,dict)]
    if live_laps:
        existing_laps={x.get("lap") for x in lap_rows}
        for lr in live_laps:
            lap_no=lr.get("lap_number")
            if lap_no in existing_laps:
                continue
            quality=lr.get("quality") if isinstance(lr.get("quality"),dict) else {}
            trusted=bool(quality.get("eligible", lr.get("lap_valid") is True))
            raw_score=lr.get("lap_score") if trusted else None
            lap_rows.append({
                "lap":lap_no,
                "lap_time_s":float(lr["lap_time_s"]) if _num(lr.get("lap_time_s")) else None,
                "delta_to_reference_s":(float(lr["lap_time_s"])-float(ref_time)) if _num(lr.get("lap_time_s")) and _num(ref_time) else None,
                "score":float(raw_score) if _num(raw_score) else None,
                "grade":score_grade(raw_score),
                "confidence":float(lr.get("confidence")) if _num(lr.get("confidence")) else 0.0,
                "coverage":float(lr.get("coverage")) if _num(lr.get("coverage")) else 0.0,
                "scored_corners":int(lr.get("scored_corner_count") or 0),
                "eligible_corners":int(lr.get("eligible_corner_count") or 0),
                "biggest_loss_corner":((lr.get("biggest_loss") or {}).get("corner_id") if isinstance(lr.get("biggest_loss"),dict) else None),
                "biggest_loss_s":((lr.get("biggest_loss") or {}).get("loss_s") if isinstance(lr.get("biggest_loss"),dict) else None),
                "evidence_status":"trusted" if trusted else "observed_compromised",
                "quality_reasons":list(quality.get("reasons") or []),
            })
            existing_laps.add(lap_no)
            for raw in (lr.get("corners") or {}).values():
                if not isinstance(raw,dict) or not isinstance(raw.get("corner_id"),int):
                    continue
                cid=int(raw["corner_id"])
                by_corner.setdefault(cid,[]).append({"live":raw,"trusted":trusted})
                for metric,val in (raw.get("dimension_scores") or {}).items():
                    if trusted and _num(val):
                        dimension_values.setdefault(metric,[]).append(float(val))
        lap_rows.sort(key=lambda x:(x.get("lap") is None, x.get("lap") or 0))

    # Every authoritative completed timed lap must remain selectable in the Hub,
    # even when it had insufficient trusted corner evidence for a technique score.
    # This prevents Lap 1 / the session-best reference lap disappearing merely
    # because no post-session comparison row was generated for it.
    existing_laps={x.get("lap") for x in lap_rows}
    for fact in (report.get("lap_facts") or []):
        if not isinstance(fact,dict) or not isinstance(fact.get("lap"),int) or fact.get("lap") in existing_laps:
            continue
        q=fact.get("quality") if isinstance(fact.get("quality"),dict) else {}
        lap_rows.append({
            "lap":fact.get("lap"),
            "lap_time_s":float(fact["lap_time_s"]) if _num(fact.get("lap_time_s")) else None,
            "delta_to_reference_s":(float(fact["lap_time_s"])-float(ref_time)) if _num(fact.get("lap_time_s")) and _num(ref_time) else None,
            "score":None,"grade":score_grade(None),"confidence":0.0,"coverage":0.0,
            "scored_corners":0,"eligible_corners":0,"biggest_loss_corner":None,"biggest_loss_s":None,
            "evidence_status":"trusted" if bool(q.get("eligible")) else "observed_compromised",
            "quality_reasons":list(q.get("reasons") or []),
        })
        existing_laps.add(fact.get("lap"))
    lap_rows.sort(key=lambda x:(x.get("lap") is None, x.get("lap") or 0))

    session_scores = [float(x["score"]) for x in lap_rows if _num(x.get("score"))]
    session_score = _robust(session_scores) if len(session_scores) >= 2 else None
    session_conf = _robust([float(x["confidence"]) for x in lap_rows if _num(x.get("confidence")) and _num(x.get("score"))])

    group_defs = {
        "Braking": ("braking_point", "brake_release", "trail_braking"),
        "Trail braking": ("trail_braking",),
        "Turn-in": ("turn_in",),
        "Corner speed": ("min_apex_speed",),
        "Throttle": ("throttle_pickup", "time_to_full_throttle"),
        "Exit": ("exit_speed",),
        "Steering": ("steering_control",),
    }
    groups = []
    for label, metrics in group_defs.items():
        vals = [v for m in metrics for v in dimension_values.get(m, [])]
        value = _robust(vals) if len(vals) >= 3 else None
        groups.append({"name": label, "score": round(value, 1) if _num(value) else None, "sample_count": len(vals), "status": "available" if _num(value) else "n/a"})

    corners = []
    drilldown = {int(x.get("corner_id")): x for x in report.get("corner_drilldown") or [] if isinstance(x, dict) and isinstance(x.get("corner_id"), int)}
    for cid in sorted(by_corner):
        rows = by_corner[cid]
        legacy=[x for x in rows if isinstance(x,dict) and "score" in x and "analysis" in x]
        live=[x for x in rows if isinstance(x,dict) and isinstance(x.get("live"),dict)]
        scores=[float(x["score"].score) for x in legacy if _num(x["score"].score)]
        scores += [float(x["live"].get("score")) for x in live if x.get("trusted") and _num(x["live"].get("score"))]
        score = _robust(scores)
        confs=[float(x["score"].confidence) for x in legacy if _num(x["score"].confidence)]
        confs += [float(x["live"].get("confidence")) for x in live if _num(x["live"].get("confidence"))]
        conf = _robust(confs)
        dd = drilldown.get(cid, {})
        live_raw=[x["live"] for x in live]
        losses=[float(x.get("estimated_loss_s")) for x in live_raw if _num(x.get("estimated_loss_s"))]
        dominant=max((x for x in live_raw if x.get("dominant_issue")),key=lambda x:float(x.get("estimated_loss_s") or 0.0),default=None)
        details=[]
        for x in live_raw:
            details.append({
                "brake_onset_delta_m":x.get("brake_point_delta_m"),
                "brake_release_delta_m":x.get("brake_release_delta_m"),
                "peak_brake_delta":x.get("peak_brake_delta"),
                "trail_brake_delta_m":x.get("trail_brake_delta_m"),
                "apex_delta_m":x.get("apex_position_delta_m") if _num(x.get("apex_position_delta_m")) else x.get("apex_estimate_delta_m"),
                "apex_speed_delta_kph":x.get("apex_speed_delta_kph"),
                "min_speed_delta_kph":x.get("min_speed_delta_kph"),
                "turn_in_delta_m":x.get("turn_in_delta_m"),
                "steering_corrections_delta":x.get("steering_corrections_delta"),
                "steering_smoothness_delta":x.get("steering_smoothness_delta"),
                "throttle_pickup_delta_m":x.get("throttle_pickup_delta_m"),
                "throttle_pickup_after_apex_delta_s":x.get("throttle_pickup_delta_s"),
                "pickup_to_full_throttle_delta_s":x.get("pickup_to_full_throttle_delta_s"),
                "full_throttle_delta_m":x.get("full_throttle_delta_m"),
                "exit_speed_delta_kph":x.get("exit_speed_delta_kph"),
                "max_slip_delta":x.get("max_slip_delta"),
                "steering_unwind_delta_s":x.get("steering_unwind_delta_s"),
                "entry_time_loss_s":(x.get("phase_losses") or {}).get("entry"),
                "mid_time_loss_s":(x.get("phase_losses") or {}).get("mid"),
                "exit_time_loss_s":(x.get("phase_losses") or {}).get("exit"),
                "time_loss_s":x.get("estimated_loss_s"),
            })
        details += [x["analysis"] for x in legacy]
        corners.append({
            "corner_id": cid,
            "score": round(score, 1) if _num(score) else None,
            "grade": score_grade(score),
            "confidence": round(conf, 3) if _num(conf) else 0.0,
            "observations": len(rows),
            "trusted_observations":sum(1 for x in live if x.get("trusted"))+len(legacy),
            "evidence_status":"trusted" if (scores or legacy) else "observed_compromised",
            "mean_loss_s": dd.get("mean_net_loss_s") if _num(dd.get("mean_net_loss_s")) else (_robust(losses) if losses else None),
            "dominant_issue": dd.get("dominant_issue") or (dominant.get("dominant_issue") if dominant else None),
            "dominant_issue_label": dd.get("dominant_issue_label") or (dominant.get("primary_text") if dominant else None),
            "dominant_phase": dd.get("dominant_phase") or (dominant.get("dominant_phase") if dominant else None),
            "detail": _corner_detail(details),
            "secondary_evidence":_secondary_evidence([x["analysis"] for x in legacy], dd.get("dominant_issue") or (dominant.get("dominant_issue") if dominant else None)),
            "total_measured_time_loss_s":dd.get("mean_net_loss_s") if _num(dd.get("mean_net_loss_s")) else (_robust(losses) if losses else _agg(details,"time_loss_s")),
        })

    opportunities = [dict(x) for x in report.get("ranked_biggest_opportunities") or [] if isinstance(x, dict)]
    strengths = [dict(x) for x in report.get("best_strengths") or [] if isinstance(x, dict)]
    quality = report.get("coaching_data_quality") if isinstance(report.get("coaching_data_quality"), dict) else {}
    trend = report.get("improvement_trend") if isinstance(report.get("improvement_trend"), dict) else {}
    potential = report.get("potential") if isinstance(report.get("potential"), dict) else {}

    # Per-lap review objects preserve the exact live corner evidence so the Hub
    # can switch between SESSION OVERALL and an individual lap without
    # re-running detectors or inventing data after the fact.
    live_by_lap={int(x.get("lap_number")):x for x in live_laps if isinstance(x.get("lap_number"),int)}
    comparison_by_lap={int(x.get("lap")):x for x in comparisons if isinstance(x.get("lap"),int)}
    lap_reviews=[]
    for lr in lap_rows:
        lap_no=lr.get("lap")
        src=live_by_lap.get(int(lap_no)) if isinstance(lap_no,int) else None
        lap_corners=[]
        if isinstance(src,dict):
            trusted=bool((src.get("quality") or {}).get("eligible",src.get("lap_valid") is True))
            for raw in (src.get("corners") or {}).values():
                if not isinstance(raw,dict) or not isinstance(raw.get("corner_id"),int):
                    continue
                lap_corners.append({
                    "corner_id":int(raw["corner_id"]),
                    "score":float(raw["score"]) if trusted and _num(raw.get("score")) else None,
                    "grade":score_grade(raw.get("score") if trusted else None),
                    "confidence":float(raw.get("confidence") or 0.0),
                    "observations":1,
                    "trusted_observations":1 if trusted else 0,
                    "evidence_status":"trusted" if trusted else "observed_compromised",
                    "mean_loss_s":float(raw["estimated_loss_s"]) if _num(raw.get("estimated_loss_s")) else None,
                    "dominant_issue":raw.get("dominant_issue"),
                    "dominant_issue_label":raw.get("primary_text"),
                    "dominant_phase":raw.get("dominant_phase"),
                    "detail":_corner_detail([{
                        "brake_onset_delta_m":raw.get("brake_point_delta_m"),
                        "brake_release_delta_m":raw.get("brake_release_delta_m"),
                        "peak_brake_delta":raw.get("peak_brake_delta"),
                        "trail_brake_delta_m":raw.get("trail_brake_delta_m"),
                        "apex_delta_m":raw.get("apex_position_delta_m") if _num(raw.get("apex_position_delta_m")) else raw.get("apex_estimate_delta_m"),
                        "apex_speed_delta_kph":raw.get("apex_speed_delta_kph"),
                        "min_speed_delta_kph":raw.get("min_speed_delta_kph"),
                        "turn_in_delta_m":raw.get("turn_in_delta_m"),
                        "steering_corrections_delta":raw.get("steering_corrections_delta"),
                        "steering_smoothness_delta":raw.get("steering_smoothness_delta"),
                        "throttle_pickup_delta_m":raw.get("throttle_pickup_delta_m"),
                        "throttle_pickup_after_apex_delta_s":raw.get("throttle_pickup_delta_s"),
                        "pickup_to_full_throttle_delta_s":raw.get("pickup_to_full_throttle_delta_s"),
                        "full_throttle_delta_m":raw.get("full_throttle_delta_m"),
                        "exit_speed_delta_kph":raw.get("exit_speed_delta_kph"),
                        "max_slip_delta":raw.get("max_slip_delta"),
                        "steering_unwind_delta_s":raw.get("steering_unwind_delta_s"),
                        "entry_time_loss_s":(raw.get("phase_losses") or {}).get("entry"),
                        "mid_time_loss_s":(raw.get("phase_losses") or {}).get("mid"),
                        "exit_time_loss_s":(raw.get("phase_losses") or {}).get("exit"),
                        "time_loss_s":raw.get("estimated_loss_s"),
                    }]),
                })
        # REC-ON/legacy reports may carry exact per-lap CornerAnalysis rows even
        # when the live accumulator snapshot is unavailable. Use those measured
        # rows as a fallback; never substitute session aggregates for a lap.
        if not lap_corners and isinstance(lap_no,int):
            comp=comparison_by_lap.get(lap_no)
            if isinstance(comp,dict):
                for i,raw in enumerate(comp.get("corner_analyses") or []):
                    if not isinstance(raw,dict):
                        continue
                    analysis=_corner_analysis(raw)
                    if analysis is None:
                        continue
                    score=build_corner_technique_score(
                        analysis, compatibility=CompatibilityState.COMPATIBLE,
                        reference_identity=reference_identity, reference_version=REVIEW_MODEL_VERSION,
                        evidence_prefix=f"review:l{lap_no}:c{i}",
                    )
                    cid=score.corner_id
                    if not isinstance(cid,int):
                        continue
                    lap_corners.append({
                        "corner_id":cid,
                        "score":float(score.score) if _num(score.score) else None,
                        "grade":score_grade(score.score),
                        "confidence":float(score.confidence or 0.0),
                        "observations":1,"trusted_observations":1,
                        "evidence_status":"trusted",
                        "mean_loss_s":float(raw["time_loss_s"]) if _num(raw.get("time_loss_s")) else None,
                        "dominant_issue":raw.get("diagnosis"),
                        "dominant_issue_label":raw.get("diagnosis_label"),
                        "dominant_phase":raw.get("dominant_phase"),
                        "detail":_corner_detail([raw]),
                        "secondary_evidence":_secondary_evidence([raw], raw.get("diagnosis")),
                        "total_measured_time_loss_s":float(raw["time_loss_s"]) if _num(raw.get("time_loss_s")) else None,
                    })
        lap_corners.sort(key=lambda x:x.get("corner_id") if isinstance(x.get("corner_id"),int) else 9999)
        lap_reviews.append({"lap":lap_no,"summary":dict(lr),"corners":lap_corners})

    return {
        "format": "RACE_ENGINEER_PERFORMANCE_REVIEW",
        "version": REVIEW_MODEL_VERSION,
        "score_model_version": "2.0.0",
        "corner_breakdown_version": "2.0.4",
        "status": "available" if lap_rows else "n/a",
        "session_technique_score": round(session_score, 1) if _num(session_score) else None,
        "session_grade": score_grade(session_score),
        "confidence": round(session_conf, 3) if _num(session_conf) else 0.0,
        "reference": {"lap": ref.get("lap"), "lap_time_s": ref_time, "identity": reference_identity},
        "average_measured_available_gain_s": potential.get("average_available_gain_s") or potential.get("available_gain_s"),
        "best_lap": report.get("best_lap"),
        "potential": potential,
        "laps": lap_rows,
        "lap_reviews": lap_reviews,
        "corners": corners,
        "technique_groups": groups,
        "phase_loss_breakdown_s": report.get("phase_loss_breakdown_s") or {},
        "strengths": strengths,
        "opportunities": opportunities,
        "improvement_trend": trend,
        "recurring_patterns": report.get("recurring_patterns") or [],
        "data_quality": {
            "eligible_laps": quality.get("eligible_laps") or [],
            "excluded_laps": quality.get("excluded_laps") or [],
            "eligible_lap_count": report.get("eligible_lap_count"),
            "timed_valid_lap_count": report.get("timed_valid_lap_count"),
            "policy": quality.get("policy"),
        },
        "telemetry": report.get("telemetry_overlay") or {},
        "method": "deterministic measured evidence; scoring is downstream of diagnosis and never changes authoritative coaching",
    }
