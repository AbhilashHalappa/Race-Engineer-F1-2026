"""Read-only LAN coaching analysis page and JSON providers."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .driver_history import DriverHistory


def _load_json(path: Path) -> dict[str,Any] | None:
    try:
        data=json.loads(path.read_text(encoding="utf-8")); return data if isinstance(data,dict) else None
    except (OSError,json.JSONDecodeError): return None


def latest_report(directory: str | Path="analysis/reports") -> dict[str,Any]:
    root=Path(directory)
    files=sorted((p for p in root.glob("*.json") if not p.name.endswith("_validation.json")),key=lambda p:p.stat().st_mtime,reverse=True) if root.exists() else []
    for path in files:
        row=_load_json(path)
        if row and row.get("format")=="RACE_ENGINEER_COACH_REPORT":
            return {"available":True,"path":str(path),"report":row}
    return {"available":False,"reason":"no_coach_report"}


def _track_from_report(report: dict[str,Any]) -> str | int | None:
    ctx=report.get("event_context") if isinstance(report.get("event_context"),dict) else {}
    return ctx.get("track_id") if ctx.get("track_id") is not None else ctx.get("track_name")


def coaching_summary_payload(report_dir: str | Path="analysis/reports",history_path: str | Path="analysis/driver_history.json") -> dict[str,Any]:
    latest=latest_report(report_dir)
    if not latest.get("available"): return latest
    report=latest["report"]; track=_track_from_report(report); history=DriverHistory(history_path)
    return {"available":True,"report_path":latest.get("path"),"track":track,
            "summary":{"best_lap":report.get("best_lap"),"potential":report.get("potential"),"reference_lap":report.get("reference_lap"),
                       "reference_gap_s":report.get("total_reference_gap_s"),"current_focus":(report.get("advice_outcomes") or {}).get("current_focus"),
                       "advice_outcomes":report.get("advice_outcomes"),"biggest_opportunities":report.get("ranked_biggest_opportunities"),
                       "strengths":report.get("best_strengths"),"technique_metrics":report.get("technique_metrics"),
                       "racing_line":report.get("latest_racing_line"),"racing_line_svg":report.get("racing_line_svg"),
                       "corner_drilldown":report.get("corner_drilldown"),"improvement_trend":report.get("improvement_trend")},
            "history":history.progress_summary(track),"session_comparison":history.compare_sessions(track)}


def coaching_page_html() -> str:
    return r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Race Engineer Coaching</title><link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCA2NCA2NCc+PHJlY3QgeD0nMycgeT0nMycgd2lkdGg9JzU4JyBoZWlnaHQ9JzU4JyByeD0nMTMnIGZpbGw9JyMwYjEyMTknIHN0cm9rZT0nIzI3Mzc0Nicgc3Ryb2tlLXdpZHRoPSczJy8+PHBhdGggZD0nTTE4IDE2djMyTTIwIDE3aDE1YzggMCAxMiA0IDEyIDEwcy00IDEwLTEyIDEwSDIwTTM1IDM3bDE0IDE0JyBmaWxsPSdub25lJyBzdHJva2U9JyM0ZGQ5ZmYnIHN0cm9rZS13aWR0aD0nNicgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJyBzdHJva2UtbGluZWpvaW49J3JvdW5kJy8+PHBhdGggZD0nTTM1IDM3bDE0IDE0JyBzdHJva2U9JyMyZWQ0ODYnIHN0cm9rZS13aWR0aD0nNicgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJy8+PC9zdmc+"><style>
body{font-family:Segoe UI,Arial;background:#0d1117;color:#e6edf3;margin:0;padding:22px}.top{display:flex;justify-content:space-between;align-items:center}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.card,section{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px}h1,h2{margin:.3em 0}.v{font-size:28px;font-weight:800}.muted{color:#8b949e}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:7px;border-bottom:1px solid #30363d}a{color:#58a6ff}.ok{color:#3fb950}.warn{color:#d29922}</style></head><body>
<div class="top"><div><h1>PERFORMANCE COACH</h1><div class="muted">Measured deterministic session analysis</div></div><div><a href="/performance">PERFORMANCE HUB</a> &nbsp; <a href="/">F1 DASH</a></div></div>
<div id="root"><p>Loading…</p></div><script>
const f=v=>Number.isFinite(v)?Number(v).toFixed(3):'--'; const esc=s=>String(s??'--').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function metric(name,obj){return `<div class=card><b>${name}</b><div class=v>${obj}</div></div>`}
function render(d){if(!d.available){root.innerHTML='<p>No coach report available yet.</p>';return}let s=d.summary||{},p=s.potential||{},focus=s.current_focus||{},ops=s.biggest_opportunities||[],hist=d.history||{},comp=d.session_comparison||{};
let cards=metric('BEST LAP',f(p.best_lap_s??s.best_lap?.lap_time_s)) + metric('POTENTIAL',f(p.potential_lap_s)) + metric('REFERENCE',f(p.reference_lap_s??s.reference_lap?.lap_time_s)) + metric('AVAILABLE GAIN',f(p.realistic_available_gain_s??p.potential_gain_s));
let rows=ops.slice(0,12).map(x=>`<tr><td>T${esc(x.corner_id)}</td><td>${f(x.mean_net_loss_s)}</td><td>${esc(x.dominant_issue_label)}</td><td>${esc(x.dominant_phase)}</td></tr>`).join('')||'<tr><td colspan=4>No repeatable measured loss.</td></tr>';
let cp=(hist.corner_progress||[]).map(x=>{let m=x.metrics||{},b=m.brake_point_consistency||{},v=m.minimum_speed_consistency||{};return `<tr><td>T${x.corner_id}</td><td>${x.session_samples}</td><td>${esc(b.direction)}</td><td>${esc(v.direction)}</td></tr>`}).join('')||'<tr><td colspan=4>Need more sessions.</td></tr>';
root.innerHTML=`<div class=cards>${cards}</div><section><h2>Current focus</h2><div class=v>${focus.corner_id?'T'+focus.corner_id+' — '+esc(focus.issue_label||focus.issue_code):'No active focus'}</div></section>
<section><h2>Biggest losses</h2><table><tr><th>Turn</th><th>Loss s</th><th>Issue</th><th>Phase</th></tr>${rows}</table></section>
<section><h2>Cross-session progress</h2><p>Sessions: ${hist.session_count||0}. Latest vs previous best-lap delta: ${f(comp.metric_deltas?.best_lap_s)} s.</p><table><tr><th>Turn</th><th>Sessions</th><th>Brake consistency</th><th>Min-speed consistency</th></tr>${cp}</table></section>
<section><h2>Technique / corner table</h2><table><tr><th>Turn</th><th>Mean loss s</th><th>Issue</th><th>Phase</th></tr>${(s.corner_drilldown||[]).map(x=>`<tr><td>T${esc(x.corner_id)}</td><td>${f(x.mean_net_loss_s)}</td><td>${esc(x.dominant_issue_label)}</td><td>${esc(x.dominant_phase)}</td></tr>`).join('')||'<tr><td colspan=4>No corner data.</td></tr>'}</table></section>
<section><h2>Racing line</h2><p>Mean deviation ${f(s.racing_line?.mean_path_deviation_m)} m; max ${f(s.racing_line?.max_path_deviation_m)} m.</p>${s.racing_line_svg||''}</section>
<section><h2>Track landmarks editor</h2><p class=muted>Only verified facts are stored; the editor never invents a board from lap distance.</p><div class=cards><div class=card><label>Corner <input id=lmCorner type=number min=1 style='width:70px'></label></div><div class=card><label>100 board distance m <input id=lm100 type=number step=.1 style='width:110px'></label></div><div class=card><label>PRE call distance m <input id=lmPre type=number step=.1 style='width:110px'></label></div><div class=card><button onclick='saveLm()'>SAVE LANDMARK</button><div id=lmMsg class=muted></div></div></div></section>`;window.currentTrack=d.track||''}
async function saveLm(){let cid=Number(lmCorner.value),b=Number(lm100.value),pre=Number(lmPre.value);if(!window.currentTrack||!Number.isInteger(cid)||cid<1){lmMsg.textContent='Track/corner required';return}let corner={};if(Number.isFinite(b)&&lm100.value!=='')corner.board_100_m=b;if(Number.isFinite(pre)&&lmPre.value!=='')corner.pre_call_distance_m=pre;let r=await fetch('/api/landmarks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({track:String(window.currentTrack),corner_id:cid,corner})});let d=await r.json();lmMsg.textContent=d.ok?'Saved':'Error: '+(d.error||'unknown')}
async function load(){try{let r=await fetch('/api/coach/latest',{cache:'no-store'});render(await r.json())}catch(e){root.innerHTML='<p>Coach data unavailable.</p>'}}load();setInterval(load,3000);
</script></body></html>'''
