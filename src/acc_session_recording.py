"""Decoded ACC Shared Memory session recording and deterministic replay."""
from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import uuid


class ACCSessionRecorder:
    """Asynchronous JSONL recorder for decoded ACC telemetry snapshots."""
    _STOP = object()

    def __init__(self, directory: Path | None = None, *, path: Path | None = None):
        from .app_paths import RECORDINGS
        from queue import SimpleQueue
        self.directory = Path(directory) if directory is not None else RECORDINGS
        self.path = Path(path) if path else None
        self._queue = SimpleQueue()
        self._lock = threading.Lock()
        self._pending = 0
        self._accepted = 0
        self._closed = False
        self.last_error: str | None = None
        self._started = None
        self._stream = None
        self._thread = threading.Thread(target=self._worker, name="acc-session-recorder", daemon=True)
        self._thread.start()

    @property
    def count(self):
        return self._accepted

    @property
    def pending(self):
        with self._lock:
            return self._pending

    def record(self, telemetry, now: float | None = None):
        if self._closed or self.last_error:
            return
        stamp = float(now if now is not None else time.monotonic())
        payload = asdict(telemetry)
        with self._lock:
            self._accepted += 1
            self._pending += 1
        self._queue.put((payload, stamp))

    def _worker(self):
        try:
            while True:
                item = self._queue.get()
                if item is self._STOP:
                    break
                payload, stamp = item
                try:
                    if self._stream is None:
                        self.directory.mkdir(parents=True, exist_ok=True)
                        if self.path is None:
                            name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                            self.path = self.directory / f"acc-session-{name}-{uuid.uuid4().hex[:8]}.accjsonl"
                        self.path.parent.mkdir(parents=True, exist_ok=True)
                        self._stream = self.path.open("x", encoding="utf-8", buffering=1)
                        self._started = stamp
                        self._stream.write(json.dumps({"format":"ACCJSONL01","version":1,"created_utc":datetime.now(timezone.utc).isoformat()}) + "\n")
                    self._stream.write(json.dumps({"offset_s":max(0.0,stamp-self._started),"telemetry":payload}, separators=(",",":"), allow_nan=False) + "\n")
                except Exception as error:
                    self.last_error = str(error)
                finally:
                    with self._lock:
                        self._pending = max(0, self._pending - 1)
        finally:
            if self._stream is not None:
                self._stream.flush()
                self._stream.close()
                self._stream = None

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._queue.put(self._STOP)
        self._thread.join(timeout=10.0)
        if self._thread.is_alive():
            self.last_error = self.last_error or "ACC recorder worker did not stop cleanly"


def replay_acc_into(receiver, path: Path | str, *, speed: float = 1.0, realtime: bool = False) -> int:
    """Replay decoded ACC snapshots through RaceStateReceiver.process_acc_telemetry."""
    if speed <= 0:
        raise ValueError("Replay speed must be greater than zero")
    source = Path(path)
    count = 0
    started = time.monotonic()
    previous = -1.0
    with source.open("r", encoding="utf-8") as stream:
        header = json.loads(next(stream))
        if header.get("format") != "ACCJSONL01":
            raise ValueError("Not an ACC JSONL session recording")
        from .hardware_companion.models import LiveTelemetry
        tuple_fields = {f.name for f in fields(LiveTelemetry) if "tuple" in str(f.type)}
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            offset = float(row["offset_s"])
            if offset < previous:
                raise ValueError("ACC recording timestamps are not monotonic")
            previous = offset
            if realtime and count:
                delay = max(0.0, (offset - (time.monotonic() - started) * speed) / speed)
                if delay:
                    time.sleep(delay)
            values = row["telemetry"]
            for name in tuple_fields:
                if isinstance(values.get(name), list):
                    values[name] = tuple(values[name])
            values["last_packet_monotonic"] = time.monotonic()
            receiver.process_acc_telemetry(LiveTelemetry(**values))
            count += 1
    return count
