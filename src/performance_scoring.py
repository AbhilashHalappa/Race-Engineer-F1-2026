"""V2.0.0 transparent performance score/evidence contract.

Scoring is deliberately downstream of authoritative measured telemetry.  This
module never detects corners, braking, apexes or throttle events; it consumes the
existing CornerAnalysis output and converts trusted measurements into an
inspectable presentation score.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Iterable

from .coaching_analysis import CornerAnalysis
from .data_quality import reference_compatible

SCORE_MODEL_VERSION = "2.0.0"


class EvidenceTier(int, Enum):
    CORNER = 1
    LAP = 2
    MULTI_LAP = 3
    LIVE_HISTORY = 4


class CompatibilityState(str, Enum):
    COMPATIBLE = "compatible"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INVALID_LAP = "invalid_lap"
    WET_DRY_MISMATCH = "wet_dry_mismatch"
    TRAFFIC = "traffic"
    PIT_PHASE = "pit_phase"
    SAFETY_CAR = "safety_car_or_vsc"
    DAMAGE = "significant_damage"
    TYRE_STATE = "incompatible_tyre_state"
    FUEL_STATE = "incompatible_fuel_state"
    REFERENCE_MISMATCH = "reference_mismatch"
    UNKNOWN = "unknown"


class ScoreStatus(str, Enum):
    AVAILABLE = "available"
    NOT_AVAILABLE = "n/a"


@dataclass(frozen=True, slots=True)
class TechniqueMetricEvidence:
    evidence_id: str
    metric: str
    tier: EvidenceTier
    current_value: float | None
    reference_value: float | None
    delta: float | None
    confidence: float
    sample_count: int
    compatibility: CompatibilityState = CompatibilityState.COMPATIBLE
    unit: str | None = None
    source: str = "CornerAnalysis"
    raw_evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def trusted(self) -> bool:
        return (
            self.compatibility is CompatibilityState.COMPATIBLE
            and _finite(self.delta)
            and 0.0 <= float(self.confidence) <= 1.0
            and self.sample_count >= 1
        )

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["tier"] = int(self.tier)
        out["compatibility"] = self.compatibility.value
        out["trusted"] = self.trusted
        return out


@dataclass(frozen=True, slots=True)
class TechniqueScore:
    metric: str
    status: ScoreStatus
    value: float | None
    confidence: float
    sample_count: int
    compatibility: CompatibilityState
    score_model_version: str = SCORE_MODEL_VERSION
    reference_identity: str | None = None
    reference_version: str | None = None
    raw_evidence_ids: tuple[str, ...] = ()
    evidence: tuple[TechniqueMetricEvidence, ...] = ()

    @classmethod
    def na(
        cls,
        metric: str,
        *,
        confidence: float = 0.0,
        sample_count: int = 0,
        compatibility: CompatibilityState = CompatibilityState.INSUFFICIENT_EVIDENCE,
        reference_identity: str | None = None,
        reference_version: str | None = None,
        evidence: Iterable[TechniqueMetricEvidence] = (),
    ) -> "TechniqueScore":
        ev = tuple(evidence)
        return cls(
            metric=metric,
            status=ScoreStatus.NOT_AVAILABLE,
            value=None,
            confidence=_clamp01(confidence),
            sample_count=max(0, int(sample_count)),
            compatibility=compatibility,
            reference_identity=reference_identity,
            reference_version=reference_version,
            raw_evidence_ids=_evidence_ids(ev),
            evidence=ev,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "status": self.status.value,
            "value": self.value,
            "confidence": self.confidence,
            "sample_count": self.sample_count,
            "compatibility": self.compatibility.value,
            "score_model_version": self.score_model_version,
            "reference_identity": self.reference_identity,
            "reference_version": self.reference_version,
            "raw_evidence_ids": list(self.raw_evidence_ids),
            "evidence": [x.to_dict() for x in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class CornerTechniqueScore:
    corner_id: int | None
    status: ScoreStatus
    score: float | None
    confidence: float
    sample_count: int
    dimensions: dict[str, TechniqueScore]
    compatibility: CompatibilityState
    score_model_version: str = SCORE_MODEL_VERSION
    reference_identity: str | None = None
    reference_version: str | None = None
    raw_evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "corner_id": self.corner_id,
            "status": self.status.value,
            "score": self.score,
            "confidence": self.confidence,
            "sample_count": self.sample_count,
            "compatibility": self.compatibility.value,
            "score_model_version": self.score_model_version,
            "reference_identity": self.reference_identity,
            "reference_version": self.reference_version,
            "raw_evidence_ids": list(self.raw_evidence_ids),
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
        }


@dataclass(frozen=True, slots=True)
class LapTechniqueScore:
    lap_number: int | None
    status: ScoreStatus
    score: float | None
    confidence: float
    sample_count: int
    scored_corner_count: int
    eligible_corner_count: int
    coverage: float
    compatibility: CompatibilityState
    score_model_version: str = SCORE_MODEL_VERSION
    corner_scores: tuple[CornerTechniqueScore, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "lap_number": self.lap_number,
            "status": self.status.value,
            "score": self.score,
            "confidence": self.confidence,
            "sample_count": self.sample_count,
            "scored_corner_count": self.scored_corner_count,
            "eligible_corner_count": self.eligible_corner_count,
            "coverage": self.coverage,
            "compatibility": self.compatibility.value,
            "score_model_version": self.score_model_version,
            "corner_scores": [x.to_dict() for x in self.corner_scores],
        }


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _evidence_ids(evidence: Iterable[TechniqueMetricEvidence]) -> tuple[str, ...]:
    out: list[str] = []
    for row in evidence:
        for evidence_id in (row.evidence_id, *row.raw_evidence_ids):
            if evidence_id and evidence_id not in out:
                out.append(evidence_id)
    return tuple(out)


# deadband: no meaningful score loss inside it; full_scale: deviation at which
# the score reaches zero.  The explicit table makes V2 calibration inspectable.
_METRIC_RULES: dict[str, tuple[float, float, str]] = {
    "braking_point": (3.0, 35.0, "absolute"),
    "brake_release": (3.0, 35.0, "absolute"),
    "trail_braking": (5.0, 45.0, "absolute"),
    "turn_in": (3.0, 35.0, "absolute"),
    "min_apex_speed": (1.0, 20.0, "deficit"),
    "throttle_pickup": (0.03, 0.80, "excess"),
    "time_to_full_throttle": (0.03, 0.80, "excess"),
    "exit_speed": (1.0, 20.0, "deficit"),
    "steering_control": (0.05, 0.60, "deficit"),
    # Racing-line consistency is Tier 3 and intentionally not synthesized from
    # one CornerAnalysis observation.
}


def normalize_metric_score(delta: float, *, deadband: float, full_scale: float, mode: str = "absolute") -> float:
    """Deterministic monotonic 0..100 normalization.

    absolute: deviation in either direction is worse.
    deficit: negative deltas are worse; equal/better values retain 100.
    excess: positive deltas are worse; equal/lower values retain 100.
    """
    if not _finite(delta) or deadband < 0.0 or full_scale <= deadband:
        raise ValueError("invalid score normalization input")
    d = float(delta)
    if mode == "absolute":
        error = abs(d)
    elif mode == "deficit":
        error = max(0.0, -d)
    elif mode == "excess":
        error = max(0.0, d)
    else:
        raise ValueError(f"unsupported score mode: {mode}")
    if error <= deadband:
        return 100.0
    fraction = min(1.0, (error - deadband) / (full_scale - deadband))
    return round(100.0 * (1.0 - fraction), 3)


def score_metric(
    evidence: TechniqueMetricEvidence,
    *,
    reference_identity: str | None = None,
    reference_version: str | None = None,
) -> TechniqueScore:
    rule = _METRIC_RULES.get(evidence.metric)
    if not evidence.trusted or rule is None:
        compatibility = evidence.compatibility if evidence.compatibility is not CompatibilityState.COMPATIBLE else CompatibilityState.INSUFFICIENT_EVIDENCE
        return TechniqueScore.na(
            evidence.metric,
            confidence=evidence.confidence,
            sample_count=evidence.sample_count,
            compatibility=compatibility,
            reference_identity=reference_identity,
            reference_version=reference_version,
            evidence=(evidence,),
        )
    deadband, full_scale, mode = rule
    if evidence.metric == "throttle_pickup" and evidence.unit == "m":
        deadband, full_scale, mode = 5.0, 50.0, "excess"
    raw_score = normalize_metric_score(float(evidence.delta), deadband=deadband, full_scale=full_scale, mode=mode)
    # Confidence does not rewrite the measurement.  It only bounds how strongly
    # the presentation score can depart from neutral/reference-match (100).
    confidence = _clamp01(evidence.confidence)
    value = round(100.0 - (100.0 - raw_score) * confidence, 3)
    return TechniqueScore(
        metric=evidence.metric,
        status=ScoreStatus.AVAILABLE,
        value=value,
        confidence=confidence,
        sample_count=evidence.sample_count,
        compatibility=evidence.compatibility,
        reference_identity=reference_identity,
        reference_version=reference_version,
        raw_evidence_ids=_evidence_ids((evidence,)),
        evidence=(evidence,),
    )


def _metric_evidence(
    analysis: CornerAnalysis,
    metric: str,
    current: Any,
    reference: Any,
    delta: Any,
    unit: str,
    *,
    compatibility: CompatibilityState,
    evidence_prefix: str,
) -> TechniqueMetricEvidence:
    cid = analysis.reference_corner_id if analysis.reference_corner_id is not None else analysis.corner_id
    evidence_id = f"{evidence_prefix}:corner:{cid}:{metric}"
    trusted_delta = float(delta) if _finite(delta) else None
    return TechniqueMetricEvidence(
        evidence_id=evidence_id,
        metric=metric,
        tier=EvidenceTier.CORNER,
        current_value=float(current) if _finite(current) else None,
        reference_value=float(reference) if _finite(reference) else None,
        delta=trusted_delta,
        confidence=_clamp01(analysis.confidence),
        sample_count=1 if trusted_delta is not None else 0,
        compatibility=compatibility,
        unit=unit,
        raw_evidence_ids=(evidence_id,),
        metadata={"corner_id": cid, "confidence_reasons": list(analysis.confidence_reasons)},
    )


def corner_evidence_from_analysis(
    analysis: CornerAnalysis,
    *,
    compatibility: CompatibilityState = CompatibilityState.COMPATIBLE,
    evidence_prefix: str = "live",
) -> dict[str, TechniqueMetricEvidence]:
    """Map existing CornerAnalysis measurements into V2 evidence; no redetection."""
    # Prefer time-domain throttle measurements where available; fall back to the
    # already-measured distance delta without deriving a new event.
    pickup_current = analysis.throttle_pickup_after_apex_s
    pickup_reference = analysis.reference_throttle_pickup_after_apex_s
    pickup_delta = analysis.throttle_pickup_after_apex_delta_s
    pickup_unit = "s"
    if not _finite(pickup_delta):
        pickup_current, pickup_reference, pickup_delta, pickup_unit = (
            analysis.throttle_pickup_m,
            analysis.reference_throttle_pickup_m,
            analysis.throttle_pickup_delta_m,
            "m",
        )
    rows = {
        "braking_point": (analysis.brake_onset_m, analysis.reference_brake_onset_m, analysis.brake_onset_delta_m, "m"),
        "brake_release": (analysis.brake_release_m, analysis.reference_brake_release_m, analysis.brake_release_delta_m, "m"),
        "trail_braking": (analysis.trail_brake_m, analysis.reference_trail_brake_m, analysis.trail_brake_delta_m, "m"),
        "turn_in": (analysis.turn_in_m, analysis.reference_turn_in_m, analysis.turn_in_delta_m, "m"),
        "min_apex_speed": (analysis.apex_speed_kph if _finite(analysis.apex_speed_kph) else analysis.min_speed_kph,
                           analysis.reference_apex_speed_kph if _finite(analysis.reference_apex_speed_kph) else analysis.reference_min_speed_kph,
                           analysis.apex_speed_delta_kph if _finite(analysis.apex_speed_delta_kph) else analysis.min_speed_delta_kph, "km/h"),
        "throttle_pickup": (pickup_current, pickup_reference, pickup_delta, pickup_unit),
        "time_to_full_throttle": (analysis.pickup_to_full_throttle_s, analysis.reference_pickup_to_full_throttle_s, analysis.pickup_to_full_throttle_delta_s, "s"),
        "exit_speed": (analysis.exit_speed_kph, analysis.reference_exit_speed_kph, analysis.exit_speed_delta_kph, "km/h"),
        "steering_control": (analysis.steering_smoothness, analysis.reference_steering_smoothness, analysis.steering_smoothness_delta, "ratio"),
    }
    out = {
        metric: _metric_evidence(analysis, metric, cur, ref, delta, unit, compatibility=compatibility, evidence_prefix=evidence_prefix)
        for metric, (cur, ref, delta, unit) in rows.items()
    }
    cid = analysis.reference_corner_id if analysis.reference_corner_id is not None else analysis.corner_id
    out["racing_line_consistency"] = TechniqueMetricEvidence(
        evidence_id=f"{evidence_prefix}:corner:{cid}:racing_line_consistency",
        metric="racing_line_consistency", tier=EvidenceTier.MULTI_LAP,
        current_value=None, reference_value=None, delta=None, confidence=0.0, sample_count=0,
        compatibility=CompatibilityState.INSUFFICIENT_EVIDENCE, unit="m",
        raw_evidence_ids=(f"{evidence_prefix}:corner:{cid}:racing_line_consistency",),
        metadata={"reason": "requires_multi_lap_evidence"},
    )
    return out



def compatibility_from_laps(current: dict[str, Any] | None, reference: dict[str, Any] | None) -> CompatibilityState:
    """Translate existing authoritative quality gates into the V2 score contract."""
    result = reference_compatible(current, reference)
    if result.get("eligible"):
        return CompatibilityState.COMPATIBLE
    reasons = tuple(str(x) for x in result.get("reasons") or ())
    ordered = (
        ("mismatch:wet_dry", CompatibilityState.WET_DRY_MISMATCH),
        ("pit_lap", CompatibilityState.PIT_PHASE),
        ("traffic_compromised", CompatibilityState.TRAFFIC),
        ("race_control_compromised", CompatibilityState.SAFETY_CAR),
        ("damage_compromised", CompatibilityState.DAMAGE),
        ("invalid_lap", CompatibilityState.INVALID_LAP),
        ("mismatch:track", CompatibilityState.REFERENCE_MISMATCH),
        ("mismatch:track_id", CompatibilityState.REFERENCE_MISMATCH),
        ("mismatch:game_version", CompatibilityState.REFERENCE_MISMATCH),
    )
    for token, state in ordered:
        if any(token in reason for reason in reasons):
            return state
    return CompatibilityState.UNKNOWN


def build_lap_technique_score(
    corner_scores: Iterable[CornerTechniqueScore],
    *,
    lap_number: int | None = None,
    eligible_corner_count: int | None = None,
    minimum_coverage: float = 0.60,
    compatibility: CompatibilityState = CompatibilityState.COMPATIBLE,
) -> LapTechniqueScore:
    """Tier-2 aggregation. A lap score is never produced from one isolated corner."""
    rows = tuple(corner_scores)
    total = int(eligible_corner_count if eligible_corner_count is not None else len(rows))
    available = [x for x in rows if x.status is ScoreStatus.AVAILABLE and _finite(x.score)]
    coverage = (len(available) / total) if total > 0 else 0.0
    if compatibility is not CompatibilityState.COMPATIBLE or len(available) < 2 or coverage < minimum_coverage:
        comp = compatibility if compatibility is not CompatibilityState.COMPATIBLE else CompatibilityState.INSUFFICIENT_EVIDENCE
        return LapTechniqueScore(
            lap_number=lap_number, status=ScoreStatus.NOT_AVAILABLE, score=None,
            confidence=0.0 if not available else round(sum(x.confidence for x in available)/len(available),4),
            sample_count=len(available), scored_corner_count=len(available), eligible_corner_count=total,
            coverage=round(coverage,4), compatibility=comp, corner_scores=rows,
        )
    # Use robust equal-corner weighting in V2.0.0. Time-cost prioritization remains
    # authoritative for coaching and is intentionally not replaced by this score.
    return LapTechniqueScore(
        lap_number=lap_number, status=ScoreStatus.AVAILABLE,
        score=round(sum(float(x.score) for x in available)/len(available),3),
        confidence=round(sum(x.confidence for x in available)/len(available),4),
        sample_count=len(available), scored_corner_count=len(available), eligible_corner_count=total,
        coverage=round(coverage,4), compatibility=CompatibilityState.COMPATIBLE, corner_scores=rows,
    )

def build_corner_technique_score(
    analysis: CornerAnalysis,
    *,
    compatibility: CompatibilityState = CompatibilityState.COMPATIBLE,
    reference_identity: str | None = None,
    reference_version: str | None = None,
    evidence_prefix: str = "live",
) -> CornerTechniqueScore:
    evidence = corner_evidence_from_analysis(analysis, compatibility=compatibility, evidence_prefix=evidence_prefix)
    dimensions = {
        metric: score_metric(row, reference_identity=reference_identity, reference_version=reference_version)
        for metric, row in evidence.items()
    }
    available = [x for x in dimensions.values() if x.status is ScoreStatus.AVAILABLE and _finite(x.value)]
    cid = analysis.reference_corner_id if analysis.reference_corner_id is not None else analysis.corner_id
    if compatibility is not CompatibilityState.COMPATIBLE or not available:
        comp = compatibility if compatibility is not CompatibilityState.COMPATIBLE else CompatibilityState.INSUFFICIENT_EVIDENCE
        return CornerTechniqueScore(
            corner_id=cid,
            status=ScoreStatus.NOT_AVAILABLE,
            score=None,
            confidence=_clamp01(analysis.confidence),
            sample_count=0,
            dimensions=dimensions,
            compatibility=comp,
            reference_identity=reference_identity,
            reference_version=reference_version,
            raw_evidence_ids=_evidence_ids(evidence.values()),
        )
    weights = {"braking_point": 1.0, "brake_release": 0.8, "trail_braking": 0.8, "turn_in": 0.8,
               "min_apex_speed": 1.0, "throttle_pickup": 1.0, "time_to_full_throttle": 0.8,
               "exit_speed": 1.0, "steering_control": 0.6}
    total_weight = sum(weights.get(x.metric, 1.0) for x in available)
    score = sum(float(x.value) * weights.get(x.metric, 1.0) for x in available) / total_weight
    confidence = sum(x.confidence * weights.get(x.metric, 1.0) for x in available) / total_weight
    return CornerTechniqueScore(
        corner_id=cid,
        status=ScoreStatus.AVAILABLE,
        score=round(score, 3),
        confidence=round(confidence, 4),
        sample_count=len(available),
        dimensions=dimensions,
        compatibility=CompatibilityState.COMPATIBLE,
        reference_identity=reference_identity,
        reference_version=reference_version,
        raw_evidence_ids=_evidence_ids(evidence.values()),
    )


def score_grade(score: float | None) -> str:
    """Human-readable V2 live grade. N/A is explicit and never synthesized."""
    if not _finite(score):
        return "N/A"
    value = float(score)
    if value >= 90.0:
        return "EXCELLENT"
    if value >= 80.0:
        return "GOOD"
    if value >= 65.0:
        return "FAIR"
    return "NEEDS WORK"


def build_live_corner_score_from_diagnosis(
    diagnosis: Any,
    *,
    corner_id: int | None = None,
    reference_identity: str | None = None,
    reference_version: str | None = None,
    evidence_prefix: str = "live-zone",
) -> CornerTechniqueScore:
    """Build Tier-1 score directly from CORNER COACH's measured diagnosis.

    This is deliberately downstream of the existing live measurement pipeline:
    no braking/apex/throttle event is re-detected here. Missing measurements stay
    N/A and confidence is inherited from the deterministic diagnosis.
    """
    row = diagnosis if isinstance(diagnosis, dict) else asdict(diagnosis)
    measurements = row.get("measurements") if isinstance(row.get("measurements"), dict) else {}
    confidence = _clamp01(float(row.get("confidence", 0.0) or 0.0))
    zone_id = str(row.get("zone_id") or "unknown")
    cid = corner_id
    if cid is None and _finite(measurements.get("dominant_corner")):
        cid = int(float(measurements["dominant_corner"]))

    specs = (
        ("braking_point", "brake_point_delta_m", "m"),
        ("brake_release", "brake_release_delta_m", "m"),
        ("turn_in", "turn_in_delta_m", "m"),
        ("min_apex_speed", "min_speed_delta_kph", "kph"),
        ("exit_speed", "exit_speed_delta_kph", "kph"),
    )
    evidence: dict[str, TechniqueMetricEvidence] = {}
    for metric, key, unit in specs:
        delta = measurements.get(key)
        evidence[metric] = TechniqueMetricEvidence(
            evidence_id=f"{evidence_prefix}:{zone_id}:{metric}", metric=metric, tier=EvidenceTier.CORNER,
            current_value=None, reference_value=None, delta=float(delta) if _finite(delta) else None,
            confidence=confidence, sample_count=1 if _finite(delta) else 0,
            compatibility=CompatibilityState.COMPATIBLE if _finite(delta) else CompatibilityState.INSUFFICIENT_EVIDENCE,
            unit=unit, source="CornerCoach.Diagnosis",
        )

    # Prefer the time-domain throttle measurement when geometry confidence made
    # it trustworthy; otherwise use the already-measured distance-domain delta.
    throttle_s = measurements.get("throttle_pickup_delta_s")
    throttle_m = measurements.get("throttle_pickup_delta_m")
    throttle_delta = throttle_s if _finite(throttle_s) else throttle_m
    throttle_unit = "s" if _finite(throttle_s) else "m"
    evidence["throttle_pickup"] = TechniqueMetricEvidence(
        evidence_id=f"{evidence_prefix}:{zone_id}:throttle_pickup", metric="throttle_pickup", tier=EvidenceTier.CORNER,
        current_value=None, reference_value=None, delta=float(throttle_delta) if _finite(throttle_delta) else None,
        confidence=confidence, sample_count=1 if _finite(throttle_delta) else 0,
        compatibility=CompatibilityState.COMPATIBLE if _finite(throttle_delta) else CompatibilityState.INSUFFICIENT_EVIDENCE,
        unit=throttle_unit, source="CornerCoach.Diagnosis",
    )
    full_delta = measurements.get("full_throttle_delta_m")
    evidence["time_to_full_throttle"] = TechniqueMetricEvidence(
        evidence_id=f"{evidence_prefix}:{zone_id}:time_to_full_throttle", metric="time_to_full_throttle", tier=EvidenceTier.CORNER,
        current_value=None, reference_value=None, delta=float(full_delta) if _finite(full_delta) else None,
        confidence=confidence, sample_count=1 if _finite(full_delta) else 0,
        compatibility=CompatibilityState.COMPATIBLE if _finite(full_delta) else CompatibilityState.INSUFFICIENT_EVIDENCE,
        unit="m", source="CornerCoach.Diagnosis",
    )

    dimensions = {
        metric: score_metric(ev, reference_identity=reference_identity, reference_version=reference_version)
        for metric, ev in evidence.items()
    }
    available = [x for x in dimensions.values() if x.status is ScoreStatus.AVAILABLE and _finite(x.value)]
    if not available:
        return CornerTechniqueScore(
            corner_id=cid, status=ScoreStatus.NOT_AVAILABLE, score=None, confidence=confidence, sample_count=0,
            dimensions=dimensions, compatibility=CompatibilityState.INSUFFICIENT_EVIDENCE,
            reference_identity=reference_identity, reference_version=reference_version, raw_evidence_ids=_evidence_ids(evidence.values()),
        )
    weights = {"braking_point":1.0,"brake_release":0.8,"turn_in":0.8,"min_apex_speed":1.0,"throttle_pickup":1.0,"time_to_full_throttle":0.8,"exit_speed":1.0}
    total = sum(weights.get(x.metric,1.0) for x in available)
    score = sum(float(x.value)*weights.get(x.metric,1.0) for x in available)/total
    conf = sum(x.confidence*weights.get(x.metric,1.0) for x in available)/total
    return CornerTechniqueScore(
        corner_id=cid, status=ScoreStatus.AVAILABLE, score=round(score,3), confidence=round(conf,4), sample_count=len(available),
        dimensions=dimensions, compatibility=CompatibilityState.COMPATIBLE, reference_identity=reference_identity, reference_version=reference_version,
        raw_evidence_ids=_evidence_ids(evidence.values()),
    )
