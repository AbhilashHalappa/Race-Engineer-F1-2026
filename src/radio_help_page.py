"""LAN/native embedded voice-command reference page.

Presentation-only. The command examples below mirror the deterministic parser
families in voice_commands.py and radio_controls.py; this page does not execute
or redefine command logic.
"""
from __future__ import annotations


def radio_help_page_html() -> str:
    return r'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Race Engineer Voice Command Help</title><link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCA2NCA2NCc+PHJlY3QgeD0nMycgeT0nMycgd2lkdGg9JzU4JyBoZWlnaHQ9JzU4JyByeD0nMTMnIGZpbGw9JyMwYjEyMTknIHN0cm9rZT0nIzI3Mzc0Nicgc3Ryb2tlLXdpZHRoPSczJy8+PHBhdGggZD0nTTE4IDE2djMyTTIwIDE3aDE1YzggMCAxMiA0IDEyIDEwcy00IDEwLTEyIDEwSDIwTTM1IDM3bDE0IDE0JyBmaWxsPSdub25lJyBzdHJva2U9JyM0ZGQ5ZmYnIHN0cm9rZS13aWR0aD0nNicgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJyBzdHJva2UtbGluZWpvaW49J3JvdW5kJy8+PHBhdGggZD0nTTM1IDM3bDE0IDE0JyBzdHJva2U9JyMyZWQ0ODYnIHN0cm9rZS13aWR0aD0nNicgc3Ryb2tlLWxpbmVjYXA9J3JvdW5kJy8+PC9zdmc+">
<style>
:root{--bg:#080d12;--panel:#101820;--panel2:#0b1219;--panel3:#151f29;--line:#273746;--line2:#3b5265;--text:#eef6fb;--muted:#8395a8;--cyan:#4dd9ff;--green:#2ed486;--amber:#f5bd4d;--red:#ff5967}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text);font-family:Segoe UI,Arial,sans-serif}body{padding:20px 22px 32px}.shell{max-width:1500px;margin:auto}.eyebrow{font-size:12px;letter-spacing:1.4px;color:var(--cyan);font-weight:800}.top{display:flex;gap:18px;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;margin-bottom:14px}h1{font-size:30px;margin:3px 0 3px}.sub{color:var(--muted);font-size:14px}.searchWrap{min-width:min(520px,100%);flex:0 1 560px}.search{width:100%;background:var(--panel2);border:1px solid var(--line);border-radius:10px;color:var(--text);font-size:15px;padding:11px 13px;outline:none}.search:focus{border-color:var(--cyan);box-shadow:0 0 0 2px #4dd9ff22}.tip{background:#0e1a22;border:1px solid #264356;border-radius:10px;padding:10px 12px;color:#b9c8d5;margin:12px 0 16px}.tip code,.cmd code{color:#dff8ff;background:#12202a;border:1px solid #223d4d;border-radius:5px;padding:2px 6px}.nav{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:16px}.nav button{background:var(--panel2);border:1px solid var(--line);border-radius:16px;color:var(--muted);font-weight:700;padding:6px 10px;cursor:pointer}.nav button:hover,.nav button.active{color:var(--text);border-color:var(--cyan);background:#133044}.group{margin:20px 0 5px}.groupHead{display:flex;align-items:center;gap:9px;margin:0 0 9px}.icon{width:28px;height:28px;border-radius:8px;background:#122631;border:1px solid #285061;color:var(--cyan);display:grid;place-items:center;font-size:15px;font-weight:800}.group h2{font-size:17px;margin:0}.groupNote{color:var(--muted);font-size:12px;margin-left:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:9px}.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:11px 12px;min-height:74px}.card:hover{border-color:var(--line2);background:#111c25}.title{font-size:12px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}.cmd{font-size:14px;line-height:1.55}.alias{color:#a7b7c5;font-size:12px;margin-top:5px}.control{border-left:3px solid var(--cyan)}.strategy{border-left:3px solid var(--amber)}.safety{border-left:3px solid var(--red)}.status{border-left:3px solid var(--green)}.empty{display:none;text-align:center;color:var(--muted);padding:35px}.footer{color:var(--muted);font-size:12px;border-top:1px solid var(--line);margin-top:22px;padding-top:12px}@media(max-width:760px){body{padding:14px}h1{font-size:24px}.grid{grid-template-columns:1fr}.groupNote{display:none}}
</style>
</head>
<body>
<div class="shell">
<!-- Legacy source compatibility: Radio Command Reference · Race Engineer controls · CORNER COACH controls -->
<div class="top"><div><div class="eyebrow">HELP · VOICE CONTROL</div><h1>Race Engineer Voice Commands</h1><div class="sub">Deterministic commands grouped by function. Natural variants are accepted; these are the recommended phrases.</div></div><div class="searchWrap"><input id="search" class="search" type="search" placeholder="Search commands — e.g. tyre, fuel, gap, coach, pit…" autocomplete="off"></div></div>
<div class="tip"><b>How to use:</b> hold PTT and speak a command. For a spoken command overview say <code>radio commands</code>, <code>voice control help</code>, or <code>what can I ask?</code>. Missing telemetry is reported as unavailable rather than guessed.</div>
<div id="nav" class="nav"></div>
<div id="content">

<section class="group" data-group="Tyres"><div class="groupHead"><div class="icon">T</div><h2>Tyres</h2><span class="groupNote">condition, compound, wear and tyre choice</span></div><div class="grid">
<div class="card status"><div class="title">General condition</div><div class="cmd"><code>Tyre information</code><br><code>How are my tyres?</code><br><code>Tyre status</code></div></div>
<div class="card"><div class="title">Wear / life</div><div class="cmd"><code>Tyre wear</code><br><code>Can I make these tyres last?</code><br><code>Will these tyres last?</code></div></div>
<div class="card"><div class="title">Temperature</div><div class="cmd"><code>Tyre temperature</code><br><code>Tyre temperatures</code><br><code>Tyre temperatures more detail</code></div></div>
<div class="card"><div class="title">Pressure</div><div class="cmd"><code>Tyre pressure</code><br><code>Tyre pressures</code></div></div>
<div class="card"><div class="title">Compound / age / set</div><div class="cmd"><code>Tyre compound</code><br><code>Tyre age</code> / <code>Stint age</code><br><code>Tyre set</code> / <code>Fitted set</code></div></div>
<div class="card safety"><div class="title">Damage</div><div class="cmd"><code>Tyre damage</code><br><code>Tyre blisters</code><br><code>Puncture status</code></div></div>
<div class="card strategy"><div class="title">Tyre choice</div><div class="cmd"><code>Which tyres should I use?</code><br><code>Which compound?</code><br><code>Which set?</code></div></div>
</div></section>

<section class="group" data-group="Brakes & Setup"><div class="groupHead"><div class="icon">B</div><h2>Brakes & Setup</h2><span class="groupNote">brakes and current car setup</span></div><div class="grid">
<div class="card status"><div class="title">Brake condition</div><div class="cmd"><code>Brake information</code><br><code>Brake status</code></div></div>
<div class="card"><div class="title">Brake temperature</div><div class="cmd"><code>Brake temperature</code><br><code>Brake temperatures more detail</code></div></div>
<div class="card safety"><div class="title">Brake damage</div><div class="cmd"><code>Brake damage</code><br><code>Brake wear</code></div></div>
<div class="card"><div class="title">Brake setup</div><div class="cmd"><code>Brake bias</code><br><code>Brake pressure</code></div></div>
<div class="card"><div class="title">Differential / engine brake</div><div class="cmd"><code>Differential</code><br><code>Engine braking</code></div></div>
<div class="card"><div class="title">Wings / setup</div><div class="cmd"><code>Wing setting</code><br><code>Setup</code><br><code>Car setup</code></div></div>
</div></section>

<section class="group" data-group="Car Condition"><div class="groupHead"><div class="icon">C</div><h2>Power Unit & Car Condition</h2></div><div class="grid">
<div class="card status"><div class="title">Engine</div><div class="cmd"><code>Engine status</code><br><code>Engine temperature</code><br><code>Engine wear</code></div></div>
<div class="card"><div class="title">Gearbox</div><div class="cmd"><code>Gearbox status</code></div></div>
<div class="card safety"><div class="title">Damage</div><div class="cmd"><code>Damage report</code><br><code>Car condition</code></div></div>
<div class="card"><div class="title">Aero/body</div><div class="cmd"><code>Wing status</code><br><code>Floor status</code></div></div>
<div class="card safety"><div class="title">Faults</div><div class="cmd"><code>Fault status</code><br><code>DRS fault</code><br><code>ERS fault</code></div></div>
</div></section>

<section class="group" data-group="Position & Traffic"><div class="groupHead"><div class="icon">P</div><h2>Position & Traffic</h2></div><div class="grid">
<div class="card status"><div class="title">Position</div><div class="cmd"><code>Position information</code><br><code>Grid position</code><br><code>Positions gained</code> / <code>Positions lost</code></div></div>
<div class="card"><div class="title">Gaps</div><div class="cmd"><code>Gap ahead</code><br><code>Gap behind</code><br><code>Gap to leader</code></div></div>
<div class="card"><div class="title">Drivers around you</div><div class="cmd"><code>Driver ahead</code><br><code>Driver behind</code></div></div>
<div class="card strategy"><div class="title">Gap trend</div><div class="cmd"><code>Gap trend</code><br><code>Am I catching the car ahead?</code><br><code>Is the gap closing?</code></div></div>
</div></section>

<section class="group" data-group="Laps & Timing"><div class="groupHead"><div class="icon">L</div><h2>Laps & Timing</h2></div><div class="grid">
<div class="card"><div class="title">Lap count</div><div class="cmd"><code>Current lap</code><br><code>Laps remaining</code><br><code>Laps completed</code><div class="alias">Also accepts: laps left / how many laps left</div></div></div>
<div class="card"><div class="title">Sector</div><div class="cmd"><code>Current sector</code><br><code>Sector times</code></div></div>
<div class="card status"><div class="title">Lap timing</div><div class="cmd"><code>Lap time</code><br><code>Last lap</code><br><code>Best lap</code><br><code>Lap valid?</code></div></div>
<div class="card"><div class="title">Compare</div><div class="cmd"><code>Compare lap</code><br><code>Lap delta</code></div></div>
<div class="card"><div class="title">Session clock</div><div class="cmd"><code>Session time remaining</code><br><code>Time left</code></div></div>
<div class="card"><div class="title">End of session</div><div class="cmd"><code>Session summary</code><br><code>Race summary</code><br><code>Race result</code><br><code>Final result</code></div></div>
</div></section>

<section class="group" data-group="Fuel & Energy"><div class="groupHead"><div class="icon">E</div><h2>Fuel, ERS & Overtake Systems</h2></div><div class="grid">
<div class="card status"><div class="title">Fuel</div><div class="cmd"><code>Fuel status</code><br><code>Fuel used</code><br><code>Fuel mix</code></div></div>
<div class="card strategy"><div class="title">Fuel to finish</div><div class="cmd"><code>Fuel to finish</code><br><code>How much fuel margin do I have?</code><br><code>Enough fuel to finish?</code></div></div>
<div class="card"><div class="title">ERS</div><div class="cmd"><code>ERS status</code><br><code>ERS harvest</code><br><code>Battery status</code></div></div>
<div class="card"><div class="title">Overtake systems</div><div class="cmd"><code>DRS status</code><br><code>S Mode status</code><br><code>Overtake status</code></div></div>
</div></section>

<section class="group" data-group="Weather & Race Control"><div class="groupHead"><div class="icon">W</div><h2>Weather & Race Control</h2></div><div class="grid">
<div class="card status"><div class="title">Weather</div><div class="cmd"><code>Weather information</code><br><code>Weather report</code><br><code>Forecast</code></div></div>
<div class="card"><div class="title">Temperatures</div><div class="cmd"><code>Track temperature</code><br><code>Air temperature</code></div></div>
<div class="card"><div class="title">Rain</div><div class="cmd"><code>Rain chance</code><br><code>Chance of rain</code></div></div>
<div class="card safety"><div class="title">Race control</div><div class="cmd"><code>Race control</code><br><code>Safety Car</code><br><code>VSC</code></div></div>
<div class="card safety"><div class="title">Penalties / limits</div><div class="cmd"><code>Penalties</code><br><code>Warnings</code><br><code>Track limits</code></div></div>
</div></section>

<section class="group" data-group="Strategy"><div class="groupHead"><div class="icon">S</div><h2>Race Strategy</h2><span class="groupNote">deterministic strategy answers only</span></div><div class="grid">
<div class="card strategy"><div class="title">Strategy state</div><div class="cmd"><code>Strategy update</code><br><code>Can I make it to the end?</code></div></div>
<div class="card strategy"><div class="title">Stint pace</div><div class="cmd"><code>Compare stint pace</code><br><code>Current stint pace</code><br><code>Previous stint pace</code></div></div>
<div class="card strategy"><div class="title">Rejoin</div><div class="cmd"><code>Will I come out in traffic?</code><br><code>Where will I rejoin?</code></div></div>
<div class="card strategy"><div class="title">Undercut</div><div class="cmd"><code>Can I undercut the car ahead?</code><br><code>Is the undercut working?</code></div></div>
<div class="card strategy"><div class="title">Safety Car opportunity</div><div class="cmd"><code>Is this a good Safety Car pit stop?</code></div></div>
<div class="card strategy"><div class="title">Pit reasoning</div><div class="cmd"><code>Why should I box?</code></div></div>
</div></section>

<section class="group" data-group="Pit"><div class="groupHead"><div class="icon">BOX</div><h2>Pit & Service</h2></div><div class="grid">
<div class="card strategy"><div class="title">Pit decision</div><div class="cmd"><code>Should I box?</code><br><code>Can I box now?</code><br><code>Box this lap?</code></div></div>
<div class="card"><div class="title">Pit information</div><div class="cmd"><code>Pit status</code><br><code>Pit speed limit</code><br><code>Pit stops</code></div></div>
<div class="card strategy"><div class="title">Service plan</div><div class="cmd"><code>Which tyres should I use?</code><br><code>Change front wing?</code><br><code>Repair front wing?</code></div></div>
</div></section>

<section class="group" data-group="Driving Performance"><div class="groupHead"><div class="icon">Δ</div><h2>Driving & Performance</h2></div><div class="grid">
<div class="card"><div class="title">Measured loss</div><div class="cmd"><code>Where am I losing time?</code><br><code>Compare performance</code></div></div>
<div class="card"><div class="title">Technique</div><div class="cmd"><code>Braking compare</code><br><code>Traction compare</code><br><code>Driving issues</code></div></div>
<div class="card"><div class="title">Vehicle motion</div><div class="cmd"><code>Wheel slip</code><br><code>G force</code></div></div>
<div class="card control"><div class="title">Reference lap</div><div class="cmd"><code>Use this lap as reference</code><br><code>Compare with previous</code><br><code>Compare with best</code></div></div>
</div></section>

<section class="group" data-group="Race Engineer Controls"><div class="groupHead"><div class="icon">RE</div><h2>Race Engineer Controls</h2><span class="groupNote">use enable / disable / toggle / status</span></div><div class="grid">
<div class="card control"><div class="title">Engineer master</div><div class="cmd"><code>Enable Race Engineer</code><br><code>Disable Race Engineer</code><br><code>Race Engineer status</code></div></div>
<div class="card control"><div class="title">Race Engineer sub-functions</div><div class="cmd"><code>PRE coach</code><br><code>POST coach</code><br><code>Lap summary</code><br><code>Positive coach</code><br><code>Race coach</code><div class="alias">Prefix with enable / disable / toggle / status.</div></div></div>
</div></section>

<section class="group" data-group="Performance Coach Controls"><div class="groupHead"><div class="icon">PC</div><h2>Performance / Speed Coach Controls</h2><span class="groupNote">use enable / disable / toggle / status</span></div><div class="grid">
<div class="card control"><div class="title">Performance Coach master</div><div class="cmd"><code>Enable Performance Coach</code><br><code>Disable Speed Coach</code><br><code>Performance Coach status</code></div></div>
<div class="card control"><div class="title">Corner Coach</div><div class="cmd"><code>Enable Corner Coach</code><br><code>Corner Voice</code><br><code>Corner PRE</code><br><code>Corner POST</code></div></div>
<div class="card control"><div class="title">Straight Line Coach</div><div class="cmd"><code>Enable Straight Line Coach</code><br><code>Disable Straight Line Coach</code><br><code>Straight Voice</code></div></div>
<div class="card control"><div class="title">Gain / loss</div><div class="cmd"><code>Map gain loss</code><br><code>Gain loss voice</code></div></div>
<div class="card control"><div class="title">Damage coaching</div><div class="cmd"><code>Damage coach</code><br><code>Damage coach status</code></div></div>
</div></section>

<section class="group" data-group="System Controls"><div class="groupHead"><div class="icon">IO</div><h2>Radio & Runtime Controls</h2><span class="groupNote">use enable / disable / toggle / status where applicable</span></div><div class="grid">
<div class="card control"><div class="title">Speech</div><div class="cmd"><code>Speech / TTS</code><br><code>Push to talk / PTT</code><br><code>Speech recognition / STT</code></div></div>
<div class="card control"><div class="title">AI / recording</div><div class="cmd"><code>LLM</code> / <code>AI reasoning</code><br><code>Recording</code></div></div>
<div class="card control"><div class="title">Control state</div><div class="cmd"><code>Control status</code><br><code>What is enabled?</code></div></div>
</div></section>

<section class="group" data-group="Modes & Voice"><div class="groupHead"><div class="icon">V</div><h2>Coaching Mode, Detail & Voice</h2></div><div class="grid">
<div class="card control"><div class="title">Coaching mode</div><div class="cmd"><code>Set coaching mode auto</code><br><code>... race engineer</code><br><code>... performance coach</code><br><code>... track learning</code><br><code>... qualifying</code><br><code>... time trial</code><br><code>... silent analysis</code></div></div>
<div class="card control"><div class="title">Radio detail</div><div class="cmd"><code>Set radio detail minimal</code><br><code>Set radio detail normal</code><br><code>Set radio detail detailed</code></div></div>
<div class="card control"><div class="title">Voice speed</div><div class="cmd"><code>Voice speed slow</code><br><code>Voice speed normal</code><br><code>Voice speed fast</code></div></div>
<div class="card control"><div class="title">Voice selection</div><div class="cmd"><code>Next voice</code><br><code>Use voice &lt;installed Piper voice name&gt;</code><br><code>Current voice</code></div></div>
</div></section>

<section class="group" data-group="General"><div class="groupHead"><div class="icon">?</div><h2>General Facts & Help</h2></div><div class="grid">
<div class="card status"><div class="title">Race / telemetry status</div><div class="cmd"><code>Race status</code><br><code>Update</code><br><code>Telemetry summary</code><br><code>All facts</code></div></div>
<div class="card"><div class="title">Instant telemetry</div><div class="cmd"><code>Speed</code><br><code>RPM</code><br><code>Gear</code></div></div>
<div class="card control"><div class="title">Help</div><div class="cmd"><code>Radio commands</code><br><code>What can I ask?</code><br><code>Voice control help</code><br><code>Radio help</code></div></div>
</div></section>

<div id="empty" class="empty">No voice commands match your search.</div>
<div class="footer">Known telemetry and strategy commands are deterministic and authoritative. Free-form explanation can use the optional local LLM only when enabled; it does not override telemetry facts or deterministic race decisions.</div>
</div></div>
<script>
const groups=[...document.querySelectorAll('.group')];const nav=document.getElementById('nav');
const all=document.createElement('button');all.textContent='ALL';all.className='active';all.onclick=()=>filterGroup('');nav.appendChild(all);
groups.forEach(g=>{const b=document.createElement('button');b.textContent=g.dataset.group;b.onclick=()=>filterGroup(g.dataset.group);nav.appendChild(b)});
function filterGroup(name){document.getElementById('search').value='';groups.forEach(g=>g.style.display=!name||g.dataset.group===name?'block':'none');[...nav.children].forEach(b=>b.classList.toggle('active',b.textContent===(name||'ALL')));document.getElementById('empty').style.display='none'}
document.getElementById('search').addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();[...nav.children].forEach(b=>b.classList.remove('active'));let shown=0;groups.forEach(g=>{let groupShown=0;[...g.querySelectorAll('.card')].forEach(c=>{const hit=!q||c.textContent.toLowerCase().includes(q)||g.dataset.group.toLowerCase().includes(q);c.style.display=hit?'block':'none';if(hit)groupShown++});g.style.display=groupShown?'block':'none';if(groupShown)shown+=groupShown});document.getElementById('empty').style.display=shown?'none':'block'});
</script>
</body></html>'''
