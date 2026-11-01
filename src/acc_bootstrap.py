"""Compatibility bootstrap that connects ACC Shared Memory to Race Engineer radio.

Loaded from the package initializer so the protected F1 receiver/runtime files do
not need to be rewritten just to add the independent ACC source.
"""
from __future__ import annotations

import threading
import time


_receivers_by_bridge: dict[int, object] = {}
_lock = threading.RLock()
_installed = False


def _receiver_for_callback(callback):
    owner = getattr(callback, "__self__", None)
    if owner is None:
        return None
    with _lock:
        return _receivers_by_bridge.get(id(owner))


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    from .race_state_receiver import RaceStateReceiver
    from .acc_telemetry import ACCSharedMemoryReader
    from .acc_runtime import ACCRuntime
    from .telemetry_pipeline import telemetry_pipeline, frame_from_acc
    from .overlay.data import OverlayDataProvider, build_overlay_snapshot, build_input_snapshot

    original_receiver_init = RaceStateReceiver.__init__

    def receiver_init(self, *args, **kwargs):
        original_receiver_init(self, *args, **kwargs)
        self.acc_runtime = ACCRuntime()
        self.acc_common_state = None
        with _lock:
            _receivers_by_bridge[id(self.wheel_bridge)] = self

    if not getattr(RaceStateReceiver, "_acc_bootstrap_installed", False):
        RaceStateReceiver.__init__ = receiver_init
        RaceStateReceiver._acc_bootstrap_installed = True

    original_reader_init = ACCSharedMemoryReader.__init__

    def reader_init(self, *args, **kwargs):
        callback = kwargs.get("on_snapshot")
        original_reader_init(self, *args, **kwargs)
        self._acc_receiver = _receiver_for_callback(callback)
        self._acc_last_engineer_at = 0.0
        self._acc_runtime_started = False

    # Existing overlays consume the common RaceState contract. Select the
    # ACC adapter state only while ACC is active; F1 keeps its native state and
    # its own measured-performance history untouched.
    if not getattr(OverlayDataProvider, "_acc_bootstrap_installed", False):
        original_input_snapshot = OverlayDataProvider.input_snapshot
        original_overlay_snapshot = OverlayDataProvider.snapshot

        def input_snapshot(provider):
            receiver = provider.receiver
            if getattr(receiver, "_telemetry_mode", "live") != "acc":
                return original_input_snapshot(provider)
            now = time.monotonic()
            lock = getattr(receiver, "_state_lock", None)
            if lock is not None:
                with lock:
                    state = getattr(receiver, "acc_common_state", None)
            else:
                state = getattr(receiver, "acc_common_state", None)
            if state is None:
                return original_input_snapshot(provider)
            runtime = getattr(receiver, "acc_runtime", None)
            stamp = getattr(getattr(runtime, "status", None), "last_packet_monotonic", None)
            connected = stamp is not None and now - stamp < 3.0
            return build_input_snapshot(state, None, connected=connected)

        def overlay_snapshot(provider):
            receiver = provider.receiver
            if getattr(receiver, "_telemetry_mode", "live") != "acc":
                return original_overlay_snapshot(provider)
            now = time.monotonic()
            lock = getattr(receiver, "_state_lock", None)
            if lock is not None:
                with lock:
                    state = getattr(receiver, "acc_common_state", None)
            else:
                state = getattr(receiver, "acc_common_state", None)
            if state is None:
                return original_overlay_snapshot(provider)
            runtime = getattr(receiver, "acc_runtime", None)
            stamp = getattr(getattr(runtime, "status", None), "last_packet_monotonic", None)
            connected = stamp is not None and now - stamp < 3.0
            return provider._runtime_status(
                build_overlay_snapshot(state, None, connected=connected, now=now)
            )

        OverlayDataProvider.input_snapshot = input_snapshot
        OverlayDataProvider.snapshot = overlay_snapshot
        OverlayDataProvider._acc_bootstrap_installed = True

    # Radio request handling already accepts RaceState. Temporarily supply the
    # ACC-adapted state to that existing handler only for ACC PTT callbacks.
    if not getattr(RaceStateReceiver, "_acc_voice_bootstrap_installed", False):
        original_on_transcript = RaceStateReceiver._on_transcript

        def on_transcript(self, *args, **kwargs):
            if getattr(self, "_telemetry_mode", "live") != "acc" or getattr(self, "acc_common_state", None) is None:
                return original_on_transcript(self, *args, **kwargs)
            lock = getattr(self, "_state_lock", None)
            if lock is None:
                previous = self.engine.state
                self.engine.state = self.acc_common_state
            else:
                with lock:
                    previous = self.engine.state
                    self.engine.state = self.acc_common_state
            try:
                return original_on_transcript(self, *args, **kwargs)
            finally:
                if lock is None:
                    if self.engine.state is self.acc_common_state:
                        self.engine.state = previous
                else:
                    with lock:
                        if self.engine.state is self.acc_common_state:
                            self.engine.state = previous

        RaceStateReceiver._on_transcript = on_transcript
        RaceStateReceiver._acc_voice_bootstrap_installed = True

    if not getattr(ACCSharedMemoryReader, "_acc_bootstrap_installed", False):
        ACCSharedMemoryReader.__init__ = reader_init
        ACCSharedMemoryReader._acc_bootstrap_installed = True

        original_start = ACCSharedMemoryReader.start

        def reader_start(self, *args, **kwargs):
            receiver = getattr(self, "_acc_receiver", None)
            if receiver is not None:
                receiver.acc_runtime.start()
                self._acc_runtime_started = True
            return original_start(self, *args, **kwargs)

        ACCSharedMemoryReader.start = reader_start

        original_close = ACCSharedMemoryReader.close

        def reader_close(self, *args, **kwargs):
            receiver = getattr(self, "_acc_receiver", None)
            try:
                return original_close(self, *args, **kwargs)
            finally:
                if receiver is not None and getattr(self, "_acc_runtime_started", False):
                    receiver.acc_runtime.stop()
                    self._acc_runtime_started = False

        ACCSharedMemoryReader.close = reader_close

        original_publish = ACCSharedMemoryReader._publish

        def reader_publish(self, *args, **kwargs):
            result = original_publish(self, *args, **kwargs)
            receiver = getattr(self, "_acc_receiver", None)
            if receiver is None:
                return result
            now = time.monotonic()
            if now - getattr(self, "_acc_last_engineer_at", 0.0) < 0.05:
                return result
            live, _wheel = self.snapshots()
            try:
                # ACC and F1 now publish the same immutable frame contract.
                telemetry_pipeline.publish(frame_from_acc(live, now=now))
                messages = receiver.acc_runtime.update(live, now)
                receiver.acc_common_state = receiver.acc_runtime.latest_state
                if messages and receiver.speech.config.enabled:
                    receiver.speech.submit(messages)
                self._acc_last_engineer_at = now
            except Exception as error:
                print(f"[ACC ENGINEER] runtime update skipped: {error}", flush=True)
            return result

        ACCSharedMemoryReader._publish = reader_publish


install()
