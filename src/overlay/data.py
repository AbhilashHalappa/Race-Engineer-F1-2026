"""Deterministic data adapter for the V0.9.9.9.1 strategy + session overlay pack.

The UI never decodes UDP and never invents coaching values. It receives immutable
snapshots derived from normalized RaceState plus the measured-performance recorder.
Real-time coaching compares the current lap with a completed valid reference at the
same physical track distance and only exposes a metric once that measurement exists.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from bisect import bisect_left, bisect_right
import math
import time
from typing import Any

from ..lap_analysis import build_driving_analysis, compare_sections
from ..pit_strategy import service_plan
from .track_maps import (get_track_map, get_track_map_distances, get_track_turn_markers, ensure_physical_turn_markers,
                         save_learned_track_map_samples, clean_geometry_lap, live_map_trace)
from ..track_geometry import physical_turns_from_lap
from ..distance_performance import physical_turn_boundaries


# Reference laps are immutable once completed. Cache their physical segment map
# so a 60 Hz overlay refresh never rescans ~1,000 reference samples per segment.
_SEGMENT_CACHE: dict[int, tuple[object, tuple, tuple]] = {}
_SEGMENT_CACHE_ORDER: list[int] = []
_SEGMENT_CACHE_MAX = 32


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _fmt_profile(value: str | None) -> str:
    if not value:
        return "WAITING"
    return value.replace("_", " ").upper()


def _session_finished(state) -> bool:
    session = getattr(state, "session", None)
    if getattr(session, "ended", False) is True:
        return True
    player = getattr(state, "player", None)
    lap = getattr(player, "lap", None) if player is not None else None
    result = getattr(lap, "result_status", None) if lap is not None else None
    return getattr(result, "raw", None) in {3, 4, 5, 6, 7}


def _sample_value(sample: Any, field: str):
    if isinstance(sample, dict):
        return sample.get(field)
    return getattr(sample, field, None)

def _trace_has_lap_start(samples: dict) -> bool:
    """Require an S/F-anchored trace without rescanning the whole lap.

    Measured-performance bins are 5 m keyed dictionaries.  Check only the
    possible start bins; this replaces an O(n) full-trace min() operation that
    used to run several times for every overlay frame.
    """
    if not samples:
        return False
    for key in (0, 0.0, 5, 5.0, 10, 10.0, 15, 15.0, 20, 20.0, 25, 25.0):
        if key not in samples:
            continue
        row=samples[key]
        d=_sample_value(row, "d")
        if not _num(d):
            d=float(key)
        t=_sample_value(row, "t")
        if _num(d) and _num(t) and -1.0 <= float(d) <= 25.0 and 0.0 <= float(t) <= 2.0:
            return True
    # Non-standard fixtures/reference formats may not use 5 m numeric keys.
    # Inspect just the first inserted row before falling back to a tiny prefix.
    for i,(key,row) in enumerate(samples.items()):
        d=_sample_value(row, "d")
        if not _num(d):
            try: d=float(key)
            except (TypeError, ValueError):
                if i >= 7: break
                continue
        t=_sample_value(row, "t")
        if _num(d) and _num(t) and -1.0 <= float(d) <= 25.0 and 0.0 <= float(t) <= 2.0:
            return True
        if i >= 7:
            break
    return False


_REFERENCE_SAMPLE_CACHE: dict[int, tuple[object, tuple[tuple[float, Any], ...], tuple[float, ...]]] = {}
_REFERENCE_SAMPLE_CACHE_ORDER: list[int] = []
_REFERENCE_SAMPLE_CACHE_MAX = 32

def _reference_rows(reference: dict | None):
    if not reference:
        return ()
    samples = reference.get("_samples", {}) or {}
    if not samples:
        return ()
    key = id(reference)
    cached = _REFERENCE_SAMPLE_CACHE.get(key)
    if cached is not None and cached[0] is reference:
        return cached[1]
    rows=[]
    for k,row in samples.items():
        d=_sample_value(row,"d")
        if not _num(d):
            try: d=float(k)
            except (TypeError, ValueError): continue
        rows.append((float(d),row))
    rows=tuple(sorted(rows,key=lambda item:item[0]))
    distances=tuple(d for d,_ in rows)
    _REFERENCE_SAMPLE_CACHE[key]=(reference,rows,distances)
    if key in _REFERENCE_SAMPLE_CACHE_ORDER:
        _REFERENCE_SAMPLE_CACHE_ORDER.remove(key)
    _REFERENCE_SAMPLE_CACHE_ORDER.append(key)
    while len(_REFERENCE_SAMPLE_CACHE_ORDER)>_REFERENCE_SAMPLE_CACHE_MAX:
        old=_REFERENCE_SAMPLE_CACHE_ORDER.pop(0)
        _REFERENCE_SAMPLE_CACHE.pop(old,None)
    return rows

def _reference_sample_at_distance(reference: dict | None, lap_distance_m):
    """Return a distance-interpolated reference sample for smooth DI/RI comparison.

    Continuous scalar channels are linearly interpolated at the exact driver
    distance. Discrete channels such as gear/DRS use the nearest real sample.
    This keeps RI on the exact same physical x-coordinate as DI without inventing
    extra temporal samples or changing the underlying reference lap.
    """
    if not reference or not _num(lap_distance_m):
        return None
    rows=_reference_rows(reference)
    if not rows:
        return None
    cached=_REFERENCE_SAMPLE_CACHE.get(id(reference))
    distances=cached[2] if cached is not None and cached[0] is reference else tuple(d for d,_ in rows)
    target=float(lap_distance_m)
    i=bisect_left(distances,target)
    if i<=0:
        d,row=rows[0]
        return dict(row) if abs(target-d)<=10.0 else None
    if i>=len(rows):
        d,row=rows[-1]
        return dict(row) if abs(target-d)<=10.0 else None
    d0,r0=rows[i-1]; d1,r1=rows[i]
    if abs(target-d0)<1e-9:
        return dict(r0)
    if abs(d1-d0)<1e-9:
        return dict(r0)
    ratio=max(0.0,min(1.0,(target-d0)/(d1-d0)))
    nearest=r0 if ratio<=0.5 else r1
    out=dict(nearest) if isinstance(nearest,dict) else {}
    out["d"]=target
    continuous=("t","speed","throttle","brake","steering","rpm","ers_j","fuel","g_lat","g_long","slip")
    for field in continuous:
        a=_sample_value(r0,field); b=_sample_value(r1,field)
        if _num(a) and _num(b):
            out[field]=float(a)+(float(b)-float(a))*ratio
        elif _num(a):
            out[field]=a
        elif _num(b):
            out[field]=b
    # Gear and boolean/status fields remain nearest-neighbour by design.
    for field in ("gear","drs","s_mode_available","s_mode_straight"):
        value=_sample_value(nearest,field)
        if value is not None:
            out[field]=value
    return out


@dataclass(frozen=True, slots=True)
class CoachMetric:
    label: str
    value: str
    status: str
    magnitude: float | None = None


@dataclass(frozen=True, slots=True)
class SectionHistory:
    section: int
    delta_s: float | None
    kind: str = "turn"


@dataclass(frozen=True, slots=True)
class TyreWearLap:
    lap: int
    fl: float | None
    fr: float | None
    rl: float | None
    rr: float | None
    life_percent: float | None


@dataclass(frozen=True, slots=True)
class FuelLap:
    lap: int
    used: float | None
    remaining: float | None
    diff: float | None


@dataclass(frozen=True, slots=True)
class WeatherForecastRow:
    offset_minutes: int
    weather: str
    rain_percent: int | None
    track_temperature_c: int | None
    air_temperature_c: int | None


@dataclass(frozen=True, slots=True)
class StandingRow:
    position: int
    name: str
    team: str
    gap_to_player_s: float | None
    compound: str | None
    is_player: bool = False


@dataclass(frozen=True, slots=True)
class MapMarker:
    """Presentation-only map marker positioned by lap distance."""
    kind: str
    label: str
    position: int | None
    lap_distance_m: float | None


@dataclass(frozen=True, slots=True)
class MapTurnMarker:
    """Detected coaching-corner label positioned by reference lap distance."""
    corner_id: int
    label: str
    lap_distance_m: float


@dataclass(frozen=True, slots=True)
class MapGainLossZone:
    start_m: float
    end_m: float
    state: str
    net_delta_s: float | None = None


@dataclass(frozen=True, slots=True)
class MapPerformanceSegment:
    kind: str
    number: int
    label: str
    start_m: float
    end_m: float
    net_loss_s: float | None
    complete: bool


@dataclass(frozen=True, slots=True)
class LapHistoryRow:
    lap: int
    lap_time_s: float | None
    delta_s: float | None
    sector1_s: float | None
    sector2_s: float | None
    sector3_s: float | None
    valid: bool
    best: bool = False


@dataclass(frozen=True, slots=True)
class TyreSetRow:
    index: int
    compound: str
    wear_percent: int
    available: bool | None
    recommended_session: str
    lifespan_laps: int
    usable_life_laps: int
    lap_delta_s: float
    fitted: bool | None


@dataclass(frozen=True, slots=True)
class RaceEngineerState:
    applicable: bool
    decision: str
    urgency: str
    confidence: str
    reason: str | None
    position: int | None
    lap_number: int | None
    total_laps: int | None
    laps_remaining: int | None
    current_compound: str | None
    tyre_age_laps: int | None
    max_wear_percent: float | None
    tyre_life_estimate_laps: float | None
    fuel_margin_laps: float | None
    fuel_remaining_mass: float | None
    next_tyre_compound: str | None
    next_tyre_set: int | None
    front_wing_damage_percent: int | None
    penalties_s: int | None
    serve_penalty: bool | None
    weather: str | None
    rain_percent: int | None
    safety_car: str | None
    pit_status: str | None
    session_finished: bool = False


@dataclass(frozen=True, slots=True)
class InputSnapshot:
    """Minimal 10 ms DI/RI frame; avoids rebuilding the full overlay model."""
    connected: bool
    speed_kph: int | None
    gear: int | None
    throttle: float
    brake: float
    ers_store_j: float | None
    ers_harvested_j: float | None
    ers_deployed_j: float | None
    lap_number: int | None
    lap_valid: bool | None
    lap_time_s: float | None
    lap_distance_m: float | None
    reference_throttle: float | None
    reference_brake: float | None
    reference_ers_store_j: float | None
    reference_speed_kph: int | None
    reference_gear: int | None
    reference_time_s: float | None
    reference_name: str | None


@dataclass(frozen=True, slots=True)
class OverlaySnapshot:
    connected: bool
    event_profile: str
    session_type: str | None
    speed_kph: int | None
    gear: int | None
    throttle: float
    brake: float
    steering: float | None
    ers_store_j: float | None
    ers_harvested_j: float | None
    ers_deployed_j: float | None
    lap_number: int | None
    # Live race facts duplicated at the top level so every overlay reads the
    # same normalized frame.  The Race Engineer uses these for its CURRENT
    # section and reserves RaceEngineerState for deterministic strategy output.
    position: int | None
    total_laps: int | None
    current_compound: str | None
    tyre_age_laps: int | None
    front_wing_damage_percent: int | None
    penalties_s: int | None
    warnings: int | None
    corner_cutting_warnings: int | None
    serve_penalty: bool | None
    safety_car: str | None
    pit_status: str | None
    driver_status: str | None
    session_time_left_s: int | None
    session_duration_s: int | None
    sector: int | None
    sector1_time_s: float | None
    sector2_time_s: float | None
    sector1_delta_s: float | None
    sector2_delta_s: float | None
    track_length_m: float | None
    delta_dots: tuple[float | None, ...]
    delta_dot_kinds: tuple[str, ...]
    delta_dot_sectors: tuple[int, ...]
    lap_valid: bool | None
    lap_time_s: float | None
    lap_distance_m: float | None
    best_lap_time_s: float | None
    reference_lap: int | None
    live_delta_s: float | None
    reference_throttle: float | None
    reference_brake: float | None
    reference_ers_store_j: float | None
    reference_speed_kph: int | None
    reference_gear: int | None
    reference_time_s: float | None
    reference_name: str | None
    active_section: int | None
    active_segment_kind: str | None
    active_segment_number: int | None
    active_segment_start_m: float | None
    active_segment_end_m: float | None
    comparison_lap: int | None
    coach_live: bool
    coach_metrics: tuple[CoachMetric, ...]
    s_mode_metric: CoachMetric | None
    previous_sections: tuple[SectionHistory, ...]
    # Modular strategy/session overlays. Raw values are retained even when a
    # strategy is not applicable; *_applicable controls presentation/advice.
    tyre_wear_applicable: bool
    tyre_wear: tuple[float | None, float | None, float | None, float | None]
    tyre_laps_remaining_estimate: float | None
    tyre_wear_history: tuple[TyreWearLap, ...]
    fuel_applicable: bool
    fuel_remaining_mass: float | None
    fuel_capacity: float | None
    fuel_remaining_laps: float | None
    fuel_history: tuple[FuelLap, ...]
    weather_applicable: bool
    weather_now: str | None
    forecast_accuracy: str | None
    weather_forecast: tuple[WeatherForecastRow, ...]
    standings_applicable: bool
    standings: tuple[StandingRow, ...]
    lap_history: tuple[LapHistoryRow, ...]
    tyre_sets_applicable: bool
    tyre_sets: tuple[TyreSetRow, ...]
    race_engineer: RaceEngineerState
    # Runtime-only status used by the Control Center. These do not affect
    # deterministic telemetry/coaching calculations.
    recording_active: bool = False
    recording_error: str | None = None
    recording_packets: int = 0
    recording_file: str | None = None
    session_finished: bool = False
    game_paused: bool = False
    # V0.9.15.1 receiver/peripheral health. Diagnostics only; never feeds
    # deterministic race-engineer decisions.
    wheel_usb_connected: bool = False
    wheel_status_fresh: bool = False
    wheel_peer_connected: bool = False
    pedals_peer_connected: bool = False
    motor_temp_peer_connected: bool = False
    wheel_link_port: str | None = None
    wheel_link_frames_sent: int = 0
    wheel_link_status_frames: int = 0
    wheel_link_reconnects: int = 0
    wheel_link_losses: int = 0
    # F1 dash channels. Presentation-only; never feed strategy decisions.
    rpm: int | None = None
    rev_lights_percent: int | None = None
    drs_active: bool | None = None
    drs_allowed: bool | None = None
    overtake_active: bool | None = None
    overtake_available: bool | None = None
    ers_deploy_mode: str | None = None
    tyre_surface_temperatures_c: tuple[float | None, float | None, float | None, float | None] = (None, None, None, None)
    tyre_inner_temperatures_c: tuple[float | None, float | None, float | None, float | None] = (None, None, None, None)
    # V0.9.19.1 dashboard setup strip. Direct EA car-setup packet values only.
    setup_diff_on_throttle_percent: float | None = None
    setup_diff_off_throttle_percent: float | None = None
    setup_brake_bias_percent: float | None = None
    setup_engine_braking_percent: float | None = None
    fuel_mix: str | None = None
    # V0.9.19.3 multi-page F1 dash channels (presentation only).
    s_mode_active: bool | None = None
    s_mode_available: bool | None = None
    active_aero_mode: str | None = None
    front_left_wing_damage_percent: int | None = None
    front_right_wing_damage_percent: int | None = None
    rear_wing_damage_percent: int | None = None
    floor_damage_percent: int | None = None
    diffuser_damage_percent: int | None = None
    sidepod_damage_percent: int | None = None
    gearbox_damage_percent: int | None = None
    engine_damage_percent: int | None = None
    drs_fault: bool | None = None
    ers_fault: bool | None = None
    brake_damage_percent: tuple[float | None, float | None, float | None, float | None] = (None, None, None, None)
    brake_temperatures_c: tuple[float | None, float | None, float | None, float | None] = (None, None, None, None)
    tyre_damage_percent: tuple[float | None, float | None, float | None, float | None] = (None, None, None, None)
    tyre_blisters_percent: tuple[float | None, float | None, float | None, float | None] = (None, None, None, None)
    tyre_pressures_psi: tuple[float | None, float | None, float | None, float | None] = (None, None, None, None)
    tyre_set_index: int | None = None
    pit_stops: int | None = None
    pit_speed_limit_kph: int | None = None
    pit_lane_timer_active: bool | None = None
    pit_lane_time_s: float | None = None
    pit_stop_time_s: float | None = None
    # V0.9.19.6 engine-health and live circuit-map channels.
    engine_temperature_c: int | None = None
    engine_ice_wear_percent: int | None = None
    engine_ce_wear_percent: int | None = None
    engine_mguh_wear_percent: int | None = None
    engine_mguk_wear_percent: int | None = None
    engine_tc_wear_percent: int | None = None
    engine_es_wear_percent: int | None = None
    engine_blown: bool | None = None
    engine_seized: bool | None = None
    world_position_x: float | None = None
    world_position_z: float | None = None
    session_uid: int | None = None
    track_name: str | None = None
    # V0.9.19.7 map comparison markers.
    reference_map_distance_m: float | None = None
    map_nearby: tuple[MapMarker, ...] = ()
    map_turns: tuple[MapTurnMarker, ...] = ()
    # Latest completed/current-vs-reference continuous performance overlay.
    # Dashboard map stays visually clean. CORNER COACH owns performance G/L.
    map_gain_loss_zones: tuple[MapGainLossZone, ...] = ()
    corner_coach_gain_loss_zones: tuple[MapGainLossZone, ...] = ()
    map_performance_segments: tuple[MapPerformanceSegment, ...] = ()
    map_reconciliation_error_s: float | None = None
    map_full_track_delta_s: float | None = None
    # V1.1.0.0 CORNER COACH hybrid overlay/runtime state. Dictionaries are
    # immutable-by-convention copies from the receiver's deterministic status.
    corner_coach_ready: bool = False
    corner_coach_active_zone: dict[str, Any] | None = None
    corner_coach_phase: str | None = None
    corner_coach_pre_visual: dict[str, Any] | None = None
    corner_coach_zones: tuple[dict[str, Any], ...] = ()
    corner_coach_physical_corners: tuple[dict[str, Any], ...] = ()
    corner_coach_driving_events: tuple[dict[str, Any], ...] = ()
    corner_coach_reference_now: dict[str, Any] | None = None
    corner_coach_live_now: dict[str, Any] | None = None
    corner_coach_last_diagnosis: dict[str, Any] | None = None
    live_corner_result: dict[str, Any] | None = None
    last_lap_intelligence: dict[str, Any] | None = None
    speed_coach_straight_last_diagnosis: dict[str, Any] | None = None
    speed_coach_enabled: bool = True
    speed_coach_corner_enabled: bool = True
    speed_coach_straight_enabled: bool = False
    corner_coach_quality: dict[str, Any] | None = None
    # First-lap high-rate measured geometry. Present only until a validated full
    # circuit map has been persisted. It is anchored to S/F by lap distance.
    map_learning_points: tuple[tuple[float, float], ...] = ()
    # Finalization E: presentation-only coaching policy state.  These fields
    # let native/LAN dashboards adapt their default focus without changing any
    # measured telemetry or strategy decisions.
    coaching_mode: str = "auto"
    coaching_verbosity: str = "normal"
    dashboard_focus_page: str = "dash"


def _map_turn_markers(reference: dict | None, track_name: object = None, track_length_m: object = None) -> tuple[MapTurnMarker, ...]:
    """Return physical T1..Tn markers with cached boundary authority.

    Geometry-backed references use the physical model. Legacy/reference fixtures
    without usable world X/Z retain the historical section-order fallback so map
    labels stay deterministic without forcing expensive geometry derivation.
    """
    cached=ensure_physical_turn_markers(track_name,track_length_m=track_length_m)
    if cached:
        return tuple(MapTurnMarker(int(x["corner_id"]),str(x.get("label") or f"T{x['corner_id']}"),float(x["lap_distance_m"])) for x in cached)
    if isinstance(reference,dict):
        samples=reference.get("_samples") or {}
        has_world=False
        for row in samples.values():
            if _num(_sample_value(row,"x")) and _num(_sample_value(row,"z")):
                has_world=True; break
        if has_world:
            # physical_turn_boundaries owns a bounded reference cache, so the UI no
            # longer re-runs world-trace smoothing/curvature detection every frame.
            physical=physical_turn_boundaries(reference,track_name=track_name)
            if physical:
                return tuple(MapTurnMarker(int(x.get("corner_id") or i+1),str(x.get("label") or f"T{i+1}"),float(x.get("apex_m") if _num(x.get("apex_m")) else x.get("start_m"))) for i,x in enumerate(physical) if _num(x.get("apex_m")) or _num(x.get("start_m")))
        rows=[]
        for sec in reference.get("sections",()) or ():
            if not isinstance(sec,dict): continue
            distance=next((sec.get(k) for k in ("min_speed_m","turn_in_m","start_m") if _num(sec.get(k))),None)
            if distance is not None: rows.append(float(distance))
        rows.sort()
        if rows:
            return tuple(MapTurnMarker(i,f"T{i}",distance) for i,distance in enumerate(rows,1))
    cached=get_track_turn_markers(track_name)
    return tuple(MapTurnMarker(int(x["corner_id"]),str(x.get("label") or f"T{x['corner_id']}"),float(x["lap_distance_m"])) for x in cached)


def _reference_lap(performance) -> dict | None:
    mode = getattr(performance, "reference_mode", "best")
    if mode == "external":
        external = getattr(performance, "external_reference", None)
        if external is not None:
            return external
    completed = list(getattr(performance, "completed", ()) or ())
    if not completed:
        return None
    if mode == "manual":
        wanted = getattr(performance, "manual_reference_lap", None)
        found = next((lap for lap in completed if lap.get("lap") == wanted), None)
        if found is not None:
            return found
    if mode == "previous":
        # Previous-lap mode intentionally follows the user's explicit selection.
        return completed[-1]
    valid = [lap for lap in completed if lap.get("valid") and _num(lap.get("lap_time_s")) and lap["lap_time_s"] > 0]
    # Best-lap coaching must never bootstrap from an invalid lap.
    return min(valid, key=lambda lap: lap["lap_time_s"]) if valid else None


_REFERENCE_TIME_AXIS_CACHE: dict[int, tuple[object, tuple[float, ...], tuple[float, ...]]] = {}
_REFERENCE_TIME_AXIS_CACHE_ORDER: list[int] = []
_REFERENCE_TIME_AXIS_CACHE_MAX = 32

def _reference_time_axis(reference: dict | None) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if not reference:
        return (), ()
    key=id(reference)
    cached=_REFERENCE_TIME_AXIS_CACHE.get(key)
    if cached is not None and cached[0] is reference:
        return cached[1],cached[2]
    rows=[]
    for distance,sample in (reference.get("_samples",{}) or {}).items():
        t=_sample_value(sample,"t")
        try: d=float(distance)
        except (TypeError,ValueError): continue
        if _num(d) and _num(t): rows.append((float(t),d))
    rows.sort()
    times=tuple(x[0] for x in rows);distances=tuple(x[1] for x in rows)
    _REFERENCE_TIME_AXIS_CACHE[key]=(reference,times,distances)
    if key in _REFERENCE_TIME_AXIS_CACHE_ORDER:_REFERENCE_TIME_AXIS_CACHE_ORDER.remove(key)
    _REFERENCE_TIME_AXIS_CACHE_ORDER.append(key)
    while len(_REFERENCE_TIME_AXIS_CACHE_ORDER)>_REFERENCE_TIME_AXIS_CACHE_MAX:
        old=_REFERENCE_TIME_AXIS_CACHE_ORDER.pop(0);_REFERENCE_TIME_AXIS_CACHE.pop(old,None)
    return times,distances

def _reference_distance_at_time(reference: dict | None, lap_time_s) -> float | None:
    """Return ghost/reference distance at lap time using a cached time axis."""
    if not reference or not _num(lap_time_s):
        return None
    times,distances=_reference_time_axis(reference)
    if not times:return None
    target=float(lap_time_s)
    i=bisect_left(times,target)
    if i<=0:return distances[0]
    if i>=len(times):return distances[-1]
    t1,t2=times[i-1],times[i];d1,d2=distances[i-1],distances[i]
    span=max(1e-9,t2-t1);alpha=max(0.0,min(1.0,(target-t1)/span))
    return d1+(d2-d1)*alpha


def _nearby_map_markers(state, player_position: int | None) -> tuple[MapMarker, ...]:
    if not isinstance(player_position, int) or player_position <= 0:
        return ()
    rows=[]
    for idx, car in (getattr(state, "field", {}) or {}).items():
        lap=getattr(car, "lap", None)
        pos=getattr(lap, "position", None)
        if not isinstance(pos, int) or pos <= 0 or pos == player_position:
            continue
        delta=pos-player_position
        if delta not in (-2,-1,1,2):
            continue
        distance=getattr(lap, "lap_distance_m", None)
        ident=getattr(car, "identity", None)
        name=getattr(ident, "name", None) or f"P{pos}"
        kind="ahead" if delta < 0 else "behind"
        rows.append(MapMarker(kind=kind, label=str(name), position=pos,
                              lap_distance_m=float(distance) if _num(distance) else None))
    rows.sort(key=lambda m: m.position or 999)
    return tuple(rows)


def _reference_display_name(performance, reference: dict | None) -> str | None:
    if reference is None:
        return None
    mode=getattr(performance,"reference_mode","best")
    if mode=="external":
        return getattr(performance,"external_reference_name",None) or "Stored reference"
    lap=reference.get("lap") if isinstance(reference,dict) else None
    if mode=="manual":
        return f"Measured L{lap}" if lap is not None else "Measured lap"
    if mode=="previous":
        return f"Previous L{lap}" if lap is not None else "Previous lap"
    return f"Session best L{lap}" if lap is not None else "Session best"


def _latest_comparable_lap(performance, reference: dict | None) -> dict | None:
    if reference is None:
        return None
    completed = list(getattr(performance, "completed", ()) or ())
    candidates = [
        lap for lap in completed
        if lap is not reference and lap.get("valid") and _num(lap.get("lap_time_s"))
    ]
    return candidates[-1] if candidates else None


def _sample_maps(performance, reference: dict | None):
    current = getattr(performance, "samples", None) or {}
    reference_samples = reference.get("_samples", {}) if reference else {}
    return current, reference_samples or {}


_ALIGNED_LIVE_TRACE_CACHE: dict[tuple[int,int], dict[str, Any]] = {}
_ALIGNED_LIVE_TRACE_CACHE_ORDER: list[tuple[int,int]] = []
_ALIGNED_LIVE_TRACE_CACHE_MAX = 16

def _numeric_last_key(samples: dict) -> float | None:
    if not samples:return None
    try:
        key=next(reversed(samples))
        row=samples[key]
        d=_sample_value(row,"d")
        return float(d) if _num(d) else float(key)
    except (StopIteration,TypeError,ValueError):
        return None

def _full_aligned_trace(current: dict,reference_samples: dict) -> tuple[list[tuple[float,float]],float|None,float|None]:
    trace=_aligned_trace_from_maps(current,reference_samples)
    prev_ct=prev_rt=None
    if trace:
        d=trace[-1][0]
        c=current.get(d);r=reference_samples.get(d)
        ct=_sample_value(c,"t");rt=_sample_value(r,"t")
        if _num(ct):prev_ct=float(ct)
        if _num(rt):prev_rt=float(rt)
    return trace,prev_ct,prev_rt

def _aligned_live_trace(performance, reference: dict | None) -> list[tuple[float, float]]:
    """Incrementally extend the live 5 m delta trace.

    The old implementation intersected, sorted and rescanned the complete lap on
    every UI snapshot.  Measured bins only grow forward during a clean lap, so
    after the first frame we process only newly reached reference bins and refresh
    the current final bin.
    """
    if reference is None:return []
    current,reference_samples=_sample_maps(performance,reference)
    if not current or not reference_samples:return []
    if not (_trace_has_lap_start(current) and _trace_has_lap_start(reference_samples)):return []
    latest=_numeric_last_key(current)
    if latest is None:return []
    key=(id(current),id(reference))
    cached=_ALIGNED_LIVE_TRACE_CACHE.get(key)
    reset=(cached is None or cached.get("current") is not current or cached.get("reference") is not reference or len(current)<cached.get("length",0) or latest+10.0<cached.get("latest",-1e9))
    if reset:
        trace,prev_ct,prev_rt=_full_aligned_trace(current,reference_samples)
        cached={"current":current,"reference":reference,"length":len(current),"latest":latest,"processed":trace[-1][0] if trace else -1.0,"trace":trace,"prev_ct":prev_ct,"prev_rt":prev_rt}
        _ALIGNED_LIVE_TRACE_CACHE[key]=cached
        if key in _ALIGNED_LIVE_TRACE_CACHE_ORDER:_ALIGNED_LIVE_TRACE_CACHE_ORDER.remove(key)
        _ALIGNED_LIVE_TRACE_CACHE_ORDER.append(key)
        while len(_ALIGNED_LIVE_TRACE_CACHE_ORDER)>_ALIGNED_LIVE_TRACE_CACHE_MAX:
            old=_ALIGNED_LIVE_TRACE_CACHE_ORDER.pop(0);_ALIGNED_LIVE_TRACE_CACHE.pop(old,None)
        return list(trace)

    trace=cached["trace"]
    rows=_reference_rows(reference)
    ref_distances=_REFERENCE_SAMPLE_CACHE.get(id(reference))[2] if id(reference) in _REFERENCE_SAMPLE_CACHE else tuple(d for d,_ in rows)
    processed=float(cached.get("processed",-1.0))
    i0=bisect_right(ref_distances,processed)
    i1=bisect_right(ref_distances,latest)
    prev_ct=cached.get("prev_ct");prev_rt=cached.get("prev_rt")
    for d in ref_distances[i0:i1]:
        if d not in current or d not in reference_samples:continue
        ct=_sample_value(current[d],"t");rt=_sample_value(reference_samples[d],"t")
        if not (_num(ct) and _num(rt)):continue
        ct=float(ct);rt=float(rt)
        if ((prev_ct is not None and ct+0.050<prev_ct) or (prev_rt is not None and rt+0.050<prev_rt)):continue
        trace.append((float(d),ct-rt));prev_ct=ct;prev_rt=rt;processed=float(d)
    # The current 5 m bin may be overwritten with a newer lap clock without a
    # new dictionary key. Refresh only that final point instead of the full trace.
    if trace and trace[-1][0] in current and trace[-1][0] in reference_samples:
        d=trace[-1][0];ct=_sample_value(current[d],"t");rt=_sample_value(reference_samples[d],"t")
        if _num(ct) and _num(rt):
            trace[-1]=(d,float(ct)-float(rt));prev_ct=float(ct);prev_rt=float(rt)
    cached.update(length=len(current),latest=latest,processed=processed,prev_ct=prev_ct,prev_rt=prev_rt)
    return list(trace)


def _live_delta(performance, reference: dict | None, trace: list[tuple[float, float]] | None = None) -> float | None:
    if trace is None:
        trace = _aligned_live_trace(performance, reference)
    return trace[-1][1] if trace else None


def _aligned_trace_from_maps(current_samples: dict, reference_samples: dict) -> list[tuple[float, float]]:
    if not current_samples or not reference_samples:
        return []
    if not (_trace_has_lap_start(current_samples) and _trace_has_lap_start(reference_samples)):
        return []
    if len(current_samples) <= len(reference_samples):
        common = [float(d) for d in current_samples if d in reference_samples]
    else:
        common = [float(d) for d in reference_samples if d in current_samples]
    if len(common) < 2:
        return []
    common.sort()
    out = []
    prev_ct = prev_rt = None
    for distance in common:
        ct = _sample_value(current_samples[distance], "t")
        rt = _sample_value(reference_samples[distance], "t")
        if not (_num(ct) and _num(rt)):
            continue
        ct=float(ct); rt=float(rt)
        if ((prev_ct is not None and ct + 0.050 < prev_ct) or
                (prev_rt is not None and rt + 0.050 < prev_rt)):
            continue
        prev_ct=ct; prev_rt=rt
        out.append((distance, ct-rt))
    return out


def _reference_sector_for_distance(reference: dict | None, distance_m: float) -> int:
    """Map a physical distance to S1/S2/S3 using the reference lap's measured sector times."""
    if reference is None:
        return 1
    s1 = reference.get("sector1_time_s")
    s2 = reference.get("sector2_time_s")
    samples = reference.get("_samples", {}) or {}
    if not (_num(s1) and _num(s2) and samples):
        return 1
    try:
        key = min(samples, key=lambda d: abs(float(d) - float(distance_m)))
    except (TypeError, ValueError):
        return 1
    t = _sample_value(samples[key], "t")
    if not _num(t):
        return 1
    if float(t) <= float(s1):
        return 1
    if float(t) <= float(s1) + float(s2):
        return 2
    return 3


def _track_segments(reference: dict | None, track_length_m: float | None = None, track_name: object = None):
    """Return the authoritative physical straight/turn partition.

    V1.0.3.0 still built the live Turn Coach header from detector/brake
    ``reference["sections"]``.  Stored TT rivals can have only a handful of
    braking sections, so the overlay could display TURN 5 while the map's learned
    physical geometry correctly showed T11.  The map and coach now consume the
    same physical T1..Tn boundaries.
    """
    if reference is None:
        return ()
    ref_samples = reference.get("_samples", {}) or {}
    if not ref_samples:
        return ()
    resolved_track = track_name or reference.get("track_name")
    map_turns = get_track_turn_markers(resolved_track) if resolved_track else ()
    turn_sig = tuple(
        (
            int(t.get("corner_id") or 0),
            round(float(t.get("lap_distance_m") or 0.0), 3),
            round(float(t.get("start_m") or -1.0), 3) if _num(t.get("start_m")) else None,
            round(float(t.get("end_m") or -1.0), 3) if _num(t.get("end_m")) else None,
        )
        for t in map_turns if isinstance(t, dict)
    )
    sections_src = reference.get("sections", ()) or ()
    cache_key = (
        str(resolved_track or ""),
        float(track_length_m) if _num(track_length_m) else None,
        reference.get("lap"), reference.get("sector1_time_s"), reference.get("sector2_time_s"),
        len(ref_samples), len(sections_src), turn_sig,
    )
    ident = id(reference)
    cached = _SEGMENT_CACHE.get(ident)
    if cached is not None and cached[0] is reference and cached[1] == cache_key:
        return cached[2]

    try:
        distances = sorted(float(x) for x in ref_samples)
        ref_start, ref_end = distances[0], distances[-1]
    except (TypeError, ValueError, IndexError):
        return ()
    if _num(track_length_m):
        ref_end = min(ref_end, float(track_length_m))

    turns = physical_turn_boundaries(reference, track_name=resolved_track)
    if not turns:
        return ()
    turns = sorted(turns, key=lambda row: float(row.get("start_m", row.get("apex_m", 0.0))))

    s1 = reference.get("sector1_time_s")
    s2 = reference.get("sector2_time_s")
    def sector_at(distance: float) -> int:
        if not (_num(s1) and _num(s2) and distances):
            return 1
        i = bisect_left(distances, distance)
        if i <= 0:
            d = distances[0]
        elif i >= len(distances):
            d = distances[-1]
        else:
            before, after = distances[i-1], distances[i]
            d = before if distance - before <= after - distance else after
        sample = ref_samples.get(d)
        if sample is None:
            key = min(ref_samples, key=lambda x: abs(float(x)-d))
            sample = ref_samples[key]
        t = _sample_value(sample, "t")
        if not _num(t):
            return 1
        if float(t) <= float(s1):
            return 1
        if float(t) <= float(s1) + float(s2):
            return 2
        return 3

    segments=[]
    cursor=ref_start
    straight_no=0
    for turn in turns:
        start_m=turn.get("start_m"); end_m=turn.get("end_m"); cid=turn.get("corner_id")
        if not (_num(start_m) and _num(end_m) and isinstance(cid, int)):
            continue
        turn_start=max(ref_start, float(start_m))
        turn_end=min(ref_end, max(turn_start, float(end_m)))
        if turn_start-cursor >= 7.5:
            straight_no += 1
            segments.append({"kind":"straight","number":straight_no,"start_m":cursor,"end_m":turn_start})
        if turn_end-turn_start >= 5.0:
            segments.append({
                "kind":"turn","number":int(cid),"start_m":turn_start,"end_m":turn_end,
                "turn":turn,"section_id":turn.get("reference_section_id"),
            })
        cursor=max(cursor,turn_end)
    if ref_end-cursor >= 7.5:
        straight_no += 1
        segments.append({"kind":"straight","number":straight_no,"start_m":cursor,"end_m":ref_end})
    for seg in segments:
        seg["sector"] = sector_at((seg["start_m"] + seg["end_m"]) / 2.0)
    result=tuple(segments)

    _SEGMENT_CACHE[ident] = (reference, cache_key, result)
    if ident not in _SEGMENT_CACHE_ORDER:
        _SEGMENT_CACHE_ORDER.append(ident)
    while len(_SEGMENT_CACHE_ORDER) > _SEGMENT_CACHE_MAX:
        old_ident = _SEGMENT_CACHE_ORDER.pop(0)
        _SEGMENT_CACHE.pop(old_ident, None)
    return result


def _active_segment(reference: dict | None, lap_distance_m: float | None, track_length_m: float | None = None, segments=None):
    if not _num(lap_distance_m):
        return None
    d = float(lap_distance_m)
    segments = _track_segments(reference, track_length_m) if segments is None else segments
    for i, seg in enumerate(segments):
        # Include the final endpoint in the final segment only.
        if seg["start_m"] <= d < seg["end_m"] or (i == len(segments) - 1 and d <= seg["end_m"]):
            return seg
    return None


def _track_structure_delta_dots(performance, reference: dict | None, track_length_m: float | None, *, trace=None, segments=None):
    """Return local gain/loss for each straight and turn, including the active segment."""
    if reference is None:
        return (), (), ()
    trace = _aligned_live_trace(performance, reference) if trace is None else trace
    segments = _track_segments(reference, track_length_m) if segments is None else segments
    if not segments:
        return (), (), ()
    current_end = trace[-1][0] if trace else -math.inf
    values = []
    kinds = []
    sectors = []
    for seg in segments:
        kind, lo, hi = seg["kind"], float(seg["start_m"]), float(seg["end_m"])
        kinds.append(kind)
        sectors.append(int(seg["sector"]))
        if current_end <= lo + 5.0:
            values.append(None)
            continue
        measured_hi = min(current_end, hi)
        if measured_hi - lo < 15.0:
            values.append(None)
            continue
        tolerance = max(10.0, min(25.0, (measured_hi - lo) * 0.20))
        a = _trace_nearest(trace, lo, tolerance_m=tolerance)
        b = _trace_nearest(trace, measured_hi, tolerance_m=tolerance)
        values.append((float(b) - float(a)) if _num(a) and _num(b) else None)
    return tuple(values), tuple(kinds), tuple(sectors)


# Kept as a compatibility alias for older tests/imports; semantics are now
# straight/turn track-structure markers rather than fixed distance slices.
def _micro_delta_dots(performance, reference: dict | None, track_length_m: float | None) -> tuple[float | None, ...]:
    return _track_structure_delta_dots(performance, reference, track_length_m)[0]


def _s_mode_enable_metric(performance, event_context: dict | None) -> CoachMetric | None:
    """Measure S-Mode reaction distance from EA availability to Straight mode.

    This is not a prediction and is not compared with another driver's lap. The
    metric starts when EA explicitly reports Active Aero available and measures
    how many metres pass before Straight mode is observed. The latest completed
    or currently active availability window is displayed.
    """
    if not isinstance(event_context, dict):
        return None
    metrics = event_context.get('metrics') or {}
    if not metrics.get('active_aero_analysis', False) or event_context.get('regulations_2026') is not True:
        return None
    current = getattr(performance, 'samples', None) or {}
    if not current:
        return CoachMetric('S Mode Enable', '--', 'WAIT')
    rows = sorted((float(d), sample) for d, sample in current.items())
    availability_start = None
    latest_delay = None
    in_available = False
    for distance, sample in rows:
        available = _sample_value(sample, 's_mode_available')
        straight = _sample_value(sample, 's_mode_straight')
        if available is True and not in_available:
            availability_start = distance
            in_available = True
            if straight is True:
                latest_delay = 0.0
        if in_available and straight is True and availability_start is not None:
            latest_delay = max(0.0, distance - availability_start)
        if available is False and in_available:
            in_available = False
            availability_start = None
    if in_available and availability_start is not None:
        # If not yet switched, report measured lateness-so-far only.
        last_distance, last_sample = rows[-1]
        if _sample_value(last_sample, 's_mode_straight') is not True:
            latest_delay = max(0.0, last_distance - availability_start)
    if latest_delay is None:
        return CoachMetric('S Mode Enable', '--', 'WAIT')
    if latest_delay <= 5.0:
        return CoachMetric('S Mode Enable', 'on spot', 'MATCH', latest_delay)
    return CoachMetric('S Mode Enable', f'{latest_delay:.0f}m late', 'LATER', latest_delay)


def _section_boundaries(reference: dict | None) -> list[tuple[float, float, dict]]:
    if reference is None:
        return []
    sections = [s for s in reference.get("sections", ()) if _num(s.get("start_m"))]
    if not sections:
        return []
    sections = sorted(sections, key=lambda s: float(s["start_m"]))
    anchors = []
    for section in sections:
        anchor = section.get("min_speed_m")
        if not _num(anchor):
            anchor = section.get("start_m")
        anchors.append(float(anchor))
    boundaries: list[tuple[float, float, dict]] = []
    for i, section in enumerate(sections):
        lo = -math.inf if i == 0 else (anchors[i - 1] + anchors[i]) / 2.0
        hi = math.inf if i == len(sections) - 1 else (anchors[i] + anchors[i + 1]) / 2.0
        boundaries.append((lo, hi, section))
    return boundaries


def _active_section(reference: dict | None, lap_distance_m: float | None) -> int | None:
    """Compatibility helper: return a turn id only when the active segment is a turn."""
    seg = _active_segment(reference, lap_distance_m)
    return int(seg["number"]) if seg and seg.get("kind") == "turn" else None


def _metric(label: str, value: float | None, *, unit: str, positive: str, negative: str, tolerance: float) -> CoachMetric:
    if not _num(value):
        return CoachMetric(label, "--", "WAIT")
    value = float(value)
    if abs(value) <= tolerance:
        text = f"{abs(value):.0f}{unit} match"
        return CoachMetric(label, text, "MATCH", abs(value))
    direction = positive if value > 0 else negative
    text = f"{abs(value):.0f}{unit} {direction}"
    return CoachMetric(label, text, direction.upper(), abs(value))


def _pace_only_turn_metrics(current_samples: dict, reference_samples: dict, tm: dict | None, *, current_distance_m: float | None = None) -> tuple[CoachMetric, ...]:
    wait=(CoachMetric("Local Loss","--","WAIT"),CoachMetric("Entry Speed","--","WAIT"),CoachMetric("Min Speed","--","WAIT"),CoachMetric("Exit Speed","--","WAIT"))
    if not isinstance(tm,dict): return wait
    start,end=tm.get("start_m"),tm.get("end_m")
    if not (_num(start) and _num(end)): return wait
    start=float(start);end=float(end);now=float(current_distance_m) if _num(current_distance_m) else end
    def rows(samples):
        out=[]
        for key,row in (samples or {}).items():
            d=_sample_value(row,"d")
            if not _num(d):
                try:d=float(key)
                except (TypeError,ValueError):continue
            out.append((float(d),row))
        out.sort(key=lambda x:x[0]);return out
    cur,ref=rows(current_samples),rows(reference_samples)
    def nearest(seq,d,field,tol=12.5):
        if not seq:return None
        hit=min(seq,key=lambda x:abs(x[0]-d));value=_sample_value(hit[1],field)
        return float(value) if abs(hit[0]-d)<=tol and _num(value) else None
    ref_entry,ref_min,ref_exit=tm.get("entry_speed_kph"),tm.get("min_speed_kph"),tm.get("exit_speed_kph")
    entry=nearest(cur,start,"speed");entry_delta=(entry-float(ref_entry)) if _num(entry) and _num(ref_entry) else None
    upto=max(start,min(now,end));speeds=[float(_sample_value(r,"speed")) for d,r in cur if start<=d<=upto and _num(_sample_value(r,"speed"))]
    min_delta=(min(speeds)-float(ref_min)) if speeds and _num(ref_min) else None
    exit_delta=None
    if now>=end:
        exit_speed=nearest(cur,end,"speed")
        if _num(exit_speed) and _num(ref_exit):exit_delta=float(exit_speed)-float(ref_exit)
    ce,re,ct,rt=nearest(cur,start,"t"),nearest(ref,start,"t"),nearest(cur,upto,"t"),nearest(ref,upto,"t")
    local_loss=(float(ct)-float(ce))-(float(rt)-float(re)) if all(_num(x) for x in (ce,re,ct,rt)) else None
    ratio=max(0.0,min(1.0,(upto-start)/max(1.0,end-start)));phase="ENTRY" if ratio<0.34 else ("MID" if ratio<0.67 else "EXIT")
    return (_time_metric(f"Local Loss {phase}",local_loss,tolerance=0.015),
            _metric("Entry Speed",entry_delta,unit=" kph",positive="faster",negative="slower",tolerance=2.0),
            _metric("Min Speed",min_delta,unit=" kph",positive="faster",negative="slower",tolerance=2.0),
            _metric("Exit Speed",exit_delta,unit=" kph",positive="faster",negative="slower",tolerance=2.0),
            CoachMetric("Braking Point","--","WAIT"),CoachMetric("Throttle Timing","--","WAIT"))


def _completed_coach_metrics(comparison_lap: dict | None, reference: dict | None, active_section: int | None, *, track_name: object = None, input_telemetry_trusted: bool = True, trusted_turn_metrics=()) -> tuple[CoachMetric, ...]:
    if comparison_lap is None or reference is None:
        return ()
    if not input_telemetry_trusted and active_section is not None:
        tm=next((x for x in (trusted_turn_metrics or ()) if isinstance(x,dict) and x.get("corner_id")==active_section),None)
        return _pace_only_turn_metrics((comparison_lap or {}).get("_samples",{}) or {}, (reference or {}).get("_samples",{}) or {}, tm, current_distance_m=(tm.get("end_m") if isinstance(tm,dict) else None))
    comparisons = compare_sections(comparison_lap, reference)
    row = None
    if active_section is not None:
        # active_section is a physical T number. Map it back to the attached raw
        # detector section only for the legacy metric calculation. Public labels
        # remain the physical T1..Tn number.
        turn = next((t for t in physical_turn_boundaries(reference, track_name=track_name)
                     if t.get("corner_id") == active_section), None)
        raw_id = turn.get("reference_section_id") if isinstance(turn, dict) else None
        if raw_id is not None:
            row = next((item for item in comparisons if item.reference_section == raw_id), None)
    if row is None and comparisons:
        row = comparisons[-1]
    if row is None:
        return ()
    return (
        _metric("Braking Point", row.brake_point_delta_m, unit="m", positive="later", negative="earlier", tolerance=5.0),
        _metric("Min Speed", row.min_speed_delta_kph, unit=" kph", positive="faster", negative="slower", tolerance=2.0),
        _metric("Throttle Timing", row.full_throttle_delta_m, unit="m", positive="later", negative="earlier", tolerance=5.0),
        _metric("Exit Speed", row.exit_speed_delta_kph, unit=" kph", positive="faster", negative="slower", tolerance=2.0),
    )


def _nearest_current_sample(current: dict, target_m: float, tolerance_m: float = 10.0):
    if not current or not _num(target_m):
        return None
    key = min(current, key=lambda d: abs(float(d) - float(target_m)))
    return current[key] if abs(float(key) - float(target_m)) <= tolerance_m else None


def _live_coach_metrics(performance, reference: dict | None, active_section: int | None, lap_distance_m: float | None, *, track_name: object = None, input_telemetry_trusted: bool = True, trusted_turn_metrics=()) -> tuple[CoachMetric, ...]:
    """Return current-lap coaching for the active *physical* turn.

    The public turn number is taken from the same stored/derived geometry used by
    the track map.  Detector sections are attached only as measured technique
    anchors; their IDs never become the displayed turn number.
    """
    if reference is None or active_section is None or not _num(lap_distance_m):
        return ()
    if not input_telemetry_trusted:
        tm=next((x for x in (trusted_turn_metrics or ()) if isinstance(x,dict) and x.get("corner_id")==active_section),None)
        current,ref_samples=_sample_maps(performance,reference)
        return _pace_only_turn_metrics(current,ref_samples,tm,current_distance_m=lap_distance_m)
    current, ref_samples = _sample_maps(performance, reference)
    if not current or not ref_samples:
        return ()
    turn = next((t for t in physical_turn_boundaries(reference, track_name=track_name)
                 if t.get("corner_id") == active_section), None)
    if not isinstance(turn, dict):
        return ()
    raw_id = turn.get("reference_section_id")
    ref = next((s for s in reference.get("sections", ()) if raw_id is not None and s.get("id") == raw_id), None) or {}
    current_d = float(lap_distance_m)
    sorted_samples = sorted((float(d), s) for d, s in current.items() if float(d) <= current_d + 1e-9)
    if not sorted_samples:
        return ()

    ref_brake = ref.get("start_m") if _num(ref.get("start_m")) else turn.get("brake_m")
    ref_min_m = ref.get("min_speed_m") if _num(ref.get("min_speed_m")) else turn.get("apex_m")
    ref_end = ref.get("end_m") if _num(ref.get("end_m")) else turn.get("end_m")

    # References with no detector section (common for imported TT-rival traces)
    # still have enough measured data for live physical-turn metrics.
    turn_start = float(turn.get("start_m")) if _num(turn.get("start_m")) else float(ref_brake or 0.0)
    turn_end = float(turn.get("end_m")) if _num(turn.get("end_m")) else float(ref_end or turn_start)
    ref_min_speed = ref.get("min_speed_kph")
    if not _num(ref_min_speed):
        vals=[float(_sample_value(sample,"speed")) for d,sample in ref_samples.items()
              if turn_start <= float(d) <= turn_end and _num(_sample_value(sample,"speed"))]
        ref_min_speed=min(vals) if vals else None

    ref_full = ref.get("full_throttle_m")
    if not _num(ref_full) and _num(ref_min_m):
        candidates=sorted((float(d),sample) for d,sample in ref_samples.items() if float(d) >= float(ref_min_m))
        for distance,sample in candidates:
            if distance > float(turn.get("ownership_end_m") or turn_end) + 20.0:
                break
            throttle=_sample_value(sample,"throttle")
            if _num(throttle) and float(throttle) >= 0.98:
                ref_full=distance; break

    ref_exit = ref.get("exit_speed_kph")
    if not _num(ref_exit) and _num(ref_end):
        ref_exit_sample=_nearest_current_sample(ref_samples,float(ref_end),tolerance_m=10.0)
        value=_sample_value(ref_exit_sample,"speed") if ref_exit_sample is not None else None
        ref_exit=float(value) if _num(value) else None

    ownership_lo = float(turn.get("ownership_start_m")) if _num(turn.get("ownership_start_m")) else 0.0
    search_lo = max(ownership_lo, max(0.0, float(ref_brake) - 180.0) if _num(ref_brake) else turn_start)

    brake_start = None
    for distance, sample in sorted_samples:
        if distance < search_lo:
            continue
        brake = _sample_value(sample, "brake")
        if _num(brake) and float(brake) >= 0.10:
            brake_start = distance
            break

    brake_delta = None
    if _num(ref_brake):
        if brake_start is not None:
            brake_delta = brake_start - float(ref_brake)
        elif current_d >= float(ref_brake) + 5.0:
            brake_delta = current_d - float(ref_brake)

    min_speed_delta = None
    if _num(ref_min_m) and _num(ref_min_speed) and current_d >= float(ref_min_m) + 5.0:
        speed_window_start = brake_start if brake_start is not None else (float(ref_brake) if _num(ref_brake) else search_lo)
        speeds = [
            float(_sample_value(sample, "speed"))
            for distance, sample in sorted_samples
            if distance >= speed_window_start and distance <= turn_end + 10.0 and _num(_sample_value(sample, "speed"))
        ]
        if speeds:
            min_speed_delta = min(speeds) - float(ref_min_speed)

    throttle_delta = None
    full_throttle_m = None
    throttle_search_start = float(ref_min_m) if _num(ref_min_m) else (float(ref_brake) if _num(ref_brake) else search_lo)
    for distance, sample in sorted_samples:
        if distance < throttle_search_start:
            continue
        if distance > float(turn.get("ownership_end_m") or turn_end) + 20.0:
            break
        throttle = _sample_value(sample, "throttle")
        if _num(throttle) and float(throttle) >= 0.98:
            full_throttle_m = distance
            break
    if _num(ref_full):
        if full_throttle_m is not None:
            throttle_delta = full_throttle_m - float(ref_full)
        elif current_d >= float(ref_full) + 5.0:
            throttle_delta = current_d - float(ref_full)

    exit_speed_delta = None
    if _num(ref_end) and _num(ref_exit) and current_d >= float(ref_end):
        exit_sample = _nearest_current_sample(current, float(ref_end), tolerance_m=10.0)
        exit_speed = _sample_value(exit_sample, "speed") if exit_sample is not None else None
        if _num(exit_speed):
            exit_speed_delta = float(exit_speed) - float(ref_exit)

    return (
        _metric("Braking Point", brake_delta, unit="m", positive="later", negative="earlier", tolerance=5.0),
        _metric("Min Speed", min_speed_delta, unit=" kph", positive="faster", negative="slower", tolerance=2.0),
        _metric("Throttle Timing", throttle_delta, unit="m", positive="later", negative="earlier", tolerance=5.0),
        _metric("Exit Speed", exit_speed_delta, unit=" kph", positive="faster", negative="slower", tolerance=2.0),
    )


def _time_metric(label: str, delta_s: float | None, tolerance: float = 0.015) -> CoachMetric:
    if not _num(delta_s):
        return CoachMetric(label, "--", "WAIT")
    value = float(delta_s)
    if abs(value) <= tolerance:
        return CoachMetric(label, f"{abs(value):.3f}s match", "MATCH", abs(value) * 1000.0)
    if value < 0:
        return CoachMetric(label, f"{abs(value):.3f}s faster", "FASTER", abs(value) * 1000.0)
    return CoachMetric(label, f"{abs(value):.3f}s slower", "SLOWER", abs(value) * 1000.0)


def _straight_coach_metrics(performance, reference: dict | None, segment: dict | None, lap_distance_m: float | None, *, trace=None) -> tuple[CoachMetric, ...]:
    if reference is None or not segment or segment.get("kind") != "straight" or not _num(lap_distance_m):
        return ()
    current, ref_samples = _sample_maps(performance, reference)
    if not current or not ref_samples:
        return ()
    lo, hi = float(segment["start_m"]), float(segment["end_m"])
    end = min(float(lap_distance_m), hi)
    if end <= lo + 5.0:
        return (
            CoachMetric("Straight Time", "--", "WAIT"), CoachMetric("Entry Speed", "--", "WAIT"),
            CoachMetric("Avg Speed", "--", "WAIT"), CoachMetric("Top Speed", "--", "WAIT"),
        )
    trace = _aligned_live_trace(performance, reference) if trace is None else trace
    a = _trace_nearest(trace, lo, tolerance_m=15.0)
    b = _trace_nearest(trace, end, tolerance_m=15.0)
    local_delta = (float(b)-float(a)) if _num(a) and _num(b) else None

    # The aligned trace already contains the sorted common distance bins. Reuse
    # it for straight speed comparison instead of intersecting/sorting maps again.
    lo_i = bisect_left(trace, lo, key=lambda row: row[0])
    hi_i = bisect_right(trace, end, key=lambda row: row[0])
    common = [row[0] for row in trace[lo_i:hi_i]]
    cur_speeds = []
    ref_speeds = []
    for d in common:
        cs = _sample_value(current[d], "speed")
        rs = _sample_value(ref_samples[d], "speed")
        if _num(cs) and _num(rs):
            cur_speeds.append(float(cs)); ref_speeds.append(float(rs))
    entry_delta = None
    entry_point = _trace_nearest_point(trace, lo, tolerance_m=15.0)
    if entry_point is not None:
        d = entry_point[0]
        c_entry, r_entry = current.get(d), ref_samples.get(d)
        if c_entry is not None and r_entry is not None:
            cs, rs = _sample_value(c_entry, "speed"), _sample_value(r_entry, "speed")
            if _num(cs) and _num(rs): entry_delta = float(cs)-float(rs)
    avg_delta = (sum(cur_speeds)/len(cur_speeds) - sum(ref_speeds)/len(ref_speeds)) if cur_speeds else None
    top_delta = (max(cur_speeds)-max(ref_speeds)) if cur_speeds else None
    return (
        _time_metric("Straight Time", local_delta),
        _metric("Entry Speed", entry_delta, unit=" kph", positive="faster", negative="slower", tolerance=2.0),
        _metric("Avg Speed", avg_delta, unit=" kph", positive="faster", negative="slower", tolerance=1.5),
        _metric("Top Speed", top_delta, unit=" kph", positive="faster", negative="slower", tolerance=1.5),
    )


def _segment_history_from_trace(trace: list[tuple[float, float]], reference: dict | None, track_length_m: float | None, *, current_end: float | None = None, segments=None) -> tuple[SectionHistory, ...]:
    if reference is None or len(trace) < 2:
        return ()
    segments = _track_segments(reference, track_length_m) if segments is None else segments
    if not segments:
        return ()
    if current_end is None:
        current_end = trace[-1][0]
    rows = []
    for seg in segments:
        lo, hi = float(seg["start_m"]), float(seg["end_m"])
        if float(current_end) + 1e-9 < hi:
            break
        a = _trace_nearest(trace, lo, tolerance_m=20.0)
        b = _trace_nearest(trace, hi, tolerance_m=20.0)
        rows.append(SectionHistory(section=int(seg["number"]), delta_s=(float(b)-float(a)) if _num(a) and _num(b) else None, kind=str(seg["kind"])))
    return tuple(rows)


def _trace_nearest_point(trace: list[tuple[float, float]], distance: float, tolerance_m: float = 10.0):
    if not trace:
        return None
    i = bisect_left(trace, distance, key=lambda row: row[0])
    if i <= 0:
        point = trace[0]
    elif i >= len(trace):
        point = trace[-1]
    else:
        before, after = trace[i-1], trace[i]
        point = before if distance - before[0] <= after[0] - distance else after
    return point if abs(point[0] - distance) <= tolerance_m else None


def _trace_nearest(trace: list[tuple[float, float]], distance: float, tolerance_m: float = 10.0) -> float | None:
    point = _trace_nearest_point(trace, distance, tolerance_m)
    return point[1] if point is not None else None


def _live_section_history(performance, reference: dict | None, active_section: int | None = None, track_length_m: float | None = None, *, trace=None, segments=None) -> tuple[SectionHistory, ...]:
    """Compatibility name; now returns completed straight + turn segment deltas."""
    if reference is None:
        return ()
    trace = _aligned_live_trace(performance, reference) if trace is None else trace
    return _segment_history_from_trace(trace, reference, track_length_m, segments=segments)


def _completed_section_history(comparison_lap: dict | None, reference: dict | None, active_section: int | None = None, track_length_m: float | None = None, *, track_name: object = None) -> tuple[SectionHistory, ...]:
    """Compatibility name; completed-lap history now includes physical straights and turns."""
    if comparison_lap is None or reference is None:
        return ()
    trace = _aligned_trace_from_maps(comparison_lap.get("_samples", {}) or {}, reference.get("_samples", {}) or {})
    segments = _track_segments(reference, track_length_m, track_name=track_name)
    return _segment_history_from_trace(trace, reference, track_length_m, segments=segments)



def _enum_name(value: Any) -> str | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    return str(value)


def _wheel_values(wheels) -> tuple[float | None, float | None, float | None, float | None]:
    if wheels is None:
        return (None, None, None, None)
    out = []
    for key in ("FL", "FR", "RL", "RR"):
        value = getattr(wheels, key, None)
        out.append(float(value) if _num(value) else None)
    return tuple(out)  # type: ignore[return-value]


def _metric_enabled(event_context: dict, name: str, *, default: bool = True) -> bool:
    metrics = event_context.get("metrics", {}) if isinstance(event_context, dict) else {}
    if isinstance(metrics, dict) and name in metrics:
        return bool(metrics[name])
    return bool(default)


def _tyre_overlay_data(state, player, event_context: dict):
    tyres = getattr(player, "tyres", None) if player is not None else None
    current = _wheel_values(getattr(tyres, "wear_percent", None))
    profile = event_context.get("profile") if isinstance(event_context, dict) else None
    applicable = _metric_enabled(event_context, "tyre_wear_strategy", default=profile != "time_trial")
    current_set = getattr(tyres, "fitted_set_index", None) if tyres is not None else None
    facts = list(getattr(state, "measured_laps", ()) or ())
    rows = []
    deltas = []
    for fact in facts:
        fact_set = getattr(fact, "fitted_tyre_set_index", None)
        if current_set is not None and fact_set is not None and fact_set != current_set:
            continue
        wear_end = getattr(fact, "tyre_wear_end", None)
        if wear_end is not None:
            fl, fr, rl, rr = _wheel_values(wear_end)
            vals = [x for x in (fl, fr, rl, rr) if _num(x)]
            rows.append(TyreWearLap(
                lap=int(getattr(fact, "lap_number", 0) or 0), fl=fl, fr=fr, rl=rl, rr=rr,
                life_percent=(100.0 - max(vals)) if vals else None,
            ))
        delta = getattr(fact, "tyre_wear_delta", None)
        if delta is not None:
            values = _wheel_values(delta)
            if all(v is not None and 0.0 <= v <= 20.0 for v in values):
                deltas.append(values)
    rows = rows[-5:]
    estimate = None
    if applicable and all(v is not None for v in current) and deltas:
        wheel_estimates = []
        for i, current_wear in enumerate(current):
            samples = [d[i] for d in deltas[-5:] if d[i] is not None and d[i] > 0.02]
            if not samples:
                continue
            avg = sum(samples) / len(samples)
            wheel_estimates.append(max(0.0, (100.0 - float(current_wear)) / avg))
        if wheel_estimates:
            estimate = min(wheel_estimates)
    return applicable, current, estimate, tuple(rows)


def _fuel_overlay_data(state, player, event_context: dict):
    fuel = getattr(player, "fuel", None) if player is not None else None
    profile = event_context.get("profile") if isinstance(event_context, dict) else None
    applicable = _metric_enabled(event_context, "fuel_strategy", default=profile != "time_trial")
    remaining = getattr(fuel, "remaining_mass", None) if fuel is not None else None
    remaining_laps = getattr(fuel, "remaining_laps", None) if fuel is not None else None
    facts = [f for f in (getattr(state, "measured_laps", ()) or ()) if _num(getattr(f, "fuel_used", None))]
    recent = facts[-5:]
    used_values = [float(getattr(f, "fuel_used")) for f in recent if _num(getattr(f, "fuel_used", None))]
    average = sum(used_values) / len(used_values) if used_values else None
    rows = []
    for fact in recent:
        used = float(getattr(fact, "fuel_used")) if _num(getattr(fact, "fuel_used", None)) else None
        end = getattr(fact, "fuel_remaining_end", None)
        rows.append(FuelLap(
            lap=int(getattr(fact, "lap_number", 0) or 0),
            used=used,
            remaining=float(end) if _num(end) else None,
            diff=(used - average) if used is not None and average is not None else None,
        ))
    return applicable, (float(remaining) if _num(remaining) else None), (float(remaining_laps) if _num(remaining_laps) else None), tuple(rows)


def _weather_overlay_data(state, event_context: dict):
    session = getattr(state, "session", None)
    profile = event_context.get("profile") if isinstance(event_context, dict) else None
    applicable = _metric_enabled(event_context, "weather_strategy", default=profile != "time_trial")
    now_weather = _enum_name(getattr(session, "weather", None)) if session is not None else None
    accuracy = _enum_name(getattr(session, "forecast_accuracy", None)) if session is not None else None
    rows = []
    forecast_rows = list(getattr(session, "forecast", ()) or ())
    # EA can include forecast samples for more than one session in the same
    # Session packet (for example One-Shot Qualifying followed by Race). The
    # live Weather overlay must show the active session only rather than merging
    # two separate NOW/+5/+10 sequences into one table.
    current_type = getattr(getattr(session, "session_type", None), "raw", None) if session is not None else None
    if current_type is not None:
        matching = [row for row in forecast_rows if getattr(getattr(row, "session_type", None), "raw", None) == current_type]
        if matching:
            forecast_rows = matching
    for row in forecast_rows[:7]:
        rows.append(WeatherForecastRow(
            offset_minutes=int(getattr(row, "offset_minutes", 0) or 0),
            weather=_enum_name(getattr(row, "weather", None)) or "Unknown",
            rain_percent=int(getattr(row, "rain_percent", 0)) if getattr(row, "rain_percent", None) is not None else None,
            track_temperature_c=int(getattr(row, "track_temperature_c", 0)) if getattr(row, "track_temperature_c", None) is not None else None,
            air_temperature_c=int(getattr(row, "air_temperature_c", 0)) if getattr(row, "air_temperature_c", None) is not None else None,
        ))
    # UI-R8: the current weather card must never depend on forecast rows being
    # populated. The Session packet already carries live weather and live track/air
    # temperatures. If EA has not supplied a zero-minute forecast sample, prepend
    # a presentation-only NOW row from those authoritative live fields.
    if now_weather is not None and not any(int(getattr(row, "offset_minutes", -1)) == 0 for row in rows):
        rows.insert(0, WeatherForecastRow(
            offset_minutes=0,
            weather=now_weather,
            rain_percent=None,
            track_temperature_c=int(getattr(session, "track_temperature_c")) if _num(getattr(session, "track_temperature_c", None)) else None,
            air_temperature_c=int(getattr(session, "air_temperature_c")) if _num(getattr(session, "air_temperature_c", None)) else None,
        ))
    return applicable, now_weather, accuracy, tuple(rows[:7])


def _standings_overlay_data(state, event_context: dict):
    profile = event_context.get("profile") if isinstance(event_context, dict) else None
    player_index = getattr(state, "player_index", None)
    player = getattr(state, "player", None)
    player_lap = getattr(player, "lap", None) if player is not None else None
    player_pos = getattr(player_lap, "position", None) if player_lap is not None else None
    player_leader_gap = getattr(player_lap, "gap_to_leader_s", None) if player_lap is not None else None
    if player_pos == 1:
        player_leader_gap = 0.0
    rows_all = []
    for idx, car in (getattr(state, "field", {}) or {}).items():
        pos = getattr(getattr(car, "lap", None), "position", None)
        if not isinstance(pos, int) or pos <= 0:
            continue
        ident = getattr(car, "identity", None)
        name = getattr(ident, "name", None) or f"CAR {idx}"
        team = _enum_name(getattr(ident, "team", None)) or ""
        gap_leader = getattr(getattr(car, "lap", None), "gap_to_leader_s", None)
        if pos == 1:
            gap_leader = 0.0
        gap_player = None
        if _num(gap_leader) and _num(player_leader_gap):
            gap_player = float(gap_leader) - float(player_leader_gap)
        compound = _enum_name(getattr(getattr(car, "tyres", None), "visual_compound", None))
        rows_all.append(StandingRow(pos, str(name), team, gap_player, compound, idx == player_index))
    rows_all.sort(key=lambda row: row.position)
    applicable = profile != "time_trial" and len(rows_all) > 1
    if isinstance(player_pos, int):
        # Five-row viewport centred on the player where possible.
        start = max(0, min(len(rows_all) - 5, player_pos - 3))
        rows = rows_all[start:start + 5]
    else:
        rows = rows_all[:5]
    return applicable, tuple(rows)


def _lap_history_overlay_data(performance, reference: dict | None):
    """Build history against the *currently active* comparison reference.

    Historical lap deltas are intentionally recalculated whenever the selected
    reference changes.  The BEST marker, however, belongs to the driver's
    fastest valid lap in this live/replay session; it must never be inferred
    from the reference lap number because an external reference can coincidentally
    carry the same lap number as one of our own laps.
    """
    completed = [lap for lap in (getattr(performance, "completed", ()) or ()) if _num(lap.get("lap_time_s"))]
    ref_time = reference.get("lap_time_s") if reference else None
    valid = [lap for lap in completed if lap.get("valid") and _num(lap.get("lap_time_s")) and float(lap["lap_time_s"]) > 0]
    best_session_lap = min(valid, key=lambda lap: float(lap["lap_time_s"])) if valid else None
    best_session_lap_num = best_session_lap.get("lap") if best_session_lap is not None else None
    rows = []
    for lap in completed[-8:]:
        lap_time = float(lap["lap_time_s"])
        s1 = lap.get("sector1_time_s")
        s2 = lap.get("sector2_time_s")
        s3 = lap.get("sector3_time_s")
        if not _num(s3) and _num(s1) and _num(s2):
            s3 = lap_time - float(s1) - float(s2)
        rows.append(LapHistoryRow(
            lap=int(lap.get("lap", 0) or 0),
            lap_time_s=lap_time,
            delta_s=(lap_time - float(ref_time)) if _num(ref_time) else None,
            sector1_s=float(s1) if _num(s1) else None,
            sector2_s=float(s2) if _num(s2) else None,
            sector3_s=float(s3) if _num(s3) else None,
            valid=bool(lap.get("valid")),
            best=bool(lap.get("valid") and lap.get("lap") == best_session_lap_num),
        ))
    return tuple(reversed(rows))


def _tyre_sets_overlay_data(player, event_context: dict):
    profile = event_context.get("profile") if isinstance(event_context, dict) else None
    tyres = getattr(player, "tyres", None) if player is not None else None
    rows = []
    for tyre_set in (getattr(tyres, "sets", ()) or ()):
        available = getattr(tyre_set, "available", None)
        fitted = getattr(tyre_set, "fitted", None)
        compound = _enum_name(getattr(tyre_set, "visual_compound", None)) or _enum_name(getattr(tyre_set, "actual_compound", None)) or "Unknown"
        if not (available is True or fitted is True):
            continue
        rows.append(TyreSetRow(
            index=int(getattr(tyre_set, "index", 0)),
            compound=compound,
            wear_percent=int(getattr(tyre_set, "wear_percent", 0) or 0),
            available=available,
            recommended_session=_enum_name(getattr(tyre_set, "recommended_session", None)) or "Unknown",
            lifespan_laps=int(getattr(tyre_set, "lifespan_laps", 0) or 0),
            usable_life_laps=int(getattr(tyre_set, "usable_life_laps", 0) or 0),
            lap_delta_s=float(getattr(tyre_set, "lap_delta_s", 0.0) or 0.0),
            fitted=fitted,
        ))
    applicable = profile != "time_trial" and bool(rows)
    return applicable, tuple(rows)


def _race_engineer_overlay_data(state, tyre_life_estimate_laps: float | None) -> RaceEngineerState:
    player = getattr(state, "player", None)
    session = getattr(state, "session", None)
    finished = _session_finished(state)
    try:
        plan = service_plan(state)
        pit = plan.pit
    except Exception:
        plan = None
        pit = None

    if pit is None:
        applicable = False
        decision = "NO DECISION"
        urgency = "unknown"
        confidence = "low"
        reason = "strategy data unavailable"
    else:
        applicable = pit.recommendation_hint != "not_applicable"
        mapping = {
            "box_now": "BOX THIS LAP",
            "box_soon": "BOX SOON",
            "consider_box": "CONSIDER BOX",
            "stay_out": "STAY OUT",
            "insufficient_data": "NO DECISION",
            "not_applicable": "NOT APPLICABLE",
        }
        decision = "FINISHED" if finished else mapping.get(pit.recommendation_hint, "NO DECISION")
        urgency = pit.urgency
        confidence = pit.confidence
        if finished:
            reason = "race finished"
        elif pit.recommendation_hint == "stay_out" and pit.data_sufficient:
            reason = "no immediate serviceable pit trigger"
        elif pit.recommendation_hint == "insufficient_data":
            reason = "insufficient deterministic race data"
        else:
            reason = pit.reasons[0] if pit.reasons else None

    lap = getattr(player, "lap", None) if player is not None else None
    tyres = getattr(player, "tyres", None) if player is not None else None
    fuel = getattr(player, "fuel", None) if player is not None else None
    damage = getattr(player, "damage", None) if player is not None else None

    current_lap = getattr(lap, "current_lap", None) if lap is not None else None
    total_laps = getattr(session, "total_laps", None) if session is not None else None
    laps_remaining = None
    if isinstance(total_laps, int) and isinstance(current_lap, int):
        laps_remaining = max(0, total_laps - current_lap)

    # Once the car is on the scheduled final lap there is no useful normal pit
    # strategy left to present. Keep the live facts, but force a terminal driving
    # instruction instead of suggesting a tyre or another strategic stop.
    final_lap = bool(
        not finished
        and applicable
        and isinstance(total_laps, int)
        and total_laps > 0
        and isinstance(current_lap, int)
        and current_lap >= total_laps
    )
    if final_lap:
        decision = "FINISH THE RACE"
        urgency = "final_lap"
        confidence = "high"
        reason = "final lap — no strategic stop remaining"

    wear_values = _wheel_values(getattr(tyres, "wear_percent", None)) if tyres is not None else []
    wear_values = [float(v) for v in wear_values if _num(v)]
    max_wear = max(wear_values) if wear_values else None

    fl = getattr(damage, "front_left_wing_percent", None) if damage is not None else None
    fr = getattr(damage, "front_right_wing_percent", None) if damage is not None else None
    fw_values = [int(v) for v in (fl, fr) if isinstance(v, (int, float))]
    front_wing = max(fw_values) if fw_values else None

    rain = None
    current_type = getattr(getattr(session, "session_type", None), "raw", None) if session is not None else None
    for fc in (getattr(session, "forecast", ()) or ()):
        if getattr(fc, "offset_minutes", None) != 0:
            continue
        fc_type = getattr(getattr(fc, "session_type", None), "raw", None)
        if current_type is None or fc_type == current_type:
            rain = getattr(fc, "rain_percent", None)
            break

    tyre_choice = getattr(plan, "tyre", None) if plan is not None else None
    next_compound = getattr(tyre_choice, "compound", None) if getattr(tyre_choice, "available", False) else None
    next_set = getattr(tyre_choice, "set_index", None) if getattr(tyre_choice, "available", False) else None

    return RaceEngineerState(
        applicable=bool(applicable),
        decision=decision,
        urgency=urgency,
        confidence=confidence,
        reason=reason,
        position=getattr(lap, "position", None) if lap is not None else None,
        lap_number=current_lap,
        total_laps=total_laps,
        laps_remaining=laps_remaining,
        current_compound=_enum_name(getattr(tyres, "visual_compound", None)) if tyres is not None else None,
        tyre_age_laps=getattr(tyres, "age_laps", None) if tyres is not None else None,
        max_wear_percent=max_wear,
        tyre_life_estimate_laps=tyre_life_estimate_laps,
        fuel_margin_laps=float(getattr(fuel, "remaining_laps")) if fuel is not None and _num(getattr(fuel, "remaining_laps", None)) else None,
        fuel_remaining_mass=float(getattr(fuel, "remaining_mass")) if fuel is not None and _num(getattr(fuel, "remaining_mass", None)) else None,
        next_tyre_compound=next_compound,
        next_tyre_set=next_set,
        front_wing_damage_percent=front_wing,
        penalties_s=getattr(lap, "penalties_s", None) if lap is not None else None,
        serve_penalty=(bool(getattr(lap, "pit_stop_should_serve_penalty", False) or getattr(lap, "unserved_stop_go", 0)) if lap is not None else None),
        weather=_enum_name(getattr(session, "weather", None)) if session is not None else None,
        rain_percent=int(rain) if rain is not None else None,
        safety_car=_enum_name(getattr(session, "safety_car", None)) if session is not None else None,
        pit_status=_enum_name(getattr(lap, "pit_status", None)) if lap is not None else None,
        session_finished=finished,
    )


def build_overlay_snapshot(state, performance, *, connected: bool, now: float | None = None) -> OverlaySnapshot:
    now = time.monotonic() if now is None else now
    player = getattr(state, "player", None)
    telemetry = getattr(player, "telemetry", None) if player is not None else None
    lap = getattr(player, "lap", None) if player is not None else None
    reference = _reference_lap(performance)
    completed_comparison = _latest_comparable_lap(performance, reference)
    lap_distance = getattr(lap, "lap_distance_m", None) if lap is not None else None
    lap_number = getattr(lap, "current_lap", None) if lap is not None else None
    event_context = getattr(performance, "event_context", None) or {}
    profile = event_context.get("profile") if isinstance(event_context, dict) else None
    session = getattr(state, "session", None)
    session_finished = _session_finished(state)
    track_name = _enum_name(getattr(session, "track", None)) if session is not None else None
    track_length = getattr(session, "track_length_m", None) if session is not None else None
    if not _num(track_length) and reference:
        ref_samples = reference.get("_samples", {}) or {}
        if ref_samples:
            track_length = max(float(x) for x in ref_samples)
    segments = _track_segments(reference, track_length, track_name=track_name) if reference is not None else ()
    live_trace = [] if session_finished else _aligned_live_trace(performance, reference)
    active_segment = None if session_finished else _active_segment(reference, lap_distance, track_length, segments=segments)
    section = int(active_segment["number"]) if active_segment and active_segment.get("kind") == "turn" else None

    throttle = getattr(telemetry, "throttle", None) if telemetry is not None else None
    brake = getattr(telemetry, "brake", None) if telemetry is not None else None
    energy = getattr(player, "energy", None) if player is not None else None
    throttle = max(0.0, min(1.0, float(throttle))) if _num(throttle) else 0.0
    brake = max(0.0, min(1.0, float(brake))) if _num(brake) else 0.0

    # Authoritative setup data for the F1 dashboard status strip. Missing packet
    # means missing value; the UI displays "--" rather than inventing a setup.
    setup_car = None
    extended = getattr(state, "extended", None)
    setup_packet = extended.get("setups") if isinstance(extended, dict) else None
    player_index = getattr(state, "player_index", None)
    setup_rows = getattr(setup_packet, "m_carSetupData", None) if setup_packet is not None else None
    if isinstance(player_index, int) and setup_rows is not None and 0 <= player_index < len(setup_rows):
        setup_car = setup_rows[player_index]

    motion_car = None
    motion_packet = extended.get("motion") if isinstance(extended, dict) else None
    motion_rows = getattr(motion_packet, "m_carMotionData", None) if motion_packet is not None else None
    if isinstance(player_index, int) and motion_rows is not None and 0 <= player_index < len(motion_rows):
        motion_car = motion_rows[player_index]

    current_samples = getattr(performance, "samples", None) or {}

    # Physical-track learning normally happens at the recorder's authoritative
    # lap boundary. Keep this lightweight first-map fallback for older/replayed
    # data paths that already contain a clean completed lap before the UI starts.
    map_exists = bool(track_name and get_track_map(track_name) is not None)
    map_has_distance_axis = bool(track_name and get_track_map_distances(track_name))
    if track_name and (not map_exists or not map_has_distance_axis) and _num(track_length):
        for completed_lap in reversed(getattr(performance, "completed", ()) or ()):
            if not clean_geometry_lap(completed_lap):
                continue
            if save_learned_track_map_samples(track_name, completed_lap.get("_samples") or {}, track_length):
                map_exists=True;map_has_distance_axis=True
                break
    map_learning_points = ()
    if track_name and get_track_map(track_name) is None and bool(getattr(performance, "current_lap_started_clean", False)):
        map_learning_points = live_map_trace(current_samples)
    coaching_status = extended.get("coaching_suite") if isinstance(extended, dict) else None
    corner_status = extended.get("corner_coach") if isinstance(extended, dict) else None
    live_corner_result = None
    last_lap_intelligence = None
    # Use the authoritative game/session clock for both live-corner and lap/stint
    # expiry.  This must be resolved before either result path is evaluated; an
    # earlier V2.0.2 build referenced an undefined local (session_time_s), which
    # caused the overlay snapshot refresh to fail repeatedly after selecting a
    # reference lap.
    current_session_s = getattr(session, "session_time_s", None) if session is not None else None
    if isinstance(corner_status, dict) and isinstance(corner_status.get("last_lap_intelligence"), dict):
        # Dedicated LAP / STINT INTELLIGENCE owns this result now. Keep the most
        # recent completed-lap summary visible until it is replaced by the next
        # completed lap/session reset; live corner cards must not hide it.
        last_lap_intelligence=dict(corner_status.get("last_lap_intelligence") or {})
    if isinstance(corner_status, dict) and isinstance(corner_status.get("live_corner_result"), dict):
        candidate = dict(corner_status.get("live_corner_result") or {})
        expires = candidate.get("expires_session_s")
        race_context = coaching_status.get("race_context") if isinstance(coaching_status, dict) else None
        attention_ok = not isinstance(race_context, dict) or bool(race_context.get("technique_coaching_allowed", True))
        if attention_ok and (not _num(expires) or not _num(current_session_s) or float(current_session_s) <= float(expires)):
            live_corner_result = candidate
    corner_distance = corner_status.get("distance_performance") if isinstance(corner_status, dict) else None
    if isinstance(corner_status,dict):
        # In V1.1 CORNER COACH owns the live gain/loss visualization.  When its
        # master/G-L child is OFF, do not resurrect the legacy coach's map layer.
        distance_status=(corner_distance if bool(corner_status.get("gain_loss_enabled")) and isinstance(corner_distance,dict) and corner_distance.get("available") else None)
    else:
        distance_status=(coaching_status.get("distance_performance") if isinstance(coaching_status, dict) else None)
    map_gain_loss_zones=[]
    map_performance_segments=[]
    map_reconciliation_error=None
    map_full_track_delta=None
    if isinstance(distance_status, dict):
        for row in distance_status.get("gain_loss_zones") or ():
            if not isinstance(row,dict) or not (_num(row.get("start_m")) and _num(row.get("end_m"))):
                continue
            map_gain_loss_zones.append(MapGainLossZone(float(row["start_m"]),float(row["end_m"]),str(row.get("state") or "NEUTRAL"),float(row["net_delta_s"]) if _num(row.get("net_delta_s")) else None))
        for row in distance_status.get("segments") or ():
            if not isinstance(row,dict) or not (_num(row.get("start_m")) and _num(row.get("end_m"))):
                continue
            number=row.get("number")
            if not isinstance(number,int):
                continue
            map_performance_segments.append(MapPerformanceSegment(str(row.get("segment_kind") or "unknown"),number,str(row.get("label") or ""),float(row["start_m"]),float(row["end_m"]),float(row["net_loss_s"]) if _num(row.get("net_loss_s")) else None,bool(row.get("complete"))))
        if _num(distance_status.get("reconciliation_error_s")):
            map_reconciliation_error=float(distance_status["reconciliation_error_s"])
        if _num(distance_status.get("full_track_net_delta_s")):
            map_full_track_delta=float(distance_status["full_track_net_delta_s"])
    live_coach = bool(
        not session_finished
        and reference is not None
        and current_samples
        and bool(getattr(performance, "current_lap_started_clean", _trace_has_lap_start(current_samples)))
        and _trace_has_lap_start(reference.get("_samples", {}) or {})
        and lap_number is not None
        and (getattr(performance, "reference_mode", "best") == "external" or lap_number != reference.get("lap"))
    )
    corner_quality=(corner_status.get("quality") or {}) if isinstance(corner_status,dict) else {}
    reference_inputs_trusted=bool(corner_quality.get("input_telemetry_trusted",True))
    trusted_turn_metrics=(corner_status.get("trusted_turn_metrics") or ()) if isinstance(corner_status,dict) else ()
    if live_coach:
        if active_segment and active_segment.get("kind") == "straight":
            metrics = _straight_coach_metrics(performance, reference, active_segment, lap_distance, trace=live_trace)
        else:
            metrics = _live_coach_metrics(performance, reference, section, lap_distance, track_name=track_name, input_telemetry_trusted=reference_inputs_trusted, trusted_turn_metrics=trusted_turn_metrics)
        history = _live_section_history(performance, reference, section, track_length, trace=live_trace, segments=segments)
        coach_lap = lap_number
    else:
        metrics = _completed_coach_metrics(completed_comparison, reference, section, track_name=track_name, input_telemetry_trusted=reference_inputs_trusted, trusted_turn_metrics=trusted_turn_metrics) if section is not None else ()
        history = _completed_section_history(completed_comparison, reference, section, track_length, track_name=track_name)
        coach_lap = completed_comparison.get("lap") if completed_comparison else None

    live_delta = None if session_finished else _live_delta(performance, reference, trace=live_trace)
    ref_sample = _reference_sample_at_distance(reference, lap_distance)
    reference_map_distance = _reference_distance_at_time(reference, getattr(lap, "current_lap_time_s", None) if lap is not None else None)
    nearby_map_markers = _nearby_map_markers(state, getattr(lap, "position", None) if lap is not None else None)
    ref_throttle = _sample_value(ref_sample, "throttle") if ref_sample is not None else None
    ref_brake = _sample_value(ref_sample, "brake") if ref_sample is not None else None
    ref_ers = _sample_value(ref_sample, "ers_j") if ref_sample is not None else None
    ref_speed = _sample_value(ref_sample, "speed") if ref_sample is not None else None
    ref_gear = _sample_value(ref_sample, "gear") if ref_sample is not None else None
    ref_time = _sample_value(ref_sample, "t") if ref_sample is not None else None
    ref_name = _reference_display_name(performance, reference)
    delta_dots, delta_dot_kinds, delta_dot_sectors = _track_structure_delta_dots(performance, reference, track_length, trace=live_trace, segments=segments)
    s_mode_metric = None if session_finished else _s_mode_enable_metric(performance, event_context)

    tyre_wear_applicable, tyre_wear, tyre_laps_remaining_estimate, tyre_wear_history = _tyre_overlay_data(state, player, event_context)
    fuel_applicable, fuel_remaining_mass, fuel_remaining_laps, fuel_history = _fuel_overlay_data(state, player, event_context)
    weather_applicable, weather_now, forecast_accuracy, weather_forecast = _weather_overlay_data(state, event_context)
    standings_applicable, standings = _standings_overlay_data(state, event_context)
    lap_history = _lap_history_overlay_data(performance, reference)
    tyre_sets_applicable, tyre_sets = _tyre_sets_overlay_data(player, event_context)
    race_engineer = _race_engineer_overlay_data(state, tyre_laps_remaining_estimate)

    return OverlaySnapshot(
        connected=bool(connected),
        event_profile=_fmt_profile(profile),
        session_type=_enum_name(getattr(session, "session_type", None)) if session is not None else None,
        speed_kph=getattr(telemetry, "speed_kph", None) if telemetry is not None else None,
        gear=getattr(telemetry, "gear", None) if telemetry is not None else None,
        throttle=throttle,
        brake=brake,
        steering=getattr(telemetry, "steering", None) if telemetry is not None else None,
        ers_store_j=getattr(energy, "store_j", None) if energy is not None else None,
        ers_harvested_j=(
            (float(getattr(energy, "harvested_mguk_j", 0.0) or 0.0) + float(getattr(energy, "harvested_mguh_j", 0.0) or 0.0))
            if energy is not None and (
                _num(getattr(energy, "harvested_mguk_j", None)) or _num(getattr(energy, "harvested_mguh_j", None))
            ) else None
        ),
        ers_deployed_j=getattr(energy, "deployed_this_lap_j", None) if energy is not None else None,
        lap_number=lap_number,
        position=getattr(lap, "position", None) if lap is not None else None,
        total_laps=getattr(session, "total_laps", None) if session is not None else None,
        current_compound=_enum_name(getattr(getattr(player, "tyres", None), "visual_compound", None)) if player is not None else None,
        tyre_age_laps=getattr(getattr(player, "tyres", None), "age_laps", None) if player is not None else None,
        tyre_set_index=getattr(getattr(player, "tyres", None), "fitted_set_index", None) if player is not None else None,
        front_wing_damage_percent=(
            max([int(v) for v in (
                getattr(getattr(player, "damage", None), "front_left_wing_percent", None),
                getattr(getattr(player, "damage", None), "front_right_wing_percent", None),
            ) if isinstance(v, (int, float))], default=None)
            if player is not None else None
        ),
        penalties_s=getattr(lap, "penalties_s", None) if lap is not None else None,
        warnings=getattr(lap, "warnings", None) if lap is not None else None,
        corner_cutting_warnings=getattr(lap, "corner_cutting_warnings", None) if lap is not None else None,
        serve_penalty=(
            bool(getattr(lap, "pit_stop_should_serve_penalty", False) or getattr(lap, "unserved_stop_go", 0))
            if lap is not None else None
        ),
        safety_car=_enum_name(getattr(session, "safety_car", None)) if session is not None else None,
        pit_status=_enum_name(getattr(lap, "pit_status", None)) if lap is not None else None,
        driver_status=_enum_name(getattr(lap, "driver_status", None)) if lap is not None else None,
        session_time_left_s=getattr(session, "time_left_s", None) if session is not None else None,
        session_duration_s=getattr(session, "duration_s", None) if session is not None else None,
        sector=getattr(lap, "sector", None) if lap is not None else None,
        sector1_time_s=getattr(lap, "sector1_time_s", None) if lap is not None else None,
        sector2_time_s=getattr(lap, "sector2_time_s", None) if lap is not None else None,
        sector1_delta_s=(float(getattr(lap, "sector1_time_s")) - float(reference.get("sector1_time_s")))
            if lap is not None and reference and _num(getattr(lap, "sector1_time_s", None)) and _num(reference.get("sector1_time_s")) else None,
        sector2_delta_s=(float(getattr(lap, "sector2_time_s")) - float(reference.get("sector2_time_s")))
            if lap is not None and reference and _num(getattr(lap, "sector2_time_s", None)) and _num(reference.get("sector2_time_s")) else None,
        track_length_m=float(track_length) if _num(track_length) else None,
        delta_dots=delta_dots,
        delta_dot_kinds=delta_dot_kinds,
        delta_dot_sectors=delta_dot_sectors,
        lap_valid=getattr(lap, "lap_valid", None) if lap is not None else None,
        lap_time_s=None if session_finished else (getattr(lap, "current_lap_time_s", None) if lap is not None else None),
        lap_distance_m=lap_distance,
        best_lap_time_s=reference.get("lap_time_s") if reference else None,
        reference_lap=reference.get("lap") if reference else None,
        live_delta_s=live_delta,
        reference_throttle=(max(0.0,min(1.0,float(ref_throttle))) if _num(ref_throttle) else None),
        reference_brake=(max(0.0,min(1.0,float(ref_brake))) if _num(ref_brake) else None),
        reference_ers_store_j=(float(ref_ers) if _num(ref_ers) else None),
        reference_speed_kph=(int(round(float(ref_speed))) if _num(ref_speed) else None),
        reference_gear=(int(ref_gear) if _num(ref_gear) else None),
        reference_time_s=(float(ref_time) if _num(ref_time) else None),
        reference_name=ref_name,
        active_section=section,
        active_segment_kind=str(active_segment.get("kind")) if active_segment else None,
        active_segment_number=int(active_segment.get("number")) if active_segment else None,
        active_segment_start_m=(float(active_segment.get("start_m")) if active_segment and _num(active_segment.get("start_m")) else None),
        active_segment_end_m=(float(active_segment.get("end_m")) if active_segment and _num(active_segment.get("end_m")) else None),
        comparison_lap=coach_lap,
        coach_live=live_coach,
        coach_metrics=metrics,
        s_mode_metric=s_mode_metric,
        previous_sections=history,
        tyre_wear_applicable=tyre_wear_applicable,
        tyre_wear=tyre_wear,
        tyre_laps_remaining_estimate=tyre_laps_remaining_estimate,
        tyre_wear_history=tyre_wear_history,
        fuel_applicable=fuel_applicable,
        fuel_remaining_mass=fuel_remaining_mass,
        fuel_capacity=getattr(getattr(player, "fuel", None), "capacity", None) if player is not None else None,
        fuel_remaining_laps=fuel_remaining_laps,
        fuel_history=fuel_history,
        weather_applicable=weather_applicable,
        weather_now=weather_now,
        forecast_accuracy=forecast_accuracy,
        weather_forecast=weather_forecast,
        standings_applicable=standings_applicable,
        standings=standings,
        lap_history=lap_history,
        tyre_sets_applicable=tyre_sets_applicable,
        tyre_sets=tyre_sets,
        race_engineer=race_engineer,
        session_finished=session_finished,
        game_paused=bool(getattr(session, "paused", False)) if session is not None else False,
        rpm=getattr(telemetry, "rpm", None) if telemetry is not None else None,
        rev_lights_percent=getattr(telemetry, "rev_lights_percent", None) if telemetry is not None else None,
        drs_active=getattr(telemetry, "drs", None) if telemetry is not None else None,
        drs_allowed=getattr(getattr(player, "aero", None), "drs_allowed", None) if player is not None else None,
        overtake_active=getattr(getattr(player, "aero", None), "overtake_active", None) if player is not None else None,
        overtake_available=getattr(getattr(player, "aero", None), "overtake_available", None) if player is not None else None,
        ers_deploy_mode=_enum_name(getattr(energy, "deploy_mode", None)) if energy is not None else None,
        tyre_surface_temperatures_c=_wheel_values(getattr(getattr(player, "tyres", None), "surface_temperature_c", None)) if player is not None else (None, None, None, None),
        tyre_inner_temperatures_c=_wheel_values(getattr(getattr(player, "tyres", None), "inner_temperature_c", None)) if player is not None else (None, None, None, None),
        setup_diff_on_throttle_percent=(float(getattr(setup_car, "m_onThrottle")) if setup_car is not None and _num(getattr(setup_car, "m_onThrottle", None)) else None),
        setup_diff_off_throttle_percent=(float(getattr(setup_car, "m_offThrottle")) if setup_car is not None and _num(getattr(setup_car, "m_offThrottle", None)) else None),
        setup_brake_bias_percent=(float(getattr(setup_car, "m_brakeBias")) if setup_car is not None and _num(getattr(setup_car, "m_brakeBias", None)) else None),
        setup_engine_braking_percent=(float(getattr(setup_car, "m_engineBraking")) if setup_car is not None and _num(getattr(setup_car, "m_engineBraking", None)) else None),
        fuel_mix=_enum_name(getattr(getattr(player, "fuel", None), "mix", None)) if player is not None else None,
        s_mode_active=(getattr(getattr(getattr(player, "aero", None), "active_aero_mode", None), "raw", None) == 1 if player is not None and getattr(getattr(player, "aero", None), "active_aero_mode", None) is not None else None),
        s_mode_available=getattr(getattr(player, "aero", None), "active_aero_available", None) if player is not None else None,
        active_aero_mode=_enum_name(getattr(getattr(player, "aero", None), "active_aero_mode", None)) if player is not None else None,
        front_left_wing_damage_percent=getattr(getattr(player, "damage", None), "front_left_wing_percent", None) if player is not None else None,
        front_right_wing_damage_percent=getattr(getattr(player, "damage", None), "front_right_wing_percent", None) if player is not None else None,
        rear_wing_damage_percent=getattr(getattr(player, "damage", None), "rear_wing_percent", None) if player is not None else None,
        floor_damage_percent=getattr(getattr(player, "damage", None), "floor_percent", None) if player is not None else None,
        diffuser_damage_percent=getattr(getattr(player, "damage", None), "diffuser_percent", None) if player is not None else None,
        sidepod_damage_percent=getattr(getattr(player, "damage", None), "sidepod_percent", None) if player is not None else None,
        gearbox_damage_percent=getattr(getattr(player, "damage", None), "gearbox_percent", None) if player is not None else None,
        engine_damage_percent=getattr(getattr(player, "damage", None), "engine_percent", None) if player is not None else None,
        drs_fault=getattr(getattr(player, "damage", None), "drs_fault", None) if player is not None else None,
        ers_fault=getattr(getattr(player, "damage", None), "ers_fault", None) if player is not None else None,
        brake_damage_percent=_wheel_values(getattr(getattr(player, "damage", None), "brakes_percent", None)) if player is not None else (None, None, None, None),
        brake_temperatures_c=_wheel_values(getattr(telemetry, "brakes_temperature_c", None)) if telemetry is not None else (None, None, None, None),
        tyre_damage_percent=_wheel_values(getattr(getattr(player, "tyres", None), "damage_percent", None)) if player is not None else (None, None, None, None),
        tyre_blisters_percent=_wheel_values(getattr(getattr(player, "tyres", None), "blisters_percent", None)) if player is not None else (None, None, None, None),
        tyre_pressures_psi=_wheel_values(getattr(getattr(player, "tyres", None), "pressure_psi", None)) if player is not None else (None, None, None, None),
        pit_stops=getattr(lap, "pit_stops", None) if lap is not None else None,
        pit_speed_limit_kph=getattr(session, "pit_speed_limit_kph", None) if session is not None else None,
        pit_lane_timer_active=getattr(lap, "pit_lane_timer_active", None) if lap is not None else None,
        pit_lane_time_s=getattr(lap, "pit_lane_time_s", None) if lap is not None else None,
        pit_stop_time_s=getattr(lap, "pit_stop_time_s", None) if lap is not None else None,
        engine_temperature_c=getattr(telemetry, "engine_temperature_c", None) if telemetry is not None else None,
        engine_ice_wear_percent=getattr(getattr(player, "damage", None), "engine_wear_percent", {}).get("ICE") if player is not None else None,
        engine_ce_wear_percent=getattr(getattr(player, "damage", None), "engine_wear_percent", {}).get("CE") if player is not None else None,
        engine_mguh_wear_percent=getattr(getattr(player, "damage", None), "engine_wear_percent", {}).get("MGUH") if player is not None else None,
        engine_mguk_wear_percent=getattr(getattr(player, "damage", None), "engine_wear_percent", {}).get("MGUK") if player is not None else None,
        engine_tc_wear_percent=getattr(getattr(player, "damage", None), "engine_wear_percent", {}).get("TC") if player is not None else None,
        engine_es_wear_percent=getattr(getattr(player, "damage", None), "engine_wear_percent", {}).get("ES") if player is not None else None,
        engine_blown=getattr(getattr(player, "damage", None), "engine_blown", None) if player is not None else None,
        engine_seized=getattr(getattr(player, "damage", None), "engine_seized", None) if player is not None else None,
        world_position_x=(float(getattr(motion_car, "m_worldPositionX")) if motion_car is not None and _num(getattr(motion_car, "m_worldPositionX", None)) else None),
        world_position_z=(float(getattr(motion_car, "m_worldPositionZ")) if motion_car is not None and _num(getattr(motion_car, "m_worldPositionZ", None)) else None),
        session_uid=getattr(session, "uid", None) if session is not None else None,
        track_name=track_name,
        reference_map_distance_m=reference_map_distance,
        map_nearby=nearby_map_markers,
        map_turns=_map_turn_markers(reference, track_name, track_length),
        map_gain_loss_zones=(),
        corner_coach_gain_loss_zones=tuple(map_gain_loss_zones),
        map_performance_segments=tuple(map_performance_segments),
        map_reconciliation_error_s=map_reconciliation_error,
        map_full_track_delta_s=map_full_track_delta,
        corner_coach_ready=bool(corner_status.get("reference_ready")) if isinstance(corner_status,dict) else False,
        corner_coach_active_zone=(dict(corner_status.get("active_zone")) if isinstance(corner_status,dict) and isinstance(corner_status.get("active_zone"),dict) else None),
        corner_coach_phase=(str(corner_status.get("active_phase")) if isinstance(corner_status,dict) and corner_status.get("active_phase") else None),
        corner_coach_pre_visual=(dict(corner_status.get("pre_visual")) if isinstance(corner_status,dict) and isinstance(corner_status.get("pre_visual"),dict) else None),
        corner_coach_zones=tuple(dict(x) for x in (corner_status.get("zones") or ()) if isinstance(x,dict)) if isinstance(corner_status,dict) else (),
        corner_coach_physical_corners=tuple(dict(x) for x in (corner_status.get("physical_corners") or ()) if isinstance(x,dict)) if isinstance(corner_status,dict) else (),
        corner_coach_driving_events=tuple(dict(x) for x in (corner_status.get("driving_events") or ()) if isinstance(x,dict)) if isinstance(corner_status,dict) else (),
        corner_coach_reference_now=(dict(corner_status.get("reference_now") or {}) if isinstance(corner_status,dict) else None),
        corner_coach_live_now=(dict(corner_status.get("live_now") or {}) if isinstance(corner_status,dict) else None),
        corner_coach_last_diagnosis=(dict(corner_status.get("last_diagnosis")) if isinstance(corner_status,dict) and isinstance(corner_status.get("last_diagnosis"),dict) else None),
        live_corner_result=live_corner_result,
        last_lap_intelligence=last_lap_intelligence,
        speed_coach_straight_last_diagnosis=(dict(corner_status.get("straight_last_diagnosis")) if isinstance(corner_status,dict) and isinstance(corner_status.get("straight_last_diagnosis"),dict) else None),
        speed_coach_enabled=bool(corner_status.get("speed_enabled",True)) if isinstance(corner_status,dict) else True,
        speed_coach_corner_enabled=bool(corner_status.get("corner_enabled",True)) if isinstance(corner_status,dict) else True,
        speed_coach_straight_enabled=bool(corner_status.get("straight_enabled",False)) if isinstance(corner_status,dict) else False,
        corner_coach_quality=(dict(corner_status.get("quality") or {}) if isinstance(corner_status,dict) else None),
        map_learning_points=tuple(map_learning_points),
    )


def build_input_snapshot(state, performance, *, connected=False) -> InputSnapshot:
    """Build only the channels required by the dedicated 10 ms input overlays."""
    player=getattr(state,"player",None)
    telemetry=getattr(player,"telemetry",None) if player is not None else None
    lap=getattr(player,"lap",None) if player is not None else None
    energy=getattr(player,"energy",None) if player is not None else None
    distance=getattr(lap,"lap_distance_m",None) if lap is not None else None
    reference=_reference_lap(performance)
    ref_sample=_reference_sample_at_distance(reference,distance)
    throttle=getattr(telemetry,"throttle",None) if telemetry is not None else None
    brake=getattr(telemetry,"brake",None) if telemetry is not None else None
    throttle=max(0.0,min(1.0,float(throttle))) if _num(throttle) else 0.0
    brake=max(0.0,min(1.0,float(brake))) if _num(brake) else 0.0
    ref_name=_reference_display_name(performance, reference)
    harvested=None; deployed=None
    if energy is not None:
        h1=getattr(energy,"harvested_mguk_j",None); h2=getattr(energy,"harvested_mguh_j",None)
        if _num(h1) or _num(h2):
            harvested=float(h1 or 0.0)+float(h2 or 0.0)
        d1=getattr(energy,"deployed_this_lap_j",None)
        if _num(d1): deployed=float(d1)
    return InputSnapshot(
        connected=bool(connected),
        speed_kph=getattr(telemetry,"speed_kph",None) if telemetry is not None else None,
        gear=getattr(telemetry,"gear",None) if telemetry is not None else None,
        throttle=throttle, brake=brake,
        ers_store_j=getattr(energy,"store_j",None) if energy is not None else None,
        ers_harvested_j=harvested, ers_deployed_j=deployed,
        lap_number=getattr(lap,"current_lap",None) if lap is not None else None,
        lap_valid=getattr(lap,"lap_valid",None) if lap is not None else None,
        lap_time_s=getattr(lap,"current_lap_time_s",None) if lap is not None else None,
        lap_distance_m=distance,
        reference_throttle=_sample_value(ref_sample,"throttle") if ref_sample is not None else None,
        reference_brake=_sample_value(ref_sample,"brake") if ref_sample is not None else None,
        reference_ers_store_j=_sample_value(ref_sample,"ers_j") if ref_sample is not None else None,
        reference_speed_kph=(int(round(float(_sample_value(ref_sample,"speed"))))
                             if ref_sample is not None and _num(_sample_value(ref_sample,"speed")) else None),
        reference_gear=(int(_sample_value(ref_sample,"gear"))
                        if ref_sample is not None and _num(_sample_value(ref_sample,"gear")) else None),
        reference_time_s=_sample_value(ref_sample,"t") if ref_sample is not None else None,
        reference_name=ref_name,
    )


class OverlayDataProvider:
    """Thread-safe adapter around a live RaceStateReceiver."""

    def __init__(self, receiver) -> None:
        self.receiver = receiver

    def _runtime_status(self, snapshot: OverlaySnapshot) -> OverlaySnapshot:
        recorder = getattr(self.receiver, "recorder", None)
        error = getattr(self.receiver, "recording_error", None)
        active = recorder is not None and error is None
        path = getattr(recorder, "path", None) if recorder is not None else None
        bridge = getattr(self.receiver, "wheel_bridge", None)
        health = bridge.health_snapshot() if bridge is not None and hasattr(bridge, "health_snapshot") else None
        settings=getattr(getattr(self.receiver, "live_coach", None), "settings", None)
        mode=str(getattr(settings, "mode", "auto") or "auto")
        verbosity=str(getattr(settings, "verbosity", "normal") or "normal")
        focus={
            "performance_coach":"map", "track_learning":"map", "time_trial":"map",
            "silent_analysis":"map",
        }.get(mode,"dash")
        return replace(
            snapshot,
            coaching_mode=mode,
            coaching_verbosity=verbosity,
            dashboard_focus_page=focus,
            recording_active=bool(active),
            recording_error=str(error) if error else None,
            recording_packets=int(getattr(recorder, "count", 0) or 0) if recorder is not None else 0,
            recording_file=str(path) if path is not None else None,
            wheel_usb_connected=bool(getattr(health, "serial_connected", False)),
            wheel_status_fresh=bool(getattr(health, "status_fresh", False)),
            wheel_peer_connected=bool(getattr(health, "wheel_connected", False)),
            pedals_peer_connected=bool(getattr(health, "pedals_connected", False)),
            motor_temp_peer_connected=bool(getattr(health, "motor_temp_connected", False)),
            wheel_link_port=getattr(health, "port", None),
            wheel_link_frames_sent=int(getattr(health, "frames_sent", 0) or 0),
            wheel_link_status_frames=int(getattr(health, "status_frames_received", 0) or 0),
            wheel_link_reconnects=int(getattr(health, "reconnects", 0) or 0),
            wheel_link_losses=int(getattr(health, "link_losses", 0) or 0),
        )

    def input_snapshot(self) -> InputSnapshot:
        """Cheap high-frequency DI/RI snapshot used by the 10 ms sampler."""
        now = time.monotonic()
        lock = getattr(self.receiver, "_state_lock", None)
        if lock is None:
            return build_input_snapshot(
                self.receiver.engine.state, self.receiver.engine.performance, connected=False
            )
        with lock:
            last_packet_at = getattr(self.receiver, "last_packet_at", None)
            connected = last_packet_at is not None and now - last_packet_at < 3.0
            return build_input_snapshot(
                self.receiver.engine.state, self.receiver.engine.performance, connected=connected
            )

    def snapshot(self) -> OverlaySnapshot:
        now = time.monotonic()
        lock = getattr(self.receiver, "_state_lock", None)
        if lock is None:
            snapshot = build_overlay_snapshot(
                self.receiver.engine.state,
                self.receiver.engine.performance,
                connected=False,
                now=now,
            )
            return self._runtime_status(snapshot)
        with lock:
            last_packet_at = getattr(self.receiver, "last_packet_at", None)
            connected = last_packet_at is not None and now - last_packet_at < 3.0
            snapshot = build_overlay_snapshot(
                self.receiver.engine.state,
                self.receiver.engine.performance,
                connected=connected,
                now=now,
            )
        return self._runtime_status(snapshot)
