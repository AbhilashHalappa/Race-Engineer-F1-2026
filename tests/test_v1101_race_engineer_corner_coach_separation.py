from types import SimpleNamespace as NS

from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, PhysicalCorner, ReferenceTrace
from src.engineer.models import EngineerMessage, Priority
from src.race_state_receiver import RaceStateReceiver
from src.tts import SpeechOutput, TTSConfig


def _state(distance=250.0, lap=2, speed=150.0, lap_time=5.0):
    return NS(
        player=NS(
            lap=NS(current_lap=lap, lap_distance_m=distance, current_lap_time_s=lap_time),
            telemetry=NS(speed_kph=speed, brake=0.0, throttle=1.0, steering=0.0, gear=5),
        ),
        session=NS(track=NS(name="TEST_TRACK"), session_time_s=50.0),
    )


def _model():
    zone = CoachingZone("Z1", 100.0, 200.0, 70.0, (1,), brake_start_m=80.0, apex_m=150.0, label="T1")
    return ReferenceTrace(
        "TEST_TRACK", 1000.0, 25.0, 5.0,
        (
            {"d": 0.0, "t": 0.0, "speed": 200.0, "brake": 0.0, "throttle": 1.0, "steering": 0.0, "gear": 5},
            {"d": 1000.0, "t": 25.0, "speed": 200.0, "brake": 0.0, "throttle": 1.0, "steering": 0.0, "gear": 5},
        ),
        (PhysicalCorner(1, "T1", 100.0, 150.0, 200.0),), (), (zone,), {}, {},
    )


def test_corner_radio_is_independent_from_engineer_master_classification():
    corner = EngineerMessage("corner:post:2:Z1:measured_loss", Priority.COACHING, "T1 lost time.", 1.0)
    race = EngineerMessage("incident:collision:1", Priority.CRITICAL, "Collision.", 1.0)
    assert SpeechOutput._is_automatic_engineer_message(corner) is False
    assert SpeechOutput._is_automatic_engineer_message(race) is True


def test_corner_post_gate_blocks_queued_family_without_disabling_pre():
    speech = SpeechOutput(TTSConfig(enabled=False))
    post = EngineerMessage("corner:post:2:Z1:measured_loss", Priority.COACHING, "post", 1.0)
    pre = EngineerMessage("corner:pre:2:Z2", Priority.COACHING, "pre", 1.0)
    speech.set_message_prefix_enabled("corner:", True)
    speech.set_message_prefix_enabled("corner:pre:", True)
    speech.set_message_prefix_enabled("corner:post:", False)
    assert speech._message_family_enabled(pre) is True
    assert speech._message_family_enabled(post) is False


def test_corner_transcript_is_separate_from_race_radio_transcript():
    receiver = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    receiver._record_radio_transcript(EngineerMessage("corner:pre:2:Z1", Priority.COACHING, "T1 coming up.", 1.0))
    receiver._record_radio_transcript(EngineerMessage("track_limits", Priority.CRITICAL, "Track limits.", 1.0))
    assert [x.text for x in receiver.corner_transcript.snapshot()] == ["T1 coming up."]
    assert [x.text for x in receiver.radio_transcript.snapshot()] == ["Track limits."]


def test_post_off_stops_corner_post_generation(monkeypatch):
    engine = CornerCoachEngine()
    model = _model()
    monkeypatch.setattr(engine, "_ensure_reference", lambda *a, **k: (setattr(engine, "reference_model", model) or model))
    monkeypatch.setattr("src.corner_coach.build_distance_performance_model", lambda *a, **k: {
        "available": True,
        "points": [{"distance_m": 0.0, "delta_s": 0.0}, {"distance_m": 1000.0, "delta_s": 0.2}],
        "turns": [],
    })
    reference = {"_samples": {0.0: {"d": 0.0, "t": 0.0}, 1000.0: {"d": 1000.0, "t": 25.0}}}
    current = {"_samples": {0.0: {"d": 0.0, "t": 0.0}, 1000.0: {"d": 1000.0, "t": 25.2}}}
    recorder = NS(current_reference_lap=lambda: reference, current_lap_snapshot=lambda state: current,
                  reference_mode="external", external_reference_meta={})
    engine.set_feature("POST", False)
    messages = engine.observe(recorder, _state(distance=220.0), 1.0)
    assert not any(m.key.startswith("corner:post:") for m in messages)


def test_corner_coach_packet_path_never_rebuilds_full_distance_model(monkeypatch):
    engine = CornerCoachEngine()
    model = _model()
    engine._reference_samples = tuple(model.samples)
    engine._reference_distances = tuple(float(x["d"]) for x in model.samples)
    monkeypatch.setattr(engine, "_ensure_reference", lambda *a, **k: (setattr(engine, "reference_model", model) or model))
    calls = {"count": 0}
    def build(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("whole-lap builder must not run in the packet-critical path")
    monkeypatch.setattr("src.corner_coach.build_distance_performance_model", build)
    reference = {"_samples": {0.0: {"d": 0.0, "t": 0.0}, 1000.0: {"d": 1000.0, "t": 25.0}}}
    recorder = NS(current_reference_lap=lambda: reference, current_lap_snapshot=lambda state: None,
                  reference_mode="external", external_reference_meta={})
    engine.observe(recorder, _state(distance=10.0, lap_time=0.25), 1.00)
    engine.observe(recorder, _state(distance=12.0, lap_time=0.30), 1.03)
    engine.observe(recorder, _state(distance=14.0, lap_time=0.35), 1.06)
    engine.observe(recorder, _state(distance=19.0, lap_time=0.47), 1.07)
    assert calls["count"] == 0
    assert len(engine._live_points) >= 2


def test_control_center_has_separate_race_engineer_and_corner_coach_sections():
    source = open("src/overlay/window.py", encoding="utf-8").read()
    control = source.split("class ControlCenterWindow", 1)[1].split("class DriverOverlayWindow", 1)[0]
    assert 'self.label("RACE ENGINEER"' in control
    assert 'self.label("CORNER COACH"' in control
    assert '("CCPOST","POST","CORNER COACH POST calls")' in control
    assert 'for name, text, tip in (("ENGR", "ENGR", "Automatic Race Engineer radio")' in control
    assert 'class CornerCoachTranscriptPanel' in source
