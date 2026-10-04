from pathlib import Path
from types import SimpleNamespace

from src.driver_profiles import DriverProfileStore
from src.performance_history import PerformanceHistoryStore
from src.career_history import CareerHistoryStore
from src.race_state.models import RaceState, CarState
from src.session_summary import SessionSummaryTracker


def _stores(tmp_path: Path):
    ph=PerformanceHistoryStore(tmp_path/'performance.sqlite3')
    pid=ph.create_user_profile('Tester')
    ph.set_active_user_profile(pid)
    ds=DriverProfileStore(tmp_path/'drivers')
    profile=ds.create_profile('Tester',active_game='f1_26',compatibility={'performance_history_profile_id':pid})
    return ds,profile,ph,pid


def _record(ph, *, uid, created, track, session_type, position=None, grid=None, best=None,
            result_status='Finished', result_raw=3, race_fastest_lap=None, race_fastest_lap_s=None):
    summary={
        'session_uid':uid,'created_utc':created,'track':track,'session_type':session_type,
        'position':position,'grid_position':grid,'best_lap_s':best,
        'result_status':result_status,'result_status_raw':result_raw,'laps_completed':10,
    }
    if race_fastest_lap is not None:
        summary['race_fastest_lap']=race_fastest_lap
    if race_fastest_lap_s is not None:
        summary['race_fastest_lap_s']=race_fastest_lap_s
    coach={'created_utc':created,'event_context':{'session_uid':uid,'track':track,'session_type':session_type}}
    ph.record_session({'name':'Tester','driver_id':1,'race_number':1,'game_year':2026},summary,coach)


def test_history_adds_wins_podiums_poles_and_live_lap_pbs(tmp_path):
    ds,p,ph,_=_stores(tmp_path)
    _record(ph,uid=1,created='2026-07-01T08:00:00+00:00',track='Melbourne',session_type='Time Trial',best=82.5)
    _record(ph,uid=2,created='2026-07-02T08:00:00+00:00',track='Melbourne',session_type='Time Trial',best=82.1)
    _record(ph,uid=3,created='2026-07-03T08:00:00+00:00',track='Melbourne',session_type='Qualifying 3',position=1,best=82.3)
    _record(ph,uid=4,created='2026-07-04T08:00:00+00:00',track='Melbourne',session_type='Race',position=1,grid=1,best=83.0,race_fastest_lap=True,race_fastest_lap_s=83.0)
    _record(ph,uid=5,created='2026-07-05T08:00:00+00:00',track='Spa',session_type='Race',position=2,grid=3,best=104.0)
    data=CareerHistoryStore(ds,ph).ensure(p['driver_id'])
    titles=[x['title'] for x in data['events']]
    assert any(t.startswith('Grand Prix win — Melbourne') for t in titles)
    assert 'First Grand Prix win' in titles
    assert any(t.startswith('Podium — P2 at Spa') for t in titles)
    assert any(t.startswith('Pole position — Melbourne') for t in titles)
    assert any(t.startswith('Race fastest lap — Melbourne') for t in titles)
    assert any(t.startswith('New Melbourne personal fastest lap') for t in titles)
    assert all('replay' not in (x.get('detail') or '').lower() for x in data['events'])


def test_unfinished_race_never_creates_win(tmp_path):
    ds,p,ph,_=_stores(tmp_path)
    _record(ph,uid=10,created='2026-08-01T08:00:00+00:00',track='Monza',session_type='Race',position=1,best=90.0,result_status='Active',result_raw=2)
    data=CareerHistoryStore(ds,ph).ensure(p['driver_id'])
    assert not any(x.get('id','').startswith('race_win_') for x in data['events'])


def test_session_summary_marks_authoritative_race_fastest_lap():
    s=RaceState(player_index=0,player=CarState(index=0)); s.field[0]=s.player
    s.session.uid=22; s.session.session_type=SimpleNamespace(name='Race')
    own=SimpleNamespace(m_resultStatus=3,m_position=1,m_gridPosition=2,m_numLaps=5,m_points=25,m_numPitStops=0,
                        m_bestLapTimeInMS=81234,m_totalRaceTime=500.0,m_penaltiesTime=0,m_numPenalties=0,m_numTyreStints=0,
                        m_tyreStintsActual=(),m_tyreStintsVisual=(),m_tyreStintsEndLaps=())
    rival=SimpleNamespace(m_bestLapTimeInMS=81500)
    s.extended['final']=SimpleNamespace(m_classificationData=(own,rival))
    summary=SessionSummaryTracker().build(s,SimpleNamespace(completed=[]))
    assert summary['race_fastest_lap'] is True
    assert summary['race_fastest_lap_s']==81.234


def test_session_summary_does_not_mark_fastest_when_rival_is_faster():
    s=RaceState(player_index=0,player=CarState(index=0)); s.field[0]=s.player
    s.session.uid=23; s.session.session_type=SimpleNamespace(name='Race')
    own=SimpleNamespace(m_resultStatus=3,m_position=2,m_gridPosition=2,m_numLaps=5,m_points=18,m_numPitStops=0,
                        m_bestLapTimeInMS=82000,m_totalRaceTime=501.0,m_penaltiesTime=0,m_numPenalties=0,m_numTyreStints=0,
                        m_tyreStintsActual=(),m_tyreStintsVisual=(),m_tyreStintsEndLaps=())
    rival=SimpleNamespace(m_bestLapTimeInMS=81000)
    s.extended['final']=SimpleNamespace(m_classificationData=(own,rival))
    summary=SessionSummaryTracker().build(s,SimpleNamespace(completed=[]))
    assert summary['race_fastest_lap'] is False
    assert summary['race_fastest_lap_s']==81.0


def test_history_ui_exposes_result_and_lap_pb_counts():
    source=Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert '"Race results","Lap PBs"' in source
    assert '"result":"#4ed282"' in source
    assert '"lap_pb":"#c58cff"' in source
