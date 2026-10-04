"""Race Engineer local-first storage abstraction (Server Roadmap S5/S6).

The live application always writes locally first.  S6 adds a durable pending
queue that stages immutable payload copies on local disk.  Remote/network I/O
is intentionally implemented in :mod:`src.server_sync`, not here, so telemetry
critical modules never acquire a LAN dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import os
import shutil
import time
import uuid


class StorageState(str, Enum):
    LOCAL = "LOCAL"
    CACHED = "CACHED"
    REMOTE = "REMOTE"
    PENDING_SYNC = "PENDING_SYNC"
    OFFLINE_FALLBACK = "OFFLINE_FALLBACK"


@dataclass(frozen=True)
class StorageLocation:
    path: Path
    state: StorageState = StorageState.LOCAL
    category: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class StorageManager:
    """Single owner for Race Engineer mutable storage locations."""

    CATEGORIES = (
        "performance",
        "sessions",
        "recordings",
        "tracks",
        "references",
        "diagnostics",
        "validation",
        "logs",
        "cache",
        "drivers",
        "exports",
        "backups",
    )

    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        local_root: str | Path | None = None,
        server_url: str | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        self.local_root = Path(local_root) if local_root is not None else self.project_root / "user_data"
        self.server_url = (server_url or os.environ.get("RACE_ENGINEER_SERVER_URL") or "").strip() or None

        # Compatibility-owned path.  S5/S6 centralise it but intentionally do
        # not migrate the authoritative LIVE DB; historical migration is S9.
        self.performance_history_db = self.project_root / "analysis" / "performance_history_live.sqlite3"

        self.pending_root = self.local_root / "cache" / "pending_sync"
        self.pending_payload_root = self.pending_root / "payloads"
        self.server_sync_root = self.local_root / "cache" / "server_sync"
        self.sync_state_path = self.server_sync_root / "state.json"
        self.initial_backup_marker = self.server_sync_root / "initial_backup.json"

    def local_path(self, category: str, *parts: str | Path) -> Path:
        if category not in self.CATEGORIES:
            raise KeyError(f"Unknown storage category: {category}")
        path = self.local_root / category
        for part in parts:
            path = path / Path(part)
        return path

    def location(
        self,
        category: str,
        *parts: str | Path,
        state: StorageState = StorageState.LOCAL,
    ) -> StorageLocation:
        return StorageLocation(self.local_path(category, *parts), state=state, category=category)

    def ensure_layout(self) -> None:
        for category in self.CATEGORIES:
            self.local_path(category).mkdir(parents=True, exist_ok=True)
        (self.local_path("tracks") / "maps").mkdir(parents=True, exist_ok=True)
        (self.local_path("references") / "uploaded").mkdir(parents=True, exist_ok=True)
        (self.local_path("sessions") / "reports").mkdir(parents=True, exist_ok=True)
        (self.local_path("sessions") / "replay_index").mkdir(parents=True, exist_ok=True)
        (self.local_path("validation") / "bundles").mkdir(parents=True, exist_ok=True)
        (self.local_path("validation") / "corner_coach").mkdir(parents=True, exist_ok=True)
        (self.local_path("validation") / "transcripts").mkdir(parents=True, exist_ok=True)
        (self.local_path("logs") / "ptt").mkdir(parents=True, exist_ok=True)
        (self.local_path("logs") / "crash").mkdir(parents=True, exist_ok=True)
        self.pending_payload_root.mkdir(parents=True, exist_ok=True)
        self.server_sync_root.mkdir(parents=True, exist_ok=True)

    def get_track_map(self, name: str | Path | None = None) -> Path:
        root = self.local_path("tracks") / "maps"
        return root if name is None else root / Path(name).name

    def get_reference(self, name: str | Path | None = None) -> Path:
        root = self.local_path("references")
        return root if name is None else root / Path(name)

    def recording_path(self, name: str | Path | None = None) -> Path:
        root = self.local_path("recordings")
        return root if name is None else root / Path(name).name

    def session_path(self, name: str | Path | None = None) -> Path:
        root = self.local_path("sessions")
        return root if name is None else root / Path(name)

    def performance_path(self, name: str | Path | None = None) -> Path:
        root = self.local_path("performance")
        return root if name is None else root / Path(name)

    @staticmethod
    def _write_json_atomic(path: Path, payload: Any) -> Path:
        """Write JSON safely even when multiple Windows threads update one file.

        Older builds reused a single ``.tmp`` pathname.  Two background writers
        could therefore replace/delete the same temp file and Windows would
        raise ``PermissionError: [WinError 5]``.  Each writer now gets a unique
        temp path and replacement is retried briefly for transient antivirus /
        file-indexer locks.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n"
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(text, encoding="utf-8")
        try:
            last_error = None
            for delay in (0.0, 0.01, 0.03, 0.08, 0.15):
                if delay:
                    time.sleep(delay)
                try:
                    os.replace(tmp, path)
                    return path
                except PermissionError as exc:
                    last_error = exc
            # Last-resort non-atomic fallback keeps the platform worker alive if
            # Windows temporarily refuses replacement of the destination file.
            path.write_text(text, encoding="utf-8")
            return path
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

    def save_session(self, name: str | Path, payload: Any) -> StorageLocation:
        path = self.session_path(name)
        self._write_json_atomic(path, payload)
        return StorageLocation(path, StorageState.LOCAL, "sessions")

    def save_performance(self, name: str | Path, payload: Any) -> StorageLocation:
        path = self.performance_path(name)
        self._write_json_atomic(path, payload)
        return StorageLocation(path, StorageState.LOCAL, "performance")

    def save_recording(self, name: str | Path, data: bytes) -> StorageLocation:
        path = self.recording_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StorageLocation(path, StorageState.LOCAL, "recordings")

    def _existing_fingerprint(self, fingerprint: str) -> StorageLocation | None:
        for item in self.pending_items():
            if item.get("fingerprint") == fingerprint:
                return StorageLocation(Path(item["manifest_path"]), StorageState.PENDING_SYNC, str(item.get("category", "")))
        return None

    def queue_upload(
        self,
        source: str | Path,
        *,
        category: str,
        metadata: dict[str, Any] | None = None,
        remote_relpath: str | Path | None = None,
        stage_payload: bool = True,
    ) -> StorageLocation:
        """Stage an immutable local copy and persist a durable S6 manifest.

        The original source remains authoritative and is never deleted here.
        The staged payload is what S6 uploads and later removes after verified
        server persistence, so a restart or source mutation cannot corrupt the
        pending operation.
        """
        if category not in self.CATEGORIES:
            raise KeyError(f"Unknown storage category: {category}")
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)

        self.ensure_layout()
        remote_text = str(remote_relpath).replace("\\", "/") if remote_relpath is not None else ""
        token = uuid.uuid4().hex
        suffix = source_path.suffix or ".bin"
        if stage_payload:
            # Snapshot first, then fingerprint the immutable staged bytes.  Several
            # Race Engineer sources (validation transcripts, JSONL logs, track maps)
            # can change while queue_upload() is running.  Hashing the live source
            # before copying creates a manifest that can never verify against the
            # staged payload if the source changes in that tiny window.
            payload_path = self.pending_payload_root / f"{token}{suffix}"
            shutil.copy2(source_path, payload_path)
            digest = _sha256_file(payload_path)
            size = payload_path.stat().st_size
        else:
            # S7 historical migration may reference the stable local source directly
            # to avoid duplicating multi-gigabyte recordings on the gaming PC.
            payload_path = source_path
            digest = _sha256_file(source_path)
            size = source_path.stat().st_size

        fingerprint = sha256(f"{category}\0{digest}\0{remote_text}".encode("utf-8")).hexdigest()
        existing = self._existing_fingerprint(fingerprint)
        if existing is not None:
            if stage_payload and payload_path.is_file():
                try:
                    payload_path.unlink()
                except OSError:
                    pass
            return existing

        manifest = self.pending_root / f"{token}.json"
        payload = {
            "queue_version": 2,
            "id": token,
            "category": category,
            "source": str(source_path),
            "payload": str(payload_path),
            "payload_staged": bool(stage_payload),
            "filename": source_path.name,
            "size_bytes": size,
            "sha256": digest,
            "fingerprint": fingerprint,
            "remote_relpath": remote_text or None,
            "metadata": dict(metadata or {}),
            "state": StorageState.PENDING_SYNC.value,
            "created_at_utc": _utc_now(),
            "attempts": 0,
            "last_error": None,
        }
        self._write_json_atomic(manifest, payload)
        return StorageLocation(manifest, StorageState.PENDING_SYNC, category)

    def pending_items(self) -> list[dict[str, Any]]:
        if not self.pending_root.exists():
            return []
        items: list[dict[str, Any]] = []
        for path in self.pending_root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if isinstance(payload, dict):
                payload = dict(payload)
                payload["manifest_path"] = str(path)
                items.append(payload)
        # Process oldest snapshots first so duplicate mutable destinations finish
        # with the newest queued state rather than UUID filename order.
        items.sort(key=lambda item: (str(item.get("created_at_utc") or ""), str(item.get("manifest_path") or "")))
        return items

    def update_pending(self, manifest_path: str | Path, **changes: Any) -> None:
        path = Path(manifest_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid pending manifest: {path}")
        payload.update(changes)
        self._write_json_atomic(path, payload)

    def complete_pending(self, item: dict[str, Any]) -> None:
        payload_path = Path(str(item.get("payload") or ""))
        manifest_path = Path(str(item.get("manifest_path") or ""))
        # Only S6 immutable staging payloads are disposable. S7 migration
        # manifests can point directly at retained historical source files.
        if bool(item.get("payload_staged", True)) and payload_path.is_file():
            try:
                payload_path.unlink()
            except OSError:
                pass
        if manifest_path.is_file():
            try:
                manifest_path.unlink()
            except OSError:
                pass

    def sync_pending(self) -> dict[str, Any]:
        """Compatibility status method; remote work is owned by server_sync."""
        pending = self.pending_items()
        return {
            "state": StorageState.PENDING_SYNC.value if pending else StorageState.LOCAL.value,
            "pending": len(pending),
            "attempted": 0,
            "server_url": self.server_url,
            "sync_enabled": False,
            "reason": "StorageManager performs no remote I/O; S6 background sync is owned by server_sync.",
        }

    def manifest(self) -> dict[str, Any]:
        pending = self.pending_items()
        return {
            "state": StorageState.PENDING_SYNC.value if pending else StorageState.LOCAL.value,
            "local_root": str(self.local_root),
            "server_url": self.server_url,
            "sync_enabled": True,
            "paths": {category: str(self.local_path(category)) for category in self.CATEGORIES},
            "performance_history_db": str(self.performance_history_db),
            "pending_sync": str(self.pending_root),
            "pending_count": len(pending),
        }


DEFAULT_STORAGE = StorageManager()
