"""UI-independent click-through routing rules.

The Control Center is the permanent escape hatch: it must never be made mouse
transparent, otherwise click-through cannot be disabled from the UI.
"""
from __future__ import annotations


def click_through_targets(windows, control_center):
    """Return overlay windows that may safely receive click-through state."""
    return tuple(window for window in windows if window is not control_center)
