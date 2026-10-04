import json

import src.overlay.track_maps as track_maps
from src.coaching_analysis import build_performance_pipeline
from src.distance_performance import build_distance_performance_model, physical_turn_boundaries


def _samples(delta_fn):
    out = {}
    for d in range(0, 305, 5):
        extra = float(delta_fn(d))
        out[float(d)] = {
            'd': float(d), 't': d / 50.0 + extra, 'speed': 180.0,
            'throttle': 1.0, 'brake': 0.0, 'steering': 0.0,
            'gear': 5, 'slip': 0.0,
        }
    return out


def _section(section_id, *, start=100.0, min_speed=100.0):
    return {
        'id': section_id, 'start_m': start, 'brake_release_m': 135.0,
        'brake_release_ramp_m': 15.0, 'brake_release_ramp_s': .3,
        'brake_duration_m': 35.0, 'peak_brake': .8, 'trail_brake_m': 20.0,
        'turn_in_m': 125.0, 'min_speed_m': 150.0, 'min_speed_kph': min_speed,
        'throttle_pickup_m': 165.0, 'full_throttle_m': 190.0,
        'pickup_to_full_throttle_m': 25.0, 'pickup_to_full_throttle_s': .5,
        'exit_speed_kph': 150.0, 'coasting_m': 5.0, 'coasting_s': .1,
        'entry_gear': 4, 'apex_gear': 3, 'exit_gear': 4, 'gear_shift_count': 2,
        'peak_abs_steering': .6, 'steering_reversals': 0, 'max_slip': .05,
        'end_m': 200.0, 'analysis_sample_count': 20, 'apex_method': 'min_speed_proxy',
    }


def test_map_capture_waits_for_real_start_line():
    assert not track_maps.verified_start_crossing(
        last_lap=None, last_distance_m=None, lap=1, distance_m=2100.0,
        track_length_m=5000.0, lap_time_s=42.0,
    )
    assert not track_maps.verified_start_crossing(
        last_lap=None, last_distance_m=None, lap=1, distance_m=50.0,
        track_length_m=5000.0, lap_time_s=42.0,
    )
    assert track_maps.verified_start_crossing(
        last_lap=1, last_distance_m=4920.0, lap=2, distance_m=8.0,
        track_length_m=5000.0, lap_time_s=.2,
    )


def test_each_track_is_persisted_in_its_own_file(tmp_path, monkeypatch):
    monkeypatch.setattr(track_maps, '_CACHE_PATH', tmp_path / 'track_maps_cache.json')
    for name in ('Austria', 'Melbourne'):
        key = name.upper()
        track_maps.LEARNED_TRACK_MAPS.pop(key, None)
        track_maps.LEARNED_TRACK_TURNS.pop(key, None)
        pts = [(float(i), float((i * 7) % 41)) for i in range(420)]
        assert track_maps.save_learned_track_map(name, pts)
        track_maps.save_track_turn_markers(name, [
            {'corner_id': 9, 'label': 'anything', 'lap_distance_m': 500.0},
            {'corner_id': 2, 'label': 'anything', 'lap_distance_m': 1500.0},
        ])
    files = sorted((tmp_path / 'tracks').glob('*.json'))
    assert [x.name for x in files] == ['AUSTRIA.json', 'MELBOURNE.json']
    raw = json.loads((tmp_path / 'tracks' / 'AUSTRIA.json').read_text())
    assert raw['version'] == 5
    assert raw['track'] == 'AUSTRIA'
    assert [x['label'] for x in raw['turns']] == ['T1', 'T2']
    assert not (tmp_path / 'track_maps_cache.json').exists()


def test_continuous_distance_model_maps_local_loss_to_physical_turn():
    ref = {
        'lap_time_s': 6.0, 'valid': True, 'lap_start_anchored': True,
        '_samples': _samples(lambda d: 0.0), 'sections': [_section(7)],
    }
    cur_sec = _section(1, start=90.0, min_speed=92.0)
    cur = {
        'lap_time_s': 6.2, 'valid': True, 'lap_start_anchored': True,
        '_samples': _samples(lambda d: 0.0 if d <= 100 else .2 * min(1.0, (d - 100) / 100.0)),
        'sections': [cur_sec],
    }
    model = build_distance_performance_model(cur, ref)
    assert model['available'] is True
    assert len(model['points']) > 50
    assert model['turns'][0]['corner_id'] == 1
    assert model['turns'][0]['reference_section_id'] == 7
    assert abs(model['turns'][0]['net_loss_s'] - .2) < 1e-9
    assert model['turns'][0]['gross_loss_s'] >= .19
    assert any(p['gain_loss'] == 'LOSS' for p in model['points'])

    pipeline = build_performance_pipeline(cur, ref)
    turn = pipeline['turns'][0]
    assert turn['diagnosis'] in {'minimum_speed_low', 'brake_early'}
    assert turn['coaching_eligible'] is True
    analysis = pipeline['corner_analyses'][0]
    assert abs(analysis['time_loss_s'] - turn['net_loss_s']) < 1e-9


def test_physical_turn_numbers_ignore_sparse_detector_ids():
    ref = {'sections': [
        {'id': 90, 'start_m': 2000.0, 'min_speed_m': 2050.0, 'end_m': 2120.0},
        {'id': 3, 'start_m': 400.0, 'min_speed_m': 460.0, 'end_m': 520.0},
        {'id': 44, 'start_m': 1200.0, 'min_speed_m': 1260.0, 'end_m': 1330.0},
    ]}
    turns = physical_turn_boundaries(ref)
    assert [(x['corner_id'], x['reference_section_id']) for x in turns] == [
        (1, 3), (2, 44), (3, 90),
    ]
