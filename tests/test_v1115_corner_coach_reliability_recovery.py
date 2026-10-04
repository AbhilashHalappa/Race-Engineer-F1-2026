from types import SimpleNamespace as NS

from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, ReferenceTrace
from src.engineer.models import estimate_speech_duration_s


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


def test_duration_estimator_matches_measured_alan_voice_conservatively():
    # A representative V1.1.0.14 PRE was estimated at 5.79 s but generated a
    # ~7.5-8.0 s WAV. The calibrated estimator must no longer under-budget it.
    text='Turn 6 coming up: reference slows in about 460 metres, minimum about 192 kph.'
    assert estimate_speech_duration_s(text) >= 7.5


def test_next_pre_context_skips_pre_already_emitted():
    engine=CornerCoachEngine()
    model=_model()
    engine.reference_model=model
    engine._reference_samples=model.samples
    engine._reference_distances=tuple(float(x['d']) for x in model.samples)
    engine._pre_spoken={'Z2'}
    session=NS(total_laps=5,ended=False)
    ctx=engine._next_pre_context(model,model.coaching_zones,model.coaching_zones[0],220.0,180.0,session,2)
    assert ctx is not None
    assert ctx['zone'].zone_id=='Z3'


def test_next_pre_context_reserves_compact_pre_not_verbose_full_sentence():
    engine=CornerCoachEngine()
    model=_model()
    engine.reference_model=model
    engine._reference_samples=model.samples
    engine._reference_distances=tuple(float(x['d']) for x in model.samples)
    session=NS(total_laps=5,ended=False)
    ctx=engine._next_pre_context(model,model.coaching_zones,model.coaching_zones[0],220.0,180.0,session,2)
    assert ctx is not None
    compact=engine._pre_text_compact(ctx['zone'],ctx['distance_ahead_m'],pace_only=True)
    full=engine._pre_text(ctx['zone'],220.0,pace_only=True,distance_to_target_m=ctx['distance_ahead_m'])
    assert ctx['reserved_pre_s'] < estimate_speech_duration_s(full) + engine.SPEECH_FINISH_MARGIN_S
    assert ctx['reserved_pre_s'] >= estimate_speech_duration_s(compact)
