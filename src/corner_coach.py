"""V1.1.0.0 CORNER COACH hybrid runtime.

This engine is deliberately additive to the older coaching suite.  It owns the
new CoachingZone model, live distance synchronization, deterministic zone
attribution, PRE/POST wording and the data consumed by the new overlay.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import asdict
import math
from typing import Any

from .corner_coach_models import CoachingZone, Diagnosis, ReferenceTrace, to_dict
from .corner_coach_validation import CornerCoachValidationRecorder
# Compatibility export for older tests/tools. V1.1.0.3 never calls this
# whole-lap builder from the packet-critical path (legacy include_channel_deltas=False path removed).
from .distance_performance import build_distance_performance_model
from .engineer.models import EngineerMessage, Priority, estimate_speech_duration_s
from .reference_model import compile_reference_model, compiled_model_for_source, load_reference_model, apply_persisted_track_geometry
from .performance_scoring import build_live_corner_score_from_diagnosis, score_grade, ScoreStatus
from .lap_stint_intelligence import LivePerformanceAccumulator


def _num(v:Any)->bool:
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v))


def _sample_rows(lap:dict|None):
    rows=[]
    for raw_d,row in ((lap or {}).get("_samples") or {}).items():
        try:d=float(raw_d)
        except (TypeError,ValueError):
            d=row.get("d") if isinstance(row,dict) else getattr(row,"d",None)
        if not _num(d):continue
        rows.append((float(d),row))
    return sorted(rows,key=lambda x:x[0])


def _value(row,key):
    return row.get(key) if isinstance(row,dict) else getattr(row,key,None)


def _first_event(rows,start,end,key,threshold,*,after=None,absolute=False):
    lo=max(start,float(after)) if _num(after) else start
    for d,row in rows:
        if d<lo:continue
        if d>end:break
        v=_value(row,key)
        if _num(v) and (abs(float(v)) if absolute else float(v))>=threshold:
            return d
    return None


def _last_event(rows,start,end,key,threshold,*,absolute=False):
    found=None
    for d,row in rows:
        if d<start:continue
        if d>end:break
        v=_value(row,key)
        if _num(v) and (abs(float(v)) if absolute else float(v))>=threshold:
            found=d
    return found


def _peak(rows,start,end,key,*,absolute=False):
    values=[]
    for d,row in rows:
        if d<start:continue
        if d>end:break
        v=_value(row,key)
        if _num(v):values.append((abs(float(v)) if absolute else float(v),d))
    return max(values,key=lambda x:x[0]) if values else (None,None)


def _min_speed(rows,start,end):
    vals=[(float(_value(r,"speed")),d) for d,r in rows if start<=d<=end and _num(_value(r,"speed"))]
    return min(vals,key=lambda x:x[0]) if vals else (None,None)


def _speed_at(rows,target,tol=12.5):
    vals=[(abs(d-target),_value(r,"speed")) for d,r in rows if _num(_value(r,"speed"))]
    if not vals:return None
    dist,v=min(vals,key=lambda x:x[0])
    return float(v) if dist<=tol and _num(v) else None


def _interp_delta(points,d):
    if not points or not _num(d):return None
    ds=[float(p["distance_m"]) for p in points]
    i=bisect_left(ds,float(d))
    if i<=0:return float(points[0]["delta_s"])
    if i>=len(points):return float(points[-1]["delta_s"])
    a,b=points[i-1],points[i]; d0,d1=float(a["distance_m"]),float(b["distance_m"])
    if d1<=d0:return float(a["delta_s"])
    f=(float(d)-d0)/(d1-d0)
    return float(a["delta_s"])+(float(b["delta_s"])-float(a["delta_s"]))*f


def _phase_loss(points,a,b):
    da=_interp_delta(points,a); db=_interp_delta(points,b)
    return (db-da) if _num(da) and _num(db) else None


def _spoken_label(zone:CoachingZone)->str:
    ids=zone.corner_ids
    if not ids:return "Corner"
    if len(ids)==1:return f"Turn {ids[0]}"
    return f"T{ids[0]} through {ids[-1]}"


class CornerCoachEngine:
    """Authoritative CoachingZone runtime using one live lap-distance source."""
    PRE_MIN_S=1.25
    PRE_MAX_S=12.5
    PRE_MAX_DISTANCE_M=525.0
    LOSS_DEADBAND_S=0.030
    POST_MIN_AFTER_M=8.0
    POST_MAX_AFTER_M=160.0
    # V1.1.0.15 real-time radio budget. PRE must FINISH before its target; POST
    # may use only the airtime left after reserving the next PRE plus this gap.
    SPEECH_FINISH_MARGIN_S=0.20
    PRE_POST_GAP_S=0.18
    POST_MIN_SPEAKABLE_S=0.85
    # Full distance-model reconstruction is intentionally decoupled from the
    # telemetry packet rate. Live bars/position stay source-rate, while expensive
    # whole-lap comparison refreshes only after meaningful distance/time progress.
    PERF_REFRESH_DISTANCE_M=8.0
    PERF_REFRESH_INTERVAL_S=0.20

    def __init__(self):
        # V1.7.0.0 SPEED COACH parent. Keep ``enabled`` as the parent master for backward compatibility.
        self.enabled=True
        self.corner_enabled=True
        self.straight_enabled=False
        self.straight_voice_enabled=True
        self.voice_enabled=True
        self.pre_enabled=True
        self.post_enabled=True
        self.gain_loss_enabled=True
        self.gain_loss_voice_enabled=False
        self._reference_id=None
        self.reference_model:ReferenceTrace|None=None
        self._track_geometry_refresh_lap:int|None=None
        self._pre_spoken:set[str]=set()
        self._post_spoken:set[str]=set()
        self._lap=None
        # True only after the current numbered lap has crossed a clean S/F
        # timing anchor. F1 Time Trial can expose lap 1 while the car is still
        # on the pre-line rolling-start segment; that segment must not be treated
        # as a completed lap when distance wraps to zero.
        self._lap_started_clean=False
        # Sticky validity for the logical lap currently owned by CORNER COACH.
        # At an EA lap-number transition, lap_state already belongs to the NEW lap;
        # using it to finalize the old lap can incorrectly mark Lap 1 invalid.
        self._lap_valid=True
        self._last_diagnosis:dict[str,Any]|None=None
        self._diagnoses:dict[str,dict[str,Any]]={}
        self._distance_model={"available":False}
        self._zone_attribution={"available":False,"zones":[],"straights":[],"segments":[],"reconciliation_error_s":None}
        self._active_zone_id=None
        self._active_phase=None
        self._last_perf_distance=None
        self._last_perf_update_at=0.0
        self._current_lap_cache=None
        self._reference_distances=()
        self._reference_samples=()
        self._zones_payload=()
        self._corners_payload=()
        self._events_payload=()
        self._trusted_turn_metrics_payload=()
        self._performance_boundaries=()
        self._distance_status_payload={"available":False}
        # V1.1.0.3: the packet-critical path is incremental only.  No whole-lap
        # interpolation / attribution rebuild is allowed from observe().
        self._live_points:list[dict[str,Any]]=[]
        self._live_point_distances:list[float]=[]
        self._live_gain_loss:list[dict[str,Any]]=[]
        self._live_segments:list[dict[str,Any]]=[]
        self._live_segment_done:set[tuple[str,int]]=set()
        self._live_zone_rows:list[dict[str,Any]]=[]
        self._live_zone_done:set[str]=set()
        self._last_lap_time_s:float|None=None
        self._last_distance_seen:float|None=None
        self._first_delta_s:float|None=None
        self._last_delta_s:float|None=None
        # V1.1.0.12: asynchronous deterministic validation trace. Disk I/O never
        # runs on the telemetry packet thread; the trace records zone/corner
        # transitions, PRE/POST eligibility, generated radio and actual audio.
        self.validation=CornerCoachValidationRecorder()
        self._validation_prev_zone_id=None
        self._validation_prev_phase=None
        self._validation_prev_corner_id=None
        self._validation_pre_missed:set[str]=set()
        # Runtime toggle bookkeeping. Zones completed while PRE/POST/VOICE is
        # disabled are intentionally not back-filled when that feature is
        # re-enabled later in the same lap. This keeps toggle semantics local
        # to the point at which the user changed the control.
        self._pre_not_applicable:set[str]=set()
        self._post_not_applicable:set[str]=set()
        self._gain_loss_voice_spoken:set[str]=set()
        self._gain_loss_voice_not_applicable:set[str]=set()
        self._straight_spoken:set[int]=set()
        self._straight_pending:list[dict[str,Any]]=[]
        self._straight_last_diagnosis:dict[str,Any]|None=None
        # V2.0.1 visual-only live corner intelligence. This never owns speech.
        self._live_corner_result:dict[str,Any]|None=None
        self._v2_scored:set[str]=set()
        # V2.0.2 bounded lap/stint intelligence; consumes V2.0.1 corner results only.
        self._v202_accumulator=LivePerformanceAccumulator()
        self._v202_lap_result:dict[str,Any]|None=None
        self.coaching_mode:str="auto"
        self._straight_diagnoses:dict[int,dict[str,Any]]={}
        self._straight_repeat_signature:dict[int,tuple[str,float|None]]={}
        self._straight_repeat_count:dict[int,int]={}
        self._validation_control_state:tuple[bool,bool,bool,bool,bool]|None=None
        self._validation_run_key=None
        # V1.1.0.13: PRE for T1 on a flying lap is scheduled on the previous
        # lap's final straight. Carry only those already-spoken next-lap zones
        # across the S/F transition so they are neither duplicated nor marked
        # as missed after the line.
        self._next_lap_pre_spoken:set[str]=set()
        # Some EA race sessions hold current_lap at the scheduled final lap even
        # after the chequered flag while lap distance wraps to zero. These guards
        # stop post-finish T1/T2 from being appended to the completed final lap.
        self._awaiting_lap_increment_from:int|None=None
        self._finished_session_hold_uid:Any=None
        self._last_observed_distance:float|None=None
        self._last_observed_session_time:float|None=None
        self._compromised_lap:int|None=None
        # Deterministic game-time model of the CORNER COACH speech channel.
        # This prevents generation from flooding TTS with POST calls that can
        # only become stale while an earlier cue is still using the channel.
        self._speech_reserved_until_session_s:float=0.0
        self._speech_reserved_kind:str|None=None
        self._speech_reserved_zone:str|None=None
        # V1.3.0.1: explicit user override allowing coaching analysis on damaged-car laps.
        # Damage remains recorded; this only changes coaching eligibility.
        self.damage_coaching_enabled:bool=False
        self._damage_coaching_blocked:bool=False
        # V1.5.0.0 long-session coaching refinement.
        self._pre_last_block_reason:dict[str,str]={}
        self._pre_block_counts:dict[str,int]={}
        self._post_repeat_signature:dict[str,tuple[str|None,float|None]]={}
        self._post_repeat_count:dict[str,int]={}
        self._was_in_pit_lane:bool=False
        self._outlap_lap:int|None=None


    def reset_session(self):
        """Clear per-session runtime state while preserving user controls and trace writer."""
        controls=(self.enabled,self.corner_enabled,self.straight_enabled,self.straight_voice_enabled,self.voice_enabled,self.pre_enabled,self.post_enabled,self.gain_loss_enabled,self.gain_loss_voice_enabled,self.damage_coaching_enabled)
        validation=self.validation
        fresh=type(self)()
        fresh.validation=validation
        self.__dict__.update(fresh.__dict__)
        (self.enabled,self.corner_enabled,self.straight_enabled,self.straight_voice_enabled,self.voice_enabled,self.pre_enabled,self.post_enabled,self.gain_loss_enabled,self.gain_loss_voice_enabled,self.damage_coaching_enabled)=controls

    def set_feature(self,feature:str,enabled:bool):
        key=str(feature).upper().strip()
        if key in {"SPEED","SPEED_COACH","SC"}:self.enabled=bool(enabled)
        elif key in {"CORNER","CORNER_COACH","CC"}:
            previous=bool(self.corner_enabled);self.corner_enabled=bool(enabled)
            if self.corner_enabled and not previous and _num(self._last_distance_seen):
                d=float(self._last_distance_seen)
                for z in (self.reference_model.coaching_zones if self.reference_model is not None else ()):
                    if self._pre_target_m(z)<=d:self._pre_not_applicable.add(z.zone_id)
                    if float(z.end_m)<=d:self._post_not_applicable.add(z.zone_id)
        elif key in {"STRAIGHT","STRAIGHT_LINE","STRAIGHT_LINE_COACH","SLC"}:
            previous=bool(self.straight_enabled);self.straight_enabled=bool(enabled)
            if not self.straight_enabled:
                self._straight_pending.clear()
            elif not previous:
                # Start from now. Completed straights while OFF remain visual history only.
                self._straight_pending.clear()
                self._straight_spoken.update(int(x.get("number",0)) for x in self._live_segments if x.get("segment_kind")=="straight" and x.get("complete"))
        elif key in {"STRAIGHTVOICE","STRAIGHT_VOICE","SLCVOICE"}:
            previous=bool(self.straight_voice_enabled);self.straight_voice_enabled=bool(enabled)
            if not self.straight_voice_enabled:
                self._straight_pending.clear()
            elif not previous:
                self._straight_pending.clear()
                self._straight_spoken.update(int(x.get("number",0)) for x in self._live_segments if x.get("segment_kind")=="straight" and x.get("complete"))
        elif key in {"VOICE","CORNER_VOICE","CCVOICE"}:self.voice_enabled=bool(enabled)
        elif key in {"PRE","CORNER_PRE"}:self.pre_enabled=bool(enabled)
        elif key in {"POST","CORNER_POST"}:
            self.post_enabled=bool(enabled)
            # V1.2.0.3: POST and G/L VOICE are two post-zone speech styles.
            # They are intentionally mutually exclusive to avoid duplicate
            # feedback and wasted radio airtime. The most recently enabled
            # style wins; MAP G/L remains completely independent.
            if enabled:
                self.gain_loss_voice_enabled=False
        elif key in {"GAINLOSS","GAIN_LOSS","GAIN/LOSS","MAP_GAINLOSS","MAP_G/L"}:self.gain_loss_enabled=bool(enabled)
        elif key in {"GAINLOSSVOICE","GAIN_LOSS_VOICE","G/L_VOICE","GLVOICE"}:
            self.gain_loss_voice_enabled=bool(enabled)
            if enabled:
                self.post_enabled=False
        elif key in {"DMGCOACH","DAMAGE_COACH","DAMAGECOACH"}:
            self.damage_coaching_enabled=bool(enabled)
        else:return False,"Unknown SPEED COACH feature"
        return True,"Enabled" if enabled else "Disabled"

    def feature_states(self):
        """Legacy CORNER COACH effective-state contract.

        V1.7 keeps this exact historical shape for third-party/tests that compare
        it directly. Runtime Speed Coach consumers use ``speed_coach_feature_states``.
        """
        corner=bool(self.enabled) and bool(self.corner_enabled)
        return {
            "CORNER":corner,
            "CCVOICE":corner and bool(self.voice_enabled),
            "CCPRE":corner and bool(self.pre_enabled),
            "CCPOST":corner and bool(self.post_enabled),
            "GAINLOSS":corner and bool(self.gain_loss_enabled),
            "GAINLOSSVOICE":corner and bool(self.voice_enabled) and bool(self.gain_loss_voice_enabled),
        }

    def speed_coach_feature_states(self):
        """V1.7 parent/child effective states used by the live runtime/UI."""
        master=bool(self.enabled)
        corner=master and bool(self.corner_enabled)
        straight=master and bool(self.straight_enabled)
        return {
            "SPEED":master,"CORNER":corner,"STRAIGHT":straight,
            "CCVOICE":corner and bool(self.voice_enabled),"CCPRE":corner and bool(self.pre_enabled),"CCPOST":corner and bool(self.post_enabled),
            "SLVOICE":straight and bool(self.voice_enabled) and bool(self.straight_voice_enabled),
            "GAINLOSS":master and bool(self.gain_loss_enabled),"GAINLOSSVOICE":master and bool(self.voice_enabled) and bool(self.gain_loss_voice_enabled),
        }

    def preference_states(self):
        """Legacy V1.1/V1.2 corner-control preference contract.

        Keep the exact historical key set because older UI/tests/integrations may
        compare this mapping directly. New Speed Coach child preferences live in
        ``speed_coach_preference_states``.
        """
        return {"CCVOICE":bool(self.voice_enabled),"CCPRE":bool(self.pre_enabled),"CCPOST":bool(self.post_enabled),"GAINLOSS":bool(self.gain_loss_enabled),"GAINLOSSVOICE":bool(self.gain_loss_voice_enabled)}

    def speed_coach_preference_states(self):
        return {"CORNER":bool(self.corner_enabled),"STRAIGHT":bool(self.straight_enabled),"SLVOICE":bool(self.straight_voice_enabled),**self.preference_states()}

    def _ensure_reference(self,reference:dict|None,track_name:str|None=None,metadata:dict|None=None):
        if not isinstance(reference,dict):
            self.reference_model=None;self._reference_id=None;return None
        metadata=dict(metadata or {})
        source_file=metadata.get("source_file")
        rid=(id(reference),str(track_name or reference.get("track_name") or "").upper(),str(source_file or ""))
        if rid==self._reference_id and self.reference_model is not None:
            return self.reference_model
        model=None
        # Permanent per-track compiled references are preferred during normal
        # runtime. Raw rival JSON remains the rebuild/source artifact only.
        compiled=compiled_model_for_source(source_file)
        if compiled is not None:
            try:
                candidate=load_reference_model(compiled)
                expected=str(track_name or reference.get("track_name") or candidate.track_name).upper()
                if not expected or candidate.track_name==expected:
                    model=candidate
            except (OSError,ValueError,TypeError,KeyError):
                model=None
        if model is None:
            try:
                compile_meta={"track_length_m":reference.get("track_length_m"),**metadata}
                source=str(compile_meta.get("source") or reference.get("source") or "").upper()
                trace_mode=str(reference.get("reference_trace_mode") or compile_meta.get("reference_trace_mode") or "").lower()
                strict_rival=source=="EA_F1_TIME_TRIAL_RIVAL" or trace_mode=="rival_pace"
                model=compile_reference_model(reference,compile_meta,track_name=track_name or reference.get("track_name"),require_quality=strict_rival)
            except Exception:
                model=None
        self.reference_model=model
        self._reference_id=rid
        self._pre_spoken.clear();self._post_spoken.clear();self._gain_loss_voice_spoken.clear();self._gain_loss_voice_not_applicable.clear();self._diagnoses.clear();self._last_diagnosis=None
        self._last_perf_distance=None;self._last_perf_update_at=0.0;self._current_lap_cache=None
        self._track_geometry_refresh_lap=None
        self._reset_live_performance()
        self._validation_prev_zone_id=None;self._validation_prev_phase=None;self._validation_prev_corner_id=None;self._validation_pre_missed=set()
        self._pre_not_applicable.clear();self._post_not_applicable.clear();self._validation_control_state=None
        self._next_lap_pre_spoken.clear();self._awaiting_lap_increment_from=None
        self._pre_last_block_reason.clear();self._pre_block_counts.clear();self._post_repeat_signature.clear();self._post_repeat_count.clear()
        self._finished_session_hold_uid=None;self._last_observed_distance=None
        if model is not None:
            self._reference_samples=tuple(model.samples)
            self._reference_distances=tuple(float(r.get("d",0.0)) for r in self._reference_samples)
            self._zones_payload=tuple(to_dict(z) for z in model.coaching_zones)
            self._corners_payload=tuple(to_dict(c) for c in model.physical_corners)
            self._events_payload=tuple(to_dict(e) for e in model.driving_events)
            trusted_turn_metrics=[]
            for c in model.physical_corners:
                start=float(c.start_m);end=float(c.end_m)
                speed_rows=[r for r in self._reference_samples if start<=float(r.get("d",-1.0))<=end and _num(r.get("speed"))]
                min_row=min(speed_rows,key=lambda r:float(r.get("speed"))) if speed_rows else None
                trusted_turn_metrics.append({
                    "corner_id":int(c.corner_id),"start_m":start,"end_m":end,
                    "min_speed_m":(float(min_row.get("d")) if min_row is not None else None),
                    "min_speed_kph":(float(min_row.get("speed")) if min_row is not None else None),
                    "exit_speed_kph":self._reference_value_at(end,"speed"),
                    "entry_speed_kph":self._reference_value_at(start,"speed"),
                })
            self._trusted_turn_metrics_payload=tuple(trusted_turn_metrics)
            # Build physical performance boundaries once per compiled reference.
            # The generic distance engine otherwise rediscovers the same geometry
            # every live refresh, which was a major V1.1 CPU regression.
            corners=tuple(sorted(model.physical_corners,key=lambda c:float(c.apex_m)))
            apexes=[float(c.apex_m) for c in corners]
            boundaries=[]
            for i,c in enumerate(corners):
                own_lo=0.0 if i==0 else (apexes[i-1]+apexes[i])*0.5
                own_hi=float(model.track_length_m) if i==len(corners)-1 else (apexes[i]+apexes[i+1])*0.5
                zone=next((z for z in model.coaching_zones if c.corner_id in z.corner_ids),None)
                brake=(zone.brake_start_m if zone is not None and zone.corner_ids and zone.corner_ids[0]==c.corner_id and _num(zone.brake_start_m) else c.start_m)
                boundaries.append({
                    "corner_id":int(c.corner_id),"label":str(c.label or f"T{c.corner_id}"),
                    "ownership_start_m":float(own_lo),"ownership_end_m":float(own_hi),
                    "start_m":float(c.start_m),"brake_m":float(brake),
                    "turn_in_m":float(c.start_m+(c.apex_m-c.start_m)*0.5),
                    "apex_m":float(c.apex_m),"end_m":float(c.end_m),
                    "turn_direction":c.direction,"physical_geometry":True,"physical_source":"compiled_reference_model",
                })
            self._performance_boundaries=tuple(boundaries)
        else:
            self._reference_samples=();self._reference_distances=();self._zones_payload=();self._corners_payload=();self._events_payload=();self._trusted_turn_metrics_payload=();self._performance_boundaries=()
        return self.reference_model

    @staticmethod
    def _current_lap(recorder,state):
        try:
            lightweight=getattr(recorder,"current_lap_trace_snapshot",None)
            if callable(lightweight):
                return lightweight(state)
            return recorder.current_lap_snapshot(state)
        except Exception:
            return None

    @staticmethod
    def _zone_for_distance(zones,d):
        if not _num(d):return None
        x=float(d)
        for z in zones:
            if z.approach_start_m<=x<=z.end_m:
                return z
        return None

    @staticmethod
    def _next_zone(zones,d):
        if not _num(d):return None
        x=float(d)
        future=[z for z in zones if z.approach_start_m>x]
        return min(future,key=lambda z:z.approach_start_m) if future else None

    @staticmethod
    def _pre_target_m(zone:CoachingZone)->float:
        """Return a PRE target that is never later than physical corner entry."""
        if _num(zone.brake_start_m):
            return min(float(zone.brake_start_m),float(zone.start_m))
        return float(zone.start_m)

    @staticmethod
    def _has_next_lap(session,lap:int)->bool:
        if getattr(session,"ended",False) is True:
            return False
        total=getattr(session,"total_laps",None)
        if isinstance(total,int) and total>0 and int(lap)>=total:
            return False
        return True

    def _target_eta_s(self, model:ReferenceTrace, current_d:float, target_d:float, speed_kph:Any, *, wrap:bool=False) -> float | None:
        """Conservative seconds until a distance target using live and clean pace clocks."""
        if not (_num(current_d) and _num(target_d)):
            return None
        length=float(model.track_length_m)
        ahead=(length-float(current_d)+float(target_d)) if wrap else (float(target_d)-float(current_d))
        if ahead < 0:
            return None
        estimates=[]
        if _num(speed_kph) and float(speed_kph)>5.0:
            estimates.append(ahead/(float(speed_kph)/3.6))
        now_t=self._reference_value_at(float(current_d),"t")
        target_t=self._reference_value_at(float(target_d),"t")
        if _num(now_t) and _num(target_t) and _num(model.lap_time_s):
            ref_eta=((float(model.lap_time_s)-float(now_t))+float(target_t)) if wrap else (float(target_t)-float(now_t))
            if ref_eta>=0:
                estimates.append(ref_eta)
        return min(estimates) if estimates else None

    def _next_pre_context(self, model:ReferenceTrace, zones, current_zone:CoachingZone, current_d:float, speed_kph:Any, session, lap:Any):
        """Return the next *pending* PRE target, wrapping at S/F when required.

        V1.1.0.14 always reserved airtime for the numerically next zone even when
        that zone's PRE had already been emitted.  That suppressed valid POSTs.
        Search forward until we find a PRE that is genuinely still pending.
        """
        # POST-only mode must never reserve airtime for a PRE that the user has
        # explicitly disabled. The same applies while CORNER COACH voice is off.
        if not self.voice_enabled or not self.pre_enabled:
            return None
        ordered=list(zones)
        try:
            idx=next(i for i,z in enumerate(ordered) if z.zone_id==current_zone.zone_id)
        except StopIteration:
            return None

        candidates=[]
        for nxt in ordered[idx+1:]:
            if nxt.zone_id in self._pre_spoken or nxt.zone_id in self._pre_not_applicable:
                continue
            target=self._pre_target_m(nxt)
            if target <= float(current_d):
                continue
            candidates.append((nxt,target,lap,False))
            break

        if not candidates and isinstance(lap,int) and self._has_next_lap(session,lap):
            for nxt in ordered:
                if nxt.zone_id in self._next_lap_pre_spoken:
                    continue
                target=self._pre_target_m(nxt)
                candidates.append((nxt,target,lap+1,True))
                break

        if not candidates:
            return None
        nxt,target,target_lap,wrap=candidates[0]
        eta=self._target_eta_s(model,float(current_d),target,speed_kph,wrap=wrap)
        if not _num(eta):
            return None
        length=float(model.track_length_m)
        ahead=(length-float(current_d)+target) if wrap else (target-float(current_d))
        pace_only=bool((model.quality or {}).get("input_telemetry_trusted") is False)
        pre_short=self._pre_text_compact(nxt,max(0.0,ahead),pace_only=pace_only)
        # Reserve the compact cue, because compact PRE is the real-time contract.
        # Full PRE is optional enrichment only when there is abundant headroom.
        pre_duration=estimate_speech_duration_s(pre_short)
        return {"zone":nxt,"target_m":target,"target_lap":target_lap,"wrap":wrap,"eta_s":float(eta),"distance_ahead_m":max(0.0,ahead),"reserved_pre_s":pre_duration+self.SPEECH_FINISH_MARGIN_S}

    def _sync_runtime_feature_state(self, zones, lap:Any, distance_m:Any, session_time_s:Any) -> None:
        """Apply PRE/POST/VOICE toggle changes at the exact live position.

        A feature enabled mid-lap starts from *now*; it must not manufacture
        missed/expired events for corners that passed while it was disabled.
        A feature disabled mid-message also releases the deterministic channel
        reservation for that message family so the other coach mode can proceed.
        """
        current=(bool(self.voice_enabled),bool(self.pre_enabled),bool(self.post_enabled),bool(self.gain_loss_enabled),bool(self.gain_loss_voice_enabled))
        previous=self._validation_control_state
        if previous is None:
            self._validation_control_state=current
            return
        if current==previous:
            return
        voice_prev,pre_prev,post_prev,gain_prev,gain_voice_prev=previous
        voice_now,pre_now,post_now,gain_now,gain_voice_now=current
        d=float(distance_m) if _num(distance_m) else None

        # Re-enabling voice or PRE applies only to targets still ahead.
        pre_became_active=(pre_now and not pre_prev) or (voice_now and not voice_prev and pre_now)
        if pre_became_active and d is not None:
            for z in zones:
                if self._pre_target_m(z) <= d:
                    self._pre_not_applicable.add(z.zone_id)

        # Re-enabling voice or POST applies only to zones not yet completed.
        post_became_active=(post_now and not post_prev) or (voice_now and not voice_prev and post_now)
        if post_became_active and d is not None:
            for z in zones:
                if float(z.end_m) <= d:
                    self._post_not_applicable.add(z.zone_id)

        # G/L voice starts from the current position too; do not back-fill zones
        # that were already completed while this independent voice mode was OFF.
        gain_voice_became_active=(gain_voice_now and not gain_voice_prev) or (voice_now and not voice_prev and gain_voice_now)
        if gain_voice_became_active and d is not None:
            for z in zones:
                if float(z.end_m) <= d:
                    self._gain_loss_voice_not_applicable.add(z.zone_id)

        # Prefix gating in TTS removes disabled queued messages. Mirror that in
        # the replay/game-time reservation model so an obsolete PRE/POST cannot
        # continue blocking the other mode after the user turns it off.
        if (not voice_now) or (pre_prev and not pre_now):
            if self._speech_reserved_kind=="PRE":
                self._speech_reserved_until_session_s=float(session_time_s) if _num(session_time_s) else 0.0
                self._speech_reserved_kind=None;self._speech_reserved_zone=None
        if (not voice_now) or (post_prev and not post_now):
            if self._speech_reserved_kind=="POST":
                self._speech_reserved_until_session_s=float(session_time_s) if _num(session_time_s) else 0.0
                self._speech_reserved_kind=None;self._speech_reserved_zone=None
        if (not voice_now) or (gain_voice_prev and not gain_voice_now):
            if self._speech_reserved_kind=="GAINLOSS":
                self._speech_reserved_until_session_s=float(session_time_s) if _num(session_time_s) else 0.0
                self._speech_reserved_kind=None;self._speech_reserved_zone=None

        self._validation_control_state=current
        self.validation.state_transition(
            "coach_config_change",lap=lap,distance_m=distance_m,session_time_s=session_time_s,
            voice_enabled=voice_now,pre_enabled=pre_now,post_enabled=post_now,gain_loss_enabled=gain_now,gain_loss_voice_enabled=gain_voice_now,
            previous_voice_enabled=voice_prev,previous_pre_enabled=pre_prev,
            previous_post_enabled=post_prev,previous_gain_loss_enabled=gain_prev,previous_gain_loss_voice_enabled=gain_voice_prev,
            pre_not_applicable=sorted(self._pre_not_applicable),
            post_not_applicable=sorted(self._post_not_applicable),
            gain_loss_voice_not_applicable=sorted(self._gain_loss_voice_not_applicable),
        )

    @staticmethod
    def _distance_wrapped(previous:Any,current:Any,track_length_m:Any)->bool:
        if not (_num(previous) and _num(current) and _num(track_length_m)):
            return False
        length=float(track_length_m)
        if length<=0:return False
        return float(previous)>=0.80*length and float(current)<=0.20*length and float(current)<float(previous)-0.50*length

    @staticmethod
    def _is_final_lap(session,lap_state)->bool:
        if getattr(session,"ended",False) is True:
            return True
        lap=getattr(lap_state,"current_lap",None)
        total=getattr(session,"total_laps",None)
        if isinstance(lap,int) and isinstance(total,int) and total>0 and lap>=total:
            return True
        result_raw=getattr(getattr(lap_state,"result_status",None),"raw",None)
        return result_raw in (3,4,5,6,7)

    @staticmethod
    def _physical_corner_for_distance(corners,d):
        if not _num(d):return None
        x=float(d)
        for corner in corners:
            if float(corner.start_m)<=x<=float(corner.end_m):
                return corner
        return None

    @staticmethod
    def _phase(zone:CoachingZone,d:float|None):
        if not _num(d):return None
        x=float(d)
        brake=zone.brake_start_m if _num(zone.brake_start_m) else zone.start_m
        apex=zone.apex_m if _num(zone.apex_m) else (zone.start_m+zone.end_m)/2
        throttle=zone.throttle_start_m if _num(zone.throttle_start_m) else apex
        if x<brake:return "APPROACH"
        if x<zone.start_m:return "BRAKE"
        if x<apex:return "ENTRY"
        if x<throttle:return "APEX"
        if x<=zone.end_m:return "EXIT"
        return "COMPLETE"

    def _reset_live_performance(self) -> None:
        self._live_points=[]
        self._live_point_distances=[]
        self._live_gain_loss=[]
        self._live_segments=[]
        self._live_segment_done=set()
        self._live_zone_rows=[]
        self._live_zone_done=set()
        self._last_lap_time_s=None
        self._last_distance_seen=None
        self._first_delta_s=None
        self._last_delta_s=None
        self._distance_model={"available":False,"points":[],"turns":[],"segments":[]}
        self._distance_status_payload={"available":False}
        self._zone_attribution={"available":False,"zones":[],"straights":[],"segments":[],"reconciliation_error_s":None}

    def _reference_value_at(self, d: float, key: str) -> float | None:
        """Linear reference lookup using arrays compiled once per reference."""
        if not self._reference_samples or not self._reference_distances or not _num(d):
            return None
        x=float(d)
        i=bisect_left(self._reference_distances,x)
        if i<=0:
            value=self._reference_samples[0].get(key)
            return float(value) if _num(value) else None
        if i>=len(self._reference_samples):
            value=self._reference_samples[-1].get(key)
            return float(value) if _num(value) else None
        d0=float(self._reference_distances[i-1]);d1=float(self._reference_distances[i])
        v0=self._reference_samples[i-1].get(key);v1=self._reference_samples[i].get(key)
        if not (_num(v0) and _num(v1)):
            v=v0 if x-d0<=d1-x else v1
            return float(v) if _num(v) else None
        if d1<=d0:return float(v1)
        a=max(0.0,min(1.0,(x-d0)/(d1-d0)))
        return float(v0)+(float(v1)-float(v0))*a

    def _live_delta_at(self, d: float) -> float | None:
        if not self._live_points or not self._live_point_distances or not _num(d):return None
        x=float(d);i=bisect_left(self._live_point_distances,x)
        if i<=0:return float(self._live_points[0]["delta_s"])
        if i>=len(self._live_points):return float(self._live_points[-1]["delta_s"])
        a=self._live_points[i-1];b=self._live_points[i];d0=float(a["distance_m"]);d1=float(b["distance_m"])
        if d1<=d0:return float(b["delta_s"])
        f=(x-d0)/(d1-d0);return float(a["delta_s"])+(float(b["delta_s"])-float(a["delta_s"]))*f

    def _complete_incremental_regions(self, model:ReferenceTrace, current_d:float) -> None:
        """Finalize crossed turn/straight/CoachingZone losses with O(Ncorners) work."""
        boundaries=tuple(sorted(self._performance_boundaries,key=lambda x:float(x.get("start_m",0.0))))
        defs=[];cursor=0.0;straight_no=0
        for b in boundaries:
            start=float(b["start_m"]);end=float(b["end_m"])
            if start-cursor>=7.5:
                straight_no+=1;defs.append(("straight",straight_no,f"S{straight_no}",cursor,start))
            defs.append(("turn",int(b["corner_id"]),str(b["label"]),start,end));cursor=max(cursor,end)
        if float(model.track_length_m)-cursor>=7.5:
            straight_no+=1;defs.append(("straight",straight_no,f"S{straight_no}",cursor,float(model.track_length_m)))
        for kind,num,label,a,b in defs:
            key=(kind,num)
            if key in self._live_segment_done or current_d+1e-6<b:continue
            da=self._live_delta_at(a);db=self._live_delta_at(b)
            if not (_num(da) and _num(db)):continue
            self._live_segment_done.add(key)
            self._live_segments.append({"segment_kind":kind,"number":num,"label":label,"start_m":a,"end_m":b,"net_loss_s":float(db)-float(da),"complete":True})
        for z in model.coaching_zones:
            if z.zone_id in self._live_zone_done or current_d+1e-6<float(z.end_m):continue
            da=self._live_delta_at(z.approach_start_m);db=self._live_delta_at(z.end_m)
            if not (_num(da) and _num(db)):continue
            self._live_zone_done.add(z.zone_id)
            self._live_zone_rows.append({"zone_id":z.zone_id,"label":z.public_label,"corner_ids":tuple(z.corner_ids),"start_m":float(z.approach_start_m),"end_m":float(z.end_m),"net_loss_s":float(db)-float(da),"complete":True})
        full_net=(float(self._last_delta_s)-float(self._first_delta_s)) if _num(self._last_delta_s) and _num(self._first_delta_s) else None
        all_segments=bool(defs) and len(self._live_segment_done)==len(defs)
        partition=sum(float(x["net_loss_s"]) for x in self._live_segments) if all_segments else None
        reconciliation=(float(full_net)-float(partition)) if _num(full_net) and _num(partition) else None
        self._zone_attribution={"available":bool(self._live_zone_rows),"zones":tuple(self._live_zone_rows),"straights":tuple(x for x in self._live_segments if x["segment_kind"]=="straight"),"segments":tuple(self._live_segments),"reconciliation_error_s":reconciliation,"full_track_net_delta_s":full_net}

    def _publish_live_performance_status(self, delta:float|None=None) -> None:
        full_net=(float(self._last_delta_s)-float(self._first_delta_s)) if _num(self._last_delta_s) and _num(self._first_delta_s) else None
        self._distance_model={"available":len(self._live_points)>=2,"points":self._live_points,"turns":[],"segments":self._live_segments,"full_track_net_delta_s":full_net}
        self._distance_status_payload={"available":len(self._live_points)>=2,"gain_loss_zones":tuple({k:v for k,v in x.items() if k!="start_delta_s"} for x in self._live_gain_loss),"segments":tuple(dict(x) for x in self._live_segments),"reconciliation_error_s":self._zone_attribution.get("reconciliation_error_s"),"full_track_net_delta_s":full_net}

    def _finalize_lap_boundary(self, model:ReferenceTrace, lap_time_s:Any) -> bool:
        """Close the exact S/F endpoint before resetting a completed lap.

        EA LapData commonly jumps from ~5270 m straight to a small distance on
        the next packet. Waiting for a sample at exactly track_length therefore
        left the final straight incomplete. ``previous_lap_time_s`` is the
        authoritative completed-lap clock, so append the exact S/F point and
        finalize every outstanding physical/straight segment before lap reset.
        """
        if not (_num(lap_time_s) and _num(model.track_length_m) and float(model.track_length_m)>0):
            return False
        length=float(model.track_length_m); current_t=float(lap_time_s)
        reference_t=float(model.lap_time_s) if _num(model.lap_time_s) else self._reference_value_at(length,"t")
        if not _num(reference_t):
            return False
        delta=current_t-float(reference_t)
        row={"distance_m":length,"current_time_s":current_t,"reference_time_s":float(reference_t),"delta_s":delta,"local_delta_s":0.0}
        if self._live_point_distances:
            prev_delta=float(self._live_points[-1]["delta_s"]) if _num(self._live_points[-1].get("delta_s")) else None
            row["local_delta_s"]=delta-float(prev_delta) if _num(prev_delta) else 0.0
            if self._live_point_distances[-1]>=length-0.25:
                self._live_points[-1]=row;self._live_point_distances[-1]=length
            elif self._live_point_distances[-1]<length:
                self._live_points.append(row);self._live_point_distances.append(length)
        else:
            self._live_points.append(row);self._live_point_distances.append(length)
        if self._first_delta_s is None:
            self._first_delta_s=delta
        self._last_delta_s=delta;self._last_perf_distance=length;self._last_distance_seen=length;self._last_lap_time_s=current_t
        self._complete_incremental_regions(model,length)
        self._publish_live_performance_status(delta)
        return True

    def _update_incremental_performance(self, model:ReferenceTrace, lap_state, d:float) -> None:
        """O(log N) live timing update.  Never rebuild the whole lap in process_packet()."""
        current_t=getattr(lap_state,"current_lap_time_s",None) if lap_state is not None else None
        if not (_num(current_t) and _num(d)):return
        current_t=float(current_t);d=float(d)
        # Lap packets are the timing authority. Telemetry packets often repeat the
        # same lap time; skipping duplicates both avoids false deltas and keeps the
        # packet hot path essentially constant time.
        if _num(self._last_lap_time_s) and abs(current_t-float(self._last_lap_time_s))<1e-9:
            return
        if _num(self._last_distance_seen) and d<float(self._last_distance_seen)-100.0:
            self._reset_live_performance()
        rt=self._reference_value_at(d,"t")
        if not _num(rt):return
        delta=current_t-float(rt)
        prev_delta=float(self._live_points[-1]["delta_s"]) if self._live_points else None
        row={"distance_m":d,"current_time_s":current_t,"reference_time_s":float(rt),"delta_s":delta,"local_delta_s":delta-prev_delta if _num(prev_delta) else 0.0}
        # Replace an equal/backward-near sample rather than creating duplicate
        # distance keys during packet jitter. Otherwise append monotonically.
        if self._live_point_distances and d<=self._live_point_distances[-1]+0.25:
            if d>=self._live_point_distances[-1]-2.0:
                self._live_points[-1]=row;self._live_point_distances[-1]=d
            else:
                return
        else:
            self._live_points.append(row);self._live_point_distances.append(d)
        self._last_lap_time_s=current_t;self._last_distance_seen=d;self._last_perf_distance=d
        if self._first_delta_s is None:self._first_delta_s=delta
        self._last_delta_s=delta
        back=self._live_delta_at(max(0.0,d-25.0));window=delta-float(back) if _num(back) else 0.0
        state="LOSS" if window>0.003 else ("GAIN" if window<-0.003 else "NEUTRAL")
        if self._live_gain_loss and self._live_gain_loss[-1]["state"]==state:
            self._live_gain_loss[-1]["end_m"]=d
            start_delta=self._live_gain_loss[-1].get("start_delta_s")
            self._live_gain_loss[-1]["net_delta_s"]=delta-float(start_delta) if _num(start_delta) else 0.0
        else:
            self._live_gain_loss.append({"start_m":d,"end_m":d,"state":state,"net_delta_s":0.0,"start_delta_s":delta})
        self._complete_incremental_regions(model,d)
        # Expose only compact immutable summaries.  The private point list is used
        # for POST phase attribution and never copied into shared overlay state.
        self._publish_live_performance_status(delta)

    def _diagnosis_model_for_zone(self, zone:CoachingZone) -> dict[str,Any]:
        turns=[]
        for b in self._performance_boundaries:
            cid=b.get("corner_id")
            if cid not in zone.corner_ids:continue
            loss=_phase_loss(self._live_points,float(b.get("start_m",0.0)),float(b.get("end_m",0.0)))
            turns.append({"corner_id":cid,"physical_net_loss_s":loss})
        return {
            "available":bool(self._live_points),"points":self._live_points,"turns":turns,"segments":self._live_segments,
            "input_telemetry_trusted":bool((self.reference_model.quality or {}).get("input_telemetry_trusted",True)) if self.reference_model is not None else True,
        }

    def _reference_row_at(self, d: float) -> dict:
        if not self._reference_samples or not self._reference_distances:
            return {}
        i=bisect_left(self._reference_distances,float(d))
        if i<=0:return dict(self._reference_samples[0])
        if i>=len(self._reference_samples):return dict(self._reference_samples[-1])
        before=i-1;after=i
        idx=before if abs(self._reference_distances[before]-float(d))<=abs(self._reference_distances[after]-float(d)) else after
        return dict(self._reference_samples[idx])

    def _diagnose(self,zone:CoachingZone,current:dict,reference:dict,model:dict)->Diagnosis:
        points=list(model.get("points") or ())
        start=zone.approach_start_m; end=zone.end_m
        net=_phase_loss(points,start,end)
        ref_rows=_sample_rows(reference); cur_rows=_sample_rows(current)
        inputs_trusted=bool(model.get("input_telemetry_trusted",True))
        ref_brake=zone.brake_start_m if inputs_trusted else None
        cur_brake=_first_event(cur_rows,start,zone.apex_m or end,"brake",0.10)
        brake_delta=(cur_brake-ref_brake) if _num(cur_brake) and _num(ref_brake) else None
        ref_release=zone.brake_release_m if inputs_trusted else None
        cur_release=_last_event(cur_rows,cur_brake if _num(cur_brake) else start,zone.apex_m or end,"brake",0.10)
        release_delta=(cur_release-ref_release) if _num(cur_release) and _num(ref_release) else None
        # Rival Time Trial pedal channels are not authoritative in rival_pace
        # mode. Never diagnose peak-brake differences from raw ghost inputs.
        ref_peak,_ref_peak_m=_peak(ref_rows,start,zone.apex_m or end,"brake") if inputs_trusted else (None,None)
        cur_peak,_cur_peak_m=_peak(cur_rows,start,zone.apex_m or end,"brake")
        peak_brake_delta=(cur_peak-ref_peak) if _num(cur_peak) and _num(ref_peak) else None
        ref_min=zone.reference_min_speed_kph
        cur_min,cur_min_m=_min_speed(cur_rows,zone.start_m,end)
        min_delta=(cur_min-ref_min) if _num(cur_min) and _num(ref_min) else None
        ref_thr=zone.throttle_start_m if inputs_trusted else None
        cur_thr=_first_event(cur_rows,zone.apex_m or zone.start_m,end+40.0,"throttle",0.20)
        throttle_delta=(cur_thr-ref_thr) if _num(cur_thr) and _num(ref_thr) else None
        ref_full=zone.full_throttle_m if inputs_trusted else None
        cur_full=_first_event(cur_rows,zone.apex_m or zone.start_m,end+80.0,"throttle",0.98)
        full_delta=(cur_full-ref_full) if _num(cur_full) and _num(ref_full) else None
        ref_steer=_first_event(ref_rows,start,zone.apex_m or end,"steering",0.08,absolute=True) if inputs_trusted else None
        cur_steer=_first_event(cur_rows,start,zone.apex_m or end,"steering",0.08,absolute=True)
        steer_delta=(cur_steer-ref_steer) if _num(cur_steer) and _num(ref_steer) else None
        # Pace-only references use the clean compiled speed trace. Raw Time
        # Trial ghost speed is known to be physically inconsistent.
        ref_exit=self._reference_value_at(end,"speed") if not inputs_trusted else _speed_at(ref_rows,end)
        cur_exit=_speed_at(cur_rows,end)
        exit_delta=(cur_exit-ref_exit) if _num(cur_exit) and _num(ref_exit) else None
        apex=float(zone.apex_m or (zone.start_m+zone.end_m)/2)
        phase_losses={
            "approach":_phase_loss(points,start,zone.start_m),
            "entry":_phase_loss(points,zone.start_m,apex),
            "exit":_phase_loss(points,apex,end),
        }
        # V1.8 geometry/time-domain evidence for the physical corner carrying the
        # largest measured loss inside this coaching zone. This keeps multi-turn
        # zone radio deterministic while retaining physical T numbering.
        corner_rows=[x for x in (model.get("turns") or ()) if isinstance(x,dict) and x.get("corner_id") in zone.corner_ids and _num(x.get("physical_net_loss_s"))]
        dominant=max(corner_rows,key=lambda x:float(x.get("physical_net_loss_s") or -1e9)) if corner_rows else None
        geometry_metrics={}
        # For normal multi-corner coaching zones, geometry follows the dominant
        # measured-loss corner exactly as before.  V2 live physical-corner cards
        # are different: they must be able to publish apex evidence even when the
        # timing model has no dominant loss for that turn yet.  In a single-turn
        # LIVE_T zone, compare that physical corner directly at the first exit
        # sample instead of waiting for loss attribution.
        geometry_corner_id=None
        if dominant is not None:
            geometry_corner_id=dominant.get("corner_id")
        elif len(zone.corner_ids)==1 and str(zone.zone_id).startswith("LIVE_T"):
            geometry_corner_id=zone.corner_ids[0]
        if _num(geometry_corner_id):
            boundary=next((b for b in self._performance_boundaries if b.get("corner_id")==geometry_corner_id),None)
            if isinstance(boundary,dict):
                try:
                    from .corner_geometry_metrics import compare_corner
                    geometry_metrics=compare_corner(current,reference,boundary)
                except Exception:
                    geometry_metrics={}
        geometry_conf=float(geometry_metrics.get("corner_confidence") or 0.0)
        apex_speed_delta=geometry_metrics.get("apex_speed_kph_delta")
        coast_time_delta=geometry_metrics.get("coasting_s_delta")
        throttle_time_delta=geometry_metrics.get("throttle_pickup_after_apex_s_delta")
        steering_corrections_delta=geometry_metrics.get("steering_corrections_delta")
        steering_smoothness_delta=geometry_metrics.get("steering_smoothness_delta")
        steering_unwind_delta=geometry_metrics.get("steering_unwind_s_delta")
        code=None;text=None;confidence=0.0
        losing=_num(net) and float(net)>self.LOSS_DEADBAND_S
        if losing:
            # Prefer directly measured timing mistakes that align with the phase
            # where time was actually lost. Do not invent causal claims.
            entry_losing=(_num(phase_losses["approach"]) and phase_losses["approach"]>0.010) or (_num(phase_losses["entry"]) and phase_losses["entry"]>0.010)
            exit_losing=_num(phase_losses["exit"]) and phase_losses["exit"]>0.010
            if _num(brake_delta) and float(brake_delta)<-8.0 and entry_losing:
                code="brake_early";text=f"braked about {abs(float(brake_delta)):.0f} metres early";confidence=0.95
            elif _num(brake_delta) and float(brake_delta)>10.0 and entry_losing:
                code="brake_late";text=f"braked about {float(brake_delta):.0f} metres late";confidence=0.90
            elif _num(peak_brake_delta) and float(peak_brake_delta)>0.12 and _num(min_delta) and float(min_delta)<-3.0 and entry_losing:
                code="over_braking";text=f"used about {float(peak_brake_delta)*100:.0f} percent more peak brake and carried less minimum speed";confidence=0.90
            elif _num(release_delta) and float(release_delta)<-10.0 and entry_losing:
                code="brake_release_early";text=f"released the brake about {abs(float(release_delta)):.0f} metres early";confidence=0.88
            elif _num(release_delta) and float(release_delta)>12.0 and entry_losing and _num(min_delta) and float(min_delta)<-2.0:
                code="brake_release_late";text=f"held the brake about {float(release_delta):.0f} metres longer";confidence=0.86
            elif geometry_conf>=0.55 and _num(coast_time_delta) and float(coast_time_delta)>0.10 and _num(phase_losses["entry"]) and phase_losses["entry"]>0.010:
                code="coasting_excessive";text=f"coasted about {float(coast_time_delta):.2f} seconds longer";confidence=min(0.92,geometry_conf)
            elif geometry_conf>=0.55 and _num(apex_speed_delta) and float(apex_speed_delta)<-4.0 and _num(phase_losses["entry"]) and phase_losses["entry"]>0.010:
                code="apex_speed_low";text=f"apex speed was about {abs(float(apex_speed_delta)):.0f} kph lower";confidence=min(0.92,geometry_conf)
            elif _num(min_delta) and float(min_delta)<-3.0 and _num(phase_losses["entry"]) and phase_losses["entry"]>0.010:
                code="min_speed_low";text=f"minimum speed was about {abs(float(min_delta)):.0f} kph lower";confidence=0.90
            elif geometry_conf>=0.55 and _num(throttle_time_delta) and float(throttle_time_delta)>0.10 and exit_losing:
                code="throttle_late";text=f"throttle pickup was about {float(throttle_time_delta):.2f} seconds late";confidence=min(0.92,geometry_conf)
            elif _num(throttle_delta) and float(throttle_delta)>8.0 and exit_losing:
                code="throttle_late";text=f"throttle pickup was about {float(throttle_delta):.0f} metres late";confidence=0.90
            elif _num(full_delta) and float(full_delta)>12.0 and exit_losing:
                code="full_throttle_late";text=f"full throttle was about {float(full_delta):.0f} metres late";confidence=0.86
            elif _num(exit_delta) and float(exit_delta)<-4.0 and exit_losing:
                code="exit_speed_low";text=f"exit speed was about {abs(float(exit_delta)):.0f} kph lower";confidence=0.85
            elif _num(steer_delta) and abs(float(steer_delta))>10.0 and _num(phase_losses["entry"]) and phase_losses["entry"]>0.010:
                code="turn_in_timing";direction="late" if float(steer_delta)>0 else "early";text=f"turn-in was about {abs(float(steer_delta)):.0f} metres {direction}";confidence=0.80
            elif geometry_conf>=0.55 and _num(steering_corrections_delta) and float(steering_corrections_delta)>=2.0 and _num(phase_losses["entry"]) and phase_losses["entry"]>0.010:
                code="steering_corrections";text=f"made {int(round(float(steering_corrections_delta)))} more steering corrections";confidence=min(0.82,geometry_conf)
            elif geometry_conf>=0.55 and _num(steering_smoothness_delta) and float(steering_smoothness_delta)<=-0.12 and _num(phase_losses["entry"]) and phase_losses["entry"]>0.010:
                code="steering_unsmooth";text="steering was less smooth than the reference";confidence=min(0.80,geometry_conf)
            elif geometry_conf>=0.55 and _num(steering_unwind_delta) and float(steering_unwind_delta)>=0.15 and exit_losing:
                code="steering_unwind_slow";text=f"steering unwind was about {float(steering_unwind_delta):.2f} seconds slower";confidence=min(0.82,geometry_conf)
            else:
                code="measured_loss";text=None;confidence=1.0
        elif _num(net) and float(net)<-self.LOSS_DEADBAND_S:
            code="gain";confidence=1.0
        else:
            code="match";confidence=1.0
        # Per-physical-corner loss remains available inside a multi-corner zone.
        # This is factual attribution only; it never changes physical numbering.
        measurements={
            "brake_point_delta_m":brake_delta,"brake_release_delta_m":release_delta,"peak_brake_delta":peak_brake_delta,
            "min_speed_delta_kph":min_delta,"throttle_pickup_delta_m":throttle_delta,
            "full_throttle_delta_m":full_delta,"turn_in_delta_m":steer_delta,"exit_speed_delta_kph":exit_delta,
            "current_min_speed_kph":cur_min,"current_min_speed_m":cur_min_m,
            "apex_speed_delta_kph":apex_speed_delta,"apex_position_delta_m":geometry_metrics.get("apex_m_delta"),
            "apex_position_trusted":geometry_metrics.get("apex_position_trusted",False),
            "apex_estimate_delta_m":geometry_metrics.get("apex_estimate_delta_m"),
            "apex_estimate_trusted":geometry_metrics.get("apex_estimate_trusted",False),
            "apex_evidence_method":geometry_metrics.get("apex_evidence_method"),
            "apex_position_confidence":min(
                float((geometry_metrics.get("current_metrics") or {}).get("apex_confidence") or 0.0),
                float((geometry_metrics.get("reference_metrics") or {}).get("apex_confidence") or 0.0),
            ) if geometry_metrics else 0.0,
            "coasting_delta_s":coast_time_delta,
            "throttle_pickup_delta_s":throttle_time_delta,"steering_corrections_delta":steering_corrections_delta,
            "steering_smoothness_delta":steering_smoothness_delta,"steering_unwind_delta_s":steering_unwind_delta,
            "minimum_speed_efficiency_pct":geometry_metrics.get("minimum_speed_efficiency_pct"),
            "throttle_pickup_efficiency_pct":geometry_metrics.get("throttle_pickup_efficiency_pct"),
            "exit_speed_efficiency_pct":geometry_metrics.get("exit_speed_efficiency_pct"),
            "corner_data_confidence":geometry_conf,
            "dominant_corner":(int(dominant["corner_id"]) if dominant and _num(dominant.get("corner_id")) else None),
            "dominant_corner_loss_s":(float(dominant["physical_net_loss_s"]) if dominant else None),
        }
        return Diagnosis(zone.zone_id,zone.public_label,float(net) if _num(net) else None,code,text,confidence,measurements,phase_losses)

    @staticmethod
    def _choose_speech_variant(full_text:str, compact_text:str, airtime_s:float, *, margin_s:float=0.20):
        """Choose the richest line that can FINISH inside the available airtime.

        Returns ``(text, estimated_duration_s, variant)`` or ``None``.  This is
        shared by PRE and POST so the scheduling policy is deterministic and easy
        to validate independently of telemetry packet timing.
        """
        full_est=estimate_speech_duration_s(full_text)
        compact_est=estimate_speech_duration_s(compact_text)
        if not _num(airtime_s) or float(airtime_s)<0:
            return None
        budget=float(airtime_s)
        if full_est+float(margin_s)<=budget:
            return full_text,full_est,"full"
        if compact_est+float(margin_s)<=budget:
            return compact_text,compact_est,"compact"
        return None

    def _speech_wait_s(self, session_time_s:Any) -> float:
        if not _num(session_time_s):
            return 0.0
        return max(0.0, float(self._speech_reserved_until_session_s)-float(session_time_s))

    def _reserve_speech(self, kind:str, zone_id:str, session_time_s:Any, duration_s:float, *, preempt:bool=False) -> tuple[float,float]:
        """Reserve the one CORNER COACH voice channel in game/session time.

        Fast replay has no wall-clock audio, so using session time here makes the
        same airtime decision in replay and live driving. PRE may deliberately
        pre-empt an older reservation when waiting would miss its hard deadline;
        POST never pre-empts.
        """
        now=float(session_time_s) if _num(session_time_s) else 0.0
        start=now if preempt else max(now,float(self._speech_reserved_until_session_s))
        end=start+max(0.0,float(duration_s))
        self._speech_reserved_until_session_s=end
        self._speech_reserved_kind=str(kind).upper()
        self._speech_reserved_zone=str(zone_id)
        return start,end

    @staticmethod
    def _pre_text(zone:CoachingZone,current_distance_m:float|None=None,*,pace_only:bool=False,distance_to_target_m:float|None=None)->str:
        label=_spoken_label(zone)
        targets=[]
        if _num(distance_to_target_m):
            distance=max(0.0,float(distance_to_target_m))
            targets.append(("reference slows in about " if pace_only else "brake in about ")+f"{distance:.0f} metres")
        elif _num(zone.brake_start_m) and _num(current_distance_m):
            distance=max(0.0,float(zone.brake_start_m)-float(current_distance_m))
            targets.append(("reference slows in about " if pace_only else "brake in about ")+f"{distance:.0f} metres")
        elif _num(zone.brake_start_m):
            targets.append("match the reference slowdown point" if pace_only else "use the reference brake point")
        if not pace_only and isinstance(zone.reference_gear,int) and zone.reference_gear>0:targets.append(f"gear {zone.reference_gear}")
        if _num(zone.reference_min_speed_kph):targets.append(f"minimum about {float(zone.reference_min_speed_kph):.0f} kph")
        if len(zone.corner_ids)>1 and _num(zone.throttle_start_m):targets.append("prioritise the final exit")
        fallback="match the rival pace" if pace_only else "match the reference inputs"
        return f"{label} coming up: "+(", ".join(targets) if targets else fallback)+"."

    @staticmethod
    def _track_learning_pre_text(zone:CoachingZone,distance_to_target_m:float|None=None)->str:
        """Instructional circuit-learning cue without performance judgment."""
        label=_spoken_label(zone)
        bits=[]
        if _num(distance_to_target_m):bits.append(f"brake in about {max(0.0,float(distance_to_target_m)):.0f} metres")
        if isinstance(zone.reference_gear,int) and zone.reference_gear>0:bits.append(f"use gear {zone.reference_gear}")
        if _num(zone.reference_min_speed_kph):bits.append(f"aim for about {float(zone.reference_min_speed_kph):.0f} kph minimum")
        if len(zone.corner_ids)>1:bits.append("prioritise the final exit")
        return f"{label} coming up: "+(", ".join(bits) if bits else "focus on a clean line and exit")+"."

    @staticmethod
    def _track_learning_pre_compact(zone:CoachingZone,distance_to_target_m:float|None=None)->str:
        label=_spoken_label(zone);bits=[]
        if _num(distance_to_target_m):bits.append(f"{max(0.0,float(distance_to_target_m)):.0f} metres")
        if isinstance(zone.reference_gear,int) and zone.reference_gear>0:bits.append(f"gear {zone.reference_gear}")
        if _num(zone.reference_min_speed_kph):bits.append(f"minimum {float(zone.reference_min_speed_kph):.0f}")
        return f"{label}, "+(", ".join(bits) if bits else "next")+"."

    @staticmethod
    def _pre_text_compact(zone:CoachingZone,distance_to_target_m:float|None=None,*,pace_only:bool=False)->str:
        """Short PRE used when the full call would consume too much approach time."""
        label=_spoken_label(zone)
        bits=[]
        if _num(distance_to_target_m):
            bits.append(f"{max(0.0,float(distance_to_target_m)):.0f} metres")
        if _num(zone.reference_min_speed_kph):
            bits.append(f"minimum {float(zone.reference_min_speed_kph):.0f}")
        if not pace_only and isinstance(zone.reference_gear,int) and zone.reference_gear>0:
            bits.append(f"gear {zone.reference_gear}")
        return f"{label}, "+(", ".join(bits) if bits else "next")+"."

    @staticmethod
    def _pre_text_micro(zone:CoachingZone)->str:
        """Minimum useful PRE for a tight approach.

        The micro cue intentionally drops distance/gear detail.  It exists for
        cases such as a flying-lap T1 where a 3-5 second compact sentence cannot
        physically finish before the target, but a short turn + minimum-speed cue
        can still be delivered safely and on time.
        """
        ids=tuple(zone.corner_ids or ())
        if len(ids)==1:
            label=f"T{ids[0]}"
        elif ids:
            label=f"T{ids[0]}-{ids[-1]}"
        else:
            label="Corner"
        if _num(zone.reference_min_speed_kph):
            return f"{label}, minimum {float(zone.reference_min_speed_kph):.0f}."
        return f"{label}, next."

    @staticmethod
    def _post_text(zone:CoachingZone,diag:Diagnosis)->str:
        label=_spoken_label(zone)
        loss=diag.net_loss_s
        if diag.primary_code=="gain" and _num(loss):return f"{label} better, gained {abs(float(loss)):.2f} seconds."
        if not _num(loss):return f"{label} complete."
        if float(loss)<=0.030:return f"{label}, matched the reference closely."
        base=f"{label}, lost {float(loss):.2f} seconds"
        if diag.primary_text:
            possessive_codes={"min_speed_low","apex_speed_low","throttle_late","full_throttle_late","exit_speed_low","turn_in_timing","steering_unsmooth","steering_unwind_slow"}
            subject="Your" if diag.primary_code in possessive_codes else "You"
            return base+f". {subject} {diag.primary_text}."
        dominant=diag.measurements.get("dominant_corner") if isinstance(diag.measurements,dict) else None
        dominant_loss=diag.measurements.get("dominant_corner_loss_s") if isinstance(diag.measurements,dict) else None
        if len(zone.corner_ids)>1 and isinstance(dominant,int) and _num(dominant_loss) and float(dominant_loss)>0.05:
            return base+f". Most of the measured corner loss was at T{dominant}."
        return base+"."

    @staticmethod
    def _post_text_compact(zone:CoachingZone,diag:Diagnosis)->str:
        """Airtime-safe POST: preserve result first, one cause only when very short."""
        label=_spoken_label(zone)
        loss=diag.net_loss_s
        if diag.primary_code=="gain" and _num(loss):
            return f"{label}, gained {abs(float(loss)):.2f}."
        if not _num(loss):
            return f"{label}, complete."
        if float(loss)<=0.030:
            return f"{label}, matched."
        base=f"{label}, lost {float(loss):.2f}."
        m=diag.measurements if isinstance(diag.measurements,dict) else {}
        if diag.primary_code=="min_speed_low" and _num(m.get("min_speed_delta_kph")):
            return base+f" Minimum {abs(float(m['min_speed_delta_kph'])):.0f} kph low."
        if diag.primary_code=="exit_speed_low" and _num(m.get("exit_speed_delta_kph")):
            return base+f" Exit {abs(float(m['exit_speed_delta_kph'])):.0f} kph low."
        if diag.primary_code=="apex_speed_low" and _num(m.get("apex_speed_delta_kph")):
            return base+f" Apex {abs(float(m['apex_speed_delta_kph'])):.0f} kph low."
        if diag.primary_code=="coasting_long" and _num(m.get("coasting_delta_s")):
            return base+f" Coast {max(0.0,float(m['coasting_delta_s'])):.2f}s long."
        if diag.primary_code=="throttle_late" and _num(m.get("throttle_pickup_delta_s")):
            return base+f" Throttle {max(0.0,float(m['throttle_pickup_delta_s'])):.2f}s late."
        if diag.primary_code=="steering_corrections" and _num(m.get("steering_corrections_delta")):
            return base+f" {max(0,int(round(float(m['steering_corrections_delta']))))} extra steering corrections."
        return base

    @staticmethod
    def _post_text_micro(zone:CoachingZone,diag:Diagnosis)->str:
        """Shortest useful visual/radio result for dense corner sequences."""
        label=_spoken_label(zone)
        loss=diag.net_loss_s
        if diag.primary_code=="gain" and _num(loss):
            return f"{label}, gained {abs(float(loss)):.2f}."
        if not _num(loss):
            return f"{label}, complete."
        if float(loss)<=0.030:
            return f"{label}, matched."
        return f"{label}, lost {float(loss):.2f}."

    def _post_text_with_memory(self, zone:CoachingZone, diag:Diagnosis) -> tuple[str,str,str]:
        """Keep per-corner coverage while avoiding identical verbose advice forever.

        The first occurrence uses the normal rich text. Repeated, materially similar
        diagnoses use compact wording. If the measured loss changes by >=80 ms or
        the diagnosis changes, the detailed explanation is re-armed.
        """
        code=str(diag.primary_code or "")
        loss=float(diag.net_loss_s) if _num(diag.net_loss_s) else None
        previous=self._post_repeat_signature.get(zone.zone_id)
        repeated=False
        if previous is not None and previous[0]==code:
            old_loss=previous[1]
            repeated=(loss is None and old_loss is None) or (_num(loss) and _num(old_loss) and abs(float(loss)-float(old_loss))<0.080)
        count=(int(self._post_repeat_count.get(zone.zone_id,0))+1) if repeated else 1
        self._post_repeat_count[zone.zone_id]=count
        self._post_repeat_signature[zone.zone_id]=(code,loss)
        full=self._post_text(zone,diag)
        compact=self._post_text_compact(zone,diag)
        micro=self._post_text_micro(zone,diag)
        if repeated and count>=2:
            # Every fourth repetition restores the richer diagnosis so long races
            # still remind the driver what the issue actually is.
            if count % 4:
                full=compact
        return full,compact,micro

    @staticmethod
    def _significant_damage_present(state) -> bool:
        """Use the same deterministic damage threshold as the coaching quality gate."""
        player=getattr(state,"player",None)
        damage=getattr(player,"damage",None) if player is not None else None
        if damage is None:
            return False
        try:
            wing=max(int(getattr(damage,"front_left_wing_percent",0) or 0),int(getattr(damage,"front_right_wing_percent",0) or 0))
            floor=int(getattr(damage,"floor_percent",0) or 0)
        except (TypeError,ValueError):
            wing=floor=0
        return bool(wing>=20 or floor>=20 or getattr(damage,"engine_blown",False) or getattr(damage,"engine_seized",False))

    def observe(self,recorder,state,now:float)->list[EngineerMessage]:
        if not self.enabled:return []
        reference=recorder.current_reference_lap()
        session=getattr(state,"session",None); track=getattr(getattr(session,"track",None),"name",None) or getattr(getattr(session,"track",None),"label",None)
        metadata=getattr(recorder,"external_reference_meta",{}) if getattr(recorder,"reference_mode",None)=="external" else {}
        model=self._ensure_reference(reference,track,metadata)
        player=getattr(state,"player",None); lap_state=getattr(player,"lap",None) if player is not None else None
        lap=getattr(lap_state,"current_lap",None) if lap_state is not None else None
        d=getattr(lap_state,"lap_distance_m",None) if lap_state is not None else None
        speed=getattr(getattr(player,"telemetry",None),"speed_kph",None) if player is not None else None
        session_time=getattr(session,"session_time_s",None) if session is not None else None
        session_uid=getattr(session,"uid",None) if session is not None else None

        # The recorder updates the shared physical-track model at the completed
        # lap boundary. Rebind the active reference once on the next lap so map,
        # T1..Tn, apex feedback and coaching all use the same newest authority.
        if model is not None and isinstance(lap,int) and lap!=self._track_geometry_refresh_lap:
            refreshed=apply_persisted_track_geometry(model)
            self._track_geometry_refresh_lap=lap
            if refreshed is not model:
                self.reference_model=refreshed
                model=refreshed
                self._reference_samples=tuple(model.samples)
                self._reference_distances=tuple(float(r.get("d",0.0)) for r in self._reference_samples)
                self._zones_payload=tuple(to_dict(z) for z in model.coaching_zones)
                self._corners_payload=tuple(to_dict(c) for c in model.physical_corners)
                # Force physical performance boundaries to rebuild from the new
                # authority without touching the reference driving events.
                corners=tuple(sorted(model.physical_corners,key=lambda c:float(c.apex_m)))
                apexes=[float(c.apex_m) for c in corners]
                boundaries=[]
                for i,c in enumerate(corners):
                    own_lo=0.0 if i==0 else (apexes[i-1]+apexes[i])*0.5
                    own_hi=float(model.track_length_m) if i==len(corners)-1 else (apexes[i]+apexes[i+1])*0.5
                    zone=next((z for z in model.coaching_zones if c.corner_id in z.corner_ids),None)
                    brake=(zone.brake_start_m if zone is not None and zone.corner_ids and zone.corner_ids[0]==c.corner_id and _num(zone.brake_start_m) else c.start_m)
                    boundaries.append({
                        "corner_id":int(c.corner_id),"label":str(c.label or f"T{c.corner_id}"),
                        "ownership_start_m":float(own_lo),"ownership_end_m":float(own_hi),
                        "start_m":float(c.start_m),"brake_m":float(brake),
                        "turn_in_m":float(c.start_m+(c.apex_m-c.start_m)*0.5),
                        "apex_m":float(c.apex_m),"end_m":float(c.end_m),
                        "turn_direction":c.direction,"physical_geometry":True,"physical_source":"adaptive_track_model",
                    })
                self._performance_boundaries=tuple(boundaries)

        # Validation trace is created only after a usable compiled
        # reference exists. This keeps startup/menus silent and produces one
        # self-contained file per session/reference pairing.
        if model is not None:
            fingerprint=(model.quality or {}).get("raw_reference_fingerprint") or (model.metadata or {}).get("raw_reference_fingerprint")
            validation_key=((session_uid,str(track or model.track_name).upper(),"SESSION_BEST") if getattr(recorder,"reference_mode",None)=="best" else (session_uid,str(track or model.track_name).upper(),fingerprint,float(model.lap_time_s)))
            if validation_key!=self._validation_run_key:
                self.validation.ensure_run(session_uid=session_uid,track_name=track or model.track_name,model=model,stable_session=(getattr(recorder,"reference_mode",None)=="best"))
                self._validation_run_key=validation_key

        # V1.5.0.0: pit lane and out-lap are analysis-only. Corner coaching on an
        # out-lap compares a deliberately slow/traffic-constrained lap against a
        # flying reference and produces misleading technique calls. Resume at the
        # next lap boundary, which becomes the first flying lap after pit exit.
        # Pit/out-lap suppression applies to sessions that actually have a
        # meaningful garage/pit transition. F1 Time Trial can transiently report
        # a non-zero pit status while loading directly onto a flying lap; treating
        # that as a real out-lap suppresses the entire first coached lap even when
        # a stored rival reference is already active. Time Trial must therefore
        # remain coachable from lap 1.
        event_context=getattr(recorder,"event_context",{}) or {}
        profile=str(event_context.get("profile") or "").strip().lower() if isinstance(event_context,dict) else ""
        pit_outlap_gate_enabled=(profile!="time_trial")
        pit_name=str(getattr(getattr(lap_state,"pit_status",None),"name",getattr(lap_state,"pit_status",None)) or "").strip().lower()
        in_pit=bool(getattr(lap_state,"pit_lane_timer_active",False) or (pit_name and pit_name not in {"none","0","n/a","na"}))
        if pit_outlap_gate_enabled:
            if in_pit:
                self._was_in_pit_lane=True
                if isinstance(lap,int): self._outlap_lap=lap
                self.validation.state_transition("pit_coaching_gate",lap=lap,distance_m=d,session_time_s=session_time,blocked=True,reason="pit_lane")
                return []
            if self._was_in_pit_lane:
                self._was_in_pit_lane=False
                if isinstance(lap,int): self._outlap_lap=lap
                self.validation.state_transition("pit_coaching_gate",lap=lap,distance_m=d,session_time_s=session_time,blocked=True,reason="out_lap")
            if isinstance(lap,int) and self._outlap_lap==lap:
                return []
            if isinstance(lap,int) and isinstance(self._outlap_lap,int) and lap!=self._outlap_lap:
                self.validation.state_transition("pit_coaching_gate",lap=lap,distance_m=d,session_time_s=session_time,blocked=False,reason="first_flying_lap")
                self._outlap_lap=None
        else:
            # Never carry a transient startup pit/out-lap latch into Time Trial.
            self._was_in_pit_lane=False
            self._outlap_lap=None

        # A new session clears the final-race hold. During the post-chequered
        # drive EA can keep current_lap pinned to the scheduled final lap, so do
        # not use the lap number alone as evidence of a new session.
        if self._finished_session_hold_uid is not None:
            fresh_session=(getattr(session,"ended",None) is False and isinstance(lap,int) and lap==1 and _num(d)
                           and (model is None or float(d)<=0.20*float(model.track_length_m)))
            if fresh_session:
                self._finished_session_hold_uid=None;self._awaiting_lap_increment_from=None
                self._lap=None;self._lap_started_clean=False;self._lap_valid=True;self._last_observed_distance=None;self._last_observed_session_time=None;self._compromised_lap=None
                self._speech_reserved_until_session_s=0.0;self._speech_reserved_kind=None;self._speech_reserved_zone=None
            else:
                return []

        # F1 Time Trial / startup ownership: EA can expose lap 1 before the
        # first real start/finish timing anchor, with lap distance near the end
        # of the circuit. When distance then wraps to ~0 the lap number can stay
        # at 1. That wrap starts timed Lap 1; it does NOT complete Lap 1.
        #
        # MeasuredPerformance already rebases ownership at this exact clean
        # anchor. CORNER COACH must follow the same authority or it enters
        # _awaiting_lap_increment_from=1 and suppresses the entire first timed lap.
        lap_time=getattr(lap_state,"current_lap_time_s",None) if lap_state is not None else None
        start_anchor=(
            _num(d) and _num(lap_time)
            and -1.0 <= float(d) <= 25.0
            and 0.0 <= float(lap_time) <= 2.0
        )
        if isinstance(lap,int) and lap==self._lap and start_anchor and not self._lap_started_clean:
            carried=set(self._next_lap_pre_spoken)
            self._next_lap_pre_spoken.clear();self._awaiting_lap_increment_from=None
            self._pre_last_block_reason.clear();self._pre_block_counts.clear()
            self._lap_started_clean=True
            self._lap_valid=(getattr(lap_state,"lap_valid",True) is not False)
            self._compromised_lap=None;self._pre_spoken=carried
            self._post_spoken.clear();self._gain_loss_voice_spoken.clear();self._straight_spoken.clear();self._straight_pending.clear()
            self._diagnoses.clear();self._last_diagnosis=None;self._straight_last_diagnosis=None;self._v2_scored.clear();self._live_corner_result=None
            self._pre_not_applicable.clear();self._post_not_applicable.clear();self._gain_loss_voice_not_applicable.clear()
            self._last_perf_distance=None;self._last_perf_update_at=0.0;self._current_lap_cache=None
            self._reset_live_performance()
            self._validation_prev_zone_id=None;self._validation_prev_phase=None;self._validation_prev_corner_id=None;self._validation_pre_missed=set()
            # Critical: discard the pre-line distance so the clean S/F anchor is
            # not interpreted by the generic wrap detector as a completed lap.
            self._last_observed_distance=None
            self._last_observed_session_time=None
            self.validation.state_transition(
                "first_timed_lap_anchor",lap=lap,distance_m=d,session_time_s=session_time,
                reason="startup_preline_rebased",carried_pre_zones=tuple(sorted(carried)),
            )

        # Preserve the authoritative validity state of the lap being observed.
        # Invalidity is sticky for that lap.  Crucially this is sampled only while
        # the packet still belongs to self._lap; after the lap number advances the
        # current LapData validity belongs to the new lap and must not be applied
        # retroactively to the lap we are finalizing.
        if isinstance(lap,int) and lap==self._lap and getattr(lap_state,"lap_valid",True) is False:
            self._lap_valid=False

        # Replay/live data-quality gate: a physically impossible forward distance
        # jump is a seek/missing-packet discontinuity, not dozens of missed
        # corners. Suppress coaching for the remainder of that logical lap rather
        # than generating stale PRE/POST calls from corrupted progression.
        if (model is not None and isinstance(lap,int) and lap==self._lap and _num(d)
                and _num(self._last_observed_distance) and _num(session_time) and _num(self._last_observed_session_time)):
            dd=float(d)-float(self._last_observed_distance)
            dt=float(session_time)-float(self._last_observed_session_time)
            jump_limit=max(750.0,0.18*float(model.track_length_m))
            implied=(dd/dt) if dt>0 else float("inf")
            if dd>jump_limit and 0.0<dt<15.0 and implied>120.0:
                self._compromised_lap=lap
                self.validation.state_transition(
                    "telemetry_discontinuity",lap=lap,distance_m=float(d),session_time_s=session_time,
                    reason="impossible_forward_distance_jump",previous_distance_m=self._last_observed_distance,
                    previous_session_time_s=self._last_observed_session_time,distance_jump_m=dd,delta_time_s=dt,implied_speed_mps=implied,
                )
                self._reset_live_performance()
                self._last_observed_distance=float(d);self._last_observed_session_time=float(session_time)
                return []
        if isinstance(lap,int) and self._compromised_lap==lap:
            self._last_observed_distance=float(d) if _num(d) else self._last_observed_distance
            self._last_observed_session_time=float(session_time) if _num(session_time) else self._last_observed_session_time
            return []

        # V1.1.0.13: detect the S/F wrap independently of EA's current_lap
        # increment. This is required on the final race lap, where current_lap
        # may remain unchanged after the chequered flag, and also prevents a few
        # post-line packets from contaminating the previous lap on normal laps.
        if (model is not None and isinstance(lap,int) and lap==self._lap and _num(d)
                and self._distance_wrapped(self._last_observed_distance,d,model.track_length_m)):
            boundary_time=getattr(lap_state,"previous_lap_time_s",None)
            if not _num(boundary_time):
                boundary_time=self._last_lap_time_s
            self._finalize_lap_boundary(model,boundary_time)
            if self._is_final_lap(session,lap_state):
                self.validation.finish_lap(
                    reason="final_lap_distance_wrap",zone_attribution=self._zone_attribution,
                    distance_status=self._distance_status_payload,
                    first_delta_s=self._first_delta_s,last_delta_s=self._last_delta_s,
                )
                self._v202_lap_result=self._v202_accumulator.finalize_lap(
                    lap_number=lap, eligible_corner_count=len(model.physical_corners),
                    lap_valid=(self._compromised_lap!=lap and self._lap_valid is not False),
                )
                if isinstance(self._v202_lap_result,dict) and _num(session_time):
                    self._v202_lap_result["created_session_s"]=float(session_time)
                    self._v202_lap_result["expires_session_s"]=float(session_time)+8.0
                self._finished_session_hold_uid=session_uid if session_uid is not None else (self._validation_run_key or "NOUID")
                self._last_observed_distance=float(d)
                return []
            self._awaiting_lap_increment_from=lap
            self._last_observed_distance=float(d)
            return []

        if self._awaiting_lap_increment_from is not None and lap==self._awaiting_lap_increment_from:
            self._last_observed_distance=float(d) if _num(d) else self._last_observed_distance
            return []

        if isinstance(lap,int) and lap!=self._lap:
            old_lap=self._lap
            if self._lap is not None:
                # The new LapData packet exposes the authoritative time of the
                # lap that just ended. Add the exact S/F endpoint before summary
                # generation so the final straight and full-lap reconciliation
                # are always complete even when no packet landed at track_length.
                self._finalize_lap_boundary(model,getattr(lap_state,"previous_lap_time_s",None)) if model is not None else None
                self.validation.finish_lap(
                    reason="lap_advanced",zone_attribution=self._zone_attribution,
                    distance_status=self._distance_status_payload,
                    first_delta_s=self._first_delta_s,last_delta_s=self._last_delta_s,
                )
                self._v202_lap_result=self._v202_accumulator.finalize_lap(
                    lap_number=old_lap, eligible_corner_count=(len(model.physical_corners) if model is not None else 0),
                    lap_valid=(self._compromised_lap!=old_lap and self._lap_valid is not False),
                )
                if isinstance(self._v202_lap_result,dict) and _num(session_time):
                    self._v202_lap_result["created_session_s"]=float(session_time)
                    self._v202_lap_result["expires_session_s"]=float(session_time)+8.0
            carried=set(self._next_lap_pre_spoken) if isinstance(old_lap,int) and lap==old_lap+1 else set()
            self._next_lap_pre_spoken.clear();self._awaiting_lap_increment_from=None
            self._pre_last_block_reason.clear();self._pre_block_counts.clear()
            self._lap=lap;self._lap_started_clean=bool(start_anchor);self._lap_valid=(getattr(lap_state,"lap_valid",True) is not False);self._compromised_lap=None;self._v202_accumulator.begin_lap(lap);self._pre_spoken=set(carried);self._post_spoken.clear();self._gain_loss_voice_spoken.clear();self._straight_spoken.clear();self._straight_pending.clear();self._diagnoses.clear();self._last_diagnosis=None;self._straight_last_diagnosis=None;self._v2_scored.clear();self._live_corner_result=None
            self._pre_not_applicable.clear();self._post_not_applicable.clear();self._gain_loss_voice_not_applicable.clear()
            self._validation_control_state=(bool(self.voice_enabled),bool(self.pre_enabled),bool(self.post_enabled),bool(self.gain_loss_enabled),bool(self.gain_loss_voice_enabled))
            self._last_perf_distance=None;self._last_perf_update_at=0.0;self._current_lap_cache=None
            self._reset_live_performance()
            self._validation_prev_zone_id=None;self._validation_prev_phase=None;self._validation_prev_corner_id=None;self._validation_pre_missed=set()
            if model is not None:
                self.validation.begin_lap(lap,distance_m=d,session_time_s=session_time)
                self.validation.state_transition(
                    "coach_config",lap=lap,distance_m=d,session_time_s=session_time,
                    voice_enabled=bool(self.voice_enabled),pre_enabled=bool(self.pre_enabled),
                    post_enabled=bool(self.post_enabled),gain_loss_enabled=bool(self.gain_loss_enabled),gain_loss_voice_enabled=bool(self.gain_loss_voice_enabled),
                )
        if model is None or not model.coaching_zones or not _num(d):
            self._active_zone_id=None;self._active_phase=None;return []

        self._last_observed_distance=float(d)
        self._last_observed_session_time=float(session_time) if _num(session_time) else self._last_observed_session_time

        zones=model.coaching_zones
        self._sync_runtime_feature_state(zones,lap,d,session_time)
        active=self._zone_for_distance(zones,float(d));self._active_zone_id=active.zone_id if active else None;self._active_phase=self._phase(active,float(d)) if active else None
        physical=self._physical_corner_for_distance(model.physical_corners,float(d))
        physical_id=int(physical.corner_id) if physical is not None else None

        # Record exact state transitions independently from CoachingZone grouping.
        # This lets one trace prove both T1..Tn physical order and Z1..Zn coach order.
        if self._active_zone_id!=self._validation_prev_zone_id:
            if self._validation_prev_zone_id is not None:
                self.validation.state_transition("zone_exit",lap=lap,distance_m=float(d),session_time_s=session_time,zone_id=self._validation_prev_zone_id)
            if active is not None:
                self.validation.state_transition("zone_enter",lap=lap,distance_m=float(d),session_time_s=session_time,zone_id=active.zone_id,label=active.public_label,corner_ids=tuple(active.corner_ids))
            self._validation_prev_zone_id=self._active_zone_id
            self._validation_prev_phase=None
        if physical_id!=self._validation_prev_corner_id:
            if self._validation_prev_corner_id is not None:
                self.validation.state_transition("physical_corner_exit",lap=lap,distance_m=float(d),session_time_s=session_time,corner_id=self._validation_prev_corner_id)
            if physical is not None:
                self.validation.state_transition("physical_corner_enter",lap=lap,distance_m=float(d),session_time_s=session_time,corner_id=physical_id,label=physical.label,direction=physical.direction)
            self._validation_prev_corner_id=physical_id
        if active is not None and self._active_phase!=self._validation_prev_phase:
            self.validation.state_transition("phase_change",lap=lap,distance_m=float(d),session_time_s=session_time,zone_id=active.zone_id,label=active.public_label,phase=self._active_phase)
            self._validation_prev_phase=self._active_phase

        self._update_incremental_performance(model,lap_state,float(d))
        telem=getattr(player,"telemetry",None) if player is not None else None
        self.validation.sample(
            lap=lap,distance_m=float(d),session_time_s=session_time,
            lap_time_s=getattr(lap_state,"current_lap_time_s",None),lap_valid=getattr(lap_state,"lap_valid",None),
            speed_kph=speed,brake=getattr(telem,"brake",None),throttle=getattr(telem,"throttle",None),steering=getattr(telem,"steering",None),gear=getattr(telem,"gear",None),
            active_zone_id=(active.zone_id if active else None),active_zone_label=(active.public_label if active else None),active_corner_ids=(tuple(active.corner_ids) if active else ()),phase=self._active_phase,
            physical_corner_id=physical_id,reference_time_s=self._reference_value_at(float(d),"t"),reference_speed_kph=self._reference_value_at(float(d),"speed"),
            delta_s=self._live_delta_at(float(d)),distance_model_available=bool(self._distance_model.get("available")),
            input_telemetry_trusted=bool((model.quality or {}).get("input_telemetry_trusted",True)),
        )

        # V1.3.0.2: DMG COACH is the authoritative live CORNER COACH damage gate.
        # Keep map/progress/performance measurement alive, but suppress PRE, POST and
        # G/L voice while significant damage is present unless the user explicitly
        # enables the override.  Passed targets are marked not-applicable so turning
        # the override on later never back-fills stale calls.
        damage_blocked=bool(self._significant_damage_present(state) and not self.damage_coaching_enabled)
        if damage_blocked:
            for z in zones:
                if self._pre_target_m(z)<=float(d):
                    self._pre_not_applicable.add(z.zone_id)
                if float(z.end_m)<=float(d):
                    self._post_not_applicable.add(z.zone_id)
                    self._gain_loss_voice_not_applicable.add(z.zone_id)
        if damage_blocked != self._damage_coaching_blocked:
            self.validation.state_transition(
                "damage_coaching_gate",lap=lap,distance_m=float(d),session_time_s=session_time,
                blocked=damage_blocked,override_enabled=bool(self.damage_coaching_enabled),
            )
        self._damage_coaching_blocked=damage_blocked
        if damage_blocked:
            return []

        current=None
        messages=[]
        straight_message=self._straight_message(recorder,model,lap,session_time,now,telem=telem,zones=zones,current_d=d,speed=speed,session=session)
        if straight_message is not None:
            messages.append(straight_message)
        # PRE uses the same lap distance as the map/overlay and the reference brake
        # point (or zone start when a no-brake corner/complex is measured).
        if self.corner_enabled and self.voice_enabled and self.pre_enabled:
            # A target passing without PRE is a first-class validation event. It
            # is deliberately diagnostic only and does not mutate coach state.
            for z in zones:
                target=self._pre_target_m(z)
                if (z.zone_id not in self._pre_spoken and z.zone_id not in self._pre_not_applicable
                        and z.zone_id not in self._validation_pre_missed and target<=float(d)):
                    self._validation_pre_missed.add(z.zone_id)
                    last_reason=self._pre_last_block_reason.get(z.zone_id)
                    reason=(f"target_passed_after_{last_reason}" if last_reason else "target_passed_without_emit")
                    self.validation.pre_decision(
                        lap=lap,zone_id=z.zone_id,event="pre_missed",reason=reason,
                        distance_m=float(d),session_time_s=session_time,target_m=target,label=z.public_label,corner_ids=tuple(z.corner_ids),
                        prior_block_count=int(self._pre_block_counts.get(z.zone_id,0)),
                    )
        if self.corner_enabled and self.voice_enabled and self.pre_enabled and _num(speed) and float(speed)>5.0:
            candidates=[]
            for z in zones:
                target=self._pre_target_m(z)
                if z.zone_id not in self._pre_spoken and z.zone_id not in self._pre_not_applicable and target>float(d):
                    candidates.append((target-float(d),z,target,lap,False))
            # Circular scheduling: on the final straight, T1 of the next lap is
            # a real upcoming target even though its numeric distance is smaller
            # than the current distance. This is what makes flying-lap T1 PRE
            # possible at Melbourne instead of discovering it ~100 m too late.
            if isinstance(lap,int) and self._has_next_lap(session,lap):
                length=float(model.track_length_m)
                for z in zones:
                    if z.zone_id in self._next_lap_pre_spoken:continue
                    target=self._pre_target_m(z)
                    ahead=(length-float(d))+target
                    if ahead>0:
                        candidates.append((ahead,z,target,lap+1,True))
            if candidates:
                distance_ahead,z,target,target_lap,wrapped=min(candidates,key=lambda row:row[0])
                ttb=float(distance_ahead)/(float(speed)/3.6)
                eta=self._target_eta_s(model,float(d),target,speed,wrap=wrapped)
                # Lap 1 can be a standing start while the clean rival reference
                # crosses S/F at full racing speed. Using min(live ETA, rival ETA)
                # here makes the reference ETA unrealistically short and can suppress
                # the very first T1 PRE. Until the first lap has been completed, use
                # the player's live-speed ETA for the current-lap target.
                standing_start_current_lap=(
                    isinstance(lap,int) and lap==1 and target_lap==lap and not wrapped
                    and float(d)<float(target)
                )
                approach_s=ttb if standing_start_current_lap else (min(ttb,float(eta)) if _num(eta) else ttb)
                # Distance sanity guard: a replay seek/teleport can make an already-passed
                # corner look like a next-lap circular target. Never schedule a PRE from
                # implausibly far away even if the time window happens to fit.
                if self.PRE_MIN_S<=approach_s<=self.PRE_MAX_S and float(distance_ahead)<=self.PRE_MAX_DISTANCE_M:
                    brake=float(getattr(telem,"brake",0.0) or 0.0);steering=abs(float(getattr(telem,"steering",0.0) or 0.0))
                    if brake<=0.08 and steering<=0.16:
                        pace_only=bool((model.quality or {}).get("input_telemetry_trusted") is False)
                        if self.coaching_mode == "track_learning":
                            full_text=self._track_learning_pre_text(z,distance_ahead)
                            short_text=self._track_learning_pre_compact(z,distance_ahead)
                            micro_text=self._pre_text_micro(z)
                        else:
                            full_text=self._pre_text(z,float(d),pace_only=pace_only,distance_to_target_m=distance_ahead)
                            short_text=self._pre_text_compact(z,distance_ahead,pace_only=pace_only)
                            micro_text=self._pre_text_micro(z)
                        # PRE is time-critical. Prefer compact; fall back to a micro
                        # cue rather than deleting an otherwise useful instruction.
                        # Full PRE is enrichment only when there is abundant headroom.
                        short_est=estimate_speech_duration_s(short_text)
                        micro_est=estimate_speech_duration_s(micro_text)
                        full_est=estimate_speech_duration_s(full_text)
                        queue_wait=self._speech_wait_s(session_time)
                        # If waiting behind the current coach line would make this
                        # PRE late, the TTS layer will pre-empt that older line.
                        # Model the same decision here so replay and generation
                        # never intentionally queue an impossible PRE.
                        preempt_planned=queue_wait+micro_est+self.SPEECH_FINISH_MARGIN_S>approach_s
                        available=approach_s if preempt_planned else max(0.0,approach_s-queue_wait)
                        if short_est+self.SPEECH_FINISH_MARGIN_S<=available:
                            if full_est+self.SPEECH_FINISH_MARGIN_S+2.00<=available:
                                choice=(full_text,full_est,"full")
                            else:
                                choice=(short_text,short_est,"compact")
                        elif micro_est+self.SPEECH_FINISH_MARGIN_S<=available:
                            choice=(micro_text,micro_est,"micro")
                        else:
                            choice=None
                        if choice is None:
                            # Physically impossible to finish a useful cue before the
                            # target. Mark it handled so it cannot become late. The
                            # validation trace preserves the reason for acceptance.
                            if wrapped:self._next_lap_pre_spoken.add(z.zone_id)
                            else:self._pre_spoken.add(z.zone_id)
                            self.validation.pre_decision(
                                lap=lap,zone_id=z.zone_id,event="pre_suppressed",reason="no_airtime_before_entry",
                                distance_m=float(d),session_time_s=session_time,target_m=target,target_lap=target_lap,circular=wrapped,
                                distance_to_target_m=distance_ahead,ttb_s=approach_s,label=z.public_label,corner_ids=tuple(z.corner_ids),
                                required_s=micro_est,compact_required_s=short_est,brake=brake,steering=steering,
                                queue_wait_s=queue_wait,preempt_planned=preempt_planned,visual_text=micro_text,
                            )
                            return []
                        text,est,variant=choice
                        reserved_start,reserved_end=self._reserve_speech("PRE",z.zone_id,session_time,est,preempt=preempt_planned)
                        if wrapped:self._next_lap_pre_spoken.add(z.zone_id)
                        else:self._pre_spoken.add(z.zone_id)
                        event="pre_emit_next_lap" if wrapped else "pre_emit"
                        self.validation.pre_decision(
                            lap=lap,zone_id=z.zone_id,event=event,distance_m=float(d),session_time_s=session_time,
                            target_m=target,target_lap=target_lap,circular=wrapped,distance_to_target_m=distance_ahead,
                            ttb_s=approach_s,label=z.public_label,corner_ids=tuple(z.corner_ids),text=text,brake=brake,steering=steering,
                            speech_variant=variant,estimated_duration_s=est,deadline_in_s=approach_s,queue_wait_s=queue_wait,
                            preempt_planned=preempt_planned,reserved_start_session_s=reserved_start,reserved_end_session_s=reserved_end,
                        )
                        messages.append(EngineerMessage(
                            f"corner:pre:{target_lap}:{z.zone_id}",Priority.COACHING,text,now,session_time,
                            deadline_at_monotonic_s=now+approach_s,estimated_duration_s=est,
                        ))
                        self._pre_last_block_reason.pop(z.zone_id,None); self._pre_block_counts.pop(z.zone_id,None)
                        return messages
                    reason="brake_active" if brake>0.08 else "steering_active"
                    self._pre_last_block_reason[z.zone_id]=reason
                    self._pre_block_counts[z.zone_id]=int(self._pre_block_counts.get(z.zone_id,0))+1
                    self.validation.pre_decision(
                        lap=lap,zone_id=z.zone_id,event="pre_blocked",reason=reason,distance_m=float(d),session_time_s=session_time,
                        target_m=target,target_lap=target_lap,circular=wrapped,distance_to_target_m=distance_ahead,
                        ttb_s=approach_s,label=z.public_label,corner_ids=tuple(z.corner_ids),brake=brake,steering=steering,
                    )
        elif self.voice_enabled and self.pre_enabled and _num(speed) and float(speed)<=5.0:
            # One low-speed record per current upcoming zone is sufficient.
            future=[z for z in zones if z.zone_id not in self._pre_spoken and z.zone_id not in self._pre_not_applicable and self._pre_target_m(z)>float(d)]
            if future:
                z=min(future,key=self._pre_target_m)
                self.validation.pre_decision(lap=lap,zone_id=z.zone_id,event="pre_blocked",reason="speed_too_low",distance_m=float(d),session_time_s=session_time,speed_kph=speed)

        # V2.0.1 LIVE CORNER INTELLIGENCE: publish per PHYSICAL corner, not per
        # multi-turn CoachingZone.  A zone such as Melbourne T1-T2 used to delay
        # the T1 card until T2 had also finished.  Use the already-compiled
        # physical boundaries and the same deterministic diagnosis pipeline so
        # the card becomes available on the first sampled point past each turn.
        if self.corner_enabled and self.coaching_mode != "track_learning" and self._distance_model.get("available"):
            for boundary in self._performance_boundaries:
                cid=boundary.get("corner_id")
                if not _num(cid):continue
                score_key=f"T{int(cid)}"
                if score_key in self._v2_scored:continue
                corner_end=boundary.get("end_m")
                if not _num(corner_end):continue
                after=float(d)-float(corner_end)
                if after < 0.0:continue
                if after > self.POST_MAX_AFTER_M:
                    self._v2_scored.add(score_key);continue
                # Incremental timing is updated immediately above from the same
                # latest state. Do not wait for the voice POST safety distance.
                if not _num(self._last_perf_distance) or float(self._last_perf_distance) < float(corner_end):continue
                current=self._current_lap(recorder,state)
                if current is None:continue
                live_zone=self._live_physical_corner_zone(model,boundary)
                if live_zone is None:continue
                diag=self._diagnose(live_zone,current,reference,self._diagnosis_model_for_zone(live_zone))
                self._publish_v201_corner_result(live_zone,diag,session_time)
                self._v2_scored.add(score_key)

        # POST is generated once the exact zone just driven has been exited.
        # Expiry is processed even when timing data is not yet available so a replay
        # seek can never leave an old corner armed for later speech.
        if self.corner_enabled and self.voice_enabled and self.post_enabled and self.coaching_mode != "track_learning":
            for z in zones:
                if z.zone_id in self._post_spoken or z.zone_id in self._post_not_applicable:continue
                after=float(d)-float(z.end_m)
                if after < self.POST_MIN_AFTER_M:continue
                if after > self.POST_MAX_AFTER_M:
                    self._post_spoken.add(z.zone_id)
                    self.validation.post_decision(
                        lap=lap,zone_id=z.zone_id,event="post_expired",reason="post_window_passed",
                        distance_m=float(d),session_time_s=session_time,after_zone_m=after,label=z.public_label,corner_ids=tuple(z.corner_ids),
                    )
                    continue
                if not self._distance_model.get("available"):
                    self.validation.post_decision(lap=lap,zone_id=z.zone_id,event="post_blocked",reason="distance_model_unavailable",distance_m=float(d),session_time_s=session_time,after_zone_m=after)
                    continue
                # Incremental timing must include the zone exit. Build the richer
                # input trace only once, at POST time, instead of throughout the lap.
                if not _num(self._last_perf_distance) or float(self._last_perf_distance) < float(z.end_m):
                    self.validation.post_decision(lap=lap,zone_id=z.zone_id,event="post_blocked",reason="timing_not_past_zone_exit",distance_m=float(d),session_time_s=session_time,after_zone_m=after,last_perf_distance_m=self._last_perf_distance)
                    continue
                current=self._current_lap(recorder,state)
                if current is None:
                    self.validation.post_decision(lap=lap,zone_id=z.zone_id,event="post_blocked",reason="current_lap_trace_unavailable",distance_m=float(d),session_time_s=session_time,after_zone_m=after)
                    continue
                existing=self._diagnoses.get(z.zone_id)
                diag=Diagnosis(**existing) if isinstance(existing,dict) else self._diagnose(z,current,reference,self._diagnosis_model_for_zone(z))
                self._diagnoses[z.zone_id]=to_dict(diag);self._last_diagnosis=to_dict(diag)
                brake=float(getattr(telem,"brake",0.0) or 0.0);steering=abs(float(getattr(telem,"steering",0.0) or 0.0))
                safe=brake<=0.08 and steering<=0.16
                if safe:
                    full_text,short_text,micro_text=self._post_text_with_memory(z,diag)
                    full_est=estimate_speech_duration_s(full_text);short_est=estimate_speech_duration_s(short_text);micro_est=estimate_speech_duration_s(micro_text)
                    next_pre=self._next_pre_context(model,zones,z,float(d),speed,session,lap)
                    airtime=float("inf")
                    if isinstance(next_pre,dict):
                        airtime=max(0.0,float(next_pre["eta_s"])-float(next_pre["reserved_pre_s"])-self.PRE_POST_GAP_S)
                    queue_wait=self._speech_wait_s(session_time)
                    usable=(airtime-queue_wait) if math.isfinite(airtime) else float("inf")
                    # POST never pre-empts. Prefer compact as the normal race-time
                    # contract; use a rich sentence only with substantial spare
                    # channel time, then fall back to a micro result.
                    if not math.isfinite(usable):
                        choice=(short_text,short_est,"compact")
                    elif full_est+self.SPEECH_FINISH_MARGIN_S+2.0<=usable:
                        choice=(full_text,full_est,"full")
                    elif short_est+self.SPEECH_FINISH_MARGIN_S<=usable:
                        choice=(short_text,short_est,"compact")
                    elif micro_est+self.SPEECH_FINISH_MARGIN_S<=usable:
                        choice=(micro_text,micro_est,"micro")
                    else:
                        choice=None
                    if choice is None or usable<self.POST_MIN_SPEAKABLE_S:
                        self._post_spoken.add(z.zone_id)
                        self.validation.post_decision(
                            lap=lap,zone_id=z.zone_id,event="post_suppressed",reason="no_airtime_before_next_pre_or_queue",
                            distance_m=float(d),session_time_s=session_time,after_zone_m=after,label=z.public_label,corner_ids=tuple(z.corner_ids),
                            diagnosis=to_dict(diag),brake=brake,steering=steering,airtime_budget_s=(airtime if math.isfinite(airtime) else None),
                            queue_wait_s=queue_wait,usable_airtime_s=(usable if math.isfinite(usable) else None),visual_text=micro_text,
                            full_duration_s=full_est,compact_duration_s=short_est,micro_duration_s=micro_est,next_pre_zone_id=(next_pre["zone"].zone_id if isinstance(next_pre,dict) else None),
                            next_pre_eta_s=(next_pre.get("eta_s") if isinstance(next_pre,dict) else None),reserved_pre_s=(next_pre.get("reserved_pre_s") if isinstance(next_pre,dict) else None),
                        )
                        # Preserve the factual result on-screen even though it is
                        # intentionally not spoken. This directly prevents the
                        # 'missing text' regression while keeping radio safe.
                        return [EngineerMessage(
                            f"corner:visual:post:{lap}:{z.zone_id}:{diag.primary_code}",Priority.COACHING,micro_text,now,session_time,
                            estimated_duration_s=0.0,speak=False,
                        )]
                    text,est,variant=choice
                    reserved_start,reserved_end=self._reserve_speech("POST",z.zone_id,session_time,est,preempt=False)
                    self._post_spoken.add(z.zone_id)
                    # Deadline uses remaining wall-clock airtime from now; the
                    # game-time reservation above guarantees the queued start is
                    # already accounted for.
                    deadline=(now+airtime) if math.isfinite(airtime) else None
                    self.validation.post_decision(
                        lap=lap,zone_id=z.zone_id,event="post_emit",distance_m=float(d),session_time_s=session_time,
                        after_zone_m=after,label=z.public_label,corner_ids=tuple(z.corner_ids),diagnosis=to_dict(diag),text=text,brake=brake,steering=steering,
                        speech_variant=variant,estimated_duration_s=est,airtime_budget_s=(airtime if math.isfinite(airtime) else None),queue_wait_s=queue_wait,
                        reserved_start_session_s=reserved_start,reserved_end_session_s=reserved_end,
                        next_pre_zone_id=(next_pre["zone"].zone_id if isinstance(next_pre,dict) else None),next_pre_eta_s=(next_pre.get("eta_s") if isinstance(next_pre,dict) else None),
                    )
                    messages.append(EngineerMessage(
                        f"corner:post:{lap}:{z.zone_id}:{diag.primary_code}",Priority.COACHING,text,now,session_time,
                        deadline_at_monotonic_s=deadline,estimated_duration_s=est,
                    ))
                    return messages
                reason="brake_active" if brake>0.08 else "steering_active"
                self.validation.post_decision(
                    lap=lap,zone_id=z.zone_id,event="post_blocked",reason=reason,distance_m=float(d),session_time_s=session_time,
                    after_zone_m=after,label=z.public_label,corner_ids=tuple(z.corner_ids),diagnosis=to_dict(diag),brake=brake,steering=steering,
                )

        # Independent low-priority gain/loss voice mode. It is evaluated only
        # after PRE/POST have had first claim on the one CORNER COACH radio.
        gl_message=self._gain_loss_voice_message(model,zones,session,lap,float(d),speed,session_time,now)
        if gl_message is not None:
            messages.append(gl_message)
        return messages

    @staticmethod
    def _gain_loss_voice_text(zone:CoachingZone, net_loss_s:float) -> str:
        label=_spoken_label(zone)
        value=abs(float(net_loss_s))
        # One-decimal tenths are fast to understand at racing speed; use hundredths
        # only for sub-tenth changes so a meaningful 0.06 s gain is not rounded away.
        amount=f"{value:.2f}" if value < 0.10 else f"{value:.1f}"
        verb="lost" if net_loss_s > 0 else "gained"
        return f"{label}, {verb} {amount} seconds."

    def _gain_loss_voice_message(self, model:ReferenceTrace, zones, session, lap:Any, d:float, speed:Any, session_time:Any, now:float):
        """Return one low-priority completed-zone gain/loss voice cue when safe.

        This mode is intentionally independent from MAP G/L.  It never changes
        the map layer, never invents rival inputs, and never steals airtime from
        a pending PRE.  Small changes inside the deterministic deadband remain
        visual-only to avoid radio spam.
        """
        if not (self.voice_enabled and self.gain_loss_voice_enabled):
            return None
        rows={str(r.get("zone_id")):r for r in self._live_zone_rows if isinstance(r,dict)}
        for z in zones:
            zid=z.zone_id
            if zid in self._gain_loss_voice_spoken or zid in self._gain_loss_voice_not_applicable:
                continue
            row=rows.get(zid)
            if not row or not bool(row.get("complete")):
                continue
            net=row.get("net_loss_s")
            if not _num(net):
                self._gain_loss_voice_spoken.add(zid)
                continue
            net=float(net)
            # 0.05 s is below normal spoken precision and would create excessive
            # chatter.  Keep it on the map but do not use radio airtime.
            if abs(net) < 0.05:
                self._gain_loss_voice_spoken.add(zid)
                self.validation.state_transition("gain_loss_voice_suppressed",lap=lap,zone_id=zid,label=z.public_label,distance_m=d,session_time_s=session_time,net_loss_s=net,reason="deadband")
                continue
            text=self._gain_loss_voice_text(z,net)
            est=estimate_speech_duration_s(text)
            queue_wait=self._speech_wait_s(session_time)
            next_pre=self._next_pre_context(model,zones,z,d,speed,session,lap)
            airtime=float("inf")
            if isinstance(next_pre,dict):
                airtime=max(0.0,float(next_pre["eta_s"])-float(next_pre["reserved_pre_s"])-self.PRE_POST_GAP_S)
            usable=(airtime-queue_wait) if math.isfinite(airtime) else float("inf")
            self._gain_loss_voice_spoken.add(zid)
            if queue_wait>0.05 or (math.isfinite(usable) and est+self.SPEECH_FINISH_MARGIN_S>usable):
                self.validation.state_transition("gain_loss_voice_suppressed",lap=lap,zone_id=zid,label=z.public_label,distance_m=d,session_time_s=session_time,net_loss_s=net,reason="radio_busy_or_pre_protected",queue_wait_s=queue_wait,usable_airtime_s=(usable if math.isfinite(usable) else None),estimated_duration_s=est,next_pre_zone_id=(next_pre["zone"].zone_id if isinstance(next_pre,dict) else None))
                return EngineerMessage(f"corner:visual:gainloss:{lap}:{zid}",Priority.COACHING,text,now,session_time,estimated_duration_s=0.0,speak=False)
            reserved_start,reserved_end=self._reserve_speech("GAINLOSS",zid,session_time,est,preempt=False)
            deadline=(now+airtime) if math.isfinite(airtime) else None
            self.validation.state_transition("gain_loss_voice_emit",lap=lap,zone_id=zid,label=z.public_label,distance_m=d,session_time_s=session_time,net_loss_s=net,text=text,estimated_duration_s=est,reserved_start_session_s=reserved_start,reserved_end_session_s=reserved_end,next_pre_zone_id=(next_pre["zone"].zone_id if isinstance(next_pre,dict) else None))
            return EngineerMessage(f"corner:gainloss:{lap}:{zid}",Priority.COACHING,text,now,session_time,deadline_at_monotonic_s=deadline,estimated_duration_s=est)
        return None

    @staticmethod
    def _straight_samples(lap, start_m:float, end_m:float):
        rows=[]
        for raw_d,row in ((lap or {}).get("_samples") or {}).items():
            try:d=float(raw_d)
            except (TypeError,ValueError):
                d=_value(row,"d")
            if not _num(d) or float(d)<start_m or float(d)>end_m:continue
            rows.append((float(d),row))
        return sorted(rows,key=lambda x:x[0])

    def _straight_message(self, recorder, model, lap, session_time, now, *, telem=None, zones=(), current_d=None, speed=None, session=None):
        """Queue completed-straight diagnoses and speak only in a safe radio window.

        Analysis completion is immediate; speech is delayed until braking/steering are
        low and the next Corner Coach PRE reservation is protected. This prevents a
        straight POST from masking the more time-critical upcoming corner instruction.
        """
        if not self.straight_enabled:
            return None
        # Capture each newly completed straight exactly once.
        for seg in self._live_segments:
            if seg.get("segment_kind")!="straight" or not seg.get("complete"):continue
            num=int(seg.get("number",0))
            if num in self._straight_spoken or any(int(x.get("straight",-1))==num for x in self._straight_pending):continue
            net=seg.get("net_loss_s");a=float(seg.get("start_m",0.0));b=float(seg.get("end_m",a))
            try:
                samples=getattr(recorder,"samples",{})
                current={"_samples":dict(samples)} if samples else None
            except Exception: current=None
            cur=self._straight_samples(current,a,b);ref=[(float(r.get("d")),r) for r in self._reference_samples if _num(r.get("d")) and a<=float(r.get("d"))<=b]
            def vals(rows,key):return [float(_value(r,key)) for _,r in rows if _num(_value(r,key))]
            cs,rs=vals(cur,"speed"),vals(ref,"speed")
            avg_delta=(sum(cs)/len(cs)-sum(rs)/len(rs)) if cs and rs else None
            top_delta=(max(cs)-max(rs)) if cs and rs else None
            cur_end=_speed_at(cur,b,15.0);ref_end=_speed_at(ref,b,15.0);exit_delta=(cur_end-ref_end) if _num(cur_end) and _num(ref_end) else None
            trusted=bool((model.quality or {}).get("input_telemetry_trusted",True))
            def frac(rows,key,pred):
                vv=[_value(r,key) for _,r in rows if _value(r,key) is not None]
                return (sum(1 for v in vv if pred(v))/len(vv)) if vv else None
            throttle_delta=drs_delta=ers_delta=None
            if trusted:
                ct=frac(cur,"throttle",lambda v:_num(v) and float(v)>=0.98);rt=frac(ref,"throttle",lambda v:_num(v) and float(v)>=0.98)
                throttle_delta=(ct-rt) if _num(ct) and _num(rt) else None
                cd=frac(cur,"s_mode_straight",lambda v:v is True);rd=frac(ref,"s_mode_straight",lambda v:v is True)
                drs_delta=(cd-rd) if _num(cd) and _num(rd) else None
                ce=vals(cur,"ers_j");re=vals(ref,"ers_j")
                if len(ce)>=2 and len(re)>=2:ers_delta=(ce[-1]-ce[0])-(re[-1]-re[0])
            diagnosis={"straight":num,"label":f"Straight {num}","start_m":a,"end_m":b,"net_loss_s":net,"avg_speed_delta_kph":avg_delta,"top_speed_delta_kph":top_delta,"exit_speed_delta_kph":exit_delta,"full_throttle_fraction_delta":throttle_delta,"s_mode_fraction_delta":drs_delta,"ers_usage_delta_j":ers_delta}
            if _num(net):
                netf=float(net)
                if netf>0.05:
                    detail=None
                    if _num(throttle_delta) and float(throttle_delta)<-0.08:detail="full throttle was lower than the reference"
                    elif _num(drs_delta) and float(drs_delta)<-0.20:detail="straight mode was available less than the reference"
                    elif _num(top_delta) and float(top_delta)<-4.0:detail=f"top speed was {abs(float(top_delta)):.0f} kph lower"
                    elif _num(avg_delta) and float(avg_delta)<-3.0:detail=f"average speed was {abs(float(avg_delta)):.0f} kph lower"
                    elif _num(exit_delta) and float(exit_delta)<-4.0:detail=f"end speed was {abs(float(exit_delta)):.0f} kph lower"
                    text=f"Straight {num}, lost {netf:.2f} seconds" + (f". {detail}." if detail else ".")
                elif netf<-0.05:text=f"Straight {num}, gained {abs(netf):.2f} seconds."
                else:text=f"Straight {num}, matched the reference."
            else:text=f"Straight {num}, comparison unavailable."
            # Long-session memory: repeat the same measured issue compactly, while
            # re-arming the full explanation when the loss or cause materially changes.
            if _num(net):
                cause=("throttle" if _num(throttle_delta) and float(throttle_delta)<-0.08 else "smode" if _num(drs_delta) and float(drs_delta)<-0.20 else "top_speed" if _num(top_delta) and float(top_delta)<-4.0 else "avg_speed" if _num(avg_delta) and float(avg_delta)<-3.0 else "exit_speed" if _num(exit_delta) and float(exit_delta)<-4.0 else "time")
                previous=self._straight_repeat_signature.get(num);loss=float(net)
                repeated=bool(previous is not None and previous[0]==cause and previous[1] is not None and abs(loss-float(previous[1]))<0.080)
                count=(int(self._straight_repeat_count.get(num,0))+1) if repeated else 1
                self._straight_repeat_count[num]=count;self._straight_repeat_signature[num]=(cause,loss)
                if repeated and count%4 and loss>0.05:
                    text=f"Straight {num}, lost {loss:.2f} seconds."
            diagnosis["primary_text"]=text
            self._straight_last_diagnosis=diagnosis;self._straight_diagnoses[num]=diagnosis
            self._straight_pending.append(dict(diagnosis,text=text,created_session_s=session_time))
            self.validation.state_transition("straight_complete",lap=lap,distance_m=(float(current_d) if _num(current_d) else b),segment_number=num,session_time_s=session_time,**diagnosis)
        if not (self.voice_enabled and self.straight_voice_enabled) or not self._straight_pending:return None
        if telem is not None:
            brake=float(getattr(telem,"brake",0.0) or 0.0);steering=abs(float(getattr(telem,"steering",0.0) or 0.0))
            if brake>0.08 or steering>0.16:return None
        item=self._straight_pending[0];text=str(item.get("text") or "");est=estimate_speech_duration_s(text)
        if not text:return None
        if _num(current_d) and _num(speed) and zones and self.corner_enabled and self.pre_enabled:
            nxt=self._next_zone(zones,float(current_d))
            if nxt is not None and nxt.zone_id not in self._pre_spoken and nxt.zone_id not in self._pre_not_applicable:
                target=self._pre_target_m(nxt);eta=self._target_eta_s(model,float(current_d),target,speed,wrap=False)
                if _num(eta):
                    pace_only=bool((model.quality or {}).get("input_telemetry_trusted") is False)
                    pre_est=estimate_speech_duration_s(self._pre_text_compact(nxt,max(0.0,target-float(current_d)),pace_only=pace_only))+self.SPEECH_FINISH_MARGIN_S
                    airtime=max(0.0,float(eta)-pre_est-self.PRE_POST_GAP_S)
                    if est+self.SPEECH_FINISH_MARGIN_S>airtime:return None
        if self._speech_wait_s(session_time)>0.05:return None
        self._straight_pending.pop(0);num=int(item.get("straight",0));self._straight_spoken.add(num)
        self._reserve_speech("STRAIGHT",f"S{num}",session_time,est,preempt=False)
        self.validation.state_transition("straight_coach_emit",lap=lap,distance_m=(float(current_d) if _num(current_d) else item.get("end_m")),segment_number=num,label=f"S{num}",session_time_s=session_time,text=text,estimated_duration_s=est)
        return EngineerMessage(f"straight:post:{lap}:S{num}",Priority.COACHING,text,now,session_time,estimated_duration_s=est)

    def set_coaching_mode(self, mode:str) -> None:
        self.coaching_mode=str(mode or "auto")

    @staticmethod
    def _live_primary_text(diag:Diagnosis) -> str:
        m=diag.measurements or {}
        code=str(diag.primary_code or "")
        if code=="brake_early" and _num(m.get("brake_point_delta_m")):return f"BRAKE {abs(float(m['brake_point_delta_m'])):.0f} m EARLY"
        if code=="brake_late" and _num(m.get("brake_point_delta_m")):return f"BRAKE {abs(float(m['brake_point_delta_m'])):.0f} m LATE"
        if code in {"min_speed_low","apex_speed_low"}:
            v=m.get("apex_speed_delta_kph") if _num(m.get("apex_speed_delta_kph")) else m.get("min_speed_delta_kph")
            if _num(v):return f"MIN SPEED {float(v):+.0f} km/h"
        if code=="throttle_late":
            if _num(m.get("throttle_pickup_delta_s")):return f"THROTTLE +{float(m['throttle_pickup_delta_s']):.2f} s LATE"
            if _num(m.get("throttle_pickup_delta_m")):return f"THROTTLE +{float(m['throttle_pickup_delta_m']):.0f} m LATE"
        if code=="full_throttle_late" and _num(m.get("full_throttle_delta_m")):return f"FULL THROTTLE +{float(m['full_throttle_delta_m']):.0f} m LATE"
        if code=="exit_speed_low" and _num(m.get("exit_speed_delta_kph")):return f"EXIT SPEED {float(m['exit_speed_delta_kph']):+.0f} km/h"
        if diag.primary_text:return str(diag.primary_text).upper()
        if diag.primary_code=="gain" and _num(diag.net_loss_s):return f"GAINED {abs(float(diag.net_loss_s)):.2f} s"
        if diag.primary_code=="match":return "MATCHED REFERENCE"
        return "MEASURED RESULT"


    @staticmethod
    def _live_action_text(diag:Diagnosis) -> str:
        """Return one evidence-backed next-attempt action for the live card.

        This is deliberately downstream of the existing deterministic diagnosis:
        it translates the already-selected dominant issue into an imperative and
        never selects a new cause from the score itself.
        """
        m=diag.measurements or {}
        code=str(diag.primary_code or "")
        if code=="brake_early" and _num(m.get("brake_point_delta_m")):
            return f"BRAKE ~{abs(float(m['brake_point_delta_m'])):.0f} m LATER"
        if code=="brake_late" and _num(m.get("brake_point_delta_m")):
            return f"BRAKE ~{abs(float(m['brake_point_delta_m'])):.0f} m EARLIER"
        if code=="over_braking" and _num(m.get("peak_brake_delta")):
            return f"REDUCE PEAK BRAKE ~{abs(float(m['peak_brake_delta']))*100:.0f}%"
        if code=="brake_release_early" and _num(m.get("brake_release_delta_m")):
            return f"TRAIL BRAKE ~{abs(float(m['brake_release_delta_m'])):.0f} m LONGER"
        if code=="brake_release_late" and _num(m.get("brake_release_delta_m")):
            return f"RELEASE BRAKE ~{abs(float(m['brake_release_delta_m'])):.0f} m EARLIER"
        if code=="coasting_excessive" and _num(m.get("coasting_delta_s")):
            return f"REDUCE COASTING ~{abs(float(m['coasting_delta_s'])):.2f} s"
        if code in {"min_speed_low","apex_speed_low"}:
            v=m.get("apex_speed_delta_kph") if _num(m.get("apex_speed_delta_kph")) else m.get("min_speed_delta_kph")
            if _num(v):return f"CARRY ~{abs(float(v)):.0f} km/h MORE MIN SPEED"
        if code=="throttle_late":
            if _num(m.get("throttle_pickup_delta_s")):
                return f"PICK UP THROTTLE ~{abs(float(m['throttle_pickup_delta_s'])):.2f} s EARLIER"
            if _num(m.get("throttle_pickup_delta_m")):
                return f"PICK UP THROTTLE ~{abs(float(m['throttle_pickup_delta_m'])):.0f} m EARLIER"
        if code=="full_throttle_late" and _num(m.get("full_throttle_delta_m")):
            return f"FULL THROTTLE ~{abs(float(m['full_throttle_delta_m'])):.0f} m EARLIER"
        if code=="exit_speed_low" and _num(m.get("exit_speed_delta_kph")):
            return f"BUILD ~{abs(float(m['exit_speed_delta_kph'])):.0f} km/h MORE EXIT SPEED"
        if code=="turn_in_timing" and _num(m.get("turn_in_delta_m")):
            v=float(m["turn_in_delta_m"])
            return f"TURN IN ~{abs(v):.0f} m {'EARLIER' if v>0 else 'LATER'}"
        if code=="steering_corrections" and _num(m.get("steering_corrections_delta")):
            return f"REMOVE ~{max(1,int(round(abs(float(m['steering_corrections_delta'])))))} STEERING CORRECTION{'S' if abs(float(m['steering_corrections_delta']))>=1.5 else ''}"
        if code=="steering_unsmooth":
            return "SMOOTH THE STEERING INPUT"
        if code=="steering_unwind_slow" and _num(m.get("steering_unwind_delta_s")):
            return f"UNWIND STEERING ~{abs(float(m['steering_unwind_delta_s'])):.2f} s EARLIER"
        if code in {"gain","match"}:
            return "KEEP CURRENT APPROACH"
        return "NO TRUSTED ACTION YET"

    def _live_physical_corner_zone(self, model:ReferenceTrace, boundary:dict[str,Any]) -> CoachingZone | None:
        """Build a lightweight per-physical-corner view from the compiled reference.

        This does not detect new events. It only narrows the already-compiled
        CoachingZone/PhysicalCorner evidence so V2 live feedback can publish at
        the physical corner exit instead of waiting for the end of a multi-turn
        coaching zone.
        """
        cid=boundary.get("corner_id")
        if not _num(cid):
            return None
        cid=int(cid)
        corner=next((c for c in model.physical_corners if int(c.corner_id)==cid),None)
        if corner is None:
            return None
        parent=next((z for z in model.coaching_zones if cid in z.corner_ids),None)
        if parent is None:
            return None
        lo=float(boundary.get("ownership_start_m",corner.start_m));hi=float(boundary.get("ownership_end_m",corner.end_m))
        def inside(value, *, extra=0.0):
            return value if _num(value) and lo-extra <= float(value) <= hi+extra else None
        trusted=next((x for x in self._trusted_turn_metrics_payload if int(x.get("corner_id",-1))==cid),{})
        # Parent pedal events are only assigned to this physical corner when the
        # compiled event actually lies inside its ownership range. That preserves
        # N/A instead of borrowing another turn's brake/throttle point.
        brake=inside(parent.brake_start_m)
        release=inside(parent.brake_release_m)
        throttle=inside(parent.throttle_start_m,extra=40.0)
        full=inside(parent.full_throttle_m,extra=80.0)
        return CoachingZone(
            zone_id=f"LIVE_T{cid}",label=f"T{cid}",corner_ids=(cid,),
            approach_start_m=max(lo,float(corner.start_m)-80.0),
            start_m=float(corner.start_m),end_m=float(corner.end_m),
            brake_start_m=(float(brake) if _num(brake) else None),
            brake_release_m=(float(release) if _num(release) else None),
            apex_m=float(corner.apex_m),
            throttle_start_m=(float(throttle) if _num(throttle) else None),
            full_throttle_m=(float(full) if _num(full) else None),
            reference_min_speed_kph=(float(trusted.get("min_speed_kph")) if _num(trusted.get("min_speed_kph")) else None),
            reference_apex_speed_kph=self._reference_value_at(float(corner.apex_m),"speed"),
            reference_exit_speed_kph=self._reference_value_at(float(corner.end_m),"speed"),
            reference_gear=parent.reference_gear,confidence=parent.confidence,
        )

    def _publish_v201_corner_result(self, zone:CoachingZone, diag:Diagnosis, session_time_s:Any) -> None:
        corner_id=(int(diag.measurements.get("dominant_corner")) if _num((diag.measurements or {}).get("dominant_corner")) else (int(zone.corner_ids[0]) if zone.corner_ids else None))
        score=build_live_corner_score_from_diagnosis(diag,corner_id=corner_id,evidence_prefix="live-v201")
        self._live_corner_result={
            "zone_id":zone.zone_id,"corner_id":corner_id,"label":zone.public_label,
            "score":score.score,"score_status":score.status.value,"grade":score_grade(score.score),
            "confidence":score.confidence,"sample_count":score.sample_count,
            "dominant_issue":diag.primary_code,"primary_text":self._live_primary_text(diag),
            "action_text":self._live_action_text(diag),
            "estimated_loss_s":diag.net_loss_s,
            "brake_point_delta_m":diag.measurements.get("brake_point_delta_m"),
            "brake_release_delta_m":diag.measurements.get("brake_release_delta_m"),
            "peak_brake_delta":diag.measurements.get("peak_brake_delta"),
            "trail_brake_delta_m":diag.measurements.get("trail_brake_delta_m"),
            "turn_in_delta_m":diag.measurements.get("turn_in_delta_m"),
            "full_throttle_delta_m":diag.measurements.get("full_throttle_delta_m"),
            "coasting_delta_s":diag.measurements.get("coasting_delta_s"),
            "steering_corrections_delta":diag.measurements.get("steering_corrections_delta"),
            "steering_smoothness_delta":diag.measurements.get("steering_smoothness_delta"),
            "steering_unwind_delta_s":diag.measurements.get("steering_unwind_delta_s"),
            "max_slip_delta":diag.measurements.get("max_slip_delta"),
            "phase_losses":dict(diag.phase_losses_s or {}),
            "apex_position_delta_m":diag.measurements.get("apex_position_delta_m"),
            "apex_position_trusted":diag.measurements.get("apex_position_trusted",False),
            "apex_position_confidence":diag.measurements.get("apex_position_confidence"),
            "apex_estimate_delta_m":diag.measurements.get("apex_estimate_delta_m"),
            "apex_estimate_trusted":diag.measurements.get("apex_estimate_trusted",False),
            "apex_evidence_method":diag.measurements.get("apex_evidence_method"),
            "apex_speed_delta_kph":diag.measurements.get("apex_speed_delta_kph"),
            "min_speed_delta_kph":diag.measurements.get("min_speed_delta_kph"),
            "throttle_pickup_delta_m":diag.measurements.get("throttle_pickup_delta_m"),
            "throttle_pickup_delta_s":diag.measurements.get("throttle_pickup_delta_s"),
            "exit_speed_delta_kph":diag.measurements.get("exit_speed_delta_kph"),
            "created_session_s":float(session_time_s) if _num(session_time_s) else None,
            "expires_session_s":float(session_time_s)+4.0 if _num(session_time_s) else None,
            "score_model_version":score.score_model_version,
            "dimension_scores":{k:(v.value if v.status is ScoreStatus.AVAILABLE else None) for k,v in score.dimensions.items()},
        }
        self._v202_accumulator.add_corner(self._live_corner_result)

    def status(self,recorder=None,state=None)->dict[str,Any]:
        model=self.reference_model
        d=None;player=None
        if state is not None:
            player=getattr(state,"player",None);lap_state=getattr(player,"lap",None) if player is not None else None;d=getattr(lap_state,"lap_distance_m",None) if lap_state is not None else None
        active=self._zone_for_distance(model.coaching_zones,d) if model is not None and _num(d) else None
        phase=self._phase(active,d) if active is not None else None
        ref_now={}
        if model is not None and _num(d) and self._reference_samples:
            row=self._reference_row_at(float(d))
            ref_now={k:row.get(k) for k in ("speed","brake","throttle","steering","gear")}
        live={}
        if player is not None:
            telem=getattr(player,"telemetry",None)
            live={"speed":getattr(telem,"speed_kph",None),"brake":getattr(telem,"brake",None),"throttle":getattr(telem,"throttle",None),"steering":getattr(telem,"steering",None),"gear":getattr(telem,"gear",None)}
        effective=self.speed_coach_feature_states()

        # UI-R3 presentation-only pre-corner payload.  This is derived from the
        # same compiled CoachingZone / reference authority used by PRE voice; it
        # never changes PRE scheduling, diagnosis, or speech eligibility.
        pre_visual=None
        if model is not None and _num(d) and effective["SPEED"] and effective["CORNER"]:
            zones=tuple(model.coaching_zones or ())
            x=float(d); length=float(model.track_length_m)
            visual_zone=active; wrapped=False
            if visual_zone is None and zones:
                future=[z for z in zones if float(z.approach_start_m)>x]
                if future:
                    visual_zone=min(future,key=lambda z:float(z.approach_start_m))
                else:
                    visual_zone=zones[0]; wrapped=True
            if visual_zone is not None:
                def ahead(target):
                    if not _num(target): return None
                    t=float(target)
                    return max(0.0,(length-x+t) if wrapped and t<x else t-x)
                approach_ahead=ahead(visual_zone.approach_start_m)
                target=self._pre_target_m(visual_zone); target_ahead=ahead(target)
                end_ahead=ahead(visual_zone.end_m)
                raw_phase=self._phase(visual_zone,x) if active is not None else None
                if active is None:
                    phase="FAR"
                else:
                    phase={"APPROACH":"APPROACHING","BRAKE":"BRAKING","ENTRY":"TURN-IN","APEX":"APEX","EXIT":"EXIT","COMPLETE":"EXIT"}.get(raw_phase,raw_phase or "APPROACHING")
                brake_ahead=ahead(visual_zone.brake_start_m if _num(visual_zone.brake_start_m) else visual_zone.start_m)
                gear=visual_zone.reference_gear if isinstance(visual_zone.reference_gear,int) and visual_zone.reference_gear>0 else None
                min_speed=float(visual_zone.reference_min_speed_kph) if _num(visual_zone.reference_min_speed_kph) else None
                throttle_ahead=ahead(visual_zone.throttle_start_m) if _num(visual_zone.throttle_start_m) else None
                if phase=="FAR":
                    primary=None
                    secondary=None
                elif phase=="APPROACHING":
                    primary=(f"BRAKE IN {max(0.0,float(brake_ahead)):.0f} M" if _num(brake_ahead) else "MATCH REFERENCE BRAKE POINT")
                    secondary=(f"GEAR {gear}" if gear else (f"MIN {min_speed:.0f} KM/H" if _num(min_speed) else None))
                elif phase=="BRAKING":
                    primary="BRAKE"
                    secondary=(f"GEAR {gear} • MIN {min_speed:.0f} KM/H" if gear and _num(min_speed) else (f"GEAR {gear}" if gear else (f"MIN {min_speed:.0f} KM/H" if _num(min_speed) else None)))
                elif phase=="TURN-IN":
                    primary="TURN IN"
                    secondary=(f"GEAR {gear} • MIN {min_speed:.0f} KM/H" if gear and _num(min_speed) else (f"GEAR {gear}" if gear else None))
                elif phase=="APEX":
                    primary=(f"MIN {min_speed:.0f} KM/H" if _num(min_speed) else "APEX")
                    secondary="PREPARE EXIT"
                else:
                    primary="EXIT"
                    secondary=("THROTTLE" if throttle_ahead is None or float(throttle_ahead)<=8.0 else f"THROTTLE IN {float(throttle_ahead):.0f} M")
                total=max(1.0,float(visual_zone.end_m)-float(visual_zone.approach_start_m))
                if active is not None:
                    progress=max(0.0,min(1.0,(x-float(visual_zone.approach_start_m))/total))
                else:
                    # Far approach remains deliberately quiet; progress begins only
                    # when the authoritative coaching zone starts.
                    progress=0.0
                ids=tuple(visual_zone.corner_ids or ())
                label=(visual_zone.public_label or (f"T{ids[0]}" if len(ids)==1 else (f"T{ids[0]}–T{ids[-1]}" if ids else "CORNER")))
                confidence=1.0 if bool((model.quality or {}).get("input_telemetry_trusted",True)) else 0.65
                pre_visual={
                    "zone_id":visual_zone.zone_id,"label":label,"corner_ids":ids,"phase":phase,
                    "distance_to_zone_m":approach_ahead,"distance_to_target_m":target_ahead,
                    "progress":progress,"primary_action":primary,"secondary_action":secondary,
                    "reference_gear":gear,"reference_min_speed_kph":min_speed,
                    "confidence":confidence,"input_telemetry_trusted":bool((model.quality or {}).get("input_telemetry_trusted",True)),
                }
        return {
            "enabled":effective["SPEED"],"speed_enabled":effective["SPEED"],"corner_enabled":effective["CORNER"],"straight_enabled":effective["STRAIGHT"],"straight_voice_enabled":effective["SLVOICE"],
            "voice_enabled":bool(self.voice_enabled and effective["SPEED"]),"pre_enabled":effective["CCPRE"],"post_enabled":effective["CCPOST"],"gain_loss_enabled":effective["GAINLOSS"],"gain_loss_voice_enabled":effective["GAINLOSSVOICE"],
            "damage_coaching_enabled":bool(self.damage_coaching_enabled),"damage_coaching_blocked":bool(self._damage_coaching_blocked),
            "reference_ready":model is not None,"track_name":model.track_name if model else None,"quality":model.quality if model else {},
            "zones":self._zones_payload,"physical_corners":self._corners_payload,
            "driving_events":self._events_payload,"trusted_turn_metrics":self._trusted_turn_metrics_payload,
            "active_zone":to_dict(active) if active else None,"active_phase":phase,"pre_visual":pre_visual,
            "lap_distance_m":float(d) if _num(d) else None,"reference_now":ref_now,"live_now":live,"last_diagnosis":self._last_diagnosis,"diagnoses":dict(self._diagnoses),
            "live_corner_result":dict(self._live_corner_result) if isinstance(self._live_corner_result,dict) else None,
            "lap_stint_intelligence":self._v202_accumulator.status(),
            "last_lap_intelligence":dict(self._v202_lap_result) if isinstance(self._v202_lap_result,dict) else None,
            "coaching_mode":self.coaching_mode,
            "straight_last_diagnosis":self._straight_last_diagnosis,"straight_diagnoses":dict(self._straight_diagnoses),
            "zone_attribution":self._zone_attribution if effective["SPEED"] else {"available":False,"zones":[],"straights":[],"segments":[],"reconciliation_error_s":None},
            "distance_performance":self._distance_status_payload if effective["GAINLOSS"] else {"available":False},
            "validation_file":str(self.validation.path) if self.validation.path is not None else None,
            "validation_dropped_records":self.validation.dropped_records,
        }
