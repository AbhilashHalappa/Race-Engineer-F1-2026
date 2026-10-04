import struct
import unittest

from src.telemetry.binary import MalformedPacket, UnsupportedPacket
from src.telemetry.decoders import decode_packet, PACKET_SIZES
from src.telemetry.events import EVENTS
from src.telemetry import layouts
from packet_fixtures import REFERENCE, ROOTS, packet, car_packet, event


class DecoderTests(unittest.TestCase):
    def test_every_field_matches_official_reference(self):
        for name, reference in REFERENCE.items():
            if name == 'PacketHeader':
                continue
            layout = getattr(layouts, name + '_LAYOUT')
            offset = 29 if name in ROOTS.values() else 0
            for field_name, codec, count, array in layout.fields:
                with self.subTest(record=name, field=field_name):
                    expected = reference['fields'][field_name]
                    self.assertEqual(offset, expected['offset'])
                    if isinstance(codec, str):
                        expected_format = f"{expected['count']}s" if expected['type'] == 'c' else expected['type'] * expected['count']
                        self.assertEqual(codec * count, expected_format)
                        offset += struct.calcsize('<' + codec) * count
                    else:
                        self.assertEqual(codec.record_type.__name__, expected['type'])
                        self.assertEqual(count, expected['count'])
                        offset += codec.size * count
            self.assertEqual(offset, reference['size'])

    def test_all_layout_sizes_match_independent_reference(self):
        for packet_id, name in ROOTS.items():
            with self.subTest(packet_id=packet_id):
                self.assertEqual(REFERENCE[name]['size'], PACKET_SIZES[packet_id])
                self.assertEqual(getattr(layouts, name + '_LAYOUT').size + 29, PACKET_SIZES[packet_id])

    def test_session_and_forecast(self):
        b = decode_packet(packet(1, dict(m_trackId=7, m_sessionType=15, m_weather=3,
            m_trackTemperature=34, m_airTemperature=22, m_trackLength=5891,
            m_totalLaps=52, m_numWeatherForecastSamples=1,
            m_weatherForecastSamples={0: dict(m_sessionType=15, m_timeOffset=5,
                m_weather=4, m_trackTemperature=30, m_trackTemperatureChange=1,
                m_airTemperature=19, m_airTemperatureChange=1, m_rainPercentage=85)},
            m_recurringRewindPrompt=1))).body
        self.assertEqual((b.m_trackId, b.m_trackLength, b.m_totalLaps), (7, 5891, 52))
        self.assertEqual(b.m_weatherForecastSamples[0].m_rainPercentage, 85)
        self.assertEqual(b.m_recurringRewindPrompt, 1)

    def test_lap_fields_and_signed_distance(self):
        b = decode_packet(car_packet(2, dict(m_lastLapTimeInMS=90001,
            m_currentLapTimeInMS=65002, m_sector1TimeMinutesPart=1, m_sector1TimeMSPart=500,
            m_deltaToCarInFrontMinutesPart=1, m_deltaToCarInFrontMSPart=2300,
            m_lapDistance=-12.5, m_gridPosition=8, m_driverStatus=4, m_resultStatus=2,
            m_pitStatus=2, m_speedTrapFastestLap=255))).body.m_lapData[5]
        self.assertEqual((b.m_lastLapTimeInMS, b.m_currentLapTimeInMS), (90001, 65002))
        self.assertEqual((b.m_gridPosition, b.m_driverStatus), (8, 4))
        self.assertEqual(b.m_lapDistance, -12.5)
        self.assertEqual(b.m_speedTrapFastestLap, 255)

    def test_participants_utf8_and_count(self):
        b = decode_packet(car_packet(4, dict(m_name='Jörg Driver', m_driverId=65535,
            m_networkId=400, m_teamId=486, m_aiControlled=0))).body
        self.assertEqual(b.m_numActiveCars, 6)
        self.assertEqual(b.m_participants[5].m_name, 'Jörg Driver')
        self.assertEqual(b.m_participants[5].m_teamId, 486)
        self.assertEqual(b.m_participants[5].m_driverId, 65535)

    def test_malformed_utf8_and_control_names(self):
        b = decode_packet(car_packet(4, dict(m_name=b'A\xff\x1b\nB\0ignored'))).body
        self.assertEqual(b.m_participants[5].m_name, 'A\ufffd\ufffd\ufffdB')

    def test_telemetry_signed_gear_and_arrays(self):
        b = decode_packet(car_packet(6, dict(m_speed=287, m_gear=-1, m_throttle=.75,
            m_tyresPressure=[21, 22, 23, 24], m_engineTemperature=105,
            m_tyresSurfaceTemperature=[80, 81, 82, 83]))).body.m_carTelemetryData[5]
        self.assertEqual((b.m_speed, b.m_gear, b.m_engineTemperature), (287, -1, 105))
        self.assertEqual(b.m_throttle, .75)
        self.assertEqual(b.m_tyresPressure, (21, 22, 23, 24))

    def test_status_fuel_and_energy(self):
        b = decode_packet(car_packet(7, dict(m_fuelInTank=42.5, m_fuelCapacity=110,
            m_fuelRemainingLaps=-.5, m_ersStoreEnergy=3200000, m_ersDeployMode=3,
            m_ersHarvestLimitPerLap=8500000, m_networkPaused=1))).body.m_carStatusData[5]
        self.assertEqual((b.m_fuelInTank, b.m_fuelRemainingLaps), (42.5, -.5))
        self.assertEqual((b.m_ersStoreEnergy, b.m_ersHarvestLimitPerLap), (3200000, 8500000))
        self.assertEqual(b.m_networkPaused, 1)

    def test_damage(self):
        b = decode_packet(car_packet(10, dict(m_tyresWear=[1.5, 2.5, 3.5, 4.5],
            m_frontLeftWingDamage=12, m_engineMGUKWear=33, m_engineSeized=1))).body.m_carDamageData[5]
        self.assertEqual(b.m_tyresWear, (1.5, 2.5, 3.5, 4.5))
        self.assertEqual((b.m_frontLeftWingDamage, b.m_engineMGUKWear, b.m_engineSeized), (12, 33, 1))

    def test_tyre_sets(self):
        b = decode_packet(packet(12, dict(m_carIdx=5, m_fittedIdx=19,
            m_tyreSetData={19: dict(m_actualTyreCompound=8, m_available=1,
                m_lapDeltaTime=-1500, m_fitted=1)}))).body
        self.assertEqual((b.m_carIdx, b.m_fittedIdx, len(b.m_tyreSetData)), (5, 19, 20))
        self.assertEqual(b.m_tyreSetData[19].m_lapDeltaTime, -1500)

    def test_telemetry2_all_fields(self):
        b = decode_packet(car_packet(16, dict(m_activeAeroMode=1, m_activeAeroAvailable=1,
            m_activeAeroActivationDistance=123, m_overtakeAvailable=1, m_overtakeActive=0,
            m_overtakeActivationDistance=456, m_2026Regulations=1, m_drivingWrongWay=0))).body.m_carTelemetry2Data[5]
        self.assertEqual((b.m_activeAeroMode, b.m_activeAeroActivationDistance, b.m_overtakeActivationDistance), (1, 123, 456))
        self.assertEqual((b.m_overtakeAvailable, b.m_overtakeActive, b.m_2026Regulations), (1, 0, 1))

    def test_each_body_requires_exact_length(self):
        for packet_id in PACKET_SIZES:
            data = packet(packet_id)
            for bad in (data[:29], data[:-1], data + b'\0'):
                with self.subTest(packet_id=packet_id, size=len(bad)), self.assertRaises(MalformedPacket):
                    decode_packet(bad)

    def test_count_bounds(self):
        cases = [(1, {'m_numWeatherForecastSamples':65}), (1, {'m_numMarshalZones':22}),
            (1, {'m_numActiveAeroZonesFull':9}), (1, {'m_numActiveAeroZonesPartial':9}),
            (1, {'m_numDRSZones':5}), (1, {'m_numSessionsInWeekend':13}),
            (4, {'m_numActiveCars':25}), (12, {'m_carIdx':24})]
        for packet_id, body in cases:
            with self.subTest(body=body), self.assertRaises(MalformedPacket):
                decode_packet(packet(packet_id, body))

    def test_unsupported_versions_and_packets(self):
        with self.assertRaises(UnsupportedPacket):
            decode_packet(packet(6, version=2))
        with self.assertRaises(UnsupportedPacket):
            decode_packet(packet(17))

    def test_unknown_enum_is_not_malformed(self):
        b = decode_packet(packet(1, dict(m_weather=99, m_sessionType=99))).body
        self.assertEqual(b.m_weather, 99)

    def test_all_event_codes_decode(self):
        for code in EVENTS:
            with self.subTest(code=code):
                self.assertEqual(decode_packet(event(code)).body.code, code)

    def test_2026_season8_control_event_codes(self):
        expected = {
            'PMEN': 'Partial Mode Enabled',
            'PMDI': 'Partial Mode Disabled',
            'OVEN': 'Overtake Enabled',
            'OVDI': 'Overtake Disabled',
        }
        for code, name in expected.items():
            with self.subTest(code=code):
                body = decode_packet(event(code)).body
                self.assertEqual(body.name, name)
                self.assertEqual(body.details, {'reason': 0} if code == 'PMEN' else {})

    def test_event_union_offsets(self):
        b = decode_packet(event('FTLP', struct.pack('<Bf', 5, 91.25))).body
        self.assertEqual(b.details, dict(vehicleIdx=5, lapTime=91.25))
        b = decode_packet(event('OVTK', bytes([5, 7]))).body
        self.assertEqual(b.details, dict(overtakingVehicleIdx=5, beingOvertakenVehicleIdx=7))
        b = decode_packet(event('COLL', bytes([5, 7, 2]))).body
        self.assertEqual(b.details['severity'], 2)

    def test_unknown_event(self):
        b = decode_packet(event('ZZZZ')).body
        self.assertEqual(b.name, 'UNKNOWN(ZZZZ)')
        self.assertEqual(b.details, {})

    def test_unknown_event_controls_are_escaped(self):
        data = bytearray(event('ZZZZ'))
        data[29:33] = b'\x1b[0m'
        self.assertNotIn('\x1b', decode_packet(bytes(data)).body.name)
