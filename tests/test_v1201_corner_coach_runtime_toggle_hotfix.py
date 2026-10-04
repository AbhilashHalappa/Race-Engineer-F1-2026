from types import SimpleNamespace as NS

from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, ReferenceTrace


def _zone(zid, start, end, label):
    return CoachingZone(zid, start, end, start, (), brake_start_m=start, apex_m=(start+end)/2, label=label)


def _model():
    zones=(
        _zone('Z1',100.0,200.0,'T1'),
        _zone('Z2',300.0,400.0,'T2'),
        _zone('Z3',500.0,600.0,'T3'),
    )
    samples=tuple({'d':float(d),'t':float(d)/50.0,'speed':180.0} for d in range(0,1001,5))
    return ReferenceTrace('TEST',1000.0,20.0,5.0,samples,(),(),zones,metadata={},quality={'input_telemetry_trusted':False})


class _ValidationSpy:
    def __init__(self):
        self.events=[]
    def state_transition(self,event,**payload):
        self.events.append((event,payload))


def _prepared_engine():
    cc=CornerCoachEngine()
    model=_model()
    cc.reference_model=model
    cc._reference_samples=model.samples
    cc._reference_distances=tuple(float(x['d']) for x in model.samples)
    cc.validation=_ValidationSpy()
    cc._lap=2
    cc._validation_control_state=(True,True,True,True,False)
    return cc,model


def test_post_only_mode_does_not_reserve_future_pre_airtime():
    cc,model=_prepared_engine()
    cc.pre_enabled=False
    session=NS(total_laps=5,ended=False)
    ctx=cc._next_pre_context(model,model.coaching_zones,model.coaching_zones[0],220.0,180.0,session,2)
    assert ctx is None


def test_enabling_pre_mid_lap_marks_already_passed_targets_not_applicable():
    cc,model=_prepared_engine()
    cc._validation_control_state=(True,False,True,True,False)
    cc.pre_enabled=True
    cc._sync_runtime_feature_state(model.coaching_zones,2,350.0,20.0)
    assert cc._pre_not_applicable=={'Z1','Z2'}
    assert cc._validation_control_state==(True,True,True,True,False)
    event,payload=cc.validation.events[-1]
    assert event=='coach_config_change'
    assert payload['pre_enabled'] is True
    assert payload['previous_pre_enabled'] is False


def test_enabling_post_mid_lap_does_not_backfill_completed_zones():
    cc,model=_prepared_engine()
    cc._validation_control_state=(True,True,False,True,False)
    cc.post_enabled=True
    cc._sync_runtime_feature_state(model.coaching_zones,2,450.0,25.0)
    assert cc._post_not_applicable=={'Z1','Z2'}
    event,payload=cc.validation.events[-1]
    assert event=='coach_config_change'
    assert payload['post_enabled'] is True
    assert payload['previous_post_enabled'] is False


def test_disabling_pre_or_post_releases_obsolete_game_time_reservation():
    cc,model=_prepared_engine()
    cc._reserve_speech('PRE','Z2',10.0,5.0)
    cc.pre_enabled=False
    cc._sync_runtime_feature_state(model.coaching_zones,2,250.0,11.0)
    assert cc._speech_reserved_kind is None
    assert cc._speech_wait_s(11.0)==0.0

    cc._validation_control_state=(True,False,True,True,False)
    cc._reserve_speech('POST','Z2',12.0,5.0)
    cc.post_enabled=False
    cc._sync_runtime_feature_state(model.coaching_zones,2,260.0,13.0)
    assert cc._speech_reserved_kind is None
    assert cc._speech_wait_s(13.0)==0.0
