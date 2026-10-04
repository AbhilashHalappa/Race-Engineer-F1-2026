from types import SimpleNamespace

from src.ptt import PTTConfig, PTTController
from src.corner_coach import CornerCoachEngine


class _FailingRecorder:
    def __init__(self):
        self._stream=None
        self.abort_calls=0
        self.stop_calls=0
    def start(self):
        raise RuntimeError('Error querying device -1')
    def abort(self):
        self.abort_calls += 1
    def stop(self):
        self.stop_calls += 1
        return None


def test_ptt_microphone_failure_stays_latched_until_release_and_releases_radio():
    events=[]
    rec=_FailingRecorder()
    p=PTTController(PTTConfig(enabled=True), recorder=rec,
                    on_press=lambda: events.append('press'),
                    on_release=lambda path: events.append(('release', path)))
    p._handle_button(True)
    assert p._pressed is True
    assert 'Error querying device -1' in (p.last_error or '')
    assert rec.abort_calls == 1
    # Same physical held state must not retry capture continuously.
    p._handle_button(True)
    assert rec.abort_calls == 1
    p._handle_button(False)
    assert p._pressed is False
    assert events == ['press', ('release', None)]


def _state_with_damage(wing=36, floor=0):
    damage=SimpleNamespace(front_left_wing_percent=wing, front_right_wing_percent=0,
                           floor_percent=floor, engine_blown=False, engine_seized=False)
    return SimpleNamespace(player=SimpleNamespace(damage=damage))


def test_corner_coach_damage_threshold_and_override_policy():
    c=CornerCoachEngine()
    state=_state_with_damage(36)
    assert c._significant_damage_present(state) is True
    assert c.damage_coaching_enabled is False
    c.set_feature('DMGCOACH', True)
    assert c.damage_coaching_enabled is True
    assert c._significant_damage_present(state) is True  # fact remains recorded


def test_minor_damage_does_not_trigger_live_damage_gate():
    c=CornerCoachEngine()
    assert c._significant_damage_present(_state_with_damage(19)) is False
