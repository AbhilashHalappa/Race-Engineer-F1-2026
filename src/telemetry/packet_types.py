"""PacketId enumeration from EA's 2026 Season Pack structures attachment."""

PACKET_TYPES = {
    0: "Motion", 1: "Session", 2: "Lap Data", 3: "Event",
    4: "Participants", 5: "Car Setups", 6: "Car Telemetry",
    7: "Car Status", 8: "Final Classification", 9: "Lobby Info",
    10: "Car Damage", 11: "Session History", 12: "Tyre Sets",
    13: "Motion Ex", 14: "Time Trial", 15: "Lap Positions",
    16: "Car Telemetry 2",
}


def packet_name(packet_id: int) -> str:
    return PACKET_TYPES.get(packet_id, f"UNKNOWN({packet_id})")
