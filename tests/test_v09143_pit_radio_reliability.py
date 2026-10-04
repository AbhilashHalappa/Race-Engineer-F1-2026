from src.pit_strategy import assess_pit, service_plan
from src.race_state.models import RaceState
from src.voice_commands import VoiceIntent, handle_voice_request


def test_empty_state_pit_assessment_is_safe_and_explicit():
    state = RaceState()
    pit = assess_pit(state)
    assert pit.recommendation_hint == "insufficient_data"
    assert pit.missing_factors == ("live car data",)
    assert pit.serve_penalty_in_pit is None
    assert service_plan(state).automatic_summary == "No reliable pit call yet. Live car data unavailable."


def test_should_i_box_never_becomes_silent_without_live_car():
    state = RaceState()
    result = handle_voice_request("Should I box?", state)
    assert result.intent == VoiceIntent.PIT_RECOMMENDATION
    assert result.response == "Live car data is unavailable."
