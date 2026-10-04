"""Server Roadmap S7: bulk historical-file migration.

S7 migrates low-risk, non-real-time files to the server in the background.
Active/current-session recordings stay local.  Historical sources are retained
locally for compatibility with the existing replay/session-library UI until a
later cache/retention phase explicitly changes that policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import json
import os
import socket
import time

from .storage_manager import DEFAULT_STORAGE, StorageManager, StorageState
from .sync_lock import SyncOwnershipLock


MIGRATION_VERSION = 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_rel(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return Path(path.name)


@dataclass(frozen=True)
class MigrationCandidate:
    source: Path
    category: str
    source_class: str
    remote_relpath: Path
    require_stable: bool = False


class BulkDataMigrator:
    """Discover and queue S7 historical files without touching the live path."""

    SKIP_SUFFIXES = {".part", ".tmp", ".lock"}

    def __init__(
        self,
        storage: StorageManager = DEFAULT_STORAGE,
        *,
        recording_stable_age_s: float = 120.0,
    ) -> None:
        self.storage = storage
        self.recording_stable_age_s = max(0.0, float(recording_stable_age_s))
        self.state_path = self.storage.server_sync_root / "bulk_migration.json"
        self.hostname = socket.gethostname() or "gaming-pc"

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"migration_version": MIGRATION_VERSION, "files": {}}
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"migration_version": MIGRATION_VERSION, "files": {}}
        if not isinstance(value, dict):
            return {"migration_version": MIGRATION_VERSION, "files": {}}
        value.setdefault("migration_version", MIGRATION_VERSION)
        value.setdefault("files", {})
        if not isinstance(value["files"], dict):
            value["files"] = {}
        return value

    def _save_state(self, state: dict[str, Any]) -> None:
        state["migration_version"] = MIGRATION_VERSION
        state["updated_at_utc"] = _utc_now()
        self.storage._write_json_atomic(self.state_path, state)

    @staticmethod
    def _iter_files(root: Path) -> Iterable[Path]:
        if not root.exists():
            return ()
        if root.is_file():
            return (root,)
        return (p for p in root.rglob("*") if p.is_file())

    def _skip(self, path: Path) -> bool:
        if path.suffix.lower() in self.SKIP_SUFFIXES:
            return True
        lowered_parts = [part.lower() for part in path.parts]
        parts = set(lowered_parts)
        if "pending_sync" in parts or "server_sync" in parts or "__pycache__" in parts:
            return True
        # PTT runtime state is client-local authority.  Neither microphone
        # captures nor hid_mapping.json belong to historical server migration.
        # Migrating hid_mapping.json as a historical_log caused retention to
        # delete the live mapping after verified sync, forcing recalibration.
        if "ptt" in parts and "logs" in parts:
            return True
        return False

    def _candidates(self) -> list[MigrationCandidate]:
        out: list[MigrationCandidate] = []

        recordings = self.storage.local_path("recordings")
        for source in self._iter_files(recordings):
            if self._skip(source):
                continue
            rel = _safe_rel(source, recordings)
            if source.suffix.lower() == ".areplay":
                out.append(MigrationCandidate(source, "recordings", "replay", Path("data/replays") / rel, True))
            else:
                out.append(MigrationCandidate(source, "recordings", "recording", Path("data/recordings") / rel, True))

        roots = (
            (self.storage.local_path("validation"), "validation", "validation", Path("data/validation")),
            (self.storage.local_path("logs"), "logs", "historical_log", Path("data/logs")),
            (self.storage.local_path("exports"), "exports", "export", Path("data/exports")),
            (self.storage.local_path("backups"), "backups", "backup", Path("backups/client_data") / self.hostname),
        )
        for root, category, source_class, remote_root in roots:
            for source in self._iter_files(root):
                if self._skip(source):
                    continue
                out.append(MigrationCandidate(source, category, source_class, remote_root / _safe_rel(source, root), False))

        # Legacy export/backup/log roots can still exist on upgraded installs.
        legacy_roots = (
            (self.storage.project_root / "exports", "exports", "export", Path("data/exports/legacy")),
            (self.storage.project_root / "backups", "backups", "backup", Path("backups/client_data") / self.hostname / "legacy"),
            (self.storage.project_root / "logs", "logs", "historical_log", Path("data/logs/legacy")),
        )
        for root, category, source_class, remote_root in legacy_roots:
            # If project_root/logs is also the local root through a custom layout,
            # the resolved-path de-duplication below prevents duplicate queueing.
            for source in self._iter_files(root):
                if self._skip(source):
                    continue
                out.append(MigrationCandidate(source, category, source_class, remote_root / _safe_rel(source, root), False))

        dedup: dict[str, MigrationCandidate] = {}
        for item in out:
            try:
                key = str(item.source.resolve())
            except OSError:
                key = str(item.source.absolute())
            dedup.setdefault(key, item)
        return sorted(dedup.values(), key=lambda item: str(item.source).lower())

    def _is_stable(self, candidate: MigrationCandidate, now: float) -> bool:
        if not candidate.require_stable:
            return True
        try:
            return (now - candidate.source.stat().st_mtime) >= self.recording_stable_age_s
        except OSError:
            return False

    def scan_and_queue(self, *, force: bool = False) -> dict[str, Any]:
        """Queue historical files for verified S6 transport.

        `stage_payload=False` is intentional for S7. Historical sources are stable
        local files and can be read directly by the background worker, avoiding a
        second multi-GB local copy before upload. They are never deleted by S7.
        """
        self.storage.ensure_layout()
        ownership = SyncOwnershipLock(self.storage.server_sync_root / "sync_owner.lock", operation="bulk_migration")
        if not ownership.acquire(timeout_s=0.0):
            owner = ownership.owner or {}
            return {
                "state": "SYNC_BUSY", "scanned": 0, "queued": 0,
                "skipped_active": 0, "skipped_known": 0, "errors": 0, "bytes_queued": 0,
                "owner": {"pid": owner.get("pid"), "hostname": owner.get("hostname"), "operation": owner.get("operation")},
            }
        try:
            state = self._load_state()
            tracked: dict[str, Any] = state["files"]
            now = time.time()
            scanned = queued = skipped_active = skipped_known = errors = 0
            bytes_queued = 0

            for candidate in self._candidates():
                scanned += 1
                source = candidate.source
                try:
                    stat = source.stat()
                    key = str(source.resolve())
                except OSError:
                    errors += 1
                    continue

                if not force and not self._is_stable(candidate, now):
                    skipped_active += 1
                    continue

                remote = candidate.remote_relpath.as_posix()
                previous = tracked.get(key) if isinstance(tracked.get(key), dict) else None
                unchanged = bool(
                    previous
                    and int(previous.get("size_bytes", -1)) == stat.st_size
                    and int(previous.get("mtime_ns", -1)) == stat.st_mtime_ns
                    and str(previous.get("remote_relpath") or "") == remote
                )
                if unchanged and not force:
                    skipped_known += 1
                    continue

                try:
                    # Replays/recordings are large and are only queued after the
                    # stability window, so they may safely upload directly.  Small
                    # historical artifacts (logs/validation/exports/backups) can
                    # still be appended/replaced while the app is running; stage an
                    # immutable snapshot so their manifest cannot become stale.
                    stage_payload = candidate.source_class not in {"replay", "recording"}
                    queued_location = self.storage.queue_upload(
                        source,
                        category=candidate.category,
                        remote_relpath=remote,
                        stage_payload=stage_payload,
                        metadata={
                            "kind": "bulk_migration",
                            "migration_version": MIGRATION_VERSION,
                            "source_class": candidate.source_class,
                            "retain_local": candidate.source_class in {"replay", "recording"},
                            "cleanup_policy": ("keep_recent_recordings" if candidate.source_class in {"replay", "recording"} else "delete_after_verified_sync"),
                            "queued_at_utc": _utc_now(),
                        },
                    )
                    tracked[key] = {
                        "source": str(source),
                        "source_class": candidate.source_class,
                        "category": candidate.category,
                        "remote_relpath": remote,
                        "size_bytes": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                        "queue_manifest": str(queued_location.path),
                        "queued_at_utc": _utc_now(),
                        "retain_local": candidate.source_class in {"replay", "recording"},
                        "cleanup_policy": ("keep_recent_recordings" if candidate.source_class in {"replay", "recording"} else "delete_after_verified_sync"),
                    }
                    queued += 1
                    bytes_queued += stat.st_size
                except (OSError, ValueError, KeyError):
                    errors += 1

            state["files"] = tracked
            state["last_scan_utc"] = _utc_now()
            state["last_scan"] = {
                "scanned": scanned,
                "queued": queued,
                "skipped_active": skipped_active,
                "skipped_known": skipped_known,
                "errors": errors,
                "bytes_queued": bytes_queued,
            }
            self._save_state(state)
            return dict(state["last_scan"])
        finally:
            ownership.release()


    @staticmethod
    def _recording_key(path: Path) -> str:
        name=path.name
        low=name.lower()
        if low.endswith(".areplay.json"):
            return name[:-len(".areplay.json")]
        if low.endswith(".areplay"):
            return name[:-len(".areplay")]
        return path.stem

    @staticmethod
    def _is_ptt_runtime_path(path: Path) -> bool:
        parts = {part.lower() for part in path.parts}
        return "logs" in parts and "ptt" in parts

    def apply_local_retention(self, share_root: Path | None, *, keep_recent_recordings: int = 10, _ownership_held: bool = False) -> dict[str, Any]:
        """Remove only local files whose server copies are already verified.

        S6 removes a pending manifest only after size+SHA256 verification.  For
        historical files migrated by older builds, this method additionally
        requires the remote object to exist with the tracked size and the local
        file to still match the exact tracked size/mtime before deletion.
        """
        ownership = None
        if not _ownership_held:
            ownership = SyncOwnershipLock(self.storage.server_sync_root / "sync_owner.lock", operation="retention")
            if not ownership.acquire(timeout_s=0.0):
                owner = ownership.owner or {}
                return {
                    "state": "SYNC_BUSY", "deleted_files": 0, "deleted_bytes": 0,
                    "recording_sessions_removed": 0, "kept_recording_sessions": 0, "errors": 0,
                    "owner": {"pid": owner.get("pid"), "hostname": owner.get("hostname"), "operation": owner.get("operation")},
                }
        try:
            result={"deleted_files":0,"deleted_bytes":0,"recording_sessions_removed":0,"kept_recording_sessions":0,"errors":0}
            if share_root is None:
                return result
            try:
                if not share_root.is_dir():
                    return result
            except OSError:
                return result
            state=self._load_state(); tracked=state.get("files") if isinstance(state.get("files"),dict) else {}
            pending_sources=set()
            for item in self.storage.pending_items():
                meta=item.get("metadata") if isinstance(item.get("metadata"),dict) else {}
                if meta.get("kind") != "bulk_migration":
                    continue
                try: pending_sources.add(str(Path(str(item.get("source") or "")).resolve()))
                except OSError: pending_sources.add(str(item.get("source") or ""))

            def verified(item):
                source=Path(str(item.get("source") or "")); remote_rel=str(item.get("remote_relpath") or "").replace("\\","/")
                if not source.is_file() or not remote_rel:
                    return False
                try:
                    if str(source.resolve()) in pending_sources: return False
                    st=source.stat()
                    if st.st_size != int(item.get("size_bytes") or -1) or st.st_mtime_ns != int(item.get("mtime_ns") or -1): return False
                    remote=share_root/Path(*[x for x in remote_rel.split("/") if x not in {"",".",".."}])
                    return remote.is_file() and remote.stat().st_size == st.st_size
                except OSError:
                    return False

            # PTT runtime files are always client-local.  Older builds may have
            # already tracked hid_mapping.json as a historical log; forget those
            # stale retention entries so a future idle pass cannot delete it.
            for key, item in list(tracked.items()):
                if not isinstance(item, dict):
                    continue
                source = Path(str(item.get("source") or ""))
                if self._is_ptt_runtime_path(source):
                    tracked.pop(key, None)

            # Small historical artifacts are server-master after verified transfer.
            immediate={"validation","historical_log","export","backup"}
            for key,item in list(tracked.items()):
                if not isinstance(item,dict) or item.get("source_class") not in immediate or not verified(item):
                    continue
                source=Path(str(item.get("source") or ""))
                if self._is_ptt_runtime_path(source):
                    continue
                try:
                    size=source.stat().st_size; source.unlink()
                    item["local_retained"]=False; item["local_deleted_at_utc"]=_utc_now(); item["retention_action"]="delete_after_verified_sync"
                    result["deleted_files"]+=1; result["deleted_bytes"]+=size
                except OSError:
                    result["errors"]+=1

            # Replays/sidecars: keep the newest N complete recording sessions local.
            groups={}
            for key,item in tracked.items():
                if not isinstance(item,dict) or item.get("source_class") not in {"replay","recording"}: continue
                source=Path(str(item.get("source") or ""))
                if not source.is_file(): continue
                g=(str(source.parent).lower(),self._recording_key(source).lower())
                groups.setdefault(g,[]).append((key,item,source))
            ordered=[]
            for g,items in groups.items():
                newest=max(int(it[1].get("mtime_ns") or 0) for it in items)
                ordered.append((newest,g,items))
            ordered.sort(reverse=True,key=lambda x:x[0])
            keep=max(0,int(keep_recent_recordings)); result["kept_recording_sessions"]=min(keep,len(ordered))
            for _,g,items in ordered[keep:]:
                if not all(verified(item) for _,item,_ in items):
                    continue
                removed_any=False
                for key,item,source in items:
                    try:
                        size=source.stat().st_size; source.unlink(); removed_any=True
                        item["local_retained"]=False; item["local_deleted_at_utc"]=_utc_now(); item["retention_action"]="keep_latest_10_sessions"
                        result["deleted_files"]+=1; result["deleted_bytes"]+=size
                    except OSError:
                        result["errors"]+=1
                if removed_any: result["recording_sessions_removed"]+=1
            state["files"]=tracked; state["last_retention_utc"]=_utc_now(); state["last_retention"]=result
            state["retention_policy"]={"recording_sessions_local":keep,"validation":"server_only","historical_logs":"server_only","exports":"server_only","backups":"server_only"}
            self._save_state(state)
            return result
        finally:
            if ownership is not None:
                ownership.release()

    def status(self) -> dict[str, Any]:
        state = self._load_state()
        files = state.get("files") if isinstance(state.get("files"), dict) else {}
        pending = [
            item for item in self.storage.pending_items()
            if isinstance(item.get("metadata"), dict) and item["metadata"].get("kind") == "bulk_migration"
        ]
        by_class: dict[str, int] = {}
        total_bytes = 0
        for item in files.values():
            if not isinstance(item, dict):
                continue
            cls = str(item.get("source_class") or "unknown")
            by_class[cls] = by_class.get(cls, 0) + 1
            total_bytes += int(item.get("size_bytes") or 0)
        return {
            "migration_version": MIGRATION_VERSION,
            "tracked_files": len(files),
            "tracked_bytes": total_bytes,
            "pending": len(pending),
            "by_class": by_class,
            "last_scan_utc": state.get("last_scan_utc"),
            "last_scan": state.get("last_scan") or {},
            "retention": "SERVER_MASTER_LOCAL_RETENTION",
            "retention_policy": state.get("retention_policy") or {"recording_sessions_local": 10, "validation": "server_only", "historical_logs": "server_only", "exports": "server_only", "backups": "server_only"},
            "last_retention_utc": state.get("last_retention_utc"),
            "last_retention": state.get("last_retention") or {},
        }
