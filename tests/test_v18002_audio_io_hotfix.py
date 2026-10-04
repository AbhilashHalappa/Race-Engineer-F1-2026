from types import SimpleNamespace
from unittest.mock import patch

from src.audio_devices import AudioDeviceInfo
from src.voice_commands import is_likely_stt_hallucination, normalize_radio_text, parse_intent, VoiceIntent


def test_audio_label_exposes_host_api_and_default_role():
    d = AudioDeviceInfo(14, "Microphone Array", 2, 0, 48000.0,
                        hostapi_index=2, hostapi_name="Windows WASAPI", is_default_input=True)
    assert "Windows WASAPI" in d.label
    assert "DEFAULT MIC" in d.label


def test_known_whisper_video_hallucinations_are_rejected():
    assert is_likely_stt_hallucination("Thank you for watching and see you in the next video.")
    assert normalize_radio_text("Thanks for watching.") == ""


def test_observed_where_i_am_losing_variant_is_supported():
    assert parse_intent("Where I am losing?") == VoiceIntent.PERFORMANCE_COMPARE


def test_runtime_control_phrases_are_available_to_fuzzy_normalizer():
    assert normalize_radio_text("straight line code status") == "straight line coach status"
    assert normalize_radio_text("table corner coach") == "disable corner coach"
