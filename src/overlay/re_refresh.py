"""UI-independent Race Engineer refresh gating for V0.9.11.2."""
from __future__ import annotations


def should_refresh_race_engineer(*, visible: bool, paused: bool, replay_mode: bool, rebuilding: bool) -> bool:
    """Return whether the dedicated RE timer should read a fresh provider snapshot."""
    if not visible:
        return False
    if replay_mode and rebuilding:
        return False
    if paused and not replay_mode:
        return False
    return True
