from types import SimpleNamespace

from src.coaching_live import IntegratedLiveCoach
from src.coaching_settings import CoachingSettingsStore
from src.engineer.models import EngineerMessage, Priority
from src.race_state.models import Freshness
from src.tts import SpeechOutput, TTSConfig


def _enum(name='None', raw=0):
    return SimpleNamespace(name=name, raw=raw)


def _state(now, distance, *, lap=1, speed=216.0):
    return SimpleNamespace(
        player=SimpleNamespace(
            lap=SimpleNamespace(current_lap=lap, lap_distance_m=distance, lap_valid=True,
                                pit_status=_enum(), gap_to_car_in_front_s=5.0),
            telemetry=SimpleNamespace(speed_kph=speed, brake=0.0, steering=0.0, throttle=1.0),
            damage=SimpleNamespace(front_left_wing_percent=0, front_right_wing_percent=0,
                                   floor_percent=0, engine_blown=False, engine_seized=False),
            updated={'telemetry': Freshness(now-.1, 1, 0.0), 'lap': Freshness(now-.1, 1, 0.0)},
        ),
        session=SimpleNamespace(session_time_s=now, paused=False, safety_car=_enum(), marshal_zones=()),
        gap_behind_s=5.0,
    )


def _reference():
    return {
        'lap_time_s': 90.0, 'valid': True, 'lap_start_anchored': True,
        'sections': [
            {'id': 1, 'start_m': 600.0, 'min_speed_kph': 120, 'apex_gear': 4, 'end_m': 740.0},
            {'id': 2, 'start_m': 1200.0, 'min_speed_kph': 100, 'apex_gear': 3, 'end_m': 1340.0},
            {'id': 3, 'start_m': 1800.0, 'min_speed_kph': 140, 'apex_gear': 5, 'end_m': 1940.0},
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


def test_external_reference_pre_can_cover_every_reference_turn_even_with_old_low_setting(tmp_path):
    store = CoachingSettingsStore(tmp_path / 'coaching.json')
    store.set(pre_corner=True, post_corner=False, lap_summary=False, positive_calls=False,
              race_coaching=True, pre_corner_max_calls_per_lap=1,
              pre_corner_min_s=4.0, pre_corner_max_s=7.0)
    coach = IntegratedLiveCoach(store)
    rec = ExternalRaceRec()

    one = coach.observe(rec, _state(100.0, 300.0), 100.0)
    two = coach.observe(rec, _state(110.0, 900.0), 110.0)
    three = coach.observe(rec, _state(120.0, 1500.0), 120.0)

    assert [m.key.split(':')[3] for m in one + two + three] == ['1', '2', '3']
    assert coach.status()['pre_spoken_corner_ids'] == [1, 2, 3]


def test_race_post_coach_has_full_corner_coverage_and_no_repeat_lap_cooldown(tmp_path):
    store = CoachingSettingsStore(tmp_path / 'coaching.json')
    coach = IntegratedLiveCoach(store)
    post = coach._new_post(store.settings, race=True)
    assert post.config.max_calls_per_lap >= 20
    assert post.config.same_issue_cooldown_laps == 0
    assert post.config.min_priority_score == 0.0


def test_engineer_mute_classification_keeps_coach_and_ptt_answers():
    auto = EngineerMessage('assist:s_mode', Priority.INFORMATION, 'S Mode.', 1.0)
    collision = EngineerMessage('incident:collision:1', Priority.CRITICAL, 'Collision.', 1.0)
    pre = EngineerMessage('coach:pre:1:2:reference_target', Priority.COACHING, 'Turn 2.', 1.0)
    post = EngineerMessage('coach:corner:2:minimum_speed_low', Priority.COACHING, 'Turn 2.', 1.0)
    voice = EngineerMessage('voice:response', Priority.STRATEGY, 'Tyres are okay.', 1.0)

    assert SpeechOutput._is_automatic_engineer_message(auto)
    assert SpeechOutput._is_automatic_engineer_message(collision)
    assert not SpeechOutput._is_automatic_engineer_message(pre)
    assert not SpeechOutput._is_automatic_engineer_message(post)
    assert not SpeechOutput._is_automatic_engineer_message(voice)

    speech = SpeechOutput(TTSConfig(enabled=False))
    ok, msg = speech.set_automatic_engineer_enabled(False)
    assert ok and msg == 'Disabled'
    assert speech._automatic_engineer_enabled is False


def test_control_center_exposes_engineer_voice_runtime_toggle():
    source = open('src/overlay/window.py', encoding='utf-8').read()
    cc = source.split('class ControlCenterWindow', 1)[1].split('class DriverOverlayWindow', 1)[0]
    assert '"ENGR": on_toggle_engineer_voice' in cc
    assert 'status_order = ("TTS", "PTT", "STT", "LLM", "ENGR"' in cc
