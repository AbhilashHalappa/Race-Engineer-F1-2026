from src.performance_hub_ui import performance_hub_page_html


def test_v2052_groups_related_performance_hub_data():
    html = performance_hub_page_html()
    assert 'class=telemetryWorkspace' in html
    assert 'class=cornerWorkspace' in html
    assert 'SELECTED CORNER' in html
    assert 'EVERY CORNER · PERFORMANCE TABLE' in html


def test_v2052_uses_progressive_disclosure_for_reference_and_legend_help():
    html = performance_hub_page_html()
    assert 'class=referenceHelp' in html
    assert 'HOW REFERENCE COMPARISON WORKS' in html
    assert 'class=legendDetails' in html
    assert 'COLOR KEY · EVIDENCE' in html


def test_v2052_quick_glance_laps_are_clickable_and_responsive():
    html = performance_hub_page_html()
    assert 'data-quick-lap' in html
    assert "querySelectorAll('tr[data-quick-lap]')" in html
    assert 'selectedQuickLap' in html
    assert '@media(max-width:1250px)' in html


def test_review_selectors_auto_refresh_with_latest_request_wins():
    html = performance_hub_page_html()
    assert "$('reviewRef').addEventListener('input'" in html
    assert "$('reviewRef').addEventListener('change'" in html
    assert "$('reviewLap').addEventListener('input'" in html
    assert "$('reviewLap').addEventListener('change'" in html
    assert 'reviewRequestSeq' in html
    assert 'new AbortController()' in html
    assert "+'&_='+Date.now()" in html
