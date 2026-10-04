from types import SimpleNamespace
from pathlib import Path

from src.measured_performance import MeasuredPerformanceRecorder
from src.race_state.models import RaceState


def _state(**overrides):
    base=dict(
        traction_control_assist=2,
        anti_lock_brakes_assist=1,
        gearbox_assist=2,
        steering_assist=0,
        braking_assist=0,
        pit_assist=0,
        pit_release_assist=0,
        ers_assist=1,
        drs_assist=1,
        equal_car_performance=1,
    )
    base.update(overrides)
    return SimpleNamespace(session=SimpleNamespace(**base))


def test_live_session_data_is_assist_authority_for_all_supported_fields():
    assists=MeasuredPerformanceRecorder._live_assists(_state())
    assert assists == {
        'traction_control': 2,
        'anti_lock_brakes': 1,
        'gearbox_assist': 2,
        'steering_assist': 0,
        'braking_assist': 0,
        'pit_assist': 0,
        'pit_release_assist': 0,
        'ers_assist': 1,
        'drs_assist': 1,
        'equal_car_performance': 1,
    }


def test_mid_lap_assist_change_is_latched_with_start_and_end_state():
    rec=MeasuredPerformanceRecorder()
    state=_state(traction_control_assist=2, anti_lock_brakes_assist=1)
    rec._start_lap_assist_tracking(state)

    state.session.traction_control_assist=1
    rec._observe_lap_assists(state, lap_time_s=31.5, distance_m=1420.0)

    assert rec.current_lap_assists_start['traction_control'] == 2
    assert rec.current_lap_assists_end['traction_control'] == 1
    assert rec.current_lap_assist_changes == [{
        'lap_time_s':31.5,
        'distance_m':1420.0,
        'changes':{'traction_control':{'from':2,'to':1}},
    }]


def test_timetrial_session_best_is_not_used_as_current_lap_assist_authority():
    source=Path('src/measured_performance.py').read_text(encoding='utf-8')
    # Time Trial PB/session-best data may still exist elsewhere for reference
    # comparison, but the lap summary assist block must not source it.
    start=source.index('        # Use the assist state actually observed on this lap.')
    end=source.index("        lap_state=getattr", start)
    assist_block=source[start:end]
    assert 'm_playerSessionBestDataSet' not in assist_block
    assert 'current_lap_assists_end' in assist_block
    assert 'assist_changes' in assist_block


def test_race_state_session_model_has_full_live_assist_fields():
    state=RaceState()
    session=state.session
    for attr in (
        'traction_control_assist','anti_lock_brakes_assist','gearbox_assist',
        'steering_assist','braking_assist','pit_assist','pit_release_assist',
        'ers_assist','drs_assist',
    ):
        assert hasattr(session, attr)
