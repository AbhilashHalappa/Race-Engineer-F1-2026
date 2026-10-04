"""Machine-readable deterministic validation snapshot for coaching analysis.

The snapshot is intentionally verbose enough to diagnose why a lap/segment was
accepted or rejected without screenshots.  It contains evidence and reconciliation
facts, not recommendations or predictions.
"""
from __future__ import annotations

import math
from typing import Any

from .data_quality import lap_quality, reference_compatible
from .potential_lap import potential_summary, compatible_laps


def _num(v: Any) -> bool:
    return isinstance(v, (int,float)) and math.isfinite(v)


def build_analysis_validation(laps, reference: dict[str, Any] | None = None, *, report: dict[str, Any] | None = None) -> dict[str, Any]:
    rows=[x for x in laps if isinstance(x,dict)]
    quality=[{"lap":x.get("lap"),**lap_quality(x)} for x in rows]
    eligible=[x for x in rows if lap_quality(x).get("eligible")]
    anchor=eligible[-1] if eligible else None
    compatible,compat=compatible_laps(eligible,anchor=anchor)
    potential=potential_summary(eligible,reference,anchor=anchor,include_corner_segments=True)
    source_laps=[]
    cp=potential.get("corner_segment_potential") or {}
    for region in cp.get("regions") or ():
        if isinstance(region,dict):
            source_laps.append({
                "corner_id":region.get("corner_id"),"start_m":region.get("start_m"),"end_m":region.get("end_m"),
                "best_time_s":region.get("best_time_s"),"source_lap":region.get("source_lap"),
            })
    reference_gate=reference_compatible(anchor,reference) if anchor is not None and isinstance(reference,dict) else {"eligible":False,"reasons":["missing_anchor_or_reference"],"warnings":[]}
    distance=(report or {}).get("latest_distance_performance") if isinstance(report,dict) else None
    if not isinstance(distance,dict): distance={}
    rec_err=distance.get("reconciliation_error_s")
    reason_counts: dict[str,int] = {}
    warning_counts: dict[str,int] = {}
    for row in quality:
        for reason in row.get("reasons") or ():
            reason_counts[str(reason)] = reason_counts.get(str(reason),0) + 1
        for warning in row.get("warnings") or ():
            warning_counts[str(warning)] = warning_counts.get(str(warning),0) + 1
    for row in compat.get("excluded") or ():
        for reason in row.get("reasons") or ():
            key="compatibility:"+str(reason); reason_counts[key]=reason_counts.get(key,0)+1
    return {
        "format":"RACE_ENGINEER_ANALYSIS_VALIDATION",
        "version":"1.3.2.0",
        "lap_count":len(rows),
        "eligible_lap_count":len(eligible),
        "compatible_lap_count":len(compatible),
        "lap_quality":quality,
        "compatibility":compat,
        "rejection_reason_counts":reason_counts,
        "warning_counts":warning_counts,
        "reference_compatibility":reference_gate,
        "potential_lap":{
            "best_lap_s":potential.get("best_lap_s"),
            "potential_lap_s":potential.get("potential_lap_s"),
            "reference_lap_s":potential.get("reference_lap_s"),
            "available_gain_s":potential.get("realistic_available_gain_s"),
            "potential_vs_reference_s":potential.get("potential_vs_reference_s"),
            "sector_best_times_s":potential.get("sector_best_times_s"),
            "corner_segment_theoretical_best_s":potential.get("corner_segment_theoretical_best_s"),
            "corner_region_sources":source_laps,
            "method":potential.get("method"),
        },
        "distance_reconciliation":{
            "available":bool(distance.get("available")),
            "full_track_net_delta_s":distance.get("full_track_net_delta_s"),
            "partition_net_delta_s":distance.get("partition_net_delta_s"),
            "reconciliation_error_s":rec_err,
            "passes_50ms": bool(_num(rec_err) and abs(float(rec_err)) <= 0.050) if _num(rec_err) else None,
        },
        "checks":{
            "has_eligible_lap":bool(eligible),
            "has_compatible_laps":bool(compatible),
            "reference_eligible":bool(reference_gate.get("eligible")),
            "potential_available":_num(potential.get("potential_lap_s")),
            "corner_segment_potential_available":_num(potential.get("corner_segment_theoretical_best_s")),
        },
        "rule":"all accept/reject decisions are deterministic and evidence-bearing; unknown remains unknown",
    }
