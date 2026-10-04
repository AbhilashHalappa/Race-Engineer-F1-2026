"""V2.0.11 validation, calibration and source-freeze helpers.

This module is deliberately read-only with respect to Race Engineer runtime data.
It audits the protected V2 baseline, validation coverage and release hygiene; it
never recalculates driving scores, mutates Performance History or opens overlays.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import hashlib
import json

V2_011_VERSION = "2.0.11.0"
PROTECTED_BASELINE_TAG = "V2.9.1.3.5.37"
SOURCE_FREEZE_MANIFEST = "V2_SOURCE_FREEZE_MANIFEST.json"
SETUP_LAB_SCOPE = "skipped_by_user_scope"

# User/runtime data must never be included in a release ZIP or modified by the
# validation harness. Keep this aligned with the packaging protection introduced
# after the .32 data-loss regression.
MUTABLE_ROOTS = {
    "analysis", "user_data", "settings", "recordings", "logs", "references", "maps",
    "validation_bundles", "recovery_20261003",
}


@dataclass(frozen=True, slots=True)
class ValidationGate:
    gate_id: str
    category: str
    requirement: str
    automated_evidence: tuple[str, ...]
    recording_required: bool = False
    scope_status: str = "required"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validation_matrix() -> tuple[ValidationGate, ...]:
    """Authoritative V2.0.11 acceptance matrix.

    Existing proven tests are reused rather than duplicating scoring/runtime
    algorithms inside a new validator. Setup Lab remains intentionally excluded
    because V2.0.8 was cancelled by user scope.
    """
    return (
        ValidationGate("score_contract", "scoring", "monotonic scoring, deadbands, N/A, confidence/sample gates and versioned evidence",
                       ("tests/test_v200_score_contract.py", "tests/test_v203_performance_review_core.py")),
        ValidationGate("telemetry_quality", "telemetry_quality", "invalid/pit/traffic/restart/damage/wet-dry quality gates",
                       ("tests/test_measured_performance_v092.py", "tests/test_v2913527_traffic_lapdata_integrity.py", "tests/test_v2042_per_lap_corner_validity_hotfix.py")),
        ValidationGate("live_runtime", "runtime", "latency, arbitration, anti-spam/cooldown and bounded long-session state",
                       ("tests/test_runtime_v03.py", "tests/test_finalization_d_long_session_bounds.py", "tests/test_finalization_g_cooldown_runtime.py", "tests/test_v1303_driver_radio_priority.py")),
        ValidationGate("review_parity", "review", "replay read-only history, live/replay review parity and cursor/navigation synchronization",
                       ("tests/test_v1400_replay_session_analysis.py", "tests/test_v2060_replay_linked_telemetry_workstation.py", "tests/test_v2062_replay_workstation_playback_activation.py", "tests/test_v1921_performance_history_completion.py")),
        ValidationGate("driver_isolation", "review", "driver-scoped history, profile switching and canonical skill reconciliation",
                       ("tests/test_v270_multi_driver_switching.py", "tests/test_v2031_local_driver_profile_session_filters.py::test_local_profile_owns_sessions_across_different_game_drivers", "tests/test_v2031_local_driver_profile_session_filters.py::test_session_and_game_mode_filters_are_independent", "tests/test_v2031_local_driver_profile_session_filters.py::test_multiple_local_profiles_are_explicitly_separate", "tests/test_v240_f1_driver_skill_v1.py")),
        ValidationGate("condition_segmentation", "review", "dry/wet/unknown evidence remains condition-scoped",
                       ("tests/test_v2913525_track_practice_weather_session_policy.py", "tests/test_track_practice_scope.py")),
        ValidationGate("setup_comparability", "review", "Setup A/B comparison gates", (), scope_status=SETUP_LAB_SCOPE),
        ValidationGate("melbourne_damage_sc_pit", "recording_acceptance", "supplied Melbourne damage/SC/pit recording", (), True),
        ValidationGate("weekend_pqr", "recording_acceptance", "full Practice -> Qualifying -> Race weekend recording", (), True),
        ValidationGate("stored_tt_qual_race", "recording_acceptance", "stored Time Trial / Qualifying / Race recordings", (), True),
        ValidationGate("corner_coach_corpus", "recording_acceptance", "CORNER COACH validation corpus", ("tests/test_v1112_corner_coach_validation_trace.py",), True),
    )


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_source_freeze_manifest(root: str | Path) -> dict[str, Any]:
    p = Path(root) / SOURCE_FREEZE_MANIFEST
    return json.loads(p.read_text(encoding="utf-8"))


def verify_source_freeze(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    manifest = load_source_freeze_manifest(root)
    rows: list[dict[str, Any]] = []
    ok = True
    for item in manifest.get("files", []):
        rel = str(item.get("path") or "")
        p = root / rel
        actual = sha256_file(p) if p.is_file() else None
        expected = item.get("sha256")
        same = bool(actual and actual == expected)
        rows.append({"path": rel, "ok": same, "expected": expected, "actual": actual})
        ok = ok and same
    return {
        "ok": ok,
        "baseline": manifest.get("protected_baseline_tag"),
        "setup_lab": manifest.get("setup_lab"),
        "checked_files": len(rows),
        "files": rows,
    }


def validate_matrix_files(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    missing: list[str] = []
    checked: list[str] = []
    for gate in validation_matrix():
        for rel in gate.automated_evidence:
            checked.append(rel)
            file_rel = rel.split("::", 1)[0]
            if not (root / file_rel).is_file():
                missing.append(rel)
    return {"ok": not missing, "checked": sorted(set(checked)), "missing": sorted(set(missing))}


def validate_setup_lab_exclusion(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    active = []
    # The cancelled .30 prototype must not silently re-enter the active product.
    for rel in ("src/setup_lab.py", "src/setup_lab_ui.py", "tests/test_v208_setup_lab.py"):
        if (root / rel).exists():
            active.append(rel)
    return {"ok": not active, "scope": SETUP_LAB_SCOPE, "unexpected_active_files": active}


def validate_release_members(names: Iterable[str]) -> dict[str, Any]:
    bad: list[str] = []
    for raw in names:
        text = str(raw).replace("\\", "/").lstrip("./")
        if not text:
            continue
        first = text.split("/", 1)[0].lower()
        if first in MUTABLE_ROOTS:
            bad.append(text)
    return {"ok": not bad, "mutable_entries": sorted(bad)}


def discover_recording_evidence(root: str | Path) -> dict[str, Any]:
    """Discover recording evidence without declaring missing recordings a failure.

    Release packages intentionally exclude recordings. Recording acceptance is a
    separate real-machine gate and remains PENDING until trusted recordings are
    explicitly supplied/run.
    """
    root = Path(root)
    candidates: list[str] = []
    for base in (root / "recordings", root / "validation", root / "validation_bundles"):
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".areplay", ".zip", ".json", ".jsonl"}:
                candidates.append(str(p.relative_to(root)))
    return {
        "status": "available" if candidates else "pending_external_recording_acceptance",
        "count": len(candidates),
        "files": sorted(candidates),
    }


def build_phase1_report(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    source = verify_source_freeze(root)
    matrix = validate_matrix_files(root)
    setup = validate_setup_lab_exclusion(root)
    recordings = discover_recording_evidence(root)
    automated_ok = bool(source["ok"] and matrix["ok"] and setup["ok"])
    return {
        "schema": 1,
        "phase": "V2.0.11",
        "version": V2_011_VERSION,
        "baseline": PROTECTED_BASELINE_TAG,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "automated_structure_ok": automated_ok,
        "source_freeze": source,
        "validation_matrix": [g.to_dict() for g in validation_matrix()],
        "matrix_files": matrix,
        "setup_lab_scope": setup,
        "recording_acceptance": recordings,
        "freeze_ready": False,  # only true after trusted recording acceptance + full regression
        "freeze_blockers": [
            "trusted recording acceptance not yet executed in this environment",
            "full regression result must be attached to the final V2.0.11 checkpoint",
        ],
    }


def write_phase1_report(root: str | Path, output: str | Path) -> Path:
    data = build_phase1_report(root)
    p = Path(output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p
