from types import SimpleNamespace

from src.measured_performance import MeasuredPerformanceRecorder
from src.race_state.models import Freshness
from src.race_state_receiver import RaceStateReceiver


def _enum(name="None", raw=0):
    return SimpleNamespace(name=name, raw=raw)


def _state(*, frame=1, time_s=10.0, front=5.0, rear=5.0, distance=1000.0, physical_front_m=None, physical_rear_m=None):
    lap = SimpleNamespace(
        pit_status=_enum(),
        gap_to_car_in_front_s=front,
        lap_distance_m=distance,
        current_lap_time_s=time_s,
    )
    damage = SimpleNamespace(
        front_left_wing_percent=0,
        front_right_wing_percent=0,
        floor_percent=0,
        engine_blown=False,
        engine_seized=False,
    )
    telemetry=SimpleNamespace(speed_kph=216)  # 60 m/s => 60 m physical headway window
    player = SimpleNamespace(lap=lap, damage=damage, telemetry=telemetry)
    field={0: player}
    if physical_front_m is not None:
        field[1]=SimpleNamespace(lap=SimpleNamespace(pit_status=_enum(),lap_distance_m=distance+physical_front_m))
    if physical_rear_m is not None:
        field[2]=SimpleNamespace(lap=SimpleNamespace(pit_status=_enum(),lap_distance_m=distance-physical_rear_m))
    session = SimpleNamespace(
        session_time_s=time_s,
        paused=False,
        safety_car=_enum(),
        marshal_zones=(),
        track_length_m=4657.0,
    )
    return SimpleNamespace(
        player=player,
        player_index=0,
        field=field,
        session=session,
        gap_behind_s=rear,
        updated={"lap": Freshness(time_s, frame, time_s)},
    )


def test_practice_rear_traffic_alone_does_not_exclude_lap():
    r = MeasuredPerformanceRecorder()
    r.event_context = {"profile": "practice"}
    s = _state(front=0.4, rear=0.4, physical_rear_m=20.0)
    r._update_lap_quality_flags(s)
    assert r.current_lap_traffic_compromised is False
    assert r.current_lap_traffic_rear_min_gap_s == 0.4


def test_practice_brief_front_traffic_does_not_exclude_lap():
    r = MeasuredPerformanceRecorder()
    r.event_context = {"profile": "practice"}
    for frame, t in ((1, 10.0), (2, 10.8), (3, 11.5)):
        r._update_lap_quality_flags(_state(frame=frame, time_s=t, front=0.7, rear=0.5, physical_front_m=40.0))
    r._update_lap_quality_flags(_state(frame=4, time_s=11.6, front=1.4, rear=0.5, physical_front_m=90.0))
    assert r.current_lap_traffic_compromised is False
    assert 1.59 <= r.current_lap_traffic_front_max_close_s <= 1.61


def test_practice_sustained_front_traffic_excludes_lap():
    r = MeasuredPerformanceRecorder()
    r.event_context = {"profile": "practice"}
    for frame, t in ((1, 20.0), (2, 21.0), (3, 22.05)):
        r._update_lap_quality_flags(_state(frame=frame, time_s=t, front=0.8, rear=0.3, physical_front_m=35.0))
    assert r.current_lap_traffic_compromised is True
    assert r.current_lap_traffic_trigger == "sustained_physical_front"
    assert r.current_lap_traffic_front_max_close_s >= 2.0


def test_non_lap_packets_cannot_turn_one_close_gap_into_sustained_traffic():
    r = MeasuredPerformanceRecorder()
    r.event_context = {"profile": "practice"}
    s = _state(frame=10, time_s=30.0, front=0.6)
    r._update_lap_quality_flags(s)
    # Same LapData frame, but other packet families advanced session time.
    for t in (31.0, 32.0, 35.0):
        s.session.session_time_s = t
        r._update_lap_quality_flags(s)
    assert r.current_lap_traffic_compromised is False
    assert r.current_lap_traffic_front_max_close_s == 0.0


def test_race_keeps_strict_close_traffic_policy():
    r = MeasuredPerformanceRecorder()
    r.event_context = {"profile": "race"}
    r._update_lap_quality_flags(_state(front=5.0, rear=0.7))
    assert r.current_lap_traffic_compromised is True
    assert r.current_lap_traffic_trigger == "rear"


def test_time_trial_ignores_traffic_gap_state_for_quality():
    r = MeasuredPerformanceRecorder()
    r.event_context = {"profile": "time_trial"}
    r._update_lap_quality_flags(_state(front=0.2, rear=0.2))
    assert r.current_lap_traffic_compromised is False


def test_live_receiver_protects_lapdata_from_coalescing():
    r = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    try:
        assert 2 not in r.coalesce_packet_ids
        assert {0, 6, 13, 15, 16}.issubset(r.coalesce_packet_ids)

        def packet(pid, tag):
            data = bytearray(8)
            data[6] = pid
            data[7] = tag
            return (bytes(data), ("127.0.0.1", 20777), float(tag))

        batch = [packet(2, 1), packet(0, 2), packet(2, 3), packet(0, 4)]
        out = r._coalesce_datagrams(batch)
        assert [(x[0][6], x[0][7]) for x in out] == [(2, 1), (2, 3), (0, 4)]
        assert r.coalesced_by_packet_id[0] == 1
        assert r.coalesced_by_packet_id[2] == 0
    finally:
        r._close_history_autosave()
