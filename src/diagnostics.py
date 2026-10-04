"""Built-in deterministic health checks and diagnostic bundle export."""
from __future__ import annotations
import json, platform, sys, zipfile, sqlite3, tempfile
from pathlib import Path
from datetime import datetime, timezone

def telemetry_health(state) -> dict:
    player=getattr(state,'player',None); telem=getattr(player,'telemetry',None) if player else None; lap=getattr(player,'lap',None) if player else None
    checks={"player":player is not None,"telemetry":telem is not None,"lap":lap is not None}
    return {"ok":all(checks.values()),"checks":checks}

def latency_health(snapshot: dict|None) -> dict:
    s=snapshot or {}; vals=[v for k,v in s.items() if 'latency' in str(k).lower() and isinstance(v,(int,float))]
    return {"available":bool(vals),"max_ms":max(vals) if vals else None,"ok":(max(vals)<=100.0) if vals else None}

def export_bundle(path=None, *, extra_files=()):
    from .app_paths import DIAGNOSTICS
    p=Path(path) if path is not None else DIAGNOSTICS/'diagnostic_bundle.zip'; p.parent.mkdir(parents=True,exist_ok=True)
    manifest={"created_utc":datetime.now(timezone.utc).isoformat(),"python":sys.version,"platform":platform.platform()}
    with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
        for name in ('settings/coaching.json','settings/product.json','analysis/driver_history.json','maps/track_landmarks.json','analysis/diagnostics/update_status.json'):
            q=Path(name)
            if q.exists(): z.write(q,name)
        # Snapshot the live Performance Hub database through SQLite's backup API.
        # Copying a WAL-backed database file directly can produce an inconsistent
        # diagnostic artifact while a live session is committing history.
        from .app_paths import PERFORMANCE_DB
        db=Path(PERFORMANCE_DB)
        if db.exists():
            tmp_name=None
            try:
                with tempfile.NamedTemporaryFile(prefix='race_engineer_perf_',suffix='.sqlite3',delete=False) as tmp:
                    tmp_name=tmp.name
                src=sqlite3.connect(f'file:{db.resolve()}?mode=ro',uri=True,timeout=2.0)
                dst=sqlite3.connect(tmp_name)
                try:
                    src.backup(dst)
                finally:
                    dst.close(); src.close()
                z.write(tmp_name,'analysis/performance_history_live.sqlite3')
            except Exception as exc:
                z.writestr('analysis/performance_history_backup_error.txt',str(exc))
            finally:
                if tmp_name:
                    try: Path(tmp_name).unlink(missing_ok=True)
                    except Exception: pass
        # Include the newest CORNER COACH validation trace automatically; it is
        # the authoritative sequencing/radio diagnostic artifact from V1.1.0.12.
        trace_dir=Path('analysis/corner_coach_validation')
        traces=sorted(trace_dir.glob('*.jsonl'),key=lambda x:x.stat().st_mtime,reverse=True)[:1] if trace_dir.exists() else []
        for q in traces:
            z.write(q,f'corner_coach_validation/{q.name}')
        crash_dir=Path('logs/crash')
        crashes=sorted(crash_dir.glob('crash_*.log'),key=lambda x:x.stat().st_mtime,reverse=True)[:3] if crash_dir.exists() else []
        for q in crashes:
            z.write(q,f'crash/{q.name}')
        for q in extra_files:
            q=Path(q)
            if q.exists() and q.is_file(): z.write(q,q.name)
    return p
