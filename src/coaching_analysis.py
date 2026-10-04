"""V0.9.20 deterministic coaching data foundation.

This module does not generate coaching language.  It consolidates already-measured
lap/section data into one authoritative per-corner comparison model that later
coaching, radio and UI layers can consume without re-deriving telemetry facts.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any

from .distance_performance import build_distance_performance_model, turn_losses_by_reference_section


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _delta(a, b):
    return (a - b) if _num(a) and _num(b) else None


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass(slots=True)
class CornerAnalysis:
    """Authoritative measured comparison for one matched physical corner.

    Positive distance deltas mean the current lap event occurred later/further
    around the lap than the reference event. Positive time_loss_s means the
    current lap lost time across this corner region relative to the reference.
    """

    corner_id: int | None
    reference_corner_id: int | None
    anchor_m: float | None
    reference_anchor_m: float | None
    anchor_delta_m: float | None

    brake_onset_m: float | None
    reference_brake_onset_m: float | None
    brake_onset_delta_m: float | None
    brake_release_m: float | None
    reference_brake_release_m: float | None
    brake_release_delta_m: float | None
    brake_release_ramp_m: float | None
    reference_brake_release_ramp_m: float | None
    brake_release_ramp_delta_m: float | None
    brake_release_ramp_s: float | None
    reference_brake_release_ramp_s: float | None
    brake_release_ramp_delta_s: float | None
    brake_duration_m: float | None
    reference_brake_duration_m: float | None
    brake_duration_delta_m: float | None
    peak_brake: float | None
    reference_peak_brake: float | None
    peak_brake_delta: float | None
    trail_brake_m: float | None
    reference_trail_brake_m: float | None
    trail_brake_delta_m: float | None

    turn_in_m: float | None
    reference_turn_in_m: float | None
    turn_in_delta_m: float | None
    apex_m: float | None
    reference_apex_m: float | None
    apex_delta_m: float | None
    apex_method: str
    min_speed_kph: float | None
    reference_min_speed_kph: float | None
    min_speed_delta_kph: float | None

    throttle_pickup_m: float | None
    reference_throttle_pickup_m: float | None
    throttle_pickup_delta_m: float | None
    full_throttle_m: float | None
    reference_full_throttle_m: float | None
    full_throttle_delta_m: float | None
    pickup_to_full_throttle_m: float | None
    reference_pickup_to_full_throttle_m: float | None
    pickup_to_full_throttle_delta_m: float | None
    pickup_to_full_throttle_s: float | None
    reference_pickup_to_full_throttle_s: float | None
    pickup_to_full_throttle_delta_s: float | None
    exit_speed_kph: float | None
    reference_exit_speed_kph: float | None
    exit_speed_delta_kph: float | None
    coasting_m: float | None
    reference_coasting_m: float | None
    coasting_delta_m: float | None
    coasting_s: float | None
    reference_coasting_s: float | None
    coasting_delta_s: float | None

    entry_gear: int | None
    reference_entry_gear: int | None
    apex_gear: int | None
    reference_apex_gear: int | None
    exit_gear: int | None
    reference_exit_gear: int | None
    gear_shift_count: int | None
    reference_gear_shift_count: int | None
    peak_abs_steering: float | None
    reference_peak_abs_steering: float | None
    steering_reversals: int | None
    reference_steering_reversals: int | None
    max_slip: float | None
    reference_max_slip: float | None
    max_slip_delta: float | None

    entry_time_loss_s: float | None
    mid_time_loss_s: float | None
    exit_time_loss_s: float | None
    time_loss_s: float | None

    current_quality: float
    reference_quality: float
    match_quality: float
    confidence: float
    confidence_reasons: tuple[str, ...]

    # V1.8 geometry/time-domain/steering metrics. These default to unavailable so
    # old serialized analyses and third-party callers remain compatible.
    apex_speed_kph: float | None = None
    reference_apex_speed_kph: float | None = None
    apex_speed_delta_kph: float | None = None
    throttle_pickup_after_apex_s: float | None = None
    reference_throttle_pickup_after_apex_s: float | None = None
    throttle_pickup_after_apex_delta_s: float | None = None
    steering_rate_mean_per_s: float | None = None
    reference_steering_rate_mean_per_s: float | None = None
    steering_rate_mean_delta_per_s: float | None = None
    steering_rate_peak_per_s: float | None = None
    reference_steering_rate_peak_per_s: float | None = None
    steering_rate_peak_delta_per_s: float | None = None
    steering_corrections: int | None = None
    reference_steering_corrections: int | None = None
    steering_corrections_delta: int | None = None
    steering_smoothness: float | None = None
    reference_steering_smoothness: float | None = None
    steering_smoothness_delta: float | None = None
    steering_unwind_s: float | None = None
    reference_steering_unwind_s: float | None = None
    steering_unwind_delta_s: float | None = None
    steering_unwind_m: float | None = None
    reference_steering_unwind_m: float | None = None
    steering_unwind_delta_m: float | None = None
    minimum_speed_efficiency_pct: float | None = None
    throttle_pickup_efficiency_pct: float | None = None
    exit_speed_efficiency_pct: float | None = None

    dominant_phase: str | None = None
    diagnosis: str | None = None
    diagnosis_label: str | None = None
    diagnosis_severity: float = 0.0
    diagnosis_confidence: float = 0.0
    actionability: float = 0.0
    estimated_time_cost_s: float | None = None
    issue_candidates: tuple[dict[str, Any], ...] = ()
    coaching_eligible: bool = False
    coaching_suppression_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_REQUIRED_METRICS = (
    "start_m",
    "brake_release_m",
    "min_speed_m",
    "min_speed_kph",
    "throttle_pickup_m",
    "exit_speed_kph",
)


def _section_quality(section: dict[str, Any]) -> tuple[float, list[str]]:
    present = sum(1 for k in _REQUIRED_METRICS if _num(section.get(k)))
    score = present / len(_REQUIRED_METRICS)
    reasons: list[str] = []
    if not _num(section.get("turn_in_m")):
        reasons.append("turn_in_unavailable")
        score -= 0.05
    if not _num(section.get("full_throttle_m")):
        reasons.append("full_throttle_unavailable")
        score -= 0.05
    apex_method=section.get("apex_method")
    if apex_method not in {"min_speed_proxy","path_curvature"}:
        reasons.append("unknown_apex_method")
        score -= 0.05
    elif apex_method=="min_speed_proxy":
        # Legacy sections remain usable, but geometric apex evidence is stronger.
        reasons.append("legacy_apex_proxy")
        score -= 0.03
    sample_count = section.get("analysis_sample_count")
    if not isinstance(sample_count, int) or sample_count < 6:
        reasons.append("low_sample_count")
        score -= 0.15
    return _clamp(score), reasons


def _nearest_delta(trace: list[tuple[float, float]], distance: float | None, tolerance_m: float = 10.0):
    if not trace or not _num(distance):
        return None
    d, value = min(trace, key=lambda x: abs(x[0] - float(distance)))
    return value if abs(d - float(distance)) <= tolerance_m else None


def _sample_map(lap: dict[str, Any]) -> dict[float, dict[str, Any]]:
    out: dict[float, dict[str, Any]] = {}
    for key, value in (lap.get("_samples") or {}).items():
        try:
            d = float(key)
        except (TypeError, ValueError):
            continue
        if _num(d) and isinstance(value, dict):
            out[d] = value
    return out


def _aligned_time_delta(current: dict[str, Any], reference: dict[str, Any]) -> list[tuple[float, float]]:
    cur = _sample_map(current)
    ref = _sample_map(reference)
    common = sorted(set(cur) & set(ref))
    if not common:
        return []
    d0 = common[0]
    ct0, rt0 = cur[d0].get("t"), ref[d0].get("t")
    if not _num(ct0) or not _num(rt0):
        return []
    out: list[tuple[float, float]] = []
    prev_ct = prev_rt = None
    for d in common:
        ct, rt = cur[d].get("t"), ref[d].get("t")
        if not _num(ct) or not _num(rt):
            continue
        ct, rt = float(ct), float(rt)
        if prev_ct is not None and ct + 0.050 < prev_ct:
            continue
        if prev_rt is not None and rt + 0.050 < prev_rt:
            continue
        prev_ct, prev_rt = ct, rt
        out.append((d, (ct - float(ct0)) - (rt - float(rt0))))
    return out


def _phase_loss(trace: list[tuple[float, float]], start_m, end_m):
    if not _num(start_m) or not _num(end_m) or float(end_m) <= float(start_m):
        return None
    a = _nearest_delta(trace, float(start_m))
    b = _nearest_delta(trace, float(end_m))
    return (b - a) if _num(a) and _num(b) else None


def _average_anchor(cur: dict[str, Any], ref: dict[str, Any]):
    values = [x for x in (cur.get("min_speed_m"), ref.get("min_speed_m")) if _num(x)]
    if values:
        return sum(float(x) for x in values) / len(values)
    values = [x for x in (cur.get("start_m"), ref.get("start_m")) if _num(x)]
    return sum(float(x) for x in values) / len(values) if values else None



_DIAG_THRESHOLDS = {
    "brake_point_m": 7.5, "peak_brake": 0.08, "trail_brake_m": 10.0,
    "coasting_m": 10.0, "min_speed_kph": 5.0, "turn_in_m": 7.5,
    "apex_m": 7.5, "throttle_pickup_m": 10.0, "throttle_ramp_m": 10.0,
    "exit_speed_kph": 5.0, "apex_speed_kph": 4.0, "slip": 0.08, "brake_release_ramp_s": 0.10,
    "coasting_s": 0.10, "throttle_pickup_s": 0.10, "steering_corrections": 2.0,
    "steering_smoothness": 0.12, "steering_unwind_s": 0.15,
}

_ACTIONABILITY = {
    "brake_early": 1.0, "brake_late": 0.95, "brake_pressure_high": 0.80,
    "brake_pressure_low": 0.85, "brake_release_abrupt": 0.90, "trail_brake_weak": 0.90, "trail_brake_excessive": 0.80,
    "coasting_excessive": 0.95, "minimum_speed_low": 0.90, "turn_in_early": 0.75,
    "turn_in_late": 0.75, "apex_early": 0.70, "apex_late": 0.70,
    "throttle_late": 1.0, "throttle_early_traction_limited": 0.70,
    "throttle_ramp_slow": 0.90, "gear_choice": 0.65, "exit_speed_low": 0.90,
    "apex_speed_low":0.92, "steering_corrections":0.75, "steering_unsmooth":0.72, "steering_unwind_slow":0.75,
}

_LABELS = {
    "brake_early":"Braking too early", "brake_late":"Braking too late",
    "brake_pressure_high":"Brake pressure too high", "brake_pressure_low":"Brake pressure too low",
    "brake_release_abrupt":"Brake release too abrupt",
    "trail_brake_weak":"Weak trail braking", "trail_brake_excessive":"Excessive trail braking",
    "coasting_excessive":"Too much coasting", "minimum_speed_low":"Minimum speed too low",
    "turn_in_early":"Turn-in too early", "turn_in_late":"Turn-in too late",
    "apex_early":"Apex too early", "apex_late":"Apex too late",
    "throttle_late":"Throttle pickup too late",
    "throttle_early_traction_limited":"Throttle too early / traction limited",
    "throttle_ramp_slow":"Too slow to full throttle", "gear_choice":"Inefficient gear choice",
    "exit_speed_low":"Exit speed too low", "apex_speed_low":"Apex speed too low",
    "steering_corrections":"Too many steering corrections", "steering_unsmooth":"Steering input less smooth",
    "steering_unwind_slow":"Steering unwind too slow",
}

def _eff_pct(current, reference, *, lower_is_better=False):
    if not (_num(current) and _num(reference)) or float(current)<0 or float(reference)<0: return None
    c=float(current); r=float(reference)
    if lower_is_better:
        if c<=1e-6: return 120.0 if r>1e-6 else 100.0
        return max(0.0,min(150.0,100.0*r/c))
    if r<=1e-6: return None
    return max(0.0,min(150.0,100.0*c/r))


def _dominant_phase(a: CornerAnalysis) -> str | None:
    vals=(("ENTRY",a.entry_time_loss_s),("MID",a.mid_time_loss_s),("EXIT",a.exit_time_loss_s))
    good=[(k,float(v)) for k,v in vals if _num(v) and float(v)>0.015]
    return max(good,key=lambda x:x[1])[0] if good else None

def _diagnose(a: CornerAnalysis) -> None:
    """Turn measured deltas into loss-supported deterministic diagnoses.

    V0.9.20.1.2 guardrails:
    - a whole corner must lose at least 20 ms before corrective coaching;
    - an issue must be supported by positive measured loss in its own phase;
    - min-speed-proxy apex timing remains informational/supporting only.
    """
    if a.confidence < 0.55:
        a.coaching_suppression_reason = "low_confidence"
        return

    # A telemetry difference is not a mistake when the current car is not slower
    # across the measured corner region. Preserve all measurements in the model,
    # but suppress corrective issue generation.
    # Ignore net corner differences smaller than 20 ms. At this scale the
    # result is not meaningful enough to justify distracting the driver, even
    # when one internal phase shows a larger local loss that was recovered in
    # another phase. Measurements stay available in JSON for analysis.
    min_corner_loss_s = 0.020
    if _num(a.time_loss_s) and float(a.time_loss_s) + 1e-9 < min_corner_loss_s:
        a.coaching_suppression_reason = (
            "corner_not_slower" if float(a.time_loss_s) <= 0.0
            else "corner_loss_below_deadband"
        )
        return


    phase=_dominant_phase(a)
    a.dominant_phase=phase
    cands=[]
    min_phase_loss_s = 0.015

    def add(code, phase_name, magnitude, threshold, *, extra=1.0, primary_eligible=True):
        if not _num(magnitude) or threshold<=0:
            return
        phase_loss={"ENTRY":a.entry_time_loss_s,"MID":a.mid_time_loss_s,"EXIT":a.exit_time_loss_s}.get(phase_name)
        # Require measured loss in the phase where the claimed issue lives.
        # This blocks advice such as "reduce brake pressure" when the entry
        # actually gained time and the lap lost time somewhere else.
        if not _num(phase_loss) or float(phase_loss) <= min_phase_loss_s:
            return
        sev=_clamp(abs(float(magnitude))/threshold/2.0)
        support=1.0 if phase is None or phase==phase_name else 0.72
        conf=_clamp(a.confidence*support*extra)
        act=_ACTIONABILITY[code]
        score=sev*conf*act
        time_cost=max(0.0,float(phase_loss))
        cands.append({"code":code,"label":_LABELS[code],"phase":phase_name,"magnitude":float(magnitude),"severity":sev,"confidence":conf,"actionability":act,"score":score,"estimated_time_cost_s":time_cost,"primary_eligible":bool(primary_eligible)})

    d=a.brake_onset_delta_m
    if _num(d) and d <= -_DIAG_THRESHOLDS["brake_point_m"]: add("brake_early","ENTRY",d,_DIAG_THRESHOLDS["brake_point_m"] )
    if _num(d) and d >= _DIAG_THRESHOLDS["brake_point_m"]: add("brake_late","ENTRY",d,_DIAG_THRESHOLDS["brake_point_m"] )
    d=a.peak_brake_delta
    if _num(d) and d >= _DIAG_THRESHOLDS["peak_brake"]: add("brake_pressure_high","ENTRY",d,_DIAG_THRESHOLDS["peak_brake"] )
    if _num(d) and d <= -_DIAG_THRESHOLDS["peak_brake"]: add("brake_pressure_low","ENTRY",d,_DIAG_THRESHOLDS["peak_brake"] )
    d=a.brake_release_ramp_delta_s
    if _num(d) and d <= -_DIAG_THRESHOLDS["brake_release_ramp_s"]:
        add("brake_release_abrupt","MID",d,_DIAG_THRESHOLDS["brake_release_ramp_s"] )
    d=a.trail_brake_delta_m
    if _num(d) and d <= -_DIAG_THRESHOLDS["trail_brake_m"]: add("trail_brake_weak","MID",d,_DIAG_THRESHOLDS["trail_brake_m"] )
    if _num(d) and d >= _DIAG_THRESHOLDS["trail_brake_m"]: add("trail_brake_excessive","MID",d,_DIAG_THRESHOLDS["trail_brake_m"] )
    # Prefer time-domain coasting because it is speed-independent; retain distance
    # as a legacy fallback for old references.
    d=a.coasting_delta_s
    if _num(d) and d >= _DIAG_THRESHOLDS["coasting_s"]: add("coasting_excessive","MID",d,_DIAG_THRESHOLDS["coasting_s"] )
    elif _num(a.coasting_delta_m) and a.coasting_delta_m >= _DIAG_THRESHOLDS["coasting_m"]: add("coasting_excessive","MID",a.coasting_delta_m,_DIAG_THRESHOLDS["coasting_m"] )
    d=a.apex_speed_delta_kph
    if _num(d) and d <= -_DIAG_THRESHOLDS["apex_speed_kph"]: add("apex_speed_low","MID",d,_DIAG_THRESHOLDS["apex_speed_kph"] )
    d=a.min_speed_delta_kph
    if _num(d) and d <= -_DIAG_THRESHOLDS["min_speed_kph"]: add("minimum_speed_low","MID",d,_DIAG_THRESHOLDS["min_speed_kph"] )
    d=a.turn_in_delta_m
    if _num(d) and d <= -_DIAG_THRESHOLDS["turn_in_m"]: add("turn_in_early","MID",d,_DIAG_THRESHOLDS["turn_in_m"] )
    if _num(d) and d >= _DIAG_THRESHOLDS["turn_in_m"]: add("turn_in_late","MID",d,_DIAG_THRESHOLDS["turn_in_m"] )
    d=a.apex_delta_m
    # Curvature apex is true geometric evidence and may coach timing; the legacy
    # minimum-speed proxy remains supporting-only.
    geometric=(a.apex_method=="path_curvature")
    if _num(d) and d <= -_DIAG_THRESHOLDS["apex_m"]: add("apex_early","MID",d,_DIAG_THRESHOLDS["apex_m"], extra=(.85 if geometric else .60), primary_eligible=geometric)
    if _num(d) and d >= _DIAG_THRESHOLDS["apex_m"]: add("apex_late","MID",d,_DIAG_THRESHOLDS["apex_m"], extra=(.85 if geometric else .60), primary_eligible=geometric)
    d=a.throttle_pickup_after_apex_delta_s
    if _num(d) and d >= _DIAG_THRESHOLDS["throttle_pickup_s"]: add("throttle_late","EXIT",d,_DIAG_THRESHOLDS["throttle_pickup_s"] )
    elif _num(a.throttle_pickup_delta_m) and a.throttle_pickup_delta_m >= _DIAG_THRESHOLDS["throttle_pickup_m"]: add("throttle_late","EXIT",a.throttle_pickup_delta_m,_DIAG_THRESHOLDS["throttle_pickup_m"] )
    d=a.throttle_pickup_delta_m
    if _num(d) and d <= -_DIAG_THRESHOLDS["throttle_pickup_m"] and _num(a.max_slip_delta) and a.max_slip_delta>=_DIAG_THRESHOLDS["slip"]:
        add("throttle_early_traction_limited","EXIT",d,_DIAG_THRESHOLDS["throttle_pickup_m"], extra=.85)
    d=a.pickup_to_full_throttle_delta_m
    if _num(d) and d >= _DIAG_THRESHOLDS["throttle_ramp_m"]: add("throttle_ramp_slow","EXIT",d,_DIAG_THRESHOLDS["throttle_ramp_m"] )
    d=a.steering_corrections_delta
    if _num(d) and d >= _DIAG_THRESHOLDS["steering_corrections"]: add("steering_corrections","MID",d,_DIAG_THRESHOLDS["steering_corrections"], extra=.85)
    d=a.steering_smoothness_delta
    if _num(d) and d <= -_DIAG_THRESHOLDS["steering_smoothness"]: add("steering_unsmooth","MID",d,_DIAG_THRESHOLDS["steering_smoothness"], extra=.82)
    d=a.steering_unwind_delta_s
    if _num(d) and d >= _DIAG_THRESHOLDS["steering_unwind_s"]: add("steering_unwind_slow","EXIT",d,_DIAG_THRESHOLDS["steering_unwind_s"], extra=.85)
    if a.apex_gear is not None and a.reference_apex_gear is not None and abs(a.apex_gear-a.reference_apex_gear)>=1:
        add("gear_choice","MID",a.apex_gear-a.reference_apex_gear,1.0, extra=.8)
    d=a.exit_speed_delta_kph
    if _num(d) and d <= -_DIAG_THRESHOLDS["exit_speed_kph"]: add("exit_speed_low","EXIT",d,_DIAG_THRESHOLDS["exit_speed_kph"], extra=.9)

    cands.sort(key=lambda x:(x["score"], x["estimated_time_cost_s"] or 0.0), reverse=True)
    a.issue_candidates=tuple(cands)
    primary=[x for x in cands if x.get("primary_eligible", True)]
    if not primary:
        a.coaching_suppression_reason = "supporting_evidence_only" if cands else "no_loss_supported_issue"
        return
    top=primary[0]
    if top["score"] < 0.16:
        a.coaching_suppression_reason = "below_diagnosis_threshold"
        return
    a.coaching_eligible=True
    a.diagnosis=top["code"]; a.diagnosis_label=top["label"]; a.diagnosis_severity=top["severity"]
    a.diagnosis_confidence=top["confidence"]; a.actionability=top["actionability"]; a.estimated_time_cost_s=top["estimated_time_cost_s"]

def build_corner_analyses(current: dict[str, Any], reference: dict[str, Any], *, distance_model: dict[str, Any] | None = None) -> list[CornerAnalysis]:
    """Build deterministic matched-corner comparisons from two measured laps.

    V1.0.3 uses the continuous distance model as the authoritative time-loss
    source. Metric/technique diagnosis still comes from the matched measured
    sections, but time is assigned by the physical reference turn boundaries.
    """
    from .lap_analysis import match_sections_by_distance

    pairs = match_sections_by_distance(current, reference)
    if not pairs:
        return []

    if distance_model is None:
        distance_model = build_distance_performance_model(current, reference)
    continuous_turns = turn_losses_by_reference_section(distance_model)

    # Legacy aligned trace remains a fallback for partial/old references that do
    # not contain enough information for the continuous model.
    trace = _aligned_time_delta(current, reference)
    anchors = [_average_anchor(cur, ref) for cur, ref in pairs]
    valid_anchors = [x for x in anchors if _num(x)]
    trace_start = trace[0][0] if trace else None
    trace_end = trace[-1][0] if trace else None

    boundaries: list[tuple[float | None, float | None]] = []
    for i, anchor in enumerate(anchors):
        if not _num(anchor):
            boundaries.append((None, None))
            continue
        prev_anchor = next((anchors[j] for j in range(i - 1, -1, -1) if _num(anchors[j])), None)
        next_anchor = next((anchors[j] for j in range(i + 1, len(anchors)) if _num(anchors[j])), None)
        lo = ((float(prev_anchor) + float(anchor)) / 2.0) if _num(prev_anchor) else trace_start
        hi = ((float(anchor) + float(next_anchor)) / 2.0) if _num(next_anchor) else trace_end
        boundaries.append((lo, hi))

    out: list[CornerAnalysis] = []
    for (cur, ref), anchor, (region_start, region_end) in zip(pairs, anchors, boundaries):
        cur_q, cur_reasons = _section_quality(cur)
        ref_q, ref_reasons = _section_quality(ref)
        anchor_delta = _delta(cur.get("min_speed_m"), ref.get("min_speed_m"))
        if anchor_delta is None:
            anchor_delta = _delta(cur.get("start_m"), ref.get("start_m"))
        if _num(anchor_delta):
            match_q = _clamp(1.0 - abs(float(anchor_delta)) / 250.0)
        else:
            match_q = 0.5

        reasons = [f"current:{x}" for x in cur_reasons] + [f"reference:{x}" for x in ref_reasons]
        if not trace:
            reasons.append("time_alignment_unavailable")
        confidence = _clamp(min(cur_q, ref_q) * (0.65 + 0.35 * match_q))

        brake_anchor = min(
            [float(x) for x in (cur.get("start_m"), ref.get("start_m")) if _num(x)] or [float(anchor)]
        ) if _num(anchor) else None
        apex_anchor = float(anchor) if _num(anchor) else None
        exit_anchor_values = [float(x) for x in (cur.get("end_m"), ref.get("end_m")) if _num(x)]
        exit_anchor = sum(exit_anchor_values) / len(exit_anchor_values) if exit_anchor_values else region_end

        continuous = continuous_turns.get(ref.get("id"))
        if isinstance(continuous, dict) and continuous.get("complete"):
            entry_loss = continuous.get("entry_loss_s")
            mid_loss = continuous.get("mid_loss_s")
            exit_loss = continuous.get("exit_loss_s")
            region_loss = continuous.get("net_loss_s")
        else:
            entry_loss = _phase_loss(trace, region_start, brake_anchor)
            mid_loss = _phase_loss(trace, brake_anchor, apex_anchor)
            exit_loss = _phase_loss(trace, apex_anchor, region_end)
            region_loss = _phase_loss(trace, region_start, region_end)

        out.append(CornerAnalysis(
            corner_id=cur.get("id"),
            reference_corner_id=ref.get("id"),
            anchor_m=cur.get("min_speed_m") if _num(cur.get("min_speed_m")) else cur.get("start_m"),
            reference_anchor_m=ref.get("min_speed_m") if _num(ref.get("min_speed_m")) else ref.get("start_m"),
            anchor_delta_m=anchor_delta,

            brake_onset_m=cur.get("start_m"), reference_brake_onset_m=ref.get("start_m"),
            brake_onset_delta_m=_delta(cur.get("start_m"), ref.get("start_m")),
            brake_release_m=cur.get("brake_release_m"), reference_brake_release_m=ref.get("brake_release_m"),
            brake_release_delta_m=_delta(cur.get("brake_release_m"), ref.get("brake_release_m")),
            brake_release_ramp_m=cur.get("brake_release_ramp_m"), reference_brake_release_ramp_m=ref.get("brake_release_ramp_m"),
            brake_release_ramp_delta_m=_delta(cur.get("brake_release_ramp_m"), ref.get("brake_release_ramp_m")),
            brake_release_ramp_s=cur.get("brake_release_ramp_s"), reference_brake_release_ramp_s=ref.get("brake_release_ramp_s"),
            brake_release_ramp_delta_s=_delta(cur.get("brake_release_ramp_s"), ref.get("brake_release_ramp_s")),
            brake_duration_m=cur.get("brake_duration_m"), reference_brake_duration_m=ref.get("brake_duration_m"),
            brake_duration_delta_m=_delta(cur.get("brake_duration_m"), ref.get("brake_duration_m")),
            peak_brake=cur.get("peak_brake"), reference_peak_brake=ref.get("peak_brake"),
            peak_brake_delta=_delta(cur.get("peak_brake"), ref.get("peak_brake")),
            trail_brake_m=cur.get("trail_brake_m"), reference_trail_brake_m=ref.get("trail_brake_m"),
            trail_brake_delta_m=_delta(cur.get("trail_brake_m"), ref.get("trail_brake_m")),

            turn_in_m=cur.get("turn_in_m"), reference_turn_in_m=ref.get("turn_in_m"),
            turn_in_delta_m=_delta(cur.get("turn_in_m"), ref.get("turn_in_m")),
            apex_m=cur.get("apex_m") if _num(cur.get("apex_m")) else cur.get("min_speed_m"),
            reference_apex_m=ref.get("apex_m") if _num(ref.get("apex_m")) else ref.get("min_speed_m"),
            apex_delta_m=_delta(cur.get("apex_m") if _num(cur.get("apex_m")) else cur.get("min_speed_m"), ref.get("apex_m") if _num(ref.get("apex_m")) else ref.get("min_speed_m")),
            apex_method=("path_curvature" if cur.get("apex_method")=="path_curvature" and ref.get("apex_method")=="path_curvature" else "min_speed_proxy"),
            min_speed_kph=cur.get("min_speed_kph"), reference_min_speed_kph=ref.get("min_speed_kph"),
            min_speed_delta_kph=_delta(cur.get("min_speed_kph"), ref.get("min_speed_kph")),

            throttle_pickup_m=cur.get("throttle_pickup_m"), reference_throttle_pickup_m=ref.get("throttle_pickup_m"),
            throttle_pickup_delta_m=_delta(cur.get("throttle_pickup_m"), ref.get("throttle_pickup_m")),
            full_throttle_m=cur.get("full_throttle_m"), reference_full_throttle_m=ref.get("full_throttle_m"),
            full_throttle_delta_m=_delta(cur.get("full_throttle_m"), ref.get("full_throttle_m")),
            pickup_to_full_throttle_m=cur.get("pickup_to_full_throttle_m"), reference_pickup_to_full_throttle_m=ref.get("pickup_to_full_throttle_m"),
            pickup_to_full_throttle_delta_m=_delta(cur.get("pickup_to_full_throttle_m"), ref.get("pickup_to_full_throttle_m")),
            pickup_to_full_throttle_s=cur.get("pickup_to_full_throttle_s"), reference_pickup_to_full_throttle_s=ref.get("pickup_to_full_throttle_s"),
            pickup_to_full_throttle_delta_s=_delta(cur.get("pickup_to_full_throttle_s"), ref.get("pickup_to_full_throttle_s")),
            exit_speed_kph=cur.get("exit_speed_kph"), reference_exit_speed_kph=ref.get("exit_speed_kph"),
            exit_speed_delta_kph=_delta(cur.get("exit_speed_kph"), ref.get("exit_speed_kph")),
            coasting_m=cur.get("coasting_m"), reference_coasting_m=ref.get("coasting_m"),
            coasting_delta_m=_delta(cur.get("coasting_m"), ref.get("coasting_m")),
            coasting_s=cur.get("coasting_s"), reference_coasting_s=ref.get("coasting_s"),
            coasting_delta_s=_delta(cur.get("coasting_s"), ref.get("coasting_s")),

            entry_gear=cur.get("entry_gear"), reference_entry_gear=ref.get("entry_gear"),
            apex_gear=cur.get("apex_gear"), reference_apex_gear=ref.get("apex_gear"),
            exit_gear=cur.get("exit_gear"), reference_exit_gear=ref.get("exit_gear"),
            gear_shift_count=cur.get("gear_shift_count"), reference_gear_shift_count=ref.get("gear_shift_count"),
            peak_abs_steering=cur.get("peak_abs_steering"), reference_peak_abs_steering=ref.get("peak_abs_steering"),
            steering_reversals=cur.get("steering_reversals"), reference_steering_reversals=ref.get("steering_reversals"),
            max_slip=cur.get("max_slip"), reference_max_slip=ref.get("max_slip"),
            max_slip_delta=_delta(cur.get("max_slip"), ref.get("max_slip")),

            entry_time_loss_s=entry_loss,
            mid_time_loss_s=mid_loss,
            exit_time_loss_s=exit_loss,
            time_loss_s=region_loss,

            current_quality=cur_q,
            reference_quality=ref_q,
            match_quality=match_q,
            confidence=confidence,
            confidence_reasons=tuple(reasons),

            apex_speed_kph=cur.get("apex_speed_kph"), reference_apex_speed_kph=ref.get("apex_speed_kph"),
            apex_speed_delta_kph=_delta(cur.get("apex_speed_kph"), ref.get("apex_speed_kph")),
            throttle_pickup_after_apex_s=cur.get("throttle_pickup_after_apex_s"),
            reference_throttle_pickup_after_apex_s=ref.get("throttle_pickup_after_apex_s"),
            throttle_pickup_after_apex_delta_s=_delta(cur.get("throttle_pickup_after_apex_s"), ref.get("throttle_pickup_after_apex_s")),
            steering_rate_mean_per_s=cur.get("steering_rate_mean_per_s"), reference_steering_rate_mean_per_s=ref.get("steering_rate_mean_per_s"),
            steering_rate_mean_delta_per_s=_delta(cur.get("steering_rate_mean_per_s"), ref.get("steering_rate_mean_per_s")),
            steering_rate_peak_per_s=cur.get("steering_rate_peak_per_s"), reference_steering_rate_peak_per_s=ref.get("steering_rate_peak_per_s"),
            steering_rate_peak_delta_per_s=_delta(cur.get("steering_rate_peak_per_s"), ref.get("steering_rate_peak_per_s")),
            steering_corrections=cur.get("steering_corrections"), reference_steering_corrections=ref.get("steering_corrections"),
            steering_corrections_delta=(int(cur.get("steering_corrections"))-int(ref.get("steering_corrections")) if cur.get("steering_corrections") is not None and ref.get("steering_corrections") is not None else None),
            steering_smoothness=cur.get("steering_smoothness"), reference_steering_smoothness=ref.get("steering_smoothness"),
            steering_smoothness_delta=_delta(cur.get("steering_smoothness"), ref.get("steering_smoothness")),
            steering_unwind_s=cur.get("steering_unwind_s"), reference_steering_unwind_s=ref.get("steering_unwind_s"),
            steering_unwind_delta_s=_delta(cur.get("steering_unwind_s"), ref.get("steering_unwind_s")),
            steering_unwind_m=cur.get("steering_unwind_m"), reference_steering_unwind_m=ref.get("steering_unwind_m"),
            steering_unwind_delta_m=_delta(cur.get("steering_unwind_m"), ref.get("steering_unwind_m")),
            minimum_speed_efficiency_pct=_eff_pct(cur.get("min_speed_kph"),ref.get("min_speed_kph")),
            throttle_pickup_efficiency_pct=_eff_pct(cur.get("throttle_pickup_after_apex_s"),ref.get("throttle_pickup_after_apex_s"),lower_is_better=True),
            exit_speed_efficiency_pct=_eff_pct(cur.get("exit_speed_kph"),ref.get("exit_speed_kph")),
        ))
        _diagnose(out[-1])
    return out


def _lap_rows_between(lap: dict[str, Any], start_m: float, end_m: float) -> list[tuple[float, dict[str, Any]]]:
    rows=[]
    for raw_d,sample in (lap.get("_samples") or {}).items():
        try: d=float(raw_d)
        except (TypeError,ValueError): continue
        if start_m-1e-6 <= d <= end_m+1e-6 and isinstance(sample,dict):
            rows.append((d,sample))
    rows.sort(key=lambda x:x[0])
    return rows


def _first_event(rows, predicate):
    for d,row in rows:
        try:
            if predicate(row): return float(d)
        except (TypeError,ValueError):
            continue
    return None


def _nearest_metric(rows, distance: float, key: str):
    valid=[(abs(d-distance),row.get(key)) for d,row in rows if _num(row.get(key))]
    if not valid: return None
    return float(min(valid,key=lambda x:x[0])[1])


def _physical_turn_fallback(turn: dict[str, Any], current: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any] | None:
    """Diagnose a physical turn directly from distance-aligned measured samples.

    This path covers physical corners that do not have their own braking-zone
    section. It never invents a cause: each corrective label requires both a
    measured local time loss and a measured input/speed difference in that phase.
    """
    if not turn.get("complete"):
        return None
    loss=turn.get("net_loss_s")
    if not _num(loss) or float(loss)<0.020:
        return None
    own_start=float(turn.get("analysis_start_m",turn.get("start_m",0.0)))
    start=float(turn.get("start_m",own_start)); apex=float(turn.get("apex_m",start)); end=float(turn.get("end_m",apex))
    if end<=own_start:
        return None
    cur=_lap_rows_between(current,own_start,end); ref=_lap_rows_between(reference,own_start,end)
    if len(cur)<5 or len(ref)<5:
        return None
    entry_loss=turn.get("entry_loss_s"); mid_loss=turn.get("mid_loss_s"); exit_loss=turn.get("exit_loss_s")
    candidates=[]
    def add(code,label,phase,magnitude,threshold,phase_loss,actionability=0.8):
        if not (_num(magnitude) and _num(phase_loss)) or float(phase_loss)<=0.015 or threshold<=0:
            return
        severity=_clamp(abs(float(magnitude))/threshold/2.0)
        confidence=_clamp(0.72 + min(0.20,(min(len(cur),len(ref))/40.0)*0.20))
        score=severity*confidence*actionability
        candidates.append({
            "code":code,"label":label,"phase":phase,"magnitude":float(magnitude),
            "severity":severity,"confidence":confidence,"actionability":actionability,
            "score":score,"estimated_time_cost_s":max(0.0,float(phase_loss)),"primary_eligible":True,
        })

    cur_entry=[x for x in cur if own_start<=x[0]<=apex]; ref_entry=[x for x in ref if own_start<=x[0]<=apex]
    cur_mid=[x for x in cur if start<=x[0]<=end]; ref_mid=[x for x in ref if start<=x[0]<=end]
    cur_exit=[x for x in cur if apex<=x[0]<=end]; ref_exit=[x for x in ref if apex<=x[0]<=end]
    cb=_first_event(cur_entry,lambda r:_num(r.get("brake")) and float(r["brake"])>=0.10)
    rb=_first_event(ref_entry,lambda r:_num(r.get("brake")) and float(r["brake"])>=0.10)
    if _num(cb) and _num(rb):
        dd=float(cb)-float(rb)
        if dd<=-7.5: add("brake_early","Braking too early","ENTRY",dd,7.5,entry_loss,1.0)
        elif dd>=7.5: add("brake_late","Braking too late","ENTRY",dd,7.5,entry_loss,0.95)
    cp=max((float(r.get("brake")) for _,r in cur_entry if _num(r.get("brake"))),default=None)
    rp=max((float(r.get("brake")) for _,r in ref_entry if _num(r.get("brake"))),default=None)
    if _num(cp) and _num(rp):
        dd=float(cp)-float(rp)
        if dd>=0.08: add("brake_pressure_high","Brake pressure too high","ENTRY",dd,0.08,entry_loss,0.8)
        elif dd<=-0.08: add("brake_pressure_low","Brake pressure too low","ENTRY",dd,0.08,entry_loss,0.85)

    ct=_first_event(cur_mid,lambda r:_num(r.get("steering")) and abs(float(r["steering"]))>=0.08)
    rt=_first_event(ref_mid,lambda r:_num(r.get("steering")) and abs(float(r["steering"]))>=0.08)
    if _num(ct) and _num(rt):
        dd=float(ct)-float(rt)
        if dd<=-7.5: add("turn_in_early","Turn-in too early","MID",dd,7.5,mid_loss,0.75)
        elif dd>=7.5: add("turn_in_late","Turn-in too late","MID",dd,7.5,mid_loss,0.75)
    cmin=min((float(r.get("speed")) for _,r in cur_mid if _num(r.get("speed"))),default=None)
    rmin=min((float(r.get("speed")) for _,r in ref_mid if _num(r.get("speed"))),default=None)
    if _num(cmin) and _num(rmin):
        dd=float(cmin)-float(rmin)
        if dd<=-5.0: add("minimum_speed_low","Minimum speed too low","MID",dd,5.0,mid_loss,0.9)

    ctp=_first_event(cur_exit,lambda r:_num(r.get("throttle")) and float(r["throttle"])>=0.20)
    rtp=_first_event(ref_exit,lambda r:_num(r.get("throttle")) and float(r["throttle"])>=0.20)
    if _num(ctp) and _num(rtp):
        dd=float(ctp)-float(rtp)
        if dd>=10.0: add("throttle_late","Throttle pickup too late","EXIT",dd,10.0,exit_loss,1.0)
    cfull=_first_event(cur_exit,lambda r:_num(r.get("throttle")) and float(r["throttle"])>=0.98)
    rfull=_first_event(ref_exit,lambda r:_num(r.get("throttle")) and float(r["throttle"])>=0.98)
    if _num(cfull) and _num(rfull):
        dd=float(cfull)-float(rfull)
        if dd>=10.0: add("throttle_ramp_slow","Too slow to full throttle","EXIT",dd,10.0,exit_loss,0.9)
    cexit=_nearest_metric(cur,end,"speed"); rexit=_nearest_metric(ref,end,"speed")
    if _num(cexit) and _num(rexit):
        dd=float(cexit)-float(rexit)
        if dd<=-5.0: add("exit_speed_low","Exit speed too low","EXIT",dd,5.0,exit_loss,0.9)

    candidates.sort(key=lambda x:(x["score"],x["estimated_time_cost_s"]),reverse=True)
    if candidates:
        top=candidates[0]
        diagnosis=top["code"]; label=top["label"]; conf=top["confidence"]; act=top["actionability"]
        eligible=top["score"]>=0.12
    else:
        # The time loss itself is deterministic even when no supported causal
        # difference clears a threshold. State that fact rather than guessing why.
        diagnosis="corner_pace_loss"; label="Measured turn pace loss"; conf=0.72; act=0.55; eligible=True
        candidates=[{"code":diagnosis,"label":label,"phase":"TURN","magnitude":float(loss),"severity":1.0,
                     "confidence":conf,"actionability":act,"score":conf*act,
                     "estimated_time_cost_s":max(0.0,float(loss)),"primary_eligible":True}]
    return {
        "corner_id":int(turn["corner_id"]),"reference_corner_id":int(turn["corner_id"]),
        "time_loss_s":float(loss),"entry_time_loss_s":entry_loss,"mid_time_loss_s":mid_loss,"exit_time_loss_s":exit_loss,
        "coaching_eligible":bool(eligible),"diagnosis":diagnosis,"diagnosis_label":label,
        "diagnosis_confidence":float(conf),"actionability":float(act),"estimated_time_cost_s":max(0.0,float(loss)),
        "issue_candidates":tuple(candidates),"analysis_source":"physical_distance_trace",
    }


def _reference_targets(turn: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    start=float(turn.get("start_m",0.0)); apex=float(turn.get("apex_m",start)); end=float(turn.get("end_m",apex))
    rows=_lap_rows_between(reference,start,end)
    speed=min((float(r.get("speed")) for _,r in rows if _num(r.get("speed"))),default=None)
    all_rows=_lap_rows_between(reference,float(turn.get("analysis_start_m",start)),end)
    brake=_first_event(all_rows,lambda r:_num(r.get("brake")) and float(r["brake"])>=0.10)
    gear=_nearest_metric(rows,apex,"gear")
    return {
        "reference_brake_m":brake if _num(brake) else turn.get("brake_m"),
        "reference_turn_in_m":turn.get("turn_in_m"),
        "reference_apex_m":apex,
        "reference_exit_m":end,
        "reference_min_speed_kph":speed,
        "reference_apex_gear":int(round(gear)) if _num(gear) else None,
    }



def _geometry_metric_candidates(metrics: dict[str, Any], diagnosis: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Convert V1.8 geometry/time-domain measurements into deterministic issues.

    A metric only becomes causal advice when the corresponding measured phase lost
    time.  This prevents better/worse input differences from being narrated when
    they did not actually cost pace.
    """
    if not isinstance(metrics,dict): return []
    diagnosis=diagnosis or {}
    confidence=float(metrics.get("corner_confidence") or 0.0)
    if confidence < 0.50: return []
    entry=diagnosis.get("entry_time_loss_s"); mid=diagnosis.get("mid_time_loss_s"); exit_loss=diagnosis.get("exit_time_loss_s")
    total=diagnosis.get("time_loss_s")
    if not _num(total) or float(total)<=0.015: return []
    out=[]
    def add(code,label,phase,magnitude,threshold,phase_loss,actionability=0.85,primary=True):
        if not (_num(magnitude) and _num(phase_loss)) or float(phase_loss)<=0.010 or threshold<=0: return
        sev=_clamp(abs(float(magnitude))/threshold/2.0)
        score=sev*confidence*actionability
        out.append({"code":code,"label":label,"phase":phase,"magnitude":float(magnitude),"severity":sev,
                    "confidence":confidence,"actionability":actionability,"score":score,
                    "estimated_time_cost_s":max(0.0,float(phase_loss)),"primary_eligible":bool(primary),
                    "evidence_source":"geometry_time_domain"})
    # True physical-apex speed, separate from the minimum-speed proxy.
    d=metrics.get("apex_speed_kph_delta")
    if _num(d) and float(d)<=-4.0: add("apex_speed_low","Apex speed too low","MID",d,4.0,mid,0.92)
    d=metrics.get("coasting_s_delta")
    if _num(d) and float(d)>=0.10: add("coasting_excessive","Too much coasting","MID",d,0.10,mid,0.95)
    d=metrics.get("throttle_pickup_after_apex_s_delta")
    if _num(d) and float(d)>=0.10: add("throttle_late","Throttle pickup too late","EXIT",d,0.10,exit_loss,1.0)
    d=metrics.get("steering_corrections_delta")
    if _num(d) and float(d)>=2.0: add("steering_corrections","Too many steering corrections","MID",d,2.0,mid,0.75)
    d=metrics.get("steering_smoothness_delta")
    if _num(d) and float(d)<=-0.12: add("steering_unsmooth","Steering input less smooth","MID",d,0.12,mid,0.72)
    d=metrics.get("steering_unwind_s_delta")
    if _num(d) and float(d)>=0.15: add("steering_unwind_slow","Steering unwind too slow","EXIT",d,0.15,exit_loss,0.75)
    return out


def _merge_geometry_metrics(turn: dict[str, Any], diagnosis: dict[str, Any] | None,
                            current: dict[str, Any], reference: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        from .corner_geometry_metrics import compare_corner
        metrics=compare_corner(current,reference,turn)
    except Exception:
        return turn,diagnosis
    turn.update(metrics)
    cur=metrics.get("current_metrics") or {}; ref=metrics.get("reference_metrics") or {}
    # Public/reference targets consumed by PRE/UI now use true physical-apex values.
    if _num(ref.get("apex_m")): turn["reference_apex_m"]=float(ref["apex_m"])
    if _num(ref.get("apex_speed_kph")): turn["reference_apex_speed_kph"]=float(ref["apex_speed_kph"])
    if _num(ref.get("min_speed_kph")): turn["reference_min_speed_kph"]=float(ref["min_speed_kph"])
    if _num(ref.get("exit_speed_kph")): turn["reference_exit_speed_kph"]=float(ref["exit_speed_kph"])
    turn["apex_method"]="path_curvature"
    if diagnosis is None:
        diagnosis={"corner_id":turn.get("corner_id"),"reference_corner_id":turn.get("corner_id"),
                   "time_loss_s":turn.get("net_loss_s") if _num(turn.get("net_loss_s")) else turn.get("physical_net_loss_s"),
                   "entry_time_loss_s":turn.get("entry_loss_s"),"mid_time_loss_s":turn.get("mid_loss_s"),"exit_time_loss_s":turn.get("exit_loss_s"),
                   "coaching_eligible":False,"issue_candidates":(),"analysis_source":"physical_geometry_metrics"}
    diagnosis.update(metrics)
    diagnosis["apex_method"]="path_curvature"
    if _num(cur.get("apex_speed_kph")): diagnosis["apex_speed_kph"]=cur.get("apex_speed_kph")
    if _num(ref.get("apex_speed_kph")): diagnosis["reference_apex_speed_kph"]=ref.get("apex_speed_kph")
    new=_geometry_metric_candidates(metrics,diagnosis)
    existing=[dict(x) for x in (diagnosis.get("issue_candidates") or ()) if isinstance(x,dict)]
    all_candidates=existing+new
    # De-duplicate same code, retaining the higher deterministic score.
    by_code={}
    for row in all_candidates:
        code=str(row.get("code") or "")
        if not code: continue
        if code not in by_code or float(row.get("score") or 0.0)>float(by_code[code].get("score") or 0.0): by_code[code]=row
    all_candidates=sorted(by_code.values(),key=lambda x:(float(x.get("score") or 0.0),float(x.get("estimated_time_cost_s") or 0.0)),reverse=True)
    diagnosis["issue_candidates"]=tuple(all_candidates)
    eligible=[x for x in all_candidates if x.get("primary_eligible",True)]
    if eligible:
        top=eligible[0]
        old_score=0.0
        old_code=str(diagnosis.get("diagnosis") or "")
        for x in existing:
            if str(x.get("code") or "")==old_code: old_score=max(old_score,float(x.get("score") or 0.0))
        if str(top.get("evidence_source") or "")=="geometry_time_domain" and float(top.get("score") or 0.0)>=max(0.12,old_score):
            diagnosis["diagnosis"]=top["code"]; diagnosis["diagnosis_label"]=top["label"]
            diagnosis["diagnosis_confidence"]=float(top["confidence"]); diagnosis["actionability"]=float(top["actionability"])
            diagnosis["estimated_time_cost_s"]=float(top["estimated_time_cost_s"]); diagnosis["coaching_eligible"]=True
    return turn,diagnosis

def build_performance_pipeline(current: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """REFERENCE -> continuous map -> physical turns/straights -> diagnosis.

    This is the single deterministic performance object consumed by offline
    analysis, PRE coaching, POST coaching and the map UI.
    """
    model=build_distance_performance_model(current,reference)
    matched=[x.to_dict() for x in build_corner_analyses(current,reference,distance_model=model)]
    matched_by_raw={row.get("reference_corner_id"):row for row in matched if row.get("reference_corner_id") is not None}
    turns=[]; analyses=[]; unmapped=[]
    used_raw=set()
    for turn in model.get("turns",()) if isinstance(model,dict) else ():
        item=dict(turn); cid=int(item.get("corner_id") or 0)
        raw=item.get("reference_section_id")
        diagnosis=matched_by_raw.get(raw) if raw is not None else None
        if diagnosis is not None:
            diagnosis=dict(diagnosis); diagnosis["raw_reference_section_id"]=raw
            diagnosis["reference_corner_id"]=cid; diagnosis["corner_id"]=cid; diagnosis["analysis_source"]="matched_brake_section"
            used_raw.add(raw)
        else:
            diagnosis=_physical_turn_fallback(item,current,reference)
        item.update(_reference_targets(item,reference))
        item,diagnosis=_merge_geometry_metrics(item,diagnosis,current,reference)
        if diagnosis:
            item["diagnosis"]=diagnosis.get("diagnosis")
            item["diagnosis_label"]=diagnosis.get("diagnosis_label")
            item["diagnosis_confidence"]=diagnosis.get("diagnosis_confidence")
            item["coaching_eligible"]=diagnosis.get("coaching_eligible")
            item["issue_candidates"]=diagnosis.get("issue_candidates") or ()
            item["estimated_time_cost_s"]=diagnosis.get("estimated_time_cost_s")
            item["analysis_source"]=diagnosis.get("analysis_source")
            analyses.append(diagnosis)
        else:
            item["coaching_eligible"]=False
        turns.append(item)

    # Keep unmatched detector-section analyses for engineering/debug visibility,
    # but never feed their detector IDs into public physical-turn coaching/memory.
    for row in matched:
        if row.get("reference_corner_id") not in used_raw:
            extra=dict(row); extra["analysis_source"]="unmapped_brake_section"; unmapped.append(extra)
    return {
        "available":bool(model.get("available")) if isinstance(model,dict) else False,
        "distance_model":model,"gain_loss_zones":list(model.get("gain_loss_zones",())) if isinstance(model,dict) else [],
        "segments":list(model.get("segments",())) if isinstance(model,dict) else [],
        "turns":turns,"corner_analyses":analyses,"unmapped_section_analyses":unmapped,
        "reconciliation_error_s":model.get("reconciliation_error_s") if isinstance(model,dict) else None,
    }

