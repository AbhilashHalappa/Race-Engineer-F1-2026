import json
import math
from pathlib import Path

from src.coaching_analysis import build_performance_pipeline
from src.coaching_live import IntegratedLiveCoach
from src.distance_performance import physical_turn_boundaries
from src.track_geometry import derive_physical_turns
import src.overlay.track_maps as track_maps


def _polygon_geometry(n=10, radius=300.0, points_per_edge=30, length=3000.0):
    vertices=[
        (radius*math.cos(2*math.pi*i/n), radius*math.sin(2*math.pi*i/n))
        for i in range(n)
    ]
    pts=[]
    # Start halfway along a straight so S/F is not inside a corner.
    a,b=vertices[0],vertices[1]
    for j in range(points_per_edge//2, points_per_edge):
        t=j/points_per_edge
        pts.append((a[0]*(1-t)+b[0]*t, a[1]*(1-t)+b[1]*t))
    for i in range(1,n):
        a,b=vertices[i],vertices[(i+1)%n]
        for j in range(points_per_edge):
            t=j/points_per_edge
            pts.append((a[0]*(1-t)+b[0]*t, a[1]*(1-t)+b[1]*t))
    a,b=vertices[0],vertices[1]
    for j in range(0, points_per_edge//2):
        t=j/points_per_edge
        pts.append((a[0]*(1-t)+b[0]*t, a[1]*(1-t)+b[1]*t))

    raw=[0.0]
    total=0.0
    for p,q in zip(pts,pts[1:]):
        total += math.hypot(q[0]-p[0], q[1]-p[1])
        raw.append(total)
    total += math.hypot(pts[0][0]-pts[-1][0], pts[0][1]-pts[-1][1])
    ds=[d/total*length for d in raw]
    return pts,ds,length


def _xy_at(distance, points, distances, length):
    if distance >= length:
        return points[0]
    for i in range(1,len(distances)):
        if distances[i] >= distance:
            d0,d1=distances[i-1],distances[i]
            alpha=(distance-d0)/(d1-d0)
            p0,p1=points[i-1],points[i]
            return (
                p0[0]+(p1[0]-p0[0])*alpha,
                p0[1]+(p1[1]-p0[1])*alpha,
            )
    return points[-1]


def _lap(*, current=False):
    points,distances,length=_polygon_geometry()
    samples={}
    for d in range(0,3001,5):
        x,z=_xy_at(float(d),points,distances,length)
        extra=0.0
        if current:
            # Lose 120 ms on T2's approach, then regain 40 ms much later.
            if 350 <= d < 425:
                extra=0.12*(d-350)/75.0
            elif d >= 425:
                extra=0.12
            if 2000 <= d < 2100:
                extra -= 0.04*(d-2000)/100.0
            elif d >= 2100:
                extra -= 0.04
        brake_start=360 if current else 380
        samples[float(d)]={
            'd':float(d), 't':d/50.0+extra, 'speed':180.0,
            'brake':0.80 if brake_start <= d <= 420 else 0.0,
            'throttle':0.20 if 425 <= d <= 455 else 1.0,
            'steering':0.35 if 425 <= d <= 475 else 0.0,
            'gear':5, 'slip':0.0, 'world_x':x, 'world_z':z,
        }
    return {
        'track_name':'AUSTRIA', 'track_length_m':length,
        'lap_time_s':60.08 if current else 60.0,
        'valid':True, 'lap_start_anchored':True,
        '_samples':samples, 'sections':[],
    }


def test_geometry_turn_regions_are_separate_and_ordered():
    points,distances,length=_polygon_geometry()
    turns=derive_physical_turns(
        'AUSTRIA', points, point_distances_m=distances,
        track_length_m=length,
    )
    assert len(turns) == 10
    assert [x['label'] for x in turns] == [f'T{i}' for i in range(1,11)]
    assert all(x['start_m'] < x['apex_m'] < x['end_m'] for x in turns)
    assert all(turns[i]['end_m'] < turns[i+1]['start_m'] for i in range(len(turns)-1))


def test_full_pipeline_reconciles_turns_and_straights_and_diagnoses_physical_turn():
    reference=_lap(current=False)
    current=_lap(current=True)
    pipeline=build_performance_pipeline(current,reference)
    model=pipeline['distance_model']

    assert pipeline['available'] is True
    assert len(model['turns']) == 10
    assert len(model['segments']) >= 19
    assert {x['segment_kind'] for x in model['segments']} == {'turn','straight'}
    assert abs(model['reconciliation_error_s']) < 1e-9
    assert abs(model['partition_net_delta_s'] - model['full_track_net_delta_s']) < 1e-9
    assert any(z['state'] == 'LOSS' for z in model['gain_loss_zones'])
    assert any(z['state'] == 'GAIN' for z in model['gain_loss_zones'])

    # T2 is diagnosed from the continuous physical-turn trace even though this
    # synthetic reference deliberately contains no detector/brake section list.
    t2=next(x for x in pipeline['turns'] if x['corner_id'] == 2)
    assert t2['diagnosis'] == 'brake_early'
    assert t2['coaching_eligible'] is True
    assert abs(t2['reference_brake_m'] - 380.0) < 1e-9
    assert t2['net_loss_s'] >= 0.119
    analysis=next(x for x in pipeline['corner_analyses'] if x['corner_id'] == 2)
    assert analysis['analysis_source'] == 'physical_distance_trace'


def test_pre_reference_targets_cover_every_physical_turn():
    reference=_lap(current=False)
    turns=physical_turn_boundaries(reference,track_name='AUSTRIA')
    seeded=IntegratedLiveCoach._reference_seed_advice(reference)
    assert len(turns) == 10
    assert sorted(seeded) == list(range(1,11))
    assert seeded[2]['reference_brake_m'] == 380.0


def test_track_schema_v5_persists_physical_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(track_maps,'_CACHE_PATH',tmp_path/'track_maps_cache.json')
    key='AUSTRIA'
    for store in (track_maps.LEARNED_TRACK_MAPS,track_maps.LEARNED_TRACK_DISTANCES,
                  track_maps.LEARNED_TRACK_LENGTHS,track_maps.LEARNED_TRACK_TURNS):
        store.pop(key,None)
    reference=_lap(current=False)
    assert track_maps.save_learned_track_map_samples(key,reference['_samples'],reference['track_length_m'])
    raw=json.loads((tmp_path/'tracks'/'AUSTRIA.json').read_text())
    assert raw['version'] == 5
    assert len(raw['turns']) == 10
    assert all({'start_m','apex_m','end_m','turn_direction'} <= set(t) for t in raw['turns'])


def test_native_and_lan_map_sources_expose_full_track_gain_loss_layer():
    root=Path(__file__).resolve().parents[1]
    native=(root/'src'/'overlay'/'window.py').read_text(encoding='utf-8')
    lan=(root/'src'/'dashboard_server.py').read_text(encoding='utf-8')
    data=(root/'src'/'overlay'/'data.py').read_text(encoding='utf-8')
    assert 'map_gain_loss_zones' in native
    assert 'map_gain_loss_zones' in lan
    assert 'map_performance_segments' in data
