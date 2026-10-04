from pathlib import Path

from src.telemetry_recording import ReplayController, TelemetrySessionRecorder


def _make_replay(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.areplay"
    rec = TelemetrySessionRecorder(path=path)
    rec.record(b"a", 10.0)
    rec.record(b"bb", 10.1)
    rec.record(b"ccc", 10.3)
    rec.record(b"dddd", 10.6)
    rec.close()
    return path


def test_replay_controller_exposes_position_range_speed_and_timing(tmp_path):
    path = _make_replay(tmp_path)
    ctl = ReplayController(path, speed=1.0, realtime=True)
    status = ctl.status()
    assert status.total == 4
    assert status.position == 0
    assert (status.range_start, status.range_end) == (0, 3)
    assert status.speed == 1.0
    assert status.use_record_timestamps is True

    ctl.set_speed(2.5)
    ctl.set_use_record_timestamps(False)
    ctl.set_range(1, 2)
    ctl.seek(2)
    status = ctl.status()
    assert status.speed == 2.5
    assert status.use_record_timestamps is False
    assert (status.range_start, status.range_end) == (1, 2)


def test_replay_controller_range_clamps_and_resume_restarts_completed_range(tmp_path):
    path = _make_replay(tmp_path)
    ctl = ReplayController(path)
    ctl.set_range(-100, 999)
    status = ctl.status()
    assert (status.range_start, status.range_end) == (0, 3)

    # Simulate a range that has already finished. Resume requests a deterministic
    # seek back to the range start rather than immediately pausing again.
    ctl.set_range(1, 2)
    ctl._position = 3
    ctl.set_paused(True)
    ctl.set_paused(False)
    assert ctl._seek_to == 1

class _FakeReceiver:
    def __init__(self):
        self.data = []
        self.reset_count = 0
        self.finish_count = 0
        self._replay_silent = False

    def reset_replay_state(self):
        self.data.clear()
        self.reset_count += 1

    def process_packet(self, data, source, now):
        self.data.append(data)

    def finish_replay_seek(self):
        self.finish_count += 1


def test_replay_seek_rebuilds_state_from_recording_start(tmp_path):
    ctl = ReplayController(_make_replay(tmp_path))
    fake = _FakeReceiver()
    assert ctl._rebuild(fake, 3, ("127.0.0.1", 20777)) is True
    assert fake.reset_count == 1
    assert fake.finish_count == 1
    assert fake.data == [b"a", b"bb", b"ccc"]
    assert ctl.status().position == 3
    assert fake._replay_silent is False
