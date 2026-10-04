from types import SimpleNamespace
from pathlib import Path

from src.dashboard_server import dashboard_payload, DASHBOARD_HTML


def test_dashboard_payload_carries_coaching_presentation_state():
    s=SimpleNamespace(coaching_mode="performance_coach", coaching_verbosity="minimal", dashboard_focus_page="map")
    payload=dashboard_payload(s)
    assert payload["coaching_mode"] == "performance_coach"
    assert payload["coaching_verbosity"] == "minimal"
    assert payload["dashboard_focus_page"] == "map"


def test_dashboard_mode_focus_is_present_without_overriding_safety_pages():
    assert "dashboard_focus_page" in DASHBOARD_HTML
    assert "lastCoachMode" in DASHBOARD_HTML
    # Damage and pit auto-pages remain higher-priority than the mode preference.
    assert "autoPage='damage'" in DASHBOARD_HTML
    assert "autoPage='pit'" in DASHBOARD_HTML


def test_control_center_exposes_mode_and_detail_selectors():
    source=Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "self.coaching_mode_combo=QComboBox()" in source
    assert 'self.coaching_verbosity_combo=QComboBox()' in source
    assert 'on_select_coaching_mode=(receiver.set_coaching_mode' in source
    assert 'on_select_coaching_verbosity=(receiver.set_coaching_verbosity' in source
    assert 'self.set_coaching_controls(getattr(s,"coaching_mode",None),getattr(s,"coaching_verbosity",None))' in source


def test_overlay_snapshot_exposes_coaching_policy_fields():
    source=Path("src/overlay/data.py").read_text(encoding="utf-8")
    assert 'coaching_mode: str = "auto"' in source
    assert 'coaching_verbosity: str = "normal"' in source
    assert 'dashboard_focus_page: str = "dash"' in source
