"""V0.8.9 exhaustive factual telemetry view.

Only direct EA values, arithmetic on those values, and historical comparisons of
already-observed samples are exposed.  This module deliberately contains no
future extrapolation, probability, strategy recommendation, or learned model.
"""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
import math
from .race_state.models import RaceState, Wheels
from .deterministic_math import snapshot as math_snapshot
from .event_context import build_event_context

WHEEL_NAMES=('FL','FR','RL','RR')
def _finite(v): return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def _wheel_dict(w): return None if w is None else {k:getattr(w,k) for k in WHEEL_NAMES}
def _stats(w):
    if w is None: return None
    vals=[getattr(w,k) for k in WHEEL_NAMES]
    if not all(_finite(v) for v in vals): return None
    return {'min':min(vals),'max':max(vals),'average':sum(vals)/4,'spread':max(vals)-min(vals),
            'front_average':(vals[0]+vals[1])/2,'rear_average':(vals[2]+vals[3])/2,
            'front_minus_rear':(vals[0]+vals[1]-vals[2]-vals[3])/2,
            'left_minus_right':(vals[0]+vals[2]-vals[1]-vals[3])/2,
            'max_wheel':WHEEL_NAMES[max(range(4),key=lambda i: vals[i])],
            'min_wheel':WHEEL_NAMES[min(range(4),key=lambda i: vals[i])]}

def _safe(obj):
    if obj is None or isinstance(obj,(str,int,bool)): return obj
    if isinstance(obj,float): return obj if math.isfinite(obj) else None
    if isinstance(obj,(tuple,list)): return [_safe(x) for x in obj]
    if isinstance(obj,dict): return {str(k):_safe(v) for k,v in obj.items()}
    if hasattr(obj,'name') and hasattr(obj,'raw'): return {'name':obj.name,'raw':obj.raw}
    if is_dataclass(obj): return {k:_safe(v) for k,v in asdict(obj).items()}
    return str(obj)

def all_facts(state:RaceState)->dict:
    c=state.player
    ctx=build_event_context(state)
    out={'event_context':ctx.to_dict(),'math':math_snapshot(state),'session':{},'car':{},'historical':{},'extended_packets':{}}
    s=state.session
    out['session']={k:_safe(getattr(s,k)) for k in s.__dataclass_fields__}
    if c:
        out['car']={
          'identity':_safe(c.identity),'lap':_safe(c.lap),'telemetry':_safe(c.telemetry),
          'fuel':_safe(c.fuel),'energy':_safe(c.energy),'aero':_safe(c.aero),
          'tyres':_safe(c.tyres),'damage':_safe(c.damage)}
        wheels={'brake_temp':c.telemetry.brakes_temperature_c,'tyre_surface_temp':c.tyres.surface_temperature_c,
                'tyre_inner_temp':c.tyres.inner_temperature_c,'tyre_pressure':c.tyres.pressure_psi,
                'tyre_wear':c.tyres.wear_percent,'tyre_damage':c.tyres.damage_percent,
                'tyre_blisters':c.tyres.blisters_percent,'brake_damage':c.damage.brakes_percent}
        out['car']['four_corner_stats']={k:_stats(v) for k,v in wheels.items() if _stats(v) is not None}
        # Direct damage extrema across components supplied by the game.
        damage={k:v for k,v in _safe(c.damage).items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
        damage.update({f'engine_{k}':v for k,v in c.damage.engine_wear_percent.items()})
        if damage:
            out['car']['damage_extrema']={'maximum':max(damage.values()),'component':max(damage,key=damage.get)}
        sets=c.tyres.sets
        out['car']['tyre_inventory']={'total_sets':len(sets),'available_sets':sum(x.available is True for x in sets),
            'fitted_set_index':c.tyres.fitted_set_index}
    laps=list(state.measured_laps)
    out['historical']['completed_laps']=[_safe(x) for x in laps]
    if laps:
        times=[x.lap_time_s for x in laps if _finite(x.lap_time_s) and x.lap_time_s>0]
        fuels=[x.fuel_used for x in laps if _finite(x.fuel_used)] if ctx.metrics.fuel_strategy else []
        out['historical']['completed_lap_count']=len(laps)
        if times:
            out['historical'].update(best_observed_lap_s=min(times),worst_observed_lap_s=max(times),
                observed_lap_time_average_s=sum(times)/len(times),observed_lap_time_spread_s=max(times)-min(times))
            if len(times)>=2: out['historical']['last_lap_vs_previous_s']=times[-1]-times[-2]
        if fuels:
            out['historical'].update(last_completed_lap_fuel_used=fuels[-1],observed_fuel_used_average=sum(fuels)/len(fuels),
                                     observed_fuel_used_min=min(fuels),observed_fuel_used_max=max(fuels))
            if len(fuels)>=2: out['historical']['last_fuel_vs_previous']=fuels[-1]-fuels[-2]
    # Preserve every decoded extended packet field for factual/debug consumers.
    out['extended_packets']={k:_safe(v) for k,v in state.extended.items()}
    return out

def factual_radio_summary(state:RaceState)->str:
    f=all_facts(state); c=state.player
    if c is None: return 'Live car data is unavailable.'
    ctx=build_event_context(state); m=ctx.metrics
    p=[]
    if m.race_position_strategy and c.lap.position: p.append(f'P{c.lap.position}')
    if c.lap.previous_lap_time_s: p.append(f'last lap {c.lap.previous_lap_time_s:.3f}')
    math=f['math']
    if 'laps_remaining' in math: p.append(f"{math['laps_remaining']} laps left")
    if m.fuel_strategy and c.fuel.remaining_laps is not None: p.append(f'fuel {c.fuel.remaining_laps:.1f} laps')
    if m.tyre_wear_strategy and 'tyre_wear_maximum' in math: p.append(f"max wear {math['tyre_wear_maximum']:.0f} percent")
    if ctx.profile=='time_trial' and 'tt_session_best_s' in math: p.append(f"session best {math['tt_session_best_s']:.3f}")
    return '. '.join(p)+'.' if p else 'Live factual telemetry is available.'
