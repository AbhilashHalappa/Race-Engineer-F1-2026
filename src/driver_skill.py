"""V2.4.1 F1 Driver Skill confidence/sample system.

Career presentation scores are derived only from persisted V2 Skill Evidence.
This module never re-detects telemetry events and never invents a value when a
skill lacks a supported, trusted measurement. V2.4.1 adds evidence-depth
confidence labels without changing the V2.4.0 skill scoring formulas.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

from .driver_profiles import DriverProfileStore

SKILL_MODEL_VERSION = "2.4.1"
CORE_SKILLS = (
    "pace", "consistency", "braking", "corner_entry",
    "apex_minimum_speed", "traction_exit", "car_control",
)
ALL_F1_SKILLS = CORE_SKILLS + ("racecraft", "tyre_management", "wet_driving")
DISPLAY_NAMES = {
    "pace": "Pace",
    "consistency": "Consistency",
    "braking": "Braking",
    "corner_entry": "Corner Entry",
    "apex_minimum_speed": "Apex / Minimum Speed",
    "traction_exit": "Traction / Exit",
    "car_control": "Car Control",
    "racecraft": "Racecraft",
    "tyre_management": "Tyre Management",
    "wet_driving": "Wet Driving",
}
OVERALL_WEIGHTS = {
    "pace": 0.20,
    "consistency": 0.15,
    "braking": 0.15,
    "corner_entry": 0.125,
    "apex_minimum_speed": 0.125,
    "traction_exit": 0.15,
    "car_control": 0.10,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _clamp100(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _weighted_mean(rows: list[tuple[float, float]]) -> float | None:
    usable = [(float(v), max(0.0, float(w))) for v, w in rows if _finite(v) and _finite(w) and float(w) > 0.0]
    if not usable:
        return None
    total = sum(w for _, w in usable)
    return sum(v * w for v, w in usable) / total if total > 0.0 else None


def _pace_score(gap_percent: float) -> float:
    """0..100 pace score from percentage gap to a valid reference.

    Equal/faster than reference retains 100. A +8% gap reaches zero. The rule is
    explicit and circuit-independent, unlike raw-second thresholds.
    """
    gap = max(0.0, float(gap_percent))
    return round(_clamp100(100.0 * (1.0 - min(1.0, gap / 8.0))), 2)


def _consistency_score(cv_percent: float) -> float:
    """0..100 score from lap-time coefficient of variation.

    <=0.25% is treated as excellent repeatability (100). >=3.0% reaches zero.
    """
    cv = max(0.0, float(cv_percent))
    if cv <= 0.25:
        return 100.0
    if cv >= 3.0:
        return 0.0
    return round(100.0 * (1.0 - (cv - 0.25) / (3.0 - 0.25)), 2)


def _confidence_label(score: float | None) -> str:
    if score is None:
        return "N/A"
    if float(score) >= 0.75:
        return "HIGH"
    if float(score) >= 0.45:
        return "MEDIUM"
    return "LOW"


def _confidence_score(*, sessions: int, tracks: int, samples: int, evidence_confidence: float) -> float:
    """Evidence-depth confidence, deliberately separate from driving skill.

    Session/track breadth dominates so one very dense session cannot claim HIGH
    career confidence. Sample depth and source evidence confidence provide the
    remaining support. This is a trust indicator only; it never changes the
    underlying V2.4.0 skill value.
    """
    session_depth = min(1.0, max(0, int(sessions)) / 8.0)
    track_depth = min(1.0, max(0, int(tracks)) / 4.0)
    sample_depth = min(1.0, math.sqrt(max(0, int(samples))) / 12.0)
    source_depth = max(0.0, min(1.0, float(evidence_confidence or 0.0)))
    return round(0.45 * session_depth + 0.25 * track_depth + 0.15 * sample_depth + 0.15 * source_depth, 4)


class F1DriverSkillModel:
    def __init__(self, driver_store: DriverProfileStore | None = None) -> None:
        self.driver_store = driver_store or DriverProfileStore()

    def evidence_root(self, driver_id: str) -> Path:
        return self.driver_store.root / str(driver_id) / "games" / "f1_26" / "skill_evidence"

    def output_path(self, driver_id: str) -> Path:
        return self.driver_store.root / str(driver_id) / "games" / "f1_26" / "driver_skill.json"

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

    def _sessions(self, driver_id: str) -> list[dict[str, Any]]:
        root = self.evidence_root(driver_id)
        index = self._read_json(root / "index.json", {})
        rows = index.get("sessions", []) if isinstance(index, dict) else []
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = self._read_json(root / str(row.get("path") or ""), {})
            if isinstance(payload, dict):
                out.append(payload)
        return out

    @staticmethod
    def _measurement_score(m: dict[str, Any]) -> float | None:
        metric = str(m.get("metric") or "")
        value = m.get("value")
        if not _finite(value):
            return None
        if metric in {
            "braking_execution", "turn_in_execution", "corner_speed_execution",
            "throttle_application", "exit_speed_execution", "steering_control",
        }:
            return _clamp100(float(value))
        if metric == "best_lap_gap_percent_to_reference":
            return _pace_score(float(value))
        if metric == "lap_time_coefficient_of_variation":
            return _consistency_score(float(value))
        return None

    def recalculate(self, driver_id: str) -> dict[str, Any]:
        sessions = self._sessions(driver_id)
        per_skill_sessions: dict[str, list[tuple[float, float]]] = {k: [] for k in ALL_F1_SKILLS}
        per_skill_samples: dict[str, int] = {k: 0 for k in ALL_F1_SKILLS}
        per_skill_measurements: dict[str, int] = {k: 0 for k in ALL_F1_SKILLS}
        per_skill_tracks: dict[str, set[str]] = {k: set() for k in ALL_F1_SKILLS}
        per_skill_source_conf: dict[str, list[tuple[float, int]]] = {k: [] for k in ALL_F1_SKILLS}

        for session in sessions:
            grouped: dict[str, list[tuple[float, float]]] = {}
            session_track = str(session.get("track") or "Unknown")
            for m in session.get("measurements", []) if isinstance(session, dict) else []:
                if not isinstance(m, dict):
                    continue
                skill = str(m.get("skill") or "")
                if skill not in per_skill_sessions:
                    continue
                score = self._measurement_score(m)
                if score is None:
                    continue
                confidence = max(0.0, min(1.0, float(m.get("confidence") or 0.0)))
                if confidence <= 0.0:
                    continue
                samples = max(1, int(m.get("sample_count") or 1))
                # Sample count affects trust sub-linearly; one high-frequency
                # session cannot dominate the driver's entire career score.
                weight = confidence * min(4.0, math.sqrt(samples))
                grouped.setdefault(skill, []).append((score, weight))
                per_skill_samples[skill] += int(m.get("sample_count") or 0)
                per_skill_measurements[skill] += 1
                if session_track and session_track.lower() != "unknown":
                    per_skill_tracks[skill].add(session_track)
                per_skill_source_conf[skill].append((confidence, samples))
            for skill, rows in grouped.items():
                session_score = _weighted_mean(rows)
                if session_score is not None:
                    session_conf = max((w for _, w in rows), default=0.1)
                    per_skill_sessions[skill].append((session_score, session_conf))

        skills: dict[str, dict[str, Any]] = {}
        for skill in ALL_F1_SKILLS:
            rows = per_skill_sessions[skill]
            value = _weighted_mean(rows)
            source_rows = per_skill_source_conf[skill]
            source_conf = _weighted_mean(source_rows) if source_rows else None
            track_count = len(per_skill_tracks[skill])
            conf_score = None
            if value is not None:
                conf_score = _confidence_score(
                    sessions=len(rows), tracks=track_count, samples=per_skill_samples[skill],
                    evidence_confidence=float(source_conf or 0.0),
                )
            skills[skill] = {
                "name": DISPLAY_NAMES[skill],
                "status": "available" if value is not None else "n/a",
                "value": round(float(value), 1) if value is not None else None,
                "session_count": len(rows),
                "track_count": track_count,
                "measurement_count": per_skill_measurements[skill],
                "sample_count": per_skill_samples[skill],
                "evidence_confidence": round(float(source_conf), 4) if source_conf is not None else None,
                "confidence_score": conf_score,
                "confidence": _confidence_label(conf_score),
            }

        available_core = [k for k in CORE_SKILLS if skills[k]["status"] == "available"]
        scored_session_keys = set()
        for session in sessions:
            if not isinstance(session, dict):
                continue
            for m in session.get("measurements", []):
                if not isinstance(m, dict):
                    continue
                if self._measurement_score(m) is not None and float(m.get("confidence") or 0.0) > 0.0:
                    scored_session_keys.add(str(session.get("session_key") or id(session)))
                    break
        scored_session_count = len(scored_session_keys)
        overall = None
        # Require evidence across a broad cross-section and more than one logical
        # scored session before publishing a Formula Driver Skill number.
        if scored_session_count >= 2 and len(available_core) >= 4:
            parts = [(skills[k]["value"], OVERALL_WEIGHTS[k]) for k in available_core if skills[k]["value"] is not None]
            overall = _weighted_mean(parts)

        overall_conf_score = None
        if overall is not None:
            conf_parts = [(skills[k].get("confidence_score"), OVERALL_WEIGHTS[k]) for k in available_core if skills[k].get("confidence_score") is not None]
            overall_conf_score = _weighted_mean(conf_parts)
            if overall_conf_score is not None:
                overall_conf_score = round(float(overall_conf_score), 4)

        payload = {
            "format": "RACE_ENGINEER_F1_DRIVER_SKILL",
            "version": SKILL_MODEL_VERSION,
            "driver_id": str(driver_id),
            "game_id": "f1_26",
            "discipline": "formula",
            "updated_at": _utc_now(),
            "evidence_session_count": scored_session_count,
            "stored_evidence_session_count": len(sessions),
            "overall": {
                "status": "available" if overall is not None else "n/a",
                "value": round(float(overall), 1) if overall is not None else None,
                "available_core_skills": len(available_core),
                "required_core_skills": 4,
                "minimum_sessions": 2,
                "confidence_score": overall_conf_score,
                "confidence": _confidence_label(overall_conf_score),
            },
            "skills": skills,
            "confidence_labels": {
                "low": "limited breadth/depth; treat score as provisional",
                "medium": "moderate multi-session/track evidence",
                "high": "broad repeated evidence across sessions and tracks",
            },
            "trend_history": "deferred_to_v2.5.0",
            "rules": {
                "pace": "100 at <=0% reference gap; linear to 0 at +8%",
                "consistency": "100 at <=0.25% CV; linear to 0 at >=3.0% CV",
                "technique": "authoritative session technique score 0..100",
                "overall": "weighted available core skills; N/A unless >=4 core skills across >=2 evidence sessions",
                "confidence": "trust label from session breadth, track breadth, sample depth and source evidence confidence; does not alter skill score",
            },
        }
        self._write_json_atomic(self.output_path(driver_id), payload)

        gp = self.driver_store.load_game_profile(driver_id, "f1_26") or {}
        gp["driver_skill"] = {
            "model_version": SKILL_MODEL_VERSION,
            "status": payload["overall"]["status"],
            "value": payload["overall"]["value"],
            "updated_at": payload["updated_at"],
            "evidence_session_count": len(sessions),
            "confidence": payload["overall"].get("confidence"),
            "confidence_score": payload["overall"].get("confidence_score"),
        }
        self.driver_store.save_game_profile(driver_id, "f1_26", gp)
        return payload

    def current(self, driver_id: str) -> dict[str, Any]:
        payload = self._read_json(self.output_path(driver_id), {})
        if not isinstance(payload, dict) or payload.get("version") != SKILL_MODEL_VERSION:
            return self.recalculate(driver_id)
        return payload
