"""Receive raw UDP datagrams and report connection statistics."""

from collections import Counter
import socket
import threading
import time


class UDPReceiver:
    """Single-use receiver; no packet format assumptions or decoding."""

    def __init__(self, host: str = "0.0.0.0", port: int = 20777) -> None:
        self.host = host
        self.port = port
        self.total_packets = 0
        self.packet_sizes: Counter[int] = Counter()
        self.source: tuple[str, int] | None = None
        self.last_packet_at: float | None = None
        self.report_elapsed = 1.0
        # Optional live-state coalescing. Subclasses with an expensive decoded
        # state pipeline can opt in so the UDP socket is drained before stale
        # high-rate frames accumulate in the kernel receive buffer.
        self.coalesce_live_udp = False
        self.coalesce_packet_ids = frozenset()
        self.coalesced_packets = 0
        self.coalesced_by_packet_id: Counter[int] = Counter()
        self.max_drain_batch = 512
        self._raw_ingest_active = False

    def process_packet(self, data: bytes, source: tuple[str, int], now: float) -> None:
        """Record traffic for direct callers; live socket ingestion records it earlier."""
        if not self._raw_ingest_active:
            self.source = source
            self.total_packets += 1
            self.packet_sizes[len(data)] += 1
            self.last_packet_at = now

    def raw_datagram_received(self, data: bytes, source: tuple[str, int], now: float) -> None:
        """Record every socket datagram before optional live-state coalescing.

        Subclasses may extend this for lossless recording/capture, but should call
        ``super().raw_datagram_received`` so public UDP counters remain raw-wire
        counters even when decoded high-rate state frames are coalesced.
        """
        self.source = source
        self.total_packets += 1
        self.packet_sizes[len(data)] += 1
        self.last_packet_at = now

    def _coalesce_datagrams(self, batch):
        """Keep every low-rate packet and only the newest duplicate high-rate packet.

        The returned order is the original wire order of the retained datagrams.
        This is deliberately packet-family based: events/session/status/damage and
        other low-rate evidence are never dropped.
        """
        replaceable = self.coalesce_packet_ids
        if not self.coalesce_live_udp or len(batch) < 2 or not replaceable:
            return batch
        latest = {}
        kept = []
        seen_replaceable: Counter[int] = Counter()
        for index, item in enumerate(batch):
            data = item[0]
            packet_id = data[6] if len(data) > 6 else None
            if packet_id in replaceable:
                seen_replaceable[packet_id] += 1
                latest[packet_id] = (index, item)
            else:
                kept.append((index, item))
        kept.extend(latest.values())
        kept.sort(key=lambda row: row[0])
        out = [item for _, item in kept]
        dropped=max(0, len(batch) - len(out))
        self.coalesced_packets += dropped
        for packet_id,count in seen_replaceable.items():
            if count > 1:
                self.coalesced_by_packet_id[packet_id] += count-1
        return out

    def print_status(self, packets_per_second: float, now: float) -> None:
        active = self.last_packet_at is not None and now - self.last_packet_at < 3.0
        print("\n" + "-" * 60)
        print("F1 TELEMETRY DETECTED" if active else "Waiting for F1 telemetry...")
        print(f"Packets/sec : {packets_per_second:.1f}")
        print(f"Total       : {self.total_packets}")
        source = f"{self.source[0]}:{self.source[1]} (last sender)" if self.source else "--"
        print(f"Source      : {source}")
        print("Packet sizes (cumulative):")
        if not self.packet_sizes:
            print("  --")
        for size, count in sorted(self.packet_sizes.items()):
            print(f"  {size:5d} bytes : {count}")
        print(flush=True)

    def run(self, stop_event: threading.Event | None = None) -> None:
        """Run until interrupted/stopped; keep diagnostics off the UDP hot path.

        V0.9.14.0 moves the once-per-second console/status rendering to a
        background reporter. Formatting/terminal I/O can occasionally take many
        milliseconds on Windows; it must never stop recvfrom() from draining the
        game socket.
        """
        stop_event = stop_event if stop_event is not None else threading.Event()
        reporter_stop = threading.Event()
        reporter_error = []

        def status_worker():
            previous_report = time.monotonic()
            previous_total = self.total_packets
            while not reporter_stop.wait(1.0):
                now = time.monotonic()
                elapsed = max(1e-9, now - previous_report)
                self.report_elapsed = elapsed
                try:
                    self.print_status((self.total_packets - previous_total) / elapsed, now)
                except BaseException as error:
                    # Diagnostics must never take telemetry down. Preserve the
                    # first error for optional inspection and keep receiving.
                    if not reporter_error:
                        reporter_error.append(error)
                previous_report = now
                previous_total = self.total_packets

        reporter = threading.Thread(
            target=status_worker, name="race-engineer-status", daemon=True
        )
        reporter.start()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
                except OSError:
                    pass
                sock.bind((self.host, self.port))
                sock.settimeout(0.02)
                print("Waiting for F1 telemetry...", flush=True)
                self._raw_ingest_active = True
                while not stop_event.is_set():
                    try:
                        data, source = sock.recvfrom(65535)
                    except socket.timeout:
                        continue
                    now = time.monotonic()
                    batch = [(data, source, now)]
                    self.raw_datagram_received(data, source, now)

                    # Drain everything already waiting in the kernel before doing
                    # expensive state/coaching work. If processing falls slightly
                    # behind, this exposes the backlog immediately and lets the
                    # latest-state pipeline discard stale duplicates instead of
                    # replaying seconds of obsolete telemetry after the game pauses.
                    if self.coalesce_live_udp:
                        sock.setblocking(False)
                        try:
                            for _ in range(max(0, int(self.max_drain_batch) - 1)):
                                try:
                                    extra, extra_source = sock.recvfrom(65535)
                                except BlockingIOError:
                                    break
                                extra_now = time.monotonic()
                                batch.append((extra, extra_source, extra_now))
                                self.raw_datagram_received(extra, extra_source, extra_now)
                        finally:
                            sock.settimeout(0.02)
                        batch = self._coalesce_datagrams(batch)

                    for packet_data, packet_source, packet_now in batch:
                        self.process_packet(packet_data, packet_source, packet_now)
        finally:
            self._raw_ingest_active = False
            reporter_stop.set()
            reporter.join(timeout=0.25)
