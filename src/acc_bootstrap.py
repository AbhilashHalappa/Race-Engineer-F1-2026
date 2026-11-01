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

    original_receiver_init = RaceStateReceiver.__init__

    def receiver_init(self, *args, **kwargs):
        original_receiver_init(self, *args, **kwargs)
        self.acc_runtime = ACCRuntime()
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
                messages = receiver.acc_runtime.update(live, now)
                if messages and receiver.speech.config.enabled:
                    receiver.speech.submit(messages)
                self._acc_last_engineer_at = now
            except Exception as error:
                print(f"[ACC ENGINEER] runtime update skipped: {error}", flush=True)
            return result

        ACCSharedMemoryReader._publish = reader_publish


install()
