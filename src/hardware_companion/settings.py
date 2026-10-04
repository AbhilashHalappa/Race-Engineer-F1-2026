from __future__ import annotations

import json
from pathlib import Path

from ..app_paths import USER_DATA

DEFAULTS = {
    "receiver_port": "auto",
    "brake_sensor_mode": "analog",
    "brake_load_cell_capacity_kg": 40.0,
    "brake_max_force_kg": 40.0,
    "handbrake_sensor_mode": "hall",
    "handbrake_load_cell_capacity_kg": 40.0,
    "handbrake_max_force_kg": 40.0,
}


def settings_path() -> Path:
    return Path(USER_DATA) / "hardware" / "wheel_companion.json"


def load_settings() -> dict:
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result = dict(DEFAULTS)
        if isinstance(data, dict):
            result.update({k: data[k] for k in DEFAULTS if k in data})
        return result
    except Exception:
        return dict(DEFAULTS)


def save_settings(settings: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = dict(DEFAULTS)
    clean.update({k: settings[k] for k in DEFAULTS if k in settings})
    path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
