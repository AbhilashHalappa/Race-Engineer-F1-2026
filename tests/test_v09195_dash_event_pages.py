from types import SimpleNamespace
from pathlib import Path

from src.dashboard_server import DASHBOARD_HTML, dashboard_payload
from src.overlay.data import build_overlay_snapshot


def test_dashboard_payload_exposes_pause_state():
    p = dashboard_payload(SimpleNamespace(game_paused=True))
    assert p["game_paused"] is True


def test_browser_auto_damage_pit_and_near_part_values_present():
    assert "damageUntil=now+3000" in DASHBOARD_HTML
    assert "function pitActive" in DASHBOARD_HTML
    assert "autoSelectPage(s)" in DASHBOARD_HTML
    assert "ALL CAR / AERO DAMAGE AND ENGINE / HYBRID WEAR" in DASHBOARD_HTML
    assert "setStatusValue('dcFL'" in DASHBOARD_HTML
    assert 'id="puMGUH"' in DASHBOARD_HTML


def test_native_source_has_three_second_damage_and_pause_freeze():
    text = Path("src/overlay/window.py").read_text()
    assert "self._damage_until = now + 3.0" in text
    assert "if self._paused or bool(getattr(snapshot,\"game_paused\",False))" in text
    assert "self._pit_active(snapshot)" in text


def test_graph_distance_ticks_are_100m():
    text = Path("src/overlay/widgets.py").read_text()
    assert text.count("range(first_tick,int(math.floor(d1/100.0)*100)+1,100)") >= 2


def test_overlay_snapshot_reads_game_pause_flag():
    session = SimpleNamespace(paused=True)
    state = SimpleNamespace(player=None, player_index=0, session=session, extended={})
    performance = SimpleNamespace(samples={}, completed=[], event_context={})
    snap = build_overlay_snapshot(state, performance, connected=True, now=0.0)
    assert snap.game_paused is True
