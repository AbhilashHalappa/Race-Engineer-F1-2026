"""Local recording/session library helpers.

V1.3.6.0 expands the original metadata helper into a safe local session library.
All destructive actions default to archive rather than permanent deletion.
"""
from __future__ import annotations
from pathlib import Path
import json
from typing import Any
from .replay_analysis import ReplayAnalysisService

class SessionLibrary:
    def __init__(self, recordings=None, metadata=None, reports=None):
        from .app_paths import RECORDINGS, SESSION_LIBRARY, REPORTS
        self.recordings=Path(recordings) if recordings is not None else RECORDINGS; self.metadata=Path(metadata) if metadata is not None else SESSION_LIBRARY; self.reports=Path(reports) if reports is not None else REPORTS
        self.replay_analysis=ReplayAnalysisService(recordings=self.recordings,reports=self.reports)
    def _meta(self):
        try:
            d=json.loads(self.metadata.read_text(encoding='utf-8')); return d if isinstance(d,dict) else {}
        except Exception: return {}
    def _save(self,d):
        self.metadata.parent.mkdir(parents=True,exist_ok=True); self.metadata.write_text(json.dumps(d,indent=2,sort_keys=True),encoding='utf-8')
    def _report_for(self,p:Path):
        exact=self.reports/(p.stem+'.html')
        if exact.exists(): return exact
        matches=sorted(self.reports.glob(p.stem+'*.html'),key=lambda q:q.stat().st_mtime,reverse=True) if self.reports.exists() else []
        return matches[0] if matches else None
    def _row(self,p:Path,meta:dict,*,archived=False):
        m=meta.get(p.name,{}) if isinstance(meta.get(p.name),dict) else {}
        report=self._report_for(p)
        row={"file":p.name,"path":str(p),"size":p.stat().st_size,"mtime":p.stat().st_mtime,"favorite":bool(m.get('favorite')),"tags":list(m.get('tags') or []),"name":m.get('name') or p.stem,"report":str(report) if report else None,"archived":bool(archived),"notes":str(m.get('notes') or '')}
        try:
            idx=self.replay_analysis.build(p)
            assoc=idx.get('associations',{})
            if isinstance(m.get('associations'),dict):
                assoc={**assoc,**{k:v for k,v in m['associations'].items() if v}}
            row.update({"session_uid":idx.get('session_uid'),"packet_count":idx.get('packet_count'),"best_lap":idx.get('best_lap'),"best_trace_lap":idx.get('best_trace_lap'),"laps":idx.get('laps',[]),"session":idx.get('session',{}),"associations":assoc})
        except Exception as error:
            row['index_error']=str(error)
        return row
    def list(self,*,include_archived=False):
        meta=self._meta(); rows=[]
        if self.recordings.exists():
            for p in sorted(self.recordings.glob('*.areplay'),key=lambda x:x.stat().st_mtime,reverse=True): rows.append(self._row(p,meta))
        if include_archived:
            archive=self.recordings/'archive'
            if archive.exists():
                for p in sorted(archive.glob('*.areplay'),key=lambda x:x.stat().st_mtime,reverse=True): rows.append(self._row(p,meta,archived=True))
        return rows
    def update(self, filename, **changes):
        d=self._meta(); row=d.get(filename,{}) if isinstance(d.get(filename),dict) else {}
        if 'tags' in changes: changes['tags']=sorted({str(x).strip() for x in (changes.get('tags') or []) if str(x).strip()})
        if 'favorite' in changes: changes['favorite']=bool(changes['favorite'])
        row.update(changes); d[filename]=row; self._save(d); return row
    def rename(self,filename,name): return self.update(filename,name=str(name).strip())
    def tag(self,filename,*tags):
        old=self._meta().get(filename,{}) if isinstance(self._meta().get(filename),dict) else {}
        return self.update(filename,tags=list(old.get('tags') or [])+list(tags))
    def favorite(self,filename,enabled=True): return self.update(filename,favorite=bool(enabled))
    def archive(self, filename):
        src=self.recordings/filename
        if not src.exists(): raise FileNotFoundError(src)
        dst=self.recordings/'archive'/filename; dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists(): raise FileExistsError(dst)
        src.replace(dst); return dst
    def restore(self,filename):
        src=self.recordings/'archive'/filename
        if not src.exists(): raise FileNotFoundError(src)
        dst=self.recordings/filename
        if dst.exists(): raise FileExistsError(dst)
        src.replace(dst); return dst
    def delete_archived(self,filename):
        """Permanently delete only from archive. Live recordings must be archived first."""
        src=self.recordings/'archive'/filename
        if not src.exists(): raise FileNotFoundError(src)
        src.unlink(); return True

    def delete_recording(self, filename):
        """Permanently delete one active ``.areplay`` recording and its local cache metadata.

        Performance History is intentionally independent and is not touched here.
        Generated reports/validation artifacts are also preserved because they may be
        useful evidence even after the large packet recording is removed.
        """
        name=Path(str(filename or '')).name
        if not name or name != str(filename):
            raise ValueError('invalid recording filename')
        src=self.recordings/name
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(src)
        if src.suffix.lower() != '.areplay':
            raise ValueError('only .areplay recordings can be deleted')
        src.unlink()
        # Recorder sidecar and the replay-analysis cache are disposable derivatives.
        sidecar=src.with_suffix(src.suffix+'.json')
        if sidecar.exists():
            sidecar.unlink()
        try:
            cache=self.replay_analysis.cache_dir/(name+'.index.json')
            if cache.exists(): cache.unlink()
        except Exception:
            pass
        d=self._meta()
        if name in d:
            d.pop(name,None); self._save(d)
        return {'file':name,'deleted':True}
    def metadata_card(self,filename):
        row=next((x for x in self.list(include_archived=True) if x['file']==filename),None)
        if row is None: return None
        sidecars=[]
        stem=Path(filename).stem
        for base in (Path('analysis'),self.reports):
            if base.exists(): sidecars.extend(str(p) for p in base.glob(stem+'*') if p.is_file())
        row=dict(row); row['sidecars']=sorted(set(sidecars)); return row

    def link_artifacts(self, filename, *, coach_report_json=None, coach_report_html=None, validation_json=None, corner_validation=None):
        d=self._meta(); row=d.get(filename,{}) if isinstance(d.get(filename),dict) else {}; assoc=row.get('associations',{}) if isinstance(row.get('associations'),dict) else {}
        for k,v in {'coach_report_json':coach_report_json,'coach_report_html':coach_report_html,'validation_json':validation_json}.items():
            if v: assoc[k]=str(v)
        if corner_validation: assoc['corner_validation']=[str(x) for x in corner_validation]
        row['associations']=assoc; d[filename]=row; self._save(d); return assoc

    def search(self, query='', *, tags=None, favorites_only=False, include_archived=False, session_type=None, track_id=None):
        q=str(query or '').strip().lower(); wanted_tags={str(x).strip().lower() for x in (tags or []) if str(x).strip()}
        rows=self.list(include_archived=include_archived); out=[]
        for row in rows:
            hay=' '.join([str(row.get('name') or ''),str(row.get('file') or ''),str(row.get('notes') or ''),' '.join(row.get('tags') or [])]).lower()
            if q and q not in hay: continue
            if favorites_only and not row.get('favorite'): continue
            have={str(x).lower() for x in row.get('tags') or []}
            if wanted_tags and not wanted_tags.issubset(have): continue
            sess=row.get('session') or {}
            if session_type is not None and sess.get('session_type') != int(session_type): continue
            if track_id is not None and sess.get('track_id') != int(track_id): continue
            out.append(row)
        return out

    def replay_details(self, filename):
        p=self.recordings/filename
        idx=dict(self.replay_analysis.build(p))
        meta=self._meta().get(filename,{}) if isinstance(self._meta().get(filename),dict) else {}
        assoc=dict(idx.get('associations') or {})
        if isinstance(meta.get('associations'),dict): assoc.update({k:v for k,v in meta['associations'].items() if v})
        idx['associations']=assoc
        return {**idx,'timeline':self.replay_analysis.timeline(p),'corners':self.replay_analysis.corners(p)}

    def compare_laps(self, filename, laps):
        return self.replay_analysis.compare_laps(self.recordings/filename,[int(x) for x in laps])

    def workstation(self, filename, lap, reference_lap=None):
        return self.replay_analysis.workstation(self.recordings/filename,int(lap),int(reference_lap) if reference_lap is not None else None)

    def compare_sessions(self, left_filename, right_filename):
        return self.replay_analysis.compare_sessions(self.recordings/left_filename,self.recordings/right_filename)

    @staticmethod
    def _report_metrics(path):
        try:
            d=json.loads(Path(path).read_text(encoding='utf-8'))
        except Exception:return {}
        def pick(*keys):
            cur=d
            for k in keys:
                if not isinstance(cur,dict): return None
                cur=cur.get(k)
            return cur
        return {
            'best_lap_s': pick('summary','best_lap_s') or d.get('best_lap_s'),
            'potential_lap_s': pick('potential_lap','potential_lap_s') or pick('summary','potential_lap_s'),
            'reference_lap_s': pick('summary','reference_lap_s') or d.get('reference_lap_s'),
            'reference_gap_s': pick('summary','reference_gap_s'),
        }
    def compare_reports(self,left,right):
        a=self._report_metrics(left); b=self._report_metrics(right)
        keys=sorted(set(a)|set(b)); out={}
        for k in keys:
            av,bv=a.get(k),b.get(k); delta=(float(bv)-float(av)) if isinstance(av,(int,float)) and isinstance(bv,(int,float)) else None
            out[k]={'left':av,'right':bv,'delta':delta}
        return {'left':str(left),'right':str(right),'metrics':out}
