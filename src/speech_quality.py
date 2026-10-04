"""Local speech/radio wording, number and pronunciation utilities."""
from __future__ import annotations
import json, re
from pathlib import Path

DEFAULT_COOLDOWNS_S={
    'critical':0.0,'race_control':2.0,'pit':3.0,'tyres':8.0,'brakes':8.0,
    'fuel':10.0,'ers':8.0,'strategy':12.0,'coaching':6.0,'information':4.0,
}

# Built-ins are intentionally conservative.  User overrides in
# settings/pronunciation.json always win.
BUILTIN_PRONUNCIATIONS = {
    'Zandvoort': 'Zand-vort',
    'Interlagos': 'Inter-lah-gos',
    'Suzuka': 'Soo-zoo-kah',
    'Imola': 'Ee-mo-lah',
    'Monza': 'Mon-zah',
    'Jeddah': 'Jed-ah',
    'Baku': 'Bah-koo',
    'Spa-Francorchamps': 'Spa Frank-or-shom',
}


def spoken_number(value, *, decimals=1, unit: str|None=None):
    if value is None: return 'unknown'
    if isinstance(value,float):
        text=f"{value:.{max(0,int(decimals))}f}"
        if '.' in text: text=text.rstrip('0').rstrip('.')
    else: text=str(value)
    if unit: text=f"{text} {unit}"
    return text


def prepare_spoken_text(text: str) -> str:
    """Normalize symbols/abbreviations that local TTS commonly reads poorly."""
    out=' '.join(str(text or '').split())
    replacements=(
        (r'(?i)\bkph\b','kilometers per hour'), (r'(?i)\bkm/h\b','kilometers per hour'),
        (r'(?i)\bmph\b','miles per hour'), (r'(?i)\brpm\b','R P M'),
        (r'(?i)\bers\b','E R S'), (r'(?i)\bdrs\b','D R S'), (r'(?i)\bvsc\b','V S C'),
        (r'(?i)\bpsi\b','P S I'), (r'(?i)\bms\b','milliseconds'),
        (r'°\s*C\b',' degrees Celsius'),
        (r'(?<=\d)\s*%',' percent'),
    )
    for pattern,repl in replacements: out=re.sub(pattern,repl,out)
    # Natural decimal reading for explicit telemetry values without rewriting lap-time colons.
    out=re.sub(r'\b(-?\d+)\.(\d+)\b', lambda m: f"{m.group(1)} point {' '.join(m.group(2))}", out)
    return re.sub(r'\s+',' ',out).strip()


class PronunciationDictionary:
    def __init__(self,path='settings/pronunciation.json'):
        self.path=Path(path)
    def load(self):
        user={}
        try:
            d=json.loads(self.path.read_text(encoding='utf-8')); user=d if isinstance(d,dict) else {}
        except Exception: pass
        merged=dict(BUILTIN_PRONUNCIATIONS); merged.update({str(k):str(v) for k,v in user.items()})
        return merged
    def apply(self,text:str)->str:
        out=str(text or '')
        for src,dst in sorted(self.load().items(), key=lambda kv: -len(str(kv[0]))):
            out=re.sub(rf'(?<![A-Za-z0-9]){re.escape(str(src))}(?![A-Za-z0-9])',str(dst),out,flags=re.I)
        return out
    def set(self,source:str,spoken:str):
        try:
            d=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
            if not isinstance(d,dict): d={}
        except Exception:d={}
        d[str(source)]=str(spoken); self.path.parent.mkdir(parents=True,exist_ok=True); self.path.write_text(json.dumps(d,indent=2,sort_keys=True),encoding='utf-8'); return d


def concise_engineer_text(text:str, verbosity='normal')->str:
    t=' '.join(str(text or '').split())
    if verbosity=='detailed': return t
    replacements=(
        ('At the moment, ',''),('Currently, ',''),('Based on the measured data, ',''),
        ('The measured data shows that ',''),('According to the measured data, ',''),
        ('I can confirm that ',''),('For your information, ',''),
    )
    for a,b in replacements: t=t.replace(a,b)
    # Compress repetitive status wording while preserving factual qualifiers.
    t=t.replace(' is currently enabled',' is on').replace(' is currently disabled',' is off')
    if verbosity=='minimal':
        parts=[p.strip() for p in re.split(r'(?<=[.!?])\s+',t) if p.strip()]
        t=' '.join(parts[:1]) if parts else t
    return t


def load_speech_preferences(path='settings/speech.json') -> dict:
    try:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}


def save_speech_preferences(*, model_path=None, length_scale=None, path='settings/speech.json') -> dict:
    target=Path(path); data=load_speech_preferences(target)
    if model_path is not None: data['model_path']=str(model_path)
    if length_scale is not None: data['length_scale']=float(length_scale)
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.tmp'); tmp.write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8'); tmp.replace(target)
    return data
