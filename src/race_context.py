"""Deterministic race-context arbitration for V1.3.6.0.

This module does not predict race outcomes.  It decides whether routine driving
coaching should be allowed right now and records which measured race facts caused
the decision.  Critical race information always outranks technique coaching.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
from typing import Any

ERS_MAX_J = 4_000_000.0


def _name(v: Any) -> str:
    return str(getattr(v, "name", v) or "").strip().lower().replace("_", " ")


def _wheel_values(w):
    if w is None:
        return []
    return [x for x in (getattr(w, 'FL', None), getattr(w, 'FR', None), getattr(w, 'RL', None), getattr(w, 'RR', None)) if isinstance(x, (int, float))]


@dataclass(frozen=True, slots=True)
class RaceContextDecision:
    level: str
    technique_coaching_allowed: bool
    prefer_race_exit_advice: bool
    reasons: tuple[str, ...]
    adaptations: tuple[str, ...]
    close_traffic: bool
    pit_active: bool
    neutralisation_active: bool
    wet_context: bool

    def to_dict(self):
        return asdict(self)


def assess_race_context(state, *, traffic_gap_s: float = 1.2, rear_gap_s: float = 1.0) -> RaceContextDecision:
    player = getattr(state, 'player', None)
    if player is None:
        return RaceContextDecision('unavailable', False, False, ('player_unavailable',), (), False, False, False, False)

    reasons: list[str] = []
    adaptations: list[str] = []
    lap = getattr(player, 'lap', None)
    tyres = getattr(player, 'tyres', None)
    damage = getattr(player, 'damage', None)
    energy = getattr(player, 'energy', None)
    fuel = getattr(player, 'fuel', None)
    telem = getattr(player, 'telemetry', None)

    pit_name = _name(getattr(lap, 'pit_status', None))
    pit_active = bool(getattr(lap, 'pit_lane_timer_active', False) or (pit_name and pit_name not in {'none', '0', 'n a', 'na'}))
    if pit_active:
        reasons.append('pit_active')

    sc = _name(getattr(getattr(state, 'session', None), 'safety_car', None))
    neutral = bool(sc and sc not in {'none', 'no safety car', 'invalid', '0'} and ('safety' in sc or 'virtual' in sc or 'vsc' in sc))
    if neutral:
        reasons.append('neutralisation_active')

    gap_ahead = getattr(lap, 'gap_to_car_in_front_s', None)
    gap_behind = getattr(state, 'gap_behind_s', None)
    close_ahead = isinstance(gap_ahead, (int, float)) and 0 <= float(gap_ahead) < float(traffic_gap_s)
    close_behind = isinstance(gap_behind, (int, float)) and 0 <= float(gap_behind) < float(rear_gap_s)
    close_traffic = close_ahead or close_behind
    if close_traffic:
        reasons.append('close_combat')

    severe_damage = False
    if damage is not None:
        if bool(getattr(damage, 'engine_blown', False)) or bool(getattr(damage, 'engine_seized', False)):
            reasons.append('critical_engine_failure'); severe_damage = True
        aero = [getattr(damage, n, None) for n in ('front_left_wing_percent','front_right_wing_percent','rear_wing_percent','floor_percent','diffuser_percent','sidepod_percent')]
        aero = [float(x) for x in aero if isinstance(x, (int, float))]
        if aero and max(aero) >= 40.0:
            reasons.append('severe_damage'); severe_damage = True
        elif aero and max(aero) >= 20.0:
            adaptations.append('damage_aware')

    wear = _wheel_values(getattr(tyres, 'wear_percent', None)) if tyres is not None else []
    if wear:
        mx = max(float(x) for x in wear)
        if mx >= 90.0:
            reasons.append('critical_tyre_wear')
        elif mx >= 70.0:
            adaptations.append('tyre_conservation')

    punctures = _wheel_values(getattr(tyres, 'punctured', None)) if tyres is not None else []
    if any(bool(x) for x in punctures):
        reasons.append('puncture')

    brake_t = _wheel_values(getattr(telem, 'brakes_temperature_c', None)) if telem is not None else []
    if brake_t and max(float(x) for x in brake_t) >= 1100.0:
        reasons.append('brake_temperature_danger')

    fuel_laps = getattr(fuel, 'remaining_laps', None) if fuel is not None else None
    if isinstance(fuel_laps, (int, float)):
        if float(fuel_laps) < 0:
            reasons.append('fuel_short')
        elif float(fuel_laps) < 0.5:
            adaptations.append('fuel_save')

    ers = getattr(energy, 'store_j', None) if energy is not None else None
    if isinstance(ers, (int, float)) and float(ers) / ERS_MAX_J < 0.20:
        adaptations.append('ers_conservation')

    session = getattr(state, 'session', None)
    weather = _name(getattr(session, 'weather', None))
    wet_context = any(k in weather for k in ('rain', 'wet', 'storm'))
    if not wet_context:
        forecasts = tuple(getattr(session, 'forecast', ()) or ())
        near = next((f for f in forecasts if getattr(f, 'offset_minutes', 99) <= 5), None)
        if near is not None:
            wn = _name(getattr(near, 'weather', None))
            rp = getattr(near, 'rain_percent', None)
            wet_context = any(k in wn for k in ('rain','wet','storm')) or (isinstance(rp, (int,float)) and float(rp) >= 50.0)
    if wet_context:
        adaptations.append('wet_weather')

    critical = any(r in reasons for r in ('critical_engine_failure','severe_damage','critical_tyre_wear','puncture','brake_temperature_danger','fuel_short'))
    if critical:
        level = 'critical'
        allowed = False
    elif pit_active or neutral:
        level = 'race_control'
        allowed = False
    elif close_traffic:
        level = 'combat'
        allowed = False
    else:
        level = 'performance'
        allowed = True

    return RaceContextDecision(
        level=level,
        technique_coaching_allowed=allowed,
        prefer_race_exit_advice=close_traffic,
        reasons=tuple(dict.fromkeys(reasons)),
        adaptations=tuple(dict.fromkeys(adaptations)),
        close_traffic=close_traffic,
        pit_active=pit_active,
        neutralisation_active=neutral,
        wet_context=wet_context,
    )


class RaceContextHysteresis:
    """Stabilise combat/performance transitions without delaying safety states.

    Combat enters immediately at the normal threshold.  Once active, it uses a
    wider release threshold plus a minimum hold and sustained-clear timer.
    Critical damage and race-control states always bypass the debounce.
    """

    def __init__(
        self,
        *,
        enter_ahead_s: float = 1.2,
        enter_behind_s: float = 1.0,
        exit_ahead_s: float = 1.8,
        exit_behind_s: float = 1.5,
        min_combat_hold_s: float = 4.0,
        clear_confirm_s: float = 3.0,
    ):
        self.enter_ahead_s = float(enter_ahead_s)
        self.enter_behind_s = float(enter_behind_s)
        self.exit_ahead_s = float(exit_ahead_s)
        self.exit_behind_s = float(exit_behind_s)
        self.min_combat_hold_s = float(min_combat_hold_s)
        self.clear_confirm_s = float(clear_confirm_s)
        self.level: str | None = None
        self.combat_entered_at: float | None = None
        self.clear_since: float | None = None

    @staticmethod
    def _as_combat(decision: RaceContextDecision) -> RaceContextDecision:
        reasons = tuple(dict.fromkeys((*decision.reasons, 'close_combat_hysteresis')))
        return replace(
            decision,
            level='combat',
            technique_coaching_allowed=False,
            prefer_race_exit_advice=True,
            reasons=reasons,
            close_traffic=True,
        )

    def reset(self) -> None:
        self.level = None
        self.combat_entered_at = None
        self.clear_since = None

    def update(self, state, now: float) -> RaceContextDecision:
        # Safety/race-control facts are always evaluated against the normal entry
        # thresholds and must never be delayed by combat hysteresis.
        raw = assess_race_context(
            state, traffic_gap_s=self.enter_ahead_s, rear_gap_s=self.enter_behind_s
        )
        if raw.level in {'critical', 'race_control', 'unavailable'}:
            self.level = raw.level
            self.clear_since = None
            if raw.level != 'combat':
                self.combat_entered_at = None
            return raw

        if self.level != 'combat':
            if raw.level == 'combat':
                self.level = 'combat'
                self.combat_entered_at = float(now)
                self.clear_since = None
                return raw
            self.level = raw.level
            self.combat_entered_at = None
            self.clear_since = None
            return raw

        # Already in combat: use a wider release threshold so small gap jitter
        # cannot immediately flip the coach back to performance mode.
        release_probe = assess_race_context(
            state, traffic_gap_s=self.exit_ahead_s, rear_gap_s=self.exit_behind_s
        )
        if release_probe.level in {'critical', 'race_control', 'unavailable'}:
            self.level = release_probe.level
            self.combat_entered_at = None
            self.clear_since = None
            return release_probe
        if release_probe.level == 'combat':
            self.clear_since = None
            return self._as_combat(release_probe)

        entered = self.combat_entered_at if self.combat_entered_at is not None else float(now)
        if float(now) - entered < self.min_combat_hold_s:
            self.clear_since = None
            return self._as_combat(release_probe)

        if self.clear_since is None:
            self.clear_since = float(now)
            return self._as_combat(release_probe)
        if float(now) - self.clear_since < self.clear_confirm_s:
            return self._as_combat(release_probe)

        self.level = 'performance'
        self.combat_entered_at = None
        self.clear_since = None
        return release_probe
