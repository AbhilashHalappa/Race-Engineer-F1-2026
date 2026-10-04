"""Automatic deterministic post-session coaching report (JSON + HTML).

V1.3.0.0 promotes the report from a raw analysis dump into a structured coaching
artifact.  Every ranking and summary is derived from measured eligible laps only.
No predicted cause, synthetic lap, or opaque score is introduced here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from .coaching_analysis import build_corner_analyses
from .coaching_priority import CoachingMemory
from .session_advice_memory import AdviceOutcomeMemory
from .potential_lap import potential_summary
from .technique_metrics import session_technique_metrics
from .performance_review import build_performance_review
from .racing_line import compare_racing_line
from .data_quality import lap_quality
from .straight_analysis import straight_line_analysis
from .analysis_validation import build_analysis_validation
from .coaching_analysis import build_performance_pipeline
from .driver_history import DriverHistory


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _public_lap(lap: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(lap, dict):
        return None
    return {k: v for k, v in lap.items() if not str(k).startswith("_")}


def _corner_id(row: dict[str, Any]) -> int | None:
    cid = row.get("reference_corner_id") if isinstance(row.get("reference_corner_id"), int) else row.get("corner_id")
    return int(cid) if isinstance(cid, int) else None


def _ranked_corner_summary(comparisons: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float], list[dict[str, Any]]]:
    """Aggregate measured corner loss/gain and phase ownership over the session."""
    by_corner: dict[int, list[dict[str, Any]]] = {}
    phase_totals = {"ENTRY": 0.0, "MID": 0.0, "EXIT": 0.0}
    phase_seen = {k: 0 for k in phase_totals}
    for comp in comparisons:
        for row in comp.get("corner_analyses") or ():
            if not isinstance(row, dict):
                continue
            cid = _corner_id(row)
            if cid is None:
                continue
            by_corner.setdefault(cid, []).append(row)
            for key, src in (("ENTRY", "entry_time_loss_s"), ("MID", "mid_time_loss_s"), ("EXIT", "exit_time_loss_s")):
                if _num(row.get(src)):
                    phase_totals[key] += float(row[src]); phase_seen[key] += 1

    drilldown: list[dict[str, Any]] = []
    for cid, rows in sorted(by_corner.items()):
        losses = [float(r["time_loss_s"]) for r in rows if _num(r.get("time_loss_s"))]
        costs = [float(r["estimated_time_cost_s"]) for r in rows if _num(r.get("estimated_time_cost_s"))]
        diagnoses = [r for r in rows if r.get("diagnosis")]
        dominant = max(diagnoses, key=lambda r: float(r.get("estimated_time_cost_s") or 0.0), default=None)
        def _avg_metric(key: str):
            vals=[float(r[key]) for r in rows if _num(r.get(key))]
            return mean(vals) if vals else None
        drilldown.append({
            "corner_id": cid,
            "observations": len(rows),
            "mean_net_loss_s": mean(losses) if losses else None,
            "best_net_gain_s": min(losses) if losses else None,
            "worst_net_loss_s": max(losses) if losses else None,
            "mean_diagnosed_cost_s": mean(costs) if costs else None,
            "dominant_issue": dominant.get("diagnosis") if dominant else None,
            "dominant_issue_label": dominant.get("diagnosis_label") if dominant else None,
            "dominant_phase": dominant.get("dominant_phase") if dominant else None,
            "confidence": dominant.get("diagnosis_confidence") if dominant else None,
            # V1.8 measured performance-quality/efficiency summary.  These are
            # averages of available physical-corner observations only; missing
            # telemetry remains None rather than being inferred.
            "mean_corner_confidence": _avg_metric("confidence"),
            "mean_minimum_speed_efficiency_pct": _avg_metric("minimum_speed_efficiency_pct"),
            "mean_throttle_pickup_efficiency_pct": _avg_metric("throttle_pickup_efficiency_pct"),
            "mean_exit_speed_efficiency_pct": _avg_metric("exit_speed_efficiency_pct"),
            "mean_apex_speed_delta_kph": _avg_metric("apex_speed_delta_kph"),
            "mean_coasting_delta_s": _avg_metric("coasting_delta_s"),
            "mean_throttle_pickup_delta_s": _avg_metric("throttle_pickup_after_apex_delta_s"),
            "mean_steering_smoothness_delta": _avg_metric("steering_smoothness_delta"),
        })

    opportunities = sorted(
        (x for x in drilldown if _num(x.get("mean_net_loss_s")) and float(x["mean_net_loss_s"]) > 0.015),
        key=lambda x: float(x["mean_net_loss_s"]), reverse=True,
    )
    strengths = sorted(
        (x for x in drilldown if _num(x.get("mean_net_loss_s")) and float(x["mean_net_loss_s"]) < -0.015),
        key=lambda x: float(x["mean_net_loss_s"]),
    )
    phase = {k: (v if phase_seen[k] else None) for k, v in phase_totals.items()}
    return opportunities, strengths, phase, drilldown


def _improvement_trend(comparisons: list[dict[str, Any]], reference: dict[str, Any] | None) -> dict[str, Any]:
    ref_time = reference.get("lap_time_s") if isinstance(reference, dict) else None
    rows = []
    if _num(ref_time):
        for c in comparisons:
            t = c.get("lap_time_s")
            if _num(t):
                rows.append({"lap": c.get("lap"), "lap_time_s": float(t), "delta_to_reference_s": float(t) - float(ref_time)})
    change = None
    if len(rows) >= 2:
        change = rows[-1]["delta_to_reference_s"] - rows[0]["delta_to_reference_s"]
    return {
        "laps": rows,
        "first_to_latest_delta_change_s": change,
        "direction": ("improving" if _num(change) and change < -0.025 else "regressing" if _num(change) and change > 0.025 else "stable") if change is not None else "insufficient_data",
    }



def _trace_series_data(lap: dict[str, Any] | None, key: str, *, max_points: int = 600) -> list[list[float]]:
    rows = (lap or {}).get("_samples") if isinstance(lap, dict) else None
    if not isinstance(rows, dict):
        return []
    aliases = {
        "speed_kph": ("speed_kph", "speed"),
        "ers": ("ers", "ers_store_percent", "ers_percent", "ers_energy_percent"),
    }
    keys = aliases.get(key, (key,))
    pts=[]
    for raw_d, r in rows.items():
        if not isinstance(r, dict): continue
        d = r.get("d", raw_d)
        v = next((r.get(k) for k in keys if _num(r.get(k))), None)
        if _num(d) and _num(v): pts.append((float(d), float(v)))
    pts.sort()
    if not pts: return []
    step=max(1, len(pts)//max_points)
    return [[round(d,3), round(v,6)] for d,v in pts[::step]]


def _delta_trace_data(current: dict[str, Any] | None, reference: dict[str, Any] | None, *, max_points: int = 600) -> list[list[float]]:
    def times(lap):
        out={}
        for raw_d,row in ((lap or {}).get("_samples") or {}).items():
            if not isinstance(row,dict) or not _num(row.get("t")): continue
            d=row.get("d",raw_d)
            if _num(d): out[round(float(d),1)]=float(row["t"])
        return out
    a,b=times(current),times(reference)
    common=sorted(set(a)&set(b))
    if len(common)<2: return []
    base=a[common[0]]-b[common[0]]
    pts=[(d,(a[d]-b[d])-base) for d in common]
    step=max(1,len(pts)//max_points)
    return [[round(d,3),round(v,6)] for d,v in pts[::step]]


def _telemetry_overlay(current: dict[str, Any] | None, reference: dict[str, Any] | None, *, max_points: int = 600) -> dict[str, Any]:
    out={}
    for key in ("speed_kph","brake","throttle","gear","ers"):
        out[key]={"driver":_trace_series_data(current,key,max_points=max_points),"reference":_trace_series_data(reference,key,max_points=max_points)}
    out["delta_s"]={"driver":_delta_trace_data(current,reference,max_points=max_points),"reference":[]}
    return out

def _lap_telemetry_store(laps: list[dict[str, Any]], reference: dict[str, Any] | None, *, max_points: int = 320) -> dict[str, Any]:
    """Compact REC-independent telemetry for lap-by-lap Performance Review.

    This intentionally stores distance-domain analysis channels, not raw UDP
    packets.  It keeps Performance Hub useful with REC OFF while bounding SQLite
    payload size for long sessions.
    """
    out={}
    for lap in laps:
        lap_no=lap.get("lap")
        if not isinstance(lap_no,int):
            continue
        out[str(lap_no)]={
            "lap":lap_no,
            "lap_time_s":lap.get("lap_time_s"),
            "sector1_time_s":lap.get("sector1_time_s"),
            "sector2_time_s":lap.get("sector2_time_s"),
            "sector3_time_s":lap.get("sector3_time_s"),
            "valid":lap.get("valid") is not False,
            "analysis_eligible":bool(lap_quality(lap).get("eligible")),
            "quality":lap_quality(lap),
            "assists":dict(lap.get("assists") or {}),
            "warnings":lap.get("warnings"),
            "penalties_s":lap.get("penalties_s"),
            "corner_cutting_warnings":lap.get("corner_cutting_warnings"),
            "telemetry":_telemetry_overlay(lap,reference,max_points=max_points),
        }
    return out

def _reconciled_live_lap_intelligence(recorder, laps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconcile CORNER COACH lap rows with authoritative completed-lap facts.

    The live accumulator owns corner evidence, while MeasuredPerformance owns the
    completed-lap timing/validity record.  Keep those responsibilities separate:
    never let a transition packet's *new-lap* validity overwrite the old lap.
    """
    raw_by_lap={x.get("lap"):x for x in laps if isinstance(x.get("lap"),int)}
    out=[]
    for src in (getattr(recorder, "live_lap_intelligence", ()) or ()):
        if not isinstance(src,dict):
            continue
        row=dict(src)
        lap_no=row.get("lap_number")
        raw=raw_by_lap.get(lap_no)
        if isinstance(raw,dict):
            if _num(raw.get("lap_time_s")):
                row["lap_time_s"]=float(raw["lap_time_s"])
            # Completed-lap validity is authoritative for the Performance Hub.
            row["lap_valid"]=bool(raw.get("valid") is not False)
            row["quality"]=dict(lap_quality(raw))
        out.append(row)
    return out


def build_coach_report(recorder) -> dict[str, Any]:
    laps = [x for x in getattr(recorder, "completed", []) if isinstance(x, dict)]
    reconciled_live_laps = _reconciled_live_lap_intelligence(recorder, laps)
    timed_valid = [x for x in laps if x.get("valid") is not False and _num(x.get("lap_time_s")) and float(x.get("lap_time_s")) > 0]
    quality_rows = [{"lap": x.get("lap"), **lap_quality(x)} for x in timed_valid]
    valid = [x for x in timed_valid if lap_quality(x)["eligible"]]
    # Session facts (best lap, trace, raw reference gap) may still be useful in a
    # race where every lap is traffic/damage compromised. Coaching diagnoses and
    # potential calculations remain restricted to quality-eligible laps.
    best = min(timed_valid, key=lambda x: x["lap_time_s"], default=None)
    reference = getattr(recorder, "external_reference", None) if getattr(recorder, "reference_mode", None) == "external" else best
    memory = CoachingMemory()
    advice_memory = AdviceOutcomeMemory()
    comparisons: list[dict[str, Any]] = []
    if reference:
        for lap in valid:
            if lap is reference or lap.get("lap") == reference.get("lap"):
                continue
            lap_pipeline = build_performance_pipeline(lap, reference)
            analyses = [dict(x) for x in (lap_pipeline.get("corner_analyses") or ()) if isinstance(x,dict)]
            # Legacy/partial reports may not have enough full-track geometry for
            # the V1.8 pipeline. Preserve the established section comparison as a
            # compatibility fallback rather than dropping the session summary.
            if not analyses:
                analyses = [x.to_dict() for x in build_corner_analyses(lap, reference)]
            priority = memory.ingest_lap(lap.get("lap"), analyses)
            advice_memory.observe_lap(lap.get("lap"), analyses, priority.get("selected_focus") if isinstance(priority, dict) else None)
            comparisons.append({
                "lap": lap.get("lap"),
                "lap_time_s": lap.get("lap_time_s"),
                "corner_analyses": analyses,
                "coaching_priority": priority,
            })

    patterns = [x.to_dict() for x in memory.patterns()]
    recurring = [x.to_dict() for x in memory.recurring_patterns()]
    latest = valid[-1] if valid else None
    potential = potential_summary(valid, reference, include_corner_segments=True)
    opportunities, strengths, phase_breakdown, corner_drilldown = _ranked_corner_summary(comparisons)
    trend = _improvement_trend(comparisons, reference)
    best_time = best.get("lap_time_s") if isinstance(best, dict) else None
    ref_time = reference.get("lap_time_s") if isinstance(reference, dict) else None
    total_reference_gap = float(best_time) - float(ref_time) if _num(best_time) and _num(ref_time) else None
    latest_pipeline = build_performance_pipeline(latest, reference) if latest and reference and latest is not reference else {}

    result = {
        "format": "RACE_ENGINEER_COACH_REPORT",
        "version": "1.3.0.1",
        "feature_schema_version": "1.8.0.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "event_context": getattr(recorder, "event_context", None),
        "lap_count": len(laps),
        "timed_valid_lap_count": len(timed_valid),
        "eligible_lap_count": len(valid),
        "coaching_data_quality": {
            "eligible_laps": [x.get("lap") for x in valid],
            "excluded_laps": [x for x in quality_rows if not x.get("eligible")],
            "damage_override_laps": [x.get("lap") for x in timed_valid if x.get("damage_compromised") is True and x.get("damage_coaching_override") is True],
            "policy": "session facts may use valid timed laps; coaching diagnosis/potential require quality-eligible laps; DMG COACH may explicitly override damage-only exclusion",
        },
        "best_lap": _public_lap(best),
        "reference_lap": _public_lap(reference),
        "reference_mode": getattr(recorder, "reference_mode", None),
        "total_reference_gap_s": total_reference_gap,
        "potential": potential,
        "ranked_biggest_opportunities": opportunities,
        "best_strengths": strengths,
        "phase_loss_breakdown_s": phase_breakdown,
        "corner_drilldown": corner_drilldown,
        "improvement_trend": trend,
        "telemetry_overlay": _telemetry_overlay(best, reference),
        "lap_telemetry": _lap_telemetry_store(timed_valid, reference),
        "lap_facts": [{
            "lap":x.get("lap"), "lap_time_s":x.get("lap_time_s"),
            "sector1_time_s":x.get("sector1_time_s"), "sector2_time_s":x.get("sector2_time_s"), "sector3_time_s":x.get("sector3_time_s"),
            "valid":x.get("valid") is not False, "analysis_eligible":bool(lap_quality(x).get("eligible")),
            "quality":lap_quality(x), "assists":dict(x.get("assists") or {}),
            "track_condition":x.get("track_condition"), "weather_name":x.get("weather_name"), "weather_code":x.get("weather_code"),
            "warnings":x.get("warnings"), "penalties_s":x.get("penalties_s"), "corner_cutting_warnings":x.get("corner_cutting_warnings"),
        } for x in laps if isinstance(x,dict) and _num(x.get("lap_time_s")) and float(x.get("lap_time_s"))>0],
        "technique_metrics": session_technique_metrics(valid),
        "driving_performance_engine": {
            "version":"1.8.0.0",
            "apex_authority":"path_curvature_with_explicit_legacy_fallback",
            "latest_corner_metrics":[dict(x) for x in (latest_pipeline.get("turns") or ()) if isinstance(x,dict)],
        },
        "recurring_patterns": recurring,
        "all_patterns": patterns,
        "session_issue_summary": memory.session_issue_summary(),
        "advice_outcomes": advice_memory.summary(),
        "lap_comparisons": comparisons,
        "live_lap_intelligence": reconciled_live_laps,
        "track_geometry_snapshot": dict(getattr(recorder, "track_geometry_snapshot", {}) or {}),
        "latest_racing_line": compare_racing_line(latest, reference) if latest and reference else {"available": False},
        "racing_line_svg": _racing_line_svg(latest, reference) if latest and reference else "",
        "latest_straight_line_analysis": straight_line_analysis(latest, reference) if latest and reference else {"available": False},
        "latest_distance_performance": (latest_pipeline.get("distance_model") or {"available": False}) if isinstance(latest_pipeline, dict) else {"available": False},
        "method": "measured deterministic telemetry only; no predicted causes",
    }
    result["performance_review"] = build_performance_review(result)
    # V2.0.7: persist the deterministic practice plan alongside the review so
    # future sessions retain the exact evidence-backed plan generated at save.
    try:
        from .practice_planner import build_practice_plan
        result["performance_review"]["practice_plan"] = build_practice_plan(result, result["performance_review"])
    except Exception:
        pass
    result["validation"] = build_analysis_validation(laps, reference, report=result)
    return result


def _fmt(v, digits=3):
    return f"{float(v):.{digits}f}" if _num(v) else "--"


def _svg_from_series(series: dict[str, Any], title: str, *, width: int = 760, height: int = 180) -> str:
    driver = series.get("driver") if isinstance(series,dict) else []
    reference = series.get("reference") if isinstance(series,dict) else []
    all_pts=[p for rows in (driver or [],reference or []) for p in rows if isinstance(p,(list,tuple)) and len(p)>=2 and _num(p[0]) and _num(p[1])]
    if not all_pts: return ""
    xmin=min(float(p[0]) for p in all_pts); xmax=max(float(p[0]) for p in all_pts)
    ymin=min(float(p[1]) for p in all_pts); ymax=max(float(p[1]) for p in all_pts)
    if xmax<=xmin: return ""
    if ymax<=ymin: ymax=ymin+1.0
    def poly(rows):
        out=[]
        for p in rows or []:
            if not isinstance(p,(list,tuple)) or len(p)<2 or not _num(p[0]) or not _num(p[1]): continue
            x=(float(p[0])-xmin)/(xmax-xmin)*width; y=height-(float(p[1])-ymin)/(ymax-ymin)*height
            out.append(f"{x:.1f},{y:.1f}")
        return " ".join(out)
    lines=[]
    if reference: lines.append(f"<polyline points='{poly(reference)}' fill='none' stroke='#7dd3fc' stroke-width='2'/>")
    if driver: lines.append(f"<polyline points='{poly(driver)}' fill='none' stroke='#facc15' stroke-width='2'/>")
    return f"<h3>{html.escape(title)}</h3><svg viewBox='0 0 {width} {height}' width='100%' height='{height}' style='background:#161616;border-radius:8px'>{''.join(lines)}</svg>"

def _racing_line_svg(current: dict[str, Any] | None, reference: dict[str, Any] | None, *, width: int = 760, height: int = 420) -> str:
    def pts(lap):
        out=[]
        for raw_d,row in ((lap or {}).get("_samples") or {}).items():
            if isinstance(row,dict) and _num(row.get("world_x")) and _num(row.get("world_z")):
                try:d=float(row.get("d",raw_d))
                except Exception:continue
                out.append((d,float(row["world_x"]),float(row["world_z"])))
        out.sort(); return out
    a,b=pts(current),pts(reference); allp=a+b
    if len(a)<10 or len(b)<10:return ""
    xs=[x[1] for x in allp]; zs=[x[2] for x in allp]; minx,maxx=min(xs),max(xs); minz,maxz=min(zs),max(zs)
    dx=max(1e-6,maxx-minx); dz=max(1e-6,maxz-minz); scale=min((width-30)/dx,(height-30)/dz)
    def poly(rows):
        step=max(1,len(rows)//800); out=[]
        for _,x,z in rows[::step]:
            sx=15+(x-minx)*scale; sy=height-15-(z-minz)*scale; out.append(f"{sx:.1f},{sy:.1f}")
        return " ".join(out)
    return f"<h3>Driver vs reference path</h3><svg viewBox='0 0 {width} {height}' width='100%' height='{height}' style='background:#161616;border-radius:8px'><polyline points='{poly(b)}' fill='none' stroke='#7dd3fc' stroke-width='3'/><polyline points='{poly(a)}' fill='none' stroke='#facc15' stroke-width='2'/></svg>"

def report_html(report: dict[str, Any]) -> str:
    p = report.get("potential") or {}
    patterns = report.get("recurring_patterns") or []
    metrics = report.get("technique_metrics") or {}
    best = report.get("best_lap") or {}
    ref = report.get("reference_lap") or {}
    overlay = report.get("telemetry_overlay") or _telemetry_overlay(best, ref)
    rows = "".join(
        f"<tr><td>{html.escape(str(x.get('corner_id')))}</td><td>{html.escape(str(x.get('issue_label')))}</td>"
        f"<td>{int(x.get('repeat_count') or 0)}</td><td>{_fmt(x.get('mean_time_cost_s'))}</td><td>{html.escape(str(x.get('trend') or '--'))}</td></tr>"
        for x in patterns[:20]
    ) or "<tr><td colspan='5'>No recurring loss-supported issue measured.</td></tr>"
    corner_rows=[]
    for c in metrics.get('corners') or []:
        def sd(name):
            v=c.get(name); return _fmt(v.get('stddev')) if isinstance(v,dict) else '--'
        corner_rows.append(f"<tr><td>{c.get('corner_id')}</td><td>{c.get('observations')}</td><td>{sd('brake_point_consistency')}</td><td>{sd('brake_release_consistency')}</td><td>{sd('minimum_speed_consistency')}</td><td>{sd('throttle_pickup_consistency')}</td><td>{sd('exit_speed_consistency')}</td></tr>")
    traces = ''.join([
        _svg_from_series(overlay.get('speed_kph') or {},'Speed — current best vs reference'),
        _svg_from_series(overlay.get('brake') or {},'Brake — current best vs reference'),
        _svg_from_series(overlay.get('throttle') or {},'Throttle — current best vs reference'),
        _svg_from_series(overlay.get('gear') or {},'Gear — current best vs reference'),
        _svg_from_series(overlay.get('ers') or {},'ERS — current best vs reference'),
        _svg_from_series(overlay.get('delta_s') or {},'Delta — current best vs reference'),
    ])
    opportunity_rows = ''.join(
        f"<tr><td>T{x.get('corner_id')}</td><td>{_fmt(x.get('mean_net_loss_s'))}</td><td>{html.escape(str(x.get('dominant_issue_label') or '--'))}</td><td>{html.escape(str(x.get('dominant_phase') or '--'))}</td></tr>"
        for x in (report.get('ranked_biggest_opportunities') or [])[:12]
    ) or '<tr><td colspan=4>No repeatable measured corner loss.</td></tr>'
    strength_rows = ''.join(
        f"<tr><td>T{x.get('corner_id')}</td><td>{_fmt(-float(x.get('mean_net_loss_s')) if _num(x.get('mean_net_loss_s')) else None)}</td><td>{html.escape(str(x.get('dominant_issue_label') or 'clean relative pace'))}</td></tr>"
        for x in (report.get('best_strengths') or [])[:8]
    ) or '<tr><td colspan=3>No repeatable measured corner gain.</td></tr>'
    phase=report.get('phase_loss_breakdown_s') or {}; trend=report.get('improvement_trend') or {}
    line=report.get('latest_racing_line') or {}; straight=report.get('latest_straight_line_analysis') or {}
    quality=report.get('coaching_data_quality') or {}; dmg_override=quality.get('damage_override_laps') or []
    advice_outcomes=report.get('advice_outcomes') or {}; validation=report.get('validation') or {}
    dmg_note=(f"<p><b>Damage coaching override:</b> enabled for lap(s) {html.escape(', '.join(str(x) for x in dmg_override))}. Damage remained recorded; technique comparisons may include car-condition effects.</p>" if dmg_override else '')
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Race Engineer Coach Report</title><link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCA2NCA2NCc+PHJlY3QgeD0nMycgeT0nMycgd2lkdGg9JzU4JyBoZWlnaHQ9JzU4JyByeD0nMTMnIGZpbGw9JyMwYjEyMTknIHN0cm9rZT0nIzI3Mzc0Nicgc3Ryb2tlLXdpZHRoPSczJy8+PHBhdGggZD0nTTE4IDE2djMyTTIwIDE3aDE1YzggMCAxMiA0IDEyIDEwcy00IDEwLTEyIDEwSDIwTTM1IDM3bDE0IDE0JyBmaWxsPSdub25lJyBzdHJva2U9JyM0ZGQ5ZmYnIHN0cm9rZS13aWR0aD0nNicgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJyBzdHJva2UtbGluZWpvaW49J3JvdW5kJy8+PHBhdGggZD0nTTM1IDM3bDE0IDE0JyBzdHJva2U9JyMyZWQ0ODYnIHN0cm9rZS13aWR0aD0nNicgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJy8+PC9zdmc+">
<style>body{{font-family:Segoe UI,Arial;background:#111;color:#eee;margin:28px;max-width:1200px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:8px;border-bottom:1px solid #333;text-align:left}}.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card{{background:#1b1b1b;padding:14px;border-radius:8px;min-width:180px}}small{{color:#aaa}}h2{{margin-top:30px}}code{{color:#93c5fd}}</style></head><body>
<h1>Race Engineer — Coach Report</h1><div class='cards'>
<div class='card'><b>Best lap</b><br>{_fmt(p.get('best_lap_s') if _num(p.get('best_lap_s')) else best.get('lap_time_s'))} s</div>
<div class='card'><b>Potential</b><br>{_fmt(p.get('potential_lap_s'))} s</div>
<div class='card'><b>Reference gap</b><br>{_fmt(report.get('total_reference_gap_s'))} s</div>
<div class='card'><b>Observed potential gain</b><br>{_fmt(p.get('potential_gain_s'))} s</div>
<div class='card'><b>Reference gap at potential</b><br>{_fmt(p.get('potential_vs_reference_s'))} s</div>
<div class='card'><b>Coaching-eligible laps</b><br>{int(report.get('eligible_lap_count') or 0)} / {int(report.get('timed_valid_lap_count') or 0)}</div>
<div class='card'><b>Active coached issues</b><br>{int(advice_outcomes.get('active_count') or 0)}</div>
<div class='card'><b>Solved coached issues</b><br>{int(advice_outcomes.get('solved_count') or 0)}</div></div>{dmg_note}
<h2>Biggest measured opportunities</h2><table><tr><th>Turn</th><th>Mean net loss (s)</th><th>Dominant issue</th><th>Phase</th></tr>{opportunity_rows}</table>
<h2>Best measured strengths</h2><table><tr><th>Turn</th><th>Mean gain (s)</th><th>Context</th></tr>{strength_rows}</table>
<h2>Entry / mid / exit ownership</h2><p>Entry {_fmt(phase.get('ENTRY'))} s · Mid {_fmt(phase.get('MID'))} s · Exit {_fmt(phase.get('EXIT'))} s</p>
<h2>Session improvement trend</h2><p>{html.escape(str(trend.get('direction') or 'insufficient_data'))}; first-to-latest reference-gap change {_fmt(trend.get('first_to_latest_delta_change_s'))} s.</p>
<h2>Recurring measured patterns</h2><table><tr><th>Turn</th><th>Issue</th><th>Repeats</th><th>Mean measured cost (s)</th><th>Trend</th></tr>{rows}</table>
<h2>Technique consistency</h2><table><tr><th>Turn</th><th>N</th><th>Brake point σ m</th><th>Release σ m</th><th>Min speed σ kph</th><th>Throttle pickup σ m</th><th>Exit speed σ kph</th></tr>{''.join(corner_rows) or '<tr><td colspan=7>Not enough valid samples.</td></tr>'}</table>
<h2>Telemetry drill-down</h2>{traces or '<p>Raw trace samples were not retained in this report.</p>'}
<h2>Racing line</h2><p>Available: {bool(line.get('available'))}; mean path deviation: {_fmt(line.get('mean_path_deviation_m'))} m; max: {_fmt(line.get('max_path_deviation_m'))} m.</p>{report.get('racing_line_svg') or ''}
<h2>Straight-line analysis</h2><pre>{html.escape(json.dumps(straight,indent=2,default=str)[:12000])}</pre>
<h2>Analysis validation</h2><pre>{html.escape(json.dumps(validation.get('checks') or {},indent=2,default=str))}</pre>
<p><small>{html.escape(str(report.get('method') or ''))}</small></p></body></html>"""


def save_coach_report(recorder, directory: str | Path | None = None, stem: str | None = None, *, record_driver_history: bool = True) -> tuple[Path, Path, dict[str, Any]]:
    report = build_coach_report(recorder)
    from .app_paths import REPORTS
    out = Path(directory) if directory is not None else REPORTS; out.mkdir(parents=True, exist_ok=True)
    stem = stem or datetime.now(timezone.utc).strftime("coach_%Y%m%dT%H%M%SZ")
    json_path = out / f"{stem}.json"; html_path = out / f"{stem}.html"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    html_path.write_text(report_html(report), encoding="utf-8")
    validation_path = out / f"{stem}_validation.json"
    validation_path.write_text(json.dumps(report.get("validation") or {}, indent=2, default=str), encoding="utf-8")
    report["validation_json"] = str(validation_path)
    # Persist a compact cross-session history row.  Raw telemetry is deliberately not duplicated.
    ctx = report.get("event_context") if isinstance(report.get("event_context"), dict) else {}
    potential = report.get("potential") if isinstance(report.get("potential"), dict) else {}
    session_uid = ctx.get("session_uid") if isinstance(ctx, dict) else None
    history_row = {
        "session_uid": session_uid if session_uid is not None else stem,
        "created_utc": report.get("created_utc"), "event_context": ctx,
        "best_lap_s": potential.get("best_lap_s"), "potential_lap_s": potential.get("potential_lap_s"),
        "potential_gain_s": potential.get("realistic_available_gain_s") if potential.get("realistic_available_gain_s") is not None else potential.get("potential_gain_s"),
        "reference_gap_s": report.get("total_reference_gap_s"), "potential_vs_reference_s": potential.get("potential_vs_reference_s"),
        "technique_metrics": report.get("technique_metrics"), "recurring_patterns": report.get("recurring_patterns") or [],
        "advice_outcomes": report.get("advice_outcomes"),
    }
    history_recorded = False
    if record_driver_history:
        try:
            DriverHistory().upsert(history_row)
            history_recorded = True
        except OSError:
            pass
    report["driver_history_recorded"] = history_recorded
    # Stable latest aliases power the read-only LAN coaching page.
    try:
        (out / "latest.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        (out / "latest.html").write_text(report_html(report), encoding="utf-8")
    except OSError:
        pass
    # Rewrite once so the report itself also points to its validation/history artifacts.
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    html_path.write_text(report_html(report), encoding="utf-8")
    return json_path, html_path, report
