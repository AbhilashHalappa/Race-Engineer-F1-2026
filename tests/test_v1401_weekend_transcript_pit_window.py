from pathlib import Path
from types import SimpleNamespace
import json

from src.pit_strategy import assess_pit
from src.race_state.models import RaceState, CarState, Wheels
from src.telemetry.enums import EnumValue
from src.validation_transcript import ValidationTranscriptWriter
from src.corner_coach_validation import CornerCoachValidationRecorder
from src.corner_coach_models import ReferenceTrace, PhysicalCorner, CoachingZone


def ev(name): return EnumValue(0,name)

def clean_race():
    s=RaceState(); s.player=CarState(0); s.session.total_laps=36; s.player.lap.current_lap=12
    s.player.tyres.wear_percent=Wheels(20,20,20,20); s.player.tyres.damage_percent=Wheels(0,0,0,0)
    s.player.tyres.surface_temperature_c=Wheels(90,90,90,90); s.player.tyres.age_laps=12
    s.player.damage.front_left_wing_percent=0; s.player.damage.front_right_wing_percent=0
    s.player.tyres.visual_compound=ev('C3'); s.session.weather=ev('Clear'); s.session.safety_car=ev('None')
    return s

def test_game_pit_window_prevents_contradictory_stay_out():
    s=clean_race(); s.session.pit_stop_window_ideal_lap=12; s.session.pit_stop_window_latest_lap=14
    a=assess_pit(s)
    assert a.recommendation_hint in ('box_soon','box_now')
    assert any('game pit window' in x for x in a.reasons)

def test_game_latest_lap_is_box_now():
    s=clean_race(); s.player.lap.current_lap=14; s.session.pit_stop_window_ideal_lap=12; s.session.pit_stop_window_latest_lap=14
    assert assess_pit(s).recommendation_hint=='box_now'

def test_async_validation_transcripts_rotate_by_session(tmp_path):
    w=ValidationTranscriptWriter(tmp_path)
    state=RaceState(); state.session.uid=11; state.session.track=ev('Austria'); state.session.session_type=ev('Practice 1'); state.session.session_time_s=3.0
    w.observe_session(state)
    msg=SimpleNamespace(text='Test engineer call',key='test',priority=30,session_time_s=3.0)
    w.message(state,msg,'race_engineer')
    state.session.uid=22; state.session.session_type=ev('Race'); state.session.session_time_s=1.0
    w.observe_session(state); w.message(state,msg,'corner_coach'); w.close(wait=True)
    assert len(list(Path(tmp_path).glob('RACE_ENGINEER_*.txt'))) == 1
    assert len(list(Path(tmp_path).glob('CORNER_COACH_TRANSCRIPT_*.txt'))) == 1
    weekend=list(Path(tmp_path).glob('WEEKEND_TRANSCRIPT_*.jsonl'))
    assert len(weekend)==1
    rows=[json.loads(x) for x in weekend[0].read_text().splitlines()]
    starts=[r for r in rows if r['event']=='session_start']
    assert [r['session_uid'] for r in starts]==[11,22]

def _model(fp,time_s):
    c=(PhysicalCorner(1,'T1',100,150,200,'RIGHT',1.0),)
    z=(CoachingZone('Z1',100,200,50,(1,),brake_start_m=80,apex_m=150,reference_min_speed_kph=150,label='T1'),)
    samples=tuple({'d':float(d),'t':float(d)/50,'speed':180.0} for d in range(0,501,10))
    return ReferenceTrace('AUSTRIA',500.0,time_s,10.0,samples,c,(),z,metadata={},quality={'raw_reference_fingerprint':fp})

def test_session_best_reference_update_stays_in_one_validation_file(tmp_path):
    rec=CornerCoachValidationRecorder(tmp_path)
    p1=rec.ensure_run(session_uid=7,track_name='AUSTRIA',model=_model('a',73.8),stable_session=True)
    p2=rec.ensure_run(session_uid=7,track_name='AUSTRIA',model=_model('b',72.6),stable_session=True)
    rec.flush(2.0); rec.close()
    assert p1==p2
    rows=[json.loads(x) for x in Path(p1).read_text().splitlines()]
    assert sum(r['event']=='run_start' for r in rows)==1
    assert sum(r['event']=='reference_update' for r in rows)==1
