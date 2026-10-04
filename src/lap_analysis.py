"""V0.9.8.2 deterministic full-lap reconciled time gain/loss analysis.

All conclusions are derived from already-observed telemetry.  The module aligns
completed laps by physical track distance, normalises timing at the first common
sample, and reports measured associations without claiming causation.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from bisect import bisect_left
import json, math
from pathlib import Path

MATCH_TOLERANCE_M = 250.0
TRACE_STEP_M = 25.0
BOUNDARY_GUARD_M = 150.0


def _num(v): return isinstance(v,(int,float)) and math.isfinite(v)
def _delta(a,b): return a-b if _num(a) and _num(b) else None

def _anchor(s):
    v=s.get('min_speed_m')
    return float(v) if _num(v) else (float(s['start_m']) if _num(s.get('start_m')) else None)

def match_sections_by_distance(current, reference, tolerance_m=MATCH_TOLERANCE_M):
    """Globally align detected zones by physical position.

    Dynamic programming is used instead of greedy current-first matching.  This
    lets a weak/extra brake event remain unmatched rather than stealing the
    reference corner and shifting every later comparison.
    """
    cur=[x for x in current.get('sections',()) if _anchor(x) is not None]
    ref=[x for x in reference.get('sections',()) if _anchor(x) is not None]
    n,m=len(cur),len(ref)
    if not n or not m:return []
    # Skipping an event is deliberately cheaper than a poor physical match.
    skip=90.0
    inf=1e18
    dp=[[inf]*(m+1) for _ in range(n+1)]; prev=[[None]*(m+1) for _ in range(n+1)]
    dp[0][0]=0.0
    for i in range(n+1):
        for j in range(m+1):
            base=dp[i][j]
            if base>=inf:continue
            if i<n and base+skip<dp[i+1][j]: dp[i+1][j]=base+skip; prev[i+1][j]=(i,j,'skip_cur')
            if j<m and base+skip<dp[i][j+1]: dp[i][j+1]=base+skip; prev[i][j+1]=(i,j,'skip_ref')
            if i<n and j<m:
                d=abs(_anchor(cur[i])-_anchor(ref[j]))
                if d<=tolerance_m:
                    # Position dominates. Peak-brake similarity is a small tie breaker.
                    cp,rp=cur[i].get('peak_brake'),ref[j].get('peak_brake')
                    strength=20.0*abs(cp-rp) if _num(cp) and _num(rp) else 0.0
                    cost=d+strength
                    if base+cost<dp[i+1][j+1]: dp[i+1][j+1]=base+cost; prev[i+1][j+1]=(i,j,'match')
    pairs=[]; i,j=n,m
    while i or j:
        q=prev[i][j]
        if q is None:break
        pi,pj,op=q
        if op=='match':pairs.append((cur[pi],ref[pj]))
        i,j=pi,pj
    pairs.reverse(); return pairs

@dataclass(slots=True)
class CornerComparison:
    section:int; reference_section:int|None; anchor_delta_m:float|None
    current_brake_m:float|None; reference_brake_m:float|None; brake_point_delta_m:float|None
    current_min_speed_kph:float|None; reference_min_speed_kph:float|None; min_speed_delta_kph:float|None
    current_full_throttle_m:float|None; reference_full_throttle_m:float|None; full_throttle_delta_m:float|None
    current_exit_speed_kph:float|None; reference_exit_speed_kph:float|None; exit_speed_delta_kph:float|None
    current_peak_brake:float|None; reference_peak_brake:float|None; peak_brake_delta:float|None
    current_max_slip:float|None; reference_max_slip:float|None; max_slip_delta:float|None

def compare_sections(current,reference):
    result=[]
    for cur,ref in match_sections_by_distance(current,reference):
        result.append(CornerComparison(
            section=cur.get('id'), reference_section=ref.get('id'), anchor_delta_m=_delta(_anchor(cur),_anchor(ref)),
            current_brake_m=cur.get('start_m'),reference_brake_m=ref.get('start_m'),brake_point_delta_m=_delta(cur.get('start_m'),ref.get('start_m')),
            current_min_speed_kph=cur.get('min_speed_kph'),reference_min_speed_kph=ref.get('min_speed_kph'),min_speed_delta_kph=_delta(cur.get('min_speed_kph'),ref.get('min_speed_kph')),
            current_full_throttle_m=cur.get('full_throttle_m'),reference_full_throttle_m=ref.get('full_throttle_m'),full_throttle_delta_m=_delta(cur.get('full_throttle_m'),ref.get('full_throttle_m')),
            current_exit_speed_kph=cur.get('exit_speed_kph'),reference_exit_speed_kph=ref.get('exit_speed_kph'),exit_speed_delta_kph=_delta(cur.get('exit_speed_kph'),ref.get('exit_speed_kph')),
            current_peak_brake=cur.get('peak_brake'),reference_peak_brake=ref.get('peak_brake'),peak_brake_delta=_delta(cur.get('peak_brake'),ref.get('peak_brake')),
            current_max_slip=cur.get('max_slip'),reference_max_slip=ref.get('max_slip'),max_slip_delta=_delta(cur.get('max_slip'),ref.get('max_slip'))))
    return result


def _sample_map(lap):
    return {float(k):v for k,v in lap.get('_samples',{}).items() if _num(float(k))}

def _aligned_delta(cur, ref):
    """Return (distance, normalised elapsed-time delta) on common 5 m samples."""
    ca,ra=_sample_map(cur),_sample_map(ref)
    common=sorted(set(ca)&set(ra))
    if not common:return [],ca,ra
    d0=common[0]; c0=ca[d0].get('t'); r0=ra[d0].get('t')
    if not _num(c0) or not _num(r0):return [],ca,ra
    out=[]
    for d in common:
        ct,rt=ca[d].get('t'),ra[d].get('t')
        if _num(ct) and _num(rt): out.append((d,(ct-c0)-(rt-r0)))
    return out,ca,ra

def _nearest_delta(trace, d, tolerance=10.0):
    if not trace or not _num(d):return None
    x=min(trace,key=lambda z:abs(z[0]-d))
    return x[1] if abs(x[0]-d)<=tolerance else None

def _mean_field(samples, lo, hi, field):
    vals=[v.get(field) for d,v in samples.items() if lo<=d<=hi and _num(v.get(field))]
    return sum(vals)/len(vals) if vals else None

def _phase(name, lo, hi, trace, ca, ra):
    if not (_num(lo) and _num(hi)) or hi<=lo:return None
    a,b=_nearest_delta(trace,lo),_nearest_delta(trace,hi)
    loss=(b-a) if _num(a) and _num(b) else None
    out={'phase':name,'start_m':round(lo,1),'end_m':round(hi,1),'time_delta_change_s':round(loss,4) if _num(loss) else None}
    for field,label in [('speed','mean_speed_kph_delta'),('throttle','mean_throttle_delta'),('brake','mean_brake_delta')]:
        x,y=_mean_field(ca,lo,hi,field),_mean_field(ra,lo,hi,field)
        out[label]=round(x-y,4) if _num(x) and _num(y) else None
    return out

def _corner_driving_analysis(cur,ref,trace,ca,ra):
    """Partition the common lap into mutually-exclusive matched driving regions.

    Region boundaries are midpoints between consecutive matched corner anchors.
    The first/last regions extend to the first/last common telemetry sample, so
    every aligned metre belongs to exactly one region and regional delta changes
    telescope back to the final normalised lap delta.
    """
    pairs=match_sections_by_distance(cur,ref)
    if not pairs or not trace:return []
    anchors=[]
    for c,r in pairs:
        vals=[_anchor(c),_anchor(r)]
        vals=[x for x in vals if _num(x)]
        if vals: anchors.append((sum(vals)/len(vals),c,r))
    anchors.sort(key=lambda x:x[0])
    if not anchors:return []
    dmin,dmax=trace[0][0],trace[-1][0]
    boundaries=[dmin]
    for i in range(len(anchors)-1):
        boundaries.append((anchors[i][0]+anchors[i+1][0])/2.0)
    boundaries.append(dmax)
    rows=[]
    for i,(anchor,c,r) in enumerate(anchors):
        lo,hi=boundaries[i],boundaries[i+1]
        brake_candidates=[x for x in (c.get('start_m'),r.get('start_m')) if _num(x)]
        brake=min(brake_candidates) if brake_candidates else anchor
        brake=max(lo,min(hi,brake))
        apex=max(brake,min(hi,anchor))
        phases=[p for p in (
            _phase('approach',lo,brake,trace,ca,ra),
            _phase('braking_to_min_speed',brake,apex,trace,ca,ra),
            _phase('exit',apex,hi,trace,ca,ra)) if p]
        a,b=_nearest_delta(trace,lo),_nearest_delta(trace,hi)
        region_change=(b-a) if _num(a) and _num(b) else None
        worst=max(phases,key=lambda p:p['time_delta_change_s'] if _num(p['time_delta_change_s']) else -1e9) if phases else None
        rows.append({'section':c.get('id'),'reference_section':r.get('id'),'anchor_m':round(anchor,1),
            'region_start_m':round(lo,1),'region_end_m':round(hi,1),'region_time_delta_change_s':round(region_change,4) if _num(region_change) else None,
            'zone_start_m':round(lo,1),'zone_end_m':round(hi,1),'zone_time_delta_change_s':round(region_change,4) if _num(region_change) else None,
            'largest_loss_phase':worst['phase'] if worst and _num(worst.get('time_delta_change_s')) and worst['time_delta_change_s']>0 else None,
            'phases':phases,
            'measured_differences':{'brake_point_delta_m':_delta(c.get('start_m'),r.get('start_m')),'min_speed_kph_delta':_delta(c.get('min_speed_kph'),r.get('min_speed_kph')),'full_throttle_delta_m':_delta(c.get('full_throttle_m'),r.get('full_throttle_m')),'exit_speed_kph_delta':_delta(c.get('exit_speed_kph'),r.get('exit_speed_kph'))}})
    return rows

def build_driving_analysis(cur,ref):
    trace,ca,ra=_aligned_delta(cur,ref)
    if not trace:return {'available':False,'reason':'No common distance-aligned samples.'}
    dmin,dmax=trace[0][0],trace[-1][0]
    # Compact 25 m trace for UI/graphs while retaining 5 m internally.
    compact=[]; next_d=dmin
    for d,v in trace:
        if d+1e-9>=next_d:
            compact.append({'distance_m':d,'delta_s':round(v,4)}); next_d=d+TRACE_STEP_M
    # Find strongest local 100 m loss/gain away from start/finish boundary.
    windows=[]
    usable=[z for z in trace if z[0]>=dmin+BOUNDARY_GUARD_M and z[0]<=dmax-BOUNDARY_GUARD_M]
    trace_distances=[z[0] for z in trace]
    for d,v in usable:
        target=d-100.0
        j=bisect_left(trace_distances,target)
        candidates=[]
        if j<len(trace): candidates.append(j)
        if j>0: candidates.append(j-1)
        k=min(candidates,key=lambda idx:(abs(trace_distances[idx]-target),idx))
        prev=trace[k]
        if abs(prev[0]-target)<=10: windows.append((v-prev[1],prev[0],d))
    loss=max(windows,key=lambda z:z[0]) if windows else None; gain=min(windows,key=lambda z:z[0]) if windows else None
    corners=_corner_driving_analysis(cur,ref,trace,ca,ra)
    ranked=sorted((x for x in corners if _num(x.get('region_time_delta_change_s'))),key=lambda x:x['region_time_delta_change_s'],reverse=True)
    finish=trace[-1][1]
    region_sum=sum(x['region_time_delta_change_s'] for x in corners if _num(x.get('region_time_delta_change_s')))
    reconciliation_error=region_sum-finish
    official=(cur.get('lap_time_s')-ref.get('lap_time_s')) if _num(cur.get('lap_time_s')) and _num(ref.get('lap_time_s')) else None
    boundary_residual=(official-finish) if _num(official) else None
    full_accounted=(region_sum+boundary_residual) if _num(boundary_residual) else None
    full_error=(full_accounted-official) if _num(full_accounted) and _num(official) else None
    return {'available':True,'alignment':'physical lap distance; timing normalised at first common sample','distance_bin_m':5.0,'trace_step_m':TRACE_STEP_M,
        'first_common_m':dmin,'last_common_m':dmax,'finish_normalized_delta_s':round(finish,4),
        'lap_time_delta_s':round(official,4) if _num(official) else None,
        'boundary_timing_residual_s':round(boundary_residual,4) if _num(boundary_residual) else None,
        'full_lap_accounted_delta_s':round(full_accounted,4) if _num(full_accounted) else None,
        'full_lap_reconciliation_error_s':round(full_error,4) if _num(full_error) else None,
        'boundary_guard_m':BOUNDARY_GUARD_M,
        'largest_clean_100m_loss':({'delta_s':round(loss[0],4),'start_m':loss[1],'end_m':loss[2]} if loss else None),
        'largest_clean_100m_gain':({'delta_s':round(gain[0],4),'start_m':gain[1],'end_m':gain[2]} if gain else None),
        'time_delta_trace':compact,'corner_phase_analysis':corners,
        'region_delta_sum_s':round(region_sum,4),'region_reconciliation_error_s':round(reconciliation_error,4),
        'regions_non_overlapping':True,'common_distance_fully_partitioned':True,
        'largest_measured_loss_regions':[{'section':x['section'],'reference_section':x['reference_section'],'anchor_m':x['anchor_m'],'time_delta_change_s':x['region_time_delta_change_s'],'largest_loss_phase':x['largest_loss_phase']} for x in ranked[:3] if x['region_time_delta_change_s']>0],
        'interpretation_rule':'Physical regions are mutually exclusive and cover the common aligned distance. Any official-lap-time difference not observed by the normalised common-distance trace is reported separately as a boundary timing residual and is never assigned to a corner. Time changes are measured associations; they are not asserted as causal.'}

def _clean_lap(lap): return {k:v for k,v in lap.items() if k not in ('_samples','_metric_applicability')}
def build_session_analysis(performance):
    laps=list(performance.completed); valid=[x for x in laps if x.get('valid') and _num(x.get('lap_time_s')) and x.get('lap_time_s')>0]
    best=min(valid,key=lambda x:x['lap_time_s']) if valid else None; comps=[]
    if best:
        for lap in valid:
            if lap is best: continue
            base=performance.compare(lap,best) or {}; base['reference_type']='best_valid_lap'
            corners=[asdict(x) for x in compare_sections(lap,best)]; base['corners']=corners; base['matched_corner_count']=len(corners)
            from .coaching_analysis import build_corner_analyses, build_performance_pipeline
            pipeline=build_performance_pipeline(lap,best)
            analyses=[dict(x) for x in (pipeline.get('corner_analyses') or ()) if isinstance(x,dict)]
            if not analyses:
                analyses=[x.to_dict() for x in build_corner_analyses(lap,best)]
            base['corner_analyses']=analyses
            base['driving_performance_engine']={'version':'1.8.0.0','turns':pipeline.get('turns') or [],
                'reconciliation_error_s':pipeline.get('reconciliation_error_s')}
            base['driving_analysis']=build_driving_analysis(lap,best)
            comps.append(base)
    # V0.9.20.2: rank loss-guarded issues and build deterministic multi-lap
    # coaching memory. This layer consumes CornerAnalysis; it never re-derives
    # telemetry or changes the underlying diagnosis measurements.
    from .coaching_priority import build_session_coaching
    coaching = build_session_coaching(comps)
    by_lap = {x.get('lap'): x for x in coaching.get('per_lap_priority', []) if isinstance(x, dict)}
    for comp in comps:
        comp['coaching_priority'] = by_lap.get(comp.get('lap'))
    return {'format':'RACE_ENGINEER_LAP_ANALYSIS','version':'0.9.10.0','coaching_schema_version':'1.8.0.0','driving_performance_schema_version':'1.8.0.0','method':'event-aware measured telemetry aligned to authoritative F1 Session History lap number/time/validity; 5 m distance alignment; filtered physical corner-braking sections; V0.9.20.1.2 20ms-deadband loss-guarded deterministic corner diagnosis; V0.9.20.2 deterministic priority scoring and multi-lap issue memory; V1.0.0 integrated pre/post-corner coaching, potential, technique, report, history and racing-line support; hysteresis steering reversals; global stable corner matching; non-overlapping driving regions; official full-lap reconciliation with explicit boundary residual; no prediction or causal claims','event_context':getattr(performance,'event_context',None),'completed_lap_count':len(laps),'valid_timed_lap_count':len(valid),'best_valid_lap':best.get('lap') if best else None,'best_valid_lap_time_s':best.get('lap_time_s') if best else None,'laps':[_clean_lap(x) for x in laps],'comparisons_to_best':comps,'session_coaching':coaching.get('memory',{})}
def write_session_analysis(performance,path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); r=build_session_analysis(performance); path.write_text(json.dumps(r,indent=2),encoding='utf-8'); return r
