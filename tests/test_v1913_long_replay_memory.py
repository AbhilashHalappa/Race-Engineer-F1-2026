from pathlib import Path

from src.telemetry.header import HEADER_STRUCT
from src.telemetry_recording import (
    ReplayController,
    TelemetrySessionRecorder,
    _MAX_REPLAY_CHECKPOINT_BYTES,
    _MAX_REPLAY_CHECKPOINTS,
    _IndexedReplayRecords,
)


def _packet(session_time: float, frame: int, uid: int = 123, packet_id: int = 0, pad: int = 256) -> bytes:
    header = HEADER_STRUCT.pack(
        2026, 26, 1, 0, 1, packet_id,
        uid, float(session_time), int(frame), int(frame), 0, 255,
    )
    return header + (b"x" * pad)


def test_interactive_controller_indexes_payload_instead_of_materialising_all_packet_bytes(tmp_path: Path):
    path = tmp_path / "largeish.areplay"
    rec = TelemetrySessionRecorder(path=path)
    for i in range(500):
        rec.record(_packet(i * 0.02, i, pad=2048), 100.0 + i * 0.02)
    rec.close()

    ctl = ReplayController(path)
    assert isinstance(ctl.records, _IndexedReplayRecords)
    assert len(ctl.records) == 500
    # Numeric index arrays scale with packet count, not UDP payload bytes.
    index_bytes = (
        ctl.records._offsets.buffer_info()[1] * ctl.records._offsets.itemsize
        + ctl.records._data_offsets.buffer_info()[1] * ctl.records._data_offsets.itemsize
        + ctl.records._sizes.buffer_info()[1] * ctl.records._sizes.itemsize
        + ctl.records._session_times.buffer_info()[1] * ctl.records._session_times.itemsize
        + ctl.records._session_uids.buffer_info()[1] * ctl.records._session_uids.itemsize
    )
    assert index_bytes < path.stat().st_size * 0.10
    assert ctl.records[123].data.startswith(HEADER_STRUCT.pack(
        2026, 26, 1, 0, 1, 0, 123, float(123 * 0.02), 123, 123, 0, 255
    ))
    ctl.records.close()


class _State:
    def __init__(self):
        self.session = type("Session", (), {"uid": 1})()
        self.player = type("Player", (), {})()
        self.player.lap = type("Lap", (), {"current_lap": 1})()


class _CheckpointReceiver:
    def __init__(self, checkpoint_size: int):
        self.engine = type("Engine", (), {"state": _State()})()
        self.checkpoint_size = checkpoint_size
        self.exports = 0

    def export_replay_checkpoint(self):
        self.exports += 1
        return bytes(self.checkpoint_size)


def test_checkpoint_cache_has_hard_count_and_memory_budget(tmp_path: Path):
    path = tmp_path / "one.areplay"
    rec = TelemetrySessionRecorder(path=path)
    rec.record(_packet(0.0, 0), 1.0)
    rec.close()
    ctl = ReplayController(path)
    receiver = _CheckpointReceiver(max(1, _MAX_REPLAY_CHECKPOINT_BYTES // 4))

    # Force sparse periodic anchors without depending on a real race packet stream.
    for i in range(12):
        ctl._checkpoint_position = i * 1000
        pos = ctl._checkpoint_position + 131072
        ctl._cache_checkpoint_if_new_lap(receiver, pos)

    assert len(ctl._checkpoints) <= _MAX_REPLAY_CHECKPOINTS
    assert ctl._checkpoint_bytes <= _MAX_REPLAY_CHECKPOINT_BYTES
    ctl.records.close()
