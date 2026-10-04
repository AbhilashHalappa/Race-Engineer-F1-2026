from src.performance_hub_ui import performance_hub_page_html


def test_corner_table_has_explicit_horizontal_scroll_and_wide_table():
    html = performance_hub_page_html()
    assert '.cornerTable{overflow-x:scroll' in html
    assert '.cornerTable table{min-width:1120px}' in html
    assert '.cornerTable::-webkit-scrollbar{height:12px' in html


def test_corner_detail_uses_three_phase_columns_and_two_row_reference_layout():
    html = performance_hub_page_html()
    assert '.phaseGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))' in html
    assert '.refMetricGrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr))' in html
    assert '<div class=refHeading>SELECTED ANALYSIS REFERENCE</div>' in html
    assert '<div class=refMetricGrid>' in html
    assert '.metricProgressGrid{grid-template-columns:repeat(3,minmax(0,1fr))' in html


def test_corner_detail_headings_have_distinct_semantic_colors():
    html = performance_hub_page_html()
    assert '.phaseCard:nth-child(1) h3{color:var(--amber)}' in html
    assert '.phaseCard:nth-child(2) h3{color:var(--cyan)}' in html
    assert '.phaseCard:nth-child(3) h3{color:var(--green)}' in html
    assert '.refCompare .refHeading{color:var(--blue)' in html


def test_control_center_launcher_reflow_is_more_compact():
    from pathlib import Path
    src = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'columns=6 if width >= 1250 else 5 if width >= 900 else 4 if width >= 700 else 3 if width >= 520 else 2' in src
    assert 'button.setMinimumHeight(30)' in src
