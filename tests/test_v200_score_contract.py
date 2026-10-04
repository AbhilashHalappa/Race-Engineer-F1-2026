from __future__ import annotations

from dataclasses import replace

from src.coaching_analysis import CornerAnalysis
from src.performance_scoring import (
    CompatibilityState, EvidenceTier, SCORE_MODEL_VERSION, ScoreStatus,
    TechniqueMetricEvidence, build_corner_technique_score,
    normalize_metric_score, score_metric, build_lap_technique_score, compatibility_from_laps,
)
from src.product_settings import ProductSettings


def evidence(metric='braking_point', delta=0.0, confidence=1.0, compatibility=CompatibilityState.COMPATIBLE):
    return TechniqueMetricEvidence(
        evidence_id=f'test:{metric}', metric=metric, tier=EvidenceTier.CORNER,
        current_value=(100.0 + delta) if delta is not None else None, reference_value=100.0, delta=delta,
        confidence=confidence, sample_count=1, compatibility=compatibility, unit='m',
    )


def test_v200_control_center_runtime_remains_enabled_but_driving_overlays_do_not_auto_open():
    # The application UI still launches; startup visibility is enforced by OverlaySuite.show().
    assert ProductSettings().overlay_enabled is True
    source=__import__('pathlib').Path('src/overlay/window.py').read_text(encoding='utf-8')
    block=source[source.index('    def show(self):', source.index('class OverlaySuite')):source.index('    def show_overlay_by_key', source.index('class OverlaySuite'))]
    assert 'for window in self.windows:' in block
    assert 'window.hide()' in block
    assert 'self.control_center.show()' in block
    assert 'window.show()' not in block


def test_v200_normalization_is_deterministic_and_monotonic():
    values=[normalize_metric_score(x,deadband=3,full_scale=35,mode='absolute') for x in (0,3,5,10,20,35,50)]
    assert values == sorted(values, reverse=True)
    assert values[0] == 100.0
    assert values[-1] == 0.0
    assert normalize_metric_score(10,deadband=3,full_scale=35,mode='absolute') == values[3]


def test_v200_directional_speed_score_does_not_penalize_beating_reference():
    better=score_metric(evidence('exit_speed', +4.0))
    worse=score_metric(evidence('exit_speed', -4.0))
    assert better.value == 100.0
    assert worse.value < better.value


def test_v200_missing_or_incompatible_evidence_is_na_never_50():
    missing=score_metric(evidence(delta=None))
    wet=score_metric(evidence(delta=10.0, compatibility=CompatibilityState.WET_DRY_MISMATCH))
    assert missing.status is ScoreStatus.NOT_AVAILABLE and missing.value is None
    assert wet.status is ScoreStatus.NOT_AVAILABLE and wet.value is None


def test_v200_score_serialization_carries_model_confidence_sample_compatibility_and_evidence():
    score=score_metric(evidence(delta=8.0, confidence=.8), reference_identity='rival-lap-7', reference_version='abc123')
    row=score.to_dict()
    assert row['score_model_version'] == SCORE_MODEL_VERSION
    assert row['confidence'] == .8
    assert row['sample_count'] == 1
    assert row['compatibility'] == 'compatible'
    assert row['reference_identity'] == 'rival-lap-7'
    assert row['reference_version'] == 'abc123'
    assert row['raw_evidence_ids'] == ['test:braking_point']
    assert row['evidence'][0]['delta'] == 8.0


def _analysis(**changes):
    defaults=dict(
        corner_id=4, reference_corner_id=4, anchor_m=500, reference_anchor_m=500, anchor_delta_m=0,
        brake_onset_m=450, reference_brake_onset_m=455, brake_onset_delta_m=-5,
        brake_release_m=485, reference_brake_release_m=485, brake_release_delta_m=0,
        brake_release_ramp_m=10, reference_brake_release_ramp_m=10, brake_release_ramp_delta_m=0,
        brake_release_ramp_s=.2, reference_brake_release_ramp_s=.2, brake_release_ramp_delta_s=0,
        brake_duration_m=35, reference_brake_duration_m=30, brake_duration_delta_m=5,
        peak_brake=.8, reference_peak_brake=.8, peak_brake_delta=0,
        trail_brake_m=12, reference_trail_brake_m=12, trail_brake_delta_m=0,
        turn_in_m=490, reference_turn_in_m=490, turn_in_delta_m=0,
        apex_m=510, reference_apex_m=510, apex_delta_m=0, apex_method='path_curvature',
        min_speed_kph=110, reference_min_speed_kph=114, min_speed_delta_kph=-4,
        throttle_pickup_m=520, reference_throttle_pickup_m=518, throttle_pickup_delta_m=2,
        full_throttle_m=550, reference_full_throttle_m=545, full_throttle_delta_m=5,
        pickup_to_full_throttle_m=30, reference_pickup_to_full_throttle_m=27, pickup_to_full_throttle_delta_m=3,
        pickup_to_full_throttle_s=.55, reference_pickup_to_full_throttle_s=.45, pickup_to_full_throttle_delta_s=.10,
        exit_speed_kph=190, reference_exit_speed_kph=194, exit_speed_delta_kph=-4,
        coasting_m=0, reference_coasting_m=0, coasting_delta_m=0, coasting_s=0, reference_coasting_s=0, coasting_delta_s=0,
        entry_gear=5, reference_entry_gear=5, apex_gear=4, reference_apex_gear=4, exit_gear=5, reference_exit_gear=5,
        gear_shift_count=2, reference_gear_shift_count=2, peak_abs_steering=.5, reference_peak_abs_steering=.5,
        steering_reversals=0, reference_steering_reversals=0, max_slip=.05, reference_max_slip=.05, max_slip_delta=0,
        entry_time_loss_s=.04, mid_time_loss_s=.03, exit_time_loss_s=.03, time_loss_s=.10,
        current_quality=1.0, reference_quality=1.0, match_quality=1.0, confidence=.9, confidence_reasons=(),
        apex_speed_kph=111, reference_apex_speed_kph=115, apex_speed_delta_kph=-4,
        throttle_pickup_after_apex_s=.30, reference_throttle_pickup_after_apex_s=.20, throttle_pickup_after_apex_delta_s=.10,
        steering_smoothness=.80, reference_steering_smoothness=.90, steering_smoothness_delta=-.10,
    )
    defaults.update(changes)
    return CornerAnalysis(**defaults)


def test_v200_corner_score_reuses_corner_analysis_and_preserves_raw_measurements():
    result=build_corner_technique_score(_analysis(), reference_identity='rival')
    assert result.status is ScoreStatus.AVAILABLE
    assert result.score is not None
    assert result.dimensions['braking_point'].evidence[0].delta == -5.0
    assert result.dimensions['min_apex_speed'].evidence[0].delta == -4.0
    assert result.dimensions['throttle_pickup'].evidence[0].unit == 's'
    assert result.dimensions['racing_line_consistency'].status is ScoreStatus.NOT_AVAILABLE


def test_v200_corner_incompatible_condition_blocks_all_published_scoring():
    result=build_corner_technique_score(_analysis(), compatibility=CompatibilityState.WET_DRY_MISMATCH)
    assert result.status is ScoreStatus.NOT_AVAILABLE
    assert result.score is None
    assert all(x.status is ScoreStatus.NOT_AVAILABLE for x in result.dimensions.values())


def test_v200_lap_score_requires_tier2_coverage_not_one_corner():
    one=build_corner_technique_score(_analysis())
    result=build_lap_technique_score([one], lap_number=3, eligible_corner_count=10)
    assert result.status is ScoreStatus.NOT_AVAILABLE
    assert result.score is None


def test_v200_lap_score_publishes_only_with_sufficient_corner_coverage():
    rows=[build_corner_technique_score(_analysis(corner_id=i, reference_corner_id=i)) for i in range(1,7)]
    result=build_lap_technique_score(rows, lap_number=4, eligible_corner_count=10)
    assert result.status is ScoreStatus.AVAILABLE
    assert result.coverage == .6
    assert result.sample_count == 6


def test_v200_compatibility_reuses_existing_quality_gates():
    base={'valid':True,'lap_start_anchored':True,'sample_count':100,'lap_time_s':90.0,'track_name':'MELBOURNE','track_condition':'dry'}
    wet=dict(base, track_condition='wet')
    assert compatibility_from_laps(base, wet) is CompatibilityState.WET_DRY_MISMATCH
    invalid=dict(base, valid=False)
    assert compatibility_from_laps(invalid, base) is CompatibilityState.INVALID_LAP
