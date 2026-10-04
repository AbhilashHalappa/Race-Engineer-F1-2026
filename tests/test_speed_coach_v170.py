from types import SimpleNamespace
from src.corner_coach import CornerCoachEngine
from src.radio_controls import parse_runtime_radio_command


def test_speed_coach_hierarchy_independent_children():
    c=CornerCoachEngine()
    st=c.speed_coach_feature_states()
    assert st['SPEED'] is True and st['CORNER'] is True and st['STRAIGHT'] is False
    assert c.set_feature('STRAIGHT',True)[0]
    assert c.speed_coach_feature_states()['STRAIGHT'] is True
    assert c.set_feature('CORNER',False)[0]
    st=c.speed_coach_feature_states()
    assert st['SPEED'] is True and st['CORNER'] is False and st['STRAIGHT'] is True
    assert st['CCPRE'] is False
    assert c.set_feature('SPEED',False)[0]
    st=c.speed_coach_feature_states()
    assert not st['CORNER'] and not st['STRAIGHT'] and not st['GAINLOSS']
    # preferences survive parent mute
    assert c.corner_enabled is False and c.straight_enabled is True
    c.set_feature('SPEED',True)
    assert c.speed_coach_feature_states()['STRAIGHT'] is True


def test_speed_coach_radio_aliases():
    assert parse_runtime_radio_command('enable speed coach').target == 'SPEED'
    assert parse_runtime_radio_command('disable corner coach').target == 'CORNER'
    assert parse_runtime_radio_command('enable straight line coach').target == 'STRAIGHT'
    assert parse_runtime_radio_command('disable straight voice').target == 'SLVOICE'


def test_straight_diagnosis_uses_measured_loss_and_speed():
    c=CornerCoachEngine(); c.straight_enabled=True
    c._live_segments=[{'segment_kind':'straight','number':1,'label':'S1','start_m':0.0,'end_m':100.0,'net_loss_s':0.20,'complete':True}]
    c._reference_samples=tuple({'d':d,'speed':300.0,'throttle':1.0,'s_mode_straight':True,'ers_j':4_000_000-d*1000} for d in (0.0,25.0,50.0,75.0,100.0))
    recorder=SimpleNamespace(samples={d:SimpleNamespace(d=d,speed=290.0,throttle=1.0,s_mode_straight=True,ers_j=4_000_000-d*1000) for d in (0.0,25.0,50.0,75.0,100.0)})
    model=SimpleNamespace(quality={'input_telemetry_trusted':True})
    telem=SimpleNamespace(brake=0.0,steering=0.0)
    m=c._straight_message(recorder,model,2,20.0,100.0,telem=telem,zones=(),current_d=120.0,speed=290.0,session=None)
    assert m is not None
    assert m.key.startswith('straight:post:')
    assert 'lost 0.20' in m.text
    assert 'speed' in m.text.lower()
    assert c._straight_last_diagnosis['avg_speed_delta_kph'] == -10.0


def test_straight_voice_waits_during_braking():
    c=CornerCoachEngine(); c.straight_enabled=True
    c._live_segments=[{'segment_kind':'straight','number':1,'label':'S1','start_m':0.0,'end_m':100.0,'net_loss_s':0.12,'complete':True}]
    c._reference_samples=tuple({'d':d,'speed':300.0} for d in (0.0,50.0,100.0))
    recorder=SimpleNamespace(samples={d:SimpleNamespace(d=d,speed=295.0) for d in (0.0,50.0,100.0)})
    model=SimpleNamespace(quality={'input_telemetry_trusted':False})
    assert c._straight_message(recorder,model,2,20.0,100.0,telem=SimpleNamespace(brake=.3,steering=0),zones=(),current_d=120,speed=280,session=None) is None
    assert len(c._straight_pending)==1
    m=c._straight_message(recorder,model,2,22.0,102.0,telem=SimpleNamespace(brake=0,steering=0),zones=(),current_d=160,speed=280,session=None)
    assert m is not None


def test_enabling_straight_mid_lap_does_not_backfill_completed_straights():
    c=CornerCoachEngine()
    c._live_segments=[
        {'segment_kind':'straight','number':1,'complete':True},
        {'segment_kind':'straight','number':2,'complete':False},
    ]
    assert c.set_feature('STRAIGHT',True)[0]
    assert 1 in c._straight_spoken
    assert 2 not in c._straight_spoken
    assert c._straight_pending == []


def test_enabling_straight_voice_discards_stale_pending_call():
    c=CornerCoachEngine(); c.straight_enabled=True; c.straight_voice_enabled=False
    c._live_segments=[{'segment_kind':'straight','number':1,'complete':True}]
    c._straight_pending=[{'straight':1,'text':'stale'}]
    assert c.set_feature('STRAIGHTVOICE',True)[0]
    assert c._straight_pending == []
    assert 1 in c._straight_spoken


def test_straight_speech_protects_upcoming_corner_pre(monkeypatch):
    from src.corner_coach_models import CoachingZone
    c=CornerCoachEngine(); c.straight_enabled=True
    c._live_segments=[{'segment_kind':'straight','number':1,'label':'S1','start_m':0.0,'end_m':100.0,'net_loss_s':0.20,'complete':True}]
    c._reference_samples=tuple({'d':d,'speed':300.0} for d in (0.0,50.0,100.0,200.0,300.0))
    recorder=SimpleNamespace(samples={d:SimpleNamespace(d=d,speed=290.0) for d in (0.0,50.0,100.0)})
    model=SimpleNamespace(quality={'input_telemetry_trusted':False})
    zone=CoachingZone('Z2',300.0,400.0,250.0,(2,),brake_start_m=280.0,apex_m=350.0,label='T2')
    # Make PRE only ~1.5 s away: there cannot be enough airtime for the straight call.
    monkeypatch.setattr(c,'_target_eta_s',lambda *args,**kwargs:1.5)
    msg=c._straight_message(recorder,model,2,20.0,100.0,telem=SimpleNamespace(brake=0,steering=0),zones=(zone,),current_d=200.0,speed=250.0,session=None)
    assert msg is None
    assert len(c._straight_pending)==1


def test_speed_coach_transcript_routes_straight_source(tmp_path):
    import json
    from pathlib import Path
    from src.validation_transcript import ValidationTranscriptWriter
    from src.engineer.models import EngineerMessage, Priority
    session_type=SimpleNamespace(name='Race')
    track=SimpleNamespace(name='Austria')
    session=SimpleNamespace(uid=77,track=track,session_type=session_type,session_time_s=12.5)
    state=SimpleNamespace(session=session)
    w=ValidationTranscriptWriter(tmp_path)
    m=EngineerMessage('straight:post:2:S1',Priority.COACHING,'Straight 1, lost 0.12 seconds.',0.0,12.5)
    w.message(state,m,'straight_line_coach'); w.close(wait=True)
    speed=list(Path(tmp_path).glob('SPEED_COACH_TRANSCRIPT_*.txt'))
    assert len(speed)==1
    assert 'Straight 1' in speed[0].read_text(encoding='utf-8')
    combined=list(Path(tmp_path).glob('VALIDATION_TRANSCRIPT_*.jsonl'))[0]
    rows=[json.loads(x) for x in combined.read_text(encoding='utf-8').splitlines()]
    assert any(r.get('source')=='straight_line_coach' and r.get('key')=='straight:post:2:S1' for r in rows)
