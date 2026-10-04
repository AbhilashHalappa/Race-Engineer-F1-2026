"""V2.5.1 per-track F1 skill summaries derived from validated Skill Evidence.

This module intentionally reuses the existing SkillTrendStore track-filtered
views so track performance and track trends cannot drift away from the V2.4/
V2.5 scoring rules.
"""
from __future__ import annotations

from typing import Any

from .driver_profiles import DriverProfileStore
from .driver_skill import ALL_F1_SKILLS, DISPLAY_NAMES
from .skill_trends import SkillTrendStore


class TrackSkillStore:
    def __init__(self, driver_store: DriverProfileStore | None = None) -> None:
        self.driver_store = driver_store or DriverProfileStore()
        self.trends = SkillTrendStore(self.driver_store)

    def available_tracks(self, driver_id: str) -> list[str]:
        return self.trends.available_tracks(driver_id)

    def summary(self, driver_id: str, track: str) -> dict[str, Any]:
        track = str(track or "").strip()
        if not track:
            return {
                "track": "",
                "overall": None,
                "trend": None,
                "personal_best": None,
                "session_count": 0,
                "skills": {},
            }

        overall = self.trends.view(driver_id, "overall", "all_time", track)
        skills: dict[str, dict[str, Any]] = {}
        for skill in ALL_F1_SKILLS:
            view = self.trends.view(driver_id, skill, "all_time", track)
            skills[skill] = {
                "name": DISPLAY_NAMES.get(skill, skill),
                "value": view.get("current"),
                "trend": view.get("change"),
                "personal_best": view.get("personal_best"),
                "session_count": int(view.get("all_time_point_count") or 0),
            }

        # Count real evidence sessions on this circuit, not only scoreable
        # Overall snapshots (which require >=2 sessions and >=4 core skills).
        session_count = sum(
            1 for row in self.trends._evidence_sessions(driver_id)
            if str(row.get("track") or "Unknown") == track
        )
        return {
            "track": track,
            "overall": overall.get("current"),
            "trend": overall.get("change"),
            "personal_best": overall.get("personal_best"),
            "session_count": session_count,
            "scoreable_session_count": int(overall.get("all_time_point_count") or 0),
            "skills": skills,
        }

    def overview(self, driver_id: str) -> list[dict[str, Any]]:
        return [self.summary(driver_id, track) for track in self.available_tracks(driver_id)]
