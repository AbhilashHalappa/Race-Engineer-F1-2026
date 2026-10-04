"""Cross-process ownership guard for Race Engineer server queue mutations.

V2.9.1.3.4 prevents the GUI background workers and a separate
``python -m src.server_sync`` process from mutating the same durable queue at
once.  The guard is intentionally local-only: it protects the gaming-PC cache
and never participates in the live telemetry path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
import json
import os
import socket
import time
import uuid


_LOCAL_GUARD = Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return False
                return int(code.value) == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            # Unknown is safer than stealing a live process' lock.
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


@dataclass
class SyncOwnershipLock:
    """Atomic file lock shared by all Race Engineer sync/migration processes."""

    lock_path: Path
    operation: str = "sync"
    stale_after_s: float = 6 * 60 * 60
    token: str = ""
    acquired: bool = False
    owner: dict[str, Any] | None = None
    _local_acquired: bool = False

    def _read_owner(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self.lock_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except Exception:
            return None

    def _is_stale(self, owner: dict[str, Any] | None) -> bool:
        try:
            age_s = max(0.0, time.time() - self.lock_path.stat().st_mtime)
        except OSError:
            return True
        if owner:
            host = str(owner.get("hostname") or "")
            try:
                pid = int(owner.get("pid") or 0)
            except (TypeError, ValueError):
                pid = 0
            if host == (socket.gethostname() or "gaming-pc") and pid:
                return not _pid_alive(pid)
        return age_s >= max(60.0, float(self.stale_after_s))

    def acquire(self, *, timeout_s: float = 0.0, poll_s: float = 0.05) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while True:
            remaining = max(0.0, deadline - time.monotonic())
            got_local = _LOCAL_GUARD.acquire(timeout=remaining if timeout_s > 0 else 0)
            if got_local:
                self._local_acquired = True
                try:
                    self.lock_path.parent.mkdir(parents=True, exist_ok=True)
                    self.token = uuid.uuid4().hex
                    payload = {
                        "version": 1,
                        "token": self.token,
                        "pid": os.getpid(),
                        "hostname": socket.gethostname() or "gaming-pc",
                        "operation": self.operation,
                        "acquired_at_utc": _utc_now(),
                    }
                    try:
                        fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    except FileExistsError:
                        self.owner = self._read_owner()
                        if self._is_stale(self.owner):
                            try:
                                self.lock_path.unlink()
                            except OSError:
                                pass
                            _LOCAL_GUARD.release()
                            self._local_acquired = False
                        else:
                            _LOCAL_GUARD.release()
                            self._local_acquired = False
                            if time.monotonic() >= deadline:
                                return False
                            time.sleep(max(0.01, poll_s))
                        continue
                    try:
                        os.write(fd, (json.dumps(payload, indent=2) + "\n").encode("utf-8"))
                    finally:
                        os.close(fd)
                    self.owner = payload
                    self.acquired = True
                    return True
                except Exception:
                    if self._local_acquired:
                        _LOCAL_GUARD.release()
                        self._local_acquired = False
                    raise
            if time.monotonic() >= deadline:
                self.owner = self._read_owner()
                return False
            time.sleep(max(0.01, poll_s))

    def release(self) -> None:
        try:
            if self.acquired:
                owner = self._read_owner()
                if owner is None or str(owner.get("token") or "") == self.token:
                    try:
                        self.lock_path.unlink(missing_ok=True)
                    except OSError:
                        pass
        finally:
            self.acquired = False
            if self._local_acquired:
                _LOCAL_GUARD.release()
                self._local_acquired = False

    def busy_result(self, pending: int) -> dict[str, Any]:
        owner = self.owner or self._read_owner() or {}
        return {
            "state": "SYNC_BUSY",
            "pending": int(pending),
            "attempted": 0,
            "synced": 0,
            "failed": 0,
            "owner": {
                "pid": owner.get("pid"),
                "hostname": owner.get("hostname"),
                "operation": owner.get("operation"),
                "acquired_at_utc": owner.get("acquired_at_utc"),
            },
        }

    def __enter__(self) -> "SyncOwnershipLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
