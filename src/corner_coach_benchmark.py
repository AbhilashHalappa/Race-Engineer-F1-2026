"""Offline CORNER COACH delivery/sequence validation for replay traces.

This harness uses game/session timestamps rather than wall-clock replay speed, so
fast replay remains representative of the driver's real available airtime.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _num(v: Any) -> bool:
    return isinstance(v,(int,float))


def load_trace(path: str | Path) -> list[dict[str,Any]]:
    rows=[]
    for line in Path(path).read_text(encoding='utf-8',errors='replace').splitlines():
        try:r=json.loads(line)
        except Exception:continue
        if isinstance(r,dict):rows.append(r)
    return rows


def analyse_trace(path: str | Path) -> dict[str,Any]:
    rows=load_trace(path)
    run=next((r for r in rows if r.get('event')=='run_start'),{})
    emits=[]
    for r in rows:
        e=r.get('event')
        if e in {'pre_emit','pre_emit_next_lap','post_emit'} and _num(r.get('session_time_s')):
            kind='PRE' if str(e).startswith('pre_') else 'POST'
            duration=float(r.get('estimated_duration_s') or 0.0)
            arrival=float(r['session_time_s'])
            if kind=='PRE':
                budget=float(r.get('deadline_in_s') or r.get('ttb_s') or 0.0)
            else:
                raw=r.get('airtime_budget_s')
                budget=float(raw) if _num(raw) else 999.0
            emits.append({'kind':kind,'lap':r.get('target_lap') if kind=='PRE' else r.get('lap'),
                          'zone_id':r.get('zone_id'),'arrival':arrival,'duration':duration,
                          'deadline':arrival+budget,'budget':budget,'variant':r.get('speech_variant')})
    emits.sort(key=lambda x:(x['arrival'],0 if x['kind']=='PRE' else 1))

    # Deterministic one-channel simulation. PRE can pre-empt an active POST/older
    # PRE only when waiting would miss the incoming PRE's finish deadline.
    active=None; late=[]; preemptions=[]; starts=[]
    for msg in emits:
        now=msg['arrival']
        if active is not None and active['end']<=now:
            active=None
        if active is not None:
            if msg['kind']=='PRE' and active['end']+msg['duration']>msg['deadline']:
                preemptions.append({'from':active['kind'],'from_zone':active['zone_id'],'to_zone':msg['zone_id'],'at':now})
                active=None
        start=now if active is None else active['end']
        end=start+msg['duration']
        if end>msg['deadline']+1e-6:
            late.append({**msg,'start':start,'finish':end,'late_by_s':end-msg['deadline']})
            # A message that cannot finish is not allowed to occupy the simulated channel.
            continue
        active={**msg,'start':start,'end':end}
        starts.append(active)

    counts={name:sum(1 for r in rows if r.get('event')==name) for name in (
        'pre_emit','pre_emit_next_lap','pre_missed','pre_suppressed','post_emit','post_suppressed','post_expired')}
    summaries=[r for r in rows if r.get('event')=='lap_summary']
    order_ok=all(bool(r.get('zone_order_ok',True)) and bool(r.get('physical_order_ok',True)) for r in summaries)
    discontinuities=[r for r in rows if r.get('event')=='telemetry_discontinuity']
    return {
        'path':str(path),'track':run.get('track_name'),'reference_lap_time_s':run.get('reference_lap_time_s'),
        'emitted_count':len(emits),'pre_emitted':sum(1 for x in emits if x['kind']=='PRE'),'post_emitted':sum(1 for x in emits if x['kind']=='POST'),
        'simulated_spoken_count':len(starts),'late_count':len(late),'late':late,'preemptions':preemptions,
        'counts':counts,'lap_summary_count':len(summaries),'order_ok':order_ok,
        'telemetry_discontinuity_count':len(discontinuities),'data_compromised':bool(discontinuities),
        'pass':not late and counts['pre_missed']==0 and counts['pre_suppressed']==0 and order_ok,
        'acceptance':'SAFE_SUPPRESSION_ON_COMPROMISED_DATA' if discontinuities and not late and counts['pre_missed']==0 else ('PASS' if not late and counts['pre_missed']==0 and counts['pre_suppressed']==0 and order_ok else 'FAIL'),
    }


def analyse_directory(directory: str | Path) -> list[dict[str,Any]]:
    return [analyse_trace(p) for p in sorted(Path(directory).glob('CORNER_COACH_*.jsonl'))]
