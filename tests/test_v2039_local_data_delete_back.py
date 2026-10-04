from pathlib import Path

from src import app_paths
from src.session_library_ui import session_library_page_html


def test_structured_local_data_layout_manifest():
    m=app_paths.layout_manifest()
    assert m['performance'].endswith('user_data/performance')
    assert m['sessions'].endswith('user_data/sessions')
    assert m['recordings'].endswith('user_data/recordings')
    assert m['tracks'].endswith('user_data/tracks')
    assert m['references'].endswith('user_data/references')


def test_replay_session_analysis_has_back_and_refresh_controls():
    html=session_library_page_html()
    assert '>BACK<' in html
    assert 'goBack()' in html
    assert "location.href='/performance'" in html
    assert '>REFRESH<' in html


def test_local_request_source_matches_host_logic_is_present():
    text=Path('src/dashboard_server.py').read_text(encoding='utf-8')
    assert "client == host.strip('[]')" in text
    assert "session deletion is local-only" in text
