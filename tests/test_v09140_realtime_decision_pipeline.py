import os
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.engineer.models import EngineerMessage, Priority
from src.latency import LatencyMonitor
from src.telemetry_recording import AsyncTelemetrySessionRecorder, read_replay
from src.tts import SpeechOutput, TTSConfig


def test_latency_monitor_reports_core_radio_and_audio_percentiles():
    m = LatencyMonitor(window=64)
    for i in range(1, 21):
        m.observe_packet(
            decode_ns=i * 100_000,
            state_ns=i * 200_000,
            decision_ns=i * 50_000,
            core_ns=i * 400_000,
            dispatch_ns=i * 10_000,
            decisions=1 if i % 4 == 0 else 0,
        )
    m.radio_queued(3)
    m.radio_dequeued(12_000_000, 2)
    m.audio_started(31_000_000)
    m.preempted()
    s = m.snapshot()
    assert s.packets == 20
    assert s.decisions == 5
    assert s.core_avg_ms > 0
    assert s.core_p95_ms >= s.core_avg_ms
    assert s.radio_queue_p95_ms == 12.0
    assert s.audio_start_p95_ms == 31.0
    assert s.queue_depth == 2
    assert s.queue_depth_max == 3
    assert s.preemptions == 1
    assert "[LATENCY]" in m.format_compact()


def test_async_recorder_is_lossless_and_drains_on_close(tmp_path):
    path = tmp_path / "async.areplay"
    r = AsyncTelemetrySessionRecorder(path=path)
    payloads = [bytes([i % 251]) * (20 + (i % 11)) for i in range(300)]
    for i, payload in enumerate(payloads):
        r.record(payload, 100.0 + i * 0.001)
    r.close()
    assert r.last_error is None
    assert r.count == len(payloads)
    records = read_replay(path)
    assert [x.data for x in records] == payloads
    assert r.pending == 0


@patch('src.tts.SpeechOutput._load_piper')
@patch('src.tts.sys.platform', 'win32')
def test_critical_call_preempts_message_during_synthesis(load):
    started = threading.Event()
    cancelled = threading.Event()
    spoken = []

    speech = SpeechOutput(TTSConfig(), latency_monitor=LatencyMonitor())
    speech._piper_voice = MagicMock()
    speech._piper_config_type = MagicMock()
    speech.backend = 'piper'

    def fake_speak(text):
        if text == 'Routine information':
            started.set()
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if speech._current_cancelled():
                    cancelled.set()
                    return False
                time.sleep(0.002)
            return True
        spoken.append(text)
        return True

    speech._speak_piper = fake_speak
    speech.submit((EngineerMessage('info', Priority.INFORMATION, 'Routine information', time.monotonic()),))
    assert started.wait(0.5)
    speech.submit((EngineerMessage('flag:local', Priority.CRITICAL, 'Yellow flag', time.monotonic()),))
    assert cancelled.wait(0.5)
    speech._queue.join()
    snap = speech.latency_monitor.snapshot()
    speech.close()

    assert spoken == ['Yellow flag']
    assert snap.preemptions >= 1


def test_static_prompt_cache_path_is_stable_and_only_for_whitelist(tmp_path):
    cfg = TTSConfig(enabled=False, static_prompt_cache_dir=str(tmp_path))
    speech = SpeechOutput(cfg)
    p1 = speech._static_cache_path('Track limits.')
    p2 = speech._static_cache_path('Track limits.')
    assert p1 == p2
    assert p1 is not None and p1.parent == tmp_path
    assert speech._static_cache_path('Dynamic gap 1.234 seconds.') is None
    speech.close()


def test_windows_native_wav_playback_path_avoids_powershell(tmp_path):
    import sys
    import types
    import wave

    wav_path = tmp_path / 'short.wav'
    with wave.open(str(wav_path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(1000); w.writeframes(b'\0\0' * 2)

    calls = []
    fake = types.SimpleNamespace(
        SND_FILENAME=1, SND_ASYNC=2, SND_NODEFAULT=4,
        PlaySound=lambda path, flags: calls.append((path, flags)),
    )
    speech = SpeechOutput(TTSConfig(enabled=False))
    with patch.dict(sys.modules, {'winsound': fake}), patch('src.tts.sys.platform', 'win32'), \
         patch.object(speech, '_run_playback_process') as fallback:
        assert speech._play_wav(wav_path) is True
        fallback.assert_not_called()
    assert calls[0][0] == str(wav_path)
    assert calls[-1][0] is None
    speech.close()
