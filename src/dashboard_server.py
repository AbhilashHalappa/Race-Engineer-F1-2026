"""Low-latency LAN dashboard server for Race Engineer.

The server is deliberately dependency-free: it serves a responsive F1-style
browser dashboard and a small SSE stream from the already-built overlay snapshot.
It never decodes UDP and never participates in control/strategy decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import json
import time
from urllib.parse import urlparse, parse_qs
from typing import Any
from .overlay.track_maps import TRACK_MAPS, get_track_map, get_track_map_distances
from .coaching_dashboard import coaching_page_html, coaching_summary_payload
from .driver_history import DriverHistory
from .performance_history import PerformanceHistoryStore
from .skill_evidence import SkillEvidenceStore
from .performance_hub_ui import performance_hub_page_html
from .practice_hub_ui import practice_hub_page_html
from .performance_review import build_selected_reference_comparison, deterministic_review_summary
from .performance_review_ai import generate_ai_summary, generate_track_ai_summary, generate_practice_ai_summary
from .track_landmarks import TrackLandmarkStore
from .track_geometry import persisted_physical_turns
from .session_library import SessionLibrary
from .session_library_ui import session_library_page_html
from .radio_help_page import radio_help_page_html
from .settings_ui import (settings_page_html, setup_page_html, snapshot as settings_snapshot, transcript_text,
    export_configuration, import_configuration_b64, reset_user_settings, create_diagnostics,
    setup_api_snapshot, setup_api_action, lan_qr_svg)

ERS_STORE_MAX_J = 4_000_000.0


def _practice_driver_binding(driver_ref: Any = None) -> dict[str, Any]:
    """Resolve Practice workspace DriverProfile authority to PH compatibility owner."""
    from .driver_profiles import DriverProfileStore
    store=DriverProfileStore()
    refs=store.list_profiles()
    valid={r.driver_id:r for r in refs}
    selected=str(driver_ref or store.active_driver_id() or "")
    if selected not in valid:
        selected=str(store.active_driver_id() or (refs[0].driver_id if refs else ""))
    profile=store.load_profile(selected) if selected else None
    compat=profile.get("compatibility") if isinstance(profile,dict) and isinstance(profile.get("compatibility"),dict) else {}
    try:
        history_id=int(compat.get("performance_history_profile_id")) if compat.get("performance_history_profile_id") is not None else None
    except (TypeError,ValueError):
        history_id=None
    return {
        "driver_id": selected or None,
        "history_profile_id": history_id,
        "profile": profile or {},
        "profiles":[{"id":r.driver_id,"name":r.display_name,"active_game":r.active_game} for r in refs],
    }


def _driver_profile_for_history_id(history_profile_id: Any = None) -> dict[str, Any]:
    """Resolve a Performance History owner back to the person-level Driver Profile."""
    from .driver_profiles import DriverProfileStore
    store=DriverProfileStore()
    refs=store.list_profiles()
    wanted=str(history_profile_id or "").strip()
    for ref in refs:
        profile=store.load_profile(ref.driver_id) or {}
        compat=profile.get("compatibility") if isinstance(profile.get("compatibility"),dict) else {}
        if wanted and str(compat.get("performance_history_profile_id") or "") == wanted:
            return {"driver_id":ref.driver_id,"profile":profile,"history_profile_id":compat.get("performance_history_profile_id")}
    profile=store.active_profile() or {}
    compat=profile.get("compatibility") if isinstance(profile.get("compatibility"),dict) else {}
    return {"driver_id":profile.get("driver_id"),"profile":profile,"history_profile_id":compat.get("performance_history_profile_id")}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _wheel_tuple(value: Any) -> list[float | None]:
    if isinstance(value, (tuple, list)):
        out = list(value[:4])
        while len(out) < 4:
            out.append(None)
        return [float(x) if _num(x) else None for x in out]
    return [None, None, None, None]



_DASH_TRACK_STATIC_CACHE: dict[str, tuple[object, list[list[float]] | None, list[float]]] = {}

def _dashboard_track_static(track_name: object):
    """Return JSON-ready immutable-ish track geometry without rebuilding it at UI rate."""
    key=str(track_name or "").strip().upper()
    points=get_track_map(track_name)
    distances=get_track_map_distances(track_name)
    cached=_DASH_TRACK_STATIC_CACHE.get(key)
    signature=(points,distances)
    if cached is not None and cached[0]==signature:
        return cached[1],cached[2]
    out_points=[list(pt) for pt in points] if points else None
    out_distances=list(distances)
    _DASH_TRACK_STATIC_CACHE[key]=(signature,out_points,out_distances)
    return out_points,out_distances

def dashboard_payload(snapshot: Any) -> dict[str, Any]:
    """Convert an OverlaySnapshot-like object to a stable browser payload."""
    store = getattr(snapshot, "ers_store_j", None)
    ers_percent = None
    if _num(store):
        ers_percent = round(_clamp(float(store) / ERS_STORE_MAX_J * 100.0, 0.0, 100.0), 1)

    fuel_mass = getattr(snapshot, "fuel_remaining_mass", None)
    fuel_laps = getattr(snapshot, "fuel_remaining_laps", None)
    delta = getattr(snapshot, "live_delta_s", None)
    lap_time = getattr(snapshot, "lap_time_s", None)
    best = getattr(snapshot, "best_lap_time_s", None)

    return {
        "connected": bool(getattr(snapshot, "connected", False)),
        "speed_kph": int(getattr(snapshot, "speed_kph", 0) or 0),
        "gear": getattr(snapshot, "gear", None),
        "rpm": getattr(snapshot, "rpm", None),
        "rev_lights_percent": getattr(snapshot, "rev_lights_percent", None),
        "throttle": round(_clamp(float(getattr(snapshot, "throttle", 0.0) or 0.0), 0.0, 1.0), 4),
        "brake": round(_clamp(float(getattr(snapshot, "brake", 0.0) or 0.0), 0.0, 1.0), 4),
        "drs_active": getattr(snapshot, "drs_active", None),
        "drs_allowed": getattr(snapshot, "drs_allowed", None),
        "overtake_active": getattr(snapshot, "overtake_active", None),
        "overtake_available": getattr(snapshot, "overtake_available", None),
        "ers_deploy_mode": getattr(snapshot, "ers_deploy_mode", None),
        "ers_store_j": float(store) if _num(store) else None,
        "ers_percent": ers_percent,
        "fuel_mass": float(fuel_mass) if _num(fuel_mass) else None,
        "fuel_laps": float(fuel_laps) if _num(fuel_laps) else None,
        "position": getattr(snapshot, "position", None),
        "lap_number": getattr(snapshot, "lap_number", None),
        "total_laps": getattr(snapshot, "total_laps", None),
        "lap_time_s": float(lap_time) if _num(lap_time) else None,
        "best_lap_time_s": float(best) if _num(best) else None,
        "delta_s": float(delta) if _num(delta) else None,
        "lap_valid": getattr(snapshot, "lap_valid", None),
        "lap_distance_m": getattr(snapshot, "lap_distance_m", None),
        "track_length_m": getattr(snapshot, "track_length_m", None),
        "sector": getattr(snapshot, "sector", None),
        "compound": getattr(snapshot, "current_compound", None),
        "tyre_age_laps": getattr(snapshot, "tyre_age_laps", None),
        "tyre_wear": _wheel_tuple(getattr(snapshot, "tyre_wear", None)),
        "tyre_surface_temp_c": _wheel_tuple(getattr(snapshot, "tyre_surface_temperatures_c", None)),
        "tyre_inner_temp_c": _wheel_tuple(getattr(snapshot, "tyre_inner_temperatures_c", None)),
        "front_wing_damage_percent": getattr(snapshot, "front_wing_damage_percent", None),
        "setup_diff_on_throttle_percent": getattr(snapshot, "setup_diff_on_throttle_percent", None),
        "setup_diff_off_throttle_percent": getattr(snapshot, "setup_diff_off_throttle_percent", None),
        "setup_brake_bias_percent": getattr(snapshot, "setup_brake_bias_percent", None),
        "setup_engine_braking_percent": getattr(snapshot, "setup_engine_braking_percent", None),
        "penalties_s": getattr(snapshot, "penalties_s", None),
        "fuel_mix": getattr(snapshot, "fuel_mix", None),
        "s_mode_active": getattr(snapshot, "s_mode_active", None),
        "s_mode_available": getattr(snapshot, "s_mode_available", None),
        "active_aero_mode": getattr(snapshot, "active_aero_mode", None),
        "front_left_wing_damage_percent": getattr(snapshot, "front_left_wing_damage_percent", None),
        "front_right_wing_damage_percent": getattr(snapshot, "front_right_wing_damage_percent", None),
        "rear_wing_damage_percent": getattr(snapshot, "rear_wing_damage_percent", None),
        "floor_damage_percent": getattr(snapshot, "floor_damage_percent", None),
        "diffuser_damage_percent": getattr(snapshot, "diffuser_damage_percent", None),
        "sidepod_damage_percent": getattr(snapshot, "sidepod_damage_percent", None),
        "gearbox_damage_percent": getattr(snapshot, "gearbox_damage_percent", None),
        "engine_damage_percent": getattr(snapshot, "engine_damage_percent", None),
        "drs_fault": getattr(snapshot, "drs_fault", None),
        "ers_fault": getattr(snapshot, "ers_fault", None),
        "brake_damage_percent": _wheel_tuple(getattr(snapshot, "brake_damage_percent", None)),
        "brake_temp_c": _wheel_tuple(getattr(snapshot, "brake_temperatures_c", None)),
        "tyre_damage_percent": _wheel_tuple(getattr(snapshot, "tyre_damage_percent", None)),
        "tyre_blisters_percent": _wheel_tuple(getattr(snapshot, "tyre_blisters_percent", None)),
        "tyre_pressure_psi": _wheel_tuple(getattr(snapshot, "tyre_pressures_psi", None)),
        "tyre_set_index": getattr(snapshot, "tyre_set_index", None),
        "pit_stops": getattr(snapshot, "pit_stops", None),
        "pit_speed_limit_kph": getattr(snapshot, "pit_speed_limit_kph", None),
        "pit_lane_timer_active": getattr(snapshot, "pit_lane_timer_active", None),
        "pit_lane_time_s": getattr(snapshot, "pit_lane_time_s", None),
        "pit_stop_time_s": getattr(snapshot, "pit_stop_time_s", None),
        "serve_penalty": getattr(snapshot, "serve_penalty", None),
        "engine_temperature_c": getattr(snapshot, "engine_temperature_c", None),
        "engine_ice_wear_percent": getattr(snapshot, "engine_ice_wear_percent", None),
        "engine_ce_wear_percent": getattr(snapshot, "engine_ce_wear_percent", None),
        "engine_mguh_wear_percent": getattr(snapshot, "engine_mguh_wear_percent", None),
        "engine_mguk_wear_percent": getattr(snapshot, "engine_mguk_wear_percent", None),
        "engine_tc_wear_percent": getattr(snapshot, "engine_tc_wear_percent", None),
        "engine_es_wear_percent": getattr(snapshot, "engine_es_wear_percent", None),
        "engine_blown": getattr(snapshot, "engine_blown", None),
        "engine_seized": getattr(snapshot, "engine_seized", None),
        "world_position_x": getattr(snapshot, "world_position_x", None),
        "world_position_z": getattr(snapshot, "world_position_z", None),
        "session_uid": getattr(snapshot, "session_uid", None),
        "track_name": getattr(snapshot, "track_name", None),
        "track_map_points": _dashboard_track_static(getattr(snapshot, "track_name", None))[0],
        "track_map_distances_m": _dashboard_track_static(getattr(snapshot, "track_name", None))[1],
        "map_learning_points": [list(pt) for pt in (getattr(snapshot, "map_learning_points", ()) or ())],
        "reference_map_distance_m": getattr(snapshot, "reference_map_distance_m", None),
        "map_nearby": [
            {"kind": getattr(m, "kind", None), "label": getattr(m, "label", None), "position": getattr(m, "position", None), "lap_distance_m": getattr(m, "lap_distance_m", None)}
            for m in (getattr(snapshot, "map_nearby", ()) or ())
        ],
        "map_turns": [
            {"corner_id": getattr(m, "corner_id", None), "label": getattr(m, "label", None), "lap_distance_m": getattr(m, "lap_distance_m", None)}
            for m in (getattr(snapshot, "map_turns", ()) or ())
        ],
        "map_gain_loss_zones": [
            {"start_m": getattr(z, "start_m", None), "end_m": getattr(z, "end_m", None), "state": getattr(z, "state", None), "net_delta_s": getattr(z, "net_delta_s", None)}
            for z in (getattr(snapshot, "map_gain_loss_zones", ()) or ())
        ],
        "map_performance_segments": [
            {"kind": getattr(z, "kind", None), "number": getattr(z, "number", None), "label": getattr(z, "label", None), "start_m": getattr(z, "start_m", None), "end_m": getattr(z, "end_m", None), "net_loss_s": getattr(z, "net_loss_s", None), "complete": getattr(z, "complete", None)}
            for z in (getattr(snapshot, "map_performance_segments", ()) or ())
        ],
        "map_reconciliation_error_s": getattr(snapshot, "map_reconciliation_error_s", None),
        "map_full_track_delta_s": getattr(snapshot, "map_full_track_delta_s", None),
        "next_tyre_compound": getattr(getattr(snapshot, "race_engineer", None), "next_tyre_compound", None),
        "next_tyre_set": getattr(getattr(snapshot, "race_engineer", None), "next_tyre_set", None),
        "safety_car": getattr(snapshot, "safety_car", None),
        "pit_status": getattr(snapshot, "pit_status", None),
        "session_type": getattr(snapshot, "session_type", None),
        "event_profile": getattr(snapshot, "event_profile", None),
        "reference_name": getattr(snapshot, "reference_name", None),
        "session_finished": bool(getattr(snapshot, "session_finished", False)),
        "game_paused": bool(getattr(snapshot, "game_paused", False)),
        "coaching_mode": getattr(snapshot, "coaching_mode", "auto"),
        "coaching_verbosity": getattr(snapshot, "coaching_verbosity", "normal"),
        "dashboard_focus_page": getattr(snapshot, "dashboard_focus_page", "dash"),
    }


class DashboardStateStore:
    """Thread-safe last-value cache shared by Qt and HTTP threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sequence = 0
        self._payload: dict[str, Any] = dashboard_payload(None)

    def update_snapshot(self, snapshot: Any) -> int:
        payload = dashboard_payload(snapshot)
        with self._lock:
            self._sequence += 1
            self._payload = payload
            return self._sequence

    def read(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            return self._sequence, dict(self._payload)


DASHBOARD_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Race Engineer F1 Dash</title>
<style>
:root{color-scheme:dark;--panel:#0b1118;--text:#f6f7f9;--muted:#8290a0;--green:#2def85;--red:#ff4755;--amber:#ffc14d;--cyan:#3ec8ff}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#000;color:var(--text);font-family:Segoe UI,Arial,sans-serif}
#dash{width:100vw;height:100vh;background:radial-gradient(circle at 50% 38%,#101923 0,#06090d 57%,#010203 100%);padding:1.2vh 2vw;display:grid;grid-template-rows:10% 50% 14% 11% 4.5%;gap:1.05%}
#rev{display:grid;grid-template-columns:repeat(15,1fr);gap:.55vw;align-items:center;padding:0 3.5vw}.led{height:55%;border-radius:999px;background:#1b232c}.led.on.g{background:#2bef85;box-shadow:0 0 1vw #2bef85}.led.on.r{background:#ff3e4d;box-shadow:0 0 1vw #ff3e4d}.led.on.b{background:#6674ff;box-shadow:0 0 1vw #6674ff}
#main{display:grid;grid-template-columns:1fr 1.35fr 1fr;align-items:stretch}.side{padding:1.1vh 1.2vw}.center{text-align:center;display:grid;grid-template-rows:1fr auto auto;align-items:center}.k{color:var(--muted);font-size:clamp(9px,1.4vw,19px);font-weight:800;letter-spacing:.14em}.v{font-size:clamp(25px,5.4vw,72px);font-weight:900;line-height:1}.m{font-size:clamp(16px,3.1vw,42px);font-weight:850}.gear{font-size:clamp(95px,18vw,230px);font-weight:900;line-height:.72;letter-spacing:-.05em}.speed{font-size:clamp(22px,4vw,55px);font-weight:900}.unit{font-size:.36em;color:var(--muted);margin-left:.35em}.right{text-align:right}.delta.good{color:var(--green)}.delta.bad{color:var(--red)}.invalid{color:var(--red)}
.statusrow{display:grid;grid-template-columns:repeat(3,1fr);gap:.7vw;width:100%;padding:0 1vw}.pill{padding:.65vh .3vw;border-radius:.55vw;border:1px solid #2b3946;color:#788595;font-weight:900;font-size:clamp(8px,1.2vw,17px)}.pill.on{color:#040806;background:var(--green);border-color:var(--green)}.pill.warn{color:#111;background:var(--amber);border-color:var(--amber)}
#bars{display:grid;grid-template-columns:repeat(4,1fr);gap:3vw;align-items:center;padding:0 2vw}.barblock{min-width:0}.barhead{display:flex;justify-content:space-between;font-size:clamp(8px,1.2vw,17px);font-weight:850;margin-bottom:.7vh}.barhead span:first-child{color:var(--muted);letter-spacing:.1em}.bar{height:1.5vh;min-height:7px;border-radius:99px;background:#19222c;overflow:hidden}.fill{height:100%;width:0;transition:width 45ms linear}.thr{background:#2de77d}.brk{background:#ff4755}.ers{background:linear-gradient(90deg,#13c7ff,#8c62ff)}.fuel{background:#43e07a}
#strip{display:grid;grid-template-columns:repeat(5,1fr);gap:.65vw;padding:0 2vw;align-items:center}.cell{height:100%;min-height:44px;border:1px solid #27333e;border-radius:.55vw;background:#0b1118;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.18vh;font-size:clamp(8px,1.25vw,18px);font-weight:900;white-space:nowrap;padding:.45vh .4vw}.cell b{color:var(--muted);font-size:.78em;letter-spacing:.08em;line-height:1}.cell span{font-size:clamp(10px,1.45vw,22px);line-height:1.05}.warn{color:var(--amber)}.bad{color:var(--red)}
.sectorBlock{margin-top:1.1vh}.sectorBlock .m{margin-top:.15vh}.sectorBlock .k{display:block}#footer{color:#687788;text-align:center;font-size:clamp(7px,.9vw,13px);display:flex;align-items:center;justify-content:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:0 1vw}
#nav{position:fixed;z-index:8;top:10.3vh;left:50%;transform:translateX(-50%);display:flex;gap:.45vw}#nav button{background:#111923;color:#91a0af;border:1px solid #2b3946;border-radius:.45vw;padding:.35vh .8vw;font:800 clamp(8px,1vw,14px) Segoe UI;letter-spacing:.04em}#nav button.active{background:#243442;color:white;border-color:#52687b}
.infoPage{position:fixed;z-index:4;left:3.5vw;right:3.5vw;top:18vh;bottom:5.5vh;display:none}.infoPage.active{display:block}.pageTitle{font-size:clamp(22px,3.5vw,48px);font-weight:900}.pageSub{color:var(--muted);font-size:clamp(9px,1.2vw,17px);font-weight:800;margin:.5vh 0 2vh}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:1vw 1.2vh}.infoCell{border:1px solid #27333e;border-radius:.55vw;background:#0b1118;min-height:13vh;display:flex;flex-direction:column;justify-content:center;align-items:center}.infoCell b{color:var(--muted);font-size:clamp(8px,1vw,14px);letter-spacing:.06em}.infoCell span{font-size:clamp(18px,2.6vw,36px);font-weight:900;margin-top:.6vh}.faultRow{display:flex;justify-content:center;gap:2vw;margin-top:2vh}.fault{border:1px solid #27333e;border-radius:.55vw;padding:1vh 3vw;font-weight:900}.ok{color:var(--green)}.fault.bad{color:var(--red);border-color:#70303a}.tyreTable{display:grid;grid-template-columns:1.25fr repeat(4,1fr);border:1px solid #27333e;border-radius:.55vw;overflow:hidden}.tyreTable div{min-height:7.6vh;display:flex;align-items:center;justify-content:center;border-right:1px solid #202a34;border-bottom:1px solid #202a34;font-size:clamp(10px,1.45vw,20px);font-weight:850}.tyreTable .lab{justify-content:flex-start;padding-left:1vw;color:var(--muted);letter-spacing:.04em}.tyreTable .head{color:var(--muted)}
.visualWrap{position:relative;height:55vh;max-height:335px;min-height:245px}.carBody{position:absolute;left:50%;top:15%;width:17%;height:62%;transform:translateX(-50%);border:2px solid #2def85;background:#102518;clip-path:polygon(38% 0,62% 0,86% 25%,78% 69%,62% 100%,38% 100%,22% 69%,14% 25%)}.carNose{position:absolute;left:50%;top:1%;width:26%;height:21%;transform:translateX(-50%);border:2px solid #2def85;background:#102518;clip-path:polygon(0 18%,38% 0,46% 35%,54% 35%,62% 0,100% 18%,98% 42%,58% 35%,55% 100%,45% 100%,42% 35%,2% 42%)}.carRear{position:absolute;left:50%;top:79%;width:23%;height:6%;transform:translateX(-50%);border:2px solid #2def85;border-radius:5px;background:#102518}.wheelViz{position:absolute;width:6.2%;height:22%;border-radius:18%;border:3px solid var(--green);background:#173324;display:flex;align-items:center;justify-content:center}.wheelViz .disc{width:42%;aspect-ratio:1;border-radius:50%;background:var(--green);border:2px solid var(--green);box-shadow:0 0 .7vw currentColor}.wFL{left:36%;top:20%}.wFR{right:36%;top:20%}.wRL{left:36%;top:60%}.wRR{right:36%;top:60%}.cornerData{position:absolute;width:25%;font-weight:850;font-size:clamp(9px,1.1vw,16px);line-height:1.38}.cornerData.left{text-align:left}.cornerData.right{text-align:left}.cFL{left:5%;top:15%}.cFR{right:5%;top:15%}.cRL{left:5%;top:57%}.cRR{right:5%;top:57%}.cornerData b{display:block;color:#a6b2be;font-size:1.15em;margin-bottom:.15vh}.metricLine{display:grid;grid-template-columns:4.5em 1fr;column-gap:.8vw;align-items:center}.metricLine .lab{color:#738191}.metricLine .num{font-weight:900;text-align:right}.cornerData.right .metricLine .num{text-align:left}.legend{display:flex;justify-content:center;gap:1.8vw;color:#8290a0;font-size:clamp(8px,1vw,13px);font-weight:800}.legend i{display:inline-block;width:.65em;height:.65em;border-radius:50%;margin-right:.35em}.f1DamageCar{position:absolute;left:32%;right:32%;top:0%;bottom:6%;filter:drop-shadow(0 0 .45vw #2def8533)}.f1WingFront{position:absolute;left:5%;right:5%;top:1%;height:8%;border:2px solid #2def85;border-radius:5px;background:#102518;clip-path:polygon(0 28%,34% 0,43% 32%,57% 32%,66% 0,100% 28%,98% 100%,62% 80%,50% 100%,38% 80%,2% 100%)}.f1Nose{position:absolute;left:44%;top:5%;width:12%;height:31%;border:2px solid #2def85;border-radius:45% 45% 18% 18%;background:#102518;clip-path:polygon(34% 0,66% 0,78% 100%,22% 100%)}.f1Body{position:absolute;left:29%;top:27%;width:42%;height:55%;border:2px solid #2def85;background:#102518;clip-path:polygon(38% 0,62% 0,86% 26%,78% 68%,63% 100%,37% 100%,22% 68%,14% 26%)}.f1Cockpit{position:absolute;left:41%;top:31%;width:18%;height:18%;border:2px solid #2def85;border-radius:50%;background:#05080b;box-shadow:inset 0 0 0 4px #173a20}.f1WingRear{position:absolute;left:9%;right:9%;bottom:2%;height:8%;border:2px solid #2def85;border-radius:5px;background:#102518}.f1Wheel{position:absolute;width:13%;height:21%;border:3px solid #2def85;border-radius:30%;background:#08100c;box-shadow:0 0 .5vw #2def8544}.f1Wfl{left:13%;top:20%}.f1Wfr{right:13%;top:20%}.f1Wrl{left:13%;top:62%}.f1Wrr{right:13%;top:62%}.damageZone{position:absolute;border:2px solid #344351;border-radius:6px;background:#122018;color:white;display:flex;align-items:center;justify-content:center;font-size:clamp(7px,.78vw,11px);font-weight:900;text-align:center;line-height:1.05;padding:.15vh .2vw}.dzFL{left:7%;top:2%;width:40%;height:7%}.dzFR{right:7%;top:2%;width:40%;height:7%}.dzRear{left:13%;bottom:4%;width:74%;height:7%}.dzFloor{left:36%;top:47%;width:28%;height:24%}.dzDiff{left:32%;bottom:13%;width:36%;height:7%}.dzSL{left:25%;top:43%;width:13%;height:26%}.dzSR{right:25%;top:43%;width:13%;height:26%}.dzEng{left:39%;top:49%;width:22%;height:14%}.dzGear{left:41%;top:66%;width:18%;height:8%}.faultStrip{position:absolute;left:37%;right:37%;bottom:1%;display:flex;gap:1vw}.faultStrip .fault{flex:1;text-align:center;padding:.7vh .6vw}

.damageCombined{display:block;height:60vh}.damageGroup{min-width:0;margin-bottom:1.3vh}.groupTitle{font-weight:900;color:#dce3e9;font-size:clamp(11px,1.25vw,18px);margin-bottom:.65vh}.damageGrid{display:grid;grid-template-columns:repeat(6,1fr);gap:.65vw}.puGrid{display:grid;grid-template-columns:repeat(5,1fr);gap:.65vw}.statusCard{border:1px solid #2b3946;border-radius:.55vw;background:#090e14;min-height:8.8vh;display:flex;flex-direction:column;align-items:center;justify-content:center}.statusCard b{color:#7f8d9c;font-size:clamp(7px,.82vw,12px);letter-spacing:.05em}.statusCard span{font-weight:900;font-size:clamp(17px,2.1vw,30px);margin-top:.25vh}.faultCard{min-height:8.8vh}.tyreQuad{position:relative;height:64vh;min-height:320px;display:grid;grid-template-columns:calc(50% - 3.9vw) calc(50% - 3.9vw);grid-template-rows:calc(50% - 4.1vh) calc(50% - 4.1vh);column-gap:7.8vw;row-gap:8.2vh;background:#020406;border:1px solid #2a3138;border-radius:1vw;overflow:hidden}.tyreQuad:before{content:"";position:absolute;left:50%;top:0;height:calc(50% - 5.1vh);width:1px;background:#343a40;box-shadow:0 calc(50% + 10.2vh) 0 #343a40}.tyreQuad:after{content:"";position:absolute;left:0;width:calc(50% - 11.2vw);top:50%;height:1px;background:#343a40;box-shadow:calc(50vw + 22.4vw) 0 0 #343a40}.tyreCenter{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:5;background:#3a3a3c;border-radius:999px;padding:.55vh 2vw;color:#fff;font-weight:900;font-size:clamp(14px,1.55vw,22px);white-space:nowrap}.tyreSetMeta{position:absolute;left:50%;top:calc(50% + 3.6vh);transform:translateX(-50%);z-index:5;color:#9ba8b5;font-size:clamp(7px,.72vw,10px);font-weight:800;white-space:nowrap}.tyreRefCard{position:relative;min-width:0;min-height:0}.tyreCorner{position:absolute;top:.6vh;color:#c7d0d9;font-weight:900;font-size:clamp(10px,.95vw,14px)}.tyreRefCard.left .tyreCorner{left:.4vw}.tyreRefCard.right .tyreCorner{right:.4vw}.tyrePsi{display:none}.tyreRefCard.left .tyrePsi{left:.7vw;justify-content:flex-start}.tyreRefCard.right .tyrePsi{right:.7vw;justify-content:flex-end}.tyrePsi .psiVal{font-size:clamp(32px,4.4vw,60px);font-weight:900;line-height:.90}.psiLab{font-size:clamp(7px,.60vw,10px);font-weight:900;color:#8f9ba7;line-height:1;margin:0 0 .35vh .08vw;letter-spacing:.04em}.tyreData{position:absolute;top:3.3vh;width:34%;display:grid;gap:.28vh}.tyreRefCard.left .tyreData{left:.7vw}.tyreRefCard.right .tyreData{right:.7vw}.tyreRow{display:grid;grid-template-columns:1fr auto;column-gap:.5vw;align-items:center;font-size:clamp(10px,1.02vw,15px);line-height:1.34;font-weight:900}.tyreRow b{color:#82909e;font-size:1em}.tyreRow span{font-size:1em}.gaugeGroup{position:absolute;top:6.7vh;width:16%;height:12.8vh;display:grid;grid-template-columns:repeat(3,1fr);column-gap:.28vw;align-items:end}.tyreRefCard.left .gaugeGroup{left:47%}.tyreRefCard.right .gaugeGroup{right:47%}.tempGauge,.brakeGauge{height:10.4vh;min-height:58px;border:1px solid #37434f;border-radius:.28vw;background:#0a0f14;overflow:hidden;position:relative}.tempGauge i,.brakeGauge i{position:absolute;left:2px;right:2px;bottom:2px;height:0;border-radius:.18vw;background:#2def85}.gaugeLabels{grid-column:1/4;display:grid;grid-template-columns:repeat(3,1fr);column-gap:.28vw;color:#82909e;font-size:clamp(6px,.52vw,8px);font-weight:900;text-align:center;line-height:1}.gaugeGroup .gOut,.gaugeGroup .gIn,.gaugeGroup .gBrk{grid-row:1}.gaugeLabels{grid-row:2}.tyreRefCard.right .gaugeGroup .gOut{grid-column:3}.tyreRefCard.right .gaugeGroup .gIn{grid-column:2}.tyreRefCard.right .gaugeGroup .gBrk{grid-column:1}.tyreRefCard.right .gaugeLabels span:nth-child(1){grid-column:3}.tyreRefCard.right .gaugeLabels span:nth-child(2){grid-column:2}.tyreRefCard.right .gaugeLabels span:nth-child(3){grid-column:1}.brakeBox{position:absolute;top:7.2vh;width:17%;display:flex;flex-direction:column;gap:.18vh}.tyreRefCard.left .brakeBox{left:66%;text-align:left}.tyreRefCard.right .brakeBox{right:66%;text-align:right}.brakeLabel{color:#82909e;font-size:clamp(7px,.60vw,9px);font-weight:900}.brakeTemp{font-size:clamp(16px,1.7vw,25px);font-weight:900;line-height:1.02}.brakeDmg{font-size:clamp(10px,.98vw,15px);font-weight:900;line-height:1.05}.engineWrap{position:relative;height:61vh;min-height:300px}.engineRefSvg{width:100%;height:100%;overflow:visible}.engLabel{fill:#f1f3f5;font:500 34px Segoe UI,Arial,sans-serif;text-anchor:end}.engValue{font:900 36px Segoe UI,Arial,sans-serif;text-anchor:start}.engLeader{stroke:#c2c7cc;stroke-width:2;stroke-dasharray:2 8;stroke-linecap:round}.engZone{stroke-width:5;fill-opacity:.26}.engCoreCut{fill:#030506;fill-opacity:.72;stroke-width:4}.engPipe{fill:none;stroke-width:8;stroke-linecap:round}.engState{text-anchor:middle;font:800 17px Segoe UI,Arial,sans-serif}.engTemp{fill:#b5c0ca;text-anchor:middle;font:700 13px Segoe UI,Arial,sans-serif}.mapWrap{position:relative;height:62vh;min-height:300px;border:1px solid #202b35;border-radius:.8vw;background:#030506}.mapWrap svg{width:100%;height:100%}.mapTrack{fill:none;stroke:#d6dadd;stroke-width:6;stroke-linecap:round;stroke-linejoin:round}.mapDot{fill:#ffd934;stroke:#111;stroke-width:2}.mapStart{fill:#080c10;stroke:#f5f8fa;stroke-width:2}.mapStartText{fill:#f5f8fa;font:700 11px Segoe UI,Arial,sans-serif;text-anchor:middle}.mapInfo{text-align:center;color:#9aa8b6;font-weight:800;margin-top:1vh}

#offline{position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:#000e;z-index:9;font-size:clamp(24px,5vw,72px);font-weight:900;letter-spacing:.1em;color:#d9dde3}#offline.show{display:flex}

/* V0.9.19.8.6.22 — LAN UI rebuilt from frozen native 800x480 geometry. */
body{background:#000;display:flex;align-items:center;justify-content:center}
#stage{position:absolute;left:50%;top:50%;width:800px;height:480px;transform-origin:center center;background:#04070a;overflow:hidden}
#stage *{box-sizing:border-box}
#dash{position:absolute;inset:0;width:800px;height:480px;padding:0;background:#04070a;display:block}
#rev{position:absolute;left:44px;top:12px;width:712px;height:27px;padding:0;display:grid;grid-template-columns:repeat(15,1fr);gap:5px;align-items:center}
.led{height:27px;border-radius:14px;background:#1b232c}.led.on.g{background:#2bef85;box-shadow:none}.led.on.r{background:#ff3e4d;box-shadow:none}.led.on.b{background:#6674ff;box-shadow:none}
#nav{position:absolute;z-index:20;top:55px;left:350px;transform:none;display:flex;gap:4px;height:25px}
#nav button{height:25px;padding:0 12px;background:#111923;color:#91a0af;border:1px solid #2b3946;border-radius:5px;font:700 10px 'Segoe UI';letter-spacing:0}
#nav button.active{background:#243442;color:#fff;border-color:#52687b}
.dashBack{position:absolute;z-index:200;left:14px;top:14px;height:30px;padding:0 12px;background:#182534;color:#f4f8fb;border:1px solid #577087;border-radius:6px;font:800 11px 'Segoe UI';letter-spacing:.02em}.dashBack:hover{background:#24394d;border-color:#7ea2bf}
#main{position:absolute;left:0;top:72px;width:800px;height:270px;display:grid;grid-template-columns:200px 400px 200px;align-items:stretch}
.side{padding:0 0 0 22px}.side.right{padding:0 28px 0 0;text-align:right}
.k{color:#8291a0;font-size:13px;font-weight:800;letter-spacing:0}.v{font-size:48px;font-weight:900;line-height:1}.m{font-size:30px;font-weight:850}.sectorBlock{margin-top:7px}
.center{position:relative;text-align:center;display:block}.gear{position:absolute;left:0;top:4px;width:400px;height:155px;font-size:145px;font-weight:900;line-height:1;letter-spacing:-4px}.speed{position:absolute;left:0;top:160px;width:400px;font-size:46px;font-weight:900}.unit{font-size:1em;color:#f7f9fb;margin-left:7px}
.statusrow{position:absolute;left:48px;top:229px;width:304px;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.pill{height:31px;padding:6px 0;border-radius:6px;border:1px solid #2b3946;color:#788595;font-weight:900;font-size:14px}.pill.on{color:#040806;background:#2def85;border-color:#2def85}.pill.warn{color:#111;background:#ffc14d;border-color:#ffc14d}
#bars{position:absolute;left:25px;top:338px;width:750px;height:48px;padding:0;display:grid;grid-template-columns:repeat(4,1fr);gap:32px;align-items:center}.barblock{min-width:0}.barhead{display:flex;justify-content:space-between;font-size:13px;font-weight:850;margin-bottom:5px}.barhead span:first-child{color:#8291a0;letter-spacing:0}.bar{height:15px;border-radius:8px;background:#19222c;overflow:hidden}.fill{height:100%;width:0;transition:width 45ms linear}
#strip{position:absolute;left:22px;top:394px;width:756px;height:45px;padding:0;display:grid;grid-template-columns:repeat(5,1fr);gap:6px;align-items:stretch}.cell{height:45px;min-height:0;border-radius:7px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;font-weight:900;white-space:nowrap;padding:2px 4px}.cell:nth-child(1){background:rgba(32,102,182,.28);border:1px solid rgba(68,126,192,.65)}.cell:nth-child(2){background:rgba(171,112,28,.28);border:1px solid rgba(186,128,44,.65)}.cell:nth-child(3){background:rgba(20,132,112,.28);border:1px solid rgba(37,150,129,.65)}.cell:nth-child(4){background:rgba(120,72,176,.28);border:1px solid rgba(137,88,193,.65)}.cell:nth-child(5){background:rgba(124,50,50,.28);border:1px solid rgba(146,70,70,.65)}.cell b{color:#a6b6c6;font-size:8px;letter-spacing:0;line-height:1}.cell span{font-size:15px;line-height:1.05}
#footer{position:absolute;left:28px;top:447px;width:744px;height:22px;color:#687788;text-align:center;font-size:10px;display:flex;align-items:center;justify-content:center;padding:0}
#validity{display:none!important}
.infoPage{position:absolute;z-index:5;left:0;top:0;width:800px;height:480px;display:none;padding:0}.infoPage.active{display:block}.pageTitle{position:absolute;left:20px;top:62px;font-size:31px;line-height:1;font-weight:900}.pageSub{position:absolute;left:20px;top:96px;margin:0;color:#8290a0;font-size:12px;font-weight:800}
/* DAMAGE — same spatial front/middle/rear grouping as native */
#damagePage .damageCombined{position:absolute;left:12px;top:110px;width:776px;height:360px;margin:0}.damageGroup{margin:0}.damageGroup:first-child>.groupTitle{position:absolute;left:0;top:0}.damageGroup:nth-child(2)>.groupTitle{position:absolute;left:0;top:252px}.groupTitle{font-size:11px;font-weight:900;color:#e6ebf0;margin:0}
.damageGrid{position:absolute;left:0;top:22px;width:776px;height:232px;display:block}.statusCard{position:absolute;width:164px;height:50px;min-height:0;border:1px solid #2c3a46;border-radius:7px;background:#090e14;display:flex;flex-direction:column;align-items:center;justify-content:center}.statusCard b{font-size:8px;color:#7e8d9c;letter-spacing:0}.statusCard span{font-size:16px;font-weight:900;margin-top:2px}
.damageGrid .statusCard:nth-child(1){left:84px;top:0}.damageGrid .statusCard:nth-child(2){left:528px;top:0}.damageGrid .statusCard:nth-child(6){left:84px;top:60px}.damageGrid .statusCard:nth-child(4){left:306px;top:60px}.damageGrid .statusCard:nth-child(5){left:306px;top:120px}.damageGrid .statusCard:nth-child(3){left:306px;top:180px}.damageGrid .statusCard:nth-child(7){left:528px;top:60px}.damageGrid .statusCard:nth-child(8){left:528px;top:112px}.damageGrid .statusCard:nth-child(9){left:84px;top:120px}.damageGrid .statusCard.engineTempCard{left:528px;top:164px}
.puGrid{position:absolute;left:0;top:274px;width:776px;height:82px;display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(2,38px);gap:6px 8px}.puGrid .statusCard{position:static;width:auto;height:38px}.puGrid .statusCard b{font-size:8px}.puGrid .statusCard span{font-size:15px}
/* TYRES — copied from the frozen native four-corner proportions */
#tyresPage .pageTitle{left:20px;top:64px}.tyreQuad{position:absolute;left:20px;top:108px;width:760px;height:346px;min-height:0;padding:0;border:0;border-radius:0;background:transparent;display:grid;grid-template-columns:341px 341px;grid-template-rows:148px 148px;column-gap:78px;row-gap:50px;overflow:visible}.tyreQuad:before{content:"";position:absolute;left:380px;top:0;width:1px;height:148px;background:#343a40;box-shadow:0 198px 0 #343a40}.tyreQuad:after{content:"";position:absolute;left:0;top:173px;width:295px;height:1px;background:#343a40;box-shadow:465px 0 0 #343a40}.tyreCenter{position:absolute;left:380px;top:173px;transform:translate(-50%,-50%);z-index:5;background:#3a3a3c;border:1px solid #444c54;border-radius:18px;padding:6px 26px;color:#fff;font-weight:900;font-size:15px;white-space:nowrap}.tyreSetMeta{position:absolute;left:380px;top:195px;transform:translateX(-50%);z-index:5;color:#9ba8b5;font-size:9px;font-weight:800;white-space:nowrap}.tyreRefCard{position:relative;min-width:0;min-height:0}.tyreCorner{position:absolute;top:1px;color:#d7dde2;font-weight:900;font-size:12px}.tyreRefCard.left .tyreCorner{left:0}.tyreRefCard.right .tyreCorner{right:0}.tyreData{position:absolute;top:22px;width:118px;display:grid;gap:1px}.tyreRefCard.left .tyreData{left:0}.tyreRefCard.right .tyreData{right:0}.tyreRow{display:grid;grid-template-columns:64px 50px;column-gap:4px;align-items:center;font-size:11px;line-height:1.33;font-weight:900}.tyreRow b{color:#82909e;font-size:11px}.tyreRow span{font-size:11px;text-align:right}.tyreRefCard.right .tyreRow{grid-template-columns:64px 50px}.tyreRefCard.right .tyreRow b{text-align:left}.gaugeGroup{position:absolute;top:44px;width:65px;height:83px;display:grid;grid-template-columns:repeat(3,17px);column-gap:6px;align-items:end}.tyreRefCard.left .gaugeGroup{left:150px}.tyreRefCard.right .gaugeGroup{right:150px}.tempGauge,.brakeGauge{height:65px;min-height:0;border:1px solid #37434f;border-radius:4px;background:#0a0f14;overflow:hidden;position:relative}.tempGauge i,.brakeGauge i{position:absolute;left:2px;right:2px;bottom:2px;height:0;border-radius:2px;background:#2def85}.gaugeLabels{grid-column:1/4;display:grid;grid-template-columns:repeat(3,17px);column-gap:6px;color:#82909e;font-size:7px;font-weight:900;text-align:center;line-height:1}.gaugeGroup .gOut,.gaugeGroup .gIn,.gaugeGroup .gBrk{grid-row:1}.gaugeLabels{grid-row:2}.tyreRefCard.right .gaugeGroup .gOut{grid-column:3}.tyreRefCard.right .gaugeGroup .gIn{grid-column:2}.tyreRefCard.right .gaugeGroup .gBrk{grid-column:1}.tyreRefCard.right .gaugeLabels span:nth-child(1){grid-column:3}.tyreRefCard.right .gaugeLabels span:nth-child(2){grid-column:2}.tyreRefCard.right .gaugeLabels span:nth-child(3){grid-column:1}.brakeBox{position:absolute;top:43px;width:95px;display:flex;flex-direction:column;gap:1px}.tyreRefCard.left .brakeBox{left:226px;text-align:left}.tyreRefCard.right .brakeBox{right:226px;text-align:right}.brakeLabel{color:#82909e;font-size:8px;font-weight:900}.brakeTemp{font-size:22px;font-weight:900;line-height:1}.brakeDmg{font-size:12px;font-weight:900;line-height:1.05}
/* PIT — native 4x2 large service-card layout */
#pitPage #pitState{position:absolute;left:48px;top:98px;width:704px;height:70px;margin:0;font-size:48px;line-height:70px}.grid4{position:absolute;left:28px;top:185px;width:744px;height:240px;display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(2,98px);gap:14px 10px}.infoCell{min-height:0;border:1px solid #27333e;border-radius:8px;background:#0b1118;display:flex;flex-direction:column;justify-content:center;align-items:center}.infoCell b{color:#8290a0;font-size:10px;letter-spacing:0}.infoCell span{font-size:20px;font-weight:900;margin-top:7px}
/* MAP — native track area, legend and info row */
#mapPage .mapWrap{position:absolute;left:20px;top:98px;width:760px;height:305px;min-height:0;border:0;border-radius:0;background:transparent}.mapWrap svg{width:100%;height:100%}.mapTrack{fill:none;stroke:#d6dadd;stroke-width:6;stroke-linecap:round;stroke-linejoin:round}.mapStart{fill:#080c10;stroke:#f5f8fa;stroke-width:3}.mapStartText{fill:#f5f8fa;font:700 13px Segoe UI,Arial,sans-serif;text-anchor:middle}.mapLegend{position:absolute;left:160px;top:406px;width:480px;height:22px;display:grid;grid-template-columns:repeat(4,1fr);align-items:center;color:#afbbc7;font-size:10px;font-weight:900}.mapLegend span{text-align:left}.mapLegend i{display:inline-block;width:12px;height:12px;border-radius:50%;vertical-align:-2px;margin-right:7px}.mapInfo{position:absolute;left:64px;top:439px;width:672px;height:20px;margin:0;text-align:center;color:#96a4b2;font-weight:800;font-size:9px;line-height:20px}
#offline{position:absolute;inset:0;display:none;align-items:center;justify-content:center;background:#000e;z-index:99;font-size:34px;font-weight:900;letter-spacing:.08em;color:#d9dde3;pointer-events:none}


/* UI-R9 — F1 Dash / secondary-display polish. Presentation only. */
#dash{background:radial-gradient(circle at 50% 34%,#101a24 0,#070b10 58%,#030507 100%);padding:1.1vh 1.8vw;gap:.9%;}
#nav{top:10.5vh;gap:.38vw;padding:.35vh .42vw;background:#080d12d9;border:1px solid #22313e;border-radius:.7vw;backdrop-filter:blur(5px)}
#nav button{min-height:32px;background:#0d151d;color:#8395a8;border:1px solid transparent;border-radius:.42vw;padding:.35vh .9vw;font-weight:800;transition:background 150ms ease,border-color 150ms ease,color 150ms ease}#nav button:focus-visible,button:focus-visible,a:focus-visible{outline:2px solid #4dd9ff;outline-offset:2px}.fill{transition:width 160ms ease}.reduce-motion .fill,.reduce-motion #nav button{transition:none!important}@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
#nav button:hover{background:#17232d;color:#eef6fb;border-color:#3b5265}
#nav button.active{background:#16384a;color:#eef6fb;border-color:#4dd9ff;box-shadow:inset 0 -2px 0 #4dd9ff}
.dashBack{left:1.8vw;top:1.4vh;height:30px;background:#0d151d;color:#dce7ee;border:1px solid #2a3d4d;border-radius:7px;padding:0 12px;font:750 11px 'Segoe UI'}
.dashBack:hover{background:#17232d;border-color:#4b6578}
.side,.center{min-width:0}.side{padding:1vh 1.1vw}
.cell,.infoCell,.statusCard{background:#0b1219;border-color:#233441;box-shadow:none}
.cell{border-radius:.65vw}.infoCell,.statusCard{border-radius:.7vw}
.pageTitle{font-weight:850;letter-spacing:-.015em}.pageSub{font-weight:650;letter-spacing:.01em}
#offline{background:#030609e8;flex-direction:column;gap:1.2vh;text-align:center;padding:8vh 8vw;font-size:0;letter-spacing:0}
#offline:before{content:'F1 DASH';color:#4dd9ff;font-size:clamp(10px,1.3vw,18px);font-weight:800;letter-spacing:.12em}
#offline:after{content:'WAITING FOR F1 TELEMETRY\A Start or resume a supported F1 session. The dash reconnects automatically.';white-space:pre-line;color:#eef6fb;font-size:clamp(18px,3vw,42px);font-weight:850;line-height:1.4}
@media(max-width:900px){#dash{padding:1vh 1.3vw}#nav{top:9.7vh}.dashBack{left:1vw;top:1vh}.infoPage{left:2.2vw;right:2.2vw}.grid4{gap:.75vw .9vh}.cell{min-height:38px}}
@media(max-aspect-ratio:4/3){#main{grid-template-columns:.92fr 1.25fr .92fr}#bars{gap:1.5vw}.infoPage{top:17vh}.pageSub{margin-bottom:1.2vh}}

/* UI-R9.1 — browser/LAN shell parity with the native 800x480 dash. */
.dashBack{width:30px;padding:0;font-size:0;text-align:center}
.dashBack:after{content:'←';font:800 17px 'Segoe UI';line-height:28px;color:#dce7ee}
#stage.infoMode #rev{visibility:hidden}
#stage.infoMode #nav{top:13px;left:auto;right:18px;transform:none;height:30px;padding:2px 3px;gap:3px;border-radius:7px}
#stage.infoMode #nav button{height:24px;min-height:24px;padding:0 10px;font-size:9px;border-radius:5px}
#stage.infoMode .dashBack{top:13px;left:18px}
#stage.infoMode .infoPage{left:0;right:auto;top:0;bottom:auto;width:800px;height:480px}
#stage.infoMode .pageTitle{left:28px;top:53px;font-size:22px;line-height:24px;letter-spacing:-.01em}
#stage.infoMode .pageTitle:before{content:'F1 DASH';display:block;color:#3ec8ff;font-size:8px;line-height:10px;font-weight:800;letter-spacing:.12em;margin-bottom:2px}
#stage.infoMode .pageSub{left:28px;top:91px;font-size:10px;line-height:14px;font-weight:650;margin:0}
#stage.infoMode .pageSub:after{content:'';position:absolute;left:0;top:22px;width:744px;height:1px;background:#263541}
#stage.infoMode #mapPage .mapWrap{left:28px;top:122px;width:744px;height:270px}
#stage.infoMode .mapLegend{left:156px;top:401px;width:488px;height:24px}
#stage.infoMode .mapInfo{left:64px;top:435px;width:672px;height:22px;line-height:22px}
#stage.infoMode #damagePage .damageCombined{top:122px}
#stage.infoMode #tyresPage .tyreQuad{top:120px;height:330px}
#stage.infoMode #pitPage #pitState{top:116px}
#stage.infoMode #pitPage .grid4{top:196px}
</style>
</head>
<body>
<div id="stage">
<div id="offline">WAITING FOR TELEMETRY</div>
<button id="dashBack" class="dashBack">← BACK TO HUB</button><div id="nav"><button class="active" data-page="dash">DASH</button><button data-page="damage">DAMAGE</button><button data-page="tyres">TYRES</button><button data-page="map">MAP</button><button data-page="pit">PIT</button></div>
<div id="dash">
 <div id="rev"></div>
 <div id="main">
  <div class="side"><div class="k">POSITION</div><div class="v" id="pos">P--</div><div style="height:3.5vh"></div><div class="k">LAP</div><div class="m"><span id="lap">--</span> <span style="color:var(--muted)" id="laps">/ --</span></div><div class="sectorBlock"><div class="k">SECTOR</div><div class="m" id="sectorMeta">--</div></div></div>
  <div class="center"><div class="gear" id="gear">N</div><div class="speed"><span id="speed">0</span><span class="unit">KM/H</span></div><div class="statusrow"><div class="pill" id="drs">S MODE</div><div class="pill" id="ersMode">ERS</div><div class="pill" id="overtake">OT</div></div></div>
  <div class="side right"><div class="k">LAP TIME</div><div class="m" id="lapTime">--:--.---</div><div id="validity" style="color:var(--muted);font-weight:800">VALID</div><div style="height:2vh"></div><div class="k">DELTA</div><div class="v delta" id="delta">--.---</div></div>
 </div>
 <div id="bars">
  <div class="barblock"><div class="barhead"><span>THROTTLE</span><span id="thrTxt">0%</span></div><div class="bar"><div class="fill thr" id="thr"></div></div></div>
  <div class="barblock"><div class="barhead"><span>BRAKE</span><span id="brkTxt">0%</span></div><div class="bar"><div class="fill brk" id="brk"></div></div></div>
  <div class="barblock"><div class="barhead"><span>ERS</span><span id="ersTxt">--%</span></div><div class="bar"><div class="fill ers" id="ersBar"></div></div></div>
  <div class="barblock"><div class="barhead"><span>FUEL</span><span id="fuelTxt">-- LAPS</span></div><div class="bar"><div class="fill fuel" id="fuelBar"></div></div></div>
 </div>
 <div id="strip">
  <div class="cell"><b>DIFF</b><span id="diff">--/--</span></div><div class="cell"><b>BBAL</b><span id="bbal">--</span></div><div class="cell"><b>ENG BRK</b><span id="engbrk">--</span></div><div class="cell"><b>FUEL MODE</b><span id="fuelMode">--</span></div><div class="cell"><b>PEN</b><span id="pen">--</span></div>
 </div>
 <div id="footer">WEB --</div>
</div>
<!-- compatibility: DAMAGE &amp; POWER UNIT | ALL CAR / AERO DAMAGE AND ENGINE / HYBRID WEAR -->
<div class="infoPage" id="damagePage"><div class="pageTitle">DAMAGE</div><div class="pageSub">CAR / AERO + POWER UNIT / HYBRID</div><div class="damageCombined">
 <div class="damageGroup"><div class="groupTitle">CAR / AERO DAMAGE</div><div class="damageGrid">
  <div class="statusCard"><b>FL WING</b><span id="dcFL">--</span></div><div class="statusCard"><b>FR WING</b><span id="dcFR">--</span></div><div class="statusCard"><b>REAR WING</b><span id="dcRW">--</span></div>
  <div class="statusCard"><b>FLOOR</b><span id="dcFloor">--</span></div><div class="statusCard"><b>DIFFUSER</b><span id="dcDiff">--</span></div><div class="statusCard"><b>SIDEPOD</b><span id="dcSide">--</span></div>
  <div class="statusCard faultCard"><b>DRS</b><span id="dcDRS">OK</span></div><div class="statusCard faultCard"><b>ERS</b><span id="dcERS">OK</span></div><div class="statusCard faultCard"><b>ENGINE STATE</b><span id="dcState">OK</span></div><div class="statusCard engineTempCard"><b>ENGINE TEMP</b><span id="puTemp">--</span></div>
 </div></div>
 <div class="damageGroup"><div class="groupTitle">POWER UNIT / HYBRID WEAR</div><div class="puGrid">
  <div class="statusCard"><b>ENGINE</b><span id="puEngine">--</span></div><div class="statusCard"><b>GEARBOX</b><span id="puGBX">--</span></div>
  <div class="statusCard"><b>ICE</b><span id="puICE">--</span></div><div class="statusCard"><b>CE</b><span id="puCE">--</span></div>
  <div class="statusCard"><b>ES</b><span id="puES">--</span></div><div class="statusCard"><b>MGU-H</b><span id="puMGUH">--</span></div>
  <div class="statusCard"><b>MGU-K</b><span id="puMGUK">--</span></div><div class="statusCard"><b>TC</b><span id="puTC">--</span></div>
 </div><span id="puFault" style="display:none">NONE</span></div>
</div></div>
<div class="infoPage" id="tyresPage"><div class="pageTitle">TYRES &amp; BRAKES</div><div class="pageSub" id="tyreSub">FOUR-CORNER TYRE / BRAKE STATUS</div><div class="tyreQuad">
 <div class="tyreCenter" id="tyreCenter">SET --</div><div class="tyreSetMeta" id="tyreSetMeta">--</div>
 <div class="tyreRefCard left" id="tcFL"><span class="tyreCorner">FL</span><div class="tyrePsi" id="tpFL"><span class="psiVal">--</span><small class="psiLab">PSI</small></div><div class="tyreData" id="ttFL"></div><div class="gaugeGroup"><div class="tempGauge gOut" id="thFL"><i></i></div><div class="tempGauge gIn" id="tiFL"><i></i></div><div class="brakeGauge gBrk" id="bgFL"><i></i></div><div class="gaugeLabels"><span>OUT</span><span>IN</span><span>BRK</span></div></div><div class="brakeBox"><span class="brakeLabel">BRAKE</span><span class="brakeTemp" id="btFL">--</span><span class="brakeLabel">BRAKE DMG</span><span class="brakeDmg" id="bdFL">--</span></div></div>
 <div class="tyreRefCard right" id="tcFR"><span class="tyreCorner">FR</span><div class="tyrePsi" id="tpFR"><span class="psiVal">--</span><small class="psiLab">PSI</small></div><div class="tyreData" id="ttFR"></div><div class="gaugeGroup"><div class="tempGauge gOut" id="thFR"><i></i></div><div class="tempGauge gIn" id="tiFR"><i></i></div><div class="brakeGauge gBrk" id="bgFR"><i></i></div><div class="gaugeLabels"><span>OUT</span><span>IN</span><span>BRK</span></div></div><div class="brakeBox"><span class="brakeLabel">BRAKE</span><span class="brakeTemp" id="btFR">--</span><span class="brakeLabel">BRAKE DMG</span><span class="brakeDmg" id="bdFR">--</span></div></div>
 <div class="tyreRefCard left" id="tcRL"><span class="tyreCorner">RL</span><div class="tyrePsi" id="tpRL"><span class="psiVal">--</span><small class="psiLab">PSI</small></div><div class="tyreData" id="ttRL"></div><div class="gaugeGroup"><div class="tempGauge gOut" id="thRL"><i></i></div><div class="tempGauge gIn" id="tiRL"><i></i></div><div class="brakeGauge gBrk" id="bgRL"><i></i></div><div class="gaugeLabels"><span>OUT</span><span>IN</span><span>BRK</span></div></div><div class="brakeBox"><span class="brakeLabel">BRAKE</span><span class="brakeTemp" id="btRL">--</span><span class="brakeLabel">BRAKE DMG</span><span class="brakeDmg" id="bdRL">--</span></div></div>
 <div class="tyreRefCard right" id="tcRR"><span class="tyreCorner">RR</span><div class="tyrePsi" id="tpRR"><span class="psiVal">--</span><small class="psiLab">PSI</small></div><div class="tyreData" id="ttRR"></div><div class="gaugeGroup"><div class="tempGauge gOut" id="thRR"><i></i></div><div class="tempGauge gIn" id="tiRR"><i></i></div><div class="brakeGauge gBrk" id="bgRR"><i></i></div><div class="gaugeLabels"><span>OUT</span><span>IN</span><span>BRK</span></div></div><div class="brakeBox"><span class="brakeLabel">BRAKE</span><span class="brakeTemp" id="btRR">--</span><span class="brakeLabel">BRAKE DMG</span><span class="brakeDmg" id="bdRR">--</span></div></div>
</div></div>
<div class="infoPage" id="mapPage"><div class="pageTitle">TRACK MAP</div><div class="pageSub" id="mapSub">LIVE POSITION</div><div class="mapWrap"><svg id="trackSvg" viewBox="0 0 1000 560" preserveAspectRatio="xMidYMid meet"><path id="trackPath" class="mapTrack" d=""></path><circle id="mapDot" cx="0" cy="0" r="0" style="display:none"></circle></svg></div><div class="mapLegend"><span><i style="background:#ffdc34"></i>YOU</span><span><i style="background:#3ec8ff"></i>REF</span><span><i style="background:#ff4755"></i>AHEAD</span><span><i style="background:#2de77d"></i>BEHIND</span></div><div class="mapInfo" id="mapInfo">TRACK MAP READY</div></div>
<div class="infoPage" id="pitPage"><div class="pageTitle">PIT</div><div class="pageSub">LIVE PIT / SERVICE STATUS</div><div style="text-align:center;font-size:clamp(28px,5vw,68px);font-weight:900;margin:1vh 0 3vh" id="pitState">NONE</div><div class="grid4">
 <div class="infoCell"><b>PIT STOPS</b><span id="pitStops">--</span></div><div class="infoCell"><b>SPEED LIMIT</b><span id="pitLimit">--</span></div><div class="infoCell"><b>LANE TIME</b><span id="pitLane">--</span></div><div class="infoCell"><b>STOP TIME</b><span id="pitStop">--</span></div>
 <div class="infoCell"><b>NEXT TYRE</b><span id="pitTyre">--</span></div><div class="infoCell"><b>TYRE SET</b><span id="pitSet">--</span></div><div class="infoCell"><b>PENALTY</b><span id="pitPen">--</span></div><div class="infoCell"><b>SERVE PEN</b><span id="pitServe">NO</span></div></div></div>
</div>
<script>
const $=id=>document.getElementById(id);
function scaleStage(){const st=$('stage'),sw=800,sh=480,s=Math.min(window.innerWidth/sw,window.innerHeight/sh);st.style.transform=`translate(-50%,-50%) scale(${s})`}window.addEventListener('resize',scaleStage);scaleStage();
const rev=$('rev');for(let i=0;i<15;i++){let e=document.createElement('div');e.className='led';rev.appendChild(e)}
let currentPage='dash',manualPage='dash',autoPage=null,damageUntil=0,lastDamage=null,lastCoachMode=null;function setPage(page,manual=false){currentPage=page;if(manual){manualPage=page;autoPage=null}document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('active',b.dataset.page===page));['damage','tyres','map','pit'].forEach(p=>$(p+'Page').classList.toggle('active',p===page));['main','bars','strip','footer'].forEach(id=>$(id).style.visibility=page==='dash'?'visible':'hidden');$('stage').classList.toggle('infoMode',page!=='dash');$('rev').style.visibility=page==='dash'?'visible':'hidden'}document.querySelectorAll('#nav button[data-page]').forEach(b=>b.onclick=()=>setPage(b.dataset.page,true));$('dashBack').onclick=()=>{location.href='/performance'};function pitActive(s){let p=String(s.pit_status||'').toUpperCase();return !!s.pit_lane_timer_active||!['','NONE','N/A','--','0'].includes(p)}function damageVector(s){return [s.front_left_wing_damage_percent,s.front_right_wing_damage_percent,s.rear_wing_damage_percent,s.floor_damage_percent,s.diffuser_damage_percent,s.sidepod_damage_percent,s.gearbox_damage_percent,s.engine_damage_percent,s.drs_fault?100:0,s.ers_fault?100:0].map(v=>Number.isFinite(v)?Number(v):0)}function autoSelectPage(s){let now=performance.now(),v=damageVector(s),mode=String(s.coaching_mode||'auto'),focus=String(s.dashboard_focus_page||'dash');if(lastCoachMode===null||mode!==lastCoachMode){lastCoachMode=mode;if(['dash','damage','tyres','map','pit'].includes(focus)){manualPage=focus;if(!autoPage)setPage(focus,false)}}if(lastDamage&&v.some((x,i)=>x>lastDamage[i]+.01))damageUntil=now+3000;lastDamage=v;if(now<damageUntil){autoPage='damage';setPage('damage',false)}else if(pitActive(s)){autoPage='pit';setPage('pit',false)}else if(autoPage){autoPage=null;setPage(manualPage,false)}}
function pct(v,d=0){return v==null||!isFinite(v)?'--':`${Number(v).toFixed(d)}%`}function val(v,s='',d=0){return v==null||!isFinite(v)?'--':`${Number(v).toFixed(d)}${s}`}function damageClass(v){return v>=60?'bad':v>=25?'warn':'ok'}function dmgColor(v){return v==null||!isFinite(v)?'#758292':v>=60?'#ff4755':v>=25?'#ffc14d':'#2def85'}function tyreColor(v){return v==null||!isFinite(v)?'#758292':v<70?'#3ec8ff':v<105?'#2def85':v<115?'#ffc14d':'#ff4755'}function brakeColor(v){return v==null||!isFinite(v)?'#758292':v<1000?'#2def85':v<1100?'#ffc14d':'#ff4755'}function wearColor(v){return v==null||!isFinite(v)?'#758292':v<25?'#2def85':v<60?'#ffc14d':'#ff4755'}function setZone(id,v,label){let e=$(id),c=dmgColor(v);e.style.borderColor=c;e.style.background=`${c}55`;e.style.boxShadow=`0 0 .7vw ${c}55`;e.innerHTML=`${label}<br><strong>${pct(v)}</strong>`}
function setStatusValue(id,v,colorFn=dmgColor,suffix='%'){let e=$(id),c=colorFn(v);e.textContent=v==null||!isFinite(v)?'--':`${Number(v).toFixed(0)}${suffix}`;e.style.color=c}
function tyreRow(label,value,color){return `<div class="tyreRow"><b>${label}</b><span style="color:${color}">${value}</span></div>`}
let tyreCacheUid=null,tyreLiveCache={};function stickyWheel(s,key){if(s.session_uid!==tyreCacheUid){tyreCacheUid=s.session_uid;tyreLiveCache={}}let a=Array.isArray(s[key])?s[key]:[],c=tyreLiveCache[key]||[null,null,null,null];for(let i=0;i<4;i++){if(Number.isFinite(a[i]))c[i]=a[i]}tyreLiveCache[key]=c;return c}
function engColor(v){if(v==null||!isFinite(v))return'#758292';v=Math.max(0,Math.min(100,Number(v)));return v<20?'#51f622':v<40?'#c6e82a':v<60?'#ffc14d':v<80?'#ff843c':'#ff4755'}function setEngText(id,v){let e=$(id),c=engColor(v);e.textContent=pct(v);e.setAttribute('fill',c)}function setEngZone(id,v){let e=$(id),c=engColor(v);e.setAttribute('stroke',c);e.setAttribute('fill',c)}function setEngStroke(id,v){let e=$(id),c=engColor(v);e.setAttribute('stroke',c)}
const predefinedTracks=__TRACK_MAPS__;
function trackKey(name){return String(name||'').trim().toUpperCase()||null}function cumulative(points){let c=[0],t=0;for(let i=1;i<points.length;i++){t+=Math.hypot(points[i][0]-points[i-1][0],points[i][1]-points[i-1][1]);c.push(t)}return [c,t]}function interpolate(points,f){if(!points.length)return null;if(points.length===1)return points[0];f=Math.max(0,Math.min(1,Number(f)||0));let [cum,total]=cumulative(points);if(total<=0)return points[points.length-1];let target=total*f;for(let i=1;i<points.length;i++){if(cum[i]>=target){let seg=Math.max(1e-9,cum[i]-cum[i-1]),t=(target-cum[i-1])/seg;return [points[i-1][0]+(points[i][0]-points[i-1][0])*t,points[i-1][1]+(points[i][1]-points[i-1][1])*t]}}return points[points.length-1]}function interpolateDistance(points,axis,distance,length){if(!Array.isArray(points)||!Array.isArray(axis)||!points.length||!Number.isFinite(distance)||!Number.isFinite(length)||length<=1)return null;let base=(points.length>1&&points[0][0]===points[points.length-1][0]&&points[0][1]===points[points.length-1][1]&&axis.length===points.length-1)?points.slice(0,-1):(axis.length===points.length?points:null);if(!base||base.length<2)return null;let d=((distance%length)+length)%length;if(d<=axis[0])return base[0];let ax=axis.concat([length]),loop=base.concat([base[0]]),i=1;while(i<ax.length&&ax[i]<d)i++;i=Math.max(1,Math.min(i,ax.length-1));let d0=ax[i-1],d1=ax[i],a=d1>d0?Math.max(0,Math.min(1,(d-d0)/(d1-d0))):1;return [loop[i-1][0]+(loop[i][0]-loop[i-1][0])*a,loop[i-1][1]+(loop[i][1]-loop[i-1][1])*a]}function mapTransform(points){let rx=points.map(p=>p[0]),ry=points.map(p=>p[1]),rdx=Math.max(1e-6,Math.max(...rx)-Math.min(...rx)),rdy=Math.max(1e-6,Math.max(...ry)-Math.min(...ry)),rotate=rdy>rdx*1.10,op=points.map(p=>rotate?[p[1],-p[0]]:p),xs=op.map(p=>p[0]),ys=op.map(p=>p[1]),minx=Math.min(...xs),maxx=Math.max(...xs),miny=Math.min(...ys),maxy=Math.max(...ys),dx=Math.max(1e-6,maxx-minx),dy=Math.max(1e-6,maxy-miny),W=1000,H=560,sc=Math.min(W*.985/dx,H*.985/dy),ox=W/2-(minx+maxx)*.5*sc,oy=H/2-(miny+maxy)*.5*sc;return {sc,ox,oy,rotate,orient:p=>rotate?[p[1],-p[0]]:p}}
let trackUid=null;
function drawMapMarker(svg,id,x,y,color,label,r=8){let e=$(id);if(!e){e=document.createElementNS('http://www.w3.org/2000/svg','g');e.id=id;let c=document.createElementNS('http://www.w3.org/2000/svg','circle');let t=document.createElementNS('http://www.w3.org/2000/svg','text');e.appendChild(c);e.appendChild(t);svg.appendChild(e)}let c=e.children[0],t=e.children[1];c.setAttribute('cx',x);c.setAttribute('cy',y);c.setAttribute('r',r);c.setAttribute('fill',color);c.setAttribute('stroke','#07090b');c.setAttribute('stroke-width','2');t.setAttribute('x',x);t.setAttribute('y',y+3);t.setAttribute('text-anchor','middle');t.setAttribute('font-size',String(Math.max(10,Math.round(r*.92))));t.setAttribute('font-weight','900');t.setAttribute('fill','#050709');t.textContent=label;e.style.display=''}
function drawTurnLabel(svg,id,x,y,label){let e=$(id);if(!e){e=document.createElementNS('http://www.w3.org/2000/svg','g');e.id=id;let c=document.createElementNS('http://www.w3.org/2000/svg','circle');let t=document.createElementNS('http://www.w3.org/2000/svg','text');e.appendChild(c);e.appendChild(t);svg.appendChild(e)}let c=e.children[0],t=e.children[1];c.setAttribute('cx',x);c.setAttribute('cy',y);c.setAttribute('r','10');c.setAttribute('fill','#e8edf2');c.setAttribute('stroke','#071018');c.setAttribute('stroke-width','2');t.setAttribute('x',x);t.setAttribute('y',y+3);t.setAttribute('text-anchor','middle');t.setAttribute('font-size','10');t.setAttribute('font-weight','900');t.setAttribute('fill','#131b23');t.textContent=label;e.style.display=''}
function hideExtraMapMarkers(keep){document.querySelectorAll('#trackSvg g[id^="mk"]').forEach(e=>{if(!keep.has(e.id))e.style.display='none'});document.querySelectorAll('#trackSvg g[id^="turnLabel"]').forEach(e=>{if(!keep.has(e.id))e.style.display='none'})}
function updateTrackMap(s){
 if(s.session_uid!=null&&s.session_uid!==trackUid){trackUid=s.session_uid}
 let pre=Array.isArray(s.track_map_points)&&s.track_map_points.length>20?s.track_map_points:null;
 let learning=!pre&&Array.isArray(s.map_learning_points)&&s.map_learning_points.length>1?s.map_learning_points:null;
 $('mapSub').textContent=`${(s.track_name||'--').toUpperCase()}  •  YOU / REF / NEARBY`;
 let pts=pre||learning;
 let svg=$('trackSvg');
 svg.querySelectorAll('path[id^="perfZone"]').forEach(e=>e.remove());
 if(!pts||pts.length<2){$('trackPath').setAttribute('d','');$('mapInfo').textContent='WAITING FOR START LINE — MAP CAPTURE STARTS AT S/F';hideExtraMapMarkers(new Set());return}
 let {sc,ox,oy,orient}=mapTransform(pts);let path=pts.map((q,i)=>{let o=orient(q);return `${i?'L':'M'} ${ox+o[0]*sc} ${oy+o[1]*sc}`}).join(' ');$('trackPath').setAttribute('d',path);let start=orient(pts[0]),sx=ox+start[0]*sc,sy=oy+start[1]*sc,scirc=$('mapStartCircle'),stxt=$('mapStartText');if(!scirc){scirc=document.createElementNS('http://www.w3.org/2000/svg','circle');scirc.id='mapStartCircle';scirc.setAttribute('class','mapStart');scirc.setAttribute('r','7');svg.appendChild(scirc);stxt=document.createElementNS('http://www.w3.org/2000/svg','text');stxt.id='mapStartText';stxt.setAttribute('class','mapStartText');stxt.textContent='START';svg.appendChild(stxt)}scirc.setAttribute('cx',sx);scirc.setAttribute('cy',sy);stxt.setAttribute('x',sx);stxt.setAttribute('y',sy-12);
 let fracPoint=distance=>{if(!pre||!Number.isFinite(distance)||!Number.isFinite(s.track_length_m)||s.track_length_m<=1)return null;let exact=interpolateDistance(pre,s.track_map_distances_m,distance,s.track_length_m);return exact||interpolate(pre,(distance%s.track_length_m)/s.track_length_m)};
 /* Dashboard map intentionally omits CORNER COACH gain/loss colouring. */
 let keep=new Set();if(pre){for(let turn of (s.map_turns||[])){let q=fracPoint(turn.lap_distance_m);if(!q)continue;q=orient(q);let id=`turnLabel${turn.corner_id}`;drawTurnLabel(svg,id,ox+q[0]*sc,oy+q[1]*sc,turn.label||`T${turn.corner_id}`);keep.add(id)}}
 let player=(Number.isFinite(s.world_position_x)&&Number.isFinite(s.world_position_z))?[s.world_position_x,s.world_position_z]:(pre?fracPoint(s.lap_distance_m):pts[pts.length-1]);if(player){player=orient(player);drawMapMarker(svg,'mkPlayer',ox+player[0]*sc,oy+player[1]*sc,'#ffdc34',String(s.position??1),16);keep.add('mkPlayer')}
 let ref=fracPoint(s.reference_map_distance_m);if(ref){ref=orient(ref);drawMapMarker(svg,'mkRef',ox+ref[0]*sc,oy+ref[1]*sc,'#3ec8ff','R',13);keep.add('mkRef')}let ai=0,bi=0;if(pre){for(let m of (s.map_nearby||[])){let q=fracPoint(m.lap_distance_m);if(!q)continue;q=orient(q);let ahead=m.kind==='ahead',color=ahead?(ai++===0?'#ff4755':'#ff9146'):(bi++===0?'#2de77d':'#ad6aff'),id=`mk${ahead?'A':'B'}${m.position??ai+bi}`;drawMapMarker(svg,id,ox+q[0]*sc,oy+q[1]*sc,color,String(m.position??'?'),13);keep.add(id)}}hideExtraMapMarkers(keep);let delta=Number.isFinite(s.map_full_track_delta_s)?`  •  LAST Δ ${s.map_full_track_delta_s>=0?'+':''}${s.map_full_track_delta_s.toFixed(3)}s`:'';$('mapInfo').textContent=pre?`LAP ${s.lap_number??'--'} / ${s.total_laps??'--'}  •  P${s.position??'--'}  •  ${Number.isFinite(s.lap_distance_m)?Math.round(s.lap_distance_m)+' m':'--'}${delta}`:'LEARNING TRACK MAP — COMPLETE S/F LAP REQUIRED';}


function gear(v){return v==null?'--':v===0?'N':v<0?'R':String(v)}
function tm(v){if(v==null||!isFinite(v))return'--:--.---';let m=Math.floor(v/60),s=v-m*60;return `${m}:${s.toFixed(3).padStart(6,'0')}`}
function p0(v){return v==null||!isFinite(v)?'--':`${Math.round(v)}%`}
function setPill(id,on,warn=false){let e=$(id);e.className='pill'+(on?(warn?' warn':' on'):'')}
function fuelModeText(v){return (typeof v==='string'&&v.trim())?v.toUpperCase():'--'}
function render(s){
 $('offline').className=s.connected?'':'show';autoSelectPage(s);$('speed').textContent=s.speed_kph??0;$('gear').textContent=gear(s.gear);$('pos').textContent=`P${s.position??'--'}`;$('lap').textContent=s.lap_number??'--';$('laps').textContent=`/ ${s.total_laps??'--'}`;$('lapTime').textContent=tm(s.lap_time_s);
 let d=s.delta_s;$('delta').textContent=d==null?'--.---':`${d>=0?'+':''}${d.toFixed(3)}`;$('delta').className='v delta '+(d==null?'':d<=0?'good':'bad');$('validity').textContent=s.lap_valid===false?'INVALID':'VALID';$('validity').className=s.lap_valid===false?'invalid':'';
 let ep=s.ers_percent;$('ersTxt').textContent=ep==null?'--%':`${Math.round(ep)}%`;$('ersBar').style.width=`${ep??0}%`;let fl=s.fuel_laps;$('fuelTxt').textContent=fl==null?'-- LAPS':`${fl.toFixed(1)} LAPS`;$('fuelBar').style.width=`${fl==null?0:Math.max(0,Math.min(100,fl/6*100))}%`;
 $('thr').style.width=`${Math.round((s.throttle||0)*100)}%`;$('thrTxt').textContent=`${Math.round((s.throttle||0)*100)}%`;$('brk').style.width=`${Math.round((s.brake||0)*100)}%`;$('brkTxt').textContent=`${Math.round((s.brake||0)*100)}%`;
 setPill('drs',!!s.s_mode_active,!!s.s_mode_available&&!s.s_mode_active);$('ersMode').textContent=s.ers_deploy_mode||'ERS';setPill('ersMode',!!s.overtake_active);setPill('overtake',!!s.overtake_active,!!s.overtake_available&&!s.overtake_active);
 let rp=Math.max(0,Math.min(100,s.rev_lights_percent??0)),on=Math.round(rp/100*15);[...rev.children].forEach((e,i)=>e.className='led'+(i<on?` on ${i<5?'g':i<10?'r':'b'}`:''));
 let din=s.setup_diff_on_throttle_percent,dout=s.setup_diff_off_throttle_percent;$('diff').textContent=(din==null&&dout==null)?'--/--':`${din==null?'--':Math.round(din)}/${dout==null?'--':Math.round(dout)}%`;$('bbal').textContent=p0(s.setup_brake_bias_percent);$('engbrk').textContent=p0(s.setup_engine_braking_percent);
 let pen=s.penalties_s;$('fuelMode').textContent=fuelModeText(s.fuel_mix);$('pen').textContent=pen==null?'--':`${Math.round(pen)}s`;$('pen').className=pen>0?'warn':'';
 setStatusValue('dcFL',s.front_left_wing_damage_percent);setStatusValue('dcFR',s.front_right_wing_damage_percent);setStatusValue('dcRW',s.rear_wing_damage_percent);setStatusValue('dcFloor',s.floor_damage_percent);setStatusValue('dcDiff',s.diffuser_damage_percent);setStatusValue('dcSide',s.sidepod_damage_percent);
 $('dcDRS').textContent=s.drs_fault?'FAULT':'OK';$('dcDRS').style.color=s.drs_fault?'#ff4755':'#2def85';$('dcERS').textContent=s.ers_fault?'FAULT':'OK';$('dcERS').style.color=s.ers_fault?'#ff4755':'#2def85';let engineFault=!!s.engine_blown||!!s.engine_seized;$('dcState').textContent=s.engine_blown?'BLOWN':s.engine_seized?'SEIZED':'OK';$('dcState').style.color=engineFault?'#ff4755':'#2def85';
 setStatusValue('puEngine',s.engine_damage_percent,engColor);setStatusValue('puGBX',s.gearbox_damage_percent,engColor);setStatusValue('puICE',s.engine_ice_wear_percent,engColor);setStatusValue('puCE',s.engine_ce_wear_percent,engColor);setStatusValue('puES',s.engine_es_wear_percent,engColor);setStatusValue('puMGUH',s.engine_mguh_wear_percent,engColor);setStatusValue('puMGUK',s.engine_mguk_wear_percent,engColor);setStatusValue('puTC',s.engine_tc_wear_percent,engColor);$('puTemp').textContent=val(s.engine_temperature_c,'°C',0);$('puTemp').style.color='#dce3e9';$('puFault').textContent=s.engine_blown?'BLOWN':s.engine_seized?'SEIZED':'NONE';$('puFault').style.color=engineFault?'#ff4755':'#2def85';
 $('tyreSub').textContent=`${(s.compound||'--').toUpperCase()}  •  TYRES OUTSIDE / BRAKES INSIDE`;$('tyreCenter').textContent=`SET ${s.tyre_set_index??'--'}`;$('tyreSetMeta').textContent=`${(s.compound||'--').toUpperCase()}`;let surf=stickyWheel(s,'tyre_surface_temp_c'),inn=stickyWheel(s,'tyre_inner_temp_c'),brt=stickyWheel(s,'brake_temp_c'),prs=stickyWheel(s,'tyre_pressure_psi');['FL','FR','RL','RR'].forEach((n,i)=>{let tv=surf[i],iv=inn[i],bv=brt[i],wv=(s.tyre_wear||[])[i],pv=prs[i],dv=(s.tyre_damage_percent||[])[i],bl=(s.tyre_blisters_percent||[])[i],bd=(s.brake_damage_percent||[])[i],sev=Math.max(Number.isFinite(wv)?wv:0,Number.isFinite(dv)?dv:0,Number.isFinite(bl)?bl:0),tc=wearColor(sev),bc=brakeColor(bv),bdc=wearColor(bd);$('tp'+n).innerHTML='';$('tt'+n).innerHTML=tyreRow('PSI',val(pv,'',2),'#f5f7f9')+tyreRow('OUTER',val(tv,'°C',0),tyreColor(tv))+tyreRow('INNER',val(iv,'°C',0),tyreColor(iv))+tyreRow('WEAR',val(wv,'%',1),wearColor(wv))+tyreRow('TYRE DMG',val(dv,'%',1),wearColor(dv))+tyreRow('BLISTER',val(bl,'%',1),wearColor(bl));let of=Number.isFinite(tv)?Math.max(0,Math.min(100,(tv-50)/70*100)):0,inf=Number.isFinite(iv)?Math.max(0,Math.min(100,(iv-50)/70*100)):0,bf=Number.isFinite(bv)?Math.max(0,Math.min(100,bv/1200*100)):0;let go=$('th'+n).querySelector('i'),gi=$('ti'+n).querySelector('i'),bg=$('bg'+n).querySelector('i');go.style.height=`${of}%`;go.style.background=tyreColor(tv);gi.style.height=`${inf}%`;gi.style.background=tyreColor(iv);bg.style.height=`${bf}%`;bg.style.background=bc;$('bt'+n).textContent=val(bv,'°C',0);$('bt'+n).style.color=bc;$('bd'+n).textContent=val(bd,'%',1);$('bd'+n).style.color=bdc;});
 updateTrackMap(s);
 $('pitState').textContent=(s.pit_status||'NONE').toUpperCase();$('pitStops').textContent=s.pit_stops??'--';$('pitLimit').textContent=val(s.pit_speed_limit_kph,' KM/H',0);$('pitLane').textContent=val(s.pit_lane_time_s,' s',1);$('pitStop').textContent=val(s.pit_stop_time_s,' s',1);$('pitTyre').textContent=(s.next_tyre_compound||'--').toUpperCase();$('pitSet').textContent=s.next_tyre_set??'--';$('pitPen').textContent=val(s.penalties_s,' s',0);$('pitServe').textContent=s.serve_penalty?'YES':'NO';$('pitServe').className=s.serve_penalty?'bad':'';
 $('sectorMeta').textContent=s.sector?`S${s.sector}`:'--';$('footer').textContent=`WEB ${window.location.origin}/`;
}
let pendingSnapshot=null,renderFrame=0,coalesced=0,lastLoadMark=performance.now();
function queueRender(s){pendingSnapshot=s;if(renderFrame){coalesced++;return}renderFrame=requestAnimationFrame(()=>{renderFrame=0;let latest=pendingSnapshot;pendingSnapshot=null;if(latest)render(latest);let now=performance.now();if(now-lastLoadMark>1000){document.documentElement.classList.toggle('reduce-motion',coalesced>4);coalesced=0;lastLoadMark=now}})}
function connect(){let es=new EventSource('/events');es.onmessage=e=>{try{queueRender(JSON.parse(e.data))}catch(_){}};es.onerror=()=>{es.close();setTimeout(connect,1000)}}connect();
</script>
</body></html>'''


DASHBOARD_HTML = DASHBOARD_HTML.replace("__TRACK_MAPS__", json.dumps(TRACK_MAPS, separators=(",", ":")))


class _DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


@dataclass(slots=True)
class DashboardServerInfo:
    host: str
    port: int
    local_url: str
    lan_url: str


class RemoteDashboardServer:
    """Background HTTP/SSE server serving the current dashboard state."""

    def __init__(self, store: DashboardStateStore | None = None, *, host: str = "0.0.0.0", port: int = 8765, replay_controller=None, replay_mode_setter=None, replay_mode_getter=None) -> None:
        self.store = store or DashboardStateStore()
        self.host = host
        self.port = int(port)
        self.replay_controller = replay_controller
        self.replay_mode_setter = replay_mode_setter
        self.replay_mode_getter = replay_mode_getter
        self._httpd: _DashboardHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @staticmethod
    def lan_ip() -> str:
        # UDP connect selects the outbound interface without sending application data.
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.connect(("8.8.8.8", 80))
                ip = sock.getsockname()[0]
            finally:
                sock.close()
            if ip and not ip.startswith("127."):
                return ip
        except OSError:
            pass
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if ip:
                return ip
        except OSError:
            pass
        return "127.0.0.1"

    def _handler_type(self):
        store = self.store
        stop = self._stop
        replay_controller = self.replay_controller
        replay_mode_setter = self.replay_mode_setter
        replay_mode_getter = self.replay_mode_getter

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, _format: str, *_args) -> None:
                return

            def _is_local_request(self) -> bool:
                # Local Control Center often opens the LAN URL (for example
                # http://192.168.x.x:8765) even on the same PC. In that case
                # client_address is the PC's LAN address, not 127.0.0.1.
                # Accept loopback, or a client whose address exactly matches
                # the Host address being served. Remote LAN clients have a
                # different source address and remain read-only for destructive
                # Performance Hub actions.
                client=str(self.client_address[0] if self.client_address else '').strip('[]')
                if client in {'127.0.0.1','::1'} or client.startswith('127.'):
                    return True
                host_header=str(self.headers.get('Host') or '').strip()
                host=host_header
                if host.startswith('[') and ']' in host:
                    host=host[1:host.index(']')]
                elif ':' in host:
                    host=host.rsplit(':',1)[0]
                return bool(client and host and client == host.strip('[]'))

            def _headers(self, status: int, content_type: str, length: int | None = None) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                if length is not None:
                    self.send_header("Content-Length", str(length))
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = parsed.path
                query = parse_qs(parsed.query)
                if path in {"/", "/index.html"}:
                    body = DASHBOARD_HTML.encode("utf-8")
                    self._headers(200, "text/html; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path == "/api/state":
                    _seq, payload = store.read()
                    body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
                    self._headers(200, "application/json; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path in {"/radio-help", "/radio-help/"}:
                    body = radio_help_page_html().encode("utf-8")
                    self._headers(200, "text/html; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path in {"/sessions", "/sessions/"}:
                    body = session_library_page_html().encode("utf-8")
                    self._headers(200, "text/html; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path in {"/settings", "/settings/"}:
                    body = settings_page_html().encode("utf-8")
                    self._headers(200, "text/html; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path in {"/setup", "/setup/"}:
                    body = setup_page_html().encode("utf-8")
                    self._headers(200, "text/html; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path == "/api/setup":
                    body=json.dumps(setup_api_snapshot(),separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/lan-qr.svg":
                    lan_url=f"http://{self.server.server_address[0]}:{self.server.server_address[1]}/"
                    try:
                        host=RemoteDashboardServer.lan_ip(); lan_url=f"http://{host}:{self.server.server_address[1]}/"
                    except Exception:
                        pass
                    body=lan_qr_svg(lan_url); self._headers(200,"image/svg+xml",len(body)); self.wfile.write(body); return
                if path == "/api/settings":
                    body=json.dumps(settings_snapshot(),separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/transcript":
                    try:
                        name=str((query.get("name") or [""])[0]); body=transcript_text(name).encode("utf-8")
                        self._headers(200,"text/plain; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=str(error).encode("utf-8"); self._headers(404,"text/plain; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path == "/api/sessions":
                    include_archived = str((query.get("archived") or ["0"])[0]).lower() in {"1","true","yes"}
                    favorite = str((query.get("favorite") or ["0"])[0]).lower() in {"1","true","yes"}
                    q=(query.get("q") or [""])[0]
                    tags=[x for raw in (query.get("tags") or []) for x in str(raw).split(",") if x]
                    st=(query.get("session_type") or [None])[0]; tid=(query.get("track_id") or [None])[0]
                    rows = SessionLibrary().search(q,tags=tags,favorites_only=favorite,include_archived=include_archived,session_type=st,track_id=tid)
                    body = json.dumps({"available": bool(rows), "sessions": rows}, separators=(",", ":"), allow_nan=False, default=str).encode("utf-8")
                    self._headers(200, "application/json; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path == "/api/replay/details":
                    try:
                        filename=str((query.get("file") or [""])[0]); payload=SessionLibrary().replay_details(filename)
                        body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8"); self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=json.dumps({"ok":False,"error":str(error)}).encode("utf-8"); self._headers(400,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path == "/api/replay/status":
                    try:
                        if replay_controller is None:
                            payload={"available":False,"active":False}
                        else:
                            st=replay_controller.status()
                            mode_active = bool(replay_mode_getter()) if replay_mode_getter is not None else bool(replay_controller.current_file())
                            payload={"available":True,"active":mode_active,"file":Path(replay_controller.current_file()).name if replay_controller.current_file() else None,**vars(st)}
                        body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8"); self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=json.dumps({"available":False,"error":str(error)}).encode("utf-8"); self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path in {"/coach", "/coach/"}:
                    body = coaching_page_html().encode("utf-8")
                    self._headers(200, "text/html; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path in {"/performance", "/performance/"}:
                    body = performance_hub_page_html().encode("utf-8")
                    self._headers(200, "text/html; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path in {"/practice", "/practice/"}:
                    body = practice_hub_page_html().encode("utf-8")
                    self._headers(200, "text/html; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path == "/api/performance/overview":
                    driver=(query.get("driver") or [None])[0]
                    session_group=(query.get("session_group") or [None])[0]
                    game_mode=(query.get("game_mode") or [None])[0]
                    payload=PerformanceHistoryStore().overview(driver,session_group_filter=session_group,game_mode_filter=game_mode)
                    try:
                        from .driver_profiles import DriverProfileStore
                        active_profile=DriverProfileStore().active_profile() or {}
                        payload["time_zone"]=str(active_profile.get("time_zone") or "UTC")
                    except Exception:
                        payload["time_zone"]="UTC"
                    body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/performance/progress":
                    history_driver=(query.get("driver") or [None])[0]
                    track=(query.get("track") or ["all"])[0] or "all"
                    binding=_driver_profile_for_history_id(history_driver)
                    did=binding.get("driver_id")
                    if did:
                        from .driver_skill_reconciliation import DriverSkillReconciliation
                        payload=DriverSkillReconciliation().build(str(did),str(track))
                        payload["driver"]={"id":did,"name":(binding.get("profile") or {}).get("display_name")}
                    else:
                        payload={"available":False,"reason":"no_driver_profile","track":str(track)}
                    body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/practice/overview":
                    binding=_practice_driver_binding((query.get("driver") or [None])[0])
                    hid=binding.get("history_profile_id")
                    ph=PerformanceHistoryStore().overview(hid) if hid is not None else {"available":False,"tracks":[]}
                    payload={
                        "available":bool(binding.get("profiles")),
                        "driver":{"id":binding.get("driver_id"),"name":binding.get("profile",{}).get("display_name")},
                        "profiles":binding.get("profiles",[]),
                        "tracks":ph.get("tracks",[]) if isinstance(ph,dict) else [],
                        "time_zone":binding.get("profile",{}).get("time_zone") or "UTC",
                    }
                    body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/practice/track":
                    track=str((query.get("track") or [""])[0]); driver=(query.get("driver") or [None])[0]
                    binding=_practice_driver_binding(driver)
                    hid=binding.get("history_profile_id")
                    ref=(query.get("reference") or [None])[0]
                    condition=(query.get("condition") or [None])[0]
                    payload=PerformanceHistoryStore().practice_track_detail(track,hid,reference=ref,condition=condition) if hid is not None else {"available":False,"reason":"no_linked_performance_history"}
                    payload["driver"]={"id":binding.get("driver_id"),"name":binding.get("profile",{}).get("display_name")}
                    payload["time_zone"]=binding.get("profile",{}).get("time_zone") or "UTC"
                    try:
                        from .user_time import format_profile_timestamp
                        for row in payload.get("sessions") or []:
                            if isinstance(row,dict): row["created_display"]=format_profile_timestamp(row.get("created_utc"),payload["time_zone"])
                    except Exception:
                        pass
                    body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/performance/track":
                    track=str((query.get("track") or [""])[0]); driver=(query.get("driver") or [None])[0]
                    session_group=(query.get("session_group") or [None])[0]
                    game_mode=(query.get("game_mode") or [None])[0]
                    payload=PerformanceHistoryStore().track_detail(track,driver,session_group_filter=session_group,game_mode_filter=game_mode)
                    body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/performance/session":
                    try: payload=PerformanceHistoryStore().session_detail(int((query.get("id") or ["0"])[0]))
                    except (ValueError,TypeError): payload={"available":False,"reason":"invalid_session_id"}
                    body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/performance/reference-options":
                    try: payload=PerformanceHistoryStore().review_reference_options(int((query.get("id") or ["0"])[0]))
                    except (ValueError,TypeError): payload={"available":False,"reason":"invalid_session_id","options":[]}
                    body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/performance/review":
                    try:
                        sid=int((query.get("id") or ["0"])[0])
                        raw_ref=(query.get("reference") or query.get("reference_session_id") or [None])[0]
                        raw_lap=(query.get("lap") or [None])[0]
                        try: view_lap=int(raw_lap) if raw_lap not in (None,"","all") else None
                        except (TypeError,ValueError): view_lap=None
                        payload=PerformanceHistoryStore().review_detail(sid,raw_ref,view_lap=view_lap)
                        if payload.get("available"):
                            sess=payload.get("session") or {}; track=sess.get("track_name") or sess.get("track_id")
                            existing=payload.get("track_geometry") if isinstance(payload.get("track_geometry"),dict) else {}
                            if not (existing.get("points") and existing.get("corners")):
                                pts,dists=_dashboard_track_static(track)
                                landmark_corners=TrackLandmarkStore().corners(track) if track else []
                                physical=list(persisted_physical_turns(track)) if track else []
                                payload["track_geometry"]={"track":track,"points":pts or [],"distances":dists or [],"corners":physical or landmark_corners}
                            payload["selected_reference_comparison"]=build_selected_reference_comparison(payload)
                            payload["data_summary"]=deterministic_review_summary(payload)
                            payload["corner_data_summaries"]={str(c.get("corner_id")):deterministic_review_summary(payload,int(c.get("corner_id"))) for c in (payload.get("review",{}).get("corners") or []) if isinstance(c,dict) and isinstance(c.get("corner_id"),int)}
                    except (ValueError,TypeError) as error:
                        payload={"available":False,"reason":"invalid_review_request","error":str(error)}
                    body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                if path == "/api/coach/latest":
                    payload = coaching_summary_payload()
                    body = json.dumps(payload, separators=(",", ":"), allow_nan=False, default=str).encode("utf-8")
                    self._headers(200, "application/json; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path == "/api/driver-history":
                    rows = DriverHistory().load()
                    body = json.dumps({"available": bool(rows), "sessions": rows}, separators=(",", ":"), allow_nan=False, default=str).encode("utf-8")
                    self._headers(200, "application/json; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path == "/api/landmarks":
                    track = (query.get("track") or [None])[0]
                    store_lm = TrackLandmarkStore()
                    payload = {"available": bool(track), "track": track, "track_metadata": store_lm.track_metadata(track) if track else {}, "corners": store_lm.corners(track) if track else []}
                    body = json.dumps(payload, separators=(",", ":"), allow_nan=False, default=str).encode("utf-8")
                    self._headers(200, "application/json; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path == "/health":
                    body = b'{"ok":true}'
                    self._headers(200, "application/json; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if path == "/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    last = -1
                    keepalive_at = time.monotonic()
                    try:
                        while not stop.is_set():
                            seq, payload = store.read()
                            if seq != last:
                                data = json.dumps(payload, separators=(",", ":"), allow_nan=False)
                                self.wfile.write(f"data:{data}\n\n".encode("utf-8"))
                                self.wfile.flush()
                                last = seq
                                keepalive_at = time.monotonic()
                            elif time.monotonic() - keepalive_at >= 1.0:
                                self.wfile.write(b":keepalive\n\n")
                                self.wfile.flush()
                                keepalive_at = time.monotonic()
                            stop.wait(0.02)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                    return
                body = b"Not found"
                self._headers(404, "text/plain; charset=utf-8", len(body))
                self.wfile.write(body)

            def do_POST(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path == "/api/setup":
                    if not self._is_local_request():
                        body=b'{"ok":false,"error":"Setup changes are allowed only from this PC"}'; self._headers(403,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                    try:
                        length=int(self.headers.get("Content-Length") or 0); data=json.loads(self.rfile.read(length).decode("utf-8")) if length else {}; action=str(data.get("action") or "")
                        result=setup_api_action(action,data)
                        body=json.dumps({"ok":True,"result":result},default=str).encode("utf-8"); self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=json.dumps({"ok":False,"error":str(error)}).encode("utf-8"); self._headers(400,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path == "/api/settings":
                    if not self._is_local_request():
                        body=b'{"ok":false,"error":"Settings changes are allowed only from this PC"}'; self._headers(403,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                    try:
                        length=int(self.headers.get("Content-Length") or 0); data=json.loads(self.rfile.read(length).decode("utf-8")) if length else {}; action=str(data.get("action") or "")
                        if action=="export_config": result={"path":str(export_configuration())}
                        elif action=="import_config": result=import_configuration_b64(str(data.get("data") or ""))
                        elif action=="reset_layout": result=reset_user_settings(layout_only=True)
                        elif action=="reset_settings": result=reset_user_settings(layout_only=False)
                        elif action=="diagnostics": result={"path":create_diagnostics()}
                        else: raise ValueError("unknown settings action")
                        body=json.dumps({"ok":True,"result":result},default=str).encode("utf-8"); self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=json.dumps({"ok":False,"error":str(error)}).encode("utf-8"); self._headers(400,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path == "/api/performance/ai-summary":
                    try:
                        length=int(self.headers.get("Content-Length") or 0)
                        data=json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                        scope=str(data.get("scope") or "session")
                        if scope=="track":
                            track=str(data.get("track") or "").strip(); driver=data.get("driver"); sg=data.get("session_group"); gm=data.get("game_mode")
                            if not track: raise ValueError("track is required")
                            tp=PerformanceHistoryStore().track_detail(track,driver,session_group_filter=sg,game_mode_filter=gm)
                            if not tp.get("available"): raise ValueError("track performance summary unavailable")
                            answer=generate_track_ai_summary(tp)
                            result={"ok":True,"scope":"track","summary":answer,"model_source":"local Ollama","authoritative":False}
                            body=json.dumps(result,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                            self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                        if scope=="practice_track":
                            track=str(data.get("track") or "").strip(); driver=data.get("driver")
                            if not track: raise ValueError("track is required")
                            binding=_practice_driver_binding(driver)
                            hid=binding.get("history_profile_id")
                            if hid is None: raise ValueError("selected Driver has no linked Performance History")
                            tp=PerformanceHistoryStore().practice_track_detail(track,hid,reference=data.get("reference"),condition=data.get("condition"))
                            if not tp.get("available"): raise ValueError("track practice plan unavailable")
                            tp["driver"]={"id":binding.get("driver_id"),"name":binding.get("profile",{}).get("display_name")}
                            answer=generate_practice_ai_summary(tp)
                            result={"ok":True,"scope":"practice_track","summary":answer,"model_source":"local Ollama","authoritative":False}
                            body=json.dumps(result,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                            self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body); return
                        sid=int(data.get("id")); reference=data.get("reference"); corner=data.get("corner_id")
                        raw_lap=data.get("lap")
                        try: view_lap=int(raw_lap) if raw_lap not in (None,"","all") else None
                        except (TypeError,ValueError): view_lap=None
                        corner_id=int(corner) if corner is not None else None
                        payload=PerformanceHistoryStore().review_detail(sid,reference,view_lap=view_lap)
                        if not payload.get("available"): raise ValueError(payload.get("reason") or "performance review unavailable")
                        sess=payload.get("session") or {}; track=sess.get("track_name") or sess.get("track_id")
                        existing=payload.get("track_geometry") if isinstance(payload.get("track_geometry"),dict) else {}
                        if not (existing.get("points") and existing.get("corners")):
                            pts,dists=_dashboard_track_static(track)
                            landmark_corners=TrackLandmarkStore().corners(track) if track else []
                            physical=list(persisted_physical_turns(track)) if track else []
                            payload["track_geometry"]={"track":track,"points":pts or [],"distances":dists or [],"corners":physical or landmark_corners}
                        payload["selected_reference_comparison"]=build_selected_reference_comparison(payload)
                        if scope=="practice":
                            answer=generate_practice_ai_summary(payload)
                            result={"ok":True,"scope":"practice","summary":answer,"model_source":"local Ollama","authoritative":False}
                        else:
                            answer=generate_ai_summary(payload,corner_id)
                            result={"ok":True,"scope":"corner" if corner_id is not None else "session","corner_id":corner_id,"summary":answer,"model_source":"local Ollama","authoritative":False}
                        body=json.dumps(result,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                        self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=json.dumps({"ok":False,"error":str(error),"summary":"AI summary unavailable. Deterministic data summary remains authoritative."},separators=(",",":"),default=str).encode("utf-8")
                        self._headers(503,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path == "/api/performance/delete":
                    try:
                        if not self._is_local_request(): raise PermissionError("session deletion is local-only")
                        length=int(self.headers.get("Content-Length") or 0)
                        data=json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                        sid=int(data.get("id")); ok=PerformanceHistoryStore().delete_session(sid)
                        if not ok: raise ValueError("session not found")
                        # Keep Driver Profile skill/track views aligned with the
                        # authoritative Performance History database immediately
                        # after a local session delete.
                        try:
                            SkillEvidenceStore().reconcile_with_performance_history()
                        except Exception:
                            pass
                        body=json.dumps({"ok":True,"deleted_session_id":sid},separators=(",",":")).encode("utf-8")
                        self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=json.dumps({"ok":False,"error":str(error)}).encode("utf-8"); self._headers(400,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path == "/api/performance/delete-track":
                    try:
                        if not self._is_local_request(): raise PermissionError("track deletion is local-only")
                        length=int(self.headers.get("Content-Length") or 0)
                        data=json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                        track=str(data.get("track") or "").strip()
                        if not track: raise ValueError("track is required")
                        count=PerformanceHistoryStore().delete_track_sessions(track,data.get("driver"))
                        if count<=0: raise ValueError("track history not found")
                        try:
                            SkillEvidenceStore().reconcile_with_performance_history()
                        except Exception:
                            pass
                        body=json.dumps({"ok":True,"track":track,"deleted_sessions":count},separators=(",",":")).encode("utf-8")
                        self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=json.dumps({"ok":False,"error":str(error)}).encode("utf-8"); self._headers(400,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path == "/api/sessions":
                    try:
                        length=int(self.headers.get("Content-Length") or 0)
                        data=json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                        lib=SessionLibrary(); action=str(data.get("action") or "update"); filename=str(data.get("file") or "")
                        if action=="delete":
                            if not self._is_local_request(): raise PermissionError("recording deletion is local-only")
                            result=lib.delete_recording(filename)
                        elif action=="archive": result={"path":str(lib.archive(filename))}
                        elif action=="restore": result={"path":str(lib.restore(filename))}
                        elif action=="favorite": result=lib.favorite(filename,bool(data.get("enabled",True)))
                        elif action=="rename": result=lib.rename(filename,data.get("name") or "")
                        elif action=="tag": result=lib.tag(filename,*(data.get("tags") or []))
                        else: result=lib.update(filename,**(data.get("changes") or {}))
                        body=json.dumps({"ok":True,"result":result},default=str).encode("utf-8"); self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=json.dumps({"ok":False,"error":str(error)}).encode("utf-8"); self._headers(400,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path in {"/api/replay/compare-laps","/api/replay/compare-sessions","/api/replay/jump","/api/replay/workstation","/api/replay/control"}:
                    try:
                        length=int(self.headers.get("Content-Length") or 0); data=json.loads(self.rfile.read(length).decode("utf-8")) if length else {}; lib=SessionLibrary()
                        if path.endswith("compare-laps"):
                            result=lib.compare_laps(str(data.get("file") or ""),list(data.get("laps") or [])); payload={"ok":True,"result":result}
                        elif path.endswith("compare-sessions"):
                            result=lib.compare_sessions(str(data.get("left") or ""),str(data.get("right") or "")); payload={"ok":True,"result":result}
                        elif path.endswith("workstation"):
                            filename=str(data.get("file") or ""); lap=int(data.get("lap")); ref=data.get("reference_lap")
                            result=lib.workstation(filename,lap,int(ref) if ref is not None else None); payload={"ok":True,"result":result}
                        elif path.endswith("control"):
                            if replay_controller is None: raise RuntimeError("Replay controller is unavailable; open the overlay replay runtime first")
                            action=str(data.get("action") or "status").lower(); filename=str(data.get("file") or "")
                            if filename:
                                target=SessionLibrary().recordings/filename
                                current=Path(replay_controller.current_file()).name if replay_controller.current_file() else None
                                if current != target.name:
                                    replay_controller.load_file(target,autoplay=False)
                            # The browser workstation controls the same replay transport as
                            # the native overlay. Merely changing ReplayController.paused is
                            # insufficient while the app is still gated to live UDP: no replay
                            # worker exists to consume packets. Activate replay mode before any
                            # command that expects packets to advance.
                            active = bool(replay_mode_getter()) if replay_mode_getter is not None else True
                            wants_runtime = action in {"load","play","toggle","seek","speed"}
                            activated_now = False
                            if wants_runtime and not active and replay_mode_setter is not None:
                                ok, message = replay_mode_setter(True)
                                if not ok:
                                    raise RuntimeError(message or "Unable to activate replay mode")
                                active = True
                                activated_now = True
                            if action=="play": replay_controller.set_paused(False)
                            elif action=="pause": replay_controller.set_paused(True)
                            elif action=="toggle":
                                # Activating replay mode already starts playback. Do not
                                # immediately toggle it back to paused on the first click.
                                if not activated_now:
                                    replay_controller.toggle_paused()
                            elif action=="speed": replay_controller.set_speed(float(data.get("speed") or 1.0))
                            elif action=="seek": replay_controller.seek(int(data.get("packet") or 0))
                            elif action=="load":
                                # LOAD REPLAY is lap-aware in the workstation. When a lap is
                                # selected, position the runtime at that lap's first indexed
                                # packet before playback starts. This keeps the analysis lap
                                # selector and the actual replay transport synchronized.
                                selected_lap = data.get("lap")
                                if selected_lap is not None and filename:
                                    try:
                                        selected_lap = int(selected_lap)
                                        idx = lib.replay_analysis.build(filename)
                                        lap_row = next((row for row in (idx.get("laps") or []) if int(row.get("lap") or 0) == selected_lap), None)
                                        start_packet = lap_row.get("start_packet") if isinstance(lap_row, dict) else None
                                        if start_packet is None:
                                            raise ValueError(f"Lap {selected_lap} has no indexed start packet")
                                        replay_controller.seek(int(start_packet))
                                    except Exception as error:
                                        raise RuntimeError(f"Unable to load selected lap {selected_lap}: {error}") from error
                                replay_controller.set_paused(False)
                            elif action!="status": raise ValueError(f"unknown replay action: {action}")
                            st=replay_controller.status(); payload={"ok":True,"status":{"file":Path(replay_controller.current_file()).name if replay_controller.current_file() else None,"mode_active":active,**vars(st)}}
                        else:
                            if replay_controller is None: raise RuntimeError("Replay controller is unavailable; open the overlay replay runtime first")
                            filename=str(data.get("file") or ""); packet=int(data.get("packet")); target=SessionLibrary().recordings/filename
                            current=Path(replay_controller.current_file()).name if replay_controller.current_file() else None
                            if current != target.name: replay_controller.load_file(target,autoplay=False)
                            replay_controller.seek(packet); payload={"ok":True,"message":f"Replay positioned at packet {packet}","packet":packet}
                        body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8"); self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    except Exception as error:
                        body=json.dumps({"ok":False,"error":str(error)}).encode("utf-8"); self._headers(400,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                    return
                if path != "/api/landmarks":
                    body=b"Not found"; self._headers(404,"text/plain; charset=utf-8",len(body)); self.wfile.write(body); return
                try:
                    length=int(self.headers.get("Content-Length") or 0)
                    data=json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                    track=str(data.get("track") or "").strip()
                    if not track: raise ValueError("track is required")
                    store_lm=TrackLandmarkStore()
                    if isinstance(data.get("track_metadata"),dict): store_lm.set_track_metadata(track,**data["track_metadata"])
                    if isinstance(data.get("corner_id"),int) and isinstance(data.get("corner"),dict): store_lm.set_manual_corner(track,int(data["corner_id"]),**data["corner"])
                    payload={"ok":True,"track":track,"track_metadata":store_lm.track_metadata(track),"corners":store_lm.corners(track)}
                    body=json.dumps(payload,separators=(",",":"),allow_nan=False,default=str).encode("utf-8")
                    self._headers(200,"application/json; charset=utf-8",len(body)); self.wfile.write(body)
                except (ValueError,TypeError,json.JSONDecodeError) as error:
                    body=json.dumps({"ok":False,"error":str(error)}).encode("utf-8"); self._headers(400,"application/json; charset=utf-8",len(body)); self.wfile.write(body)

        return Handler

    def start(self) -> DashboardServerInfo:
        if self._httpd is not None:
            return self.info()
        self._stop.clear()
        self._httpd = _DashboardHTTPServer((self.host, self.port), self._handler_type())
        # Port 0 is useful in tests; expose the actual chosen port.
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="race-engineer-web-dash", daemon=True)
        self._thread.start()
        return self.info()

    def info(self) -> DashboardServerInfo:
        lan_ip = self.lan_ip()
        return DashboardServerInfo(
            host=self.host,
            port=self.port,
            local_url=f"http://127.0.0.1:{self.port}/",
            lan_url=f"http://{lan_ip}:{self.port}/",
        )

    def stop(self) -> None:
        self._stop.set()
        httpd = self._httpd
        self._httpd = None
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
