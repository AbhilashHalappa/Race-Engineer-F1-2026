import contextlib
import io
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from src.capture import PacketCapture
from src.race_state_receiver import RaceStateReceiver
from packet_fixtures import packet, car_packet, event


class RuntimeTests(unittest.TestCase):
    def test_bad_bodies_do_not_reset_state(self):
        r = RaceStateReceiver()
        r.process_packet(car_packet(6, {'m_speed':200}), ('127.0.0.1', 1), 1)
        for data in (packet(1, uid=222)[:-1], b'bad', packet(0), packet(6, version=2), event('ZZZZ')):
            r.process_packet(data, ('127.0.0.1', 1), 2)
        self.assertEqual(r.engine.state.session.uid, 111)
        self.assertEqual(r.engine.state.player.telemetry.speed_kph, 200)
        self.assertEqual((r.valid_bodies, r.malformed_bodies, r.unknown_events), (2, 2, 1))
        self.assertEqual(sum(r.unsupported_packets.values()), 1)
        self.assertEqual(sum(r.invalid_reasons.values()), 1)

    def test_packet_stats_and_size_modes(self):
        for stats in (False, True):
            r = RaceStateReceiver(packet_stats=stats, show_sizes=True)
            r.process_packet(packet(1), ('127.0.0.1', 1), 1)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                r.print_status(1, 2)
            text = output.getvalue()
            self.assertIn('Packet sizes', text)
            self.assertIn('Bodies valid: 1', text)
            self.assertEqual('Packet types (since startup)' in text, stats)

    def test_capture_bounded_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = PacketCapture(2, Path(directory))
            capture.record(b'one')
            capture.record(b'two')
            capture.record(b'not recorded')
            self.assertEqual(capture.count, 2)
            self.assertIsNone(capture._file)
            self.assertEqual(capture.path.read_bytes(), b'ARECAP01' + struct.pack('<I', 3) + b'one' + struct.pack('<I', 3) + b'two')

    def test_capture_disabled_by_default(self):
        self.assertIsNone(RaceStateReceiver().capture)

    def test_capture_failure_does_not_stop_state(self):
        r = RaceStateReceiver(capture_packets=1)
        with patch.object(r.capture, 'record', side_effect=OSError('disk unavailable')):
            r.process_packet(packet(1), ('127.0.0.1', 1), 1)
        self.assertEqual(r.valid_bodies, 1)
        self.assertIn('disk unavailable', r.capture_error)

    def test_capture_bounds(self):
        for count in (0, -1, 2001):
            with self.assertRaises(ValueError):
                PacketCapture(count)

    def test_native_socket_idle_mixed_traffic_stop_and_release(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reserve:
            reserve.bind(('127.0.0.1', 0))
            port = reserve.getsockname()[1]
        r = RaceStateReceiver('127.0.0.1', port)
        stop, ready = threading.Event(), threading.Event()
        errors = []

        class Output(io.StringIO):
            def write(self, text):
                if 'Waiting for F1 telemetry...' in text:
                    ready.set()
                return super().write(text)

        def receive():
            try:
                r.run(stop)
            except BaseException as error:
                errors.append(error)

        with contextlib.redirect_stdout(Output()) as output:
            worker = threading.Thread(target=receive, daemon=True)
            worker.start()
            try:
                self.assertTrue(ready.wait(3))
                # Allow an idle report before any traffic.
                deadline = time.monotonic() + 3
                while 'Total UDP: 0' not in output.getvalue() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertIn('Total UDP: 0', output.getvalue())
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    for data in (b'bad', packet(1)[:-1], car_packet(6, {'m_speed':287}),
                                 event('ZZZZ'), packet(1, uid=222)):
                        sender.sendto(data, ('127.0.0.1', port))
                deadline = time.monotonic() + 3
                while r.total_packets < 5 and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(worker.is_alive())
            finally:
                stop.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(r.total_packets, 5)
        self.assertEqual(r.malformed_bodies, 1)
        self.assertEqual(r.engine.state.session.uid, 222)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(('127.0.0.1', port))
