from src.engineer.engine import AutomaticEngineer
from src.engineer.models import Priority
from src.race_state.models import RaceState, CarState


def test_decision_audit_is_bounded_for_long_sessions():
    s=RaceState(); s.session.uid=1; s.player_index=0; s.player=CarState(0); s.field[0]=s.player
    e=AutomaticEngineer()
    for i in range(900):
        e._emit(f"test:{i}", Priority.INFORMATION, f"message {i}", float(i), s, 0)
    audit=s.extended.get("decision_audit")
    assert len(audit)==200
    assert audit[0]["text"]=="message 700"
    assert audit[-1]["text"]=="message 899"
