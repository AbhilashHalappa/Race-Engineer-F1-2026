from types import SimpleNamespace as NS

from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, ReferenceTrace


def _zone(zid, start, end, label):
    return CoachingZone(zid, start, end, start, (), brake_start_m=start, apex_m=(start+end)/2, label=label)


def _model():
    zones=(
        _zone('Z1',100.0,200.0,'T1'),
        _zone('Z2',300.0,400.0,'T2'),
    )
    samples=tuple({'d':float(d),'t':float(d)/50.0,'speed':180.0} for d in range(0,1001,5))
    return ReferenceTrace('TEST',1000.0,20.0,5.0,samples,(),(),zones,metadata={},quality={'input_telemetry_trusted':False})


class _ValidationSpy:
    def __init__(self): self.events=[]
    def state_transition(self,event,**payload): self.events.append((event,payload))


def _prepared():
    cc=CornerCoachEngine(); model=_model()
    cc.reference_model=model
    cc._reference_samples=model.samples
    cc._reference_distances=tuple(float(x['d']) for x in model.samples)
    cc.validation=_ValidationSpy()
    cc._lap=2
    cc._validation_control_state=(True,True,True,True,False)
    return cc,model


def test_map_gain_loss_and_voice_are_independent_feature_states():
    cc,_=_prepared()
    assert cc.feature_states()['GAINLOSS'] is True
    assert cc.feature_states()['GAINLOSSVOICE'] is False
    cc.set_feature('GAINLOSS', False)
    cc.set_feature('GAINLOSSVOICE', True)
    states=cc.feature_states()
    assert states['GAINLOSS'] is False
    assert states['GAINLOSSVOICE'] is True


def test_gain_loss_voice_uses_completed_zone_result_and_does_not_require_map_layer():
    cc,model=_prepared()
    cc.gain_loss_enabled=False
    cc.gain_loss_voice_enabled=True
    cc.pre_enabled=False; cc.post_enabled=False
    cc._live_zone_rows=[{'zone_id':'Z1','label':'T1','net_loss_s':0.24,'complete':True}]
    msg=cc._gain_loss_voice_message(model,model.coaching_zones,NS(total_laps=5,ended=False),2,220.0,180.0,10.0,100.0)
    assert msg is not None
    assert msg.key.startswith('corner:gainloss:2:Z1')
    assert 'lost 0.2 seconds' in msg.text
    assert msg.speak is True


def test_gain_loss_voice_reports_gain_with_correct_sign():
    cc,model=_prepared(); cc.gain_loss_voice_enabled=True; cc.pre_enabled=False; cc.post_enabled=False
    cc._live_zone_rows=[{'zone_id':'Z1','label':'T1','net_loss_s':-0.16,'complete':True}]
    msg=cc._gain_loss_voice_message(model,model.coaching_zones,NS(total_laps=5,ended=False),2,220.0,180.0,10.0,100.0)
    assert msg is not None
    assert 'gained 0.2 seconds' in msg.text


def test_gain_loss_voice_deadband_is_silent_but_marked_complete():
    cc,model=_prepared(); cc.gain_loss_voice_enabled=True; cc.pre_enabled=False; cc.post_enabled=False
    cc._live_zone_rows=[{'zone_id':'Z1','label':'T1','net_loss_s':0.03,'complete':True}]
    msg=cc._gain_loss_voice_message(model,model.coaching_zones,NS(total_laps=5,ended=False),2,220.0,180.0,10.0,100.0)
    assert msg is None
    assert 'Z1' in cc._gain_loss_voice_spoken
    assert cc.validation.events[-1][0]=='gain_loss_voice_suppressed'
    assert cc.validation.events[-1][1]['reason']=='deadband'


def test_gain_loss_voice_never_steals_reserved_pre_airtime():
    cc,model=_prepared(); cc.gain_loss_voice_enabled=True; cc.pre_enabled=True; cc.post_enabled=False
    cc._live_zone_rows=[{'zone_id':'Z1','label':'T1','net_loss_s':0.35,'complete':True}]
    # Existing PRE reservation keeps the voice channel busy.
    cc._reserve_speech('PRE','Z2',10.0,5.0)
    msg=cc._gain_loss_voice_message(model,model.coaching_zones,NS(total_laps=5,ended=False),2,220.0,180.0,10.1,100.0)
    assert msg is not None
    assert msg.speak is False
    assert msg.key.startswith('corner:visual:gainloss:')
    event,payload=cc.validation.events[-1]
    assert event=='gain_loss_voice_suppressed'
    assert payload['reason']=='radio_busy_or_pre_protected'


def test_enabling_gain_loss_voice_mid_lap_does_not_backfill_old_zones():
    cc,model=_prepared()
    cc._validation_control_state=(True,True,True,True,False)
    cc.gain_loss_voice_enabled=True
    cc._sync_runtime_feature_state(model.coaching_zones,2,350.0,20.0)
    assert cc._gain_loss_voice_not_applicable=={'Z1'}
    event,payload=cc.validation.events[-1]
    assert event=='coach_config_change'
    assert payload['gain_loss_voice_enabled'] is True
    assert payload['previous_gain_loss_voice_enabled'] is False


def test_control_center_renames_visual_button_and_adds_separate_voice_button():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/'src'/'overlay'/'window.py').read_text(encoding='utf-8')
    assert '"GAINLOSS","MAP G/L"' in text
    assert '"GAINLOSSVOICE","G/L VOICE"' in text


def test_receiver_has_independent_gain_loss_voice_tts_gate():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/'src'/'race_state_receiver.py').read_text(encoding='utf-8')
    assert 'set_message_prefix_enabled("corner:gainloss:"' in text
