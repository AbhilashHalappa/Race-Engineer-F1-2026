from src.performance_hub_ui import performance_hub_page_html


def test_corner_detail_uses_full_width_and_expected_wide_layout():
    html = performance_hub_page_html()
    assert '#cornerDetailed{max-width:none;width:100%}' in html
    assert '.metricProgressGrid{width:100%;grid-template-columns:repeat(3,minmax(0,1fr))}' in html
    assert '.phaseGrid{width:100%;grid-template-columns:repeat(3,minmax(0,1fr))}' in html
    assert '.refMetricGrid{width:100%;grid-template-columns:repeat(3,minmax(0,1fr))}' in html


def test_corner_table_has_explicit_visible_synced_horizontal_scrollbar():
    html = performance_hub_page_html()
    assert 'id=cornerTable class=cornerTable' in html
    assert 'function syncCornerTableScroll()' in html
    assert ('id=cornerTableHScroll class=cornerTableHScroll' in html or 'id=cornerTableScrollRange class=cornerTableScrollRange type=range' in html or 'id=cornerTableHScroll class=cornerTableHScroll' in html)
    assert "box.onscroll=()=>" in html
    assert "window.addEventListener('resize',()=>requestAnimationFrame(syncCornerTableScroll))" in html


def test_narrow_corner_layout_still_collapses_responsively():
    html = performance_hub_page_html()
    assert '@media(max-width:1250px)' in html
    assert '.phaseGrid{grid-template-columns:1fr}' in html
    assert '@media(max-width:600px)' in html
    assert '.phaseCard .metricGrid,.refMetricGrid,.metricProgressGrid{grid-template-columns:1fr}' in html
