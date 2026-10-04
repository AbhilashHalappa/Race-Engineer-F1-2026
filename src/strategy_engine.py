"""V0.9.16.1.1 deterministic race-strategy calculations.

Only uses facts already present in RaceState / measured completed laps.  Unknown
inputs remain unknown; the engine never invents pit-loss, rejoin or degradation
numbers that are not supported by telemetry.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import median
from .race_state.models import RaceState
from .event_context import build_event_context
from .pit_strategy import assess_pit, choose_tyre


def _enum_name(v):
    return getattr(v, "name", None) if v is not None else None


def _wheel_values(w):
    if w is None:
        return []
    return [x for x in (w.FL, w.FR, w.RL, w.RR) if x is not None]


def _laps_remaining(state: RaceState):
    c = state.player
    if c is None or c.lap.current_lap is None or state.session.total_laps is None:
        return None
    return max(0, int(state.session.total_laps) - int(c.lap.current_lap))


def _same_current_stint_laps(state: RaceState):
    c = state.player
    if c is None:
        return []
    idx = c.tyres.fitted_set_index
    laps = list(state.measured_laps)
    clean=[]
    for x in laps:
        if int(getattr(x, 'lap_number', 0) or 0) <= 1:
            continue
        if idx is not None and x.fitted_tyre_set_index != idx:
            continue
        if (getattr(x, 'pit_lap', False) or getattr(x, 'race_control_compromised', False) or
            getattr(x, 'damage_compromised', False) or getattr(x, 'tyre_set_changed', False)):
            continue
        clean.append(x)
    return clean[-8:]


def _wear_rate(state: RaceState):
    """Return robust maximum-wheel wear rate, percentage points per completed lap."""
    rates = []
    for lap in _same_current_stint_laps(state):
        vals = _wheel_values(lap.tyre_wear_delta)
        if not vals:
            continue
        # Negative values can occur around set changes / packet ordering; never
        # treat them as tyre regeneration.
        positive = [float(v) for v in vals if v is not None and float(v) >= 0.0]
        if positive:
            rates.append(max(positive))
    if len(rates) < 2:
        return None
    return round(float(median(rates[-5:])), 3)


def _gap_trend(state: RaceState):
    """Return (change, basis). Negative means the gap is closing.

    Prefer sane completed-lap deltas. Otherwise use a robust rolling 1 Hz trend
    over a stable same-opponent window. Discontinuous or internally inconsistent
    samples are rejected rather than converted into misleading radio numbers.
    """
    vals = [float(x.gap_ahead_change_s) for x in state.measured_laps[-4:]
            if x.gap_ahead_change_s is not None and abs(float(x.gap_ahead_change_s)) <= 5.0]
    if vals:
        return round(float(median(vals[-3:])), 3), 'lap'

    samples = list(state.extended.get('_strategy_gap_samples', ()) or ())
    if len(samples) < 5:
        return None, None
    latest_t, _, latest_ahead = samples[-1]
    same = [x for x in samples if x[2] == latest_ahead and 0.0 <= latest_t - x[0] <= 20.0]
    if len(same) < 5:
        return None, None
    span = float(same[-1][0]) - float(same[0][0])
    if span < 4.0:
        return None, None

    slopes = []
    for left, right in zip(same, same[1:]):
        dt = float(right[0]) - float(left[0])
        if dt < 0.5 or dt > 3.0:
            continue
        slope = (float(right[1]) - float(left[1])) / dt
        # More than 0.5 s of gap change per second is treated as an incident/
        # discontinuity, not normal comparable pace.
        if abs(slope) > 0.5:
            # One teleport-like pair invalidates the entire rolling window.
            return None, None
        slopes.append(slope)
    if len(slopes) < 3:
        return None, None

    med = float(median(slopes))
    deviations = [abs(x - med) for x in slopes]
    mad = float(median(deviations)) if deviations else 0.0
    # Require directional agreement as well as low dispersion. Alternating
    # opening/closing samples are noise, not a useful race-pace trend.
    if abs(med) > 0.02:
        same_direction = sum(1 for x in slopes if (x < 0) == (med < 0))
        if same_direction / len(slopes) < 0.75:
            return None, None
    if mad > 0.15:
        return None, None
    change_10s = med * 10.0
    if abs(change_10s) > 5.0:
        return None, None
    return round(change_10s, 3), '10s'


def _stint_pace(state: RaceState):
    c = state.player
    if c is None:
        return None, None, None
    groups = {}
    order = []
    for lap in state.measured_laps:
        if lap.lap_time_s is None or lap.fitted_tyre_set_index is None:
            continue
        idx = lap.fitted_tyre_set_index
        if idx not in groups:
            groups[idx] = []
            order.append(idx)
        groups[idx].append(float(lap.lap_time_s))
    cur = c.tyres.fitted_set_index
    if cur is None or cur not in groups or not groups[cur]:
        return None, None, None
    current_avg = sum(groups[cur][-3:]) / len(groups[cur][-3:])
    prior_candidates = [idx for idx in order if idx != cur and groups.get(idx)]
    if not prior_candidates:
        return round(current_avg, 3), None, None
    prior = prior_candidates[-1]
    prior_avg = sum(groups[prior][-3:]) / len(groups[prior][-3:])
    return round(current_avg, 3), round(prior_avg, 3), round(current_avg - prior_avg, 3)


@dataclass(frozen=True, slots=True)
class StrategyAssessment:
    applicable: bool
    laps_remaining: int | None
    fuel_margin_laps: float | None
    fuel_to_finish: str
    max_tyre_wear_percent: float | None
    tyre_wear_rate_pct_per_lap: float | None
    projected_finish_wear_percent: float | None
    laps_to_80_percent: float | None
    laps_to_90_percent: float | None
    tyres_can_finish: bool | None
    tyre_life_reason: str
    recommended_tyre: str | None
    recommended_tyre_set: int | None
    replacement_can_cover_finish: bool | None
    replacement_usable_life_laps: int | None
    gap_ahead_s: float | None
    gap_ahead_change_s_per_lap: float | None
    gap_trend_basis: str | None
    gap_trend: str
    current_stint_avg_lap_s: float | None
    previous_stint_avg_lap_s: float | None
    stint_delta_s: float | None
    safety_car: str | None
    safety_car_pit_opportunity: bool | None
    pit_recommendation: str
    pit_reason: str
    serve_penalty_in_pit: bool | None
    rejoin_projection_available: bool
    rejoin_reason: str
    undercut_projection_available: bool
    undercut_reason: str

    def to_dict(self):
        return asdict(self)


def assess_strategy(state: RaceState) -> StrategyAssessment:
    ctx = build_event_context(state)
    c = state.player
    pit = assess_pit(state)
    if c is None or not ctx.metrics.pit_strategy:
        label = ctx.profile.replace("_", " ")
        return StrategyAssessment(
            False, None, None, "unavailable", None, None, None, None, None, None,
            f"race strategy is not applicable in {label}", None, None, None, None,
            None, None, None, "unavailable", None, None, None, _enum_name(state.session.safety_car),
            None, pit.recommendation_hint, pit.reasons[0] if pit.reasons else "insufficient data",
            pit.serve_penalty_in_pit, False,
            "no factual pit-loss/rejoin model is available from telemetry",
            False, "no factual pit-loss and post-stop pace model is available from telemetry")

    laps = _laps_remaining(state)
    fuel = c.fuel.remaining_laps
    if fuel is None:
        fuel_state = "unavailable"
    elif fuel < 0:
        fuel_state = "short"
    elif fuel < 0.5:
        fuel_state = "tight"
    else:
        fuel_state = "safe"

    wear_vals = _wheel_values(c.tyres.wear_percent)
    max_wear = max(wear_vals) if wear_vals else None
    rate = _wear_rate(state)
    projected = None
    to80 = to90 = None
    can_finish = None
    tyre_reason = "tyre wear projection unavailable"
    if max_wear is not None and rate is not None and rate > 0:
        if laps is not None:
            projected = round(float(max_wear) + rate * laps, 1)
            can_finish = projected < 90.0
            tyre_reason = (f"projected maximum wear {projected:.1f} percent at the finish "
                           f"from {rate:.2f} percent per lap measured wear")
        to80 = round(max(0.0, (80.0 - float(max_wear)) / rate), 1)
        to90 = round(max(0.0, (90.0 - float(max_wear)) / rate), 1)
    elif max_wear is not None and laps == 0:
        projected = float(max_wear); can_finish = True; tyre_reason = "race distance is complete"

    choice = choose_tyre(state)
    usable = None
    replacement_cover = None
    if choice.available and laps is not None:
        ts = next((x for x in c.tyres.sets if x.index == choice.set_index), None)
        if ts is not None:
            usable = ts.usable_life_laps
            if usable is not None:
                replacement_cover = int(usable) >= int(laps)

    gap_change, gap_basis = _gap_trend(state)
    if gap_change is None:
        gap_desc = "unavailable"
    elif gap_change < -0.05:
        gap_desc = "closing"
    elif gap_change > 0.05:
        gap_desc = "opening"
    else:
        gap_desc = "stable"

    cur_pace, prev_pace, stint_delta = _stint_pace(state)
    sc = _enum_name(state.session.safety_car)
    scn = (sc or "").lower().replace("_", " ")
    neutral = bool(scn and scn not in {"none", "no safety car", "invalid"}
                   and ("safety" in scn or "virtual" in scn or "vsc" in scn))
    sc_opportunity = None
    if state.session.safety_car is not None:
        # We deliberately do not invent a time saving. This flag only says a
        # neutralisation exists while the deterministic pit engine has a
        # service reason / useful replacement available.
        sc_opportunity = bool(neutral and pit.recommendation_hint in
                              {"box_now", "box_soon", "consider_box"})

    reason = pit.reasons[0] if pit.reasons else "no immediate serviceable pit trigger"
    return StrategyAssessment(
        True, laps, round(float(fuel), 2) if fuel is not None else None, fuel_state,
        round(float(max_wear), 1) if max_wear is not None else None, rate, projected,
        to80, to90, can_finish, tyre_reason,
        choice.compound if choice.available else None,
        choice.set_index if choice.available else None,
        replacement_cover, usable,
        c.lap.gap_to_car_in_front_s, gap_change, gap_basis, gap_desc,
        cur_pace, prev_pace, stint_delta, sc, sc_opportunity,
        pit.recommendation_hint, reason, pit.serve_penalty_in_pit,
        False, "pit-loss/rejoin time is not supplied by the game telemetry and has not been measured in this session",
        False, "undercut gain cannot be quantified without a factual pit-loss and post-stop pace delta")


def format_strategy_summary(state: RaceState) -> str:
    a = assess_strategy(state)
    if not a.applicable:
        return a.tyre_life_reason.capitalize() + "."
    parts = []
    if a.pit_recommendation == "box_now": parts.append("Box this lap")
    elif a.pit_recommendation == "box_soon": parts.append("Box soon")
    elif a.pit_recommendation == "consider_box": parts.append("Consider boxing")
    else: parts.append("Stay out for now")
    if a.laps_remaining is not None: parts.append(f"{a.laps_remaining} laps remaining")
    if a.fuel_margin_laps is not None: parts.append(f"fuel margin {a.fuel_margin_laps:.1f} laps")
    if a.projected_finish_wear_percent is not None:
        parts.append(f"projected tyre wear {a.projected_finish_wear_percent:.0f} percent at finish")
    if a.gap_ahead_change_s_per_lap is not None:
        unit = "per lap" if a.gap_trend_basis == "lap" else "per 10 seconds"
        parts.append(f"gap ahead {a.gap_trend} by {abs(a.gap_ahead_change_s_per_lap):.2f} seconds {unit}")
    return ". ".join(parts) + "."


def format_tyre_life(state: RaceState) -> str:
    a = assess_strategy(state)
    if not a.applicable:
        return a.tyre_life_reason.capitalize() + "."
    if a.tyres_can_finish is True:
        return f"Tyres should make the finish. {a.tyre_life_reason.capitalize()}."
    if a.tyres_can_finish is False:
        return f"Tyres are projected past 90 percent wear before the finish. {a.tyre_life_reason.capitalize()}."
    return "I don't have enough completed-lap tyre wear data to project tyre life yet."


def format_fuel_to_finish(state: RaceState) -> str:
    a = assess_strategy(state)
    if a.fuel_margin_laps is None:
        return "Fuel-to-finish margin unavailable."
    if a.fuel_margin_laps < 0:
        return f"Fuel is short by {-a.fuel_margin_laps:.1f} laps on the game's estimate."
    if a.fuel_margin_laps < 0.5:
        return f"Fuel is tight. Margin {a.fuel_margin_laps:.1f} laps."
    return f"Fuel margin {a.fuel_margin_laps:.1f} laps."


def format_gap_trend(state: RaceState) -> str:
    a = assess_strategy(state)
    if a.gap_ahead_change_s_per_lap is None:
        return "Gap trend unavailable; I need a few seconds of continuous gap data."
    change = abs(a.gap_ahead_change_s_per_lap)
    unit = "per lap" if a.gap_trend_basis == "lap" else "per 10 seconds"
    if a.gap_trend == "closing": return f"Gap ahead is closing by about {change:.2f} seconds {unit}."
    if a.gap_trend == "opening": return f"Gap ahead is opening by about {change:.2f} seconds {unit}."
    return "Gap ahead is stable over the measured window."


def format_stint_compare(state: RaceState) -> str:
    a = assess_strategy(state)
    if a.current_stint_avg_lap_s is None:
        return "Current stint pace comparison unavailable."
    if a.previous_stint_avg_lap_s is None:
        return f"Current stint measured pace averages {a.current_stint_avg_lap_s:.3f} seconds; no previous stint is available."
    d = a.stint_delta_s or 0.0
    if abs(d) < 0.05:
        return "Current and previous stint measured pace are effectively equal."
    return (f"Current stint is {abs(d):.3f} seconds per lap "
            f"{'slower' if d > 0 else 'faster'} than the previous measured stint.")


def format_rejoin_traffic(state: RaceState) -> str:
    a = assess_strategy(state)
    # Do not guess a rejoin position from current gaps alone. The missing variable
    # is track/session-specific pit loss, which is not present in RaceState.
    return "I can't reliably project rejoin traffic yet; no factual pit-loss estimate is available."


def format_undercut(state: RaceState) -> str:
    a = assess_strategy(state)
    trend = ""
    if a.gap_ahead_change_s_per_lap is not None:
        unit = "per lap" if a.gap_trend_basis == "lap" else "per 10 seconds"
        trend = f" Current gap trend is {a.gap_trend} by {abs(a.gap_ahead_change_s_per_lap):.2f} seconds {unit}."
    return "I can't quantify an undercut yet without a factual pit-loss and post-stop pace delta." + trend


def format_safety_car_pit(state: RaceState) -> str:
    a = assess_strategy(state)
    if not a.applicable:
        return "Safety Car pit strategy is not applicable in this session."
    sc = (a.safety_car or "").lower()
    active = bool(sc and sc not in {"none", "no safety car", "invalid"}
                  and ("safety" in sc or "virtual" in sc or "vsc" in sc))
    if not active:
        return "No Safety Car or VSC is active."
    if a.safety_car_pit_opportunity:
        return f"Neutralisation is active and the pit engine says {a.pit_recommendation.replace('_', ' ')}. {a.pit_reason.capitalize()}."
    return "Neutralisation is active, but there is no current deterministic service trigger."
