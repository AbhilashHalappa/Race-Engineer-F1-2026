import contextlib
import io
import socket
import threading
import time
import unittest

from src.telemetry_receiver import TelemetryReceiver
from test_header import make_header


class TelemetryReceiverTests(unittest.TestCase):
    def test_waits_without_game_traffic(self):
        # Port zero lets the OS select an unused port, isolated from live F1.
        receiver = TelemetryReceiver("127.0.0.1", 0)
        stop = threading.Event()
        timer = threading.Timer(1.3, stop.set)
        output = io.StringIO()
        timer.start()
        try:
            with contextlib.redirect_stdout(output):
                receiver.run(stop)
        finally:
            timer.cancel()
            timer.join()
        self.assertEqual(receiver.total_packets, 0)
        self.assertIn("Packets/sec     : 0.0", output.getvalue())
        self.assertNotIn("F1 2026 TELEMETRY DETECTED", output.getvalue())

    def test_unrelated_traffic_never_marks_detected(self):
        receiver = TelemetryReceiver()
        for data in (b"", b"unrelated", b"x" * 100, make_header(format=2025)):
            receiver.process_packet(data, ("127.0.0.1", 1234), 1.0)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            receiver.print_status(4.0, 1.5)
        self.assertNotIn("F1 2026 TELEMETRY DETECTED", output.getvalue())
        self.assertIn("Wrong format: 2", output.getvalue())
        self.assertEqual(sum(receiver.invalid_reasons.values()), 4)
        self.assertEqual(receiver.total_packets, 4)

    def test_unknown_id_counted_separately(self):
        receiver = TelemetryReceiver()
        receiver.process_packet(make_header(packet_id=222), ("127.0.0.1", 1), 1)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            receiver.print_status(1, 2)
        self.assertEqual(receiver.unknown_ids[222], 1)
        self.assertEqual(sum(receiver.invalid_reasons.values()), 0)
        self.assertIn("UNKNOWN(222)", output.getvalue())
        self.assertIsNone(receiver.last_valid_at)

    def test_rates_use_elapsed_and_reset_each_report(self):
        receiver = TelemetryReceiver()
        for _ in range(3):
            receiver.process_packet(make_header(), ("127.0.0.1", 1), 1)
        receiver.report_elapsed = 1.5
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            receiver.print_status(2, 2)
        self.assertIn("3 total / 2.0 pps", output.getvalue())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            receiver.print_status(0, 3.5)
        self.assertIn("3 total / 0.0 pps", output.getvalue())

    def test_invalid_traffic_does_not_refresh_valid_header(self):
        receiver = TelemetryReceiver()
        receiver.process_packet(make_header(), ("127.0.0.1", 1), 1)
        receiver.process_packet(b"bad", ("127.0.0.1", 2), 5)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            receiver.print_status(1, 5)
        self.assertIn("Waiting for F1 telemetry", output.getvalue())
        self.assertEqual(receiver.telemetry_source, ("127.0.0.1", 1))
        self.assertEqual(receiver.source, ("127.0.0.1", 2))

    def test_sizes_are_optional(self):
        for enabled in (False, True):
            receiver = TelemetryReceiver(show_sizes=enabled)
            receiver.process_packet(make_header(), ("127.0.0.1", 1), 1)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                receiver.print_status(1, 2)
            self.assertEqual("Packet sizes" in output.getvalue(), enabled)

    def test_live_udp_malformed_then_valid_and_clean_stop(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reserve:
            reserve.bind(("127.0.0.1", 0))
            port = reserve.getsockname()[1]
        ready = threading.Event()
        stop = threading.Event()
        receiver = TelemetryReceiver("127.0.0.1", port)
        failures = []

        class Output(io.StringIO):
            def write(self, value):
                if "Waiting for F1 telemetry" in value:
                    ready.set()
                return super().write(value)

        def run():
            try:
                receiver.run(stop)
            except BaseException as error:
                failures.append(error)

        output = Output()
        with contextlib.redirect_stdout(output):
            worker = threading.Thread(target=run, daemon=True)
            worker.start()
            try:
                self.assertTrue(ready.wait(3), failures)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    for packet in (b"bad", make_header(format=2025), make_header(packet_id=222), make_header(packet_id=16)):
                        sender.sendto(packet, ("127.0.0.1", port))
                deadline = time.monotonic() + 3
                while "F1 2026 TELEMETRY DETECTED" not in output.getvalue() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(worker.is_alive())
            finally:
                stop.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(receiver.total_packets, 4)
        self.assertEqual(sum(receiver.invalid_reasons.values()), 2)
        self.assertEqual(receiver.unknown_ids[222], 1)
        self.assertEqual(receiver.packet_types[16], 1)
        self.assertIn("F1 2026 TELEMETRY DETECTED", output.getvalue())
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", port))
