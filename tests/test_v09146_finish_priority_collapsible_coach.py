from pathlib import Path
from types import SimpleNamespace

from src.race_state.models import RaceState, CarState
from src.telemetry.enums import EnumValue
from src.session_summary import SessionSummaryTracker
from src.race_state_receiver import RaceStateReceiver


def _finished_state(position=1, total_laps=5):
    s = RaceState(player_index=0, player=CarState(index=0))
    s.field[0] = s.player
    s.session.uid = 146
    s.session.total_laps = total_laps
    s.player.lap.position = position
    s.player.lap.current_lap = total_laps
    s.player.lap.grid_position = 2
    s.player.lap.result_status = EnumValue(3, 'Finished')
    return s


def test_finished_lapdata_summary_uses_full_race_distance_without_final_packet():
    s = _finished_state()
    tracker = SessionSummaryTracker(); tracker.observe(s)
    summary = tracker.build(s, SimpleNamespace(completed=[]))
    assert summary['position'] == 1
    assert summary['laps_completed'] == 5
    assert 'win' in summary['finish_call'].lower() or 'won' in summary['finish_call'].lower()


def test_finish_evidence_accepts_finished_lapdata_before_final_classification():
    r = RaceStateReceiver.__new__(RaceStateReceiver)
    r.engine = SimpleNamespace(state=_finished_state(), performance=SimpleNamespace(completed=[]))
    r._finish_pending_after_chequered = False
    assert r._finish_evidence('lap') == 'lap_result'


def test_finish_evidence_accepts_chequered_plus_completed_final_lap():
    s = _finished_state()
    s.player.lap.result_status = EnumValue(2, 'Active')
    r = RaceStateReceiver.__new__(RaceStateReceiver)
    r.engine = SimpleNamespace(state=s, performance=SimpleNamespace(completed=[{'lap': 5, 'valid': True, 'lap_time_s': 87.2}]))
    r._finish_pending_after_chequered = True
    assert r._finish_evidence('lap') == 'chequered_final_lap'


def test_coach_overlay_has_independent_section_collapse_controls():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'self.delta_toggle' in source
    assert 'self.coach_toggle' in source
    assert 'self.history_toggle' in source
    assert 'def _toggle_delta_section' in source
    assert 'def _toggle_coach_section' in source
    assert 'def _toggle_history_section' in source
    assert 'self.coach_metrics_widget.setVisible(not self._coach_section_collapsed)' in source
    assert 'not self._history_section_collapsed' in source
