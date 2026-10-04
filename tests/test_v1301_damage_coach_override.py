from types import SimpleNamespace

from src.corner_coach import CornerCoachEngine
from src.data_quality import lap_quality, live_context_blockers
from src.measured_performance import MeasuredPerformanceRecorder


def _lap(**extra):
    row={
        "lap": 1, "valid": True, "lap_time_s": 80.0,
        "lap_start_anchored": True, "sample_count": 120,
        "damage_compromised": True,
    }
    row.update(extra)
    return row


def test_damage_lap_rejected_by_default():
    q=lap_quality(_lap())
    assert not q["eligible"]
    assert "damage_compromised" in q["reasons"]


def test_damage_coach_override_keeps_damage_fact_but_allows_quality():
    q=lap_quality(_lap(damage_coaching_override=True))
    assert q["eligible"]
    assert "damage_compromised" not in q["reasons"]
    assert "damage_coaching_override" in q["warnings"]


def test_damage_override_does_not_bypass_other_quality_failures():
    q=lap_quality(_lap(damage_coaching_override=True, traffic_compromised=True))
    assert not q["eligible"]
    assert "traffic_compromised" in q["reasons"]
    assert "damage_compromised" not in q["reasons"]


def test_corner_coach_damage_switch_is_independent_and_default_off():
    c=CornerCoachEngine()
    assert c.damage_coaching_enabled is False
    ok,_=c.set_feature("DMGCOACH", True)
    assert ok and c.damage_coaching_enabled
    states=c.feature_states()
    assert c.damage_coaching_enabled is True
    assert states["CCPRE"] is True
    assert states["CCPOST"] is True
    assert states["GAINLOSS"] is True


def test_recorder_preserves_override_across_session_reset():
    r=MeasuredPerformanceRecorder()
    r.allow_damage_coaching=True
    r.reset()
    assert r.allow_damage_coaching is True


def test_live_damage_blocker_obeys_override_only_for_damage():
    damage=SimpleNamespace(front_left_wing_percent=25, front_right_wing_percent=0, floor_percent=0, engine_blown=False, engine_seized=False)
    player=SimpleNamespace(damage=damage, lap=None, updated={})
    state=SimpleNamespace(session=SimpleNamespace(paused=False, safety_car=None, marshal_zones=()), player=player, gap_behind_s=None)
    assert "significant_damage" in live_context_blockers(state, race_mode=False)
    assert "significant_damage" not in live_context_blockers(state, race_mode=False, allow_damage_coaching=True)
