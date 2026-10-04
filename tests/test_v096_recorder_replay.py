import tempfile
import unittest
import threading
import time
from pathlib import Path

from src.telemetry_recording import TelemetrySessionRecorder, read_replay, replay_into, MAGIC
from src.race_state_receiver import RaceStateReceiver
from tests.packet_fixtures import packet


class RecorderReplayTests(unittest.TestCase):
    def test_round_trip_preserves_bytes_and_timing(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'session.areplay'
            r = TelemetrySessionRecorder(path=path)
            r.record(b'one', 10.0); r.record(b'two', 10.25); r.close()
            rows = read_replay(path)
            self.assertEqual([x.data for x in rows], [b'one', b'two'])
            self.assertAlmostEqual(rows[1].offset_s, .25, places=6)
            self.assertTrue(path.read_bytes().startswith(MAGIC))
            self.assertTrue(path.with_suffix('.areplay.json').exists())

    def test_fast_replay_uses_normal_receiver_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'session.areplay'
            rec = TelemetrySessionRecorder(path=path)
            rec.record(packet(1, uid=456), 20.0); rec.close()
            receiver = RaceStateReceiver(tts_enabled=False)
            count = replay_into(receiver, path, realtime=False)
            self.assertEqual(count, 1)
            self.assertEqual(receiver.total_packets, 1)
            self.assertEqual(receiver.valid_bodies, 1)
            self.assertEqual(receiver.engine.state.session.uid, 456)
            receiver.speech.close(wait=True)


    def test_realtime_replay_can_pause_without_catchup_burst(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'paused.areplay'
            rec = TelemetrySessionRecorder(path=path)
            rec.record(packet(1, uid=111), 10.0)
            rec.record(packet(1, uid=222), 10.12)
            rec.close()
            receiver = RaceStateReceiver(tts_enabled=False)
            pause = threading.Event(); pause.set()
            result = {}
            worker = threading.Thread(target=lambda: result.setdefault('count', replay_into(receiver, path, realtime=True, pause_event=pause)))
            worker.start()
            time.sleep(0.05)
            self.assertEqual(receiver.total_packets, 0)
            pause.clear()
            worker.join(timeout=1.0)
            self.assertFalse(worker.is_alive())
            self.assertEqual(result.get('count'), 2)
            self.assertEqual(receiver.engine.state.session.uid, 222)
            receiver.speech.close(wait=True)

    def test_corrupt_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'bad.areplay'; path.write_bytes(b'bad')
            with self.assertRaises(ValueError): read_replay(path)

    def test_receiver_recording_is_opt_in(self):
        self.assertIsNone(RaceStateReceiver(tts_enabled=False).recorder)


if __name__ == '__main__': unittest.main()
