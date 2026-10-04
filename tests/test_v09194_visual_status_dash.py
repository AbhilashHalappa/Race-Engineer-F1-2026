from pathlib import Path

from src.dashboard_server import DASHBOARD_HTML


def test_lan_visual_tyres_have_four_corner_status_cards():
    for ident in ("tcFL", "tcFR", "tcRL", "tcRR", "tpFL", "tpFR", "tpRL", "tpRR", "thFL", "thFR", "thRL", "thRR"):
        assert f'id="{ident}"' in DASHBOARD_HTML
    for helper in ("tyreColor", "brakeColor", "wearColor"):
        assert f"function {helper}" in DASHBOARD_HTML
    for label in ("OUTER", "INNER", "BRAKE", "WEAR", "TYRE DMG", "BRAKE DMG", "BLISTER"):
        assert label in DASHBOARD_HTML
    assert "v<1000" in DASHBOARD_HTML
    assert "v<1100" in DASHBOARD_HTML
    assert "v<115" in DASHBOARD_HTML


def test_lan_damage_page_combines_car_and_power_unit_status():
    for ident in ("dcFL", "dcFR", "dcRW", "dcFloor", "dcDiff", "dcSide", "puEngine", "puGBX", "puICE", "puCE", "puES", "puMGUH", "puMGUK", "puTC"):
        assert f'id="{ident}"' in DASHBOARD_HTML
    assert "DAMAGE &amp; POWER UNIT" in DASHBOARD_HTML
    assert "function dmgColor" in DASHBOARD_HTML


def test_native_dash_source_uses_independent_dynamic_status_colors():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "def _tyre_temp_color" in source
    assert "def _brake_temp_color" in source
    assert "def _wear_color" in source
    assert '"OUTER"' in source
    assert '"BRAKE DMG"' in source
    assert "_paint_damage_page" in source
    assert "_paint_tyres_page" in source
