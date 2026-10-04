import contextlib
import io
import socket
import threading
import time
import unittest
from unittest.mock import patch

from src.main import main
from src.udp_receiver import UDPReceiver


class ReceiverTests(unittest.TestCase):
    def test_local_packets_and_stop(self):
        # Reserve an ephemeral port so this test does not compete with the game.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        receiver = UDPReceiver("127.0.0.1", port)
        stop = threading.Event()
        ready = threading.Event()
        errors = []

        class Output(io.StringIO):
            def write(self, value):
                if "Waiting for F1 telemetry" in value:
                    ready.set()
                return super().write(value)

        def receive():
            try:
                receiver.run(stop)
            except BaseException as error:
                errors.append(error)

        output = Output()
        with contextlib.redirect_stdout(output):
            worker = threading.Thread(target=receive, daemon=True)
            worker.start()
            try:
                self.assertTrue(ready.wait(3), errors)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.bind(("127.0.0.1", 0))
                    source = sender.getsockname()
                    for payload in (b"a", b"abc", b"abc", b""):
                        sender.sendto(payload, ("127.0.0.1", port))
                    deadline = time.monotonic() + 3
                    while "F1 TELEMETRY DETECTED" not in output.getvalue() and time.monotonic() < deadline:
                        time.sleep(0.02)
            finally:
                stop.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(receiver.total_packets, 4)
        self.assertEqual(receiver.packet_sizes, {0: 1, 1: 1, 3: 2})
        self.assertEqual(receiver.source, source)
        self.assertIn("F1 TELEMETRY DETECTED", output.getvalue())
        self.assertIn("Packets/sec :", output.getvalue())
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", port))

    def test_idle_status_preserves_totals(self):
        receiver = UDPReceiver()
        receiver.last_packet_at = 10.0
        receiver.total_packets = 7
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            receiver.print_status(0.0, 13.1)
        self.assertIn("Waiting for F1 telemetry", output.getvalue())
        self.assertIn("Total       : 7", output.getvalue())

    def test_ctrl_c_exits_successfully(self):
        with patch("src.main.UDPReceiver.run", side_effect=KeyboardInterrupt), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 0)
        self.assertIn("Stopped. UDP socket closed.", output.getvalue())

    def test_socket_error_exits_with_diagnostic(self):
        with patch("src.main.UDPReceiver.run", side_effect=OSError("port occupied")), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(), 1)
        self.assertIn("UDP socket error: port occupied", error.getvalue())


if __name__ == "__main__":
    unittest.main()


def test_live_coalescing_keeps_low_rate_and_latest_high_rate_order():
    receiver = UDPReceiver()
    receiver.coalesce_live_udp = True
    receiver.coalesce_packet_ids = frozenset({0, 2, 6})

    def packet(pid, tag):
        data = bytearray(8)
        data[6] = pid
        data[7] = tag
        return (bytes(data), ("127.0.0.1", 20777), float(tag))

    batch = [
        packet(0, 1),   # replaceable, stale
        packet(3, 2),   # event, preserve
        packet(6, 3),   # replaceable, stale
        packet(0, 4),   # newest motion
        packet(7, 5),   # status, preserve
        packet(6, 6),   # newest telemetry
    ]
    out = receiver._coalesce_datagrams(batch)
    assert [(x[0][6], x[0][7]) for x in out] == [(3, 2), (0, 4), (7, 5), (6, 6)]
    assert receiver.coalesced_packets == 2
