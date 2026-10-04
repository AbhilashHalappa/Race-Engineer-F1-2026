"""Connect V0.2 diagnostics to selected body decoding and normalized state."""

from collections import Counter
from dataclasses import replace
import threading
import queue
from types import SimpleNamespace

from .capture import PacketCapture
from .telemetry.header import InvalidHeader
from .telemetry.binary import MalformedPacket, UnsupportedPacket
from .telemetry.decoders import decode_packet
from .telemetry_receiver import TelemetryReceiver
from .race_state.engine import RaceStateEngine, CATEGORIES
from .race_state.formatter import format_state
from .engineer import AutomaticEngineer
from .engineer.formatter import format_messages
from .tts import SpeechOutput, TTSConfig
from .ptt import PTTConfig, PTTController
from .stt import STTConfig, SpeechToText
from .voice_commands import handle_voice_request, VoiceIntent, normalize_radio_text, is_likely_stt_hallucination
from .radio_controls import parse_runtime_radio_command, CONTROL_LABELS
from .speech_quality import concise_engineer_text, load_speech_preferences, save_speech_preferences
from .llm_engineer import LLMConfig, LocalLLMEngineer
from .pit_strategy import format_pit_fallback, assess_pit, service_plan
from .telemetry_recording import AsyncTelemetrySessionRecorder, replay_into
from .engineer.models import EngineerMessage, Priority
from .latency import LatencyMonitor
from .radio_transcript import RadioTranscriptStore
from .validation_transcript import ValidationTranscriptWriter
from .validation_bundle import ValidationBundleManager
from .runtime_validation import RuntimeBenchmarkMonitor
from .session_summary import SessionSummaryTracker, save_summary
from .wheel_telemetry import WheelTelemetryBridge
from .ai_benchmark import AIBenchmarkCapture
from .rival_benchmark import TimeTrialRivalCapture
from .coaching_live import IntegratedLiveCoach
from .corner_coach import CornerCoachEngine
from .session_coach_report import build_coach_report, save_coach_report
from .driver_history import DriverHistory
from .performance_history import PerformanceHistoryStore, driver_profile_from_state
from .driving_time import F1DrivingTimeTracker


def persistent_history_allowed(mode: str) -> bool:
    """Only live game telemetry may mutate persistent driver performance history."""
    return str(mode or "").lower() == "live"

from .session_library import SessionLibrary
from .advanced_race_strategy import assess_advanced_strategy, arbitrate_messages
from .race_context import RaceContextHysteresis
from .strategy_learning import StrategyEvidenceLearner
import copy
import pickle
import time
from pathlib import Path


class RaceStateReceiver(TelemetryReceiver):
    def __init__(self, host='0.0.0.0', port=20777, *, show_sizes=False,
                 packet_stats=False, capture_packets=0, engineer_only=False,
                 tts_enabled=True, tts_backend="piper", tts_model="voices/en_GB-alan-medium.onnx", tts_speed=0.82, tts_volume=100, audio_device=None,
                 ers_assist=True, drs_s_mode_assist=True, position_updates=False, ptt_config=None, stt_config=None, llm_config=None,
                 record_telemetry=False, recording_path=None, latency_stats=False, wheel_telemetry=True, wheel_port=None,
                 ai_reference=False, ai_reference_output=None, ai_reference_min_difficulty=0, rival_reference=False, rival_reference_output=None) -> None:
        super().__init__(host, port, show_sizes=show_sizes)
        # V2.9.1.2 S13: the decoded Race Engineer pipeline is intentionally more
        # expensive than raw UDP ingestion. Drain the socket first and coalesce
        # only duplicate high-rate state families so UI/state always converges to
        # the newest F1 frame instead of accumulating a seconds-long kernel queue.
        # LapData (packet 2) is deliberately NOT coalesced: measured-performance
        # distance sampling depends on its continuous lap-distance progression.
        # Low-rate session/event/status/damage/history evidence is never dropped.
        self.coalesce_live_udp = True
        self.coalesce_packet_ids = frozenset({0, 6, 13, 15, 16})
        self.engine = RaceStateEngine()
        self.automatic_engineer = AutomaticEngineer(ers_assist=ers_assist, drs_s_mode_assist=drs_s_mode_assist, position_updates=position_updates)
        self.engineer_only = engineer_only
        self.latency_stats = bool(latency_stats)
        self.latency = LatencyMonitor()
        self.radio_transcript = RadioTranscriptStore(max_entries=200)
        self.corner_transcript = RadioTranscriptStore(max_entries=120)
        self.validation_transcript = ValidationTranscriptWriter()
        self.validation_bundle = ValidationBundleManager()
        self.runtime_benchmark = RuntimeBenchmarkMonitor()
        self._last_reference_validation_stamp = None
        self._last_validation_bundle = None
        self._last_runtime_session_uid = None
        self.session_summary_tracker = SessionSummaryTracker()
        self.session_summary = None
        self.session_summary_revision = 0
        self._finish_radio_sent = False
        self._finish_pending_after_chequered = False
        self._summary_saved_for_uid = None
        self._summary_authoritative = False
        self._automatic_engineer_voice_enabled = True
        speech_prefs = load_speech_preferences()
        if tts_model == "voices/en_GB-alan-medium.onnx" and speech_prefs.get("model_path"):
            tts_model = str(speech_prefs.get("model_path"))
        if abs(float(tts_speed) - 0.82) < 1e-9 and isinstance(speech_prefs.get("length_scale"), (int, float)):
            tts_speed = float(speech_prefs.get("length_scale"))
        self.speech = SpeechOutput(
            TTSConfig(enabled=tts_enabled, backend=tts_backend, model_path=tts_model, length_scale=tts_speed, volume=tts_volume, output_device=audio_device),
            latency_monitor=self.latency if self.latency_stats else None,
            on_audio_start=self._on_radio_audio_start,
            on_delivery_event=self._on_radio_delivery_event,
        )
        self._state_lock = threading.RLock()
        self._runtime_lock = threading.RLock()
        self.stt = SpeechToText(
            stt_config or STTConfig(enabled=False),
            on_transcript=self._on_transcript, on_complete=self._on_stt_complete,
        )
        self.llm = LocalLLMEngineer(llm_config or LLMConfig(enabled=False), on_response=self._on_llm_response)
        self.ptt = PTTController(
            ptt_config or PTTConfig(), on_capture=self.stt.submit,
            on_press=self.speech.begin_listening, on_release=self._on_ptt_release,
        )
        self._pending_llm_fallback = None
        self._radio_reasoning_pending = False
        # V2.0.6.4: end-to-end driver radio latency markers. These live outside
        # the telemetry hot path and make STT / response formatting / TTS startup
        # delay visible independently instead of treating the whole pause as one
        # unexplained radio lag.
        self._driver_radio_release_at: float | None = None
        self._driver_radio_transcript_at: float | None = None
        self._driver_radio_response_queued_at: float | None = None
        self._decoded_packet_at = {}
        # V1.9.1.2: heavy decision/coaching work is deliberately decoupled from
        # the raw 60 Hz telemetry stream.  State still updates on every packet,
        # but engineer/coaching evaluation consumes the latest state at a bounded
        # cadence so telemetry rendering cannot be starved during long replays.
        self._last_telemetry_engineer_eval_at = None
        self._last_telemetry_coach_eval_at = None
        self._telemetry_engineer_interval_s = 0.050   # 20 Hz
        self._telemetry_coach_interval_s = 0.050      # 20 Hz
        self.packet_stats = packet_stats
        self.valid_bodies = 0
        self.malformed_bodies = 0
        self.unsupported_packets: Counter[int] = Counter()
        self.unknown_events = 0
        self.last_body_error = '--'
        self.capture = PacketCapture(capture_packets) if capture_packets else None
        self.capture_error = None
        self._last_performance_lap_announced = None
        self.live_coach = IntegratedLiveCoach()
        self.corner_coach = CornerCoachEngine()
        try:self.corner_coach.set_coaching_mode(self.live_coach.settings.mode)
        except Exception:pass
        self._sync_corner_speech_gates()
        self.driver_history = DriverHistory()
        self.performance_history = PerformanceHistoryStore()
        from .skill_evidence import SkillEvidenceStore
        self.skill_evidence = SkillEvidenceStore()
        self.driving_time_tracker = F1DrivingTimeTracker()
        # V2.0.3.5: REC-OFF performance history is autosaved after every completed
        # LIVE lap on a dedicated worker. Full .areplay recording remains optional.
        self._history_autosave_q = queue.Queue(maxsize=1)
        self._history_autosave_stop = threading.Event()
        self._history_autosave_thread = threading.Thread(
            target=self._history_autosave_worker, name="performance-history-autosave", daemon=True
        )
        self._history_autosave_thread.start()
        self._history_autosave_completed_count = 0
        self._history_autosave_game_lap_count = 0
        self.strategy_learner = StrategyEvidenceLearner()
        self._last_race_context_level = None
        self._race_context_hysteresis = RaceContextHysteresis()
        self._last_combat_call_at = None
        self._last_resume_call_at = None
        self._last_strategy_assess_at = None
        self._last_strategy_context_at = None
        # Validation persistence is deliberately slower than strategy decisions.
        # Strategy can update at 4 Hz, but serializing full evidence that often is
        # unnecessary and made long race replays progressively expensive.
        self._last_strategy_validation_at = None
        self._last_strategy_validation_signature = None
        self._coach_report_saved_for_uid = None
        self._coach_report_completed_count = -1
        self.recorder = AsyncTelemetrySessionRecorder(path=recording_path) if record_telemetry else None
        self._recording_mode = "session"
        self._session_recording_preference = bool(record_telemetry)
        self.recording_error = None
        self._replay_silent = False
        self._replay_rebuild = False
        self.wheel_bridge = WheelTelemetryBridge(enabled=wheel_telemetry, port=wheel_port)
        self.ai_benchmark = AIBenchmarkCapture(enabled=ai_reference, min_difficulty=ai_reference_min_difficulty)
        self.ai_reference_output = Path(ai_reference_output) if ai_reference_output else None
        self._ai_best_announced = None
        self.rival_benchmark = TimeTrialRivalCapture(enabled=rival_reference)
        self.rival_reference_output = Path(rival_reference_output) if rival_reference_output else None
        self._rival_best_announced = None
        from .app_paths import REFERENCES
        self.reference_directory = REFERENCES
        self._manual_reference_path = None
        self._manual_reference_lap = None
        self._manual_reference_meta = {}
        self._manual_reference_suspended_reason = None
        self._pending_reference_selection = None
        self._pending_reference_lap = None
        self._pending_reference_meta = {}
        # V0.9.17.2.4: live UDP stays bound while replay is active. The runtime
        # switches which source is allowed into the deterministic state pipeline.
        self._telemetry_mode = "live"
        self._replay_thread_id = None


    def _history_autosave_worker(self) -> None:
        """Persist coalesced LIVE lap snapshots away from the telemetry thread."""
        while not self._history_autosave_stop.is_set():
            try:
                job = self._history_autosave_q.get(timeout=0.25)
            except queue.Empty:
                continue
            if job is None:
                break
            profile, summary, frozen = job
            try:
                coach = build_coach_report(frozen)
                self.performance_history.record_session(profile, summary, coach)
            except Exception as error:
                print(f"[PERFORMANCE HUB] Lap autosave failed: {error}", flush=True)

    def _queue_live_history_autosave_locked(self) -> None:
        """Queue one compact session refresh when a new LIVE lap is completed.

        The expensive report/review build and SQLite write happen on the worker.
        This is independent from REC and therefore keeps performance analysis
        available when full packet recording is disabled.
        """
        if self._telemetry_mode != "live":
            return
        perf = getattr(self.engine, "performance", None)
        completed = list(getattr(perf, "completed", ()) or ())
        count = len(completed)
        player = getattr(self.engine.state, "player", None)
        current_lap = getattr(getattr(player, "lap", None), "current_lap", None)
        game_completed = max(0, int(current_lap) - 1) if isinstance(current_lap, int) else 0
        prev_analysis = int(getattr(self, "_history_autosave_completed_count", 0))
        prev_game = int(getattr(self, "_history_autosave_game_lap_count", 0))
        # Trigger on either source. The F1 lap counter is authoritative for how
        # many laps were completed; analysis may legitimately lag or exclude a
        # lap because of damage/traffic/invalidity.
        if count <= prev_analysis and game_completed <= prev_game:
            return

        # The measured-performance recorder can publish a completed lap on a LapData
        # packet a few milliseconds before the cadence-limited CORNER COACH observe()
        # call finalizes the same lap.  Do not consume the autosave edge in that
        # narrow window or the persisted lap will have timing but no corner evidence.
        # A following telemetry/lap packet will retry after the accumulator catches up.
        acc=getattr(getattr(self, "corner_coach", None), "_v202_accumulator", None)
        latest_completed_lap=max(
            (int(x.get("lap")) for x in completed if isinstance(x,dict) and isinstance(x.get("lap"),int)),
            default=None,
        )
        corner_coach_enabled=bool(getattr(getattr(self, "corner_coach", None), "enabled", False))
        if corner_coach_enabled and acc is not None and isinstance(latest_completed_lap,int):
            accumulated_laps={
                int(x.get("lap_number")) for x in (getattr(acc, "completed", ()) or ())
                if isinstance(x,dict) and isinstance(x.get("lap_number"),int)
            }
            if latest_completed_lap not in accumulated_laps:
                return

        self._history_autosave_completed_count = max(prev_analysis, count)
        self._history_autosave_game_lap_count = max(prev_game, game_completed)
        # Freeze only lap-domain analysis state. We deliberately do not copy raw
        # UDP packets, so REC remains the opt-in full-session recorder.
        # V2.0.3.7 also persists the already-authoritative V2 live lap/corner
        # intelligence.  This is the data the Performance Coach displays live;
        # losing it here was why Performance Hub could show 8 game laps but
        # zero scored/observed corners.
        live_laps=[]
        for row in copy.deepcopy(list(getattr(acc, "completed", ()) or ())):
            if not isinstance(row, dict):
                continue
            lap_no=row.get("lap_number")
            raw=next((x for x in completed if isinstance(x,dict) and x.get("lap")==lap_no),None)
            if isinstance(raw,dict):
                if isinstance(raw.get("lap_time_s"),(int,float)):
                    row["lap_time_s"]=float(raw["lap_time_s"])
                try:
                    from .data_quality import lap_quality
                    row["quality"]=copy.deepcopy(lap_quality(raw))
                except Exception:
                    pass
            live_laps.append(row)
        frozen = SimpleNamespace(
            completed=copy.deepcopy(completed),
            external_reference=copy.deepcopy(getattr(perf, "external_reference", None)),
            reference_mode=getattr(perf, "reference_mode", None),
            event_context=copy.deepcopy(getattr(perf, "event_context", None)),
            live_lap_intelligence=live_laps,
        )
        timed=[x for x in completed if isinstance(x,dict) and isinstance(x.get("lap_time_s"),(int,float)) and x.get("valid") is not False]
        best=min((float(x["lap_time_s"]) for x in timed), default=None)
        ctx=frozen.event_context if isinstance(frozen.event_context,dict) else {}
        session=getattr(self.engine.state,"session",None)
        # Reuse the authoritative live SessionSummaryTracker so REC-OFF history
        # also retains damage/wear/warnings and the real game lap count.
        tracked = self.session_summary_tracker.build(self.engine.state, perf) if getattr(self, "session_summary_tracker", None) is not None else None
        summary = dict(tracked or {})
        summary.update({
            "session_uid":getattr(session,"uid",None),
            "track":summary.get("track") or ctx.get("track_name") or ctx.get("track_id"),
            "session_type":summary.get("session_type") or ctx.get("session_type") or getattr(getattr(session,"session_type",None),"name",None),
            "laps_completed":max(game_completed, int(summary.get("laps_completed") or 0), count),
            # V2.9.1.3.5.14: for Time Trial, the current session's measured
            # completed laps are the Performance History best-lap authority.
            # Do not allow a Final Classification personal/track best to replace it.
            "best_lap_s":(best if isinstance(best,(int,float)) and str(summary.get("session_type") or ctx.get("session_type") or "").lower()=="time trial" else (summary.get("best_lap_s") if isinstance(summary.get("best_lap_s"),(int,float)) else best)),
        })
        # Snapshot the shared backend track authority into the session review.
        # The review must not depend on whether the map overlay is open later.
        try:
            from .overlay.track_maps import get_track_map, get_track_map_distances
            from .track_geometry import persisted_physical_turns
            track_name=summary.get("track")
            points=get_track_map(track_name) or ()
            distances=get_track_map_distances(track_name) or ()
            frozen.track_geometry_snapshot={
                "track":track_name,
                "points":[list(x) for x in points],
                "distances":[float(x) for x in distances],
                "corners":[dict(x) for x in persisted_physical_turns(track_name)],
            }
        except Exception:
            frozen.track_geometry_snapshot={"track":summary.get("track"),"points":[],"distances":[],"corners":[]}
        profile=copy.deepcopy(driver_profile_from_state(self.engine.state))
        job=(profile,summary,frozen)
        try:
            self._history_autosave_q.put_nowait(job)
        except queue.Full:
            # Coalesce stale lap snapshots; newest completed-lap state wins.
            try:self._history_autosave_q.get_nowait()
            except queue.Empty:pass
            try:self._history_autosave_q.put_nowait(job)
            except queue.Full:pass

    def _finalize_validation_session_locked(self, uid=None) -> None:
        """Persist a compact evidence bundle for the session that just ended."""
        target_uid = self._last_runtime_session_uid if uid is None else uid
        if target_uid is None:
            return
        try:
            self.validation_transcript.flush()
            info = self.validation_transcript.session_artifacts(target_uid) or {}
            meta = dict(info.get("meta") or {})
            meta.setdefault("session_uid", target_uid)
            paths = dict(info.get("paths") or {})
            corner_path = getattr(getattr(self, "corner_coach", None), "validation", None)
            corner_path = getattr(corner_path, "path", None)
            recording = getattr(getattr(self, "recorder", None), "path", None)
            replay_index = None
            if recording is not None and Path(recording).exists():
                try:
                    lib = SessionLibrary()
                    lib.replay_analysis.build(recording)
                    replay_index = lib.replay_analysis.cache_path(recording)
                except Exception:
                    replay_index = None
            self._last_validation_bundle = self.validation_bundle.finalize_session(
                self.engine.state, transcript_paths=paths, corner_validation=corner_path,
                recording_path=recording, replay_index=replay_index,
                latency=self.latency.snapshot(), runtime=self.runtime_benchmark.snapshot(),
                session_meta_override=meta,
            )
            if self._last_validation_bundle is not None:
                print(f"[VALIDATION] Bundle: {self._last_validation_bundle}", flush=True)
        except Exception as error:
            try:
                self.validation_bundle.warning(self.engine.state, "validation_bundle_finalize_failed", str(error))
            except Exception:
                pass
            print(f"[VALIDATION] Bundle finalize failed: {error}", flush=True)



    def _handle_session_transition_locked(self) -> None:
        uid=getattr(self.engine.state.session,"uid",None)
        if uid is None or uid==self._last_runtime_session_uid:
            return
        previous=self._last_runtime_session_uid
        self._last_runtime_session_uid=uid
        self.validation_transcript.observe_session(self.engine.state)
        if previous is not None:
            self._finalize_validation_session_locked(previous)
        self.validation_transcript.marker(self.engine.state,"session_transition",previous_session_uid=previous,new_session_uid=uid)
        self.runtime_benchmark.reset_session_metrics()
        self.latency.reset()
        if previous is not None:
            self.live_coach.reset_session()
            self.corner_coach.reset_session()
            self._race_context_hysteresis.reset()
            self._last_race_context_level=None
            self._last_combat_call_at=None; self._last_resume_call_at=None
            self._last_strategy_validation_at=None
            self._last_strategy_validation_signature=None
            self._last_telemetry_engineer_eval_at=None
            self._last_telemetry_coach_eval_at=None
            self.session_summary_tracker=SessionSummaryTracker()
            self.session_summary=None; self.session_summary_revision=0
            self._finish_radio_sent=False; self._finish_pending_after_chequered=False
            self._summary_saved_for_uid=None; self._summary_authoritative=False
            self._coach_report_saved_for_uid=None; self._coach_report_completed_count=-1
            self._history_autosave_completed_count=0
            self._history_autosave_game_lap_count=0

    def set_telemetry_mode(self, mode: str, *, replay_thread_id=None) -> None:
        mode = str(mode).lower()
        if mode not in {"live", "replay"}:
            raise ValueError(f"Unsupported telemetry mode: {mode}")
        with self._runtime_lock:
            self._telemetry_mode = mode
            self._replay_thread_id = replay_thread_id if mode == "replay" else None
        self._last_telemetry_engineer_eval_at = None
        self._last_telemetry_coach_eval_at = None

    def telemetry_mode(self) -> str:
        with self._runtime_lock:
            return self._telemetry_mode

    def current_reference_selection(self) -> str:
        with self._state_lock:
            if self._pending_reference_selection is not None:
                return str(self._pending_reference_selection)
            return str(self._manual_reference_path) if self._manual_reference_path is not None else "__SESSION_BEST__"

    def reference_selection_status(self) -> dict:
        """Return selected/active/pending reference state for the Control Center."""
        with self._state_lock:
            perf = self.engine.performance
            pending = self._pending_reference_selection
            selected = pending if pending is not None else (self._manual_reference_path if self._manual_reference_path is not None else "__SESSION_BEST__")

            if getattr(perf, "reference_mode", "best") == "external" and getattr(perf, "external_reference", None) is not None:
                active_sel = self._manual_reference_path if self._manual_reference_path is not None else "__EXTERNAL__"
                active_name = getattr(perf, "external_reference_name", None) or "Stored reference"
                active_lap = getattr(perf, "external_reference", None) or {}
                active_time = active_lap.get("lap_time_s") if isinstance(active_lap, dict) else None
            else:
                mode = getattr(perf, "reference_mode", "best")
                completed = list(getattr(perf, "completed", None) or ())
                valid = [x for x in completed if x.get("valid") and isinstance(x.get("lap_time_s"), (int, float))]
                if mode == "manual":
                    lap_no = getattr(perf, "manual_reference_lap", None)
                    active_lap = next((x for x in completed if x.get("lap") == lap_no), None)
                    active_sel = "__MEASURED_MANUAL__"
                    active_name = f"Measured L{lap_no}" if active_lap else "Measured lap — waiting"
                    active_time = active_lap.get("lap_time_s") if active_lap else None
                elif mode == "previous":
                    active_lap = completed[-1] if completed else None
                    active_sel = "__MEASURED_PREVIOUS__"
                    active_name = f"Previous L{active_lap.get('lap')}" if active_lap else "Previous lap — waiting"
                    active_time = active_lap.get("lap_time_s") if active_lap else None
                else:
                    best = min(valid, key=lambda x: x["lap_time_s"]) if valid else None
                    active_sel = "__SESSION_BEST__"
                    active_name = f"Session best L{best.get('lap')}" if best else "Session best — waiting for valid lap"
                    active_time = best.get("lap_time_s") if best else None

            return {
                "selected": str(selected),
                "active": str(active_sel),
                "active_name": active_name,
                "active_time_s": float(active_time) if isinstance(active_time, (int, float)) else None,
                "pending": str(pending) if pending is not None else None,
                "pending_name": (
                    ("Lap " + str(self._pending_reference_meta.get("lap")))
                    if pending == "__MEASURED_REFERENCE__" and self._pending_reference_meta.get("mode") == "manual"
                    else "Previous lap" if pending == "__MEASURED_REFERENCE__" and self._pending_reference_meta.get("mode") == "previous"
                    else "Best lap" if pending == "__MEASURED_REFERENCE__"
                    else None
                ),
            }

    def _lap_is_at_start_locked(self) -> bool:
        player = getattr(self.engine.state, "player", None)
        lap = getattr(player, "lap", None) if player is not None else None
        d = getattr(lap, "lap_distance_m", None) if lap is not None else None
        t = getattr(lap, "current_lap_time_s", None) if lap is not None else None
        return (isinstance(d, (int, float)) and isinstance(t, (int, float))
                and -1.0 <= float(d) <= 25.0 and 0.0 <= float(t) <= 2.0)

    def _lap_is_in_progress_locked(self) -> bool:
        player = getattr(self.engine.state, "player", None)
        lap = getattr(player, "lap", None) if player is not None else None
        d = getattr(lap, "lap_distance_m", None) if lap is not None else None
        t = getattr(lap, "current_lap_time_s", None) if lap is not None else None
        if not isinstance(d, (int, float)) or not isinstance(t, (int, float)):
            return False
        return float(d) > 25.0 or float(t) > 2.0

    def _queue_reference_selection_locked(self, selection, lap=None, meta=None) -> None:
        self._pending_reference_selection = selection
        self._pending_reference_lap = lap
        self._pending_reference_meta = dict(meta or {})

    def _apply_measured_reference_locked(self, mode: str, lap_number=None) -> tuple[bool, str]:
        """Activate an in-session measured reference without touching stored files."""
        mode=str(mode).lower()
        if mode not in {"manual","previous","best"}:
            return False, "Unsupported measured reference mode."
        self._manual_reference_path=None
        self._manual_reference_lap=None
        self._manual_reference_meta={}
        self._manual_reference_suspended_reason=None
        ok=self.engine.performance.set_reference(mode, lap=lap_number)
        if not ok:
            return False, "No completed measured lap is available for that reference."
        self.engine.performance._publish(self.engine.state)
        if mode=="manual":
            return True, f"Lap {self.engine.performance.manual_reference_lap} is now the reference."
        if mode=="previous":
            return True, "Previous completed lap is now the reference."
        return True, "Best valid measured lap is now the reference."

    def select_measured_reference(self, mode: str) -> tuple[bool, str]:
        """Radio-safe measured reference selection with lap-boundary activation."""
        mode=str(mode).lower()
        if mode not in {"manual","previous","best"}:
            return False, "Unsupported measured reference mode."
        with self._state_lock:
            target_lap=None
            completed=list(getattr(self.engine.performance,"completed",()) or ())
            in_progress=self._lap_is_in_progress_locked()
            if mode=="previous" and not completed:
                return False, "No completed measured lap is available to set as reference."
            if mode=="manual":
                if in_progress:
                    # "Use this lap" means the lap being driven now. Engine.update
                    # closes it before pending-reference activation at the next
                    # start/finish packet, so it is available by then.
                    player=getattr(self.engine.state,"player",None)
                    lap_state=getattr(player,"lap",None) if player is not None else None
                    target_lap=getattr(lap_state,"current_lap",None) if lap_state is not None else None
                    if not isinstance(target_lap,int):
                        return False, "Current lap number is unavailable."
                else:
                    if not completed:
                        return False, "No completed measured lap is available to set as reference."
                    target_lap=completed[-1].get("lap")
            if in_progress:
                self._queue_reference_selection_locked(
                    "__MEASURED_REFERENCE__", meta={"mode":mode,"lap":target_lap}
                )
                label=(f"Lap {target_lap}" if mode=="manual" else "Previous lap" if mode=="previous" else "Best lap")
                return True, f"{label} queued as reference for the next start/finish crossing."
            return self._apply_measured_reference_locked(mode,target_lap)

    def _apply_pending_reference_locked(self) -> tuple[bool, str | None]:
        if self._pending_reference_selection is None or not self._lap_is_at_start_locked():
            return False, None
        selection = self._pending_reference_selection
        lap = self._pending_reference_lap
        meta = dict(self._pending_reference_meta or {})
        self._pending_reference_selection = None
        self._pending_reference_lap = None
        self._pending_reference_meta = {}
        if str(selection) == "__MEASURED_REFERENCE__":
            ok, message = self._apply_measured_reference_locked(meta.get("mode", "best"), meta.get("lap"))
            print(f"[REFERENCE] Applied at lap start: {message}", flush=True)
            return ok, message
        if str(selection) in {"__AUTO__", "__SESSION_BEST__", ""}:
            self._manual_reference_path = None
            self._manual_reference_lap = None
            self._manual_reference_meta = {}
            self._manual_reference_suspended_reason = None
            message = self._apply_session_best_reference_locked()
            print(f"[REFERENCE] Applied at lap start: {message}", flush=True)
            return True, message
        path = Path(str(selection))
        ok, reason = self._check_reference_track_locked(meta)
        if not ok:
            self._apply_session_best_reference_locked()
            print(f"[REFERENCE] Pending reference not applied: {reason}", flush=True)
            return False, reason
        name = meta.get("driver") or meta.get("name") or path.stem
        self.engine.performance.set_external_reference(lap, name=name, metadata=meta)
        self._manual_reference_path = path
        self._manual_reference_lap = lap
        self._manual_reference_meta = meta
        self._manual_reference_suspended_reason = None
        print(f"[REFERENCE] Applied at lap start: {name}", flush=True)
        return True, f"Reference active: {name}"

    def _reference_compatibility_context_locked(self):
        """Return only currently measured identity fields used by reference compatibility."""
        state=self.engine.state
        session=getattr(state,"session",None)
        player=getattr(state,"player",None)
        ident=getattr(player,"identity",None) if player is not None else None
        team=getattr(getattr(ident,"team",None),"raw",None) if ident is not None else None
        return {
            "track_id": getattr(getattr(session,"track",None),"raw",None),
            "track_length_m": getattr(session,"track_length_m",None),
            "game_year": getattr(session,"game_year",None),
            "game_version": getattr(session,"game_version",None),
            "packet_format": getattr(session,"packet_format",None),
            "formula": getattr(session,"formula",None),
            "equal_car_performance": getattr(session,"equal_car_performance",None),
            "team_id": team,
            "weather": getattr(getattr(session,"weather",None),"raw",None),
        }

    def import_reference_package(self, package_path):
        from .reference_ecosystem import install_reference_package
        with self._state_lock:
            ctx=self._reference_compatibility_context_locked()
        try:
            result=install_reference_package(package_path,root=self.reference_directory,context=ctx)
        except Exception as error:
            return False, f"Reference import failed: {error}"
        return True, f"Reference installed: {(result.get('manifest') or {}).get('label') or Path(result['path']).stem}"

    def export_reference_package(self, reference_path, output_path):
        from .reference_ecosystem import export_reference_package
        try:
            result=export_reference_package(reference_path,output_path)
        except Exception as error:
            return False, f"Reference export failed: {error}"
        return True, f"Reference package saved: {result['path']}"

    def reference_lap_options(self):
        """Return validated stored reference laps for the Control Center selector."""
        from .reference_lap import load_reference_lap
        base=self.reference_directory
        if not base.exists():
            return []
        rows=[]
        # Legacy references live directly under references/. V1.1 compiled rival
        # bundles live under references/<TRACK>/; expose only their raw reusable
        # rival_reference.json source, never the internal reference_model/zones files.
        paths=list(base.glob("*.json"))
        paths.extend(base.glob("*/rival_reference.json"))
        paths.extend(base.glob("imported/*/*/reference.json"))
        seen=set()
        for path in sorted(paths):
            try:
                resolved=str(path.resolve())
            except OSError:
                resolved=str(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                lap, meta=load_reference_lap(path)
            except Exception:
                continue
            lap_time=lap.get("lap_time_s")
            driver=meta.get("driver") or meta.get("name") or path.stem
            source=meta.get("source")
            detail=[]
            if path.name=="rival_reference.json" and path.parent!=base:
                detail.append(path.parent.name.replace("_"," "))
            if isinstance(lap_time,(int,float)) and lap_time>0:
                mins=int(lap_time//60); secs=lap_time-mins*60
                detail.append(f"{mins}:{secs:06.3f}" if mins else f"{secs:.3f}s")
            if driver and str(driver)!=path.stem:
                detail.append(str(driver))
            if source=="EA_F1_TIME_TRIAL_RIVAL":
                detail.append("TT rival")
            elif source=="EA_F1_AI_CAR":
                detail.append("AI")
            try:
                from .reference_ecosystem import reference_quality
                quality=reference_quality(lap,meta)
                detail.append(f"Q{quality.get('grade','?')} {quality.get('score','?')}")
            except Exception:
                quality=None
            manifest_path=path.parent/"manifest.json"
            manifest=None
            if manifest_path.exists():
                try:
                    import json as _json
                    manifest=_json.loads(manifest_path.read_text(encoding="utf-8"))
                    detail.append("imported")
                except Exception:
                    manifest=None
            display=(manifest or {}).get("label") or path.stem
            label=display + (" • " + " • ".join(detail) if detail else "")
            rows.append({"label":label,"path":str(path),"quality":quality,"manifest":manifest})
        return rows

    def _apply_session_best_reference_locked(self):
        """Use only the best valid lap from the current live/replay session."""
        self.engine.performance.external_reference = None
        self.engine.performance.external_reference_name = None
        self.engine.performance.external_reference_meta = {}
        self.engine.performance.reference_mode = "best"
        self.engine.performance.manual_reference_lap = None
        return "Reference: current-session best lap"

    def _current_track_id_locked(self):
        track = getattr(getattr(self.engine.state, "session", None), "track", None)
        raw = getattr(track, "raw", None)
        return int(raw) if isinstance(raw, int) and raw >= 0 else None

    def _check_reference_track_locked(self, metadata) -> tuple[bool, str | None]:
        """Verify a stored reference belongs to the active track when known."""
        current_track = self._current_track_id_locked()
        if current_track is None:
            return True, None
        ref_track = (metadata or {}).get("track_id")
        if not isinstance(ref_track, int):
            return False, "Reference rejected: track cannot be verified from the stored metadata"
        if ref_track != current_track:
            from .telemetry.enums import TRACKS
            return False, (
                f"Reference rejected: {TRACKS.get(ref_track, f'Track {ref_track}')} does not match "
                f"{TRACKS.get(current_track, f'Track {current_track}')}"
            )
        return True, None

    def _restore_manual_reference_locked(self) -> tuple[bool, str | None]:
        """Re-apply a manually selected stored reference after engine/replay resets."""
        if self._manual_reference_path is None:
            self._apply_session_best_reference_locked()
            return True, None
        if self._manual_reference_lap is None:
            from .reference_lap import load_reference_lap
            try:
                lap, meta = load_reference_lap(self._manual_reference_path)
            except Exception as error:
                self._manual_reference_path = None
                self._manual_reference_lap = None
                self._manual_reference_meta = {}
                self._manual_reference_suspended_reason = None
                self._apply_session_best_reference_locked()
                return False, f"Reference reload failed: {error}"
            self._manual_reference_lap = lap
            self._manual_reference_meta = dict(meta or {})
        ok, reason = self._check_reference_track_locked(self._manual_reference_meta)
        if not ok:
            self._apply_session_best_reference_locked()
            self._manual_reference_suspended_reason = reason
            return False, reason
        name = (self._manual_reference_meta.get("driver") or self._manual_reference_meta.get("name")
                or self._manual_reference_path.stem)
        self.engine.performance.set_external_reference(
            self._manual_reference_lap, name=name, metadata=self._manual_reference_meta
        )
        self._manual_reference_suspended_reason = None
        return True, None

    def _enforce_manual_reference_track_locked(self) -> None:
        """Use the selected reference only on its track; suspend it on other tracks."""
        if self._manual_reference_path is None:
            return
        # Track is not known yet (startup/source transition): preserve the selection
        # and wait for the first Session packet instead of guessing compatibility.
        if self._current_track_id_locked() is None:
            return
        ok, reason = self._check_reference_track_locked(self._manual_reference_meta)
        if not ok:
            if getattr(self.engine.performance, "reference_mode", "best") == "external":
                self._apply_session_best_reference_locked()
            if reason != self._manual_reference_suspended_reason:
                print(f"[REFERENCE] {reason}; using current-session best on this track", flush=True)
            self._manual_reference_suspended_reason = reason
            return
        # A source/replay reset creates a fresh RaceStateEngine. Re-apply the
        # selected stored reference as soon as the matching track is identified.
        if (getattr(self.engine.performance, "reference_mode", "best") != "external"
                or self.engine.performance.external_reference is None):
            name = (self._manual_reference_meta.get("driver") or self._manual_reference_meta.get("name")
                    or self._manual_reference_path.stem)
            self.engine.performance.set_external_reference(
                self._manual_reference_lap, name=name, metadata=self._manual_reference_meta
            )
            if self._manual_reference_suspended_reason is not None:
                print(f"[REFERENCE] Matching track restored; using {name}", flush=True)
        self._manual_reference_suspended_reason = None

    def select_reference_lap(self, selection) -> tuple[bool, str]:
        """Select the coaching reference. Mid-lap changes activate at the next lap start."""
        value=str(selection or "__SESSION_BEST__")
        with self._state_lock:
            if value in {"__AUTO__", "__SESSION_BEST__", ""}:
                if self._lap_is_in_progress_locked():
                    self._queue_reference_selection_locked("__SESSION_BEST__")
                    return True, "Session best queued — activates at the next start/finish crossing"
                self._pending_reference_selection=None
                self._pending_reference_lap=None
                self._pending_reference_meta={}
                self._manual_reference_path=None
                self._manual_reference_lap=None
                self._manual_reference_meta={}
                self._manual_reference_suspended_reason=None
                return True, self._apply_session_best_reference_locked()
            path=Path(value)
            from .reference_lap import load_reference_lap
            try:
                lap, meta = load_reference_lap(path)
            except Exception as error:
                return False, f"Reference load failed: {error}"
            ok, reason = self._check_reference_track_locked(meta)
            if not ok:
                return False, reason or "Reference track mismatch"
            name=meta.get("driver") or meta.get("name") or path.stem
            lap_time=lap.get("lap_time_s")
            text=f"Reference: {name}"
            if isinstance(lap_time,(int,float)) and lap_time>0:
                text+=f" • {lap_time:.3f}s"
            if isinstance(meta.get("track_id"), int):
                from .telemetry.enums import TRACKS
                text += f" • {TRACKS.get(meta['track_id'], 'Track ' + str(meta['track_id']))}"
            if self._lap_is_in_progress_locked():
                self._queue_reference_selection_locked(path, lap, meta)
                print(f"[REFERENCE] Queued for next lap start: {text}", flush=True)
                return True, text + " • queued for next lap start"
            self.engine.performance.set_external_reference(lap, name=name, metadata=meta)
            self._pending_reference_selection=None
            self._pending_reference_lap=None
            self._pending_reference_meta={}
            self._manual_reference_path=path
            self._manual_reference_lap=lap
            self._manual_reference_meta=dict(meta or {})
            self._manual_reference_suspended_reason=None
            print(f"[REFERENCE] {text}", flush=True)
            return True, text

    def runtime_feature_states(self) -> dict[str, bool]:
        """Return live feature switches shown by the Control Center."""
        with self._runtime_lock:
            # REC represents the normal raw Session Recording switch only.
            # Rival Reference Capture has its own auto-armed status row.
            recording_active=(self.recorder is not None and self.recording_error is None) if self._recording_mode=="session" else False
            return {
                "TTS": bool(getattr(self.speech.config, "enabled", False)),
                "PTT": bool(getattr(self.ptt.config, "enabled", False)),
                "STT": bool(getattr(self.stt.config, "enabled", False)),
                "LLM": bool(getattr(self.llm.config, "enabled", False)),
                "REC": bool(recording_active),
            }

    def recording_mode(self) -> str:
        with self._runtime_lock:
            return self._recording_mode

    def set_recording_mode(self, mode: str) -> tuple[bool, str]:
        mode=str(mode or "").strip().lower().replace(" ","_")
        aliases={"session":"session","session_recording":"session","rival":"rival_reference","rival_reference":"rival_reference","rival_reference_capture":"rival_reference"}
        if mode not in aliases:
            return False,"Unknown recording mode"
        target=aliases[mode]
        close_recorder=None
        with self._runtime_lock:
            if self._recording_mode==target:
                if target=="rival_reference":
                    # Rival reference mode is self-arming. REC belongs to normal
                    # session recording and is intentionally not the master here.
                    self.rival_benchmark.strict_quality=True
                    self.rival_benchmark.enabled=True
                    return True,"Rival Reference Capture — auto armed"
                return True,"Session Recording"

            previous=self._recording_mode
            if previous=="session":
                self._session_recording_preference=bool(self.recorder is not None and self.recording_error is None)
            close_recorder=self.recorder
            self.recorder=None
            self.recording_error=None
            self.rival_benchmark.enabled=False
            self._recording_mode=target

            if target=="rival_reference":
                self.rival_benchmark.strict_quality=True
                self.rival_benchmark.enabled=True
                self.rival_benchmark.reset_capture()
            elif self._session_recording_preference and self._telemetry_mode=="live":
                self.recorder=AsyncTelemetrySessionRecorder()

        if close_recorder is not None:
            close_recorder.close()
        if target=="rival_reference":
            print("[UI] RECORDING MODE RIVAL REFERENCE CAPTURE (AUTO-ARMED)",flush=True)
            return True,"Rival Reference Capture — auto armed; normal REC is not required"
        print("[UI] RECORDING MODE SESSION RECORDING",flush=True)
        return True,"Session Recording"

    def rival_reference_capture_status(self) -> dict:
        status=self.rival_benchmark.capture_status()
        status["recording_mode"]=self.recording_mode()
        return status

    def coaching_feature_states(self) -> dict[str, bool]:
        """Return effective Race Engineer + CORNER COACH hierarchy states.

        Child preferences are intentionally not overwritten when a master is OFF.
        The Control Center therefore shows dependent switches OFF while muted and
        restores their previous preferences automatically when the master returns.
        """
        engineer=bool(self._automatic_engineer_voice_enabled)
        out={
            "ENGR":engineer,
            # Legacy PRE/POST are no longer rendered in the Control Center, but
            # retain their persisted values for compatibility/offline tooling.
            "POST": engineer and bool(self.live_coach.settings.post_corner),
            "PRE": engineer and bool(self.live_coach.settings.pre_corner),
            "LAP": engineer and bool(self.live_coach.settings.lap_summary),
            "POS": engineer and bool(self.live_coach.settings.positive_calls),
            "RACE": engineer and bool(self.live_coach.settings.race_coaching),
        }
        out.update(self.corner_coach.speed_coach_feature_states())
        out["DMGCOACH"] = bool(self.corner_coach.enabled and getattr(self.corner_coach,"damage_coaching_enabled",False))
        return out

    def _sync_corner_speech_gates(self, *, damage_blocked: bool | None = None) -> None:
        """Keep CORNER COACH radio ownership independent from Race Engineer.

        Significant damage with DMG COACH OFF mutes only CORNER COACH speech; map
        and measurement continue.  Prefix gating also stops any already-playing
        corner line when damage becomes blocking.
        """
        speech = getattr(self, "speech", None)
        if speech is None or not hasattr(speech, "set_message_prefix_enabled"):
            return
        if damage_blocked is None:
            damage_blocked=bool(getattr(self.corner_coach,"_damage_coaching_blocked",False))
        speed_master = bool(self.corner_coach.enabled and self.corner_coach.voice_enabled and not damage_blocked)
        corner_master = bool(speed_master and getattr(self.corner_coach,"corner_enabled",True))
        straight_master = bool(speed_master and getattr(self.corner_coach,"straight_enabled",False) and getattr(self.corner_coach,"straight_voice_enabled",True))
        speech.set_message_prefix_enabled("corner:", corner_master)
        speech.set_message_prefix_enabled("corner:pre:", corner_master and bool(self.corner_coach.pre_enabled))
        speech.set_message_prefix_enabled("corner:post:", corner_master and bool(self.corner_coach.post_enabled))
        speech.set_message_prefix_enabled("corner:gainloss:", speed_master and bool(self.corner_coach.gain_loss_voice_enabled))
        speech.set_message_prefix_enabled("straight:", straight_master)

    def set_corner_coach_feature(self, feature: str, enabled: bool) -> tuple[bool, str]:
        ok,message=self.corner_coach.set_feature(feature,enabled)
        if ok:
            # Keep damaged-lap eligibility synchronized across recorder/report and live coach.
            allow_damage=bool(self.corner_coach.enabled and getattr(self.corner_coach,"damage_coaching_enabled",False))
            try:self.engine.performance.allow_damage_coaching=allow_damage
            except Exception:pass
            try:self.live_coach.allow_damage_coaching=allow_damage
            except Exception:pass
            self._sync_corner_speech_gates()
            print(f"[UI] PERFORMANCE COACH {str(feature).upper()} {'ENABLED' if enabled else 'DISABLED'}",flush=True)
        return ok,message

    def set_coaching_feature(self, feature: str, enabled: bool) -> tuple[bool, str]:
        ok, message = self.live_coach.set_feature(feature, enabled)
        if ok:
            print(f"[UI] COACH {str(feature).upper()} {'ENABLED' if enabled else 'DISABLED'}", flush=True)
        return ok, message

    def set_coaching_mode(self, mode: str) -> tuple[bool, str]:
        ok, message = self.live_coach.set_mode(mode)
        if ok:
            try:self.corner_coach.set_coaching_mode(mode)
            except Exception:pass
            print(f"[UI] COACH MODE {message}", flush=True)
        return ok, message

    def set_coaching_verbosity(self, verbosity: str) -> tuple[bool, str]:
        ok, message = self.live_coach.set_verbosity(verbosity)
        if ok:
            print(f"[UI] COACH VERBOSITY {message}", flush=True)
        return ok, message

    def set_automatic_engineer_voice_enabled(self, enabled: bool) -> tuple[bool, str]:
        """Toggle automatic race-engineer speech while leaving coach/PTT active."""
        enabled = bool(enabled)
        with self._runtime_lock:
            self._automatic_engineer_voice_enabled = enabled
            if hasattr(self.speech, "set_automatic_engineer_enabled"):
                self.speech.set_automatic_engineer_enabled(enabled)
        print(f"[UI] AUTOMATIC ENGINEER VOICE {'ENABLED' if enabled else 'DISABLED'}", flush=True)
        return True, "Enabled" if enabled else "Disabled"

    def set_tts_enabled(self, enabled: bool) -> tuple[bool, str]:
        enabled = bool(enabled)
        with self._runtime_lock:
            if bool(getattr(self.speech.config, "enabled", False)) == enabled:
                return True, "Enabled" if enabled else "Disabled"
            old = self.speech
            config = replace(old.config, enabled=enabled)
            if not enabled:
                old.begin_listening()
            old.close(wait=False)
            self.speech = SpeechOutput(
                config,
                latency_monitor=self.latency if self.latency_stats else None,
                on_audio_start=self._on_radio_audio_start,
                on_delivery_event=self._on_radio_delivery_event,
            )
            if hasattr(self.speech, "set_automatic_engineer_enabled"):
                self.speech.set_automatic_engineer_enabled(self._automatic_engineer_voice_enabled)
            self._sync_corner_speech_gates()
            self.ptt.on_press = self.speech.begin_listening
        print(f"[UI] TTS {'ENABLED' if enabled else 'DISABLED'}", flush=True)
        return True, "Enabled" if enabled else "Disabled"

    def set_stt_enabled(self, enabled: bool) -> tuple[bool, str]:
        enabled = bool(enabled)
        with self._runtime_lock:
            self.stt.config = replace(self.stt.config, enabled=enabled)
            if enabled:
                self.stt.start()
            self.ptt.on_capture = self.stt.submit
        print(f"[UI] STT {'ENABLED' if enabled else 'DISABLED'}", flush=True)
        return True, "Enabled" if enabled else "Disabled"

    def set_llm_enabled(self, enabled: bool) -> tuple[bool, str]:
        enabled = bool(enabled)
        with self._runtime_lock:
            if hasattr(self.llm, "set_enabled"):
                self.llm.set_enabled(enabled)
            else:
                self.llm.config = replace(self.llm.config, enabled=enabled)
        print(f"[UI] LLM {'ENABLED' if enabled else 'DISABLED'}", flush=True)
        return True, "Enabled" if enabled else "Disabled"

    def set_ptt_enabled(self, enabled: bool) -> tuple[bool, str]:
        enabled = bool(enabled)
        with self._runtime_lock:
            current = bool(getattr(self.ptt.config, "enabled", False))
            if current == enabled:
                return True, "Enabled" if enabled else "Disabled"
            old = self.ptt
            config = replace(old.config, enabled=enabled)
            if enabled and config.backend != "hid":
                return False, "Runtime PTT toggle requires HID backend"
            old.close(wait=False)
            self.ptt = PTTController(
                config, on_capture=self.stt.submit,
                on_press=self.speech.begin_listening, on_release=self._on_ptt_release,
            )
            if enabled:
                self.ptt.start()
        print(f"[UI] PTT {'ENABLED' if enabled else 'DISABLED'}", flush=True)
        return True, "Enabled" if enabled else "Disabled"

    def set_recording_enabled(self, enabled: bool) -> tuple[bool, str]:
        enabled = bool(enabled)
        with self._runtime_lock:
            if self._recording_mode=="rival_reference":
                # REC is the normal raw-session recorder only. Rival Reference
                # Capture auto-arms from the recording-mode selector and cannot
                # accidentally be disabled by the REC button/state.
                self.rival_benchmark.strict_quality=True
                self.rival_benchmark.enabled=True
                return True,"Automatic — Rival Reference Capture is armed"
            if enabled and self._telemetry_mode != "live":
                return False, "Recording is available in Live mode only"
            self.rival_benchmark.enabled=False
            self._session_recording_preference=enabled
            if enabled:
                if self.recorder is None:
                    self.recording_error = None
                    self.recorder = AsyncTelemetrySessionRecorder()
                print("[UI] Telemetry recording ENABLED", flush=True)
                return True, "On"
            old, self.recorder = self.recorder, None
        if old is not None:
            old.close()
        print("[UI] Telemetry recording DISABLED", flush=True)
        return True,"Off"

    def _runtime_control_states(self) -> dict[str, bool]:
        states = dict(self.coaching_feature_states())
        states.update({
            "TTS": bool(getattr(self.speech.config, "enabled", False)),
            "PTT": bool(getattr(self.ptt.config, "enabled", False)),
            "STT": bool(getattr(self.stt.config, "enabled", False)),
            "LLM": bool(getattr(self.llm.config, "enabled", False)),
            "REC": bool(self.recorder is not None) if self._recording_mode != "rival_reference" else bool(self.rival_benchmark.enabled),
        })
        return states

    def _set_runtime_control(self, target: str, enabled: bool) -> tuple[bool, str]:
        target = str(target or "").upper()
        if target == "ENGR": return self.set_automatic_engineer_voice_enabled(enabled)
        if target in {"PRE", "POST", "LAP", "POS", "RACE"}: return self.set_coaching_feature(target, enabled)
        corner = {
            "SPEED":"SPEED", "CORNER":"CORNER", "STRAIGHT":"STRAIGHT", "CCVOICE":"VOICE", "CCPRE":"PRE", "CCPOST":"POST",
            "SLVOICE":"STRAIGHTVOICE", "GAINLOSS":"GAINLOSS", "GAINLOSSVOICE":"GAINLOSSVOICE", "DMGCOACH":"DMGCOACH",
        }
        if target in corner: return self.set_corner_coach_feature(corner[target], enabled)
        if target == "TTS": return self.set_tts_enabled(enabled)
        if target == "PTT": return self.set_ptt_enabled(enabled)
        if target == "STT": return self.set_stt_enabled(enabled)
        if target == "LLM": return self.set_llm_enabled(enabled)
        if target == "REC": return self.set_recording_enabled(enabled)
        return False, "Unknown control"

    @staticmethod
    def _voice_speed_value(profile: str) -> float | None:
        return {"slow":1.00, "normal":0.82, "fast":0.68}.get(str(profile or "").lower())

    def _replace_speech_config(self, **changes) -> tuple[bool, str]:
        with self._runtime_lock:
            old = self.speech
            try:
                config = replace(old.config, **changes)
                old.close(wait=False)
                self.speech = SpeechOutput(
                    config,
                    latency_monitor=self.latency if self.latency_stats else None,
                    on_audio_start=self._on_radio_audio_start,
                    on_delivery_event=self._on_radio_delivery_event,
                )
                if hasattr(self.speech, "set_automatic_engineer_enabled"):
                    self.speech.set_automatic_engineer_enabled(self._automatic_engineer_voice_enabled)
                self._sync_corner_speech_gates()
                self.ptt.on_press = self.speech.begin_listening
                return True, "Updated"
            except Exception as error:
                return False, str(error)

    def set_voice_speed_profile(self, profile: str) -> tuple[bool, str]:
        profile = str(profile or "").lower()
        value = self._voice_speed_value(profile)
        if value is None: return False, "Use slow, normal, or fast"
        ok, message = self._replace_speech_config(length_scale=value)
        if ok:
            try: save_speech_preferences(length_scale=value)
            except OSError: pass
            print(f"[VOICE] Speed profile {profile.upper()} ({value:.2f})", flush=True)
            return True, profile
        return False, message

    def voice_model_options(self) -> list[Path]:
        voices = Path("voices")
        return sorted(voices.glob("*.onnx"), key=lambda p: p.name.lower()) if voices.exists() else []

    def set_voice_model(self, query: str) -> tuple[bool, str]:
        options = self.voice_model_options()
        if not options: return False, "No alternate Piper voices are installed"
        q = str(query or "").strip().lower()
        match = next((p for p in options if q in p.stem.lower() or q in p.name.lower()), None)
        if match is None: return False, "Voice not found"
        ok, message = self._replace_speech_config(model_path=str(match))
        if ok:
            try: save_speech_preferences(model_path=str(match))
            except OSError: pass
        return (True, match.stem) if ok else (False, message)

    def select_next_voice_model(self) -> tuple[bool, str]:
        options = self.voice_model_options()
        if len(options) < 2: return False, "No alternate Piper voice is installed"
        current = Path(str(self.speech.config.model_path)).name.lower()
        index = next((i for i,p in enumerate(options) if p.name.lower() == current), -1)
        selected = options[(index + 1) % len(options)]
        ok, message = self._replace_speech_config(model_path=str(selected))
        if ok:
            try: save_speech_preferences(model_path=str(selected))
            except OSError: pass
        return (True, selected.stem) if ok else (False, message)

    def _runtime_radio_help(self) -> str:
        return ("Voice controls: say enable, disable, toggle, or status, followed by Race Engineer, PRE coach, "
                "POST coach, lap summary, positive coach, race coach, SPEED COACH, CORNER COACH, STRAIGHT LINE COACH, speed coach voice, corner PRE, "
                "corner POST, straight voice, map gain loss, gain loss voice, damage coach, T T S, P T T, S T T, L L M, or recording. "
                "You can also set coaching mode, verbosity, voice speed, or change voice.")

    def handle_runtime_radio_command(self, text: str) -> tuple[bool, str, object | None]:
        """Handle deterministic runtime controls before ordinary telemetry intents.

        Returns (handled, response, deferred_action). TTS-off is deferred so its
        spoken acknowledgement is not destroyed by the command itself.
        """
        cmd = parse_runtime_radio_command(text)
        if cmd is None: return False, "", None
        states = self._runtime_control_states()
        if cmd.action == "HELP": return True, self._runtime_radio_help(), None
        if cmd.action == "STATUS":
            on = [CONTROL_LABELS.get(k,k) for k,v in states.items() if v]
            return True, "On: " + ", ".join(on) + ".", None
        if cmd.action == "CONTROL_STATUS":
            target=str(cmd.target); state=bool(states.get(target, False)); label=CONTROL_LABELS.get(target,target)
            if target in {"CCVOICE","CCPRE","CCPOST"} and not states.get("CORNER",False):
                return True, f"{label} is off because CORNER COACH is off.", None
            if target in {"SLVOICE"} and not states.get("STRAIGHT",False):
                return True, f"{label} is off because Straight Line Coach is off.", None
            if target in {"CORNER","STRAIGHT","GAINLOSS","GAINLOSSVOICE","DMGCOACH"} and not states.get("SPEED",False):
                return True, f"{label} is off because Speed Coach is off.", None
            if target in {"PRE","POST","LAP","POS","RACE"} and not states.get("ENGR",False):
                return True, f"{label} is off while Race Engineer is off.", None
            return True, f"{label} is {'on' if state else 'off'}.", None
        if cmd.action == "CONTROL_MULTI_SET":
            desired=bool(cmd.value); changed=[]
            for target in cmd.targets:
                ok,msg=self._set_runtime_control(target,desired)
                if not ok:
                    return True, f"Could not change {CONTROL_LABELS.get(target,target)}: {msg}.", None
                changed.append(CONTROL_LABELS.get(target,target))
            return True, f"{' and '.join(changed)} {'on' if desired else 'off'}.", None
        if cmd.action in {"CONTROL_SET","CONTROL_TOGGLE"}:
            target=str(cmd.target); desired=(not bool(states.get(target,False))) if cmd.action=="CONTROL_TOGGLE" else bool(cmd.value)
            label=CONTROL_LABELS.get(target,target)
            if target == "TTS" and not desired and states.get("TTS",False):
                return True, "Speech output off.", lambda: self.set_tts_enabled(False)
            ok,msg=self._set_runtime_control(target,desired)
            if not ok: return True, f"Could not change {label}: {msg}.", None
            if desired and target in {"CORNER","STRAIGHT","CCVOICE","CCPRE","CCPOST","SLVOICE","GAINLOSS","GAINLOSSVOICE","DMGCOACH"} and not self.corner_coach.enabled:
                return True, f"{label} preference on. Speed Coach is still off.", None
            if desired and target in {"PRE","POST","LAP","POS","RACE"} and not self._automatic_engineer_voice_enabled:
                return True, f"{label} preference on. Race Engineer is still off.", None
            return True, f"{label} {'on' if desired else 'off'}.", None
        if cmd.action == "MODE":
            ok,msg=self.set_coaching_mode(str(cmd.value)); return True,(f"Coaching mode {str(msg).replace('_',' ')}." if ok else str(msg)),None
        if cmd.action == "MODE_STATUS": return True,f"Coaching mode {self.live_coach.settings.mode.replace('_',' ')}.",None
        if cmd.action == "VERBOSITY":
            ok,msg=self.set_coaching_verbosity(str(cmd.value)); return True,(f"Radio detail {msg}." if ok else str(msg)),None
        if cmd.action == "VERBOSITY_STATUS": return True,f"Radio detail {self.live_coach.settings.verbosity}.",None
        if cmd.action == "VOICE_SPEED":
            ok,msg=self.set_voice_speed_profile(str(cmd.value)); return True,(f"Voice speed {msg}." if ok else str(msg)),None
        if cmd.action == "VOICE_SPEED_STATUS":
            ls=float(self.speech.config.length_scale); profile=min(("slow","normal","fast"),key=lambda p:abs(self._voice_speed_value(p)-ls))
            return True,f"Voice speed {profile}.",None
        if cmd.action == "NEXT_VOICE":
            ok,msg=self.select_next_voice_model(); return True,(f"Voice {msg}." if ok else msg),None
        if cmd.action == "VOICE_SELECT":
            ok,msg=self.set_voice_model(str(cmd.value)); return True,(f"Voice {msg}." if ok else msg),None
        if cmd.action == "VOICE_STATUS": return True,f"Voice {Path(str(self.speech.config.model_path)).stem}.",None
        return False,"",None

    def audio_device_options(self):
        """Return current input/output device choices for Control Center."""
        try:
            from .audio_devices import input_devices, output_devices
            return input_devices(), output_devices()
        except Exception as error:
            print(f"[AUDIO] Device discovery failed: {error}", flush=True)
            return [], []

    def set_microphone_device(self, device: int | None) -> tuple[bool, str]:
        ok, message = self.ptt.set_microphone_device(device)
        if ok:
            try:
                from .audio_devices import device_name
                message = device_name(device, direction="input")
            except Exception:
                pass
            print(f"[AUDIO] Microphone: {message}", flush=True)
        return ok, message

    def set_audio_output_device(self, device: int | None) -> tuple[bool, str]:
        ok, message = self.speech.set_output_device(device)
        if ok:
            try:
                from .audio_devices import device_name
                message = device_name(device, direction="output")
            except Exception:
                pass
            print(f"[AUDIO] Output: {message}", flush=True)
        return ok, message


    def _finish_evidence(self, category: str) -> str | None:
        """Return the strongest available evidence that the player's race is over.

        Final Classification remains authoritative, but EA recordings do not always
        retain it.  V0.9.14.6 therefore also accepts the player's LapData result
        status, or (after CHQF) a measured completion of the scheduled final lap.
        """
        if category == "final" and self.engine.state.extended.get("final") is not None:
            return "final"
        car = self.engine.state.player
        if car is not None:
            result_raw = getattr(getattr(car.lap, "result_status", None), "raw", None)
            if result_raw in (3, 4, 5, 6, 7):
                return "lap_result"
        if self._finish_pending_after_chequered:
            total = getattr(self.engine.state.session, "total_laps", None)
            completed = list(getattr(self.engine.performance, "completed", ()) or ())
            completed_laps = [x.get("lap") for x in completed if isinstance(x, dict) and isinstance(x.get("lap"), int)]
            if total and completed_laps and max(completed_laps) >= int(total):
                return "chequered_final_lap"
        return None

    def _publish_session_summary(self, now: float, *, authoritative: bool, speak: bool) -> list[EngineerMessage]:
        summary = self.session_summary_tracker.build(self.engine.state, self.engine.performance)
        if summary is None:
            return []
        summary["authoritative_final"] = bool(authoritative)
        self.session_summary = summary
        self.session_summary_revision += 1
        self.engine.state.extended["session_summary"] = summary

        uid = self.engine.state.session.uid
        save_key = (uid, bool(authoritative))
        if save_key != self._summary_saved_for_uid:
            try:
                paths = save_summary(summary)
                print(f"[SUMMARY] Saved: {paths[0]} | {paths[1]}", flush=True)
            except OSError as error:
                print(f"[SUMMARY] Save failed: {error}", flush=True)
            self._summary_saved_for_uid = save_key

        # V0.9.25.0: automatically attach the deterministic coaching report and
        # update local progress history.  Reusing a session-UID stem means the
        # later authoritative Final Classification safely refreshes the fallback.
        coach_settings = self.live_coach.settings
        coach_save_key = (uid, bool(authoritative))
        persist_live_history = persistent_history_allowed(self.telemetry_mode())
        if coach_settings.auto_reports and coach_save_key != self._coach_report_saved_for_uid:
            try:
                stem = f"session_{uid}" if uid is not None else None
                json_path, html_path, coach_report = save_coach_report(self.engine.performance, stem=stem, record_driver_history=persist_live_history)
                summary["coach_report_json"] = str(json_path)
                summary["coach_report_html"] = str(html_path)
                self.engine.state.extended["coach_report"] = coach_report
                try:
                    if self.recorder is not None and self.recorder.path is not None:
                        SessionLibrary().link_artifacts(Path(self.recorder.path).name,coach_report_json=json_path,coach_report_html=html_path,validation_json=coach_report.get("validation_json"),corner_validation=[self.corner_coach.validation.path] if self.corner_coach.validation.path is not None else None)
                except Exception:
                    pass
                print(f"[COACH REPORT] Saved: {json_path} | {html_path}", flush=True)
                # V1.9.1.0: personal history is LIVE GAME authority only. Replay
                # remains available for analysis/validation but must never alter the
                # driver's profile, track history, best laps or progress trends.
                if coach_settings.progress_history and persist_live_history:
                    potential = coach_report.get("potential") or {}
                    self.driver_history.upsert({
                        "session_uid": uid,
                        "authoritative_final": bool(authoritative),
                        "event_context": coach_report.get("event_context"),
                        "best_lap_s": potential.get("best_lap_s"),
                        "potential_lap_s": potential.get("potential_lap_s"),
                        "potential_gain_s": potential.get("potential_gain_s"),
                        "reference_lap_s": potential.get("reference_lap_s"),
                        "reference_gap_s": coach_report.get("total_reference_gap_s"),
                        "potential_vs_reference_s": potential.get("potential_vs_reference_s"),
                        "eligible_lap_count": potential.get("eligible_lap_count"),
                        "recurring_patterns": coach_report.get("recurring_patterns", [])[:10],
                        "advice_outcomes": coach_report.get("advice_outcomes", {}),
                        "technique_progress": (coach_report.get("technique_metrics") or {}).get("lap_time_progress"),
                    })
            except (OSError, ValueError) as error:
                print(f"[COACH REPORT] Save failed: {error}", flush=True)
            self._coach_report_saved_for_uid = coach_save_key
            self._coach_report_completed_count = len(list(getattr(self.engine.performance, "completed", ()) or ()))

        # V1.9.2.1: the Performance Hub is an independent LIVE-game history
        # authority, not a side effect of optional HTML/JSON coach reports.
        # With auto_reports disabled we still build the same deterministic report
        # in memory and upsert the driver-scoped session row.  Replay remains
        # read-only for persistent personal history.
        if persist_live_history:
            try:
                coach_report_for_history = self.engine.state.extended.get("coach_report")
                if not isinstance(coach_report_for_history, dict):
                    coach_report_for_history = build_coach_report(self.engine.performance)
                history_id = self.performance_history.record_session(
                    driver_profile_from_state(self.engine.state), summary, coach_report_for_history
                )
                # V2.9.1.3.5.29: Performance History is the authoritative session
                # identity. Link live Skill Evidence to that exact row immediately
                # so track/session corrections and deletes stay in real-time sync.
                linked_summary = dict(summary or {})
                linked_summary["performance_history_session_id"] = int(history_id)
                # V2.3.0: persist session-level skill evidence only from LIVE
                # measured history. This is idempotent and intentionally does not
                # calculate a career Driver Skill score.
                try:
                    evidence = self.skill_evidence.capture_f1_session(linked_summary, coach_report_for_history)
                    if evidence is not None:
                        try:
                            self.skill_evidence.reconcile_with_performance_history(driver_id=evidence.get("driver_id"))
                        except Exception:
                            pass
                        print(f"[SKILL EVIDENCE] {evidence.get('measurement_count', 0)} measurements stored.", flush=True)
                except Exception as evidence_error:
                    print(f"[SKILL EVIDENCE] Save failed: {evidence_error}", flush=True)
                print("[PERFORMANCE HUB] LIVE session stored.", flush=True)
            except Exception as history_error:
                # Performance history must never interrupt live engineering.
                print(f"[PERFORMANCE HUB] History save failed: {history_error}", flush=True)
        else:
            print("[PERFORMANCE HUB] Replay session ignored (live history unchanged).", flush=True)

        if speak and not self._finish_radio_sent:
            self._finish_radio_sent = True
            return [
                EngineerMessage(key="finish:result", priority=Priority.CRITICAL, text=summary["finish_call"], created_at=now, session_time_s=self.engine.state.session.session_time_s),
                EngineerMessage(key="finish:summary", priority=Priority.STRATEGY, text=summary["spoken_summary"], created_at=now, session_time_s=self.engine.state.session.session_time_s),
            ]
        return []

    def raw_datagram_received(self, data, source, now) -> None:
        """Lossless raw recording/capture before latest-state coalescing."""
        super().raw_datagram_received(data, source, now)
        if self.recorder is not None and self.recording_error is None:
            if self.recorder.last_error:
                self.recording_error = self.recorder.last_error
            else:
                self.recorder.record(data, now)
        if self.capture is not None and self.capture_error is None:
            try:
                self.capture.record(data)
            except OSError as error:
                self.capture_error = str(error)
                self._close_capture()

    def process_packet(self, data, source, now) -> None:
        # V0.9.17.2.4 source multiplexer: the live UDP listener stays alive even
        # while a replay is running. Only packets from the active source may
        # mutate deterministic state. This makes Replay -> Live instantaneous.
        tid = threading.get_ident()
        with self._runtime_lock:
            mode = self._telemetry_mode
            replay_tid = self._replay_thread_id
        replay_packet = replay_tid is not None and tid == replay_tid
        if mode == "replay" and not replay_packet:
            return
        if mode == "live" and replay_packet:
            return

        # `now` is captured immediately after recvfrom() returns. perf_counter_ns
        # then measures the software pipeline without wall-clock adjustments.
        measure_latency = True  # V1.5 formal validation: always collect cheap pipeline metrics
        packet_start_ns = time.perf_counter_ns() if measure_latency else 0
        header = super().process_packet(data, source, now)

        # Direct process_packet() callers (tests/replay utilities) retain the old
        # recording semantics. During the live socket loop every raw datagram was
        # already handed to raw_datagram_received() before any coalescing.
        if not getattr(self, "_raw_ingest_active", False):
            if not replay_packet and self.recorder is not None and self.recording_error is None:
                if self.recorder.last_error:
                    self.recording_error = self.recorder.last_error
                else:
                    self.recorder.record(data, now)
            if self.capture is not None and self.capture_error is None:
                try:
                    self.capture.record(data)
                except OSError as error:
                    self.capture_error = str(error)
                    self._close_capture()

        decode_start_ns = time.perf_counter_ns() if measure_latency else 0
        try:
            packet = decode_packet(data, header=header)
        except InvalidHeader:
            return  # V0.2 already counted this header failure.
        except UnsupportedPacket:
            self.unsupported_packets[data[6]] += 1
            return
        except MalformedPacket as error:
            self.malformed_bodies += 1
            self.last_body_error = str(error)
            return
        decode_end_ns = time.perf_counter_ns() if measure_latency else 0

        self.valid_bodies += 1
        self.runtime_benchmark.observe_header(packet.header)
        self._decoded_packet_at[packet.header.m_packetId] = now

        # V0.9.17.1: AI benchmark capture observes the same decoded all-car EA
        # packets without touching player state or the hardware transport path.
        # It only promotes a reference when a complete valid AI lap is measured.
        ai_old_uid = self.ai_benchmark.session_meta.get("session_uid") if self.ai_benchmark.enabled else None
        ai_new_best = self.ai_benchmark.observe(packet) if self.ai_benchmark.enabled else None
        ai_new_uid = self.ai_benchmark.session_meta.get("session_uid") if self.ai_benchmark.enabled else None
        ai_session_changed = ai_old_uid is not None and ai_new_uid is not None and ai_old_uid != ai_new_uid
        rival_old_uid = self.rival_benchmark.session_meta.get("session_uid") if self.rival_benchmark.enabled else None
        rival_new_best = self.rival_benchmark.observe(packet) if self.rival_benchmark.enabled else None
        rival_new_uid = self.rival_benchmark.session_meta.get("session_uid") if self.rival_benchmark.enabled else None
        rival_session_changed = rival_old_uid is not None and rival_new_uid is not None and rival_old_uid != rival_new_uid
        if packet.header.m_packetId == 3 and packet.body.name.startswith('UNKNOWN('):
            self.unknown_events += 1
        if packet.header.m_packetId == 3 and getattr(packet.body, 'code', None) == 'CHQF':
            self._finish_pending_after_chequered = True

        state_start_ns = time.perf_counter_ns() if measure_latency else 0
        with self._state_lock:
            state_changed = self.engine.update(packet, now)
            if state_changed:
                try:
                    self.driving_time_tracker.observe(self.engine.state, mode=self.telemetry_mode(), packet_category=CATEGORIES[packet.header.m_packetId])
                except Exception as driving_time_error:
                    print(f"[DRIVING TIME] Update skipped: {driving_time_error}", flush=True)
                self._handle_session_transition_locked()
            # Mid-lap reference changes are queued so a new reference can never
            # alter delta/coaching partway through the current lap.
            self._apply_pending_reference_locked()
            # Manual stored references are authoritative.  When none is selected,
            # coaching always uses the best valid lap measured in THIS session.
            # TT-rival / AI captures are still recorded and saved, but never silently
            # replace the user's current-session reference.
            self._enforce_manual_reference_track_locked()

            if rival_new_best is not None:
                rival_lap, rival_meta = rival_new_best
                stamp = (rival_meta.get("car_index"), rival_lap.get("lap_time_s"), rival_lap.get("sample_count"))
                if stamp != self._rival_best_announced:
                    self._rival_best_announced = stamp
                    print(
                        f"[TT RIVAL] Reference captured: {rival_meta.get('driver', 'Time Trial rival')} "
                        f"{rival_lap.get('lap_time_s'):.3f}s | {rival_lap.get('sample_count')} samples",
                        flush=True,
                    )
                if self.rival_reference_output is not None:
                    try:
                        self.rival_benchmark.save_best(self.rival_reference_output)
                    except OSError as error:
                        print(f"[TT RIVAL] Save failed: {error}", flush=True)
                if self.recording_mode()=="rival_reference" and self.rival_benchmark.strict_quality:
                    try:
                        paths=self.rival_benchmark.save_reference_bundle(self.reference_directory)
                        print(f"[CORNER COACH] Rival reference compiled: {paths['model']}",flush=True)
                    except (OSError,ValueError) as error:
                        print(f"[CORNER COACH] Reference compile rejected: {error}",flush=True)

            if ai_new_best is not None:
                ai_lap, ai_meta = ai_new_best
                stamp = (ai_meta.get("car_index"), ai_lap.get("lap"), ai_lap.get("lap_time_s"))
                if stamp != self._ai_best_announced:
                    self._ai_best_announced = stamp
                    difficulty = ai_meta.get("ai_difficulty")
                    diff_text = f" | AI {difficulty}" if difficulty is not None else ""
                    print(
                        f"[AI BENCHMARK] New best: {ai_meta.get('driver', 'AI')} "
                        f"lap {ai_lap.get('lap')} {ai_lap.get('lap_time_s'):.3f}s{diff_text}",
                        flush=True,
                    )
                if self.ai_reference_output is not None:
                    try:
                        self.ai_benchmark.save_best(self.ai_reference_output)
                    except OSError as error:
                        print(f"[AI BENCHMARK] Save failed: {error}", flush=True)
            if state_changed:
                self.session_summary_tracker.observe(self.engine.state)
            state_end_ns = time.perf_counter_ns() if measure_latency else 0
            category = CATEGORIES.get(packet.header.m_packetId)
            if state_changed and category in {"session", "lap", "telemetry", "status", "telemetry2", "final"}:
                self.wheel_bridge.update_from_state(self.engine.state)
            engineer_relevant = category in {"session", "lap", "events", "telemetry", "status", "damage", "tyres", "telemetry2", "final"}
            decision_start_ns = state_end_ns if measure_latency else 0
            # Car telemetry can arrive around 60 Hz.  Automatic Engineer does
            # not need to recompute safety/radio decisions on every one of those
            # packets; doing so makes the telemetry packet family substantially
            # more expensive than Motion (the map path).  Preserve immediate
            # evaluation for all non-telemetry categories, while sampling the
            # latest telemetry state at 20 Hz.
            engineer_due = True
            if category in {"telemetry", "lap"}:
                engineer_due = (
                    self._last_telemetry_engineer_eval_at is None
                    or now - self._last_telemetry_engineer_eval_at >= self._telemetry_engineer_interval_s
                )
            generated = (
                self.automatic_engineer.evaluate(self.engine.state, now, changed_category=category)
                if state_changed and engineer_relevant and engineer_due and not self._replay_rebuild else []
            )
            if state_changed and category in {"telemetry", "lap"} and engineer_due:
                self._last_telemetry_engineer_eval_at = now
            # Keep AutomaticEngineer evaluating while muted so its transition baselines
            # stay current. Only suppress delivery/radio ownership; coach/PTT remain live.
            if not self._automatic_engineer_voice_enabled:
                self.automatic_engineer.drain()
                generated = []
            decision_end_ns = time.perf_counter_ns() if measure_latency else 0

        # V0.9.25.0 integrated deterministic coaching suite.  It consumes the
        # same loss-guarded measured facts as offline analysis, adds pre-corner
        # reminders/lap summaries, and sees already-generated race-engineer calls
        # so critical context owns the radio before routine technique coaching.
        coach_due = True
        if category in {"telemetry", "lap"}:
            coach_due = (
                self._last_telemetry_coach_eval_at is None
                or now - self._last_telemetry_coach_eval_at >= self._telemetry_coach_interval_s
            )
        if state_changed and category in {"lap", "telemetry"} and coach_due and not self._replay_rebuild:
            if category in {"telemetry", "lap"}:
                self._last_telemetry_coach_eval_at = now
            # V1.1 CORNER COACH owns PRE/POST whenever a hybrid reference model is
            # available. The older suite still supplies lap summaries/positive
            # calls, but cannot emit duplicate turn PRE/POST messages.
            corner_messages=self.corner_coach.observe(self.engine.performance,self.engine.state,now)
            corner_status=self.corner_coach.status(self.engine.performance,self.engine.state)
            self._sync_corner_speech_gates(damage_blocked=bool(corner_status.get("damage_coaching_blocked")))
            hybrid_ready=bool(corner_status.get("reference_ready") and corner_status.get("zones"))
            live_coaching = self.live_coach.observe(
                self.engine.performance, self.engine.state, now,
                generated_messages=list(generated)+list(corner_messages),
                # CORNER COACH is now the sole owner of corner PRE/POST. The
                # legacy integrated coach remains available for lap summaries,
                # positive calls and race-mode policy only.
                suppress_pre_post=True,
            )
            # Race Engineer master and CORNER COACH master are independent.
            # Keep observing the legacy coach so its memory/state stays current,
            # but do not deliver its automatic messages while ENGR is OFF.
            if not self._automatic_engineer_voice_enabled:
                live_coaching = []
            if corner_messages or live_coaching:
                generated = list(generated) + list(corner_messages) + list(live_coaching)
            coach_status = self.live_coach.status()
            self.engine.state.extended['coaching_suite'] = coach_status
            self.engine.state.extended['corner_coach'] = corner_status
            self.engine.state.extended['post_corner_coaching'] = coach_status.get('post_corner', {})
            ref_stamp=(corner_status.get("reference_fingerprint"), corner_status.get("reference_lap_time_s"), self.current_reference_selection())
            if ref_stamp != self._last_reference_validation_stamp:
                self._last_reference_validation_stamp=ref_stamp
                self.validation_bundle.reference(self.engine.state, selection=str(ref_stamp[2]), fingerprint=ref_stamp[0], lap_time_s=ref_stamp[1], event="reference_update")
                self.validation_transcript.marker(self.engine.state,"reference_authority",selection=str(ref_stamp[2]),reference_fingerprint=ref_stamp[0],reference_lap_time_s=ref_stamp[1])
            if measure_latency:
                decision_end_ns = time.perf_counter_ns()

        if state_changed and not self._replay_silent:
            # Finish/result radio has priority over the ordinary final-lap and lap-
            # comparison chatter. Final Classification is preferred, but if a
            # recording ends before that packet we fall back to finished LapData or
            # CHQF + a measured completion of the scheduled last lap.
            finish_evidence = self._finish_evidence(category)
            if finish_evidence and not self._replay_rebuild:
                authoritative = finish_evidence == "final"
                finish_messages = self._publish_session_summary(
                    now, authoritative=authoritative, speak=self._automatic_engineer_voice_enabled
                )
                if authoritative:
                    self._summary_authoritative = True
                if finish_messages:
                    generated = [m for m in generated if not (m.key.startswith('lap:') or m.key.startswith('performance:lap:'))]
                    generated = finish_messages + list(generated)

            # V1.3.0.0: Final Classification can precede the recorder's last lap
            # reconciliation by a few packets. Refresh the post-session report once
            # the completed-lap set grows, so the final JSON/HTML cannot remain an
            # early empty/partial snapshot. This does not affect radio or coaching.
            if self.session_summary is not None and self.live_coach.settings.auto_reports and not replay_packet:
                completed_count = len(list(getattr(self.engine.performance, "completed", ()) or ()))
                total_laps = getattr(self.engine.state.session, "total_laps", None)
                race_complete = isinstance(total_laps, int) and total_laps > 0 and completed_count >= total_laps
                final_ready = race_complete or (not total_laps and self._summary_authoritative)
                if final_ready and completed_count > self._coach_report_completed_count:
                    try:
                        uid = self.engine.state.session.uid
                        stem = f"session_{uid}" if uid is not None else None
                        json_path, html_path, coach_report = save_coach_report(self.engine.performance, stem=stem, record_driver_history=persistent_history_allowed(self.telemetry_mode()))
                        self.session_summary["coach_report_json"] = str(json_path)
                        self.session_summary["coach_report_html"] = str(html_path)
                        self.engine.state.extended["coach_report"] = coach_report
                        try:
                            if self.recorder is not None and self.recorder.path is not None:
                                SessionLibrary().link_artifacts(Path(self.recorder.path).name,coach_report_json=json_path,coach_report_html=html_path,validation_json=coach_report.get("validation_json"),corner_validation=[self.corner_coach.validation.path] if self.corner_coach.validation.path is not None else None)
                        except Exception:
                            pass
                        self._coach_report_completed_count = completed_count
                        # Keep the LIVE-only Performance Hub row synchronized with
                        # the refreshed final-lap coach report. record_session is an
                        # idempotent driver-scoped upsert for this session.
                        if persistent_history_allowed(self.telemetry_mode()):
                            try:
                                history_id = self.performance_history.record_session(
                                    driver_profile_from_state(self.engine.state), self.session_summary, coach_report
                                )
                                try:
                                    linked_summary = dict(self.session_summary or {})
                                    linked_summary["performance_history_session_id"] = int(history_id)
                                    evidence = self.skill_evidence.capture_f1_session(linked_summary, coach_report)
                                    if evidence is not None:
                                        try:
                                            self.skill_evidence.reconcile_with_performance_history(driver_id=evidence.get("driver_id"))
                                        except Exception:
                                            pass
                                except Exception as evidence_error:
                                    print(f"[SKILL EVIDENCE] Final refresh failed: {evidence_error}", flush=True)
                            except Exception as history_error:
                                print(f"[PERFORMANCE HUB] Final history refresh failed: {history_error}", flush=True)
                        print(f"[COACH REPORT] Refreshed final data: {json_path} | {html_path}", flush=True)
                    except OSError as error:
                        print(f"[COACH REPORT] Refresh failed: {error}", flush=True)

            # V1.3.8.0 advanced race evidence + unified coaching arbitration.
            # The learner only records observed lap/pit/damage evidence; it never
            # fabricates pit loss or damage cost. The arbitration gate runs after
            # Race Engineer + CORNER COACH + Performance Coach have all produced
            # messages so race context owns the final delivery decision.
            try:
                session_type_name = str(getattr(getattr(self.engine.state.session, "session_type", None), "name", "") or "").lower()
                if "race" in session_type_name:
                    packet_id = int(getattr(packet.header, "m_packetId", -1))
                    # Strategy evidence only changes on session/lap/status/damage/tyre
                    # families.  Do not rescan completed laps on 60 Hz motion or
                    # telemetry packets.  This keeps long race replays and the live
                    # packet path effectively zero-cost when no strategy evidence can
                    # have changed.
                    if packet_id in {1, 2, 7, 10, 12}:
                        self.strategy_learner.observe(self.engine.state)

                    # The full strategy assessment is intentionally capped at 4 Hz
                    # unless a strategy-relevant packet arrives after the cache age.
                    # All exposed values are race-state projections rather than
                    # per-frame graphics, so faster recomputation adds no decision
                    # value and materially hurts replay throughput.
                    due_assess = (
                        self._last_strategy_assess_at is None
                        or now - self._last_strategy_assess_at >= 0.25
                    )
                    if due_assess and packet_id in {1, 2, 7, 10, 12}:
                        advanced = assess_advanced_strategy(self.engine.state)
                        advanced_payload = advanced.to_dict()
                        self.engine.state.extended["advanced_strategy"] = advanced_payload
                        # Keep strategy computation responsive at 4 Hz, but persist
                        # heavyweight validation evidence at a bounded cadence. Replay
                        # uses 5 s because it is analysis-only; live keeps 1 s evidence.
                        validation_interval = 5.0 if replay_packet else 1.0
                        due_validation = (
                            self._last_strategy_validation_at is None
                            or now - self._last_strategy_validation_at >= validation_interval
                        )
                        if due_validation:
                            # Signature intentionally excludes session time; the payload
                            # itself is the measured decision state we want to retain.
                            signature = repr(sorted(advanced_payload.items()))
                            # Record periodically even when unchanged so long sessions
                            # retain auditable heartbeats without 4 Hz disk/memory churn.
                            self.validation_bundle.strategy(self.engine.state, advanced_payload, reason="strategy_sample")
                            self.validation_transcript.decision(self.engine.state, "strategy", advanced.pit_window, assessment=advanced_payload)
                            self._last_strategy_validation_signature = signature
                            self._last_strategy_validation_at = now
                        self._last_strategy_assess_at = now

                    # Arbitration must still run whenever a message is produced so a
                    # critical/race-control/combat gate can suppress it immediately.
                    # With no candidate message, evaluate context only on Lap/Status/
                    # Damage packets at <=10 Hz to detect combat entry/resume calls.
                    due_context = (
                        self._last_strategy_context_at is None
                        or now - self._last_strategy_context_at >= 0.10
                    )
                    should_arbitrate = bool(generated) or (due_context and packet_id in {2, 7, 10})
                    if should_arbitrate:
                        stable_context = self._race_context_hysteresis.update(self.engine.state, now)
                        arb = arbitrate_messages(
                            generated, self.engine.state,
                            previous_level=self._last_race_context_level, now=now,
                            context=stable_context,
                        )
                        filtered = []
                        for msg in arb.accepted:
                            if msg.key == "race_context:combat_exit":
                                if self._last_combat_call_at is not None and now - self._last_combat_call_at < 15.0:
                                    continue
                                self._last_combat_call_at = now
                            elif msg.key == "race_context:resume":
                                if self._last_resume_call_at is not None and now - self._last_resume_call_at < 15.0:
                                    continue
                                self._last_resume_call_at = now
                            filtered.append(msg)
                        generated = filtered
                        self.engine.state.extended["race_message_arbitration"] = {
                            "context": arb.context, "suppressed_keys": list(arb.suppressed_keys),
                        }
                        self._last_race_context_level = arb.context.get("level")
                        self._last_strategy_context_at = now
                else:
                    self._last_race_context_level = None
                    self._race_context_hysteresis.reset()
                    self._last_combat_call_at = None
                    self._last_resume_call_at = None
                    self._last_strategy_assess_at = None
                    self._last_strategy_context_at = None
            except Exception as error:
                # Strategy enrichment must never block the real-time telemetry path.
                self.engine.state.extended["advanced_strategy_error"] = str(error)

            # Measured lap comparison is also a deterministic decision, so include
            # its concise radio-generation work in the packet->decision metric.
            # Do not add a final-lap comparison ahead of/after the finish call.
            self._queue_live_history_autosave_locked()
            perf = self.engine.state.extended.get('measured_performance', {})
            cmp = perf.get('latest_comparison') if isinstance(perf, dict) else None
            if cmp and cmp.get('lap') != self._last_performance_lap_announced:
                dt = cmp.get('lap_time_s_delta')
                loss = cmp.get('largest_100m_loss_s')
                if (self._automatic_engineer_voice_enabled and not self.live_coach.settings.lap_summary and not self._finish_radio_sent
                        and ((dt is not None and abs(dt) >= 0.25) or (loss is not None and loss >= 0.15))):
                    perf_rec = self.engine.performance
                    if getattr(perf_rec, 'reference_mode', None) == 'external' and getattr(perf_rec, 'external_reference', None) is not None:
                        from .performance_coach import coaching_summary
                        cur = next((x for x in reversed(perf_rec.completed) if x.get('lap') == cmp.get('lap')), None)
                        text = coaching_summary(cur, perf_rec.external_reference)
                    else:
                        from .measured_performance import radio_summary
                        text = radio_summary(self.engine.state, 'compare')
                    generated = list(generated) + [EngineerMessage(
                        key=f"performance:lap:{cmp.get('lap')}", priority=Priority.COACHING,
                        text=text, created_at=now,
                        session_time_s=self.engine.state.session.session_time_s)]
                self._last_performance_lap_announced = cmp.get('lap')
            decision_end_ns = time.perf_counter_ns() if measure_latency else 0

            # If Final Classification arrives after the fallback finish call, refresh
            # the stored/overlay summary with authoritative classification facts but
            # do not speak the victory/result call twice.
            if category == "final" and not self._replay_rebuild and not self._summary_authoritative:
                self._publish_session_summary(now, authoritative=True, speak=False)
                self._summary_authoritative = True
            dispatch_start_ns = decision_end_ns if measure_latency else 0
            self._submit_radio(generated)
            dispatch_end_ns = time.perf_counter_ns() if measure_latency else 0

            if self.engineer_only and generated:
                print('\n' + format_messages(generated), flush=True)
                self.automatic_engineer.drain()
        else:
            dispatch_start_ns = decision_end_ns
            dispatch_end_ns = decision_end_ns
            if state_changed and self._replay_silent:
                self.automatic_engineer.drain()

        if measure_latency:
            self.latency.observe_packet(
                decode_ns=decode_end_ns - decode_start_ns,
                state_ns=state_end_ns - state_start_ns,
                decision_ns=decision_end_ns - decision_start_ns,
                core_ns=decision_end_ns - packet_start_ns,
                dispatch_ns=dispatch_end_ns - dispatch_start_ns,
                decisions=len(generated),
            )


    def _on_ptt_release(self, capture_path) -> None:
        self._driver_radio_release_at = time.perf_counter() if capture_path is not None else None
        self._driver_radio_transcript_at = None
        self._driver_radio_response_queued_at = None
        # Keep TTS silent while Whisper is processing a valid capture. If capture
        # failed (or STT is disabled), return the radio immediately.
        if capture_path is None or not self.stt.config.enabled or self.stt.last_error:
            self.speech.end_listening()

    def _on_stt_complete(self, _wav_path) -> None:
        # For an LLM/strategy request, keep ownership of the radio until the
        # requested answer is queued. This prevents system chatter from speaking
        # during the LLM wait.
        if not self._radio_reasoning_pending:
            self.speech.end_listening()

    def _on_transcript(self, transcript, _wav_path) -> None:
        self._driver_radio_transcript_at = time.perf_counter()
        if self._driver_radio_release_at is not None:
            print(f"[RADIO LATENCY] PTT release -> transcript {(self._driver_radio_transcript_at - self._driver_radio_release_at) * 1000.0:.0f} ms", flush=True)
        # Reject the small family of well-known Whisper silence/noise hallucinations
        # before they reach the radio parser/transcript.  These were observed in
        # real PTT validation as "thanks for watching" / "see you in the next
        # video" and are not driver radio requests.
        if is_likely_stt_hallucination(transcript):
            print(f'[STT] Ignored likely silence/noise hallucination: "{transcript}"', flush=True)
            return
        # STT runs on its own worker. Copy the current state under a short lock so
        # voice answering never races telemetry mutation and never blocks UDP while formatting.
        with self._state_lock:
            state = copy.deepcopy(self.engine.state)
        normalized = normalize_radio_text(transcript)
        if normalized and normalized != " ".join(str(transcript).split()).strip().lower():
            print(f'[STT] Radio normalized: "{normalized}"', flush=True)
        # A Whisper repetition loop is not useful as a literal transcript. Keep
        # ordinary mis-hearings visible, but use the cleaned command for pathological
        # long repetitions so the radio window stays readable.
        display_transcript = transcript if len(str(transcript).split()) <= 24 else (normalized or transcript)
        self.radio_transcript.add_driver(
            display_transcript, session_time_s=state.session.session_time_s, interpreted_text=normalized
        )
        self.validation_transcript.driver(state, display_transcript, normalized)
        handled, control_response, deferred_action = self.handle_runtime_radio_command(normalized or transcript)
        if handled:
            with self._state_lock:
                session_time_s = self.engine.state.session.session_time_s
            self.speech.prepare_radio_response()
            print("[VOICE] Intent: RUNTIME_CONTROL", flush=True)
            self._speak_voice_response(control_response, session_time_s)
            if deferred_action is not None:
                timer = threading.Timer(1.5, deferred_action); timer.daemon = True; timer.start()
            return
        result = handle_voice_request(normalized or transcript, state)
        # Voice reference changes obey the same lap-boundary authority rule as
        # Control Center changes. Never switch the live comparison clock mid-lap.
        if result.intent in (VoiceIntent.REFERENCE_SET, VoiceIntent.REFERENCE_PREVIOUS, VoiceIntent.REFERENCE_BEST):
            mode = ("manual" if result.intent == VoiceIntent.REFERENCE_SET
                    else "previous" if result.intent == VoiceIntent.REFERENCE_PREVIOUS
                    else "best")
            _ok, response = self.select_measured_reference(mode)
            with self._state_lock:
                session_time_s = self.engine.state.session.session_time_s
            self.speech.prepare_radio_response()
            self._speak_voice_response(response, session_time_s)
            return
        self.speech.prepare_radio_response()
        print(f"[VOICE] Intent: {result.intent.value}", flush=True)
        if result.intent == VoiceIntent.PIT_RECOMMENDATION:
            # V0.9.14.3: a radio request must never go silent because the pit
            # strategy formatter hit an unexpected edge case.  The generic voice
            # answer is already safe for a missing live car, so preserve it when
            # telemetry is unavailable and use it as a defensive fallback if the
            # richer deterministic service-plan path raises.
            if state.player is not None:
                try:
                    pit = assess_pit(state)
                    print(f"[PIT] Offline signal: {pit.recommendation_hint} | confidence: {pit.confidence} | score: {pit.decision_score}", flush=True)
                    print(f"[PIT] Checked: {', '.join(pit.factors_checked) or 'none'}", flush=True)
                    if pit.reasons: print(f"[PIT] Evidence: {'; '.join(pit.reasons)}", flush=True)
                    if pit.nonserviceable_warnings: print(f"[PIT] Non-serviceable: {'; '.join(pit.nonserviceable_warnings)}", flush=True)
                    if pit.missing_factors: print(f"[PIT] Missing: {', '.join(pit.missing_factors)}", flush=True)
                    plan = service_plan(state)
                    game_window={"ideal_lap":getattr(state.session,"pit_stop_window_ideal_lap",None),"latest_lap":getattr(state.session,"pit_stop_window_latest_lap",None)}
                    self.validation_bundle.pit(state,decision=pit.recommendation_hint,reasons=pit.reasons,game_window=game_window)
                    self.validation_transcript.decision(state,"pit",pit.recommendation_hint,reasons=list(pit.reasons),game_window=game_window,automatic_summary=plan.automatic_summary)
                    result = type(result)(result.intent, plan.automatic_summary)
                except Exception as error:
                    print(f"[PIT] Strategy response fallback after error: {error}", flush=True)
            else:
                print("[PIT] Live car data unavailable; returning explicit radio fallback.", flush=True)
        elif result.intent == VoiceIntent.COMPLEX_REASONING:
            fallback = "Reasoning is unavailable right now."
            self._pending_llm_fallback = fallback
            self._radio_reasoning_pending = True
            if self.llm.submit(transcript, state):
                print("[VOICE] Routed to local LLM reasoning.", flush=True)
                return
            self._pending_llm_fallback = None
            self._radio_reasoning_pending = False
            result = type(result)(result.intent, fallback)
        self._speak_voice_response(result.response, state.session.session_time_s)

    def _on_llm_response(self, response: str) -> None:
        with self._state_lock:
            session_time_s = self.engine.state.session.session_time_s
        if response == "Reasoning is unavailable right now." and self._pending_llm_fallback:
            response = self._pending_llm_fallback
            print("[PIT] LLM unavailable; using deterministic pit fallback.", flush=True)
        self._pending_llm_fallback = None
        self.speech.prepare_radio_response()
        self._speak_voice_response(response, session_time_s)
        self._radio_reasoning_pending = False
        self.speech.end_listening()

    def _speak_voice_response(self, response: str, session_time_s) -> None:
        response = concise_engineer_text(str(response or "").strip(), getattr(self.live_coach.settings, "verbosity", "normal"))
        if not response:
            self.speech.cancel_driver_response()
            self.speech.end_listening()
            return
        print(f"[VOICE] Engineer: {response}", flush=True)
        self._driver_radio_response_queued_at = time.perf_counter()
        if self._driver_radio_transcript_at is not None:
            print(f"[RADIO LATENCY] transcript -> response queued {(self._driver_radio_response_queued_at - self._driver_radio_transcript_at) * 1000.0:.0f} ms", flush=True)
        self._submit_radio([EngineerMessage(
            key="voice:response", priority=Priority.STRATEGY, text=response,
            created_at=time.monotonic(), session_time_s=session_time_s,
        )])

    @staticmethod
    def _is_corner_coach_message(message: EngineerMessage) -> bool:
        key=str(getattr(message, "key", "") or "")
        return key.startswith("corner:") or key.startswith("straight:")

    @staticmethod
    def _speed_coach_source(message: EngineerMessage) -> str:
        key=str(getattr(message,"key","") or "")
        if key.startswith("straight:"):return "straight_line_coach"
        if key.startswith("corner:"):return "corner_coach"
        return "race_engineer"

    def _record_radio_transcript(self, message: EngineerMessage) -> None:
        # SPEED COACH owns a dedicated transcript embedded in its overlay. The
        # ordinary Radio Transcript is therefore Race Engineer / driver radio only.
        store = self.corner_transcript if self._is_corner_coach_message(message) else self.radio_transcript
        store.add_engineer(message)

    def _on_radio_audio_start(self, message: EngineerMessage) -> None:
        """Record actual audio start without hiding generated CORNER COACH text.

        SPEED COACH owns a dedicated on-screen transcript.  From V1.1.0.15 its
        text is appended at submit time so a useful visual cue remains visible even
        when TTS later drops/pre-empts the audio for real-time safety.  Ordinary
        Race Engineer radio keeps the historical heard-only transcript semantics.
        """
        if not self._is_corner_coach_message(message):
            self._record_radio_transcript(message)
        if str(getattr(message, "key", "") or "") == "voice:response":
            now = time.perf_counter()
            if self._driver_radio_response_queued_at is not None:
                print(f"[RADIO LATENCY] response queued -> audio {(now - self._driver_radio_response_queued_at) * 1000.0:.0f} ms", flush=True)
            if self._driver_radio_release_at is not None:
                print(f"[RADIO LATENCY] PTT release -> audio {(now - self._driver_radio_release_at) * 1000.0:.0f} ms total", flush=True)
            self._driver_radio_release_at = None
            self._driver_radio_transcript_at = None
            self._driver_radio_response_queued_at = None
        if self._is_corner_coach_message(message):
            self.corner_coach.validation.audio_start(message)

    def _on_radio_delivery_event(self, message: EngineerMessage, outcome: str, details: dict | None = None) -> None:
        """Forward deterministic TTS scheduling outcomes to the validation trace."""
        try:
            source=self._speed_coach_source(message)
            self.validation_transcript.message(self.engine.state,message,source,event=str(outcome).lower())
        except Exception:
            pass
        if self._is_corner_coach_message(message):
            self.corner_coach.validation.delivery_event(message, outcome, **(details or {}))

    def _submit_radio(self, messages) -> None:
        """Submit radio without coupling transcript rendering to telemetry.

        With TTS enabled, the TTS worker records a line at actual audio start.
        With TTS disabled, retain the generated text as a useful silent transcript
        for replay/debugging without changing the decision path.
        """
        if not messages:
            return
        messages = tuple(messages)
        for message in messages:
            try:
                source=self._speed_coach_source(message)
                self.validation_transcript.message(self.engine.state,message,source,event="submitted")
                key=str(getattr(message,"key","") or "")
                if key.startswith("pit:") or key.startswith("strategy:pit"):
                    game_window={"ideal_lap":getattr(self.engine.state.session,"pit_stop_window_ideal_lap",None),"latest_lap":getattr(self.engine.state.session,"pit_stop_window_latest_lap",None)}
                    self.validation_bundle.pit(self.engine.state,decision=key,reasons=(str(getattr(message,"text","") or ""),),game_window=game_window)
                    self.validation_transcript.decision(self.engine.state,"pit_radio",key,text=str(getattr(message,"text","") or ""),game_window=game_window)
            except Exception:
                pass
            if self._is_corner_coach_message(message):
                # Visual SPEED COACH transcript records generated coaching text
                # immediately. Audio delivery is tracked separately in validation.
                self._record_radio_transcript(message)
                self.corner_coach.validation.radio_submit(message)
        if not self.speech.available:
            for message in messages:
                if not self._is_corner_coach_message(message):
                    self._record_radio_transcript(message)
        self.speech.submit(messages)

    def print_status(self, packets_per_second, now) -> None:
        if self.engineer_only:
            if self.latency_stats:
                print(self.latency.format_compact(), flush=True)
            return
        with self._state_lock:
            messages = self.automatic_engineer.drain()
        if self.packet_stats:
            super().print_status(packets_per_second, now)
            print(format_messages(messages))
        else:
            print(format_state(self.engine.state, now))
            print(format_messages(messages))
            print(f'Packets: {packets_per_second:.1f} pps | Total UDP: {self.total_packets}')
            print(f'Headers invalid: {sum(self.invalid_reasons.values())} | Unknown IDs: {sum(self.unknown_ids.values())}')
            if self.invalid_reasons:
                print(f'Last header error: {self.last_error}')
            if self.show_sizes:
                print('Packet sizes: ' + ', '.join(f'{size} bytes: {count}' for size, count in sorted(self.packet_sizes.items())))
        print(f'Bodies valid: {self.valid_bodies} | Malformed: {self.malformed_bodies} | Unsupported/ID-only: {sum(self.unsupported_packets.values())}')
        print(f'Live stale high-rate packets coalesced: {int(getattr(self, "coalesced_packets", 0))}')
        by_pid=getattr(self,'coalesced_by_packet_id',{}) or {}
        if by_pid:
            labels={0:'motion',6:'telemetry',13:'motionex',15:'lappos',16:'telemetry2'}
            details=', '.join(f"{labels.get(pid,str(pid))}={count}" for pid,count in sorted(by_pid.items()) if count)
            if details:
                print('Coalesced by family: ' + details + ' | LapData=PROTECTED')
        print(f'Older/duplicate updates ignored: {self.engine.out_of_order} | Unknown events: {self.unknown_events}')
        # V0.8.5 UDP health: distinguish no UDP from missing car packet families.
        packet_names = {0:"motion",1:"session",2:"lap",4:"participants",5:"setups",6:"telemetry",7:"status",10:"damage",12:"tyres",16:"telemetry2"}
        if self.last_packet_at is None or now - self.last_packet_at >= 3.0:
            print('[UDP HEALTH] GAME UDP STOPPED - no recent datagrams')
        else:
            important=(1,2,4,6,7,10,12,16)
            missing=[]
            for pid in important:
                seen=self._decoded_packet_at.get(pid)
                if seen is None or now-seen>=5.0:
                    missing.append(packet_names[pid])
            if missing:
                print('[UDP HEALTH] UDP ACTIVE / CAR PACKETS MISSING: ' + ', '.join(missing))
            else:
                print('[UDP HEALTH] UDP ACTIVE / required race packets current')
        if self.malformed_bodies:
            print(f'Last body error: {self.last_body_error}')
        if self.capture:
            print(f'Capture: {self.capture.count}/{self.capture.limit} | {self.capture.path or "awaiting packets"}')
        if self.capture_error:
            print(f'Capture disabled: {self.capture_error}')
        if self.recorder:
            print(f'Recording: {self.recorder.count} packets | pending writes: {self.recorder.pending} | {self.recorder.path or "awaiting packets"}')
            if self.recorder.last_error and self.recording_error is None:
                self.recording_error = self.recorder.last_error
        if self.recording_error:
            print(f'Recording disabled: {self.recording_error}')
        if self.latency_stats:
            print(self.latency.format_compact())
        print(flush=True)

    def run(self, stop_event=None) -> None:
        stop_event = stop_event if stop_event is not None else threading.Event()
        telemetry_error = []

        def telemetry_worker():
            try:
                super(RaceStateReceiver, self).run(stop_event)
            except BaseException as error:
                telemetry_error.append(error)
                stop_event.set()

        try:
            self.wheel_bridge.start()
            self.stt.start()
            if self.ptt.config.enabled and self.ptt.config.backend == "hid":
                self.ptt.start()
                super().run(stop_event)
            elif self.ptt.config.enabled:
                telemetry_thread = threading.Thread(
                    target=telemetry_worker, name="race-engineer-telemetry", daemon=True
                )
                telemetry_thread.start()
                self.ptt.run_forever(stop_event)
                stop_event.set()
                telemetry_thread.join(timeout=3.0)
                if telemetry_error:
                    raise telemetry_error[0]
            else:
                super().run(stop_event)
        finally:
            stop_event.set()
            self.ptt.close(wait=True)
            self.stt.close(wait=True)
            self.llm.close(wait=True)
            self.speech.close(wait=True)
            self.wheel_bridge.close(wait=True)
            self._close_capture()
            self._close_recorder()
            self._close_history_autosave()
            try:
                self.driving_time_tracker.flush()
            except Exception as driving_time_error:
                print(f"[DRIVING TIME] Final flush skipped: {driving_time_error}", flush=True)
            with self._state_lock:
                self._finalize_validation_session_locked(self._last_runtime_session_uid)
            try:
                track=getattr(getattr(self.engine.state.session,"track",None),"name",None) or getattr(getattr(self.engine.state.session,"track",None),"label",None)
                weekend=self.validation_bundle.build_weekend_bundle(track=track)
                if weekend is not None: print(f"[VALIDATION] Weekend bundle: {weekend}",flush=True)
            except Exception:
                pass
            self.validation_transcript.close(wait=True)

    def reset_replay_state(self) -> None:
        """Reset deterministic receiver state before an interactive replay seek."""
        with self._state_lock:
            self.engine = RaceStateEngine()
            self._restore_manual_reference_locked()
            self.automatic_engineer.reset()
            self._decoded_packet_at.clear()
            self._last_performance_lap_announced = None
            self.live_coach.reset_session()
            self.session_summary_tracker = SessionSummaryTracker()
            self.session_summary = None
            self.session_summary_revision = 0
            self._finish_radio_sent = False
            self._finish_pending_after_chequered = False
            self._summary_saved_for_uid = None
            self._summary_authoritative = False
            self._coach_report_saved_for_uid = None
            self._coach_report_completed_count = -1
            self._history_autosave_completed_count = 0
            self._history_autosave_game_lap_count = 0
            self.total_packets = 0
            self.packet_sizes.clear()
            self.source = None
            self.last_packet_at = None
            self.packet_types.clear()
            self.previous_types.clear()
            self.invalid_reasons.clear()
            self.unknown_ids.clear()
            self.packet_versions.clear()
            self.latest_header = None
            self.telemetry_source = None
            self.last_valid_at = None
            self.valid_bodies = 0
            self.malformed_bodies = 0
            self.unsupported_packets.clear()
            self.unknown_events = 0
            self.last_body_error = '--'

    def finish_replay_seek(self) -> None:
        """Clear transient engineer state after silent fast-forward reconstruction."""
        with self._state_lock:
            uid = self.engine.state.session.uid
            self.automatic_engineer.reset(uid)
            self._last_performance_lap_announced = None
        self.live_coach.reset_session()

    def export_replay_checkpoint(self):
        """Return a compact deterministic checkpoint for interactive replay seeks.

        V0.9.13.0: serializing the deterministic engine graph with pickle is
        substantially faster than recursively ``deepcopy``-ing it and produces
        an immutable byte snapshot.  Checkpoints are replay-local, never trusted
        external input, and are restored only by this same process/version.
        """
        with self._state_lock:
            payload = (
                1,  # checkpoint schema version
                self.engine,
                self._decoded_packet_at,
                self.latest_header,
                self.telemetry_source,
                self.last_valid_at,
            )
            return pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)

    def restore_replay_checkpoint(self, checkpoint) -> None:
        """Restore a checkpoint without replaying earlier packets again.

        Deserialization happens before taking the state lock, keeping the lock
        hold time to the final pointer/state swap.  The legacy dictionary format
        is still accepted for tests or checkpoints created earlier in the same
        development session.
        """
        if isinstance(checkpoint, (bytes, bytearray, memoryview)):
            version, engine, decoded_packet_at, latest_header, telemetry_source, last_valid_at = pickle.loads(checkpoint)
            if version != 1:
                raise ValueError(f"Unsupported replay checkpoint version: {version}")
        else:
            # Backward-compatible fallback for pre-V0.9.13 in-memory checkpoints.
            engine = copy.deepcopy(checkpoint["engine"])
            decoded_packet_at = copy.deepcopy(checkpoint.get("decoded_packet_at", {}))
            latest_header = copy.deepcopy(checkpoint.get("latest_header"))
            telemetry_source = checkpoint.get("telemetry_source")
            last_valid_at = checkpoint.get("last_valid_at")

        with self._state_lock:
            self.engine = engine
            self._restore_manual_reference_locked()
            self._decoded_packet_at = decoded_packet_at
            self.latest_header = latest_header
            self.telemetry_source = telemetry_source
            self.last_valid_at = last_valid_at
            uid = self.engine.state.session.uid
            self.automatic_engineer.reset(uid)
            self._last_performance_lap_announced = None
        self.live_coach.reset_session()

    def run_replay(self, replay_file, *, speed=1.0, realtime=True, stop_event=None, pause_event=None, controller=None) -> int:
        """Replay telemetry while keeping the normal interactive radio stack alive.

        Replay replaces only the UDP source. PTT, microphone capture, STT, live
        radio questions and TTS continue to run exactly as they do in live mode.
        """
        stop_event = stop_event if stop_event is not None else threading.Event()
        replay_result = {"count": 0}
        replay_error = []

        def replay_worker():
            try:
                replay_result["count"] = replay_into(
                    self, replay_file, speed=speed, realtime=realtime, stop_event=stop_event, pause_event=pause_event, controller=controller
                )
            except BaseException as error:
                replay_error.append(error)
            finally:
                stop_event.set()

        try:
            self.wheel_bridge.start()
            self.stt.start()
            if self.ptt.config.enabled and self.ptt.config.backend == "hid":
                self.ptt.start()
                replay_worker()
            elif self.ptt.config.enabled:
                worker = threading.Thread(target=replay_worker, name="race-engineer-replay", daemon=True)
                worker.start()
                self.ptt.run_forever(stop_event)
                stop_event.set()
                worker.join(timeout=3.0)
                if worker.is_alive():
                    raise RuntimeError("Replay worker did not stop cleanly")
            else:
                replay_worker()
            if replay_error:
                raise replay_error[0]
            return replay_result["count"]
        finally:
            stop_event.set()
            self.ptt.close(wait=True)
            self.stt.close(wait=True)
            self.llm.close(wait=True)
            self.speech.close(wait=True)
            self.wheel_bridge.close(wait=True)
            self._close_capture()
            self._close_recorder()
            self._close_history_autosave()
            with self._state_lock:
                self._finalize_validation_session_locked(self._last_runtime_session_uid)
            try:
                track=getattr(getattr(self.engine.state.session,"track",None),"name",None) or getattr(getattr(self.engine.state.session,"track",None),"label",None)
                weekend=self.validation_bundle.build_weekend_bundle(track=track)
                if weekend is not None: print(f"[VALIDATION] Weekend bundle: {weekend}",flush=True)
            except Exception:
                pass
            self.validation_transcript.close(wait=True)

    def _close_history_autosave(self) -> None:
        stop=getattr(self,"_history_autosave_stop",None)
        q=getattr(self,"_history_autosave_q",None)
        thread=getattr(self,"_history_autosave_thread",None)
        if stop is None or q is None:
            return
        # Give the worker a short chance to persist the latest coalesced lap.
        deadline=time.monotonic()+2.0
        while not q.empty() and time.monotonic()<deadline:
            time.sleep(0.02)
        stop.set()
        try:q.put_nowait(None)
        except queue.Full:pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def _close_recorder(self) -> None:
        if self.recorder:
            try:
                self.recorder.close()
                if self.recorder.last_error:
                    self.recording_error = self.recorder.last_error
            except OSError as error:
                self.recording_error = str(error)

    def _close_capture(self) -> None:
        if self.capture:
            try:
                self.capture.close()
            except OSError as error:
                self.capture_error = str(error)
