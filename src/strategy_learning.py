"""Deterministic race-strategy evidence learner with per-circuit persistence.

V1.5.0.0 keeps normal / Safety Car / VSC pit-cycle measurements separate and
records only observed opponent stop/compound changes.  No future outcome is
predicted by this module.
"""
from __future__ import annotations
import json
from pathlib import Path
from statistics import median


def _name(value):
    return str(getattr(value,'name',value) or '').strip().lower().replace('_',' ')


class StrategyEvidenceLearner:
    def __init__(self, path='settings/strategy_history.json'):
        self.path=Path(path); self.pit_laps=set(); self.seen=set(); self.clean=[]; self.pit_samples=[]; self.damage_samples=[]
        self.sc_pit_samples=[]; self.vsc_pit_samples=[]; self._pit_context={}; self._opponent_last={}; self._stop_match=None
        self._track_key=None; self._db=self._load()
    def _load(self):
        try:
            d=json.loads(self.path.read_text(encoding='utf-8')); return d if isinstance(d,dict) else {}
        except Exception:return {}
    def _save(self):
        try:self.path.parent.mkdir(parents=True,exist_ok=True);self.path.write_text(json.dumps(self._db,indent=2,sort_keys=True),encoding='utf-8')
        except OSError:pass
    @staticmethod
    def _damage(car):
        d=getattr(car,'damage',None); vals=[getattr(d,k,None) for k in ('front_left_wing_percent','front_right_wing_percent','floor_percent','diffuser_percent')] if d else []
        return max([float(x) for x in vals if isinstance(x,(int,float))] or [0.0])
    @staticmethod
    def _track(state):
        s=getattr(state,'session',None); t=getattr(s,'track',None); name=getattr(t,'name',None)
        if name:return str(name).strip().lower().replace(' ','_')
        raw=getattr(t,'raw',None)
        if raw is not None:return f'track_{raw}'
        return 'unknown'
    def _sync_track(self,state):
        key=self._track(state)
        if key!=self._track_key:
            self._track_key=key; self.pit_laps=set();self.seen=set();self.clean=[];self.pit_samples=[];self.damage_samples=[]
            self.sc_pit_samples=[];self.vsc_pit_samples=[];self._pit_context={};self._opponent_last={};self._stop_match=None
        row=self._db.get(key,{}) if key!='unknown' else {}
        mappings=(('pit_loss_samples_s','_track_pit_cycle_samples_s'),('sc_pit_loss_samples_s','_track_sc_pit_cycle_samples_s'),('vsc_pit_loss_samples_s','_track_vsc_pit_cycle_samples_s'))
        for dbkey,extkey in mappings:
            vals=[float(x) for x in row.get(dbkey,[]) if isinstance(x,(int,float))]
            if vals:state.extended[extkey]=tuple(vals[-9:])
        track_dmg=[float(x) for x in row.get('damage_pace_loss_samples_s',[]) if isinstance(x,(int,float))]
        if track_dmg and 'measured_damage_pace_loss_s' not in state.extended:
            state.extended['measured_damage_pace_loss_s']=round(float(median(track_dmg[-7:])),3)
    def _persist_sample(self,kind,value):
        if self._track_key in (None,'unknown'):return
        row=self._db.setdefault(self._track_key,{})
        arr=row.setdefault(kind,[]); arr.append(round(float(value),3)); row[kind]=arr[-20:]; self._save()

    def _observe_opponent(self,state,lapno):
        p=getattr(state,'player',None); idx=getattr(state,'ahead_index',None); car=getattr(state,'field',{}).get(idx) if idx is not None else None
        if p is None or car is None or not isinstance(lapno,int):return
        pit_name=_name(getattr(car.lap,'pit_status',None)); pit=bool(getattr(car.lap,'pit_lane_timer_active',False)) or pit_name not in ('','none','0','n/a','na')
        comp=_name(getattr(car.tyres,'visual_compound',None)); age=getattr(car.tyres,'age_laps',None)
        current={'index':idx,'lap':lapno,'pit':pit,'compound':comp or None,'age_laps':age}
        prev=self._opponent_last.get(idx)
        if prev:
            events=[]
            if not prev.get('pit') and pit: events.append('pit_entry')
            if prev.get('pit') and not pit: events.append('pit_exit')
            if comp and prev.get('compound') and comp!=prev.get('compound'): events.append('compound_change')
            if events:
                state.extended['opponent_strategy_inference']={'car_index':idx,'lap':lapno,'events':events,'previous_compound':prev.get('compound'),'compound':comp or None,'tyre_age_laps':age,'source':'observed_telemetry'}
        self._opponent_last[idx]=current

        # Matched stop-sequence evidence. Positive gain_s means the player reduced
        # the measured gap after both relevant stops were completed.
        player_pit=bool(getattr(p.lap,'pit_lane_timer_active',False)) or _name(getattr(p.lap,'pit_status',None)) not in ('','none','0','n/a','na')
        gap=getattr(p.lap,'gap_to_car_in_front_s',None)
        if not isinstance(gap,(int,float)):return
        match=self._stop_match
        if match is None:
            if player_pit and not pit:
                self._stop_match={'sequence':'player_first','start_lap':lapno,'gap_before_s':float(gap),'player_seen':True,'opponent_seen':False}
            elif pit and not player_pit:
                self._stop_match={'sequence':'opponent_first','start_lap':lapno,'gap_before_s':float(gap),'player_seen':False,'opponent_seen':True}
            return
        if lapno-int(match['start_lap'])>4:
            self._stop_match=None; return
        match['player_seen']=bool(match.get('player_seen') or player_pit)
        match['opponent_seen']=bool(match.get('opponent_seen') or pit)
        if match['player_seen'] and match['opponent_seen'] and not player_pit and not pit:
            gain=float(match['gap_before_s'])-float(gap)
            row={'sequence':match['sequence'],'start_lap':match['start_lap'],'end_lap':lapno,'gap_before_s':round(float(match['gap_before_s']),3),'gap_after_s':round(float(gap),3),'player_gap_gain_s':round(gain,3),'source':'observed_matched_stop_sequence'}
            state.extended['measured_stop_sequence_effect']=row
            self._stop_match=None

    def observe(self,state):
        p=getattr(state,'player',None)
        if p is None:return
        self._sync_track(state)
        lapno=getattr(p.lap,'current_lap',None)
        sc=_name(getattr(getattr(state,'session',None),'safety_car',None))
        context='vsc' if ('virtual' in sc or 'vsc' in sc) else ('sc' if 'safety' in sc and 'virtual' not in sc else 'normal')
        pit_name=_name(getattr(p.lap,'pit_status',None))
        pit=bool(getattr(p.lap,'pit_lane_timer_active',False)) or pit_name not in ('','none','0','n/a','na')
        if pit and isinstance(lapno,int):
            self.pit_laps.add(lapno); self._pit_context.setdefault(lapno,context)
        self._observe_opponent(state,lapno)
        for row in getattr(state,'measured_laps',()) or ():
            if row.lap_number in self.seen or not isinstance(row.lap_time_s,(int,float)):continue
            self.seen.add(row.lap_number);t=float(row.lap_time_s);dmg=self._damage(p)
            if row.lap_number in self.pit_laps and len(self.clean)>=2:
                sample=t-median(self.clean[-3:])
                if 3<sample<180:
                    ctx=self._pit_context.get(row.lap_number,'normal')
                    if ctx=='sc': self.sc_pit_samples.append(sample);self._persist_sample('sc_pit_loss_samples_s',sample)
                    elif ctx=='vsc': self.vsc_pit_samples.append(sample);self._persist_sample('vsc_pit_loss_samples_s',sample)
                    else:self.pit_samples.append(sample);self._persist_sample('pit_loss_samples_s',sample)
            elif dmg<10:self.clean.append(t)
            elif dmg>=20 and len(self.clean)>=2:
                sample=t-median(self.clean[-3:])
                if 0<=sample<20:self.damage_samples.append(sample);self._persist_sample('damage_pace_loss_samples_s',sample)
        if self.pit_samples:state.extended['_pit_cycle_samples_s']=tuple(round(x,3) for x in self.pit_samples[-7:])
        if self.sc_pit_samples:state.extended['_sc_pit_cycle_samples_s']=tuple(round(x,3) for x in self.sc_pit_samples[-7:])
        if self.vsc_pit_samples:state.extended['_vsc_pit_cycle_samples_s']=tuple(round(x,3) for x in self.vsc_pit_samples[-7:])
        if self.damage_samples:state.extended['measured_damage_pace_loss_s']=round(float(median(self.damage_samples[-5:])),3)
        comp=_name(getattr(p.tyres,'visual_compound',None))
        if comp and all(k not in comp for k in ('inter','wet')):
            used=set(state.extended.get('_used_dry_compounds',()) or ());used.add(comp);state.extended['_used_dry_compounds']=tuple(sorted(used))
