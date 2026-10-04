from pathlib import Path

from src.driver_skill_reconciliation import DriverSkillReconciliation
from src.performance_hub_ui import performance_hub_page_html


def test_hub_uses_actual_trend_window_count_not_fixed_five_session_label():
    html = performance_hub_page_html()
    assert "trend_window_count" in html
    assert "n+'-session '" in html
    assert "· 5-session ${" not in html
    assert "domain evidence snapshots" in html


def test_reconciliation_publishes_actual_trend_window_count():
    src = Path("src/driver_skill_reconciliation.py").read_text(encoding="utf-8")
    assert '"trend_window_count": len(last5)' in src


def test_driver_profile_skill_headers_are_larger_and_more_readable():
    src = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'skill_label=self.label(key.upper(),10,True,"#aebdcc")' in src
    assert 'detail=self.label("No validated evidence",8,False,MUTED)' in src


def test_performance_hub_skill_domain_labels_are_larger():
    html = performance_hub_page_html()
    assert ".skillDomain .k{font-size:12px" in html
