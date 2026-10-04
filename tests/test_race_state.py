from dataclasses import asdict
import json
import struct
import unittest

from src.race_state.engine import RaceStateEngine, wheels
from src.race_state.formatter import format_state
from src.telemetry.decoders import decode_packet
from packet_fixtures import packet, car_packet, event


class RaceStateTests(unittest.TestCase):
    def setUp(self):
        self.engine = RaceStateEngine()

    def feed(self, data, at=100):
        return self.engine.update(decode_packet(data), at)

    def test_empty_state_is_unavailable(self):
        self.assertIsNone(self.engine.state.player)
        self.assertIn('N/A', format_state(self.engine.state, 1))
        self.assertIn('Waiting', format_state(self.engine.state, 1))

    def test_nonzero_player_and_secondary_sentinel(self):
        self.feed(car_packet(6, {'m_speed': 287}, player=5))
        self.assertEqual(self.engine.state.player.index, 5)
        self.assertEqual(self.engine.state.player.telemetry.speed_kph, 287)
        self.assertIsNone(self.engine.state.secondary_player_index)

    def test_real_secondary_index(self):
        self.feed(packet(1, secondary=7))
        self.assertEqual(self.engine.state.secondary_player_index, 7)

    def test_player_index_change_uses_other_car(self):
        self.feed(packet(6, {'m_carTelemetryData': {5: {'m_speed': 100}, 7: {'m_speed': 200}}}))
        self.feed(packet(1, player=7, frame=11))
        self.assertEqual(self.engine.state.player.telemetry.speed_kph, 200)

    def test_session_weather_forecast(self):
        self.feed(packet(1, dict(m_trackId=7, m_sessionType=15, m_weather=0,
            m_trackTemperature=34, m_airTemperature=22, m_totalLaps=52,
            m_trackLength=5891, m_sessionTimeLeft=1800, m_sessionDuration=3600,
            m_pitSpeedLimit=80, m_gamePaused=1, m_safetyCarStatus=2,
            m_numWeatherForecastSamples=1, m_weatherForecastSamples={0: dict(
                m_sessionType=15, m_timeOffset=5, m_weather=4, m_trackTemperature=30,
                m_airTemperature=20, m_rainPercentage=80, m_trackTemperatureChange=1)})))
        s = self.engine.state.session
        self.assertEqual((s.track.name, s.session_type.name, s.weather.name), ('Silverstone', 'Race', 'Clear'))
        self.assertEqual((s.time_left_s, s.duration_s, s.pit_speed_limit_kph), (1800, 3600, 80))
        self.assertTrue(s.paused)
        self.assertEqual(s.forecast[0].rain_percent, 80)
        self.assertEqual(s.forecast[0].track_temperature_change.name, 'Down')

    def test_lap_position_times_pit_and_warnings(self):
        self.feed(car_packet(2, dict(m_resultStatus=2, m_driverStatus=4, m_carPosition=6,
            m_currentLapNum=8, m_currentLapTimeInMS=61500, m_lastLapTimeInMS=90000,
            m_sector=1, m_sector1TimeMinutesPart=1, m_sector1TimeMSPart=250,
            m_sector2TimeMSPart=23000, m_pitStatus=2, m_numPitStops=1,
            m_pitLaneTimerActive=1, m_pitLaneTimeInLaneInMS=12345, m_pitStopTimerInMS=2400,
            m_penalties=5, m_totalWarnings=3, m_cornerCuttingWarnings=2,
            m_gridPosition=9, m_currentLapInvalid=1)))
        l = self.engine.state.player.lap
        self.assertEqual((l.position, l.current_lap, l.sector), (6, 8, 2))
        self.assertEqual((l.current_lap_time_s, l.previous_lap_time_s, l.sector1_time_s), (61.5, 90, 60.25))
        self.assertEqual((l.pit_lane_time_s, l.pit_stop_time_s, l.pit_stops), (12.345, 2.4, 1))
        self.assertEqual((l.penalties_s, l.warnings, l.grid_position), (5, 3, 9))
        self.assertFalse(l.lap_valid)
        self.assertEqual(l.pit_status.name, 'In pit area')

    def test_fuel_and_ers_no_strategy_or_percentage(self):
        self.feed(car_packet(7, dict(m_fuelInTank=42.5, m_fuelCapacity=110,
            m_fuelRemainingLaps=-.5, m_fuelMix=1, m_ersStoreEnergy=3200000,
            m_ersDeployMode=3, m_ersHarvestedThisLapMGUK=123000,
            m_ersHarvestedThisLapMGUH=0, m_ersHarvestLimitPerLap=8500000,
            m_ersDeployedThisLap=240000)))
        p = self.engine.state.player
        self.assertEqual((p.fuel.remaining_mass, p.fuel.remaining_laps), (42.5, -.5))
        self.assertEqual(p.energy.store_j, 3200000)
        self.assertEqual(p.energy.deploy_mode.name, 'Boost')
        self.assertEqual(p.energy.harvest_limit_j, 8500000)
        self.assertEqual(p.energy.deployed_this_lap_j, 240000)

    def test_wheel_order(self):
        w = wheels((10, 20, 30, 40))
        self.assertEqual((w.FL, w.FR, w.RL, w.RR), (30, 40, 10, 20))

    def test_tyre_temperatures_pressure_wear_and_damage(self):
        self.feed(car_packet(6, dict(m_tyresSurfaceTemperature=[80, 81, 82, 83],
            m_tyresInnerTemperature=[90, 91, 92, 93], m_tyresPressure=[21, 22, 23, 24])))
        self.feed(car_packet(10, dict(m_tyresWear=[1, 2, 3, 4], m_tyresDamage=[5, 6, 7, 8],
            m_frontLeftWingDamage=12, m_frontRightWingDamage=34, m_floorDamage=56,
            m_engineICEWear=78, m_drsFault=1)))
        p = self.engine.state.player
        self.assertEqual((p.tyres.surface_temperature_c.FL, p.tyres.inner_temperature_c.FR), (82, 93))
        self.assertEqual((p.tyres.pressure_psi.RL, p.tyres.wear_percent.FL, p.tyres.damage_percent.RR), (21, 3, 6))
        self.assertEqual((p.damage.front_left_wing_percent, p.damage.floor_percent), (12, 56))
        self.assertEqual(p.damage.engine_wear_percent['ICE'], 78)
        self.assertTrue(p.damage.drs_fault)
        self.assertIsNone(p.tyres.punctured)

    def test_overtake_active_aero_independent_from_ers(self):
        self.feed(car_packet(16, dict(m_activeAeroMode=1, m_activeAeroAvailable=1,
            m_activeAeroActivationDistance=100, m_overtakeAvailable=1,
            m_overtakeActive=0, m_overtakeActivationDistance=250, m_2026Regulations=1)))
        self.feed(car_packet(7, dict(m_ersDeployMode=3)))
        a = self.engine.state.player.aero
        self.assertEqual(a.active_aero_mode.name, 'Straight mode')
        self.assertTrue(a.overtake_available)
        self.assertFalse(a.overtake_active)
        self.assertEqual(a.overtake_activation_distance_m, 250)
        self.assertTrue(a.regulations_2026)

    def test_tyre_set_car_index_and_undefined_fitted_value(self):
        self.feed(packet(12, dict(m_carIdx=6, m_fittedIdx=1)))
        self.assertEqual(self.engine.state.player.tyres.sets, ())
        self.feed(packet(12, dict(m_carIdx=5, m_fittedIdx=255,
            m_tyreSetData={0: dict(m_actualTyreCompound=16, m_visualTyreCompound=16,
                m_wear=12, m_available=1, m_recommendedSession=15, m_lapDeltaTime=-1500)})))
        t = self.engine.state.player.tyres
        self.assertIsNone(t.fitted_set_index)
        self.assertEqual(t.fitted_set_index_raw, 255)
        self.assertEqual(t.sets[0].actual_compound.name, 'C5')
        self.assertEqual(t.sets[0].lap_delta_s, -1.5)

    def test_participants_count_bounds_field(self):
        self.feed(packet(4, dict(m_numActiveCars=2, m_participants={0: {'m_name': 'Alice'},
            1: {'m_name': 'Bob'}, 10: {'m_name': 'Unused'}}), player=1))
        self.assertEqual(set(self.engine.state.field), {0, 1})
        self.assertEqual(self.engine.state.player.identity.name, 'Bob')
        self.feed(packet(4, dict(m_numActiveCars=0), frame=11))
        self.assertEqual(self.engine.state.field, {})
        self.assertIsNone(self.engine.state.player)

    def test_packets_before_participants_are_reconciled(self):
        self.feed(packet(2, {'m_lapData': {0: {'m_resultStatus':2, 'm_carPosition':1},
            5: {'m_resultStatus':2, 'm_carPosition':2}}}))
        self.assertEqual(self.engine.state.field, {})
        self.feed(car_packet(4, {'m_name': 'Player', 'm_teamId': 484}, frame=9))
        self.assertEqual(self.engine.state.field[0].lap.position, 1)
        self.assertEqual(self.engine.state.player.identity.team.name, "McLaren '26")
        self.assertEqual(self.engine.state.player.lap.position, 2)

    def test_neighbours_and_official_deltas(self):
        self.feed(packet(4, {'m_numActiveCars': 8}))
        self.feed(packet(2, {'m_lapData': {
            5: dict(m_resultStatus=2, m_carPosition=3, m_deltaToCarInFrontMinutesPart=1, m_deltaToCarInFrontMSPart=250),
            7: dict(m_resultStatus=2, m_carPosition=2),
            2: dict(m_resultStatus=2, m_carPosition=4, m_deltaToCarInFrontMSPart=1250)}}))
        s = self.engine.state
        self.assertEqual((s.ahead_index, s.behind_index), (7, 2))
        self.assertEqual(s.player.lap.gap_to_car_in_front_s, 60.25)
        self.assertEqual(s.gap_behind_s, 1.25)

    def test_session_uid_reset_and_late_previous_session(self):
        self.feed(car_packet(6, {'m_speed': 200}))
        self.feed(packet(1, {'m_trackId':7}, uid=222, frame=1))
        self.assertEqual(self.engine.state.session.uid, 222)
        self.assertIsNone(self.engine.state.player.telemetry.speed_kph)
        self.assertEqual(self.engine.state.events, ())
        self.assertFalse(self.feed(car_packet(6, {'m_speed': 300}, uid=111, frame=99)))
        self.assertEqual(self.engine.state.session.uid, 222)

    def test_out_of_order_per_category(self):
        self.feed(car_packet(6, {'m_speed':200}, frame=20))
        self.assertFalse(self.feed(car_packet(6, {'m_speed':100}, frame=19)))
        self.feed(car_packet(7, {'m_fuelInTank':40}, frame=10))
        p = self.engine.state.player
        self.assertEqual((p.telemetry.speed_kph, p.fuel.remaining_mass), (200, 40))

    def test_flashback_frame_and_time_may_decrease(self):
        self.feed(car_packet(6, {'m_speed':200}, frame=20, m_sessionTime=30))
        self.feed(car_packet(6, {'m_speed':100}, frame=21, m_frameIdentifier=5, m_sessionTime=10))
        self.assertEqual(self.engine.state.player.telemetry.speed_kph, 100)

    def test_frame_wrap(self):
        self.feed(car_packet(6, {'m_speed':200}, frame=0xffffffff))
        self.assertTrue(self.feed(car_packet(6, {'m_speed':100}, frame=0)))

    def test_freshness_independent_and_stale_display(self):
        self.feed(car_packet(6, {'m_speed':200}), at=100)
        self.feed(car_packet(7, {'m_fuelInTank':40}), at=107)
        p = self.engine.state.player
        self.assertEqual(p.updated['telemetry'].age(107), 7)
        self.assertIn('telemetry: 7.0s STALE', format_state(self.engine.state, 107))

    def test_unknown_enums_booleans(self):
        self.feed(packet(1, {'m_weather':99, 'm_trackId':99}))
        self.feed(car_packet(16, {'m_activeAeroMode':27, 'm_overtakeAvailable':27}))
        self.assertEqual(self.engine.state.session.track.name, 'UNKNOWN(99)')
        a = self.engine.state.player.aero
        self.assertEqual(a.active_aero_mode.name, 'UNKNOWN(27)')
        self.assertIsNone(a.overtake_available)
        self.assertEqual(a.raw_flags['m_overtakeAvailable'], 27)

    def test_nonfinite_values_are_unavailable(self):
        self.feed(car_packet(7, {'m_fuelInTank':float('nan'), 'm_ersStoreEnergy':float('inf')}))
        self.assertIsNone(self.engine.state.player.fuel.remaining_mass)
        self.assertIsNone(self.engine.state.player.energy.store_j)
        json.dumps(asdict(self.engine.state), allow_nan=False)

    def test_event_history_bounded_unknown_and_session_ended(self):
        self.feed(event('SSTA'))
        self.assertFalse(self.engine.state.session.ended)
        for frame in range(11, 51):
            self.feed(event('ZZZZ', frame=frame))
        self.assertEqual(len(self.engine.state.events), 32)
        self.assertEqual(self.engine.state.events[-1].name, 'UNKNOWN(ZZZZ)')
        self.feed(event('SEND', frame=51))
        self.assertTrue(self.engine.state.session.ended)

    def test_multiple_events_same_frame(self):
        self.feed(event('SSTA'))
        self.feed(event('CHQF'))
        self.assertEqual(len(self.engine.state.events), 2)

    def test_nonfinite_event_remains_json_safe(self):
        self.feed(event('FTLP', struct.pack('<Bf', 5, float('nan'))))
        self.assertIsNone(self.engine.state.events[-1].details['lapTime'])
        json.dumps(asdict(self.engine.state), allow_nan=False)

class ZeroSessionUidRegressionTests(unittest.TestCase):
    def test_zero_uid_results_packet_does_not_reset_active_session(self):
        engine = RaceStateEngine()
        active = decode_packet(packet(1, dict(m_sessionType=18), uid=123456, frame=10))
        self.assertTrue(engine.update(active, 1.0))
        self.assertEqual(engine.state.session.uid, 123456)
        self.assertEqual(engine.state.session.session_type.name, 'Time Trial')
        # F1 26 can emit UID 0 packets on results/menu screens. They must not
        # replace the just-finished active session or wipe measured performance.
        zero = decode_packet(packet(1, dict(m_sessionType=0), uid=0, frame=11))
        self.assertFalse(engine.update(zero, 2.0))
        self.assertEqual(engine.state.session.uid, 123456)
        self.assertEqual(engine.state.session.session_type.name, 'Time Trial')
