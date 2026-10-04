import threading
import time
from pathlib import Path
from unittest.mock import patch

from src.engineer.models import EngineerMessage, Priority
from src.radio_transcript import RadioTranscriptStore
from src.tts import SpeechOutput, TTSConfig


def test_radio_transcript_store_keeps_driver_and_engineer_in_order():
    store = RadioTranscriptStore(max_entries=3)
    store.add_driver("  Tyres   please?  ", session_time_s=62.5)
    store.add_engineer(EngineerMessage(
        key="voice:response", priority=Priority.STRATEGY,
        text="Fronts are warm.", created_at=time.monotonic(), session_time_s=63.0,
    ))
    entries = store.snapshot()
    assert [(e.role, e.text) for e in entries] == [
        ("DRIVER", "Tyres please?"),
        ("ENGINEER", "Fronts are warm."),
    ]
    assert entries[0].session_time_s == 62.5
    assert entries[1].key == "voice:response"


def test_radio_transcript_store_is_bounded_and_clear_advances_revision():
    store = RadioTranscriptStore(max_entries=2)
    store.add_driver("one")
    store.add_driver("two")
    store.add_driver("three")
    assert [e.text for e in store.snapshot()] == ["two", "three"]
    revision = store.latest_sequence
    store.clear()
    assert store.snapshot() == ()
    assert store.latest_sequence > revision


@patch("src.tts.SpeechOutput._load_piper")
@patch("src.tts.sys.platform", "win32")
def test_tts_transcript_callback_runs_only_when_audio_starts(_load):
    heard = []
    started = threading.Event()
    speech = SpeechOutput(TTSConfig(), on_audio_start=lambda message: (heard.append(message.text), started.set()))
    speech._piper_voice = object()
    speech._piper_config_type = object()

    def fake_speak(text):
        speech._mark_audio_start()
        return True

    speech._speak = fake_speak
    speech.submit((EngineerMessage(
        key="voice:response", priority=Priority.STRATEGY,
        text="Box this lap.", created_at=time.monotonic(), session_time_s=81.2,
    ),))
    assert started.wait(0.5)
    speech._queue.join()
    speech.close()
    assert heard == ["Box this lap."]


def test_radio_overlay_source_has_launcher_and_incremental_store_refresh():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "class RadioTranscriptOverlayWindow" in source
    assert '("RT", "Radio Transcript"' in source and 'on_show_radio_transcript' in source
    assert "self.radio_transcript.update_from_store()" in source
    assert "DRIVER questions" in source


def test_overlay_ptt_allows_hid_but_keeps_pygame_guard():
    source = Path("src/main.py").read_text(encoding="utf-8")
    assert 'args.overlay and args.ptt and args.ptt_backend != "hid"' in source
    assert "raw HID backend only" in source
    assert "V0.9.17.2.3 REPLAY RECORDING SELECTOR" in source
