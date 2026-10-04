from pathlib import Path
from types import SimpleNamespace

from src.overlay.session_router import is_qualifying_snapshot


def test_router_detects_qualifying_from_profile():
    s = SimpleNamespace(event_profile='QUALIFYING', session_type='One-Shot Qualifying')
    assert is_qualifying_snapshot(s) is True


def test_router_detects_qualifying_from_session_type_even_if_profile_stale():
    s = SimpleNamespace(event_profile='WAITING', session_type='One-Shot Qualifying')
    assert is_qualifying_snapshot(s) is True


def test_router_rejects_race():
    s = SimpleNamespace(event_profile='RACE', session_type='Race')
    assert is_qualifying_snapshot(s) is False


def test_overlay_suite_has_separate_qualifying_window_and_atomic_swap():
    source = Path('src/overlay/window.py').read_text()
    assert 'class QualifyingEngineerOverlayWindow(RaceEngineerOverlayWindow)' in source
    assert 'self.qualifying_engineer = QualifyingEngineerOverlayWindow' in source
    assert 'if is_qualifying_snapshot(snapshot):' in source
    assert 'self.race_engineer.hide()' in source
    assert 'self.qualifying_engineer.show()' in source


def test_dedicated_qualifying_window_forces_qualifying_renderer():
    source = Path('src/overlay/window.py').read_text()
    section = source.split('class QualifyingEngineerOverlayWindow',1)[1].split('class DriverOverlayWindow',1)[0]
    assert 'self._render_qualifying(s)' in section
    assert 'RACE STRATEGY NOT APPLICABLE' not in section


def test_main_banner_is_v09123():
    source = Path('src/main.py').read_text()
    assert 'V0.9.17.2.3 REPLAY RECORDING SELECTOR' in source
