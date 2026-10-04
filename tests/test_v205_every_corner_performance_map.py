from src.performance_hub_ui import performance_hub_page_html


def test_v205_review_map_has_all_heat_modes_and_corner_cards():
    html=performance_hub_page_html()
    assert 'EVERY-CORNER PERFORMANCE MAP' in html
    for token in (
        'SCORE','TIME LOSS / GAIN','SPEED DEFICIT','BRAKING DELTA',
        'THROTTLE DELTA','RACING-LINE DEVIATION',
    ):
        assert token in html
    assert 'renderPerformanceMap()' in html
    assert 'cornerStrip' not in html
    assert 'dominant_issue_label' in html
    assert 'total_measured_time_loss_s' in html
    assert "heatMode==='score'" in html
    assert "heatMode==='line'" in html


def test_v205_map_does_not_invent_missing_racing_line_evidence():
    html=performance_hub_page_html()
    assert "No trusted per-corner path evidence" in html
    assert "Grey = path evidence unavailable" in html
    # Racing-line mode consumes persisted geometry evidence only.
    assert 'mean_path_deviation_m' in html
