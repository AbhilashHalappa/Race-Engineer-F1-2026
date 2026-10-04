"""V1.3.8.1 deterministic advanced race strategy and coaching arbitration.

No outcome prediction is performed. Recommendations are conditional on measured
telemetry/history and expose missing evidence explicitly.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from statistics import median
from typing import Any, Iterable

from .engineer.models import EngineerMessage, Priority
from .race_context import assess_race_context

ERS_MAX_J = 4_000_000.0


def _n(v: Any) -> str:
    return str(getattr(v, 'name', v) or '').strip().lower().replace('_',' ')

def _num(v): return isinstance(v,(int,float)) and not isinstance(v,bool)

def _wheels(w):
    if w is None: return []
    return [float(v) for v in (getattr(w,'FL',None),getattr(w,'FR',None),getattr(w,'RL',None),getattr(w,'RR',None)) if _num(v)]

def _laps_remaining(state):
    total=getattr(getattr(state,'session',None),'total_laps',None)
    cur=getattr(getattr(getattr(state,'player',None),'lap',None),'current_lap',None)
    if _num(total) and _num(cur): return max(0,int(total)-int(cur)+1)
    return None

def _pit_loss(state):
    ext=getattr(state,'extended',{}) or {}
    vals=[]
    for key in ('_pit_cycle_samples_s','_track_pit_cycle_samples_s'):
        for x in ext.get(key,()) or ():
            if _num(x) and 3.0 < float(x) < 180.0: vals.append(float(x))
    if vals: return round(float(median(vals[-7:])),3), ('track_history' if ext.get('_track_pit_cycle_samples_s') else 'session_history')
    x=ext.get('measured_pit_cycle_s')
    if _num(x) and 3.0 < float(x) < 180.0: return round(float(x),3),'measured'
    return None,None

def _same_set_laps(state):
    rows=[x for x in (getattr(state,'measured_laps',()) or ()) if _num(getattr(x,'lap_time_s',None))]
    if len(rows)<2: return []
    latest=rows[-1].fitted_tyre_set_index
    return [x for x in rows if latest is not None and x.fitted_tyre_set_index==latest][-6:]

def _tyre_deg(state):
    rows=_same_set_laps(state); ds=[]
    for a,b in zip(rows,rows[1:]):
        d=float(b.lap_time_s)-float(a.lap_time_s)
        if -1.0 <= d <= 3.0: ds.append(d)
    return round(float(median(ds[-4:])),3) if ds else None

def _forecast(state):
    s=getattr(state,'session',None); fs=list(getattr(s,'forecast',()) or ())
    acc=_n(getattr(s,'forecast_accuracy',None)) or 'unknown'
    if not fs: return 'unavailable',acc,None
    fs=sorted(fs,key=lambda f:getattr(f,'offset_minutes',999))
    near=next((f for f in fs if getattr(f,'offset_minutes',999)<=10),fs[0])
    now=_n(getattr(s,'weather',None)); future=_n(getattr(near,'weather',None)); rain=getattr(near,'rain_percent',None)
    nw=any(k in now for k in ('rain','wet','storm'))
    fw=any(k in future for k in ('rain','wet','storm')) or (_num(rain) and float(rain)>=50)
    transition='dry_to_wet' if (not nw and fw) else 'wet_to_dry' if (nw and not fw) else ('stable_wet' if nw else 'stable_dry')
    return transition,acc,(int(rain) if _num(rain) else None)

def _service_need(state):
    p=getattr(state,'player',None)
    if p is None: return False
    wear=_wheels(getattr(getattr(p,'tyres',None),'wear_percent',None))
    dmg=getattr(p,'damage',None)
    wing=max([float(x) for x in (getattr(dmg,'front_left_wing_percent',None),getattr(dmg,'front_right_wing_percent',None)) if _num(x)] or [0])
    punct=any(bool(x) for x in _wheels(getattr(getattr(p,'tyres',None),'punctured',None)))
    return punct or (wear and max(wear)>=70) or wing>=25

def _opponent(state):
    idx=getattr(state,'ahead_index',None); car=getattr(state,'field',{}).get(idx) if idx is not None else None
    p=getattr(state,'player',None)
    if car is None or p is None: return 'unavailable',None
    a_age=getattr(car.tyres,'age_laps',None); p_age=getattr(p.tyres,'age_laps',None)
    a_comp=_n(getattr(car.tyres,'visual_compound',None)); p_comp=_n(getattr(p.tyres,'visual_compound',None))
    if _num(a_age) and _num(p_age):
        delta=int(a_age)-int(p_age)
        if delta>=3: return 'ahead_older_tyres',delta
        if delta<=-3: return 'ahead_newer_tyres',delta
    if a_comp and p_comp and a_comp!=p_comp: return f'ahead_{a_comp}_vs_{p_comp}',None
    return 'same_or_unknown_strategy',0

def _mandatory(state):
    ext=getattr(state,'extended',{}) or {}
    explicit=ext.get('mandatory_compound_status')
    if explicit is not None: return str(explicit)
    # Only apply generic two-dry-compound check when the session explicitly says race
    # and current conditions are dry. This is a warning, not a claim about every rule set.
    st=_n(getattr(getattr(state,'session',None),'session_type',None))
    weather=_n(getattr(getattr(state,'session',None),'weather',None))
    if 'race' not in st or any(k in weather for k in ('rain','wet','storm')): return 'not_applicable_or_unverified'
    used=set(str(x).lower() for x in (ext.get('_used_dry_compounds') or ()) if x)
    if len(used)>=2: return 'two_dry_compounds_observed'
    if len(used)==1: return 'only_one_dry_compound_observed'
    return 'unavailable'

@dataclass(frozen=True,slots=True)
class AdvancedStrategyAssessment:
    pit_loss_s: float|None; pit_loss_source: str|None
    tyre_degradation_s_per_lap: float|None
    projected_tyre_loss_next_5_laps_s: float|None
    fuel_margin_laps: float|None; fuel_target: str
    ers_percent: float|None; ers_end_projection_percent: float|None; ers_target: str
    damage_pace_loss_s: float|None; wing_damage_percent: float|None; wing_pit_threshold: str
    weather_transition: str; weather_confidence: str; rain_percent_10m: int|None; tyre_transition: str
    opponent_strategy: str; opponent_tyre_age_delta_laps: int|None
    undercut: str; overcut: str
    safety_car_pit: str; vsc_pit: str
    mandatory_compound_status: str; race_rule_status: str
    pit_window: str
    measured_sc_pit_loss_s: float|None = None
    measured_vsc_pit_loss_s: float|None = None
    game_pit_window_status: str = 'unavailable'
    game_pit_ideal_lap: int|None = None
    game_pit_latest_lap: int|None = None
    mandatory_compound_urgency: str = 'unavailable'
    measured_stop_sequence_effect: dict|None = None
    opponent_observed_event: dict|None = None
    missing_evidence: tuple[str,...] = ()
    def to_dict(self): return asdict(self)

def assess_advanced_strategy(state)->AdvancedStrategyAssessment:
    p=getattr(state,'player',None); missing=[]
    pit,psrc=_pit_loss(state)
    if pit is None: missing.append('circuit_pit_loss')
    deg=_tyre_deg(state)
    if deg is None: missing.append('same_set_lap_degradation')
    tyre5=round(max(0.0,deg)*5,3) if deg is not None else None
    laps_left=_laps_remaining(state)
    fuel_laps=getattr(getattr(p,'fuel',None),'remaining_laps',None) if p else None
    fuel_margin=round(float(fuel_laps)-float(laps_left),2) if _num(fuel_laps) and _num(laps_left) else None
    fuel_target='save' if fuel_margin is not None and fuel_margin < -0.2 else 'on_target' if fuel_margin is not None and fuel_margin<=0.5 else 'surplus' if fuel_margin is not None else 'unavailable'
    if fuel_margin is None: missing.append('fuel_to_finish')
    e=getattr(p,'energy',None) if p else None; store=getattr(e,'store_j',None); dep=getattr(e,'deployed_this_lap_j',None); harv=0.0
    for k in ('harvested_mguk_j','harvested_mguh_j'):
        v=getattr(e,k,None) if e else None
        if _num(v): harv+=float(v)
    ers_pct=round(float(store)/ERS_MAX_J*100,1) if _num(store) else None
    end=None; etarget='unavailable'
    if _num(store) and _num(laps_left) and _num(dep):
        end=max(0.0,min(100.0,(float(store)+(harv-float(dep))*float(laps_left))/ERS_MAX_J*100.0)); end=round(end,1)
        etarget='harvest_more' if end<10 else 'balanced' if end<60 else 'deployment_available'
    else: missing.append('ers_lap_balance')
    ext=getattr(state,'extended',{}) or {}; dpl=ext.get('measured_damage_pace_loss_s'); dpl=round(float(dpl),3) if _num(dpl) and float(dpl)>=0 else None
    dmg=getattr(p,'damage',None) if p else None; wing=max([float(x) for x in (getattr(dmg,'front_left_wing_percent',None),getattr(dmg,'front_right_wing_percent',None)) if _num(x)] or [0]) if dmg else None
    if dpl is None: missing.append('matched_damage_pace_loss')
    wing_thr='pit_consideration_supported' if dpl is not None and wing is not None and wing>=20 and dpl>=0.5 else 'stay_out_supported' if dpl is not None and dpl<0.5 else 'unavailable'
    wt,wconf,rain=_forecast(state)
    tyre_trans='consider_wet_or_intermediate' if wt=='dry_to_wet' and rain is not None and rain>=50 else 'consider_dry' if wt=='wet_to_dry' else 'no_transition_trigger'
    opp,age_delta=_opponent(state)
    gap=getattr(getattr(p,'lap',None),'gap_to_car_in_front_s',None) if p else None
    under='unavailable'; over='unavailable'
    if pit is not None and _num(gap):
        advantage=max(0.0,deg or 0.0)
        under='consider' if (advantage>=0.15 and float(gap)<=pit+2.0) else 'no_trigger'
        over='consider' if (age_delta is not None and age_delta<=-3 and advantage<=0.10) else 'no_trigger'
    sc=_n(getattr(getattr(state,'session',None),'safety_car',None)); need=_service_need(state)
    vsc=('virtual' in sc or 'vsc' in sc); full=('safety' in sc and not vsc)
    scp='consider' if full and need else 'active_no_service_trigger' if full else 'inactive'
    vscp='consider' if vsc and need else 'active_no_service_trigger' if vsc else 'inactive'
    mandatory=_mandatory(state)
    rule='penalty_service_required' if p and ((getattr(p.lap,'unserved_drive_through',0) or 0)>0 or (getattr(p.lap,'unserved_stop_go',0) or 0)>0) else 'no_known_service_penalty'
    pitwindow='immediate_service' if need and (full or vsc) else 'consider_stop' if need else 'stay_out_no_service_trigger'
    def med(key):
        vals=[float(x) for x in (ext.get(key) or ()) if _num(x) and 0<float(x)<180]
        return round(float(median(vals[-7:])),3) if vals else None
    sc_loss=med('_sc_pit_cycle_samples_s') or med('_track_sc_pit_cycle_samples_s')
    vsc_loss=med('_vsc_pit_cycle_samples_s') or med('_track_vsc_pit_cycle_samples_s')
    cur=getattr(getattr(p,'lap',None),'current_lap',None) if p else None
    ideal=getattr(getattr(state,'session',None),'pit_stop_window_ideal_lap',None)
    latest=getattr(getattr(state,'session',None),'pit_stop_window_latest_lap',None)
    if _num(cur) and _num(latest) and int(cur)>=int(latest): game_window='latest_or_later'
    elif _num(cur) and _num(ideal) and int(cur)>=int(ideal): game_window='open'
    elif _num(cur) and _num(ideal): game_window='before_ideal'
    else: game_window='unavailable'
    mandatory_urgency='unavailable'
    if mandatory=='two_dry_compounds_observed': mandatory_urgency='satisfied'
    elif mandatory=='only_one_dry_compound_observed' and _num(laps_left):
        mandatory_urgency='box_required_soon' if int(laps_left)<=3 else 'pending'
    stop_effect=ext.get('measured_stop_sequence_effect') if isinstance(ext.get('measured_stop_sequence_effect'),dict) else None
    opp_event=ext.get('opponent_strategy_inference') if isinstance(ext.get('opponent_strategy_inference'),dict) else None
    return AdvancedStrategyAssessment(pit,psrc,deg,tyre5,fuel_margin,fuel_target,ers_pct,end,etarget,dpl,wing,wing_thr,wt,wconf,rain,tyre_trans,opp,age_delta,under,over,scp,vscp,mandatory,rule,pitwindow,sc_loss,vsc_loss,game_window,int(ideal) if _num(ideal) else None,int(latest) if _num(latest) else None,mandatory_urgency,stop_effect,opp_event,tuple(dict.fromkeys(missing)))

@dataclass(frozen=True,slots=True)
class ArbitrationResult:
    context: dict
    accepted: tuple[EngineerMessage,...]
    suppressed_keys: tuple[str,...]
    race_exit_message: EngineerMessage|None
    resume_message: EngineerMessage|None

def arbitrate_messages(messages: Iterable[EngineerMessage], state, *, previous_level: str|None=None, now: float=0.0, context=None)->ArbitrationResult:
    ctx=context if context is not None else assess_race_context(state)
    accepted=[]; suppressed=[]
    for m in messages:
        is_tech=(m.priority==Priority.COACHING or str(m.key).startswith(('coach:','corner:')))
        if is_tech and not ctx.technique_coaching_allowed:
            suppressed.append(m.key); continue
        if is_tech and ctx.technique_coaching_allowed and ctx.adaptations:
            text=m.text
            suffix=[]
            if 'tyre_conservation' in ctx.adaptations: suffix.append('protect the tyres')
            if 'fuel_save' in ctx.adaptations: suffix.append('save fuel on exit')
            if 'ers_conservation' in ctx.adaptations: suffix.append('ERS is low')
            if 'damage_aware' in ctx.adaptations:
                # V1.3.8.1: do not decorate every CORNER COACH line merely because
                # moderate damage exists.  The user's DMG COACH override is intended
                # to keep coaching active on damaged laps, not to turn damage into a
                # universal diagnosis.  Only mention damage when we have measured
                # damage pace-loss evidence and the current message is otherwise a
                # generic loss/advice line.  Matched/gained corners and messages with
                # a specific technique diagnosis keep that diagnosis clean.
                ext = getattr(state, 'extended', {}) or {}
                dpl = ext.get('measured_damage_pace_loss_s')
                t = str(text or '').lower()
                positive_or_matched = any(k in t for k in ('matched the reference', 'gained ', 'gain '))
                specific_diagnosis = any(k in t for k in (
                    'throttle pickup', 'brake', 'braking', 'coast', 'coasting',
                    'steer', 'steering', 'apex', 'minimum speed', 'entry speed',
                    'exit speed', 'gear ', 'lift', 'traction',
                ))
                measured_damage_cost = _num(dpl) and float(dpl) >= 0.50
                if measured_damage_cost and not positive_or_matched and not specific_diagnosis:
                    suffix.append('damage is costing pace')
            if 'wet_weather' in ctx.adaptations: suffix.append('prioritize traction in the wet')
            if suffix:
                text=f"{text.rstrip('.')} — {', '.join(suffix)}."
                m=EngineerMessage(m.key,m.priority,text,m.created_at,m.session_time_s,m.deadline_at_monotonic_s,m.estimated_duration_s,m.speak)
        accepted.append(m)
    exit_msg=None; resume=None
    if ctx.level=='combat' and previous_level!='combat':
        exit_msg=EngineerMessage('race_context:combat_exit',Priority.STRATEGY,'Car close. Prioritize the exit and traction.',now,getattr(getattr(state,'session',None),'session_time_s',None))
        accepted.insert(0,exit_msg)
    if ctx.level=='performance' and previous_level in {'combat','critical','race_control'}:
        resume=EngineerMessage('race_context:resume',Priority.INFORMATION,'Clear again. Performance coaching resumed.',now,getattr(getattr(state,'session',None),'session_time_s',None))
        accepted.append(resume)
    return ArbitrationResult(ctx.to_dict(),tuple(accepted),tuple(suppressed),exit_msg,resume)
