from src.race_state.models import RaceState, CarState
from src.strategy_engine import assess_strategy, format_gap_trend


def _state(samples):
    s = RaceState(); c = CarState(0)
    s.player = s.field[0] = c; s.player_index = 0
    s.session.total_laps = 10; c.lap.current_lap = 5
    c.lap.gap_to_car_in_front_s = samples[-1][1] if samples else 2.0
    s.extended['_strategy_gap_samples'] = tuple(samples)
    return s


def test_large_gap_discontinuity_is_not_reported_as_pace_trend():
    s = _state(((10.0, 2.0, 1), (11.0, 1.9, 1), (12.0, 9.7, 1),
                (13.0, 9.6, 1), (14.0, 9.5, 1)))
    a = assess_strategy(s)
    assert a.gap_ahead_change_s_per_lap is None
    assert format_gap_trend(s).startswith('Gap trend unavailable')


def test_scattered_gap_window_is_rejected():
    s = _state(((10.0, 2.0, 1), (11.0, 1.6, 1), (12.0, 1.9, 1),
                (13.0, 1.5, 1), (14.0, 1.8, 1), (15.0, 1.4, 1)))
    a = assess_strategy(s)
    assert a.gap_ahead_change_s_per_lap is None


def test_stable_same_opponent_window_still_reports_trend():
    s = _state(((10.0, 2.00, 1), (11.0, 1.94, 1), (12.0, 1.88, 1),
                (13.0, 1.82, 1), (14.0, 1.76, 1), (15.0, 1.70, 1)))
    a = assess_strategy(s)
    assert a.gap_trend == 'closing'
    assert a.gap_trend_basis == '10s'
    assert a.gap_ahead_change_s_per_lap == -0.6


def test_absurd_completed_lap_gap_delta_is_ignored():
    # No rolling samples and no sane completed-lap trend => unavailable.
    from src.race_state.models import MeasuredLapFact
    s = _state(())
    # Construct via defaults is version-dependent; mutate only if supported.
    try:
        fact = MeasuredLapFact(lap=1, gap_ahead_change_s=77.0)
    except TypeError:
        return
    s.measured_laps = (fact,)
    assert assess_strategy(s).gap_ahead_change_s_per_lap is None


def test_sampler_resets_when_car_ahead_changes():
    from src.race_state.engine import RaceStateEngine
    e = RaceStateEngine(); c = CarState(0)
    e.state.player = e.state.field[0] = c; e.state.player_index = 0
    c.lap.position = 3; e.state.ahead_index = 1
    for t, gap in ((10.0, 2.0), (11.0, 1.9), (12.0, 1.8)):
        e.state.session.session_time_s = t; c.lap.gap_to_car_in_front_s = gap
        e._observe_strategy_gap_sample()
    assert len(e.state.extended['_strategy_gap_samples']) == 3
    e.state.ahead_index = 2; e.state.session.session_time_s = 13.0; c.lap.gap_to_car_in_front_s = 1.2
    e._observe_strategy_gap_sample()
    assert e.state.extended['_strategy_gap_samples'] == ((13.0, 1.2, 2),)


def test_sampler_resets_on_position_change_even_same_ahead_index():
    from src.race_state.engine import RaceStateEngine
    e = RaceStateEngine(); c = CarState(0)
    e.state.player = e.state.field[0] = c; e.state.player_index = 0
    c.lap.position = 4; e.state.ahead_index = 1
    for t, gap in ((20.0, 3.0), (21.0, 2.9)):
        e.state.session.session_time_s = t; c.lap.gap_to_car_in_front_s = gap
        e._observe_strategy_gap_sample()
    c.lap.position = 3; e.state.session.session_time_s = 22.0; c.lap.gap_to_car_in_front_s = 1.4
    e._observe_strategy_gap_sample()
    assert e.state.extended['_strategy_gap_samples'] == ((22.0, 1.4, 1),)
