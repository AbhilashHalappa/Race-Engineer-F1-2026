"""Portable local reference ecosystem for Race Engineer.

This module deliberately sits above the long-standing RACE_ENGINEER_REFERENCE_LAP
format.  Runtime coaching still consumes the proven raw reference lap/model files;
portable friend packages add checksummed metadata, compatibility and install/export
without forcing existing references to be rebuilt.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .reference_lap import load_reference_lap
from .reference_model import (
    REFERENCE_COMPILER_ID,
    raw_reference_fingerprint,
    validate_reference_lap as validate_compiled_reference_lap,
    load_reference_model,
)

PACKAGE_SCHEMA = "RACE_ENGINEER_REFERENCE_PACKAGE"
PACKAGE_VERSION = 2
MANIFEST_NAME = "manifest.json"
REFERENCE_NAME = "reference.json"
MODEL_NAME = "reference_model.json"
ZONES_NAME = "coaching_zones.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_name(value: Any, fallback: str = "reference") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return value[:80] or fallback


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def normalized_metadata(metadata: dict[str, Any] | None, lap: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the formal V2 metadata view without fabricating absent values."""
    md = dict(metadata or {})
    lap = dict(lap or {})
    assists = {
        "traction_control": md.get("traction_control"),
        "anti_lock_brakes": md.get("anti_lock_brakes"),
        "gearbox_assist": md.get("gearbox_assist"),
    }
    assists = {k: v for k, v in assists.items() if v is not None}
    setup = dict(md.get("setup") or {}) if isinstance(md.get("setup"), dict) else {}
    if md.get("custom_setup_used") is not None:
        setup.setdefault("custom_setup_used", md.get("custom_setup_used"))
    weather = {
        "weather": md.get("weather"),
        "track_temperature_c": md.get("track_temperature_c"),
        "air_temperature_c": md.get("air_temperature_c"),
    }
    weather = {k: v for k, v in weather.items() if v is not None}
    tyre = dict(md.get("tyre") or {}) if isinstance(md.get("tyre"), dict) else {}
    for src, dst in (("actual_tyre_compound", "actual_compound"), ("visual_tyre_compound", "visual_compound"), ("tyre_age_laps", "age_laps")):
        if md.get(src) is not None:
            tyre.setdefault(dst, md.get(src))
    fuel = dict(md.get("fuel") or {}) if isinstance(md.get("fuel"), dict) else {}
    for src, dst in (("fuel_at_start_kg", "start_kg"), ("fuel_load_kg", "start_kg")):
        if md.get(src) is not None:
            fuel.setdefault(dst, md.get(src))

    return {
        "game": {
            "year": md.get("game_year"),
            "version": md.get("game_version"),
            "formula": md.get("formula"),
        },
        "track": {
            "id": md.get("track_id"),
            "name": lap.get("track_name") or md.get("track_name") or md.get("track"),
            "length_m": lap.get("track_length_m") or md.get("track_length_m"),
        },
        "car": {
            "team_id": md.get("team_id"),
            "car_index": md.get("car_index"),
            "equal_performance": md.get("equal_car_performance"),
        },
        "driver": {
            "name": md.get("driver") or md.get("name"),
            "driver_id": md.get("driver_id"),
        },
        "session": {
            "session_type": md.get("session_type"),
            "session_uid": md.get("session_uid"),
        },
        "assists": assists,
        "setup": setup,
        "conditions": weather,
        "tyre": tyre,
        "fuel": fuel,
        "source": md.get("source"),
        "lap": {
            "number": md.get("reference_lap_number", lap.get("lap")),
            "time_s": md.get("reference_lap_time_s", lap.get("lap_time_s")),
            "sector1_s": md.get("sector1_time_s", lap.get("sector1_time_s")),
            "sector2_s": md.get("sector2_time_s", lap.get("sector2_time_s")),
            "sector3_s": md.get("sector3_time_s", lap.get("sector3_time_s")),
        },
    }


def _flatten_context(context: dict[str, Any] | None) -> dict[str, Any]:
    """Accept either normalized V2 metadata or a flat runtime metadata dict."""
    ctx = dict(context or {})
    if "track" in ctx or "game" in ctx or "car" in ctx:
        return ctx
    return normalized_metadata(ctx, {})


def reference_quality(lap: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Expose compiler quality plus a stable user-facing grade/score."""
    q = dict(validate_compiled_reference_lap(lap, metadata or {}))
    score = 100
    reasons = list(q.get("reasons") or ())
    if not q.get("accepted"):
        score = min(score, 40)
    sample_count = int(lap.get("sample_count") or len(lap.get("_samples") or {}))
    length = float(lap.get("track_length_m") or (metadata or {}).get("track_length_m") or q.get("track_length_m") or 0.0)
    if sample_count < 100:
        score -= 35
    elif length > 0 and sample_count < max(200, int(length / 20.0)):
        score -= 15
    if not _num(lap.get("lap_time_s")) or float(lap.get("lap_time_s") or 0) <= 0:
        score -= 50
    if not lap.get("_samples"):
        score -= 50
    if q.get("input_telemetry_trusted") is False:
        # Pace-only TT rivals are valid but intentionally have less technique authority.
        score -= 8
    score = max(0, min(100, score))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
    return {
        "accepted": bool(q.get("accepted")),
        "score": score,
        "grade": grade,
        "reasons": reasons,
        "sample_count": sample_count,
        "track_length_m": length or None,
        "input_telemetry_trusted": q.get("input_telemetry_trusted"),
        "compiler_quality": q,
    }


def compatibility_report(reference_metadata: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare normalized package metadata with the active target context.

    Missing values are reported as unknown rather than guessed.  Hard mismatches are
    restricted to identities that can make a lap invalid as a coaching reference.
    """
    ref = _flatten_context(reference_metadata)
    cur = _flatten_context(context)
    blockers: list[str] = []
    warnings: list[str] = []
    matches: list[str] = []
    unknown: list[str] = []

    def val(root, section, key):
        s = root.get(section) if isinstance(root, dict) else None
        return s.get(key) if isinstance(s, dict) else None

    def compare(section, key, label, *, blocking=False, tolerance=None):
        a, b = val(ref, section, key), val(cur, section, key)
        if a is None or b is None:
            unknown.append(label); return
        same = abs(float(a)-float(b)) <= tolerance if tolerance is not None and _num(a) and _num(b) else str(a) == str(b)
        if same:
            matches.append(label)
        elif blocking:
            blockers.append(f"{label}_mismatch")
        else:
            warnings.append(f"{label}_mismatch")

    compare("track", "id", "track", blocking=True)
    compare("track", "length_m", "track_length", blocking=True, tolerance=25.0)
    compare("game", "year", "game_year", blocking=True)
    compare("game", "version", "game_version", blocking=False)
    compare("game", "formula", "formula", blocking=True)
    compare("car", "equal_performance", "equal_performance", blocking=True)

    # Team identity only matters when both contexts explicitly use unequal cars.
    eq_ref, eq_cur = val(ref, "car", "equal_performance"), val(cur, "car", "equal_performance")
    team_blocking = eq_ref == 0 and eq_cur == 0
    compare("car", "team_id", "team", blocking=team_blocking)

    for key in ("traction_control", "anti_lock_brakes", "gearbox_assist"):
        compare("assists", key, f"assist_{key}", blocking=False)
    compare("setup", "custom_setup_used", "setup", blocking=False)
    compare("conditions", "weather", "weather", blocking=False)
    compare("tyre", "actual_compound", "tyre_compound", blocking=False)
    compare("fuel", "start_kg", "fuel_load", blocking=False, tolerance=0.5)

    return {
        "compatible": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "matches": matches,
        "unknown": unknown,
    }


def _reference_payload(source: Path) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    lap, meta = load_reference_lap(source)
    raw = source.read_bytes()
    return lap, meta, raw


def export_reference_package(source: str | Path, output: str | Path, *, author: str | None = None, label: str | None = None) -> dict[str, Any]:
    """Export an existing runtime reference as a portable checksummed friend pack."""
    source = Path(source)
    output = Path(output)
    lap, meta, raw = _reference_payload(source)
    quality = reference_quality(lap, meta)
    normalized = normalized_metadata(meta, lap)
    fingerprint = raw_reference_fingerprint(lap, meta)
    model_authority = False
    track_label = (normalized.get("track") or {}).get("name") or (normalized.get("track") or {}).get("id") or source.parent.name
    driver = (normalized.get("driver") or {}).get("name") or source.stem
    package_id = _safe_name(f"{track_label}_{driver}_{fingerprint[:12]}").lower()

    files: dict[str, dict[str, Any]] = {}
    blobs: dict[str, bytes] = {REFERENCE_NAME: raw}
    files[REFERENCE_NAME] = {"sha256": _sha256_bytes(raw), "bytes": len(raw), "required": True}

    model_path = source.parent / MODEL_NAME
    zones_path = source.parent / ZONES_NAME
    if model_path.exists():
        try:
            model = load_reference_model(model_path)
            if str((model.metadata or {}).get("raw_reference_fingerprint") or "") == fingerprint and bool((model.quality or {}).get("accepted")):
                model_authority = True
                data = model_path.read_bytes(); blobs[MODEL_NAME] = data
                files[MODEL_NAME] = {"sha256": _sha256_bytes(data), "bytes": len(data), "required": False, "compiler_id": (model.metadata or {}).get("reference_compiler_id")}
                if zones_path.exists():
                    z = zones_path.read_bytes(); blobs[ZONES_NAME] = z
                    files[ZONES_NAME] = {"sha256": _sha256_bytes(z), "bytes": len(z), "required": False}
        except Exception:
            # A stale/incompatible compiled model is intentionally omitted; runtime can compile locally.
            pass

    if not quality["accepted"] and not model_authority:
        raise ValueError("reference failed quality validation: " + ", ".join(quality.get("reasons") or ["unknown reason"]))
    quality_summary={k: v for k, v in quality.items() if k != "compiler_quality"}
    quality_summary["raw_accepted"]=bool(quality.get("accepted"))
    quality_summary["compiled_model_authority"]=bool(model_authority)
    quality_summary["accepted"]=bool(quality.get("accepted") or model_authority)
    if model_authority and not quality.get("accepted"):
        quality_summary["legacy_raw_warning"]="raw source fails current validator; authenticated compiled model remains authoritative"

    manifest = {
        "schema": PACKAGE_SCHEMA,
        "version": PACKAGE_VERSION,
        "package_id": package_id,
        "label": label or f"{track_label} — {driver}",
        "author": author,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "metadata": normalized,
        "quality": quality_summary,
        "raw_reference_fingerprint": fingerprint,
        "reference_compiler_id": REFERENCE_COMPILER_ID,
        "files": files,
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True, default=str).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, manifest_bytes)
        for name, data in blobs.items():
            zf.writestr(name, data)
    return {"path": str(output), "manifest": manifest, "quality": quality_summary}


def inspect_reference_package(package: str | Path, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    package = Path(package)
    with ZipFile(package, "r") as zf:
        names = set(zf.namelist())
        if MANIFEST_NAME not in names or REFERENCE_NAME not in names:
            raise ValueError("reference package is missing manifest/reference")
        manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        if manifest.get("schema") != PACKAGE_SCHEMA or int(manifest.get("version") or 0) != PACKAGE_VERSION:
            raise ValueError("unsupported reference package schema/version")
        checks: list[str] = []
        for name, info in (manifest.get("files") or {}).items():
            if name not in names:
                if info.get("required"):
                    raise ValueError(f"reference package is missing required file: {name}")
                checks.append(f"optional_missing:{name}"); continue
            actual = _sha256_bytes(zf.read(name))
            if actual != str(info.get("sha256") or ""):
                raise ValueError(f"checksum mismatch: {name}")
            checks.append(f"checksum_ok:{name}")
        raw = zf.read(REFERENCE_NAME)
        model_authority=False
        with tempfile.TemporaryDirectory(prefix="race_engineer_ref_") as td:
            p = Path(td) / REFERENCE_NAME; p.write_bytes(raw)
            lap, meta = load_reference_lap(p)
            quality = reference_quality(lap, meta)
            fp = raw_reference_fingerprint(lap, meta)
            if MODEL_NAME in names:
                mp=Path(td)/MODEL_NAME; mp.write_bytes(zf.read(MODEL_NAME))
                try:
                    model=load_reference_model(mp)
                    model_authority=bool((model.quality or {}).get("accepted")) and str((model.metadata or {}).get("raw_reference_fingerprint") or "")==fp
                except Exception:
                    model_authority=False
        if fp != manifest.get("raw_reference_fingerprint"):
            raise ValueError("reference fingerprint does not match package manifest")
        overall=bool(quality.get("accepted") or model_authority)
        quality=dict(quality); quality["raw_accepted"]=bool(quality.get("accepted")); quality["compiled_model_authority"]=model_authority; quality["accepted"]=overall
        if model_authority and not quality["raw_accepted"]:
            quality["legacy_raw_warning"]="raw source fails current validator; authenticated compiled model remains authoritative"
        compat = compatibility_report(manifest.get("metadata") or normalized_metadata(meta, lap), context)
        return {"valid": overall, "manifest": manifest, "quality": quality, "compatibility": compat, "checks": checks}


def install_reference_package(package: str | Path, *, root: str | Path = "references", context: dict[str, Any] | None = None, allow_incompatible: bool = False) -> dict[str, Any]:
    """Validate then install a portable pack without replacing existing references."""
    package = Path(package)
    report = inspect_reference_package(package, context=context)
    if not report["quality"].get("accepted"):
        raise ValueError("reference quality validation failed")
    if not report["compatibility"].get("compatible") and not allow_incompatible:
        raise ValueError("reference is incompatible: " + ", ".join(report["compatibility"].get("blockers") or ()))
    manifest = report["manifest"]
    track = (manifest.get("metadata") or {}).get("track") or {}
    track_name = track.get("name") or f"TRACK_{track.get('id','UNKNOWN')}"
    package_id = _safe_name(manifest.get("package_id"), "imported_reference")
    dest = Path(root) / "imported" / _safe_name(track_name).upper() / package_id
    dest.mkdir(parents=True, exist_ok=True)
    with ZipFile(package, "r") as zf:
        for src, target in ((REFERENCE_NAME, REFERENCE_NAME), (MODEL_NAME, MODEL_NAME), (ZONES_NAME, ZONES_NAME)):
            if src in zf.namelist():
                (dest / target).write_bytes(zf.read(src))
    # Persist a local copy of the manifest as provenance; runtime ignores it.
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    # Re-validate the exact installed source.
    lap, meta = load_reference_lap(dest / REFERENCE_NAME)
    installed_quality = reference_quality(lap, meta)
    if not report.get("valid"):
        shutil.rmtree(dest, ignore_errors=True)
        raise ValueError("installed reference failed post-copy validation")
    installed_quality["accepted"]=True
    installed_quality["compiled_model_authority"]=bool(report.get("quality",{}).get("compiled_model_authority"))
    return {"installed": True, "path": str(dest / REFERENCE_NAME), "folder": str(dest), "manifest": manifest, "quality": installed_quality, "compatibility": report["compatibility"]}


def list_installed_references(root: str | Path = "references") -> list[dict[str, Any]]:
    root = Path(root)
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows
    candidates = list(root.glob("*.json")) + list(root.glob("*/rival_reference.json")) + list(root.glob("imported/*/*/reference.json"))
    seen = set()
    for path in sorted(candidates):
        try: key = str(path.resolve())
        except OSError: key = str(path)
        if key in seen: continue
        seen.add(key)
        try:
            lap, meta = load_reference_lap(path)
            quality = reference_quality(lap, meta)
        except Exception as error:
            rows.append({"path": str(path), "valid": False, "error": str(error)})
            continue
        manifest_path = path.parent / MANIFEST_NAME
        manifest = None
        if manifest_path.exists():
            try: manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception: manifest = None
        rows.append({
            "path": str(path), "valid": bool(quality.get("accepted")), "quality": quality,
            "metadata": normalized_metadata(meta, lap), "manifest": manifest,
            "lap_time_s": lap.get("lap_time_s"),
        })
    return rows
