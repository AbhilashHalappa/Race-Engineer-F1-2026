"""Session-engineer routing helpers with no Qt dependency."""
from __future__ import annotations


def is_qualifying_snapshot(snapshot) -> bool:
    """Return True for any qualifying-family session snapshot.

    Use both normalized event profile and human-readable session type so One-Shot,
    Short and full Qualifying sessions are routed consistently.
    """
    profile = str(getattr(snapshot, "event_profile", "") or "").strip().upper()
    session_type = str(getattr(snapshot, "session_type", "") or "").strip().upper()
    return "QUALIFY" in profile or "QUALIFY" in session_type
