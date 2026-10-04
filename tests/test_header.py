import math
import struct
import unittest

from src.telemetry.header import HEADER_SIZE, InvalidHeader, decode_header
from src.telemetry.packet_types import PACKET_TYPES, packet_name


def make_header(**changes):
    values = dict(format=2026, year=26, major=1, minor=23, version=1,
                  packet_id=6, uid=0x0102030405060708, session_time=12.5,
                  frame=0x10203040, overall_frame=0x50607080, player=23, secondary=255)
    values.update(changes)
    return struct.pack("<HBBBBBQfIIBB", *values.values())


class HeaderTests(unittest.TestCase):
    def test_independent_literal_header(self):
        # Literal wire bytes independently fix every offset and byte order.
        data = bytes.fromhex("ea07 1a 01 17 01 06 0807060504030201 00004841 40302010 80706050 17 ff")
        h = decode_header(data)
        self.assertEqual(HEADER_SIZE, 29)
        self.assertEqual((h.m_packetFormat, h.m_gameYear), (2026, 26))
        self.assertEqual((h.m_gameMajorVersion, h.m_gameMinorVersion), (1, 23))
        self.assertEqual((h.m_packetVersion, h.m_packetId), (1, 6))
        self.assertEqual(h.m_sessionUID, 0x0102030405060708)
        self.assertEqual(h.m_sessionTime, 12.5)
        self.assertEqual((h.m_frameIdentifier, h.m_overallFrameIdentifier), (0x10203040, 0x50607080))
        self.assertEqual((h.m_playerCarIndex, h.m_secondaryPlayerCarIndex), (23, 255))

    def test_official_packet_mapping(self):
        expected = ["Motion", "Session", "Lap Data", "Event", "Participants",
                    "Car Setups", "Car Telemetry", "Car Status", "Final Classification",
                    "Lobby Info", "Car Damage", "Session History", "Tyre Sets",
                    "Motion Ex", "Time Trial", "Lap Positions", "Car Telemetry 2"]
        self.assertEqual(PACKET_TYPES, dict(enumerate(expected)))

    def test_unknown_id(self):
        h = decode_header(make_header(packet_id=255))
        self.assertEqual(packet_name(h.m_packetId), "UNKNOWN(255)")

    def test_every_short_length(self):
        for length in range(29):
            with self.subTest(length=length), self.assertRaisesRegex(InvalidHeader, "needs 29"):
                decode_header(make_header()[:length])

    def test_wrong_format(self):
        with self.assertRaisesRegex(InvalidHeader, "received 2025"):
            decode_header(make_header(format=2025))

    def test_wrong_year(self):
        with self.assertRaisesRegex(InvalidHeader, "game year 25 or 26"):
            decode_header(make_header(year=24))

    def test_f1_25_season_pack_game_year(self):
        h = decode_header(make_header(year=25))
        self.assertEqual((h.m_packetFormat, h.m_gameYear), (2026, 25))

    def test_player_indices(self):
        for index in range(24):
            self.assertEqual(decode_header(make_header(player=index)).m_playerCarIndex, index)
        for index in (24, 254, 255):
            with self.assertRaises(InvalidHeader):
                decode_header(make_header(player=index))

    def test_secondary_indices(self):
        for index in (*range(24), 255):
            self.assertEqual(decode_header(make_header(secondary=index)).m_secondaryPlayerCarIndex, index)
        for index in (24, 254):
            with self.assertRaises(InvalidHeader):
                decode_header(make_header(secondary=index))

    def test_frame_and_uid_unsigned_limits(self):
        h = decode_header(make_header(uid=2**64-1, frame=2**32-1, overall_frame=0))
        self.assertEqual(h.m_sessionUID, 2**64-1)
        self.assertEqual(h.m_frameIdentifier, 2**32-1)
        self.assertEqual(h.m_overallFrameIdentifier, 0)
        self.assertEqual(decode_header(make_header(uid=0)).m_sessionUID, 0)

    def test_session_time_finite(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(InvalidHeader):
                decode_header(make_header(session_time=value))
        self.assertEqual(decode_header(make_header(session_time=-1)).m_sessionTime, -1)

    def test_versions(self):
        with self.assertRaises(InvalidHeader):
            decode_header(make_header(version=0))
        h = decode_header(make_header(major=255, minor=255, version=2))
        self.assertEqual((h.m_gameMajorVersion, h.m_gameMinorVersion, h.m_packetVersion), (255, 255, 2))

    def test_payload_length_does_not_identify_type(self):
        for size in (0, 1, 100, 3000):
            self.assertEqual(decode_header(make_header(packet_id=16) + b"x" * size).m_packetId, 16)
