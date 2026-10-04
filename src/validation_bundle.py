"""Automatic session/weekend validation bundle generation for V1.5.0.0."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
from typing import Any, Iterable


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper()
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)[:80] or "UNKNOWN"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _jsonable(value: Any):
    if is_dataclass(value): return _jsonable(asdict(value))
    if isinstance(value, dict): return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)): return [_jsonable(v) for v in value]
    if isinstance(value, Path): return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None: return value
    return str(value)


class ValidationBundleManager:
    """Create compact evidence ZIPs from artifacts already written asynchronously.

    Large `.areplay` recordings are never copied into the validation ZIP. The
    manifest stores path, size and SHA-256 instead, which makes a 500+ MB race
    auditable without forcing the user to upload it unless packet-level analysis
    is actually required.
    """

    def __init__(self, output_dir: str | Path | None = None) -> None:
        from .app_paths import VALIDATION_BUNDLES
        self.output_dir = Path(output_dir) if output_dir is not None else VALIDATION_BUNDLES
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._strategy_rows: list[dict[str, Any]] = []
        self._pit_rows: list[dict[str, Any]] = []
        self._warnings: list[dict[str, Any]] = []
        self._reference_history: list[dict[str, Any]] = []
        # Validation evidence must never become an unbounded replay-time cache.
        # These limits are far above normal evidence volume, but guarantee that a
        # multi-hour replay cannot grow memory indefinitely if a producer regresses.
        self._max_strategy_rows = 4096
        self._max_event_rows = 2048
        self._finalized_uids: set[Any] = set()

    def strategy(self, state, assessment: Any, *, reason: str = "periodic") -> None:
        session = getattr(state, "session", None)
        row = {"session_uid": getattr(session, "uid", None), "session_time_s": getattr(session, "session_time_s", None),
               "reason": reason, "assessment": _jsonable(assessment)}
        if not self._strategy_rows or self._strategy_rows[-1] != row:
            self._strategy_rows.append(row)
            if len(self._strategy_rows) > self._max_strategy_rows:
                del self._strategy_rows[:-self._max_strategy_rows]

    def pit(self, state, *, decision: str, reasons: Iterable[str] = (), game_window: dict[str, Any] | None = None) -> None:
        session = getattr(state, "session", None)
        self._pit_rows.append({"session_uid": getattr(session, "uid", None), "session_time_s": getattr(session, "session_time_s", None),
                               "decision": str(decision), "reasons": list(reasons), "game_window": _jsonable(game_window or {})})
        if len(self._pit_rows) > self._max_event_rows:
            del self._pit_rows[:-self._max_event_rows]

    def warning(self, state, code: str, detail: Any) -> None:
        session = getattr(state, "session", None)
        self._warnings.append({"session_uid": getattr(session, "uid", None), "session_time_s": getattr(session, "session_time_s", None),
                               "code": str(code), "detail": _jsonable(detail)})
        if len(self._warnings) > self._max_event_rows:
            del self._warnings[:-self._max_event_rows]

    def reference(self, state, *, selection: str, fingerprint: Any, lap_time_s: Any, event: str = "active") -> None:
        session = getattr(state, "session", None)
        row = {"session_uid": getattr(session, "uid", None), "session_time_s": getattr(session, "session_time_s", None),
               "event": event, "selection": selection, "fingerprint": fingerprint, "lap_time_s": lap_time_s}
        if not self._reference_history or self._reference_history[-1] != row:
            self._reference_history.append(row)
            if len(self._reference_history) > self._max_event_rows:
                del self._reference_history[:-self._max_event_rows]

    @staticmethod
    def _state_meta(state) -> dict[str, Any]:
        session = getattr(state, "session", None)
        player = getattr(state, "player", None)
        lap = getattr(player, "lap", None) if player is not None else None
        track = getattr(getattr(session, "track", None), "name", None) or getattr(getattr(session, "track", None), "label", None)
        st = getattr(getattr(session, "session_type", None), "name", None) or getattr(getattr(session, "session_type", None), "label", None)
        return {"session_uid": getattr(session, "uid", None), "track": track, "session_type": st,
                "session_time_s": getattr(session, "session_time_s", None), "total_laps": getattr(session, "total_laps", None),
                "current_lap": getattr(lap, "current_lap", None), "position": getattr(lap, "position", None)}

    @staticmethod
    def _copy_artifacts(root: Path, artifacts: Iterable[Path | str | None]) -> list[dict[str, Any]]:
        rows=[]; seen=set()
        for raw in artifacts:
            if not raw: continue
            p=Path(raw)
            if not p.exists() or not p.is_file(): continue
            try: key=str(p.resolve())
            except OSError: key=str(p)
            if key in seen: continue
            seen.add(key)
            # Never copy the huge raw recording; only hash/reference it.
            if p.suffix.lower()==".areplay":
                rows.append({"name": p.name, "source": str(p), "size": p.stat().st_size, "sha256": sha256_file(p), "embedded": False})
                continue
            target=root/"artifacts"/p.name; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,target)
            rows.append({"name": p.name, "source": str(p), "size": p.stat().st_size, "sha256": sha256_file(p), "embedded": True,
                         "bundle_path": str(target.relative_to(root))})
        return rows

    def finalize_session(self, state, *, transcript_paths: dict[str, Any] | None = None, corner_validation: Any = None,
                         recording_path: Any = None, replay_index: Any = None, latency: Any = None, runtime: Any = None,
                         additional_artifacts: Iterable[Any] = (), label: str = "session", session_meta_override: dict[str, Any] | None = None) -> Path | None:
        meta=dict(session_meta_override or self._state_meta(state)); uid=meta.get("session_uid")
        if uid is None or uid in self._finalized_uids: return None
        self._finalized_uids.add(uid)
        track=_safe(meta.get("track")); typ=_safe(meta.get("session_type")); stamp=_stamp()
        root=self.output_dir/f".build_{track}_{typ}_{uid}_{stamp}"; root.mkdir(parents=True,exist_ok=True)
        paths=list((transcript_paths or {}).values())+[corner_validation,recording_path,replay_index,*list(additional_artifacts)]
        artifact_rows=self._copy_artifacts(root,paths)
        strategy=[x for x in self._strategy_rows if x.get("session_uid")==uid]
        pits=[x for x in self._pit_rows if x.get("session_uid")==uid]
        warnings=[x for x in self._warnings if x.get("session_uid")==uid]
        refs=[x for x in self._reference_history if x.get("session_uid")==uid]
        (root/"strategy_decisions.json").write_text(json.dumps(strategy,indent=2,default=str),encoding="utf-8")
        (root/"pit_decisions.json").write_text(json.dumps(pits,indent=2,default=str),encoding="utf-8")
        (root/"reference_history.json").write_text(json.dumps(refs,indent=2,default=str),encoding="utf-8")
        (root/"warnings_errors.json").write_text(json.dumps(warnings,indent=2,default=str),encoding="utf-8")
        perf={"latency":_jsonable(latency),"runtime":_jsonable(runtime)}
        (root/"performance_metrics.json").write_text(json.dumps(perf,indent=2,default=str),encoding="utf-8")
        manifest={"schema":1,"release":"V1.5.0.0","created_utc":datetime.now(timezone.utc).isoformat(),"label":label,
                  "session":meta,"artifacts":artifact_rows,"strategy_decision_count":len(strategy),"pit_decision_count":len(pits),
                  "reference_event_count":len(refs),"warning_count":len(warnings),"performance":perf}
        (root/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True,default=str),encoding="utf-8")
        out=self.output_dir/f"VALIDATION_BUNDLE_{track}_{typ}_{uid}_{stamp}.zip"
        with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(root.rglob("*")):
                if p.is_file(): z.write(p,p.relative_to(root))
        shutil.rmtree(root,ignore_errors=True)
        # The bundle is now durable on disk; release finalized-session evidence so
        # weekend replays do not retain every prior session in process memory.
        self._strategy_rows = [x for x in self._strategy_rows if x.get("session_uid") != uid]
        self._pit_rows = [x for x in self._pit_rows if x.get("session_uid") != uid]
        self._warnings = [x for x in self._warnings if x.get("session_uid") != uid]
        self._reference_history = [x for x in self._reference_history if x.get("session_uid") != uid]
        return out

    def build_weekend_bundle(self, *, track: Any = None) -> Path | None:
        zips=sorted(self.output_dir.glob("VALIDATION_BUNDLE_*.zip"),key=lambda p:p.stat().st_mtime)
        if track:
            key=_safe(track); zips=[p for p in zips if f"_{key}_" in p.name]
        if not zips:return None
        stamp=_stamp(); key=_safe(track or "WEEKEND")
        out=self.output_dir/f"WEEKEND_VALIDATION_BUNDLE_{key}_{stamp}.zip"
        manifest={"schema":1,"release":"V1.5.0.0","created_utc":datetime.now(timezone.utc).isoformat(),
                  "session_bundles":[{"name":p.name,"sha256":sha256_file(p),"size":p.stat().st_size} for p in zips]}
        with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            z.writestr("manifest.json",json.dumps(manifest,indent=2,sort_keys=True))
            for p in zips:z.write(p,f"sessions/{p.name}")
        return out
