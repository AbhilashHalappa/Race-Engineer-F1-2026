from pathlib import Path
import time

from src.stt import STTConfig, SpeechToText


class _Segment:
    text = "tyre temperatures"


class _Model:
    def __init__(self):
        self.kwargs = None
    def transcribe(self, _path, **kwargs):
        self.kwargs = kwargs
        return [_Segment()], object()


def test_fast_ptt_uses_greedy_no_vad_no_timestamps(tmp_path):
    model = _Model()
    got = []
    stt = SpeechToText(
        STTConfig(enabled=True, fast_ptt=True, beam_size=5, vad_filter=True),
        on_transcript=lambda text, path: got.append(text),
        model_factory=lambda *a, **k: model,
    )
    wav = tmp_path / "ptt.wav"
    wav.write_bytes(b"x")
    stt.start(); stt.submit(wav)
    deadline = time.time() + 2
    while not got and time.time() < deadline:
        time.sleep(0.01)
    stt.close()
    assert got == ["tyre temperatures"]
    assert model.kwargs["beam_size"] == 1
    assert model.kwargs["vad_filter"] is False
    assert model.kwargs["without_timestamps"] is True
