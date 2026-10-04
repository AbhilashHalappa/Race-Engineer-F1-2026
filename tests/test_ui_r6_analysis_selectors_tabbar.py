from src.performance_hub_ui import performance_hub_page_html


def test_lap_and_reference_selectors_live_beside_review_tabs():
    html = performance_hub_page_html()
    assert 'class=reviewTabBar' in html
    bar = html.split('class=reviewTabBar', 1)[1].split('</div></div>', 1)[0]
    assert 'data-tab=overview' in bar
    assert 'data-tab=telemetry' in bar
    assert 'data-tab=corners' in bar
    assert 'id=reviewLap' in bar
    assert 'id=reviewRef' in bar
    # Selectors must no longer be in the session header controls.
    head = html.split('class=review-head', 1)[1].split('</div></div>', 1)[0]
    assert 'id=reviewLap' not in head
    assert 'id=reviewRef' not in head
