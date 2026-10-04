"""V0.9.20.3 immediate post-corner coaching with safe speech timing.

The live coach consumes the existing deterministic measured-performance recorder.
It does not invent a racing line or re-score raw telemetry independently.  A
corner is considered only after enough distance has been observed beyond the
reference exit to build the same CornerAnalysis model used by post-session
analysis.  Eligible diagnoses are then held until a low-workload straight is
observed, or dropped if the next braking zone is too close.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .coaching_analysis import build_corner_analyses, build_performance_pipeline
from .distance_performance import physical_turn_boundaries
from .engineer.models import EngineerMessage, Priority


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


@dataclass(frozen=True, slots=True)
class PostCornerCoachConfig:
    enabled_profiles: tuple[str, ...] = ("time_trial", "practice", "qualifying")
    analysis_margin_m: float = 35.0
    safe_min_time_to_brake_s: float = 3.5
    abandon_time_to_brake_s: float = 1.5
    pending_max_age_s: float = 8.0
    safe_max_brake: float = 0.08
    safe_max_abs_steering: float = 0.12
    safe_min_throttle: float = 0.60
    safe_min_speed_kph: float = 80.0
    max_calls_per_lap: int = 2
    same_issue_cooldown_laps: int = 2
    min_priority_score: float = 0.060


@dataclass(slots=True)
class _PendingCall:
    message: EngineerMessage
    lap: int
    corner_id: int
    issue_code: str
    created_at: float
    next_brake_m: float | None
    track_length_m: float | None
    priority_score: float


class PostCornerCoach:
    """Session-scoped deterministic post-corner speech scheduler."""

    def __init__(self, config: PostCornerCoachConfig | None = None) -> None:
        self.config = config or PostCornerCoachConfig()
        self._lap: int | None = None
        self._evaluated: set[int] = set()
        self._calls_this_lap = 0
        self._pending: _PendingCall | None = None
        self._last_spoken_lap: dict[tuple[int, str], int] = {}
        self.generated_count = 0
        self.spoken_count = 0
        self.dropped_unsafe_count = 0
        self.suppressed_cooldown_count = 0
        self.suppressed_priority_count = 0

    def reset(self) -> None:
        self.__init__(self.config)

    @staticmethod
    def _event_profile(recorder) -> str:
        ctx = getattr(recorder, "event_context", None)
        return str((ctx or {}).get("profile") or "unknown") if isinstance(ctx, dict) else "unknown"

    @staticmethod
    def _track_length(reference: dict[str, Any]) -> float | None:
        explicit=reference.get("track_length_m") if isinstance(reference,dict) else None
        if _num(explicit) and float(explicit)>1000.0:
            return float(explicit)
        samples = reference.get("_samples") if isinstance(reference, dict) else None
        vals = []
        if isinstance(samples, dict):
            for key in samples:
                try:
                    vals.append(float(key))
                except (TypeError, ValueError):
                    pass
        if vals:
            return max(vals)
        return None

    @staticmethod
    def _canonical_sections(reference: dict[str, Any]) -> list[dict[str, Any]]:
        rows = [dict(s) for s in (reference.get("sections") or []) if isinstance(s, dict)]
        rows = [s for s in rows if _num(s.get("min_speed_m")) or _num(s.get("start_m"))]
        rows.sort(key=lambda s: float(s.get("min_speed_m") if _num(s.get("min_speed_m")) else s.get("start_m")))

        # When measured world geometry is available, T-number authority comes
        # from the physical circuit, not from the number of braking zones. A
        # long complex may therefore map brake sections to T1, T3, T4... rather
        # than compressing the whole circuit into T1..T11.
        physical_map = {}
        for turn in physical_turn_boundaries(reference, track_name=reference.get("track_name")):
            rid = turn.get("reference_section_id")
            cid = turn.get("corner_id")
            if rid is not None and isinstance(cid, int):
                physical_map[rid] = cid

        for i, section in enumerate(rows, 1):
            raw = section.get("id")
            section["_raw_reference_id"] = raw
            section["id"] = int(physical_map.get(raw, i))
        return rows

    @staticmethod
    def _nearest_sample(lap: dict[str, Any], distance: float, tolerance_m: float = 12.5):
        rows = []
        for key, value in (lap.get("_samples") or {}).items():
            try:
                d = float(key)
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict):
                rows.append((d, value))
        if not rows:
            return None
        d, sample = min(rows, key=lambda x: abs(x[0] - distance))
        return sample if abs(d - distance) <= tolerance_m else None

    @classmethod
    def _fallback_slow_turn(cls, current: dict[str, Any], reference: dict[str, Any], section: dict[str, Any], canonical_id: int):
        """Create deterministic generic advice for a slower reference turn.

        This covers a real gap in the brake-zone diagnosis path: if the current
        lap has an extra/missing brake pulse, section matching can fail even though
        the driver clearly lost time through the reference turn window.
        """
        lo = section.get("start_m")
        hi = section.get("end_m")
        if not (_num(lo) and _num(hi) and float(hi) > float(lo)):
            return None
        cs0, cs1 = cls._nearest_sample(current, float(lo)), cls._nearest_sample(current, float(hi))
        rs0, rs1 = cls._nearest_sample(reference, float(lo)), cls._nearest_sample(reference, float(hi))
        if not all(isinstance(x, dict) for x in (cs0, cs1, rs0, rs1)):
            return None
        vals = [cs0.get("t"), cs1.get("t"), rs0.get("t"), rs1.get("t")]
        if not all(_num(x) for x in vals):
            return None
        loss = (float(vals[1]) - float(vals[0])) - (float(vals[3]) - float(vals[2]))
        if loss < 0.020:
            return None
        cur_speeds=[]
        for key, sample in (current.get("_samples") or {}).items():
            try: d=float(key)
            except (TypeError, ValueError): continue
            if float(lo) <= d <= float(hi) and isinstance(sample, dict) and _num(sample.get("speed")):
                cur_speeds.append(float(sample["speed"]))
        ref_min = section.get("min_speed_kph")
        cur_min = min(cur_speeds) if cur_speeds else None
        deficit = (float(ref_min) - cur_min) if _num(ref_min) and _num(cur_min) else None
        if _num(deficit) and deficit >= 3.0:
            code = "minimum_speed_low"
            label = "Minimum speed low"
            magnitude = -float(deficit)
        else:
            code = "corner_pace_loss"
            label = "Corner pace loss"
            magnitude = loss
        return {
            "corner_id": canonical_id, "reference_corner_id": canonical_id,
            "coaching_eligible": True, "diagnosis": code, "diagnosis_label": label,
            "diagnosis_confidence": 0.85, "actionability": 0.75,
            "estimated_time_cost_s": loss, "time_loss_s": loss,
            "issue_candidates": [{"code": code, "magnitude": magnitude, "primary_eligible": True}],
        }

    @staticmethod
    def _next_brake(reference: dict[str, Any], reference_corner_id: int) -> float | None:
        turns=physical_turn_boundaries(reference,track_name=reference.get("track_name"))
        turns=[t for t in turns if isinstance(t.get("corner_id"),int)]
        for i,turn in enumerate(turns):
            if int(turn["corner_id"])==reference_corner_id:
                nxt=turns[(i+1)%len(turns)] if turns else None
                value=(nxt or {}).get("brake_m") if nxt else None
                return float(value) if _num(value) else None
        return None

    @staticmethod
    def _distance_to_brake(current_d: float, next_brake_m: float | None, track_length_m: float | None) -> float | None:
        if not _num(next_brake_m):
            return None
        nb = float(next_brake_m)
        if nb >= current_d:
            return nb - current_d
        if _num(track_length_m) and float(track_length_m) > current_d:
            return max(0.0, float(track_length_m) - current_d + nb)
        return None

    @staticmethod
    def _spoken_text(a: dict[str, Any]) -> str:
        cid = a.get("corner_id")
        code = str(a.get("diagnosis") or "")
        prefix = f"Turn {cid}: " if cid is not None else ""
        magnitude = None
        for c in a.get("issue_candidates") or []:
            if isinstance(c, dict) and c.get("code") == code and c.get("primary_eligible", True):
                magnitude = c.get("magnitude")
                break

        if code == "brake_early":
            return prefix + (f"brake about {abs(float(magnitude)):.0f} metres later." if _num(magnitude) else "brake later.")
        if code == "brake_late":
            return prefix + (f"brake about {abs(float(magnitude)):.0f} metres earlier." if _num(magnitude) else "brake earlier.")
        if code == "brake_pressure_high": return prefix + "use less peak brake."
        if code == "brake_pressure_low": return prefix + "use more peak brake."
        if code == "brake_release_abrupt": return prefix + "release the brake more progressively."
        if code == "trail_brake_weak": return prefix + "carry the brake deeper into the corner."
        if code == "trail_brake_excessive": return prefix + "release the brake earlier."
        if code == "coasting_excessive": return prefix + "reduce the coast phase."
        if code == "minimum_speed_low":
            return prefix + (f"carry about {abs(float(magnitude)):.0f} kph more minimum speed." if _num(magnitude) else "carry more minimum speed.")
        if code == "apex_speed_low":
            return prefix + (f"carry about {abs(float(magnitude)):.0f} kph more at the apex." if _num(magnitude) else "carry more speed at the apex.")
        if code == "turn_in_early": return prefix + "turn in later."
        if code == "turn_in_late": return prefix + "turn in earlier."
        if code == "throttle_late": return prefix + "pick up the throttle earlier."
        if code == "throttle_early_traction_limited": return prefix + "be smoother on throttle pickup."
        if code == "throttle_ramp_slow": return prefix + "build to full throttle faster."
        if code == "gear_choice": return prefix + "match the reference gear through the corner."
        if code == "exit_speed_low":
            return prefix + (f"find about {abs(float(magnitude)):.0f} kph more exit speed." if _num(magnitude) else "improve exit speed.")
        if code == "steering_corrections": return prefix + "use fewer steering corrections through the corner."
        if code == "steering_unsmooth": return prefix + "make the steering input smoother."
        if code == "steering_unwind_slow": return prefix + "unwind the steering earlier on exit."
        if code == "corner_pace_loss":
            cost = a.get("estimated_time_cost_s")
            return prefix + (f"match the reference line and inputs; about {float(cost):.2f} seconds lost here." if _num(cost) else "match the reference line and inputs through the corner.")
        return prefix + str(a.get("diagnosis_label") or "clean up the corner.") + "."

    def _safe_now(self, state, pending: _PendingCall) -> tuple[bool, bool]:
        player = getattr(state, "player", None)
        if player is None:
            return False, False
        lap = getattr(player, "lap", None)
        telemetry = getattr(player, "telemetry", None)
        if lap is None or telemetry is None or not _num(getattr(lap, "lap_distance_m", None)):
            return False, False
        d = float(lap.lap_distance_m)
        speed = float(getattr(telemetry, "speed_kph", 0.0) or 0.0)
        brake = float(getattr(telemetry, "brake", 0.0) or 0.0)
        throttle = float(getattr(telemetry, "throttle", 0.0) or 0.0)
        steering = float(getattr(telemetry, "steering", 0.0) or 0.0)
        distance = self._distance_to_brake(d, pending.next_brake_m, pending.track_length_m)
        time_to_brake = None
        if _num(distance) and speed > 5.0:
            time_to_brake = float(distance) / (speed / 3.6)

        too_late = time_to_brake is not None and time_to_brake <= self.config.abandon_time_to_brake_s
        safe = (
            brake <= self.config.safe_max_brake
            and abs(steering) <= self.config.safe_max_abs_steering
            and throttle >= self.config.safe_min_throttle
            and speed >= self.config.safe_min_speed_kph
            and (time_to_brake is None or time_to_brake >= self.config.safe_min_time_to_brake_s)
        )
        return safe, too_late

    def _drain_pending(self, state, now: float) -> list[EngineerMessage]:
        p = self._pending
        if p is None:
            return []
        if now - p.created_at > self.config.pending_max_age_s:
            self._pending = None
            self.dropped_unsafe_count += 1
            return []
        safe, too_late = self._safe_now(state, p)
        if too_late:
            self._pending = None
            self.dropped_unsafe_count += 1
            return []
        if not safe:
            return []
        self._pending = None
        self._last_spoken_lap[(p.corner_id, p.issue_code)] = p.lap
        self._calls_this_lap += 1
        self.spoken_count += 1
        return [p.message]

    def observe(self, recorder, state, now: float) -> list[EngineerMessage]:
        """Observe current telemetry and return at most one safe coaching line."""
        if self._event_profile(recorder) not in self.config.enabled_profiles:
            self._pending = None
            return []

        player = getattr(state, "player", None)
        lap_state = getattr(player, "lap", None) if player is not None else None
        if lap_state is None or not isinstance(getattr(lap_state, "current_lap", None), int):
            return self._drain_pending(state, now)
        lap = int(lap_state.current_lap)
        if lap != self._lap:
            self._lap = lap
            self._evaluated.clear()
            self._calls_this_lap = 0
            self._pending = None

        ready = self._drain_pending(state, now)
        if ready:
            return ready
        if self._pending is not None or self._calls_this_lap >= self.config.max_calls_per_lap:
            return []
        if not getattr(recorder, "current_lap_started_clean", False):
            return []
        if not _num(getattr(lap_state, "lap_distance_m", None)):
            return []
        d = float(lap_state.lap_distance_m)

        reference = recorder.current_reference_lap()
        if not reference:
            return []
        turns=physical_turn_boundaries(reference,track_name=reference.get("track_name"))
        track_length=self._track_length(reference)
        target=None
        for turn in turns:
            cid=turn.get("corner_id"); end_m=turn.get("end_m")
            if not isinstance(cid,int) or cid in self._evaluated or not _num(end_m):
                continue
            # Last-corner feedback cannot wait 35 m beyond an exit that sits near
            # S/F. Clamp the readiness point to the final measured bins of the lap.
            ready_m=float(end_m)+self.config.analysis_margin_m
            if _num(track_length):
                ready_m=min(ready_m,max(float(end_m),float(track_length)-7.5))
            if d>=ready_m:
                target=turn; break
        if target is None:
            return []

        cid=int(target["corner_id"])
        self._evaluated.add(cid)
        snapshot=recorder.current_lap_snapshot(state)
        if not snapshot:
            return []
        pipeline=build_performance_pipeline(snapshot,reference)
        a=next((dict(x) for x in (pipeline.get("turns") or ()) if isinstance(x,dict) and x.get("corner_id")==cid),None)
        # Compatibility fallback for old/external references and sparse test/live
        # snapshots where a continuous trace is not yet available. The integrated
        # performance pipeline remains the primary authority whenever it produced
        # a physical-turn result.
        if not a or not a.get("coaching_eligible") or not a.get("diagnosis"):
            raw_ref_id=target.get("reference_section_id")
            analyses=build_corner_analyses(snapshot,reference)
            legacy=next((x.to_dict() for x in analyses if getattr(x,"reference_corner_id",None)==raw_ref_id),None)
            if legacy is not None:
                legacy["corner_id"]=cid; legacy["reference_corner_id"]=cid
                a=legacy
        if not a or not a.get("coaching_eligible") or not a.get("diagnosis"):
            return []

        code = str(a["diagnosis"])
        last_lap = self._last_spoken_lap.get((cid, code))
        if isinstance(last_lap, int) and lap - last_lap < self.config.same_issue_cooldown_laps:
            self.suppressed_cooldown_count += 1
            return []

        cost = float(a.get("estimated_time_cost_s") or 0.0)
        conf = float(a.get("diagnosis_confidence") or 0.0)
        act = float(a.get("actionability") or 0.0)
        score = cost * conf * act
        if score < self.config.min_priority_score:
            self.suppressed_priority_count += 1
            return []

        message = EngineerMessage(
            key=f"coach:corner:{cid}:{code}",
            priority=Priority.COACHING,
            text=self._spoken_text(a),
            created_at=now,
            session_time_s=getattr(getattr(state, "session", None), "session_time_s", None),
        )
        self._pending = _PendingCall(
            message=message,
            lap=lap,
            corner_id=cid,
            issue_code=code,
            created_at=now,
            next_brake_m=self._next_brake(reference, cid),
            track_length_m=self._track_length(reference),
            priority_score=score,
        )
        self.generated_count += 1
        return self._drain_pending(state, now)

    def status(self) -> dict[str, Any]:
        p = self._pending
        return {
            "enabled_profiles": list(self.config.enabled_profiles),
            "lap": self._lap,
            "calls_this_lap": self._calls_this_lap,
            "pending": ({
                "corner_id": p.corner_id,
                "issue_code": p.issue_code,
                "priority_score": p.priority_score,
            } if p is not None else None),
            "generated_count": self.generated_count,
            "spoken_count": self.spoken_count,
            "dropped_unsafe_count": self.dropped_unsafe_count,
            "suppressed_cooldown_count": self.suppressed_cooldown_count,
            "suppressed_priority_count": self.suppressed_priority_count,
            "safe_min_time_to_brake_s": self.config.safe_min_time_to_brake_s,
            "max_calls_per_lap": self.config.max_calls_per_lap,
            "same_issue_cooldown_laps": self.config.same_issue_cooldown_laps,
        }
