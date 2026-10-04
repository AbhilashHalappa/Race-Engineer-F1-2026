"""V0.9.14.6 deterministic end-of-session summary and finish radio."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import math

from .telemetry import enums as E


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _enum_name(v):
    return getattr(v, "name", None) if v is not None else None


def _lap_time(v):
    if not _finite(v) or v <= 0:
        return None
    m = int(v // 60); s = v - 60*m
    return f"{m}:{s:06.3f}" if m else f"{s:.3f}s"


def _result_name(raw):
    return E.RESULT_STATUS.get(raw, f"Result {raw}") if raw is not None else None


def _compound(raw):
    return E.VISUAL_COMPOUND.get(raw) or E.ACTUAL_COMPOUND.get(raw) or (str(raw) if raw not in (None, 0) else None)


@dataclass
class SessionSummaryTracker:
    uid: int | None = None
    max_tyre_temp_c: float | None = None
    max_tyre_wear_percent: float | None = None
    max_tyre_damage_percent: float | None = None
    max_front_wing_damage_percent: float | None = None
    max_engine_wear_percent: float | None = None
    max_gearbox_wear_percent: float | None = None
    max_warnings: int = 0
    max_corner_warnings: int = 0
    max_penalties_s: int = 0
    weather_changes: list[str] = field(default_factory=list)
    initial_grid_position: int | None = None
    _last_weather: str | None = None

    def reset(self, uid=None):
        self.__init__(uid=uid)

    @staticmethod
    def _wheel_max(w):
        if w is None:
            return None
        vals=[float(x) for x in (w.FL,w.FR,w.RL,w.RR) if _finite(x)]
        return max(vals) if vals else None

    @staticmethod
    def _acc(old, value):
        if value is None: return old
        return value if old is None else max(old, value)

    def observe(self, state):
        uid = getattr(state.session, 'uid', None)
        if uid and self.uid not in (None, uid):
            self.reset(uid)
        elif self.uid is None:
            self.uid = uid
        weather = _enum_name(getattr(state.session, 'weather', None))
        if weather and weather != self._last_weather:
            if weather not in self.weather_changes:
                self.weather_changes.append(weather)
            self._last_weather = weather
        car=state.player
        if car is None: return
        if self.initial_grid_position is None and car.lap.grid_position:
            self.initial_grid_position=car.lap.grid_position
        self.max_tyre_temp_c=self._acc(self.max_tyre_temp_c,self._wheel_max(car.tyres.surface_temperature_c))
        self.max_tyre_wear_percent=self._acc(self.max_tyre_wear_percent,self._wheel_max(car.tyres.wear_percent))
        self.max_tyre_damage_percent=self._acc(self.max_tyre_damage_percent,self._wheel_max(car.tyres.damage_percent))
        wing=max([x for x in (car.damage.front_left_wing_percent,car.damage.front_right_wing_percent) if _finite(x)], default=None)
        self.max_front_wing_damage_percent=self._acc(self.max_front_wing_damage_percent,wing)
        self.max_engine_wear_percent=self._acc(self.max_engine_wear_percent,car.damage.engine_percent if _finite(car.damage.engine_percent) else None)
        self.max_gearbox_wear_percent=self._acc(self.max_gearbox_wear_percent,car.damage.gearbox_percent if _finite(car.damage.gearbox_percent) else None)
        self.max_warnings=max(self.max_warnings,int(car.lap.warnings or 0))
        self.max_corner_warnings=max(self.max_corner_warnings,int(car.lap.corner_cutting_warnings or 0))
        self.max_penalties_s=max(self.max_penalties_s,int(car.lap.penalties_s or 0))

    def build(self, state, performance) -> dict | None:
        final=state.extended.get('final')
        idx=state.player_index
        row=None
        if final is not None and idx is not None:
            arr=getattr(final,'m_classificationData',())
            if 0 <= idx < len(arr): row=arr[idx]
        car=state.player
        if row is None and car is None:
            return None

        result_raw=getattr(row,'m_resultStatus',None) if row is not None else getattr(getattr(car,'lap',None).result_status,'raw',None)
        position=getattr(row,'m_position',None) if row is not None else getattr(car.lap,'position',None)
        grid=getattr(row,'m_gridPosition',None) if row is not None else (self.initial_grid_position or getattr(car.lap,'grid_position',None))
        if row is not None:
            laps=getattr(row,'m_numLaps',None)
        elif car is not None:
            # When Final Classification is delayed or absent, a finished LapData
            # packet is still enough to know the race distance. Do not report
            # current_lap-1 in that case (that was the pre-V0.9.14.6 off-by-one).
            result_now=getattr(getattr(car,'lap',None),'result_status',None)
            result_now_raw=getattr(result_now,'raw',None)
            total_laps=getattr(state.session,'total_laps',None)
            if result_now_raw == 3 and total_laps:
                laps=int(total_laps)
            else:
                laps=max(0,(car.lap.current_lap or 1)-1)
        else:
            laps=None
        best_ms=getattr(row,'m_bestLapTimeInMS',0) if row is not None else 0
        best_s=best_ms/1000.0 if best_ms else None
        # V2.6.1: when the authoritative Final Classification packet is
        # available, compare the player's race best against the whole field.
        # This is the only safe way to persist a race-fastest-lap milestone.
        race_fastest_lap=None
        race_fastest_lap_s=None
        session_type_name=_enum_name(state.session.session_type)
        if final is not None and row is not None and session_type_name in ('Race','Race 2','Race 3'):
            field_best_ms=[]
            for classification_row in getattr(final,'m_classificationData',()) or ():
                ms=getattr(classification_row,'m_bestLapTimeInMS',0)
                if isinstance(ms,(int,float)) and ms>0:
                    field_best_ms.append(int(ms))
            if best_ms and field_best_ms:
                fastest_ms=min(field_best_ms)
                race_fastest_lap=(int(best_ms)==fastest_ms)
                race_fastest_lap_s=fastest_ms/1000.0
        completed=list(getattr(performance,'completed',()) or ())
        valid_times=[x.get('lap_time_s') for x in completed if x.get('valid') and _finite(x.get('lap_time_s')) and x.get('lap_time_s')>0]
        # V2.9.1.3.5.14: in Time Trial, Final Classification can expose the
        # driver's track/personal-best value rather than the best lap completed
        # in this specific stored session.  Performance History session best is
        # owned by this session's completed valid laps whenever they exist.
        if session_type_name == 'Time Trial' and valid_times:
            best_s=min(valid_times)
        elif best_s is None and valid_times:
            best_s=min(valid_times)
        avg_s=(sum(valid_times)/len(valid_times)) if valid_times else None
        pit_stops=getattr(row,'m_numPitStops',None) if row is not None else (car.lap.pit_stops if car else None)
        penalties=getattr(row,'m_penaltiesTime',None) if row is not None else self.max_penalties_s
        num_pen=getattr(row,'m_numPenalties',None) if row is not None else None
        total_time=getattr(row,'m_totalRaceTime',None) if row is not None else None
        points=getattr(row,'m_points',None) if row is not None else None
        stints=[]
        if row is not None:
            n=min(int(getattr(row,'m_numTyreStints',0) or 0),8)
            actual=getattr(row,'m_tyreStintsActual',())
            visual=getattr(row,'m_tyreStintsVisual',())
            ends=getattr(row,'m_tyreStintsEndLaps',())
            for i in range(n):
                stints.append({'compound':_compound(visual[i]) or _compound(actual[i]),'end_lap':int(ends[i]) if i<len(ends) else None})
        summary={
            'session_uid':state.session.uid,'session_type':_enum_name(state.session.session_type),'track':_enum_name(state.session.track),
            'result_status':_result_name(result_raw),'result_status_raw':result_raw,'position':position,'grid_position':grid,
            'positions_gained':(grid-position) if grid and position else None,'laps_completed':laps,'points':points,
            'best_lap_s':best_s,'best_lap':_lap_time(best_s),'average_valid_lap_s':avg_s,'average_valid_lap':_lap_time(avg_s),
            'race_fastest_lap':race_fastest_lap,'race_fastest_lap_s':race_fastest_lap_s,
            'total_race_time_s':total_time if _finite(total_time) else None,'pit_stops':pit_stops,'penalties_s':penalties,
            'penalty_count':num_pen,'warnings':self.max_warnings,'corner_cutting_warnings':self.max_corner_warnings,
            'max_tyre_temp_c':self.max_tyre_temp_c,'max_tyre_wear_percent':self.max_tyre_wear_percent,
            'max_tyre_damage_percent':self.max_tyre_damage_percent,'max_front_wing_damage_percent':self.max_front_wing_damage_percent,
            'max_engine_wear_percent':self.max_engine_wear_percent,'max_gearbox_wear_percent':self.max_gearbox_wear_percent,
            'weather_changes':list(self.weather_changes),'tyre_stints':stints,
        }
        summary['finish_call']=finish_call(summary)
        summary['spoken_summary']=spoken_summary(summary)
        summary['text']=format_text(summary)
        return summary


def finish_call(s: dict) -> str:
    status=s.get('result_status_raw'); p=s.get('position')
    if status==5: return "We've been disqualified."
    if status in (4,7): return "We're out. Tough end to the race."
    if status==6: return "Race complete. We were not classified."
    if status not in (3,None): return "Session complete."
    if p==1:
        choices=("That's the win! Brilliant drive. P1. Great job.","Race win! Fantastic job. P1.","P1. You've won it. Brilliant drive.")
        return choices[int(s.get('session_uid') or 0)%len(choices)]
    if p==2: return "P2. Strong race. We were right there."
    if p==3: return "Podium. P3. Good result."
    if p in (4,5): return f"P{p}. Solid result. Good points."
    if p and 6<=p<=10: return f"P{p}. Points on the board. Good work."
    if p and 11<=p<=15: return f"P{p}. Tough race. We'll review where the time went."
    if p: return f"P{p}. Difficult one. We'll go through it."
    return "Race complete."


def spoken_summary(s: dict) -> str:
    parts=[]
    p=s.get('position')
    if p: parts.append(f"P{p}")
    if s.get('best_lap'): parts.append(f"best lap {s['best_lap']}")
    w=s.get('warnings'); pen=s.get('penalties_s')
    if w is not None: parts.append(f"{w} warning{'s' if w!=1 else ''}")
    if pen: parts.append(f"{pen} seconds penalties")
    fw=s.get('max_front_wing_damage_percent')
    if _finite(fw) and fw>0: parts.append(f"front wing damage peaked at {fw:.0f} percent")
    tt=s.get('max_tyre_temp_c')
    if _finite(tt) and tt>=110: parts.append(f"tyres peaked at {tt:.0f} degrees")
    if not parts: return "Session summary is available."
    return "Race summary. " + ". ".join(parts) + "."


def format_text(s: dict) -> str:
    lines=["SESSION SUMMARY", "="*44]
    pairs=[('Result',f"P{s['position']}" if s.get('position') else s.get('result_status')),('Status',s.get('result_status')),
           ('Grid',f"P{s['grid_position']}" if s.get('grid_position') else None),('Positions gained',s.get('positions_gained')),
           ('Laps completed',s.get('laps_completed')),('Best lap',s.get('best_lap')),('Average valid lap',s.get('average_valid_lap')),
           ('Pit stops',s.get('pit_stops')),('Penalties',f"{s.get('penalties_s',0)} s"),('Warnings',s.get('warnings')),
           ('Track-limit warnings',s.get('corner_cutting_warnings'))]
    for k,v in pairs:
        if v is not None: lines.append(f"{k}: {v}")
    for k,label in [('max_tyre_temp_c','Peak tyre temp'),('max_tyre_wear_percent','Peak tyre wear'),('max_front_wing_damage_percent','Peak front-wing damage'),('max_engine_wear_percent','Engine wear'),('max_gearbox_wear_percent','Gearbox wear')]:
        v=s.get(k)
        if _finite(v): lines.append(f"{label}: {v:.1f}{' C' if k=='max_tyre_temp_c' else ' %'}")
    if s.get('weather_changes'): lines.append('Weather: '+' -> '.join(s['weather_changes']))
    if s.get('tyre_stints'):
        lines.append('Tyre stints: '+', '.join(f"{x.get('compound') or '--'} to L{x.get('end_lap')}" for x in s['tyre_stints']))
    return '\n'.join(lines)


def save_summary(summary: dict, directory='analysis') -> tuple[Path,Path]:
    out=Path(directory); out.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    base=out/f"session_summary-{stamp}"
    jp=base.with_suffix('.json'); tp=base.with_suffix('.txt')
    jp.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    tp.write_text(summary.get('text') or format_text(summary),encoding='utf-8')
    return jp,tp
