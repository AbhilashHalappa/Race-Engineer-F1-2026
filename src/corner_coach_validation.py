"""V1.2.0.4 CORNER COACH deterministic validation trace.

The live coach is difficult to validate from screenshots because the important
questions are temporal: which physical corner/zone was active, whether PRE/POST
was eligible, why a call was blocked, and whether a generated call actually
reached audio playback.  This module writes a compact JSONL trace asynchronously
so the telemetry hot path never waits for disk I/O.

A trace is self-contained: the first record carries the reference geometry and
zone definitions, distance samples are emitted at a fixed spatial cadence, and
all state transitions / radio decisions are event records.  A lap summary is
written whenever the lap number advances.
"""
from __future__ import annotations

import atexit
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import queue
import re
import threading
from typing import Any, Iterable


VALIDATION_SCHEMA_VERSION = 3
VALIDATION_RELEASE = "V1.2.0.4"
from .app_paths import CORNER_VALIDATION
DEFAULT_OUTPUT_DIR = CORNER_VALIDATION


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_safe(x) for x in value]
    if isinstance(value, list):
        return [_json_safe(x) for x in value]
    if isinstance(value, set):
        return [_json_safe(x) for x in sorted(value, key=str)]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    # EnumValue and similar objects normally expose a useful name/label.
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    label = getattr(value, "label", None)
    if isinstance(label, str):
        return label
    try:
        return str(value)
    except Exception:
        return None


def _safe_name(text: Any) -> str:
    raw = str(text or "UNKNOWN").strip().upper()
    raw = re.sub(r"[^A-Z0-9._-]+", "_", raw)
    return raw.strip("_") or "UNKNOWN"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class _AsyncJsonlWriter:
    """Single daemon writer shared by one validation recorder.

    Telemetry/audio threads only perform a non-blocking queue put.  Opening,
    serialising and flushing files happens on the daemon thread.
    """

    def __init__(self, max_queue: int = 8192) -> None:
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.dropped = 0
        self._closed = False

    def _ensure_started(self) -> None:
        if self._thread is not None:
            return
        with self._lock:
            if self._thread is None and not self._closed:
                self._thread = threading.Thread(target=self._run, name="CornerCoachValidationWriter", daemon=True)
                self._thread.start()

    def submit(self, path: Path, record: dict[str, Any]) -> None:
        if self._closed:
            return
        self._ensure_started()
        try:
            self._queue.put_nowait((Path(path), _json_safe(record)))
        except queue.Full:
            self.dropped += 1

    def flush(self, timeout: float = 2.0) -> bool:
        if self._thread is None or self._closed:
            return True
        done = threading.Event()
        try:
            self._queue.put(("__flush__", done), timeout=max(0.05, timeout))
        except queue.Full:
            return False
        return done.wait(timeout)

    def close(self) -> None:
        if self._closed:
            return
        self.flush(1.5)
        self._closed = True
        if self._thread is not None:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                return
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        handles: dict[Path, Any] = {}
        try:
            while True:
                item = self._queue.get()
                if item is None:
                    break
                if isinstance(item, tuple) and item and item[0] == "__flush__":
                    for handle in handles.values():
                        try:
                            handle.flush()
                        except Exception:
                            pass
                    item[1].set()
                    continue
                path, record = item
                try:
                    handle = handles.get(path)
                    if handle is None:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        handle = path.open("a", encoding="utf-8", newline="\n")
                        handles[path] = handle
                    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                    # Validation data is more valuable than a small throughput gain;
                    # flush each low-rate record so Ctrl+C still leaves a useful file.
                    handle.flush()
                except Exception:
                    # Diagnostics must never destabilise Race Engineer.
                    self.dropped += 1
        finally:
            for handle in handles.values():
                try:
                    handle.flush(); handle.close()
                except Exception:
                    pass


class CornerCoachValidationRecorder:
    """Low-overhead state/event recorder for end-to-end CORNER COACH validation."""

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR, *, enabled: bool = True, sample_step_m: float = 10.0) -> None:
        self.enabled = bool(enabled)
        self.output_dir = Path(output_dir)
        self.sample_step_m = max(2.5, float(sample_step_m))
        self._writer = _AsyncJsonlWriter()
        self._lock = threading.RLock()
        self._run_key: tuple[Any, ...] | None = None
        self._path: Path | None = None
        self._expected_zones: list[str] = []
        self._zone_defs: dict[str, dict[str, Any]] = {}
        self._physical_ids: list[int] = []
        self._current_lap: int | None = None
        self._sample_bucket: int | None = None
        self._lap_stats: dict[str, Any] = {}
        self._last_pre_reason: dict[str, str] = {}
        self._last_post_reason: dict[str, str] = {}
        self._radio_submit_counts: Counter[tuple[int|None,str]] = Counter()
        self._audio_start_counts: Counter[tuple[int|None,str]] = Counter()
        self._delivery_counts: Counter[tuple[int|None,str,str]] = Counter()
        self._pending_pre_emitted: dict[int,set[str]] = {}
        atexit.register(self.close)

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def dropped_records(self) -> int:
        return int(self._writer.dropped)

    def _emit(self, event: str, **payload: Any) -> None:
        path = self._path
        if not self.enabled or path is None:
            return
        record = {
            "schema": VALIDATION_SCHEMA_VERSION,
            "release": VALIDATION_RELEASE,
            "event": str(event),
            "utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            **payload,
        }
        self._writer.submit(path, record)

    @staticmethod
    def _reference_checks(corners: list[dict[str, Any]], zones: list[dict[str, Any]]) -> dict[str, Any]:
        corner_ids = [int(c.get("corner_id")) for c in corners if isinstance(c, dict) and isinstance(c.get("corner_id"), int)]
        expected_ids = list(range(1, len(corner_ids) + 1))
        apexes = [float(c.get("apex_m")) for c in corners if isinstance(c, dict) and _finite(c.get("apex_m"))]
        zone_starts = [float(z.get("approach_start_m")) for z in zones if isinstance(z, dict) and _finite(z.get("approach_start_m"))]
        zone_corner_ids = [int(cid) for z in zones if isinstance(z, dict) for cid in (z.get("corner_ids") or ()) if isinstance(cid, int)]
        return {
            "physical_corner_ids_sequential": corner_ids == expected_ids,
            "physical_apex_order_monotonic": all(b > a for a, b in zip(apexes, apexes[1:])),
            "zone_distance_order_monotonic": all(b >= a for a, b in zip(zone_starts, zone_starts[1:])),
            "zone_corner_ids_known": all(cid in set(corner_ids) for cid in zone_corner_ids),
            "physical_corner_count": len(corner_ids),
            "coaching_zone_count": len(zones),
        }

    def ensure_run(self, *, session_uid: Any, track_name: Any, model: Any, stable_session: bool = False) -> Path | None:
        if not self.enabled or model is None:
            return None
        quality = dict(getattr(model, "quality", {}) or {})
        metadata = dict(getattr(model, "metadata", {}) or {})
        fingerprint = quality.get("raw_reference_fingerprint") or metadata.get("raw_reference_fingerprint")
        track_key = str(track_name or getattr(model, "track_name", "")).upper()
        key = (session_uid, track_key, "SESSION_BEST") if stable_session else (session_uid, track_key, fingerprint, getattr(model, "lap_time_s", None))
        with self._lock:
            if key == self._run_key and self._path is not None:
                if stable_session and fingerprint != getattr(self, "_active_reference_fingerprint", None):
                    from .corner_coach_models import to_dict
                    corners = [to_dict(c) if not isinstance(c, dict) else c for c in (getattr(model, "physical_corners", ()) or ())]
                    zones = [to_dict(z) if not isinstance(z, dict) else z for z in (getattr(model, "coaching_zones", ()) or ())]
                    self._expected_zones = [str(z.get("zone_id")) for z in zones if z.get("zone_id")]
                    self._zone_defs = {str(z.get("zone_id")): dict(z) for z in zones if z.get("zone_id")}
                    self._physical_ids = [int(c.get("corner_id")) for c in corners if isinstance(c.get("corner_id"), int)]
                    self._active_reference_fingerprint = fingerprint
                    self._emit("reference_update", session_uid=session_uid, track_name=getattr(model, "track_name", track_key), reference_lap_time_s=getattr(model, "lap_time_s", None), reference_fingerprint=fingerprint, physical_corners=corners, coaching_zones=zones, reference_checks=self._reference_checks(corners, zones))
                return self._path
            if self._current_lap is not None:
                self.finish_lap(reason="validation_run_changed")
            self._run_key = key
            self._active_reference_fingerprint = fingerprint
            track = _safe_name(track_name or getattr(model, "track_name", None))
            uid = _safe_name(session_uid if session_uid is not None else "NOUID")
            self._path = self.output_dir / f"CORNER_COACH_{track}_{uid}_{_utc_stamp()}.jsonl"
            corners = [_json_safe(c) for c in (getattr(model, "physical_corners", ()) or ())]
            zones = [_json_safe(z) for z in (getattr(model, "coaching_zones", ()) or ())]
            # Dataclasses are converted by caller/model helper in most places, but
            # preserve a safe fallback for direct dataclass instances.
            from .corner_coach_models import to_dict
            corners = [to_dict(c) if not isinstance(c, dict) else c for c in (getattr(model, "physical_corners", ()) or ())]
            zones = [to_dict(z) if not isinstance(z, dict) else z for z in (getattr(model, "coaching_zones", ()) or ())]
            self._expected_zones = [str(z.get("zone_id")) for z in zones if z.get("zone_id")]
            self._zone_defs = {str(z.get("zone_id")): dict(z) for z in zones if z.get("zone_id")}
            self._physical_ids = [int(c.get("corner_id")) for c in corners if isinstance(c.get("corner_id"), int)]
            self._current_lap = None
            self._sample_bucket = None
            self._lap_stats = {}
            self._last_pre_reason = {}
            self._last_post_reason = {}
            self._radio_submit_counts.clear(); self._audio_start_counts.clear(); self._delivery_counts.clear()
            self._pending_pre_emitted.clear()
            self._emit(
                "run_start",
                session_uid=session_uid,
                track_name=getattr(model, "track_name", track),
                track_length_m=getattr(model, "track_length_m", None),
                reference_lap_time_s=getattr(model, "lap_time_s", None),
                reference_fingerprint=fingerprint,
                reference_compiler_id=quality.get("reference_compiler_id") or metadata.get("reference_compiler_id"),
                quality_validator_version=quality.get("quality_validator_version"),
                pace_compiler_version=quality.get("pace_compiler_version"),
                reference_trace_mode=quality.get("reference_trace_mode"),
                input_telemetry_trusted=quality.get("input_telemetry_trusted"),
                reference_metadata=metadata,
                reference_quality=quality,
                physical_corners=corners,
                coaching_zones=zones,
                reference_checks=self._reference_checks(corners, zones),
            )
            print(f"[CORNER COACH] Validation trace: {self._path}", flush=True)
            return self._path

    def begin_lap(self, lap: int, *, distance_m: Any = None, session_time_s: Any = None) -> None:
        with self._lock:
            if self._current_lap == lap:
                return
            self._current_lap = int(lap)
            self._sample_bucket = None
            self._last_pre_reason = {}
            self._last_post_reason = {}
            carried=sorted(self._pending_pre_emitted.pop(int(lap),set()))
            self._lap_stats = {
                "zone_entries": [], "physical_entries": [], "phase_transitions": [],
                "pre_emitted": carried, "pre_missed": [], "pre_suppressed": [], "pre_blocked": {},
                "post_emitted": [], "post_expired": [], "post_suppressed": [], "post_blocked": {},
                "diagnoses": {}, "sample_count": 0, "latest_sample": None,
            }
            self._emit("lap_start", lap=int(lap), distance_m=distance_m, session_time_s=session_time_s,
                       expected_zone_order=list(self._expected_zones), expected_physical_corner_order=list(self._physical_ids),
                       carried_pre_emitted=carried)

    def sample(self, *, lap: Any, distance_m: Any, force: bool = False, **payload: Any) -> None:
        if not self.enabled or not isinstance(lap, int) or not _finite(distance_m):
            return
        with self._lock:
            if self._current_lap != lap:
                self.begin_lap(lap, distance_m=distance_m, session_time_s=payload.get("session_time_s"))
            bucket = int(float(distance_m) // self.sample_step_m)
            if not force and self._sample_bucket == bucket:
                return
            self._sample_bucket = bucket
            record = {"lap": lap, "distance_m": float(distance_m), **payload}
            self._lap_stats["sample_count"] = int(self._lap_stats.get("sample_count", 0)) + 1
            self._lap_stats["latest_sample"] = _json_safe(record)
            self._emit("sample", **record)

    def state_transition(self, kind: str, *, lap: Any, distance_m: Any, session_time_s: Any = None, **payload: Any) -> None:
        with self._lock:
            if isinstance(lap, int) and self._current_lap != lap:
                self.begin_lap(lap, distance_m=distance_m, session_time_s=session_time_s)
            if kind == "zone_enter" and payload.get("zone_id"):
                self._lap_stats.setdefault("zone_entries", []).append(str(payload["zone_id"]))
            elif kind == "physical_corner_enter" and isinstance(payload.get("corner_id"), int):
                self._lap_stats.setdefault("physical_entries", []).append(int(payload["corner_id"]))
            elif kind == "phase_change":
                self._lap_stats.setdefault("phase_transitions", []).append({"zone_id": payload.get("zone_id"), "phase": payload.get("phase"), "distance_m": distance_m})
            self._emit(kind, lap=lap, distance_m=distance_m, session_time_s=session_time_s, **payload)

    def pre_decision(self, *, lap: Any, zone_id: str, event: str, reason: str | None = None, **payload: Any) -> None:
        with self._lock:
            if event == "pre_blocked":
                normalized = str(reason or "unknown")
                if self._last_pre_reason.get(zone_id) == normalized:
                    return
                self._last_pre_reason[zone_id] = normalized
                self._lap_stats.setdefault("pre_blocked", {}).setdefault(zone_id, []).append(normalized)
            elif event == "pre_emit":
                self._lap_stats.setdefault("pre_emitted", []).append(zone_id)
                self._last_pre_reason.pop(zone_id, None)
            elif event == "pre_emit_next_lap":
                target_lap=payload.get("target_lap")
                if isinstance(target_lap,int):
                    self._pending_pre_emitted.setdefault(target_lap,set()).add(zone_id)
            elif event == "pre_missed":
                if zone_id in self._lap_stats.setdefault("pre_missed", []):
                    return
                self._lap_stats["pre_missed"].append(zone_id)
            elif event == "pre_suppressed":
                if zone_id in self._lap_stats.setdefault("pre_suppressed", []):
                    return
                self._lap_stats["pre_suppressed"].append(zone_id)
            self._emit(event, lap=lap, zone_id=zone_id, reason=reason, **payload)

    def post_decision(self, *, lap: Any, zone_id: str, event: str, reason: str | None = None, diagnosis: Any = None, **payload: Any) -> None:
        with self._lock:
            if event == "post_blocked":
                normalized = str(reason or "unknown")
                if self._last_post_reason.get(zone_id) == normalized:
                    return
                self._last_post_reason[zone_id] = normalized
                self._lap_stats.setdefault("post_blocked", {}).setdefault(zone_id, []).append(normalized)
            elif event == "post_emit":
                self._lap_stats.setdefault("post_emitted", []).append(zone_id)
                self._last_post_reason.pop(zone_id, None)
                if diagnosis is not None:
                    self._lap_stats.setdefault("diagnoses", {})[zone_id] = _json_safe(diagnosis)
            elif event == "post_expired":
                if zone_id in self._lap_stats.setdefault("post_expired", []):
                    return
                self._lap_stats["post_expired"].append(zone_id)
            elif event == "post_suppressed":
                if zone_id in self._lap_stats.setdefault("post_suppressed", []):
                    return
                self._lap_stats["post_suppressed"].append(zone_id)
                if diagnosis is not None:
                    self._lap_stats.setdefault("diagnoses", {})[zone_id] = _json_safe(diagnosis)
            self._emit(event, lap=lap, zone_id=zone_id, reason=reason, diagnosis=diagnosis, **payload)

    @staticmethod
    def _corner_key(message_key: str) -> str | None:
        parts = str(message_key or "").split(":")
        if len(parts) >= 4 and parts[0] == "corner" and parts[1] in {"pre", "post"}:
            return ":".join(parts[:4])
        return None

    @staticmethod
    def _message_lap(message_key:str)->int|None:
        parts=str(message_key or "").split(":")
        if len(parts)>=4 and parts[0]=="corner" and parts[1] in {"pre","post"}:
            try:return int(parts[2])
            except (TypeError,ValueError):return None
        return None

    def radio_submit(self, message: Any) -> None:
        key = str(getattr(message, "key", "") or "")
        if not key.startswith("corner:"):
            return
        with self._lock:
            canonical = self._corner_key(key) or key
            target_lap=self._message_lap(key)
            self._radio_submit_counts[(target_lap,canonical)] += 1
            self._emit("radio_submit", message_key=key, text=getattr(message, "text", None), priority=str(getattr(message, "priority", "")), speak=bool(getattr(message,"speak",True)))

    def audio_start(self, message: Any) -> None:
        key = str(getattr(message, "key", "") or "")
        if not key.startswith("corner:"):
            return
        with self._lock:
            canonical = self._corner_key(key) or key
            target_lap=self._message_lap(key)
            self._audio_start_counts[(target_lap,canonical)] += 1
            self._emit("audio_start", message_key=key, text=getattr(message, "text", None), priority=str(getattr(message, "priority", "")), deadline_at_monotonic_s=getattr(message,"deadline_at_monotonic_s",None), estimated_duration_s=getattr(message,"estimated_duration_s",None))

    def delivery_event(self, message: Any, outcome: str, **details: Any) -> None:
        """Record why a generated CORNER COACH line completed, waited or was dropped."""
        key = str(getattr(message, "key", "") or "")
        if not key.startswith("corner:"):
            return
        with self._lock:
            canonical = self._corner_key(key) or key
            target_lap = self._message_lap(key)
            normalized = str(outcome or "UNKNOWN")
            self._delivery_counts[(target_lap, canonical, normalized)] += 1
            self._emit(
                "radio_delivery", message_key=key, outcome=normalized, text=getattr(message,"text",None),
                priority=str(getattr(message,"priority","")), deadline_at_monotonic_s=getattr(message,"deadline_at_monotonic_s",None),
                estimated_duration_s=getattr(message,"estimated_duration_s",None), **details,
            )

    def finish_lap(self, *, reason: str = "lap_advanced", zone_attribution: Any = None, distance_status: Any = None,
                   last_delta_s: Any = None, first_delta_s: Any = None) -> None:
        with self._lock:
            lap = self._current_lap
            if lap is None or not self._lap_stats:
                return
            stats = _json_safe(self._lap_stats)
            observed_zones = list(stats.get("zone_entries") or [])
            observed_physical = list(stats.get("physical_entries") or [])
            expected_zones = list(self._expected_zones)
            expected_physical = list(self._physical_ids)
            pre_emitted = list(stats.get("pre_emitted") or [])
            post_emitted = list(stats.get("post_emitted") or [])
            radio_submitted = {key:int(count) for (target_lap,key),count in self._radio_submit_counts.items() if target_lap==lap}
            audio_started = {key:int(count) for (target_lap,key),count in self._audio_start_counts.items() if target_lap==lap}
            delivery_outcomes: dict[str, dict[str, int]] = {}
            for (target_lap,key,outcome),count in self._delivery_counts.items():
                if target_lap==lap:
                    delivery_outcomes.setdefault(key,{})[outcome]=int(count)
            generated_not_spoken = []
            for key, count in radio_submitted.items():
                heard = int(audio_started.get(key, 0))
                if heard < int(count):
                    generated_not_spoken.append({"message_key": key, "submitted": int(count), "audio_started": heard})
            reconciliation = None
            if isinstance(zone_attribution, dict):
                reconciliation = zone_attribution.get("reconciliation_error_s")
            complete_hint = False
            latest = stats.get("latest_sample") if isinstance(stats, dict) else None
            if isinstance(latest, dict) and _finite(latest.get("distance_m")):
                complete_hint = float(latest["distance_m"]) >= 0.95 * max(1.0, max((float(z.get("end_m", 0.0)) for z in self._zone_defs.values()), default=0.0))
            checks = {
                "observed_zone_order_matches_reference": observed_zones == expected_zones if complete_hint else observed_zones == expected_zones[:len(observed_zones)],
                "observed_physical_order_matches_reference": observed_physical == expected_physical if complete_hint else observed_physical == expected_physical[:len(observed_physical)],
                "duplicate_zone_entries": [k for k, v in Counter(observed_zones).items() if v > 1],
                "duplicate_physical_entries": [k for k, v in Counter(observed_physical).items() if v > 1],
                "duplicate_pre_emits": [k for k, v in Counter(pre_emitted).items() if v > 1],
                "duplicate_post_emits": [k for k, v in Counter(post_emitted).items() if v > 1],
                "generated_not_spoken_at_lap_close": generated_not_spoken,
                "radio_delivery_provisional": False,
                "radio_delivery_outcomes": delivery_outcomes,
                "reconciliation_error_s": reconciliation,
                "reconciliation_within_20ms": (abs(float(reconciliation)) <= 0.020) if _finite(reconciliation) else None,
            }
            self._emit(
                "lap_summary", lap=lap, reason=reason, complete_hint=complete_hint,
                expected_zone_order=expected_zones, expected_physical_corner_order=expected_physical,
                stats=stats, checks=checks,
                zone_attribution=zone_attribution, distance_performance=distance_status,
                first_delta_s=first_delta_s, last_delta_s=last_delta_s,
                net_lap_delta_change_s=(float(last_delta_s)-float(first_delta_s)) if _finite(last_delta_s) and _finite(first_delta_s) else None,
                writer_dropped_records=self.dropped_records,
            )
            self._current_lap = None
            self._lap_stats = {}
            self._sample_bucket = None
            self._last_pre_reason = {}; self._last_post_reason = {}
            # Preserve future-lap circular PRE delivery counts until that target
            # lap closes. Purge only the lap whose summary was just emitted.
            self._radio_submit_counts=Counter({k:v for k,v in self._radio_submit_counts.items() if k[0]!=lap})
            self._audio_start_counts=Counter({k:v for k,v in self._audio_start_counts.items() if k[0]!=lap})
            self._delivery_counts=Counter({k:v for k,v in self._delivery_counts.items() if k[0]!=lap})

    def flush(self, timeout: float = 2.0) -> bool:
        return self._writer.flush(timeout)

    def close(self) -> None:
        try:
            if self._current_lap is not None:
                self.finish_lap(reason="process_exit")
            self._writer.close()
        except Exception:
            pass


def analyze_validation_file(path: str | Path) -> dict[str, Any]:
    """Return a compact deterministic report from a CORNER COACH JSONL trace."""
    p = Path(path)
    events: list[dict[str, Any]] = []
    bad_lines = 0
    with p.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                bad_lines += 1
                continue
            if isinstance(row, dict):
                events.append(row)
    run = next((x for x in events if x.get("event") == "run_start"), {})
    summaries = [x for x in events if x.get("event") == "lap_summary"]
    counts = Counter(str(x.get("event")) for x in events)
    submitted=Counter()
    heard=Counter()
    delivery=Counter()
    for row in events:
        key=str(row.get("message_key") or "")
        canonical=CornerCoachValidationRecorder._corner_key(key) or key
        if not canonical:
            continue
        if row.get("event")=="radio_submit": submitted[canonical]+=1
        elif row.get("event")=="audio_start": heard[canonical]+=1
        elif row.get("event")=="radio_delivery": delivery[(canonical,str(row.get("outcome") or "UNKNOWN"))]+=1
    generated_not_spoken=[]
    for key,count in submitted.items():
        audio=int(heard.get(key,0))
        if audio<int(count):
            generated_not_spoken.append({"message_key":key,"submitted":int(count),"audio_started":audio})
    return {
        "file": str(p),
        "schema": run.get("schema"),
        "release": run.get("release"),
        "track_name": run.get("track_name"),
        "reference_lap_time_s": run.get("reference_lap_time_s"),
        "reference_compiler_id": run.get("reference_compiler_id"),
        "physical_corner_count": (run.get("reference_checks") or {}).get("physical_corner_count"),
        "coaching_zone_count": (run.get("reference_checks") or {}).get("coaching_zone_count"),
        "event_counts": dict(counts),
        "generated_not_spoken": generated_not_spoken,
        "delivery_outcomes": {f"{key}|{outcome}":int(count) for (key,outcome),count in delivery.items()},
        "lap_summaries": summaries,
        "bad_json_lines": bad_lines,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyze a Race Engineer CORNER COACH validation JSONL file")
    parser.add_argument("file")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    report = analyze_validation_file(args.file)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
        print(out)
    else:
        print(text)
