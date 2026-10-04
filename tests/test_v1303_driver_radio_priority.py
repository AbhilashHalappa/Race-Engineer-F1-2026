import threading
import time
from unittest.mock import MagicMock, patch

from src.engineer.models import EngineerMessage, Priority
from src.tts import SpeechOutput, TTSConfig


def _speech():
    s = SpeechOutput(TTSConfig(enabled=False))
    s.available = True
    s.backend = "piper"
    s._piper_voice = MagicMock()
    s._piper_config_type = MagicMock()
    return s


def test_prepare_radio_response_reserves_channel_and_drops_fresh_corner_coach():
    s = _speech()
    s.prepare_radio_response()
    assert s.driver_response_pending() is True
    q0 = s._queue.qsize()
    s.submit((EngineerMessage("corner:post:1:Z1", Priority.COACHING, "Turn one, lost two tenths.", time.monotonic()),))
    assert s._queue.qsize() == q0
    s.submit((EngineerMessage("voice:response", Priority.STRATEGY, "Your answer.", time.monotonic()),))
    assert s._queue.qsize() == q0 + 1
    s.cancel_driver_response()


def test_worker_rechecks_epoch_after_ptt_wait_so_popped_coach_cannot_speak_before_answer():
    spoken = []
    coach_popped = threading.Event()

    with patch('src.tts.sys.platform', 'win32'), patch.object(SpeechOutput, '_load_piper'):
        s = SpeechOutput(TTSConfig())
        s._piper_voice = MagicMock(); s._piper_config_type = MagicMock(); s.backend = 'piper'

        def fake_speak(text):
            spoken.append(text)
            return True
        s._speak = fake_speak

        # Hold PTT first, then queue coaching. The worker can pop this item and
        # wait on _listening. The later answer invalidates its epoch.
        s.begin_listening()
        s.submit((EngineerMessage('corner:post:1:Z1', Priority.COACHING, 'Old coach', time.monotonic()),))
        time.sleep(0.05)
        s.prepare_radio_response()
        s.submit((EngineerMessage('voice:response', Priority.STRATEGY, 'Driver answer', time.monotonic()),))
        s.end_listening()
        s._queue.join()
        s.close()

    assert spoken == ['Driver answer']


def test_driver_answer_pending_clears_only_after_answer_worker_finishes():
    entered = threading.Event(); release = threading.Event()
    with patch('src.tts.sys.platform', 'win32'), patch.object(SpeechOutput, '_load_piper'):
        s = SpeechOutput(TTSConfig())
        s._piper_voice = MagicMock(); s._piper_config_type = MagicMock(); s.backend = 'piper'
        def fake_speak(text):
            entered.set(); release.wait(1); return True
        s._speak = fake_speak
        s.prepare_radio_response()
        s.submit((EngineerMessage('voice:response', Priority.STRATEGY, 'Answer now', time.monotonic()),))
        s.end_listening()
        assert entered.wait(1)
        assert s.driver_response_pending() is True
        release.set(); s._queue.join()
        assert s.driver_response_pending() is False
        s.close()
