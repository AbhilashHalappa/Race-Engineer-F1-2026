"""Durable Driver Profile deletion journal.

Deleting a Driver is local-first.  This journal records a small tombstone after
local deletion so the background server coordinator can soft-delete the server
copy without making the UI wait for LAN availability.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from .storage_manager import DEFAULT_STORAGE, StorageManager

RETENTION_DAYS = 30


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DriverDeletionJournal:
    def __init__(self, storage: StorageManager = DEFAULT_STORAGE, *, root: str | Path | None = None) -> None:
        self.storage = storage
        self.root = Path(root) if root is not None else storage.server_sync_root / "driver_deletions"

    def record(self, profile: dict[str, Any], *, deleted_sessions: int = 0) -> Path:
        driver_id = str(profile.get("driver_id") or "").strip()
        if not driver_id:
            raise ValueError("Driver deletion requires a permanent driver_id")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{driver_id}.json"
        payload = {
            "journal_version": 1,
            "status": "pending",
            "driver_id": driver_id,
            "display_name": str(profile.get("display_name") or "Driver"),
            "active_game": str(profile.get("active_game") or "f1_26"),
            "time_zone": str(profile.get("time_zone") or "UTC"),
            "deleted_at_utc": _utc_now(),
            "retention_days": RETENTION_DAYS,
            "deleted_local_sessions": int(deleted_sessions),
        }
        self.storage._write_json_atomic(path, payload)
        return path

    def entries(self, *, pending_only: bool = False) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        out=[]
        for path in sorted(self.root.glob("*.json")):
            try:
                value=json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(value,dict):
                continue
            if pending_only and str(value.get("status") or "") != "pending":
                continue
            value=dict(value); value["journal_path"]=str(path); out.append(value)
        return out

    def mark_synced(self, entry: dict[str, Any], server_response: dict[str, Any]) -> None:
        path=Path(str(entry.get("journal_path") or ""))
        if not path.is_file():
            return
        payload=dict(entry)
        payload.pop("journal_path",None)
        payload["status"]="server_retained"
        payload["synced_at_utc"]=_utc_now()
        payload["server"]=server_response
        self.storage._write_json_atomic(path,payload)

    def pending_count(self) -> int:
        return len(self.entries(pending_only=True))
