"""Packed 29-byte EA 2026 PacketHeader. See RACE_ENGINEER_STABLE_V2.md for source notes."""

from dataclasses import dataclass
import math
import struct

HEADER_STRUCT = struct.Struct("<HBBBBBQfIIBB")
HEADER_SIZE = HEADER_STRUCT.size
MAX_CARS = 24


@dataclass(frozen=True, slots=True)
class PacketHeader:
    m_packetFormat: int
    m_gameYear: int
    m_gameMajorVersion: int
    m_gameMinorVersion: int
    m_packetVersion: int
    m_packetId: int
    m_sessionUID: int
    m_sessionTime: float
    m_frameIdentifier: int
    m_overallFrameIdentifier: int
    m_playerCarIndex: int
    m_secondaryPlayerCarIndex: int


class InvalidHeader(ValueError):
    """A datagram does not satisfy the supported common header checks."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


def decode_header(data: bytes) -> PacketHeader:
    if len(data) < HEADER_SIZE:
        raise InvalidHeader("Too short", f"Header needs {HEADER_SIZE} bytes; received {len(data)}")
    header = PacketHeader(*HEADER_STRUCT.unpack_from(data))
    if header.m_packetFormat != 2026:
        raise InvalidHeader("Wrong format", f"Expected format 2026; received {header.m_packetFormat}")
    # The Season Pack runs on F1 25: live format-2026 traffic reports year 25.
    # EA's structures comment gives 26 as an example, not an equality rule.
    if header.m_gameYear not in (25, 26):
        raise InvalidHeader("Wrong game year", f"Expected game year 25 or 26; received {header.m_gameYear}")
    if header.m_packetVersion == 0:
        raise InvalidHeader("Packet version zero", "Packet version must be nonzero")
    if not math.isfinite(header.m_sessionTime):
        raise InvalidHeader("Nonfinite session time", "Session time is NaN or infinity")
    if header.m_playerCarIndex >= MAX_CARS:
        raise InvalidHeader("Player car index", f"Player index {header.m_playerCarIndex} is outside 0..23")
    if header.m_secondaryPlayerCarIndex not in (*range(MAX_CARS), 255):
        raise InvalidHeader("Secondary player car index", f"Secondary index {header.m_secondaryPlayerCarIndex} is outside 0..23 or 255")
    # Integer widths are enforced by struct. Do not invent patch-version, UID,
    # timestamp-sign or frame-order restrictions. Flashbacks/reordering are legal.
    return header
