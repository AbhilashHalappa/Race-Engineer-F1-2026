from src.lap_stint_intelligence import LivePerformanceAccumulator


def corner(cid, score, loss, issue='match', **dims):
    return {
        'corner_id': cid, 'score': score, 'score_status': 'available', 'confidence': .9,
        'estimated_loss_s': loss, 'dominant_issue': issue, 'primary_text': issue,
        'dimension_scores': dims,
    }


def test_lap_score_requires_coverage_and_multiple_corners():
    a=LivePerformanceAccumulator(); a.begin_lap(1)
    a.add_corner(corner(1,80,.1)); a.add_corner(corner(2,90,.0)); a.add_corner(corner(3,70,.2))
    r=a.finalize_lap(lap_number=1,eligible_corner_count=4,lap_valid=True)
    assert r['status']=='available'
    assert r['lap_score']==80.0
    assert r['coverage']==.75


def test_insufficient_coverage_stays_na():
    a=LivePerformanceAccumulator(); a.begin_lap(1)
    a.add_corner(corner(1,80,.1))
    r=a.finalize_lap(lap_number=1,eligible_corner_count=4,lap_valid=True)
    assert r['status']=='n/a' and r['lap_score'] is None


def test_biggest_loss_and_next_focus_are_time_cost_first():
    a=LivePerformanceAccumulator(); a.begin_lap(1)
    a.add_corner(corner(1,95,.25,'brake_early'))
    a.add_corner(corner(2,60,.08,'throttle_late'))
    r=a.finalize_lap(lap_number=1,eligible_corner_count=2,lap_valid=True)
    assert r['biggest_loss']['corner_id']==1
    assert r['next_lap_focus']['corner_id']==1


def test_best_improvement_compares_same_corner_previous_lap():
    a=LivePerformanceAccumulator(); a.begin_lap(1)
    a.add_corner(corner(1,70,.30,'brake_early')); a.add_corner(corner(2,80,.10))
    a.finalize_lap(lap_number=1,eligible_corner_count=2)
    a.begin_lap(2)
    a.add_corner(corner(1,85,.10,'brake_early')); a.add_corner(corner(2,82,.08))
    r=a.finalize_lap(lap_number=2,eligible_corner_count=2)
    assert r['best_improvement']=={'corner_id':1,'recovered_s':.2}


def test_repeated_issue_needs_two_observations():
    a=LivePerformanceAccumulator(); a.begin_lap(1)
    a.add_corner(corner(1,70,.1,'brake_early')); a.add_corner(corner(2,72,.12,'brake_early'))
    r=a.finalize_lap(lap_number=1,eligible_corner_count=2)
    assert r['repeated_issue']=={'issue':'brake_early','count':2}


def test_provisional_groups_need_three_samples():
    a=LivePerformanceAccumulator(); a.begin_lap(1)
    a.add_corner(corner(1,80,.1, braking_point=80)); a.add_corner(corner(2,82,.1, braking_point=82))
    r1=a.finalize_lap(lap_number=1,eligible_corner_count=2)
    assert r1['provisional_scores']['braking'] is None
    a.begin_lap(2); a.add_corner(corner(1,84,.08, braking_point=84)); a.add_corner(corner(2,86,.05, braking_point=86))
    r2=a.finalize_lap(lap_number=2,eligible_corner_count=2)
    assert r2['provisional_scores']['braking']==83.0


def test_invalid_lap_never_gets_lap_score():
    a=LivePerformanceAccumulator(); a.begin_lap(1)
    a.add_corner(corner(1,90,.0)); a.add_corner(corner(2,90,.0))
    r=a.finalize_lap(lap_number=1,eligible_corner_count=2,lap_valid=False)
    assert r['status']=='n/a' and r['lap_score'] is None


def test_overlay_snapshot_lap_intelligence_uses_defined_session_clock():
    from types import SimpleNamespace
    from src.overlay.data import build_overlay_snapshot

    state = SimpleNamespace(
        player=None,
        session=SimpleNamespace(session_time_s=10.0, track=None, track_length_m=5000.0),
        extended={"corner_coach": {"last_lap_intelligence": {"expires_session_s": 20.0, "lap_number": 2}}},
        player_index=None,
    )
    performance = SimpleNamespace(
        event_context={}, completed=[], samples={}, current_lap_started_clean=False
    )
    snapshot = build_overlay_snapshot(state, performance, connected=True, now=0.0)
    assert snapshot.last_lap_intelligence["lap_number"] == 2


def test_overlay_snapshot_keeps_latest_lap_intelligence_visible():
    from types import SimpleNamespace
    from src.overlay.data import build_overlay_snapshot

    state = SimpleNamespace(
        player=None,
        session=SimpleNamespace(session_time_s=21.0, track=None, track_length_m=5000.0),
        extended={"corner_coach": {"last_lap_intelligence": {"expires_session_s": 20.0, "lap_number": 2}}},
        player_index=None,
    )
    performance = SimpleNamespace(
        event_context={}, completed=[], samples={}, current_lap_started_clean=False
    )
    snapshot = build_overlay_snapshot(state, performance, connected=True, now=0.0)
    assert snapshot.last_lap_intelligence["lap_number"] == 2


def test_lap_summary_has_dedicated_performance_coach_panel_and_is_not_gated_by_live_corner():
    from pathlib import Path
    text=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "class LapStintSummaryPanel" in text
    layout=text[text.index("body=QHBoxLayout();body.setSpacing(6)"):text.index("# Legacy regression marker",text.index("body=QHBoxLayout();body.setSpacing(6)"))]
    assert "self.lap_summary_panel=LapStintSummaryPanel()" in layout
    assert "right.addWidget(self.lap_summary_panel" in layout
    driver=text[text.index("class CornerCoachDriverPanel"):text.index("class LiveCornerFeedbackOverlayWindow")]
    assert "last_lap_intelligence" not in driver
    assert "live_corner_result" not in driver


def test_lap_summary_remains_visible_past_old_eight_second_expiry():
    from types import SimpleNamespace
    from src.overlay.data import build_overlay_snapshot
    state=SimpleNamespace(
        player=None,
        session=SimpleNamespace(session_time_s=99.0,track=None,track_length_m=5000.0),
        extended={"corner_coach":{"last_lap_intelligence":{"expires_session_s":20.0,"lap_number":2}}},
        player_index=None,
    )
    performance=SimpleNamespace(event_context={},completed=[],samples={},current_lap_started_clean=False)
    snapshot=build_overlay_snapshot(state,performance,connected=True,now=0.0)
    assert snapshot.last_lap_intelligence["lap_number"]==2
