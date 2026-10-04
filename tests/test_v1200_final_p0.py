from __future__ import annotations

import json
from pathlib import Path

from src.data_quality import lap_quality, reference_compatible
from src.potential_lap import potential_summary, sector_potential, corner_potential
from src.corner_coach_benchmark import analyse_trace
from src.overlay.data import _pace_only_turn_metrics


def _lap(n, lap_time, sectors, *, weather='dry', tyre='SOFT', fuel=20.0, speed=200.0):
    length=1000.0
    samples={}
    for i in range(201):
        d=i*5.0
        t=lap_time*d/length
        samples[d]={'d':d,'t':t,'speed':speed,'fuel':fuel-d/length}
    return {
        'lap':n,'valid':True,'lap_start_anchored':True,'sample_count':len(samples),
        'lap_time_s':lap_time,'track_name':'TEST','track_length_m':length,
        'sector1_time_s':sectors[0],'sector2_time_s':sectors[1],'sector3_time_s':sectors[2],
        'track_condition':weather,'tyre_compound':tyre,'fuel_start_kg':fuel,
        'sections':[{'id':1,'start_m':100.0,'min_speed_m':250.0,'end_m':400.0},
                    {'id':2,'start_m':500.0,'min_speed_m':700.0,'end_m':900.0}],
        '_samples':samples,
    }


def test_potential_filters_incompatible_conditions_and_reports_both_models():
    a=_lap(1,90.0,(30.0,30.0,30.0),weather='dry',fuel=20.0)
    b=_lap(2,88.0,(29.0,30.0,29.0),weather='dry',fuel=22.0)
    wet=_lap(3,70.0,(20.0,25.0,25.0),weather='wet',fuel=20.0)
    out=potential_summary([a,b,wet],anchor=b,reference={'lap_time_s':87.0},include_corner_segments=True)
    assert out['compatible_lap_count']==2
    assert out['sector_theoretical_best_s']==88.0
    assert out['potential_lap_s']==88.0
    assert out['corner_segment_theoretical_best_s'] is not None
    assert out['realistic_available_gain_s']==0.0
    assert any(x['lap']==3 for x in out['excluded'])


def test_data_quality_rejects_outlier_and_seek_flags():
    lap=_lap(1,90.0,(30,30,30))
    lap['_samples'][500.0]['speed']=700.0
    q=lap_quality(lap)
    assert not q['eligible']
    assert 'telemetry_outlier_speed' in q['reasons']
    lap2=_lap(2,90.0,(30,30,30));lap2['replay_seek_detected']=True
    assert 'replay_seek' in lap_quality(lap2)['reasons']


def test_reference_compatibility_rejects_wet_dry_and_warns_fuel_tyre():
    a=_lap(1,90,(30,30,30),weather='dry',tyre='SOFT',fuel=20)
    b=_lap(2,90,(30,30,30),weather='wet',tyre='WET',fuel=35)
    out=reference_compatible(a,b)
    assert not out['eligible']
    assert 'mismatch:wet_dry' in out['reasons']
    assert 'mismatch:tyre_compound' in out['warnings']
    assert 'mismatch:fuel_load_large' in out['warnings']


def test_pace_only_turn_bars_use_time_and_speed_not_brake_throttle():
    cur={0:{'d':0,'t':0,'speed':200},100:{'d':100,'t':1.8,'speed':180},200:{'d':200,'t':3.8,'speed':190}}
    ref={0:{'d':0,'t':0,'speed':210},100:{'d':100,'t':1.5,'speed':190},200:{'d':200,'t':3.2,'speed':200}}
    tm={'corner_id':1,'start_m':0.0,'end_m':200.0,'entry_speed_kph':210.0,'min_speed_kph':190.0,'exit_speed_kph':200.0}
    metrics=_pace_only_turn_metrics(cur,ref,tm,current_distance_m=200.0)
    labels=[m.label for m in metrics]
    assert labels[0].startswith('Local Loss')
    assert labels[:4]==[labels[0],'Entry Speed','Min Speed','Exit Speed']
    assert metrics[0].status=='SLOWER'


def test_offline_benchmark_accepts_nonoverlap_and_detects_late(tmp_path: Path):
    p=tmp_path/'trace.jsonl'
    rows=[
        {'event':'run_start','track_name':'TEST','reference_lap_time_s':90.0},
        {'event':'pre_emit','session_time_s':10.0,'zone_id':'Z1','target_lap':1,'estimated_duration_s':2.0,'deadline_in_s':5.0},
        {'event':'post_emit','session_time_s':20.0,'zone_id':'Z1','lap':1,'estimated_duration_s':1.0,'airtime_budget_s':3.0},
        {'event':'lap_summary','zone_order_ok':True,'physical_order_ok':True},
    ]
    p.write_text('\n'.join(json.dumps(x) for x in rows))
    out=analyse_trace(p)
    assert out['pass']
    rows[1]['estimated_duration_s']=6.0
    p.write_text('\n'.join(json.dumps(x) for x in rows))
    assert analyse_trace(p)['late_count']==1

from src.corner_coach import CornerCoachEngine
from src.engineer.models import EngineerMessage, Priority


def test_corner_voice_game_time_reservation_blocks_post_queueing():
    cc=CornerCoachEngine()
    start,end=cc._reserve_speech('PRE','Z1',10.0,3.0)
    assert (start,end)==(10.0,13.0)
    assert cc._speech_wait_s(11.0)==2.0
    start2,end2=cc._reserve_speech('POST','Z1',11.0,2.0)
    assert start2==13.0 and end2==15.0


def test_corner_voice_preemption_replaces_old_game_time_reservation():
    cc=CornerCoachEngine()
    cc._reserve_speech('POST','Z1',20.0,5.0)
    start,end=cc._reserve_speech('PRE','Z2',21.0,2.0,preempt=True)
    assert start==21.0 and end==23.0
    assert cc._speech_reserved_kind=='PRE'
    assert cc._speech_reserved_zone=='Z2'


def test_visual_only_engineer_message_is_explicit():
    msg=EngineerMessage('corner:visual:post:2:Z4',Priority.COACHING,'T6, lost 0.20.',1.0,2.0,speak=False)
    assert msg.speak is False
    assert msg.estimated_duration_s is None


def test_benchmark_accepts_compromised_trace_without_false_corner_misses(tmp_path: Path):
    p=tmp_path/'trace.jsonl'
    rows=[
        {'event':'run_start','track_name':'SHANGHAI','reference_lap_time_s':90.0},
        {'event':'pre_emit','session_time_s':10.0,'zone_id':'Z1','target_lap':1,'estimated_duration_s':2.0,'deadline_in_s':5.0},
        {'event':'telemetry_discontinuity','session_time_s':14.0,'lap':1,'reason':'impossible_forward_distance_jump'},
        {'event':'lap_summary','zone_order_ok':True,'physical_order_ok':True},
    ]
    p.write_text('\n'.join(json.dumps(x) for x in rows))
    out=analyse_trace(p)
    assert out['late_count']==0
