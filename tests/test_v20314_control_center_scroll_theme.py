from pathlib import Path


def test_control_center_scroll_layers_are_explicitly_dark_themed():
    text = Path('src/overlay/window.py').read_text(encoding='utf-8')
    cc = text.split('class ControlCenterWindow', 1)[1].split('class DriverOverlayWindow', 1)[0]
    assert 'setObjectName("controlPageScroll")' in cc
    assert 'setObjectName("controlPageViewport")' in cc
    assert 'setObjectName("controlPageContent")' in cc
    assert 'Qt.WA_StyledBackground' in cc
    assert 'QScrollArea#controlPageScroll { background: #171d24;' in cc
    assert 'QWidget#controlPageViewport { background: #171d24; }' in cc
    assert 'QWidget#controlPageContent { background: #171d24; }' in cc
    assert 'QScrollBar::handle:vertical' in cc
