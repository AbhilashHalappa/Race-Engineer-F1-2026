"""Separate measured straight-line time changes from corner-region losses."""
from __future__ import annotations

import math
from typing import Any


def _num(v: Any) -> bool:
    return isinstance(v, (int,float)) and math.isfinite(v)


def _samples(lap):
    out={}
    if not isinstance(lap,dict): return out
    for k,row in (lap.get('_samples') or {}).items():
        if not isinstance(row,dict): continue
        try:d=float(k)
        except (TypeError,ValueError):
            if not _num(row.get('d')): continue
            d=float(row['d'])
        if _num(row.get('t')): out[round(d/5.0)*5.0]=float(row['t'])
    return out


def _delta_trace(current,reference):
    c,r=_samples(current),_samples(reference); common=sorted(set(c)&set(r))
    if not common:return []
    d0=common[0]; c0=c[d0]; r0=r[d0]
    return [(d,(c[d]-c0)-(r[d]-r0)) for d in common]


def _nearest(trace,d):
    if not trace or not _num(d):return None
    row=min(trace,key=lambda x:abs(x[0]-float(d)))
    return row[1] if abs(row[0]-float(d))<=10 else None


def straight_line_analysis(current: dict[str,Any]|None, reference: dict[str,Any]|None) -> dict[str,Any]:
    if not current or not reference:return {'available':False,'reason':'missing_lap'}
    trace=_delta_trace(current,reference)
    if not trace:return {'available':False,'reason':'time_alignment_unavailable'}
    secs=[s for s in (reference.get('sections') or []) if isinstance(s,dict) and _num(s.get('start_m')) and _num(s.get('end_m'))]
    secs.sort(key=lambda s:float(s['start_m']))
    rows=[]
    for i,sec in enumerate(secs):
        start=float(sec.get('end_m'))+20.0
        if i+1<len(secs): end=float(secs[i+1]['start_m'])-20.0
        else: end=trace[-1][0]
        if end-start<50:continue
        a,b=_nearest(trace,start),_nearest(trace,end)
        if not _num(a) or not _num(b):continue
        loss=float(b)-float(a)
        rows.append({'after_corner_id':sec.get('id'),'start_m':start,'end_m':end,'time_delta_change_s':loss})
    rows.sort(key=lambda x:x['time_delta_change_s'],reverse=True)
    return {
        'available':bool(rows),
        'straights':rows,
        'largest_straight_loss':rows[0] if rows and rows[0]['time_delta_change_s']>0 else None,
        'total_positive_straight_loss_s':sum(max(0.0,x['time_delta_change_s']) for x in rows),
        'interpretation':'matched-distance time change on reference-defined straights; descriptive only',
    }
