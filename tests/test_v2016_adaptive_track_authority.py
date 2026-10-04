import json
import math

import src.overlay.track_maps as track_maps
import src.track_geometry as track_geometry
from src.reference_model import physical_corners_from_reference


def _circle_lap(offset=0.0, lap_no=1, *, compromised=False):
    length=3000.0
    samples={}
    radius=450.0
    for d in range(0,3001,5):
        a=2.0*math.pi*(d/length)
        # Small coherent offset mimics a different clean racing line while
        # preserving the same circuit/lap-distance authority.
        r=radius+offset*math.sin(a*3.0)
        samples[float(d)]={
            'd':float(d),'t':float(d)/50.0,'speed':180.0,
            'world_x':r*math.cos(a),'world_z':r*math.sin(a),
            'brake':0.0,'throttle':1.0,'steering':0.2,'gear':5,
        }
    return {
        'lap':lap_no,'valid':True,'lap_start_anchored':True,'lap_time_s':60.0+lap_no*0.01,
        'track_name':'AUSTRIA','track_length_m':length,'_samples':samples,
        'traffic_compromised':compromised,'pit_lap':False,'race_control_compromised':False,
        'damage_compromised':False,'pause_compromised':False,'replay_seek_detected':False,
        'session_restart_detected':False,
    }


def _reset(key):
    for store in (track_maps.LEARNED_TRACK_MAPS,track_maps.LEARNED_TRACK_DISTANCES,
                  track_maps.LEARNED_TRACK_LENGTHS,track_maps.LEARNED_TRACK_TURNS,
                  track_maps.LEARNED_TRACK_OBSERVATIONS,track_maps.LEARNED_TRACK_LAST_LAP,track_maps.LEARNED_TRACK_FINGERPRINTS):
        store.pop(key,None)


def test_adaptive_track_model_learns_only_from_clean_laps(tmp_path, monkeypatch):
    monkeypatch.setattr(track_maps,'_CACHE_PATH',tmp_path/'track_maps_cache.json')
    key='AUSTRIA';_reset(key)
    first=_circle_lap(0.0,1)
    assert track_maps.learn_track_model_from_clean_lap(key,first,3000.0)
    assert track_maps.LEARNED_TRACK_OBSERVATIONS[key] == 1
    before=track_maps.LEARNED_TRACK_MAPS[key]

    bad=_circle_lap(6.0,2,compromised=True)
    assert track_maps.learn_track_model_from_clean_lap(key,bad,3000.0) is None
    assert track_maps.LEARNED_TRACK_OBSERVATIONS[key] == 1
    assert track_maps.LEARNED_TRACK_MAPS[key] == before

    clean=_circle_lap(6.0,3)
    assert track_maps.learn_track_model_from_clean_lap(key,clean,3000.0)
    assert track_maps.LEARNED_TRACK_OBSERVATIONS[key] == 2
    assert track_maps.LEARNED_TRACK_LAST_LAP[key] == 3
    raw=json.loads((tmp_path/'tracks'/'AUSTRIA.json').read_text())
    assert raw['learning']['accepted_clean_laps'] == 2
    assert raw['learning']['policy'] == 'robust_running_geometry_mean_v1'


def test_adaptive_geometry_moves_gradually_not_to_one_lap(tmp_path, monkeypatch):
    monkeypatch.setattr(track_maps,'_CACHE_PATH',tmp_path/'track_maps_cache.json')
    key='AUSTRIA';_reset(key)
    assert track_maps.learn_track_model_from_clean_lap(key,_circle_lap(0.0,1),3000.0)
    base=list(track_maps.LEARNED_TRACK_MAPS[key])[:-1]
    assert track_maps.learn_track_model_from_clean_lap(key,_circle_lap(8.0,2),3000.0)
    updated=list(track_maps.LEARNED_TRACK_MAPS[key])[:-1]
    # At least some geometry refines, but capped learning prevents a single lap
    # from becoming the new authority wholesale.
    moves=[math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(base,updated)]
    assert max(moves) > 0.05
    assert max(moves) <= 1.61


def test_reference_physical_corners_prefer_shared_track_authority(monkeypatch):
    shared=tuple({
        'corner_id':i,'label':f'T{i}','start_m':100.0*i,'apex_m':100.0*i+20.0,
        'end_m':100.0*i+40.0,'turn_direction':'left' if i%2 else 'right','curvature_score':0.01,
    } for i in range(1,11))
    monkeypatch.setattr(track_geometry,'persisted_physical_turns',lambda *a,**k: shared)
    lap=_circle_lap(0.0,1)
    corners=physical_corners_from_reference(lap,'AUSTRIA')
    assert len(corners)==10
    assert corners[0].apex_m==120.0
    assert corners[-1].label=='T10'
