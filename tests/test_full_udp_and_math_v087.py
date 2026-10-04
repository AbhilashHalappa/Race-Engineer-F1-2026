import struct, unittest
from src.telemetry.decoders import decode_packet, PACKET_SIZES
from src.race_state.engine import RaceStateEngine
from src.deterministic_math import snapshot
from src.voice_commands import parse_intent, VoiceIntent

HEADER=struct.Struct('<HBBBBBQfIIBB')
def zero_packet(pid, uid=1, frame=1, player=0):
    n=PACKET_SIZES[pid]
    return HEADER.pack(2026,25,1,0,1,pid,uid,1.0,frame,frame,player,255)+bytes(n-29)

class FullCoverageTests(unittest.TestCase):
    def test_all_17_packet_ids_have_exact_sizes(self):
        self.assertEqual(set(PACKET_SIZES),set(range(17)))
        expected={0:1325,1:926,2:1399,3:45,4:1470,5:1233,6:1448,7:1445,8:1134,9:1062,10:1133,11:1460,12:231,13:273,14:104,15:1231,16:269}
        self.assertEqual(PACKET_SIZES,expected)
    def test_new_packet_bodies_decode(self):
        for pid in (0,5,8,9,11,13,14,15):
            with self.subTest(pid=pid):
                self.assertIsNotNone(decode_packet(zero_packet(pid)).body)
    def test_extended_packets_are_retained(self):
        e=RaceStateEngine()
        for i,pid in enumerate((0,5,8,9,11,13,14,15),1):
            e.update(decode_packet(zero_packet(pid,frame=i)),float(i))
        self.assertEqual(set(e.state.extended),{'motion','setups','final','lobby','history','motionex','timetrial','lappos'})
    def test_radio_math_intents(self):
        self.assertEqual(parse_intent('what is my brake bias'),VoiceIntent.BRAKE_BIAS)
        self.assertEqual(parse_intent('how many laps left'),VoiceIntent.LAPS_REMAINING)
        self.assertEqual(parse_intent('what are my g forces'),VoiceIntent.G_FORCE)
        self.assertEqual(parse_intent('wheel slip'),VoiceIntent.WHEEL_SLIP)
