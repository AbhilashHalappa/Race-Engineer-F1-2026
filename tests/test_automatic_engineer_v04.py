import unittest

from src.engineer import AutomaticEngineer, Priority
from src.race_state.models import CarState, Forecast, MarshalZoneState, RaceEvent, RaceState, Wheels
from src.telemetry.enums import EnumValue


def ev(raw, name):
    return EnumValue(raw, name)


def state(uid=1):
    s = RaceState(player_index=0)
    s.session.uid = uid
    s.session.session_time_s = 10.0
    s.session.weather = ev(0, 'Clear')
    s.session.safety_car = ev(0, 'None')
    c = CarState(0)
    c.lap.current_lap = 1
    c.lap.position = 10
    c.lap.pit_status = ev(0, 'None')
    c.lap.driver_status = ev(4, 'On track')
    c.lap.pit_stops = 0
    c.lap.penalties_s = 0
    c.lap.unserved_drive_through = 0
    c.lap.unserved_stop_go = 0
    c.fuel.remaining_laps = 5.0
    c.tyres.fitted_set_index = 8
    c.tyres.age_laps = 0
    c.tyres.visual_compound = ev(18, 'Soft')
    c.tyres.wear_percent = Wheels(0, 0, 0, 0)
    c.tyres.damage_percent = Wheels(0, 0, 0, 0)
    c.damage.front_left_wing_percent = 0
    c.damage.front_right_wing_percent = 0
    c.damage.rear_wing_percent = 0
    c.damage.floor_percent = 0
    c.damage.engine_percent = 0
    c.damage.gearbox_percent = 0
    c.damage.drs_fault = False
    c.damage.ers_fault = False
    c.damage.engine_blown = False
    c.damage.engine_seized = False
    c.aero.driving_wrong_way = False
    c.aero.overtake_available = False
    c.aero.overtake_active = False
    s.player = c
    s.field = {0: c}
    return s


class AutomaticEngineerTests(unittest.TestCase):
    def setUp(self):
        self.e = AutomaticEngineer()
        self.s = state()
        self.e.evaluate(self.s, 1.0)
        self.assertEqual(self.e.drain(), ())

    def messages(self, now=2.0):
        self.e.evaluate(self.s, now)
        return self.e.drain()

    def test_initial_state_is_baseline_not_message_burst(self):
        e = AutomaticEngineer()
        s = state()
        s.player.damage.front_left_wing_percent = 90
        s.player.tyres.wear_percent = Wheels(90, 0, 0, 0)
        e.evaluate(s, 1)
        self.assertEqual(e.drain(), ())

    def test_lap_transition(self):
        self.s.player.lap.current_lap = 2
        self.s.player.lap.previous_lap_time_s = 91.234
        m = self.messages()[0]
        self.assertEqual(m.priority, Priority.INFORMATION)
        self.assertIn('Lap 2', m.text)
        self.assertIn('91.234', m.text)

    def test_position_change_is_disabled_by_default(self):
        self.s.player.lap.position = 8
        self.assertEqual(self.messages(), ())

    def test_position_change_can_be_enabled(self):
        e = AutomaticEngineer(position_updates=True)
        s = state()
        e.evaluate(s, 1.0)
        e.drain()
        s.player.lap.position = 8
        e.evaluate(s, 2.0)
        self.assertIn('Position 8', e.drain()[0].text)

    def test_pit_entry_and_exit(self):
        self.s.player.lap.pit_status = ev(1, 'Pitting')
        self.assertEqual(self.messages()[0].priority, Priority.STRATEGY)
        self.s.player.lap.pit_status = ev(0, 'None')
        self.assertIn('Pit exit', self.messages(20)[0].text)


    def test_real_capture_pit_sequence_survives_intermediate_updates(self):
        # Observed live V0.3 sequence: In lap/Pitting -> Out lap/Pitting -> Out lap/None.
        self.s.player.lap.driver_status = ev(2, 'In lap')
        self.s.player.lap.pit_status = ev(1, 'Pitting')
        self.assertIn('Pit lane', self.messages(2)[0].text)
        self.assertEqual(self.messages(2.1), ())  # unrelated packet/state refresh
        self.s.player.tyres.fitted_set_index = 9
        self.assertIn('New Soft tyre set', self.messages(3)[0].text)
        self.s.player.lap.current_lap = 2
        self.s.player.lap.driver_status = ev(3, 'Out lap')
        self.assertTrue(any('Lap 2' in m.text for m in self.messages(4)))
        self.s.player.lap.pit_status = ev(0, 'None')
        self.s.player.lap.pit_stops = 1
        self.assertTrue(any('Pit exit' in m.text for m in self.messages(5)))

    def test_weather_first_becoming_available_is_silent(self):
        e = AutomaticEngineer()
        s = state()
        s.session.weather = None
        e.evaluate(s, 1)
        s.session.weather = ev(1, 'Light cloud')
        e.evaluate(s, 2)
        self.assertEqual(e.drain(), ())
        s.session.weather = ev(3, 'Light rain')
        e.evaluate(s, 5)
        self.assertTrue(any('Light rain' in m.text for m in e.drain()))


    def test_startup_weather_transition_is_silent_baseline(self):
        # Live telemetry can briefly expose Clear before the first current Session
        # packet reports the actual weather. This startup correction is not a change.
        self.s.session.weather = ev(1, 'Light cloud')
        self.assertEqual(self.messages(2), ())
        self.assertEqual(self.messages(3.5), ())
        # A real later transition must still be announced.
        self.s.session.weather = ev(3, 'Light rain')
        msgs = self.messages(5)
        self.assertTrue(any('Light rain' in m.text for m in msgs))

    def test_major_accident_reports_additional_damage_components(self):
        self.s.player.damage.diffuser_percent = 90
        self.s.player.damage.sidepod_percent = 82
        self.s.player.damage.brakes_percent = Wheels(10, 80, 5, 5)
        msgs = self.messages()
        keys = {m.key for m in msgs}
        self.assertIn('diffuser:75', keys)
        self.assertIn('sidepod:75', keys)
        self.assertIn('brakes:75', keys)
        self.assertTrue(all(m.priority == Priority.CRITICAL for m in msgs))

    def test_tyre_set_change(self):
        self.s.player.tyres.fitted_set_index = 9
        m = self.messages()[0]
        self.assertIn('New Soft tyre set', m.text)
        self.assertEqual(m.priority, Priority.STRATEGY)

    def test_time_penalty(self):
        self.s.player.lap.penalties_s = 5
        m = self.messages()[0]
        self.assertEqual(m.priority, Priority.CRITICAL)
        self.assertIn('5 seconds', m.text)

    def test_drive_through(self):
        self.s.player.lap.unserved_drive_through = 1
        self.assertIn('Drive-through', self.messages()[0].text)

    def test_safety_car(self):
        self.s.session.safety_car = ev(1, 'Full')
        self.assertIn('Safety Car deployed', self.messages()[0].text)

    def test_weather_change(self):
        self.s.session.weather = ev(3, 'Light rain')
        self.assertIn('Light rain', self.messages(5)[0].text)

    def test_game_forecast_threshold(self):
        self.s.session.forecast = (Forecast(ev(15, 'Race'), 5, ev(0, 'Clear'), 30, ev(0, 'Up'), 20, ev(0, 'Up'), 10),)
        self.messages()  # establish 10% forecast after initial no-forecast baseline
        self.s.session.forecast = (Forecast(ev(15, 'Race'), 5, ev(2, 'Overcast'), 29, ev(0, 'Up'), 20, ev(0, 'Up'), 55),)
        m = self.messages(3)[0]
        self.assertEqual(m.priority, Priority.STRATEGY)
        self.assertIn('55%', m.text)

    def test_low_fuel_uses_mfd_value(self):
        self.s.player.fuel.remaining_laps = .9
        m = self.messages()[0]
        self.assertIn('MFD estimate', m.text)
        self.assertEqual(m.priority, Priority.STRATEGY)

    def test_tyre_wear_threshold_and_worst_wheel(self):
        self.s.player.tyres.wear_percent = Wheels(12, 51, 10, 8)
        msgs = self.messages()
        self.assertEqual([m.key for m in msgs], ['wear:50'])
        self.assertTrue(any('FR at 51%' in m.text for m in msgs))

    def test_front_wing_escalation_only_once_per_threshold(self):
        self.s.player.damage.front_right_wing_percent = 55
        msgs = self.messages()
        self.assertEqual({m.key for m in msgs}, {'front_wing:50'})
        self.assertEqual(self.messages(3), ())
        self.s.player.damage.front_right_wing_percent = 85
        msgs = self.messages(4)
        self.assertIn('front_wing:80', [m.key for m in msgs])
        self.assertIn('pit:deterministic_plan', [m.key for m in msgs])
        self.assertEqual(msgs[0].priority, Priority.CRITICAL)

    def test_fault_and_wrong_way(self):
        self.s.player.damage.ers_fault = True
        self.s.player.aero.driving_wrong_way = True
        msgs = self.messages()
        self.assertEqual(len(msgs), 2)
        self.assertTrue(all(m.priority == Priority.CRITICAL for m in msgs))

    def test_overtake_available_transition(self):
        self.s.player.aero.overtake_available = True
        self.assertIn('Overtake is available', self.messages()[0].text)

    def test_new_session_resets_without_old_session_messages(self):
        self.s.player.lap.position = 5
        self.messages()
        self.s = state(uid=2)
        self.s.player.lap.position = 20
        self.e.evaluate(self.s, 3)
        self.assertEqual(self.e.drain(), ())

    def test_priority_order_critical_before_strategy_before_information(self):
        self.s.player.lap.penalties_s = 5
        self.s.player.tyres.fitted_set_index = 9
        self.s.player.lap.current_lap = 2
        msgs = self.messages()
        self.assertEqual([m.priority for m in msgs], [Priority.CRITICAL, Priority.STRATEGY, Priority.INFORMATION])


    def test_2026_s_mode_assist_and_independent_disable(self):
        self.s.player.aero.regulations_2026 = True
        self.s.player.aero.active_aero_available = True
        self.s.player.aero.active_aero_mode = ev(0, 'Corner mode')
        msgs = self.messages(2.0)
        self.assertTrue(any(m.key == 'assist:s_mode' and m.text == 'S Mode.' for m in msgs))
        # V0.9.14.4: one call per availability/mode opportunity; continuous
        # availability must not create repeated S-Mode chatter.
        self.assertFalse(any(m.key == 'assist:s_mode' for m in self.messages(3.0)))
        self.assertFalse(any(m.key == 'assist:s_mode' for m in self.messages(8.1)))
        self.s.player.aero.active_aero_available = False
        self.messages(8.2)
        self.s.player.aero.active_aero_available = True
        # V0.9.14.5 suppresses repeated automatic S-Mode reminders within one lap.
        self.assertFalse(any(m.key == 'assist:s_mode' for m in self.messages(14.3)))
        self.s.player.lap.current_lap = (self.s.player.lap.current_lap or 1) + 1
        self.assertTrue(any(m.key == 'assist:s_mode' for m in self.messages(14.4)))

        e = AutomaticEngineer(drs_s_mode_assist=False)
        s = state(); e.evaluate(s, 1.0)
        s.player.aero.regulations_2026 = True
        s.player.aero.active_aero_available = True
        s.player.aero.active_aero_mode = ev(0, 'Corner mode')
        e.evaluate(s, 2.0)
        self.assertFalse(any(m.key == 'assist:s_mode' for m in e.drain()))

    def test_ers_assist_overtake_reminder_and_independent_disable(self):
        self.s.player.aero.overtake_available = True
        self.s.player.aero.overtake_active = False
        msgs = self.messages(2.0)
        self.assertTrue(any(m.key == 'assist:ers' and m.text == 'Overtake available.' for m in msgs))
        self.s.player.aero.overtake_active = True
        self.assertFalse(any(m.key == 'assist:ers' for m in self.messages(9.0)))

        e = AutomaticEngineer(ers_assist=False)
        s = state(); e.evaluate(s, 1.0)
        s.player.aero.overtake_available = True
        e.evaluate(s, 2.0)
        self.assertFalse(any(m.key == 'assist:ers' for m in e.drain()))

    def test_legacy_drs_assist(self):
        self.s.player.aero.regulations_2026 = False
        self.s.player.aero.drs_allowed = True
        self.s.player.telemetry.drs = False
        msgs = self.messages(2.0)
        self.assertTrue(any(m.key == 'assist:drs' and m.text == 'DRS.' for m in msgs))

    def add_event(self, code, details, now=2.0):
        self.s.events = (*self.s.events, RaceEvent(code, code, details, now, now))
        return self.messages(now)

    def test_detailed_player_time_penalty_reason(self):
        msgs = self.add_event('PENA', dict(penaltyType=4, infringementType=17,
            vehicleIdx=0, otherVehicleIdx=255, time=5, lapNum=1, placesGained=0))
        self.assertEqual(len(msgs), 1)
        self.assertIn('5-second time penalty', msgs[0].text)
        self.assertIn('speeding in the pit lane', msgs[0].text)

    def test_penalty_for_other_driver_is_not_announced(self):
        self.assertEqual(self.add_event('PENA', dict(penaltyType=4, infringementType=17,
            vehicleIdx=7, otherVehicleIdx=255, time=5, lapNum=1, placesGained=0)), ())

    def test_drs_disabled_reason_and_overtake_control(self):
        msgs = self.add_event('DRSD', {'reason': 0})
        self.assertIn('wet track', msgs[0].text)
        msgs = self.add_event('OVEN', {}, 3.0)
        self.assertIn('Overtake mode enabled', msgs[0].text)

    def test_red_flag_and_safety_car_event(self):
        self.assertIn('Red flag', self.add_event('RDFL', {})[0].text)
        self.assertIn('Safety Car deployed', self.add_event('SCAR', {'safetyCarType': 1, 'eventType': 0}, 3.0)[0].text)

    def test_collision_resolves_opponent_name(self):
        other = CarState(3)
        other.identity.name = 'Norris'
        self.s.field[3] = other
        msgs = self.add_event('COLL', {'vehicle1Idx': 0, 'vehicle2Idx': 3, 'severity': 2})
        self.assertIn('High collision with Norris', msgs[0].text)

    def test_local_yellow_then_green_flag(self):
        self.s.session.track_length_m = 1000
        self.s.player.lap.lap_distance_m = 100
        self.s.session.marshal_zones = (MarshalZoneState(0.0, ev(0, 'None')),)
        self.messages(2.0)
        self.s.session.marshal_zones = (MarshalZoneState(0.0, ev(3, 'Yellow')),)
        self.assertIn('Yellow flag', self.messages(3.0)[0].text)
        self.s.session.marshal_zones = (MarshalZoneState(0.0, ev(1, 'Green')),)
        self.assertIn('Green flag', self.messages(4.0)[0].text)

    def test_yellow_in_next_marshal_zone_is_announced_once(self):
        self.s.session.track_length_m = 1000
        self.s.player.lap.lap_distance_m = 100
        self.s.session.marshal_zones = (
            MarshalZoneState(0.0, ev(1, 'Green')),
            MarshalZoneState(0.25, ev(1, 'Green')),
            MarshalZoneState(0.50, ev(1, 'Green')),
            MarshalZoneState(0.75, ev(1, 'Green')),
        )
        self.messages(2.0)
        zones = list(self.s.session.marshal_zones)
        zones[1] = MarshalZoneState(0.25, ev(3, 'Yellow'))
        self.s.session.marshal_zones = tuple(zones)
        msgs = self.messages(3.0)
        self.assertEqual(len(msgs), 1)
        self.assertIn('Yellow flag ahead', msgs[0].text)
        # Entering the already-announced yellow zone must not repeat it.
        self.s.player.lap.lap_distance_m = 300
        self.assertEqual(self.messages(4.0), ())

    def test_distant_yellow_is_not_announced_until_it_is_next(self):
        self.s.session.track_length_m = 1000
        self.s.player.lap.lap_distance_m = 100
        self.s.session.marshal_zones = (
            MarshalZoneState(0.0, ev(1, 'Green')),
            MarshalZoneState(0.25, ev(1, 'Green')),
            MarshalZoneState(0.50, ev(1, 'Green')),
            MarshalZoneState(0.75, ev(1, 'Green')),
        )
        self.messages(2.0)
        zones = list(self.s.session.marshal_zones)
        zones[2] = MarshalZoneState(0.50, ev(3, 'Yellow'))
        self.s.session.marshal_zones = tuple(zones)
        self.assertEqual(self.messages(3.0), ())
        # Once the car reaches zone 1, zone 2 becomes the immediately upcoming zone.
        self.s.player.lap.lap_distance_m = 300
        msgs = self.messages(4.0)
        self.assertEqual(len(msgs), 1)
        self.assertIn('Yellow flag ahead', msgs[0].text)

    def test_green_only_after_relevant_yellow_clears(self):
        self.s.session.track_length_m = 1000
        self.s.player.lap.lap_distance_m = 100
        self.s.session.marshal_zones = (
            MarshalZoneState(0.0, ev(1, 'Green')),
            MarshalZoneState(0.25, ev(3, 'Yellow')),
            MarshalZoneState(0.50, ev(1, 'Green')),
        )
        # Establish the existing yellow-ahead condition as baseline.
        self.messages(2.0)
        # Unrelated far-zone changes do not produce green/yellow chatter.
        zones = list(self.s.session.marshal_zones)
        zones[2] = MarshalZoneState(0.50, ev(0, 'None'))
        self.s.session.marshal_zones = tuple(zones)
        self.assertEqual(self.messages(3.0), ())
        # Clear the relevant next-zone yellow: exactly one green call.
        zones = list(self.s.session.marshal_zones)
        zones[1] = MarshalZoneState(0.25, ev(1, 'Green'))
        self.s.session.marshal_zones = tuple(zones)
        msgs = self.messages(4.0)
        self.assertEqual(len(msgs), 1)
        self.assertIn('Green flag', msgs[0].text)

    def test_penalty_served_events(self):
        self.assertIn('Drive-through penalty served', self.add_event('DTSV', {'vehicleIdx': 0})[0].text)
        self.assertIn('Stop-go penalty served', self.add_event('SGSV', {'vehicleIdx': 0, 'stopTime': 5.2}, 3.0)[0].text)

    def test_partial_mode_reason(self):
        self.assertIn('wet track', self.add_event('PMEN', {'reason': 0})[0].text)
        self.assertIn('Partial mode disabled', self.add_event('PMDI', {}, 3.0)[0].text)


if __name__ == '__main__':
    unittest.main()
