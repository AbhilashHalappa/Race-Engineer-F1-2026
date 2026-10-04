"""Typed data contracts for V1.1.0.0 CORNER COACH.

The public architecture deliberately separates physical circuit facts, measured
reference-driver actions, coaching segmentation, live performance and diagnosis.
No object is allowed to silently stand in for another.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PhysicalCorner:
    corner_id: int
    label: str
    start_m: float
    apex_m: float
    end_m: float
    direction: str | None = None
    curvature_score: float | None = None


@dataclass(frozen=True, slots=True)
class DrivingEvent:
    event_id: str
    kind: str
    start_m: float
    end_m: float
    peak_m: float | None = None
    peak_value: float | None = None
    direction: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CoachingZone:
    zone_id: str
    start_m: float
    end_m: float
    approach_start_m: float
    corner_ids: tuple[int, ...]
    event_ids: tuple[str, ...] = ()
    brake_start_m: float | None = None
    brake_release_m: float | None = None
    apex_m: float | None = None
    throttle_start_m: float | None = None
    full_throttle_m: float | None = None
    reference_min_speed_kph: float | None = None
    reference_apex_speed_kph: float | None = None
    reference_exit_speed_kph: float | None = None
    reference_gear: int | None = None
    label: str = ""
    confidence: float = 1.0

    @property
    def public_label(self) -> str:
        if self.label:
            return self.label
        if not self.corner_ids:
            return "CORNER"
        if len(self.corner_ids) == 1:
            return f"T{self.corner_ids[0]}"
        contiguous = tuple(range(self.corner_ids[0], self.corner_ids[-1] + 1)) == self.corner_ids
        if contiguous:
            return f"T{self.corner_ids[0]}–T{self.corner_ids[-1]}"
        return "/".join(f"T{x}" for x in self.corner_ids)


@dataclass(frozen=True, slots=True)
class ReferenceTrace:
    track_name: str
    track_length_m: float
    lap_time_s: float
    step_m: float
    samples: tuple[dict[str, Any], ...]
    physical_corners: tuple[PhysicalCorner, ...]
    driving_events: tuple[DrivingEvent, ...]
    coaching_zones: tuple[CoachingZone, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PerformanceTrace:
    available: bool
    points: tuple[dict[str, Any], ...] = ()
    full_track_net_delta_s: float | None = None
    reconciliation_error_s: float | None = None


@dataclass(frozen=True, slots=True)
class Diagnosis:
    zone_id: str
    public_label: str
    net_loss_s: float | None
    primary_code: str | None
    primary_text: str | None
    confidence: float
    measurements: dict[str, float | int | str | None] = field(default_factory=dict)
    phase_losses_s: dict[str, float | None] = field(default_factory=dict)


def to_dict(value: Any) -> Any:
    """Recursively convert CORNER COACH dataclasses to JSON-friendly data."""
    if hasattr(value, "__dataclass_fields__"):
        raw = asdict(value)
        return {k: to_dict(v) for k, v in raw.items()}
    if isinstance(value, tuple):
        return [to_dict(v) for v in value]
    if isinstance(value, list):
        return [to_dict(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_dict(v) for k, v in value.items()}
    return value
