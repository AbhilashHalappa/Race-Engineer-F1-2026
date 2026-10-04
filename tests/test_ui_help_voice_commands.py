from pathlib import Path


def test_control_center_has_help_tab_and_shared_radio_help_page():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'self.help_page = self._build_help_tab()' in source
    assert 'self.tabs.addTab(self.help_page, "HELP")' in source
    assert 'self.help_web_view.setUrl(QUrl(self.dashboard_url + "radio-help"))' in source


def test_voice_help_is_grouped_and_searchable():
    from src.radio_help_page import radio_help_page_html
    html = radio_help_page_html()
    for heading in (
        'Tyres', 'Brakes & Setup', 'Power Unit & Car Condition',
        'Position & Traffic', 'Laps & Timing', 'Fuel, ERS & Overtake Systems',
        'Weather & Race Control', 'Race Strategy', 'Pit & Service',
        'Driving & Performance', 'Race Engineer Controls',
        'Performance / Speed Coach Controls', 'Radio & Runtime Controls',
        'Coaching Mode, Detail & Voice', 'General Facts & Help',
    ):
        assert heading in html
    assert 'id="search"' in html
    assert 'Radio commands' in html
    assert 'Use this lap as reference' in html
    assert 'Enable Straight Line Coach' in html
