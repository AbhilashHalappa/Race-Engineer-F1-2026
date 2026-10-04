"""On-demand local AI explanation for deterministic Performance Review facts.

The AI is explanatory only. It never changes scores, diagnoses, reference data, or
persistent history. All numeric facts are prepared by deterministic Python first.
"""
from __future__ import annotations
import json
import os
import urllib.request
import socket
from typing import Any


def _fmt_time(value: Any) -> str:
    try:
        v=float(value)
    except (TypeError,ValueError):
        return "N/A"
    if not (v >= 0):
        return "N/A"
    m=int(v//60); sec=v-m*60
    return f"{m}:{sec:06.3f}" if m else f"{sec:.3f} s"


def _driver_facing_context(payload: dict[str, Any], corner_id: int | None = None) -> str:
    review=payload.get("review") if isinstance(payload.get("review"),dict) else {}
    session=payload.get("session") if isinstance(payload.get("session"),dict) else {}
    selected=payload.get("selected_reference_comparison") if isinstance(payload.get("selected_reference_comparison"),dict) else {}
    result=payload.get("result_summary") if isinstance(payload.get("result_summary"),dict) else {}
    lines=[
        f"Track: {session.get('track_name') or session.get('track_id') or 'unknown'}.",
        f"Session: {session.get('session_type') or 'unknown'}.",
    ]
    if result:
        scope=(f"Lap {result.get('lap')}" if result.get('scope')=='lap' else 'Session best')
        lines.append(f"{scope} lap time: {_fmt_time(result.get('lap_time_s'))}.")
        if result.get('sector1_time_s') is not None: lines.append(f"Sector 1: {_fmt_time(result.get('sector1_time_s'))}.")
        if result.get('sector2_time_s') is not None: lines.append(f"Sector 2: {_fmt_time(result.get('sector2_time_s'))}.")
        if result.get('sector3_time_s') is not None: lines.append(f"Sector 3: {_fmt_time(result.get('sector3_time_s'))}.")
        gap=result.get('gap_to_selected_reference_s')
        if isinstance(gap,(int,float)):
            lines.append(f"Gap to selected reference ({result.get('reference_label') or 'reference'}): {gap:+.3f} seconds.")
        if result.get('valid') is not None: lines.append(f"Lap validity: {'valid' if result.get('valid') else 'invalid'}.")
        if result.get('warnings') is not None: lines.append(f"Warnings: {result.get('warnings')}.")
        if result.get('penalties_s') is not None: lines.append(f"Penalties: {result.get('penalties_s')} seconds.")
        if result.get('assist_labels'): lines.append("Assists used: "+", ".join(str(x) for x in result.get('assist_labels'))+".")
        if result.get('theoretical_potential_lap_s') is not None: lines.append(f"Measured theoretical/potential lap: {_fmt_time(result.get('theoretical_potential_lap_s'))}.")
    if corner_id is None:
        score=review.get('session_technique_score')
        if isinstance(score,(int,float)): lines.append(f"Technique score: {score:.0f}/100 with {float(review.get('confidence') or 0)*100:.0f}% confidence.")
        opps=review.get('opportunities') or []
        if opps:
            lines.append("Biggest measured opportunities:")
            for x in opps[:4]:
                if not isinstance(x,dict): continue
                loss=x.get('mean_net_loss_s'); issue=x.get('dominant_issue_label') or 'measured time loss'; cid=x.get('corner_id')
                loss_txt=f"{float(loss):.3f} s" if isinstance(loss,(int,float)) else 'time loss measured'
                lines.append(f"- Turn {cid}: {issue}; {loss_txt}.")
        strengths=review.get('strengths') or []
        if strengths:
            lines.append("Measured strengths:")
            for x in strengths[:3]:
                if isinstance(x,dict): lines.append(f"- Turn {x.get('corner_id')}: {x.get('dominant_issue_label') or 'relative strength'}.")
    else:
        corner=next((x for x in review.get('corners') or [] if int(x.get('corner_id') or -1)==int(corner_id)),None)
        comp=next((x for x in selected.get('corners') or [] if int(x.get('corner_id') or -1)==int(corner_id)),None)
        lines.append(f"Selected corner: Turn {corner_id}.")
        if isinstance(corner,dict):
            if corner.get('dominant_issue_label'): lines.append(f"Primary measured issue: {corner.get('dominant_issue_label')} ({corner.get('dominant_phase') or 'phase unknown'}).")
            if isinstance(corner.get('total_measured_time_loss_s'),(int,float)): lines.append(f"Measured corner time loss: {corner.get('total_measured_time_loss_s'):.3f} seconds.")
            detail=corner.get('detail') if isinstance(corner.get('detail'),dict) else {}
            for label,key,unit in (("Brake-point difference","brake_onset_delta_m","m"),("Minimum-speed difference","min_speed_delta_kph","km/h"),("Throttle-pickup difference","throttle_pickup_delta_m","m"),("Exit-speed difference","exit_speed_delta_kph","km/h")):
                v=detail.get(key)
                if isinstance(v,(int,float)): lines.append(f"{label}: {v:+.2f} {unit}.")
        if isinstance(comp,dict) and isinstance(comp.get('time_loss_s'),(int,float)): lines.append(f"Against the currently selected visual reference, this corner changes lap time by {comp.get('time_loss_s'):+.3f} seconds.")
    return "\n".join(lines)


def generate_ai_summary(payload: dict[str, Any], corner_id: int | None = None, *, timeout_s: float = 75.0) -> str:
    context = _driver_facing_context(payload, corner_id)
    model = os.environ.get("RACE_ENGINEER_LLM_MODEL", "qwen2.5:3b")
    url = os.environ.get("RACE_ENGINEER_LLM_URL", "http://127.0.0.1:11434/api/chat")
    scope = "one selected corner" if corner_id is not None else "the full session"
    system = (
        "You are the driver's post-session sim-racing coach. Use ONLY the supplied verified facts. "
        "Speak directly to the driver in natural coaching language. Do not mention JSON, schemas, keys, field names, payloads, variables, or internal model structure. "
        "Do not invent telemetry, causes, scores, time gains, setup advice, or missing data. "
        "Keep recorded-reference scoring distinct from the separately selected comparison reference. "
        "Summarize what happened, identify the strongest measured issue or strength, and give one evidence-backed next focus. "
        "If evidence is missing, say so plainly. Use concise plain English, 90-150 words."
    )
    prompt = f"Write a driver-facing coaching summary for {scope}. Do not explain the data structure. Verified facts:\n{context}"
    body = json.dumps({
        "model": model, "stream": False, "keep_alive": "30m",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "options": {"temperature": 0.1, "num_ctx": 4096, "num_predict": 220},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            obj = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as error:
        raise RuntimeError(f"local Ollama timed out after {int(timeout_s)} s; keep Ollama running and try again") from error
    answer = str((obj.get("message") or {}).get("content") or "").strip()
    if not answer:
        raise RuntimeError("Ollama returned an empty AI summary")
    return answer


def generate_track_ai_summary(track_payload: dict[str, Any], *, timeout_s: float = 75.0) -> str:
    """Explain deterministic cross-session track progress; never invent measurements."""
    summary=track_payload.get("track_summary") if isinstance(track_payload.get("track_summary"),dict) else {}
    sessions=track_payload.get("sessions") if isinstance(track_payload.get("sessions"),list) else []
    context={
        "track":track_payload.get("track"),
        "session_count":track_payload.get("session_count"),
        "best_lap_s":summary.get("best_lap_s"),
        "predicted_potential_lap_s":summary.get("predicted_potential_lap_s"),
        "latest_best_change_s":summary.get("latest_best_change_s"),
        "latest_technique_change":summary.get("latest_technique_change"),
        "improvements":summary.get("improvements"),
        "recent_sessions":[{k:x.get(k) for k in ("created_utc","session_type","best_lap_s","potential_lap_s","session_technique_score")} for x in sessions[-5:]],
    }
    model=os.environ.get("RACE_ENGINEER_LLM_MODEL","qwen2.5:3b")
    url=os.environ.get("RACE_ENGINEER_LLM_URL","http://127.0.0.1:11434/api/chat")
    system=("You are a sim-racing track-performance explainer. Use ONLY the supplied deterministic facts. "
            "Do not invent causes, telemetry, lap time gains, or setup advice. Explain measured progress across sessions, "
            "the current measured potential, and the next evidence-backed focus. If evidence is missing, say so. 90-150 words.")
    body=json.dumps({"model":model,"stream":False,"keep_alive":"30m","messages":[{"role":"system","content":system},{"role":"user","content":"Verified track-performance facts:\n"+json.dumps(context,separators=(",",":"),default=str)}],"options":{"temperature":0.1,"num_ctx":3072,"num_predict":240}}).encode("utf-8")
    req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=timeout_s) as response:
            obj=json.loads(response.read().decode("utf-8"))
    except (TimeoutError,socket.timeout) as error:
        raise RuntimeError(f"local Ollama timed out after {int(timeout_s)} s; keep Ollama running and try again") from error
    answer=str((obj.get("message") or {}).get("content") or "").strip()
    if not answer: raise RuntimeError("Ollama returned an empty track summary")
    return answer


def generate_practice_ai_summary(payload: dict[str, Any], *, timeout_s: float = 75.0) -> str:
    """Explain the deterministic V2.0.7 practice plan without changing its decisions."""
    plan = payload.get("practice_plan") if isinstance(payload.get("practice_plan"), dict) else {}
    if not plan:
        review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
        plan = review.get("practice_plan") if isinstance(review.get("practice_plan"), dict) else {}
    session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    if not session and isinstance(payload.get("track"), str):
        session = {"track_name": payload.get("track"), "session_type": "Track history"}
    if not plan:
        raise RuntimeError("deterministic practice plan is unavailable")
    def focus(x):
        if not isinstance(x, dict):
            return None
        return {
            "corner": x.get("corner_id"),
            "issue": x.get("issue_label") or x.get("issue_code"),
            "phase": x.get("phase"),
            "measured_time_cost_s": x.get("measured_time_cost_s"),
            "confidence": x.get("confidence"),
            "repeat_count": x.get("repeat_count"),
            "trend": x.get("trend"),
            "provisional": bool(x.get("provisional")),
            "authority": x.get("authority"),
        }
    status=str(plan.get("status") or "")
    primary=focus(plan.get("primary_focus"))
    secondary=focus(plan.get("secondary_focus"))
    if status == "clear" and not primary:
        track=session.get("track_name") or session.get("track_id") or payload.get("track") or "this track"
        return f"No current measured practice issue is surviving in the newest stored session at {track}. Older weaknesses remain historical only. Use the baseline phase to confirm clean repeatability; if a measured issue reappears, the deterministic planner will promote it into the current plan."
    if not primary:
        raise RuntimeError("no deterministic current practice focus is available for AI explanation")
    context = {
        "track": session.get("track_name") or session.get("track_id") or payload.get("track"),
        "session_type": session.get("session_type"),
        "plan_status": status,
        "plan_reason": plan.get("reason"),
        "eligible_baseline_laps": plan.get("baseline_eligible_laps"),
        "track_session_count": plan.get("session_count"),
        "evidence_policy": plan.get("evidence_policy"),
        "estimated_20_min_laps": plan.get("estimated_laps"),
        "current_focus_cost_s": (plan.get("summary") or {}).get("current_focus_cost_s") if isinstance(plan.get("summary"), dict) else None,
        "primary": primary,
        "secondary": secondary,
        "verification": plan.get("verification"),
    }
    model = os.environ.get("RACE_ENGINEER_LLM_MODEL", "qwen2.5:3b")
    url = os.environ.get("RACE_ENGINEER_LLM_URL", "http://127.0.0.1:11434/api/chat")
    system = (
        "You are the driver's practice-session explainer. Use ONLY the supplied deterministic practice-plan facts. "
        "The deterministic planner is authoritative. Never select a different primary/secondary issue, never alter a measured value, "
        "never invent telemetry, setup advice, causes, lap-time gains, or confidence. Distinguish an immediate next-lap focus from a repeatable multi-lap practice focus. "
        "If the primary is provisional, explicitly say it must be validated by repeated clean-lap evidence before treating it as a recurring issue. "
        "Give a concise 20-minute brief: primary focus, what to do, how improvement will be verified, and when to move to the secondary. 80-130 words."
    )
    body = json.dumps({
        "model": model, "stream": False, "keep_alive": "30m",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": "Verified deterministic practice-plan facts:\n" + json.dumps(context, separators=(",", ":"), default=str)}],
        "options": {"temperature": 0.1, "num_ctx": 3072, "num_predict": 220},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            obj = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as error:
        raise RuntimeError(f"local Ollama timed out after {int(timeout_s)} s; keep Ollama running and try again") from error
    answer = str((obj.get("message") or {}).get("content") or "").strip()
    if not answer:
        raise RuntimeError("Ollama returned an empty practice brief")
    return answer
