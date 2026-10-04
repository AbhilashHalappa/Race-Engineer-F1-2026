"""Independent byte fixtures from verified EA declarations, not app layouts."""

import json
from pathlib import Path
import struct

REFERENCE = json.loads((Path(__file__).parent / 'fixtures/2026-layout-reference.json').read_text())
ROOTS = {1: 'PacketSessionData', 2: 'PacketLapData', 4: 'PacketParticipantsData',
         6: 'PacketCarTelemetryData', 7: 'PacketCarStatusData', 10: 'PacketCarDamageData',
         12: 'PacketTyreSetsData', 16: 'PacketCarTelemetry2Data'}


def put(data, record, offset, values):
    for name, value in values.items():
        f = REFERENCE[record]['fields'][name]
        at, kind, count = offset + f['offset'], f['type'], f['count']
        if kind in REFERENCE:
            if count == 1:
                put(data, kind, at, value)
            else:
                for index, changes in value.items():
                    put(data, kind, at + index * REFERENCE[kind]['size'], changes)
        elif kind == 'c':
            text = value.encode('utf-8') if isinstance(value, str) else value
            data[at:at+count] = text[:count].ljust(count, b'\0')
        else:
            struct.pack_into('<' + str(count) + kind, data, at, *(value if count > 1 else [value]))


def packet(packet_id, body=None, *, player=5, secondary=255, uid=111, frame=10, version=1, **header):
    root = ROOTS.get(packet_id)
    data = bytearray(REFERENCE[root]['size'] if root else 45)
    values = dict(m_packetFormat=2026, m_gameYear=25, m_gameMajorVersion=1,
        m_gameMinorVersion=25, m_packetVersion=version, m_packetId=packet_id,
        m_sessionUID=uid, m_sessionTime=12.5, m_frameIdentifier=frame,
        m_overallFrameIdentifier=frame, m_playerCarIndex=player, m_secondaryPlayerCarIndex=secondary)
    values.update(header)
    put(data, 'PacketHeader', 0, values)
    if body:
        put(data, root, 0, body)
    return bytes(data)


def event(code, payload=b'', **kwargs):
    data = bytearray(packet(3, **kwargs))
    data[29:33] = code.encode('ascii')
    data[33:33+len(payload)] = payload
    return bytes(data)


def car_packet(packet_id, changes, index=5, **kwargs):
    array = {2: 'm_lapData', 4: 'm_participants', 6: 'm_carTelemetryData',
             7: 'm_carStatusData', 10: 'm_carDamageData', 16: 'm_carTelemetry2Data'}[packet_id]
    body = {array: {index: changes}}
    if packet_id == 4:
        body['m_numActiveCars'] = index + 1
    return packet(packet_id, body, **kwargs)
