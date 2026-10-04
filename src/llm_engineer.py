"""V0.8.1 low-latency local LLM reasoning layer.

Direct telemetry and simple arithmetic stay in Python.  The LLM receives only a
small verified/derived context and is used for judgement/explanation questions.
The Ollama model is warmed asynchronously and kept resident to reduce radio delay.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import queue
import threading
import urllib.request
from typing import Callable

from .race_state.models import RaceState
from .pit_strategy import assess_pit
from .event_context import build_event_context


@dataclass(frozen=True, slots=True)
class LLMConfig:
    enabled: bool = True
    model: str = "qwen2.5:3b"
    url: str = "http://127.0.0.1:11434/api/chat"
    timeout_s: float = 8.0
    keep_alive: str = "30m"
    num_ctx: int = 2048
    num_predict: int = 48


def _name(v):
    return getattr(v, "name", None) if v is not None else None


def _wheels(w):
    if w is None:
        return None
    return {"FL": w.FL, "FR": w.FR, "RL": w.RL, "RR": w.RR}


def _known_wheel_values(w):
    if w is None:
        return []
    return [v for v in (w.FL, w.FR, w.RL, w.RR) if v is not None]


def build_reasoning_context(state: RaceState) -> dict:
    """Compact verified, event-applicable facts plus deterministic arithmetic."""
    c = state.player
    if c is None:
        return {"live_car_data": False}
    s = state.session
    ctx = build_event_context(state)
    m = ctx.metrics
    wear = _known_wheel_values(c.tyres.wear_percent) if m.tyre_wear_strategy else []
    temps = _known_wheel_values(c.tyres.surface_temperature_c)
    derived = {
        "max_surface_temp_c": max(temps) if temps else None,
        "min_surface_temp_c": min(temps) if temps else None,
        "surface_temp_spread_c": round(max(temps) - min(temps), 1) if temps else None,
    }
    if m.tyre_wear_strategy:
        derived.update(
            max_tyre_wear_percent=max(wear) if wear else None,
            average_tyre_wear_percent=round(sum(wear) / len(wear), 1) if wear else None,
            tyre_wear_spread_percent=round(max(wear) - min(wear), 1) if wear else None,
        )
    if m.ers_energy_strategy and c.energy.store_j is not None:
        # Energy conversion only; no assumed battery maximum.
        derived["ers_store_kj"] = round(c.energy.store_j / 1000.0, 0)

    pit = assess_pit(state)
    race = {
        "lap": c.lap.current_lap, "previous_lap_s": c.lap.previous_lap_time_s,
        "pit_status": _name(c.lap.pit_status), "penalties_s": c.lap.penalties_s,
    }
    if m.race_position_strategy:
        race.update(position=c.lap.position, pit_stops=c.lap.pit_stops)
    if m.traffic_gap_analysis:
        race.update(gap_ahead_s=c.lap.gap_to_car_in_front_s, gap_behind_s=state.gap_behind_s)

    tyres = {
        "compound": _name(c.tyres.visual_compound),
        "surface_temp_c": _wheels(c.tyres.surface_temperature_c),
        "pressure_psi": _wheels(c.tyres.pressure_psi),
    }
    if m.tyre_wear_strategy:
        tyres.update(age_laps=c.tyres.age_laps, wear_percent=_wheels(c.tyres.wear_percent))
    if m.damage_strategy:
        tyres["damage_percent"] = _wheels(c.tyres.damage_percent)

    session = {
        "track": _name(s.track), "type": _name(s.session_type), "weather": _name(s.weather),
        "air_temp_c": s.air_temperature_c, "track_temp_c": s.track_temperature_c,
        "event_profile": ctx.profile, "2026_regulations": ctx.regulations_2026,
    }
    if m.weather_strategy:
        session["forecast"] = [{"offset_min": f.offset_minutes, "weather": _name(f.weather),
                                "rain_percent": f.rain_percent} for f in s.forecast[:2]]
    if m.race_position_strategy:
        session.update(lap_total=s.total_laps, safety_car=_name(s.safety_car))

    out = {
        "live_car_data": True,
        "event_context": ctx.to_dict(),
        "pit_strategy": pit.to_dict(),
        "session": session,
        "race": race,
        "tyres": tyres,
        "aero": {
            "s_mode": _name(c.aero.active_aero_mode) if m.active_aero_analysis else None,
            "s_mode_available": c.aero.active_aero_available if m.active_aero_analysis else None,
            "overtake_available": c.aero.overtake_available if m.overtake_analysis else None,
            "overtake_active": c.aero.overtake_active if m.overtake_analysis else None,
            "drs_allowed": c.aero.drs_allowed if m.legacy_drs_analysis else None,
            "drs_active": c.telemetry.drs if m.legacy_drs_analysis else None,
        },
        "derived_by_python": derived,
    }
    if m.fuel_strategy:
        out["fuel"] = {"remaining_laps": c.fuel.remaining_laps, "remaining_mass": c.fuel.remaining_mass}
    if m.ers_energy_strategy:
        out["ers"] = {"store_j": c.energy.store_j, "deploy_mode": _name(c.energy.deploy_mode)}
    if m.damage_strategy:
        out["damage"] = {
            "front_left_wing_percent": c.damage.front_left_wing_percent,
            "front_right_wing_percent": c.damage.front_right_wing_percent,
            "rear_wing_percent": c.damage.rear_wing_percent, "floor_percent": c.damage.floor_percent,
            "diffuser_percent": c.damage.diffuser_percent, "sidepod_percent": c.damage.sidepod_percent,
            "gearbox_percent": c.damage.gearbox_percent, "engine_percent": c.damage.engine_percent,
            "drs_fault": c.damage.drs_fault, "ers_fault": c.damage.ers_fault,
        }
    return out


SYSTEM_PROMPT = """You are the driver's Formula 1 race engineer on live radio.
Use ONLY the supplied verified telemetry and Python-derived facts. Never invent facts, rules, causes, lap deltas, strategy windows, tyre targets, or missing data.
Answer the driver's exact question immediately. Maximum 22 words, one sentence whenever possible. No lists, introductions, safety disclaimers, or generic road-car advice.
For judgement, state the recommendation first and only one short reason. If the telemetry cannot support a reliable judgement, say so briefly.
Tyre heat advice must stay racing-specific; never tell the driver to stop the car merely because tyre temperatures are high.
For pit questions, use pit_strategy as deterministic evidence. Treat recommendation_hint as a conservative signal, not proof of an optimal stop. Never invent pit loss, traffic after rejoin, tyre degradation rate, or tyre rules. If pit evidence is insufficient, say what key fact is missing instead of guessing."""


class LocalLLMEngineer:
    """Single background worker; warm-up and inference never block telemetry/PTT."""
    def __init__(self, config: LLMConfig, on_response: Callable[[str], None] | None = None, transport=None):
        self.config = config
        self.on_response = on_response
        self._transport = transport
        self._queue: queue.Queue[tuple[str, dict] | None] = queue.Queue(maxsize=2)
        self._stop = threading.Event()
        self._thread = None
        self._warm_thread = None
        self.last_error = None
        self.warmed = False
        if config.enabled:
            self._thread = threading.Thread(target=self._run, name="race-engineer-llm", daemon=True)
            self._thread.start()
            # Do not warm mocked transports: tests/callers may use them as one-shot inference hooks.
            if transport is None:
                self._warm_thread = threading.Thread(target=self._warm_up, name="race-engineer-llm-warmup", daemon=True)
                self._warm_thread.start()

    def set_enabled(self, enabled: bool) -> None:
        """Toggle reasoning at runtime and lazy-start workers on first enable."""
        enabled = bool(enabled)
        self.config = replace(self.config, enabled=enabled)
        if not enabled or self._stop.is_set():
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="race-engineer-llm", daemon=True)
            self._thread.start()
        if not self.warmed and self._transport is None and self._warm_thread is None:
            self._warm_thread = threading.Thread(target=self._warm_up, name="race-engineer-llm-warmup", daemon=True)
            self._warm_thread.start()

    def submit(self, question: str, state: RaceState) -> bool:
        if not self.config.enabled or self._stop.is_set():
            return False
        try:
            self._queue.put_nowait((question, build_reasoning_context(state)))
            return True
        except queue.Full:
            return False

    def close(self, wait=True):
        self._stop.set()
        if self._thread:
            try: self._queue.put_nowait(None)
            except queue.Full: pass
            if wait: self._thread.join(timeout=2.0)
        if wait and self._warm_thread:
            self._warm_thread.join(timeout=.2)

    def _payload(self, question: str, context: dict, *, warmup=False) -> bytes:
        if warmup:
            messages = [{"role": "user", "content": "Ready."}]
            options = {"temperature": 0, "num_ctx": 256, "num_predict": 1}
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Question: " + question + "\nVerified RaceState facts:" + json.dumps(context, separators=(",", ":"))},
            ]
            options = {"temperature": 0.1, "num_ctx": self.config.num_ctx, "num_predict": self.config.num_predict}
        return json.dumps({"model": self.config.model, "stream": False, "keep_alive": self.config.keep_alive,
                           "messages": messages, "options": options}).encode("utf-8")

    def _http(self, payload: bytes) -> str:
        req = urllib.request.Request(self.config.url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.config.timeout_s) as response:
            obj = json.loads(response.read().decode("utf-8"))
        return str(obj.get("message", {}).get("content", "")).strip()

    def _request(self, question: str, context: dict) -> str:
        payload = self._payload(question, context)
        if self._transport is not None:
            return self._transport(payload)
        return self._http(payload)

    def _warm_up(self):
        try:
            print(f"[LLM] Warming {self.config.model} in background...", flush=True)
            self._http(self._payload("", {}, warmup=True))
            self.warmed = True
            print(f"[LLM] {self.config.model} ready (keep-alive {self.config.keep_alive}).", flush=True)
        except Exception as e:
            self.last_error = str(e)
            print(f"[LLM] Warm-up unavailable: {e}", flush=True)

    @staticmethod
    def _radio_trim(answer: str) -> str:
        answer = " ".join(answer.replace("\n", " ").split())
        words = answer.split()
        if len(words) > 28:
            answer = " ".join(words[:28]).rstrip(" ,;:") + "."
        return answer

    def _run(self):
        while not self._stop.is_set():
            item = self._queue.get()
            if item is None:
                break
            question, context = item
            try:
                print(f'[LLM] Reasoning: "{question}"', flush=True)
                answer = self._radio_trim(self._request(question, context))
                if not answer:
                    raise RuntimeError("empty response")
                print(f"[LLM] Engineer: {answer}", flush=True)
            except Exception as e:
                self.last_error = str(e)
                answer = "Reasoning is unavailable right now."
                print(f"[LLM] Unavailable: {e}", flush=True)
            if self.on_response:
                self.on_response(answer)
