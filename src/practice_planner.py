"""V2.0.7 deterministic 20-minute Practice Planner.

This module is integration-only. It consumes already-authoritative measured
session evidence (coaching priority memory, recurring patterns, lap/stint data
and Performance Review lap scores). It never re-detects telemetry, never changes
score/confidence rules, and never generates generic setup/coaching claims.
"""
from __future__ import annotations

from typing import Any
import math

PRACTICE_PLANNER_VERSION = "2.0.7.2"


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _round(value: Any, digits: int = 3):
    return round(float(value), digits) if _num(value) else None



def _focus_group(row: dict[str, Any] | None) -> tuple[Any, str] | None:
    """Group correlated diagnoses that describe the same corner phase/event."""
    if not isinstance(row, dict):
        return None
    cid=row.get("corner_id")
    phase=str(row.get("phase") or row.get("dominant_phase") or "").strip().upper()
    if not phase:
        text=(str(row.get("issue_code") or "")+" "+str(row.get("issue_label") or "")).lower()
        if any(x in text for x in ("brak", "turn-in", "entry")): phase="ENTRY"
        elif any(x in text for x in ("apex", "minimum speed", "mid")): phase="MID"
        elif any(x in text for x in ("throttle", "exit", "unwind")): phase="EXIT"
        else: phase=str(row.get("issue_code") or "MEASURED").upper()
    return (cid, phase)

def _active_pattern(rows: list[dict[str, Any]], excluded: set[tuple[Any, str]], excluded_groups: set[tuple[Any, str]] | None = None) -> dict[str, Any] | None:
    excluded_groups = excluded_groups or set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (row.get("corner_id"), str(row.get("issue_code") or ""))
        if key in excluded or _focus_group(row) in excluded_groups:
            continue
        if row.get("latest_observed") is False:
            continue
        if int(row.get("repeat_count") or 0) < 2:
            continue
        if not _num(row.get("mean_time_cost_s")) or float(row["mean_time_cost_s"]) <= 0.0:
            continue
        return row
    return None


def _fallback_opportunity(rows: list[dict[str, Any]], excluded_corners: set[Any]) -> dict[str, Any] | None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("corner_id")
        if cid in excluded_corners:
            continue
        cost = row.get("mean_net_loss_s")
        if not _num(cost) or float(cost) <= 0.0:
            continue
        return {
            "corner_id": cid,
            "issue_code": str(row.get("dominant_issue") or "measured_loss"),
            "issue_label": str(row.get("dominant_issue_label") or "Measured loss"),
            "phase": row.get("dominant_phase"),
            "repeat_count": int(row.get("observations") or 1),
            "mean_time_cost_s": float(cost),
            "recent_time_cost_s": float(cost),
            "mean_confidence": float(row.get("confidence") or 0.0) if _num(row.get("confidence")) else 0.0,
            "trend": "insufficient_history",
            "trend_delta_s": None,
            "latest_observed": True,
            "source": "ranked_opportunity",
        }
    return None


def _focus_payload(row: dict[str, Any] | None, *, rank: int) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    cid = row.get("corner_id")
    label = str(row.get("issue_label") or row.get("dominant_issue_label") or row.get("issue_code") or "Measured issue")
    phase = row.get("phase") or row.get("dominant_phase")
    cost = row.get("recent_time_cost_s") if _num(row.get("recent_time_cost_s")) else row.get("mean_time_cost_s")
    return {
        "rank": rank,
        "corner_id": int(cid) if isinstance(cid, int) else cid,
        "issue_code": str(row.get("issue_code") or row.get("dominant_issue") or "measured_loss"),
        "issue_label": label,
        "phase": phase,
        "measured_time_cost_s": _round(cost),
        "mean_time_cost_s": _round(row.get("mean_time_cost_s")),
        "confidence": _round(row.get("mean_confidence") if _num(row.get("mean_confidence")) else row.get("confidence"), 3) or 0.0,
        "repeat_count": int(row.get("repeat_count") or row.get("observations") or 0),
        "trend": str(row.get("trend") or "insufficient_history"),
        "trend_delta_s": _round(row.get("trend_delta_s")),
        "instruction": f"T{cid}: {label}" if cid is not None else label,
    }


def _latest_next_lap_focus(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Reuse the existing coaching-priority decision; do not create a new coach."""
    comparisons = [x for x in report.get("lap_comparisons") or [] if isinstance(x, dict)]
    for comp in reversed(comparisons):
        priority = comp.get("coaching_priority") if isinstance(comp.get("coaching_priority"), dict) else {}
        ranked = [x for x in priority.get("ranked_candidates") or [] if isinstance(x, dict)]
        if not ranked:
            selected = priority.get("selected_focus")
            ranked = [selected] if isinstance(selected, dict) else []
        out = []
        used = set()
        for row in ranked:
            if len(out) >= 2:
                break
            cid = row.get("corner_id")
            code = str(row.get("issue_code") or "")
            key = (cid, code)
            if key in used:
                continue
            used.add(key)
            out.append({
                "corner_id": cid,
                "issue_code": code,
                "issue_label": str(row.get("issue_label") or code or "Measured issue"),
                "phase": row.get("phase"),
                "measured_time_cost_s": _round(row.get("estimated_time_cost_s")),
                "confidence": _round(row.get("confidence"), 3) or 0.0,
                "priority_rank": int(row.get("rank") or len(out) + 1),
            })
        if out:
            return out
    return []


def _provisional_from_next_lap(rows: list[dict[str, Any]], *, excluded: set[tuple[Any, str]] | None = None, excluded_groups: set[tuple[Any, str]] | None = None) -> dict[str, Any] | None:
    """Promote an existing next-lap coaching decision as a provisional practice target.

    This does not make the issue repeatable. It only lets the 20-minute planner
    consume the existing coaching-priority authority when recurring-pattern
    history is absent. The baseline/verification phases must establish repeatability.
    """
    excluded = excluded or set()
    excluded_groups = excluded_groups or set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("corner_id")
        code = str(row.get("issue_code") or "")
        if (cid, code) in excluded or _focus_group(row) in excluded_groups:
            continue
        cost = row.get("measured_time_cost_s")
        conf = row.get("confidence")
        if not _num(cost) or float(cost) <= 0.0:
            continue
        if not _num(conf) or float(conf) <= 0.0:
            continue
        return {
            "corner_id": cid,
            "issue_code": code or "measured_loss",
            "issue_label": str(row.get("issue_label") or code or "Measured issue"),
            "phase": row.get("phase"),
            "repeat_count": 1,
            "mean_time_cost_s": float(cost),
            "recent_time_cost_s": float(cost),
            "mean_confidence": float(conf),
            "trend": "needs_repeat_validation",
            "trend_delta_s": None,
            "latest_observed": True,
            "source": "coaching_priority_provisional",
            "provisional": True,
        }
    return None


def build_practice_plan(report: dict[str, Any] | None, review: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the V2.0.7 20-minute plan from measured evidence only.

    The phase structure is fixed by the roadmap. Issue selection, verification
    status and next-lap focus are all sourced from existing deterministic
    measurements.
    """
    report = report if isinstance(report, dict) else {}
    review = review if isinstance(review, dict) else {}
    quality = report.get("coaching_data_quality") if isinstance(report.get("coaching_data_quality"), dict) else {}
    eligible_laps = [x for x in quality.get("eligible_laps") or [] if isinstance(x, int)]
    if not eligible_laps:
        dq = review.get("data_quality") if isinstance(review.get("data_quality"), dict) else {}
        eligible_laps = [x for x in dq.get("eligible_laps") or [] if isinstance(x, int)]

    patterns = [x for x in report.get("recurring_patterns") or [] if isinstance(x, dict)]
    patterns.sort(key=lambda x: (
        float(x.get("focus_score") or 0.0) if _num(x.get("focus_score")) else 0.0,
        float(x.get("mean_time_cost_s") or 0.0) if _num(x.get("mean_time_cost_s")) else 0.0,
        int(x.get("repeat_count") or 0),
    ), reverse=True)
    opportunities = [x for x in report.get("ranked_biggest_opportunities") or [] if isinstance(x, dict)]
    if not opportunities:
        # Performance Review is another persisted view of the same deterministic
        # measured-loss evidence. Use it only when the report-side ranking is absent.
        opportunities = [x for x in review.get("opportunities") or [] if isinstance(x, dict)]

    next_lap_focus = _latest_next_lap_focus(report)
    excluded: set[tuple[Any, str]] = set()
    primary_row = _active_pattern(patterns, excluded)
    primary_authority = "recurring_pattern" if primary_row is not None else None
    if primary_row is None:
        primary_row = _fallback_opportunity(opportunities, set())
        if primary_row is not None:
            primary_authority = "ranked_measured_opportunity"
    if primary_row is None:
        primary_row = _provisional_from_next_lap(next_lap_focus)
        if primary_row is not None:
            primary_authority = "next_lap_focus_provisional"
    excluded_groups: set[tuple[Any, str]] = set()
    if primary_row:
        excluded.add((primary_row.get("corner_id"), str(primary_row.get("issue_code") or "")))
        group=_focus_group(primary_row)
        if group is not None: excluded_groups.add(group)

    secondary_row = _active_pattern(patterns, excluded, excluded_groups)
    secondary_authority = "recurring_pattern" if secondary_row is not None else None
    if secondary_row is None:
        # Ranked opportunity fallback has historically used a different corner,
        # which remains the safest independent target when pattern evidence is absent.
        secondary_row = _fallback_opportunity(opportunities, {primary_row.get("corner_id")} if primary_row else set())
        if secondary_row is not None:
            secondary_authority = "ranked_measured_opportunity"
    if secondary_row is None:
        secondary_row = _provisional_from_next_lap(next_lap_focus, excluded=excluded, excluded_groups=excluded_groups)
        if secondary_row is not None:
            secondary_authority = "next_lap_focus_provisional"

    primary = _focus_payload(primary_row, rank=1)
    secondary = _focus_payload(secondary_row, rank=2)
    if primary is not None:
        primary["authority"] = primary_authority
        primary["provisional"] = bool(primary_row.get("provisional"))
    if secondary is not None:
        secondary["authority"] = secondary_authority
        secondary["provisional"] = bool(secondary_row.get("provisional"))

    best = report.get("best_lap") if isinstance(report.get("best_lap"), dict) else {}
    best_lap_s = best.get("lap_time_s")
    if not _num(best_lap_s):
        p = report.get("potential") if isinstance(report.get("potential"), dict) else {}
        best_lap_s = p.get("best_lap_s")
    estimated_20m_laps = max(1, int(1200.0 / float(best_lap_s))) if _num(best_lap_s) and float(best_lap_s) > 0 else None

    primary_trend = primary.get("trend") if primary else None
    primary_improved = primary_trend == "improving"
    primary_cost = primary.get("measured_time_cost_s") if primary else None
    potential = report.get("potential") if isinstance(report.get("potential"), dict) else {}
    theoretical_gain = potential.get("realistic_available_gain_s") if _num(potential.get("realistic_available_gain_s")) else potential.get("potential_gain_s")
    # Practice "remaining opportunity" follows the selected measured focus.
    # Theoretical lap potential is a separate pace metric and can be zero even
    # while a measured corner issue still costs time.
    remaining_gain = primary_cost if _num(primary_cost) else theoretical_gain

    primary_provisional = bool(primary and primary.get("provisional"))
    evidence_ok = len(eligible_laps) >= 2 and primary is not None
    plan_status = "available" if evidence_ok and not primary_provisional else ("provisional" if evidence_ok else "insufficient_evidence")
    reason = None
    if len(eligible_laps) < 2:
        reason = "need_at_least_2_quality_eligible_laps"
    elif primary is None:
        reason = "no_measured_focus_available"
    elif primary_provisional:
        reason = "next_lap_focus_needs_repeat_validation"

    phases = [
        {
            "order": 1, "name": "Baseline", "start_min": 0, "end_min": 4,
            "goal": "Establish 2–3 clean representative laps before changing the focus.",
            "evidence": f"{len(eligible_laps)} quality-eligible lap(s) available from the reviewed session.",
            "focus": None,
        },
        {
            "order": 2, "name": "Primary issue", "start_min": 4, "end_min": 10,
            "goal": primary.get("instruction") if primary else "No primary measured issue available.",
            "evidence": ((f"Immediate measured focus {primary_cost:.3f} s · confidence {float(primary.get('confidence') or 0)*100:.0f}% · repeat validation required" if primary_provisional else f"Measured cost {primary_cost:.3f} s · repeats {primary.get('repeat_count',0)} · trend {primary.get('trend')}") if primary and _num(primary_cost) else "Insufficient measured primary-issue evidence."),
            "focus": primary,
        },
        {
            "order": 3, "name": "Verification", "start_min": 10, "end_min": 14,
            "goal": "Re-measure the same issue over clean laps; improvement is evidence-based, not lap-time-only.",
            "evidence": ("Establish repeated observations first; then apply the existing ±0.015 s issue-cost trend deadband." if primary_provisional else ("Existing evidence already trends improving; verify that the issue remains reduced." if primary_improved else "Use the existing ±0.015 s measured issue-cost trend deadband when comparing repeated observations.")),
            "focus": primary,
        },
        {
            "order": 4, "name": "Secondary issue", "start_min": 14, "end_min": 18,
            "goal": (secondary.get("instruction") if secondary else "Stay on the primary issue; no independent secondary issue is sufficiently measured."),
            "evidence": ("Move here only after the primary issue improves or stops surviving the existing loss/confidence gates." if secondary else "No second measured recurring issue available."),
            "focus": secondary,
            "conditional": True,
        },
        {
            "order": 5, "name": "Summary", "start_min": 18, "end_min": 20,
            "goal": "Finish with clean laps and compare measured issue cost, session score trend and remaining opportunity.",
            "evidence": (f"Current measured remaining opportunity {float(remaining_gain):.3f} s." if _num(remaining_gain) else "Remaining opportunity unavailable from current evidence."),
            "focus": None,
        },
    ]

    return {
        "version": PRACTICE_PLANNER_VERSION,
        "status": plan_status,
        "reason": reason,
        "duration_minutes": 20,
        "estimated_laps": estimated_20m_laps,
        "baseline_eligible_laps": len(eligible_laps),
        "primary_focus": primary,
        "secondary_focus": secondary,
        "next_lap_focus": next_lap_focus[:2],
        "verification": {
            "rule": "Same corner/issue repeated measurement; improvement is confirmed if the issue stops surviving existing gates or measured time cost improves by at least 0.015 s.",
            "primary_trend": primary_trend,
            "primary_trend_delta_s": primary.get("trend_delta_s") if primary else None,
            "already_improving": bool(primary_improved),
        },
        "summary": {
            "best_lap_s": _round(best_lap_s),
            "remaining_opportunity_s": _round(remaining_gain),
            "eligible_laps": eligible_laps,
        },
        "phases": phases,
        "evidence_authority": {"primary": primary_authority, "secondary": secondary_authority, "next_lap": "existing_coaching_priority" if next_lap_focus else None},
        "secondary_selection_rule": "next-highest independently measured corner/phase issue; correlated diagnoses from the same corner phase are one practice target; the same technique may appear at a different corner when measured evidence ranks it next",
        "method": "integration of existing measured-loss, coaching-priority, lap/stint and review evidence; no new coaching detector",
    }


def build_track_practice_plan(session_reports: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Build one current practice plan for a driver+track across stored LIVE sessions.

    Historical evidence strengthens/weakens issues, but only issues still observed
    in the newest stored session are treated as current recurring targets. This
    prevents an older mastered weakness from remaining the recommended focus.
    The underlying per-session coaching/scoring engines are not changed.
    """
    rows = [x for x in (session_reports or []) if isinstance(x, dict)]
    if not rows:
        return {
            "version": PRACTICE_PLANNER_VERSION,
            "scope": "track",
            "status": "insufficient_evidence",
            "reason": "no_track_sessions",
            "session_count": 0,
            "baseline_eligible_laps": 0,
            "primary_focus": None,
            "secondary_focus": None,
            "next_lap_focus": [],
        }

    # Caller supplies chronological rows; keep that contract explicit.
    latest = rows[-1]
    latest_report = latest.get("report") if isinstance(latest.get("report"), dict) else {}
    latest_review = latest.get("review") if isinstance(latest.get("review"), dict) else {}

    # Build historical observations for recurring issues. Only issues still
    # present in the latest session are considered current; older-only keys are
    # reported as resolved/stale and cannot become a primary/secondary target.
    history: dict[tuple[Any, str], list[dict[str, Any]]] = {}
    session_eligible_total = 0
    for idx, item in enumerate(rows):
        report = item.get("report") if isinstance(item.get("report"), dict) else {}
        review = item.get("review") if isinstance(item.get("review"), dict) else {}
        quality = report.get("coaching_data_quality") if isinstance(report.get("coaching_data_quality"), dict) else {}
        eligible = [x for x in quality.get("eligible_laps") or [] if isinstance(x, int)]
        if not eligible:
            dq = review.get("data_quality") if isinstance(review.get("data_quality"), dict) else {}
            eligible = [x for x in dq.get("eligible_laps") or [] if isinstance(x, int)]
        session_eligible_total += len(eligible)
        for p in report.get("recurring_patterns") or []:
            if not isinstance(p, dict):
                continue
            key = (p.get("corner_id"), str(p.get("issue_code") or ""))
            if key[0] is None or not key[1]:
                continue
            obs = dict(p)
            obs["_session_index"] = idx
            obs["_session_id"] = item.get("session_id")
            obs["_created_utc"] = item.get("created_utc")
            history.setdefault(key, []).append(obs)

    latest_keys: set[tuple[Any, str]] = set()
    for p in latest_report.get("recurring_patterns") or []:
        if isinstance(p, dict):
            key = (p.get("corner_id"), str(p.get("issue_code") or ""))
            if key[0] is not None and key[1] and p.get("latest_observed") is not False:
                latest_keys.add(key)
    latest_quality = latest_report.get("coaching_data_quality") if isinstance(latest_report.get("coaching_data_quality"), dict) else {}
    latest_eligible = [x for x in latest_quality.get("eligible_laps") or [] if isinstance(x, int)]
    latest_mode = latest.get("reference_evidence_mode")
    latest_can_retire = (latest_mode == "verified" or latest_mode is None) and len(latest_eligible) >= 2
    # Absence in an unverified/thin latest session is not proof that an older
    # track weakness was mastered.  Keep historical issues provisional until a
    # sufficiently measured session against the selected Practice Reference can
    # actually confirm their disappearance.
    if not latest_can_retire:
        latest_keys.update(history.keys())

    aggregated: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    for key, obs in history.items():
        obs = sorted(obs, key=lambda x: int(x.get("_session_index") or 0))
        last = obs[-1]
        costs = [float(x.get("recent_time_cost_s") if _num(x.get("recent_time_cost_s")) else x.get("mean_time_cost_s")) for x in obs if _num(x.get("recent_time_cost_s")) or _num(x.get("mean_time_cost_s"))]
        confs = [float(x.get("mean_confidence")) for x in obs if _num(x.get("mean_confidence"))]
        latest_cost = costs[-1] if costs else None
        prev_cost = costs[-2] if len(costs) > 1 else None
        delta = (latest_cost - prev_cost) if _num(latest_cost) and _num(prev_cost) else None
        if _num(delta):
            trend = "improving" if float(delta) <= -0.015 else "regressing" if float(delta) >= 0.015 else "stable"
        else:
            trend = str(last.get("trend") or "insufficient_history")
        row = dict(last)
        row["repeat_count"] = sum(max(1, int(x.get("repeat_count") or 1)) for x in obs)
        row["session_repeat_count"] = len(obs)
        row["mean_time_cost_s"] = (sum(costs) / len(costs)) if costs else None
        row["recent_time_cost_s"] = latest_cost
        row["mean_confidence"] = (sum(confs) / len(confs)) if confs else (float(last.get("mean_confidence")) if _num(last.get("mean_confidence")) else 0.0)
        row["trend"] = trend
        row["trend_delta_s"] = delta
        row["source"] = "track_history_recurring_pattern"
        row["latest_observed"] = key in latest_keys
        row["history_sessions"] = len(obs)
        # Track-practice recurrence requires evidence from at least two stored
        # sessions. A current issue seen in only the newest session remains a
        # measured target, but is provisional until another session confirms it.
        row["provisional"] = len(obs) < 2
        if key in latest_keys:
            aggregated.append(row)
        else:
            resolved.append({
                "corner_id": key[0],
                "issue_code": key[1],
                "issue_label": str(last.get("issue_label") or key[1]),
                "last_measured_time_cost_s": _round(latest_cost),
                "history_sessions": len(obs),
                "state": "resolved_or_not_current",
            })

    aggregated.sort(key=lambda x: (
        float(x.get("recent_time_cost_s") or 0.0) if _num(x.get("recent_time_cost_s")) else 0.0,
        int(x.get("session_repeat_count") or 0),
        float(x.get("mean_confidence") or 0.0) if _num(x.get("mean_confidence")) else 0.0,
    ), reverse=True)

    synthetic_report = dict(latest_report)
    synthetic_report["recurring_patterns"] = aggregated
    # Current-state opportunities and next-lap priority deliberately come from
    # the newest session, while historical sessions only affect recurrence/trend.
    quality = synthetic_report.get("coaching_data_quality") if isinstance(synthetic_report.get("coaching_data_quality"), dict) else {}
    quality = dict(quality)
    quality["eligible_laps"] = list(range(1, session_eligible_total + 1))
    synthetic_report["coaching_data_quality"] = quality

    plan = build_practice_plan(synthetic_report, latest_review)
    # Track-level readiness requires cross-session recurrence. The session-level
    # planner may report AVAILABLE when repeat_count is high inside one session;
    # that is still provisional for a progression plan until a second compatible
    # stored session confirms the same corner/issue.
    if isinstance(plan.get("primary_focus"), dict):
        pk=(plan["primary_focus"].get("corner_id"), str(plan["primary_focus"].get("issue_code") or ""))
        src=next((x for x in aggregated if (x.get("corner_id"),str(x.get("issue_code") or ""))==pk),None)
        if isinstance(src,dict) and int(src.get("history_sessions") or 0)<2:
            plan["status"]="provisional"
            plan["reason"]="current_issue_needs_cross_session_repeat_validation"
            plan["primary_focus"]["provisional"]=True
            plan["primary_focus"]["authority"]="track_current_provisional"
            plan["primary_focus"]["history_sessions"]=int(src.get("history_sessions") or 1)
    # A current pattern seen in only one stored session is measured but not yet
    # cross-session repeatable. Keep it visible as PROVISIONAL instead of
    # incorrectly reporting either READY or NO CURRENT ISSUE.
    if plan.get("primary_focus") is None and aggregated:
        first=_focus_payload(aggregated[0], rank=1)
        if first is not None:
            first["authority"]="track_current_provisional"
            first["provisional"]=True
            first["history_sessions"]=int(aggregated[0].get("history_sessions") or 1)
            plan["primary_focus"]=first
            second=None
            second_source=next((row for row in aggregated[1:] if _focus_group(row) != _focus_group(aggregated[0])),None)
            if second_source is not None:
                second=_focus_payload(second_source, rank=2)
                if second is not None:
                    second["authority"]="track_current_provisional"
                    second["provisional"]=True
                    second["history_sessions"]=int(second_source.get("history_sessions") or 1)
                    plan["secondary_focus"]=second
            plan["status"]="provisional"
            plan["reason"]="current_issue_needs_cross_session_repeat_validation"
            phases=plan.get("phases") if isinstance(plan.get("phases"),list) else []
            if len(phases)>=2:
                phases[1]["goal"]=first.get("instruction") or phases[1].get("goal")
                phases[1]["evidence"]=f"Current measured issue {float(first.get('measured_time_cost_s') or 0):.3f} s · confidence {float(first.get('confidence') or 0)*100:.0f}% · confirm across another stored session"
                phases[1]["focus"]=first
            if len(phases)>=3:
                phases[2]["evidence"]="Confirm repeated clean-lap evidence and cross-session recurrence before treating this issue as established."
                phases[2]["focus"]=first
            if len(phases)>=4 and second is not None:
                phases[3]["goal"]=second.get("instruction") or phases[3].get("goal")
                phases[3]["focus"]=second
    plan["scope"] = "track"
    plan["session_count"] = len(rows)
    plan["baseline_eligible_laps"] = session_eligible_total
    plan["latest_session_id"] = latest.get("session_id")
    plan["latest_session_utc"] = latest.get("created_utc")
    plan["track_name"] = latest.get("track_name") or latest.get("track_id")
    plan["resolved_or_not_current"] = resolved[:12]
    plan["evidence_policy"] = "track_weather_history_selected_reference_confirmation_authority"
    # Track best is useful only for the pace ceiling; current issue selection is
    # still latest-session-authoritative.
    bests = [float(x.get("best_lap_s")) for x in rows if _num(x.get("best_lap_s")) and float(x.get("best_lap_s")) > 0]
    if bests:
        best = min(bests)
        plan.setdefault("summary", {})["track_best_lap_s"] = best
        plan["estimated_laps"] = max(1, int(1200.0 // best))

    # Track workspace states distinguish "we have enough evidence and no
    # weakness is currently surviving" from genuine lack of evidence.
    if session_eligible_total >= 2 and plan.get("primary_focus") is None and not plan.get("next_lap_focus"):
        plan["status"] = "clear"
        plan["reason"] = "no_current_measured_issue"

    # Practice opportunity must describe the selected current focus, not the
    # theoretical-lap potential. The latter is a different metric and made the
    # UI contradictory when a >1 s measured issue coexisted with 0.001 s
    # theoretical potential.
    primary = plan.get("primary_focus") if isinstance(plan.get("primary_focus"), dict) else None
    summary = plan.setdefault("summary", {})
    current_cost = primary.get("measured_time_cost_s") if primary else None
    summary["current_focus_cost_s"] = _round(current_cost) if _num(current_cost) else (0.0 if plan.get("status") == "clear" else None)
    return plan
