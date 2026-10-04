"""V0.9.20.2 deterministic coaching priority and multi-lap pattern memory.

This module consumes loss-guarded ``CornerAnalysis`` dictionaries. It does not
re-derive telemetry and it does not generate speech. Its job is to:

- rank only already-eligible corrective issues;
- weight measured time cost, confidence, repeat frequency and actionability;
- keep per-corner/per-issue history across completed lap comparisons;
- expose persistence and simple improvement/regression trends;
- select one deterministic coaching focus per lap and one session focus.

All outputs are descriptive measurements. Trend labels describe the measured
history of the same issue; they are not causal claims or predictions.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from statistics import mean, median
from typing import Any, Iterable
import math


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _round(value: Any, digits: int = 6):
    return round(float(value), digits) if _num(value) else value


@dataclass(slots=True)
class CoachingPriorityItem:
    lap: int | None
    corner_id: int | None
    issue_code: str
    issue_label: str
    phase: str | None
    magnitude: float | None
    estimated_time_cost_s: float
    confidence: float
    actionability: float
    severity: float
    repeat_count: int
    opportunity_count: int
    repeat_factor: float
    persistence: float
    priority_score: float
    rank: int = 0
    selected_focus: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CoachingPattern:
    corner_id: int | None
    issue_code: str
    issue_label: str
    phase: str | None
    observations: int
    opportunities: int
    repeat_count: int
    persistence: float
    mean_magnitude: float | None
    median_magnitude: float | None
    mean_time_cost_s: float
    median_time_cost_s: float
    total_measured_time_cost_s: float
    mean_confidence: float
    mean_actionability: float
    first_lap: int | None
    last_lap: int | None
    recent_time_cost_s: float | None
    latest_observed: bool
    trend: str
    trend_delta_s: float | None
    focus_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class _History:
    label: str
    phase: str | None
    observations: list[dict[str, Any]] = field(default_factory=list)
    opportunities: int = 0
    last_opportunity_lap: int | None = None


class CoachingMemory:
    """Session-scoped deterministic issue memory.

    An *opportunity* is a lap comparison in which the same physical corner was
    measured with sufficient quality to appear in ``corner_analyses``. An
    *observation* is an issue candidate that survived the V0.9.20.1.x
    loss/confidence guards and is primary-eligible.
    """

    def __init__(self) -> None:
        self._histories: dict[tuple[int | None, str], _History] = {}
        self._corner_opportunities: dict[int | None, int] = {}
        self._lap_focuses: list[dict[str, Any]] = []

    @staticmethod
    def _primary_candidates(corner: dict[str, Any]) -> list[dict[str, Any]]:
        if not corner.get("coaching_eligible"):
            return []
        out = []
        for c in corner.get("issue_candidates") or []:
            if not isinstance(c, dict) or not c.get("primary_eligible", True):
                continue
            if not _num(c.get("estimated_time_cost_s")) or float(c["estimated_time_cost_s"]) <= 0.0:
                continue
            if not _num(c.get("confidence")) or not _num(c.get("actionability")):
                continue
            code = c.get("code")
            if not code:
                continue
            out.append(c)
        return out

    def ingest_lap(self, lap: int | None, corner_analyses: Iterable[dict[str, Any]]) -> dict[str, Any]:
        corners = [c for c in corner_analyses if isinstance(c, dict)]

        # First count measurement opportunities for every observed physical corner.
        # Existing issue histories are updated even when the issue is absent on
        # this lap. That makes persistence meaningful and lets the memory notice
        # when a previously coached issue stops recurring.
        seen_corners: set[int | None] = set()
        for corner in corners:
            cid = corner.get("corner_id")
            if cid in seen_corners:
                continue
            seen_corners.add(cid)
            self._corner_opportunities[cid] = self._corner_opportunities.get(cid, 0) + 1
        for (cid, _code), history in self._histories.items():
            if cid in seen_corners:
                history.opportunities = self._corner_opportunities.get(cid, history.opportunities)
                history.last_opportunity_lap = lap if isinstance(lap, int) else history.last_opportunity_lap

        items: list[CoachingPriorityItem] = []
        for corner in corners:
            cid = corner.get("corner_id")
            opportunities = self._corner_opportunities.get(cid, 1)
            for c in self._primary_candidates(corner):
                code = str(c["code"])
                key = (cid, code)
                history = self._histories.get(key)
                if history is None:
                    history = _History(label=str(c.get("label") or code), phase=c.get("phase"))
                    self._histories[key] = history
                history.opportunities = opportunities
                history.last_opportunity_lap = lap if isinstance(lap, int) else history.last_opportunity_lap
                history.observations.append({
                    "lap": lap,
                    "magnitude": float(c["magnitude"]) if _num(c.get("magnitude")) else None,
                    "estimated_time_cost_s": float(c["estimated_time_cost_s"]),
                    "confidence": float(c["confidence"]),
                    "actionability": float(c["actionability"]),
                    "severity": float(c.get("severity", 0.0)) if _num(c.get("severity")) else 0.0,
                })
                repeat_count = len(history.observations)
                persistence = repeat_count / max(1, opportunities)
                # Repeat frequency promotes persistent errors without allowing an
                # old habit to overwhelm a much larger current measured loss.
                repeat_factor = min(1.75, 1.0 + 0.25 * max(0, repeat_count - 1) * persistence)
                time_cost = float(c["estimated_time_cost_s"])
                confidence = _clamp(c["confidence"])
                actionability = _clamp(c["actionability"])
                priority = time_cost * confidence * actionability * repeat_factor
                items.append(CoachingPriorityItem(
                    lap=lap,
                    corner_id=cid,
                    issue_code=code,
                    issue_label=str(c.get("label") or code),
                    phase=c.get("phase"),
                    magnitude=float(c["magnitude"]) if _num(c.get("magnitude")) else None,
                    estimated_time_cost_s=time_cost,
                    confidence=confidence,
                    actionability=actionability,
                    severity=_clamp(c.get("severity", 0.0)) if _num(c.get("severity")) else 0.0,
                    repeat_count=repeat_count,
                    opportunity_count=opportunities,
                    repeat_factor=repeat_factor,
                    persistence=persistence,
                    priority_score=priority,
                ))

        items.sort(
            key=lambda x: (
                x.priority_score,
                x.estimated_time_cost_s,
                x.confidence,
                -999999 if x.corner_id is None else -int(x.corner_id),
                x.issue_code,
            ),
            reverse=True,
        )
        for rank, item in enumerate(items, 1):
            item.rank = rank
        if items:
            items[0].selected_focus = True
            self._lap_focuses.append(items[0].to_dict())

        return {
            "lap": lap,
            "candidate_count": len(items),
            "selected_focus": items[0].to_dict() if items else None,
            "ranked_candidates": [x.to_dict() for x in items],
            "selection_rule": "estimated_time_cost_s * confidence * actionability * repeat_factor; one selected focus per lap",
        }

    def patterns(self) -> list[CoachingPattern]:
        out: list[CoachingPattern] = []
        for (corner_id, code), history in self._histories.items():
            obs = history.observations
            if not obs:
                continue
            costs = [float(x["estimated_time_cost_s"]) for x in obs]
            magnitudes = [float(x["magnitude"]) for x in obs if _num(x.get("magnitude"))]
            confidences = [float(x["confidence"]) for x in obs]
            actionabilities = [float(x["actionability"]) for x in obs]
            persistence = len(obs) / max(1, history.opportunities)

            last_observed_lap = obs[-1].get("lap") if obs else None
            latest_observed = not (
                isinstance(history.last_opportunity_lap, int)
                and isinstance(last_observed_lap, int)
                and last_observed_lap < history.last_opportunity_lap
            )
            trend = "insufficient_history"
            trend_delta = None
            if not latest_observed and history.opportunities > len(obs):
                # The same corner was measured again but this issue no longer
                # survived the loss/confidence guards. Treat that as measured
                # improvement, without claiming why it changed.
                trend = "improving"
            elif len(costs) >= 2:
                trend_delta = costs[-1] - costs[0]
                # 15 ms avoids labeling tiny measurement movement as progress/regression.
                if trend_delta <= -0.015:
                    trend = "improving"
                elif trend_delta >= 0.015:
                    trend = "regressing"
                else:
                    trend = "stable"

            # Pattern focus score is based on mean measured cost and reliability,
            # with persistence as the repeat-frequency term.
            repeat_factor = min(1.75, 1.0 + 0.75 * persistence)
            focus_score = mean(costs) * mean(confidences) * mean(actionabilities) * repeat_factor
            laps = [x.get("lap") for x in obs if isinstance(x.get("lap"), int)]
            out.append(CoachingPattern(
                corner_id=corner_id,
                issue_code=code,
                issue_label=history.label,
                phase=history.phase,
                observations=len(obs),
                opportunities=max(history.opportunities, len(obs)),
                repeat_count=len(obs),
                persistence=persistence,
                mean_magnitude=mean(magnitudes) if magnitudes else None,
                median_magnitude=median(magnitudes) if magnitudes else None,
                mean_time_cost_s=mean(costs),
                median_time_cost_s=median(costs),
                total_measured_time_cost_s=sum(costs),
                mean_confidence=mean(confidences),
                mean_actionability=mean(actionabilities),
                first_lap=min(laps) if laps else None,
                last_lap=max(laps) if laps else None,
                recent_time_cost_s=costs[-1],
                latest_observed=latest_observed,
                trend=trend,
                trend_delta_s=trend_delta,
                focus_score=focus_score,
            ))

        out.sort(
            key=lambda x: (x.focus_score, x.mean_time_cost_s, x.persistence, x.repeat_count),
            reverse=True,
        )
        return out

    def recurring_patterns(self, minimum_repeats: int = 2) -> list[CoachingPattern]:
        return [p for p in self.patterns() if p.repeat_count >= minimum_repeats]

    def session_issue_summary(self) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for pattern in self.patterns():
            g = grouped.setdefault(pattern.issue_code, {
                "issue_code": pattern.issue_code,
                "issue_label": pattern.issue_label,
                "occurrences": 0,
                "corners": set(),
                "total_measured_time_cost_s": 0.0,
                "weighted_confidence_sum": 0.0,
            })
            g["occurrences"] += pattern.observations
            g["corners"].add(pattern.corner_id)
            g["total_measured_time_cost_s"] += pattern.total_measured_time_cost_s
            g["weighted_confidence_sum"] += pattern.mean_confidence * pattern.observations
        out = []
        for g in grouped.values():
            occurrences = max(1, g["occurrences"])
            out.append({
                "issue_code": g["issue_code"],
                "issue_label": g["issue_label"],
                "occurrences": g["occurrences"],
                "corner_ids": sorted(x for x in g["corners"] if x is not None),
                "total_measured_time_cost_s": g["total_measured_time_cost_s"],
                "mean_confidence": g["weighted_confidence_sum"] / occurrences,
            })
        out.sort(key=lambda x: (x["total_measured_time_cost_s"], x["occurrences"]), reverse=True)
        return out

    def report(self) -> dict[str, Any]:
        patterns = self.patterns()
        recurring = [p for p in patterns if p.repeat_count >= 2]
        active_recurring = [p for p in recurring if p.latest_observed]
        active_patterns = [p for p in patterns if p.latest_observed]
        session_focus = active_recurring[0] if active_recurring else (active_patterns[0] if active_patterns else None)
        return {
            "pattern_count": len(patterns),
            "recurring_pattern_count": len(recurring),
            "session_focus": session_focus.to_dict() if session_focus else None,
            "patterns": [p.to_dict() for p in patterns],
            "recurring_patterns": [p.to_dict() for p in recurring],
            "session_issue_summary": self.session_issue_summary(),
            "lap_focus_history": list(self._lap_focuses),
            "trend_rule": "first-vs-latest measured issue time cost; +/-15ms deadband; descriptive only",
        }


def build_session_coaching(comparisons: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build per-lap priority decisions plus multi-lap session memory.

    ``comparisons`` should be ordered chronologically. Each item is modified only
    by returning a separate priority payload; callers decide where to attach it.
    """
    memory = CoachingMemory()
    per_lap: list[dict[str, Any]] = []
    for comp in comparisons:
        if not isinstance(comp, dict):
            continue
        per_lap.append(memory.ingest_lap(comp.get("lap"), comp.get("corner_analyses") or []))
    return {
        "version": "0.9.20.2",
        "per_lap_priority": per_lap,
        "memory": memory.report(),
    }
