from src.performance_hub_ui import performance_hub_page_html


def test_v2051_corner_map_matches_telemetry_map_geometry_and_has_no_duplicate_cards():
    html = performance_hub_page_html()
    assert 'class="mapBox performanceMap"' in html
    assert 'W=700,H=350' in html
    assert 'stroke-width="6"' in html
    assert 'cornerStrip' not in html
    assert 'cornerChip' not in html


def test_v2051_every_corner_table_contains_all_review_metrics_and_colour_coding():
    html = performance_hub_page_html()
    for token in (
        'Time loss/gain', 'Speed deficit', 'Braking delta',
        'Throttle delta', 'Racing-line dev.', 'heatCell', 'metricColor',
    ):
        assert token in html
    assert "heatCornerDataFor(c,'score')" in html
    assert "heatCornerDataFor(c,'line')" in html


def test_v2051_selected_corner_has_six_progress_bars():
    html = performance_hub_page_html()
    assert 'metricProgressGrid' in html
    assert 'cornerProgressBars(c)' in html
    assert "['score','time','speed','brake','throttle','line']" in html
    assert 'TIME LOSS / GAIN' in html
    assert 'RACING-LINE DEVIATION' in html
