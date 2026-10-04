"""Deterministic actionable performance coaching from measured lap traces."""
from __future__ import annotations

from .lap_analysis import compare_sections


def _num(v):
    return isinstance(v, (int, float))


def _corner_actions(current: dict, reference: dict, *, max_actions: int = 3) -> list[dict]:
    actions = []
    for c in compare_sections(current, reference):
        candidates = []
        # Positive brake-point delta means current braking starts later than reference.
        d = c.brake_point_delta_m
        if _num(d) and abs(d) >= 8:
            if d < 0:
                candidates.append((abs(d) / 12.0, f"Turn {c.section}: brake about {abs(d):.0f} metres later."))
            else:
                candidates.append((abs(d) / 14.0, f"Turn {c.section}: reference brakes about {abs(d):.0f} metres earlier."))
        d = c.min_speed_delta_kph
        if _num(d) and abs(d) >= 4:
            if d < 0:
                candidates.append((abs(d) / 5.0, f"Turn {c.section}: carry about {abs(d):.0f} kph more minimum speed."))
        d = c.full_throttle_delta_m
        if _num(d) and abs(d) >= 10:
            if d > 0:
                candidates.append((abs(d) / 14.0, f"Turn {c.section}: reach full throttle about {abs(d):.0f} metres earlier."))
        d = c.exit_speed_delta_kph
        if _num(d) and d <= -4:
            candidates.append((abs(d) / 5.0, f"Turn {c.section}: improve exit; reference is about {abs(d):.0f} kph faster."))
        d = c.max_slip_delta
        if _num(d) and d >= 0.05:
            candidates.append((d * 12.0, f"Turn {c.section}: reduce wheel slip on exit."))
        if candidates:
            score, text = max(candidates, key=lambda x: x[0])
            actions.append({"score": score, "text": text, "section": c.section})
    actions.sort(key=lambda x: x["score"], reverse=True)
    return actions[:max_actions]


def coaching_summary(current: dict | None, reference: dict | None, *, max_actions: int = 2) -> str:
    if not current or not reference:
        return "Performance coaching needs a completed lap and a valid reference lap."
    dt = None
    if _num(current.get("lap_time_s")) and _num(reference.get("lap_time_s")):
        dt = current["lap_time_s"] - reference["lap_time_s"]
    actions = _corner_actions(current, reference, max_actions=max_actions)
    parts = []
    if _num(dt):
        parts.append(f"Lap is {abs(dt):.3f} seconds {'off the reference' if dt > 0 else 'faster than the reference'}")
    parts.extend(a["text"] for a in actions)
    return " ".join(parts) if parts else "No large deterministic driving difference found against the reference."
