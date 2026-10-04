"""Asynchronous persistent Race Engineer / SPEED COACH validation transcripts."""
from __future__ import annotations
import json, queue, threading
from datetime import datetime, timezone
from pathlib import Path


def _safe(v):
    s=str(v or 'UNKNOWN').strip().upper()
    return ''.join(c if c.isalnum() or c in ('-','_') else '_' for c in s)[:64] or 'UNKNOWN'

def _stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

class ValidationTranscriptWriter:
    def __init__(self, output_dir=None):
        from .app_paths import TRANSCRIPTS
        self.output_dir=Path(output_dir) if output_dir is not None else TRANSCRIPTS; self.output_dir.mkdir(parents=True,exist_ok=True)
        self._q=queue.Queue(); self._thread=threading.Thread(target=self._worker,name='validation-transcript',daemon=True); self._thread.start()
        self._uid=None; self._session_meta={}; self._paths={}; self._weekend_path=None; self._weekend_track=None
        self._history={}

    @staticmethod
    def _meta(state):
        s=getattr(state,'session',None); tr=getattr(getattr(s,'track',None),'name',None) or getattr(getattr(s,'track',None),'label',None)
        st=getattr(getattr(s,'session_type',None),'name',None) or getattr(getattr(s,'session_type',None),'label',None)
        return {'session_uid':getattr(s,'uid',None),'session_type':st,'track':tr,'session_time_s':getattr(s,'session_time_s',None)}

    def observe_session(self,state):
        meta=self._meta(state); uid=meta.get('session_uid')
        if uid is None or uid==self._uid:return
        if self._uid is not None:
            self._history[self._uid]={'meta':dict(self._session_meta),'paths':dict(self._paths),'weekend_path':self._weekend_path}
        self._uid=uid; self._session_meta=meta; stamp=_stamp(); track=_safe(meta.get('track')); typ=_safe(meta.get('session_type'))
        self._paths={
            'race_engineer':self.output_dir/f'RACE_ENGINEER_{track}_{typ}_{uid}_{stamp}.txt',
            'speed_coach':self.output_dir/f'SPEED_COACH_TRANSCRIPT_{track}_{typ}_{uid}_{stamp}.txt',
            'corner_coach':self.output_dir/f'CORNER_COACH_TRANSCRIPT_{track}_{typ}_{uid}_{stamp}.txt',
            'combined':self.output_dir/f'VALIDATION_TRANSCRIPT_{track}_{typ}_{uid}_{stamp}.jsonl'}
        if self._weekend_path is None or self._weekend_track!=track:
            self._weekend_track=track; self._weekend_path=self.output_dir/f'WEEKEND_TRANSCRIPT_{track}_{stamp}.jsonl'
        self._enqueue({'event':'session_start',**meta,'utc':datetime.now(timezone.utc).isoformat()},targets=('combined','weekend'))

    def _enqueue(self,row,targets=('combined',)):
        self._q.put((dict(row),tuple(targets),dict(self._paths),self._weekend_path))

    def message(self,state,message,source,event='submitted'):
        self.observe_session(state); meta=self._meta(state)
        row={'event':event,'source':source,'role':'ENGINEER','text':str(getattr(message,'text','') or ''),'key':getattr(message,'key',None),
             'priority':int(getattr(message,'priority',0)) if getattr(message,'priority',None) is not None else None,
             'message_session_time_s':getattr(message,'session_time_s',None),'utc':datetime.now(timezone.utc).isoformat(),**meta}
        if source=='corner_coach':
            targets=('speed_coach','corner_coach','combined','weekend')
        elif source in {'speed_coach','straight_line_coach'}:
            targets=('speed_coach','combined','weekend')
        else:
            targets=('race_engineer','combined','weekend')
        self._enqueue(row,targets=targets)

    def driver(self,state,text,interpreted=None):
        self.observe_session(state); row={'event':'driver_radio','source':'race_engineer','role':'DRIVER','text':str(text or ''),'interpreted_text':interpreted,
             'utc':datetime.now(timezone.utc).isoformat(),**self._meta(state)}
        self._enqueue(row,targets=('race_engineer','combined','weekend'))

    def marker(self,state,event,**details):
        self.observe_session(state); row={'event':event,'utc':datetime.now(timezone.utc).isoformat(),**self._meta(state),**details}
        self._enqueue(row,targets=('combined','weekend'))


    def flush(self):
        self._q.join()

    def current_session(self):
        return {'uid':self._uid,'meta':dict(self._session_meta),'paths':dict(self._paths),'weekend_path':self._weekend_path}

    def session_artifacts(self, uid=None):
        if uid is None or uid==self._uid:
            return self.current_session()
        return dict(self._history.get(uid) or {})

    def decision(self,state,kind,decision,**details):
        self.observe_session(state)
        row={'event':'decision','decision_kind':str(kind),'decision':str(decision),'utc':datetime.now(timezone.utc).isoformat(),**self._meta(state),**details}
        self._enqueue(row,targets=('combined','weekend'))

    def _worker(self):
        while True:
            item=self._q.get()
            if item is None:break
            row,targets,paths,weekend=item
            try:
                line=json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n'
                for t in targets:
                    p=weekend if t=='weekend' else paths.get(t)
                    if p is None:continue
                    p.parent.mkdir(parents=True,exist_ok=True)
                    if str(p).endswith('.txt'):
                        tm=row.get('message_session_time_s',row.get('session_time_s'))
                        prefix=f"{float(tm):09.3f}" if isinstance(tm,(int,float)) else '---.---'
                        role=row.get('role','SYSTEM'); txt=row.get('text') or row.get('event','')
                        with p.open('a',encoding='utf-8') as f:f.write(f"{prefix} {role} {txt}\n")
                    else:
                        with p.open('a',encoding='utf-8') as f:f.write(line)
            finally:self._q.task_done()

    def close(self,wait=True):
        if self._uid is not None:
            self._history[self._uid]={'meta':dict(self._session_meta),'paths':dict(self._paths),'weekend_path':self._weekend_path}
        if wait:self._q.join()
        self._q.put(None)
        if wait:self._thread.join(timeout=2.0)
