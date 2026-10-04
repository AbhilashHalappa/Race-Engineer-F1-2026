"""V0.4 deterministic rules that turn RaceState changes into engineer messages.

The engine intentionally reacts only to telemetry/state transitions. It does not
invent gaps, predict strategy, or use an LLM. Initial telemetry establishes a
baseline so joining a running session does not produce a burst of old warnings.
"""

from collections import deque
from dataclasses import dataclass

from .models import EngineerMessage, Priority
from ..speech_quality import DEFAULT_COOLDOWNS_S
from ..race_state.models import RaceEvent, RaceState, Wheels
from ..telemetry import enums as E
from ..event_context import build_event_context


def _name(value) -> str | None:
    return None if value is None else value.name


def _wheel_values(value: Wheels | None) -> tuple[float | int | None, ...]:
    return () if value is None else (value.FL, value.FR, value.RL, value.RR)


def _maximum(value: Wheels | None) -> float | None:
    values = [float(v) for v in _wheel_values(value) if v is not None]
    return max(values) if values else None


def _worst_wheel(value: Wheels | None) -> tuple[str, float] | None:
    if value is None:
        return None
    pairs = [(name, getattr(value, name)) for name in ('FL', 'FR', 'RL', 'RR')]
    pairs = [(name, float(v)) for name, v in pairs if v is not None]
    return max(pairs, key=lambda item: item[1]) if pairs else None


@dataclass(frozen=True, slots=True)
class Snapshot:
    uid: int | None
    lap: int | None
    position: int | None
    pit: str | None
    driver_status: str | None
    pit_stops: int | None
    penalties_s: int | None
    drive_through: int | None
    stop_go: int | None
    safety_car: str | None
    weather: str | None
    rain_now: int | None
    rain_5m: int | None
    fuel_laps: float | None
    tyre_age: int | None
    tyre_set: int | None
    tyre_wear_max: float | None
    tyre_wear_worst: tuple[str, float] | None
    tyre_damage_max: float | None
    tyre_damage_worst: tuple[str, float] | None
    tyre_surface_temp_max: float | None
    tyre_surface_temp_worst: tuple[str, float] | None
    brake_temp_max: float | None
    brake_temp_worst: tuple[str, float] | None
    off_track_surface: bool | None
    engine_temp_c: int | None
    tyre_blisters_max: float | None
    tyre_blisters_worst: tuple[str, float] | None
    engine_wear_max: int | None
    engine_wear_component: str | None
    warnings: int | None
    corner_cutting_warnings: int | None
    lap_valid: bool | None
    fl_wing: int | None
    fr_wing: int | None
    rear_wing: int | None
    floor: int | None
    diffuser: int | None
    sidepod: int | None
    brakes_max: float | None
    brakes_worst: tuple[str, float] | None
    engine: int | None
    gearbox: int | None
    drs_fault: bool | None
    ers_fault: bool | None
    engine_blown: bool | None
    engine_seized: bool | None
    wrong_way: bool | None
    overtake_available: bool | None
    overtake_active: bool | None
    active_aero_mode: str | None
    active_aero_available: bool | None
    regulations_2026: bool | None
    drs_allowed: bool | None
    drs_active: bool | None
    ers_deploy_mode: str | None
    local_flag: str | None
    next_flag: str | None


class AutomaticEngineer:
    """State-change/threshold based engineer with priority, dedupe and cooldowns."""

    def __init__(self, *, max_queue: int = 32, ers_assist: bool = True, drs_s_mode_assist: bool = True, position_updates: bool = False) -> None:
        self.ers_assist = bool(ers_assist)
        self.drs_s_mode_assist = bool(drs_s_mode_assist)
        # Keep position-change logic available, but disable automatic radio calls by default.
        self.position_updates = bool(position_updates)
        self._previous: Snapshot | None = None
        self._session_uid: int | None = None
        self._queue: deque[EngineerMessage] = deque(maxlen=max_queue)
        self._last_emitted: dict[str, float] = {}
        self._thresholds_seen: set[str] = set()
        self._pit_active = False
        self._weather_baseline_until: float | None = None
        self._seen_events: set[tuple] = set()
        self._last_pit_call: str | None = None
        self._last_pit_signature: tuple | None = None
        self._last_pit_signature_at: float | None = None
        self._last_position_event_at: dict[int, float] = {}
        self._temp_alert_last: dict[str, float] = {}
        self._event_context = None
        self._s_mode_prompted = False
        self._s_mode_last_prompt_lap = None

    def reset(self, uid: int | None = None) -> None:
        self._previous = None
        self._session_uid = uid
        self._queue.clear()
        self._last_emitted.clear()
        self._thresholds_seen.clear()
        self._pit_active = False
        self._weather_baseline_until = None
        self._seen_events.clear()
        self._last_pit_call = None
        self._last_pit_signature = None
        self._last_pit_signature_at = None
        self._last_position_event_at.clear()
        self._temp_alert_last.clear()
        self._event_context = None
        self._s_mode_prompted = False
        self._s_mode_last_prompt_lap = None

    def evaluate(self, state: RaceState, now: float, changed_category: str | None = None) -> tuple[EngineerMessage, ...]:
        if state.player is None:
            return ()
        self._event_context = build_event_context(state)
        current = self._snapshot(state)
        if self._session_uid != current.uid:
            self.reset(current.uid)
        previous = self._previous
        self._previous = current
        if previous is None:
            self._seed_thresholds(current)
            self._pit_active = current.pit in ('Pitting', 'In pit area')
            # Session packets arrive asynchronously. During startup the RaceState can
            # briefly expose a default/earlier weather value before the first current
            # Session packet lands. Treat the first three seconds as weather baseline
            # acquisition so joining a session never creates a false 'weather change'.
            self._weather_baseline_until = now + 3.0
            self._mark_existing_events(state)
            return ()

        before = len(self._queue)
        # In production the receiver supplies the packet category.  Avoid running
        # expensive rules on packet families that cannot change their inputs,
        # while preserving the legacy full-evaluation path when category is None
        # (tests/direct callers).
        if changed_category is None or changed_category == "events":
            self._event_calls(state, now)
        self._transitions(previous, current, state, now)
        if changed_category is None or changed_category in {"status", "telemetry", "telemetry2", "session"}:
            self._assist_rules(current, state, now)
        if self._metric("pit_strategy") and (
            changed_category is None or changed_category in {"session", "lap", "status", "damage", "tyres", "events"}
        ):
            self._pit_strategy_rule(state, now)
        self._threshold_rules(previous, current, state, now)
        # Return only messages generated by this evaluation. The public drain()
        # remains the authoritative delivery queue.
        if len(self._queue) >= before:
            return tuple(list(self._queue)[before:])
        return ()

    def drain(self) -> tuple[EngineerMessage, ...]:
        messages = tuple(sorted(self._queue, key=lambda m: (m.priority, m.created_at)))
        self._queue.clear()
        return messages

    def _metric(self, name: str) -> bool:
        ctx = self._event_context
        return bool(ctx is not None and getattr(ctx.metrics, name, False))

    @staticmethod
    def _cooldown_category(key: str, priority: Priority) -> str:
        k=str(key or '').lower()
        if priority == Priority.CRITICAL:
            return 'critical'
        if k.startswith(('pit:', 'tyre_set:')):
            return 'pit'
        if k.startswith(('wear:', 'tyre_damage:', 'tyre_temp:', 'blisters:')):
            return 'tyres'
        if k.startswith('brake'):
            return 'brakes'
        if k.startswith('fuel:'):
            return 'fuel'
        if k.startswith(('assist:ers', 'overtake:')):
            return 'ers'
        if k.startswith(('race_control:', 'safety_car', 'flag:')):
            return 'race_control'
        if k.startswith(('strategy:', 'weather', 'forecast:')):
            return 'strategy'
        if k.startswith(('corner:', 'straight:', 'assist:')) or priority == Priority.COACHING:
            return 'coaching'
        return 'information'

    def _emit(self, key: str, priority: Priority, text: str, now: float,
              state: RaceState, cooldown: float | None = None) -> None:
        if cooldown is None:
            cooldown=float(DEFAULT_COOLDOWNS_S[self._cooldown_category(key, priority)])
        last = self._last_emitted.get(key)
        if last is not None and now - last < cooldown:
            return
        self._last_emitted[key] = now
        self._queue.append(EngineerMessage(key, priority, text, now, state.session.session_time_s))
        # V0.9.5 deterministic decision audit: retain exactly what rule spoke,
        # when it spoke, and its priority. Message text contains the measured
        # value/reason for threshold and strategy calls; no inferred evidence is added.
        audit = state.extended.setdefault('decision_audit', [])
        audit.append({'key': key, 'priority': priority.name, 'text': text,
                      'session_time_s': state.session.session_time_s, 'observed_at': now})
        if len(audit) > 200:
            del audit[:-200]

    def _rearm_thresholds(self, prefix: str, value: float | None,
                          thresholds: tuple[int, ...], hysteresis: float = 5.0) -> None:
        """Re-arm reversible alert bands only after a real recovery.

        V0.9.0 latched threshold bands forever, which meant a brake/tyre/engine
        temperature could overheat, cool down, then overheat again without a new
        warning. Hysteresis prevents chatter around the boundary while allowing a
        later independent excursion to be announced. The same helper also lets a
        repaired/replaced component re-arm after its reported damage falls.
        """
        if value is None:
            return
        for threshold in thresholds:
            if value < threshold - hysteresis:
                self._thresholds_seen.discard(f'{prefix}:{threshold}')

    def _clear_threshold_family(self, prefix: str) -> None:
        self._thresholds_seen = {k for k in self._thresholds_seen if not k.startswith(prefix + ':')}

    def _highest_crossed(self, prefix: str, old: float | None, new: float | None,
                         thresholds: tuple[int, ...]) -> int | None:
        if new is None:
            return None
        crossed = [t for t in thresholds if new >= t and f'{prefix}:{t}' not in self._thresholds_seen
                   and (old is None or old < t)]
        # If one packet jumps across several bands, announce only the most severe
        # band and latch all lower bands to avoid a burst of redundant calls.
        for threshold in thresholds:
            if new >= threshold:
                self._thresholds_seen.add(f'{prefix}:{threshold}')
        return max(crossed) if crossed else None

    def _seed_thresholds(self, s: Snapshot) -> None:
        for prefix, value, thresholds in (
            ('wear', s.tyre_wear_max, (25, 50, 70, 85)),
            ('tyre_damage', s.tyre_damage_max, (25, 50, 75)),
            ('tyre_temp', s.tyre_surface_temp_max, (110, 115)),
            ('brake_temp', s.brake_temp_max, (1000, 1100)),
            ('engine_temp', s.engine_temp_c, (120, 130)),
            ('blisters', s.tyre_blisters_max, (25, 50, 75)),
            ('engine_wear_component', s.engine_wear_max, (50, 75, 90)),
            ('front_wing', max(v for v in (s.fl_wing, s.fr_wing) if v is not None) if any(v is not None for v in (s.fl_wing, s.fr_wing)) else None, (20, 50, 80)),
            ('rear_wing', s.rear_wing, (20, 50, 80)), ('floor', s.floor, (25, 50, 75)),
            ('diffuser', s.diffuser, (25, 50, 75)), ('sidepod', s.sidepod, (25, 50, 75)),
            ('brakes', s.brakes_max, (25, 50, 75)), ('engine', s.engine, (25, 50, 75)),
            ('gearbox', s.gearbox, (25, 50, 75))):
            if value is not None:
                for threshold in thresholds:
                    if value >= threshold:
                        self._thresholds_seen.add(f'{prefix}:{threshold}')

    def _transitions(self, p: Snapshot, c: Snapshot, state: RaceState, now: float) -> None:
        if p.lap is not None and c.lap is not None and c.lap > p.lap:
            prev_time = state.player.lap.previous_lap_time_s
            suffix = f' Previous lap {prev_time:.3f} seconds.' if prev_time else ''
            self._emit(f'lap:{c.lap}', Priority.INFORMATION, f'Lap {c.lap}.{suffix}', now, state, 0)
        if self.position_updates and self._metric("race_position_strategy") and p.position and c.position and p.position != c.position:
            direction = 'up' if c.position < p.position else 'down'
            self._emit('position', Priority.INFORMATION, f'Position {c.position}, {direction} from P{p.position}.', now, state, 2)
        # Pit detection deliberately uses both EA pitStatus and driverStatus.
        # Real captures show In lap/Pitting -> Out lap/Pitting -> Out lap/None,
        # so a one-packet equality check is too brittle for the multi-rate stream.
        pit_now = c.pit in ('Pitting', 'In pit area')
        if self._metric("pit_lane_guidance"):
            entered = not self._pit_active and pit_now
            if entered:
                self._pit_active = True
                self._emit('pit:enter', Priority.STRATEGY, 'Pit lane. Pit limiter and marks.', now, state, 0)
            exited = self._pit_active and not pit_now and (
                c.driver_status == 'Out lap' or
                (p.pit in ('Pitting', 'In pit area') and c.pit == 'None') or
                (p.pit_stops is not None and c.pit_stops is not None and c.pit_stops > p.pit_stops)
            )
            if exited:
                self._pit_active = False
                self._emit('pit:exit', Priority.INFORMATION, 'Pit exit. Watch the line and bring the tyres in.', now, state, 0)
        else:
            self._pit_active = False
        if self._metric("tyre_wear_strategy") and p.tyre_set is not None and c.tyre_set is not None and p.tyre_set != c.tyre_set:
            # A newly fitted set is a new physical component. Re-arm all tyre
            # condition bands so genuine problems on the new set can be announced.
            for family in ('wear', 'tyre_damage', 'tyre_temp', 'blisters'):
                self._clear_threshold_family(family)
            compound = _name(state.player.tyres.visual_compound) or _name(state.player.tyres.actual_compound) or 'new'
            self._emit(f'tyre_set:{c.tyre_set}', Priority.STRATEGY,
                       f'New {compound} tyre set fitted, set {c.tyre_set}.', now, state, 0)
        if self._metric("penalty_monitoring") and p.penalties_s is not None and c.penalties_s is not None and c.penalties_s > p.penalties_s:
            self._emit('penalty:time', Priority.CRITICAL,
                       f'Penalty registered. Total time penalties now {c.penalties_s} seconds.', now, state, 2)
        if self._metric("penalty_monitoring") and (p.drive_through or 0) < (c.drive_through or 0):
            self._emit('penalty:dt', Priority.CRITICAL, 'Drive-through penalty to serve.', now, state, 5)
        if self._metric("penalty_monitoring") and (p.stop_go or 0) < (c.stop_go or 0):
            self._emit('penalty:sg', Priority.CRITICAL, 'Stop-go penalty to serve.', now, state, 5)
        if self._metric("safety_car_strategy") and p.safety_car != c.safety_car and c.safety_car is not None:
            if c.safety_car == 'Full':
                self._emit('safety_car', Priority.CRITICAL, 'Safety Car deployed.', now, state, 10)
            elif c.safety_car == 'Virtual':
                self._emit('safety_car', Priority.CRITICAL, 'Virtual Safety Car deployed.', now, state, 10)
            elif p.safety_car in ('Full', 'Virtual') and c.safety_car == 'None':
                self._emit('safety_car:end', Priority.STRATEGY, 'Safety Car period ending. Prepare for racing.', now, state, 10)
        # Local flag relevance: only the player's current marshal zone and the
        # immediately upcoming marshal zone matter. A yellow farther around the
        # circuit must not generate radio traffic. Treat 'yellow ahead' and
        # entering that same yellow zone as one continuous condition so it is
        # announced only once. Green is spoken only when that relevant yellow
        # condition actually clears, not when unrelated marshal zones update.
        p_yellow_relevant = p.local_flag == 'Yellow' or p.next_flag == 'Yellow'
        c_yellow_relevant = c.local_flag == 'Yellow' or c.next_flag == 'Yellow'
        if self._metric("flag_monitoring") and c.local_flag == 'Blue' and p.local_flag != 'Blue':
            self._emit('flag:local', Priority.CRITICAL,
                       'Blue flag. A faster car is approaching.', now, state, 0)
        elif self._metric("flag_monitoring") and c_yellow_relevant and not p_yellow_relevant:
            if c.local_flag == 'Yellow':
                text = 'Yellow flag. Slow down and be prepared to avoid an incident.'
            else:
                text = 'Yellow flag ahead. Be prepared to slow down.'
            self._emit('flag:local', Priority.CRITICAL, text, now, state, 0)
        elif self._metric("flag_monitoring") and p_yellow_relevant and not c_yellow_relevant:
            self._emit('flag:local', Priority.INFORMATION,
                       'Green flag. Track is clear.', now, state, 0)

        # A field becoming available is baseline acquisition, not a change.
        if self._metric("weather_strategy") and p.weather is not None and c.weather is not None and p.weather != c.weather:
            if self._weather_baseline_until is None or now >= self._weather_baseline_until:
                self._emit('weather', Priority.STRATEGY, f'Weather change: {c.weather}.', now, state, 15)
        if self._metric("overtake_analysis") and p.overtake_available is False and c.overtake_available is True:
            self._emit('overtake:available', Priority.INFORMATION, 'Overtake is available.', now, state, 10)
        if p.drs_fault is not True and c.drs_fault is True:
            self._emit('fault:drs', Priority.CRITICAL, 'DRS fault reported.', now, state, 30)
        if p.ers_fault is not True and c.ers_fault is True:
            self._emit('fault:ers', Priority.CRITICAL, 'ERS fault reported.', now, state, 30)
        if p.engine_blown is not True and c.engine_blown is True:
            self._emit('fault:engine_blown', Priority.CRITICAL, 'Engine failure. Engine blown.', now, state, 60)
        if p.engine_seized is not True and c.engine_seized is True:
            self._emit('fault:engine_seized', Priority.CRITICAL, 'Engine failure. Engine seized.', now, state, 60)
        if p.wrong_way is not True and c.wrong_way is True:
            self._emit('wrong_way', Priority.CRITICAL, 'Wrong way. Turn the car around safely.', now, state, 10)

    def _pit_strategy_rule(self, state: RaceState, now: float) -> None:
        """Automatic deterministic pit call with semantic repeat suppression.

        The same service reason can wobble numerically from packet to packet (for
        example 44% wing damage or a 109/110% wear projection).  Do not keep
        repeating the same instruction merely because the numeric detail changed.
        A higher urgency, different reason, tyre/service plan or penalty is allowed
        through immediately.
        """
        from ..pit_strategy import service_plan
        plan = service_plan(state)
        call = plan.pit.recommendation_hint
        self._last_pit_call = call
        if call not in ('box_now', 'box_soon'):
            return
        reason = (plan.pit.reasons[0] if plan.pit.reasons else 'unknown').lower()
        if reason.startswith('front wing damage'): reason_key='front_wing_damage'
        elif reason.startswith('measured tyre wear projects'): reason_key='tyre_projection'
        elif reason.startswith('game pit window'): reason_key='game_pit_window'
        elif 'puncture' in reason: reason_key='puncture'
        elif reason.startswith('maximum tyre wear'): reason_key='tyre_wear'
        elif reason.startswith('maximum tyre damage') or reason.startswith('tyre damage'): reason_key='tyre_damage'
        elif 'wet conditions' in reason or 'dry conditions' in reason: reason_key='weather_compound'
        else: reason_key=reason.split(':',1)[0][:64]
        signature=(call, reason_key, plan.tyre.compound, plan.tyre.set_index,
                   bool(plan.front_wing_service), bool(plan.serve_penalty))
        if (self._last_pit_signature == signature and self._last_pit_signature_at is not None
                and now - self._last_pit_signature_at < 120.0):
            return
        self._last_pit_signature = signature
        self._last_pit_signature_at = now
        # One concise service-plan call combines the most useful pit facts. Critical
        # safety messages remain independently eligible and outrank this strategy call.
        self._emit('pit:deterministic_plan', Priority.STRATEGY, plan.automatic_summary, now, state, 20)

    def _assist_rules(self, c: Snapshot, state: RaceState, now: float) -> None:
        """Optional driving-aid reminders based only on explicit EA telemetry.

        These are advisory calls: they never press a control or infer an
        activation zone. 2026 S Mode uses Active Aero availability/mode; legacy
        DRS uses DRS allowed/active. ERS Assist uses the explicit 2026 Overtake
        available/active flags.
        """
        if self.drs_s_mode_assist:
            if self._metric("active_aero_analysis") and c.regulations_2026 is True:
                eligible = c.active_aero_available is True and c.active_aero_mode != 'Straight mode'
                # V0.9.14.5: at most one automatic S-Mode reminder per lap. F1 26
                # can toggle availability/mode several times around one lap and the
                # old edge-trigger rule still sounded repetitive in real replays.
                # Manual "S mode status" radio remains available at any time.
                lap_key = c.lap if c.lap is not None else -1
                if eligible and self._s_mode_last_prompt_lap != lap_key:
                    self._emit('assist:s_mode', Priority.COACHING,
                               'S Mode.', now, state, None)
                    self._s_mode_last_prompt_lap = lap_key
                self._s_mode_prompted = eligible
            elif self._metric("legacy_drs_analysis") and c.drs_allowed is True and c.drs_active is not True:
                self._emit('assist:drs', Priority.COACHING,
                           'DRS.', now, state, None)

        if self.ers_assist and self._metric("overtake_analysis"):
            if c.overtake_available is True and c.overtake_active is not True:
                self._emit('assist:ers', Priority.COACHING,
                           'Overtake available.', now, state, None)

    @staticmethod
    def _event_id(event: RaceEvent) -> tuple:
        return (event.code, event.session_time_s, event.received_at, tuple(sorted(event.details.items())))

    def _mark_existing_events(self, state: RaceState) -> None:
        self._seen_events.update(self._event_id(event) for event in state.events)

    @staticmethod
    def _driver_name(state: RaceState, index: int | None) -> str:
        if index is None or index == 255:
            return 'another car'
        if index == state.player_index:
            return 'you'
        car = state.field.get(index)
        if car and car.identity.name:
            return car.identity.name
        return f'car {index}'

    @staticmethod
    def _is_player(state: RaceState, index: int | None) -> bool:
        return index is not None and index == state.player_index

    @staticmethod
    def _local_flags(state: RaceState) -> tuple[str | None, str | None]:
        """Return flags for the player's current and immediately next marshal zones.

        Marshal zones are circular around the lap. Sorting by start fraction also
        makes this robust to packet/order quirks. The next zone wraps from the
        final zone back to zone zero.
        """
        player = state.player
        zones = state.session.marshal_zones
        length = state.session.track_length_m
        distance = player.lap.lap_distance_m if player else None
        if not zones or not length or distance is None or length <= 0:
            return None, None
        ordered = tuple(sorted(zones, key=lambda zone: zone.start_fraction))
        fraction = (distance % length) / length
        current_index = len(ordered) - 1
        for index, zone in enumerate(ordered):
            if zone.start_fraction <= fraction:
                current_index = index
            else:
                break
        next_index = (current_index + 1) % len(ordered)
        return ordered[current_index].flag.name, ordered[next_index].flag.name

    def _event_calls(self, state: RaceState, now: float) -> None:
        for event in state.events:
            event_id = self._event_id(event)
            if event_id in self._seen_events:
                continue
            self._seen_events.add(event_id)
            d, code = event.details, event.code
            player = state.player_index

            if code == 'PENA' and self._is_player(state, d.get('vehicleIdx')):
                ptype = E.PENALTY_TYPES.get(d.get('penaltyType'), f"penalty type {d.get('penaltyType')}")
                infringement = d.get('infringementType')
                reason = E.INFRINGEMENT_TYPES.get(infringement, f"infringement {infringement}")
                seconds = d.get('time', 0) or 0
                places = d.get('placesGained', 0) or 0
                # V0.9.3: immediate, deliberately tiny track-limit call. EA explicitly
                # reports corner-cutting/running-wide infringements as 25..29. Use
                # the game event rather than trying to infer track boundaries from
                # world coordinates. The shared key/cooldown deduplicates the near-
                # simultaneous LapData corner-warning counter update.
                if infringement in (25, 26, 27, 28, 29):
                    self._emit('track_limits', Priority.CRITICAL, 'Track limits.', now, state, 1.0)
                    # Preserve a separate time/grid/drive-through/stop-go call when
                    # race control also assigns a real penalty for the excursion.
                    if d.get('penaltyType') == 5:
                        continue
                if not self._metric("penalty_monitoring"):
                    continue
                if d.get('penaltyType') == 4 and seconds:
                    text = f'{seconds}-second time penalty for {reason}.'
                elif d.get('penaltyType') == 2 and places:
                    text = f'{places}-place grid penalty for {reason}.'
                elif d.get('penaltyType') == 0:
                    text = f'Drive-through penalty for {reason}.'
                elif d.get('penaltyType') == 1:
                    text = f'Stop-go penalty for {reason}.'
                elif d.get('penaltyType') == 5:
                    text = f'Warning for {reason}.'
                elif d.get('penaltyType') in (10, 11, 12, 13, 14, 15):
                    text = f'{ptype} for {reason}.'
                else:
                    text = f'{ptype} for {reason}.'
                self._emit(f'race_control:penalty:{event.session_time_s}', Priority.CRITICAL, text, now, state, 0)
            elif code == 'DRSD':
                reason = E.DRS_DISABLED_REASONS.get(d.get('reason'), 'race control')
                self._emit(f'race_control:drs_off:{event.session_time_s}', Priority.STRATEGY,
                           f'DRS disabled: {reason}.', now, state, 0)
            elif code == 'DRSE':
                self._emit(f'race_control:drs_on:{event.session_time_s}', Priority.INFORMATION,
                           'DRS enabled.', now, state, 0)
            elif code == 'RDFL' and self._metric("red_flag_strategy"):
                self._emit(f'race_control:red:{event.session_time_s}', Priority.CRITICAL,
                           'Red flag. Session suspended. Reduce speed and follow race control.', now, state, 0)
            elif code == 'PMEN':
                reason = E.PARTIAL_MODE_REASONS.get(d.get('reason'), 'race control')
                self._emit(f'race_control:partial_on:{event.session_time_s}', Priority.STRATEGY,
                           f'Partial mode enabled: {reason}.', now, state, 0)
            elif code == 'PMDI':
                self._emit(f'race_control:partial_off:{event.session_time_s}', Priority.INFORMATION,
                           'Partial mode disabled.', now, state, 0)
            elif code == 'RCWN' and self._metric("race_position_strategy"):
                self._emit(f'race_control:winner:{event.session_time_s}', Priority.INFORMATION,
                           f'Race winner: {self._driver_name(state, d.get("vehicleIdx"))}.', now, state, 0)
            elif code == 'OVEN' and self._metric("overtake_analysis"):
                self._emit(f'race_control:overtake_on:{event.session_time_s}', Priority.INFORMATION,
                           'Race control: Overtake mode enabled.', now, state, 0)
            elif code == 'OVDI' and self._metric("overtake_analysis"):
                self._emit(f'race_control:overtake_off:{event.session_time_s}', Priority.STRATEGY,
                           'Race control: Overtake mode disabled.', now, state, 0)
            elif code == 'SCAR' and self._metric("safety_car_strategy"):
                sc = {0: 'Safety Car', 1: 'Safety Car', 2: 'Virtual Safety Car', 3: 'Formation-lap Safety Car'}.get(d.get('safetyCarType'), 'Safety Car')
                action = E.SAFETY_CAR_EVENT.get(d.get('eventType'), 'update')
                texts = {'Deployed': f'{sc} deployed.', 'Returning': f'{sc} returning. Prepare for the restart.',
                         'Returned': f'{sc} returned to the pits.', 'Resume race': 'Race resumed. Green flag.'}
                self._emit('safety_car' if action == 'Deployed' else 'safety_car:end',
                           Priority.CRITICAL if action == 'Deployed' else Priority.STRATEGY,
                           texts.get(action, f'{sc}: {action}.'), now, state, 10)
            elif code == 'DTSV' and self._metric("penalty_monitoring") and self._is_player(state, d.get('vehicleIdx')):
                self._emit(f'race_control:dt_served:{event.session_time_s}', Priority.INFORMATION,
                           'Drive-through penalty served.', now, state, 0)
            elif code == 'SGSV' and self._metric("penalty_monitoring") and self._is_player(state, d.get('vehicleIdx')):
                stop = d.get('stopTime')
                suffix = f' Stop time {stop:.1f} seconds.' if isinstance(stop, float) else ''
                self._emit(f'race_control:sg_served:{event.session_time_s}', Priority.INFORMATION,
                           f'Stop-go penalty served.{suffix}', now, state, 0)
            elif code == 'COLL' and (self._is_player(state, d.get('vehicle1Idx')) or self._is_player(state, d.get('vehicle2Idx'))):
                other = d.get('vehicle2Idx') if self._is_player(state, d.get('vehicle1Idx')) else d.get('vehicle1Idx')
                severity = E.COLLISION_SEVERITY.get(d.get('severity'), 'unknown')
                self._emit(f'incident:collision:{event.session_time_s}', Priority.CRITICAL if severity == 'high' else Priority.INFORMATION,
                           f'{severity.capitalize()} collision with {self._driver_name(state, other)}.', now, state, 0)
            elif code == 'RTMT' and self._is_player(state, d.get('vehicleIdx')):
                reason = E.RETIREMENT_REASONS.get(d.get('reason'), 'unknown reason')
                self._emit(f'race_control:retirement:{event.session_time_s}', Priority.CRITICAL,
                           f'Race over. Retirement: {reason}.', now, state, 0)
            elif code == 'TMPT' and self._metric("race_position_strategy"):
                self._emit(f'team:mate_pit:{event.session_time_s}', Priority.INFORMATION,
                           f'Team mate {self._driver_name(state, d.get("vehicleIdx"))} is in the pits.', now, state, 0)
            elif code == 'FTLP':
                name = self._driver_name(state, d.get('vehicleIdx'))
                lap = d.get('lapTime')
                if self._is_player(state, d.get('vehicleIdx')):
                    text = f'Fastest lap. {lap:.3f} seconds.' if isinstance(lap, float) else 'Fastest lap.'
                    self._emit(f'race_control:fastest:{event.session_time_s}', Priority.INFORMATION, text, now, state, 0)
            elif code == 'CHQF':
                self._emit(f'race_control:chequered:{event.session_time_s}', Priority.INFORMATION,
                           'Chequered flag. Finish the lap.', now, state, 0)
            elif code == 'LGOT' and self._metric("race_position_strategy"):
                self._emit(f'race_control:lightsout:{event.session_time_s}', Priority.CRITICAL,
                           'Lights out. Go, go, go.', now, state, 0)
            elif code == 'OVTK' and self._metric("race_position_strategy"):
                c=state.player
                pit_name=(getattr(getattr(c,'lap',None).pit_status,'name',None) or '').lower() if c is not None else ''
                sc_name=(getattr(state.session.safety_car,'name',None) or '').lower().replace('_',' ')
                unstable = bool(c is not None and (getattr(c.lap,'pit_lane_timer_active',False) or
                          (pit_name and pit_name not in {'none','no pit'}))) or bool(
                          sc_name and sc_name not in {'none','no safety car','invalid'} and
                          ('safety' in sc_name or 'virtual' in sc_name or 'vsc' in sc_name))
                if unstable:
                    continue
                if self._is_player(state, d.get('overtakingVehicleIdx')):
                    other=d.get('beingOvertakenVehicleIdx')
                    if isinstance(other,int) and now-self._last_position_event_at.get(other,-1e9) < 8.0:
                        continue
                    if isinstance(other,int): self._last_position_event_at[other]=now
                    self._emit(f'race:overtake:{event.session_time_s}', Priority.INFORMATION,
                               f'Overtake complete on {self._driver_name(state, other)}.', now, state, 0)
                elif self._is_player(state, d.get('beingOvertakenVehicleIdx')):
                    other=d.get('overtakingVehicleIdx')
                    if isinstance(other,int) and now-self._last_position_event_at.get(other,-1e9) < 8.0:
                        continue
                    if isinstance(other,int): self._last_position_event_at[other]=now
                    self._emit(f'race:overtaken:{event.session_time_s}', Priority.INFORMATION,
                               f'{self._driver_name(state, other)} has passed you.', now, state, 0)

    def _threshold_rules(self, p: Snapshot, c: Snapshot, state: RaceState, now: float) -> None:
        # Re-arm reversible bands after recovery/repair. This is deliberately done
        # before crossing detection and uses hysteresis to avoid boundary chatter.
        self._rearm_thresholds('tyre_temp', c.tyre_surface_temp_max, (115,), 8)
        self._rearm_thresholds('brake_temp', c.brake_temp_max, (1100, 1200), 75)
        self._rearm_thresholds('engine_temp', c.engine_temp_c, (120, 130), 5)
        self._rearm_thresholds('blisters', c.tyre_blisters_max, (25, 50, 75), 5)
        self._rearm_thresholds('tyre_damage', c.tyre_damage_max, (25, 50, 75), 5)
        self._rearm_thresholds('brakes', c.brakes_max, (25, 50, 75), 5)
        self._rearm_thresholds('engine_wear_component', c.engine_wear_max, (50, 75, 90), 5)
        for prefix, value in (('rear_wing', c.rear_wing), ('floor', c.floor),
                              ('diffuser', c.diffuser), ('sidepod', c.sidepod),
                              ('engine', c.engine), ('gearbox', c.gearbox)):
            self._rearm_thresholds(prefix, value, (25, 50, 75), 5)
        front = max(v for v in (c.fl_wing, c.fr_wing) if v is not None) if any(v is not None for v in (c.fl_wing, c.fr_wing)) else None
        self._rearm_thresholds('front_wing', front, (20, 50, 80), 5)

        # Game-supplied MFD fuel-laps value: warn without predicting consumption.
        if self._metric("fuel_strategy") and c.fuel_laps is not None:
            if p.fuel_laps is not None and p.fuel_laps > .25 >= c.fuel_laps:
                self._emit('fuel:critical', Priority.CRITICAL,
                           f'Fuel critical. MFD estimate is a {c.fuel_laps:.2f} lap fuel margin.', now, state, 30)
            elif p.fuel_laps is not None and p.fuel_laps > 1.0 >= c.fuel_laps:
                self._emit('fuel:low', Priority.STRATEGY,
                           f'Fuel warning. MFD estimate is a {c.fuel_laps:.2f} lap fuel margin.', now, state, 30)

        # Forecast warnings are based only on game-supplied rain percentages.
        if self._metric("weather_strategy") and p.rain_5m is not None and c.rain_5m is not None:
            if p.rain_5m < 50 <= c.rain_5m:
                self._emit('forecast:rain50', Priority.STRATEGY,
                           f'Rain risk increasing. Game forecast is {c.rain_5m}% in five minutes.', now, state, 60)
            elif p.rain_5m < 20 <= c.rain_5m:
                self._emit('forecast:rain20', Priority.INFORMATION,
                           f'Rain possible. Game forecast is {c.rain_5m}% in five minutes.', now, state, 60)

        wear_priorities = {25: Priority.INFORMATION, 50: Priority.STRATEGY,
                           70: Priority.STRATEGY, 85: Priority.CRITICAL}
        threshold = self._highest_crossed('wear', p.tyre_wear_max, c.tyre_wear_max, (25, 50, 70, 85)) if self._metric("tyre_wear_strategy") else None
        if threshold is not None:
            wheel = c.tyre_wear_worst
            where = f' Worst is {wheel[0]} at {wheel[1]:.0f}%.' if wheel else ''
            self._emit(f'wear:{threshold}', wear_priorities[threshold],
                       f'Tyre wear has reached {threshold}%.{where}', now, state, 0)

        tyre_damage_priorities = {25: Priority.STRATEGY, 50: Priority.CRITICAL, 75: Priority.CRITICAL}
        threshold = self._highest_crossed('tyre_damage', p.tyre_damage_max, c.tyre_damage_max, (25, 50, 75)) if self._metric("damage_strategy") else None
        if threshold is not None:
            wheel = c.tyre_damage_worst
            where = f' {wheel[0]} is {wheel[1]:.0f}% damaged.' if wheel else ''
            self._emit(f'tyre_damage:{threshold}', tyre_damage_priorities[threshold],
                       f'Tyre damage warning.{where}', now, state, 0)

        # Temperature limits are deliberately explicit and deterministic. They are
        # project alert bands, not predictions of future failure. V0.9.6.1 uses the
        # upper bands only for automatic radio so brief normal MFD colour changes
        # do not create repetitive calls. Exact temperatures remain available on request.
        threshold = self._highest_crossed('tyre_temp', p.tyre_surface_temp_max, c.tyre_surface_temp_max, (115,)) if self._metric("tyre_temperature") else None
        if threshold is not None:
            wheel = c.tyre_surface_temp_worst
            where = f' {wheel[0]} is {wheel[1]:.0f} degrees.' if wheel else ''
            self._emit('tyre_temp:115', Priority.STRATEGY, f'Tyres hot.{where}', now, state, 20)

        threshold = self._highest_crossed('brake_temp', p.brake_temp_max, c.brake_temp_max, (1100, 1200)) if self._metric("brake_temperature") else None
        if threshold is not None:
            wheel = c.brake_temp_worst
            where = f' {wheel[0]} is {wheel[1]:.0f} degrees.' if wheel else ''
            pri = Priority.CRITICAL if threshold >= 1200 else Priority.STRATEGY
            self._emit(f'brake_temp:{threshold}', pri, f'Brakes hot.{where}', now, state, 20)

        threshold = self._highest_crossed('engine_temp', p.engine_temp_c, c.engine_temp_c, (120, 130))
        if threshold is not None:
            pri = Priority.CRITICAL if threshold >= 130 else Priority.STRATEGY
            self._emit(f'engine_temp:{threshold}', pri, f'Engine temperature warning. {c.engine_temp_c} degrees.', now, state, 0)

        threshold = self._highest_crossed('blisters', p.tyre_blisters_max, c.tyre_blisters_max, (25, 50, 75)) if self._metric("damage_strategy") else None
        if threshold is not None:
            wheel = c.tyre_blisters_worst
            where = f' Worst is {wheel[0]} at {wheel[1]:.0f}%.' if wheel else ''
            pri = Priority.CRITICAL if threshold >= 75 else Priority.STRATEGY
            self._emit(f'blisters:{threshold}', pri, f'Tyre blistering warning.{where}', now, state, 0)

        threshold = self._highest_crossed('engine_wear_component', p.engine_wear_max, c.engine_wear_max, (50, 75, 90)) if self._metric("damage_strategy") else None
        if threshold is not None:
            comp = (c.engine_wear_component or 'engine component').replace('_', ' ')
            pri = Priority.CRITICAL if threshold >= 90 else Priority.STRATEGY
            self._emit(f'engine_wear_component:{threshold}', pri, f'{comp.title()} wear is {c.engine_wear_max}%.', now, state, 0)

        # Immediate physical off-track cue from the per-wheel surface type in the
        # high-rate CarTelemetry packet. Surface codes 3..8 are rock/gravel/mud/
        # sand/grass/water. Require at least three wheels so a kerb touch or a
        # single dropped wheel does not chatter. Official corner-cutting/PENA
        # events below remain the authoritative race-control fallback.
        if c.off_track_surface is True and p.off_track_surface is not True:
            self._emit('track_limits', Priority.CRITICAL, 'Track limits.', now, state, 1.0)

        if p.warnings is not None and c.warnings is not None and c.warnings > p.warnings:
            self._emit('warnings', Priority.INFORMATION, f'Warnings now {c.warnings}.', now, state, 0)
        if p.corner_cutting_warnings is not None and c.corner_cutting_warnings is not None and c.corner_cutting_warnings > p.corner_cutting_warnings:
            # Immediate short driver cue. The warning count remains available via
            # RaceState/radio; don't read the number aloud while the driver is busy.
            self._emit('track_limits', Priority.CRITICAL, 'Track limits.', now, state, 1.0)
        if p.lap_valid is True and c.lap_valid is False:
            self._emit('lap_invalid', Priority.INFORMATION, 'Current lap invalidated.', now, state, 0)

        if self._metric("damage_strategy"):
            old_front = max(v for v in (p.fl_wing, p.fr_wing) if v is not None) if any(v is not None for v in (p.fl_wing, p.fr_wing)) else None
            new_front = max(v for v in (c.fl_wing, c.fr_wing) if v is not None) if any(v is not None for v in (c.fl_wing, c.fr_wing)) else None
            front_priorities = {20: Priority.STRATEGY, 50: Priority.CRITICAL, 80: Priority.CRITICAL}
            threshold = self._highest_crossed('front_wing', old_front, new_front, (20, 50, 80))
            if threshold is not None:
                self._emit(f'front_wing:{threshold}', front_priorities[threshold],
                    f'Front wing damage. Left {c.fl_wing or 0}%, right {c.fr_wing or 0}%.', now, state, 0)

            component_priorities = {25: Priority.STRATEGY, 50: Priority.CRITICAL, 75: Priority.CRITICAL}
            for prefix, label, old, new in (
                ('rear_wing', 'Rear wing', p.rear_wing, c.rear_wing),
                ('floor', 'Floor', p.floor, c.floor), ('diffuser', 'Diffuser', p.diffuser, c.diffuser),
                ('sidepod', 'Sidepod', p.sidepod, c.sidepod), ('engine', 'Engine', p.engine, c.engine),
                ('gearbox', 'Gearbox', p.gearbox, c.gearbox)):
                threshold = self._highest_crossed(prefix, old, new, (25, 50, 75))
                if threshold is not None:
                    self._emit(f'{prefix}:{threshold}', component_priorities[threshold],
                               f'{label} damage is {new}%.', now, state, 0)

            threshold = self._highest_crossed('brakes', p.brakes_max, c.brakes_max, (25, 50, 75))
            if threshold is not None:
                wheel = c.brakes_worst
                where = f' Worst is {wheel[0]} at {wheel[1]:.0f}%.' if wheel else ''
                self._emit(f'brakes:{threshold}', component_priorities[threshold],
                           f'Brake damage warning.{where}', now, state, 0)

    @staticmethod
    def _snapshot(state: RaceState) -> Snapshot:
        p = state.player
        assert p is not None
        forecast_now = next((f for f in state.session.forecast if f.offset_minutes == 0), None)
        forecast_5m = next((f for f in state.session.forecast if f.offset_minutes == 5), None)
        local_flag, next_flag = AutomaticEngineer._local_flags(state)
        return Snapshot(
            uid=state.session.uid, lap=p.lap.current_lap, position=p.lap.position,
            pit=_name(p.lap.pit_status), driver_status=_name(p.lap.driver_status),
            pit_stops=p.lap.pit_stops, penalties_s=p.lap.penalties_s,
            drive_through=p.lap.unserved_drive_through, stop_go=p.lap.unserved_stop_go,
            safety_car=_name(state.session.safety_car), weather=_name(state.session.weather),
            rain_now=forecast_now.rain_percent if forecast_now else None,
            rain_5m=forecast_5m.rain_percent if forecast_5m else None,
            fuel_laps=p.fuel.remaining_laps, tyre_age=p.tyres.age_laps,
            tyre_set=p.tyres.fitted_set_index, tyre_wear_max=_maximum(p.tyres.wear_percent),
            tyre_wear_worst=_worst_wheel(p.tyres.wear_percent),
            tyre_damage_max=_maximum(p.tyres.damage_percent),
            tyre_damage_worst=_worst_wheel(p.tyres.damage_percent),
            tyre_surface_temp_max=_maximum(p.tyres.surface_temperature_c),
            tyre_surface_temp_worst=_worst_wheel(p.tyres.surface_temperature_c),
            brake_temp_max=_maximum(p.telemetry.brakes_temperature_c),
            brake_temp_worst=_worst_wheel(p.telemetry.brakes_temperature_c),
            off_track_surface=(sum(1 for v in _wheel_values(p.telemetry.surface_type) if v is not None and 3 <= int(v) <= 8) >= 3) if p.telemetry.surface_type is not None else None,
            engine_temp_c=p.telemetry.engine_temperature_c,
            tyre_blisters_max=_maximum(p.tyres.blisters_percent),
            tyre_blisters_worst=_worst_wheel(p.tyres.blisters_percent),
            engine_wear_max=(max(p.damage.engine_wear_percent.values()) if p.damage.engine_wear_percent else None),
            engine_wear_component=(max(p.damage.engine_wear_percent, key=p.damage.engine_wear_percent.get) if p.damage.engine_wear_percent else None),
            warnings=p.lap.warnings, corner_cutting_warnings=p.lap.corner_cutting_warnings,
            lap_valid=p.lap.lap_valid,
            fl_wing=p.damage.front_left_wing_percent, fr_wing=p.damage.front_right_wing_percent,
            rear_wing=p.damage.rear_wing_percent, floor=p.damage.floor_percent,
            diffuser=p.damage.diffuser_percent, sidepod=p.damage.sidepod_percent,
            brakes_max=_maximum(p.damage.brakes_percent), brakes_worst=_worst_wheel(p.damage.brakes_percent),
            engine=p.damage.engine_percent, gearbox=p.damage.gearbox_percent,
            drs_fault=p.damage.drs_fault, ers_fault=p.damage.ers_fault,
            engine_blown=p.damage.engine_blown, engine_seized=p.damage.engine_seized,
            wrong_way=p.aero.driving_wrong_way, overtake_available=p.aero.overtake_available,
            overtake_active=p.aero.overtake_active, active_aero_mode=_name(p.aero.active_aero_mode),
            active_aero_available=p.aero.active_aero_available, regulations_2026=p.aero.regulations_2026,
            drs_allowed=p.aero.drs_allowed, drs_active=p.telemetry.drs,
            ers_deploy_mode=_name(p.energy.deploy_mode),
            local_flag=local_flag, next_flag=next_flag)
