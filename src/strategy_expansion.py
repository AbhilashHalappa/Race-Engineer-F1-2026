"""Measured-only strategy expansion for V1.3.6.0.

The engine exposes additional race decisions only when the required telemetry or
session measurements exist.  Unknown inputs stay unknown.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from statistics import median
from typing import Any
from .strategy_engine import assess_strategy


def _name(v: Any) -> str:
    return str(getattr(v, 'name', v) or '').lower().replace('_',' ')


def _valid_numbers(values):
    return [float(x) for x in (values or ()) if isinstance(x,(int,float)) and 0.0 <= float(x) <= 180.0]


@dataclass(frozen=True, slots=True)
class ExpandedStrategy:
    pit_cycle_time_s: float | None
    pit_cycle_source: str | None
    rejoin_gap_margin_s: float | None
    rejoin_projection: str
    undercut_opportunity: str
    safety_car_opportunity: str
    vsc_opportunity: str
    tyre_degradation_s_per_lap: float | None
    fuel_margin_laps: float | None
    ers_percent: float | None
    weather_transition: str
    weather_confidence: str
    damage_pace_loss_s: float | None
    wing_pit_threshold_available: bool
    mandatory_compound_status: str

    def to_dict(self): return asdict(self)


def _measured_pit_cycle(state):
    vals = _valid_numbers(getattr(state, 'extended', {}).get('_pit_cycle_samples_s'))
    if len(vals) >= 2:
        return round(float(median(vals[-3:])), 3), 'session_median'
    val = getattr(state, 'extended', {}).get('measured_pit_cycle_s')
    if isinstance(val,(int,float)) and 0 < float(val) <= 180:
        return round(float(val),3), 'session_measurement'
    return None, None


def _tyre_deg(state):
    rows=[]
    laps=list(getattr(state,'measured_laps',()) or ())
    # Compare consecutive same-set completed lap times only. This is deliberately
    # descriptive; it does not claim tyre wear caused the delta.
    for a,b in zip(laps,laps[1:]):
        if a.fitted_tyre_set_index is None or a.fitted_tyre_set_index != b.fitted_tyre_set_index: continue
        if not isinstance(a.lap_time_s,(int,float)) or not isinstance(b.lap_time_s,(int,float)): continue
        d=float(b.lap_time_s)-float(a.lap_time_s)
        if abs(d)<=3.0: rows.append(d)
    return round(float(median(rows[-4:])),3) if rows else None


def _weather(state):
    s=getattr(state,'session',None)
    now=_name(getattr(s,'weather',None))
    forecasts=tuple(getattr(s,'forecast',()) or ())
    near=next((f for f in forecasts if getattr(f,'offset_minutes',99) <= 10),None)
    accuracy=_name(getattr(s,'forecast_accuracy',None)) or 'unknown'
    if near is None: return 'unavailable', accuracy
    future=_name(getattr(near,'weather',None)); rain=getattr(near,'rain_percent',None)
    now_wet=any(k in now for k in ('rain','wet','storm'))
    future_wet=any(k in future for k in ('rain','wet','storm')) or (isinstance(rain,(int,float)) and float(rain)>=50)
    if not now_wet and future_wet: return 'dry_to_wet', accuracy
    if now_wet and not future_wet: return 'wet_to_dry', accuracy
    return 'stable_wet' if now_wet else 'stable_dry', accuracy


def assess_expanded_strategy(state) -> ExpandedStrategy:
    base=assess_strategy(state)
    player=getattr(state,'player',None)
    pit_cycle,pit_source=_measured_pit_cycle(state)
    gap=getattr(getattr(player,'lap',None),'gap_to_car_in_front_s',None) if player else None
    rejoin_margin=None; rejoin='unavailable'
    if pit_cycle is not None and isinstance(gap,(int,float)):
        # This is a gap-vs-measured-pit-cycle margin, not a predicted position.
        rejoin_margin=round(float(gap)-pit_cycle,3)
        rejoin='clear_margin' if rejoin_margin>1.0 else ('borderline' if rejoin_margin>=-1.0 else 'traffic_risk')
    undercut='unavailable'
    if pit_cycle is not None and isinstance(base.stint_delta_s,(int,float)) and isinstance(gap,(int,float)):
        # Factual opportunity classification only; no winner/outcome prediction.
        if float(base.stint_delta_s)>0.15 and float(gap)<pit_cycle+3.0: undercut='measured_conditions_support_consideration'
        else: undercut='no_measured_trigger'
    sc=_name(getattr(getattr(state,'session',None),'safety_car',None))
    sc_opp='active_consider' if ('safety' in sc and 'virtual' not in sc and base.safety_car_pit_opportunity) else ('active_no_trigger' if 'safety' in sc and 'virtual' not in sc else 'inactive')
    vsc_active=('virtual' in sc or 'vsc' in sc)
    vsc_opp='active_consider' if (vsc_active and base.safety_car_pit_opportunity) else ('active_no_trigger' if vsc_active else 'inactive')
    ers=getattr(getattr(player,'energy',None),'store_j',None) if player else None
    ers_pct=round(max(0.0,min(100.0,float(ers)/4_000_000.0*100.0)),1) if isinstance(ers,(int,float)) else None
    weather,confidence=_weather(state)
    pace_loss=getattr(state,'extended',{}).get('measured_damage_pace_loss_s')
    if not isinstance(pace_loss,(int,float)) or float(pace_loss)<0: pace_loss=None
    mandatory=getattr(state,'extended',{}).get('mandatory_compound_status')
    mandatory=str(mandatory) if mandatory is not None else 'unavailable'
    return ExpandedStrategy(
        pit_cycle, pit_source, rejoin_margin, rejoin, undercut, sc_opp, vsc_opp,
        _tyre_deg(state), base.fuel_margin_laps, ers_pct, weather, confidence,
        round(float(pace_loss),3) if pace_loss is not None else None,
        pace_loss is not None, mandatory,
    )

def format_rejoin_projection(state):
    a=assess_expanded_strategy(state)
    if a.pit_cycle_time_s is None:
        return "Rejoin projection needs a measured pit-loss/pit-cycle sample from this track and session context."
    if a.rejoin_gap_margin_s is None:
        return f"Measured pit cycle is {a.pit_cycle_time_s:.1f} seconds. Current comparable gap data is unavailable."
    if a.rejoin_projection=='clear_margin':
        return f"Measured pit cycle {a.pit_cycle_time_s:.1f} seconds. Current gap margin is {a.rejoin_gap_margin_s:.1f} seconds clear of that cycle."
    if a.rejoin_projection=='borderline':
        return f"Measured pit cycle {a.pit_cycle_time_s:.1f} seconds. Current gap is within about one second of that cycle."
    return f"Measured pit cycle {a.pit_cycle_time_s:.1f} seconds. Current gap is {abs(a.rejoin_gap_margin_s):.1f} seconds inside that cycle, so traffic risk is present."


def format_undercut_projection(state):
    a=assess_expanded_strategy(state)
    if a.undercut_opportunity=='unavailable':
        return "Undercut assessment needs a measured pit-loss/pit-cycle sample, current gap, and comparable stint pace."
    if a.undercut_opportunity=='measured_conditions_support_consideration':
        return "Measured gap, pit-cycle and stint-pace conditions support considering an undercut."
    return "No measured undercut trigger is present right now."


def format_neutralisation_strategy(state):
    a=assess_expanded_strategy(state)
    if a.vsc_opportunity.startswith('active'):
        return "VSC is active. " + ("Measured pit conditions support considering a stop." if a.vsc_opportunity=='active_consider' else "No deterministic service trigger is active.")
    if a.safety_car_opportunity.startswith('active'):
        return "Safety Car is active. " + ("Measured pit conditions support considering a stop." if a.safety_car_opportunity=='active_consider' else "No deterministic service trigger is active.")
    return "No Safety Car or VSC is active."
