"""V2.3.0 session-level Skill Evidence Engine.

This module sits between measured session telemetry/review and the future career
skill model.  It deliberately does *not* calculate a career driver rating.
Evidence is persisted once per logical live session and is idempotently updated
if a later authoritative/final snapshot contains more complete measurements.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any

from .driver_profiles import DriverProfileStore
from .performance_review import build_performance_review

EVIDENCE_VERSION = "2.4.0"


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _slug(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = "unknown"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in raw)
    return safe[:80] or "unknown"


class SkillEvidenceStore:
    """Persistent session-evidence store owned by one Driver/Game Profile."""

    def __init__(self, driver_store: DriverProfileStore | None = None, performance_history_store: Any | None = None) -> None:
        self.driver_store = driver_store or DriverProfileStore()
        self.performance_history_store = performance_history_store

    def root(self, driver_id: str, game_id: str = "f1_26") -> Path:
        return self.driver_store.root / str(driver_id) / "games" / str(game_id) / "skill_evidence"

    def index_path(self, driver_id: str, game_id: str = "f1_26") -> Path:
        return self.root(driver_id, game_id) / "index.json"

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

    @staticmethod
    def _session_identity(summary: dict[str, Any], coach: dict[str, Any]) -> tuple[str, str | None]:
        ctx = coach.get("event_context") if isinstance(coach.get("event_context"), dict) else {}
        uid = summary.get("session_uid") if summary.get("session_uid") is not None else ctx.get("session_uid")
        history_id = summary.get("performance_history_session_id")
        track = summary.get("track") or ctx.get("track_name") or ctx.get("track") or ctx.get("track_id") or "unknown"
        session_type = summary.get("session_type") or ctx.get("session_type") or ctx.get("profile") or "unknown"
        # V2.9.1.3.5.9: Performance History row identity is authoritative when
        # available. Track/session labels can be provisional during an app restart,
        # so they must not create a second Skill Evidence session for the same
        # persisted Performance History session.
        if history_id is not None:
            identity = f"history-{history_id}"
            base = identity
        else:
            identity = uid if uid is not None else (coach.get('created_utc') or summary.get('created_utc') or '')
            base = f"{identity}|{track}|{session_type}"
        digest = hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return f"{_slug(identity if identity else 'session')}_{digest}", (str(uid) if uid is not None else None)

    @staticmethod
    def _conditions(coach: dict[str, Any]) -> dict[str, Any]:
        ctx = coach.get("event_context") if isinstance(coach.get("event_context"), dict) else {}
        return {
            "profile": ctx.get("profile") or "unknown",
            "weather": ctx.get("weather") if "weather" in ctx else "unknown",
            "wet_dry": ctx.get("wet_dry") if "wet_dry" in ctx else "unknown",
            "equal_car_performance": ctx.get("equal_car_performance"),
            "network_game": ctx.get("network_game"),
        }

    @staticmethod
    def _reference_quality(review: dict[str, Any], coach: dict[str, Any]) -> str:
        ref = review.get("reference") if isinstance(review.get("reference"), dict) else {}
        if _finite(ref.get("lap_time_s")):
            # Keep this deliberately descriptive in V2.3.0. Reference quality
            # weighting/calibration belongs to the later skill model.
            return "reference_available"
        external = coach.get("external_reference_meta") if isinstance(coach.get("external_reference_meta"), dict) else {}
        quality = external.get("reference_quality")
        if isinstance(quality, dict):
            if quality.get("valid") is True:
                return "reference_available"
            if quality.get("valid") is False:
                return "reference_rejected"
        return "no_valid_reference"

    @staticmethod
    def _measurement(*, skill: str, metric: str, value: float, confidence: float,
                     sample_count: int, track: str, conditions: dict[str, Any],
                     session_type: str, timestamp: str, reference_quality: str,
                     unit: str | None = None, source: str = "performance_review") -> dict[str, Any]:
        return {
            "skill": skill,
            "metric": metric,
            "value": round(float(value), 6),
            "confidence": round(_clamp01(confidence), 6),
            "sample_count": max(0, int(sample_count)),
            "track": track,
            "conditions": dict(conditions),
            "session_type": session_type,
            "timestamp": timestamp,
            "reference_quality": reference_quality,
            "unit": unit,
            "source": source,
        }

    def build_f1_session_evidence(self, summary: dict[str, Any] | None, coach: dict[str, Any] | None) -> dict[str, Any]:
        summary = dict(summary or {})
        coach = dict(coach or {})
        review = coach.get("performance_review") if isinstance(coach.get("performance_review"), dict) else None
        if not review:
            review = build_performance_review(coach)
        ctx = coach.get("event_context") if isinstance(coach.get("event_context"), dict) else {}
        track = str(summary.get("track") or ctx.get("track_name") or ctx.get("track") or ctx.get("track_id") or "Unknown")
        session_type = str(summary.get("session_type") or ctx.get("profile") or ctx.get("session_type") or "Unknown")
        timestamp = str(coach.get("created_utc") or summary.get("created_utc") or _utc_now())
        conditions = self._conditions(coach)
        ref_quality = self._reference_quality(review, coach)
        session_conf = _clamp01(review.get("confidence"))
        measurements: list[dict[str, Any]] = []

        # Existing deterministic Performance Review dimensions are session-level
        # measured evidence. They are *not* promoted into career skill scores here.
        group_map = {
            "Braking": ("braking", "braking_execution"),
            "Turn-in": ("corner_entry", "turn_in_execution"),
            "Corner speed": ("apex_minimum_speed", "corner_speed_execution"),
            "Throttle": ("traction_exit", "throttle_application"),
            "Exit": ("traction_exit", "exit_speed_execution"),
            "Steering": ("car_control", "steering_control"),
        }
        for row in review.get("technique_groups") or []:
            if not isinstance(row, dict):
                continue
            mapped = group_map.get(str(row.get("name") or ""))
            if not mapped or not _finite(row.get("score")):
                continue
            samples = int(row.get("sample_count") or 0)
            if samples < 1:
                continue
            skill, metric = mapped
            # Confidence is evidence trust, not a career confidence label. Bound
            # the review confidence by sample coverage without inventing a HIGH/
            # MEDIUM/LOW classification (that belongs to V2.4.1).
            sample_factor = min(1.0, samples / 12.0)
            measurements.append(self._measurement(
                skill=skill, metric=metric, value=float(row["score"]),
                confidence=session_conf * sample_factor, sample_count=samples,
                track=track, conditions=conditions, session_type=session_type,
                timestamp=timestamp, reference_quality=ref_quality, unit="session_technique_0_100",
            ))

        # Pace evidence remains a raw measured gap rather than a career score.
        ref = review.get("reference") if isinstance(review.get("reference"), dict) else {}
        ref_time = ref.get("lap_time_s")
        valid_laps = [x for x in review.get("laps") or [] if isinstance(x, dict) and _finite(x.get("lap_time_s"))]
        best_time = min((float(x["lap_time_s"]) for x in valid_laps), default=None)
        if _finite(best_time) and _finite(ref_time):
            measurements.append(self._measurement(
                skill="pace", metric="best_lap_gap_to_reference", value=float(best_time) - float(ref_time),
                confidence=session_conf, sample_count=len(valid_laps), track=track, conditions=conditions,
                session_type=session_type, timestamp=timestamp, reference_quality=ref_quality, unit="s",
            ))
            if float(ref_time) > 0.0:
                measurements.append(self._measurement(
                    skill="pace", metric="best_lap_gap_percent_to_reference",
                    value=((float(best_time) - float(ref_time)) / float(ref_time)) * 100.0,
                    confidence=session_conf, sample_count=len(valid_laps), track=track, conditions=conditions,
                    session_type=session_type, timestamp=timestamp, reference_quality=ref_quality, unit="percent",
                ))

        # Consistency evidence is raw lap-time spread. No 0..100 career score is
        # manufactured here. At least two timed laps are required.
        lap_times = [float(x["lap_time_s"]) for x in valid_laps]
        if len(lap_times) >= 2:
            spread = statistics.pstdev(lap_times)
            measurements.append(self._measurement(
                skill="consistency", metric="lap_time_standard_deviation", value=spread,
                confidence=min(1.0, len(lap_times) / 5.0), sample_count=len(lap_times),
                track=track, conditions=conditions, session_type=session_type,
                timestamp=timestamp, reference_quality="not_required", unit="s",
            ))
            mean_lap = statistics.fmean(lap_times)
            if mean_lap > 0.0:
                measurements.append(self._measurement(
                    skill="consistency", metric="lap_time_coefficient_of_variation",
                    value=(spread / mean_lap) * 100.0,
                    confidence=min(1.0, len(lap_times) / 5.0), sample_count=len(lap_times),
                    track=track, conditions=conditions, session_type=session_type,
                    timestamp=timestamp, reference_quality="not_required", unit="percent",
                ))

        session_key, uid = self._session_identity(summary, coach)
        return {
            "format": "RACE_ENGINEER_SKILL_EVIDENCE",
            "version": EVIDENCE_VERSION,
            "game_id": "f1_26",
            "discipline": "formula",
            "session_key": session_key,
            "session_uid": uid,
            "track": track,
            "conditions": conditions,
            "session_type": session_type,
            "timestamp": timestamp,
            "reference_quality": ref_quality,
            "measurement_count": len(measurements),
            "measurements": measurements,
            "career_skill_score": None,
            "career_skill_score_status": "calculated_by_v2_4_0_model_after_persist",
        }

    def capture_f1_session(self, summary: dict[str, Any] | None, coach: dict[str, Any] | None,
                           *, driver_id: str | None = None, evidence_origin: str = "live_session") -> dict[str, Any] | None:
        profile = self.driver_store.load_profile(driver_id) if driver_id else self.driver_store.active_profile()
        if not isinstance(profile, dict):
            return None
        driver_id = str(profile.get("driver_id") or "")
        if not driver_id or str(profile.get("active_game") or "f1_26") != "f1_26":
            return None
        self.driver_store.ensure_game_profile(driver_id, "f1_26")
        payload = self.build_f1_session_evidence(summary, coach)
        payload["driver_id"] = driver_id
        payload["evidence_origin"] = str(evidence_origin or "live_session")
        if isinstance(summary, dict) and summary.get("performance_history_session_id") is not None:
            payload["performance_history_session_id"] = summary.get("performance_history_session_id")
        root = self.root(driver_id, "f1_26")
        session_path = root / "sessions" / f"{payload['session_key']}.json"
        self._write_json_atomic(session_path, payload)

        index = self._read_json(self.index_path(driver_id, "f1_26"), {})
        if not isinstance(index, dict):
            index = {}
        rows = [x for x in index.get("sessions", []) if isinstance(x, dict)]
        row = {
            "session_key": payload["session_key"],
            "session_uid": payload.get("session_uid"),
            "track": payload.get("track"),
            "session_type": payload.get("session_type"),
            "timestamp": payload.get("timestamp"),
            "reference_quality": payload.get("reference_quality"),
            "measurement_count": payload.get("measurement_count", 0),
            "evidence_origin": payload.get("evidence_origin", "live_session"),
            "performance_history_session_id": payload.get("performance_history_session_id"),
            "path": str(session_path.relative_to(root)),
        }
        replaced = False
        for i, old in enumerate(rows):
            if old.get("session_key") == payload["session_key"]:
                rows[i] = row
                replaced = True
                break
        if not replaced:
            rows.append(row)
        rows.sort(key=lambda x: str(x.get("timestamp") or ""))
        index = {
            "format": "RACE_ENGINEER_SKILL_EVIDENCE_INDEX",
            "version": EVIDENCE_VERSION,
            "driver_id": driver_id,
            "game_id": "f1_26",
            "session_count": len(rows),
            "measurement_count": sum(int(x.get("measurement_count") or 0) for x in rows),
            "last_updated": _utc_now(),
            "sessions": rows,
        }
        self._write_json_atomic(self.index_path(driver_id, "f1_26"), index)

        game_profile = self.driver_store.load_game_profile(driver_id, "f1_26") or {}
        game_profile["skill_evidence"] = {
            "engine_version": EVIDENCE_VERSION,
            "session_count": index["session_count"],
            "measurement_count": index["measurement_count"],
            "last_updated": index["last_updated"],
            "career_skill_score": None,
        }
        self.driver_store.save_game_profile(driver_id, "f1_26", game_profile)
        try:
            from .driver_skill import F1DriverSkillModel
            F1DriverSkillModel(self.driver_store).recalculate(driver_id)
        except Exception:
            # Evidence persistence remains authoritative even if the derived
            # presentation model cannot be refreshed in this save cycle.
            pass
        if str(evidence_origin or "live_session") != "historical_backfill":
            try:
                from .skill_trends import SkillTrendStore
                SkillTrendStore(self.driver_store).ensure(driver_id)
            except Exception:
                # Trend history is a derived layer and must never block evidence.
                pass
        return payload

    def reconcile_with_performance_history(self, *, driver_id: str | None = None) -> dict[str, Any]:
        """Repair derived Skill Evidence identity/track labels from authoritative Performance History.

        This repair is intentionally non-destructive: it never deletes Performance
        History. It only rewrites derived Skill Evidence rows when they carry an
        exact performance_history_session_id that still exists in the authoritative
        LIVE history database. Stale duplicate evidence rows for the same history
        id are de-indexed, but their JSON files are left on disk for forensic
        recovery.
        """
        profile = self.driver_store.load_profile(driver_id) if driver_id else self.driver_store.active_profile()
        if not isinstance(profile, dict):
            return {"available": False, "reason": "no_driver_profile", "updated": 0, "deduplicated": 0, "orphaned": 0}
        driver_id = str(profile.get("driver_id") or "")
        compat = profile.get("compatibility") if isinstance(profile.get("compatibility"), dict) else {}
        history_profile_id = compat.get("performance_history_profile_id")
        if not driver_id or history_profile_id is None:
            return {"available": False, "reason": "no_performance_history_binding", "updated": 0, "deduplicated": 0, "orphaned": 0}
        try:
            if self.performance_history_store is None:
                from .performance_history import PerformanceHistoryStore
                history_store = PerformanceHistoryStore()
            else:
                history_store = self.performance_history_store
            source_rows = history_store.skill_evidence_source_sessions(history_profile_id)
        except Exception as error:
            return {"available": False, "reason": f"history_read_failed:{error}", "updated": 0, "deduplicated": 0, "orphaned": 0}

        authority: dict[int, dict[str, Any]] = {}
        authority_by_uid: dict[str, list[int]] = {}
        authoritative_unknown_exists = False
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            try:
                hid = int(row.get("history_session_id"))
            except (TypeError, ValueError):
                continue
            summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
            track = str(summary.get("track") or "").strip()
            session_type = str(summary.get("session_type") or "").strip()
            authority[hid] = {
                "track": track if track and track.lower() != "unknown" else None,
                "session_type": session_type if session_type and session_type.lower() != "unknown" else None,
                "summary": summary,
                "coach": row.get("coach") if isinstance(row.get("coach"), dict) else {},
            }
            if not track or track.lower() == "unknown":
                authoritative_unknown_exists = True
            uid = summary.get("session_uid")
            if uid is None:
                ctx = authority[hid]["coach"].get("event_context") if isinstance(authority[hid]["coach"], dict) else {}
                uid = ctx.get("session_uid") if isinstance(ctx, dict) else None
            if uid is not None:
                authority_by_uid.setdefault(str(uid), []).append(hid)

        root = self.root(driver_id, "f1_26")
        index = self._read_json(self.index_path(driver_id, "f1_26"), {})
        if not isinstance(index, dict):
            index = {}
        rows = [x for x in index.get("sessions", []) if isinstance(x, dict)]
        kept: list[dict[str, Any]] = []
        by_history_id: dict[int, tuple[int, dict[str, Any]]] = {}
        updated = 0
        deduplicated = 0
        orphaned = 0

        for old in rows:
            path = root / str(old.get("path") or "")
            payload = self._read_json(path, {})
            if not isinstance(payload, dict):
                kept.append(old)
                continue
            raw_hid = payload.get("performance_history_session_id", old.get("performance_history_session_id"))
            linked_legacy = False
            try:
                hid = int(raw_hid)
            except (TypeError, ValueError):
                # Pre-.29 live evidence did not always carry the Performance
                # History row id. Recover it only from an unambiguous session UID.
                # If an unlinked legacy row is merely "Unknown" while authoritative
                # Performance History has no Unknown session at all, de-index it:
                # Driver Profile must never invent a track absent from the Hub.
                uid = payload.get("session_uid", old.get("session_uid"))
                matches = authority_by_uid.get(str(uid), []) if uid is not None else []
                if len(matches) == 1:
                    hid = int(matches[0])
                    payload["performance_history_session_id"] = hid
                    linked_legacy = True
                else:
                    # V2.9.1.3.5.34: Performance History owns the set of live
                    # sessions, not merely their track labels. An unlinked legacy
                    # Skill Evidence row that cannot be mapped unambiguously to an
                    # existing Performance History session is therefore derived
                    # orphan data. De-index it regardless of whether its stored
                    # track happens to look valid. The JSON artifact remains on
                    # disk for forensic recovery; backfill immediately recreates
                    # authoritative evidence for every current history session.
                    orphaned += 1
                    continue
            auth = authority.get(hid)
            if not auth:
                # V2.9.1.3.5.10: Performance History is authoritative for
                # linked derived evidence. If a user explicitly deletes a
                # Performance Hub session, any Skill Evidence row carrying that
                # exact history id must disappear from the active evidence index
                # as well. Leave the JSON artifact on disk for forensic recovery,
                # but do not let it continue to produce Driver Profile track
                # cards, scores or trends.
                orphaned += 1
                continue

            changed = bool(linked_legacy)
            track = auth.get("track")
            stype = auth.get("session_type")
            if track and str(payload.get("track") or "") != track:
                payload["track"] = track
                for m in payload.get("measurements", []) if isinstance(payload.get("measurements"), list) else []:
                    if isinstance(m, dict):
                        m["track"] = track
                changed = True
            if stype and str(payload.get("session_type") or "") != stype:
                payload["session_type"] = stype
                for m in payload.get("measurements", []) if isinstance(payload.get("measurements"), list) else []:
                    if isinstance(m, dict):
                        m["session_type"] = stype
                changed = True

            # Normalize the derived identity to the stable Performance History id.
            new_key = f"history-{hid}_{hashlib.sha1(f'history-{hid}'.encode()).hexdigest()[:16]}"
            if payload.get("session_key") != new_key:
                payload["session_key"] = new_key
                changed = True
            if changed:
                self._write_json_atomic(path, payload)
                updated += 1

            row = dict(old)
            row.update({
                "session_key": payload.get("session_key"),
                "track": payload.get("track"),
                "session_type": payload.get("session_type"),
                "timestamp": payload.get("timestamp"),
                "reference_quality": payload.get("reference_quality"),
                "measurement_count": payload.get("measurement_count", 0),
                "evidence_origin": payload.get("evidence_origin", row.get("evidence_origin", "live_session")),
                "performance_history_session_id": hid,
            })
            candidate_score = (
                1 if str(payload.get("track") or "").lower() != "unknown" else 0,
                int(payload.get("measurement_count") or 0),
                str(payload.get("timestamp") or ""),
            )
            if hid in by_history_id:
                prev_idx, prev_meta = by_history_id[hid]
                if candidate_score > prev_meta["score"]:
                    kept[prev_idx] = row
                    by_history_id[hid] = (prev_idx, {"score": candidate_score})
                deduplicated += 1
            else:
                by_history_id[hid] = (len(kept), {"score": candidate_score})
                kept.append(row)

        kept.sort(key=lambda x: str(x.get("timestamp") or ""))
        index = {
            "format": "RACE_ENGINEER_SKILL_EVIDENCE_INDEX",
            "version": EVIDENCE_VERSION,
            "driver_id": driver_id,
            "game_id": "f1_26",
            "session_count": len(kept),
            "measurement_count": sum(int(x.get("measurement_count") or 0) for x in kept),
            "last_updated": _utc_now(),
            "sessions": kept,
        }
        self._write_json_atomic(self.index_path(driver_id, "f1_26"), index)
        try:
            from .driver_skill import F1DriverSkillModel
            F1DriverSkillModel(self.driver_store).recalculate(driver_id)
            from .skill_trends import SkillTrendStore
            SkillTrendStore(self.driver_store).rebuild(driver_id)
        except Exception:
            pass
        return {"available": True, "updated": updated, "deduplicated": deduplicated, "orphaned": orphaned, "session_count": len(kept)}

    def backfill_f1_history(self, *, driver_id: str | None = None, force: bool = False) -> dict[str, Any]:
        """Derive V2.3 evidence from already persisted LIVE Performance Hub sessions.

        The operation is non-destructive and idempotent. Existing evidence files
        are updated by the same deterministic session identity rather than
        duplicated. Sessions with insufficient measurements are retained as
        zero-measurement evidence artifacts so N/A remains explicit.
        """
        profile = self.driver_store.load_profile(driver_id) if driver_id else self.driver_store.active_profile()
        if not isinstance(profile, dict):
            return {"available": False, "reason": "no_driver_profile", "scanned": 0, "written": 0}
        driver_id = str(profile.get("driver_id") or "")
        if not driver_id:
            return {"available": False, "reason": "no_driver_id", "scanned": 0, "written": 0}
        compat = profile.get("compatibility") if isinstance(profile.get("compatibility"), dict) else {}
        history_profile_id = compat.get("performance_history_profile_id")
        if history_profile_id is None:
            return {"available": False, "reason": "no_performance_history_binding", "scanned": 0, "written": 0}
        try:
            if self.performance_history_store is None:
                from .performance_history import PerformanceHistoryStore
                history_store = PerformanceHistoryStore()
            else:
                history_store = self.performance_history_store
            source_rows = history_store.skill_evidence_source_sessions(history_profile_id)
        except Exception as error:
            return {"available": False, "reason": f"history_read_failed:{error}", "scanned": 0, "written": 0}

        # V2.9.1.3.5.9: clean stale derived Unknown-track evidence first.
        # This uses only exact Performance History row ids; it never guesses by
        # session UID, lap time, or timestamp.
        self.reconcile_with_performance_history(driver_id=driver_id)
        root = self.root(driver_id, "f1_26")
        marker_path = root / "historical_backfill.json"
        signature_source = "|".join(
            f"{x.get('history_session_id')}:{x.get('history_session_key')}" for x in source_rows if isinstance(x, dict)
        )
        signature = hashlib.sha1(signature_source.encode("utf-8", errors="ignore")).hexdigest()
        marker = self._read_json(marker_path, {})
        if (not force and isinstance(marker, dict) and marker.get("version") == EVIDENCE_VERSION
                and marker.get("source_signature") == signature
                and int(marker.get("source_session_count") or 0) == len(source_rows)):
            return {"available": True, "already_current": True, "scanned": len(source_rows),
                    "written": 0, "measurement_count": int(marker.get("measurement_count") or 0)}

        written = 0
        measurement_count = 0
        zero_measurement_sessions = 0
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
            coach = row.get("coach") if isinstance(row.get("coach"), dict) else {}
            # PerformanceHistoryStore is LIVE-only. Still reject explicit replay
            # markers defensively in case a legacy/custom database was imported.
            source = str(coach.get("source") or summary.get("source") or "").lower()
            replay = bool(coach.get("replay") or summary.get("replay") or source == "replay")
            if replay:
                continue
            payload = self.capture_f1_session(summary, coach, driver_id=driver_id, evidence_origin="historical_backfill")
            if payload is None:
                continue
            written += 1
            count = int(payload.get("measurement_count") or 0)
            measurement_count += count
            if count == 0:
                zero_measurement_sessions += 1

        marker = {
            "format": "RACE_ENGINEER_SKILL_EVIDENCE_HISTORICAL_BACKFILL",
            "version": EVIDENCE_VERSION,
            "driver_id": driver_id,
            "game_id": "f1_26",
            "completed_at": _utc_now(),
            "source_profile_id": history_profile_id,
            "source_session_count": len(source_rows),
            "source_signature": signature,
            "written_sessions": written,
            "measurement_count": measurement_count,
            "zero_measurement_sessions": zero_measurement_sessions,
            "mode": "non_destructive_logical_read",
        }
        self._write_json_atomic(marker_path, marker)
        try:
            from .skill_trends import SkillTrendStore
            SkillTrendStore(self.driver_store).ensure(driver_id)
        except Exception:
            pass
        return {"available": True, "already_current": False, "scanned": len(source_rows),
                "written": written, "measurement_count": measurement_count,
                "zero_measurement_sessions": zero_measurement_sessions}

    def summary(self, driver_id: str, game_id: str = "f1_26") -> dict[str, Any]:
        index = self._read_json(self.index_path(driver_id, game_id), {})
        if not isinstance(index, dict):
            index = {}
        rows = [x for x in index.get("sessions", []) if isinstance(x, dict)]
        by_skill: dict[str, dict[str, int]] = {}
        for row in rows:
            path = self.root(driver_id, game_id) / str(row.get("path") or "")
            payload = self._read_json(path, {})
            for m in payload.get("measurements", []) if isinstance(payload, dict) else []:
                if not isinstance(m, dict):
                    continue
                skill = str(m.get("skill") or "unknown")
                bucket = by_skill.setdefault(skill, {"measurements": 0, "samples": 0})
                bucket["measurements"] += 1
                bucket["samples"] += int(m.get("sample_count") or 0)
        return {
            "available": bool(rows),
            "session_count": len(rows),
            "measurement_count": sum(int(x.get("measurement_count") or 0) for x in rows),
            "by_skill": by_skill,
            "last_updated": index.get("last_updated"),
        }
