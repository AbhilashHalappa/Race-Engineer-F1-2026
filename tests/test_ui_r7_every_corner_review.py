from src.performance_hub_ui import performance_hub_page_html


def test_r7_corner_review_has_sticky_sortable_table_and_column_chooser():
    html = performance_hub_page_html()
    assert 'cornerColumnChooser' in html
    assert 'cornerColumnMenu' in html
    for key in ('corner','score','time','speed','brake','throttle'):
        assert f'data-sort="{key}"' in html
    assert 'position:sticky;top:0;z-index:5' in html
    assert "localStorage.setItem('race.corner.sort'" in html
    assert "localStorage.setItem('race.corner.columns'" in html


def test_r7_heat_tint_is_cell_scoped_and_selection_is_explicit():
    html = performance_hub_page_html()
    assert '.cornerTable .heatCell.heatGood' in html
    assert '.cornerTable .heatCell.heatBad' in html
    assert '.cornerTable tbody tr.selectedCorner' in html
    assert 'data-col="line"' in html
    assert 'data-col="evidence"' in html


def test_r7_wide_split_and_narrow_stack_preserve_reference_group():
    html = performance_hub_page_html()
    assert 'cornerReviewLayout' in html
    assert 'grid-template-columns:minmax(0,1.55fr) minmax(430px,.85fr)' in html
    assert '@media(max-width:1500px){.cornerReviewLayout{grid-template-columns:1fr}' in html
    assert 'SELECTED ANALYSIS REFERENCE' in html
    assert 'refCompare' in html


def test_r7_existing_horizontal_scroll_controls_remain():
    html = performance_hub_page_html()
    for token in ('cornerTableHScroll','cornerScrollLeft','cornerScrollRight','syncCornerTableScroll'):
        assert token in html
