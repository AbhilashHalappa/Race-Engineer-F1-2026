"""Run from the project root with: python -m src.main."""
# Release: Stable V2 / V2.0.0 (V2.9.1.3.5.46 release-audit RC1)
# Compatibility marker: V2.9.1.2 S13 Live Telemetry Freshness + Performance Hub Auto Refresh
# Compatibility marker: V0.9.18.0 FINAL DETERMINISTIC CORE
# Compatibility marker: V0.9.17.2.9.10 CURRENT-LAP TRACE ISOLATION
# Compatibility marker: V0.9.17.2.9.9 10MS DI-MASTER INPUT SAMPLING
# Compatibility marker: V0.9.17.2.9.7 DI CONTINUOUS ACROSS REFERENCE/LAP BOUNDARY
# Compatibility marker retained for V0.9.17.2.9.6 release tests: V0.9.17.2.9.6 DISTANCE-ALIGNED INPUT GRAPH AXES
# Compatibility marker retained for V0.9.17.2.6 release tests: V0.9.17.2.6 LAP-BOUNDARY REFERENCE + DRIVER INPUTS VISIBILITY
# Compatibility marker retained for V0.9.17.2.5 release tests: V0.9.17.2.5 REFERENCE AUTHORITY + TRACK SYNC
# Compatibility marker retained for historical release tests: V0.9.17.2.3 REPLAY RECORDING SELECTOR
import sys
import argparse
from pathlib import Path
from .ptt import PTTConfig, list_audio_devices, list_controllers, list_hid_devices
from .session_coach_report import save_coach_report
from .stt import STTConfig
from .llm_engineer import LLMConfig
from .race_state_receiver import RaceStateReceiver as UDPReceiver
from . import reference_model as _reference_model
from .wheel_telemetry import list_serial_ports, run_health_check


def _verify_reference_compiler_runtime() -> tuple[bool, str]:
    """Prove the process imported the compiler from this release folder."""
    expected_dir=Path(__file__).resolve().parent
    actual_path=Path(getattr(_reference_model,"__file__","")).resolve()
    problems=[]
    if actual_path.parent != expected_dir:
        problems.append(f"compiler imported from {actual_path}, expected {expected_dir}")
    if getattr(_reference_model,"QUALITY_VALIDATOR_VERSION",None) != 5:
        problems.append(f"validator={getattr(_reference_model,'QUALITY_VALIDATOR_VERSION',None)} expected=5")
    if getattr(_reference_model,"CLEAN_RIVAL_PACE_COMPILER_VERSION",None) != 2:
        problems.append(f"pace_compiler={getattr(_reference_model,'CLEAN_RIVAL_PACE_COMPILER_VERSION',None)} expected=2")
    if getattr(_reference_model,"REFERENCE_MODEL_SCHEMA_VERSION",None) != 3:
        problems.append(f"reference_schema={getattr(_reference_model,'REFERENCE_MODEL_SCHEMA_VERSION',None)} expected=3")
    if getattr(_reference_model,"REFERENCE_COMPILER_ID",None) != "V1.1.0.13_CLEAN_RIVAL_PACE_V2_ZONE_ASSOCIATION_V2":
        problems.append(f"compiler_id={getattr(_reference_model,'REFERENCE_COMPILER_ID',None)!r}")
    return (not problems, "; ".join(problems) if problems else str(actual_path))


def main(*, host="0.0.0.0", udp_port=20777, show_sizes=False, packet_stats=False, capture_packets=0, engineer_only=False,
         tts_enabled=True, tts_backend="piper", tts_model="voices/en_GB-alan-medium.onnx",
         tts_speed=0.82, tts_volume=100, audio_device=None, ers_assist=True, drs_s_mode_assist=True, position_updates=False,
         ptt_enabled=False, ptt_controller=0, ptt_button=6, mic_device=None, ptt_backend="hid",
         ptt_hid_vendor_id=0x303A, ptt_hid_product_id=0x1001, ptt_hid_usage_page=0x0001, ptt_hid_usage=0x0005,
         stt_enabled=True, stt_model="small.en", llm_enabled=False, llm_model="qwen2.5:3b",
         llm_url="http://127.0.0.1:11434/api/chat", record_telemetry=False, recording_path=None,
         replay_file=None, replay_speed=1.0, replay_fast=False, analysis_output=None,
         overlay=False, overlay_click_through=False, latency_stats=False, wheel_telemetry=True, wheel_port=None, reference_lap=None, export_reference_lap_path=None, reference_lap_number=None,
         web_dash=True, dash_host="0.0.0.0", dash_port=8765,
         ai_reference=False, ai_reference_output=None, ai_reference_min_difficulty=0, rival_reference=False, rival_reference_output=None,
         coach_mode=None, coach_verbosity=None, post_coach=None, pre_coach=None, lap_coach=None, positive_coach=None, race_coach=None) -> int:
    from .app_paths import migrate_legacy_layout, RECORDINGS
    migrate_legacy_layout()
    # S6: background-only server synchronization.  This daemon never sits in
    # the UDP/telemetry decision path; all live writes remain local first.
    try:
        from .server_sync import start_default_sync_worker
        start_default_sync_worker()
        # S8-S14 persistent-data coordinator. This runs only in daemon threads;
        # live UDP/strategy/coaching paths never wait on network I/O.
        from .server_platform import start_default_server_platform
        start_default_server_platform()
    except Exception as _sync_start_error:
        # Server support is optional. Startup must never depend on it.
        print(f"[SERVER SYNC] Local fallback: {_sync_start_error}", flush=True)
    if sys.version_info < (3, 11):
        print("Race Engineer requires Python 3.11 or newer.", file=sys.stderr); return 1
    compiler_ok,compiler_info=_verify_reference_compiler_runtime()
    if not compiler_ok:
        print(f"REFERENCE COMPILER SELF-CHECK FAILED: {compiler_info}",file=sys.stderr)
        print("Start Race Engineer from this Stable V2 folder; do not reuse an already-running older process.",file=sys.stderr)
        return 1
    receiver = UDPReceiver(host, udp_port, show_sizes=show_sizes, packet_stats=packet_stats,
        capture_packets=capture_packets, engineer_only=engineer_only,
        tts_enabled=tts_enabled, tts_backend=tts_backend, tts_model=tts_model,
        tts_speed=tts_speed, tts_volume=tts_volume, audio_device=audio_device, ers_assist=ers_assist,
        drs_s_mode_assist=drs_s_mode_assist, position_updates=position_updates, ptt_config=PTTConfig(enabled=ptt_enabled,
        controller_index=ptt_controller, button_index=ptt_button, mic_device=mic_device, backend=ptt_backend,
        hid_vendor_id=ptt_hid_vendor_id, hid_product_id=ptt_hid_product_id, hid_usage_page=ptt_hid_usage_page, hid_usage=ptt_hid_usage),
        stt_config=STTConfig(enabled=ptt_enabled and stt_enabled, model=stt_model),
        llm_config=LLMConfig(enabled=ptt_enabled and llm_enabled, model=llm_model, url=llm_url),
        record_telemetry=record_telemetry, recording_path=recording_path, latency_stats=latency_stats,
        wheel_telemetry=wheel_telemetry, wheel_port=wheel_port, ai_reference=ai_reference,
        ai_reference_output=ai_reference_output, ai_reference_min_difficulty=ai_reference_min_difficulty,
        rival_reference=rival_reference, rival_reference_output=rival_reference_output)
    # Persistent coaching settings are preserved unless an explicit CLI override
    # is provided. Runtime Control Center changes are saved immediately.
    if coach_mode is not None:
        receiver.set_coaching_mode(coach_mode)
    if coach_verbosity is not None:
        receiver.set_coaching_verbosity(coach_verbosity)
    for _feature, _value in (("POST", post_coach), ("PRE", pre_coach), ("LAP", lap_coach),
                             ("POS", positive_coach), ("RACE", race_coach)):
        if _value is not None:
            receiver.set_coaching_feature(_feature, bool(_value))
    if reference_lap:
        ok, message = receiver.select_reference_lap(reference_lap)
        if not ok:
            print(f"Reference lap error: {message}", file=sys.stderr); return 1
    print("=" * 60); print("RACE ENGINEER\nStable V2 / V2.0.0"); print("=" * 60)
    print("Starting..."); print(f"Reference compiler: {_reference_model.REFERENCE_COMPILER_ID} | validator {_reference_model.QUALITY_VALIDATOR_VERSION} | pace {_reference_model.CLEAN_RIVAL_PACE_COMPILER_VERSION}"); print(f"Compiler source: {compiler_info}"); print(f"\nUDP Address : {receiver.host}"); print(f"UDP Port    : {receiver.port}")
    if tts_enabled:
        print(f"TTS         : {tts_backend.title()} offline voice ({'system default output' if audio_device is None else f'audio device {audio_device}'})")
        if tts_backend == "piper": print(f"Voice model : {tts_model}\nSpeech speed: {tts_speed:.2f} length scale")
    else: print("TTS         : Disabled")
    print(f"ERS Assist  : {'Enabled' if ers_assist else 'Disabled'}")
    print(f"DRS/S Assist: {'Enabled' if drs_s_mode_assist else 'Disabled'}")
    print(f"Position calls: {'Enabled' if position_updates else 'Disabled'}")
    print(f"PTT         : {'Enabled' if ptt_enabled else 'Disabled'}" + (f" (controller {ptt_controller}, button {ptt_button})" if ptt_enabled else ""))
    print(f"STT         : {stt_model + ' offline' if ptt_enabled and stt_enabled else 'Disabled'}")
    print(f"LLM         : {llm_model + ' via local Ollama (reasoning only)' if ptt_enabled and llm_enabled else 'Disabled'}")
    if record_telemetry:
        print(f"Recorder    : Enabled ({recording_path or str(RECORDINGS) + '/ auto file'})")
    else:
        print("Recorder    : Disabled by default (enable REC in Control Center when needed)")
    if replay_file: print(f"Replay      : {replay_file} ({'fast' if replay_fast else str(replay_speed) + 'x'})")
    print(f"Overlay     : {'Enabled' if overlay else 'Disabled'}")
    if overlay:
        print(f"F1 Dash     : Native + {'LAN web enabled on ' + dash_host + ':' + str(dash_port) if web_dash else 'LAN web disabled'}")
    print(f"Latency diag: {'Enabled' if latency_stats else 'Disabled'}")
    print(f"Wheel link   : {'Disabled' if not wheel_telemetry else (wheel_port or 'Auto-detect receiver COM')}")
    if reference_lap: print(f"Reference   : External ({reference_lap})")
    if rival_reference:
        print("TT rival    : Enabled (selected Time Trial rival is preferred reference)")
        if rival_reference_output: print(f"Rival ref save: {rival_reference_output}")
    if ai_reference:
        print(f"AI benchmark: Enabled (minimum difficulty {ai_reference_min_difficulty})")
        if ai_reference_output: print(f"AI ref save : {ai_reference_output}")
    print(flush=True)
    try:
        if overlay:
            from .overlay.runtime import run_overlay
            rc = run_overlay(receiver, replay_file=replay_file, replay_speed=replay_speed,
                             replay_fast=replay_fast, click_through=overlay_click_through,
                             web_dash=web_dash, dash_host=dash_host, dash_port=dash_port)
            if replay_file and analysis_output:
                from .lap_analysis import write_session_analysis
                report = write_session_analysis(receiver.engine.performance, analysis_output)
                print(f"Lap analysis: {report['completed_lap_count']} completed laps; best valid lap {report['best_valid_lap'] or '--'}.", flush=True)
                print(f"Analysis saved: {analysis_output}", flush=True)
            if replay_file and export_reference_lap_path:
                from .reference_lap import export_reference_lap
                payload=export_reference_lap(receiver.engine.performance, export_reference_lap_path, lap_number=reference_lap_number)
                print(f"Reference lap saved: {export_reference_lap_path} ({payload['metadata']['reference_lap_time_s']:.3f}s)", flush=True)
            return rc
        if replay_file:
            count = receiver.run_replay(replay_file, speed=replay_speed, realtime=not replay_fast)
            print(f"\nReplay complete: {count} packets processed.", flush=True)
            # V1.3.0.0 replay acceptance: the packet stream is now complete, so
            # overwrite any earlier finish snapshot with the fully reconciled report.
            if receiver.live_coach.settings.auto_reports:
                try:
                    uid = receiver.engine.state.session.uid
                    stem = f"session_{uid}" if uid is not None else None
                    jp, hp, report = save_coach_report(receiver.engine.performance, stem=stem, record_driver_history=False)
                    receiver.engine.state.extended["coach_report"] = report
                    print(f"[COACH REPORT] Final replay report: {jp} | {hp}", flush=True)
                except OSError as error:
                    print(f"[COACH REPORT] Final replay save failed: {error}", flush=True)
            if analysis_output:
                from .lap_analysis import write_session_analysis
                report = write_session_analysis(receiver.engine.performance, analysis_output)
                print(f"Lap analysis: {report['completed_lap_count']} completed laps; best valid lap {report['best_valid_lap'] or '--'}." , flush=True)
                print(f"Analysis saved: {analysis_output}", flush=True)
            if export_reference_lap_path:
                from .reference_lap import export_reference_lap
                payload=export_reference_lap(receiver.engine.performance, export_reference_lap_path, lap_number=reference_lap_number)
                print(f"Reference lap saved: {export_reference_lap_path} ({payload['metadata']['reference_lap_time_s']:.3f}s)", flush=True)
            return 0
        receiver.run()
    except KeyboardInterrupt:
        print("\nStopped. UDP socket closed. Speech output closed.", flush=True); return 0
    except OSError as error:
        print(f"\nUDP socket error: {error}", file=sys.stderr); return 1
    except RuntimeError as error:
        print(f"\nRuntime error: {error}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Race Engineer Stable V2 / V2.0.0")
    parser.add_argument("--show-sizes", action="store_true")
    parser.add_argument("--packet-stats", action="store_true")
    parser.add_argument("--latency-stats", action="store_true", help="Print rolling packet->decision/radio latency every second")
    parser.add_argument("--engineer-only", action="store_true")
    parser.add_argument("--capture-packets", type=int, default=0, metavar="N")
    parser.add_argument("--record-telemetry", action="store_true", help="Record the full raw UDP session for deterministic replay")
    parser.add_argument("--recording-path", default=None, help="Optional .areplay output path (implies --record-telemetry)")
    parser.add_argument("--replay", default=None, metavar="FILE", help="Replay a V0.9.6 .areplay session instead of opening UDP")
    parser.add_argument("--replay-browser", action="store_true", help="Start replay mode with the newest stored recording, then choose recordings from Control Center")
    parser.add_argument("--replay-speed", type=float, default=1.0, metavar="N", help="Replay timing multiplier, e.g. 2 = twice as fast")
    parser.add_argument("--replay-fast", action="store_true", help="Replay without sleeping; deterministic rapid analysis/test mode")
    parser.add_argument("--analysis-output", default=None, metavar="FILE", help="Write measured lap/corner analysis JSON after replay")
    parser.add_argument("--reference-lap", default=None, metavar="FILE", help="Use an exported Race Engineer reference lap for live coaching")
    parser.add_argument("--export-reference-lap", default=None, metavar="FILE", help="After replay, export the best valid measured lap as a reusable reference")
    parser.add_argument("--reference-lap-number", type=int, default=None, metavar="N", help="With --export-reference-lap, export this completed lap instead of the best valid lap")
    parser.add_argument("--ai-reference", action="store_true", help="Capture AI-controlled cars and use the fastest valid AI lap as the live coaching reference")
    parser.add_argument("--ai-reference-output", default=None, metavar="FILE", help="Save each new fastest valid AI benchmark lap as a reusable reference JSON (implies --ai-reference)")
    parser.add_argument("--ai-reference-min-difficulty", type=int, default=0, metavar="N", help="Only capture AI benchmarks when session AI difficulty is at least N (0..110)")
    parser.add_argument("--rival-reference", action="store_true", help="Capture the selected Time Trial rival and use it as the preferred live coaching reference")
    parser.add_argument("--rival-reference-output", default=None, metavar="FILE", help="Save the selected Time Trial rival reference JSON (implies --rival-reference)")
    parser.add_argument("--overlay", action="store_true", help="Show the live always-on-top Race Engineer overlay")
    parser.add_argument("--overlay-click-through", action="store_true", help="Start overlay in click-through mode (F8 toggles when focused)")
    parser.add_argument("--no-web-dash", action="store_true", help="Disable the LAN/browser F1 dashboard server")
    parser.add_argument("--dash-host", default="0.0.0.0", help="F1 web dash bind address (default: 0.0.0.0 for LAN access)")
    parser.add_argument("--dash-port", type=int, default=8765, metavar="N", help="F1 web dash TCP port (default: 8765)")
    parser.add_argument("--no-tts", action="store_true")
    parser.add_argument("--no-ers-assist", action="store_true", help="Disable Overtake/Boost reminder assist")
    parser.add_argument("--no-drs-s-mode-assist", action="store_true", help="Disable DRS / 2026 S Mode reminder assist")
    parser.add_argument("--position-updates", action="store_true", help="Enable automatic position-change radio calls (disabled by default)")
    parser.add_argument("--coach-mode", choices=("auto", "race_engineer", "performance_coach", "track_learning", "qualifying", "time_trial", "silent_analysis"), default=None, help="Override persistent coaching mode")
    parser.add_argument("--coach-verbosity", choices=("minimal", "normal", "detailed"), default=None, help="Override persistent coaching verbosity")
    parser.add_argument("--show-coaching-settings", action="store_true", help="Print persisted local coaching settings and exit")
    parser.add_argument("--reset-coaching-settings", action="store_true", help="Reset persisted local coaching settings to defaults and exit")
    parser.add_argument("--diagnostic-bundle", nargs="?", const="analysis/diagnostics/diagnostic_bundle.zip", default=None, metavar="FILE", help="Create a local diagnostic ZIP and exit")
    parser.add_argument("--post-coach", action=argparse.BooleanOptionalAction, default=None, help="Enable/disable post-corner coaching and persist the choice")
    parser.add_argument("--pre-coach", action=argparse.BooleanOptionalAction, default=None, help="Enable/disable pre-corner reminders and persist the choice")
    parser.add_argument("--lap-coach", action=argparse.BooleanOptionalAction, default=None, help="Enable/disable lap-end coaching and persist the choice")
    parser.add_argument("--positive-coach", action=argparse.BooleanOptionalAction, default=None, help="Enable/disable improvement calls and persist the choice")
    parser.add_argument("--race-coach", action=argparse.BooleanOptionalAction, default=None, help="Enable/disable conservative coaching during races and persist the choice")
    parser.add_argument("--ptt", action="store_true", help="Enable wheel push-to-talk WAV capture")
    parser.add_argument("--ptt-controller", type=int, default=0, metavar="N")
    parser.add_argument("--ptt-button", type=int, default=6, metavar="N", help="PTT button number (default: 6)")
    parser.add_argument("--ptt-backend", choices=("hid", "pygame"), default="hid", help="PTT input backend (default: hid)")
    parser.add_argument("--mic-device", type=int, default=None, metavar="N")
    parser.add_argument("--audio-device", type=int, default=None, metavar="N", help="TTS output device index; default uses Windows system output")
    parser.add_argument("--no-stt", action="store_true", help="Disable automatic offline transcription after PTT release")
    parser.add_argument("--stt-model", default="small.en", help="faster-whisper model (default: small.en)")
    parser.add_argument("--llm", action="store_true", help="Enable optional local LLM explanation/fallback reasoning (disabled by default)")
    parser.add_argument("--no-llm", action="store_true", help="Compatibility switch; local LLM is already disabled by default")
    parser.add_argument("--llm-model", default="qwen2.5:3b", help="Local Ollama model used only for complex reasoning")
    parser.add_argument("--llm-url", default="http://127.0.0.1:11434/api/chat", help="Local Ollama chat endpoint")
    parser.add_argument("--wheel-port", default=None, metavar="COMx", help="GamePad Pro Receiver CDC port; default auto-detects a unique ESP32/TinyUSB serial port")
    parser.add_argument("--no-wheel-telemetry", action="store_true", help="Disable the Race Engineer -> wheel telemetry bridge")
    parser.add_argument("--list-wheel-ports", action="store_true", help="List serial/COM ports for the GamePad Pro Receiver")
    parser.add_argument("--wheel-health-check", action="store_true", help="Bench-test Receiver USB, wheel, pedals and MotorTemp links, then exit")
    parser.add_argument("--list-audio-devices", action="store_true")
    parser.add_argument("--list-controllers", action="store_true")
    parser.add_argument("--list-hid-devices", action="store_true", help="List raw HID descriptors for PTT device selection")
    parser.add_argument("--tts-backend", choices=("piper", "windows"), default="piper")
    parser.add_argument("--tts-model", default="voices/en_GB-alan-medium.onnx")
    parser.add_argument("--tts-speed", type=float, default=0.82, metavar="N", help="Piper length scale 0.5..2.0; lower is faster (default: 0.82)")
    parser.add_argument("--tts-volume", type=int, default=100, metavar="N")
    args = parser.parse_args()
    if args.replay_browser:
        if args.replay:
            parser.error("--replay-browser cannot be combined with --replay")
        stored = sorted(RECORDINGS.glob("*.areplay"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not stored:
            parser.error("--replay-browser found no .areplay files in .\recordings")
        args.replay = str(stored[0])
    if args.show_coaching_settings or args.reset_coaching_settings:
        import json as _json
        from .coaching_settings import CoachingSettingsStore
        _store = CoachingSettingsStore()
        if args.reset_coaching_settings:
            _store.reset()
            print("Coaching settings reset to defaults.")
        print(_json.dumps(_store.settings.to_dict(), indent=2, sort_keys=True))
        raise SystemExit(0)
    if args.diagnostic_bundle:
        from .diagnostics import export_bundle
        _bundle = export_bundle(args.diagnostic_bundle)
        print(f"Diagnostic bundle saved: {_bundle}")
        raise SystemExit(0)
    if args.list_wheel_ports:
        list_serial_ports(); raise SystemExit(0)
    if args.wheel_health_check:
        raise SystemExit(run_health_check(args.wheel_port))
    if args.list_audio_devices:
        list_audio_devices(); raise SystemExit(0)
    if args.list_controllers:
        list_controllers(); raise SystemExit(0)
    if args.list_hid_devices:
        list_hid_devices(); raise SystemExit(0)
    if not 0 <= args.capture_packets <= 2000: parser.error("--capture-packets must be 1..2000 (0 disables capture)")
    if args.replay_speed <= 0: parser.error("--replay-speed must be greater than zero")
    if not 0 <= args.ai_reference_min_difficulty <= 110: parser.error("--ai-reference-min-difficulty must be 0..110")
    if args.replay and (args.record_telemetry or args.recording_path): parser.error("--replay cannot be combined with telemetry recording")
    if args.overlay_click_through and not args.overlay: parser.error("--overlay-click-through requires --overlay")
    if not 1 <= args.dash_port <= 65535: parser.error("--dash-port must be 1..65535")
    if args.overlay and args.ptt and args.ptt_backend != "hid":
        parser.error("--overlay + --ptt is supported with the raw HID backend only; pygame joystick polling requires the main UI thread")
    if not 0.5 <= args.tts_speed <= 2.0: parser.error("--tts-speed must be 0.5..2.0")
    if not 0 <= args.tts_volume <= 100: parser.error("--tts-volume must be 0..100")
    raise SystemExit(main(show_sizes=args.show_sizes, packet_stats=args.packet_stats,
        capture_packets=args.capture_packets, engineer_only=args.engineer_only,
        tts_enabled=not args.no_tts, tts_backend=args.tts_backend,
        tts_model=args.tts_model, tts_speed=args.tts_speed, tts_volume=args.tts_volume, audio_device=args.audio_device,
        ers_assist=not args.no_ers_assist, drs_s_mode_assist=not args.no_drs_s_mode_assist, position_updates=args.position_updates,
        ptt_enabled=args.ptt, ptt_controller=args.ptt_controller, ptt_button=args.ptt_button, mic_device=args.mic_device, ptt_backend=args.ptt_backend,
        stt_enabled=not args.no_stt, stt_model=args.stt_model,
        llm_enabled=bool(args.llm and not args.no_llm), llm_model=args.llm_model, llm_url=args.llm_url,
        record_telemetry=args.record_telemetry or bool(args.recording_path),
        recording_path=Path(args.recording_path) if args.recording_path else None,
        replay_file=Path(args.replay) if args.replay else None, replay_speed=args.replay_speed, replay_fast=args.replay_fast,
        analysis_output=Path(args.analysis_output) if args.analysis_output else None,
        overlay=args.overlay, overlay_click_through=args.overlay_click_through, latency_stats=args.latency_stats,
        web_dash=not args.no_web_dash, dash_host=args.dash_host, dash_port=args.dash_port,
        wheel_telemetry=not args.no_wheel_telemetry, wheel_port=args.wheel_port,
        reference_lap=Path(args.reference_lap) if args.reference_lap else None,
        export_reference_lap_path=Path(args.export_reference_lap) if args.export_reference_lap else None,
        reference_lap_number=args.reference_lap_number,
        ai_reference=args.ai_reference or bool(args.ai_reference_output),
        ai_reference_output=Path(args.ai_reference_output) if args.ai_reference_output else None,
        ai_reference_min_difficulty=args.ai_reference_min_difficulty,
        rival_reference=args.rival_reference or bool(args.rival_reference_output),
        rival_reference_output=Path(args.rival_reference_output) if args.rival_reference_output else None,
        coach_mode=args.coach_mode, coach_verbosity=args.coach_verbosity,
        post_coach=args.post_coach, pre_coach=args.pre_coach, lap_coach=args.lap_coach,
        positive_coach=args.positive_coach, race_coach=args.race_coach))
