import tempfile
import time
import unittest
from pathlib import Path

from src.stt import STTConfig, SpeechToText


class Segment:
    def __init__(self, text): self.text = text


class FakeModel:
    def transcribe(self, path, **kwargs):
        return iter([Segment(" Can I box now? ")]), object()


class STTTests(unittest.TestCase):
    def test_defaults_are_local_cpu_small_english(self):
        c = STTConfig()
        self.assertEqual((c.model, c.device, c.compute_type, c.language),
                         ("small.en", "cpu", "int8", "en"))

    def test_worker_transcribes_submitted_capture(self):
        received = []
        stt = SpeechToText(STTConfig(), on_transcript=lambda text, path: received.append((text, path)),
                           model_factory=lambda *a, **k: FakeModel())
        stt.start(); stt.submit(Path("fake.wav"))
        deadline = time.time() + 2
        while not received and time.time() < deadline: time.sleep(0.01)
        stt.close()
        self.assertEqual(received, [("Can I box now?", Path("fake.wav"))])

    def test_disabled_worker_does_not_start(self):
        stt = SpeechToText(STTConfig(enabled=False), model_factory=lambda *a, **k: FakeModel())
        stt.start()
        self.assertIsNone(stt._thread)
