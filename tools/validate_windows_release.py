from __future__ import annotations
from pathlib import Path
import json,sys,struct
ROOT=Path(__file__).resolve().parents[1]
checks={}
def has(path,needle=None):
    p=ROOT/path; ok=p.exists()
    if ok and needle is not None: ok=needle in p.read_text(encoding='utf-8',errors='replace')
    checks[str(path)+((':'+needle) if needle else '')]=bool(ok)
    return ok

# Stable V2 external-dependency launcher architecture.
has('RaceEngineer.exe')
has('launcher/bootstrapper_windows.go','runtime_dependencies.json')
has('launcher/bootstrapper_windows.go','snapshot_download')
has('launcher/bootstrapper_windows.go','ollama')
has('launcher/bootstrapper_windows.go','pip')
has('runtime_dependencies.json','qwen2.5:3b')
has('runtime_dependencies.json','en_GB-alan-medium.onnx')
has('runtime_dependencies.json','Systran/faster-whisper-small.en')
has('build_exe.ps1','No Python runtime, Piper voice, Whisper model, Ollama runtime or LLM model is embedded')
has('build_release.ps1','Compress-Archive')
has('installer/RaceEngineer.iss','DefaultDirName={localappdata}\\RaceEngineer')
has('installer/RaceEngineer.iss','Excludes: "settings\\*;user_data\\*;recordings\\*;analysis\\*;logs\\*;references\\*;maps\\*;voices\\*"')
has('src/product_launcher.py','create_upgrade_backup_if_needed')
has('src/crash_reporting.py','latest_crash.log')

# The release launcher must remain small enough that it clearly cannot contain
# the ~64 MB Piper voice, ~486 MB Whisper model or multi-GB Ollama model.
exe=ROOT/'RaceEngineer.exe'
if exe.exists():
    raw=exe.read_bytes()
    pe_off = struct.unpack_from('<I', raw, 0x3C)[0] if len(raw) >= 0x40 else -1
    checks['RaceEngineer.exe:PE64'] = raw[:2] == b'MZ' and pe_off >= 0 and raw[pe_off:pe_off+4] == b'PE\x00\x00'
    checks['RaceEngineer.exe:small_external_bootstrapper']=exe.stat().st_size < 8*1024*1024

# Version consistency for the Stable V2 product surface.
for f in ('src/update_checker.py','src/product_migration.py','installer/RaceEngineer.iss'):
    text=(ROOT/f).read_text(encoding='utf-8')
    checks[f+':version_2.0.0']='2.0.0' in text
print(json.dumps({'ok':all(checks.values()),'checks':checks},indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
