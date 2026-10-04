"""Small presentation helpers that do not depend on Qt."""
from __future__ import annotations


def coach_button_text(name: str, value: str | None) -> str:
    """Keep the coaching feature name visible while also showing its state."""
    state = "ON" if str(value or "").lower() in {"enabled", "on", "active"} else "OFF"
    return f"{name} {state}"
