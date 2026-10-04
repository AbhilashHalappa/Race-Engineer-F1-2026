"""Single-threaded deterministic state updates from already decoded packets."""

from collections import deque
import math

from ..telemetry.decoders import DecodedPacket
from ..telemetry import enums as E
from ..measured_performance import MeasuredPerformanceRecorder
from .models import (AeroOvertakeState, CarState, CarTelemetry, DamageState,
    EnergyState, Forecast, Freshness, FuelState, Identity, LapState, MarshalZoneState, RaceEvent,
    RaceState, SessionState, TyreSet, Wheels, MeasuredLapFact)

CATEGORIES = {0:'motion', 1: 'session', 2: 'lap', 3: 'events', 4: 'participants', 5:'setups',
              6: 'telemetry', 7: 'status', 8:'final', 9:'lobby', 10: 'damage', 11:'history', 12: 'tyres', 13:'motionex', 14:'timetrial', 15:'lappos', 16: 'telemetry2'}
ARRAYS = {'lap': 'm_lapData', 'telemetry': 'm_carTelemetryData',
          'status': 'm_carStatusData', 'damage': 'm_carDamageData',
          'telemetry2': 'm_carTelemetry2Data'}
# Only LapData needs the whole field continuously (positions/gaps/neighbours).
# High-rate car telemetry/status/damage/aero packets are consumed only for the
# local player(s), so rebuilding 20-24 opponent CarState objects every frame is
# pure latency. Keep primary + secondary player state current and leave opponent
# identities/lap state authoritative from Participants/LapData.
PLAYER_ONLY_ARRAY_CATEGORIES = {'telemetry', 'status', 'damage', 'telemetry2'}


def finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def wheels(raw) -> Wheels:
    """EA order RL, RR, FL, FR -> explicitly named consumer fields."""
    values = [finite(v) if isinstance(v, float) else v for v in raw]
    return Wheels(FL=values[2], FR=values[3], RL=values[0], RR=values[1])


def older(new: int, old: int) -> bool:
    """Unsigned serial comparison, including uint32 wrap."""
    return ((new - old) & 0xffffffff) >= 0x80000000


class RaceStateEngine:
    def __init__(self) -> None:
        self.state = RaceState()
        self._retired_uids = deque(maxlen=64)
        self._frames: dict[tuple, int] = {}
        self._cache: dict[str, tuple] = {}
        self._tyres: dict[int, tuple] = {}
        self._cars: dict[int, CarState] = {}
        self._context_frame: int | None = None
        self.out_of_order = 0
        self._lap_baseline = None
        self._last_strategy_gap_sample_t = None
        self._strategy_gap_context = None
        self.performance = MeasuredPerformanceRecorder()

    def update(self, packet: DecodedPacket, received_at: float) -> bool:
        h, body = packet.header, packet.body
        uid = h.m_sessionUID
        # F1 26 can emit menu/results packets with sessionUID == 0 after an
        # active session. They are not a new driving session. Resetting on those
        # packets destroys the completed-lap analysis collected moments earlier.
        # Ignore zero-UID packets at the race-state layer; a real F1 session uses
        # its non-zero unique session identifier.
        if uid == 0:
            return False
        if uid != self.state.session.uid:
            if uid in self._retired_uids:
                self.out_of_order += 1
                return False
            if self.state.session.uid is not None:
                self._retired_uids.append(self.state.session.uid)
            self.state = RaceState(session=SessionState(uid=uid))
            self._frames.clear()
            self._cache.clear()
            self._tyres.clear()
            self._cars.clear()
            self._context_frame = None
            self._lap_baseline = None
            self._last_strategy_gap_sample_t = None
            self._strategy_gap_context = None
            self.performance.reset()
        self.state.session.packet_format = int(getattr(h, "m_packetFormat", 0) or 0) or None
        gy = getattr(h, "m_gameYear", None)
        self.state.session.game_year = (2000 + int(gy) if gy is not None and int(gy) < 100 else int(gy)) if gy is not None else None
        major = getattr(h, "m_gameMajorVersion", None); minor = getattr(h, "m_gameMinorVersion", None)
        self.state.session.game_version = f"{int(major)}.{int(minor or 0)}" if major is not None else None
        category = CATEGORIES[h.m_packetId]
        key = (category, body.m_carIdx) if category in ('tyres','history') else (category,)
        frame = h.m_overallFrameIdentifier
        previous = self._frames.get(key)
        if previous is not None and (older(frame, previous) or
                (frame == previous and category != 'events')):
            self.out_of_order += 1
            return False
        self._frames[key] = frame
        stamp = Freshness(received_at, frame, h.m_sessionTime)
        if self._context_frame is None or not older(frame, self._context_frame):
            self._context_frame = frame
            self.state.player_index = h.m_playerCarIndex
            self.state.secondary_player_index = None if h.m_secondaryPlayerCarIndex == 255 else h.m_secondaryPlayerCarIndex
            self.state.session.session_time_s = h.m_sessionTime
        self.state.updated[category] = stamp
        if category == 'session':
            self._session(body)
        elif category == 'events':
            # Button-status packets are frequent state, not useful event history.
            if body.code != 'BUTN':
                details = {key: finite(v) if isinstance(v, float) else v for key, v in body.details.items()}
                event = RaceEvent(body.code, body.name, details, h.m_sessionTime, received_at)
                self.state.events = (*self.state.events[-31:], event)
            if body.code == 'SEND':
                self.state.session.ended = True
            elif body.code == 'SSTA':
                self.state.session.ended = False
        elif category == 'tyres':
            self._tyres[body.m_carIdx] = (body, stamp)
        else:
            self._cache[category] = (body, stamp)
            if category in ('motion','setups','final','lobby','history','motionex','timetrial','lappos'):
                self.state.extended[category] = body
            if category == 'participants':
                self.state.active_car_count = body.m_numActiveCars
        self._sync_cars(category, body.m_carIdx if category == 'tyres' else None)

        # V0.9.14.0: do not run lap/performance sampling for packet families that
        # cannot change any of its inputs. These helpers used to run on every UDP
        # datagram, including session/participants/damage/setup traffic, causing
        # repeated same-distance work in the real-time path.
        if category in {'lap', 'status', 'damage', 'tyres'}:
            self._observe_completed_lap()
        if category == 'lap':
            self._observe_strategy_gap_sample()
        if category in {'lap', 'telemetry', 'status', 'motion', 'motionex', 'telemetry2',
                        'history', 'events', 'final'}:
            self.performance.observe(self.state)
        return True



    def _observe_strategy_gap_sample(self) -> None:
        """Keep a conservative 1 Hz rolling gap-ahead history for live strategy radio.

        A gap trend is only meaningful while the same race context is continuous.
        Reset the window on car-ahead changes, position swaps, pit-state changes,
        timer discontinuities, or teleport-like gap jumps. This deliberately prefers
        "trend unavailable" over broadcasting a mathematically valid but racing-
        meaningless number after an overtake, pit transition, spin, or replay seek.
        """
        c = self.state.player
        now = self.state.session.session_time_s
        gap = c.lap.gap_to_car_in_front_s if c is not None else None
        ahead = self.state.ahead_index
        if c is None or now is None or gap is None or ahead is None:
            return
        try:
            now_f, gap_f = float(now), float(gap)
        except (TypeError, ValueError):
            return
        if not math.isfinite(now_f) or not math.isfinite(gap_f) or gap_f <= 0.0:
            return

        pit_name = getattr(c.lap.pit_status, 'name', None) if c.lap.pit_status is not None else None
        context = (int(ahead), c.lap.position, pit_name, bool(c.lap.pit_lane_timer_active))
        samples = list(self.state.extended.get('_strategy_gap_samples', ()))

        # Overtakes/position changes and pit entry/exit invalidate the old opponent
        # relationship even if the same driver later becomes the car ahead again.
        if self._strategy_gap_context is not None and context != self._strategy_gap_context:
            samples = []
            self._last_strategy_gap_sample_t = None
        self._strategy_gap_context = context

        if self._last_strategy_gap_sample_t is not None:
            dt_last = now_f - float(self._last_strategy_gap_sample_t)
            if dt_last < 0.0 or dt_last > 5.0:
                samples = []
                self._last_strategy_gap_sample_t = None
            elif dt_last < 1.0:
                return

        if samples:
            prev_t, prev_gap, prev_ahead = samples[-1]
            dt = now_f - float(prev_t)
            jump = abs(gap_f - float(prev_gap))
            # A >~2 s one-second gap jump is normally a pass, incident, pit-state
            # transition, replay seek, or packet discontinuity—not usable pace trend.
            max_jump = 1.5 + (0.35 * max(dt, 0.0))
            if prev_ahead != int(ahead) or dt <= 0.0 or dt > 5.0 or jump > max_jump:
                samples = []

        self._last_strategy_gap_sample_t = now_f
        samples.append((now_f, gap_f, int(ahead)))
        cutoff = now_f - 30.0
        samples = [x for x in samples if x[0] >= cutoff][-31:]
        self.state.extended['_strategy_gap_samples'] = tuple(samples)

    def _observe_completed_lap(self) -> None:
        """Record only completed, already-observed lap facts; never extrapolate."""
        c = self.state.player
        if c is None or c.lap.current_lap is None:
            return
        lap = c.lap.current_lap
        wear = c.tyres.wear_percent
        pit_name = (getattr(c.lap.pit_status, 'name', None) or '').lower()
        pit_now = bool(c.lap.pit_lane_timer_active) or bool(pit_name and pit_name not in {'none', 'no pit'})
        sc_name = (getattr(self.state.session.safety_car, 'name', None) or '').lower().replace('_', ' ')
        neutral_now = bool(sc_name and sc_name not in {'none', 'no safety car', 'invalid'} and
                           ('safety' in sc_name or 'virtual' in sc_name or 'vsc' in sc_name))
        dmg = c.damage
        wing = max(int(getattr(dmg, 'front_left_wing_percent', 0) or 0),
                   int(getattr(dmg, 'front_right_wing_percent', 0) or 0))
        damage_now = (wing >= 20 or int(getattr(dmg, 'floor_percent', 0) or 0) >= 20 or
                      bool(getattr(dmg, 'engine_blown', False)) or bool(getattr(dmg, 'engine_seized', False)))
        snap = {
            'lap': lap, 'fuel': c.fuel.remaining_mass, 'wear': wear,
            'tyre_set': c.tyres.fitted_set_index,
            'position': c.lap.position, 'gap': c.lap.gap_to_car_in_front_s,
            'pit_lap': pit_now, 'race_control_compromised': neutral_now,
            'damage_compromised': damage_now, 'tyre_set_changed': False,
        }
        if self._lap_baseline is None:
            self._lap_baseline = snap
            return
        old = self._lap_baseline
        if lap == old['lap']:
            # Preserve the earliest known values, but latch any condition observed
            # anywhere during the lap.  Pit/degradation logic must not treat a lap
            # as clean merely because the final packet arrived after the condition
            # cleared.
            for key in ('fuel','wear','tyre_set','position','gap'):
                if old[key] is None and snap[key] is not None:
                    old[key] = snap[key]
            old['pit_lap'] = bool(old.get('pit_lap') or snap['pit_lap'])
            old['race_control_compromised'] = bool(old.get('race_control_compromised') or snap['race_control_compromised'])
            old['damage_compromised'] = bool(old.get('damage_compromised') or snap['damage_compromised'])
            if old.get('tyre_set') is not None and snap.get('tyre_set') is not None and old['tyre_set'] != snap['tyre_set']:
                old['tyre_set_changed'] = True
            return
        if lap == old['lap'] + 1:
            def delta_wheels(a, b):
                if a is None or b is None:
                    return None
                vals=[]
                for k in ('FL','FR','RL','RR'):
                    x,y=getattr(a,k),getattr(b,k)
                    if x is None or y is None: return None
                    vals.append(y-x)
                return Wheels(FL=vals[0],FR=vals[1],RL=vals[2],RR=vals[3])
            fuel = None if old['fuel'] is None or c.fuel.remaining_mass is None else old['fuel']-c.fuel.remaining_mass
            poschg = None if old['position'] is None or c.lap.position is None else old['position']-c.lap.position
            gapchg = None if old['gap'] is None or c.lap.gap_to_car_in_front_s is None else c.lap.gap_to_car_in_front_s-old['gap']
            fact=MeasuredLapFact(
                old['lap'], c.lap.previous_lap_time_s, fuel,
                delta_wheels(old['wear'], c.tyres.wear_percent), old['position'], c.lap.position, poschg,
                old['gap'], c.lap.gap_to_car_in_front_s, gapchg,
                fuel_remaining_end=c.fuel.remaining_mass,
                tyre_wear_end=c.tyres.wear_percent,
                fitted_tyre_set_index=old.get('tyre_set'),
                end_tyre_set_index=c.tyres.fitted_set_index,
                pit_lap=bool(old.get('pit_lap')),
                race_control_compromised=bool(old.get('race_control_compromised')),
                damage_compromised=bool(old.get('damage_compromised')),
                tyre_set_changed=bool(old.get('tyre_set_changed') or
                                      (old.get('tyre_set') is not None and c.tyres.fitted_set_index is not None and
                                       old.get('tyre_set') != c.tyres.fitted_set_index)),
            )
            self.state.measured_laps=(*self.state.measured_laps[-49:], fact)
        self._lap_baseline = snap

    def _session(self, b) -> None:
        s = self.state.session
        s.session_type = E.label(E.SESSION_TYPES, b.m_sessionType)
        s.track = E.label(E.TRACKS, b.m_trackId)
        s.weather = E.label(E.WEATHER, b.m_weather)
        s.track_temperature_c = b.m_trackTemperature
        s.air_temperature_c = b.m_airTemperature
        s.total_laps = b.m_totalLaps
        s.track_length_m = b.m_trackLength
        s.time_left_s, s.duration_s = b.m_sessionTimeLeft, b.m_sessionDuration
        s.pit_speed_limit_kph = b.m_pitSpeedLimit
        s.pit_stop_window_ideal_lap = int(b.m_pitStopWindowIdealLap) if int(b.m_pitStopWindowIdealLap) > 0 else None
        s.pit_stop_window_latest_lap = int(b.m_pitStopWindowLatestLap) if int(b.m_pitStopWindowLatestLap) > 0 else None
        s.safety_car = E.label(E.SAFETY_CAR, b.m_safetyCarStatus)
        s.formula = b.m_formula
        s.network_game = E.flag(b.m_networkGame)
        s.game_mode = b.m_gameMode
        s.rule_set = b.m_ruleSet
        s.equal_car_performance = b.m_equalCarPerformance
        s.low_fuel_mode = b.m_lowFuelMode
        s.car_damage = b.m_carDamage
        s.car_damage_rate = b.m_carDamageRate
        s.corner_cutting_stringency = b.m_cornerCuttingStringency
        s.parc_ferme_rules = E.flag(b.m_parcFermeRules)
        s.safety_car_setting = b.m_safetyCar
        s.red_flags_setting = b.m_redFlags
        # PacketSessionData is the live authority for the player's assist
        # configuration.  Keep every assist field F1 exposes here so downstream
        # lap history never has to infer the current lap from Time Trial PB data.
        s.anti_lock_brakes_assist = int(getattr(b, 'm_antiLockBrakesAssist', 0))
        s.traction_control_assist = int(getattr(b, 'm_tractionControlAssist', 0))
        s.steering_assist = int(getattr(b, 'm_steeringAssist', 0))
        s.braking_assist = int(getattr(b, 'm_brakingAssist', 0))
        s.gearbox_assist = int(getattr(b, 'm_gearboxAssist', 0))
        s.pit_assist = int(getattr(b, 'm_pitAssist', 0))
        s.pit_release_assist = int(getattr(b, 'm_pitReleaseAssist', 0))
        s.ers_assist = int(getattr(b, 'm_ERSAssist', 0))
        s.drs_assist = int(getattr(b, 'm_DRSAssist', 0))
        s.marshal_zones = tuple(MarshalZoneState(f.m_zoneStart, E.label(E.MARSHAL_FLAG, f.m_zoneFlag))
                                for f in b.m_marshalZones[:b.m_numMarshalZones])
        s.paused, s.spectating = E.flag(b.m_gamePaused), E.flag(b.m_isSpectating)
        s.forecast_accuracy = E.label({0: 'Perfect', 1: 'Approximate'}, b.m_forecastAccuracy)
        s.forecast = tuple(Forecast(E.label(E.SESSION_TYPES, f.m_sessionType), f.m_timeOffset,
            E.label(E.WEATHER, f.m_weather), f.m_trackTemperature,
            E.label(E.TEMPERATURE_CHANGE, f.m_trackTemperatureChange), f.m_airTemperature,
            E.label(E.TEMPERATURE_CHANGE, f.m_airTemperatureChange), f.m_rainPercentage)
            for f in b.m_weatherForecastSamples[:b.m_numWeatherForecastSamples])

    def _sync_cars(self, category: str, target_index: int | None = None) -> None:
        """Synchronize only cars affected by the incoming packet category.

        V0.9.13.0 latency pass.  The old implementation walked every active car
        for *every* UDP packet and, on each tyre-set packet, rebuilt tyre-set
        objects for every car that had ever sent a tyre packet.  F1 sends many
        high-rate packet categories, so that unnecessary fan-out dominated the
        state-update cost.

        Array packets (lap/telemetry/status/damage/telemetry2) genuinely carry
        one record per active car and therefore still update all active cars.
        A TyreSets packet belongs to exactly one car and updates only that car.
        Session/events/motion/etc. do not modify CarState and no longer walk the
        field.
        """
        count, player = self.state.active_car_count, self.state.player_index
        if count is not None:
            active_indices = tuple(range(count))
        elif player is not None:
            active_indices = (player,)
        else:
            active_indices = ()

        membership_changed = False

        # Participants is authoritative for active field membership.
        if category == 'participants' and count is not None:
            active_set = set(active_indices)
            for removed in tuple(self._cars):
                if removed not in active_set:
                    del self._cars[removed]
                    membership_changed = True

        def hydrate(index: int) -> CarState:
            nonlocal membership_changed
            car = self._cars.get(index)
            if car is None:
                car = CarState(index)
                self._cars[index] = car
                membership_changed = True
                # A car first seen mid-session needs the latest cached values.
                for cat, cached in self._cache.items():
                    body0, stamp0 = cached
                    if cat == 'participants':
                        if index < len(body0.m_participants):
                            pp = body0.m_participants[index]
                            car.identity = Identity(name=pp.m_name, team=E.label(E.TEAMS, pp.m_teamId),
                                ai_controlled=E.flag(pp.m_aiControlled), race_number=pp.m_raceNumber,
                                telemetry_public=E.flag(pp.m_yourTelemetry), driver_id=pp.m_driverId,
                                team_id=pp.m_teamId, nationality_id=pp.m_nationality, platform_id=pp.m_platform,
                                my_team=E.flag(pp.m_myTeam))
                            car.updated[cat] = stamp0
                    elif cat in ARRAYS:
                        arr = getattr(body0, ARRAYS[cat])
                        if index < len(arr):
                            self._car_update(car, cat, arr[index])
                            car.updated[cat] = stamp0
                tyre_cached = self._tyres.get(index)
                if tyre_cached is not None:
                    tyre_body, tyre_stamp = tyre_cached
                    self._tyre_sets(car, tyre_body)
                    car.updated['tyres'] = tyre_stamp
            return car

        if category == 'participants':
            body, stamp = self._cache.get('participants', (None, None))
            if body is not None:
                for index in active_indices:
                    car = hydrate(index)
                    if index < len(body.m_participants):
                        pp = body.m_participants[index]
                        car.identity = Identity(name=pp.m_name, team=E.label(E.TEAMS, pp.m_teamId),
                            ai_controlled=E.flag(pp.m_aiControlled), race_number=pp.m_raceNumber,
                            telemetry_public=E.flag(pp.m_yourTelemetry), driver_id=pp.m_driverId,
                            team_id=pp.m_teamId, nationality_id=pp.m_nationality, platform_id=pp.m_platform,
                            my_team=E.flag(pp.m_myTeam))
                        car.updated['participants'] = stamp

        elif category in ARRAYS:
            cached = self._cache.get(category)
            if cached is not None:
                body, stamp = cached
                arr = getattr(body, ARRAYS[category])
                if category in PLAYER_ONLY_ARRAY_CATEGORIES:
                    local_indices = []
                    for index in (player, self.state.secondary_player_index):
                        if index is None or index in local_indices:
                            continue
                        if count is None or 0 <= index < count:
                            local_indices.append(index)
                    update_indices = local_indices
                else:
                    update_indices = active_indices
                for index in update_indices:
                    car = hydrate(index)
                    if index < len(arr):
                        self._car_update(car, category, arr[index])
                        car.updated[category] = stamp

        elif category == 'tyres' and target_index is not None:
            # TyreSets packets are per-car. Never rebuild 20 tyre-set objects for
            # unrelated cars just because one car's packet arrived.
            if count is None:
                allowed = player is not None and target_index == player
            else:
                allowed = 0 <= target_index < count
            if allowed:
                car = hydrate(target_index)
                cached = self._tyres.get(target_index)
                if cached is not None:
                    tyre_body, stamp = cached
                    self._tyre_sets(car, tyre_body)
                    car.updated['tyres'] = stamp

        # Header player index can arrive before Participants. Ensure the current
        # player object exists whenever cached car data can hydrate it.
        if player is not None and player not in self._cars and active_indices:
            hydrate(player)

        if membership_changed or category == 'participants':
            self.state.field = dict(self._cars) if count is not None else {}
        self.state.player = self._cars.get(player)

        # Neighbour identities/gaps only depend on lap/position or field/player
        # membership, not on 60 Hz motion/telemetry/status packets.
        if category == 'lap' or membership_changed or category == 'participants':
            self._neighbours()

    def _car_update(self, car: CarState, category: str, b) -> None:
        if category == 'lap':
            result = E.label(E.RESULT_STATUS, b.m_resultStatus)
            if b.m_resultStatus in (0, 1):
                car.lap = LapState(result_status=result)
                return
            car.lap = LapState(
                position=b.m_carPosition or None, current_lap=b.m_currentLapNum or None,
                current_lap_time_s=b.m_currentLapTimeInMS / 1000,
                previous_lap_time_s=b.m_lastLapTimeInMS / 1000 if b.m_lastLapTimeInMS else None,
                sector=b.m_sector + 1 if b.m_sector in (0, 1, 2) else None,
                sector1_time_s=(b.m_sector1TimeMinutesPart * 60 + b.m_sector1TimeMSPart / 1000) or None,
                sector2_time_s=(b.m_sector2TimeMinutesPart * 60 + b.m_sector2TimeMSPart / 1000) or None,
                lap_distance_m=finite(b.m_lapDistance), total_distance_m=finite(b.m_totalDistance),
                lap_valid={0: True, 1: False}.get(b.m_currentLapInvalid),
                pit_status=E.label(E.PIT_STATUS, b.m_pitStatus), pit_stops=b.m_numPitStops,
                pit_lane_timer_active=E.flag(b.m_pitLaneTimerActive),
                pit_lane_time_s=b.m_pitLaneTimeInLaneInMS / 1000 if b.m_pitLaneTimerActive == 1 else None,
                pit_stop_time_s=b.m_pitStopTimerInMS / 1000 if b.m_pitLaneTimerActive == 1 else None,
                pit_stop_should_serve_penalty=E.flag(b.m_pitStopShouldServePen),
                penalties_s=b.m_penalties, warnings=b.m_totalWarnings,
                corner_cutting_warnings=b.m_cornerCuttingWarnings,
                unserved_drive_through=b.m_numUnservedDriveThroughPens,
                unserved_stop_go=b.m_numUnservedStopGoPens,
                grid_position=b.m_gridPosition or None,
                driver_status=E.label(E.DRIVER_STATUS, b.m_driverStatus), result_status=result,
                gap_to_car_in_front_s=(b.m_deltaToCarInFrontMinutesPart * 60 + b.m_deltaToCarInFrontMSPart / 1000) if b.m_carPosition > 1 else None,
                gap_to_leader_s=(b.m_deltaToRaceLeaderMinutesPart * 60 + b.m_deltaToRaceLeaderMSPart / 1000) if b.m_carPosition > 1 else None)
        elif category == 'telemetry':
            car.telemetry = CarTelemetry(b.m_speed, finite(b.m_throttle), finite(b.m_brake),
                b.m_clutch, finite(b.m_steer), b.m_gear, b.m_engineRPM, E.flag(b.m_drs),
                b.m_revLightsPercent, b.m_revLightsBitValue, b.m_engineTemperature, wheels(b.m_brakesTemperature), wheels(b.m_surfaceType))
            car.tyres.surface_temperature_c = wheels(b.m_tyresSurfaceTemperature)
            car.tyres.inner_temperature_c = wheels(b.m_tyresInnerTemperature)
            car.tyres.pressure_psi = wheels(b.m_tyresPressure)
        elif category == 'status':
            car.fuel = FuelState(finite(b.m_fuelInTank), finite(b.m_fuelCapacity),
                                finite(b.m_fuelRemainingLaps), E.label(E.FUEL_MIX, b.m_fuelMix))
            car.energy = EnergyState(finite(b.m_ersStoreEnergy), E.label(E.ERS_MODE, b.m_ersDeployMode),
                finite(b.m_ersHarvestedThisLapMGUK), finite(b.m_ersHarvestedThisLapMGUH),
                finite(b.m_ersHarvestLimitPerLap), finite(b.m_ersDeployedThisLap))
            car.tyres.actual_compound = E.label(E.ACTUAL_COMPOUND, b.m_actualTyreCompound)
            car.tyres.visual_compound = E.label(E.VISUAL_COMPOUND, b.m_visualTyreCompound)
            car.tyres.age_laps = b.m_tyresAgeLaps
            car.aero.drs_allowed = E.flag(b.m_drsAllowed)
            car.aero.drs_activation_distance_m = b.m_drsActivationDistance
        elif category == 'damage':
            car.tyres.wear_percent, car.tyres.damage_percent = wheels(b.m_tyresWear), wheels(b.m_tyresDamage)
            car.tyres.blisters_percent = wheels(b.m_tyreBlisters)
            car.damage = DamageState(b.m_frontLeftWingDamage, b.m_frontRightWingDamage,
                b.m_rearWingDamage, b.m_floorDamage, b.m_diffuserDamage, b.m_sidepodDamage,
                E.flag(b.m_drsFault), E.flag(b.m_ersFault), b.m_gearBoxDamage, b.m_engineDamage,
                {component: getattr(b, f'm_engine{component}Wear') for component in ('MGUH', 'ES', 'CE', 'ICE', 'MGUK', 'TC')},
                E.flag(b.m_engineBlown), E.flag(b.m_engineSeized), wheels(b.m_brakesDamage))
        elif category == 'telemetry2':
            a = car.aero
            a.active_aero_mode = E.label(E.ACTIVE_AERO, b.m_activeAeroMode)
            a.active_aero_available = E.flag(b.m_activeAeroAvailable)
            a.active_aero_activation_distance_m = b.m_activeAeroActivationDistance
            a.overtake_available, a.overtake_active = E.flag(b.m_overtakeAvailable), E.flag(b.m_overtakeActive)
            a.overtake_activation_distance_m = b.m_overtakeActivationDistance
            a.regulations_2026, a.driving_wrong_way = E.flag(b.m_2026Regulations), E.flag(b.m_drivingWrongWay)
            a.raw_flags = {name: getattr(b, name) for name in ('m_activeAeroMode', 'm_activeAeroAvailable',
                'm_overtakeAvailable', 'm_overtakeActive', 'm_2026Regulations', 'm_drivingWrongWay')}

    def _tyre_sets(self, car: CarState, b) -> None:
        car.tyres.sets = tuple(TyreSet(i, E.label(E.ACTUAL_COMPOUND, t.m_actualTyreCompound),
            E.label(E.VISUAL_COMPOUND, t.m_visualTyreCompound), t.m_wear, E.flag(t.m_available),
            E.label(E.SESSION_TYPES, t.m_recommendedSession), t.m_lifeSpan, t.m_usableLife,
            t.m_lapDeltaTime / 1000, E.flag(t.m_fitted)) for i, t in enumerate(b.m_tyreSetData))
        car.tyres.fitted_set_index_raw = b.m_fittedIdx
        # EA does not define an out-of-range sentinel here. Preserve it, don't index it.
        car.tyres.fitted_set_index = b.m_fittedIdx if b.m_fittedIdx < 20 else None

    def _neighbours(self) -> None:
        s = self.state
        s.ahead_index = s.behind_index = s.gap_behind_s = None
        if s.player is None or s.player.lap.position is None:
            return
        position = s.player.lap.position
        for delta, attribute in ((-1, 'ahead_index'), (1, 'behind_index')):
            candidates = [i for i, car in s.field.items() if car.lap.position == position + delta]
            if len(candidates) == 1:
                setattr(s, attribute, candidates[0])
        if s.behind_index is not None:
            s.gap_behind_s = s.field[s.behind_index].lap.gap_to_car_in_front_s
