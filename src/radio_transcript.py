"""Thread-safe in-memory transcript for driver/engineer radio traffic.

The store is intentionally independent from telemetry state.  STT and TTS worker
threads append tiny immutable entries while the Qt overlay only reads snapshots,
so opening the transcript window can never stall UDP packet processing.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading
import time

from .engineer.models import EngineerMessage


@dataclass(frozen=True, slots=True)
class RadioTranscriptEntry:
    sequence: int
    role: str
    text: str
    session_time_s: float | None
    created_at: float
    key: str | None = None
    priority: int | None = None
    interpreted_text: str | None = None


class RadioTranscriptStore:
    """Small bounded conversation/event history shared by radio + overlay threads."""

    def __init__(self, max_entries: int = 200) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self._entries: deque[RadioTranscriptEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._sequence = 0
        self._last_session_time_s: float | None = None

    @property
    def latest_sequence(self) -> int:
        with self._lock:
            return self._sequence

    def _append(self, role: str, text: str, *, session_time_s: float | None,
                key: str | None = None, priority: int | None = None,
                interpreted_text: str | None = None) -> RadioTranscriptEntry | None:
        text = " ".join(str(text or "").split()).strip()
        if not text:
            return None
        interpreted_text = " ".join(str(interpreted_text or "").split()).strip() or None
        with self._lock:
            # Transcript is appended in actual heard/request order. Clamp replay/session
            # timestamps so older queued telemetry events cannot make the visible log
            # run backwards after a newer PTT request.
            if session_time_s is not None:
                try:
                    session_time_s = float(session_time_s)
                    if self._last_session_time_s is not None:
                        session_time_s = max(session_time_s, self._last_session_time_s)
                    self._last_session_time_s = session_time_s
                except (TypeError, ValueError):
                    session_time_s = self._last_session_time_s
            self._sequence += 1
            entry = RadioTranscriptEntry(
                sequence=self._sequence,
                role=role,
                text=text,
                session_time_s=session_time_s,
                created_at=time.monotonic(),
                key=key,
                priority=priority,
                interpreted_text=interpreted_text,
            )
            self._entries.append(entry)
            return entry

    def add_driver(self, text: str, *, session_time_s: float | None = None,
                   interpreted_text: str | None = None) -> RadioTranscriptEntry | None:
        return self._append("DRIVER", text, session_time_s=session_time_s, key="voice:request",
                            interpreted_text=interpreted_text)

    def add_engineer(self, message: EngineerMessage) -> RadioTranscriptEntry | None:
        return self._append(
            "ENGINEER",
            message.text,
            session_time_s=message.session_time_s,
            key=message.key,
            priority=int(message.priority),
        )

    def snapshot(self) -> tuple[RadioTranscriptEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._last_session_time_s = None
            # Advance the sequence as a revision marker so an open overlay redraws
            # immediately even though the newest entry disappeared.
            self._sequence += 1
