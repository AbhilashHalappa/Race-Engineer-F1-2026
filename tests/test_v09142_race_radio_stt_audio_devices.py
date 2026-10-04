from pathlib import Path
from unittest.mock import patch

from src.stt import STTConfig, SpeechToText
from src.ptt import PTTConfig, PTTController, MicrophoneRecorder
from src.tts import SpeechOutput, TTSConfig


def test_race_radio_stt_defaults_are_tuned():
    cfg = STTConfig()
    assert cfg.model == "small.en"
    assert cfg.beam_size == 1
    assert cfg.vad_filter is False
    assert cfg.fast_ptt is True
    assert "tyres" in cfg.hotwords.lower()
    assert "brake" in cfg.initial_prompt.lower()


def test_stt_passes_race_radio_prompt_when_supported(tmp_path):
    seen = {}
    class Segment:
        text = " Brake information. "
    class Model:
        def transcribe(self, path, **kwargs):
            seen.update(kwargs)
            return [Segment()], object()
    got=[]
    stt=SpeechToText(STTConfig(), on_transcript=lambda text, path: got.append(text), model_factory=lambda *a, **k: Model())
    model=stt._make_model()
    kwargs = dict(language=stt.config.language, vad_filter=stt.config.vad_filter, beam_size=stt.config.beam_size,
                  temperature=0.0, condition_on_previous_text=False, initial_prompt=stt.config.initial_prompt,
                  hotwords=stt.config.hotwords, vad_parameters={"speech_pad_ms":220})
    segs,_=model.transcribe("x.wav", **kwargs)
    assert list(segs)[0].text.strip() == "Brake information."
    assert seen["condition_on_previous_text"] is False
    assert "ERS" in seen["hotwords"]


def test_ptt_microphone_can_change_between_transmissions():
    recorder = MicrophoneRecorder(PTTConfig(enabled=True, mic_device=None))
    ptt = PTTController(recorder.config, recorder=recorder)
    ok,_ = ptt.set_microphone_device(7)
    assert ok
    assert ptt.config.mic_device == 7
    assert recorder.config.mic_device == 7
    ptt._pressed = True
    ok,msg = ptt.set_microphone_device(8)
    assert not ok and "Release PTT" in msg


def test_tts_output_device_setting_is_runtime_mutable():
    speech = SpeechOutput(TTSConfig(enabled=False, output_device=None))
    ok,_ = speech.set_output_device(5)
    assert ok
    assert speech.config.output_device == 5


def test_control_center_source_contains_audio_selectors():
    source = (Path(__file__).parents[1] / "src" / "overlay" / "window.py").read_text(encoding="utf-8")
    assert "QComboBox" in source
    assert '"MIC"' in source
    assert '"OUT"' in source
    assert "on_select_mic" in source
    assert "on_select_audio" in source
