"""V2.5.0 session-completion Skill Trend history for the F1 26 game profile.

Trend snapshots are reconstructed deterministically from persisted Skill Evidence
and therefore remain idempotent. One snapshot represents the career skill state
*after* one logical scored session; no telemetry-frame or corner-level trend rows
are stored here.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
from typing import Any

from .driver_profiles import DriverProfileStore
from .driver_skill import (
    ALL_F1_SKILLS, CORE_SKILLS, DISPLAY_NAMES, OVERALL_WEIGHTS,
    F1DriverSkillModel, _weighted_mean,
)

TREND_VERSION = "2.5.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: Any) -> datetime | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


class SkillTrendStore:
    def __init__(self, driver_store: DriverProfileStore | None = None) -> None:
        self.driver_store = driver_store or DriverProfileStore()
        self.skill_model = F1DriverSkillModel(self.driver_store)

    def root(self, driver_id: str) -> Path:
        return self.driver_store.root / str(driver_id) / "games" / "f1_26"

    def output_path(self, driver_id: str) -> Path:
        return self.root(driver_id) / "skill_trends.json"

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return default

    @staticmethod
    def _write_json_atomic(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)

    def _evidence_sessions(self, driver_id: str) -> list[dict[str, Any]]:
        sessions = self.skill_model._sessions(driver_id)
        sessions = [x for x in sessions if isinstance(x, dict)]
        sessions.sort(key=lambda x: (_parse_time(x.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc), str(x.get("session_key") or "")))
        return sessions

    def _snapshot_values(self, sessions: list[dict[str, Any]]) -> dict[str, Any]:
        per_skill: dict[str, list[tuple[float, float]]] = {k: [] for k in ALL_F1_SKILLS}
        scored_sessions = 0
        for session in sessions:
            grouped: dict[str, list[tuple[float, float]]] = {}
            scored = False
            for m in session.get("measurements", []) if isinstance(session, dict) else []:
                if not isinstance(m, dict):
                    continue
                skill = str(m.get("skill") or "")
                if skill not in per_skill:
                    continue
                score = self.skill_model._measurement_score(m)
                if score is None:
                    continue
                try:
                    confidence = max(0.0, min(1.0, float(m.get("confidence") or 0.0)))
                except (TypeError, ValueError):
                    confidence = 0.0
                if confidence <= 0.0:
                    continue
                samples = max(1, int(m.get("sample_count") or 1))
                weight = confidence * min(4.0, math.sqrt(samples))
                grouped.setdefault(skill, []).append((float(score), weight))
                scored = True
            if scored:
                scored_sessions += 1
            for skill, rows in grouped.items():
                value = _weighted_mean(rows)
                if value is not None:
                    session_weight = max((w for _, w in rows), default=0.1)
                    per_skill[skill].append((value, session_weight))

        skills: dict[str, float | None] = {}
        for skill in ALL_F1_SKILLS:
            value = _weighted_mean(per_skill[skill])
            skills[skill] = round(float(value), 1) if value is not None else None

        available = [k for k in CORE_SKILLS if skills.get(k) is not None]
        overall = None
        if scored_sessions >= 2 and len(available) >= 4:
            parts = [(skills[k], OVERALL_WEIGHTS[k]) for k in available if skills[k] is not None]
            overall = _weighted_mean(parts)
        return {
            "overall": round(float(overall), 1) if overall is not None else None,
            "skills": skills,
            "scored_session_count": scored_sessions,
        }

    def rebuild(self, driver_id: str) -> dict[str, Any]:
        sessions = self._evidence_sessions(driver_id)
        snapshots: list[dict[str, Any]] = []
        prefix: list[dict[str, Any]] = []
        for session in sessions:
            prefix.append(session)
            values = self._snapshot_values(prefix)
            snapshots.append({
                "session_key": str(session.get("session_key") or f"session_{len(prefix)}"),
                "timestamp": str(session.get("timestamp") or _utc_now()),
                "track": str(session.get("track") or "Unknown"),
                "session_type": str(session.get("session_type") or "Unknown"),
                "overall": values["overall"],
                "skills": values["skills"],
                "scored_session_count": values["scored_session_count"],
            })
        payload = {
            "format": "RACE_ENGINEER_F1_SKILL_TRENDS",
            "version": TREND_VERSION,
            "driver_id": str(driver_id),
            "game_id": "f1_26",
            "discipline": "formula",
            "updated_at": _utc_now(),
            "snapshot_count": len(snapshots),
            "source_session_keys": [x["session_key"] for x in snapshots],
            "snapshots": snapshots,
            "rules": {
                "cadence": "one cumulative snapshot per persisted logical session",
                "source": "validated Skill Evidence only",
                "missing": "N/A remains absent; no interpolation or synthetic scores",
            },
        }
        self._write_json_atomic(self.output_path(driver_id), payload)
        return payload

    def ensure(self, driver_id: str) -> dict[str, Any]:
        sessions = self._evidence_sessions(driver_id)
        keys = [str(x.get("session_key") or f"session_{i+1}") for i, x in enumerate(sessions)]
        payload = self._read_json(self.output_path(driver_id), {})
        if not isinstance(payload, dict) or payload.get("version") != TREND_VERSION or payload.get("source_session_keys") != keys:
            return self.rebuild(driver_id)
        return payload

    def available_tracks(self, driver_id: str) -> list[str]:
        """Return Performance-History-authoritative tracks for this Driver.

        Skill Evidence supplies the scores, but Performance History owns which
        live sessions/tracks actually exist.  This keeps Driver Profile/Trends in
        lock-step with Performance Hub and prevents stale derived ``Unknown``
        cards from surviving after the Hub has resolved or removed that session.
        """
        try:
            profile = self.driver_store.load_profile(driver_id) or {}
            compat = profile.get("compatibility") if isinstance(profile.get("compatibility"), dict) else {}
            history_profile_id = compat.get("performance_history_profile_id")
            if history_profile_id is not None:
                from .performance_history import PerformanceHistoryStore
                overview = PerformanceHistoryStore().overview(history_profile_id)
                if isinstance(overview, dict) and overview.get("available"):
                    tracks = {
                        str(row.get("track") or "Unknown").strip() or "Unknown"
                        for row in (overview.get("tracks") or []) if isinstance(row, dict)
                    }
                    return sorted(tracks, key=lambda x: x.casefold())
        except Exception:
            pass
        tracks = {str(x.get("track") or "Unknown").strip() or "Unknown" for x in self._evidence_sessions(driver_id)}
        return sorted(tracks, key=lambda x: x.casefold())

    def _snapshots_for_track(self, driver_id: str, track: str) -> list[dict[str, Any]]:
        wanted = str(track or "all").strip()
        if not wanted or wanted.lower() in {"all", "all_tracks", "all tracks"}:
            return list(self.ensure(driver_id).get("snapshots") or [])
        sessions = [x for x in self._evidence_sessions(driver_id) if str(x.get("track") or "Unknown") == wanted]
        snapshots: list[dict[str, Any]] = []
        prefix: list[dict[str, Any]] = []
        for session in sessions:
            prefix.append(session)
            values = self._snapshot_values(prefix)
            snapshots.append({
                "session_key": str(session.get("session_key") or f"session_{len(prefix)}"),
                "timestamp": str(session.get("timestamp") or _utc_now()),
                "track": str(session.get("track") or "Unknown"),
                "session_type": str(session.get("session_type") or "Unknown"),
                "overall": values["overall"],
                "skills": values["skills"],
                "scored_session_count": values["scored_session_count"],
            })
        return snapshots

    def view(self, driver_id: str, skill: str = "overall", period: str = "10_sessions", track: str = "all") -> dict[str, Any]:
        snapshots = self._snapshots_for_track(driver_id, track)
        key = str(skill or "overall")
        if key != "overall" and key not in ALL_F1_SKILLS:
            key = "overall"

        rows: list[dict[str, Any]] = []
        for snap in snapshots:
            value = snap.get("overall") if key == "overall" else (snap.get("skills") or {}).get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                rows.append({**snap, "value": float(value)})

        period = str(period or "10_sessions")
        if period == "10_sessions":
            shown = rows[-10:]
        elif period == "30_sessions":
            shown = rows[-30:]
        elif period == "3_months":
            latest = max((_parse_time(x.get("timestamp")) for x in rows), default=None)
            cutoff = latest - timedelta(days=92) if latest else None
            shown = [x for x in rows if cutoff is None or (_parse_time(x.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff]
        else:
            shown = rows

        current = shown[-1]["value"] if shown else None
        change = None
        if len(shown) >= 2:
            change = round(float(shown[-1]["value"]) - float(shown[0]["value"]), 1)
        personal_best = max((float(x["value"]) for x in rows), default=None)
        return {
            "skill": key,
            "name": "Overall" if key == "overall" else DISPLAY_NAMES.get(key, key),
            "period": period,
            "track": str(track or "all"),
            "points": shown,
            "point_count": len(shown),
            "current": round(current, 1) if current is not None else None,
            "change": change,
            "personal_best": round(personal_best, 1) if personal_best is not None else None,
            "all_time_point_count": len(rows),
            "snapshot_count": len(snapshots),
        }
