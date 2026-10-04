from dataclasses import replace
from pathlib import Path

from src.llm_engineer import LLMConfig, LocalLLMEngineer
from src.ptt import PTTConfig, PTTController
from src.race_state_receiver import RaceStateReceiver
from src.stt import STTConfig, SpeechToText


def make_receiver():
    return RaceStateReceiver(
        tts_enabled=False,
        ptt_config=PTTConfig(enabled=False, backend="hid"),
        stt_config=STTConfig(enabled=False),
        llm_config=LLMConfig(enabled=False),
        wheel_telemetry=False,
    )


def test_runtime_feature_states_and_safe_toggles(monkeypatch, tmp_path):
    receiver = make_receiver()
    assert receiver.runtime_feature_states() == {
        "TTS": False, "PTT": False, "STT": False, "LLM": False, "REC": False,
    }

    monkeypatch.setattr(PTTController, "start", lambda self: None)
    monkeypatch.setattr(SpeechToText, "start", lambda self: None)

    def fake_llm_set_enabled(self, enabled):
        self.config = replace(self.config, enabled=bool(enabled))
    monkeypatch.setattr(LocalLLMEngineer, "set_enabled", fake_llm_set_enabled)

    assert receiver.set_tts_enabled(True)[0]
    assert receiver.set_ptt_enabled(True)[0]
    assert receiver.set_stt_enabled(True)[0]
    assert receiver.set_llm_enabled(True)[0]
    states = receiver.runtime_feature_states()
    assert states["TTS"] and states["PTT"] and states["STT"] and states["LLM"]

    monkeypatch.chdir(tmp_path)
    assert receiver.set_recording_enabled(True) == (True, "On")
    assert receiver.runtime_feature_states()["REC"] is True
    assert receiver.set_recording_enabled(False) == (True, "Off")
    assert receiver.runtime_feature_states()["REC"] is False

    receiver.ptt.close(wait=False)
    receiver.stt.close(wait=False)
    receiver.llm.close(wait=False)
    receiver.speech.close(wait=False)


def test_control_center_exposes_clickable_runtime_statuses():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    for feature in ("TTS", "PTT", "STT", "LLM", "REC"):
        assert f'"{feature}"' in source
    assert "_toggle_runtime_feature" in source
    assert "set_runtime_statuses" in source
    assert "on_toggle_recording" in source


def test_current_banner_is_v09152():
    source = Path("src/main.py").read_text(encoding="utf-8")
    assert "V0.9.17.2.3 REPLAY RECORDING SELECTOR" in source
