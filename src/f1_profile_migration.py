"""V2.1.3 non-destructive F1 history attachment.

The legacy/live Performance Hub SQLite database remains the authoritative store.
This module records a stable ownership binding from the person-level Driver
Profile's F1 Game Profile to that existing store. No session payload is copied.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .driver_profiles import DriverProfileStore
from .performance_history import PerformanceHistoryStore

MIGRATION_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def attach_existing_f1_history(
    driver_store: DriverProfileStore,
    history_store: PerformanceHistoryStore,
    driver_id: str,
) -> dict[str, Any]:
    profile = driver_store.load_profile(driver_id)
    if not profile:
        raise ValueError("Driver profile does not exist")

    compat = profile.get("compatibility") if isinstance(profile.get("compatibility"), dict) else {}
    legacy_id = compat.get("performance_history_profile_id")
    if legacy_id is None:
        legacy_id = history_store.active_user_profile_id()
    if legacy_id is None:
        legacy_id = history_store.create_user_profile(str(profile.get("display_name") or "Driver"))
    legacy_id = int(legacy_id)
    history_store.set_active_user_profile(legacy_id)
    driver_store.set_compatibility_value(driver_id, "performance_history_profile_id", legacy_id)

    inventory = history_store.profile_inventory(legacy_id)
    if not inventory.get("available"):
        inventory = {
            "available": True,
            "profile_id": legacy_id,
            "profile_name": str(profile.get("display_name") or "Driver"),
            "sessions": 0,
            "tracks": 0,
            "laps": 0,
            "game_identities": 0,
            "session_types": [],
            "evidence": {
                "telemetry_sessions": 0,
                "lap_telemetry_records": 0,
                "reference_sessions": 0,
                "corner_performance_sessions": 0,
                "performance_analysis_sessions": 0,
                "assist_sessions": 0,
                "recorded_history_sessions": 0,
            },
        }

    game_profile = driver_store.ensure_game_profile(driver_id, "f1_26")
    existing_binding = game_profile.get("history_binding") if isinstance(game_profile.get("history_binding"), dict) else {}
    first_attached = existing_binding.get("attached_at") or _utc_now()
    binding = {
        "migration_version": MIGRATION_VERSION,
        "status": "linked",
        "storage_mode": "logical_link",
        "authoritative_store": "performance_history_live_sqlite",
        "database_path": str(history_store.path).replace("\\", "/"),
        "performance_history_profile_id": legacy_id,
        "attached_at": first_attached,
        "last_verified_at": _utc_now(),
        "inventory": inventory,
        "content_scope": [
            "sessions",
            "laps",
            "tracks",
            "telemetry",
            "session_recorded_references",
            "corner_performance",
            "performance_analysis",
            "assists",
            "driver_game_information",
            "recorded_history",
        ],
        "shared_assets_note": "Installed track/reference assets remain in their shared Race Engineer stores; they are not duplicated per driver.",
    }
    game_profile["history_binding"] = binding
    # Sessions/laps are safe factual aggregates from the authoritative history.
    # Driving seconds intentionally remains untouched until V2.2.0.
    game_profile["sessions"] = int(inventory.get("sessions") or 0)
    game_profile["history_laps"] = int(inventory.get("laps") or 0)
    game_profile["history_tracks"] = int(inventory.get("tracks") or 0)
    driver_store.save_game_profile(driver_id, "f1_26", game_profile)

    career = driver_store.load_career_summary(driver_id)
    career["total_sessions"] = int(inventory.get("sessions") or 0)
    career["total_laps"] = int(inventory.get("laps") or 0)
    driver_store.save_career_summary(driver_id, career)
    return binding
