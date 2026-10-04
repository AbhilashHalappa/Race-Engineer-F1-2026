"""Validate complete selected bodies before passing typed packets to state."""

from dataclasses import dataclass

from .binary import MalformedPacket, UnsupportedPacket
from .header import PacketHeader, decode_header
from . import layouts as L
from .events import EventData, decode_event
from . import full_layouts as F

LAYOUTS = {**F.LAYOUTS,
    1: L.PacketSessionData_LAYOUT, 2: L.PacketLapData_LAYOUT,
    4: L.PacketParticipantsData_LAYOUT, 6: L.PacketCarTelemetryData_LAYOUT,
    7: L.PacketCarStatusData_LAYOUT, 10: L.PacketCarDamageData_LAYOUT,
    12: L.PacketTyreSetsData_LAYOUT, 16: L.PacketCarTelemetry2Data_LAYOUT,
}
PACKET_SIZES = {**F.PACKET_SIZES, 1: 926, 2: 1399, 3: 45, 4: 1470, 6: 1448,
                7: 1445, 10: 1133, 12: 231, 16: 269}
for packet_id, layout in LAYOUTS.items():
    assert layout.size + 29 == PACKET_SIZES[packet_id], (packet_id, layout.size)

Body = object  # all 17 official packet bodies are decoded


@dataclass(frozen=True, slots=True)
class DecodedPacket:
    header: PacketHeader
    body: Body


def decode_packet(data: bytes, header: PacketHeader | None = None) -> DecodedPacket:
    header = decode_header(data) if header is None else header
    packet_id = header.m_packetId
    if packet_id not in PACKET_SIZES:
        raise UnsupportedPacket(f'ID {packet_id}: identification only')
    if header.m_packetVersion != 1:
        raise UnsupportedPacket(f'ID {packet_id}: body version {header.m_packetVersion} unsupported')
    expected = PACKET_SIZES[packet_id]
    if len(data) != expected:
        raise MalformedPacket(f'ID {packet_id}: expected {expected} bytes, received {len(data)}')
    body = decode_event(data) if packet_id == 3 else LAYOUTS[packet_id].decode(data)
    if packet_id == 1:
        for name, maximum in [('m_numMarshalZones', 21), ('m_numWeatherForecastSamples', 64),
                              ('m_numSessionsInWeekend', 12), ('m_numActiveAeroZonesFull', 8),
                              ('m_numActiveAeroZonesPartial', 8), ('m_numDRSZones', 4)]:
            if getattr(body, name) > maximum:
                raise MalformedPacket(f'{name} exceeds {maximum}')
    elif packet_id == 4:
        if body.m_numActiveCars > 24:
            raise MalformedPacket('Participant count exceeds 24')
        if any(p.m_numColours > 4 for p in body.m_participants[:body.m_numActiveCars]):
            raise MalformedPacket('Participant colour count exceeds 4')
    elif packet_id == 12 and body.m_carIdx >= 24:
        raise MalformedPacket('Tyre set car index exceeds 23')
    elif packet_id == 8 and body.m_numCars > 24:
        raise MalformedPacket('Final classification car count exceeds 24')
    elif packet_id == 9 and body.m_numPlayers > 24:
        raise MalformedPacket('Lobby player count exceeds 24')
    elif packet_id == 11 and (body.m_carIdx >= 24 or body.m_numLaps > 100 or body.m_numTyreStints > 8):
        raise MalformedPacket('Session history count/index out of range')
    elif packet_id == 15 and body.m_numLaps > 50:
        raise MalformedPacket('Lap positions lap count exceeds 50')
    return DecodedPacket(header, body)
