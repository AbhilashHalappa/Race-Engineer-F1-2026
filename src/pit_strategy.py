"""V0.8.6 offline-first deterministic pit decision engine.

Pit recommendations never require an LLM.  The engine evaluates every pit-relevant
field currently represented by RaceState and combines serviceable car condition,
weather/compound suitability, race distance, neutralisation, penalties, fuel and
nearby gaps.  Unknown inputs stay unknown; no pit-loss/rejoin/degradation values are
invented.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from .race_state.models import RaceState
from .event_context import build_event_context


def _name(v): return getattr(v, "name", None) if v is not None else None
def _vals(w): return [] if w is None else [x for x in (w.FL,w.FR,w.RL,w.RR) if x is not None]
def _neutral(name):
    n=(name or "").lower().replace("_"," ")
    return n not in ("","none","no safety car","invalid") and ("safety" in n or "virtual" in n or "vsc" in n)
def _wet_weather(name, rain=None):
    n=(name or "").lower()
    return any(x in n for x in ("rain","wet","storm","heavy")) or (rain is not None and rain >= 50)
def _wet_tyre(name):
    n=(name or "").lower()
    return "intermediate" in n or "wet" in n

def _best_reason(reasons):
    return reasons[0] if reasons else "current race conditions"

@dataclass(frozen=True, slots=True)
class PitAssessment:
    data_sufficient: bool
    urgency: str
    recommendation_hint: str
    confidence: str
    reasons: tuple[str,...]
    factors_checked: tuple[str,...]
    missing_factors: tuple[str,...]
    laps_remaining: int|None
    tyre_age_laps: int|None
    max_wear_percent: float|None
    average_wear_percent: float|None
    max_tyre_damage_percent: float|None
    max_tyre_temp_c: float|None
    front_wing_damage_percent: int|None
    rear_wing_damage_percent: int|None
    floor_damage_percent: int|None
    current_compound: str|None
    available_sets: tuple[dict,...]
    safety_car: str|None
    current_weather: str|None
    forecast: tuple[dict,...]
    fuel_remaining_laps: float|None
    fuel_margin_laps: float|None
    gap_ahead_s: float|None
    gap_behind_s: float|None
    pit_status: str|None
    penalties_s: int|None
    serve_penalty_in_pit: bool|None
    decision_score: int = 0
    serviceable_trigger: bool = False
    nonserviceable_warnings: tuple[str,...] = ()
    def to_dict(self): return asdict(self)


def assess_pit(state: RaceState) -> PitAssessment:
    c,s=state.player,state.session
    ctx=build_event_context(state)
    if not ctx.metrics.pit_strategy:
        label=ctx.profile.replace('_',' ')
        return PitAssessment(
            data_sufficient=False, urgency="not_applicable", recommendation_hint="not_applicable", confidence="high",
            reasons=(f"race pit strategy is not applicable in {label}",), factors_checked=(), missing_factors=(),
            laps_remaining=None, tyre_age_laps=None, max_wear_percent=None, average_wear_percent=None,
            max_tyre_damage_percent=None, max_tyre_temp_c=None, front_wing_damage_percent=None,
            rear_wing_damage_percent=None, floor_damage_percent=None, current_compound=None, available_sets=(),
            safety_car=_name(s.safety_car), current_weather=_name(s.weather), forecast=(),
            fuel_remaining_laps=None, fuel_margin_laps=None, gap_ahead_s=None, gap_behind_s=None, pit_status=None,
            penalties_s=None, serve_penalty_in_pit=None)
    if c is None:
        return PitAssessment(False,"unknown","insufficient_data","low",("live car data unavailable",),(),("live car data",),None,None,None,None,None,None,None,None,None,(),_name(s.safety_car),_name(s.weather),(),None,None,None,None,None,None,None,None)

    checked=[]; missing=[]; reasons=[]; warnings=[]
    wear=_vals(c.tyres.wear_percent); tdamage=_vals(c.tyres.damage_percent); temps=_vals(c.tyres.surface_temperature_c)
    blisters=_vals(c.tyres.blisters_percent); punct=_vals(c.tyres.punctured); brakes=_vals(c.damage.brakes_percent)
    mx=max(wear) if wear else None; avg=round(sum(wear)/len(wear),1) if wear else None
    max_td=max(tdamage) if tdamage else None; max_temp=max(temps) if temps else None
    d=c.damage
    fw=max([x for x in (d.front_left_wing_percent,d.front_right_wing_percent) if x is not None], default=None)
    rw=d.rear_wing_percent; floor=d.floor_percent
    fields=(("tyre wear",wear),("tyre damage",tdamage),("tyre temperature",temps),("tyre blistering",blisters),("puncture status",punct),("brake wear",brakes))
    for label,val in fields:
        (checked if val else missing).append(label)
    for label,val in (("front wing damage",fw),("rear wing damage",rw),("floor damage",floor),("diffuser damage",d.diffuser_percent),("sidepod damage",d.sidepod_percent),("gearbox condition",d.gearbox_percent),("engine condition",d.engine_percent),("DRS fault",d.drs_fault),("ERS fault",d.ers_fault),("engine blown",d.engine_blown),("engine seized",d.engine_seized)):
        (checked if val is not None else missing).append(label)
    if d.engine_wear_percent: checked.append("engine component wear")
    if c.tyres.age_laps is not None: checked.append("stint age")
    else: missing.append("stint age")

    laps=(s.total_laps-c.lap.current_lap) if s.total_laps is not None and c.lap.current_lap is not None else None
    game_ideal=getattr(s,"pit_stop_window_ideal_lap",None); game_latest=getattr(s,"pit_stop_window_latest_lap",None); current_lap=c.lap.current_lap
    if game_ideal is not None or game_latest is not None: checked.append("game pit window")
    (checked if laps is not None else missing).append("laps remaining" if laps is not None else "race distance")
    sets=[]
    for ts in c.tyres.sets:
        if ts.fitted or ts.available is False: continue
        sets.append({"index":ts.index,"compound":_name(ts.visual_compound),"wear_percent":ts.wear_percent,"lifespan_laps":ts.lifespan_laps,"usable_life_laps":ts.usable_life_laps,"lap_delta_s":ts.lap_delta_s})
    (checked if c.tyres.sets else missing).append("replacement tyre sets")
    forecast=tuple({"offset_min":f.offset_minutes,"weather":_name(f.weather),"rain_percent":f.rain_percent} for f in s.forecast[:3])
    (checked if s.weather is not None else missing).append("current weather")
    (checked if forecast else missing).append("weather forecast")
    sc=_name(s.safety_car); (checked if s.safety_car is not None else missing).append("Safety Car/VSC")
    fuel_margin=None
    if c.fuel.remaining_laps is not None:
        # EA's m_fuelRemainingLaps is the MFD fuel-laps margin (positive = surplus,
        # negative = deficit), not an absolute projected range.  Do not subtract
        # race laps remaining from it.
        checked.append("fuel")
        fuel_margin=round(float(c.fuel.remaining_laps), 2)
    else:
        missing.append("fuel")
    if c.lap.gap_to_car_in_front_s is not None or state.gap_behind_s is not None: checked.append("nearby gaps")
    else: missing.append("nearby gaps")
    if c.lap.pit_status is not None: checked.append("pit status")
    else: missing.append("pit status")
    if c.lap.penalties_s is not None or c.lap.pit_stop_should_serve_penalty is not None or c.lap.unserved_drive_through is not None or c.lap.unserved_stop_go is not None: checked.append("penalties")

    # EA's session packet provides the game's planned pit window. It is explicit
    # game strategy evidence, so never issue a contradictory stay-out call while
    # inside/after that window unless a stronger hard safety condition already owns
    # the decision. We do not invent a window when EA reports zero/unknown.
    game_window_score=0
    if isinstance(current_lap,int):
        if isinstance(game_latest,int) and current_lap>=game_latest:
            game_window_score=9; reasons.append(f"game pit window latest lap {game_latest} reached")
        elif isinstance(game_ideal,int) and current_lap>=game_ideal:
            game_window_score=7; reasons.append(f"game pit window is active from lap {game_ideal}" + (f" to {game_latest}" if isinstance(game_latest,int) else ""))

    # Decision score combines all *serviceable* pit reasons. Non-serviceable damage
    # is reported but cannot by itself justify a normal pit stop.
    score=game_window_score; hard=None; serviceable=bool(game_window_score)
    if any(bool(x) for x in punct): hard="puncture reported"; serviceable=True
    elif max_td is not None and max_td>=75: hard=f"maximum tyre damage {max_td:g} percent"; serviceable=True
    elif mx is not None and mx>=90: hard=f"maximum tyre wear {mx:g} percent"; serviceable=True
    elif fw is not None and fw>=85: hard=f"front wing damage {fw:g} percent"; serviceable=True

    if hard:
        score=100; reasons.append(hard)
    else:
        if mx is not None:
            if mx>=80: score+=8; serviceable=True; reasons.append(f"maximum tyre wear {mx:g} percent")
            elif mx>=65: score+=5; serviceable=True; reasons.append(f"maximum tyre wear {mx:g} percent")
            elif mx>=50: score+=2; reasons.append(f"maximum tyre wear {mx:g} percent")
        if max_td is not None:
            if max_td>=60: score+=7; serviceable=True; reasons.append(f"tyre damage {max_td:g} percent")
            elif max_td>=35: score+=3; reasons.append(f"tyre damage {max_td:g} percent")
        if blisters:
            mb=max(blisters)
            if mb>=70: score+=4; serviceable=True; reasons.append(f"tyre blistering {mb:g} percent")
            elif mb>=50: score+=2; reasons.append(f"tyre blistering {mb:g} percent")
        if fw is not None:
            if fw>=65: score+=8; serviceable=True; reasons.append(f"front wing damage {fw:g} percent")
            elif fw>=40: score+=5; serviceable=True; reasons.append(f"front wing damage {fw:g} percent")
            elif fw>=20: score+=2; reasons.append(f"front wing damage {fw:g} percent")

        # V0.9.16.0 measured tyre-life projection. Use only completed laps on the
        # currently fitted set; median of the last three maximum-wheel deltas
        # suppresses one noisy UDP sample. This never invents a degradation rate.
        if mx is not None and laps is not None and laps > 0 and state.measured_laps:
            current_set=c.tyres.fitted_set_index
            rates=[]
            for fact in state.measured_laps[-8:]:
                # The standing-start lap is a poor degradation sample and was the
                # source of a real false lap-2 "Box soon" call.  Require clean,
                # completed, same-stint evidence and at least two samples before
                # extrapolating tyre life.
                if int(getattr(fact, 'lap_number', 0) or 0) <= 1:
                    continue
                if current_set is not None and fact.fitted_tyre_set_index != current_set:
                    continue
                if (getattr(fact, 'pit_lap', False) or getattr(fact, 'race_control_compromised', False) or
                    getattr(fact, 'damage_compromised', False) or getattr(fact, 'tyre_set_changed', False)):
                    continue
                vals=_vals(fact.tyre_wear_delta)
                vals=[float(v) for v in vals if v is not None and 0.0 <= float(v) <= 15.0]
                if vals: rates.append(max(vals))
            if len(rates) >= 2:
                rates=sorted(rates[-5:])
                rate=rates[len(rates)//2]
                if rate > 0:
                    projected=mx + rate*laps
                    checked.append("measured tyre-life projection")
                    if projected >= 90:
                        score+=7; serviceable=True
                        reasons.append(f"measured tyre wear projects {projected:.0f} percent at the finish")
                    elif projected >= 80:
                        score+=3
                        reasons.append(f"measured tyre wear projects {projected:.0f} percent at the finish")

        # Weather/compound mismatch is a strong deterministic stop reason when a suitable set exists.
        comp=_name(c.tyres.visual_compound); current_wet=_wet_weather(_name(s.weather)); tyre_wet=_wet_tyre(comp)
        near=forecast[0] if forecast else None
        forecast_wet=_wet_weather(near["weather"],near["rain_percent"]) if near else current_wet
        has_wet=any(_wet_tyre(x["compound"]) for x in sets); has_dry=any(not _wet_tyre(x["compound"]) for x in sets)
        if current_wet and not tyre_wet and has_wet:
            score+=9; serviceable=True; reasons.append("wet conditions on dry tyres with a wet-weather set available")
        elif not current_wet and tyre_wet and has_dry:
            score+=7; serviceable=True; reasons.append("dry conditions on wet-weather tyres with a dry set available")
        elif forecast_wet != current_wet:
            # The game forecast is a factual input, but a future weather state is
            # not an *actual current* service requirement. Report it as context
            # without turning it into a deterministic pit trigger/score.
            reasons.append("game forecast indicates a near-term weather transition")

        # Temperatures are deliberately modifiers, not standalone pit triggers: a single
        # live sample can be transient and changing tyres may not cure setup/driving heat.
        if temps and max(temps)>115: score+=1; reasons.append(f"high tyre surface temperature {max(temps):g} degrees")
        if c.tyres.age_laps is not None and c.tyres.age_laps>=20 and (mx is None or mx>=50): score+=1; reasons.append(f"stint age {c.tyres.age_laps} laps")
        if _neutral(sc) and serviceable: score+=2; reasons.append(f"{sc} improves the opportunity to stop")
        if c.lap.pit_stop_should_serve_penalty: score+=2; serviceable=True; reasons.append("pending penalty can be served at a pit stop")
        if c.lap.unserved_stop_go:
            score+=8; serviceable=True; reasons.append(f"{c.lap.unserved_stop_go} unserved stop-go penalty")
        if c.lap.unserved_drive_through: warnings.append(f"{c.lap.unserved_drive_through} unserved drive-through penalty; do not treat a normal tyre stop as serving it")

    # Non-serviceable car condition: important for the driver, but not a false pit trigger.
    for label,val,threshold in (("rear wing",rw,50),("floor",floor,50),("diffuser",d.diffuser_percent,50),("sidepod",d.sidepod_percent,50),("gearbox",d.gearbox_percent,70),("engine",d.engine_percent,70)):
        if val is not None and val>=threshold:
            reasons.append(f"{label} damage {val:g} percent" if label in ("rear wing","floor","diffuser","sidepod") else f"{label} wear {val:g} percent")
            warnings.append(f"{label} damage/wear {val:g} percent is severe and is not assumed repairable by a normal stop")
    if brakes and max(brakes)>=70: warnings.append(f"brake wear/damage {max(brakes):g} percent is severe and is not assumed repairable by a normal stop")
    if d.engine_blown: warnings.append("engine blown; a pit stop cannot repair this")
    if d.engine_seized: warnings.append("engine seized; a pit stop cannot repair this")
    if d.drs_fault: warnings.append("DRS fault present; repairability is not assumed")
    if d.ers_fault: warnings.append("ERS fault present; repairability is not assumed")
    if fuel_margin is not None:
        if fuel_margin < 0:
            reasons.append(f"fuel estimate short by {-fuel_margin:.1f} laps")
            warnings.append(f"fuel estimate short by {-fuel_margin:.1f} laps; refuelling is not assumed available")
        else:
            reasons.append(f"fuel margin {fuel_margin:.1f} laps")

    # Combination modifiers. Avoid wasting a stop near the finish for merely marginal
    # triggers, but never suppress a hard failure. Traffic is context only because we do
    # not yet know track-specific pit loss/rejoin position.
    if hard:
        hint="box_now"; urgency="critical"
    else:
        if laps is not None and laps<=1 and score<8: score-=4; reasons.append("final-lap distance reduces the value of a non-critical stop")
        elif laps is not None and laps<=2 and score<7: score-=2; reasons.append(f"only {laps} laps remaining")
        if serviceable and not sets and (mx is not None or max_td is not None):
            reasons.append("no confirmed replacement tyre set is available in telemetry")
        if score>=9: hint="box_now"; urgency="critical"
        elif score>=7: hint="box_soon"; urgency="high"
        elif score>=4: hint="consider_box"; urgency="elevated"
        else: hint="stay_out"; urgency="normal"

    # For an affirmative stay-out call require current tyre condition + distance + wing.
    sufficient = (mx is not None and laps is not None) or hard is not None
    if not sufficient and hint=="stay_out": hint="insufficient_data"
    confidence="high" if sufficient and len(checked)>=12 else "medium" if sufficient and len(checked)>=8 else "low"
    return PitAssessment(sufficient,urgency,hint,confidence,tuple(reasons),tuple(checked),tuple(missing),laps,c.tyres.age_laps,mx,avg,max_td,max_temp,fw,rw,floor,_name(c.tyres.visual_compound),tuple(sets),sc,_name(s.weather),forecast,c.fuel.remaining_laps,fuel_margin,c.lap.gap_to_car_in_front_s,state.gap_behind_s,_name(c.lap.pit_status),c.lap.penalties_s,c.lap.pit_stop_should_serve_penalty,score,serviceable,tuple(warnings))


def format_pit_fallback(state: RaceState) -> str:
    a=assess_pit(state)
    r=_best_reason(a.reasons)
    if a.recommendation_hint=="not_applicable": return a.reasons[0][0].upper()+a.reasons[0][1:]+"."
    if a.recommendation_hint=="box_now": return f"Box this lap. {r[0].upper()+r[1:]}."
    if a.recommendation_hint=="box_soon": return f"Box soon. {r[0].upper()+r[1:]}."
    if a.recommendation_hint=="consider_box": return f"Consider boxing. {r[0].upper()+r[1:]}."
    if a.recommendation_hint=="stay_out" and a.data_sufficient:
        if a.nonserviceable_warnings: return "Stay out for now. " + a.nonserviceable_warnings[0] + "."
        return "Stay out for now. No immediate serviceable pit trigger in the available live data."
    return "I can't make a reliable pit call yet; " + " and ".join(a.missing_factors[:2]) + " are unavailable."

# --- V0.9.1 unified deterministic service plan ---------------------------------
@dataclass(frozen=True, slots=True)
class TyreChoice:
    available: bool; set_index:int|None; compound:str|None; wear_percent:int|None
    reason:str; alternatives:tuple[dict,...]=()
@dataclass(frozen=True, slots=True)
class ServicePlan:
    pit: PitAssessment; tyre: TyreChoice; front_wing_service:bool
    front_wing_adjustment:float|None; front_wing_reason:str|None
    serve_penalty:bool; automatic_summary:str
    def to_dict(self): return asdict(self)

def _tyre_kind(comp):
    n=(comp or '').lower()
    if 'inter' in n:return 'intermediate'
    if 'wet' in n:return 'wet'
    return 'dry'

def choose_tyre(state:RaceState)->TyreChoice:
    c=state.player
    if c is None:return TyreChoice(False,None,None,None,'live car data unavailable')
    sets=[x for x in c.tyres.sets if not x.fitted and x.available is not False]
    if not sets:return TyreChoice(False,None,None,None,'no confirmed replacement set available')
    weather=_name(state.session.weather)
    # Compound choice is based on actual current conditions. If EA supplies an
    # offset-0 forecast sample, its rain percentage is also current-state data.
    now_fc=next((f for f in state.session.forecast if f.offset_minutes == 0), None)
    rain=now_fc.rain_percent if now_fc is not None else None
    wet=_wet_weather(weather,rain); wn=(weather or '').lower()
    desired=('wet' if ('heavy' in wn or 'storm' in wn) else 'intermediate') if wet else 'dry'
    matches=[x for x in sets if _tyre_kind(_name(x.visual_compound))==desired]
    if not matches and desired=='wet': matches=[x for x in sets if _tyre_kind(_name(x.visual_compound))=='intermediate']
    if not matches and desired=='intermediate': matches=[x for x in sets if _tyre_kind(_name(x.visual_compound))=='wet']
    if not matches:
        return TyreChoice(False,None,None,None,f'no {desired} set confirmed available',tuple({'index':x.index,'compound':_name(x.visual_compound),'wear_percent':x.wear_percent} for x in sets))
    # V0.9.16.0: when the game provides usable-life data, first prefer a set
    # whose stated usable life covers the remaining race distance.  This stays
    # deterministic: no degradation model or track-specific assumption is added.
    laps_remaining = None
    if state.session.total_laps is not None and c.lap.current_lap is not None:
        laps_remaining = max(0, int(state.session.total_laps) - int(c.lap.current_lap))
    def cover_rank(x):
        life = x.usable_life_laps
        if laps_remaining is None or life is None or int(life) <= 0:
            return 1  # unknown
        return 0 if int(life) >= laps_remaining else 2
    matches.sort(key=lambda x:(cover_rank(x), (x.wear_percent if x.wear_percent is not None else 101),
                               (x.lap_delta_s if x.lap_delta_s is not None else float('inf')), x.index))
    x=matches[0]
    life_note = ''
    if laps_remaining is not None and x.usable_life_laps is not None and int(x.usable_life_laps) > 0:
        life_note = (f'; game usable life {x.usable_life_laps} laps covers the remaining distance'
                     if int(x.usable_life_laps) >= laps_remaining
                     else f'; game usable life {x.usable_life_laps} laps does not cover {laps_remaining} remaining laps')
    return TyreChoice(True,x.index,_name(x.visual_compound),x.wear_percent,
                      f'best available {desired} set for current conditions{life_note}',
                      tuple({'index':y.index,'compound':_name(y.visual_compound),'wear_percent':y.wear_percent,'lap_delta_s':y.lap_delta_s,'usable_life_laps':y.usable_life_laps} for y in matches[1:]))

def _game_front_wing(state):
    p=state.extended.get('setups'); idx=state.player_index
    if p is None:return None
    return getattr(p,'m_nextFrontWingValue',None)

def service_plan(state:RaceState)->ServicePlan:
    a=assess_pit(state); c=state.player
    if a.recommendation_hint=='not_applicable':
        reason=a.reasons[0] if a.reasons else 'race pit strategy is not applicable in this session'
        return ServicePlan(a,TyreChoice(False,None,None,None,reason),False,None,None,False,reason[0].upper()+reason[1:]+'.')
    tyre=choose_tyre(state)
    fw=a.front_wing_damage_percent
    repair=fw is not None and fw>=40
    next_fw=_game_front_wing(state)
    wing_reason='game-provided next front-wing value' if next_fw is not None else ('replace damaged front wing; no factual click adjustment is available' if repair else None)
    serve=bool(c and (c.lap.pit_stop_should_serve_penalty or c.lap.unserved_stop_go))
    if a.recommendation_hint=='box_now': lead='Box this lap.'
    elif a.recommendation_hint=='box_soon': lead='Box soon.'
    elif a.recommendation_hint=='consider_box': lead='Consider boxing.'
    elif a.recommendation_hint=='stay_out': lead='Stay out for now.'
    else: lead="No reliable pit call yet."
    if a.reasons: lead+=' '+a.reasons[0][0].upper()+a.reasons[0][1:]+'.'
    if a.recommendation_hint in ('box_now','box_soon','consider_box') and tyre.available: lead+=f' Fit {tyre.compound}, set {tyre.set_index}.'
    if repair:
        if a.recommendation_hint in ('box_now','box_soon','consider_box'):
            lead+=' Replace front wing.'
        else:
            lead+=' If you pit, replace the front wing.'
    if next_fw is not None:
        if a.recommendation_hint in ('box_now','box_soon','consider_box'):
            lead+=f' Game front-wing setting {next_fw:g}.'
        elif repair:
            lead+=f' Game front-wing setting {next_fw:g}.'
    if serve: lead+=' Serve the pending pit penalty.'
    return ServicePlan(a,tyre,repair,next_fw,wing_reason,serve,lead)
