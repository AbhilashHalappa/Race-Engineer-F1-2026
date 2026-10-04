"""Opt-in update checker. Never downloads or installs updates automatically."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re
from urllib.request import Request, urlopen

CURRENT_VERSION = "2.0.0"


@dataclass(frozen=True, slots=True)
class UpdateStatus:
    ok: bool
    current_version: str
    latest_version: str | None = None
    update_available: bool | None = None
    release_url: str | None = None
    error: str | None = None
    def to_dict(self): return asdict(self)


def _version_tuple(value: str) -> tuple[int, ...]:
    nums = [int(x) for x in re.findall(r"\d+", str(value))[:4]]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums)


def check_for_updates(url: str, *, timeout: float = 3.0, current_version: str = CURRENT_VERSION) -> UpdateStatus:
    try:
        req = Request(url, headers={"User-Agent": f"RaceEngineer/{current_version}", "Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=max(0.5, float(timeout))) as response:  # noqa: S310 - configured HTTPS endpoint
            raw = json.loads(response.read(512_000).decode("utf-8"))
        tag = str(raw.get("tag_name") or raw.get("name") or "").strip()
        if not tag:
            raise ValueError("release response has no tag/name")
        return UpdateStatus(True, current_version, tag, _version_tuple(tag) > _version_tuple(current_version), str(raw.get("html_url") or "") or None)
    except Exception as error:
        return UpdateStatus(False, current_version, error=str(error))
