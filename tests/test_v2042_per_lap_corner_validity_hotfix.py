from types import SimpleNamespace

from src.performance_review import build_performance_review
from src.session_coach_report import _reconciled_live_lap_intelligence


def _corner(cid=1, loss=0.12):
    return {
        'corner_id': cid,
        'score': 78.0,
        'score_status': 'available',
        'confidence': 0.95,
        'estimated_loss_s': loss,
        'dominant_issue': 'brake_early',
        'primary_text': 'Brake later',
        'dominant_phase': 'ENTRY',
        'dimension_scores': {'braking_point': 78.0},
        'brake_point_delta_m': -8.0,
        'phase_losses': {'entry': loss, 'mid': 0.0, 'exit': 0.0},
    }


def test_completed_lap_validity_overrides_transition_packet_live_flag():
    # Simulates the real failure: CORNER COACH had already finalized Lap 1 with
    # a stale/new-lap validity value, while MeasuredPerformance stored the game-
    # authoritative completed Lap 1 as valid.
    recorder = SimpleNamespace(live_lap_intelligence=[{
        'lap_number': 1,
        'lap_valid': False,
        'lap_time_s': 99.0,
        'quality': {'eligible': False, 'reasons': ['invalid_lap']},
        'corners': {1: _corner(1)},
    }])
    completed = [{
        'lap': 1,
        'lap_time_s': 83.708,
        'valid': True,
        'damage_compromised': False,
        'traffic_compromised': False,
        'replay_seek_detected': False,
        'session_restart_detected': False,
        'lap_start_anchored': True,
        'sample_count': 500,
    }]
    rows = _reconciled_live_lap_intelligence(recorder, completed)
    assert rows[0]['lap_number'] == 1
    assert rows[0]['lap_valid'] is True
    assert rows[0]['lap_time_s'] == 83.708
    assert rows[0]['quality']['eligible'] is True


def test_every_authoritative_timed_lap_remains_selectable_even_without_score_row():
    report = {
        'reference_lap': {'lap': 5, 'lap_time_s': 78.668},
        'lap_comparisons': [],
        'live_lap_intelligence': [],
        'lap_facts': [
            {'lap': 1, 'lap_time_s': 83.708, 'valid': True, 'quality': {'eligible': True, 'reasons': []}},
            {'lap': 5, 'lap_time_s': 78.668, 'valid': True, 'quality': {'eligible': True, 'reasons': []}},
        ],
        'coaching_data_quality': {'eligible_laps': [1, 5], 'excluded_laps': [], 'timed_valid_lap_count': 2},
    }
    review = build_performance_review(report)
    assert [x['lap'] for x in review['laps']] == [1, 5]
    assert [x['lap'] for x in review['lap_reviews']] == [1, 5]


def test_each_lap_review_keeps_its_own_live_corner_rows():
    report = {
        'reference_lap': {'lap': 2, 'lap_time_s': 80.0},
        'lap_comparisons': [],
        'live_lap_intelligence': [
            {'lap_number': 1, 'lap_time_s': 81.0, 'lap_valid': True, 'quality': {'eligible': True, 'reasons': []},
             'lap_score': 78.0, 'confidence': .95, 'coverage': 1.0, 'scored_corner_count': 1, 'eligible_corner_count': 1,
             'corners': {1: _corner(1, .12)}},
            {'lap_number': 2, 'lap_time_s': 80.0, 'lap_valid': True, 'quality': {'eligible': True, 'reasons': []},
             'lap_score': 84.0, 'confidence': .96, 'coverage': 1.0, 'scored_corner_count': 1, 'eligible_corner_count': 1,
             'corners': {4: _corner(4, .05)}},
        ],
        'lap_facts': [
            {'lap': 1, 'lap_time_s': 81.0, 'valid': True, 'quality': {'eligible': True, 'reasons': []}},
            {'lap': 2, 'lap_time_s': 80.0, 'valid': True, 'quality': {'eligible': True, 'reasons': []}},
        ],
        'coaching_data_quality': {'eligible_laps': [1, 2], 'excluded_laps': [], 'timed_valid_lap_count': 2},
    }
    review = build_performance_review(report)
    by_lap = {x['lap']: x for x in review['lap_reviews']}
    assert [c['corner_id'] for c in by_lap[1]['corners']] == [1]
    assert [c['corner_id'] for c in by_lap[2]['corners']] == [4]
    assert by_lap[1]['corners'][0]['detail']['phase_time_cost_s']['braking'] == .12


def test_per_lap_corner_fallback_uses_exact_legacy_comparison_not_session_aggregate():
    import dataclasses
    from src.coaching_analysis import CornerAnalysis
    analysis = {f.name: None for f in dataclasses.fields(CornerAnalysis)}
    analysis.update({
        'corner_id': 7, 'reference_corner_id': 7, 'apex_method': 'path_curvature',
        'current_quality': .95, 'reference_quality': .96, 'match_quality': .92,
        'confidence': .9, 'confidence_reasons': (),
        'time_loss_s': 0.21,
        'diagnosis': 'throttle_late',
        'diagnosis_label': 'Throttle pickup too late',
        'dominant_phase': 'EXIT',
        'diagnosis_confidence': 0.9,
        'exit_time_loss_s': 0.21,
    })
    report = {
        'reference_lap': {'lap': 1, 'lap_time_s': 80.0},
        'lap_comparisons': [{'lap': 2, 'lap_time_s': 81.0, 'corner_analyses': [analysis]}],
        'live_lap_intelligence': [],
        'lap_facts': [
            {'lap': 1, 'lap_time_s': 80.0, 'valid': True, 'quality': {'eligible': True, 'reasons': []}},
            {'lap': 2, 'lap_time_s': 81.0, 'valid': True, 'quality': {'eligible': True, 'reasons': []}},
        ],
        'coaching_data_quality': {'eligible_laps': [1, 2], 'excluded_laps': [], 'timed_valid_lap_count': 2},
    }
    review = build_performance_review(report)
    lap2 = next(x for x in review['lap_reviews'] if x['lap'] == 2)
    assert [c['corner_id'] for c in lap2['corners']] == [7]
    assert lap2['corners'][0]['mean_loss_s'] == 0.21
