from types import SimpleNamespace

import src.post_corner_coach as pc
from src.post_corner_coach import PostCornerCoach, PostCornerCoachConfig


class FakeRecorder:
    def __init__(self, reference, profile="time_trial"):
        self.event_context = {"profile": profile}
        self.current_lap_started_clean = True
        self._reference = reference

    def current_reference_lap(self):
        return self._reference

    def current_lap_snapshot(self, _state):
        return {"lap": 2, "sections": [], "_samples": {}}


class FakeAnalysis:
    reference_corner_id = 1

    def __init__(self, code="minimum_speed_low", cost=.16, conf=.95, actionability=.9, magnitude=-10):
        self._dict = {
            "corner_id": 1,
            "reference_corner_id": 1,
            "coaching_eligible": True,
            "diagnosis": code,
            "diagnosis_label": "Minimum speed too low",
            "estimated_time_cost_s": cost,
            "diagnosis_confidence": conf,
            "actionability": actionability,
            "issue_candidates": [{
                "code": code,
                "magnitude": magnitude,
                "primary_eligible": True,
            }],
        }

    def to_dict(self):
        return dict(self._dict)


def state(lap=2, distance=560.0, speed=220.0, throttle=.95, brake=0.0, steering=.01):
    return SimpleNamespace(
        player=SimpleNamespace(
            lap=SimpleNamespace(current_lap=lap, lap_distance_m=distance),
            telemetry=SimpleNamespace(speed_kph=speed, throttle=throttle, brake=brake, steering=steering),
        ),
        session=SimpleNamespace(session_time_s=123.0),
    )


def reference():
    return {
        "sections": [
            {"id": 1, "start_m": 300.0, "end_m": 500.0},
            {"id": 2, "start_m": 1200.0, "end_m": 1400.0},
        ],
        "_samples": {0.0: {}, 4300.0: {}},
    }


def test_post_corner_call_waits_for_safe_straight(monkeypatch):
    monkeypatch.setattr(pc, "build_corner_analyses", lambda *_: [FakeAnalysis()])
    coach = PostCornerCoach(PostCornerCoachConfig(analysis_margin_m=35.0))
    rec = FakeRecorder(reference())

    # Corner is analysable, but steering workload is still too high: hold it.
    assert coach.observe(rec, state(distance=550.0, steering=.35), 10.0) == []
    assert coach.status()["pending"]["corner_id"] == 1

    # Once the car is settled and the next braking zone is >3.5 s away, speak.
    out = coach.observe(rec, state(distance=600.0, steering=.02), 10.3)
    assert len(out) == 1
    assert out[0].key.startswith("coach:corner:1:")
    assert out[0].text == "Turn 1: carry about 10 kph more minimum speed."
    assert coach.status()["pending"] is None
    assert coach.status()["spoken_count"] == 1


def test_pending_call_is_dropped_when_next_braking_zone_becomes_imminent(monkeypatch):
    monkeypatch.setattr(pc, "build_corner_analyses", lambda *_: [FakeAnalysis()])
    coach = PostCornerCoach()
    rec = FakeRecorder(reference())
    assert coach.observe(rec, state(distance=550.0, steering=.30), 20.0) == []
    # At 1100 m and 240 km/h there is ~1.5 s to the next 1200 m braking point.
    assert coach.observe(rec, state(distance=1100.0, speed=240.0, steering=.20), 21.0) == []
    assert coach.status()["pending"] is None
    assert coach.status()["dropped_unsafe_count"] == 1


def test_race_profile_does_not_generate_performance_coaching(monkeypatch):
    monkeypatch.setattr(pc, "build_corner_analyses", lambda *_: [FakeAnalysis()])
    coach = PostCornerCoach()
    rec = FakeRecorder(reference(), profile="race")
    assert coach.observe(rec, state(distance=600.0), 30.0) == []
    assert coach.status()["generated_count"] == 0


def test_same_corner_issue_is_suppressed_for_cooldown_lap(monkeypatch):
    monkeypatch.setattr(pc, "build_corner_analyses", lambda *_: [FakeAnalysis()])
    coach = PostCornerCoach(PostCornerCoachConfig(same_issue_cooldown_laps=2))
    rec = FakeRecorder(reference())
    assert len(coach.observe(rec, state(lap=2, distance=600.0), 40.0)) == 1
    # New lap: same issue in same corner is measured again but lap delta is only 1.
    assert coach.observe(rec, state(lap=3, distance=600.0), 50.0) == []
    assert coach.status()["suppressed_cooldown_count"] == 1


def test_low_priority_issue_is_not_queued(monkeypatch):
    monkeypatch.setattr(pc, "build_corner_analyses", lambda *_: [FakeAnalysis(cost=.03, conf=.7, actionability=.7)])
    coach = PostCornerCoach(PostCornerCoachConfig(min_priority_score=.06))
    rec = FakeRecorder(reference())
    assert coach.observe(rec, state(distance=600.0), 60.0) == []
    assert coach.status()["pending"] is None
    assert coach.status()["suppressed_priority_count"] == 1
