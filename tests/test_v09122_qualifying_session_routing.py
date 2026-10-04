from pathlib import Path


def test_re_routes_by_profile_or_session_type():
    source = Path("src/overlay/window.py").read_text()
    assert '"QUALIFY" in profile or "QUALIFY" in session_type' in source
    assert 'self._render_qualifying(s)' in source


def test_re_default_header_is_session_engineer_for_build_identity():
    source = Path("src/overlay/window.py").read_text()
    assert 'super().__init__("SESSION ENGINEER"' in source


def test_main_banner_has_current_build_identity():
    source = Path("src/main.py").read_text()
    assert "V0.9.17.2.3 REPLAY RECORDING SELECTOR" in source
