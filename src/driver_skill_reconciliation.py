"""V2.0.9 Driver Skill reconciliation.

Presentation/reconciliation layer only. It consumes the existing persisted
Skill Evidence, F1DriverSkillModel, SkillTrendStore and Performance History.
It never creates a second Driver Skill model.
"""
from __future__ import annotations

from typing import Any
import math

from .driver_profiles import DriverProfileStore
from .driver_skill import ALL_F1_SKILLS, DISPLAY_NAMES, F1DriverSkillModel
from .skill_trends import SkillTrendStore
from .track_skill import TrackSkillStore


def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _all_tracks(track: str) -> bool:
    return str(track or "all").strip().lower() in {"", "all", "all_tracks", "all tracks"}


class DriverSkillReconciliation:
    """Expose one canonical Driver Skill result to every UI surface.

    Global values come directly from ``F1DriverSkillModel``. Track-scoped values
    come directly from ``TrackSkillStore``/``SkillTrendStore``. The Hub may add
    presentation diagnostics, but it must not recalculate alternate skill scores.
    """

    def __init__(self, driver_store: DriverProfileStore | None = None) -> None:
        self.driver_store = driver_store or DriverProfileStore()
        self.skill_model = F1DriverSkillModel(self.driver_store)
        self.trends = SkillTrendStore(self.driver_store)
        self.track_skills = TrackSkillStore(self.driver_store)

    def _sessions(self, driver_id: str, track: str = "all") -> list[dict[str, Any]]:
        rows = [x for x in self.skill_model._sessions(driver_id) if isinstance(x, dict)]
        wanted = str(track or "all").strip()
        if not _all_tracks(wanted):
            rows = [x for x in rows if str(x.get("track") or "Unknown") == wanted]
        rows.sort(key=lambda x: (str(x.get("timestamp") or ""), str(x.get("session_key") or "")))
        return rows

    def _canonical_scope(self, driver_id: str, track: str) -> tuple[dict[str, Any], dict[str, Any], int, int]:
        """Return (overall, skills, stored sessions, scoreable snapshots)."""
        if _all_tracks(track):
            current = self.skill_model.recalculate(driver_id)
            overall = dict(current.get("overall") or {})
            skills = {k: dict((current.get("skills") or {}).get(k) or {}) for k in ALL_F1_SKILLS}
            stored = int(current.get("stored_evidence_session_count") or 0)
            scoreable = int(current.get("evidence_session_count") or 0)
            return overall, skills, stored, scoreable

        summary = self.track_skills.summary(driver_id, track)
        overall_value = summary.get("overall")
        overall = {
            "status": "available" if _finite(overall_value) else "n/a",
            "value": float(overall_value) if _finite(overall_value) else None,
            "confidence": None,  # track cards do not publish a separate confidence model
        }
        skills: dict[str, Any] = {}
        for key in ALL_F1_SKILLS:
            row = dict((summary.get("skills") or {}).get(key) or {})
            value = row.get("value")
            skills[key] = {
                "name": DISPLAY_NAMES.get(key, key),
                "status": "available" if _finite(value) else "n/a",
                "value": float(value) if _finite(value) else None,
                "session_count": int(row.get("session_count") or 0),
                "confidence": None,
            }
        return overall, skills, int(summary.get("session_count") or 0), int(summary.get("scoreable_session_count") or 0)

    def _canonical_domains(self, driver_id: str, track: str, skills: dict[str, Any]) -> dict[str, Any]:
        domains: dict[str, Any] = {}
        for key in ALL_F1_SKILLS:
            current_row = skills.get(key) or {}
            current_value = current_row.get("value")
            all_view = self.trends.view(driver_id, key, "all_time", track)
            points = [x for x in (all_view.get("points") or []) if _finite(x.get("value"))]
            last5 = points[-5:]
            five_change = None
            if len(last5) >= 2:
                five_change = round(float(last5[-1]["value"]) - float(last5[0]["value"]), 1)
            domains[key] = {
                "name": DISPLAY_NAMES.get(key, key),
                "status": "available" if _finite(current_value) else "n/a",
                # IMPORTANT: this is the exact canonical Driver Profile/Track value.
                "current": round(float(current_value), 1) if _finite(current_value) else None,
                "personal_best": all_view.get("personal_best"),
                "five_session_change": five_change,
                # Number of actual scoreable points used by the rolling change.
                # The UI must not label a three-point history as a "5-session" trend.
                "trend_window_count": len(last5),
                "scoreable_snapshots": int(all_view.get("all_time_point_count") or 0),
                "authority": "F1DriverSkillModel" if _all_tracks(track) else "TrackSkillStore/SkillTrendStore",
            }
        return domains

    def _recurring_and_solved(self, driver_id: str, track: str, domains: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        recurring: list[dict[str, Any]] = []
        solved: list[dict[str, Any]] = []
        for key in ALL_F1_SKILLS:
            view = self.trends.view(driver_id, key, "all_time", track)
            vals = [float(x["value"]) for x in (view.get("points") or []) if _finite(x.get("value"))]
            recent = vals[-5:]
            current = domains.get(key, {}).get("current")
            if _finite(current) and len(recent) >= 3 and sum(1 for v in recent[-3:] if v < 70.0) >= 3:
                recurring.append({"domain": key, "name": DISPLAY_NAMES.get(key, key), "value": float(current), "samples": 3})
            if len(recent) >= 4:
                prior = sum(recent[-4:-2]) / 2.0
                now = sum(recent[-2:]) / 2.0
                if prior < 70.0 and now >= 75.0 and now - prior >= 6.0:
                    solved.append({"domain": key, "name": DISPLAY_NAMES.get(key, key), "improvement": round(now-prior, 1), "current": round(now, 1)})
        recurring.sort(key=lambda x: (x["value"], x["name"]))
        solved.sort(key=lambda x: (-x["improvement"], x["name"]))
        return (recurring[0] if recurring else None), (solved[0] if solved else None)

    def _evidence_diagnostics(self, sessions: list[dict[str, Any]]) -> dict[str, Any]:
        wet_sessions = 0
        skills_with_measurements: set[str] = set()
        for session in sessions:
            conditions = session.get("conditions") if isinstance(session.get("conditions"), dict) else {}
            wet = str(conditions.get("wet_dry") or "").lower()
            if wet in {"wet", "1", "true"}:
                wet_sessions += 1
            for m in session.get("measurements", []) if isinstance(session, dict) else []:
                if isinstance(m, dict) and str(m.get("skill") or ""):
                    skills_with_measurements.add(str(m.get("skill")))
        return {
            "wet_session_count": wet_sessions,
            "wet_driving": (
                "dedicated_evidence_available" if "wet_driving" in skills_with_measurements else
                "no dedicated wet_driving Skill Evidence producer; remains N/A by design"
            ),
            "racecraft": (
                "dedicated_evidence_available" if "racecraft" in skills_with_measurements else
                "no dedicated racecraft Skill Evidence producer; remains N/A by design"
            ),
            "tyre_management": (
                "dedicated_evidence_available" if "tyre_management" in skills_with_measurements else
                "no dedicated tyre_management Skill Evidence producer; remains N/A by design"
            ),
        }

    def _measured_time_recovered(self, driver_id: str, track: str) -> dict[str, Any]:
        wanted = str(track or "all").strip()
        if _all_tracks(wanted):
            return {"value_s": None, "status": "track_required", "method": "N/A across incompatible circuits"}
        try:
            profile = self.driver_store.load_profile(driver_id) or {}
            compat = profile.get("compatibility") if isinstance(profile.get("compatibility"), dict) else {}
            hid = compat.get("performance_history_profile_id")
            if hid is None:
                return {"value_s": None, "status": "no_history_binding"}
            from .performance_history import PerformanceHistoryStore
            detail = PerformanceHistoryStore().track_detail(wanted, hid)
            rows = [x for x in detail.get("sessions", []) if isinstance(x, dict)]
            gains = [float(x["potential_gain_s"]) for x in rows if _finite(x.get("potential_gain_s")) and float(x["potential_gain_s"]) >= 0.0]
            gains = gains[-5:]
            if len(gains) < 2:
                return {"value_s": None, "status": "insufficient_history", "sample_count": len(gains)}
            raw_change = gains[0] - gains[-1]
            recovered = max(0.0, raw_change)
            if raw_change > 0.0005:
                direction = "improved"
            elif raw_change < -0.0005:
                direction = "worsened"
            else:
                direction = "unchanged"
            return {
                "value_s": round(recovered, 3), "status": "available", "sample_count": len(gains),
                "from_available_gain_s": round(gains[0], 3), "to_available_gain_s": round(gains[-1], 3),
                "raw_change_s": round(raw_change, 3), "direction": direction,
                "method": "change in measured available gain across the latest comparable track sessions; recovered time never goes below zero",
            }
        except Exception as exc:
            return {"value_s": None, "status": "unavailable", "reason": str(exc)}

    def build(self, driver_id: str, track: str = "all") -> dict[str, Any]:
        try:
            from .skill_evidence import SkillEvidenceStore
            SkillEvidenceStore(self.driver_store).reconcile_with_performance_history(driver_id=driver_id)
        except Exception:
            pass

        track = str(track or "all")
        sessions = self._sessions(driver_id, track)
        overall, skills, stored_sessions, scoreable_snapshots = self._canonical_scope(driver_id, track)
        domains = self._canonical_domains(driver_id, track, skills)
        recurring, solved = self._recurring_and_solved(driver_id, track, domains)
        return {
            "available": bool(self._sessions(driver_id, "all")),
            "version": "2.0.9-canonical-reconciled",
            "driver_id": str(driver_id),
            "track": track,
            "scope": "global" if _all_tracks(track) else "track",
            "source": "ONE canonical Driver Skill: F1DriverSkillModel globally; TrackSkillStore/SkillTrendStore for circuit scope",
            "persistent_history": "LIVE-only; replay read-only",
            "stored_evidence_session_count": stored_sessions,
            "scoreable_snapshot_count": scoreable_snapshots,
            "overall": overall,
            "domains": domains,
            "recurring_weakness": recurring,
            "recently_solved_issue": solved,
            "measured_time_recovered": self._measured_time_recovered(driver_id, track),
            "evidence_diagnostics": self._evidence_diagnostics(sessions),
        }
