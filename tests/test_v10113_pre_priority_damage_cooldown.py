from types import SimpleNamespace

from src.coaching_live import IntegratedLiveCoach
from src.coaching_settings import CoachingSettingsStore
from src.engineer.models import EngineerMessage, Priority
from src.race_state.models import Freshness
from src.tts import SpeechOutput


def _enum(name='None', raw=0):
    return SimpleNamespace(name=name, raw=raw)


def _state(now=100.0, *, lap=1, distance=300.0, speed=216.0, wing=0):
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
        ],
    }


class ExternalRaceRec:
    event_context = {'profile': 'race'}
    completed = []
    current_lap_started_clean = True
    reference_mode = 'external'
    external_reference_name = 'Rival'
    external_reference = _reference()
    def current_reference_lap(self): return self.external_reference


def test_pre_radio_rank_beats_routine_radio_but_not_critical():
    pre = EngineerMessage('coach:pre:2:3:minimum_speed_low', Priority.COACHING, 'pre', 1.0)
    lap = EngineerMessage('coach:lap_summary:1', Priority.COACHING, 'lap', 1.0)
    post = EngineerMessage('coach:corner:3:minimum_speed_low', Priority.COACHING, 'post', 1.0)
    strategy = EngineerMessage('strategy:test', Priority.STRATEGY, 'strategy', 1.0)
    assist = EngineerMessage('assist:ers', Priority.INFORMATION, 'assist', 1.0)
    critical = EngineerMessage('damage:wing', Priority.CRITICAL, 'critical', 1.0)
    track = EngineerMessage('track_limits', Priority.CRITICAL, 'track', 1.0)
    voice = EngineerMessage('voice:response', Priority.STRATEGY, 'voice', 1.0)

    assert SpeechOutput._radio_rank(voice) < SpeechOutput._radio_rank(pre)
    assert SpeechOutput._radio_rank(track) < SpeechOutput._radio_rank(pre)
    assert SpeechOutput._radio_rank(critical) < SpeechOutput._radio_rank(pre)
    assert SpeechOutput._radio_rank(pre) < SpeechOutput._radio_rank(assist)
    assert SpeechOutput._radio_rank(pre) < SpeechOutput._radio_rank(strategy)
    assert SpeechOutput._radio_rank(pre) < SpeechOutput._radio_rank(lap)
    assert SpeechOutput._radio_rank(pre) < SpeechOutput._radio_rank(post)


def test_pre_is_selected_before_pending_lap_summary(tmp_path):
    store = CoachingSettingsStore(tmp_path / 'coaching.json')
    store.set(pre_corner=True, post_corner=False, lap_summary=True, positive_calls=False,
              race_coaching=True, pre_corner_min_s=4.0, pre_corner_max_s=7.0)
    coach = IntegratedLiveCoach(store)
    coach._lap_summary_pending = EngineerMessage(
        'coach:lap_summary:0', Priority.COACHING, 'Old lap summary.', 99.0, 9.0
    )
    out = coach.observe(ExternalRaceRec(), _state(), 100.0)
    assert len(out) == 1
    assert out[0].key.startswith('coach:pre:1:1:reference_target')
    assert coach._lap_summary_pending is not None


def test_damage_cooldown_is_three_seconds(tmp_path):
    store = CoachingSettingsStore(tmp_path / 'coaching.json')
    store.set(race_coaching=True)
    coach = IntegratedLiveCoach(store)
    state = _state(now=100.0, wing=36)
    coach._update_damage_state(state, 100.0)
    _, blockers = coach._safe_live(state, 'race', 100.0)
    assert 'significant_damage' in blockers

    state.player.updated['telemetry'] = Freshness(102.8, 1, 0.0)
    state.player.updated['lap'] = Freshness(102.8, 1, 0.0)
    coach._update_damage_state(state, 102.9)
    _, blockers = coach._safe_live(state, 'race', 102.9)
    assert 'significant_damage' in blockers

    state.player.updated['telemetry'] = Freshness(103.1, 1, 0.0)
    state.player.updated['lap'] = Freshness(103.1, 1, 0.0)
    coach._update_damage_state(state, 103.1)
    safe, blockers = coach._safe_live(state, 'race', 103.1)
    assert 'significant_damage' not in blockers
    assert safe
