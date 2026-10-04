from pathlib import Path
from types import SimpleNamespace

import src.dashboard_server as dashboard_server
import src.overlay.track_maps as track_maps
from src.dashboard_server import dashboard_payload


def test_dashboard_payload_prefers_learned_track_points(monkeypatch):
    monkeypatch.setattr(dashboard_server, "get_track_map", lambda name: ((1.0, 2.0), (3.0, 4.0), (1.0, 2.0)))
    payload = dashboard_payload(SimpleNamespace(track_name="Melbourne"))
    assert payload["track_map_points"] == [[1.0, 2.0], [3.0, 4.0], [1.0, 2.0]]


def test_get_track_map_does_not_use_approximation_by_default(monkeypatch):
    monkeypatch.setitem(track_maps.TRACK_MAPS, "TEST CIRCUIT", ((0.0, 0.0), (1.0, 1.0), (0.0, 0.0)))
    track_maps.LEARNED_TRACK_MAPS.pop("TEST CIRCUIT", None)
    assert track_maps.get_track_map("Test Circuit") is None
    assert track_maps.get_track_map("Test Circuit", allow_fallback=True) is not None


def test_save_learned_map_persists_real_geometry(tmp_path, monkeypatch):
    monkeypatch.setattr(track_maps, "_CACHE_PATH", tmp_path / "track_maps_cache.json")
    points = [(float(i), float(i % 17)) for i in range(400)]
    learned = track_maps.save_learned_track_map("Telemetry Test", points)
    assert learned is not None and len(learned) >= 100
    assert track_maps.get_track_map("Telemetry Test") == learned
    assert (tmp_path / "tracks" / "TELEMETRY_TEST.json").exists()
