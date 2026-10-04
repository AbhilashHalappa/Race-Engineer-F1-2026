from src.performance_hub_ui import performance_hub_page_html


def test_corner_table_uses_real_scroll_proxy_not_range_input():
    html = performance_hub_page_html()
    assert 'id=cornerTableHScroll class=cornerTableHScroll' in html
    assert 'id=cornerTableHScrollSpacer class=cornerTableHScrollSpacer' in html
    assert 'id=cornerTableScrollRange' not in html
    assert 'bar.onscroll=' in html
    assert 'id=cornerScrollLeft' in html
    assert 'id=cornerScrollRight' in html
    assert "left.onclick=()=>box.scrollBy" in html
    assert "right.onclick=()=>box.scrollBy" in html
    assert 'box.onscroll=' in html
    assert "spacer.style.width=content+'px'" in html
