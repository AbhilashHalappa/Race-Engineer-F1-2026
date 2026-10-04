"""V2.7.0 person-level Driver context switching.

A Driver switch must move the complete person-owned context together: the
DriverProfileStore active Driver and its linked PerformanceHistoryStore owner.
This module keeps that operation testable outside Qt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .driver_profiles import DriverProfileStore
from .performance_history import PerformanceHistoryStore
from .user_time import DEFAULT_TIME_ZONE


class DriverContextManager:
    def __init__(self, driver_store: DriverProfileStore | None = None,
                 performance_store: PerformanceHistoryStore | None = None) -> None:
        self.driver_store = driver_store or DriverProfileStore()
        self.performance_store = performance_store or PerformanceHistoryStore()

    @staticmethod
    def _linked_history_id(profile: dict[str, Any]) -> int | None:
        compat = profile.get("compatibility") if isinstance(profile.get("compatibility"), dict) else {}
        value = compat.get("performance_history_profile_id")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def ensure_history_owner(self, driver_id: str) -> int:
        profile = self.driver_store.load_profile(driver_id)
        if not profile:
            raise ValueError("Driver profile does not exist")
        history_id = self._linked_history_id(profile)
        if history_id is not None and self.performance_store.set_active_user_profile(history_id):
            return history_id
        # Missing/broken compatibility links must never adopt another Driver's
        # history. Repair with a new empty owner.
        history_id = self.performance_store.create_distinct_user_profile(
            str(profile.get("display_name") or "Driver")
        )
        self.driver_store.set_compatibility_value(driver_id, "performance_history_profile_id", int(history_id))
        return int(history_id)

    def activate(self, driver_id: str) -> dict[str, Any]:
        driver_id = str(driver_id or "")
        profile = self.driver_store.load_profile(driver_id)
        if not profile:
            raise ValueError("Driver profile does not exist")
        previous_driver_id = self.driver_store.active_driver_id()
        previous_history_id = self.performance_store.active_user_profile_id()
        try:
            history_id = self.ensure_history_owner(driver_id)
            if not self.performance_store.set_active_user_profile(history_id):
                raise RuntimeError("Unable to activate linked Performance Hub owner")
            if not self.driver_store.set_active_driver(driver_id):
                raise RuntimeError("Unable to activate Driver Profile")
        except Exception:
            if previous_history_id is not None:
                self.performance_store.set_active_user_profile(previous_history_id)
            if previous_driver_id:
                self.driver_store.set_active_driver(previous_driver_id)
            raise
        return self.driver_store.active_profile() or profile

    def delete(self, driver_id: str) -> dict[str, Any]:
        """Permanently remove one Driver and its linked Performance Hub owner.

        When deleting the active Driver, another Driver is activated first so
        application ownership never points at data that is being removed.
        """
        driver_id = str(driver_id or "").strip()
        profile = self.driver_store.load_profile(driver_id)
        if not profile:
            raise ValueError("Driver profile does not exist")
        refs = self.driver_store.list_profiles()
        if len(refs) <= 1:
            raise ValueError("The only remaining Driver Profile cannot be deleted")

        fallback_id = next(ref.driver_id for ref in refs if ref.driver_id != driver_id)
        was_active = self.driver_store.active_driver_id() == driver_id
        if was_active:
            self.activate(fallback_id)

        # Persist the local deletion intent before destructive local work.  The
        # tombstone is tiny and local-only; the background coordinator later
        # turns it into a 30-day server soft-delete.
        from .driver_retention import DriverDeletionJournal
        journal = DriverDeletionJournal(root=self.driver_store.root.parent / "cache" / "server_sync" / "driver_deletions")
        journal_path = journal.record(profile, deleted_sessions=0)

        history_id = self._linked_history_id(profile)
        deleted_sessions = 0
        try:
            if history_id is not None:
                result = self.performance_store.delete_user_profile(history_id)
                deleted_sessions = int(result.get("sessions") or 0)
            if not self.driver_store.delete_profile(driver_id):
                raise RuntimeError("Unable to delete Driver Profile")
            journal.record(profile, deleted_sessions=deleted_sessions)
        except Exception:
            try:
                journal_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

        # Reassert a valid complete context after deletion. This also repairs an
        # older fallback Driver if its compatibility link was missing.
        active_id = self.driver_store.active_driver_id() or fallback_id
        active_profile = self.activate(active_id)
        return {
            "deleted_driver_id": driver_id,
            "deleted_history_id": history_id,
            "deleted_sessions": deleted_sessions,
            "active_driver_id": str(active_profile.get("driver_id") or active_id),
        }

    def create(self, display_name: str, *, country_region: str = "", units: str = "metric",
               time_zone: str = DEFAULT_TIME_ZONE, avatar_source: str | Path | None = None,
               active_game: str = "f1_26") -> dict[str, Any]:
        # Always create a distinct empty legacy owner first. create_profile()
        # creates a fresh Driver ID and never copies another person's files.
        history_id = self.performance_store.create_distinct_user_profile(display_name)
        try:
            profile = self.driver_store.create_profile(
                display_name,
                country_region=country_region,
                units=units,
                time_zone=time_zone,
                avatar_source=avatar_source,
                active_game=active_game,
                compatibility={"performance_history_profile_id": int(history_id)},
            )
            self.performance_store.set_active_user_profile(int(history_id))
            self.driver_store.set_active_driver(str(profile["driver_id"]))
            return profile
        except Exception:
            # Performance History intentionally has no destructive delete API;
            # a failed creation can leave only an empty unlinked compatibility
            # owner, but it can never steal or overwrite another Driver's data.
            raise
