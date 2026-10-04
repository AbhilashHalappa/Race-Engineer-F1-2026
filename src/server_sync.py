"""Server Roadmap S6: background sync and offline fallback.

This module is the *only* place in the S6 client that touches the server share.
It is deliberately detached from telemetry processing and runs on a daemon
thread.  Live writes remain local first.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any
import argparse
import json
import os
import shutil
import socket
import sqlite3
import tempfile
import time
import zipfile

from .storage_manager import DEFAULT_STORAGE, StorageManager, StorageState
from .bulk_migration import BulkDataMigrator
from .sync_lock import SyncOwnershipLock


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _default_share_root() -> Path | None:
    configured = (os.environ.get("RACE_ENGINEER_SERVER_SHARE") or "").strip()
    if configured:
        return Path(configured)
    if os.name == "nt":
        return Path("R:/")
    return None


@dataclass(frozen=True)
class ServerSyncConfig:
    share_root: Path | None = None
    interval_s: float = 30.0
    initial_delay_s: float = 12.0
    enabled: bool = True
    migration_interval_s: float = 300.0
    retention_interval_s: float = 1800.0
    background_batch_size: int = 64

    @classmethod
    def from_environment(cls) -> "ServerSyncConfig":
        enabled = (os.environ.get("RACE_ENGINEER_SERVER_SYNC", "1").strip().lower() not in {"0", "false", "off", "no"})
        try:
            interval = max(5.0, float(os.environ.get("RACE_ENGINEER_SERVER_SYNC_INTERVAL", "30")))
        except ValueError:
            interval = 30.0
        try:
            migration_interval = max(30.0, float(os.environ.get("RACE_ENGINEER_BULK_MIGRATION_INTERVAL", "300")))
        except ValueError:
            migration_interval = 300.0
        try:
            retention_interval = max(300.0, float(os.environ.get("RACE_ENGINEER_RETENTION_INTERVAL", "1800")))
        except ValueError:
            retention_interval = 1800.0
        try:
            batch_size = max(8, int(os.environ.get("RACE_ENGINEER_SYNC_BATCH_SIZE", "64")))
        except ValueError:
            batch_size = 64
        return cls(
            share_root=_default_share_root(), interval_s=interval, enabled=enabled,
            migration_interval_s=migration_interval, retention_interval_s=retention_interval,
            background_batch_size=batch_size,
        )


class LocalBackupBuilder:
    """Build a point-in-time ZIP of mutable local Race Engineer data."""

    LEGACY_MUTABLE = (
        "settings",
        "analysis",
        "recordings",
        "references",
        "references_uploaded",
    )

    def __init__(self, storage: StorageManager) -> None:
        self.storage = storage

    def _skip(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self.storage.project_root)
        except ValueError:
            return False
        parts = {p.lower() for p in rel.parts}
        if ".pytest_cache" in parts or "__pycache__" in parts:
            return True
        # Do not recursively back up the pending queue or prior local snapshots.
        normalized = "/".join(rel.as_posix().lower().split("/"))
        return (
            normalized.startswith("user_data/cache/pending_sync/")
            or normalized.startswith("user_data/cache/server_sync/backups/")
        )

    def _sqlite_snapshot(self, source: Path, temp_dir: Path) -> Path:
        target = temp_dir / source.name
        try:
            src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=2.0)
            dst = sqlite3.connect(target)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            return target
        except sqlite3.Error:
            # If SQLite cannot be opened (for example, zero-byte placeholder),
            # fall back to a byte copy; snapshot creation must remain best-effort.
            shutil.copy2(source, target)
            return target

    def create(self) -> Path:
        self.storage.ensure_layout()
        backup_dir = self.storage.server_sync_root / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        hostname = socket.gethostname() or "gaming-pc"
        output = backup_dir / f"RaceEngineer_local_backup_{hostname}_{_safe_stamp()}.zip"

        roots: list[Path] = [self.storage.local_root]
        for name in self.LEGACY_MUTABLE:
            candidate = self.storage.project_root / name
            if candidate.exists():
                roots.append(candidate)

        with tempfile.TemporaryDirectory(prefix="race_engineer_backup_") as temp_name:
            temp_dir = Path(temp_name)
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                manifest_entries: list[dict[str, Any]] = []
                seen: set[Path] = set()
                for root in roots:
                    if root.is_file():
                        files = [root]
                    else:
                        files = [p for p in root.rglob("*") if p.is_file()]
                    for source in files:
                        try:
                            resolved = source.resolve()
                        except OSError:
                            continue
                        if resolved in seen or self._skip(source):
                            continue
                        seen.add(resolved)
                        try:
                            arcname = source.relative_to(self.storage.project_root).as_posix()
                        except ValueError:
                            arcname = source.name
                        try:
                            if source.suffix.lower() in {".sqlite", ".sqlite3", ".db"} and source.stat().st_size > 0:
                                snap = self._sqlite_snapshot(source, temp_dir)
                                archive.write(snap, arcname)
                                size = snap.stat().st_size
                            else:
                                archive.write(source, arcname)
                                size = source.stat().st_size
                            manifest_entries.append({"path": arcname, "size_bytes": size})
                        except (OSError, sqlite3.Error):
                            continue

                backup_manifest = {
                    "backup_version": 1,
                    "created_at_utc": _utc_now(),
                    "hostname": hostname,
                    "project_root": str(self.storage.project_root),
                    "entry_count": len(manifest_entries),
                    "entries": manifest_entries,
                }
                archive.writestr("BACKUP_MANIFEST.json", json.dumps(backup_manifest, indent=2) + "\n")
        return output


class ServerSyncWorker:
    def __init__(
        self,
        storage: StorageManager = DEFAULT_STORAGE,
        config: ServerSyncConfig | None = None,
        *,
        create_initial_backup: bool = True,
        enable_bulk_migration: bool = True,
    ) -> None:
        self.storage = storage
        self.config = config or ServerSyncConfig.from_environment()
        self.create_initial_backup = create_initial_backup
        self.enable_bulk_migration = enable_bulk_migration
        self.bulk_migrator = BulkDataMigrator(storage)
        self._last_migration_scan_monotonic = 0.0
        # Stable V2 audit: None means no retention pass has run in this process.
        # Using 0.0 tied the first pass to OS uptime, so a freshly booted PC could
        # incorrectly skip the initial idle retention cycle for up to 30 minutes.
        self._last_retention_monotonic: float | None = None
        self._stop = Event()
        self._wake = Event()
        self._lock = Lock()
        self._thread: Thread | None = None

    @property
    def share_root(self) -> Path | None:
        return self.config.share_root

    def _write_state(self, **payload: Any) -> None:
        state = {
            "updated_at_utc": _utc_now(),
            "share_root": str(self.share_root) if self.share_root is not None else None,
            **payload,
        }
        self.storage._write_json_atomic(self.storage.sync_state_path, state)

    def status(self) -> dict[str, Any]:
        if not self.storage.sync_state_path.exists():
            return {
                "state": StorageState.LOCAL.value,
                "pending": len(self.storage.pending_items()),
                "share_root": str(self.share_root) if self.share_root is not None else None,
            }
        try:
            return json.loads(self.storage.sync_state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"state": StorageState.LOCAL.value, "pending": len(self.storage.pending_items())}

    def _share_available(self) -> bool:
        root = self.share_root
        if root is None:
            return False
        try:
            return root.is_dir()
        except OSError:
            return False

    def _remote_destination(self, item: dict[str, Any]) -> Path:
        assert self.share_root is not None
        explicit = str(item.get("remote_relpath") or "").strip().replace("\\", "/")
        if explicit:
            rel = Path(*[p for p in explicit.split("/") if p not in {"", ".", ".."}])
            return self.share_root / rel
        category = str(item.get("category") or "incoming")
        filename = str(item.get("filename") or Path(str(item.get("payload"))).name)
        return self.share_root / "incoming" / category / f"{item.get('id')}__{filename}"

    def _copy_verified(self, item: dict[str, Any]) -> Path:
        payload = Path(str(item.get("payload") or item.get("source") or ""))
        destination = self._remote_destination(item)
        destination.parent.mkdir(parents=True, exist_ok=True)

        # V2.9.1.3.2: a prior worker may already have verified/published the
        # remote object and removed the staged payload before a duplicate
        # manifest is encountered.  Accept the already-published object when it
        # still matches the manifest instead of failing forever on the missing
        # local payload.
        if not payload.is_file():
            expected_hash = str(item.get("sha256") or "")
            expected_size = int(item.get("size_bytes") or -1)
            try:
                if (
                    destination.is_file()
                    and expected_hash
                    and expected_size >= 0
                    and destination.stat().st_size == expected_size
                    and _hash_file(destination) == expected_hash
                ):
                    return destination
            except OSError:
                pass
            raise FileNotFoundError(f"Pending payload missing: {payload}")

        # S6 queue_version=2 staged payloads are immutable upload snapshots and
        # therefore authoritative for verification.  Older manifests could contain
        # a source hash/size captured just before a still-changing source was copied
        # into staging.  Repair those manifests from the staged bytes so an already
        # valid pending snapshot does not retry forever.  Direct-source S7 migration
        # entries remain strict: a changed source must not silently change identity.
        if bool(item.get("payload_staged", True)):
            expected_size = payload.stat().st_size
            expected_hash = str(item.get("sha256") or "")
            # queue_version=2 hashes immutable staged bytes when the snapshot is
            # created.  Re-hash only legacy/incomplete manifests; the remote temp
            # copy is still SHA256-verified before publish, so same-size local
            # corruption cannot be accepted.
            if int(item.get("queue_version") or 0) < 2 or not expected_hash or int(item.get("size_bytes") or -1) != expected_size:
                expected_hash = _hash_file(payload)
            if str(item.get("sha256") or "") != expected_hash or int(item.get("size_bytes") or -1) != expected_size:
                remote_text = str(item.get("remote_relpath") or "")
                category = str(item.get("category") or "incoming")
                fingerprint = sha256(f"{category}\0{expected_hash}\0{remote_text}".encode("utf-8")).hexdigest()
                manifest = item.get("manifest_path")
                if manifest:
                    self.storage.update_pending(
                        manifest,
                        sha256=expected_hash,
                        size_bytes=expected_size,
                        fingerprint=fingerprint,
                        repaired_staged_manifest_utc=_utc_now(),
                        last_error=None,
                    )
                    item["sha256"] = expected_hash
                    item["size_bytes"] = expected_size
                    item["fingerprint"] = fingerprint
        else:
            expected_hash = str(item.get("sha256") or _hash_file(payload))
            expected_size = int(item.get("size_bytes") or payload.stat().st_size)

        if destination.is_file():
            try:
                if destination.stat().st_size == expected_size and _hash_file(destination) == expected_hash:
                    return destination
            except OSError:
                pass

        temp = destination.with_name(destination.name + f".{item.get('id')}.part")
        shutil.copy2(payload, temp)
        if temp.stat().st_size != expected_size or _hash_file(temp) != expected_hash:
            try:
                temp.unlink()
            except OSError:
                pass
            raise IOError("Remote verification failed after copy")
        temp.replace(destination)
        # The temp object was hash+size verified on the remote share immediately
        # before the same-filesystem atomic rename.  Re-reading the published
        # destination over SMB doubled remote I/O for every small file.  A final
        # size check still catches publish/truncation failures without a second
        # network hash pass.
        if destination.stat().st_size != expected_size:
            raise IOError("Remote verification failed after atomic publish")
        return destination

    def ensure_initial_backup_queued(self, *, force: bool = False) -> Path | None:
        # V2.9.1.3.4: backup creation also adds a durable queue manifest, so it
        # must share the same cross-process ownership guard as S6/S7 mutation.
        ownership = SyncOwnershipLock(self.storage.server_sync_root / "sync_owner.lock", operation="backup_queue")
        if not ownership.acquire(timeout_s=0.0):
            return None
        try:
            marker = self.storage.initial_backup_marker
            if marker.exists() and not force:
                return None
            builder = LocalBackupBuilder(self.storage)
            snapshot = builder.create()
            hostname = socket.gethostname() or "gaming-pc"
            remote = Path("backups") / "client_snapshots" / hostname / snapshot.name
            queued = self.storage.queue_upload(
                snapshot,
                category="backups",
                remote_relpath=remote,
                metadata={
                    "kind": "current_local_data_backup",
                    "cleanup_source_after_sync": True,
                    "created_at_utc": _utc_now(),
                },
            )
            marker_payload = {
                "created_at_utc": _utc_now(),
                "snapshot": str(snapshot),
                "queue_manifest": str(queued.path),
                "remote_relpath": remote.as_posix(),
            }
            self.storage._write_json_atomic(marker, marker_payload)
            return snapshot
        finally:
            ownership.release()

    def _repair_or_prune_missing_payloads(self) -> dict[str, int]:
        """Recover durable queue manifests whose upload payload disappeared.

        Mutable S7 history uses staged snapshots.  If that cache file is lost
        but the original source still exists, create a fresh immutable snapshot
        and retire the broken manifest.  If both payload and original source are
        gone for a disposable historical class, the manifest is an orphan and
        can never succeed; retire it instead of retrying forever.  Replays and
        recordings remain strict because silently dropping those could lose the
        only durable copy.
        """
        mutable_classes = {"validation", "historical_log", "export", "backup"}
        restaged = 0
        remote_verified = 0
        orphan_pruned = 0

        for item in list(self.storage.pending_items()):
            payload = Path(str(item.get("payload") or item.get("source") or ""))
            if payload.is_file():
                continue

            # A duplicate/racing manifest may have lost its local payload only
            # after another worker already published the exact same bytes.
            destination = self._remote_destination(item) if self.share_root is not None else None
            expected_hash = str(item.get("sha256") or "")
            expected_size = int(item.get("size_bytes") or -1)
            try:
                if (
                    destination is not None
                    and destination.is_file()
                    and expected_hash
                    and expected_size >= 0
                    and destination.stat().st_size == expected_size
                    and _hash_file(destination) == expected_hash
                ):
                    self.storage.complete_pending(item)
                    remote_verified += 1
                    continue
            except OSError:
                pass

            meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            source_class = str(meta.get("source_class") or "")
            source = Path(str(item.get("source") or ""))

            if source_class in mutable_classes and source.is_file():
                try:
                    # Retire the broken manifest first so queue_upload() does not
                    # de-duplicate against its stale fingerprint and hand the same
                    # missing-payload manifest back to us.  The source itself is
                    # still present, so a fresh durable snapshot can be created.
                    self.storage.complete_pending(item)
                    self.storage.queue_upload(
                        source,
                        category=str(item.get("category") or "logs"),
                        remote_relpath=str(item.get("remote_relpath") or "") or None,
                        stage_payload=True,
                        metadata=dict(meta),
                    )
                    restaged += 1
                    continue
                except (OSError, ValueError, KeyError):
                    pass

            if source_class in mutable_classes and not source.is_file():
                # These are historical/cache-derived artifacts.  With neither a
                # payload nor an original source there is nothing left to send.
                # Retiring the impossible manifest is safer than an infinite
                # retry loop.
                self.storage.complete_pending(item)
                orphan_pruned += 1

        return {
            "restaged": restaged,
            "remote_verified": remote_verified,
            "orphan_pruned": orphan_pruned,
        }

    def _repair_and_compact_mutable_history(self) -> dict[str, int]:
        """Repair legacy S7 mutable entries and drop superseded snapshots.

        V2.9.1.3 correctly kept direct-source historical entries strict, but
        older S7 manifests for logs/validation/exports/backups can point at a
        source that changed after queueing.  Such entries can never verify.
        Convert only those small mutable historical classes to immutable staged
        snapshots, then retain only the newest pending snapshot per remote path.
        Replays/recordings remain direct-source and strict.
        """
        mutable_classes = {"validation", "historical_log", "export", "backup"}
        repaired = 0
        superseded = 0

        # First replace stale legacy direct-source manifests with a current
        # immutable snapshot.  queue_upload() de-duplicates identical content.
        for item in list(self.storage.pending_items()):
            meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            if meta.get("kind") != "bulk_migration" or meta.get("source_class") not in mutable_classes:
                continue
            if bool(item.get("payload_staged", True)):
                continue
            source = Path(str(item.get("source") or ""))
            if not source.is_file():
                continue
            try:
                current_size = source.stat().st_size
                current_hash = _hash_file(source)
            except OSError:
                continue
            if current_size == int(item.get("size_bytes") or -1) and current_hash == str(item.get("sha256") or ""):
                # Even unchanged legacy mutable items are staged now so they
                # cannot change between this check and the network copy.
                pass
            try:
                self.storage.queue_upload(
                    source,
                    category=str(item.get("category") or "logs"),
                    remote_relpath=str(item.get("remote_relpath") or "") or None,
                    stage_payload=True,
                    metadata=dict(meta),
                )
                self.storage.complete_pending(item)
                repaired += 1
            except (OSError, ValueError, KeyError):
                continue

        # Multiple snapshots can legitimately target the same remote object.
        # Only the newest one matters; uploading every older version wastes time
        # and can make the queue appear to refill while sync is running.
        pending = self.storage.pending_items()
        newest: dict[tuple[str, str], dict[str, Any]] = {}
        for item in pending:
            meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            if meta.get("kind") != "bulk_migration" or meta.get("source_class") not in mutable_classes:
                continue
            remote = str(item.get("remote_relpath") or "")
            if not remote:
                continue
            key = (str(item.get("category") or ""), remote)
            newest[key] = item  # pending_items() is chronological; last wins

        for item in pending:
            meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            if meta.get("kind") != "bulk_migration" or meta.get("source_class") not in mutable_classes:
                continue
            remote = str(item.get("remote_relpath") or "")
            if not remote:
                continue
            key = (str(item.get("category") or ""), remote)
            if newest.get(key) is item:
                continue
            self.storage.complete_pending(item)
            superseded += 1

        return {"repaired": repaired, "superseded": superseded}

    def run_once(self, *, max_items: int | None = None) -> dict[str, Any]:
        with self._lock:
            self.storage.ensure_layout()
            # V2.9.1.3.4: process-local Locks do not protect the queue from a
            # second Python process (for example the GUI plus `--sync-now`).
            # Take one atomic file ownership lock before *any* queue repair,
            # upload, completion or retention mutation.  A competing process
            # returns SYNC_BUSY without touching state or the queue.
            ownership = SyncOwnershipLock(self.storage.server_sync_root / "sync_owner.lock", operation="sync")
            if not ownership.acquire(timeout_s=0.0):
                return ownership.busy_result(len(self.storage.pending_items()))
            try:
                missing_payload_maintenance = self._repair_or_prune_missing_payloads()
                queue_maintenance = self._repair_and_compact_mutable_history()
                pending = self.storage.pending_items()
                if not self.config.enabled:
                    result = {"state": StorageState.LOCAL.value, "pending": len(pending), "attempted": 0, "synced": 0, "failed": 0, "reason": "disabled"}
                    self._write_state(**result)
                    return result
                if not self._share_available():
                    result = {"state": StorageState.OFFLINE_FALLBACK.value, "pending": len(pending), "attempted": 0, "synced": 0, "failed": 0}
                    self._write_state(**result)
                    return result

                attempted = synced = failed = 0
                work_items = pending if max_items is None else pending[:max(1, int(max_items))]
                for item in work_items:
                    attempted += 1
                    manifest = item.get("manifest_path")
                    attempts = int(item.get("attempts") or 0) + 1
                    try:
                        destination = self._copy_verified(item)
                        original = Path(str(item.get("source") or ""))
                        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                        self.storage.complete_pending(item)
                        if metadata.get("cleanup_source_after_sync") and original.is_file():
                            try:
                                original.unlink()
                            except OSError:
                                pass
                        synced += 1
                    except Exception as exc:  # background failure must never escape into live runtime
                        failed += 1
                        if manifest:
                            try:
                                self.storage.update_pending(
                                    manifest,
                                    attempts=attempts,
                                    last_attempt_utc=_utc_now(),
                                    last_error=str(exc),
                                    state=StorageState.OFFLINE_FALLBACK.value,
                                )
                            except (OSError, ValueError):
                                pass

                remaining = len(self.storage.pending_items())

                # V2.9.1.3.5: retention is maintenance, not part of every transport
                # pass.  Running it while a historical backlog exists caused a
                # second full local/remote tree walk after each upload cycle.
                # Only run it when the queue is idle, and throttle it.
                now_mono = time.monotonic()
                retention = {"skipped": True, "reason": "queue_busy" if remaining else "interval"}
                if remaining == 0 and (self._last_retention_monotonic is None or (now_mono - self._last_retention_monotonic) >= self.config.retention_interval_s):
                    try:
                        retention = self.bulk_migrator.apply_local_retention(self.share_root, keep_recent_recordings=10, _ownership_held=True)
                    except Exception as exc:
                        retention = {"errors": 1, "last_error": str(exc)}
                    self._last_retention_monotonic = now_mono

                state = StorageState.REMOTE.value if remaining == 0 and failed == 0 else (StorageState.PENDING_SYNC.value if self._share_available() else StorageState.OFFLINE_FALLBACK.value)
                result = {"state": state, "pending": remaining, "attempted": attempted, "synced": synced, "failed": failed}
                self._write_state(**result)
                return result
            finally:
                ownership.release()
    def _loop(self) -> None:
        if self._stop.wait(max(0.0, self.config.initial_delay_s)):
            return
        if self.create_initial_backup:
            try:
                self.ensure_initial_backup_queued()
            except Exception as exc:
                self._write_state(state=StorageState.OFFLINE_FALLBACK.value, pending=len(self.storage.pending_items()), attempted=0, synced=0, failed=1, last_error=f"backup: {exc}")
        while not self._stop.is_set():
            pending_before = self.storage.pending_items()
            # V2.9.1.3.5: never rescan the complete historical tree while an
            # existing queue is still draining.  This removes repeated rglob/stat
            # work and prevents already-busy sync cycles from discovering more
            # history before they can finish the current batch.
            if self.enable_bulk_migration and not pending_before:
                now_mono = time.monotonic()
                if (now_mono - self._last_migration_scan_monotonic) >= self.config.migration_interval_s:
                    try:
                        self.bulk_migrator.scan_and_queue()
                    except Exception as exc:
                        self._write_state(
                            state=StorageState.OFFLINE_FALLBACK.value if not self._share_available() else StorageState.PENDING_SYNC.value,
                            pending=len(self.storage.pending_items()), attempted=0, synced=0, failed=1,
                            last_error=f"bulk_migration: {exc}",
                        )
                    self._last_migration_scan_monotonic = now_mono

            result = self.run_once(max_items=self.config.background_batch_size)
            self._wake.clear()
            # Drain backlogs continuously in bounded batches; use the normal
            # interval only when idle.  This keeps UI/status updates responsive
            # without inserting a 30 s pause between small-file batches.
            wait_s = 0.25 if int(result.get("pending") or 0) > 0 and result.get("state") != "SYNC_BUSY" else self.config.interval_s
            self._wake.wait(wait_s)

    def start(self) -> "ServerSyncWorker":
        if self._thread is not None and self._thread.is_alive():
            return self
        self._thread = Thread(target=self._loop, name="RaceEngineerServerSync", daemon=True)
        self._thread.start()
        return self

    def wake(self) -> None:
        self._wake.set()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)


_DEFAULT_WORKER: ServerSyncWorker | None = None


def start_default_sync_worker() -> ServerSyncWorker:
    global _DEFAULT_WORKER
    if _DEFAULT_WORKER is None:
        _DEFAULT_WORKER = ServerSyncWorker().start()
    return _DEFAULT_WORKER


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Race Engineer S6/S7 server sync and bulk migration utility")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--sync-now", action="store_true")
    parser.add_argument("--backup-now", action="store_true")
    parser.add_argument("--migrate-now", action="store_true")
    parser.add_argument("--migration-status", action="store_true")
    parser.add_argument("--retention-now", action="store_true")
    args = parser.parse_args()
    worker = ServerSyncWorker(create_initial_backup=False, enable_bulk_migration=False)
    if args.backup_now:
        path = worker.ensure_initial_backup_queued(force=True)
        print(json.dumps({"backup": str(path) if path else None, "pending": len(worker.storage.pending_items())}, indent=2))
    if args.migrate_now:
        scan = worker.bulk_migrator.scan_and_queue()
        sync = worker.run_once()
        print(json.dumps({"scan": scan, "sync": sync, "migration": worker.bulk_migrator.status()}, indent=2))
    if args.sync_now:
        print(json.dumps(worker.run_once(), indent=2))
    if args.migration_status:
        print(json.dumps(worker.bulk_migrator.status(), indent=2))
    if args.retention_now:
        print(json.dumps(worker.bulk_migrator.apply_local_retention(worker.share_root, keep_recent_recordings=10), indent=2))
    if args.status or not (args.backup_now or args.sync_now or args.migrate_now or args.migration_status or args.retention_now):
        print(json.dumps(worker.status(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
