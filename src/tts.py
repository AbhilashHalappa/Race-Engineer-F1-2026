"""Offline text-to-speech output for V0.5.

Primary backend: Piper neural TTS with a local ONNX voice loaded once in the
speech worker. Piper mode is voice-locked: failures are logged and skipped, never
silently switched to a different Windows voice.
Telemetry never waits for synthesis or playback.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from queue import Empty, Full, PriorityQueue
import subprocess
import sys
import tempfile
import threading
import time
import wave
from typing import Iterable, Any

from .engineer.models import EngineerMessage, Priority, estimate_speech_duration_s
from .speech_quality import PronunciationDictionary, prepare_spoken_text


@dataclass(frozen=True, slots=True)
class TTSConfig:
    enabled: bool = True
    backend: str = "piper"
    model_path: str = "voices/en_GB-alan-medium.onnx"
    length_scale: float = 0.82
    volume: int = 100
    fallback_voice: str = "Microsoft Hazel Desktop"
    fallback_rate: int = 3
    max_queue: int = 64
    information_max_age_s: float = 3.0
    strategy_max_age_s: float = 5.0
    critical_max_age_s: float = 2.0
    static_prompt_cache: bool = True
    static_prompt_cache_dir: str = "logs/tts_cache"
    output_device: int | None = None

    def __post_init__(self) -> None:
        if self.backend not in {"piper", "windows"}:
            raise ValueError("TTS backend must be 'piper' or 'windows'")
        if not 0.5 <= self.length_scale <= 2.0:
            raise ValueError("Piper length_scale must be between 0.5 and 2.0")
        if not 0 <= self.volume <= 100:
            raise ValueError("TTS volume must be between 0 and 100")
        if not -10 <= self.fallback_rate <= 10:
            raise ValueError("Windows fallback rate must be between -10 and 10")
        if self.max_queue < 1:
            raise ValueError("TTS max_queue must be positive")
        if min(self.information_max_age_s, self.strategy_max_age_s, self.critical_max_age_s) <= 0:
            raise ValueError("TTS message ages must be positive")


class SpeechOutput:
    """Non-blocking priority speech queue with real-time pre-emption."""

    _STOP = object()
    _CACHEABLE_TEXTS = frozenset({
        "Track limits.", "DRS.", "S Mode.", "Overtake available.",
        "Safety Car deployed.", "Virtual Safety Car deployed.",
        "Blue flag. A faster car is approaching.",
        "Yellow flag ahead. Be prepared to slow down.",
        "Yellow flag. Slow down and be prepared to avoid an incident.",
        "Green flag. Track is clear.",
    })

    def __init__(self, config: TTSConfig | None = None, *, latency_monitor=None, on_audio_start=None, on_delivery_event=None) -> None:
        self.config = config or TTSConfig()
        self.latency_monitor = latency_monitor
        self.on_audio_start = on_audio_start
        self.on_delivery_event = on_delivery_event
        self.available = bool(self.config.enabled and sys.platform == "win32")
        self.backend = "disabled" if not self.available else self.config.backend
        self.last_error: str | None = None
        self.spoken_count = 0
        self.dropped_count = 0
        self.stale_count = 0
        self.superseded_count = 0
        self._queue: PriorityQueue[tuple[int, int, object]] = PriorityQueue(self.config.max_queue)
        self._sequence = 0
        self._closed = False
        self._latest_generation: dict[str, int] = {}
        self._generation = 0
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._listening = threading.Event()
        self._speech_epoch = 0
        # V1.3.0.3: once STT has produced a driver question, reserve the radio
        # until that answer has finished. This prevents CORNER COACH from occupying
        # the worker between transcript handling and the queued voice response.
        self._driver_response_pending = threading.Event()
        self._process_lock = threading.Lock()
        self._play_process = None
        self._playback_interrupted = threading.Event()
        self._current_rank: int | None = None
        self._current_key: str | None = None
        self._current_cancel_event: threading.Event | None = None
        self._current_enqueued_ns: int | None = None
        self._current_message: EngineerMessage | None = None
        self._current_audio_notified = False
        self._current_expected_end_at: float | None = None
        self._current_exact_duration_s: float | None = None
        self._current_delivery_event_notified: set[str] = set()
        self._native_playback_active = threading.Event()
        self._automatic_engineer_enabled = True
        # Independent runtime gates for message families. This keeps CORNER COACH
        # speech independent from the Race Engineer master switch and lets PRE/POST
        # be cancelled immediately even when a line is already queued.
        self._message_prefix_enabled: dict[str, bool] = {}
        self._sd_stream = None
        self._piper_voice: Any = None
        self._piper_config_type: Any = None
        self._pronunciation = PronunciationDictionary()
        if self.available:
            self._thread = threading.Thread(target=self._worker, name="race-engineer-tts", daemon=True)
            self._thread.start()


    @staticmethod
    def _is_automatic_engineer_message(message: EngineerMessage) -> bool:
        """Return True only for automatic Race Engineer chatter.

        CORNER COACH is an independent radio producer. Its ``corner:*`` keys must
        never be muted by the Race Engineer ENGR switch.
        """
        key = str(getattr(message, "key", "") or "")
        # Driver-requested PTT answers, legacy coach/performance messages and
        # CORNER COACH are not classified as AutomaticEngineer chatter here.
        # RaceStateReceiver owns the higher-level Race Engineer master gate; the
        # explicit ``corner:*`` exclusion is what keeps CORNER COACH independent.
        if (key == "voice:response" or key.startswith("coach:")
                or key.startswith("performance:") or key.startswith("corner:")):
            return False
        return True

    def _message_family_enabled(self, message: EngineerMessage) -> bool:
        key = str(getattr(message, "key", "") or "")
        with self._lock:
            gates = tuple(self._message_prefix_enabled.items())
        # Every matching gate must be enabled. This allows ``corner:`` to be ON
        # while ``corner:post:`` remains OFF.
        return all(enabled for prefix, enabled in gates if key.startswith(prefix))

    def set_message_prefix_enabled(self, prefix: str, enabled: bool) -> tuple[bool, str]:
        """Enable/disable one radio family and stop a matching line immediately."""
        prefix = str(prefix or "")
        if not prefix:
            return False, "Message prefix is required"
        enabled = bool(enabled)
        with self._lock:
            self._message_prefix_enabled[prefix] = enabled
            current = self._current_message
        if not enabled and current is not None and str(getattr(current, "key", "") or "").startswith(prefix):
            self._notify_delivery(current, "FAMILY_DISABLED_DURING_AUDIO", disabled_prefix=prefix)
            self._stop_current_playback()
        return True, "Enabled" if enabled else "Disabled"

    def set_automatic_engineer_enabled(self, enabled: bool) -> tuple[bool, str]:
        """Mute/unmute automatic engineer speech without muting coach or PTT answers."""
        enabled = bool(enabled)
        self._automatic_engineer_enabled = enabled
        if not enabled:
            with self._lock:
                current = self._current_message
            if current is not None and self._is_automatic_engineer_message(current):
                self._stop_current_playback()
        return True, "Enabled" if enabled else "Disabled"

    @staticmethod
    def _is_corner_pre(message: EngineerMessage | None) -> bool:
        return bool(message is not None and str(getattr(message, "key", "") or "").startswith("corner:pre:"))

    @staticmethod
    def _is_corner_post(message: EngineerMessage | None) -> bool:
        return bool(message is not None and str(getattr(message, "key", "") or "").startswith("corner:post:"))

    def _estimated_duration(self, message: EngineerMessage) -> float:
        supplied = getattr(message, "estimated_duration_s", None)
        if isinstance(supplied, (int, float)) and supplied > 0:
            base = float(supplied)
        else:
            base = estimate_speech_duration_s(message.text)
        # Corner-coach estimates are authored for the project's normal 0.82 Piper
        # length scale.  Respect slower/faster runtime voice settings conservatively.
        if self.config.backend == "piper":
            base *= max(0.60, float(self.config.length_scale) / 0.82)
        return max(0.35, base)

    @staticmethod
    def _deadline(message: EngineerMessage | None) -> float | None:
        value = getattr(message, "deadline_at_monotonic_s", None) if message is not None else None
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
        return None

    def _notify_delivery(self, message: EngineerMessage | None, outcome: str, **details) -> None:
        if message is None or not str(getattr(message, "key", "") or "").startswith("corner:"):
            return
        terminal = {
            "PRE_STALE_AT_ENTRY", "PRE_NO_AIRTIME", "POST_NO_AIRTIME",
            "DEADLINE_REACHED_DURING_AUDIO", "POST_PREEMPTED_FOR_PRE",
            "PRE_PREEMPTED_FOR_NEXT_PRE", "PRE_PREEMPTED_BY_HIGHER_PRIORITY",
            "POST_PREEMPTED_BY_HIGHER_PRIORITY", "FAMILY_DISABLED_DURING_AUDIO",
            "PREEMPTED_FOR_PTT", "SPOKEN_COMPLETE", "PLAYBACK_SKIPPED",
        }
        if str(outcome) in terminal:
            with self._lock:
                if message is self._current_message:
                    self._current_delivery_event_notified.add(str(outcome))
        callback = self.on_delivery_event
        if callback is None:
            return
        try:
            callback(message, str(outcome), details)
        except Exception as error:
            print(f"[CORNER COACH] delivery callback error: {error}", flush=True)

    def _deadline_allows(self, message: EngineerMessage, duration_s: float, *, margin_s: float = 0.12) -> bool:
        deadline = self._deadline(message)
        if deadline is None:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            self._notify_delivery(message, "PRE_STALE_AT_ENTRY" if self._is_corner_pre(message) else "POST_NO_AIRTIME", remaining_s=remaining, required_s=duration_s)
            return False
        if remaining + 1e-9 < float(duration_s) + float(margin_s):
            self._notify_delivery(message, "PRE_NO_AIRTIME" if self._is_corner_pre(message) else "POST_NO_AIRTIME", remaining_s=remaining, required_s=duration_s, margin_s=margin_s)
            return False
        return True

    def _current_deadline_expired(self) -> bool:
        with self._lock:
            message = self._current_message
        deadline = self._deadline(message)
        return bool(deadline is not None and time.monotonic() >= deadline)

    def _should_preempt_current(self, incoming: EngineerMessage, incoming_rank: int) -> tuple[bool, str | None, dict[str, float]]:
        """Return whether an incoming line should interrupt current playback.

        V1.1.0.15 keeps CORNER COACH a strict single-channel sequencer.  A POST
        may finish only when it still leaves enough airtime for the upcoming PRE.
        The same rule also applies PRE->PRE on tightly packed corners: an older PRE
        may finish only if the newer PRE can still finish before its own corner.
        """
        with self._lock:
            current_rank = self._current_rank
            current = self._current_message
            expected_end = self._current_expected_end_at
        if current_rank is None or current is None:
            return False, None, {}

        incoming_pre = self._is_corner_pre(incoming)
        current_pre = self._is_corner_pre(current)
        current_post = self._is_corner_post(current)
        if incoming_pre and (current_post or current_pre):
            deadline = self._deadline(incoming)
            if deadline is not None:
                now = time.monotonic()
                current_end = float(expected_end) if isinstance(expected_end, (int, float)) else now + self._estimated_duration(current)
                pre_duration = self._estimated_duration(incoming)
                finish_both = current_end + 0.18 + pre_duration
                details = {
                    "current_remaining_s": max(0.0, current_end - now),
                    "pre_required_s": pre_duration,
                    "pre_deadline_in_s": max(0.0, deadline - now),
                }
                if finish_both <= deadline:
                    outcome = "POST_FINISH_ALLOWED_BEFORE_PRE" if current_post else "PRE_FINISH_ALLOWED_BEFORE_NEXT_PRE"
                    return False, outcome, details
                outcome = "POST_PREEMPTED_FOR_PRE" if current_post else "PRE_PREEMPTED_FOR_NEXT_PRE"
                return True, outcome, details

        if incoming_rank >= current_rank:
            return False, None, {}
        return True, None, {}

    def submit(self, messages: Iterable[EngineerMessage]) -> None:
        if not self.available or self._closed:
            return
        for message in sorted(messages, key=self._radio_rank):
            # While an explicit driver answer owns the channel, do not let fresh
            # CORNER COACH/routine chatter occupy the worker ahead of it. Critical
            # safety traffic is retained in the queue and will follow the answer.
            if self._driver_response_pending.is_set() and message.key != "voice:response":
                if str(message.key).startswith("corner:") or int(message.priority) >= int(Priority.STRATEGY):
                    self.superseded_count += 1
                    self._notify_delivery(message, "PREEMPTED_FOR_PTT")
                    continue
            # CORNER COACH can deliberately publish a visual-only result when a
            # POST cannot safely fit before the next PRE.  The receiver records
            # it in the dedicated transcript before submit(); it must never enter
            # the TTS queue.
            if getattr(message, "speak", True) is False:
                self._notify_delivery(message, "VISUAL_ONLY")
                continue
            if (not self._automatic_engineer_enabled) and self._is_automatic_engineer_message(message):
                continue
            if not self._message_family_enabled(message):
                continue
            self._sequence += 1
            family = self._replaceable_family(message.key)
            generation = 0
            if family is not None:
                with self._lock:
                    self._generation += 1
                    generation = self._generation
                    self._latest_generation[family] = generation
            with self._lock:
                epoch = self._speech_epoch
            enqueued_ns = time.perf_counter_ns()
            try:
                rank = self._radio_rank(message)
                self._queue.put_nowait((rank, self._sequence, (message, family, generation, epoch, enqueued_ns)))
                monitor = self.latency_monitor
                if monitor is not None:
                    monitor.radio_queued(self._queue.qsize())

                # V0.9.14.0 pre-empts synthesis as well as playback. Previously a
                # critical call arriving while Piper was rendering an old sentence
                # had to wait for that synthesis to finish before it could take the
                # radio, even though playback had not started yet.
                with self._lock:
                    current_rank = self._current_rank
                    current_cancel = self._current_cancel_event
                    current_message = self._current_message
                should_consider = (
                    current_rank is not None
                    and (rank < current_rank or (self._is_corner_pre(message) and self._is_corner_pre(current_message)))
                )
                if should_consider:
                    preempt, outcome, details = self._should_preempt_current(message, rank)
                    if outcome is not None and current_message is not None:
                        self._notify_delivery(current_message, outcome, incoming_key=message.key, **details)
                    if preempt:
                        if outcome is None and current_message is not None and str(getattr(current_message, "key", "")).startswith("corner:"):
                            family = "PRE" if self._is_corner_pre(current_message) else "POST"
                            self._notify_delivery(
                                current_message, f"{family}_PREEMPTED_BY_HIGHER_PRIORITY",
                                incoming_key=message.key, incoming_rank=rank, current_rank=current_rank,
                            )
                        if current_cancel is not None:
                            current_cancel.set()
                        if monitor is not None:
                            monitor.preempted()
                        self._stop_current_playback()
            except Full:
                self.dropped_count += 1
                self._notify_delivery(message, "QUEUE_FULL")

    @staticmethod
    def _radio_rank(message: EngineerMessage) -> int:
        """Radio scheduling rank; lower is spoken first.

        The V0.9.3 track-limit cue is intentionally the one automatic call that
        can beat/interupt a driver answer: it is useful only *on the spot*. Other
        driver-requested answers retain ownership ahead of ordinary critical calls,
        then assists, strategy, information and coaching follow.
        """
        if message.key == "voice:response":
            return -5
        if message.key == "track_limits":
            return -4
        # Safety-critical race engineer traffic still owns the radio. PRE coaching
        # is deliberately next: an approaching braking zone is time-sensitive and
        # may interrupt lap summaries, ordinary coaching, strategy/information and
        # assist chatter.  It never interrupts driver-requested answers, instant
        # track-limit cues, or CRITICAL safety messages.
        if int(message.priority) == 0:
            return -3
        if message.key.startswith(("coach:pre:", "corner:pre:")):
            return -2
        # CORNER COACH POST is still less urgent than PRE/critical traffic, but
        # it is more time-sensitive than ordinary assists/information/coaching.
        # Giving it a dedicated rank prevents a full corner-coach lap from
        # backing up behind routine radio chatter while preserving PRE ownership.
        if message.key.startswith("corner:post:"):
            return 0
        # G/L voice is useful but deliberately lower priority than PRE/POST and
        # safety/assist traffic. It should never steal the radio from a turn cue.
        if message.key.startswith("corner:gainloss:"):
            return 4
        # V0.9.20.3.1: the automatic 2026 S-Mode reminder is routine
        # coaching chatter, not a safety/strategy assist. It must never pre-empt
        # or suppress a post-corner correction. DRS/ERS assist reminders retain
        # their existing higher radio rank.
        if message.key == "assist:s_mode":
            return 5
        if message.key.startswith("assist:"):
            return 1
        if int(message.priority) == 1:
            return 2
        if int(message.priority) == 2:
            return 3
        return 4

    def begin_listening(self) -> None:
        """Give PTT the radio: stop speech and invalidate queued non-critical chatter."""
        if not self.available or self._closed:
            return
        self._listening.set()
        with self._lock:
            self._speech_epoch += 1
            current = self._current_message
        if current is not None and str(getattr(current, "key", "") or "").startswith("corner:"):
            self._notify_delivery(current, "PREEMPTED_FOR_PTT")
        self._stop_current_playback()

    def prepare_radio_response(self) -> None:
        """Reserve the radio for the driver's requested answer.

        A PTT question is explicit user input, so its answer must outrank CORNER
        COACH and routine Race Engineer traffic. Incrementing the epoch invalidates
        already-queued chatter; the pending flag prevents fresh coaching from
        refilling the channel before the answer has finished.
        """
        self._driver_response_pending.set()
        with self._lock:
            self._speech_epoch += 1
            current = self._current_message
        if current is not None and str(getattr(current, "key", "") or "") != "voice:response":
            self._stop_current_playback()

    def driver_response_pending(self) -> bool:
        return self._driver_response_pending.is_set()

    def cancel_driver_response(self) -> None:
        """Release a pending driver-answer reservation when no answer can be queued."""
        self._driver_response_pending.clear()

    def end_listening(self) -> None:
        self._listening.clear()

    def set_output_device(self, device: int | None) -> tuple[bool, str]:
        """Select output device for subsequent radio lines."""
        from dataclasses import replace
        self._stop_current_playback()
        self.config = replace(self.config, output_device=device)
        return True, "System default" if device is None else f"Device {device}"

    def _stop_current_playback(self) -> None:
        with self._lock:
            cancel = self._current_cancel_event
        if cancel is not None:
            cancel.set()
        if self._native_playback_active.is_set():
            self._playback_interrupted.set()
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except (ImportError, RuntimeError):
                pass
        stream = self._sd_stream
        if stream is not None:
            self._playback_interrupted.set()
            try:
                stream.abort()
            except Exception:
                pass
        with self._process_lock:
            proc = self._play_process
        if proc is not None and proc.poll() is None:
            self._playback_interrupted.set()
            try:
                proc.terminate()
            except OSError:
                pass

    def close(self, *, wait: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        if self._thread is None:
            return
        try:
            self._queue.put_nowait((99, self._sequence + 1, self._STOP))
        except Full:
            pass
        if wait:
            self._thread.join(timeout=8.0)

    def _worker(self) -> None:
        if self.config.backend == "piper":
            self._load_piper()
        while True:
            try:
                _, _, item = self._queue.get(timeout=0.25)
            except Empty:
                if self._closed:
                    return
                continue
            try:
                if item is self._STOP:
                    return
                message, family, generation, epoch, enqueued_ns = item
                assert isinstance(message, EngineerMessage)
                if not self._message_family_enabled(message):
                    self.superseded_count += 1
                    self._notify_delivery(message, "FAMILY_DISABLED")
                    continue
                if (not self._automatic_engineer_enabled) and self._is_automatic_engineer_message(message):
                    self.superseded_count += 1
                    self._notify_delivery(message, "ENGINEER_DISABLED")
                    continue
                with self._lock:
                    current_epoch = self._speech_epoch
                if int(message.priority) != 0 and epoch != current_epoch:
                    self.superseded_count += 1
                    self._notify_delivery(message, "RADIO_EPOCH_INVALIDATED")
                    continue
                while self._listening.is_set() and not self._closed:
                    time.sleep(0.005)
                # The worker may have popped a coaching item while PTT was held.
                # STT can then invalidate that item and enqueue a higher-priority
                # driver answer while this worker is waiting. Re-check the epoch
                # after listening ends so the stale popped item cannot speak first.
                with self._lock:
                    current_epoch = self._speech_epoch
                if int(message.priority) != 0 and epoch != current_epoch:
                    self.superseded_count += 1
                    self._notify_delivery(message, "RADIO_EPOCH_INVALIDATED")
                    continue
                if family is not None:
                    with self._lock:
                        latest = self._latest_generation.get(family)
                    if latest != generation:
                        self.superseded_count += 1
                        self._notify_delivery(message, "SUPERSEDED")
                        continue
                if self._is_stale(message):
                    self.stale_count += 1
                    self._notify_delivery(message, "PRE_STALE_AT_ENTRY" if self._is_corner_pre(message) else ("POST_NO_AIRTIME" if self._is_corner_post(message) else "QUEUE_STALE"))
                    continue
                estimated = self._estimated_duration(message)
                if not self._deadline_allows(message, estimated):
                    self.stale_count += 1
                    continue

                cancel_event = threading.Event()
                with self._lock:
                    self._current_rank = self._radio_rank(message)
                    self._current_key = message.key
                    self._current_cancel_event = cancel_event
                    self._current_enqueued_ns = enqueued_ns
                    self._current_message = message
                    self._current_audio_notified = False
                    self._current_exact_duration_s = None
                    self._current_expected_end_at = time.monotonic() + estimated + (0.25 if self.config.backend == "piper" else 0.10)
                    self._current_delivery_event_notified = set()
                monitor = self.latency_monitor
                if monitor is not None:
                    monitor.radio_dequeued(time.perf_counter_ns() - enqueued_ns, self._queue.qsize())
                try:
                    spoken = self._speak(prepare_spoken_text(self._pronunciation.apply(message.text)))
                    if spoken:
                        self._notify_delivery(message, "SPOKEN_COMPLETE")
                    elif not cancel_event.is_set() and not self._listening.is_set():
                        with self._lock:
                            terminal_already = bool(self._current_delivery_event_notified)
                        if not terminal_already:
                            self._notify_delivery(message, "PLAYBACK_SKIPPED")
                finally:
                    if message.key == "voice:response":
                        self._driver_response_pending.clear()
                    with self._lock:
                        self._current_rank = None
                        self._current_key = None
                        self._current_cancel_event = None
                        self._current_enqueued_ns = None
                        self._current_message = None
                        self._current_audio_notified = False
                        self._current_expected_end_at = None
                        self._current_exact_duration_s = None
                        self._current_delivery_event_notified = set()
            finally:
                self._queue.task_done()


    @staticmethod
    def _replaceable_family(key: str) -> str | None:
        """Return the live-state family whose older queued calls are obsolete.

        Event-like calls (pit entry/exit, tyre fitted, faults, lap completion,
        safety car) intentionally return None and retain their place in the queue.
        """
        if key == "position":
            return "position"
        if key.startswith("fuel:"):
            return "fuel"
        if key == "weather" or key.startswith("forecast:"):
            return "weather"
        if key.startswith("front_wing:"):
            return "front_wing"
        if key.startswith("tyre_damage:"):
            return "tyre_damage"
        if key.startswith("tyre_temp:"):
            return "tyre_temp"
        if key.startswith("brake_temp:"):
            return "brake_temp"
        if key.startswith("engine_temp:"):
            return "engine_temp"
        if key.startswith("blisters:"):
            return "blisters"
        if key.startswith("brakes:"):
            return "brake_damage"
        if key.startswith(("rear_wing:", "floor:", "diffuser:", "sidepod:", "engine:", "gearbox:")):
            return key.split(":", 1)[0]
        if key.startswith("wear:"):
            return "tyre_wear"
        if key == "penalty:time":
            return "penalty_time"
        if key.startswith("assist:"):
            return key
        # Only the newest queued correction for a physical corner remains useful.
        # Critical/strategy traffic still pre-empts coaching through radio rank.
        if key.startswith("coach:corner:"):
            parts = key.split(":")
            return ":".join(parts[:3]) if len(parts) >= 3 else "coach:corner"
        if key.startswith("coach:pre:"):
            parts = key.split(":")
            # Only the newest reminder for a corner is useful.
            return f"coach:pre:{parts[3]}" if len(parts) >= 4 else "coach:pre"
        if key.startswith("corner:pre:"):
            parts = key.split(":")
            # corner:pre:<lap>:<zone>.  A newer lap's reminder for the same
            # CoachingZone supersedes any queued reminder from an older lap.
            return f"corner:pre:{parts[3]}" if len(parts) >= 4 else "corner:pre"
        if key.startswith("corner:post:"):
            parts = key.split(":")
            return f"corner:post:{parts[3]}" if len(parts) >= 4 else "corner:post"
        if key.startswith("corner:gainloss:"):
            parts = key.split(":")
            return f"corner:gainloss:{parts[3]}" if len(parts) >= 4 else "corner:gainloss"
        if key.startswith("coach:lap_summary:"):
            return "coach:lap_summary"
        if key.startswith("coach:positive:"):
            parts = key.split(":")
            return f"coach:positive:{parts[-1]}" if len(parts) >= 4 else "coach:positive"
        if key == "flag:local":
            return "flag:local"
        return None

    def _is_stale(self, message: EngineerMessage) -> bool:
        # CORNER COACH carries an explicit finish deadline.  Do not apply the old
        # 1.5 s queue-age rule to a PRE that still has enough real airtime; the
        # duration/deadline gate below is the authoritative validity check.
        deadline = self._deadline(message)
        if deadline is not None and str(message.key).startswith("corner:"):
            return time.monotonic() >= deadline
        # created_at=0 is retained for synthetic/backward-compatible callers.
        if message.created_at <= 0:
            return False
        age = max(0.0, time.monotonic() - message.created_at)
        if message.key.startswith("coach:pre:"):
            limit = min(1.5, self.config.information_max_age_s)
        elif message.key.startswith("corner:pre:"):
            # Backward compatibility for old/synthetic corner messages without a
            # deadline.  New V1.1.0.15 PRE messages always carry one.
            limit = max(8.5, self.config.information_max_age_s)
        elif message.key.startswith("corner:post:"):
            limit = 4.5
        elif message.key.startswith("corner:gainloss:"):
            limit = 3.5
        elif int(message.priority) == 0:
            limit = self.config.critical_max_age_s
        elif int(message.priority) == 1:
            limit = self.config.strategy_max_age_s
        else:
            limit = self.config.information_max_age_s
        return age > limit

    def _load_piper(self) -> None:
        try:
            from piper import PiperVoice
            from piper.config import SynthesisConfig
            model = Path(self.config.model_path)
            if not model.is_absolute():
                model = Path.cwd() / model
            config = Path(str(model) + ".json")
            if not model.is_file() or not config.is_file():
                raise FileNotFoundError(f"Piper voice files not found: {model}")
            self._piper_voice = PiperVoice.load(model, config_path=config)
            self._piper_config_type = SynthesisConfig
            self.backend = "piper"
        except Exception as error:
            self.last_error = f"Piper unavailable: {error}"
            self.backend = "piper-unavailable"
            print(f"[TTS] Piper unavailable: {error}", flush=True)

    def _current_cancelled(self) -> bool:
        with self._lock:
            cancel = self._current_cancel_event
        return bool(cancel is not None and cancel.is_set())

    def _mark_audio_start(self) -> None:
        # This is the authoritative point for the radio transcript: the message
        # survived staleness/supersession checks and audio playback actually began.
        with self._lock:
            if self._current_audio_notified:
                return
            self._current_audio_notified = True
            enqueued_ns = self._current_enqueued_ns
            message = self._current_message
        monitor = self.latency_monitor
        if monitor is not None and enqueued_ns is not None:
            monitor.audio_started(time.perf_counter_ns() - enqueued_ns)
        callback = self.on_audio_start
        if callback is not None and message is not None:
            try:
                callback(message)
            except Exception as error:
                # Transcript/UI failures must never interrupt race radio audio.
                print(f"[RADIO TRANSCRIPT] callback error: {error}", flush=True)

    def _static_cache_path(self, text: str) -> Path | None:
        if not self.config.static_prompt_cache or text not in self._CACHEABLE_TEXTS:
            return None
        model = Path(self.config.model_path)
        if not model.is_absolute():
            model = Path.cwd() / model
        try:
            stat = model.stat()
            signature = f"{model}|{stat.st_size}|{stat.st_mtime_ns}"
        except OSError:
            signature = str(model)
        raw = f"{signature}|{self.config.length_scale}|{self.config.volume}|{text}".encode("utf-8")
        name = hashlib.sha1(raw).hexdigest() + ".wav"
        return Path(self.config.static_prompt_cache_dir) / name

    def _play_wav(self, wav_path: str | Path) -> bool:
        wav_path = str(wav_path)
        if self._current_cancelled() or self._listening.is_set():
            return False
        try:
            with wave.open(wav_path, "rb") as probe:
                rate = probe.getframerate() or 1
                duration = probe.getnframes() / rate
        except (OSError, wave.Error):
            duration = None
        with self._lock:
            message = self._current_message
            if duration is not None:
                self._current_exact_duration_s = float(duration)
                self._current_expected_end_at = time.monotonic() + float(duration)
        if message is not None and duration is not None and not self._deadline_allows(message, float(duration)):
            return False

        # An explicit endpoint needs PortAudio; system-default output retains the
        # lower-overhead winsound path below.
        if self.config.output_device is not None:
            try:
                import sounddevice as sd
                self._playback_interrupted.clear()
                with wave.open(wav_path, "rb") as src:
                    channels = src.getnchannels()
                    sample_width = src.getsampwidth()
                    samplerate = src.getframerate()
                    if sample_width != 2:
                        raise RuntimeError(f"Unsupported Piper WAV sample width: {sample_width}")
                    stream = sd.RawOutputStream(
                        samplerate=samplerate, channels=channels, dtype="int16",
                        device=self.config.output_device, blocksize=0,
                    )
                    self._sd_stream = stream
                    stream.start()
                    self._mark_audio_start()
                    chunk = max(256, int(samplerate * 0.02))
                    while True:
                        if self._closed or self._listening.is_set() or self._current_cancelled() or self._playback_interrupted.is_set() or self._current_deadline_expired():
                            if self._current_deadline_expired():
                                self._notify_delivery(self._current_message, "DEADLINE_REACHED_DURING_AUDIO")
                            stream.abort()
                            return False
                        payload = src.readframes(chunk)
                        if not payload:
                            break
                        stream.write(payload)
                    stream.stop()
                    return True
            except Exception as error:
                self.last_error = f"Selected audio output failed: {error}"
                print(f"[TTS] {self.last_error}; falling back to system default output.", flush=True)
            finally:
                self._sd_stream = None

        # On Windows, stdlib winsound avoids launching a fresh PowerShell/.NET
        # process for every radio line. That removes a sizeable and highly
        # variable startup delay from the packet->audio path while remaining
        # interruptible for PTT/critical pre-emption.
        if sys.platform == "win32":
            try:
                import winsound
                with wave.open(wav_path, "rb") as src:
                    rate = src.getframerate() or 1
                    duration = src.getnframes() / rate
                self._playback_interrupted.clear()
                self._native_playback_active.set()
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                self._mark_audio_start()
                deadline = time.monotonic() + duration + 0.05
                while time.monotonic() < deadline:
                    if self._closed or self._listening.is_set() or self._current_cancelled() or self._current_deadline_expired():
                        if self._current_deadline_expired():
                            self._notify_delivery(self._current_message, "DEADLINE_REACHED_DURING_AUDIO")
                        self._playback_interrupted.set()
                        winsound.PlaySound(None, 0)
                        return False
                    time.sleep(0.005)
                winsound.PlaySound(None, 0)
                return True
            except (ImportError, OSError, RuntimeError, wave.Error):
                # Retain the proven PowerShell SoundPlayer path as a fallback.
                pass
            finally:
                self._native_playback_active.clear()

        if self._current_cancelled() or self._listening.is_set():
            return False
        env = os.environ.copy()
        env["RACE_ENGINEER_WAV"] = wav_path
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$p=New-Object System.Media.SoundPlayer $env:RACE_ENGINEER_WAV; "
            "$p.PlaySync(); $p.Dispose()"
        )
        self._mark_audio_start()
        result = self._run_playback_process(script, env)
        if result.returncode:
            if self._listening.is_set() or self._playback_interrupted.is_set() or self._current_cancelled():
                return False
            raise RuntimeError((result.stderr or f"PowerShell exit {result.returncode}").strip())
        return True

    def _speak(self, text: str) -> bool:
        # Explicit Windows mode remains available for diagnostics, but Piper mode
        # NEVER falls back to another voice.
        if self.config.backend == "piper":
            if self._piper_voice is None:
                self.last_error = self.last_error or "Piper voice is unavailable"
                print(f"[TTS] Message skipped; Piper voice unavailable: {self.last_error}", flush=True)
                return False
            try:
                played = bool(self._speak_piper(text))
                if played:
                    self.spoken_count += 1
                return played
            except Exception as error:
                self.last_error = f"Piper failed: {error}"
                print(f"[TTS] {self.last_error}", flush=True)
                print("[TTS] Message skipped; Windows fallback disabled.", flush=True)
                return False
        played = bool(self._speak_windows(text))
        if played:
            self.spoken_count += 1
        else:
            self.available = False
        return played

    def _speak_piper(self, text: str) -> bool:
        cache_path = self._static_cache_path(text)
        if cache_path is not None and cache_path.is_file():
            return self._play_wav(cache_path)

        fd, wav_path = tempfile.mkstemp(prefix="race_engineer_", suffix=".wav")
        os.close(fd)
        play_path: Path | str = wav_path
        try:
            syn = self._piper_config_type(
                length_scale=self.config.length_scale,
                volume=self.config.volume / 100.0,
            )
            with wave.open(wav_path, "wb") as wav_file:
                self._piper_voice.synthesize_wav(text, wav_file, syn_config=syn)

            # A higher-priority message may have arrived while Piper was rendering.
            # Do not start obsolete audio; the urgent message is already next.
            if self._current_cancelled() or self._listening.is_set():
                return False

            if cache_path is not None:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(wav_path, cache_path)
                    play_path = cache_path
                    wav_path = ""
                except OSError:
                    play_path = wav_path
            return self._play_wav(play_path)
        finally:
            if wav_path:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass


    def _run_playback_process(self, script: str, env: dict[str, str]):
        """Run interruptible Windows playback so PTT can immediately take the radio."""
        self._playback_interrupted.clear()
        proc = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        with self._process_lock:
            self._play_process = proc
        try:
            try:
                _stdout, stderr = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                _stdout, stderr = proc.communicate()
                raise RuntimeError("TTS playback timed out")
            class Result:
                pass
            result = Result()
            result.returncode = proc.returncode
            result.stderr = stderr or ""
            return result
        finally:
            with self._process_lock:
                if self._play_process is proc:
                    self._play_process = None

    def _speak_windows(self, text: str) -> bool:
        env = os.environ.copy()
        env["RACE_ENGINEER_TTS_TEXT"] = text
        env["RACE_ENGINEER_TTS_RATE"] = str(self.config.fallback_rate)
        env["RACE_ENGINEER_TTS_VOLUME"] = str(self.config.volume)
        env["RACE_ENGINEER_TTS_VOICE"] = self.config.fallback_voice
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Rate=[int]$env:RACE_ENGINEER_TTS_RATE; $s.Volume=[int]$env:RACE_ENGINEER_TTS_VOLUME; "
            "if($env:RACE_ENGINEER_TTS_VOICE){try{$s.SelectVoice($env:RACE_ENGINEER_TTS_VOICE)}catch{}}; "
            "$s.Speak($env:RACE_ENGINEER_TTS_TEXT); $s.Dispose()"
        )
        try:
            if self._current_cancelled():
                return True
            self._mark_audio_start()
            result = self._run_playback_process(script, env)
            if result.returncode:
                if self._listening.is_set() or self._current_cancelled():
                    return True
                self.last_error = (result.stderr or f"PowerShell exit {result.returncode}").strip()
                return False
            return True
        except (OSError, subprocess.SubprocessError) as error:
            self.last_error = str(error)
            return False
