"""V0.9.17.1 deterministic AI benchmark capture.

Builds reusable Race Engineer reference laps from EA UDP data for AI-controlled
cars in the same session.  No car setup data is required or used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path

from .measured_performance import MeasuredPerformanceRecorder, Sample
from .reference_lap import FORMAT, VERSION


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


@dataclass(slots=True)
class _CarTrack:
    current_lap: int | None = None
    valid: bool = True
    samples: dict | None = None

    def __post_init__(self):
        if self.samples is None:
            self.samples = {}


class AIBenchmarkCapture:
    """Capture distance-aligned telemetry for AI cars and retain the fastest lap."""

    BIN_M = 5.0
    MIN_SAMPLES = 20

    def __init__(self, *, enabled: bool = False, min_difficulty: int = 0):
        self.enabled = bool(enabled)
        self.min_difficulty = max(0, min(110, int(min_difficulty or 0)))
        self.participants = {}
        self.tracks = {}
        self.latest_lap = None
        self.latest_telemetry = None
        self.latest_motion = None
        self.session_meta = {}
        self.best_lap = None
        self.best_meta = None
        self.completed_count = 0
        self.extra_samples = {}
        self._summariser = MeasuredPerformanceRecorder()

    def _reset_session(self, uid=None):
        self.participants = {}
        self.tracks = {}
        self.latest_lap = None
        self.latest_telemetry = None
        self.latest_motion = None
        self.best_lap = None
        self.best_meta = None
        self.completed_count = 0
        self.extra_samples = {}
        if uid is not None:
            self.session_meta = {"session_uid": int(uid)}

    def _participant(self, idx):
        return self.participants.get(idx)

    def _is_ai(self, idx):
        p = self._participant(idx)
        return bool(p and p.get("ai"))

    def _metadata_for(self, idx, lap_number, lap_time_s):
        p = self._participant(idx) or {}
        meta = dict(self.session_meta)
        meta.update({
            "source": "EA_F1_AI_CAR",
            "driver": p.get("name") or f"AI car {idx}",
            "car_index": idx,
            "driver_id": p.get("driver_id"),
            "team_id": p.get("team_id"),
            "race_number": p.get("race_number"),
            "ai_controlled": True,
            "reference_lap_number": lap_number,
            "reference_lap_time_s": lap_time_s,
        })
        return meta

    def _build_lap(self, idx, lap_number, lap_time_s, valid, samples):
        ordered = sorted(samples.values(), key=lambda x: x.d)
        if len(ordered) < self.MIN_SAMPLES or not _finite(lap_time_s) or lap_time_s <= 0:
            return None
        speeds = [x.speed for x in ordered if _finite(x.speed)]
        brakes = [x for x in ordered if _finite(x.brake) and x.brake >= self._summariser.BRAKE_ON]
        full = [x for x in ordered if _finite(x.throttle) and x.throttle >= self._summariser.FULL_THROTTLE]
        overlap = [x for x in ordered if (x.brake or 0) >= self._summariser.OVERLAP and (x.throttle or 0) >= self._summariser.OVERLAP]
        coast = [x for x in ordered if (x.brake or 0) < self._summariser.COAST_BRAKE and (x.throttle or 0) < self._summariser.COAST_THROTTLE]
        lap = {
            "lap": int(lap_number),
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
            "gear_changes": sum(1 for a, b in zip(ordered, ordered[1:]) if a.gear is not None and b.gear is not None and a.gear != b.gear),
            "sections": self._summariser._segments(ordered),
            "_samples": {x.d: dict(asdict(x), **self.extra_samples.get((idx, int(lap_number), x.d), {})) for x in ordered},
        }
        # AI MotionEx wheel-slip is not an all-car packet, so deliberately leave
        # slip metrics absent rather than borrowing the player's data.
        return lap

    def _finish_previous_lap(self, idx, track, new_lap_row):
        if track.current_lap is None or not track.samples:
            return None
        ms = int(getattr(new_lap_row, "m_lastLapTimeInMS", 0) or 0)
        lap_time_s = ms / 1000.0 if ms > 0 else None
        lap = self._build_lap(idx, track.current_lap, lap_time_s, track.valid, track.samples)
        if lap is None:
            return None
        self.completed_count += 1
        if not lap.get("valid"):
            return None
        meta = self._metadata_for(idx, track.current_lap, lap["lap_time_s"])
        if self.best_lap is None or lap["lap_time_s"] < self.best_lap["lap_time_s"]:
            self.best_lap = lap
            self.best_meta = meta
            return (lap, meta)
        return None

    def _sample_all_ai(self):
        if self.latest_lap is None or self.latest_telemetry is None:
            return
        laps = getattr(self.latest_lap, "m_lapData", ())
        tels = getattr(self.latest_telemetry, "m_carTelemetryData", ())
        motions = getattr(self.latest_motion, "m_carMotionData", ()) if self.latest_motion is not None else ()
        n = min(len(laps), len(tels))
        for idx in range(n):
            if not self._is_ai(idx):
                continue
            laprow, tel = laps[idx], tels[idx]
            lapnum = int(getattr(laprow, "m_currentLapNum", 0) or 0)
            distance = getattr(laprow, "m_lapDistance", None)
            if lapnum <= 0 or not _finite(distance) or distance < 0:
                continue
            tr = self.tracks.setdefault(idx, _CarTrack())
            if tr.current_lap is None:
                tr.current_lap = lapnum
                tr.valid = not bool(getattr(laprow, "m_currentLapInvalid", 0))
            if lapnum != tr.current_lap:
                # Completion is handled on LapData receipt before latest_lap swaps.
                tr.current_lap = lapnum
                tr.valid = not bool(getattr(laprow, "m_currentLapInvalid", 0))
                tr.samples = {}
            elif getattr(laprow, "m_currentLapInvalid", 0):
                tr.valid = False
            d = round(float(distance) / self.BIN_M) * self.BIN_M
            motion = motions[idx] if idx < len(motions) else None
            glat = getattr(motion, "m_gForceLateral", None)
            glong = getattr(motion, "m_gForceLongitudinal", None)
            glat = glat / 1000.0 if _finite(glat) else None
            glong = glong / 1000.0 if _finite(glong) else None
            t = (int(getattr(laprow, "m_currentLapTimeInMS", 0) or 0)) / 1000.0
            s = Sample(
                d=d, t=t,
                speed=float(getattr(tel, "m_speed", 0)) if _finite(getattr(tel, "m_speed", None)) else None,
                throttle=getattr(tel, "m_throttle", None),
                brake=getattr(tel, "m_brake", None),
                steering=getattr(tel, "m_steer", None),
                gear=getattr(tel, "m_gear", None),
                rpm=getattr(tel, "m_engineRPM", None),
                g_lat=glat, g_long=glong, slip=None,
            )
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
                    "world_x": getattr(motion, "m_worldPositionX", None),
                    "world_y": getattr(motion, "m_worldPositionY", None),
                    "world_z": getattr(motion, "m_worldPositionZ", None),
                    "world_velocity_x": getattr(motion, "m_worldVelocityX", None),
                    "world_velocity_y": getattr(motion, "m_worldVelocityY", None),
                    "world_velocity_z": getattr(motion, "m_worldVelocityZ", None),
                    "yaw": getattr(motion, "m_yaw", None),
                    "pitch": getattr(motion, "m_pitch", None),
                    "roll": getattr(motion, "m_roll", None),
                })
            self.extra_samples[(idx, lapnum, d)] = extras
            tr.samples[d] = s

    def observe(self, packet):
        """Observe one decoded packet. Return ``(lap, metadata)`` on a new best."""
        if not self.enabled:
            return None
        pid = packet.header.m_packetId
        uid = getattr(packet.header, "m_sessionUID", None)
        if uid is not None and self.session_meta.get("session_uid") not in (None, int(uid)):
            self._reset_session(uid)
        elif uid is not None and "session_uid" not in self.session_meta:
            self.session_meta["session_uid"] = int(uid)

        body = packet.body
        if pid == 1:
            self.session_meta.update({
                "track_id": getattr(body, "m_trackId", None),
                "track_length_m": getattr(body, "m_trackLength", None),
                "session_type": getattr(body, "m_sessionType", None),
                "formula": getattr(body, "m_formula", None),
                "ai_difficulty": getattr(body, "m_aiDifficulty", None),
                "equal_car_performance": getattr(body, "m_equalCarPerformance", None),
                "weather": getattr(body, "m_weather", None),
                "track_temperature_c": getattr(body, "m_trackTemperature", None),
                "air_temperature_c": getattr(body, "m_airTemperature", None),
            })
            return None
        if pid == 4:
            self.participants = {}
            count = int(getattr(body, "m_numActiveCars", 0) or 0)
            for idx, p in enumerate(getattr(body, "m_participants", ())[:count]):
                self.participants[idx] = {
                    "ai": int(getattr(p, "m_aiControlled", 0) or 0) == 1,
                    "name": str(getattr(p, "m_name", "") or "").strip("\x00 "),
                    "driver_id": getattr(p, "m_driverId", None),
                    "team_id": getattr(p, "m_teamId", None),
                    "race_number": getattr(p, "m_raceNumber", None),
                }
            return None
        if pid == 0:
            self.latest_motion = body
            return None
        if pid == 2:
            previous = self.latest_lap
            self.latest_lap = body
            rows = getattr(body, "m_lapData", ())
            best = None
            for idx, row in enumerate(rows):
                if not self._is_ai(idx):
                    continue
                lapnum = int(getattr(row, "m_currentLapNum", 0) or 0)
                tr = self.tracks.setdefault(idx, _CarTrack())
                if tr.current_lap is not None and lapnum == tr.current_lap + 1:
                    candidate = self._finish_previous_lap(idx, tr, row)
                    if candidate is not None:
                        best = candidate
                    tr.current_lap = lapnum
                    tr.valid = not bool(getattr(row, "m_currentLapInvalid", 0))
                    tr.samples = {}
                elif tr.current_lap is None and lapnum > 0:
                    tr.current_lap = lapnum
                    tr.valid = not bool(getattr(row, "m_currentLapInvalid", 0))
                elif lapnum == tr.current_lap and getattr(row, "m_currentLapInvalid", 0):
                    tr.valid = False
            return best
        if pid == 6:
            self.latest_telemetry = body
            difficulty = self.session_meta.get("ai_difficulty")
            if difficulty is not None and int(difficulty) < self.min_difficulty:
                return None
            self._sample_all_ai()
        return None

    def payload(self):
        if self.best_lap is None:
            raise ValueError("no valid AI benchmark lap has been captured")
        return {"format": FORMAT, "version": VERSION, "metadata": dict(self.best_meta or {}), "lap": self.best_lap}

    def save_best(self, path):
        import json
        payload = self.payload()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
