"""V0.7 offline speech-to-text worker for completed PTT WAV captures."""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True, slots=True)
class STTConfig:
    enabled: bool = True
    model: str = "small.en"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "en"
    vad_filter: bool = False
    beam_size: int = 1
    fast_ptt: bool = True
    initial_prompt: str = (
        "Formula 1 race engineer radio. Driver may ask: tyres, tyre wear, tyre temperatures, "
        "brakes, brake temperatures, fuel, ERS, DRS, S Mode, gap ahead, gap behind, damage, "
        "weather, penalties, track limits, pit, box, wing, setup, lap time, position, safety car, "
        "engine, engine temperature, engine wear, gearbox, current lap, laps remaining, laps completed, "
        "sector, gap to leader, driver ahead, driver behind, tyre compound, tyre age, tyre set, DRS, "
        "active aero, overtake mode, pit speed limit, pit stops, track temperature, air temperature, "
        "rain chance, speed, RPM, gear, fuel mix, ERS harvest, grid position, strategy update, stint pace, compare stint pace, traffic, rejoin traffic, undercut, overcut, tyre life, fuel margin."
    )
    hotwords: str = (
        "tyres tyre wear tyre temperatures brakes brake temperatures fuel ERS DRS S Mode "
        "gap ahead gap behind damage weather penalties track limits pit box wing setup "
        "lap time position safety car VSC undercut overcut engine engine temperature engine wear gearbox "
        "current lap laps remaining laps completed sector gap leader driver ahead driver behind tyre compound "
        "tyre age tyre set DRS active aero overtake mode pit speed limit pit stops track temperature air temperature "
        "rain chance speed RPM gear fuel mix ERS harvest grid position strategy update stint pace compare stint pace traffic rejoin traffic undercut overcut tyre life fuel margin"
    )


class SpeechToText:
    """Load faster-whisper once and transcribe WAVs away from telemetry/HID threads."""

    def __init__(self, config: STTConfig, on_transcript: Callable[[str, Path], None] | None = None,
                 model_factory=None, on_complete=None) -> None:
        self.config = config
        self.on_transcript = on_transcript
        self._model_factory = model_factory
        self.on_complete = on_complete
        self._queue: queue.Queue[Path | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_transcript: str | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        if not self.config.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="race-engineer-stt", daemon=True)
        self._thread.start()

    def submit(self, wav_path: str | Path) -> None:
        if self.config.enabled and not self._stop.is_set():
            self._queue.put(Path(wav_path))

    def close(self, *, wait: bool = True) -> None:
        self._stop.set()
        if self._thread is not None:
            self._queue.put(None)
            if wait:
                self._thread.join(timeout=5.0)

    def _make_model(self):
        if self._model_factory is not None:
            return self._model_factory(self.config.model, device=self.config.device,
                                       compute_type=self.config.compute_type)
        from faster_whisper import WhisperModel
        return WhisperModel(self.config.model, device=self.config.device,
                            compute_type=self.config.compute_type)

    def _run(self) -> None:
        try:
            print(f"[STT] Loading offline model {self.config.model}...", flush=True)
            model = self._make_model()
            print("[STT] Ready.", flush=True)
        except Exception as error:
            self.last_error = str(error)
            print(f"[STT] Disabled: failed to load model: {error}", flush=True)
            if self.on_complete is not None:
                self.on_complete(None)
            return

        while not self._stop.is_set():
            wav_path = self._queue.get()
            if wav_path is None:
                break
            try:
                print(f"[STT] Transcribing: {wav_path}", flush=True)
                transcribe_started = time.perf_counter()
                kwargs = dict(
                    language=self.config.language,
                    vad_filter=False if self.config.fast_ptt else self.config.vad_filter,
                    beam_size=1 if self.config.fast_ptt else self.config.beam_size,
                    without_timestamps=True if self.config.fast_ptt else False,
                    temperature=0.0,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.60,
                    log_prob_threshold=-1.0,
                    compression_ratio_threshold=2.4,
                    initial_prompt=self.config.initial_prompt,
                    hotwords=self.config.hotwords,
                    vad_parameters={
                        "threshold": 0.35,
                        "min_speech_duration_ms": 100,
                        "min_silence_duration_ms": 180,
                        "speech_pad_ms": 220,
                    },
                )
                try:
                    segments, _info = model.transcribe(str(wav_path), **kwargs)
                except TypeError:
                    # Compatibility with older faster-whisper builds / test fakes.
                    kwargs.pop("hotwords", None)
                    kwargs.pop("vad_parameters", None)
                    kwargs.pop("no_speech_threshold", None)
                    kwargs.pop("log_prob_threshold", None)
                    kwargs.pop("compression_ratio_threshold", None)
                    try:
                        segments, _info = model.transcribe(str(wav_path), **kwargs)
                    except TypeError:
                        segments, _info = model.transcribe(
                            str(wav_path), language=self.config.language,
                            vad_filter=self.config.vad_filter,
                        )
                elapsed_ms = (time.perf_counter() - transcribe_started) * 1000.0
                transcript = " ".join(
                    segment.text.strip() for segment in segments if segment.text.strip()
                ).strip()
                self.last_transcript = transcript
                print(f"[STT] Latency {elapsed_ms:.0f} ms ({'fast PTT' if self.config.fast_ptt else 'quality mode'})", flush=True)
                if transcript:
                    print(f'[STT] "{transcript}"', flush=True)
                    if self.on_transcript is not None:
                        self.on_transcript(transcript, wav_path)
                else:
                    print("[STT] No speech recognized.", flush=True)
            except Exception as error:
                self.last_error = str(error)
                print(f"[STT] Transcription error: {error}", flush=True)
            finally:
                if self.on_complete is not None:
                    self.on_complete(wav_path)
