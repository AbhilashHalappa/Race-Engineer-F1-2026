"""V0.2 reporting layered on the working raw UDP receiver."""

from collections import Counter

from .telemetry.header import InvalidHeader, PacketHeader, decode_header
from .telemetry.packet_types import PACKET_TYPES, packet_name
from .udp_receiver import UDPReceiver


class TelemetryReceiver(UDPReceiver):
    def __init__(self, host: str = "0.0.0.0", port: int = 20777, *, show_sizes: bool = False) -> None:
        super().__init__(host, port)
        self.show_sizes = show_sizes
        self.packet_types: Counter[int] = Counter()
        self.previous_types: Counter[int] = Counter()
        self.invalid_reasons: Counter[str] = Counter()
        self.unknown_ids: Counter[int] = Counter()
        self.packet_versions: Counter[int] = Counter()
        self.latest_header: PacketHeader | None = None
        self.telemetry_source: tuple[str, int] | None = None
        self.last_valid_at: float | None = None
        self.last_error = "--"

    def process_packet(self, data: bytes, source: tuple[str, int], now: float) -> None:
        super().process_packet(data, source, now)
        try:
            header = decode_header(data)
        except InvalidHeader as error:
            self.invalid_reasons[error.reason] += 1
            self.last_error = str(error)
            return None
        self.packet_types[header.m_packetId] += 1
        self.packet_versions[header.m_packetVersion] += 1
        if header.m_packetId not in PACKET_TYPES:
            self.unknown_ids[header.m_packetId] += 1
            return None
        self.latest_header = header
        self.telemetry_source = source
        self.last_valid_at = now
        return header

    def print_status(self, packets_per_second: float, now: float) -> None:
        active = self.last_valid_at is not None and now - self.last_valid_at < 3.0
        print("\n" + "=" * 60)
        print("F1 2026 TELEMETRY DETECTED" if active else "Waiting for F1 telemetry (valid 2026 header)...")
        h = self.latest_header
        if h is not None:
            print("Header (last accepted, may be stale):")
            print(f"Format          : {h.m_packetFormat}")
            print(f"Game year       : {h.m_gameYear}")
            print(f"Game version    : {h.m_gameMajorVersion}.{h.m_gameMinorVersion:02d}")
            print(f"Packet version  : {h.m_packetVersion}")
            print(f"Packet ID       : {h.m_packetId} ({packet_name(h.m_packetId)})")
            print(f"Session UID     : {h.m_sessionUID}")
            print(f"Session Time    : {h.m_sessionTime:.3f}")
            print(f"Frame           : {h.m_frameIdentifier}")
            print(f"Overall Frame   : {h.m_overallFrameIdentifier}")
            print(f"Player Car      : {h.m_playerCarIndex}")
            print(f"Secondary Player: {h.m_secondaryPlayerCarIndex} (255 = none)")
            print(f"Telemetry source: {self.telemetry_source[0]}:{self.telemetry_source[1]}")
        print(f"Packets/sec     : {packets_per_second:.1f} (all UDP)")
        print(f"Total packets   : {self.total_packets} (all UDP)")
        if self.source:
            print(f"Last UDP source : {self.source[0]}:{self.source[1]}")
        print("Packet types (since startup):")
        for packet_id in sorted(PACKET_TYPES.keys() | self.packet_types.keys()):
            total = self.packet_types[packet_id]
            rate = (total - self.previous_types[packet_id]) / self.report_elapsed
            print(f"  {packet_name(packet_id):22s}: {total} total / {rate:.1f} pps")
        self.previous_types = self.packet_types.copy()
        print("Unknown/invalid packets:")
        print(f"  Unknown IDs     : {sum(self.unknown_ids.values())}")
        print(f"  Invalid headers : {sum(self.invalid_reasons.values())}")
        for reason, count in sorted(self.invalid_reasons.items()):
            print(f"    {reason}: {count}")
        if self.invalid_reasons:
            print(f"  Last invalid    : {self.last_error}")
        if self.packet_versions:
            print("Observed packet versions: " + ", ".join(f"{version}: {count}" for version, count in sorted(self.packet_versions.items())))
        if self.show_sizes:
            print("Packet sizes (all UDP, cumulative):")
            for size, count in sorted(self.packet_sizes.items()):
                print(f"  {size:5d} bytes : {count}")
        print(flush=True)
