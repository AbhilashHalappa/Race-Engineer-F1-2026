"""Deterministic automatic-engineer messages. No AI/LLM content."""

from dataclasses import dataclass
import re
from enum import IntEnum


def estimate_speech_duration_s(text: str, *, words_per_second: float = 1.85, fixed_overhead_s: float = 0.35) -> float:
    """Conservative speech-duration estimate used by real-time radio scheduling.

    The exact Piper WAV duration is checked again immediately before playback.
    V1.1.0.15 calibrates this estimate to the measured en_GB-alan-medium voice
    at the project's normal 0.82 length scale.  The older 2.55 words/s model
    under-estimated real WAV duration by roughly 28-38% in live validation.
    This conservative estimate lets CORNER COACH schedule compact PRE/POST calls
    before they become stale instead of generating lines that Piper later drops.
    """
    words = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", str(text or ""))
    if not words:
        return float(fixed_overhead_s)
    return max(0.45, float(fixed_overhead_s) + len(words) / max(1.0, float(words_per_second)))


class Priority(IntEnum):
    CRITICAL = 0
    STRATEGY = 1
    INFORMATION = 2
    COACHING = 3


@dataclass(frozen=True, slots=True)
class EngineerMessage:
    key: str
    priority: Priority
    text: str
    created_at: float
    session_time_s: float | None = None
    # Real-time speech scheduling metadata. ``deadline_at_monotonic_s`` is an
    # absolute monotonic timestamp by which playback must be FINISHED, not merely
    # started.  Non-coach callers can ignore both fields.
    deadline_at_monotonic_s: float | None = None
    estimated_duration_s: float | None = None
    # Visual-only coaching may be shown in the CORNER COACH transcript when
    # there is not enough safe radio airtime. SpeechManager ignores it.
    speak: bool = True


    @property
    def priority_name(self) -> str:
        return self.priority.name.title()
