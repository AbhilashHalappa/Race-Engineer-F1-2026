"""Profile-selected time-zone helpers.

Persisted application timestamps remain UTC. Presentation converts them into the
active Driver Profile's selected IANA time zone so changing the profile setting
never rewrites historical records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIME_ZONE = "UTC"
COMMON_TIME_ZONES = (
    "UTC",
    "Asia/Kolkata",
    "Asia/Dubai",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Australia/Sydney",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
)


_BUNDLED_ZONEINFO_ROOT = Path(__file__).resolve().parent / "_tzdata" / "zoneinfo"


def _safe_zone_path(name: str) -> Path | None:
    # IANA identifiers are slash-separated relative paths. Refuse traversal or
    # absolute paths before touching the bundled database.
    parts = [part for part in str(name or "").split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        return None
    path = _BUNDLED_ZONEINFO_ROOT.joinpath(*parts)
    try:
        path.relative_to(_BUNDLED_ZONEINFO_ROOT)
    except ValueError:
        return None
    return path


def resolve_time_zone(value: Any):
    """Return a tzinfo for an IANA name, using bundled tzdata on Windows.

    Python's stdlib zoneinfo normally reads the operating system database.
    Windows installations often do not ship that database, so Race Engineer
    includes its own copy and falls back to ZoneInfo.from_file().
    """
    name = str(value or "").strip()
    if not name:
        raise ValueError("Time zone is required")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as system_exc:
        path = _safe_zone_path(name)
        if path is not None and path.is_file():
            try:
                with path.open("rb") as handle:
                    return ZoneInfo.from_file(handle, key=name)
            except (OSError, ValueError) as bundled_exc:
                raise ValueError(f"Unknown IANA time zone: {name}") from bundled_exc
        raise ValueError(f"Unknown IANA time zone: {name}") from system_exc


def validate_time_zone(value: Any, *, fallback: str | None = DEFAULT_TIME_ZONE) -> str:
    name = str(value or "").strip()
    if not name:
        if fallback is None:
            raise ValueError("Time zone is required")
        name = str(fallback)
    try:
        resolve_time_zone(name)
    except ValueError:
        if fallback is not None and name != fallback:
            return validate_time_zone(fallback, fallback=None)
        raise
    return name


def parse_utc_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        # Stored historical timestamps without an explicit suffix were written as
        # UTC by Race Engineer, so preserve that compatibility here.
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def format_profile_timestamp(value: Any, time_zone: str | None, *, include_zone: bool = True) -> str:
    dt = parse_utc_timestamp(value)
    if dt is None:
        return "--"
    zone_name = validate_time_zone(time_zone)
    local = dt.astimezone(resolve_time_zone(zone_name))
    base = local.strftime("%Y-%m-%d %H:%M:%S")
    if not include_zone:
        return base
    label = local.tzname() or zone_name
    return f"{base} {label}"


def sort_timestamp_desc(rows: list[dict[str, Any]], key: str = "timestamp") -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]):
        dt = parse_utc_timestamp(row.get(key))
        return dt or datetime.min.replace(tzinfo=timezone.utc)
    return sorted((x for x in rows if isinstance(x, dict)), key=sort_key, reverse=True)
