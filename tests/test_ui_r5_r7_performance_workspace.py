from src.performance_hub_ui import performance_hub_page_html


def test_performance_hub_keeps_explicit_track_session_hierarchy():
    html = performance_hub_page_html()
    assert 'TRACK PERFORMANCE' in html
    assert 'Select a circuit to view its trend and stored sessions.' in html
    assert 'SESSION HISTORY' in html
    assert 'Open a session for lap, telemetry and corner analysis.' in html
    assert 'id=trackRows' in html
    assert 'id=sessionRows' in html


def test_performance_hub_does_not_force_workspace_default_before_selection():
    html = performance_hub_page_html()
    assert 'id=workspaceNav' not in html
    assert 'function setWorkspace(mode)' not in html
    assert 'class=sessionContext' not in html


def test_session_review_still_contains_existing_review_tabs():
    html = performance_hub_page_html()
    for token in ('OVERVIEW', 'CORNERS', 'TELEMETRY'):
        assert token in html
    assert 'id=tab-overview' in html
    assert 'id=tab-corners' in html
    assert 'id=tab-telemetry' in html


def test_existing_corner_review_features_are_preserved():
    html = performance_hub_page_html()
    assert 'EVERY CORNER · PERFORMANCE TABLE' in html
    assert 'SELECTED ANALYSIS REFERENCE' in html
    assert 'cornerTableHScroll' in html
    assert 'RACING-LINE DEVIATION' in html
