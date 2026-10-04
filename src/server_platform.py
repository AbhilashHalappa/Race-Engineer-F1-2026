"""Race Engineer consolidated server platform integration (Server Roadmap S8-S14).

The gaming PC remains authoritative for live processing.  This module runs only
in background threads and uses local/cache-first semantics.  It mirrors the
persistent historical data set to race-server, refreshes reference/track masters,
and publishes a safe SQLite snapshot for the server-side Performance Hub.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
import json
import os
import shutil
import socket
import sqlite3
import tempfile
import time
import zipfile
import tarfile
import re

from .storage_manager import DEFAULT_STORAGE, StorageManager, StorageState
from .driver_retention import DriverDeletionJournal
from .sync_lock import SyncOwnershipLock


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(path: Path, chunk: int = 1024 * 1024) -> str:
    h = sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class ServerPlatformConfig:
    api_url: str
    share_root: Path | None
    interval_s: float = 10.0
    timeout_s: float = 3.0

    @classmethod
    def from_environment(cls) -> "ServerPlatformConfig":
        api = (os.environ.get("RACE_ENGINEER_SERVER_API") or "http://192.168.1.21:8765").rstrip("/")
        raw_share = os.environ.get("RACE_ENGINEER_SERVER_SHARE", "R:\\")
        return cls(api_url=api, share_root=Path(raw_share) if raw_share else None)


class ServerApiClient:
    def __init__(self, config: ServerPlatformConfig | None = None) -> None:
        self.config = config or ServerPlatformConfig.from_environment()

    def _json(self, path: str, *, method: str = "GET", body: bytes | None = None,
              content_type: str = "application/json", timeout: float | None = None) -> Any:
        req = Request(self.config.api_url + path, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", content_type)
        with urlopen(req, timeout=timeout or self.config.timeout_s) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def health(self) -> dict[str, Any]:
        try:
            data = self._json("/api/health")
            if isinstance(data, dict):
                return data
        except Exception as exc:
            return {"status": "offline", "error": str(exc)}
        return {"status": "offline"}

    def put_snapshot(self, kind: str, source: Path, *, sha256_hex: str | None = None) -> dict[str, Any]:
        payload = source.read_bytes()
        safe_kind = kind.replace("/", "_")
        req = Request(self.config.api_url + f"/api/snapshots/{safe_kind}", data=payload, method="PUT")
        req.add_header("Content-Type", "application/octet-stream")
        req.add_header("X-Race-Engineer-SHA256", sha256_hex or sha256(payload).hexdigest())
        req.add_header("X-Race-Engineer-Source", socket.gethostname() or "gaming-pc")
        with urlopen(req, timeout=max(15.0, self.config.timeout_s)) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}


    def trigger_backup(self) -> dict[str, Any]:
        try:
            data = self._json("/api/backup", method="POST", timeout=max(5.0, self.config.timeout_s))
            return data if isinstance(data, dict) else {"status": "unknown"}
        except Exception as exc:
            return {"status": "offline", "error": str(exc)}

    def soft_delete_profile_driver(self, driver_id: str, tombstone: dict[str, Any]) -> dict[str, Any]:
        body=json.dumps({k:v for k,v in tombstone.items() if k != "journal_path"}).encode("utf-8")
        return self._json(f"/api/profile-drivers/{driver_id}/delete", method="POST", body=body, timeout=max(10.0,self.config.timeout_s))

    @property
    def performance_hub_url(self) -> str:
        return self.config.api_url + "/performance-hub"


_BACKUP_STAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")


def _backup_stamp_from_name(name: str) -> str | None:
    match = re.search(r"_(\d{8}T\d{6}Z)(?:\.sqlite3|\.tar\.gz)$", str(name or ""))
    return match.group(1) if match else None


def _backup_stamp_label(stamp: str) -> str:
    try:
        dt = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        return stamp


class ServerBackupRestoreManager:
    """One-click recovery from verified backups stored on the server share.

    The restore source is the existing S12 automated backup directory on the
    mapped server share.  The manager first creates a local rollback snapshot,
    validates the selected SQLite database, atomically replaces local persistent
    performance/profile data, then republishes the restored state through the
    existing verified S9 API path.  No shell commands or direct server DB writes
    are required from the user.
    """

    def __init__(self, storage: StorageManager = DEFAULT_STORAGE,
                 config: ServerPlatformConfig | None = None,
                 api: ServerApiClient | None = None) -> None:
        self.storage = storage
        self.config = config or ServerPlatformConfig.from_environment()
        self.api = api or ServerApiClient(self.config)

    @property
    def backup_root(self) -> Path | None:
        root = self.config.share_root
        return (root / "backups" / "automated") if root is not None else None

    def list_recent(self, *, limit: int = 12) -> list[dict[str, Any]]:
        root = self.backup_root
        if root is None or not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for perf in root.glob("performance_history_live_*.sqlite3"):
            stamp = _backup_stamp_from_name(perf.name)
            if not stamp or not _BACKUP_STAMP_RE.match(stamp):
                continue
            drivers = root / f"drivers_{stamp}.tar.gz"
            server_db = root / f"race_engineer_{stamp}.sqlite3"
            try:
                size = int(perf.stat().st_size)
            except OSError:
                size = 0
            rows.append({
                "stamp": stamp,
                "label": _backup_stamp_label(stamp),
                "performance_db": str(perf),
                "performance_bytes": size,
                "driver_profiles": drivers.exists(),
                "server_database": server_db.exists(),
                "restorable": size > 0,
            })
        rows.sort(key=lambda row: str(row.get("stamp") or ""), reverse=True)
        return rows[:max(1, int(limit))]

    @staticmethod
    def _quick_check(path: Path) -> dict[str, Any]:
        con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=10.0)
        try:
            row = con.execute("PRAGMA quick_check").fetchone()
            if not row or str(row[0]).lower() != "ok":
                raise RuntimeError(f"SQLite quick_check failed: {row}")
            counts: dict[str, Any] = {"integrity": "ok"}
            tables = {str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if "sessions" in tables:
                counts["sessions"] = int(con.execute("SELECT count(*) FROM sessions").fetchone()[0])
            if "drivers" in tables:
                counts["drivers"] = int(con.execute("SELECT count(*) FROM drivers").fetchone()[0])
            return counts
        finally:
            con.close()

    @staticmethod
    def _sqlite_snapshot(source: Path, target: Path) -> None:
        if not source.is_file():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        src = sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True, timeout=10.0)
        dst = sqlite3.connect(str(target), timeout=10.0)
        try:
            src.backup(dst)
        finally:
            dst.close(); src.close()

    @staticmethod
    def _safe_extract_tar(archive: Path, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        with tarfile.open(archive, "r:gz") as tf:
            members = tf.getmembers()
            for member in members:
                candidate = (destination / member.name).resolve()
                if candidate != root and root not in candidate.parents:
                    raise RuntimeError("Unsafe path in driver-profile backup")
            tf.extractall(destination, filter="data")
        return destination / "drivers"

    def _create_local_rollback(self, stamp: str) -> Path:
        rollback = self.storage.local_path("backups") / f"pre_restore_{stamp}"
        rollback.mkdir(parents=True, exist_ok=True)
        self._sqlite_snapshot(self.storage.performance_history_db, rollback / "performance_history_live.sqlite3")
        drivers = self.storage.local_path("drivers")
        if drivers.exists() and not (rollback / "drivers").exists():
            shutil.copytree(drivers, rollback / "drivers")
        return rollback

    @staticmethod
    def _restore_sqlite_in_place(source: Path, target: Path, *, retries: int = 12, delay_s: float = 0.25) -> None:
        """Restore a SQLite backup without replacing the live DB file.

        On Windows the Control Center / embedded Performance Hub can keep a read
        handle open on Performance History.  os.replace() then fails with
        WinError 5 even though no live F1 session is running.  SQLite's native
        backup API is designed to copy into an existing database while other
        readers remain attached, so use it for the one-click restore path.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        last: Exception | None = None
        for _ in range(max(1, retries)):
            src = dst = None
            try:
                src = sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True, timeout=10.0)
                dst = sqlite3.connect(str(target), timeout=10.0)
                dst.execute("PRAGMA busy_timeout=10000")
                # Do not unlink -wal/-shm here: existing UI readers may own them.
                # The backup API commits the restored image through SQLite's own
                # locking/journal machinery and therefore remains Windows-safe.
                src.backup(dst, pages=256, sleep=0.05)
                dst.commit()
                dst.close(); dst = None
                src.close(); src = None
                check = ServerBackupRestoreManager._quick_check(target)
                if str(check.get("integrity") or "").lower() != "ok":
                    raise RuntimeError("Restored database failed SQLite quick_check")
                return
            except (OSError, sqlite3.Error, RuntimeError) as exc:
                last = exc
                try:
                    if dst is not None: dst.close()
                except Exception:
                    pass
                try:
                    if src is not None: src.close()
                except Exception:
                    pass
                time.sleep(delay_s)
        raise RuntimeError(f"Could not restore {target} through SQLite backup API: {last}")

    def restore(self, stamp: str) -> dict[str, Any]:
        stamp = str(stamp or "").strip()
        if not _BACKUP_STAMP_RE.match(stamp):
            raise ValueError("Invalid backup restore point")
        root = self.backup_root
        if root is None or not root.exists():
            raise FileNotFoundError("Server backup share is unavailable")
        perf_source = root / f"performance_history_live_{stamp}.sqlite3"
        drivers_source = root / f"drivers_{stamp}.tar.gz"
        if not perf_source.is_file():
            raise FileNotFoundError(f"Performance backup {stamp} is unavailable")

        guard = self.storage.server_sync_root / "restore_in_progress.json"
        self.storage.server_sync_root.mkdir(parents=True, exist_ok=True)
        platform = globals().get("_DEFAULT_PLATFORM")
        platform_lock = getattr(platform, "_lock", None) if platform is not None else None
        if platform_lock is not None:
            platform_lock.acquire()
        self.storage._write_json_atomic(guard, {"stamp": stamp, "started_at_utc": _utc_now()})
        rollback = self._create_local_rollback(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        try:
            with tempfile.TemporaryDirectory(prefix="race_engineer_restore_") as temp_name:
                temp = Path(temp_name)
                incoming = temp / "performance_history_live.sqlite3"
                shutil.copy2(perf_source, incoming)
                verified = self._quick_check(incoming)

                extracted_drivers: Path | None = None
                if drivers_source.is_file():
                    extracted_drivers = self._safe_extract_tar(drivers_source, temp / "profiles")
                    if not extracted_drivers.exists():
                        raise RuntimeError("Driver-profile backup is incomplete")

                target = self.storage.performance_history_db
                self._restore_sqlite_in_place(incoming, target)

                drivers_target = self.storage.local_path("drivers")
                if extracted_drivers is not None:
                    staged = drivers_target.with_name(f".{drivers_target.name}.restore.{os.getpid()}")
                    if staged.exists():
                        shutil.rmtree(staged, ignore_errors=True)
                    shutil.copytree(extracted_drivers, staged)
                    old = drivers_target.with_name(f".{drivers_target.name}.pre_restore.{os.getpid()}")
                    if old.exists():
                        shutil.rmtree(old, ignore_errors=True)
                    if drivers_target.exists():
                        os.replace(drivers_target, old)
                    os.replace(staged, drivers_target)
                    shutil.rmtree(old, ignore_errors=True)

            # Reconcile derived skill evidence against the restored authoritative
            # Performance History before publishing the restored profile tree.
            try:
                from .skill_evidence import SkillEvidenceStore
                SkillEvidenceStore().reconcile_with_performance_history()
            except Exception:
                pass

            performance_publish = PerformanceDatabasePublisher(self.storage, self.api).publish_if_changed(force=True)
            profile_publish = DriverProfilePublisher(self.storage, self.api).publish_if_changed(force=True)
            server_ok = performance_publish.get("status") == "published" and (not drivers_source.is_file() or profile_publish.get("status") == "published")
            return {
                "status": "restored" if server_ok else "restored_local_server_pending",
                "stamp": stamp,
                "label": _backup_stamp_label(stamp),
                "rollback": str(rollback),
                "verified": verified,
                "driver_profiles_restored": bool(drivers_source.is_file()),
                "server_performance": performance_publish.get("status"),
                "server_profiles": profile_publish.get("status"),
            }
        finally:
            try:
                guard.unlink(missing_ok=True)
            except OSError:
                pass
            if platform_lock is not None:
                try:
                    platform_lock.release()
                except RuntimeError:
                    pass


class ReferenceTrackMigrator:
    """S8: server master copies with retained local race-time cache."""
    def __init__(self, storage: StorageManager = DEFAULT_STORAGE) -> None:
        self.storage = storage
        self.registry_path = storage.server_sync_root / "s8_reference_track_registry.json"

    def _load(self) -> dict[str, Any]:
        try:
            return json.loads(self.registry_path.read_text(encoding="utf-8"))
        except Exception:
            return {"version": 1, "files": {}}

    def scan_and_queue(self) -> dict[str, Any]:
        self.storage.ensure_layout()
        ownership = SyncOwnershipLock(self.storage.server_sync_root / "sync_owner.lock", operation="reference_track_scan")
        if not ownership.acquire(timeout_s=0.0):
            owner = ownership.owner or {}
            return {"state": "SYNC_BUSY", "queued": 0, "skipped_known": 0, "by_class": {},
                    "owner": {"pid": owner.get("pid"), "hostname": owner.get("hostname"), "operation": owner.get("operation")}}
        try:
            registry = self._load(); known = registry.setdefault("files", {})
            queued = skipped = 0; by_class: dict[str, int] = {}
            roots = [
                (self.storage.local_path("references"), "reference", "data/references"),
                (self.storage.local_path("tracks"), "track", "data/track_maps"),
            ]
            for root, cls, remote_root in roots:
                if not root.exists():
                    continue
                for source in root.rglob("*"):
                    if not source.is_file() or "server_sync" in source.parts:
                        continue
                    try:
                        rel = source.relative_to(root).as_posix()
                        stat = source.stat()
                    except OSError:
                        continue
                    key = f"{cls}:{rel}"
                    sig = f"{stat.st_size}:{stat.st_mtime_ns}"
                    if known.get(key, {}).get("signature") == sig:
                        skipped += 1; continue
                    self.storage.queue_upload(
                        source,
                        category="references" if cls == "reference" else "tracks",
                        remote_relpath=f"{remote_root}/{rel}",
                        stage_payload=False,
                        metadata={"kind": "s8_master", "class": cls, "cache_policy": "server_master_local_cache"},
                    )
                    known[key] = {"signature": sig, "size_bytes": stat.st_size, "updated_at_utc": _utc_now()}
                    queued += 1; by_class[cls] = by_class.get(cls, 0) + 1
            registry["last_scan_utc"] = _utc_now(); registry["last_scan"] = {"queued": queued, "skipped_known": skipped, "by_class": by_class}
            self.storage._write_json_atomic(self.registry_path, registry)
            return registry["last_scan"]
        finally:
            ownership.release()

    def status(self) -> dict[str, Any]:
        r = self._load(); files = r.get("files", {})
        return {"tracked_files": len(files), "last_scan_utc": r.get("last_scan_utc"), "last_scan": r.get("last_scan", {}), "policy": "SERVER_MASTER_LOCAL_CACHE"}


class PerformanceDatabasePublisher:
    """S9/S10: publish verified, consistent performance-history snapshots to API.

    The active SQLite database is never placed on Samba.  sqlite3 backup creates
    an immutable local snapshot which is then sent via HTTP to the server-local DB.
    """
    def __init__(self, storage: StorageManager = DEFAULT_STORAGE, api: ServerApiClient | None = None) -> None:
        self.storage = storage; self.api = api or ServerApiClient()
        self.state_path = storage.server_sync_root / "s9_performance_publish.json"

    def _state(self) -> dict[str, Any]:
        try: return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception: return {}

    def publish_if_changed(self, *, force: bool = False) -> dict[str, Any]:
        source = self.storage.performance_history_db
        if not source.is_file() or source.stat().st_size <= 0:
            return {"status": "no_local_database"}
        sig = f"{source.stat().st_size}:{source.stat().st_mtime_ns}"
        state = self._state()
        if not force and state.get("source_signature") == sig and state.get("status") == "published":
            return state
        self.storage.server_sync_root.mkdir(parents=True, exist_ok=True)
        snap = self.storage.server_sync_root / "performance_history_server_snapshot.sqlite3"
        try:
            src = sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True, timeout=3.0)
            dst = sqlite3.connect(str(snap), timeout=3.0)
            try: src.backup(dst)
            finally: dst.close(); src.close()
            digest = _hash(snap)
            result = self.api.put_snapshot("performance_history.sqlite3", snap, sha256_hex=digest)
            out = {"status": "published", "published_at_utc": _utc_now(), "source_signature": sig,
                   "sha256": digest, "size_bytes": snap.stat().st_size, "server": result}
            self.storage._write_json_atomic(self.state_path, out)
            return out
        except Exception as exc:
            out = {"status": "offline_fallback", "last_error": str(exc), "source_signature": sig,
                   "updated_at_utc": _utc_now()}
            self.storage._write_json_atomic(self.state_path, out)
            return out

    def status(self) -> dict[str, Any]:
        return self._state() or {"status": "not_published"}


class DriverProfilePublisher:
    """S9: publish the complete Driver Profile tree as one verified snapshot.

    Local profiles remain the offline cache.  The server receives an atomic
    replacement of ``data/drivers`` and normalizes person-level identities into
    its own SQLite database.  A full-tree snapshot also propagates deletions
    without requiring a separate remote-delete queue.
    """
    def __init__(self, storage: StorageManager = DEFAULT_STORAGE, api: ServerApiClient | None = None) -> None:
        self.storage = storage
        self.api = api or ServerApiClient()
        self.state_path = storage.server_sync_root / "s9_driver_profiles_publish.json"

    @property
    def root(self) -> Path:
        return self.storage.local_path("drivers")

    def _state(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _tree_signature(self) -> tuple[str, int, int]:
        h = sha256(); count = 0; total = 0
        if not self.root.exists():
            return h.hexdigest(), 0, 0
        for path in sorted((p for p in self.root.rglob("*") if p.is_file()), key=lambda x: x.as_posix().lower()):
            try:
                rel = path.relative_to(self.root).as_posix()
                stat = path.stat()
            except OSError:
                continue
            h.update(rel.encode("utf-8")); h.update(b"\0")
            h.update(str(stat.st_size).encode("ascii")); h.update(b"\0")
            h.update(str(stat.st_mtime_ns).encode("ascii")); h.update(b"\n")
            count += 1; total += int(stat.st_size)
        return h.hexdigest(), count, total

    def publish_if_changed(self, *, force: bool = False) -> dict[str, Any]:
        signature, file_count, source_bytes = self._tree_signature()
        state = self._state()
        if not force and state.get("source_signature") == signature and state.get("status") == "published":
            return state
        self.storage.server_sync_root.mkdir(parents=True, exist_ok=True)
        archive = self.storage.server_sync_root / "driver_profiles_server_snapshot.zip"
        tmp = archive.with_name(f".{archive.name}.{os.getpid()}.{int(time.time()*1000)}.tmp")
        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                if self.root.exists():
                    for path in sorted((p for p in self.root.rglob("*") if p.is_file()), key=lambda x: x.as_posix().lower()):
                        zf.write(path, arcname=path.relative_to(self.root).as_posix())
            os.replace(tmp, archive)
            digest = _hash(archive)
            result = self.api.put_snapshot("driver_profiles.zip", archive, sha256_hex=digest)
            out = {
                "status": "published", "published_at_utc": _utc_now(),
                "source_signature": signature, "source_files": file_count,
                "source_bytes": source_bytes, "archive_bytes": archive.stat().st_size,
                "sha256": digest, "server": result,
                "policy": "SERVER_MASTER_LOCAL_CACHE",
            }
            self.storage._write_json_atomic(self.state_path, out)
            return out
        except Exception as exc:
            out = {
                "status": "offline_fallback", "last_error": str(exc),
                "source_signature": signature, "source_files": file_count,
                "source_bytes": source_bytes, "updated_at_utc": _utc_now(),
                "policy": "SERVER_MASTER_LOCAL_CACHE",
            }
            self.storage._write_json_atomic(self.state_path, out)
            return out
        finally:
            try: tmp.unlink(missing_ok=True)
            except Exception: pass

    def status(self) -> dict[str, Any]:
        return self._state() or {"status": "not_published", "policy": "SERVER_MASTER_LOCAL_CACHE"}


def _normalize_sync_display_state(health_status: str, transport_state: str, pending_files: int) -> str:
    """Return the authoritative sync state exposed to the UI.

    A local worker lock (SYNC_BUSY) only means another local process/thread owns
    the queue.  It must never imply a remote transfer when the API/server is
    offline.
    """
    health_online = str(health_status or "").lower() == "online"
    state = str(transport_state or StorageState.LOCAL.value).upper()
    pending_files = max(0, int(pending_files or 0))
    if not health_online:
        return StorageState.OFFLINE_FALLBACK.value
    if state == "SYNC_BUSY":
        return "SYNCING"
    if pending_files == 0 and state in {StorageState.REMOTE.value, StorageState.PENDING_SYNC.value, "SYNCING"}:
        return StorageState.REMOTE.value
    if pending_files and state == StorageState.REMOTE.value:
        return "SYNCING"
    return state


def _display_api_latency_ms(health_status: str, measured_ms: float) -> float | None:
    """Only expose latency for a successful API health response.

    Failed connection timeout duration is not a network ping and was previously
    shown as ~2000 ms while the server was intentionally offline.
    """
    if str(health_status or "").lower() != "online":
        return None
    return round(float(measured_ms), 2)


class ServerPlatformCoordinator:
    """Background-only S8-S14 coordinator."""
    def __init__(self, storage: StorageManager = DEFAULT_STORAGE, config: ServerPlatformConfig | None = None) -> None:
        self.storage = storage; self.config = config or ServerPlatformConfig.from_environment()
        self.api = ServerApiClient(self.config)
        self.s8 = ReferenceTrackMigrator(storage)
        self.s9 = PerformanceDatabasePublisher(storage, self.api)
        self.driver_profiles = DriverProfilePublisher(storage, self.api)
        self.driver_deletions = DriverDeletionJournal(storage)
        self.status_path = storage.server_sync_root / "platform_status.json"
        self._stop = Event(); self._wake = Event(); self._lock = Lock(); self._thread: Thread | None = None

    def run_once(self, *, force_performance: bool = False) -> dict[str, Any]:
        with self._lock:
            started = time.perf_counter()
            try: s8 = self.s8.scan_and_queue()
            except Exception as exc: s8 = {"error": str(exc)}
            api_started = time.perf_counter()
            health = self.api.health()
            api_latency_ms = (time.perf_counter() - api_started) * 1000.0
            # S13 acceptance hotfix: preserve only safe last-known backup metadata
            # across a temporary API outage. Do not make stale DB/storage health
            # look online; this is display continuity for a verified historical fact.
            if health.get("status") != "online":
                try:
                    previous = json.loads(self.status_path.read_text(encoding="utf-8"))
                except Exception:
                    previous = {}
                previous_api = previous.get("api") if isinstance(previous.get("api"), dict) else {}
                if previous_api.get("last_backup_utc"):
                    health["last_backup_utc"] = previous_api.get("last_backup_utc")
                    if isinstance(previous_api.get("backup"), dict):
                        health["backup"] = dict(previous_api.get("backup"))
                    health["backup_cached"] = True
                if not health.get("hostname") and previous_api.get("hostname"):
                    health["hostname"] = previous_api.get("hostname")
            deletion_results=[]
            if health.get("status") == "online":
                for tombstone in self.driver_deletions.entries(pending_only=True):
                    try:
                        response=self.api.soft_delete_profile_driver(str(tombstone.get("driver_id") or ""),tombstone)
                        self.driver_deletions.mark_synced(tombstone,response)
                        deletion_results.append({"driver_id":tombstone.get("driver_id"),"status":"server_retained"})
                    except Exception as exc:
                        deletion_results.append({"driver_id":tombstone.get("driver_id"),"status":"pending","error":str(exc)})
            pending_deletions=self.driver_deletions.pending_count()
            # Never publish the post-delete Performance DB or full Driver tree
            # until the server has safely retained every deletion tombstone.
            restore_guard = self.storage.server_sync_root / "restore_in_progress.json"
            if restore_guard.exists():
                s9={"status":"held_for_restore"}; driver_profiles={"status":"held_for_restore"}
            elif health.get("status") == "online" and pending_deletions == 0:
                s9 = self.s9.publish_if_changed(force=force_performance)
                driver_profiles = self.driver_profiles.publish_if_changed(force=force_performance)
            elif pending_deletions:
                s9={"status":"held_for_driver_retention","pending_driver_deletions":pending_deletions}
                driver_profiles={"status":"held_for_driver_retention","pending_driver_deletions":pending_deletions}
            else:
                s9={"status":"offline_fallback"}; driver_profiles={"status":"offline_fallback"}
            # V2.9.1.3.1: reuse the single process-wide S6 transport worker.
            # Creating a second ServerSyncWorker here allowed two independent
            # locks/threads to mutate the same pending queue concurrently while
            # the S7 migrator was also discovering files.  That produced status
            # such as hundreds synced but hundreds immediately pending again.
            from .server_sync import start_default_sync_worker
            try:
                transport_worker = start_default_sync_worker()
                transport = transport_worker.run_once()
            except Exception as exc:
                transport = {"state": StorageState.OFFLINE_FALLBACK.value, "error": str(exc)}
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            state = "ONLINE" if health.get("status") == "online" and transport.get("state") in {"REMOTE", "PENDING_SYNC", "SYNC_BUSY"} else "OFFLINE_FALLBACK"
            pending = self.storage.pending_items()
            pending_files = len(pending)
            pending_bytes = sum(int(item.get("size_bytes") or 0) for item in pending)
            pending_historical = 0
            pending_historical_bytes = 0
            pending_normal = 0
            pending_normal_bytes = 0
            current_transfer = None
            share_root = self.config.share_root
            for item in pending:
                meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                size = int(item.get("size_bytes") or 0)
                if meta.get("kind") == "bulk_migration":
                    pending_historical += 1
                    pending_historical_bytes += size
                else:
                    pending_normal += 1
                    pending_normal_bytes += size
                if current_transfer is None and share_root is not None:
                    try:
                        explicit = str(item.get("remote_relpath") or "").strip().replace("\\", "/")
                        if explicit:
                            dest = share_root / Path(*[part for part in explicit.split("/") if part not in {"", ".", ".."}])
                            parts = list(dest.parent.glob(dest.name + ".*.part"))
                            if parts:
                                part = max(parts, key=lambda path: path.stat().st_mtime_ns)
                                copied = int(part.stat().st_size)
                                current_transfer = {
                                    "filename": dest.name,
                                    "bytes_transferred": copied,
                                    "size_bytes": size,
                                    "progress_pct": round((copied / size) * 100.0, 1) if size > 0 else 0.0,
                                }
                    except OSError:
                        pass
            sync_state = _normalize_sync_display_state(
                health.get("status"), transport.get("state"), pending_files
            )
            display_api_latency_ms = _display_api_latency_ms(health.get("status"), api_latency_ms)
            payload = {"updated_at_utc": _utc_now(), "state": state, "api": health, "transport": transport,
                       "references_tracks": self.s8.status(), "performance": s9, "driver_profiles": driver_profiles,
                       "driver_deletions": {"pending": pending_deletions, "attempts": deletion_results}, "elapsed_ms": round(elapsed_ms, 2),
                       "api_latency_ms": display_api_latency_ms,
                       "sync": {"state": sync_state, "pending_files": pending_files, "pending_bytes": pending_bytes,
                                "historical_files": pending_historical, "historical_bytes": pending_historical_bytes,
                                "normal_files": pending_normal, "normal_bytes": pending_normal_bytes,
                                "current_transfer": current_transfer},
                       "performance_hub_url": self.api.performance_hub_url,
                       "architecture": "LOCAL_LIVE_SERVER_PERSISTENT"}
            self.storage._write_json_atomic(self.status_path, payload)
            return payload

    def status(self) -> dict[str, Any]:
        try: return json.loads(self.status_path.read_text(encoding="utf-8"))
        except Exception:
            return {"state": "LOCAL", "api": self.api.health(), "transport": {"pending": len(self.storage.pending_items())},
                    "performance_hub_url": self.api.performance_hub_url}

    def _loop(self) -> None:
        if self._stop.wait(8.0): return
        while not self._stop.is_set():
            self.run_once(); self._wake.clear(); self._wake.wait(self.config.interval_s)

    def start(self) -> "ServerPlatformCoordinator":
        if self._thread is None or not self._thread.is_alive():
            self._thread = Thread(target=self._loop, name="RaceEngineerServerPlatform", daemon=True); self._thread.start()
        return self

    def wake(self) -> None: self._wake.set()
    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set(); self._wake.set()
        if self._thread and self._thread.is_alive(): self._thread.join(timeout=timeout)


_DEFAULT_PLATFORM: ServerPlatformCoordinator | None = None

def start_default_server_platform() -> ServerPlatformCoordinator:
    global _DEFAULT_PLATFORM
    if _DEFAULT_PLATFORM is None: _DEFAULT_PLATFORM = ServerPlatformCoordinator().start()
    return _DEFAULT_PLATFORM


def platform_status() -> dict[str, Any]:
    return (_DEFAULT_PLATFORM.status() if _DEFAULT_PLATFORM is not None else ServerPlatformCoordinator().status())
