from pathlib import Path
from types import SimpleNamespace

from src.measured_performance import MeasuredPerformanceRecorder
from src.race_state.models import Freshness
from src.driver_profiles import DriverProfileStore
from src.performance_history import PerformanceHistoryStore
from src.skill_evidence import SkillEvidenceStore
from src.skill_trends import SkillTrendStore


def _enum(name="None", raw=0):
    return SimpleNamespace(name=name, raw=raw)


def _traffic_state(frame, t, *, player_d=1000.0, other_d=None, speed=216):
    player = SimpleNamespace(
        lap=SimpleNamespace(pit_status=_enum(), gap_to_car_in_front_s=3.0, lap_distance_m=player_d, current_lap_time_s=t),
        telemetry=SimpleNamespace(speed_kph=speed),
        damage=SimpleNamespace(front_left_wing_percent=0,front_right_wing_percent=0,floor_percent=0,engine_blown=False,engine_seized=False),
    )
    field={0:player}
    if other_d is not None:
        field[1]=SimpleNamespace(lap=SimpleNamespace(pit_status=_enum(),lap_distance_m=other_d))
    return SimpleNamespace(
        player=player,player_index=0,field=field,gap_behind_s=5.0,
        session=SimpleNamespace(session_time_s=t,paused=False,safety_car=_enum(),marshal_zones=(),track_length_m=4657.0),
        updated={"lap":Freshness(t,frame,t)},
    )


def test_visible_but_not_close_practice_car_does_not_exclude_lap():
    r=MeasuredPerformanceRecorder(); r.event_context={"profile":"practice"}
    # At 216 km/h the .29 interaction window is 42 m. A car 70 m ahead is
    # plainly visible but should not contaminate coaching evidence.
    for frame,t in ((1,10.0),(2,11.0),(3,12.2),(4,13.0)):
        r._update_lap_quality_flags(_traffic_state(frame,t,other_d=1070.0))
    assert r.current_lap_traffic_compromised is False
    assert r.current_lap_traffic_front_min_distance_m is None


def test_sustained_close_practice_car_still_excludes_lap():
    r=MeasuredPerformanceRecorder(); r.event_context={"profile":"practice"}
    for frame,t in ((1,20.0),(2,21.0),(3,22.1)):
        r._update_lap_quality_flags(_traffic_state(frame,t,other_d=1030.0))
    assert r.current_lap_traffic_compromised is True
    assert r.current_lap_traffic_trigger == "sustained_physical_front"


def _make_driver_store(root: Path, history_profile_id=None):
    store=DriverProfileStore(root)
    compat={"performance_history_profile_id":history_profile_id} if history_profile_id is not None else None
    profile=store.create_profile("Tester", compatibility=compat)
    store.set_active_driver(profile["driver_id"])
    return store, profile


def test_available_tracks_follow_performance_history_not_stale_unknown(tmp_path: Path, monkeypatch):
    ph=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    hid=ph.create_user_profile('Tester')
    ds, profile=_make_driver_store(tmp_path/'drivers', hid)
    ph.record_session({'name':'Tester'}, {'session_uid':11,'track':'Catalunya','session_type':'Time Trial','laps_completed':1},
                      {'created_utc':'2026-10-03T00:00:00+00:00','event_context':{'session_uid':11,'track_name':'Catalunya','session_type':'Time Trial'},'lap_telemetry':{}})
    import src.performance_history as phmod
    monkeypatch.setattr(phmod, 'PerformanceHistoryStore', lambda *a, **k: ph)
    # A stale derived Unknown evidence row exists, but the authoritative Hub does not.
    trend=SkillTrendStore(ds)
    root=trend.root(profile['driver_id'])/'skill_evidence'
    (root/'sessions').mkdir(parents=True,exist_ok=True)
    stale={'session_key':'legacy','session_uid':99,'track':'Unknown','session_type':'Time Trial','timestamp':'2026-10-02T00:00:00+00:00','measurements':[]}
    (root/'sessions'/'legacy.json').write_text(__import__('json').dumps(stale),encoding='utf-8')
    (root/'index.json').write_text(__import__('json').dumps({'sessions':[dict(stale,path='sessions/legacy.json')]}),encoding='utf-8')
    assert trend.available_tracks(profile['driver_id']) == ['Catalunya']


def test_reconcile_links_legacy_unknown_by_unique_session_uid(tmp_path: Path):
    ph=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    hid=ph.create_user_profile('Tester')
    ds, profile=_make_driver_store(tmp_path/'drivers', hid)
    history_id=ph.record_session({'name':'Tester'}, {'session_uid':77,'track':'Catalunya','session_type':'Time Trial','laps_completed':1},
                                 {'created_utc':'2026-10-03T00:00:00+00:00','event_context':{'session_uid':77,'track_name':'Catalunya','session_type':'Time Trial'},'lap_telemetry':{}})
    se=SkillEvidenceStore(ds, performance_history_store=ph)
    root=se.root(profile['driver_id'],'f1_26'); (root/'sessions').mkdir(parents=True,exist_ok=True)
    payload={'session_key':'legacy77','session_uid':77,'track':'Unknown','session_type':'Unknown','timestamp':'2026-10-03T00:00:00+00:00','measurement_count':0,'measurements':[]}
    (root/'sessions'/'legacy77.json').write_text(__import__('json').dumps(payload),encoding='utf-8')
    (root/'index.json').write_text(__import__('json').dumps({'sessions':[dict(payload,path='sessions/legacy77.json')]}),encoding='utf-8')
    out=se.reconcile_with_performance_history(driver_id=profile['driver_id'])
    assert out['updated'] >= 1
    idx=__import__('json').loads((root/'index.json').read_text())
    assert len(idx['sessions']) == 1
    assert idx['sessions'][0]['track'] == 'Catalunya'
    assert int(idx['sessions'][0]['performance_history_session_id']) == history_id
