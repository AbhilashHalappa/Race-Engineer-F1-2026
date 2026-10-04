import queue
from types import SimpleNamespace

from src.performance_history import PerformanceHistoryStore
from src.performance_hub_ui import performance_hub_page_html
from src.race_state_receiver import RaceStateReceiver


def _lap(n, t):
    return {
        'lap': n, 'lap_time_s': t, 'valid': True, 'lap_start_anchored': True,
        '_samples': {}, 'track_name': 'LAS VEGAS', 'track_length_m': 6201.0,
    }


def test_live_history_autosave_queues_all_completed_laps_with_rec_off():
    r = RaceStateReceiver.__new__(RaceStateReceiver)
    r._telemetry_mode = 'live'
    r._history_autosave_completed_count = 0
    r._history_autosave_q = queue.Queue(maxsize=1)
    perf = SimpleNamespace(
        completed=[_lap(1, 92.0), _lap(2, 91.5), _lap(3, 91.1), _lap(4, 90.9)],
        external_reference=None, reference_mode='best',
        event_context={'session_uid': 99, 'track_name': 'LAS VEGAS', 'track_id': 20, 'session_type': 'Time Trial', 'game_mode': 5},
    )
    r.engine = SimpleNamespace(
        performance=perf,
        state=SimpleNamespace(
            session=SimpleNamespace(uid=99, session_type=SimpleNamespace(name='Time Trial')),
            player=None,
        ),
    )
    r._queue_live_history_autosave_locked()
    profile, summary, frozen = r._history_autosave_q.get_nowait()
    assert summary['laps_completed'] == 4
    assert summary['best_lap_s'] == 90.9
    assert len(frozen.completed) == 4
    assert r._history_autosave_completed_count == 4


def test_progressive_same_session_upsert_keeps_one_row_and_latest_lap_count(tmp_path):
    store = PerformanceHistoryStore(tmp_path/'perf.sqlite3')
    profile = {'name':'Driver','race_number':7,'platform_id':1}
    ctx = {'session_uid':99,'track_name':'LAS VEGAS','track_id':20,'session_type':'Time Trial','game_mode':5}
    for laps in (1,2,4):
        coach = {'event_context':ctx,'potential':{'best_lap_s':90.0}}
        store.record_session(profile, {'session_uid':99,'track':'LAS VEGAS','session_type':'Time Trial','laps_completed':laps,'best_lap_s':90.0}, coach)
    overview = store.overview()
    assert overview['totals']['sessions'] == 1
    assert overview['totals']['laps'] == 4
    assert overview['recent_sessions'][0]['laps_completed'] == 4


def test_map_persistence_is_backend_owned_not_dashboard_owned():
    from pathlib import Path
    text = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'save_learned_track_map(' not in text
    assert 'save_track_turn_markers(' not in text
    backend = Path('src/measured_performance.py').read_text(encoding='utf-8')
    assert 'learn_track_model_from_clean_lap' in backend


def test_performance_hub_has_refresh_and_back_controls():
    html = performance_hub_page_html()
    assert 'id=hubBack' in html and '>BACK<' in html
    assert 'id=hubRefresh' in html and '>REFRESH<' in html
    assert 'closeReviewToList' in html


def test_live_history_uses_game_lap_counter_even_when_analysis_lags_and_keeps_damage_summary():
    r = RaceStateReceiver.__new__(RaceStateReceiver)
    r._telemetry_mode = 'live'
    r._history_autosave_completed_count = 1
    r._history_autosave_game_lap_count = 1
    r._history_autosave_q = queue.Queue(maxsize=1)
    perf = SimpleNamespace(
        completed=[_lap(1, 92.0)], external_reference=None, reference_mode='best',
        event_context={'session_uid': 77, 'track_name': 'MELBOURNE', 'track_id': 0, 'session_type': 'Practice', 'game_mode': 3},
    )
    state = SimpleNamespace(
        session=SimpleNamespace(uid=77, session_type=SimpleNamespace(name='Practice')),
        player=SimpleNamespace(lap=SimpleNamespace(current_lap=4), identity=None),
    )
    r.engine = SimpleNamespace(performance=perf, state=state)
    r.session_summary_tracker = SimpleNamespace(build=lambda state, performance: {
        'session_uid':77, 'track':'MELBOURNE', 'session_type':'Practice',
        'laps_completed':3, 'best_lap_s':91.0,
        'max_front_wing_damage_percent':23.0, 'max_tyre_damage_percent':5.0,
    })
    r._queue_live_history_autosave_locked()
    _profile, summary, frozen = r._history_autosave_q.get_nowait()
    assert summary['laps_completed'] == 3
    assert summary['best_lap_s'] == 91.0
    assert summary['max_front_wing_damage_percent'] == 23.0
    assert summary['max_tyre_damage_percent'] == 5.0
    assert len(frozen.completed) == 1  # analysis can lag without hiding actual completed laps
    assert r._history_autosave_game_lap_count == 3
