"""Integrated live deterministic coach for V1.0.3.1.

Combines the previously separate post-corner scheduler with:
- pre-corner reminders based on the previous measured issue;
- current-speed / distance-to-reference-brake timing;
- lap-end summaries and positive improvement acknowledgement;
- session coaching memory and conservative race-context suppression;
- persistent user switches/modes.

No path in this module predicts an unseen driver action.  Pre-corner calls are
reminders of an already measured issue and already measured reference target.
"""
from __future__ import annotations

from dataclasses import replace
import math
from typing import Any

from .coaching_analysis import build_corner_analyses, build_performance_pipeline
from .coaching_priority import CoachingMemory
from .session_advice_memory import AdviceOutcomeMemory
from .coaching_settings import CoachingSettings, CoachingSettingsStore
from .data_quality import live_context_blockers, lap_quality
from .engineer.models import EngineerMessage, Priority
from .post_corner_coach import PostCornerCoach, PostCornerCoachConfig
from .distance_performance import physical_turn_boundaries
from .potential_lap import potential_summary
from .track_landmarks import TrackLandmarkStore
from .technique_metrics import session_technique_metrics
from .racing_line import compare_racing_line
from .race_context import assess_race_context


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _profile(recorder) -> str:
    ctx = getattr(recorder, "event_context", None)
    return str((ctx or {}).get("profile") or "unknown") if isinstance(ctx, dict) else "unknown"


def _is_race(profile: str) -> bool:
    return profile in {"race", "sprint", "sprint_race"}


def _track_key(recorder, state) -> str:
    ctx = getattr(recorder, "event_context", None)
    if isinstance(ctx, dict) and ctx.get("track_id") is not None:
        return str(ctx.get("track_id"))
    track = getattr(getattr(state, "session", None), "track", None)
    raw = getattr(track, "raw", None)
    return str(raw if raw is not None else getattr(track, "name", "unknown"))


def _primary_for_corner(analyses: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Return eligible advice keyed by the authoritative reference turn ID.

    Live/current-lap brake-zone numbering can change when an extra brake pulse is
    detected.  The external reference is the stable authority for spoken/map turn
    numbers, so all downstream coaching uses reference_corner_id when available.
    """
    out: dict[int, dict[str, Any]] = {}
    for a in analyses:
        if not isinstance(a, dict) or not a.get("coaching_eligible") or not a.get("diagnosis"):
            continue
        cid = a.get("reference_corner_id") if isinstance(a.get("reference_corner_id"), int) else a.get("corner_id")
        if not isinstance(cid, int):
            continue
        row = dict(a)
        row["corner_id"] = cid
        out[cid] = row
    return out


def _issue_cost(a: dict[str, Any] | None, code: str | None = None) -> float | None:
    if not isinstance(a, dict): return None
    if code is None or a.get("diagnosis") == code:
        v = a.get("estimated_time_cost_s")
        return float(v) if _num(v) else None
    for c in a.get("issue_candidates") or []:
        if isinstance(c, dict) and c.get("code") == code and c.get("primary_eligible", True) and _num(c.get("estimated_time_cost_s")):
            return float(c["estimated_time_cost_s"])
    return None


class IntegratedLiveCoach:
    def __init__(self, settings_store: CoachingSettingsStore | None = None) -> None:
        self.store = settings_store or CoachingSettingsStore()
        self.memory = CoachingMemory()
        self.advice_memory = AdviceOutcomeMemory()
        self.landmarks = TrackLandmarkStore()
        self.post = self._new_post(self.store.settings, race=False)
        self._post_profile_race = False
        self._last_completed_count = 0
        self._last_lap = None
        self._advice: dict[int, dict[str, Any]] = {}
        self._previous_advice: dict[int, dict[str, Any]] = {}
        self._pre_spoken: set[int] = set()
        self._pre_calls_this_lap = 0
        self._positive_pending: EngineerMessage | None = None
        self._lap_summary_pending: EngineerMessage | None = None
        self._radio_busy_until = 0.0
        self._last_analysis_lap: int | None = None
        self._last_priority: dict[str, Any] | None = None
        self._potential: dict[str, Any] = {}
        self._technique: dict[str, Any] = {}
        self._racing_line: dict[str, Any] = {"available": False}
        self._distance_performance: dict[str, Any] = {"available": False}
        self._turn_performance: list[dict[str, Any]] = []
        self._last_blockers: list[str] = []
        self._pre_generated = 0
        self._pre_spoken_count = 0
        self._lap_summary_count = 0
        self._positive_count = 0
        self._seed_reference_id: int | None = None
        self._damage_signature: tuple[int, int, bool, bool] | None = None
        self._damage_changed_at: float = 0.0
        self._damage_stable = False
        self.allow_damage_coaching = False
        self._race_context: dict[str, Any] = {"level":"unavailable","technique_coaching_allowed":False,"reasons":["not_observed"]}

    @staticmethod
    def _new_post(settings: CoachingSettings, race: bool) -> PostCornerCoach:
        # In race coaching the user wants coverage, not a one-corner quota.
        # CornerAnalysis already applies the measured-loss/deadband eligibility gate,
        # so allow every eligible slower corner to speak once per lap.
        max_calls = 32 if race else settings.post_corner_max_calls_per_lap
        return PostCornerCoach(PostCornerCoachConfig(
            enabled_profiles=("time_trial", "practice", "qualifying", "race", "sprint", "sprint_race", "unknown"),
            max_calls_per_lap=max_calls,
            same_issue_cooldown_laps=0 if race else settings.same_issue_cooldown_laps,
            min_priority_score=0.0 if race else 0.060,
        ))


    @staticmethod
    def _reference_seed_advice(reference: dict[str, Any]) -> dict[int, dict[str, Any]]:
        """Build first-lap PRE targets for every physical reference turn."""
        out: dict[int, dict[str, Any]] = {}
        samples=reference.get("_samples") or {}
        def near(distance,key):
            rows=[]
            for raw,row in samples.items():
                try:d=float(raw)
                except (TypeError,ValueError):continue
                if isinstance(row,dict) and _num(row.get(key)): rows.append((abs(d-float(distance)),row.get(key)))
            return min(rows,key=lambda x:x[0])[1] if rows else None
        for turn in physical_turn_boundaries(reference,track_name=reference.get("track_name")):
            cid=turn.get("corner_id")
            if not isinstance(cid,int): continue
            apex=turn.get("apex_m"); start_m=turn.get("start_m")
            min_speed=None
            if _num(start_m) and _num(turn.get("end_m")):
                vals=[]
                for raw,row in samples.items():
                    try:d=float(raw)
                    except (TypeError,ValueError):continue
                    if float(start_m)<=d<=float(turn["end_m"]) and isinstance(row,dict) and _num(row.get("speed")):
                        vals.append(float(row["speed"]))
                if vals:min_speed=min(vals)
            gear=near(apex,"gear") if _num(apex) else None
            out[cid]={
                "corner_id":cid,"reference_corner_id":cid,"diagnosis":"reference_target",
                "diagnosis_label":"Reference target","reference_guidance":True,
                "estimated_time_cost_s":0.0,"diagnosis_confidence":1.0,"actionability":1.0,"issue_candidates":[],
                "reference_brake_m":turn.get("brake_m"),"reference_turn_in_m":turn.get("turn_in_m"),
                "reference_apex_m":turn.get("apex_m"),"reference_exit_m":turn.get("end_m"),
                "reference_min_speed_kph":min_speed,
                "reference_apex_gear":int(round(float(gear))) if _num(gear) else None,
            }
        # Old references without world geometry still expose canonical sections.
        if not out:
            for sec in PostCornerCoach._canonical_sections(reference):
                if not isinstance(sec.get("id"),int):continue
                cid=int(sec["id"])
                out[cid]={"corner_id":cid,"reference_corner_id":cid,"diagnosis":"reference_target","diagnosis_label":"Reference target",
                          "reference_guidance":True,"estimated_time_cost_s":0.0,"diagnosis_confidence":1.0,"actionability":1.0,"issue_candidates":[],
                          "reference_brake_m":sec.get("start_m"),"reference_apex_m":sec.get("min_speed_m"),"reference_exit_m":sec.get("end_m"),
                          "reference_min_speed_kph":sec.get("min_speed_kph"),"reference_apex_gear":sec.get("apex_gear")}
        return out

    def _seed_external_reference(self, recorder) -> None:
        if getattr(recorder, "reference_mode", None) != "external":
            return
        reference = getattr(recorder, "external_reference", None)
        if not isinstance(reference, dict) or not (reference.get("_samples") or reference.get("sections")):
            return
        rid = id(reference)
        if self._seed_reference_id == rid:
            return
        if self._seed_reference_id is not None and self._seed_reference_id != rid:
            # Advice outcomes are reference-relative. Never carry solved/active
            # coaching claims across a reference switch inside the same session.
            self.advice_memory.reset()
        self._seed_reference_id = rid
        # Make PRE available from the first lap. Once a completed/current corner is
        # measured, normal diagnosis replaces this seed guidance corner-by-corner.
        self._advice = self._reference_seed_advice(reference)
        self._pre_spoken.clear()

    def _update_damage_state(self, state, now: float) -> None:
        player = getattr(state, "player", None)
        damage = getattr(player, "damage", None) if player is not None else None
        if damage is None:
            sig = (0, 0, False, False)
        else:
            wing = max(int(getattr(damage, "front_left_wing_percent", 0) or 0), int(getattr(damage, "front_right_wing_percent", 0) or 0))
            floor = int(getattr(damage, "floor_percent", 0) or 0)
            sig = (wing, floor, bool(getattr(damage, "engine_blown", False)), bool(getattr(damage, "engine_seized", False)))
        if sig != self._damage_signature:
            self._damage_signature = sig
            self._damage_changed_at = now
        wing, floor, blown, seized = sig
        self._damage_stable = (wing >= 20 or floor >= 20) and not blown and not seized and (now - self._damage_changed_at) >= 3.0

    @staticmethod
    def _damage_sensitive_message(message: EngineerMessage) -> bool:
        key = str(getattr(message, "key", "") or "")
        return any(key.endswith(":" + code) for code in ("minimum_speed_low", "exit_speed_low", "throttle_late", "throttle_ramp_slow"))

    @property
    def settings(self) -> CoachingSettings:
        return self.store.settings

    def reset_session(self) -> None:
        settings = self.store.settings
        self.__init__(self.store)
        self.store.settings = settings

    def set_feature(self, name: str, enabled: bool) -> tuple[bool, str]:
        mapping = {
            "POST": "post_corner", "PRE": "pre_corner", "LAP": "lap_summary",
            "POS": "positive_calls", "RACE": "race_coaching",
        }
        field = mapping.get(str(name).upper(), name)
        if field not in {"post_corner", "pre_corner", "lap_summary", "positive_calls", "race_coaching", "auto_reports", "progress_history"}:
            return False, f"Unknown coaching feature: {name}"
        self.store.set(**{field: bool(enabled)})
        return True, "Enabled" if enabled else "Disabled"

    def set_mode(self, mode: str) -> tuple[bool, str]:
        s = self.store.set(mode=str(mode).lower())
        return True, s.mode

    def set_verbosity(self, verbosity: str) -> tuple[bool, str]:
        s = self.store.set(verbosity=str(verbosity).lower())
        return True, s.verbosity

    def _effective(self, profile: str) -> dict[str, bool]:
        s = self.settings
        if s.mode == "silent_analysis":
            return {"post": False, "pre": False, "lap": False, "positive": False}
        post, pre, lap, positive = s.post_corner, s.pre_corner, s.lap_summary, s.positive_calls
        if s.mode == "race_engineer":
            pre = False; positive = False; post = post and _is_race(profile)
        elif s.mode == "performance_coach":
            # Full performance-coach mode keeps both proactive PRE reminders
            # and reactive POST feedback. Earlier builds accidentally disabled
            # PRE here, which made the named mode less capable than AUTO.
            pre = pre
        elif s.mode == "track_learning":
            pre = True; post = True
        elif s.mode == "qualifying":
            pre = False if profile == "race" else pre
        elif s.mode == "time_trial":
            pre = pre; post = post
        if _is_race(profile) and not s.race_coaching:
            post = pre = lap = positive = False
        return {"post": post, "pre": pre, "lap": lap, "positive": positive}

    def _update_radio_busy(self, messages, now: float) -> None:
        for m in messages or ():
            if not isinstance(m, EngineerMessage): continue
            # Routine S-mode is explicitly non-blocking. Driver-requested and
            # safety/strategy/information calls retain radio ownership.
            if m.key == "assist:s_mode":
                continue
            if m.key.startswith("coach:"):
                continue
            if m.key == "voice:response" or int(m.priority) <= int(Priority.INFORMATION) or m.key.startswith("assist:"):
                hold = 4.0 if int(m.priority) <= int(Priority.STRATEGY) else 2.5
                self._radio_busy_until = max(self._radio_busy_until, now + hold)

    def _reference_for_completed(self, recorder, latest):
        try:
            return recorder._reference(latest)
        except Exception:
            ref = recorder.current_reference_lap()
            if ref is latest or (isinstance(ref, dict) and ref.get("lap") == latest.get("lap")):
                prior = [x for x in recorder.completed[:-1] if isinstance(x, dict) and x.get("valid")]
                return min(prior, key=lambda x: x.get("lap_time_s", 1e12), default=None)
            return ref

    def _analyse_new_completed_lap(self, recorder, state, now: float, effective: dict[str, bool]) -> list[EngineerMessage]:
        completed = list(getattr(recorder, "completed", []) or ())
        if len(completed) <= self._last_completed_count:
            return []
        self._last_completed_count = len(completed)
        latest = completed[-1]
        lap_no = latest.get("lap") if isinstance(latest, dict) else None
        self._last_analysis_lap = lap_no if isinstance(lap_no, int) else self._last_analysis_lap
        if lap_quality(latest).get("eligible") is not True:
            if getattr(recorder, "reference_mode", None) == "external" and isinstance(getattr(recorder, "external_reference", None), dict):
                self._advice = self._reference_seed_advice(recorder.external_reference)
            else:
                self._advice = {}
            return []
        reference = self._reference_for_completed(recorder, latest)
        if not isinstance(reference, dict):
            return []
        # Imported/external references from older releases may not carry the
        # live-recorder anchor/sample metadata. Require the measured content,
        # but do not reject an otherwise valid reference solely for legacy
        # metadata omissions.
        ref_sections = reference.get("sections") or []
        ref_samples = reference.get("_samples") or {}
        if not _num(reference.get("lap_time_s")) or not (ref_sections or ref_samples):
            return []
        if reference.get("valid") is False or reference.get("lap_start_anchored") is False:
            return []
        pipeline = build_performance_pipeline(latest, reference)
        analyses = list(pipeline.get("corner_analyses") or [])
        self._distance_performance = pipeline.get("distance_model") or {"available": False}
        self._turn_performance = list(pipeline.get("turns") or [])

        priority = self.memory.ingest_lap(lap_no, analyses)
        self._last_priority = priority
        self.advice_memory.observe_lap(
            lap_no, analyses, priority.get("selected_focus") if isinstance(priority, dict) else None
        )
        self._potential = potential_summary(completed, reference)
        self._technique = session_technique_metrics(completed)
        self._racing_line = compare_racing_line(latest, reference)
        previous = self._advice
        self._previous_advice = previous
        measured = _primary_for_corner(analyses)
        # Best measured improvement is retained for the lap-end summary even when
        # positive radio acknowledgements are disabled.
        best_improvement = None
        for _cid, _old in previous.items():
            _code = str(_old.get("diagnosis") or "") if isinstance(_old, dict) else ""
            _old_cost = _issue_cost(_old, _code)
            _new = measured.get(_cid)
            _new_cost = _issue_cost(_new, _code)
            if _num(_old_cost):
                _gain = float(_old_cost) - (float(_new_cost) if _num(_new_cost) else 0.0)
                if _gain >= self.settings.positive_improvement_threshold_s:
                    _row = (_gain, _cid, _code)
                    if best_improvement is None or _row[0] > best_improvement[0]:
                        best_improvement = _row
        turn_targets={int(t["corner_id"]):t for t in self._turn_performance if isinstance(t,dict) and isinstance(t.get("corner_id"),int)}
        for cid,row in measured.items():
            target=turn_targets.get(cid,{})
            for key in ("reference_brake_m","reference_turn_in_m","reference_apex_m","reference_exit_m","reference_min_speed_kph","reference_apex_speed_kph","reference_exit_speed_kph","reference_apex_gear"):
                if target.get(key) is not None: row[key]=target.get(key)
        if getattr(recorder, "reference_mode", None) == "external":
            seeded = self._reference_seed_advice(reference)
            seeded.update(measured)
            self._advice = seeded
        else:
            self._advice = measured
        self._pre_spoken.clear()
        self.landmarks.learn_from_reference(_track_key(recorder, state), reference)

        messages: list[EngineerMessage] = []
        # Positive acknowledgement: only when a previously coached, loss-supported
        # issue materially improves or disappears on the next valid measured lap.
        if effective["positive"] and previous:
            improvements = []
            for cid, old in previous.items():
                code = str(old.get("diagnosis") or "")
                old_cost = _issue_cost(old, code)
                new = self._advice.get(cid)
                new_cost = _issue_cost(new, code)
                if _num(old_cost):
                    if new_cost is None:
                        improvements.append((float(old_cost), cid, code, "resolved"))
                    elif float(old_cost) - float(new_cost) >= self.settings.positive_improvement_threshold_s:
                        improvements.append((float(old_cost)-float(new_cost), cid, code, "improved"))
            if improvements:
                _, cid, _code, status = max(improvements)
                text = f"Turn {cid} improved. Keep that change." if status == "improved" else f"Turn {cid} is clean against the reference now."
                self._positive_pending = EngineerMessage(
                    key=f"coach:positive:{lap_no}:{cid}", priority=Priority.COACHING, text=text,
                    created_at=now, session_time_s=getattr(getattr(state, "session", None), "session_time_s", None),
                )

        if effective["lap"]:
            lap_time = latest.get("lap_time_s")
            ref_time = reference.get("lap_time_s")
            focus = priority.get("selected_focus") if isinstance(priority, dict) else None
            parts = []
            profile = _profile(recorder)
            if profile == "qualifying":
                prefix = "Qualifying lap"
            elif _is_race(profile):
                prefix = "Race lap"
            elif profile in {"time_trial", "time trial", "tt"}:
                prefix = "Time trial lap"
            elif profile in {"practice", "practice_1", "practice_2", "practice_3"}:
                prefix = "Practice lap"
            else:
                prefix = "Lap"
            if _num(lap_time):
                parts.append(f"{prefix} {lap_no}, {float(lap_time):.3f} seconds.")
            if _num(lap_time) and _num(ref_time):
                delta = float(lap_time)-float(ref_time)
                if abs(delta) >= self.settings.lap_summary_min_gap_s:
                    parts.append(f"{abs(delta):.3f} {'off' if delta > 0 else 'faster than'} the reference.")
            prev = next((x for x in reversed(completed[:-1]) if isinstance(x, dict) and lap_quality(x).get("eligible") and _num(x.get("lap_time_s"))), None)
            if prev is not None and _num(lap_time):
                pd = float(lap_time)-float(prev["lap_time_s"])
                if abs(pd) >= self.settings.lap_summary_min_gap_s:
                    parts.append(f"{abs(pd):.3f} {'slower' if pd > 0 else 'quicker'} than the previous valid lap.")
            ranked = priority.get("ranked_candidates") if isinstance(priority, dict) else None
            if isinstance(ranked, list) and ranked:
                top = ranked[0]
                if isinstance(top, dict) and top.get("corner_id") is not None:
                    cost = top.get("estimated_time_cost_s")
                    txt=f"Biggest measured opportunity Turn {top['corner_id']}: {str(top.get('issue_label') or 'focus').lower()}"
                    if _num(cost): txt += f", about {float(cost):.3f} seconds in that phase"
                    parts.append(txt + ".")
                if len(ranked) > 1 and isinstance(ranked[1], dict):
                    second=ranked[1]; second_cost=second.get("estimated_time_cost_s")
                    if _num(second_cost) and float(second_cost) >= 0.080:
                        parts.append(f"Next opportunity Turn {second.get('corner_id')}: {str(second.get('issue_label') or 'focus').lower()}, about {float(second_cost):.3f} seconds.")
            elif isinstance(focus, dict) and focus.get("corner_id") is not None:
                cid = focus["corner_id"]; label = str(focus.get("issue_label") or "focus")
                parts.append(f"Focus Turn {cid}: {label.lower()}.")
            if isinstance(focus, dict) and focus.get("corner_id") is not None and ranked:
                parts.append(f"Next-lap focus Turn {focus['corner_id']}: {str(focus.get('issue_label') or 'focus').lower()}.")
            if best_improvement is not None:
                _gain,_cid,_code=best_improvement
                parts.append(f"Best improvement Turn {_cid}, about {_gain:.3f} seconds recovered from the previous measured issue.")
            pot = potential_summary(completed, reference, anchor=latest)
            if _num(pot.get("potential_gain_s")) and float(pot["potential_gain_s"]) >= 0.080:
                parts.append(f"Observed potential is {float(pot['potential_gain_s']):.3f} faster than the current best.")
            if parts:
                self._lap_summary_pending = EngineerMessage(
                    key=f"coach:lap_summary:{lap_no}", priority=Priority.COACHING, text=" ".join(parts),
                    created_at=now, session_time_s=getattr(getattr(state, "session", None), "session_time_s", None),
                )
        return messages

    @staticmethod
    def _next_advice_window(advice: dict[int, dict[str, Any]], reference: dict[str, Any], d: float, speed_kph: float):
        if speed_kph <= 5.0:
            return None
        legacy={s.get("id"):s for s in PostCornerCoach._canonical_sections(reference)}
        best=None
        for cid,a in advice.items():
            target=a if isinstance(a,dict) else {}
            brake_m=target.get("reference_brake_m")
            if not _num(brake_m):
                sec=legacy.get(cid); brake_m=sec.get("start_m") if sec else None
            else:
                sec=legacy.get(cid) or {}
            if not _num(brake_m):
                brake_m=target.get("reference_turn_in_m") or target.get("reference_apex_m")
            if not _num(brake_m): continue
            distance=float(brake_m)-d
            if distance<=0: continue
            t=distance/(speed_kph/3.6)
            row=(t,distance,cid,a,sec)
            if best is None or t<best[0]: best=row
        return best

    @staticmethod
    def _pre_text(a: dict[str, Any], sec: dict[str, Any] | None, verbosity: str) -> str:
        sec=sec or {}; cid=a.get("corner_id"); code=str(a.get("diagnosis") or "")
        if a.get("reference_guidance") or code=="reference_target":
            targets=[]
            brake=a.get("reference_brake_m") if _num(a.get("reference_brake_m")) else sec.get("start_m")
            gear=a.get("reference_apex_gear") if a.get("reference_apex_gear") is not None else sec.get("apex_gear")
            speed=a.get("reference_min_speed_kph") if _num(a.get("reference_min_speed_kph")) else sec.get("min_speed_kph")
            if _num(brake): targets.append(f"reference brake point {float(brake):.0f} metres")
            if isinstance(gear,int) and gear>0: targets.append(f"gear {gear}")
            if _num(speed): targets.append(f"minimum about {float(speed):.0f} kph")
            detail=", ".join(targets) if targets else "match the reference line and inputs"
            return f"Turn {cid} coming up: {detail}."
        base=PostCornerCoach._spoken_text(a)
        if base.startswith(f"Turn {cid}: "): base=base[len(f"Turn {cid}: "):]
        extra=""
        if verbosity=="detailed":
            gear=a.get("reference_apex_gear") if a.get("reference_apex_gear") is not None else sec.get("apex_gear")
            speed=a.get("reference_min_speed_kph") if _num(a.get("reference_min_speed_kph")) else sec.get("min_speed_kph")
            targets=[]
            if isinstance(gear,int) and gear>0: targets.append(f"gear {gear}")
            if _num(speed): targets.append(f"reference minimum {float(speed):.0f} kph")
            if targets: extra=" "+", ".join(targets)+"."
        return f"Turn {cid} coming up: {base}{extra}".replace("..",".")

    def _safe_live(self, state, profile: str, now: float) -> tuple[bool, list[str]]:
        blockers = live_context_blockers(
            state, race_mode=_is_race(profile), traffic_gap_s=self.settings.traffic_gap_s,
            rear_traffic_gap_s=self.settings.rear_traffic_gap_s, now=now,
            stale_telemetry_s=self.settings.stale_telemetry_s, stale_lap_s=self.settings.stale_lap_s,
            allow_damage_coaching=bool(self.allow_damage_coaching),
        )
        # Moderate aero damage should not silence an entire race forever. After it
        # has been stable for a short period, allow technique coaching again, but
        # later suppress speed-outcome advice that the damaged car may distort.
        if self._damage_stable:
            blockers = [b for b in blockers if b != "significant_damage"]
        if now < self._radio_busy_until:
            blockers.append("radio_busy")
        player = getattr(state, "player", None)
        telem = getattr(player, "telemetry", None) if player is not None else None
        if telem is not None:
            if float(getattr(telem, "brake", 0.0) or 0.0) > 0.08: blockers.append("braking")
            if abs(float(getattr(telem, "steering", 0.0) or 0.0)) > 0.16: blockers.append("cornering")
        self._last_blockers = blockers
        return not blockers, blockers

    def _safe_pre(self, state, profile: str, now: float) -> tuple[bool, list[str]]:
        """PRE-specific safety gate.

        Race PRE guidance tolerates an invalid lap and stable moderate aero damage,
        but active close combat suppresses technique PRE so attack/defence workload
        owns the driver's attention.  A separate race-exit message covers the combat
        context.  We also suppress during stale telemetry, pause/pit/flag states,
        active radio ownership, braking, or meaningful steering input.
        """
        blockers = live_context_blockers(
            state, race_mode=_is_race(profile), traffic_gap_s=self.settings.traffic_gap_s,
            rear_traffic_gap_s=self.settings.rear_traffic_gap_s, now=now,
            stale_telemetry_s=self.settings.stale_telemetry_s, stale_lap_s=self.settings.stale_lap_s,
            allow_damage_coaching=bool(self.allow_damage_coaching),
        )
        if _is_race(profile):
            # V1.3.8.0: active attack/defence owns attention. Keep invalid-lap
            # tolerance for race coaching, but do NOT let corner technique PRE
            # compete with close-combat workload. A separate race-exit message is
            # generated by the unified arbitration layer.
            blockers = [b for b in blockers if b != "invalid_lap"]
        if self._damage_stable:
            blockers = [b for b in blockers if b != "significant_damage"]
        if now < self._radio_busy_until:
            blockers.append("radio_busy")
        player = getattr(state, "player", None)
        telem = getattr(player, "telemetry", None) if player is not None else None
        if telem is not None:
            if float(getattr(telem, "brake", 0.0) or 0.0) > 0.08:
                blockers.append("braking")
            if abs(float(getattr(telem, "steering", 0.0) or 0.0)) > 0.16:
                blockers.append("cornering")
        self._last_blockers = blockers
        return not blockers, blockers

    def _drain_low_priority(self, state, profile: str, now: float) -> list[EngineerMessage]:
        safe, _ = self._safe_live(state, profile, now)
        if not safe: return []
        if self._positive_pending is not None:
            m, self._positive_pending = self._positive_pending, None
            self._positive_count += 1
            return [m]
        if self._lap_summary_pending is not None:
            m, self._lap_summary_pending = self._lap_summary_pending, None
            self._lap_summary_count += 1
            return [m]
        return []

    def observe(self, recorder, state, now: float, generated_messages=(), *, suppress_pre_post: bool = False) -> list[EngineerMessage]:
        profile = _profile(recorder)
        effective = self._effective(profile)
        self._update_damage_state(state, now)
        if _is_race(profile):
            self._race_context = assess_race_context(state, traffic_gap_s=self.settings.traffic_gap_s, rear_gap_s=self.settings.rear_traffic_gap_s).to_dict()
        else:
            self._race_context = {"level":"not_race","technique_coaching_allowed":True,"reasons":[],"adaptations":[]}
        self._seed_external_reference(recorder)
        self._update_radio_busy(generated_messages, now)
        self._analyse_new_completed_lap(recorder, state, now, effective)

        player = getattr(state, "player", None)
        lap_state = getattr(player, "lap", None) if player is not None else None
        lap = getattr(lap_state, "current_lap", None) if lap_state is not None else None
        if isinstance(lap, int) and lap != self._last_lap:
            self._last_lap = lap; self._pre_spoken.clear(); self._pre_calls_this_lap = 0

        # V1.1 CORNER COACH owns all corner PRE/POST work.  When the receiver
        # suppresses legacy PRE/POST, keep only lightweight Race Engineer chatter.
        # Never load/scan the reference or derive physical turns on this packet path.
        if suppress_pre_post:
            safe, _ = self._safe_live(state, profile, now)
            if not safe:
                return []
            return self._drain_low_priority(state, profile, now)

        # Legacy PRE remains only for callers that explicitly use this coach
        # without CORNER COACH ownership.
        pre_safe, _ = self._safe_pre(state, profile, now)
        reference = recorder.current_reference_lap()
        configured_pre_limit = self.settings.pre_corner_max_calls_per_lap + (1 if self.settings.verbosity == "detailed" else 0)
        reference_turn_count = len(physical_turn_boundaries(reference, track_name=(reference or {}).get("track_name"))) if isinstance(reference, dict) else 0
        pre_limit = max(configured_pre_limit, reference_turn_count) if getattr(recorder, "reference_mode", None) == "external" else configured_pre_limit
        if pre_safe and effective["pre"] and self._advice and self._pre_calls_this_lap < pre_limit and player is not None and lap_state is not None:
            d = getattr(lap_state, "lap_distance_m", None)
            speed = getattr(getattr(player, "telemetry", None), "speed_kph", None)
            if _num(d) and _num(speed) and reference:
                candidate = self._next_advice_window(
                    {cid:a for cid,a in self._advice.items() if cid not in self._pre_spoken},
                    reference, float(d), float(speed),
                )
                if candidate is not None:
                    ttb, _distance, cid, a, sec = candidate
                    # External-reference race coaching favors coverage.  A transient
                    # blocker may clear late in the approach, so retain a wider
                    # delivery window instead of permanently skipping the turn.
                    external_race = _is_race(profile) and getattr(recorder, "reference_mode", None) == "external"
                    pre_min = 1.5 if external_race else self.settings.pre_corner_min_s
                    pre_max = max(8.0, self.settings.pre_corner_max_s) if external_race else self.settings.pre_corner_max_s
                    track_key = _track_key(recorder, state)
                    distance_override = self.landmarks.pre_call_distance_override(track_key, cid)
                    distance_ready = distance_override is None or float(_distance) <= float(distance_override)
                    if pre_min <= ttb <= pre_max and distance_ready:
                        self._pre_spoken.add(cid); self._pre_calls_this_lap += 1; self._pre_generated += 1; self._pre_spoken_count += 1
                        return [EngineerMessage(
                            key=f"coach:pre:{lap}:{cid}:{a.get('diagnosis')}", priority=Priority.COACHING,
                            text=self._pre_text(a, sec, self.settings.verbosity), created_at=now,
                            session_time_s=getattr(getattr(state, "session", None), "session_time_s", None),
                        )]

        # Only after PRE had its chance may lower-value coaching chatter use the
        # normal safety gate.
        safe, _ = self._safe_live(state, profile, now)
        if not safe:
            return []
        # This also leaves a pending lap summary available to resume later if PRE
        # interrupts it at the TTS layer.
        low = self._drain_low_priority(state, profile, now)
        if low:
            return low

        if effective["post"]:
            race = _is_race(profile)
            if race != self._post_profile_race:
                self.post = self._new_post(self.settings, race=race)
                self._post_profile_race = race
            out = self.post.observe(recorder, state, now)
            if self._damage_stable and out:
                out = [m for m in out if not self._damage_sensitive_message(m)]
            return out
        return []

    def status(self) -> dict[str, Any]:
        eff = self._effective("unknown")
        return {
            "settings": self.settings.to_dict(),
            "effective_unknown_profile": eff,
            "last_analysis_lap": self._last_analysis_lap,
            "last_priority": self._last_priority,
            "advice_corner_ids": sorted(self._advice),
            "advice": {str(k): v for k, v in self._advice.items()},
            "potential": self._potential,
            "technique_metrics": self._technique,
            "racing_line": self._racing_line,
            "distance_performance": {
                "available": bool(self._distance_performance.get("available")),
                "coverage_start_m": self._distance_performance.get("coverage_start_m"),
                "coverage_end_m": self._distance_performance.get("coverage_end_m"),
                "full_track_net_delta_s": self._distance_performance.get("full_track_net_delta_s"),
                "partition_net_delta_s": self._distance_performance.get("partition_net_delta_s"),
                "reconciliation_error_s": self._distance_performance.get("reconciliation_error_s"),
                "step_m": self._distance_performance.get("step_m"),
                "gain_loss_zones": list(self._distance_performance.get("gain_loss_zones") or ()),
                "segments": list(self._distance_performance.get("segments") or ()),
            },
            "turn_performance": list(self._turn_performance),
            "pre_spoken_corner_ids": sorted(self._pre_spoken),
            "radio_busy_until": self._radio_busy_until,
            "last_blockers": list(self._last_blockers),
            "damage_stable": self._damage_stable,
            "damage_signature": self._damage_signature,
            "race_context": dict(self._race_context),
            "pre_generated_count": self._pre_generated,
            "pre_spoken_count": self._pre_spoken_count,
            "lap_summary_count": self._lap_summary_count,
            "positive_count": self._positive_count,
            "post_corner": self.post.status(),
            "session_patterns": [x.to_dict() for x in self.memory.patterns()[:20]],
            "advice_memory": self.advice_memory.summary(),
            "coaching_focus": self.advice_memory.current_focus(),
        }
