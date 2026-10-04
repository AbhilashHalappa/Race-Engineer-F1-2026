from pathlib import Path
import json
import zipfile

from src.v2_final_validation import (
    MUTABLE_ROOTS, PROTECTED_BASELINE_TAG, SETUP_LAB_SCOPE,
    build_phase1_report, validate_matrix_files, validate_release_members,
    validate_setup_lab_exclusion, verify_source_freeze,
)

ROOT=Path(__file__).resolve().parents[1]


def test_v2011_source_freeze_matches_exact_v2913537_baseline():
    result=verify_source_freeze(ROOT)
    assert result['ok'] is True
    assert result['baseline']==PROTECTED_BASELINE_TAG=='V2.9.1.3.5.37'
    assert result['checked_files'] >= 12


def test_v2011_validation_matrix_points_to_real_existing_tests():
    result=validate_matrix_files(ROOT)
    assert result['ok'] is True
    assert result['missing']==[]
    assert len(result['checked']) >= 12


def test_v2011_setup_lab_stays_cancelled_and_is_not_reintroduced():
    result=validate_setup_lab_exclusion(ROOT)
    assert result=={'ok':True,'scope':SETUP_LAB_SCOPE,'unexpected_active_files':[]}


def test_v2011_release_hygiene_rejects_mutable_runtime_data():
    clean=['src/app.py','tests/test_x.py','README.md']
    assert validate_release_members(clean)['ok'] is True
    for root in sorted(MUTABLE_ROOTS):
        result=validate_release_members([f'{root}/example.bin'])
        assert result['ok'] is False


def test_v2011_phase1_report_never_claims_final_freeze_before_recording_acceptance():
    report=build_phase1_report(ROOT)
    assert report['automated_structure_ok'] is True
    assert report['freeze_ready'] is False
    assert report['recording_acceptance']['status'] in {'available','pending_external_recording_acceptance'}
    assert report['freeze_blockers']
