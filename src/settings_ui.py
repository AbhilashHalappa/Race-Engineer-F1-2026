"""Consolidated local setup/settings/diagnostics UI helpers."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import base64, io, json, zipfile

from .diagnostics import export_bundle
from .product_readiness import first_run_check
from .product_settings import ProductSettingsStore
from .product_setup import setup_snapshot, apply_setup, firewall_status, install_private_firewall_rule
from .update_checker import check_for_updates
from .app_paths import PTT_LOGS

ROOT=Path('.')
SETTINGS=ROOT/'settings'
TRANSCRIPTS=ROOT/'analysis'/'transcripts'
BUNDLES=ROOT/'analysis'/'validation_bundles'


def _safe_audio():
    try:
        from .audio_devices import input_devices, output_devices
        def item(d):
            return {'index':int(d.index),'name':d.name,'sample_rate':float(d.default_samplerate)}
        return {'inputs':[item(d) for d in input_devices()], 'outputs':[item(d) for d in output_devices()]}
    except Exception as e:
        return {'inputs':[],'outputs':[],'error':str(e)}


def snapshot()->dict:
    refs=[]
    rroot=ROOT/'references'
    if rroot.exists():
        refs=[str(p.relative_to(rroot)) for p in sorted(rroot.rglob('*.json')) if p.is_file()][:500]
    trs=[]
    if TRANSCRIPTS.exists():
        trs=[{'name':p.name,'bytes':p.stat().st_size,'mtime':p.stat().st_mtime}
             for p in sorted(TRANSCRIPTS.glob('*'),key=lambda p:p.stat().st_mtime,reverse=True)[:100] if p.is_file()]
    vals=[]
    if BUNDLES.exists():
        for p in sorted(BUNDLES.glob('*.zip'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
            vals.append({'name':p.name,'bytes':p.stat().st_size,'mtime':p.stat().st_mtime})
    cfg=[str(p.relative_to(SETTINGS)) for p in SETTINGS.rglob('*') if p.is_file()] if SETTINGS.exists() else []
    product=ProductSettingsStore().settings
    return {'readiness':first_run_check(udp_port=product.udp_port).to_dict(),'audio':_safe_audio(),'references':refs,
            'transcripts':trs,'validation_bundles':vals,'configuration_files':cfg,
            'product_settings':product.to_dict(),'firewall':firewall_status()}


def export_configuration(path='analysis/diagnostics/user_configuration.zip')->Path:
    out=Path(path); out.parent.mkdir(parents=True,exist_ok=True)
    include_roots=[Path('settings'),Path('maps'),Path('references')]
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'format':'race-engineer-config-v2'},indent=2))
        for root in include_roots:
            if not root.exists(): continue
            for p in root.rglob('*'):
                if p.is_file() and p.stat().st_size<10*1024*1024: z.write(p,p.as_posix())
        # Stable V2 audit: include the canonical structured PTT mapping and the
        # pre-S5 legacy location.  The legacy fallback matters for upgrade/config
        # exports created before migrate_legacy_layout() has run in this process.
        hid_candidates=(
            PTT_LOGS / "hid_mapping.json",
            ROOT / "user_data" / "logs" / "ptt" / "hid_mapping.json",
            ROOT / "logs" / "ptt" / "hid_mapping.json",
        )
        seen=set()
        for hid in hid_candidates:
            try:
                key=str(hid.resolve())
            except OSError:
                key=str(hid)
            if key in seen:
                continue
            seen.add(key)
            if hid.exists() and hid.is_file() and hid.stat().st_size<2*1024*1024:
                z.write(hid,'logs/ptt/hid_mapping.json')
                break
    return out


def import_configuration_b64(data:str)->dict:
    raw=base64.b64decode(data); changed=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for info in z.infolist():
            name=Path(info.filename)
            if name.is_absolute() or '..' in name.parts or not name.parts: continue
            allowed_root=name.parts[0] in {'settings','maps','references'} or name.parts[:2]==('logs','ptt')
            if not allowed_root or info.is_dir(): continue
            target=ROOT/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(z.read(info)); changed.append(name.as_posix())
    return {'changed':changed}


def reset_user_settings(*,layout_only=False)->dict:
    removed=[]
    patterns=('*layout*.json','*geometry*.json','*window*.json') if layout_only else ('*.json',)
    if SETTINGS.exists():
        for pat in patterns:
            for p in SETTINGS.glob(pat):
                try:p.unlink();removed.append(str(p))
                except OSError:pass
    return {'removed':removed}


def transcript_text(name:str)->str:
    p=(TRANSCRIPTS/Path(name).name)
    if not p.exists() or not p.is_file(): raise FileNotFoundError(name)
    return p.read_text(encoding='utf-8',errors='replace')[-2_000_000:]


def create_diagnostics()->str:
    extras=[]
    if BUNDLES.exists(): extras=sorted(BUNDLES.glob('*.zip'),key=lambda p:p.stat().st_mtime,reverse=True)[:1]
    return str(export_bundle(extra_files=extras))


def setup_api_snapshot()->dict:
    data=setup_snapshot(); data['firewall']=firewall_status(); return data


def setup_api_action(action:str, data:dict, *, exe_path:str|None=None)->dict:
    if action=='save': return apply_setup(dict(data.get('changes') or {}))
    if action=='firewall': return install_private_firewall_rule(exe_path or __import__('sys').executable)
    if action=='update_check':
        s=ProductSettingsStore().settings
        return check_for_updates(s.update_manifest_url).to_dict()
    raise ValueError('unknown setup action')


def lan_qr_svg(url: str) -> bytes:
    try:
        import qrcode
        import qrcode.image.svg
        image=qrcode.make(url,image_factory=qrcode.image.svg.SvgPathImage,box_size=7,border=2)
        bio=io.BytesIO(); image.save(bio); return bio.getvalue()
    except Exception:
        safe=url.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="420" height="80"><rect width="100%" height="100%" fill="white"/><text x="10" y="42" font-size="14" fill="black">{safe}</text></svg>'.encode('utf-8')


def setup_page_html()->str:
    return r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Race Engineer Setup</title><link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCA2NCA2NCc+PHJlY3QgeD0nMycgeT0nMycgd2lkdGg9JzU4JyBoZWlnaHQ9JzU4JyByeD0nMTMnIGZpbGw9JyMwYjEyMTknIHN0cm9rZT0nIzI3Mzc0Nicgc3Ryb2tlLXdpZHRoPSczJy8+PHBhdGggZD0nTTE4IDE2djMyTTIwIDE3aDE1YzggMCAxMiA0IDEyIDEwcy00IDEwLTEyIDEwSDIwTTM1IDM3bDE0IDE0JyBmaWxsPSdub25lJyBzdHJva2U9JyM0ZGQ5ZmYnIHN0cm9rZS13aWR0aD0nNicgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJyBzdHJva2UtbGluZWpvaW49J3JvdW5kJy8+PHBhdGggZD0nTTM1IDM3bDE0IDE0JyBzdHJva2U9JyMyZWQ0ODYnIHN0cm9rZS13aWR0aD0nNicgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJy8+PC9zdmc+"><style>
body{font-family:Segoe UI,system-ui;background:#0d0f12;color:#eee;margin:0;padding:22px}h2{margin-top:0}.step{background:#171a20;border:1px solid #343a46;border-radius:10px;padding:16px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px}label{display:block;margin:8px 0 3px;color:#b9c3cf}select,input[type=number]{width:100%;box-sizing:border-box;padding:9px;background:#0f1116;color:#eee;border:1px solid #4b5565;border-radius:5px}button{padding:10px 15px;margin:5px;background:#26354b;color:#fff;border:1px solid #506a8e;border-radius:6px}.ok{color:#8bd49a}.bad{color:#ff9a9a}.muted{color:#9aa5b1}pre{background:#0a0c0f;padding:8px;border-radius:5px;white-space:pre-wrap}a{color:#8ec7ff}</style></head><body>
<h2>Race Engineer — First Run Setup</h2><div class=muted>Configure local devices and Windows/LAN options. Saved changes apply on the next Race Engineer start.</div>
<div class=step><h3>1. F1 Telemetry & Display</h3><div class=muted>In F1: Telemetry Settings → UDP Telemetry ON → UDP IP 127.0.0.1 → UDP Port must match below. Keep the game UDP format on the current game format.</div><div class=grid><div><label>F1 UDP port</label><input id=udp type=number value=20777></div><div><label>LAN dashboard port</label><input id=dashport type=number value=8765></div></div><label><input id=overlay type=checkbox checked> Native overlay</label><label><input id=webdash type=checkbox checked> LAN/browser dashboard</label><div id=ready></div></div>
<div class=step><h3>2. Audio & Radio</h3><div class=grid><div><label>Microphone</label><select id=mic></select></div><div><label>Engineer output</label><select id=audio></select></div></div><label><input id=ptt type=checkbox> Enable PTT</label><div class=grid><div><label>PTT button number</label><input id=pttbtn type=number min=0 max=255 value=6></div><div><label>PTT HID controller</label><select id=hid></select></div></div></div>
<div class=step><h3>3. Wheel / Receiver</h3><label><input id=wheelon type=checkbox checked> Enable wheel telemetry bridge</label><label>Receiver COM port</label><select id=wheel></select></div>
<div class=step><h3>4. Windows / LAN</h3><div id=fw></div><button onclick="firewall()">Add Private-network Firewall Rule</button><div><img id=qr alt="LAN QR" style="background:white;padding:8px;max-width:220px"><div id=lan></div></div></div>
<div class=step><h3>5. Finish</h3><label><input id=updates type=checkbox> Enable update checks when requested</label><button onclick="save(true)">Save & Finish Setup</button><button onclick="save(false)">Save</button><button onclick="updateCheck()">Check for update now</button><pre id=result></pre><a href="/settings">Advanced settings / diagnostics</a></div>
<script>
async function api(u,o){let r=await fetch(u,o);let t=await r.text();try{return JSON.parse(t)}catch(e){throw Error(t)}}
function opt(sel,v,t){let o=document.createElement('option');o.value=v;o.textContent=t;sel.appendChild(o)}
async function load(){let x=await api('/api/setup');let s=x.settings;udp.value=s.udp_port;dashport.value=s.dash_port;overlay.checked=s.overlay_enabled;webdash.checked=s.web_dash_enabled;ptt.checked=s.ptt_enabled;pttbtn.value=s.ptt_button;wheelon.checked=s.wheel_telemetry_enabled;updates.checked=s.update_check_enabled;
mic.innerHTML='';opt(mic,'','System default');(x.audio.inputs||[]).forEach(d=>opt(mic,d.index,d.index+': '+d.name));mic.value=s.mic_device==null?'':String(s.mic_device);audio.innerHTML='';opt(audio,'','System default');(x.audio.outputs||[]).forEach(d=>opt(audio,d.index,d.index+': '+d.name));audio.value=s.audio_device==null?'':String(s.audio_device);
wheel.innerHTML='';opt(wheel,'','Auto-detect');(x.wheel_ports||[]).forEach(d=>opt(wheel,d.device,d.device+' — '+(d.description||'')));wheel.value=s.wheel_port||'';
hid.innerHTML='';(x.hid_devices||[]).forEach((d,i)=>opt(hid,i,(d.product||'Gamepad')+' ['+d.vendor_id.toString(16).padStart(4,'0')+':'+d.product_id.toString(16).padStart(4,'0')+']'));hid.dataset.devices=JSON.stringify(x.hid_devices||[]);let ix=(x.hid_devices||[]).findIndex(d=>d.vendor_id==s.hid_vendor_id&&d.product_id==s.hid_product_id&&d.usage_page==s.hid_usage_page&&d.usage==s.hid_usage);if(ix>=0)hid.value=String(ix);
ready.innerHTML=Object.entries(x.readiness||{}).map(([k,v])=>'<div class='+(v===false?'bad':'ok')+'>'+k+': '+v+'</div>').join('')+'<div class=muted>Displays: '+JSON.stringify(x.display||{})+'</div>';fw.textContent='Firewall rule: '+((x.firewall||{}).installed?'installed':'not confirmed');qr.src='/api/lan-qr.svg?t='+Date.now();lan.textContent='Scan to open the LAN dashboard.'}
function payload(done){let ds=JSON.parse(hid.dataset.devices||'[]'),d=ds[Number(hid.value)]||{};return {setup_complete:done,udp_port:Number(udp.value),dash_port:Number(dashport.value),overlay_enabled:overlay.checked,web_dash_enabled:webdash.checked,mic_device:mic.value===''?null:Number(mic.value),audio_device:audio.value===''?null:Number(audio.value),ptt_enabled:ptt.checked,ptt_button:Number(pttbtn.value),hid_vendor_id:d.vendor_id||0x303a,hid_product_id:d.product_id||0x1001,hid_usage_page:d.usage_page||1,hid_usage:d.usage||5,wheel_telemetry_enabled:wheelon.checked,wheel_port:wheel.value||null,update_check_enabled:updates.checked}}
async function save(done){let x=await api('/api/setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'save',changes:payload(done)})});result.textContent=JSON.stringify(x,null,2)}
async function firewall(){let x=await api('/api/setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'firewall'})});result.textContent=JSON.stringify(x,null,2);load()}
async function updateCheck(){let x=await api('/api/setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'update_check'})});result.textContent=JSON.stringify(x,null,2)}load()</script></body></html>'''


def settings_page_html()->str:
    return r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Race Engineer Settings</title><style>
body{font-family:system-ui;background:#101114;color:#eee;margin:0;padding:18px}.top{display:flex;gap:14px;align-items:center;flex-wrap:wrap}a{color:#8ec7ff}button,input{font:inherit;padding:8px;margin:3px;background:#222;color:#eee;border:1px solid #555;border-radius:5px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:12px;margin-top:14px}.card{background:#181a1f;border:1px solid #333;border-radius:8px;padding:12px;min-height:130px}pre{white-space:pre-wrap;max-height:420px;overflow:auto;background:#0d0e11;padding:8px}.row{padding:3px 0;border-bottom:1px solid #282a30}.ok{color:#8fd694}.bad{color:#ff9a9a}</style></head><body>
<div class=top><h2>Race Engineer — Setup & Validation</h2><a href="/">Dash</a><a href="/sessions">Sessions</a><a href="/coach">Coach</a><a href="/setup">First-run setup</a><button onclick="load()">Refresh</button></div>
<div class=grid><div class=card><h3>Readiness / Devices</h3><div id=ready></div><div id=audio></div></div><div class=card><h3>References</h3><div id=refs></div></div><div class=card><h3>Validation</h3><div id=val></div><button onclick="diag()">Create diagnostics bundle</button></div><div class=card><h3>Configuration</h3><button onclick="cfgExport()">Export config</button><input id=cfg type=file><button onclick="cfgImport()">Import config</button><button onclick="reset('layout')">Reset layout</button><button onclick="reset('settings')">Reset settings</button><pre id=action></pre></div><div class=card style="grid-column:1/-1"><h3>Transcripts</h3><div id=trs></div><pre id=view>Select a transcript.</pre></div></div>
<script>async function api(u,o){let r=await fetch(u,o);return await r.json()}async function load(){let x=await api('/api/settings');ready.innerHTML=Object.entries(x.readiness).map(([k,v])=>`<div class=row>${k}: ${v}</div>`).join('');audio.innerHTML=`<b>Inputs:</b> ${(x.audio.inputs||[]).map(d=>d.index+': '+d.name).join('<br>')||'none'}<br><b>Outputs:</b> ${(x.audio.outputs||[]).map(d=>d.index+': '+d.name).join('<br>')||'none'}`;refs.innerHTML=(x.references||[]).map(n=>`<div class=row>${n}</div>`).join('')||'No references';val.innerHTML=(x.validation_bundles||[]).map(n=>`<div class=row>${n.name} (${Math.round(n.bytes/1024)} KiB)</div>`).join('')||'No bundles';trs.innerHTML=(x.transcripts||[]).map(n=>`<button onclick="showTr('${encodeURIComponent(n.name)}')">${n.name}</button>`).join('')||'No transcripts'}async function showTr(n){let r=await fetch('/api/transcript?name='+n);view.textContent=await r.text()}async function post(a,p={}){let x=await api('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a,...p})});action.textContent=JSON.stringify(x,null,2);load()}function diag(){post('diagnostics')}function reset(x){post(x==='layout'?'reset_layout':'reset_settings')}async function cfgExport(){let x=await api('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'export_config'})});action.textContent=JSON.stringify(x,null,2)}function cfgImport(){let f=cfg.files[0];if(!f)return;let r=new FileReader;r.onload=()=>post('import_config',{data:String(r.result).split(',')[1]});r.readAsDataURL(f)}load()</script></body></html>'''
