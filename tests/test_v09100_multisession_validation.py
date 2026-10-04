from pathlib import Path
from types import SimpleNamespace

from src.measured_performance import MeasuredPerformanceRecorder
from src.overlay.data import OverlayDataProvider, build_overlay_snapshot
from src.race_state.models import CarState, Forecast, LapState, RaceState, SessionState
from src.telemetry.enums import EnumValue


def ev(raw, name):
    return EnumValue(raw, name)


def _performance(profile="qualifying"):
    return SimpleNamespace(
        completed=[],
        samples={},
        reference_mode="best",
        manual_reference_lap=None,
        event_context={"profile": profile, "metrics": {"weather_strategy": True}},
    )


def test_weather_forecast_filters_to_active_session_type():
    qual = ev(9, "One-Shot Qualifying")
    race = ev(15, "Race")
    session = SessionState(
        session_type=qual,
        weather=ev(3, "Light rain"),
        forecast_accuracy=ev(0, "Perfect"),
        forecast=(
            Forecast(qual, 0, ev(3, "Light rain"), 23, ev(2, "No change"), 18, ev(2, "No change"), 85),
            Forecast(qual, 5, ev(3, "Light rain"), 23, ev(2, "No change"), 18, ev(2, "No change"), 85),
            Forecast(qual, 10, ev(3, "Light rain"), 23, ev(2, "No change"), 18, ev(2, "No change"), 85),
            Forecast(race, 0, ev(2, "Overcast"), 25, ev(2, "No change"), 19, ev(2, "No change"), 24),
            Forecast(race, 5, ev(2, "Overcast"), 25, ev(2, "No change"), 19, ev(2, "No change"), 22),
            Forecast(race, 10, ev(2, "Overcast"), 25, ev(2, "No change"), 19, ev(2, "No change"), 19),
        ),
    )
    state = RaceState(session=session)
    snap = build_overlay_snapshot(state, _performance(), connected=True)
    assert [row.offset_minutes for row in snap.weather_forecast] == [0, 5, 10]
    assert [row.weather for row in snap.weather_forecast] == ["Light rain"] * 3
    assert [row.rain_percent for row in snap.weather_forecast] == [85, 85, 85]


def test_finished_session_suppresses_reset_timer_live_delta_and_segment():
    player = CarState(index=0)
    player.lap = LapState(
        current_lap=5,
        current_lap_time_s=0.020,
        lap_distance_m=120.0,
        lap_valid=True,
        result_status=ev(3, "Finished"),
    )
    state = RaceState(session=SessionState(session_type=ev(15, "Race")), player_index=0, player=player, field={0: player})
    ref_samples = {
        0.0: {"t": 0.0, "speed": 200, "throttle": 1.0, "brake": 0.0},
        100.0: {"t": 2.0, "speed": 200, "throttle": 1.0, "brake": 0.0},
        120.0: {"t": 2.4, "speed": 200, "throttle": 1.0, "brake": 0.0},
    }
    cur_samples = {
        0.0: SimpleNamespace(t=0.0),
        100.0: SimpleNamespace(t=1.9),
        120.0: SimpleNamespace(t=2.2),
    }
    perf = SimpleNamespace(
        completed=[{"lap": 3, "valid": True, "lap_time_s": 90.0, "sections": [], "_samples": ref_samples}],
        samples=cur_samples,
        reference_mode="best",
        manual_reference_lap=None,
        event_context={"profile": "race", "metrics": {}},
    )
    snap = build_overlay_snapshot(state, perf, connected=True)
    assert snap.session_finished is True
    assert snap.lap_time_s is None
    assert snap.live_delta_s is None
    assert snap.coach_live is False
    assert snap.active_segment_kind is None
    assert snap.active_segment_number is None


def test_performance_recorder_does_not_overwrite_final_lap_after_finish():
    player = CarState(index=0)
    player.lap = LapState(current_lap=5, current_lap_time_s=0.0, lap_distance_m=0.0, lap_valid=True, result_status=ev(2, "Active"))
    player.telemetry.speed_kph = 200
    player.telemetry.throttle = 1.0
    player.telemetry.brake = 0.0
    state = RaceState(session=SessionState(session_type=ev(15, "Race")), player_index=0, player=player, field={0: player})
    recorder = MeasuredPerformanceRecorder()

    for i in range(21):
        player.lap.lap_distance_m = float(i * 5)
        player.lap.current_lap_time_s = float(i) * 0.1
        recorder.observe(state)

    before = dict(recorder.samples)
    assert len(before) >= 20
    player.lap.result_status = ev(3, "Finished")
    player.lap.current_lap_time_s = 0.020
    player.lap.lap_distance_m = 100.0
    recorder.observe(state)

    assert recorder.samples == before
    assert recorder.samples[100.0].t == before[100.0].t


def test_overlay_provider_exposes_recorder_on_off_and_error_status():
    engine = SimpleNamespace(state=RaceState(), performance=_performance("waiting"))
    receiver = SimpleNamespace(
        engine=engine,
        _state_lock=None,
        recorder=SimpleNamespace(count=123, path=Path("recordings/test.areplay")),
        recording_error=None,
    )
    snap = OverlayDataProvider(receiver).snapshot()
    assert snap.recording_active is True
    assert snap.recording_packets == 123
    assert snap.recording_file.endswith("recordings/test.areplay")
    assert snap.recording_error is None

    receiver.recording_error = "disk full"
    snap = OverlayDataProvider(receiver).snapshot()
    assert snap.recording_active is False
    assert snap.recording_error == "disk full"

    receiver.recorder = None
    receiver.recording_error = None
    snap = OverlayDataProvider(receiver).snapshot()
    assert snap.recording_active is False
    assert snap.recording_packets == 0
    assert snap.recording_file is None
