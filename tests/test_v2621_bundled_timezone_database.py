from datetime import datetime
from zoneinfo import ZoneInfo as RealZoneInfo, ZoneInfoNotFoundError

import src.user_time as user_time


class _NoSystemZoneInfo:
    def __new__(cls, key):
        raise ZoneInfoNotFoundError(key)

    @staticmethod
    def from_file(handle, key=None):
        return RealZoneInfo.from_file(handle, key=key)


def test_bundled_timezone_fallback_works_without_system_tzdata(monkeypatch):
    monkeypatch.setattr(user_time, "ZoneInfo", _NoSystemZoneInfo)
    assert user_time.validate_time_zone("Asia/Kolkata", fallback=None) == "Asia/Kolkata"
    assert user_time.format_profile_timestamp(
        "2026-09-30T05:39:51+00:00", "Asia/Kolkata"
    ) == "2026-09-30 11:09:51 IST"


def test_bundled_timezone_fallback_preserves_dst_rules(monkeypatch):
    monkeypatch.setattr(user_time, "ZoneInfo", _NoSystemZoneInfo)
    winter=user_time.format_profile_timestamp("2026-01-15T12:00:00Z", "Europe/London")
    summer=user_time.format_profile_timestamp("2026-07-15T12:00:00Z", "Europe/London")
    assert winter == "2026-01-15 12:00:00 GMT"
    assert summer == "2026-07-15 13:00:00 BST"


def test_bundled_timezone_rejects_unknown_or_traversal(monkeypatch):
    monkeypatch.setattr(user_time, "ZoneInfo", _NoSystemZoneInfo)
    for value in ("Mars/Olympus", "../Asia/Kolkata", "/etc/passwd"):
        try:
            user_time.validate_time_zone(value, fallback=None)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected invalid time zone: {value}")
