"""Optional live UI overlay for Race Engineer.

PySide6 is imported lazily by :mod:`src.overlay.runtime` so the telemetry backend
and test suite continue to run without the GUI dependency installed.
"""

from .data import CoachMetric, OverlaySnapshot, SectionHistory, build_overlay_snapshot

__all__ = [
    "CoachMetric",
    "OverlaySnapshot",
    "SectionHistory",
    "build_overlay_snapshot",
]
