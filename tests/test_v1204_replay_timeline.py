from pathlib import Path

from src.telemetry.header import HEADER_STRUCT
from src.telemetry_recording import ReplayController, TelemetrySessionRecorder


def _packet(session_time: float, frame: int, packet_id: int = 0) -> bytes:
    header = HEADER_STRUCT.pack(
        2026, 26, 1, 0, 1, packet_id,
        123456789, float(session_time), int(frame), int(frame), 0, 255,
    )
    return header


def test_interactive_replay_uses_game_session_time_not_udp_arrival_stall(tmp_path: Path):
    path = tmp_path / "stall.areplay"
    rec = TelemetrySessionRecorder(path=path)
    rec.record(_packet(10.000, 100, 2), 100.000)
    rec.record(_packet(10.000, 100, 0), 101.500)  # 1.5 s OS/arrival stall, same game frame
    rec.record(_packet(10.050, 101, 2), 101.510)
    rec.close()

    ctl = ReplayController(path, speed=1.0, realtime=True)
    assert ctl._logical_time(0, True) == 0.0
    assert ctl._logical_time(1, True) == 0.0
    assert abs(ctl._logical_time(2, True) - 0.050) < 1e-6


def test_game_timeline_stitches_session_time_reset_monotonically(tmp_path: Path):
    path = tmp_path / "reset.areplay"
    rec = TelemetrySessionRecorder(path=path)
    rec.record(_packet(20.000, 200), 50.000)
    rec.record(_packet(20.040, 201), 50.040)
    rec.record(_packet(0.000, 0), 52.000)  # new session/reset
    rec.record(_packet(0.050, 1), 52.050)
    rec.close()

    ctl = ReplayController(path)
    times = [ctl._logical_time(i, True) for i in range(4)]
    assert times == sorted(times)
    assert 0.040 <= times[1] <= 0.041
    assert 0.040 < times[2] <= 0.091
    assert times[3] > times[2]


def test_uniform_timing_mode_remains_available(tmp_path: Path):
    path = tmp_path / "uniform.areplay"
    rec = TelemetrySessionRecorder(path=path)
    rec.record(_packet(1.0, 1), 10.0)
    rec.record(_packet(1.0, 1), 11.0)
    rec.record(_packet(1.1, 2), 12.0)
    rec.close()
    ctl = ReplayController(path)
    ctl.set_use_record_timestamps(False)
    assert abs(ctl._logical_time(1, False) - 1.0) < 1e-9


def _packet_uid(session_time: float, frame: int, session_uid: int, packet_id: int = 0) -> bytes:
    return HEADER_STRUCT.pack(
        2026, 26, 1, 0, 1, packet_id,
        int(session_uid), float(session_time), int(frame), int(frame), 0, 255,
    )


def test_game_timeline_stitches_weekend_session_uid_change_even_without_time_reset(tmp_path: Path):
    """Practice -> qualifying -> race must continue without replaying menu/loading gaps.

    Some F1 weekend transitions start the next session with a session-time value
    that is not lower than the preceding final packet.  UID is the authoritative
    boundary, so the replay clock must still stitch the sessions together.
    """
    path = tmp_path / "weekend.areplay"
    rec = TelemetrySessionRecorder(path=path)
    rec.record(_packet_uid(100.000, 1000, 111), 10.000)
    rec.record(_packet_uid(100.050, 1001, 111), 10.050)
    # Five minutes of real/menu time pass. The next session happens to expose a
    # numerically larger sessionTime, so a time-reset-only detector would wait.
    rec.record(_packet_uid(120.000, 1, 222), 310.000)
    rec.record(_packet_uid(120.050, 2, 222), 310.050)
    rec.close()

    ctl = ReplayController(path)
    times = [ctl._logical_time(i, True) for i in range(4)]
    assert times == sorted(times)
    assert times[1] <= 0.051
    # The weekend transition is one small frame step, not a 20 s game-time jump
    # or a 300 s recorder/menu gap.
    assert 0.050 < times[2] <= 0.101
    assert 0.045 <= times[3] - times[2] <= 0.055


def test_realtime_scheduler_does_not_catch_up_in_a_packet_burst_after_stall(tmp_path: Path):
    import time

    path = tmp_path / "stall_burst.areplay"
    rec = TelemetrySessionRecorder(path=path)
    base = 20.0
    for i in range(10):
        rec.record(_packet_uid(base + i * 0.020, i, 333, 2), 100.0 + i * 0.020)
    rec.close()

    class SlowOnceReceiver:
        def __init__(self):
            self.starts = []
            self._replay_silent = False
            self._replay_rebuild = False

        def process_packet(self, data, source, now):
            self.starts.append(time.monotonic())
            # One realistic UI/GC/serialization-style hitch.
            if len(self.starts) == 3:
                time.sleep(0.150)

    import threading
    ctl = ReplayController(path, speed=1.0, realtime=True)
    receiver = SlowOnceReceiver()
    stop = threading.Event()
    worker = threading.Thread(target=lambda: ctl.run(receiver, stop_event=stop), daemon=True)
    worker.start()
    deadline = time.monotonic() + 2.0
    while len(receiver.starts) < 10 and time.monotonic() < deadline:
        time.sleep(0.005)
    stop.set()
    worker.join(timeout=1.0)

    assert len(receiver.starts) == 10  # no packet dropping
    # Packet 4 may execute immediately when the late deadline is detected, but
    # the scheduler must then resume paced playback instead of bursting all the
    # remaining stale packets back-to-back.
    assert receiver.starts[4] - receiver.starts[3] >= 0.010


def _packet_transition(session_time: float, frame: int, session_uid: int, *, player_index: int = 255) -> bytes:
    return HEADER_STRUCT.pack(
        2026, 26, 1, 0, 1, 0,
        int(session_uid), float(session_time), int(frame), int(frame), int(player_index), 255,
    )


def test_indexed_replay_clock_accepts_transition_header_without_active_player(tmp_path: Path):
    """Player index 255 during menu/session handoff must not hide the new UID."""
    path = tmp_path / "transition_player_255.areplay"
    rec = TelemetrySessionRecorder(path=path)
    rec.record(_packet_uid(900.000, 9000, 111), 10.000)
    # New qualifying UID first appears while there is no active player car.
    rec.record(_packet_transition(15.000, 1, 222, player_index=255), 90.000)
    rec.record(_packet_uid(15.050, 2, 222), 90.050)
    rec.close()

    ctl = ReplayController(path)
    times = [ctl._logical_time(i, True) for i in range(3)]
    assert times == sorted(times)
    assert 0.0 < times[1] <= 0.051
    assert 0.045 <= times[2] - times[1] <= 0.055


def test_replay_clock_collapses_large_same_uid_loading_jump(tmp_path: Path):
    """A large stale/session-time discontinuity cannot create a visible replay stop."""
    path = tmp_path / "same_uid_jump.areplay"
    rec = TelemetrySessionRecorder(path=path)
    rec.record(_packet_uid(100.000, 100, 777), 10.000)
    rec.record(_packet_uid(100.050, 101, 777), 10.050)
    # Some weekend/loading phases keep the old UID while sessionTime jumps.
    rec.record(_packet_uid(240.000, 102, 777), 150.000)
    rec.record(_packet_uid(0.000, 1, 888), 151.000)
    rec.record(_packet_uid(0.050, 2, 888), 151.050)
    rec.close()

    ctl = ReplayController(path)
    times = [ctl._logical_time(i, True) for i in range(5)]
    assert times == sorted(times)
    assert times[2] - times[1] <= 0.051
    assert times[3] - times[2] <= 0.051
    assert 0.045 <= times[4] - times[3] <= 0.055


def test_full_weekend_practice_qualifying_race_auto_continues(tmp_path: Path):
    """Three-session weekend replay must not stall at either session boundary."""
    path = tmp_path / "full_weekend.areplay"
    rec = TelemetrySessionRecorder(path=path)
    # Practice
    rec.record(_packet_uid(600.000, 6000, 1001), 10.000)
    rec.record(_packet_uid(600.050, 6001, 1001), 10.050)
    # Transition packet has no active player and a large stale game-time jump.
    rec.record(_packet_transition(900.000, 0, 2002, player_index=255), 180.000)
    # Qualifying
    rec.record(_packet_uid(20.000, 1, 2002), 180.050)
    rec.record(_packet_uid(20.050, 2, 2002), 180.100)
    # Another menu/loading discontinuity, then Race.
    rec.record(_packet_transition(400.000, 0, 3003, player_index=255), 400.000)
    rec.record(_packet_uid(5.000, 1, 3003), 400.050)
    rec.record(_packet_uid(5.050, 2, 3003), 400.100)
    rec.close()

    ctl = ReplayController(path)
    times = [ctl._logical_time(i, True) for i in range(8)]
    assert times == sorted(times)
    # Neither weekend boundary may introduce a visible multi-second pause.
    assert times[2] - times[1] <= 0.051
    assert times[3] - times[2] <= 0.051
    assert times[5] - times[4] <= 0.051
    assert times[6] - times[5] <= 0.051
    assert times[-1] < 0.40
