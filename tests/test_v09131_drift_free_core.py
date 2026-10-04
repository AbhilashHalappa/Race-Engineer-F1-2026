import threading
import time

from src.telemetry_recording import ReplayController, TelemetrySessionRecorder


class _SlowReceiver:
    def __init__(self, stop_event, expected):
        self.stop_event = stop_event
        self.expected = expected
        self.count = 0

    def process_packet(self, data, source, now):
        # Deliberately simulate expensive decode/state/overlay work. A relative
        # per-packet sleeper would add this delay to every replay interval.
        time.sleep(0.003)
        self.count += 1
        if self.count >= self.expected:
            self.stop_event.set()


def test_interactive_replay_absolute_clock_does_not_accumulate_processing_time(tmp_path):
    path = tmp_path / "drift.areplay"
    recorder = TelemetrySessionRecorder(path=path)
    packet_count = 21
    interval = 0.02
    for i in range(packet_count):
        recorder.record(b"x", 100.0 + i * interval)
    recorder.close()

    controller = ReplayController(path, speed=1.0, realtime=True)
    stop = threading.Event()
    receiver = _SlowReceiver(stop, packet_count)
    started = time.perf_counter()
    processed = controller.run(receiver, stop_event=stop)
    elapsed = time.perf_counter() - started

    recorded_duration = (packet_count - 1) * interval
    assert processed == packet_count
    # Drift-free playback should be near recorded duration + only the final
    # packet's processing cost. The old scheduler would be ~0.46 s here because
    # all 21 processing sleeps accumulated on top of the 0.40 s recording.
    assert recorded_duration * 0.90 <= elapsed < recorded_duration + 0.04
    assert abs(controller.status().clock_drift_s) < 0.04


def test_compiled_layout_decoder_matches_generic_reader_for_all_packet_layouts():
    from src.telemetry.decoders import LAYOUTS

    for packet_id, layout in LAYOUTS.items():
        values = layout.struct.unpack(bytes(layout.size))
        generic, consumed = layout._read_from(values, 0)
        compiled = layout._compiled_decode(values)
        assert compiled == generic, packet_id
        assert consumed == len(values), packet_id
