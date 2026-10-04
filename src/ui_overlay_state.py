"""Small local UI-only state store for overlay geometry and presentation.

The file is intentionally separate from session/performance persistence.
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

_STATE_PATH = Path("settings") / "ui_overlay_state.json"
_LOCK = RLock()


def _read_all() -> dict:
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def read_overlay_state(key: str) -> dict:
    with _LOCK:
        value = _read_all().get(str(key), {})
        return dict(value) if isinstance(value, dict) else {}


def write_overlay_state(key: str, state: dict) -> None:
    with _LOCK:
        data = _read_all()
        data[str(key)] = dict(state)
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp = _STATE_PATH.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(_STATE_PATH)
