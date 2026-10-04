from pathlib import Path


def test_race_engineer_is_updated_from_shared_overlay_snapshot():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    refresh_start = source.index("    def refresh(self):")
    refresh_end = source.index("    def toggle_pause(self):", refresh_start)
    refresh = source[refresh_start:refresh_end]
    assert "snapshot = self.provider.snapshot()" in refresh
    assert "self.race_engineer.update_snapshot(snapshot)" in refresh
    assert refresh.index("self.race_engineer.update_snapshot(snapshot)") > refresh.index("snapshot = self.provider.snapshot()")


def test_no_second_race_engineer_refresh_timer_remains():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "race_engineer_timer" not in source
    assert "def refresh_race_engineer(" not in source
