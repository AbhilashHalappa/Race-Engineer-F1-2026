from types import SimpleNamespace

from src.coaching_live import IntegratedLiveCoach
from src.coaching_settings import CoachingSettingsStore
from src.data_quality import live_context_blockers
from src.engineer.models import EngineerMessage, Priority
from src.race_state.models import Freshness
from src.tts import SpeechOutput


def _enum(name="None", raw=0):
    return SimpleNamespace(name=name, raw=raw)


def _state(now=100.0, *, front=5.0, behind=5.0, telem_age=0.1, lap_age=0.1):
    lap = SimpleNamespace(
        pit_status=_enum(), lap_valid=True, gap_to_car_in_front_s=front,
        current_lap=3, lap_distance_m=1000.0,
    )
    telemetry = SimpleNamespace(brake=0.0, steering=0.0, throttle=1.0, speed_kph=250.0)
    damage = SimpleNamespace(front_left_wing_percent=0, front_right_wing_percent=0, floor_percent=0,
                             engine_blown=False, engine_seized=False)
    player = SimpleNamespace(
        lap=lap, telemetry=telemetry, damage=damage,
        updated={
            "telemetry": Freshness(now-telem_age, 1, 0.0),
            "lap": Freshness(now-lap_age, 1, 0.0),
        },
    )
    session = SimpleNamespace(paused=False, safety_car=_enum(), marshal_zones=(), session_time_s=10.0)
    return SimpleNamespace(player=player, session=session, gap_behind_s=behind)


def test_performance_coach_mode_keeps_pre_and_post(tmp_path):
    store = CoachingSettingsStore(tmp_path / "coaching.json")
    store.set(mode="performance_coach", pre_corner=True, post_corner=True)
    coach = IntegratedLiveCoach(store)
    effective = coach._effective("time_trial")
    assert effective["pre"] is True
    assert effective["post"] is True


def test_race_context_blocks_close_car_ahead_and_behind():
    s = _state(front=0.8, behind=0.7)
    blockers = live_context_blockers(s, race_mode=True, traffic_gap_s=1.2, rear_traffic_gap_s=1.0, now=100.0)
    assert "close_traffic_ahead" in blockers
    assert "close_traffic_behind" in blockers


def test_live_context_blocks_stale_telemetry_and_lap():
    s = _state(telem_age=1.5, lap_age=3.0)
    blockers = live_context_blockers(s, race_mode=False, now=100.0, stale_telemetry_s=1.0, stale_lap_s=2.0)
    assert "stale_telemetry" in blockers
    assert "stale_lap" in blockers


def test_tts_replaces_old_pre_corner_and_lap_summary_calls():
    assert SpeechOutput._replaceable_family("coach:pre:4:3:trail_brake_weak") == "coach:pre:3"
    assert SpeechOutput._replaceable_family("coach:pre:5:3:minimum_speed_low") == "coach:pre:3"
    assert SpeechOutput._replaceable_family("coach:lap_summary:4") == "coach:lap_summary"
    assert SpeechOutput._replaceable_family("coach:lap_summary:5") == "coach:lap_summary"


def test_pre_corner_tts_has_short_stale_window(monkeypatch):
    out = object.__new__(SpeechOutput)
    out.config = SimpleNamespace(critical_max_age_s=2.0, strategy_max_age_s=5.0, information_max_age_s=3.0)
    monkeypatch.setattr("src.tts.time.monotonic", lambda: 102.0)
    m = EngineerMessage(key="coach:pre:4:3:x", priority=Priority.COACHING, text="x", created_at=100.0)
    assert out._is_stale(m) is True

from src.measured_performance import MeasuredPerformanceRecorder
from src.data_quality import lap_quality


def test_recorder_latches_compromised_reference_conditions():
    r = MeasuredPerformanceRecorder()
    lap = SimpleNamespace(pit_status=_enum("Pitting"), gap_to_car_in_front_s=0.6)
    damage = SimpleNamespace(front_left_wing_percent=25, front_right_wing_percent=0, floor_percent=0,
                             engine_blown=False, engine_seized=False)
    player = SimpleNamespace(lap=lap, damage=damage)
    session = SimpleNamespace(safety_car=_enum("Safety Car", 1), marshal_zones=())
    state = SimpleNamespace(player=player, session=session, gap_behind_s=0.7)
    r._update_lap_quality_flags(state)
    assert r.current_lap_pit
    assert r.current_lap_traffic_compromised
    assert r.current_lap_race_control_compromised
    assert r.current_lap_damage_compromised


def test_compromised_lap_is_not_reference_eligible():
    q = lap_quality({
        "valid": True, "lap_start_anchored": True, "sample_count": 500, "lap_time_s": 70.0,
        "pit_lap": False, "traffic_compromised": True, "race_control_compromised": False,
        "damage_compromised": False,
    })
    assert not q["eligible"]
    assert "traffic_compromised" in q["reasons"]
