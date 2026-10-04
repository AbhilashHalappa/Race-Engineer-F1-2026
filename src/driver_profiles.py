"""Persistent Driver + per-game profile architecture for Race Engineer V2.1.2.

This layer deliberately sits above game telemetry/history. A Driver is the
human using Race Engineer; a game profile is a per-game container owned by that
Driver. No skill score is calculated here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import uuid
from typing import Any

from .app_paths import USER_DATA
from .user_time import DEFAULT_TIME_ZONE, validate_time_zone

SCHEMA_VERSION = 1
GAME_PROFILE_SCHEMA_VERSION = 1
SUPPORTED_GAMES: dict[str, dict[str, Any]] = {
    "f1_26": {"name": "F1 26", "discipline": "formula", "available": True},
    "acc": {"name": "Assetto Corsa Competizione", "discipline": "gt", "available": False},
    "dirt_rally_2": {"name": "Dirt Rally 2.0", "discipline": "rally", "available": False},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any, *, fallback: str = "") -> str:
    text = " ".join(str(value or "").strip().split())
    return text or fallback


@dataclass(frozen=True)
class DriverProfileRef:
    driver_id: str
    display_name: str
    active_game: str
    path: Path


@dataclass(frozen=True)
class GameProfileRef:
    game_id: str
    game_name: str
    discipline: str
    driver_id: str
    supported: bool
    path: Path


class DriverProfileStore:
    """Local/server-ready file store for person-level profiles.

    Layout::

        user_data/drivers/index.json
        user_data/drivers/<DRIVER_ID>/profile.json
        user_data/drivers/<DRIVER_ID>/career/
        user_data/drivers/<DRIVER_ID>/games/<GAME_ID>/profile.json
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else USER_DATA / "drivers"
        self.index_path = self.root / "index.json"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value
        except (OSError, ValueError, TypeError):
            return default

    @staticmethod
    def _write_json_atomic(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)

    def _index(self) -> dict[str, Any]:
        raw = self._read_json(self.index_path, {})
        if not isinstance(raw, dict):
            raw = {}
        drivers = raw.get("drivers")
        if not isinstance(drivers, list):
            drivers = []
        return {
            "schema_version": SCHEMA_VERSION,
            "active_driver_id": raw.get("active_driver_id"),
            "drivers": drivers,
        }

    def _save_index(self, index: dict[str, Any]) -> None:
        index = dict(index)
        index["schema_version"] = SCHEMA_VERSION
        self._write_json_atomic(self.index_path, index)

    def has_profiles(self) -> bool:
        return bool(self.list_profiles())

    def list_profiles(self) -> list[DriverProfileRef]:
        refs: list[DriverProfileRef] = []
        index = self._index()
        seen: set[str] = set()
        for row in index.get("drivers", []):
            if not isinstance(row, dict):
                continue
            driver_id = _clean_text(row.get("driver_id"))
            if not driver_id or driver_id in seen:
                continue
            path = self.root / driver_id / "profile.json"
            profile = self._read_json(path, {})
            if not isinstance(profile, dict) or str(profile.get("driver_id") or "") != driver_id:
                continue
            seen.add(driver_id)
            refs.append(DriverProfileRef(
                driver_id=driver_id,
                display_name=_clean_text(profile.get("display_name"), fallback="Driver"),
                active_game=_clean_text(profile.get("active_game"), fallback="f1_26"),
                path=path,
            ))
        return refs

    def profile_path(self, driver_id: str) -> Path:
        return self.root / str(driver_id) / "profile.json"

    def load_profile(self, driver_id: str) -> dict[str, Any] | None:
        profile = self._read_json(self.profile_path(driver_id), None)
        if not isinstance(profile, dict):
            return None
        if str(profile.get("driver_id") or "") != str(driver_id):
            return None
        return profile

    def active_driver_id(self) -> str | None:
        profiles = self.list_profiles()
        if not profiles:
            return None
        valid = {p.driver_id for p in profiles}
        preferred = str(self._index().get("active_driver_id") or "")
        if preferred in valid:
            return preferred
        return profiles[0].driver_id

    def active_profile(self) -> dict[str, Any] | None:
        driver_id = self.active_driver_id()
        if not driver_id:
            return None
        # V2.1.2 compatibility/repair path: older V2.1.x drivers may only have
        # the F1 container. Ensure every known game owns its own profile
        # container without touching telemetry or performance history.
        self.ensure_all_game_profiles(driver_id)
        profile = self.load_profile(driver_id)
        if isinstance(profile, dict) and not profile.get("time_zone"):
            profile["time_zone"] = DEFAULT_TIME_ZONE
            self._write_json_atomic(self.profile_path(driver_id), profile)
        return profile

    def set_active_driver(self, driver_id: str) -> bool:
        profile = self.load_profile(driver_id)
        if not profile:
            return False
        now = _utc_now()
        profile["last_active"] = now
        self._write_json_atomic(self.profile_path(driver_id), profile)
        index = self._index()
        index["active_driver_id"] = str(driver_id)
        for row in index.get("drivers", []):
            if isinstance(row, dict) and str(row.get("driver_id") or "") == str(driver_id):
                row["last_active"] = now
                row["display_name"] = profile.get("display_name")
                row["active_game"] = profile.get("active_game")
        self._save_index(index)
        return True

    def create_profile(
        self,
        display_name: str,
        *,
        country_region: str = "",
        units: str = "metric",
        time_zone: str = DEFAULT_TIME_ZONE,
        avatar_source: str | Path | None = None,
        active_game: str = "f1_26",
        compatibility: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        name = _clean_text(display_name)
        if not name:
            raise ValueError("Display name is required")
        units = str(units or "metric").strip().lower()
        if units not in {"metric", "imperial"}:
            raise ValueError("Units must be metric or imperial")
        time_zone = validate_time_zone(time_zone, fallback=None)
        if active_game not in SUPPORTED_GAMES:
            raise ValueError(f"Unsupported game profile: {active_game}")
        if not SUPPORTED_GAMES[active_game]["available"]:
            raise ValueError(f"{SUPPORTED_GAMES[active_game]['name']} support is not available yet")

        driver_id = uuid.uuid4().hex
        created = _utc_now()
        driver_dir = self.root / driver_id
        career_dir = driver_dir / "career"
        games_dir = driver_dir / "games"
        career_dir.mkdir(parents=True, exist_ok=False)
        games_dir.mkdir(parents=True, exist_ok=True)

        avatar_rel = None
        if avatar_source:
            src = Path(avatar_source)
            if src.is_file():
                ext = src.suffix.lower() if src.suffix else ".img"
                dst = driver_dir / ("avatar" + ext)
                shutil.copy2(src, dst)
                avatar_rel = dst.name

        profile = {
            "schema_version": SCHEMA_VERSION,
            "driver_id": driver_id,
            "display_name": name,
            "avatar": avatar_rel,
            "country_region": _clean_text(country_region),
            "units": units,
            "time_zone": time_zone,
            "created_at": created,
            "last_active": created,
            "active_game": active_game,
            "compatibility": dict(compatibility or {}),
        }
        self._write_json_atomic(driver_dir / "profile.json", profile)
        self._write_json_atomic(career_dir / "summary.json", {
            "schema_version": SCHEMA_VERSION,
            "driver_id": driver_id,
            "total_driving_seconds": 0,
            "total_sessions": 0,
            "total_laps": 0,
            "total_distance_m": 0.0,
        })
        # Game Profile architecture exists from day one for every supported
        # discipline, even when the telemetry adapter is not available yet.
        self.ensure_all_game_profiles(driver_id)

        index = self._index()
        index.setdefault("drivers", []).append({
            "driver_id": driver_id,
            "display_name": name,
            "active_game": active_game,
            "created_at": created,
            "last_active": created,
        })
        index["active_driver_id"] = driver_id
        self._save_index(index)
        return profile

    def delete_profile(self, driver_id: str) -> bool:
        """Permanently delete one person-level Driver tree.

        This store only owns the Driver filesystem/index. Linked compatibility
        stores (Performance Hub) are cleaned by DriverContextManager so ownership
        boundaries remain explicit. The last remaining Driver cannot be removed.
        """
        driver_id = str(driver_id or "").strip()
        profile = self.load_profile(driver_id)
        if not profile:
            return False
        refs = self.list_profiles()
        if len(refs) <= 1:
            raise ValueError("The only remaining Driver Profile cannot be deleted")

        index = self._index()
        rows = [row for row in index.get("drivers", [])
                if not (isinstance(row, dict) and str(row.get("driver_id") or "") == driver_id)]
        remaining_ids = [str(row.get("driver_id") or "") for row in rows if isinstance(row, dict)]
        if not remaining_ids:
            raise ValueError("The only remaining Driver Profile cannot be deleted")
        if str(index.get("active_driver_id") or "") == driver_id:
            index["active_driver_id"] = remaining_ids[0]
        index["drivers"] = rows

        driver_dir = self.root / driver_id
        # Update the index only after the owned tree has been removed. If file
        # deletion fails, the Driver remains fully registered and recoverable.
        if driver_dir.exists():
            shutil.rmtree(driver_dir)
        self._save_index(index)
        return True

    def game_profile_path(self, driver_id: str, game_id: str) -> Path:
        return self.root / str(driver_id) / "games" / str(game_id) / "profile.json"

    def load_game_profile(self, driver_id: str, game_id: str) -> dict[str, Any] | None:
        if game_id not in SUPPORTED_GAMES:
            return None
        payload = self._read_json(self.game_profile_path(driver_id, game_id), None)
        if not isinstance(payload, dict):
            return None
        if str(payload.get("driver_id") or "") != str(driver_id):
            return None
        if str(payload.get("game_id") or "") != str(game_id):
            return None
        return payload

    def list_game_profiles(self, driver_id: str) -> list[GameProfileRef]:
        if not self.load_profile(driver_id):
            return []
        self.ensure_all_game_profiles(driver_id)
        refs: list[GameProfileRef] = []
        for game_id, spec in SUPPORTED_GAMES.items():
            payload = self.load_game_profile(driver_id, game_id)
            if not payload:
                continue
            refs.append(GameProfileRef(
                game_id=game_id,
                game_name=str(payload.get("game_name") or spec["name"]),
                discipline=str(payload.get("discipline") or spec["discipline"]),
                driver_id=str(driver_id),
                supported=bool(payload.get("supported", spec["available"])),
                path=self.game_profile_path(driver_id, game_id),
            ))
        return refs

    def ensure_all_game_profiles(self, driver_id: str) -> dict[str, dict[str, Any]]:
        if not self.load_profile(driver_id):
            raise ValueError("Driver profile does not exist")
        return {game_id: self.ensure_game_profile(driver_id, game_id) for game_id in SUPPORTED_GAMES}

    def ensure_game_profile(self, driver_id: str, game_id: str) -> dict[str, Any]:
        if game_id not in SUPPORTED_GAMES:
            raise ValueError(f"Unsupported game profile: {game_id}")
        profile = self.load_profile(driver_id)
        if not profile:
            raise ValueError("Driver profile does not exist")
        path = self.game_profile_path(driver_id, game_id)
        spec = SUPPORTED_GAMES[game_id]
        existing = self._read_json(path, None)
        if isinstance(existing, dict) and str(existing.get("driver_id") or "") == driver_id:
            # Non-destructive schema completion for profiles created by earlier
            # V2.1.x builds. Never reset counters or future evidence fields.
            changed = False
            defaults = {
                "schema_version": GAME_PROFILE_SCHEMA_VERSION,
                "game_id": game_id,
                "game_name": spec["name"],
                "discipline": spec["discipline"],
                "driver_id": driver_id,
                "created_at": _utc_now(),
                "driving_seconds": 0,
                "driving_time": {"practice": 0.0, "time_trial": 0.0, "qualifying": 0.0, "sprint": 0.0, "race": 0.0},
                "sessions": 0,
                "supported": bool(spec["available"]),
                "active": str(profile.get("active_game") or "f1_26") == game_id,
            }
            for key, value in defaults.items():
                if key not in existing:
                    existing[key] = value
                    changed = True
            # Adapter availability is application capability, not user data.
            if existing.get("supported") != bool(spec["available"]):
                existing["supported"] = bool(spec["available"]); changed = True
            if changed:
                self._write_json_atomic(path, existing)
            return existing
        payload = {
            "schema_version": GAME_PROFILE_SCHEMA_VERSION,
            "game_id": game_id,
            "game_name": spec["name"],
            "discipline": spec["discipline"],
            "driver_id": driver_id,
            "created_at": _utc_now(),
            "driving_seconds": 0,
            "driving_time": {"practice": 0.0, "time_trial": 0.0, "qualifying": 0.0, "sprint": 0.0, "race": 0.0},
            "sessions": 0,
            "supported": bool(spec["available"]),
            "active": str(profile.get("active_game") or "f1_26") == game_id,
        }
        self._write_json_atomic(path, payload)
        return payload

    def save_game_profile(self, driver_id: str, game_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist metadata for an owned game profile without changing identity."""
        if game_id not in SUPPORTED_GAMES:
            raise ValueError(f"Unsupported game profile: {game_id}")
        if not self.load_profile(driver_id):
            raise ValueError("Driver profile does not exist")
        data = dict(payload or {})
        data["schema_version"] = GAME_PROFILE_SCHEMA_VERSION
        data["game_id"] = game_id
        data["game_name"] = SUPPORTED_GAMES[game_id]["name"]
        data["discipline"] = SUPPORTED_GAMES[game_id]["discipline"]
        data["driver_id"] = str(driver_id)
        data["supported"] = bool(SUPPORTED_GAMES[game_id]["available"])
        self._write_json_atomic(self.game_profile_path(driver_id, game_id), data)
        return data

    def career_summary_path(self, driver_id: str) -> Path:
        return self.root / str(driver_id) / "career" / "summary.json"

    def load_career_summary(self, driver_id: str) -> dict[str, Any]:
        payload = self._read_json(self.career_summary_path(driver_id), {})
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("schema_version", SCHEMA_VERSION)
        payload.setdefault("driver_id", str(driver_id))
        payload.setdefault("total_driving_seconds", 0)
        payload.setdefault("total_sessions", 0)
        payload.setdefault("total_laps", 0)
        payload.setdefault("total_distance_m", 0.0)
        return payload

    def save_career_summary(self, driver_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.load_profile(driver_id):
            raise ValueError("Driver profile does not exist")
        data = dict(payload or {})
        data["schema_version"] = SCHEMA_VERSION
        data["driver_id"] = str(driver_id)
        self._write_json_atomic(self.career_summary_path(driver_id), data)
        return data

    def update_personal_info(
        self,
        driver_id: str,
        *,
        display_name: str | None = None,
        country_region: str | None = None,
        units: str | None = None,
        time_zone: str | None = None,
    ) -> dict[str, Any] | None:
        """Edit personal fields without ever changing the persistent Driver ID."""
        profile = self.load_profile(driver_id)
        if not profile:
            return None
        if display_name is not None:
            clean = _clean_text(display_name)
            if not clean:
                raise ValueError("Display name is required")
            profile["display_name"] = clean
        if country_region is not None:
            profile["country_region"] = _clean_text(country_region)
        if units is not None:
            clean_units = str(units or "").strip().lower()
            if clean_units not in {"metric", "imperial"}:
                raise ValueError("Units must be metric or imperial")
            profile["units"] = clean_units
        if time_zone is not None:
            profile["time_zone"] = validate_time_zone(time_zone, fallback=None)
        elif not profile.get("time_zone"):
            profile["time_zone"] = DEFAULT_TIME_ZONE
        profile["last_active"] = _utc_now()
        self._write_json_atomic(self.profile_path(driver_id), profile)
        index = self._index()
        for row in index.get("drivers", []):
            if isinstance(row, dict) and str(row.get("driver_id") or "") == str(driver_id):
                row["display_name"] = profile.get("display_name")
                row["last_active"] = profile["last_active"]
        self._save_index(index)
        return profile


    def avatar_path(self, driver_id: str) -> Path | None:
        profile = self.load_profile(driver_id)
        if not profile:
            return None
        rel = _clean_text(profile.get("avatar"))
        if not rel:
            return None
        path = self.root / str(driver_id) / rel
        return path if path.is_file() else None

    def update_avatar(self, driver_id: str, avatar_source: str | Path | None) -> dict[str, Any] | None:
        """Replace or clear the optional avatar without changing Driver ID."""
        profile = self.load_profile(driver_id)
        if not profile:
            return None
        driver_dir = self.root / str(driver_id)
        old_rel = _clean_text(profile.get("avatar"))
        if old_rel:
            old = driver_dir / old_rel
            try:
                if old.is_file():
                    old.unlink()
            except OSError:
                pass
        avatar_rel = None
        if avatar_source:
            src = Path(avatar_source)
            if not src.is_file():
                raise ValueError("Avatar image does not exist")
            ext = src.suffix.lower() if src.suffix else ".img"
            dst = driver_dir / ("avatar" + ext)
            shutil.copy2(src, dst)
            avatar_rel = dst.name
        profile["avatar"] = avatar_rel
        profile["last_active"] = _utc_now()
        self._write_json_atomic(self.profile_path(driver_id), profile)
        index = self._index()
        for row in index.get("drivers", []):
            if isinstance(row, dict) and str(row.get("driver_id") or "") == str(driver_id):
                row["last_active"] = profile["last_active"]
        self._save_index(index)
        return profile

    def set_compatibility_value(self, driver_id: str, key: str, value: Any) -> bool:
        profile = self.load_profile(driver_id)
        if not profile:
            return False
        compat = profile.get("compatibility")
        if not isinstance(compat, dict):
            compat = {}
        compat[str(key)] = value
        profile["compatibility"] = compat
        self._write_json_atomic(self.profile_path(driver_id), profile)
        return True

    def set_active_game(self, driver_id: str, game_id: str) -> bool:
        """Select exactly one active Game Profile for a Driver.

        Game-profile selection is independent from telemetry-adapter availability.
        ACC and Dirt containers can therefore be selected before their adapters are
        implemented; their profile remains active but receives no telemetry-derived
        evidence until support exists.
        """
        if game_id not in SUPPORTED_GAMES:
            return False
        profile = self.load_profile(driver_id)
        if not profile:
            return False
        self.ensure_all_game_profiles(driver_id)
        now = _utc_now()
        profile["active_game"] = game_id
        profile["last_active"] = now
        self._write_json_atomic(self.profile_path(driver_id), profile)

        # Keep an explicit mirror in each game container as well as the single
        # authoritative person-level active_game field. This makes the invariant
        # inspectable on disk: exactly one container is active at a time.
        for candidate in SUPPORTED_GAMES:
            game_profile = self.load_game_profile(driver_id, candidate) or {}
            game_profile["active"] = candidate == game_id
            if candidate == game_id:
                game_profile["last_active"] = now
            self._write_json_atomic(self.game_profile_path(driver_id, candidate), game_profile)

        index = self._index()
        for row in index.get("drivers", []):
            if isinstance(row, dict) and str(row.get("driver_id") or "") == driver_id:
                row["active_game"] = game_id
                row["last_active"] = now
        index["active_driver_id"] = driver_id
        self._save_index(index)
        return True
