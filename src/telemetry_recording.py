"""V0.9.6 lossless telemetry session recording and deterministic replay.

The recorder stores the raw UDP datagrams plus their relative arrival times. Replay
feeds those exact bytes back through RaceStateReceiver.process_packet(), so packet
decoding, race-state updates, safety, strategy and measured-performance logic use
the normal production path without F1 running.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import time
import uuid
import threading
import mmap
from array import array

from .telemetry.header import decode_header, HEADER_STRUCT, HEADER_SIZE

MAGIC = b"ARERPL01"

# Interactive replay checkpoints bound deterministic fast-forward work after a seek.
# V1.8.0.0.3 deliberately spaces periodic snapshots farther apart during normal
# realtime playback.  Serialising the complete deterministic engine every ~4k
# packets was measurable work on dense 2026 recordings (often >1000 packets/s) and
# could make 1x playback hitch.  Lap changes still create checkpoints immediately.
_CHECKPOINT_PACKET_INTERVAL = 131072
_MAX_REPLAY_CHECKPOINTS = 6
_MAX_REPLAY_CHECKPOINT_BYTES = 48 * 1024 * 1024
_MAX_REALTIME_CATCHUP_S = 0.075
_U32 = struct.Struct("<I")
_F64 = struct.Struct("<d")
_RECORD_HEADER = struct.Struct("<dI")




def _replay_clock_metadata(data: bytes):
    """Extract only the fields needed by the replay clock.

    Session/menu transition packets can legally carry a player index of 255 while
    the game is between sessions.  The production ``decode_header`` validator
    intentionally rejects those datagrams for normal telemetry processing, but the
    replay transport must still see their session UID/time so it can stitch a full
    Practice -> Qualifying -> Race recording without waiting through menu/loading
    gaps.  Keep this parser deliberately narrow and do not use it for race state.
    """
    if len(data) < HEADER_SIZE:
        return None, None
    try:
        fields = HEADER_STRUCT.unpack_from(data)
        packet_format = int(fields[0])
        game_year = int(fields[1])
        packet_version = int(fields[4])
        session_uid = int(fields[6])
        session_time = float(fields[7])
    except Exception:
        return None, None
    if packet_format != 2026 or game_year not in (25, 26) or packet_version == 0:
        return None, None
    if session_time != session_time or session_time in (float("inf"), float("-inf")):
        return None, None
    return session_time, (session_uid if session_uid else None)


@dataclass(frozen=True)
class ReplayRecord:
    offset_s: float
    data: bytes

class _IndexedReplayRecords:
    """Memory-efficient random-access view of an ARERPL01 file.

    Interactive replay used to materialise every UDP payload as an individual
    Python ``bytes`` object. A 500+ MB weekend recording therefore occupied far
    more than its file size in the Python heap before playback even started, and
    seek checkpoints added further pressure as the run progressed.

    This index keeps only compact numeric arrays in Python memory and memory-maps
    the file. Packet payloads are copied only when the replay worker asks for the
    current record. The public ``ReplayRecord`` shape is preserved for callers.
    """
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._stream = self.path.open("rb")
        if self._stream.read(len(MAGIC)) != MAGIC:
            self._stream.close()
            raise ValueError("Not a Race Engineer ARERPL01 replay file")
        self._offsets = array("d")
        self._data_offsets = array("Q")
        self._sizes = array("I")
        self._session_times = array("d")
        self._session_uids = array("Q")
        previous = -1.0
        while True:
            raw = self._stream.read(_RECORD_HEADER.size)
            if not raw:
                break
            if len(raw) != _RECORD_HEADER.size:
                self.close()
                raise ValueError("Truncated replay record header")
            offset, size = _RECORD_HEADER.unpack(raw)
            if offset < previous:
                self.close()
                raise ValueError("Replay timestamps are not monotonic")
            previous = offset
            data_offset = self._stream.tell()
            # Read only the F1 packet header when possible. The full UDP payload
            # remains on disk until that packet is actually replayed.
            header_size = min(int(size), 64)
            prefix = self._stream.read(header_size)
            if len(prefix) != header_size:
                self.close()
                raise ValueError("Truncated replay packet")
            session_time, session_uid = _replay_clock_metadata(prefix)
            if session_time is None:
                session_time = float("nan")
            if session_uid is None:
                session_uid = 0
            remaining = int(size) - header_size
            if remaining:
                self._stream.seek(remaining, 1)
            self._offsets.append(float(offset))
            self._data_offsets.append(int(data_offset))
            self._sizes.append(int(size))
            self._session_times.append(session_time)
            self._session_uids.append(session_uid)
        self._map = mmap.mmap(self._stream.fileno(), 0, access=mmap.ACCESS_READ)

    def __len__(self) -> int:
        return len(self._offsets)

    def __getitem__(self, index):
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return [self[i] for i in range(start, stop, step)]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        start = int(self._data_offsets[index])
        size = int(self._sizes[index])
        return ReplayRecord(float(self._offsets[index]), bytes(self._map[start:start + size]))

    def game_metadata(self, index: int):
        st = float(self._session_times[index])
        uid = int(self._session_uids[index])
        if st != st:  # NaN
            st = None
        return st, (uid if uid else None)

    def offset_at(self, index: int) -> float:
        return float(self._offsets[index])

    def close(self) -> None:
        mm = getattr(self, "_map", None)
        self._map = None
        if mm is not None:
            try:
                mm.close()
            except Exception:
                pass
        stream = getattr(self, "_stream", None)
        self._stream = None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass

    def __del__(self):
        self.close()



class TelemetrySessionRecorder:
    """Append-only raw UDP recorder with monotonic relative timestamps."""
    def __init__(self, directory: Path | None = None, *, path: Path | None = None) -> None:
        from .app_paths import RECORDINGS
        self.directory = Path(directory) if directory is not None else RECORDINGS
        self.path = Path(path) if path else None
        self.metadata_path: Path | None = None
        self.count = 0
        self.bytes = 0
        self.started_monotonic: float | None = None
        self.started_utc: str | None = None
        self._file = None

    def _open(self, now: float) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.path is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            self.path = self.directory / f"telemetry-{stamp}-{uuid.uuid4().hex[:8]}.areplay"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("xb")
        self._file.write(MAGIC)
        self.started_monotonic = now
        self.started_utc = datetime.now(timezone.utc).isoformat()
        self.metadata_path = self.path.with_suffix(self.path.suffix + ".json")

    def record(self, data: bytes, now: float | None = None) -> None:
        now = time.monotonic() if now is None else float(now)
        if self._file is None:
            self._open(now)
        offset = max(0.0, now - self.started_monotonic)
        # One buffered write per datagram keeps recording off the critical path
        # as much as possible while preserving the exact lossless file format.
        self._file.write(_RECORD_HEADER.pack(offset, len(data)) + data)
        self.count += 1
        self.bytes += len(data)

    def close(self) -> None:
        if self._file is None:
            return
        stream, self._file = self._file, None
        stream.flush(); stream.close()
        if self.metadata_path:
            meta = {
                "format": "ARERPL01",
                "version": "0.9.6",
                "created_utc": self.started_utc,
                "packet_count": self.count,
                "udp_payload_bytes": self.bytes,
                "recording_file": self.path.name if self.path else None,
            }
            self.metadata_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def read_replay(path: Path | str) -> list[ReplayRecord]:
    path = Path(path)
    records: list[ReplayRecord] = []
    with path.open("rb") as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise ValueError("Not a Race Engineer ARERPL01 replay file")
        previous = -1.0
        while True:
            raw_offset = stream.read(_F64.size)
            if not raw_offset:
                break
            if len(raw_offset) != _F64.size:
                raise ValueError("Truncated replay timestamp")
            raw_size = stream.read(_U32.size)
            if len(raw_size) != _U32.size:
                raise ValueError("Truncated replay packet length")
            offset = _F64.unpack(raw_offset)[0]
            size = _U32.unpack(raw_size)[0]
            data = stream.read(size)
            if len(data) != size:
                raise ValueError("Truncated replay packet")
            if offset < previous:
                raise ValueError("Replay timestamps are not monotonic")
            previous = offset
            records.append(ReplayRecord(offset, data))
    return records


@dataclass(frozen=True)
class ReplayControlStatus:
    position: int
    total: int
    range_start: int
    range_end: int
    speed: float
    paused: bool
    use_record_timestamps: bool
    rebuilding: bool = False
    requested_position: int | None = None
    clock_drift_s: float = 0.0


class ReplayController:
    """Thread-safe interactive controller for deterministic .areplay playback.

    Position and range are packet indices. Seeking reconstructs receiver state by
    replaying packets from the beginning up to the target without wall-clock
    sleeping, then normal timed playback resumes from that point.
    """
    def __init__(self, path: Path | str | None = None, *, speed: float = 1.0, realtime: bool = True) -> None:
        if speed <= 0:
            raise ValueError("Replay speed must be greater than zero")
        self.path = Path(path) if path is not None else None
        self.records = _IndexedReplayRecords(self.path) if self.path is not None else []
        self.realtime = bool(realtime)
        self._lock = threading.RLock()
        self._changed = threading.Condition(self._lock)
        self._position = 0
        self._range_start = 0
        self._range_end = max(0, len(self.records) - 1)
        self._speed = float(speed)
        self._paused = False
        self._use_record_timestamps = True
        self._seek_to: int | None = None
        self._requested_position: int | None = None
        self._rebuilding = False
        self._checkpoints: dict[int, object] = {}
        self._checkpoint_bytes = 0
        self._checkpoint_lap: int | None = None
        self._checkpoint_session_uid: int | None = None
        self._checkpoint_position = 0
        # Incremented whenever an interactive control changes replay timing.
        # The realtime scheduler uses this to re-anchor without accumulating
        # packet-processing time into the playback clock.
        self._timing_revision = 0
        self._clock_drift_s = 0.0
        self._game_timeline = self._build_game_timeline(self.records)


    def load_file(self, path: Path | str, *, autoplay: bool = True) -> int:
        """Replace the active replay recording without restarting the application.

        The file is parsed before taking the controller lock so the Qt thread is not
        blocked while playback state is held.  The replay thread notices the timing
        revision, re-anchors immediately, resets receiver state at packet zero and
        then continues with the newly selected recording.
        """
        new_path = Path(path)
        new_records = _IndexedReplayRecords(new_path)
        if not new_records:
            raise ValueError(f"Replay contains no packets: {new_path}")
        with self._changed:
            old_records = self.records
            self.path = new_path
            self.records = new_records
            self._position = 0
            self._range_start = 0
            self._range_end = len(new_records) - 1
            self._requested_position = 0
            self._seek_to = 0
            self._paused = not bool(autoplay)
            self._checkpoints.clear()
            self._checkpoint_bytes = 0
            self._checkpoint_lap = None
            self._checkpoint_session_uid = None
            self._checkpoint_position = 0
            self._clock_drift_s = 0.0
            self._game_timeline = self._build_game_timeline(new_records)
            self._timing_revision += 1
            self._changed.notify_all()
        if hasattr(old_records, "close"):
            old_records.close()
        return len(new_records)

    def current_file(self) -> str | None:
        with self._lock:
            return str(self.path) if self.path is not None else None

    def status(self) -> ReplayControlStatus:
        with self._lock:
            last = max(0, len(self.records) - 1)
            display_position = self._requested_position if self._requested_position is not None else self._position
            return ReplayControlStatus(
                position=min(display_position, last),
                total=len(self.records),
                range_start=self._range_start,
                range_end=self._range_end,
                speed=self._speed,
                paused=self._paused,
                use_record_timestamps=self._use_record_timestamps,
                rebuilding=self._rebuilding or self._requested_position is not None,
                requested_position=self._requested_position,
                clock_drift_s=self._clock_drift_s,
            )

    def set_paused(self, paused: bool) -> None:
        with self._changed:
            paused = bool(paused)
            if not paused and self._position > self._range_end:
                self._requested_position = self._range_start
                self._seek_to = self._range_start
            if self._paused != paused:
                self._paused = paused
                self._timing_revision += 1
            self._changed.notify_all()

    def toggle_paused(self) -> bool:
        with self._changed:
            self._paused = not self._paused
            self._timing_revision += 1
            self._changed.notify_all()
            return self._paused

    def set_speed(self, speed: float) -> None:
        if speed <= 0:
            return
        with self._changed:
            new_speed = max(0.10, min(8.0, float(speed)))
            if new_speed != self._speed:
                self._speed = new_speed
                self._timing_revision += 1
            self._changed.notify_all()

    def set_use_record_timestamps(self, enabled: bool) -> None:
        with self._changed:
            enabled = bool(enabled)
            if enabled != self._use_record_timestamps:
                self._use_record_timestamps = enabled
                self._timing_revision += 1
            self._changed.notify_all()

    def seek(self, position: int) -> None:
        if not self.records:
            return
        with self._changed:
            pos = max(self._range_start, min(self._range_end, int(position)))
            self._requested_position = pos
            self._seek_to = pos
            self._timing_revision += 1
            self._changed.notify_all()

    def set_range(self, start: int, end: int) -> None:
        if not self.records:
            return
        last = len(self.records) - 1
        start = max(0, min(last, int(start)))
        end = max(start, min(last, int(end)))
        with self._changed:
            if (start, end) != (self._range_start, self._range_end):
                self._range_start, self._range_end = start, end
                self._timing_revision += 1
            if self._position < start or self._position > end:
                self._requested_position = start
                self._seek_to = start
                self._timing_revision += 1
            self._changed.notify_all()

    def _wait_interruptible(self, seconds: float, stop_event=None) -> bool:
        return self._wait_until_interruptible(
            time.monotonic() + max(0.0, seconds), self._timing_revision, stop_event
        )

    def _wait_until_interruptible(self, deadline: float, timing_revision: int, stop_event=None) -> bool:
        """Wait to an absolute wall-clock deadline without accumulating drift.

        A seek/pause/speed/timestamp-mode change invalidates the current deadline
        immediately so the caller can re-anchor the replay clock.  Using an
        absolute deadline is the key difference from the old per-packet sleep:
        decoder/engine/overlay work is absorbed by the next wait instead of being
        added to every recorded packet interval.
        """
        while True:
            if stop_event is not None and stop_event.is_set():
                return False
            with self._changed:
                if self._seek_to is not None or self._timing_revision != timing_revision:
                    return False
                if self._paused:
                    return False
                remain = deadline - time.monotonic()
                if remain <= 0:
                    return True
                # Short condition waits keep controls responsive while still
                # landing close to the target timestamp on Windows.
                self._changed.wait(timeout=min(0.005, remain))

    def _current_lap(self, receiver):
        try:
            player = receiver.engine.state.player
            return player.lap.current_lap if player is not None else None
        except Exception:
            return None

    def _cache_checkpoint_if_new_lap(self, receiver, position: int) -> None:
        """Cache deterministic replay state at lap changes and bounded intervals.

        The historical method name is kept to avoid churn in callers.  V0.9.13.0
        additionally checkpoints every few thousand packets so a seek never needs
        to rebuild an entire long lap from its start.
        """
        if not hasattr(receiver, "export_replay_checkpoint"):
            return
        position = int(position)
        lap = self._current_lap(receiver)
        try:
            session_uid = getattr(receiver.engine.state.session, "uid", None)
        except Exception:
            session_uid = None
        first_checkpoint = not self._checkpoints
        session_changed = (
            session_uid is not None and self._checkpoint_session_uid is not None
            and session_uid != self._checkpoint_session_uid
        )
        interval_due = position - self._checkpoint_position >= _CHECKPOINT_PACKET_INTERVAL
        # Long realtime playback does not need a full serialized engine at every
        # lap boundary. Keep an initial anchor, session boundaries and sparse
        # periodic anchors only. This prevents checkpoint memory/GC cost from
        # growing with race distance.
        if not first_checkpoint and not session_changed and not interval_due:
            self._checkpoint_lap = lap
            if session_uid is not None:
                self._checkpoint_session_uid = session_uid
            return
        try:
            checkpoint = receiver.export_replay_checkpoint()
            size = len(checkpoint) if isinstance(checkpoint, (bytes, bytearray, memoryview)) else 0
            # A pathological single snapshot must never consume the whole replay
            # memory budget. Seeking can always rebuild from an older anchor.
            if size and size > _MAX_REPLAY_CHECKPOINT_BYTES:
                return
            old = self._checkpoints.pop(position, None)
            if isinstance(old, (bytes, bytearray, memoryview)):
                self._checkpoint_bytes = max(0, self._checkpoint_bytes - len(old))
            self._checkpoints[position] = checkpoint
            self._checkpoint_bytes += size
            self._checkpoint_lap = lap
            self._checkpoint_session_uid = session_uid
            self._checkpoint_position = position
            while (len(self._checkpoints) > _MAX_REPLAY_CHECKPOINTS or
                   self._checkpoint_bytes > _MAX_REPLAY_CHECKPOINT_BYTES):
                oldest = min(self._checkpoints)
                removed = self._checkpoints.pop(oldest)
                if isinstance(removed, (bytes, bytearray, memoryview)):
                    self._checkpoint_bytes = max(0, self._checkpoint_bytes - len(removed))
        except Exception:
            pass

    def _nearest_checkpoint(self, target: int):
        eligible = [p for p in self._checkpoints if p <= target]
        if not eligible:
            return None, None
        pos = max(eligible)
        return pos, self._checkpoints[pos]

    def _rebuild(self, receiver, target: int, source, stop_event=None) -> bool:
        with self._lock:
            self._rebuilding = True
        completed = False
        try:
            checkpoint_pos, checkpoint = self._nearest_checkpoint(target)
            start_index = 0
            if checkpoint is not None and hasattr(receiver, 'restore_replay_checkpoint'):
                receiver.restore_replay_checkpoint(checkpoint)
                start_index = int(checkpoint_pos)
                self._checkpoint_lap = self._current_lap(receiver)
                self._checkpoint_position = start_index
            elif hasattr(receiver, 'reset_replay_state'):
                receiver.reset_replay_state()
                self._checkpoint_lap = None
                self._checkpoint_position = 0
            if hasattr(receiver, '_replay_silent'):
                receiver._replay_silent = True
            if hasattr(receiver, '_replay_rebuild'):
                receiver._replay_rebuild = True
            base = time.monotonic()
            for i in range(start_index, target):
                record = self.records[i]
                if stop_event is not None and stop_event.is_set():
                    return False
                # If the user drags to another point while rebuilding, abandon the
                # obsolete seek quickly; the next loop rebuilds directly to the
                # newest requested position instead of making them wait twice.
                if i % 64 == 0:
                    with self._lock:
                        if self._seek_to is not None:
                            return True
                    # The deterministic rebuild is CPU-heavy Python work. Yield the
                    # GIL regularly so the Qt UI remains responsive while a large
                    # seek is being reconstructed. This does not change replay state.
                    time.sleep(0)
                receiver.process_packet(record.data, source, base + record.offset_s)
                if i % 64 == 0:
                    self._cache_checkpoint_if_new_lap(receiver, i + 1)
            self._cache_checkpoint_if_new_lap(receiver, target)
            if hasattr(receiver, 'finish_replay_seek'):
                receiver.finish_replay_seek()
            with self._lock:
                self._position = target
                if self._requested_position == target:
                    self._requested_position = None
                completed = True
            return True
        finally:
            if hasattr(receiver, '_replay_silent'):
                receiver._replay_silent = False
            if hasattr(receiver, '_replay_rebuild'):
                receiver._replay_rebuild = False
            with self._lock:
                self._rebuilding = False
                # A completed target clears the pending display request. A newer
                # request intentionally remains so the slider stays on that point.
                if completed and self._requested_position == target:
                    self._requested_position = None

    @staticmethod
    def _build_game_timeline(records: list[ReplayRecord]) -> list[float]:
        """Build a smooth 1x game clock across a complete F1 weekend recording.

        Normal driving uses EA ``m_sessionTime`` deltas.  Session boundaries and
        loading/menu discontinuities are deliberately collapsed to a single small
        frame step.  This is important for one-file Practice -> Qualifying -> Race
        recordings: a new session UID is authoritative, and large game-time jumps
        or transition-only packets must never make interactive replay wait minutes
        before the next session.
        """
        if not records:
            return []
        out = array("d")
        previous_logical = 0.0
        previous_arrival = records.offset_at(0) if hasattr(records, "offset_at") else records[0].offset_s
        previous_session: float | None = None
        previous_uid: int | None = None

        # A genuine F1 frame-to-frame advance is far below this.  Anything larger
        # is a recording/session/loading discontinuity and is collapsed rather than
        # reproduced as dead wall-clock time.
        max_continuous_game_step = 0.500
        transition_step = 0.050
        invalid_metadata_step = 0.050

        for index in range(len(records)):
            if hasattr(records, "game_metadata"):
                session_time, session_uid = records.game_metadata(index)
                record_offset = records.offset_at(index)
            else:
                record = records[index]
                record_offset = record.offset_s
                session_time, session_uid = _replay_clock_metadata(record.data)

            arrival_dt = max(0.0, float(record_offset) - float(previous_arrival))
            previous_arrival = record_offset

            if session_time is None:
                # Transition/menu datagrams can lack a production-valid F1 header.
                # Preserve ordering, but never turn a long run of such packets into
                # a visible stop between weekend sessions.
                logical = previous_logical + min(arrival_dt, invalid_metadata_step)
            elif previous_session is None:
                logical = previous_logical
                previous_session = session_time
            else:
                uid_changed = (
                    session_uid is not None and previous_uid is not None
                    and session_uid != previous_uid
                )
                game_dt = float(session_time) - float(previous_session)
                time_reset = game_dt < -0.100
                time_jump = game_dt > max_continuous_game_step

                if uid_changed or time_reset or time_jump:
                    # Stitch Practice -> Qualifying -> Race and any menu/loading
                    # discontinuity with at most one small frame-sized step.
                    logical = previous_logical + min(max(arrival_dt, 0.001), transition_step)
                else:
                    logical = previous_logical + max(0.0, game_dt)
                previous_session = session_time

            if session_uid is not None:
                previous_uid = session_uid
            previous_logical = max(previous_logical, logical)
            out.append(previous_logical)
        return out

    def _logical_time(self, position: int, recorded: bool) -> float:
        if recorded:
            # "Recorded timing" now means the recording's authoritative *game*
            # timeline, not incidental UDP arrival jitter.  This preserves 1.0x game
            # time while eliminating recorder-induced freezes/jumps.
            if len(self._game_timeline) == len(self.records):
                return self._game_timeline[position]
            return self.records.offset_at(position) if hasattr(self.records, "offset_at") else self.records[position].offset_s
        if len(self.records) <= 1:
            return 0.0
        if hasattr(self.records, "offset_at"):
            duration = max(0.001, self.records.offset_at(len(self.records)-1) - self.records.offset_at(0))
        else:
            duration = max(0.001, self.records[-1].offset_s - self.records[0].offset_s)
        return position * (duration / (len(self.records) - 1))

    def run(self, receiver, *, source=("127.0.0.1", 20777), stop_event=None) -> int:
        """Run interactive replay on an absolute, drift-free timeline.

        V0.9.13.0 waited the recorded interval *after* processing each packet.
        That made 1.0x replay run slower than real time by the cumulative decode /
        state / engineer cost.  This scheduler anchors packet timestamps to one
        monotonic wall clock, so processing time is automatically subtracted from
        the next wait and cannot accumulate as replay latency.
        """
        if not self.records:
            return 0
        count = 0
        previous_position = None
        anchor_wall = None
        anchor_logical = None
        anchor_revision = None
        anchor_speed = None
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            with self._changed:
                seek_to = self._seek_to
                if seek_to is not None:
                    self._seek_to = None
                pos = self._position
                start, end = self._range_start, self._range_end
                paused = self._paused
                speed = self._speed
                recorded = self._use_record_timestamps
                timing_revision = self._timing_revision
            if seek_to is not None:
                if not self._rebuild(receiver, seek_to, source, stop_event):
                    break
                previous_position = None
                anchor_wall = anchor_logical = None
                anchor_revision = anchor_speed = None
                continue
            if pos < start:
                self.seek(start)
                continue
            if pos > end or pos >= len(self.records):
                self.set_paused(True)
                with self._changed:
                    self._changed.wait(timeout=0.05)
                previous_position = None
                anchor_wall = anchor_logical = None
                continue
            if paused:
                with self._changed:
                    self._changed.wait(timeout=0.05)
                # Paused wall time must never become replay catch-up time.
                anchor_wall = anchor_logical = None
                anchor_revision = anchor_speed = None
                continue

            logical = self._logical_time(pos, recorded)
            deadline = None
            if self.realtime:
                sequential = previous_position is not None and pos == previous_position + 1
                reanchor = (
                    anchor_wall is None or anchor_logical is None or not sequential or
                    anchor_revision != timing_revision or anchor_speed != speed
                )
                if reanchor:
                    anchor_wall = time.monotonic()
                    if sequential:
                        anchor_logical = self._logical_time(previous_position, recorded)
                    else:
                        anchor_logical = logical
                    anchor_revision = timing_revision
                    anchor_speed = speed
                deadline = anchor_wall + max(0.0, logical - anchor_logical) / max(0.10, speed)
                if not self._wait_until_interruptible(deadline, timing_revision, stop_event):
                    # A control changed while waiting. Re-read it and establish a
                    # fresh clock anchor instead of carrying stale elapsed time.
                    anchor_wall = anchor_logical = None
                    anchor_revision = anchor_speed = None
                    continue

                # Never turn decoder/overlay latency into a high-speed catch-up
                # burst.  On dense 2026 recordings one expensive packet or a GC /
                # checkpoint pause can put the replay tens of milliseconds behind.
                # The old absolute scheduler then processed hundreds of packets as
                # fast as possible until it caught up, which looked like skipped
                # corners/laps and made every overlay visibly choppy.  Re-anchor
                # once the lag exceeds a small human-visible budget.  No packet is
                # dropped: playback simply resumes smoothly from the current game
                # timestamp instead of racing through stale timestamps.
                lag = time.monotonic() - deadline
                if lag > _MAX_REALTIME_CATCHUP_S:
                    anchor_wall = time.monotonic()
                    anchor_logical = logical
                    deadline = anchor_wall
                    self._clock_drift_s = lag

            # A recording can be switched from the Control Center while this
            # worker is running.  Re-check the timing revision under the lock
            # before dereferencing the record array so an old packet index can
            # never be applied to a newly loaded file.
            with self._lock:
                if timing_revision != self._timing_revision or pos >= len(self.records):
                    anchor_wall = anchor_logical = None
                    anchor_revision = anchor_speed = None
                    continue
                record = self.records[pos]
            receiver.process_packet(record.data, source, time.monotonic())
            count += 1
            if deadline is not None:
                # Positive = this packet completed behind its target timestamp.
                # This is informational only; the next absolute deadline catches
                # up automatically rather than propagating the delay.
                self._clock_drift_s = time.monotonic() - deadline
            self._cache_checkpoint_if_new_lap(receiver, pos + 1)
            previous_position = pos
            with self._lock:
                self._position = pos + 1
        return count


def replay_into(receiver, path: Path | str, *, speed: float = 1.0, realtime: bool = True,
                source=("127.0.0.1", 20777), stop_event=None, pause_event=None, controller=None) -> int:
    """Replay a recording through the receiver's normal packet-processing path.

    speed=1 preserves original timing; 2 is twice as fast. realtime=False performs
    deterministic no-sleep replay, useful for tests and rapid analysis. When an
    interactive ReplayController is supplied, it owns pause/seek/range/speed.
    """
    if controller is not None:
        return controller.run(receiver, source=source, stop_event=stop_event)
    if speed <= 0:
        raise ValueError("Replay speed must be greater than zero")
    records = read_replay(path)
    if not records:
        return 0
    wall_start = time.monotonic()
    logical_start = wall_start
    count = 0
    paused_total = 0.0
    for record in records:
        if stop_event is not None and stop_event.is_set():
            break
        target = record.offset_s / speed
        if realtime:
            # Preserve the original replay timing while allowing the UI pause
            # button to stop playback without causing a catch-up burst on resume.
            while True:
                if stop_event is not None and stop_event.is_set():
                    return count
                if pause_event is not None and pause_event.is_set():
                    pause_started = time.monotonic()
                    while pause_event.is_set():
                        if stop_event is not None and stop_event.is_set():
                            return count
                        time.sleep(0.02)
                    paused_total += time.monotonic() - pause_started
                delay = wall_start + paused_total + target - time.monotonic()
                if delay <= 0:
                    break
                time.sleep(min(delay, 0.02))
            now = time.monotonic()
        else:
            # Fast deterministic replay ignores pause because there is no human-
            # visible timing to preserve.
            now = logical_start + target
        receiver.process_packet(record.data, source, now)
        count += 1
    return count

class AsyncTelemetrySessionRecorder:
    """Lossless live recorder whose disk writes never run on the UDP thread.

    The queue is intentionally unbounded: dropping a raw telemetry datagram would
    violate the replay format's lossless guarantee.  Normal local disk throughput
    is far above F1 UDP throughput, so the queue should stay near zero; `pending`
    is exposed for diagnostics.
    """
    _STOP = object()

    def __init__(self, directory: Path | None = None, *, path: Path | None = None) -> None:
        from queue import SimpleQueue
        self._writer = TelemetrySessionRecorder(directory=directory, path=path)
        self._queue = SimpleQueue()
        self._accepted = 0
        self._pending = 0
        self._lock = threading.Lock()
        self.last_error: str | None = None
        self._closed = False
        self._thread = threading.Thread(target=self._worker, name="race-engineer-recorder", daemon=True)
        self._thread.start()

    @property
    def path(self):
        return self._writer.path

    @property
    def metadata_path(self):
        return self._writer.metadata_path

    @property
    def count(self) -> int:
        return self._accepted

    @property
    def bytes(self) -> int:
        return self._writer.bytes

    @property
    def pending(self) -> int:
        with self._lock:
            return self._pending

    def record(self, data: bytes, now: float | None = None) -> None:
        if self._closed or self.last_error is not None:
            return
        # `data` is already an immutable bytes object returned by recvfrom(), so
        # queueing it does not copy the packet payload.
        if now is None:
            now = time.monotonic()
        with self._lock:
            self._accepted += 1
            self._pending += 1
        self._queue.put((data, float(now)))

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is self._STOP:
                break
            data, now = item
            try:
                if self.last_error is None:
                    self._writer.record(data, now)
            except OSError as error:
                self.last_error = str(error)
            finally:
                with self._lock:
                    self._pending = max(0, self._pending - 1)
        try:
            self._writer.close()
        except OSError as error:
            self.last_error = self.last_error or str(error)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put(self._STOP)
        self._thread.join(timeout=10.0)
        if self._thread.is_alive():
            self.last_error = self.last_error or "Recorder worker did not stop cleanly"
