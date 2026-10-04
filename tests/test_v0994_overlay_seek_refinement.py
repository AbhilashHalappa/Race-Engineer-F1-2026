from pathlib import Path

from src.telemetry_recording import ReplayController, TelemetrySessionRecorder


def _make_replay(tmp_path: Path, count: int = 6) -> Path:
    path = tmp_path / "seek.areplay"
    rec = TelemetrySessionRecorder(path=path)
    for i in range(count):
        rec.record(bytes([65 + i]), 10.0 + i * 0.1)
    rec.close()
    return path


def test_seek_status_stays_at_requested_target_while_rebuild_is_pending(tmp_path):
    ctl = ReplayController(_make_replay(tmp_path))
    ctl._position = 1
    ctl.seek(5)
    status = ctl.status()
    assert status.position == 5
    assert status.requested_position == 5
    assert status.rebuilding is True


class _FastSeekReceiver:
    def __init__(self):
        self._replay_silent = False
        self._replay_rebuild = False
        self.flags_seen = []
        self.reset_count = 0
        self.finish_count = 0

    def reset_replay_state(self):
        self.reset_count += 1

    def process_packet(self, data, source, now):
        self.flags_seen.append((self._replay_silent, self._replay_rebuild, data))

    def finish_replay_seek(self):
        self.finish_count += 1


def test_seek_rebuild_uses_fast_silent_mode_and_clears_pending_target(tmp_path):
    ctl = ReplayController(_make_replay(tmp_path))
    receiver = _FastSeekReceiver()
    ctl.seek(4)
    # Simulate the run loop consuming the queued target before calling rebuild.
    ctl._seek_to = None
    assert ctl._rebuild(receiver, 4, ("127.0.0.1", 20777)) is True
    status = ctl.status()
    assert status.position == 4
    assert status.requested_position is None
    assert status.rebuilding is False
    assert receiver.reset_count == 1
    assert receiver.finish_count == 1
    assert receiver.flags_seen
    assert all(silent and rebuilding for silent, rebuilding, _ in receiver.flags_seen)
    assert receiver._replay_silent is False
    assert receiver._replay_rebuild is False
