from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOW = (ROOT / "src" / "overlay" / "window.py").read_text(encoding="utf-8")


def _class_block(name: str, next_name: str) -> str:
    return WINDOW.split(f"class {name}", 1)[1].split(f"class {next_name}", 1)[0]


def test_fuel_overlay_reserves_vertical_room_for_banner_hero_metrics_and_footer():
    block = _class_block("FuelOverlayWindow", "WeatherOverlayWindow")
    assert "WIDTH=390; HEIGHT=335" in block
    assert 'self.set_applicable(s.fuel_applicable, "FUEL STRATEGY NOT APPLICABLE IN THIS SESSION")' in block
    # The footer must exist before the first showEvent captures the overlay zoom baseline.
    assert block.find("self.create_footer()") < block.find("def update_snapshot")
    # Protect the existing fuel data presentation; this hotfix is layout-only.
    assert 'self.big_mass = self.label("-- kg", 20, True, WHITE)' in block
    assert 'self.fuel_bar.setFixedHeight(16)' in block
    assert 'metrics = [("Last lap", "--"), ("Remaining", "--"), ("Avg / 3", "--"), ("Δ use", "--"), ("Min use", "--"), ("Max use", "--")]' in block


def test_weather_overlay_reserves_vertical_room_and_scales_footer_with_content():
    block = _class_block("WeatherOverlayWindow", "StandingsOverlayWindow")
    assert "WIDTH=420; HEIGHT=330" in block
    assert 'self.set_applicable(s.weather_applicable, "WEATHER STRATEGY NOT APPLICABLE IN THIS SESSION")' in block
    assert block.find("self.create_footer()") < block.find("def update_snapshot")
    # Keep the existing three-card forecast layout and telemetry fields intact.
    assert "for _ in range(3):" in block
    assert 'self.track_temp = self.label("Track --", 8, True, WHITE)' in block
    assert 'self.air_temp = self.label("Air --", 8, True, WHITE)' in block
    assert 'data=list(s.weather_forecast)' in block
