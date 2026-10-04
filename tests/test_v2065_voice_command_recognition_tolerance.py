from src.voice_commands import normalize_radio_text, parse_intent, VoiceIntent
from src.radio_controls import parse_runtime_radio_command


def test_observed_pre_coach_stt_near_misses_are_exactly_normalized():
    for raw, expected in (
        ("Pre-coat", "pre coach"),
        ("enable pre-cut", "enable pre coach"),
        ("enable pre-code", "enable pre coach"),
    ):
        assert normalize_radio_text(raw) == expected


def test_observed_coach_and_voice_near_misses_route_to_intended_controls():
    cases = (
        ("Enable performance good.", "SPEED", True),
        ("Enable straight line good.", "STRAIGHT", True),
        ("Enable driitline voice", "SLVOICE", True),
        ("Enable gain loss wise", "GAINLOSSVOICE", True),
    )
    for raw, target, value in cases:
        normalized = normalize_radio_text(raw)
        command = parse_runtime_radio_command(normalized)
        assert command is not None
        assert command.action == "CONTROL_SET"
        assert command.target == target
        assert command.value is value


def test_help_and_voice_speed_observed_near_misses_are_tolerated():
    assert normalize_radio_text("Vise control help") == "voice control help"
    command = parse_runtime_radio_command(normalize_radio_text("Vise control help"))
    assert command is not None and command.action == "HELP"

    assert normalize_radio_text("set Y speed fast") == "set voice speed fast"
    command = parse_runtime_radio_command(normalize_radio_text("set Y speed fast"))
    assert command is not None and command.action == "VOICE_SPEED" and command.value == "fast"

    assert normalize_radio_text("set voice speed low") == "set voice speed slow"
    command = parse_runtime_radio_command(normalize_radio_text("set voice speed low"))
    assert command is not None and command.action == "VOICE_SPEED" and command.value == "slow"


def test_compare_previous_observed_variant_uses_existing_reference_intent():
    normalized = normalize_radio_text("compare it previous")
    assert normalized == "compare with previous"
    assert parse_intent(normalized) == VoiceIntent.REFERENCE_PREVIOUS


def test_ambiguous_short_speech_is_not_promoted_to_a_control():
    # Do not make the normalization layer so fuzzy that ordinary/misheard speech
    # starts changing runtime state.
    assert normalize_radio_text("Be good") == "be good"
    assert parse_runtime_radio_command(normalize_radio_text("Be good")) is None
    assert normalize_radio_text("G4") == "g4"
    assert parse_runtime_radio_command(normalize_radio_text("G4")) is None
