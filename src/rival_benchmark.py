"""V0.9.17.2.2 Time Trial rival benchmark capture + sanity filtering.

Captures the user-selected EA Time Trial rival directly from all-car UDP packets.
The rival index comes from PacketLapData/PacketTimeTrialData; no AI detection,
car setup data, or leaderboard scraping is required.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import statistics
from pathlib import Path

from .measured_performance import MeasuredPerformanceRecorder, Sample
from .reference_lap import FORMAT, VERSION


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


@dataclass(slots=True)
class _RivalTrack:
    current_lap: int | None = None
    valid: bool = True
    samples: dict | None = None
    last_distance: float | None = None
    max_distance: float = 0.0
    anchored: bool = False

    def __post_init__(self):
        if self.samples is None:
            self.samples = {}


class TimeTrialRivalCapture:
    """Build a reusable reference lap from the selected Time Trial rival."""

    BIN_M = 5.0
    MIN_SAMPLES = 20

    def __init__(self, *, enabled: bool = False, strict_quality: bool = False):
        self.enabled = bool(enabled)
        self.strict_quality = bool(strict_quality)
        self.session_meta = {}
        self.participants = {}
        self.rival_idx = None
        self.rival_dataset = None
        self.track = _RivalTrack()
        self.latest_lap = None
        self.latest_telemetry = None
        self.latest_motion = None
        self.latest_status = None
        self.extra_samples = {}
        self.best_lap = None
        self.best_meta = None
        self.completed_count = 0
        self.rejected_count = 0
        self.last_quality = {}
        self.last_bundle_paths = {}
        self._summariser = MeasuredPerformanceRecorder()

    def _reset_session(self, uid=None):
        self.session_meta = {"session_uid": int(uid)} if uid is not None else {}
        self.participants = {}
        self.rival_idx = None
        self.rival_dataset = None
        self.track = _RivalTrack()
        self.latest_lap = None
        self.latest_telemetry = None
        self.latest_motion = None
        self.latest_status = None
        self.extra_samples = {}
        self.best_lap = None
        self.best_meta = None
        self.completed_count = 0
        self.rejected_count = 0
        self.last_quality = {}
        self.last_bundle_paths = {}

    def _set_rival_idx(self, idx):
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return
        # EA uses 255 when a Time Trial comparison car is unavailable.
        if idx < 0 or idx >= 24 or idx == 255:
            return
        if self.rival_idx != idx:
            self.rival_idx = idx
            self.track = _RivalTrack()
            self.extra_samples = {}

    def _dataset_time_s(self):
        ds = self.rival_dataset
        ms = int(getattr(ds, "m_lapTimeInMS", 0) or 0) if ds is not None else 0
        return ms / 1000.0 if ms > 0 else None

    def _metadata(self, lap_number, lap_time_s):
        p = self.participants.get(self.rival_idx, {})
        ds = self.rival_dataset
        meta = dict(self.session_meta)
        meta.update({
            "source": "EA_F1_TIME_TRIAL_RIVAL",
            "driver": p.get("name") or "Time Trial rival",
            "car_index": self.rival_idx,
            "driver_id": p.get("driver_id"),
            "team_id": getattr(ds, "m_teamId", None) if ds is not None else p.get("team_id"),
            "race_number": p.get("race_number"),
            "reference_lap_number": lap_number,
            "reference_lap_time_s": lap_time_s,
            "rival_selected": True,
        })
        if ds is not None:
            meta.update({
                "rival_valid": bool(getattr(ds, "m_valid", 0)),
                "sector1_time_s": (getattr(ds, "m_sector1TimeInMS", 0) or 0) / 1000.0,
                "sector2_time_s": (getattr(ds, "m_sector2TimeInMS", 0) or 0) / 1000.0,
                "sector3_time_s": (getattr(ds, "m_sector3TimeInMS", 0) or 0) / 1000.0,
                "traction_control": getattr(ds, "m_tractionControl", None),
                "gearbox_assist": getattr(ds, "m_gearboxAssist", None),
                "anti_lock_brakes": getattr(ds, "m_antiLockBrakes", None),
                "equal_car_performance": getattr(ds, "m_equalCarPerformance", None),
                "custom_setup_used": getattr(ds, "m_customSetup", None),
            })
        return meta

    @staticmethod
    def _clean_numeric_trace(ordered):
        """Remove Time Trial ghost speed/gear discontinuities before coaching.

        EA rival ghosts can briefly jump to impossible velocities (often 435/486
        km/h) for one or more 5 m bins.  A simple one-bin median is insufficient
        because the corruption can persist across a short run.  We therefore use
        a physical longitudinal-acceleration envelope against the last accepted
        sample, then interpolate across rejected runs.
        """
        if len(ordered) < 3:
            return list(ordered)
        rows=[asdict(x) for x in ordered]
        # Drop asynchronous post-line ghost rows whose lap clock has already
        # reset while their distance still belongs to the previous lap.  These
        # rows are the source of whole-lap-sized final-segment deltas.
        monotonic=[]
        last_t=None
        for row in rows:
            t=row.get("t")
            if _finite(t):
                t=float(t)
                if last_t is not None and t + 0.050 < last_t:
                    continue
                last_t=max(last_t,t) if last_t is not None else t
            monotonic.append(row)
        rows=monotonic
        if len(rows) < 3:
            return [Sample(**row) for row in rows]
        valid=[True]*len(rows)
        last_good=0
        # Conservative limits: acceleration above +4.5 g or deceleration beyond
        # -8 g is not a useful F1 coaching reference and is treated as ghost noise.
        max_accel=45.0
        max_decel=80.0
        for i in range(1,len(rows)):
            v=rows[i].get("speed"); pv=rows[last_good].get("speed")
            t=rows[i].get("t"); pt=rows[last_good].get("t")
            if not (_finite(v) and _finite(pv) and _finite(t) and _finite(pt)):
                valid[i]=False; continue
            dt=float(t)-float(pt)
            if dt<=0 or dt>2.0 or float(v)>380.0:
                valid[i]=False; continue
            accel=((float(v)-float(pv))/3.6)/dt
            if accel>max_accel or accel < -max_decel:
                valid[i]=False
                continue
            last_good=i
        # Interpolate every rejected block between the nearest accepted points.
        i=0
        while i<len(rows):
            if valid[i]:
                i+=1; continue
            a=i-1
            j=i
            while j<len(rows) and not valid[j]:
                j+=1
            if a>=0 and j<len(rows) and _finite(rows[a].get("speed")) and _finite(rows[j].get("speed")):
                ta=float(rows[a].get("t") or 0.0); tb=float(rows[j].get("t") or 0.0)
                for k in range(i,j):
                    tk=float(rows[k].get("t") or ta)
                    ratio=(tk-ta)/(tb-ta) if tb>ta else (k-a)/(j-a)
                    ratio=max(0.0,min(1.0,ratio))
                    rows[k]["speed"]=float(rows[a]["speed"])+(float(rows[j]["speed"])-float(rows[a]["speed"]))*ratio
            elif a>=0:
                for k in range(i,j): rows[k]["speed"]=rows[a].get("speed")
            elif j<len(rows):
                for k in range(i,j): rows[k]["speed"]=rows[j].get("speed")
            i=j

        # Suppress short gear glitches. A new gear must persist for three 5 m bins
        # before it becomes the reference gear. Once confirmed, retroactively mark
        # the candidate bins so the shift point remains close to the real event.
        stable=None; candidate=None; cand_indices=[]
        for i,row in enumerate(rows):
            g=row.get("gear")
            if not isinstance(g,int) or g<=0:
                continue
            if stable is None:
                stable=g; continue
            if g==stable:
                candidate=None; cand_indices=[]
                continue
            if g==candidate:
                cand_indices.append(i)
            else:
                candidate=g; cand_indices=[i]
            row["gear"]=stable
            if len(cand_indices)>=3:
                stable=candidate
                for idx in cand_indices:
                    rows[idx]["gear"]=stable
                candidate=None; cand_indices=[]
        return [Sample(**row) for row in rows]

    def _derive_kinematic_g(self, ordered):
        """Derive longitudinal/lateral G when EA sends zero G for the rival ghost."""
        if len(ordered) < 3:
            return ordered
        result=[]
        for i,sample in enumerate(ordered):
            data=asdict(sample)
            if i>0:
                prev=ordered[i-1]
                dt=float(sample.t)-float(prev.t) if _finite(sample.t) and _finite(prev.t) else 0.0
                if 0.015 <= dt <= 0.5 and _finite(sample.speed) and _finite(prev.speed):
                    dv=(float(sample.speed)-float(prev.speed))/3.6
                    glong=dv/dt/9.80665
                    if abs(glong)<=6.0 and (not _finite(data.get("g_long")) or abs(float(data.get("g_long") or 0.0))<1e-6):
                        data["g_long"]=glong
                yaw=self.extra_samples.get((self.track.current_lap or 1, sample.d),{}).get("yaw")
                pyaw=self.extra_samples.get((self.track.current_lap or 1, prev.d),{}).get("yaw")
                if dt>0 and _finite(yaw) and _finite(pyaw) and _finite(sample.speed):
                    dy=float(yaw)-float(pyaw)
                    while dy>math.pi: dy-=2*math.pi
                    while dy<-math.pi: dy+=2*math.pi
                    glat=(float(sample.speed)/3.6)*(dy/dt)/9.80665
                    if abs(glat)<=7.0 and (not _finite(data.get("g_lat")) or abs(float(data.get("g_lat") or 0.0))<1e-6):
                        data["g_lat"]=glat
            result.append(Sample(**data))
        return result

    @staticmethod
    def _stable_gear_changes(ordered):
        gears=[x.gear for x in ordered]
        changes=0; stable=None; candidate=None; run=0
        for g in gears:
            if g is None or g<=0:
                continue
            if stable is None:
                stable=g; continue
            if g==stable:
                candidate=None; run=0; continue
            if g==candidate:
                run+=1
            else:
                candidate=g; run=1
            # Require the new gear to persist across at least three 5 m bins.
            if run>=3:
                changes+=1; stable=candidate; candidate=None; run=0
        return changes

    def _build_lap(self, lap_number, lap_time_s, valid, samples):
        ordered = sorted(samples.values(), key=lambda x: x.d)
        ordered = self._clean_numeric_trace(ordered)
        ordered = self._derive_kinematic_g(ordered)
        if len(ordered) < self.MIN_SAMPLES or not _finite(lap_time_s) or lap_time_s <= 0:
            return None
        speeds = [x.speed for x in ordered if _finite(x.speed)]
        brakes = [x for x in ordered if _finite(x.brake) and x.brake >= self._summariser.BRAKE_ON]
        full = [x for x in ordered if _finite(x.throttle) and x.throttle >= self._summariser.FULL_THROTTLE]
        overlap = [x for x in ordered if (x.brake or 0) >= self._summariser.OVERLAP and (x.throttle or 0) >= self._summariser.OVERLAP]
        coast = [x for x in ordered if (x.brake or 0) < self._summariser.COAST_BRAKE and (x.throttle or 0) < self._summariser.COAST_THROTTLE]
        return {
            "lap": int(lap_number or 1),
            "valid": bool(valid),
            "sample_count": len(ordered),
            "lap_time_s": float(lap_time_s),
            "min_speed_kph": min(speeds) if speeds else None,
            "max_speed_kph": max(speeds) if speeds else None,
            "brake_start_m": brakes[0].d if brakes else None,
            "brake_end_m": brakes[-1].d if brakes else None,
            "brake_distance_covered_m": len(brakes) * self.BIN_M,
            "peak_brake": max((x.brake for x in brakes), default=None),
            "full_throttle_first_m": full[0].d if full else None,
            "full_throttle_distance_m": len(full) * self.BIN_M,
            "throttle_brake_overlap_m": len(overlap) * self.BIN_M,
            "coasting_distance_m": len(coast) * self.BIN_M,
            "steering_reversals": self._summariser._steering_reversals(ordered),
            "max_abs_lateral_g": max((abs(x.g_lat) for x in ordered if _finite(x.g_lat)), default=None),
            "max_braking_g": min((x.g_long for x in ordered if _finite(x.g_long)), default=None),
            "gear_changes": self._stable_gear_changes(ordered),
            "sections": self._summariser._segments(ordered),
            "_samples": {x.d: dict(asdict(x), **self.extra_samples.get((int(lap_number or 1), x.d), {})) for x in ordered},
        }

    def _finish(self, lap_number, last_ms=0):
        if not self.track.samples:
            return None
        dataset_time = self._dataset_time_s()
        lap_time_s = dataset_time or ((int(last_ms or 0) / 1000.0) if int(last_ms or 0) > 0 else None)
        valid = self.track.valid
        if self.rival_dataset is not None and hasattr(self.rival_dataset, "m_valid"):
            valid = valid and bool(getattr(self.rival_dataset, "m_valid", 0))
        lap = self._build_lap(lap_number, lap_time_s, valid, self.track.samples)
        if lap is None or not lap.get("valid"):
            self.rejected_count += 1
            return None
        # V1.1.0.0: attach track identity/length and validate S/F coverage before
        # a dedicated rival-reference capture may become authoritative.
        try:
            from .telemetry.enums import TRACKS
            from .track_geometry import canonical_track_name
            track_id=self.session_meta.get("track_id")
            track_label=TRACKS.get(track_id) if isinstance(track_id,int) else None
            if track_label:
                lap["track_name"]=canonical_track_name(track_label)
        except Exception:
            pass
        if _finite(self.session_meta.get("track_length_m")):
            lap["track_length_m"]=float(self.session_meta["track_length_m"])
        try:
            from .reference_model import validate_capture_lap
            self.last_quality=validate_capture_lap(lap,self._metadata(lap_number,lap["lap_time_s"]))
        except Exception as error:
            self.last_quality={"accepted":False,"reasons":[f"quality_error:{error}"]}
        lap["reference_quality"]=dict(self.last_quality)
        if self.strict_quality and not self.last_quality.get("accepted"):
            self.rejected_count += 1
            return None
        self.completed_count += 1
        meta = self._metadata(lap_number, lap["lap_time_s"])
        # A selected rival normally repeats the same leaderboard lap. Keep the
        # cleanest/highest-density trace; lower lap time still wins if it changes.
        better = self.best_lap is None or lap["lap_time_s"] < self.best_lap["lap_time_s"] - 1e-6
        denser = self.best_lap is not None and abs(lap["lap_time_s"] - self.best_lap["lap_time_s"]) <= 1e-6 and lap["sample_count"] > self.best_lap.get("sample_count", 0)
        if better or denser:
            self.best_lap, self.best_meta = lap, meta
            return lap, meta
        return None

    def _sample_rival(self):
        idx = self.rival_idx
        if idx is None or self.latest_lap is None or self.latest_telemetry is None or not self.track.anchored:
            return
        laps = getattr(self.latest_lap, "m_lapData", ())
        tels = getattr(self.latest_telemetry, "m_carTelemetryData", ())
        if idx >= len(laps) or idx >= len(tels):
            return
        row, tel = laps[idx], tels[idx]
        lapnum = int(getattr(row, "m_currentLapNum", 0) or 0) or 1
        distance = getattr(row, "m_lapDistance", None)
        if not _finite(distance) or distance < 0:
            return
        d = round(float(distance) / self.BIN_M) * self.BIN_M
        motion_rows = getattr(self.latest_motion, "m_carMotionData", ()) if self.latest_motion is not None else ()
        motion = motion_rows[idx] if idx < len(motion_rows) else None
        status_rows = getattr(self.latest_status, "m_carStatusData", ()) if self.latest_status is not None else ()
        status = status_rows[idx] if idx < len(status_rows) else None
        glat = getattr(motion, "m_gForceLateral", None) if motion is not None else None
        glong = getattr(motion, "m_gForceLongitudinal", None) if motion is not None else None
        glat = float(glat) if _finite(glat) else None
        glong = float(glong) if _finite(glong) else None
        t = int(getattr(row, "m_currentLapTimeInMS", 0) or 0) / 1000.0
        s = Sample(d=d, t=t,
                   speed=float(getattr(tel, "m_speed", 0)) if _finite(getattr(tel, "m_speed", None)) else None,
                   throttle=getattr(tel, "m_throttle", None), brake=getattr(tel, "m_brake", None),
                   steering=getattr(tel, "m_steer", None), gear=getattr(tel, "m_gear", None),
                   rpm=getattr(tel, "m_engineRPM", None), g_lat=glat, g_long=glong, slip=None,
                   ers_j=(float(getattr(status, "m_ersStoreEnergy")) if status is not None and _finite(getattr(status, "m_ersStoreEnergy", None)) else None))
        extras = {
            "drs": getattr(tel, "m_drs", None),
            "clutch": getattr(tel, "m_clutch", None),
            "rev_lights_percent": getattr(tel, "m_revLightsPercent", None),
            "brake_temperatures_c": list(getattr(tel, "m_brakesTemperature", ()) or ()),
            "tyre_surface_temperatures_c": list(getattr(tel, "m_tyresSurfaceTemperature", ()) or ()),
            "tyre_inner_temperatures_c": list(getattr(tel, "m_tyresInnerTemperature", ()) or ()),
            "tyre_pressures_psi": list(getattr(tel, "m_tyresPressure", ()) or ()),
            "surface_type": list(getattr(tel, "m_surfaceType", ()) or ()),
        }
        if motion is not None:
            extras.update({
                "world_x": getattr(motion, "m_worldPositionX", None), "world_y": getattr(motion, "m_worldPositionY", None), "world_z": getattr(motion, "m_worldPositionZ", None),
                "world_velocity_x": getattr(motion, "m_worldVelocityX", None), "world_velocity_y": getattr(motion, "m_worldVelocityY", None), "world_velocity_z": getattr(motion, "m_worldVelocityZ", None),
                "yaw": getattr(motion, "m_yaw", None), "pitch": getattr(motion, "m_pitch", None), "roll": getattr(motion, "m_roll", None),
            })
        self.extra_samples[(lapnum, d)] = extras
        self.track.samples[d] = s
        self.track.current_lap = lapnum
        self.track.valid = self.track.valid and not bool(getattr(row, "m_currentLapInvalid", 0))
        self.track.last_distance = float(distance)
        self.track.max_distance = max(self.track.max_distance, float(distance))

    def observe(self, packet):
        if not self.enabled:
            return None
        pid = packet.header.m_packetId
        uid = getattr(packet.header, "m_sessionUID", None)
        if uid is not None and self.session_meta.get("session_uid") not in (None, int(uid)):
            self._reset_session(uid)
        elif uid is not None and "session_uid" not in self.session_meta:
            self.session_meta["session_uid"] = int(uid)
        # Persist packet/game identity with every newly captured reference so
        # friend-package compatibility can reject known cross-game mismatches.
        pf=getattr(packet.header,"m_packetFormat",None)
        gy=getattr(packet.header,"m_gameYear",None)
        major=getattr(packet.header,"m_gameMajorVersion",None)
        minor=getattr(packet.header,"m_gameMinorVersion",None)
        if pf is not None:self.session_meta["packet_format"]=int(pf)
        if gy is not None:self.session_meta["game_year"]=2000+int(gy) if int(gy)<100 else int(gy)
        if major is not None:
            self.session_meta["game_version"]=f"{int(major)}.{int(minor or 0)}"
        body = packet.body

        if pid == 1:
            self.session_meta.update({
                "track_id": getattr(body, "m_trackId", None), "track_length_m": getattr(body, "m_trackLength", None),
                "session_type": getattr(body, "m_sessionType", None), "formula": getattr(body, "m_formula", None),
                "weather": getattr(body, "m_weather", None), "track_temperature_c": getattr(body, "m_trackTemperature", None),
                "air_temperature_c": getattr(body, "m_airTemperature", None), "equal_car_performance": getattr(body, "m_equalCarPerformance", None),
            })
            return None
        if pid == 4:
            count = int(getattr(body, "m_numActiveCars", 0) or 0)
            self.participants = {}
            for idx, p in enumerate(getattr(body, "m_participants", ())[:count]):
                self.participants[idx] = {"name": str(getattr(p, "m_name", "") or "").strip("\x00 "), "driver_id": getattr(p, "m_driverId", None), "team_id": getattr(p, "m_teamId", None), "race_number": getattr(p, "m_raceNumber", None)}
            return None
        if pid == 14:
            ds = getattr(body, "m_rivalDataSet", None)
            self.rival_dataset = ds
            if ds is not None:
                self._set_rival_idx(getattr(ds, "m_carIdx", None))
            return None
        if pid == 0:
            self.latest_motion = body
            return None
        if pid == 2:
            idx = getattr(body, "m_timeTrialRivalCarIdx", None)
            self._set_rival_idx(idx)
            rows = getattr(body, "m_lapData", ())
            result = None
            if self.rival_idx is not None and self.rival_idx < len(rows):
                row = rows[self.rival_idx]
                new_lap = int(getattr(row, "m_currentLapNum", 0) or 0) or 1
                new_distance = getattr(row, "m_lapDistance", None)
                track_len = float(self.session_meta.get("track_length_m") or 0)
                lap_changed = self.track.current_lap is not None and new_lap != self.track.current_lap
                wrapped = (_finite(new_distance) and self.track.last_distance is not None and track_len > 0 and
                           self.track.last_distance > track_len * 0.65 and float(new_distance) < track_len * 0.25)
                lap_time_ms=int(getattr(row,"m_currentLapTimeInMS",0) or 0)
                start_anchor=bool(_finite(new_distance) and float(new_distance) <= 25.0 and lap_time_ms <= 2000)
                if lap_changed or wrapped:
                    # Never promote the first partial lap seen after capture starts.
                    # Only an S/F-anchored trace is eligible for reference capture.
                    if self.track.samples and self.track.anchored:
                        result = self._finish(self.track.current_lap or new_lap, getattr(row, "m_lastLapTimeInMS", 0))
                    self.track = _RivalTrack(current_lap=new_lap, valid=not bool(getattr(row, "m_currentLapInvalid", 0)), anchored=bool(wrapped or start_anchor))
                    self.extra_samples = {}
                elif self.track.current_lap is None:
                    self.track.current_lap = new_lap
                    self.track.valid = not bool(getattr(row, "m_currentLapInvalid", 0))
                    self.track.anchored = start_anchor
                elif start_anchor and not self.track.anchored:
                    self.track = _RivalTrack(current_lap=new_lap, valid=not bool(getattr(row, "m_currentLapInvalid", 0)), anchored=True)
                    self.extra_samples = {}
                elif getattr(row, "m_currentLapInvalid", 0):
                    self.track.valid = False
            self.latest_lap = body
            return result
        if pid == 7:
            self.latest_status = body
            return None
        if pid == 6:
            self.latest_telemetry = body
            self._sample_rival()
        return None

    def reset_capture(self):
        """Clear the current capture while keeping the configured enable state."""
        enabled = bool(self.enabled)
        strict = bool(self.strict_quality)
        self._reset_session(None)
        self.enabled = enabled
        self.strict_quality = strict

    def capture_status(self):
        if not self.enabled:
            phase = "off"
        elif self.latest_lap is None and self.latest_telemetry is None:
            phase = "armed_waiting_telemetry"
        elif self.rival_idx is None:
            phase = "armed_waiting_rival"
        elif not self.track.anchored:
            phase = "armed_waiting_sf"
        elif self.track.samples:
            phase = "capturing"
        else:
            phase = "armed_waiting_samples"
        return {
            "enabled":bool(self.enabled),
            "phase":phase,
            "strict_quality":bool(self.strict_quality),
            "rival_index":self.rival_idx,
            "current_lap":self.track.current_lap,
            "anchored":bool(self.track.anchored),
            "sample_count":len(self.track.samples or {}),
            "completed_count":self.completed_count,
            "rejected_count":self.rejected_count,
            "best_lap_time_s":self.best_lap.get("lap_time_s") if isinstance(self.best_lap,dict) else None,
            "quality":dict(self.last_quality or {}),
            "driver":(self.best_meta or {}).get("driver") or (self.participants.get(self.rival_idx,{}).get("name") if self.rival_idx is not None else None),
            "compiled":bool(self.last_bundle_paths),
            "reference_model_path":self.last_bundle_paths.get("model"),
        }

    def save_reference_bundle(self, root="references"):
        if self.best_lap is None:
            raise ValueError("no valid Time Trial rival benchmark lap has been captured")
        from .reference_model import save_reference_bundle
        paths=save_reference_bundle(self.best_lap,self.best_meta or {},root=root,track_name=self.best_lap.get("track_name"),raw_payload=self.payload())
        self.last_bundle_paths={key:str(value) for key,value in paths.items()}
        return paths

    def payload(self):
        if self.best_lap is None:
            raise ValueError("no valid Time Trial rival benchmark lap has been captured")
        return {"format": FORMAT, "version": VERSION, "metadata": dict(self.best_meta or {}), "lap": self.best_lap}

    def save_best(self, path):
        import json
        payload = self.payload()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
