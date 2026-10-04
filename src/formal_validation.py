"""V1.5.0.0 deterministic validation helpers for release hardening."""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from pathlib import Path
import json, time, zipfile


def _read_jsonl(path):
    rows=[]
    p=Path(path)
    if not p.exists(): return rows
    for line in p.read_text(encoding='utf-8',errors='replace').splitlines():
        try: rows.append(json.loads(line))
        except Exception: pass
    return rows


def validate_corner_trace(path)->dict:
    rows=_read_jsonl(path); counts={}; problems=[]; refs=[]
    last_lap=None
    for r in rows:
        typ=str(r.get('event') or r.get('type') or r.get('kind') or 'unknown'); counts[typ]=counts.get(typ,0)+1
        lap=r.get('lap') or r.get('lap_number')
        if isinstance(lap,int) and isinstance(last_lap,int) and lap < last_lap-1: problems.append({'type':'lap_regression','from':last_lap,'to':lap})
        if isinstance(lap,int): last_lap=lap
        fp=r.get('reference_fingerprint') or (r.get('reference') or {}).get('fingerprint') if isinstance(r.get('reference'),dict) else r.get('reference_fingerprint')
        if fp and fp not in refs: refs.append(fp)
    return {'ok':bool(rows) and not problems,'rows':len(rows),'event_counts':counts,'reference_fingerprints':refs,'problems':problems}


def validate_transcript_consistency(path)->dict:
    rows=_read_jsonl(path); problems=[]; sessions=[]; message_ids=set(); dup=0
    for r in rows:
        uid=r.get('session_uid') or (r.get('session') or {}).get('uid') if isinstance(r.get('session'),dict) else r.get('session_uid')
        if uid is not None and uid not in sessions: sessions.append(uid)
        mid=r.get('message_id')
        if mid:
            if mid in message_ids: dup+=1
            message_ids.add(mid)
        if r.get('delivered') is False and r.get('spoken') is True: problems.append({'type':'spoken_without_delivery','row':r})
    return {'ok':bool(rows) and not problems,'rows':len(rows),'sessions':sessions,'duplicate_message_ids':dup,'problems':problems}


def validate_bundle(path)->dict:
    p=Path(path); problems=[]; names=[]; manifest={}
    try:
        with zipfile.ZipFile(p) as z:
            names=z.namelist()
            if 'manifest.json' not in names: problems.append('missing_manifest')
            else: manifest=json.loads(z.read('manifest.json'))
            if any(n.lower().endswith('.areplay') for n in names): problems.append('embedded_large_recording')
            for req in ('strategy_decisions.json','pit_decisions.json','reference_history.json','performance_metrics.json'):
                if req not in names: problems.append('missing_'+req)
    except Exception as e: problems.append('invalid_zip:'+str(e))
    return {'ok':not problems,'problems':problems,'files':names,'manifest':manifest}


def benchmark_replay_index(service, replay)->dict:
    start=time.perf_counter(); result=service.build(replay); elapsed=time.perf_counter()-start
    data=result if isinstance(result,dict) else (asdict(result) if is_dataclass(result) else getattr(result,'__dict__',{}))
    return {'ok':True,'elapsed_s':round(elapsed,4),'laps':len(data.get('laps') or []),'track_id':data.get('track_id'),'session_uid':data.get('session_uid')}


def scenario_matrix()->list[dict]:
    return [
      {'id':'weekend_transition','required':True,'evidence':'session UID markers + reset audit'},
      {'id':'long_race','required':True,'evidence':'runtime/performance bundle'},
      {'id':'wet_dry','required':True,'evidence':'forecast + tyre transition decisions'},
      {'id':'sc_vsc','required':True,'evidence':'separate measured pit-cycle samples'},
      {'id':'pit_window','required':True,'evidence':'EA ideal/latest + decision history'},
      {'id':'damage','required':True,'evidence':'damage event + measured pace attribution'},
      {'id':'tyre_degradation','required':True,'evidence':'same-set measured lap trend'},
      {'id':'fuel_ers','required':True,'evidence':'measured margins/energy balance'},
      {'id':'combat','required':True,'evidence':'context enter/exit + coaching suppression'},
      {'id':'session_best','required':True,'evidence':'lap-boundary reference_update'},
      {'id':'race_finish','required':True,'evidence':'finish + summary transcript'},
      {'id':'latency_load','required':True,'evidence':'latency + CPU/RAM/frame continuity'},
      {'id':'replay_live_parity','required':True,'evidence':'signature comparison'},
    ]


def write_validation_report(path, *, checks, title='V1.5.0.0 Formal Validation Report'):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    passed=sum(1 for x in checks if x.get('ok')); failed=len(checks)-passed
    lines=[f'# {title}','',f'- Checks: {len(checks)}',f'- Passed: {passed}',f'- Failed/unverified: {failed}','']
    for x in checks:
        lines.append(f"## {'PASS' if x.get('ok') else 'UNVERIFIED/FAIL'} — {x.get('name','check')}")
        lines.append('```json'); lines.append(json.dumps(x,indent=2,default=str)); lines.append('```'); lines.append('')
    p.write_text('\n'.join(lines),encoding='utf-8'); return p
