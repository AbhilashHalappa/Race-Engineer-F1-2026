"""Persistent runtime settings for the integrated deterministic coaching suite.

Settings are deliberately local JSON.  They control *delivery*, never the
underlying measured facts, so replay/offline analysis remains deterministic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
import json
from pathlib import Path
from typing import Any


_ALLOWED_MODES = {
    "auto", "race_engineer", "performance_coach", "track_learning",
    "qualifying", "time_trial", "silent_analysis",
}
_ALLOWED_VERBOSITY = {"minimal", "normal", "detailed"}


@dataclass(frozen=True, slots=True)
class CoachingSettings:
    # Delivery switches requested by the user.
    post_corner: bool = True
    pre_corner: bool = True
    lap_summary: bool = True
    positive_calls: bool = True
    race_coaching: bool = True
    auto_reports: bool = True
    progress_history: bool = True

    # Behaviour.
    mode: str = "auto"
    verbosity: str = "normal"
    pre_corner_target_s: float = 5.5
    pre_corner_min_s: float = 4.0
    pre_corner_max_s: float = 7.0
    post_corner_max_calls_per_lap: int = 2
    pre_corner_max_calls_per_lap: int = 2
    race_max_calls_per_lap: int = 1
    same_issue_cooldown_laps: int = 2
    positive_improvement_threshold_s: float = 0.040
    lap_summary_min_gap_s: float = 0.080
    traffic_gap_s: float = 1.2
    rear_traffic_gap_s: float = 1.0
    stale_telemetry_s: float = 1.0
    stale_lap_s: float = 2.0

    def validated(self) -> "CoachingSettings":
        mode = self.mode if self.mode in _ALLOWED_MODES else "auto"
        verbosity = self.verbosity if self.verbosity in _ALLOWED_VERBOSITY else "normal"
        lo = max(2.0, float(self.pre_corner_min_s))
        hi = max(lo, float(self.pre_corner_max_s))
        target = min(hi, max(lo, float(self.pre_corner_target_s)))
        return replace(
            self,
            mode=mode,
            verbosity=verbosity,
            pre_corner_min_s=lo,
            pre_corner_max_s=hi,
            pre_corner_target_s=target,
            post_corner_max_calls_per_lap=max(0, min(6, int(self.post_corner_max_calls_per_lap))),
            pre_corner_max_calls_per_lap=max(0, min(6, int(self.pre_corner_max_calls_per_lap))),
            race_max_calls_per_lap=max(0, min(3, int(self.race_max_calls_per_lap))),
            same_issue_cooldown_laps=max(0, min(10, int(self.same_issue_cooldown_laps))),
            positive_improvement_threshold_s=max(0.015, min(1.0, float(self.positive_improvement_threshold_s))),
            lap_summary_min_gap_s=max(0.0, min(2.0, float(self.lap_summary_min_gap_s))),
            traffic_gap_s=max(0.3, min(5.0, float(self.traffic_gap_s))),
            rear_traffic_gap_s=max(0.3, min(5.0, float(self.rear_traffic_gap_s))),
            stale_telemetry_s=max(0.25, min(5.0, float(self.stale_telemetry_s))),
            stale_lap_s=max(0.5, min(10.0, float(self.stale_lap_s))),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.validated())

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "CoachingSettings":
        if not isinstance(value, dict):
            return cls()
        allowed = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in value.items() if k in allowed}
        try:
            return cls(**kwargs).validated()
        except (TypeError, ValueError):
            return cls()


class CoachingSettingsStore:
    def __init__(self, path: str | Path = "settings/coaching.json") -> None:
        self.path = Path(path)
        self.settings = self.load()

    def load(self) -> CoachingSettings:
        try:
            if self.path.exists():
                return CoachingSettings.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return CoachingSettings()

    def save(self, settings: CoachingSettings | None = None) -> CoachingSettings:
        if settings is not None:
            self.settings = settings.validated()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.settings.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
        return self.settings

    def set(self, **changes: Any) -> CoachingSettings:
        allowed = {f.name for f in fields(CoachingSettings)}
        filtered = {k: v for k, v in changes.items() if k in allowed}
        self.settings = replace(self.settings, **filtered).validated()
        try:
            self.save()
        except OSError:
            # Runtime control must remain usable even on a read-only install.
            pass
        return self.settings

    def reset(self) -> CoachingSettings:
        self.settings = CoachingSettings()
        try:
            self.save()
        except OSError:
            pass
        return self.settings
