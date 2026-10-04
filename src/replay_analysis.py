"""Cached replay/session analysis for local Race Engineer recordings.

Builds a lightweight navigation/telemetry index directly from ARERPL01 files so
session browsing and comparisons never need to run the full RaceState engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import bisect
import json
import math
import struct
from typing import Any

from .telemetry.header import decode_header
from .telemetry.decoders import decode_packet
from .telemetry_recording import MAGIC
from .telemetry.enums import TRACKS
from .track_geometry import persisted_physical_turns, derive_physical_turns, expected_turn_count

_REC = struct.Struct('<dI')
ERS_MAX_J = 4_000_000.0
INDEX_VERSION = 2


def _safe(v, digits=4):
    if isinstance(v, bool) or v is None: return v
    if isinstance(v, (int, str)): return v
    try:
        f=float(v)
        return round(f,digits) if math.isfinite(f) else None
    except Exception:return None


def _iter_records(path: Path):
    with path.open('rb') as f:
        if f.read(len(MAGIC)) != MAGIC:
            raise ValueError('Not a Race Engineer ARERPL01 replay file')
        i=0
        while True:
            raw=f.read(_REC.size)
            if not raw: break
            if len(raw)!=_REC.size: raise ValueError('Truncated replay record header')
            off,size=_REC.unpack(raw)
            data=f.read(size)
            if len(data)!=size: raise ValueError('Truncated replay packet')
            yield i,float(off),data
            i+=1


def _mtime_ns(path: Path):
    try:return path.stat().st_mtime_ns
    except OSError:return 0


@dataclass
class ReplayAnalysisService:
    recordings: Path = Path('user_data/recordings')
    cache_dir: Path = Path('user_data/sessions/replay_index')
    reports: Path = Path('user_data/sessions/reports')
    corner_validation: Path = Path('user_data/validation/corner_coach')

    def __init__(self, recordings=None, cache_dir=None, reports=None, corner_validation=None):
        from .app_paths import RECORDINGS, REPLAY_INDEX, REPORTS, CORNER_VALIDATION
        self.recordings=Path(recordings) if recordings is not None else RECORDINGS; self.cache_dir=Path(cache_dir) if cache_dir is not None else REPLAY_INDEX; self.reports=Path(reports) if reports is not None else REPORTS; self.corner_validation=Path(corner_validation) if corner_validation is not None else CORNER_VALIDATION

    def resolve(self, value: str | Path) -> Path:
        p=Path(value)
        if p.exists(): return p
        p=self.recordings/p.name
        if not p.exists(): raise FileNotFoundError(p)
        return p

    def cache_path(self, replay: str | Path) -> Path:
        p=self.resolve(replay)
        return self.cache_dir/(p.name+'.index.json')

    def build(self, replay: str | Path, *, force=False) -> dict[str,Any]:
        p=self.resolve(replay); cp=self.cache_path(p)
        if not force and cp.exists():
            try:
                d=json.loads(cp.read_text(encoding='utf-8'))
                src=d.get('source') or {}
                same_source=src.get('size')==p.stat().st_size and src.get('mtime_ns')==_mtime_ns(p)
                version=d.get('version')
                if same_source and version==INDEX_VERSION:
                    return d
                # Test/legacy synthetic caches can remain readable. Real ARERPL01
                # recordings are rescanned once so V2.0.6 gains steer/RPM/G channels.
                if same_source and version==1:
                    try:
                        with p.open('rb') as fh: is_real=fh.read(len(MAGIC))==MAGIC
                    except OSError:
                        is_real=False
                    if not is_real:
                        return d
            except Exception: pass
        d=self._scan(p)
        cp.parent.mkdir(parents=True,exist_ok=True)
        cp.write_text(json.dumps(d,separators=(',',':'),allow_nan=False),encoding='utf-8')
        return d

    def _scan(self,p:Path)->dict[str,Any]:
        session_uid=None; game={}; session={}; packet_count=0
        nav=[]; traces={}; laps={}; last_lap=None; last_dist=None; last_lap_start_time=None
        last_status={}; last_motion={}; last_trace_key={}
        player_idx=0
        for idx,off,data in _iter_records(p):
            packet_count=idx+1
            try:h=decode_header(data)
            except Exception: continue
            session_uid=int(h.m_sessionUID); player_idx=int(h.m_playerCarIndex)
            if not game:
                game={'packet_format':int(h.m_packetFormat),'game_year':int(h.m_gameYear),'game_major':int(h.m_gameMajorVersion),'game_minor':int(h.m_gameMinorVersion),'packet_version':int(h.m_packetVersion)}
            pid=int(h.m_packetId)
            if pid not in {0,1,2,6,7,11}: continue
            try: body=decode_packet(data,h).body
            except Exception: continue
            if pid==1:
                session={'track_id':int(body.m_trackId),'track_name':TRACKS.get(int(body.m_trackId),f'UNKNOWN({int(body.m_trackId)})'),'track_length_m':int(body.m_trackLength),'session_type':int(body.m_sessionType),'total_laps':int(body.m_totalLaps),'formula':int(body.m_formula)}
            elif pid==2:
                lap=body.m_lapData[player_idx]
                ln=int(lap.m_currentLapNum); dist=float(lap.m_lapDistance)
                if ln>0:
                    if last_lap != ln:
                        last_lap=ln; last_lap_start_time=float(h.m_sessionTime)
                        laps.setdefault(str(ln),{'lap':ln,'start_packet':idx,'end_packet':idx,'start_session_time_s':_safe(h.m_sessionTime),'end_session_time_s':_safe(h.m_sessionTime),'valid':not bool(lap.m_currentLapInvalid),'last_lap_time_s':None,'trace_samples':0})
                    row=laps.setdefault(str(ln),{'lap':ln,'start_packet':idx,'end_packet':idx})
                    row['end_packet']=idx; row['end_session_time_s']=_safe(h.m_sessionTime); row['valid']=not bool(lap.m_currentLapInvalid)
                    if lap.m_lastLapTimeInMS and ln>1:
                        prev=laps.get(str(ln-1))
                        if prev is not None: prev['lap_time_s']=round(lap.m_lastLapTimeInMS/1000.0,3)
                    last_dist=dist
                    nav.append({'packet':idx,'offset_s':_safe(off),'session_time_s':_safe(h.m_sessionTime),'lap':ln,'distance_m':_safe(dist,2)})
            elif pid==7:
                s=body.m_carStatusData[player_idx]
                last_status={'ers_percent':_safe(float(s.m_ersStoreEnergy)/ERS_MAX_J*100.0,2),'fuel_kg':_safe(s.m_fuelInTank,3),'tyre_age_laps':int(s.m_tyresAgeLaps),'compound':int(s.m_visualTyreCompound)}
            elif pid==0:
                m=body.m_carMotionData[player_idx]
                last_motion={'x':_safe(m.m_worldPositionX,3),'z':_safe(m.m_worldPositionZ,3),'g_lateral':_safe(getattr(m,'m_gForceLateral',0)/1000.0,4),'g_longitudinal':_safe(getattr(m,'m_gForceLongitudinal',0)/1000.0,4),'g_vertical':_safe(getattr(m,'m_gForceVertical',0)/1000.0,4)}
            elif pid==6 and last_lap and last_dist is not None:
                t=body.m_carTelemetryData[player_idx]
                key=(round(last_dist/5.0), int(float(h.m_sessionTime)*20))
                if last_trace_key.get(last_lap)==key: continue
                last_trace_key[last_lap]=key
                start=float(laps[str(last_lap)].get('start_session_time_s') or h.m_sessionTime)
                sample={'packet':idx,'session_time_s':_safe(h.m_sessionTime),'lap_time_s':_safe(float(h.m_sessionTime)-start,4),'distance_m':_safe(last_dist,2),'speed_kph':int(t.m_speed),'throttle':_safe(t.m_throttle,4),'brake':_safe(t.m_brake,4),'gear':int(t.m_gear),'steer':_safe(t.m_steer,4),'rpm':int(getattr(t,'m_engineRPM',0) or 0),**last_status,**last_motion}
                traces.setdefault(str(last_lap),[]).append(sample)
                laps[str(last_lap)]['trace_samples']=len(traces[str(last_lap)])
            elif pid==11 and int(body.m_carIdx)==player_idx:
                for i,lh in enumerate(body.m_lapHistoryData[:int(body.m_numLaps)],1):
                    if lh.m_lapTimeInMS:
                        row=laps.setdefault(str(i),{'lap':i})
                        row['lap_time_s']=round(lh.m_lapTimeInMS/1000.0,3)
                        row['valid']=bool(lh.m_lapValidBitFlags & 1)
        lap_rows=sorted(laps.values(),key=lambda x:x.get('lap',0))
        valid_times=[x for x in lap_rows if isinstance(x.get('lap_time_s'),(int,float)) and x.get('lap_time_s',0)>0 and x.get('valid',True)]
        best=min(valid_times,key=lambda x:x['lap_time_s'])['lap'] if valid_times else None
        trace_candidates=[x for x in valid_times if int(x.get('trace_samples') or 0)>1]
        best_trace=min(trace_candidates,key=lambda x:x['lap_time_s'])['lap'] if trace_candidates else None
        out={'format':'race_engineer_replay_index','version':INDEX_VERSION,'source':{'file':p.name,'path':str(p),'size':p.stat().st_size,'mtime_ns':_mtime_ns(p)},'session_uid':session_uid,'packet_count':packet_count,'game':game,'session':session,'laps':lap_rows,'best_lap':best,'best_trace_lap':best_trace,'navigation':nav,'traces':traces}
        out['associations']=self.associations(p,session_uid=session_uid)
        return out

    def associations(self,replay:str|Path,*,session_uid=None)->dict[str,Any]:
        p=self.resolve(replay); uid=str(session_uid) if session_uid else None
        out={'replay_metadata':str(p.with_suffix(p.suffix+'.json')) if p.with_suffix(p.suffix+'.json').exists() else None,'coach_report_json':None,'coach_report_html':None,'validation_json':None,'corner_validation':[],'analysis':[]}
        if uid:
            for ext,key in [('.json','coach_report_json'),('.html','coach_report_html'),('_validation.json','validation_json')]:
                q=self.reports/f'session_{uid}{ext}'
                if q.exists(): out[key]=str(q)
            if self.corner_validation.exists():
                out['corner_validation']=[str(q) for q in sorted(self.corner_validation.glob(f'*_{uid}_*.jsonl'),key=lambda x:abs(x.stat().st_mtime-p.stat().st_mtime))]
        root=Path('analysis')
        if root.exists():
            out['analysis']=[str(q) for q in root.glob(p.stem+'*.json') if q.is_file()]
        return out

    def timeline(self,replay:str|Path)->list[dict[str,Any]]:
        idx=self.build(replay); files=(idx.get('associations') or {}).get('corner_validation') or []
        if not files:return []
        path=Path(files[0]); rows=[]
        wanted={'pre_emit','post_emit','post_suppressed','pre_blocked','zone_enter','lap_summary','radio_submit'}
        for line in path.read_text(encoding='utf-8',errors='ignore').splitlines():
            try:d=json.loads(line)
            except Exception:continue
            ev=d.get('event')
            if ev not in wanted:continue
            st=d.get('session_time_s'); lap=d.get('lap'); dist=d.get('distance_m')
            packet=self._nearest_packet(idx,lap=lap,distance=dist,session_time=st)
            rows.append({'event':ev,'session_time_s':st,'lap':lap,'distance_m':dist,'packet':packet,'zone_id':d.get('zone_id'),'label':d.get('label'),'corner_ids':d.get('corner_ids') or [],'text':d.get('text'),'reason':d.get('reason'),'diagnosis':d.get('diagnosis')})
        rows.sort(key=lambda x:(float(x.get('session_time_s') or 1e30),int(x.get('packet') or 0)))
        return rows

    def _nearest_packet(self,idx,*,lap=None,distance=None,session_time=None):
        nav=idx.get('navigation') or []
        cand=[x for x in nav if lap is None or x.get('lap')==lap]
        if not cand:cand=nav
        if not cand:return None
        if distance is not None:
            return min(cand,key=lambda x:abs(float(x.get('distance_m') or 0)-float(distance))).get('packet')
        if session_time is not None:
            return min(cand,key=lambda x:abs(float(x.get('session_time_s') or 0)-float(session_time))).get('packet')
        return cand[0].get('packet')

    def _reference_zones(self,idx):
        target=(idx.get('session') or {}).get('track_length_m')
        if not isinstance(target,(int,float)) or target<=0:return []
        from .app_paths import REFERENCES_UPLOADED
        root=Path(REFERENCES_UPLOADED)
        matches=[]
        if root.exists():
            for q in root.glob('*/coaching_zones.json'):
                try:
                    d=json.loads(q.read_text(encoding='utf-8')); length=float(d.get('track_length_m') or 0)
                except Exception:continue
                if length>0: matches.append((abs(length-float(target)),q,d))
        if not matches:return []
        diff,q,d=min(matches,key=lambda x:x[0])
        if diff>150:return []
        return list(d.get('coaching_zones') or [])

    def corners(self,replay:str|Path)->list[dict[str,Any]]:
        idx=self.build(replay); out=[]; seen=set()
        for e in self.timeline(replay):
            ids=e.get('corner_ids') or []
            if not ids: continue
            key=(e.get('lap'),tuple(ids))
            if key in seen:continue
            seen.add(key)
            out.append({'lap':e.get('lap'),'corner_ids':ids,'label':e.get('label') or ('T'+'-'.join(map(str,ids))),'packet':e.get('packet'),'distance_m':e.get('distance_m'),'session_time_s':e.get('session_time_s'),'source':'coach_timeline'})
        # Fill missing zones from the installed trusted reference geometry. This
        # also makes jump-to-corner complete when a validation trace starts late.
        lap=idx.get('best_trace_lap') or idx.get('best_lap')
        if not lap:return out
        covered={i for row in out for i in (row.get('corner_ids') or [])}
        for z in self._reference_zones(idx):
            ids=list(z.get('corner_ids') or []); dist=z.get('start_m') if isinstance(z.get('start_m'),(int,float)) else z.get('apex_m')
            if not ids or all(i in covered for i in ids) or not isinstance(dist,(int,float)):continue
            out.append({'lap':lap,'corner_ids':ids,'label':z.get('label') or ('T'+'-'.join(map(str,ids))),'packet':self._nearest_packet(idx,lap=lap,distance=dist),'distance_m':float(dist),'session_time_s':None,'source':'reference_geometry'})
            covered.update(ids)
        out.sort(key=lambda x:(int(x.get('lap') or 0),float(x.get('distance_m') or 0)))
        return out

    def lap_trace(self,replay:str|Path,lap:int)->dict[str,Any]:
        idx=self.build(replay); samples=(idx.get('traces') or {}).get(str(int(lap))) or []
        meta=next((x for x in idx.get('laps',[]) if x.get('lap')==int(lap)),{'lap':int(lap)})
        return {'file':idx['source']['file'],'session_uid':idx.get('session_uid'),'lap':int(lap),'meta':meta,'samples':samples}

    @staticmethod
    def _interp(samples,key,grid):
        pts=[(float(x['distance_m']),x.get(key)) for x in samples if isinstance(x.get('distance_m'),(int,float)) and isinstance(x.get(key),(int,float))]
        if len(pts)<2:return [None for _ in grid]
        pts.sort(); xs=[x[0] for x in pts]; ys=[float(x[1]) for x in pts]; out=[]
        for g in grid:
            i=bisect.bisect_left(xs,g)
            if i<=0:out.append(ys[0]);continue
            if i>=len(xs):out.append(ys[-1]);continue
            x0,x1=xs[i-1],xs[i]; y0,y1=ys[i-1],ys[i]
            f=0 if x1==x0 else (g-x0)/(x1-x0); out.append(round(y0+(y1-y0)*f,4))
        return out

    def compare_laps(self,replay:str|Path,laps:list[int])->dict[str,Any]:
        selected=[self.lap_trace(replay,int(l)) for l in laps]
        available=[x for x in selected if x['samples']]
        maxd=max((max(float(s['distance_m']) for s in x['samples']) for x in available),default=0)
        grid=[float(x) for x in range(0,int(maxd)+1,10)]
        series=[]
        keys=['speed_kph','brake','throttle','steer','gear','ers_percent','rpm','g_lateral','g_longitudinal','g_vertical','x','z']
        for x in selected:
            row={'lap':x['lap'],'lap_time_s':x['meta'].get('lap_time_s'),'valid':x['meta'].get('valid'),'trace_samples':len(x['samples'])}
            for k in keys: row[k]=self._interp(x['samples'],k,grid)
            series.append(row)
        if series:
            base=series[0].get('lap_time_s')
            base_arr=self._interp(selected[0]['samples'],'lap_time_s',grid) if selected else []
            for row,x in zip(series,selected):
                row['lap_delta_s']=round(float(row['lap_time_s'])-float(base),3) if isinstance(row.get('lap_time_s'),(int,float)) and isinstance(base,(int,float)) else None
                arr=self._interp(x['samples'],'lap_time_s',grid)
                row['delta_s']=[round(float(v)-float(b),4) if isinstance(v,(int,float)) and isinstance(b,(int,float)) else None for v,b in zip(arr,base_arr)]
        return {'file':self.resolve(replay).name,'distance_m':grid,'series':series}


    def workstation(self, replay: str | Path, lap: int, reference_lap: int | None = None) -> dict[str, Any]:
        """Return bounded, distance-domain replay telemetry for the interactive workstation.

        This is a read-only analysis surface. It reuses the replay index and never
        runs the RaceState engine or mutates live Performance History.
        """
        idx=self.build(replay)
        lap=int(lap)
        if reference_lap is None:
            reference_lap=idx.get('best_trace_lap') or idx.get('best_lap') or lap
        reference_lap=int(reference_lap)
        compared=self.compare_laps(replay,[lap,reference_lap])
        selected=self.lap_trace(replay,lap)
        ref=self.lap_trace(replay,reference_lap)
        samples=list(selected.get('samples') or [])
        timeline=[e for e in self.timeline(replay) if e.get('packet') is not None]

        # Build one shared corner authority from any available coach/reference
        # marker, then project those distances onto the selected lap.
        by_corner={}
        for row in self.corners(replay):
            dist=row.get('distance_m')
            if not isinstance(dist,(int,float)):
                continue
            for cid in row.get('corner_ids') or []:
                try: cid=int(cid)
                except Exception: continue
                by_corner.setdefault(cid,float(dist))

        # Old recordings often pre-date CORNER COACH validation files. Reuse the
        # shared physical track authority when possible; otherwise derive the same
        # geometry model directly from the selected replay lap. This keeps replay
        # analysis read-only while restoring T1..Tn navigation for legacy .areplay
        # files that still contain complete world-position telemetry.
        if not by_corner:
            sess=idx.get('session') or {}
            track_name=sess.get('track_name') or TRACKS.get(sess.get('track_id'))
            track_length=sess.get('track_length_m')
            turns=persisted_physical_turns(track_name,track_length) if track_name else ()
            if not turns and track_name and expected_turn_count(track_name):
                geom=[s for s in samples if isinstance(s.get('distance_m'),(int,float)) and isinstance(s.get('x'),(int,float)) and isinstance(s.get('z'),(int,float))]
                if len(geom)>=20:
                    turns=derive_physical_turns(
                        track_name,
                        [(float(s['x']),float(s['z'])) for s in geom],
                        point_distances_m=[float(s['distance_m']) for s in geom],
                        track_length_m=track_length,
                    )
            for turn in turns or ():
                cid=turn.get('corner_id'); dist=turn.get('apex_m') if isinstance(turn.get('apex_m'),(int,float)) else turn.get('lap_distance_m')
                if isinstance(cid,int) and cid>0 and isinstance(dist,(int,float)):
                    by_corner.setdefault(cid,float(dist))

        def nearest_sample(distance):
            if not samples:
                return None
            return min(samples,key=lambda s:abs(float(s.get('distance_m') or 0)-float(distance)))

        corner_rows=[]
        for cid,dist in sorted(by_corner.items(),key=lambda kv:kv[1]):
            near=nearest_sample(dist)
            if not near:
                continue
            # Deterministic phase anchors from the recorded telemetry itself.
            window=[s for s in samples if isinstance(s.get('distance_m'),(int,float)) and dist-260 <= float(s['distance_m']) <= dist+220]
            brake_candidates=[s for s in window if float(s.get('brake') or 0)>=0.10 and float(s.get('distance_m') or 0)<=dist+40]
            brake=min(brake_candidates,key=lambda s:float(s.get('distance_m') or 0),default=None)
            apex=min(window,key=lambda s:float(s.get('speed_kph') or 1e9),default=near) if window else near
            apex_d=float(apex.get('distance_m') or dist) if apex else dist
            throttle_candidates=[s for s in window if float(s.get('distance_m') or 0)>=apex_d and float(s.get('throttle') or 0)>=0.20]
            throttle=min(throttle_candidates,key=lambda s:float(s.get('distance_m') or 0),default=None)
            corner_rows.append({
                'corner_id':cid,'label':f'T{cid}','distance_m':round(dist,2),
                'packet':near.get('packet'),'brake_packet':brake.get('packet') if brake else None,
                'brake_distance_m':brake.get('distance_m') if brake else None,
                'apex_packet':apex.get('packet') if apex else None,'apex_distance_m':apex_d,
                'throttle_packet':throttle.get('packet') if throttle else None,
                'throttle_distance_m':throttle.get('distance_m') if throttle else None,
            })

        return {
            'file':idx.get('source',{}).get('file'),'session_uid':idx.get('session_uid'),
            'session':idx.get('session') or {},'lap':lap,'reference_lap':reference_lap,
            'lap_meta':selected.get('meta') or {},'reference_meta':ref.get('meta') or {},
            'distance_m':compared.get('distance_m') or [],'series':compared.get('series') or [],
            'samples':samples,'corners':corner_rows,'events':timeline,
        }

    def compare_sessions(self,left:str|Path,right:str|Path)->dict[str,Any]:
        a=self.build(left); b=self.build(right)
        atrack=(a.get('session') or {}).get('track_id'); btrack=(b.get('session') or {}).get('track_id')
        if atrack is not None and btrack is not None and int(atrack) != int(btrack):
            raise ValueError(f'Session comparison requires the same track: {atrack} != {btrack}')
        aformula=(a.get('session') or {}).get('formula'); bformula=(b.get('session') or {}).get('formula')
        if aformula is not None and bformula is not None and int(aformula) != int(bformula):
            raise ValueError(f'Session comparison requires the same formula: {aformula} != {bformula}')
        al=a.get('best_trace_lap') or a.get('best_lap') or (a.get('laps') or [{}])[0].get('lap'); bl=b.get('best_trace_lap') or b.get('best_lap') or (b.get('laps') or [{}])[0].get('lap')
        at=self.lap_trace(left,al) if al else {'samples':[],'meta':{}}; bt=self.lap_trace(right,bl) if bl else {'samples':[],'meta':{}}
        maxd=min(max([float(s['distance_m']) for s in at['samples']],default=0),max([float(s['distance_m']) for s in bt['samples']],default=0))
        grid=[float(x) for x in range(0,int(maxd)+1,10)]
        keys=['speed_kph','brake','throttle','steer','gear','ers_percent','rpm','g_lateral','g_longitudinal','g_vertical','x','z']
        def row(idx,tr,lap):
            r={'file':idx['source']['file'],'session_uid':idx.get('session_uid'),'lap':lap,'lap_time_s':tr.get('meta',{}).get('lap_time_s')}
            for k in keys:r[k]=self._interp(tr.get('samples') or [],k,grid)
            return r
        leftrow=row(a,at,al); rightrow=row(b,bt,bl)
        left_elapsed=self._interp(at.get('samples') or [], 'lap_time_s', grid)
        right_elapsed=self._interp(bt.get('samples') or [], 'lap_time_s', grid)
        leftrow['delta_s']=[0.0 if isinstance(v,(int,float)) else None for v in left_elapsed]
        rightrow['delta_s']=[round(float(r)-float(l),4) if isinstance(r,(int,float)) and isinstance(l,(int,float)) else None for r,l in zip(right_elapsed,left_elapsed)]
        return {'distance_m':grid,'left':leftrow,'right':rightrow,'best_lap_delta_s':round(float(rightrow['lap_time_s'])-float(leftrow['lap_time_s']),3) if isinstance(leftrow.get('lap_time_s'),(int,float)) and isinstance(rightrow.get('lap_time_s'),(int,float)) else None}
