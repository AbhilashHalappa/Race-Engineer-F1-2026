from types import SimpleNamespace

from src.dashboard_server import dashboard_payload
from src.overlay.data import MapTurnMarker, _map_turn_markers
from src.overlay.ui_text import coach_button_text


def test_coaching_button_keeps_feature_name_visible():
    assert coach_button_text("POST", "Enabled") == "POST ON"
    assert coach_button_text("PRE", "Disabled") == "PRE OFF"
    assert coach_button_text("RACE", "On") == "RACE ON"


def test_reference_sections_become_map_turn_labels_at_apex_proxy():
    reference = {
        "sections": [
            {"id": 1, "start_m": 300.0, "turn_in_m": 350.0, "min_speed_m": 390.0},
            {"id": 2, "start_m": 900.0, "turn_in_m": 950.0},
            {"id": 3, "start_m": 1400.0},
        ]
    }
    turns = _map_turn_markers(reference)
    assert [(t.corner_id, t.label, t.lap_distance_m) for t in turns] == [
        (1, "T1", 390.0),
        (2, "T2", 950.0),
        (3, "T3", 1400.0),
    ]


def test_lan_dashboard_payload_exposes_map_turns():
    snap = SimpleNamespace(
        connected=True,
        map_turns=(MapTurnMarker(1, "T1", 390.0), MapTurnMarker(3, "T3", 1400.0)),
    )
    payload = dashboard_payload(snap)
    assert payload["map_turns"] == [
        {"corner_id": 1, "label": "T1", "lap_distance_m": 390.0},
        {"corner_id": 3, "label": "T3", "lap_distance_m": 1400.0},
    ]
