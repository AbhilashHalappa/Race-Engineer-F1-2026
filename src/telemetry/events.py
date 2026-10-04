"""EA EventDataDetails: fixed 12-byte union after the four-byte event code."""

from dataclasses import dataclass
import struct

EVENTS = {
    'SSTA': ('Session Started', '', ()), 'SEND': ('Session Ended', '', ()),
    'FTLP': ('Fastest Lap', 'Bf', ('vehicleIdx', 'lapTime')),
    'RTMT': ('Retirement', 'BB', ('vehicleIdx', 'reason')),
    'DRSE': ('DRS Enabled', '', ()), 'DRSD': ('DRS Disabled', 'B', ('reason',)),
    'TMPT': ('Team Mate in Pits', 'B', ('vehicleIdx',)),
    'CHQF': ('Chequered Flag', '', ()), 'RCWN': ('Race Winner', 'B', ('vehicleIdx',)),
    'PENA': ('Penalty', '7B', ('penaltyType', 'infringementType', 'vehicleIdx', 'otherVehicleIdx', 'time', 'lapNum', 'placesGained')),
    'SPTP': ('Speed Trap', 'BfBBBf', ('vehicleIdx', 'speed', 'isOverallFastestInSession', 'isDriverFastestInSession', 'fastestVehicleIdxInSession', 'fastestSpeedInSession')),
    'STLG': ('Start Lights', 'B', ('numLights',)), 'LGOT': ('Lights Out', '', ()),
    'DTSV': ('Drive Through Served', 'B', ('vehicleIdx',)),
    'SGSV': ('Stop Go Served', 'Bf', ('vehicleIdx', 'stopTime')),
    'FLBK': ('Flashback', 'If', ('flashbackFrameIdentifier', 'flashbackSessionTime')),
    'BUTN': ('Button Status', 'I', ('buttonStatus',)), 'RDFL': ('Red Flag', '', ()),
    'OVTK': ('Overtake', 'BB', ('overtakingVehicleIdx', 'beingOvertakenVehicleIdx')),
    'SCAR': ('Safety Car', 'BB', ('safetyCarType', 'eventType')),
    'COLL': ('Collision', 'BBB', ('vehicle1Idx', 'vehicle2Idx', 'severity')),
    'PMEN': ('Partial Mode Enabled', 'B', ('reason',)), 'PMDI': ('Partial Mode Disabled', '', ()),
    'OVEN': ('Overtake Enabled', '', ()), 'OVDI': ('Overtake Disabled', '', ()),
}


@dataclass(frozen=True, slots=True)
class EventData:
    code: str
    name: str
    details: dict[str, int | float]
    raw_code: bytes


def decode_event(data: bytes) -> EventData:
    raw = data[29:33]
    code = ''.join(chr(c) if 32 <= c <= 126 else f'\\x{c:02x}' for c in raw)
    name, fmt, fields = EVENTS.get(code, (f'UNKNOWN({code})', '', ()))
    values = struct.unpack_from('<' + fmt, data, 33)
    return EventData(code, name, dict(zip(fields, values)), raw)
