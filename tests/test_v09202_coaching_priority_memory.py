from src.coaching_priority import CoachingMemory, build_session_coaching


def issue(code="brake_early", label="Braking too early", phase="ENTRY", cost=.12, conf=.9, act=1.0, mag=-12.0, severity=.8):
    return {
        "code": code,
        "label": label,
        "phase": phase,
        "estimated_time_cost_s": cost,
        "confidence": conf,
        "actionability": act,
        "magnitude": mag,
        "severity": severity,
        "primary_eligible": True,
    }


def corner(cid, *issues, eligible=True):
    return {
        "corner_id": cid,
        "coaching_eligible": eligible,
        "issue_candidates": list(issues),
    }


def test_priority_uses_time_confidence_actionability_and_repeat_factor():
    m = CoachingMemory()
    first = m.ingest_lap(2, [corner(3, issue(cost=.10, conf=.8, act=.9))])
    a = first["selected_focus"]
    assert round(a["priority_score"], 6) == round(.10 * .8 * .9 * 1.0, 6)
    second = m.ingest_lap(3, [corner(3, issue(cost=.10, conf=.8, act=.9))])
    b = second["selected_focus"]
    assert b["repeat_count"] == 2
    assert b["repeat_factor"] > 1.0
    assert b["priority_score"] > a["priority_score"]


def test_only_one_focus_is_selected_per_lap():
    m = CoachingMemory()
    out = m.ingest_lap(4, [
        corner(1, issue(cost=.08)),
        corner(2, issue(code="exit_speed_low", label="Exit speed too low", phase="EXIT", cost=.20, conf=.9, act=.9, mag=-12)),
    ])
    selected = [x for x in out["ranked_candidates"] if x["selected_focus"]]
    assert len(selected) == 1
    assert selected[0]["corner_id"] == 2
    assert out["candidate_count"] == 2


def test_noneligible_and_supporting_only_candidates_do_not_enter_priority():
    supporting = issue(code="apex_early", label="Apex too early", phase="MID", cost=.2)
    supporting["primary_eligible"] = False
    m = CoachingMemory()
    out = m.ingest_lap(2, [corner(1, supporting), corner(2, issue(), eligible=False)])
    assert out["candidate_count"] == 0
    assert out["selected_focus"] is None
    assert m.report()["pattern_count"] == 0


def test_pattern_memory_tracks_persistence_and_improvement():
    m = CoachingMemory()
    m.ingest_lap(2, [corner(6, issue(cost=.20))])
    m.ingest_lap(3, [corner(6, issue(cost=.16))])
    report = m.report()
    p = report["patterns"][0]
    assert p["repeat_count"] == 2
    assert p["opportunities"] == 2
    assert p["persistence"] == 1.0
    assert p["trend"] == "improving"
    assert round(p["trend_delta_s"], 3) == -.04
    assert report["recurring_pattern_count"] == 1


def test_pattern_memory_tracks_regression_and_stable_deadband():
    m = CoachingMemory()
    m.ingest_lap(2, [corner(6, issue(cost=.10))])
    m.ingest_lap(3, [corner(6, issue(cost=.13))])
    assert m.report()["patterns"][0]["trend"] == "regressing"

    m2 = CoachingMemory()
    m2.ingest_lap(2, [corner(6, issue(cost=.100))])
    m2.ingest_lap(3, [corner(6, issue(cost=.109))])
    assert m2.report()["patterns"][0]["trend"] == "stable"


def test_build_session_coaching_promotes_recurring_pattern_and_keeps_lap_history():
    comps = [
        {"lap": 4, "corner_analyses": [corner(3, issue(code="minimum_speed_low", label="Minimum speed too low", phase="MID", cost=.18, conf=.95, act=.9, mag=-10))]},
        {"lap": 5, "corner_analyses": [corner(3, issue(code="minimum_speed_low", label="Minimum speed too low", phase="MID", cost=.14, conf=.96, act=.9, mag=-8))]},
    ]
    out = build_session_coaching(comps)
    assert out["version"] == "0.9.20.2"
    assert len(out["per_lap_priority"]) == 2
    mem = out["memory"]
    assert mem["recurring_pattern_count"] == 1
    assert mem["session_focus"]["corner_id"] == 3
    assert mem["session_focus"]["issue_code"] == "minimum_speed_low"
    assert len(mem["lap_focus_history"]) == 2


def test_issue_absence_on_later_measured_corner_reduces_persistence_and_moves_focus():
    m = CoachingMemory()
    m.ingest_lap(2, [corner(3, issue(cost=.20)), corner(4, issue(code="exit_speed_low", label="Exit speed too low", phase="EXIT", cost=.10, act=.9, mag=-8))])
    # Corner 3 is measured again but its old issue no longer survives diagnosis;
    # corner 4 continues to show its issue.
    m.ingest_lap(3, [corner(3, eligible=False), corner(4, issue(code="exit_speed_low", label="Exit speed too low", phase="EXIT", cost=.09, act=.9, mag=-7))])
    report = m.report()
    old = next(x for x in report["patterns"] if x["corner_id"] == 3)
    assert old["opportunities"] == 2
    assert old["repeat_count"] == 1
    assert old["persistence"] == 0.5
    assert old["latest_observed"] is False
    assert old["trend"] == "improving"
    assert report["session_focus"]["corner_id"] == 4
