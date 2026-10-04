import json
from types import SimpleNamespace

from src.coaching_live import IntegratedLiveCoach
from src.coaching_settings import CoachingSettingsStore
from src.overlay.data import _map_turn_markers
import src.overlay.track_maps as track_maps
from src.race_state.models import Freshness


def _enum(name='None', raw=0):
    return SimpleNamespace(name=name, raw=raw)


def _live_state(now=100.0, *, lap=1, distance=300.0, speed=216.0, wing=0):
    return SimpleNamespace(
        player=SimpleNamespace(
            lap=SimpleNamespace(current_lap=lap, lap_distance_m=distance, lap_valid=True,
                                pit_status=_enum(), gap_to_car_in_front_s=5.0),
            telemetry=SimpleNamespace(speed_kph=speed, brake=0.0, steering=0.0, throttle=1.0),
            damage=SimpleNamespace(front_left_wing_percent=wing, front_right_wing_percent=0,
                                   floor_percent=0, engine_blown=False, engine_seized=False),
            updated={'telemetry': Freshness(now-.1, 1, 0.0), 'lap': Freshness(now-.1, 1, 0.0)},
        ),
        session=SimpleNamespace(session_time_s=10.0, paused=False, safety_car=_enum(), marshal_zones=()),
        gap_behind_s=5.0,
    )


def _reference():
    return {
        'lap_time_s': 70.0, 'valid': True, 'lap_start_anchored': True,
        'sections': [
            {'id': 1, 'start_m': 600.0, 'turn_in_m': 650.0, 'min_speed_m': 690.0,
             'min_speed_kph': 120, 'apex_gear': 4, 'end_m': 740.0},
            {'id': 2, 'start_m': 1200.0, 'turn_in_m': 1250.0, 'min_speed_m': 1290.0,
             'min_speed_kph': 90, 'apex_gear': 3, 'end_m': 1340.0},
        ],
    }


class ExternalRec:
    event_context = {'profile': 'race'}
    completed = []
    current_lap_started_clean = True
    reference_mode = 'external'
    external_reference_name = 'Rival'
    external_reference = _reference()
    def current_reference_lap(self): return self.external_reference


def test_external_reference_seeds_pre_coach_on_lap_one(tmp_path):
    store = CoachingSettingsStore(tmp_path / 'coaching.json')
    store.set(pre_corner=True, post_corner=False, lap_summary=False, positive_calls=False,
              race_coaching=True, pre_corner_min_s=4.0, pre_corner_max_s=7.0)
    coach = IntegratedLiveCoach(store)
    out = coach.observe(ExternalRec(), _live_state(), 100.0)
    assert len(out) == 1
    assert out[0].key.startswith('coach:pre:1:1:reference_target')
    assert 'Turn 1 coming up:' in out[0].text
    assert 'reference brake point 600 metres' in out[0].text
    assert 'gear 4' in out[0].text


def test_stable_moderate_damage_no_longer_blocks_entire_race(tmp_path):
    store = CoachingSettingsStore(tmp_path / 'coaching.json')
    store.set(race_coaching=True)
    coach = IntegratedLiveCoach(store)
    state = _live_state(now=100.0, wing=36)
    coach._update_damage_state(state, 100.0)
    safe, blockers = coach._safe_live(state, 'race', 100.0)
    assert 'significant_damage' in blockers
    state.player.updated['telemetry'] = Freshness(103.1, 1, 0.0)
    state.player.updated['lap'] = Freshness(103.1, 1, 0.0)
    coach._update_damage_state(state, 103.1)
    safe, blockers = coach._safe_live(state, 'race', 103.1)
    assert 'significant_damage' not in blockers
    assert safe


def test_map_cache_v2_persists_geometry_and_turn_numbers(tmp_path, monkeypatch):
    monkeypatch.setattr(track_maps, '_CACHE_PATH', tmp_path / 'track_maps_cache.json')
    track_maps.LEARNED_TRACK_MAPS.pop('TEST TRACK', None)
    track_maps.LEARNED_TRACK_TURNS.pop('TEST TRACK', None)
    points = [(float(i), float(i % 31)) for i in range(400)]
    assert track_maps.save_learned_track_map('Test Track', points)
    track_maps.save_track_turn_markers('Test Track', [
        {'corner_id': 1, 'label': 'T1', 'lap_distance_m': 690.0},
        {'corner_id': 2, 'label': 'T2', 'lap_distance_m': 1290.0},
    ])
    raw = json.loads((tmp_path / 'tracks' / 'TEST_TRACK.json').read_text())
    assert raw['version'] == 5
    assert raw['track'] == 'TEST TRACK'
    assert raw['turns'][0]['corner_id'] == 1
    assert track_maps.get_track_turn_markers('Test Track')[1]['label'] == 'T2'


def test_map_turns_fall_back_to_persisted_cache_without_reference(monkeypatch):
    monkeypatch.setitem(track_maps.LEARNED_TRACK_TURNS, 'MELBOURNE', (
        {'corner_id': 1, 'label': 'T1', 'lap_distance_m': 390.0},
        {'corner_id': 3, 'label': 'T3', 'lap_distance_m': 1400.0},
    ))
    turns = _map_turn_markers(None, 'Melbourne')
    assert [(t.corner_id, t.label, t.lap_distance_m) for t in turns] == [
        (1, 'T1', 390.0), (3, 'T3', 1400.0)
    ]
