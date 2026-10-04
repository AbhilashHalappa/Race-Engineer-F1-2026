"""Portable reference-lap package import/export and compatibility validation."""
from __future__ import annotations
import json, hashlib
from pathlib import Path
from typing import Any

SCHEMA = "RACE_ENGINEER_REFERENCE_V1"

def _clean(v):
    if isinstance(v, dict): return {str(k): _clean(x) for k,x in v.items() if not str(k).startswith('_')}
    if isinstance(v, list): return [_clean(x) for x in v]
    return v

def build_reference_package(lap: dict[str,Any], *, metadata: dict[str,Any]|None=None) -> dict[str,Any]:
    clean=_clean(lap)
    payload={"schema":SCHEMA,"metadata":dict(metadata or {}),"lap":clean}
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()
    payload["sha256"]=hashlib.sha256(raw).hexdigest()
    return payload

def export_reference(path: str|Path, lap: dict[str,Any], *, metadata=None) -> Path:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(build_reference_package(lap,metadata=metadata),indent=2,default=str),encoding='utf-8')
    return p

def load_reference(path: str|Path) -> dict[str,Any]:
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data,dict) or data.get('schema')!=SCHEMA or not isinstance(data.get('lap'),dict):
        raise ValueError('unsupported reference package')
    return data

def validate_reference(pkg: dict[str,Any], *, track_id=None, game_year=None, car=None, assists=None) -> dict[str,Any]:
    md=pkg.get('metadata') if isinstance(pkg,dict) else {}
    md=md if isinstance(md,dict) else {}
    issues=[]
    for key,expected in (("track_id",track_id),("game_year",game_year),("car",car)):
        if expected is not None and md.get(key) is not None and str(md.get(key))!=str(expected): issues.append(f"{key}_mismatch")
    if assists is not None and md.get('assists') is not None and md.get('assists')!=assists: issues.append('assists_mismatch')
    lap=pkg.get('lap') if isinstance(pkg,dict) else None
    if not isinstance(lap,dict) or not lap.get('sections') or not isinstance(lap.get('lap_time_s'),(int,float)): issues.append('incomplete_lap')
    return {"valid":not issues,"issues":issues,"metadata":md}
