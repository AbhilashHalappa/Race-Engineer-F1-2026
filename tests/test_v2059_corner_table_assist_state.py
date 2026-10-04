from types import SimpleNamespace

from src.performance_hub_ui import performance_hub_page_html
from src.race_state_receiver import RaceStateReceiver


def test_autosave_waits_for_corner_accumulator_before_consuming_lap_edge():
    receiver=RaceStateReceiver.__new__(RaceStateReceiver)
    receiver._telemetry_mode='live'
    receiver._history_autosave_completed_count=0
    receiver._history_autosave_game_lap_count=0
    receiver.engine=SimpleNamespace(
        performance=SimpleNamespace(completed=[{'lap':10,'lap_time_s':77.711,'valid':True}]),
        state=SimpleNamespace(player=SimpleNamespace(lap=SimpleNamespace(current_lap=11))),
    )
    receiver.corner_coach=SimpleNamespace(enabled=True,_v202_accumulator=SimpleNamespace(completed=[]))

    receiver._queue_live_history_autosave_locked()

    # The completion edge must remain unconsumed so the next packet can retry
    # after CORNER COACH finalizes lap 10.
    assert receiver._history_autosave_completed_count == 0
    assert receiver._history_autosave_game_lap_count == 0


def test_corner_table_uses_same_effective_corner_sources_as_map():
    html=performance_hub_page_html()
    assert 'function effectiveReviewCorners()' in html
    assert 'selected_reference_only' in html
    assert "let rows=effectiveReviewCorners();$('cornerRows')" in html
    assert "rows=effectiveReviewCorners();if(!pts.length)" in html
    assert 'effectiveReviewCorners().find' in html


def test_assist_icons_are_green_when_used_and_gray_when_not_used():
    html=performance_hub_page_html()
    # No amber/cyan semantic classes are assigned by the icon renderer now;
    # active assists are green (`on`) and inactive/unknown assists gray (`off`).
    start=html.index('function assistIcons')
    end=html.index('function renderGameSummary', start)
    fn=html[start:end]
    assert "used=v==1||v==2" in fn
    assert "used=Boolean(Number(v))" in fn
    assert "${used?'on':'off'}" in fn
    assert "?'mid'" not in fn
    assert "?'auto'" not in fn
