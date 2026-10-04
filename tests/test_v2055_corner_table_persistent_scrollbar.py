from src.performance_hub_ui import performance_hub_page_html


def test_corner_table_has_persistent_visible_range_scroll_control():
    html = performance_hub_page_html()
    assert 'id=cornerTableScrollControl class=cornerTableScrollControl' in html
    assert ('id=cornerTableScrollRange class=cornerTableScrollRange type=range' in html or 'id=cornerTableHScroll class=cornerTableHScroll' in html)
    assert 'id=cornerTableScrollValue class=cornerTableScrollValue' in html
    assert "box.scrollWidth-box.clientWidth" in html
    assert ("box.scrollLeft=Number(range.value)||0" in html or "bar.onscroll=" in html)
    assert ('cornerTableHScrollSpacer' in html or "ctl.style.display='flex'" in html)


def test_scrollbar_has_no_obsolete_overlay_inner_proxy():
    html = performance_hub_page_html()
    assert 'cornerTableHScrollInner' not in html
