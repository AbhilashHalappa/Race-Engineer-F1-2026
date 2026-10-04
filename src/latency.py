"""Lightweight end-to-end latency telemetry for the real-time engineer pipeline.

The monitor deliberately keeps the UDP hot path cheap: observations are O(1)
append/counter operations and percentile work happens only when a snapshot is
requested by diagnostics/tests.  All timings are monotonic/perf-counter based.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading


@dataclass(frozen=True, slots=True)
class LatencySnapshot:
    packets: int
    decisions: int
    decode_avg_ms: float
    decode_p95_ms: float
    state_avg_ms: float
    state_p95_ms: float
    decision_avg_ms: float
    decision_p95_ms: float
    core_avg_ms: float
    core_p95_ms: float
    core_max_ms: float
    dispatch_avg_ms: float
    radio_queue_avg_ms: float
    radio_queue_p95_ms: float
    radio_queue_max_ms: float
    audio_start_avg_ms: float
    audio_start_p95_ms: float
    audio_start_max_ms: float
    queue_depth: int
    queue_depth_max: int
    preemptions: int


class LatencyMonitor:
    """Rolling latency statistics with very small hot-path overhead."""

    def __init__(self, window: int = 4096) -> None:
        if window < 32:
            raise ValueError("Latency window must be at least 32 samples")
        self._lock = threading.Lock()
        self._decode = deque(maxlen=window)
        self._state = deque(maxlen=window)
        self._decision = deque(maxlen=window)
        self._core = deque(maxlen=window)
        self._dispatch = deque(maxlen=window)
        self._radio_queue = deque(maxlen=window)
        self._audio_start = deque(maxlen=window)
        self._packets = 0
        self._decisions = 0
        self._queue_depth = 0
        self._queue_depth_max = 0
        self._preemptions = 0

    def reset(self) -> None:
        """Start a fresh per-session measurement window."""
        with self._lock:
            for q in (self._decode,self._state,self._decision,self._core,self._dispatch,self._radio_queue,self._audio_start): q.clear()
            self._packets=self._decisions=0; self._queue_depth=self._queue_depth_max=0; self._preemptions=0

    @staticmethod
    def _ms(ns: int) -> float:
        return max(0, ns) / 1_000_000.0

    def observe_packet(self, *, decode_ns: int, state_ns: int, decision_ns: int,
                       core_ns: int, dispatch_ns: int = 0, decisions: int = 0) -> None:
        # deque.append is already cheap; one short lock keeps snapshots coherent
        # with the TTS worker without putting any formatting/sorting on UDP.
        with self._lock:
            self._packets += 1
            self._decisions += max(0, int(decisions))
            self._decode.append(self._ms(decode_ns))
            self._state.append(self._ms(state_ns))
            self._decision.append(self._ms(decision_ns))
            self._core.append(self._ms(core_ns))
            self._dispatch.append(self._ms(dispatch_ns))

    def radio_queued(self, depth: int) -> None:
        with self._lock:
            self._queue_depth = max(0, int(depth))
            self._queue_depth_max = max(self._queue_depth_max, self._queue_depth)

    def radio_dequeued(self, queue_ns: int, depth: int) -> None:
        with self._lock:
            self._radio_queue.append(self._ms(queue_ns))
            self._queue_depth = max(0, int(depth))

    def audio_started(self, queued_to_audio_ns: int) -> None:
        with self._lock:
            self._audio_start.append(self._ms(queued_to_audio_ns))

    def preempted(self) -> None:
        with self._lock:
            self._preemptions += 1

    @staticmethod
    def _stats(values) -> tuple[float, float, float]:
        if not values:
            return 0.0, 0.0, 0.0
        seq = list(values)
        avg = sum(seq) / len(seq)
        ordered = sorted(seq)
        # nearest-rank p95 without importing statistics/numpy on the hot project.
        index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * 0.95 + 0.5)))
        return avg, ordered[index], ordered[-1]

    def snapshot(self) -> LatencySnapshot:
        with self._lock:
            packets, decisions = self._packets, self._decisions
            queue_depth, queue_depth_max = self._queue_depth, self._queue_depth_max
            preemptions = self._preemptions
            decode = tuple(self._decode)
            state = tuple(self._state)
            decision = tuple(self._decision)
            core = tuple(self._core)
            dispatch = tuple(self._dispatch)
            radio_queue = tuple(self._radio_queue)
            audio_start = tuple(self._audio_start)
        da, dp, _ = self._stats(decode)
        sa, sp, _ = self._stats(state)
        ea, ep, _ = self._stats(decision)
        ca, cp, cm = self._stats(core)
        xa, _, _ = self._stats(dispatch)
        qa, qp, qm = self._stats(radio_queue)
        aa, ap, am = self._stats(audio_start)
        return LatencySnapshot(
            packets=packets, decisions=decisions,
            decode_avg_ms=da, decode_p95_ms=dp,
            state_avg_ms=sa, state_p95_ms=sp,
            decision_avg_ms=ea, decision_p95_ms=ep,
            core_avg_ms=ca, core_p95_ms=cp, core_max_ms=cm,
            dispatch_avg_ms=xa,
            radio_queue_avg_ms=qa, radio_queue_p95_ms=qp, radio_queue_max_ms=qm,
            audio_start_avg_ms=aa, audio_start_p95_ms=ap, audio_start_max_ms=am,
            queue_depth=queue_depth, queue_depth_max=queue_depth_max,
            preemptions=preemptions,
        )

    def format_compact(self) -> str:
        s = self.snapshot()
        return (
            f"[LATENCY] core {s.core_avg_ms:.3f} ms avg / {s.core_p95_ms:.3f} p95 / {s.core_max_ms:.3f} max"
            f" | decode {s.decode_avg_ms:.3f} | state {s.state_avg_ms:.3f} | decision {s.decision_avg_ms:.3f}"
            f" | radio-q {s.radio_queue_p95_ms:.1f} ms p95 | audio {s.audio_start_p95_ms:.1f} ms p95"
            f" | q {s.queue_depth}/{s.queue_depth_max} | preempt {s.preemptions}"
        )
