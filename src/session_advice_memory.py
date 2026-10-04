"""Session-scoped deterministic coaching advice outcome memory.

V1.3.1.0 adds a separate memory layer on top of the existing CoachingMemory.
CoachingMemory answers "what issues repeat?".  AdviceOutcomeMemory answers
"what did we coach, did the next comparable attempts improve, and can we retire
that advice?".

No prediction is performed.  Outcomes are based only on measured, loss-guarded
CornerAnalysis issue candidates from comparable completed laps.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Iterable


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _corner_id(row: dict[str, Any]) -> int | None:
    cid = row.get("reference_corner_id") if isinstance(row.get("reference_corner_id"), int) else row.get("corner_id")
    return int(cid) if isinstance(cid, int) else None


def _issue_measurement(row: dict[str, Any] | None, code: str) -> tuple[float | None, float | None, float | None]:
    """Return (cost, magnitude, confidence) for the requested issue on a corner."""
    if not isinstance(row, dict):
        return None, None, None
    if row.get("diagnosis") == code and _num(row.get("estimated_time_cost_s")):
        return (
            float(row["estimated_time_cost_s"]),
            float(row["diagnosis_magnitude"]) if _num(row.get("diagnosis_magnitude")) else None,
            float(row["diagnosis_confidence"]) if _num(row.get("diagnosis_confidence")) else None,
        )
    for cand in row.get("issue_candidates") or ():
        if not isinstance(cand, dict) or str(cand.get("code") or "") != code:
            continue
        if not cand.get("primary_eligible", True) or not _num(cand.get("estimated_time_cost_s")):
            continue
        return (
            float(cand["estimated_time_cost_s"]),
            float(cand["magnitude"]) if _num(cand.get("magnitude")) else None,
            float(cand["confidence"]) if _num(cand.get("confidence")) else None,
        )
    return None, None, None


@dataclass(slots=True)
class AdviceAttempt:
    lap: int | None
    measured: bool
    cost_s: float | None
    magnitude: float | None
    confidence: float | None
    outcome: str
    delta_cost_s: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AdviceRecord:
    corner_id: int
    issue_code: str
    issue_label: str
    phase: str | None
    first_advice_lap: int | None
    last_advice_lap: int | None
    baseline_cost_s: float
    baseline_magnitude: float | None
    latest_cost_s: float | None
    latest_magnitude: float | None
    latest_confidence: float | None
    status: str = "active"
    attempts: int = 0
    measured_opportunities: int = 0
    consecutive_clear_attempts: int = 0
    best_recovered_s: float = 0.0
    latest_outcome: str = "new"
    solved_lap: int | None = None
    history: list[AdviceAttempt] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["history"] = [x.to_dict() if isinstance(x, AdviceAttempt) else x for x in self.history]
        return out


class AdviceOutcomeMemory:
    """Track whether previously coached issues improve on later measured attempts.

    Conservative retirement rules:
    - an issue is solved when its measured cost falls below ``solved_cost_s``;
    - or when the same corner is measured on two consecutive opportunities and
      the issue no longer survives the deterministic loss/confidence guards.

    A one-off disappearance is labelled ``improved`` but does not immediately
    erase the advice.  This avoids retiring advice because of a noisy comparison.
    """

    def __init__(self, *, improvement_deadband_s: float = 0.015, solved_cost_s: float = 0.020, clear_attempts_to_solve: int = 2) -> None:
        self.improvement_deadband_s = float(improvement_deadband_s)
        self.solved_cost_s = float(solved_cost_s)
        self.clear_attempts_to_solve = max(1, int(clear_attempts_to_solve))
        self._records: dict[tuple[int, str], AdviceRecord] = {}
        self._focus_key: tuple[int, str] | None = None
        self._last_lap: int | None = None
        self._events: list[dict[str, Any]] = []

    def reset(self) -> None:
        self._records.clear(); self._focus_key = None; self._last_lap = None; self._events.clear()

    @staticmethod
    def _rows_by_corner(analyses: Iterable[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        out: dict[int, dict[str, Any]] = {}
        for row in analyses:
            if not isinstance(row, dict):
                continue
            cid = _corner_id(row)
            if cid is not None:
                out[cid] = row
        return out

    def _record_focus(self, lap: int | None, focus: dict[str, Any] | None) -> None:
        if not isinstance(focus, dict):
            return
        cid = _corner_id(focus)
        code = str(focus.get("issue_code") or focus.get("diagnosis") or "")
        cost = focus.get("estimated_time_cost_s")
        if cid is None or not code or not _num(cost) or float(cost) <= 0:
            return
        key = (cid, code)
        rec = self._records.get(key)
        label = str(focus.get("issue_label") or focus.get("diagnosis_label") or code)
        magnitude = focus.get("magnitude") if _num(focus.get("magnitude")) else focus.get("diagnosis_magnitude")
        confidence = focus.get("confidence") if _num(focus.get("confidence")) else focus.get("diagnosis_confidence")
        if rec is None:
            rec = AdviceRecord(
                corner_id=cid, issue_code=code, issue_label=label, phase=focus.get("phase") or focus.get("dominant_phase"),
                first_advice_lap=lap, last_advice_lap=lap,
                baseline_cost_s=float(cost), baseline_magnitude=float(magnitude) if _num(magnitude) else None,
                latest_cost_s=float(cost), latest_magnitude=float(magnitude) if _num(magnitude) else None,
                latest_confidence=float(confidence) if _num(confidence) else None,
            )
            self._records[key] = rec
            self._events.append({"lap": lap, "corner_id": cid, "issue_code": code, "event": "advice_created", "cost_s": float(cost)})
        else:
            rec.last_advice_lap = lap
            if rec.status == "solved":
                # A solved issue becoming dominant again is a deterministic regression.
                rec.status = "active"; rec.solved_lap = None; rec.consecutive_clear_attempts = 0
                rec.baseline_cost_s = float(cost); rec.baseline_magnitude = float(magnitude) if _num(magnitude) else rec.baseline_magnitude
                rec.latest_outcome = "regressed"
                self._events.append({"lap": lap, "corner_id": cid, "issue_code": code, "event": "issue_reopened", "cost_s": float(cost)})
        self._focus_key = key

    def observe_lap(self, lap: int | None, analyses: Iterable[dict[str, Any]], selected_focus: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = self._rows_by_corner(analyses)
        # First evaluate existing advice against this newly measured lap. Do not
        # compare a record against the same lap on which it was first created.
        for key, rec in list(self._records.items()):
            if rec.first_advice_lap == lap and rec.attempts == 0:
                continue
            corner = rows.get(rec.corner_id)
            if corner is None:
                continue
            rec.measured_opportunities += 1; rec.attempts += 1
            cost, magnitude, confidence = _issue_measurement(corner, rec.issue_code)
            previous = rec.latest_cost_s if _num(rec.latest_cost_s) else rec.baseline_cost_s
            if _num(cost):
                rec.consecutive_clear_attempts = 0
                delta = float(cost) - float(previous) if _num(previous) else None
                recovered = rec.baseline_cost_s - float(cost)
                rec.best_recovered_s = max(rec.best_recovered_s, recovered)
                rec.latest_cost_s = float(cost); rec.latest_magnitude = magnitude; rec.latest_confidence = confidence
                if float(cost) <= self.solved_cost_s:
                    outcome = "solved"
                    rec.status = "solved"; rec.solved_lap = lap
                elif _num(delta) and float(delta) <= -self.improvement_deadband_s:
                    outcome = "improved"
                    rec.status = "active"
                elif _num(delta) and float(delta) >= self.improvement_deadband_s:
                    outcome = "regressed"
                    rec.status = "active"
                else:
                    outcome = "stable"
                    rec.status = "active"
            else:
                rec.consecutive_clear_attempts += 1
                delta = -float(previous) if _num(previous) else None
                rec.latest_cost_s = 0.0; rec.latest_magnitude = None; rec.latest_confidence = None
                rec.best_recovered_s = max(rec.best_recovered_s, rec.baseline_cost_s)
                if rec.consecutive_clear_attempts >= self.clear_attempts_to_solve:
                    outcome = "solved"; rec.status = "solved"; rec.solved_lap = lap
                else:
                    outcome = "improved"; rec.status = "active"
            rec.latest_outcome = outcome
            rec.history.append(AdviceAttempt(lap, True, rec.latest_cost_s, rec.latest_magnitude, rec.latest_confidence, outcome, delta))
            self._events.append({"lap": lap, "corner_id": rec.corner_id, "issue_code": rec.issue_code, "event": outcome, "cost_s": rec.latest_cost_s, "delta_cost_s": delta})

        self._record_focus(lap, selected_focus)
        self._last_lap = lap if isinstance(lap, int) else self._last_lap
        # If the current focus was solved on this lap, allow the deterministic
        # priority engine's new selected focus to take over; otherwise retain the
        # unresolved focus to avoid bouncing between similar-sized issues.
        if self._focus_key is not None:
            current = self._records.get(self._focus_key)
            if current is not None and current.status == "solved":
                candidate = self._best_active_key()
                self._focus_key = candidate
        return self.summary()

    def _best_active_key(self) -> tuple[int, str] | None:
        active = [(k, r) for k, r in self._records.items() if r.status == "active"]
        if not active:
            return None
        active.sort(key=lambda kv: ((kv[1].latest_cost_s or 0.0), kv[1].baseline_cost_s, -kv[1].corner_id), reverse=True)
        return active[0][0]

    def current_focus(self) -> dict[str, Any] | None:
        key = self._focus_key
        rec = self._records.get(key) if key is not None else None
        if rec is None or rec.status != "active":
            key = self._best_active_key(); self._focus_key = key
            rec = self._records.get(key) if key is not None else None
        return rec.to_dict() if rec is not None else None

    def corner_status(self, corner_id: int) -> dict[str, Any] | None:
        rows = [r for r in self._records.values() if r.corner_id == int(corner_id)]
        if not rows:
            return None
        rows.sort(key=lambda r: (r.status == "active", r.last_advice_lap or -1, r.baseline_cost_s), reverse=True)
        return rows[0].to_dict()

    def active_records(self) -> list[dict[str, Any]]:
        rows = [r.to_dict() for r in self._records.values() if r.status == "active"]
        rows.sort(key=lambda r: (float(r.get("latest_cost_s") or 0.0), float(r.get("baseline_cost_s") or 0.0)), reverse=True)
        return rows

    def solved_records(self) -> list[dict[str, Any]]:
        rows = [r.to_dict() for r in self._records.values() if r.status == "solved"]
        rows.sort(key=lambda r: (r.get("solved_lap") or -1, r.get("corner_id") or -1), reverse=True)
        return rows

    def summary(self) -> dict[str, Any]:
        focus = self.current_focus()
        return {
            "version": "1.3.1.0",
            "last_lap": self._last_lap,
            "active_count": sum(1 for r in self._records.values() if r.status == "active"),
            "solved_count": sum(1 for r in self._records.values() if r.status == "solved"),
            "current_focus": focus,
            "active": self.active_records(),
            "solved": self.solved_records(),
            "events": list(self._events[-100:]),
            "rules": {
                "improvement_deadband_s": self.improvement_deadband_s,
                "solved_cost_s": self.solved_cost_s,
                "clear_attempts_to_solve": self.clear_attempts_to_solve,
                "method": "same-corner same-issue measured cost across eligible completed laps; no prediction",
            },
        }
