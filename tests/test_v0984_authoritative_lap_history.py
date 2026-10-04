from types import SimpleNamespace as NS
from src.measured_performance import MeasuredPerformanceRecorder, Sample


def row(ms, valid=True):
    return NS(m_lapTimeInMS=ms, m_lapValidBitFlags=1 if valid else 0)


def state(history, player_index=0):
    lap=NS(lap_valid=True, previous_lap_time_s=99.999)
    player=NS(lap=lap)
    return NS(player=player, player_index=player_index, extended={'history':history})


def samples(n=25):
    return {float(i*5): Sample(float(i*5), i*.1, 100, 1, 0, 0, 5, 10000) for i in range(n)}


def test_history_overrides_transition_time_and_validity():
    r=MeasuredPerformanceRecorder(); st=state(NS(m_carIdx=0,m_numLaps=2,m_lapHistoryData=(row(74579,True),row(70488,False))))
    r.completed=[{'lap':1,'lap_time_s':70.387,'valid':False,'_samples':{}}, {'lap':2,'lap_time_s':71.042,'valid':True,'_samples':{}}]
    r.current_lap=3; r.samples={}
    r._sync_session_history(st)
    assert r.completed[0]['lap_time_s']==74.579 and r.completed[0]['valid'] is True
    assert r.completed[1]['lap_time_s']==70.488 and r.completed[1]['valid'] is False


def test_history_closes_final_lap_without_lap_number_increment():
    r=MeasuredPerformanceRecorder(); st=state(NS(m_carIdx=0,m_numLaps=1,m_lapHistoryData=(row(69617,True),)))
    r.current_lap=1; r.current_lap_valid=True; r.samples=samples()
    r._sync_session_history(st)
    assert len(r.completed)==1
    assert r.completed[0]['lap']==1
    assert r.completed[0]['lap_time_s']==69.617
    assert r.completed[0]['valid'] is True
    assert r.samples=={}


def test_history_for_other_car_is_ignored():
    r=MeasuredPerformanceRecorder(); st=state(NS(m_carIdx=1,m_numLaps=1,m_lapHistoryData=(row(69617,True),)))
    r.current_lap=1; r.samples=samples()
    r._sync_session_history(st)
    assert r.completed==[]

def test_austria_time_trial_history_matches_game_results_validity():
    # Regression values from the preserved Austria Time Trial recording/results.
    rows=(row(74579,True),row(75509,True),row(70832,True),row(69617,True),
          row(69756,False),row(70488,True),row(70916,False),row(72065,True))
    r=MeasuredPerformanceRecorder(); st=state(NS(m_carIdx=0,m_numLaps=8,m_lapHistoryData=rows))
    r.completed=[{'lap':i,'lap_time_s':60.0+i,'valid':True,'_samples':{}} for i in range(1,9)]
    r.current_lap=9; r.samples={}
    r._sync_session_history(st)
    ranked=sorted((x for x in r.completed if x['valid']),key=lambda x:x['lap_time_s'])
    assert [(x['lap'],x['lap_time_s']) for x in ranked]==[(4,69.617),(6,70.488),(3,70.832),(8,72.065),(1,74.579),(2,75.509)]
    assert [x['lap'] for x in r.completed if not x['valid']]==[5,7]
