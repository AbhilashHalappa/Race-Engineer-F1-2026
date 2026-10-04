"""V0.9.5 measured driving intelligence.

Facts only: records already-observed telemetry, segments measured driving phases,
and compares completed laps. It never predicts future performance.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from bisect import bisect_left
import math
from pathlib import Path
from .event_context import build_event_context
from .track_geometry import canonical_track_name


def _finite(x): return x if isinstance(x,(int,float)) and math.isfinite(x) else None
def _maxabs(xs):
    vals=[abs(x) for x in xs if _finite(x) is not None]
    return max(vals) if vals else None


_TERMINAL_RESULT_STATUS = {3, 4, 5, 6, 7}

def _sample_field(row, key):
    return row.get(key) if isinstance(row, dict) else getattr(row, key, None)

def _samples_have_lap_start(samples, *, max_distance_m=25.0, max_time_s=2.0):
    """True only when the trace contains the start/finish-line beginning of the lap.

    Live/replay source switches can begin halfway around a lap.  Such a partial
    trace must never be stitched to a stored reference or promoted as session best.
    """
    if not samples:
        return False
    rows = samples.values() if isinstance(samples, dict) else samples
    candidates=[]
    for row in rows:
        d=_sample_field(row,'d'); t=_sample_field(row,'t')
        if _finite(d) is not None and _finite(t) is not None:
            candidates.append((float(d), float(t)))
    if not candidates:
        return False
    d,t=min(candidates, key=lambda x:x[0])
    return -1.0 <= d <= max_distance_m and 0.0 <= t <= max_time_s


def _session_finished(state):
    session = getattr(state, "session", None)
    if getattr(session, "ended", False) is True:
        return True
    player = getattr(state, "player", None)
    lap = getattr(player, "lap", None) if player is not None else None
    result = getattr(lap, "result_status", None) if lap is not None else None
    return getattr(result, "raw", None) in _TERMINAL_RESULT_STATUS

@dataclass(slots=True)
class Sample:
    d: float; t: float; speed: float|None; throttle: float|None; brake: float|None
    steering: float|None; gear: int|None; rpm: int|None
    g_lat: float|None=None; g_long: float|None=None; slip: float|None=None
    ers_j: float|None=None; fuel: float|None=None
    s_mode_available: bool|None=None; s_mode_straight: bool|None=None
    world_x: float|None=None; world_z: float|None=None; yaw: float|None=None

class MeasuredPerformanceRecorder:
    BIN_M=5.0; MAX_LAPS=20
    BRAKE_ON=.10; BRAKE_RELEASE=.05; FULL_THROTTLE=.98; THROTTLE_PICKUP=.20; COAST_THROTTLE=.05; COAST_BRAKE=.05
    HIGH_SLIP=.15; OVERLAP=.10
    STEER_DEADBAND=.04; TURN_IN_STEER=.08
    MIN_CORNER_BRAKE_DISTANCE_M=25.0
    MIN_CORNER_SPEED_DROP_KPH=10.0
    SHORT_STRONG_BRAKE_DISTANCE_M=15.0
    SHORT_STRONG_BRAKE_PEAK=.55
    TRAFFIC_CLOSE_GAP_S=1.0
    PRACTICE_TRAFFIC_SUSTAINED_S=2.0
    # Practice traffic means an actual interaction, not merely a visible car.
    # A ~0.7 s physical headway (capped at 55 m) is close enough to plausibly
    # alter braking/line/throttle.  Cars farther ahead remain diagnostic only.
    PRACTICE_TRAFFIC_HEADWAY_S=0.7
    PRACTICE_TRAFFIC_MIN_DISTANCE_M=12.0
    PRACTICE_TRAFFIC_MAX_DISTANCE_M=55.0
    def __init__(self):
        self.current_lap=None; self.samples={}; self.completed=[]; self.latest_finding=None
        self.event_context=None
        self._event_context_obj=None
        self.reference_mode='best'; self.manual_reference_lap=None
        self.external_reference=None; self.external_reference_name=None; self.external_reference_meta={}
        # Authoritative per-lap metadata is supplied by F1's Session History packet.
        # Keep the current lap validity separately because the first packet of the
        # next lap describes the NEW lap, not the lap that just finished.
        self.current_lap_valid=None
        self.current_lap_started_clean=False
        self.current_lap_pit=False
        self.current_lap_traffic_compromised=False
        # Traffic evidence is tracked separately from the final sticky quality
        # flag. Practice/qualifying only reject sustained close traffic ahead;
        # a brief observation or a car merely following closely must not throw
        # away an otherwise clean lap. Race mode preserves the stricter legacy
        # behaviour because defending/attacking can genuinely distort technique.
        self._traffic_last_lap_frame=None
        self._traffic_front_close_started_at=None
        self._traffic_front_close_started_m=None
        self.current_lap_traffic_front_min_gap_s=None
        self.current_lap_traffic_rear_min_gap_s=None
        self.current_lap_traffic_front_max_close_s=0.0
        self.current_lap_traffic_front_min_distance_m=None
        self.current_lap_traffic_front_car_index=None
        self.current_lap_traffic_trigger=None
        self.current_lap_race_control_compromised=False
        self.current_lap_damage_compromised=False
        self.current_lap_pause_compromised=False
        self.current_lap_replay_seek_detected=False
        self.current_lap_session_restart_detected=False
        # Startup/out-lap pit ownership.  When the first timed lap is anchored
        # after a garage/pit-exit phase, EA can keep pitStatus asserted for a few
        # packets.  Ignore only that carry-over until pitStatus first clears.
        self._ignore_startup_pit_until_clear=False
        self._last_observed_distance=None
        self._last_observed_lap_time=None
        self._last_session_uid=None
        self._history_signature=None
        self.allow_damage_coaching=False
        # Per-lap live assist authority.  SessionData can change while a lap is
        # in progress; retain start/end snapshots plus every observed transition.
        self.current_lap_assists_start={}
        self.current_lap_assists_end={}
        self.current_lap_assist_changes=[]
    def reset(self):
        external=self.external_reference
        name=self.external_reference_name
        meta=dict(self.external_reference_meta)
        allow_damage_coaching=bool(getattr(self,"allow_damage_coaching",False))
        self.__init__()
        self.allow_damage_coaching=allow_damage_coaching
        if external is not None:
            self.external_reference=external
            self.external_reference_name=name
            self.external_reference_meta=meta
            self.reference_mode='external'


    def _reset_lap_quality_flags(self):
        self.current_lap_pit=False
        self.current_lap_traffic_compromised=False
        self._traffic_last_lap_frame=None
        self._traffic_front_close_started_at=None
        self._traffic_front_close_started_m=None
        self.current_lap_traffic_front_min_gap_s=None
        self.current_lap_traffic_rear_min_gap_s=None
        self.current_lap_traffic_front_max_close_s=0.0
        self.current_lap_traffic_front_min_distance_m=None
        self.current_lap_traffic_front_car_index=None
        self.current_lap_traffic_trigger=None
        self.current_lap_race_control_compromised=False
        self.current_lap_damage_compromised=False
        self.current_lap_pause_compromised=False
        self.current_lap_replay_seek_detected=False
        self.current_lap_session_restart_detected=False
        # Startup/out-lap pit ownership.  When the first timed lap is anchored
        # after a garage/pit-exit phase, EA can keep pitStatus asserted for a few
        # packets.  Ignore only that carry-over until pitStatus first clears.
        self._ignore_startup_pit_until_clear=False
        self._last_observed_distance=None
        self._last_observed_lap_time=None

    @staticmethod
    def _live_assists(state):
        """Return the current assist configuration from live SessionData state.

        Do not use PacketTimeTrialData.m_playerSessionBestDataSet here: that
        packet describes the session-best lap and becomes stale as soon as the
        driver changes an assist during the session.
        """
        session=getattr(state,'session',None)
        if session is None:
            return {}
        mapping=(
            ('traction_control','traction_control_assist'),
            ('anti_lock_brakes','anti_lock_brakes_assist'),
            ('gearbox_assist','gearbox_assist'),
            ('steering_assist','steering_assist'),
            ('braking_assist','braking_assist'),
            ('pit_assist','pit_assist'),
            ('pit_release_assist','pit_release_assist'),
            ('ers_assist','ers_assist'),
            ('drs_assist','drs_assist'),
            ('equal_car_performance','equal_car_performance'),
        )
        out={}
        for key,attr in mapping:
            value=getattr(session,attr,None)
            if value is not None:
                out[key]=value
        return out

    def _start_lap_assist_tracking(self,state):
        assists=self._live_assists(state)
        self.current_lap_assists_start=dict(assists)
        self.current_lap_assists_end=dict(assists)
        self.current_lap_assist_changes=[]

    def _observe_lap_assists(self,state, *, lap_time_s=None, distance_m=None):
        assists=self._live_assists(state)
        if not assists:
            return
        if not self.current_lap_assists_start:
            self.current_lap_assists_start=dict(assists)
        previous=dict(self.current_lap_assists_end or self.current_lap_assists_start)
        changed={}
        for key,value in assists.items():
            if key in previous and previous.get(key) != value:
                changed[key]={'from':previous.get(key),'to':value}
        if changed:
            self.current_lap_assist_changes.append({
                'lap_time_s':float(lap_time_s) if _finite(lap_time_s) is not None else None,
                'distance_m':float(distance_m) if _finite(distance_m) is not None else None,
                'changes':changed,
            })
        self.current_lap_assists_end=dict(assists)


    @staticmethod
    def _pit_active(lap):
        pit=str(getattr(getattr(lap,'pit_status',None),'name','') or '').lower()
        return bool(pit and pit not in {'none','no pit'})

    def _practice_physical_front(self, state):
        """Return the nearest car physically ahead on the circuit.

        EA's time-delta-to-car-in-front field is useful for race strategy, but in
        Practice it can identify a classification neighbour that is not actually
        obstructing the player's current piece of track.  Coaching eligibility
        therefore uses lap-distance geometry instead.  Rear cars never count.
        """
        player=getattr(state,'player',None)
        player_lap=getattr(player,'lap',None) if player is not None else None
        session=getattr(state,'session',None)
        track_len=_finite(getattr(session,'track_length_m',None)) if session is not None else None
        player_d=_finite(getattr(player_lap,'lap_distance_m',None)) if player_lap is not None else None
        if track_len is None or float(track_len) <= 100.0 or player_d is None:
            return None
        speed=_finite(getattr(getattr(player,'telemetry',None),'speed_kph',None))
        if speed is None:
            threshold=float(self.PRACTICE_TRAFFIC_MAX_DISTANCE_M)
        else:
            one_second=max(0.0,float(speed)/3.6*float(self.PRACTICE_TRAFFIC_HEADWAY_S))
            threshold=max(float(self.PRACTICE_TRAFFIC_MIN_DISTANCE_M),
                          min(float(self.PRACTICE_TRAFFIC_MAX_DISTANCE_M),one_second))
        best=None
        player_idx=getattr(state,'player_index',None)
        for idx,car in (getattr(state,'field',{}) or {}).items():
            if idx == player_idx or car is player:
                continue
            lap=getattr(car,'lap',None)
            if lap is None or self._pit_active(lap):
                continue
            other_d=_finite(getattr(lap,'lap_distance_m',None))
            if other_d is None:
                continue
            # Signed shortest circuit separation: positive means physically ahead,
            # negative means physically behind. This is independent of race order.
            signed=((float(other_d)-float(player_d)+float(track_len)/2.0)%float(track_len))-float(track_len)/2.0
            if signed <= 0.0 or signed > threshold:
                continue
            if best is None or signed < best['distance_m']:
                best={'distance_m':float(signed),'car_index':idx,'threshold_m':float(threshold)}
        return best

    def _update_lap_quality_flags(self, state):
        """Latch observed conditions that make a lap a poor coaching reference.

        These are factual session-state observations only. They never invalidate
        the game's official lap; they simply prevent compromised laps from being
        promoted as clean performance references.
        """
        c=getattr(state,'player',None)
        if c is None:return
        lap=getattr(c,'lap',None)
        if lap is not None:
            pit=str(getattr(getattr(lap,'pit_status',None),'name','') or '').lower()
            pit_active=bool(pit and pit not in {'none','no pit'})
            if self._ignore_startup_pit_until_clear:
                # The first timed lap can begin while EA still reports the
                # garage/out-lap pit state.  That state belongs to the pre-lap
                # phase.  Once pit status clears, normal sticky pit detection
                # resumes for the rest of the timed lap.
                if not pit_active:
                    self._ignore_startup_pit_until_clear=False
            elif pit_active:
                self.current_lap_pit=True
        session=getattr(state,'session',None)

        # V2.9.1.3.5.28: traffic must be evaluated only when a NEW LapData frame
        # has been observed. performance.observe() is also called by telemetry,
        # motion and other families; counting those calls would artificially turn
        # one stale <1 s gap observation into several seconds of "sustained" traffic.
        updated=getattr(state,'updated',{}) or {}
        lap_stamp=updated.get('lap') if hasattr(updated,'get') else None
        lap_frame=getattr(lap_stamp,'overall_frame',None)
        new_lap_observation=(lap_frame is None or lap_frame != self._traffic_last_lap_frame)
        if new_lap_observation:
            self._traffic_last_lap_frame=lap_frame
            gap=getattr(lap,'gap_to_car_in_front_s',None) if lap is not None else None
            behind=getattr(state,'gap_behind_s',None)
            front=float(gap) if _finite(gap) is not None else None
            rear=float(behind) if _finite(behind) is not None else None
            if front is not None and front >= 0.0:
                if self.current_lap_traffic_front_min_gap_s is None:
                    self.current_lap_traffic_front_min_gap_s=front
                else:
                    self.current_lap_traffic_front_min_gap_s=min(self.current_lap_traffic_front_min_gap_s,front)
            if rear is not None and rear >= 0.0:
                if self.current_lap_traffic_rear_min_gap_s is None:
                    self.current_lap_traffic_rear_min_gap_s=rear
                else:
                    self.current_lap_traffic_rear_min_gap_s=min(self.current_lap_traffic_rear_min_gap_s,rear)

            profile=str((self.event_context or {}).get('profile') or 'unknown').lower()
            close_front=front is not None and 0.0 <= front < self.TRAFFIC_CLOSE_GAP_S
            close_rear=rear is not None and 0.0 <= rear < self.TRAFFIC_CLOSE_GAP_S
            physical_front=self._practice_physical_front(state) if profile in {'practice','qualifying'} else None
            physical_close=physical_front is not None
            if physical_front is not None:
                fd=float(physical_front['distance_m'])
                if self.current_lap_traffic_front_min_distance_m is None:
                    self.current_lap_traffic_front_min_distance_m=fd
                else:
                    self.current_lap_traffic_front_min_distance_m=min(self.current_lap_traffic_front_min_distance_m,fd)
                self.current_lap_traffic_front_car_index=physical_front.get('car_index')
            obs_t=getattr(lap_stamp,'session_time_s',None)
            if _finite(obs_t) is None:
                obs_t=getattr(session,'session_time_s',None) if session is not None else None
            if _finite(obs_t) is None and lap is not None:
                obs_t=getattr(lap,'current_lap_time_s',None)
            obs_t=float(obs_t) if _finite(obs_t) is not None else None
            obs_d=getattr(lap,'lap_distance_m',None) if lap is not None else None
            obs_d=float(obs_d) if _finite(obs_d) is not None else None

            if profile in {'practice','qualifying'}:
                # Practice/Qualifying authority is physical track geometry, not
                # classification/time-gap ordering. A car behind the player can
                # never invalidate the lap. Only a physically-ahead car inside a
                # close interaction window (~0.7 s headway, max 55 m) for a
                # sustained interval can. A merely visible car farther up the road
                # must not discard the lap.
                if physical_close:
                    if self._traffic_front_close_started_at is None:
                        self._traffic_front_close_started_at=obs_t
                        self._traffic_front_close_started_m=obs_d
                    if obs_t is not None and self._traffic_front_close_started_at is not None:
                        duration=max(0.0,obs_t-float(self._traffic_front_close_started_at))
                        self.current_lap_traffic_front_max_close_s=max(self.current_lap_traffic_front_max_close_s,duration)
                        if duration >= self.PRACTICE_TRAFFIC_SUSTAINED_S:
                            self.current_lap_traffic_compromised=True
                            self.current_lap_traffic_trigger='sustained_physical_front'
                else:
                    if obs_t is not None and self._traffic_front_close_started_at is not None:
                        duration=max(0.0,obs_t-float(self._traffic_front_close_started_at))
                        self.current_lap_traffic_front_max_close_s=max(self.current_lap_traffic_front_max_close_s,duration)
                    self._traffic_front_close_started_at=None
                    self._traffic_front_close_started_m=None
            elif profile == 'time_trial':
                # Time Trial has no meaningful traffic interaction for player-lap
                # coaching eligibility. Never reject a TT lap on stale gap state.
                self._traffic_front_close_started_at=None
                self._traffic_front_close_started_m=None
            else:
                # Preserve the proven strict race/unknown policy.
                if close_front or close_rear:
                    self.current_lap_traffic_compromised=True
                    self.current_lap_traffic_trigger='front' if close_front else 'rear'

        if bool(getattr(session,'paused',False)):
            self.current_lap_pause_compromised=True
        sc=getattr(getattr(session,'safety_car',None),'raw',0) if session is not None else 0
        if isinstance(sc,int) and sc != 0:
            self.current_lap_race_control_compromised=True
        for zone in getattr(session,'marshal_zones',()) or () if session is not None else ():
            flag=str(getattr(getattr(zone,'flag',None),'name','') or '').lower()
            if 'yellow' in flag or 'red' in flag:
                self.current_lap_race_control_compromised=True;break
        dmg=getattr(c,'damage',None)
        if dmg is not None:
            wing=max(int(getattr(dmg,'front_left_wing_percent',0) or 0),int(getattr(dmg,'front_right_wing_percent',0) or 0))
            floor=int(getattr(dmg,'floor_percent',0) or 0)
            if wing >= 20 or floor >= 20 or getattr(dmg,'engine_blown',False) or getattr(dmg,'engine_seized',False):
                self.current_lap_damage_compromised=True

    def set_reference(self, mode='best', lap=None):
        if mode not in ('best','previous','manual','external'): return False
        if mode=='external':
            if self.external_reference is None: return False
            self.reference_mode='external'; return True
        if mode=='manual':
            if lap is None and self.completed: lap=self.completed[-1]['lap']
            if not any(x['lap']==lap for x in self.completed): return False
            self.manual_reference_lap=lap
        self.reference_mode=mode; return True


    def set_external_reference(self, lap, *, name=None, metadata=None):
        from .reference_lap import validate_reference_lap
        from .telemetry.enums import TRACKS
        meta=dict(metadata or {})
        ref=validate_reference_lap(lap)
        # Older stored TT-rival references predate track_name in the lap payload.
        # Preserve their verified track_id metadata as a canonical track name so
        # map geometry and coaching resolve the exact same physical T1..Tn model.
        if not ref.get('track_name'):
            track_id=meta.get('track_id')
            if isinstance(track_id,int):
                track_label=TRACKS.get(track_id)
                if track_label:
                    ref['track_name']=canonical_track_name(track_label)
        if not _finite(ref.get('track_length_m')):
            length=_finite(meta.get('track_length_m'))
            if length is not None:
                ref['track_length_m']=float(length)
        self.external_reference=ref
        self.external_reference_name=name or 'External reference'
        self.external_reference_meta=meta
        self.reference_mode='external'
        return True

    def load_external_reference(self, path):
        from .reference_lap import load_reference_lap
        lap, meta=load_reference_lap(path)
        name=meta.get('driver') or meta.get('name') or Path(path).stem
        return self.set_external_reference(lap, name=name, metadata=meta)

    def observe(self,state):
        c=state.player
        if not c:return
        ctx = build_event_context(state)
        if ctx is not self._event_context_obj:
            self._event_context_obj = ctx
            self.event_context = ctx.to_dict()
        # Once the player's result is terminal (or Session Ended arrived), F1 may
        # keep publishing LapData while the car rolls after the chequered flag.
        # Some builds reset currentLapTime to ~0 while keeping currentLapNum on the
        # just-finished lap. Never let those cool-down packets overwrite the final
        # lap samples and create a fake huge live delta. Still reconcile Session
        # History so the authoritative final lap can close normally.
        if _session_finished(state):
            self._sync_session_history(state)
            self._publish(state)
            return
        if c.lap.current_lap is None or c.lap.lap_distance_m is None:return
        lap,d=c.lap.current_lap,c.lap.lap_distance_m
        if d<0:return
        raw_t=c.lap.current_lap_time_s or 0.0
        session_uid=getattr(getattr(state,'session',None),'uid',None)
        if self._last_session_uid is not None and session_uid is not None and session_uid != self._last_session_uid:
            self.current_lap_session_restart_detected=True
        if session_uid is not None:
            self._last_session_uid=session_uid
        # Same-lap backwards motion of this magnitude is not normal S/F progress;
        # treat it as replay seek/teleport and keep that lap out of references.
        if self.current_lap == lap and self._last_observed_distance is not None:
            prev=float(self._last_observed_distance); cur=float(d)
            track_len=_finite(getattr(getattr(state,'session',None),'track_length_m',None))
            sf_wrap=bool(track_len is not None and prev>0.80*float(track_len) and cur<0.20*float(track_len))
            if cur < prev-100.0 and not sf_wrap:
                self.current_lap_replay_seek_detected=True
        if self.current_lap == lap and self._last_observed_lap_time is not None and float(raw_t)+1.0 < float(self._last_observed_lap_time):
            self.current_lap_replay_seek_detected=True
        self._last_observed_distance=float(d); self._last_observed_lap_time=float(raw_t)
        start_anchor=(d <= 25.0 and raw_t <= 2.0)
        if self.current_lap is None:
            self.current_lap=lap
            self.current_lap_valid=c.lap.lap_valid
            self.current_lap_started_clean=bool(start_anchor)
            self._reset_lap_quality_flags()
            self._start_lap_assist_tracking(state)
        if lap!=self.current_lap:
            if (lap==self.current_lap+1 and self.current_lap_started_clean and len(self.samples)>=20
                    and not any(x.get('lap')==self.current_lap for x in self.completed)):
                self._complete(self.current_lap,self.samples,state, valid=self.current_lap_valid)
            self.current_lap=lap;self.samples={};self.current_lap_valid=c.lap.lap_valid
            self.current_lap_started_clean=bool(start_anchor)
            self._reset_lap_quality_flags()
            self._start_lap_assist_tracking(state)
        elif start_anchor and not self.current_lap_started_clean:
            # V2.9.1.3.5.17: the first numbered lap can exist while the car is
            # still completing its garage/pit-exit startup phase.  Any pit flag
            # (and any samples) observed before the first real S/F timing anchor
            # belong to that pre-lap phase, not to the timed lap that starts at
            # the line.  Re-base ownership exactly once at the first clean anchor.
            # After this point the normal sticky pit-lap rule is unchanged: if
            # the driver enters/is in pit lane during the timed lap, pit_lap is
            # latched and the existing quality gate excludes it.
            startup_pit_carryover=bool(self.current_lap_pit or (lap == 1 and not self.completed))
            self.samples={}
            self._reset_lap_quality_flags()
            self._ignore_startup_pit_until_clear=startup_pit_carryover
            self._start_lap_assist_tracking(state)
            self.current_lap_valid=c.lap.lap_valid
            self.current_lap_started_clean=True
        elif start_anchor:
            self.current_lap_started_clean=True
        self._update_lap_quality_flags(state)
        self._observe_lap_assists(state, lap_time_s=raw_t, distance_m=d)
        if c.lap.lap_valid is False:
            # Invalidity is sticky for the whole lap. Never let a later packet
            # accidentally turn an invalid completed lap back into valid.
            self.current_lap_valid=False
        b=round(d/self.BIN_M)*self.BIN_M
        motion=state.extended.get('motion'); mex=state.extended.get('motionex'); m=None
        if motion is not None and state.player_index is not None:
            arr=getattr(motion,'m_carMotionData',())
            if state.player_index<len(arr):m=arr[state.player_index]
        glat=(getattr(m,'m_gForceLateral',None)/1000.0) if m else None
        glong=(getattr(m,'m_gForceLongitudinal',None)/1000.0) if m else None
        slip=_maxabs(getattr(mex,'m_wheelSlipRatio',())) if mex else None
        aero = getattr(c, 'aero', None)
        s_mode_name = getattr(getattr(aero, 'active_aero_mode', None), 'name', None) if aero is not None else None
        s_mode_available = getattr(aero, 'active_aero_available', None) if aero is not None else None
        world_x=getattr(m,'m_worldPositionX',None) if m else None
        world_z=getattr(m,'m_worldPositionZ',None) if m else None
        yaw=getattr(m,'m_yaw',None) if m else None
        self.samples[b]=Sample(b,raw_t,c.telemetry.speed_kph,c.telemetry.throttle,c.telemetry.brake,c.telemetry.steering,c.telemetry.gear,c.telemetry.rpm,glat,glong,slip,c.energy.store_j,c.fuel.remaining_mass,s_mode_available,s_mode_name == 'Straight mode' if s_mode_name is not None else None,world_x,world_z,yaw)
        self._sync_session_history(state)
        self._publish(state)

    def _steering_reversals(self, a):
        """Count meaningful left/right steering direction changes with hysteresis.

        Adjacent-sample sign checks miss real reversals because steering normally
        passes through zero.  This state-machine ignores the centre deadband and
        counts only transitions between established left/right states.
        """
        last_sign=0; changes=0
        for x in a:
            v=x.steering
            if v is None or not math.isfinite(v) or abs(v)<self.STEER_DEADBAND:
                continue
            sign=1 if v>0 else -1
            if last_sign and sign!=last_sign:
                changes+=1
            last_sign=sign
        return changes

    def _segments(self,a):
        """Detect stable braking zones and merge secondary brake applications.

        Separate brake pulses are merged when the driver never returned to full
        throttle between them and the pulses are close on track. This prevents
        one physical corner from becoming two section IDs.
        """
        raw=[]; start=None
        for i,x in enumerate(a):
            braking=x.brake is not None and x.brake>=self.BRAKE_ON
            if braking and start is None: start=i
            if start is not None and (not braking or i==len(a)-1):
                end=i if braking else i-1
                if end-start>=1: raw.append([start,end])
                start=None
        merged=[]
        for z in raw:
            if not merged: merged.append(z); continue
            ps,pe=merged[-1]; ns,ne=z
            gap_m=a[ns].d-a[pe].d
            between=a[pe+1:ns]
            full_between=any((x.throttle or 0)>=self.FULL_THROTTLE for x in between)
            if gap_m<=150.0 and not full_between: merged[-1][1]=ne
            else: merged.append(z)
        zones=[]
        for start,end in merged:
            brake_chunk=a[start:end+1]
            peak_brake=max((z.brake for z in brake_chunk if z.brake is not None),default=0.0)
            brake_distance=(end-start+1)*self.BIN_M
            start_speed=a[start].speed
            min_brake_speed=min((z.speed for z in brake_chunk if z.speed is not None),default=None)
            speed_drop=(start_speed-min_brake_speed) if start_speed is not None and min_brake_speed is not None else 0.0
            # A tiny pedal correction is still measured in whole-lap brake totals,
            # but it must not become a corner section and disturb corner matching.
            strong_short=brake_distance>=self.SHORT_STRONG_BRAKE_DISTANCE_M and peak_brake>=self.SHORT_STRONG_BRAKE_PEAK
            if brake_distance<self.MIN_CORNER_BRAKE_DISTANCE_M and speed_drop<self.MIN_CORNER_SPEED_DROP_KPH and not strong_short:
                continue
            exit_i=end
            for j in range(end+1,len(a)):
                if a[j].d-a[end].d>300: break
                exit_i=j
                if (a[j].throttle or 0)>=self.FULL_THROTTLE: break
            chunk=a[start:exit_i+1]; speeds=[z.speed for z in chunk if z.speed is not None]
            min_s=min(speeds) if speeds else None
            min_speed_sample=next((z for z in chunk if z.speed==min_s),None) if min_s is not None else None
            # V1.8: apex is a geometric/path fact, not the slowest-speed sample.
            # Preserve min_speed_m separately for minimum-speed coaching.
            from .corner_geometry_metrics import path_curvature_apex, steering_shape
            metric_rows=[{"d":z.d,"t":z.t,"speed":z.speed,"throttle":z.throttle,"brake":z.brake,
                          "steering":z.steering,"gear":z.gear,"world_x":z.world_x,"world_z":z.world_z,
                          "g_long":z.g_long} for z in chunk]
            apex_m,curvature_score,apex_conf=path_curvature_apex(metric_rows,a[start].d,a[exit_i].d,
                                                                  fallback_m=(min_speed_sample.d if min_speed_sample else None))
            apex=next((z for z in chunk if apex_m is not None and abs(z.d-float(apex_m))<=self.BIN_M/2+1e-6),None)
            if apex is None and apex_m is not None:
                apex=min(chunk,key=lambda z:abs(z.d-float(apex_m)))

            # V0.9.20 coaching data foundation.  These are measured anchors only;
            # diagnosis and spoken coaching are intentionally kept out of the
            # recorder so every consumer uses the same deterministic facts.
            peak_i=max(range(start,end+1), key=lambda j:(a[j].brake if a[j].brake is not None else -1.0))
            release=None
            release_search_end=min(len(a), exit_i+1)
            for j in range(peak_i+1, release_search_end):
                if (a[j].brake or 0.0) <= self.BRAKE_RELEASE:
                    release=a[j]; break
            if release is None:
                release=a[end]

            # Brake-release shape: measure from the first meaningful reduction
            # after peak pressure to the near-zero release point.  Time is used
            # for coaching because it is less speed-dependent than distance.
            release_begin=None
            peak_value=float(a[peak_i].brake or 0.0)
            begin_threshold=max(self.BRAKE_RELEASE, peak_value*0.80)
            for j in range(peak_i+1, release_search_end):
                if (a[j].brake or 0.0) <= begin_threshold:
                    release_begin=a[j]; break
            if release_begin is None:
                release_begin=a[peak_i]
            brake_release_ramp_m=max(0.0, release.d-release_begin.d) if release is not None else None
            brake_release_ramp_s=max(0.0, release.t-release_begin.t) if release is not None and _finite(release.t) is not None and _finite(release_begin.t) is not None else None

            # Turn-in is the first sustained steering input above a conservative
            # threshold near the braking/min-speed region. Requiring two bins in
            # the same direction rejects one-sample wheel noise.
            turn_in=None
            steer_start=max(0,start-10)
            steer_stop=min(len(a)-1, (a.index(apex)+10) if apex is not None else exit_i)
            for j in range(steer_start, steer_stop):
                v0=a[j].steering; v1=a[j+1].steering
                if (v0 is not None and v1 is not None and abs(v0)>=self.TURN_IN_STEER and
                        abs(v1)>=self.TURN_IN_STEER and (v0>0)==(v1>0)):
                    turn_in=a[j]; break

            throttle_search_start=(a.index(apex) if apex is not None else end)
            pickup=next((a[j] for j in range(throttle_search_start,exit_i+1)
                         if (a[j].throttle or 0)>=self.THROTTLE_PICKUP),None)
            full=next((a[j] for j in range(throttle_search_start,exit_i+1)
                       if (a[j].throttle or 0)>=self.FULL_THROTTLE),None)

            trail_start=turn_in.d if turn_in is not None else None
            trail_end=release.d if release is not None else None
            trail_brake_m=max(0.0,trail_end-trail_start) if trail_start is not None and trail_end is not None else None
            brake_duration_m=max(0.0,release.d-a[start].d) if release is not None else None
            pickup_to_full=(max(0.0,full.d-pickup.d) if pickup is not None and full is not None else None)
            pickup_to_full_s=(max(0.0,full.t-pickup.t) if pickup is not None and full is not None and _finite(full.t) is not None and _finite(pickup.t) is not None else None)

            coast_rows=[z for z in chunk if release is not None and pickup is not None and
                        release.d<=z.d<=pickup.d and (z.brake or 0)<self.COAST_BRAKE and
                        (z.throttle or 0)<self.COAST_THROTTLE]
            coasting_m=len(coast_rows)*self.BIN_M
            if len(coast_rows)>=2 and _finite(coast_rows[0].t) is not None and _finite(coast_rows[-1].t) is not None:
                coasting_s=max(0.0, coast_rows[-1].t-coast_rows[0].t)
            elif len(coast_rows)==1:
                coasting_s=0.0
            else:
                coasting_s=0.0

            gears=[z.gear for z in chunk if z.gear is not None]
            gear_shifts=sum(1 for x,y in zip(gears,gears[1:]) if x!=y) if gears else None
            apex_gear=apex.gear if apex is not None else None
            steering_vals=[z.steering for z in chunk if z.steering is not None and math.isfinite(z.steering)]
            peak_steer=max((abs(v) for v in steering_vals),default=None)
            steering_reversals=self._steering_reversals(chunk)
            steer_shape=steering_shape(metric_rows,a[start].d,a[exit_i].d)
            apex_speed=(apex.speed if apex is not None else None)
            apex_t=(apex.t if apex is not None and _finite(apex.t) is not None else None)
            throttle_pickup_after_apex_s=(max(0.0,pickup.t-apex_t) if pickup is not None and apex_t is not None and _finite(pickup.t) is not None else None)

            zones.append({'id':len(zones)+1,'start_m':a[start].d,'brake_end_m':a[end].d,'end_m':a[exit_i].d,
                'brake_start_speed_kph':a[start].speed,'min_speed_kph':min_s,'min_speed_m':min_speed_sample.d if min_speed_sample else None,
                'apex_m':apex.d if apex else None,'apex_speed_kph':apex_speed,'curvature_score':curvature_score,
                'apex_confidence':apex_conf,'apex_method':('path_curvature' if curvature_score is not None else 'min_speed_proxy'),'brake_release_m':release.d if release else None,
                'brake_release_ramp_m':brake_release_ramp_m,'brake_release_ramp_s':brake_release_ramp_s,
                'brake_duration_m':brake_duration_m,'turn_in_m':turn_in.d if turn_in else None,
                'trail_brake_m':trail_brake_m,'throttle_pickup_m':pickup.d if pickup else None,
                'full_throttle_m':full.d if full else None,'pickup_to_full_throttle_m':pickup_to_full,
                'pickup_to_full_throttle_s':pickup_to_full_s,'throttle_pickup_after_apex_s':throttle_pickup_after_apex_s,
                'coasting_m':coasting_m,'coasting_s':coasting_s,'exit_speed_kph':a[exit_i].speed,
                'entry_gear':a[start].gear,'apex_gear':apex_gear,'exit_gear':a[exit_i].gear,
                'gear_shift_count':gear_shifts,'peak_abs_steering':peak_steer,'steering_reversals':steering_reversals,
                'steering_rate_mean_per_s':steer_shape.get('steering_rate_mean_per_s'),
                'steering_rate_peak_per_s':steer_shape.get('steering_rate_peak_per_s'),
                'steering_corrections':steer_shape.get('steering_corrections'),
                'steering_smoothness':steer_shape.get('steering_smoothness'),
                'steering_unwind_s':steer_shape.get('steering_unwind_s'),
                'steering_unwind_m':steer_shape.get('steering_unwind_m'),
                'steering_unwind_monotonicity':steer_shape.get('steering_unwind_monotonicity'),
                'analysis_sample_count':len(chunk),'peak_brake':peak_brake,
                'max_slip':max((z.slip for z in chunk if z.slip is not None),default=None)})
        return zones

    def _summary(self,lap,samples,state, *, lap_time_s=None, valid=None):
        a=sorted(samples.values(),key=lambda x:x.d)
        if not a:return None
        brakes=[x for x in a if x.brake is not None and x.brake>=self.BRAKE_ON]
        full=[x for x in a if x.throttle is not None and x.throttle>=self.FULL_THROTTLE]
        slips=[x.slip for x in a if x.slip is not None]; speeds=[x.speed for x in a if x.speed is not None]
        fuel0=next((x.fuel for x in a if x.fuel is not None),None);fuel1=next((x.fuel for x in reversed(a) if x.fuel is not None),None)
        ers0=next((x.ers_j for x in a if x.ers_j is not None),None);ers1=next((x.ers_j for x in reversed(a) if x.ers_j is not None),None)
        overlap=[x for x in a if (x.brake or 0)>=self.OVERLAP and (x.throttle or 0)>=self.OVERLAP]
        coast=[x for x in a if (x.brake or 0)<self.COAST_BRAKE and (x.throttle or 0)<self.COAST_THROTTLE]
        highslip=[x for x in a if x.slip is not None and x.slip>=self.HIGH_SLIP]
        steering_changes=self._steering_reversals(a)
        if valid is None: valid=bool(state.player.lap.lap_valid is not False)
        if lap_time_s is None: lap_time_s=state.player.lap.previous_lap_time_s
        session=getattr(state,'session',None)
        track_name=canonical_track_name(getattr(session,'track',None)) if session is not None else None
        track_length_m=_finite(getattr(session,'track_length_m',None)) if session is not None else None
        weather_obj=getattr(session,'weather',None) if session is not None else None
        weather_code=getattr(weather_obj,'raw',weather_obj)
        weather_name=getattr(weather_obj,'name',None)
        tyres=getattr(state.player,'tyres',None) if getattr(state,'player',None) is not None else None
        visual_comp=getattr(getattr(tyres,'visual_compound',None),'name',None) if tyres is not None else None
        actual_comp=getattr(getattr(tyres,'actual_compound',None),'name',None) if tyres is not None else None
        fuel_start=next((x.fuel for x in a if x.fuel is not None),None)
        fuel_end=next((x.fuel for x in reversed(a) if x.fuel is not None),None)
        # Use the assist state actually observed on this lap.  The final state is
        # used for the existing compact lap icon row, while start/change history
        # is retained so a mid-lap change is explicit instead of silently being
        # attributed to an older Time Trial session-best lap.
        assists=dict(self.current_lap_assists_end or self.current_lap_assists_start or self._live_assists(state))
        assists_start=dict(self.current_lap_assists_start or assists)
        assist_changes=[dict(x) for x in self.current_lap_assist_changes]
        lap_state=getattr(getattr(state,'player',None),'lap',None)
        return {'lap':lap,'valid':bool(valid),'sample_count':len(a),'lap_time_s':lap_time_s,
          'track_name':track_name,'track_length_m':float(track_length_m) if track_length_m is not None else None,
          'weather_code':weather_code if isinstance(weather_code,(int,float,str)) else None,'weather_name':weather_name,
          'track_condition':('wet' if isinstance(weather_code,int) and weather_code>=3 else ('dry' if isinstance(weather_code,int) else None)),
          'track_temperature_c':getattr(session,'track_temperature_c',None) if session is not None else None,
          'air_temperature_c':getattr(session,'air_temperature_c',None) if session is not None else None,
          'visual_tyre_compound':visual_comp,'actual_tyre_compound':actual_comp,'tyre_compound':visual_comp or actual_comp,
          'fuel_start_kg':float(fuel_start) if fuel_start is not None else None,'fuel_end_kg':float(fuel_end) if fuel_end is not None else None,
          'min_speed_kph':min(speeds) if speeds else None,'max_speed_kph':max(speeds) if speeds else None,
          'brake_start_m':brakes[0].d if brakes else None,'brake_end_m':brakes[-1].d if brakes else None,'brake_distance_covered_m':len(brakes)*self.BIN_M,
          'peak_brake':max((x.brake for x in brakes),default=None),'full_throttle_first_m':full[0].d if full else None,'full_throttle_distance_m':len(full)*self.BIN_M,
          'max_abs_slip_ratio':max(slips) if slips else None,'high_slip_distance_m':len(highslip)*self.BIN_M,
          'throttle_brake_overlap_m':len(overlap)*self.BIN_M,'coasting_distance_m':len(coast)*self.BIN_M,'steering_reversals':steering_changes,
          'max_abs_lateral_g':max((abs(x.g_lat) for x in a if x.g_lat is not None),default=None),'max_braking_g':min((x.g_long for x in a if x.g_long is not None),default=None),
          'fuel_used_observed':(fuel0-fuel1) if fuel0 is not None and fuel1 is not None else None,'ers_store_change_j':(ers1-ers0) if ers0 is not None and ers1 is not None else None,
          'assists':assists,'assists_start':assists_start,'assist_changes':assist_changes,
          'assist_changed_mid_lap':bool(assist_changes),
          'warnings':getattr(lap_state,'warnings',None) if lap_state is not None else None,
          'penalties_s':getattr(lap_state,'penalties_s',None) if lap_state is not None else None,
          'corner_cutting_warnings':getattr(lap_state,'corner_cutting_warnings',None) if lap_state is not None else None,
          'gear_changes':sum(1 for x,y in zip(a,a[1:]) if x.gear is not None and y.gear is not None and x.gear!=y.gear),'sections':self._segments(a),'lap_start_anchored':_samples_have_lap_start(a),
          'pit_lap':bool(self.current_lap_pit),'traffic_compromised':bool(self.current_lap_traffic_compromised),
          'traffic_evidence':{
              'profile':str((self.event_context or {}).get('profile') or 'unknown'),
              'front_min_gap_s':self.current_lap_traffic_front_min_gap_s,
              'rear_min_gap_s':self.current_lap_traffic_rear_min_gap_s,
              'front_close_max_duration_s':round(float(self.current_lap_traffic_front_max_close_s),3),
              'front_min_physical_distance_m':self.current_lap_traffic_front_min_distance_m,
              'front_car_index':self.current_lap_traffic_front_car_index,
              'authority':('physical_track_distance' if str((self.event_context or {}).get('profile') or '').lower() in {'practice','qualifying'} else 'race_gap'),
              'physical_headway_s':float(self.PRACTICE_TRAFFIC_HEADWAY_S),
              'physical_min_distance_m':float(self.PRACTICE_TRAFFIC_MIN_DISTANCE_M),
              'physical_max_distance_m':float(self.PRACTICE_TRAFFIC_MAX_DISTANCE_M),
              'close_gap_threshold_s':float(self.TRAFFIC_CLOSE_GAP_S),
              'sustained_required_s':float(self.PRACTICE_TRAFFIC_SUSTAINED_S) if str((self.event_context or {}).get('profile') or '').lower() in {'practice','qualifying'} else 0.0,
              'trigger':self.current_lap_traffic_trigger,
          },
          'race_control_compromised':bool(self.current_lap_race_control_compromised),'damage_compromised':bool(self.current_lap_damage_compromised),
          'damage_coaching_override':bool(self.allow_damage_coaching),
          'pause_compromised':bool(self.current_lap_pause_compromised),'replay_seek_detected':bool(self.current_lap_replay_seek_detected),
          'session_restart_detected':bool(self.current_lap_session_restart_detected),
          '_metric_applicability':(self.event_context or {}).get('metrics',{}),'_samples':{x.d:asdict(x) for x in a}}


    def _sync_session_history(self,state):
        """Reconcile sampled laps with F1's authoritative Session History packet.

        LapData is asynchronous with the other UDP packet families.  At a start/
        finish crossing, sampling can therefore see the new lap before every field
        for the previous lap has settled.  Session History is explicitly indexed by
        game lap number and carries the completed lap time plus lap-valid bit, so it
        is the source of truth for completed-lap identity/timing/validity.
        """
        hist=state.extended.get('history')
        if hist is None or state.player_index is None or getattr(hist,'m_carIdx',None)!=state.player_index:
            return
        n=min(max(int(getattr(hist,'m_numLaps',0)),0),100)
        rows=getattr(hist,'m_lapHistoryData',())
        n=min(n,len(rows))
        signature=(getattr(hist,'m_carIdx',None),n,tuple((
            int(getattr(rows[i],'m_lapTimeInMS',0) or 0),
            int(getattr(rows[i],'m_lapValidBitFlags',0) or 0),
            int(getattr(rows[i],'m_sector1TimeMinutesPart',0) or 0),int(getattr(rows[i],'m_sector1TimeMSPart',0) or 0),
            int(getattr(rows[i],'m_sector2TimeMinutesPart',0) or 0),int(getattr(rows[i],'m_sector2TimeMSPart',0) or 0),
            int(getattr(rows[i],'m_sector3TimeMinutesPart',0) or 0),int(getattr(rows[i],'m_sector3TimeMSPart',0) or 0),
        ) for i in range(n)))
        if signature==self._history_signature:return
        self._history_signature=signature
        authoritative={}
        for i in range(n):
            row=rows[i]; ms=int(getattr(row,'m_lapTimeInMS',0) or 0)
            if ms>0:
                s1=int(getattr(row,'m_sector1TimeMinutesPart',0) or 0)*60 + int(getattr(row,'m_sector1TimeMSPart',0) or 0)/1000.0
                s2=int(getattr(row,'m_sector2TimeMinutesPart',0) or 0)*60 + int(getattr(row,'m_sector2TimeMSPart',0) or 0)/1000.0
                s3=int(getattr(row,'m_sector3TimeMinutesPart',0) or 0)*60 + int(getattr(row,'m_sector3TimeMSPart',0) or 0)/1000.0
                authoritative[i+1]={'lap_time_s':ms/1000.0,'valid':bool(int(getattr(row,'m_lapValidBitFlags',0))&1),
                    'sector1_time_s':s1 or None,'sector2_time_s':s2 or None,'sector3_time_s':s3 or None}
        if not authoritative:return

        # Correct laps already closed from the live LapData transition.
        for item in self.completed:
            auth=authoritative.get(item.get('lap'))
            if auth is not None:
                item.update(auth)

        # Session History can report the just-completed final Time Trial lap even
        # when currentLapNum never advances again before the results screen.  Close
        # that sampled lap here instead of silently losing it.
        if self.current_lap in authoritative and (self.current_lap_started_clean or _samples_have_lap_start(self.samples)) and len(self.samples)>=20 and not any(x.get('lap')==self.current_lap for x in self.completed):
            auth=authoritative[self.current_lap]
            self._complete(self.current_lap,self.samples,state,lap_time_s=auth['lap_time_s'],valid=auth['valid'])
            self.completed[-1].update(auth)
            self.samples={}

        # Recompute latest comparison after authoritative corrections.
        if self.completed:
            cur=self.completed[-1];ref=self._reference(cur)
            self.latest_finding=self.compare(cur,ref) if ref else None

    def current_reference_lap(self):
        """Return the active deterministic reference for the lap in progress.

        Unlike ``_reference`` this does not exclude the newest completed lap merely
        because there is no newly completed current lap yet. It is used by the
        live post-corner coach and keeps the same reference-mode authority rules.
        """
        if self.reference_mode == 'external' and self.external_reference is not None:
            return self.external_reference
        if not self.completed:
            return None
        if self.reference_mode == 'previous':
            return self.completed[-1]
        if self.reference_mode == 'manual':
            return next((x for x in self.completed if x.get('lap') == self.manual_reference_lap), None)
        valid=[x for x in self.completed if x.get('valid') and x.get('lap_time_s')]
        return min(valid,key=lambda x:x['lap_time_s']) if valid else self.completed[-1]

    def current_lap_trace_snapshot(self, state):
        """Return the lightweight current-lap trace used by live CORNER COACH.

        The full ``current_lap_snapshot`` intentionally calculates completed-lap
        statistics/sections and serializes every sample.  CORNER COACH only needs
        the live distance/time/input trace, so doing that summary several times per
        second created avoidable CPU/GIL pressure across the entire application.
        Keep this path shallow and non-mutating.
        """
        if self.current_lap is None or not self.samples or not self.current_lap_started_clean:
            return None
        session=getattr(state, 'session', None)
        track_name=canonical_track_name(getattr(session, 'track', None)) if session is not None else None
        track_length_m=_finite(getattr(session, 'track_length_m', None)) if session is not None else None
        lap_state=getattr(getattr(state, 'player', None), 'lap', None)
        lap_time=getattr(lap_state, 'current_lap_time_s', None) if lap_state is not None else None
        return {
            'lap':self.current_lap,
            'valid':bool(self.current_lap_valid is not False),
            'lap_time_s':lap_time,
            'track_name':track_name,
            'track_length_m':float(track_length_m) if track_length_m is not None else None,
            'lap_start_anchored':True,
            # Shallow copy gives the consumer a stable bin mapping while avoiding
            # dataclass -> dict conversion for every 5 m sample.
            '_samples':dict(self.samples),
        }

    def current_lap_snapshot(self, state):
        """Build a non-mutating measured snapshot of the lap currently in progress."""
        if self.current_lap is None or not self.samples or not self.current_lap_started_clean:
            return None
        lap_state=getattr(getattr(state, 'player', None), 'lap', None)
        lap_time=getattr(lap_state, 'current_lap_time_s', None) if lap_state is not None else None
        return self._summary(self.current_lap, self.samples, state,
                             lap_time_s=lap_time, valid=self.current_lap_valid)

    def _reference(self,cur):
        if self.reference_mode=='external' and self.external_reference is not None:return self.external_reference
        prior=self.completed[:-1]
        if not prior:return None
        if self.reference_mode=='previous':return prior[-1]
        if self.reference_mode=='manual':return next((x for x in prior if x['lap']==self.manual_reference_lap),None)
        valid=[x for x in prior if x.get('valid') and x.get('lap_time_s')]
        return min(valid,key=lambda x:x['lap_time_s']) if valid else prior[-1]

    def _complete(self,lap,samples,state, *, lap_time_s=None, valid=None):
        s=self._summary(lap,samples,state, lap_time_s=lap_time_s, valid=valid)
        if not s:return
        self.completed.append(s);self.completed=self.completed[-self.MAX_LAPS:]
        # Teach the shared physical-track model immediately at the authoritative
        # lap boundary, before the next lap's CORNER COACH pass.  Import lazily
        # to keep the recorder/backend import graph lightweight at startup.
        try:
            from .overlay.track_maps import learn_track_model_from_clean_lap
            learn_track_model_from_clean_lap(s.get('track_name'),s,s.get('track_length_m'))
        except Exception:
            # Geometry learning is additive. It must never block lap recording or
            # deterministic race/coaching state if storage is unavailable.
            pass
        ref=self._reference(s);self.latest_finding=self.compare(s,ref) if ref else None

    @staticmethod
    def compare(cur,ref):
        if not cur or not ref:return None
        out={'lap':cur['lap'],'reference_lap':ref.get('lap')}
        keys=['lap_time_s','min_speed_kph','max_speed_kph','brake_start_m','brake_distance_covered_m','peak_brake','full_throttle_first_m','full_throttle_distance_m','max_abs_slip_ratio','high_slip_distance_m','throttle_brake_overlap_m','coasting_distance_m','steering_reversals','max_abs_lateral_g','max_braking_g','gear_changes']
        applicability=cur.get('_metric_applicability') or ref.get('_metric_applicability') or {}
        if applicability.get('fuel_strategy', True): keys.append('fuel_used_observed')
        if applicability.get('ers_energy_strategy', True): keys.append('ers_store_change_j')
        for k in keys:
            a,b=cur.get(k),ref.get(k)
            if a is not None and b is not None:out[k+'_delta']=a-b
        ca,ra=cur.get('_samples',{}),ref.get('_samples',{});common=sorted(set(ca)&set(ra))
        if common and _samples_have_lap_start(ca) and _samples_have_lap_start(ra):
            deltas=[]; prev_ct=prev_rt=None
            for d in common:
                ct=_sample_field(ca[d],'t'); rt=_sample_field(ra[d],'t')
                if _finite(ct) is None or _finite(rt) is None:
                    continue
                ct=float(ct); rt=float(rt)
                if ((prev_ct is not None and ct + 0.050 < prev_ct) or
                        (prev_rt is not None and rt + 0.050 < prev_rt)):
                    continue
                prev_ct=ct; prev_rt=rt
                deltas.append((d,ct-rt))
            if deltas:
                out['finish_observed_delta_s']=deltas[-1][1]
            # V0.9.10.0: the old implementation scanned every previous point for
            # every distance bin (O(n²)). Long race replays therefore spent a
            # disproportionate amount of time rebuilding completed-lap comparisons.
            # Distances are sorted, so use binary search for the nearest d-100 m
            # point while preserving the old nearest-point semantics.
            distances=[z[0] for z in deltas]
            windows=[]
            for i,(d,v) in enumerate(deltas):
                if not i:continue
                target=d-100
                j=bisect_left(distances,target,0,i+1)
                candidates=[]
                if j<=i:candidates.append(j)
                if j>0:candidates.append(j-1)
                k=min(candidates,key=lambda idx:(abs(distances[idx]-target),idx))
                prev=deltas[k]
                windows.append((v-prev[1],prev[0],d))
            if windows:
                loss=max(windows,key=lambda z:z[0]);gain=min(windows,key=lambda z:z[0])
                out['largest_100m_loss_s'],out['loss_section_start_m'],out['loss_section_end_m']=loss
                out['largest_100m_gain_s'],out['gain_section_start_m'],out['gain_section_end_m']=gain
        # Match detected sections by physical track position, not ordinal ID.
        from .lap_analysis import match_sections_by_distance
        sc=[]
        for a,b in match_sections_by_distance(cur,ref):
            z={'section':a['id'],'reference_section':b['id'],'current_start_m':a['start_m'],'reference_start_m':b['start_m']}
            for k in ('start_m','brake_start_speed_kph','min_speed_kph','full_throttle_m','exit_speed_kph','peak_brake','max_slip'):
                if a.get(k) is not None and b.get(k) is not None:z[k+'_delta']=a[k]-b[k]
            sc.append(z)
        out['section_comparisons']=sc
        # V1.0.3: one continuous distance-based performance pipeline. The full
        # local gain/loss map is built first, then time is aggregated by physical
        # reference T1..Tn boundaries, then deterministic technique diagnosis is
        # attached to those turns. Legacy section_comparisons remain available.
        from .coaching_analysis import build_performance_pipeline
        pipeline=build_performance_pipeline(cur,ref)
        out['distance_performance']=pipeline.get('distance_model')
        out['turn_performance']=pipeline.get('turns')
        out['corner_analyses']=pipeline.get('corner_analyses') or []
        return out

    def _publish(self,state):
        clean=[{k:v for k,v in s.items() if k not in ('_samples','_metric_applicability')} for s in self.completed]
        state.extended['measured_performance']={'completed_laps':clean,'latest_comparison':self.latest_finding,'current_sample_count':len(self.samples),'current_lap_start_anchored':self.current_lap_started_clean,'distance_bin_m':self.BIN_M,'reference_mode':self.reference_mode,'manual_reference_lap':self.manual_reference_lap,'external_reference_name':self.external_reference_name,'external_reference_meta':self.external_reference_meta,'event_context':self.event_context}

def radio_summary(state,topic='compare'):
    p=state.extended.get('measured_performance',{});c=p.get('latest_comparison') if isinstance(p,dict) else None
    if not c:return 'Two sufficiently sampled completed laps are required for measured performance comparison.'
    f=c.get
    if topic=='braking':
        parts=[];x=f('brake_start_m_delta');y=f('peak_brake_delta')
        if x is not None:parts.append(f'braking started {abs(x):.0f} metres {"later" if x>0 else "earlier" if x<0 else "at the same point"}')
        if y is not None and abs(y)>=.005:parts.append(f'peak brake was {abs(y)*100:.0f} percent {"higher" if y>0 else "lower"}')
        return '. '.join(parts)+'.' if parts else 'Measured braking comparison unavailable.'
    if topic=='traction':
        parts=[];x=f('full_throttle_first_m_delta');s=f('max_abs_slip_ratio_delta')
        if x is not None:parts.append(f'first full throttle was {abs(x):.0f} metres {"later" if x>0 else "earlier" if x<0 else "at the same point"}')
        if s is not None:parts.append(f'maximum slip ratio was {abs(s):.3f} {"higher" if s>0 else "lower" if s<0 else "unchanged"}')
        return '. '.join(parts)+'.' if parts else 'Measured traction comparison unavailable.'
    if topic=='issues':
        parts=[]
        for k,label in [('high_slip_distance_m_delta','high-slip distance'),('throttle_brake_overlap_m_delta','throttle-brake overlap'),('coasting_distance_m_delta','coasting'),('steering_reversals_delta','steering reversals')]:
            x=f(k)
            if x is not None and x!=0:parts.append(f'{label} was {abs(x):.0f} {"metres" if "distance" in label or label in ("throttle-brake overlap","coasting") else "counts"} {"higher" if x>0 else "lower"}')
        return '. '.join(parts)+'.' if parts else 'No measured driving-issue difference is available.'
    dt=f('lap_time_s_delta');loss=f('largest_100m_loss_s');parts=[]
    if dt is not None:parts.append(f'last measured lap was {abs(dt):.3f} seconds {"slower" if dt>0 else "faster" if dt<0 else "the same"}')
    if loss is not None and loss>0 and f('loss_section_start_m') is not None:parts.append(f'largest measured 100 metre time loss was {loss:.3f} seconds around {f("loss_section_start_m"):.0f} to {f("loss_section_end_m"):.0f} metres')
    return '. '.join(parts)+'.' if parts else 'Measured lap comparison unavailable.'
