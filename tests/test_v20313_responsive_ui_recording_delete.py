from pathlib import Path

from src.session_library import SessionLibrary
from src.session_library_ui import session_library_page_html
from src.performance_hub_ui import performance_hub_page_html


def test_session_library_can_delete_active_recording_and_cache(tmp_path):
    recordings=tmp_path/'recordings'; recordings.mkdir()
    reports=tmp_path/'reports'; reports.mkdir()
    metadata=tmp_path/'sessions'/'session_library.json'
    p=recordings/'sample.areplay'; p.write_bytes(b'replay')
    sidecar=recordings/'sample.areplay.json'; sidecar.write_text('{}')
    lib=SessionLibrary(recordings=recordings,metadata=metadata,reports=reports)
    lib.replay_analysis.cache_dir=tmp_path/'cache'; lib.replay_analysis.cache_dir.mkdir()
    cache=lib.replay_analysis.cache_dir/'sample.areplay.index.json'; cache.write_text('{}')
    lib.update('sample.areplay',name='Sample')
    out=lib.delete_recording('sample.areplay')
    assert out['deleted'] is True
    assert not p.exists() and not sidecar.exists() and not cache.exists()
    assert 'sample.areplay' not in lib._meta()


def test_session_analysis_exposes_delete_recording_with_confirmation():
    html=session_library_page_html()
    assert 'DELETE RECORDING' in html
    assert 'deleteRecording' in html
    assert "action:'delete'" in html
    assert 'permanently deletes the .areplay recording' in html


def test_dashboard_delete_recording_route_is_local_only():
    text=Path('src/dashboard_server.py').read_text(encoding='utf-8')
    assert 'recording deletion is local-only' in text
    assert 'lib.delete_recording(filename)' in text


def test_control_center_is_scrollable_and_reflows_launchers():
    text=Path('src/overlay/window.py').read_text(encoding='utf-8')
    cc=text.split('class ControlCenterWindow',1)[1].split('class DriverOverlayWindow',1)[0]
    assert 'QScrollArea()' in cc
    assert 'setWidgetResizable(True)' in cc
    assert 'ScrollBarAsNeeded' in cc
    assert 'def _reflow_overlay_launchers' in cc
    assert 'def resizeEvent' in cc
    assert 'def _scale_control_fonts' in cc


def test_performance_hub_uses_full_width_responsive_layout():
    html=performance_hub_page_html()
    assert 'max-width:none' in html
    assert 'font-size:clamp(' in html
    assert '@media(max-width:1100px)' in html
    assert '@media(max-width:700px)' in html
