"""Session/event-aware metric applicability for EA SPORTS F1 25: 2026 Season Pack.

The EA UDP session packet describes both the session type and the active rule
configuration. This module converts that observed state into a conservative
analysis profile. It never fabricates unavailable rules and it never mutates
raw telemetry; it only decides which derived analyses/automatic calls are
meaningful for the current event.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any


PRACTICE_TYPES = {1, 2, 3, 4}
QUALIFYING_TYPES = set(range(5, 15))
RACE_TYPES = {15, 16, 17}
TIME_TRIAL_TYPE = 18


def _raw_enum(value: Any) -> int | None:
    raw = getattr(value, "raw", value)
    return raw if isinstance(raw, int) else None


def session_profile(session_type: int | None) -> str:
    if session_type == TIME_TRIAL_TYPE:
        return "time_trial"
    if session_type in PRACTICE_TYPES:
        return "practice"
    if session_type in QUALIFYING_TYPES:
        return "qualifying"
    if session_type in RACE_TYPES:
        return "race"
    return "unknown"


@dataclass(frozen=True, slots=True)
class MetricApplicability:
    # Driving/performance measurements
    lap_timing: bool = True
    lap_validity: bool = True
    driving_inputs: bool = True
    corner_analysis: bool = True
    lap_comparison: bool = True
    slip_traction: bool = True
    tyre_temperature: bool = True
    brake_temperature: bool = True
    tyre_pressure: bool = True

    # Session/resource strategy
    fuel_strategy: bool = False
    ers_energy_strategy: bool = False
    tyre_wear_strategy: bool = False
    race_position_strategy: bool = False
    traffic_gap_analysis: bool = False
    pit_strategy: bool = False
    pit_lane_guidance: bool = False
    penalty_monitoring: bool = False
    flag_monitoring: bool = False
    safety_car_strategy: bool = False
    red_flag_strategy: bool = False
    weather_strategy: bool = False
    damage_strategy: bool = False
    setup_change_advice: bool = False

    # Regulation-specific driving systems
    active_aero_analysis: bool = False
    overtake_analysis: bool = False
    legacy_drs_analysis: bool = False


@dataclass(frozen=True, slots=True)
class EventContext:
    profile: str
    session_type: int | None
    game_mode: int | None
    rule_set: int | None
    network_game: bool | None
    formula: int | None
    regulations_2026: bool | None
    equal_car_performance: int | None
    parc_ferme_rules: bool | None
    car_damage: int | None
    car_damage_rate: int | None
    corner_cutting_stringency: int | None
    safety_car_setting: int | None
    red_flags_setting: int | None
    low_fuel_mode: int | None
    metrics: MetricApplicability

    def to_dict(self) -> dict[str, Any]:
        # Avoid recursive dataclasses.asdict() on this hot path.  The shape stays
        # identical, but this is dramatically cheaper when sampled at UDP rate.
        m = self.metrics
        return {
            "profile": self.profile,
            "session_type": self.session_type,
            "game_mode": self.game_mode,
            "rule_set": self.rule_set,
            "network_game": self.network_game,
            "formula": self.formula,
            "regulations_2026": self.regulations_2026,
            "equal_car_performance": self.equal_car_performance,
            "parc_ferme_rules": self.parc_ferme_rules,
            "car_damage": self.car_damage,
            "car_damage_rate": self.car_damage_rate,
            "corner_cutting_stringency": self.corner_cutting_stringency,
            "safety_car_setting": self.safety_car_setting,
            "red_flags_setting": self.red_flags_setting,
            "low_fuel_mode": self.low_fuel_mode,
            "metrics": {name: getattr(m, name) for name in m.__dataclass_fields__},
        }


@lru_cache(maxsize=128)
def _build_event_context_cached(st, game_mode, rule_set, network_game, formula, equal, parc,
                                damage, damage_rate, cutting, safety, red, low_fuel, regulations_2026) -> EventContext:
    profile = session_profile(st)

    race = profile == "race"
    tt = profile == "time_trial"
    practice = profile == "practice"
    qualifying = profile == "qualifying"
    session_with_resource_management = practice or qualifying or race

    # Zero is EA's disabled/off value for the boolean-like rule controls we gate.
    # Unknown values stay disabled here: raw telemetry is still preserved, but we
    # do not activate a strategy/automatic rule without positive evidence.
    damage_enabled = damage is not None and damage != 0
    safety_enabled = race and safety is not None and safety != 0
    red_enabled = race and red is not None and red != 0

    # Parc ferme is not a useful setup lock in Time Trial, where EA explicitly
    # exposes custom setups/leaderboard setup loading. Practice is also the setup
    # development phase. In qualifying, respect the reported parc-ferme rule.
    if tt or practice:
        setup_change_advice = True
    elif qualifying:
        setup_change_advice = parc is False
    else:
        setup_change_advice = False

    regs_2026 = regulations_2026 is True
    legacy_regs = regulations_2026 is False

    if profile == "unknown":
        # Compatibility fallback while the Session packet is not available yet.
        # Do not reinterpret/drop explicit live telemetry merely because context is
        # temporarily unknown; once EA identifies the session, strict gating below
        # takes over.
        metrics = MetricApplicability(
            fuel_strategy=True, ers_energy_strategy=True, tyre_wear_strategy=True,
            race_position_strategy=True, traffic_gap_analysis=True, pit_strategy=True, pit_lane_guidance=True,
            penalty_monitoring=True, flag_monitoring=True, safety_car_strategy=True,
            red_flag_strategy=True, weather_strategy=True, damage_strategy=True,
            setup_change_advice=True, active_aero_analysis=True, overtake_analysis=True,
            legacy_drs_analysis=True,
        )
    else:
        metrics = MetricApplicability(
            fuel_strategy=session_with_resource_management,
            ers_energy_strategy=session_with_resource_management,
            tyre_wear_strategy=session_with_resource_management,
            race_position_strategy=race,
            traffic_gap_analysis=practice or qualifying or race,
            pit_strategy=race,
            pit_lane_guidance=practice or qualifying or race,
            penalty_monitoring=qualifying or race,
            flag_monitoring=practice or qualifying or race,
            safety_car_strategy=safety_enabled,
            red_flag_strategy=red_enabled,
            weather_strategy=session_with_resource_management,
            damage_strategy=session_with_resource_management and damage_enabled,
            setup_change_advice=setup_change_advice,
            active_aero_analysis=regs_2026,
            overtake_analysis=regs_2026,
            legacy_drs_analysis=legacy_regs,
        )

    return EventContext(
        profile=profile,
        session_type=st,
        game_mode=game_mode,
        rule_set=rule_set,
        network_game=network_game,
        formula=formula,
        regulations_2026=regulations_2026,
        equal_car_performance=equal,
        parc_ferme_rules=parc,
        car_damage=damage,
        car_damage_rate=damage_rate,
        corner_cutting_stringency=cutting,
        safety_car_setting=safety,
        red_flags_setting=red,
        low_fuel_mode=low_fuel,
        metrics=metrics,
    )


def build_event_context(state) -> EventContext:
    """Return a cached immutable context for the current session/rule signature."""
    s = getattr(state, "session", None)
    st = _raw_enum(getattr(s, "session_type", None)) if s is not None else None
    game_mode = getattr(s, "game_mode", None) if s is not None else None
    rule_set = getattr(s, "rule_set", None) if s is not None else None
    network_game = getattr(s, "network_game", None) if s is not None else None
    formula = getattr(s, "formula", None) if s is not None else None
    equal = getattr(s, "equal_car_performance", None) if s is not None else None
    parc = getattr(s, "parc_ferme_rules", None) if s is not None else None
    damage = getattr(s, "car_damage", None) if s is not None else None
    damage_rate = getattr(s, "car_damage_rate", None) if s is not None else None
    cutting = getattr(s, "corner_cutting_stringency", None) if s is not None else None
    safety = getattr(s, "safety_car_setting", None) if s is not None else None
    red = getattr(s, "red_flags_setting", None) if s is not None else None
    low_fuel = getattr(s, "low_fuel_mode", None) if s is not None else None
    p = getattr(state, "player", None)
    regulations_2026 = getattr(getattr(p, "aero", None), "regulations_2026", None)
    return _build_event_context_cached(
        st, game_mode, rule_set, network_game, formula, equal, parc, damage,
        damage_rate, cutting, safety, red, low_fuel, regulations_2026,
    )
