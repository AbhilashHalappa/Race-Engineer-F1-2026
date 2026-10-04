from pathlib import Path


def test_qualifying_engineer_declared_after_race_engineer():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    race = source.index("class RaceEngineerOverlayWindow(DataOverlayWindow):")
    qual = source.index("class QualifyingEngineerOverlayWindow(RaceEngineerOverlayWindow):")
    assert race < qual


def test_startup_banner_updated():
    source = Path("src/main.py").read_text(encoding="utf-8")
    assert "V0.9.17.2.3 REPLAY RECORDING SELECTOR" in source
