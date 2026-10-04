"""V1.5.0.0 low-overhead runtime validation and benchmark instrumentation.

The monitor is deliberately dependency-free and does not participate in any race
engineering decision.  It records only measured process/packet facts so long live
sessions and replays can be compared without screenshots or profiler tooling.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
import os
import platform
import threading
import time
from typing import Any

try:
    import resource  # POSIX only
except ImportError:  # Windows
    resource = None

if os.name == "nt":
    try:
        import ctypes
        from ctypes import wintypes

        class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        _GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
        _GetCurrentProcess.restype = wintypes.HANDLE
        _GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
        _GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        _GetProcessMemoryInfo.restype = wintypes.BOOL
    except Exception:
        ctypes = None
        _PROCESS_MEMORY_COUNTERS = None
        _GetCurrentProcess = None
        _GetProcessMemoryInfo = None
else:
    ctypes = None
    _PROCESS_MEMORY_COUNTERS = None
    _GetCurrentProcess = None
    _GetProcessMemoryInfo = None

def _rss_mb() -> float:
    """Return peak resident/working-set memory in MiB on supported platforms.

    Keep runtime validation dependency-free: Windows uses the native PSAPI,
    while POSIX platforms use ``resource.getrusage``. A metrics failure must
    never prevent Race Engineer from starting or processing telemetry.
    """
    if os.name == "nt" and _GetProcessMemoryInfo is not None:
        try:
            counters = _PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            ok = _GetProcessMemoryInfo(
                _GetCurrentProcess(), ctypes.byref(counters), counters.cb
            )
            if ok:
                return float(counters.PeakWorkingSetSize) / (1024.0 * 1024.0)
        except Exception:
            return 0.0

    if resource is not None:
        try:
            value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            # Linux and most Unix platforms report KiB; macOS reports bytes.
            if platform.system() == "Darwin":
                return value / (1024.0 * 1024.0)
            return value / 1024.0
        except Exception:
            return 0.0

    return 0.0


@dataclass(frozen=True, slots=True)
class RuntimeBenchmarkSnapshot:
    wall_s: float
    cpu_s: float
    cpu_percent_single_core: float
    rss_peak_mb: float
    packets: int
    unique_packet_families: int
    inferred_frame_gaps: int
    out_of_order_frames: int
    duplicate_frames: int
    max_frame_gap: int
    packet_family_counts: dict[int, int]
    packet_family_gaps: dict[int, int]
    sample_count: int
    process_id: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuntimeBenchmarkMonitor:
    """Measured CPU/RAM and frame continuity statistics.

    EA packet families have independent frame cadence, therefore drop inference is
    performed per packet ID instead of across the global stream. Flashbacks can
    legitimately move frame identifiers backwards; those are reported separately
    and are never counted as drops.
    """

    def __init__(self, *, sample_interval_s: float = 1.0, history: int = 7200) -> None:
        self._lock = threading.Lock()
        self.started_wall = time.monotonic()
        self.started_cpu = time.process_time()
        self.sample_interval_s = max(0.25, float(sample_interval_s))
        self._last_sample_wall = self.started_wall
        self._last_sample_cpu = self.started_cpu
        self._last_frame: dict[int, int] = {}
        self._counts: Counter[int] = Counter()
        self._gaps: Counter[int] = Counter()
        self._packets = 0
        self._out_of_order = 0
        self._duplicates = 0
        self._max_gap = 0
        self._rss_peak_mb = _rss_mb()
        self._samples = deque(maxlen=max(60, int(history)))

    def observe_header(self, header: Any) -> None:
        pid = int(getattr(header, "m_packetId", -1))
        frame = getattr(header, "m_frameIdentifier", None)
        now = time.monotonic()
        cpu = time.process_time()
        with self._lock:
            self._packets += 1
            self._counts[pid] += 1
            if isinstance(frame, int):
                previous = self._last_frame.get(pid)
                if previous is not None:
                    delta = int(frame) - int(previous)
                    if delta > 1:
                        gap = delta - 1
                        self._gaps[pid] += gap
                        self._max_gap = max(self._max_gap, gap)
                    elif delta == 0:
                        self._duplicates += 1
                    elif delta < 0:
                        self._out_of_order += 1
                # Do not let an older reordered packet move the continuity anchor.
                if previous is None or frame > previous:
                    self._last_frame[pid] = int(frame)
            if now - self._last_sample_wall >= self.sample_interval_s:
                wall_delta = max(1e-9, now - self._last_sample_wall)
                cpu_delta = max(0.0, cpu - self._last_sample_cpu)
                rss = _rss_mb()
                self._rss_peak_mb = max(self._rss_peak_mb, rss)
                self._samples.append({
                    "monotonic_s": now,
                    "cpu_percent_single_core": cpu_delta / wall_delta * 100.0,
                    "rss_mb": rss,
                    "packets": self._packets,
                })
                self._last_sample_wall = now
                self._last_sample_cpu = cpu

    def reset_session_continuity(self) -> None:
        """Session UIDs define fresh frame timelines; keep aggregate totals."""
        with self._lock:
            self._last_frame.clear()

    def reset_session_metrics(self) -> None:
        """Start a fresh per-session CPU/RAM/packet benchmark window."""
        with self._lock:
            self.started_wall=time.monotonic(); self.started_cpu=time.process_time()
            self._last_sample_wall=self.started_wall; self._last_sample_cpu=self.started_cpu
            self._last_frame.clear(); self._counts.clear(); self._gaps.clear(); self._packets=0
            self._out_of_order=0; self._duplicates=0; self._max_gap=0; self._rss_peak_mb=_rss_mb(); self._samples.clear()

    def snapshot(self) -> RuntimeBenchmarkSnapshot:
        now = time.monotonic(); cpu = time.process_time()
        with self._lock:
            wall = max(0.0, now - self.started_wall)
            cpu_total = max(0.0, cpu - self.started_cpu)
            rss = max(self._rss_peak_mb, _rss_mb())
            return RuntimeBenchmarkSnapshot(
                wall_s=round(wall, 6), cpu_s=round(cpu_total, 6),
                cpu_percent_single_core=round(cpu_total / wall * 100.0, 3) if wall > 0 else 0.0,
                rss_peak_mb=round(rss, 3), packets=self._packets,
                unique_packet_families=len(self._counts), inferred_frame_gaps=sum(self._gaps.values()),
                out_of_order_frames=self._out_of_order, duplicate_frames=self._duplicates,
                max_frame_gap=self._max_gap, packet_family_counts=dict(sorted(self._counts.items())),
                packet_family_gaps=dict(sorted(self._gaps.items())), sample_count=len(self._samples),
                process_id=os.getpid(),
            )

    def samples(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._samples)


def compare_replay_live_signatures(live: dict[str, Any], replay: dict[str, Any], *, tolerances: dict[str, float] | None = None) -> dict[str, Any]:
    """Compare deterministic end-state signatures without inventing missing data."""
    tolerances = dict(tolerances or {})
    keys = sorted(set(live) | set(replay))
    diffs = []
    for key in keys:
        a, b = live.get(key), replay.get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
            tol = float(tolerances.get(key, 1e-6))
            if abs(float(a) - float(b)) > tol:
                diffs.append({"key": key, "live": a, "replay": b, "tolerance": tol})
        elif a != b:
            diffs.append({"key": key, "live": a, "replay": b, "tolerance": None})
    return {"match": not diffs, "differences": diffs, "compared_keys": keys}
