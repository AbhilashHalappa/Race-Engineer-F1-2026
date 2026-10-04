
from src.practice_hub_ui import practice_hub_page_html

def test_status_pill_is_compact_and_legacy_history_is_visible():
    html=practice_hub_page_html()
    assert "align-self:flex-start" in html
    assert "PRACTICE HISTORY" in html
    assert "legacy provisional" in html
    assert "legacy_reference_notice" in html
