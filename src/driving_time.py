"""Telemetry-active driving time accounting for Race Engineer V2.2.0.

The counter is intentionally based on trusted live F1 session-time deltas from
player telemetry packets. Application uptime, replay, menus, paused sessions,
spectating, garage time and long telemetry gaps do not contribute.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

from .driver_profiles import DriverProfileStore, SUPPORTED_GAMES

F1_BUCKETS = ("practice", "time_trial", "qualifying", "sprint", "race")


def f1_session_bucket(session_type: Any) -> str | None:
    name = str(getattr(session_type, "name", session_type) or "").strip().lower()
    if not name or name == "unknown":
        return None
    if "time trial" in name:
        return "time_trial"
    if "sprint" in name and "shootout" not in name:
        return "sprint"
    if "qualifying" in name or "shootout" in name:
        return "qualifying"
    if "practice" in name:
        return "practice"
    if "race" in name:
        return "race"
    return None


def _driver_status_name(player: Any) -> str:
    lap = getattr(player, "lap", None)
    status = getattr(lap, "driver_status", None)
    return str(getattr(status, "name", status) or "").strip().lower()


def _active_driving_sample(state: Any) -> tuple[bool, str | None, float | None, int | None]:
    session = getattr(state, "session", None)
    player = getattr(state, "player", None)
    if session is None or player is None:
        return False, None, None, None
    uid = getattr(session, "uid", None)
    t = getattr(session, "session_time_s", None)
    if uid is None or t is None:
        return False, None, None, None
    try:
        t = float(t)
    except (TypeError, ValueError):
        return False, None, None, None
    if not math.isfinite(t):
        return False, None, None, None
    if bool(getattr(session, "paused", False)) or bool(getattr(session, "spectating", False)) or bool(getattr(session, "ended", False)):
        return False, None, t, int(uid)
    bucket = f1_session_bucket(getattr(session, "session_type", None))
    if bucket is None:
        return False, None, t, int(uid)
    # EA's driver status is the most reliable distinction between actual track
    # activity and sitting in the garage/menu while packets still exist.
    status = _driver_status_name(player)
    if status not in {"flying lap", "in lap", "out lap", "on track"}:
        return False, bucket, t, int(uid)
    if getattr(player, "telemetry", None) is None:
        return False, bucket, t, int(uid)
    return True, bucket, t, int(uid)


@dataclass
class F1DrivingTimeTracker:
    store: DriverProfileStore = field(default_factory=DriverProfileStore)
    flush_interval_s: float = 15.0
    max_sample_gap_s: float = 2.0
    _last_driver_id: str | None = None
    _last_uid: int | None = None
    _last_session_time_s: float | None = None
    _pending: dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in F1_BUCKETS})
    _pending_total: float = 0.0

    def reset_baseline(self) -> None:
        self._last_driver_id = None
        self._last_uid = None
        self._last_session_time_s = None

    def observe(self, state: Any, *, mode: str, packet_category: str | None = None) -> float:
        """Observe one state update and return seconds newly counted.

        Only live player telemetry packets establish/count samples. This keeps
        replay and low-rate session/menu packets from inflating totals.
        """
        if str(mode or "").lower() != "live" or packet_category != "telemetry":
            if str(mode or "").lower() != "live":
                if self._pending_total > 0.0 and self._last_driver_id:
                    self.flush(self._last_driver_id)
                self.reset_baseline()
            return 0.0

        profile = self.store.active_profile() or {}
        driver_id = str(profile.get("driver_id") or "")
        if self._last_driver_id and driver_id and self._last_driver_id != driver_id and self._pending_total > 0.0:
            self.flush(self._last_driver_id)
        if not driver_id or str(profile.get("active_game") or "f1_26") != "f1_26":
            if self._pending_total > 0.0 and self._last_driver_id:
                self.flush(self._last_driver_id)
            self.reset_baseline()
            return 0.0

        valid, bucket, session_time_s, uid = _active_driving_sample(state)
        if session_time_s is None or uid is None:
            self.reset_baseline()
            return 0.0

        same_stream = self._last_driver_id == driver_id and self._last_uid == uid
        previous = self._last_session_time_s if same_stream else None
        self._last_driver_id = driver_id
        self._last_uid = uid
        self._last_session_time_s = session_time_s

        if not valid or bucket is None or previous is None:
            return 0.0
        dt = session_time_s - previous
        if not math.isfinite(dt) or dt <= 0.0 or dt > float(self.max_sample_gap_s):
            return 0.0

        self._pending[bucket] += dt
        self._pending_total += dt
        if self._pending_total >= float(self.flush_interval_s):
            self.flush(driver_id)
        return dt

    def flush(self, driver_id: str | None = None) -> float:
        driver_id = str(driver_id or self._last_driver_id or "")
        amount = float(self._pending_total)
        if not driver_id or amount <= 0.0:
            return 0.0

        game = self.store.ensure_game_profile(driver_id, "f1_26")
        breakdown = game.get("driving_time") if isinstance(game.get("driving_time"), dict) else {}
        for key in F1_BUCKETS:
            breakdown[key] = float(breakdown.get(key) or 0.0) + float(self._pending.get(key) or 0.0)
        game["driving_time"] = breakdown
        game["driving_seconds"] = float(game.get("driving_seconds") or 0.0) + amount
        self.store.save_game_profile(driver_id, "f1_26", game)

        # Career time is the sum of supported game-profile counters. At V2.2.0
        # only F1 has a telemetry adapter, but summing here is server/multi-game ready.
        total = 0.0
        for game_id in SUPPORTED_GAMES:
            gp = self.store.load_game_profile(driver_id, game_id) or {}
            try:
                total += max(0.0, float(gp.get("driving_seconds") or 0.0))
            except (TypeError, ValueError):
                pass
        career = self.store.load_career_summary(driver_id)
        career["total_driving_seconds"] = total
        self.store.save_career_summary(driver_id, career)

        self._pending = {k: 0.0 for k in F1_BUCKETS}
        self._pending_total = 0.0
        return amount
