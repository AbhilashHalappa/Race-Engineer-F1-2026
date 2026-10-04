from types import SimpleNamespace

from src.coaching_live import IntegratedLiveCoach, _primary_for_corner
from src.coaching_settings import CoachingSettingsStore
from src.overlay.data import _map_turn_markers
from src.post_corner_coach import PostCornerCoach
from src.race_state.models import Freshness


def _enum(name='None', raw=0):
    return SimpleNamespace(name=name, raw=raw)


def test_measured_advice_uses_reference_turn_id_not_unstable_current_id():
    rows = [{
        'corner_id': 9, 'reference_corner_id': 4, 'coaching_eligible': True,
        'diagnosis': 'brake_early', 'estimated_time_cost_s': .12,
    }]
    out = _primary_for_corner(rows)
    assert list(out) == [4]
    assert out[4]['corner_id'] == 4


def test_map_turns_are_relabelled_in_physical_lap_order():
    ref = {'sections': [
        {'id': 8, 'min_speed_m': 2200.0},
        {'id': 2, 'min_speed_m': 500.0},
        {'id': 11, 'min_speed_m': 1500.0},
    ]}
    turns = _map_turn_markers(ref, 'Melbourne')
    assert [(x.corner_id, x.label, x.lap_distance_m) for x in turns] == [
        (1, 'T1', 500.0), (2, 'T2', 1500.0), (3, 'T3', 2200.0)
    ]


def test_race_pre_blocks_close_combat_but_not_invalid_lap(tmp_path):
    store = CoachingSettingsStore(tmp_path / 'coaching.json')
    coach = IntegratedLiveCoach(store)
    now = 100.0
    state = SimpleNamespace(
        player=SimpleNamespace(
            lap=SimpleNamespace(current_lap=1, lap_distance_m=300.0, lap_valid=False,
                                pit_status=_enum(), gap_to_car_in_front_s=.4),
            telemetry=SimpleNamespace(speed_kph=200.0, brake=0.0, steering=0.0, throttle=1.0),
            damage=SimpleNamespace(front_left_wing_percent=0, front_right_wing_percent=0,
                                   floor_percent=0, engine_blown=False, engine_seized=False),
            updated={'telemetry': Freshness(now-.1, 1, 0.0), 'lap': Freshness(now-.1, 1, 0.0)},
        ),
        session=SimpleNamespace(paused=False, safety_car=_enum(), marshal_zones=()),
        gap_behind_s=.3,
    )
    safe, blockers = coach._safe_pre(state, 'race', now)
    assert not safe
    assert 'close_traffic' in blockers
    assert 'invalid_lap' not in blockers


def _samples(times_speeds):
    return {str(d): {'t': t, 'speed': speed} for d, t, speed in times_speeds}


def test_fallback_coaches_a_slower_reference_turn_even_without_section_match():
    ref = {
        '_samples': _samples([(100, 2.0, 190), (150, 3.0, 140), (200, 4.0, 180)]),
    }
    cur = {
        '_samples': _samples([(100, 2.0, 185), (150, 3.4, 130), (200, 4.5, 175)]),
    }
    sec = {'id': 1, 'start_m': 100.0, 'end_m': 200.0, 'min_speed_kph': 140.0}
    a = PostCornerCoach._fallback_slow_turn(cur, ref, sec, 1)
    assert a is not None
    assert a['corner_id'] == 1
    assert a['coaching_eligible'] is True
    assert a['estimated_time_cost_s'] > .45
    assert a['diagnosis'] == 'minimum_speed_low'
