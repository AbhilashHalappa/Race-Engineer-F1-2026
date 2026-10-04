from pathlib import Path
from src.corner_coach import CornerCoachEngine


def test_post_enabling_disables_gain_loss_voice():
    cc=CornerCoachEngine()
    cc.post_enabled=False
    cc.gain_loss_voice_enabled=True
    ok,_=cc.set_feature('POST',True)
    assert ok is True
    assert cc.post_enabled is True
    assert cc.gain_loss_voice_enabled is False


def test_gain_loss_voice_enabling_disables_post():
    cc=CornerCoachEngine()
    cc.post_enabled=True
    cc.gain_loss_voice_enabled=False
    ok,_=cc.set_feature('GAINLOSSVOICE',True)
    assert ok is True
    assert cc.gain_loss_voice_enabled is True
    assert cc.post_enabled is False


def test_pre_and_map_gain_loss_remain_independent():
    cc=CornerCoachEngine()
    cc.set_feature('PRE',True)
    cc.set_feature('POST',False)
    cc.set_feature('GAINLOSS',True)
    cc.set_feature('GAINLOSSVOICE',False)
    states=cc.preference_states()
    assert states['CCPRE'] is True
    assert states['CCPOST'] is False
    assert states['GAINLOSS'] is True
    assert states['GAINLOSSVOICE'] is False


def test_corner_coach_controls_are_in_corner_overlay_and_not_built_in_control_center():
    text=(Path(__file__).resolve().parents[1]/'src'/'overlay'/'window.py').read_text(encoding='utf-8')
    overlay=text.split('class CornerCoachOverlayWindow',1)[1]
    control=text.split('class ControlCenterWindow',1)[1].split('class CornerCoachMapCanvas',1)[0]
    assert "'CORNER','CC'" in overlay
    assert "'CCVOICE','VOICE'" in overlay
    assert "'CCPRE','PRE'" in overlay
    assert "'CCPOST','POST'" in overlay
    assert "'GAINLOSS','MAP G/L'" in overlay
    assert "'GAINLOSSVOICE','G/L VOICE'" in overlay
    # Only legacy comments may mention the old CC control block in Control Center.
    assert 'corner_row = QHBoxLayout()' not in control
    assert 'corner_gl_row = QHBoxLayout()' not in control


def test_corner_overlay_receives_live_receiver_callbacks_and_states():
    text=(Path(__file__).resolve().parents[1]/'src'/'overlay'/'window.py').read_text(encoding='utf-8')
    assert 'on_toggle_corner_post=(lambda enabled: receiver.set_corner_coach_feature("POST", enabled))' in text
    assert 'on_toggle_gain_loss_voice=(lambda enabled: receiver.set_corner_coach_feature("GAINLOSSVOICE", enabled))' in text
    assert 'self.corner_coach.set_control_states(receiver.coaching_feature_states())' in text
