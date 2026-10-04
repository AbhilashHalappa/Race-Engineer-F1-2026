from pathlib import Path
from src.practice_hub_ui import practice_hub_page_html


def test_practice_workspace_is_track_scoped_and_separate():
    html = practice_hub_page_html()
    assert 'TRACK PRACTICE' in html
    assert 'All stored live sessions for this driver on this track' in html
    assert '/api/practice/track' in html
    assert 'OLDER WEAKNESSES NO LONGER CURRENT' in html


def test_control_center_has_separate_practice_tab_after_performance_hub():
    src = (Path(__file__).parents[1] / 'src' / 'overlay' / 'window.py').read_text()
    perf = src.index('self.tabs.addTab(self.performance_page, "PERFORMANCE HUB")')
    prac = src.index('self.tabs.addTab(self.practice_page, "PRACTICE")')
    server = src.index('self.tabs.addTab(self.server_page, "SERVER")')
    assert perf < prac < server


def test_protected_scoring_and_coaching_core_unchanged_from_520():
    # Stable V2 portable audit uses the V2 source-freeze manifest rather than
    # requiring an unpacked V2.9.1.3.5.20 sibling tree.
    root = Path(__file__).parents[1]
    from src.v2_final_validation import verify_source_freeze
    result = verify_source_freeze(root)
    assert result["ok"] is True
    protected = {item["path"] for item in result["files"]}
    for name in [
        'performance_scoring.py', 'data_quality.py', 'performance_review.py',
        'corner_coach.py', 'coaching_priority.py', 'lap_stint_intelligence.py',
        'race_state_receiver.py',
    ]:
        assert f"src/{name}" in protected
