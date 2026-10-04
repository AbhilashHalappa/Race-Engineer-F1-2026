"""Deterministic runtime radio controls for Race Engineer + CORNER COACH.

Voice commands route to the same receiver setters used by the UI.  This keeps
button state, persisted coaching settings and spoken controls synchronized.
"""
from __future__ import annotations
from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class RuntimeRadioCommand:
    action: str
    target: str | None = None
    value: str | bool | None = None
    targets: tuple[str, ...] = ()


_CONTROL_ALIASES = {
    # Race Engineer / coaching controls.
    "race engineer": "ENGR", "engineer": "ENGR", "automatic engineer": "ENGR",
    "pre coach": "PRE", "pre coaching": "PRE", "pre corner": "PRE",
    "post coach": "POST", "post coaching": "POST", "post corner": "POST",
    "lap coach": "LAP", "lap code": "LAP", "lap summary": "LAP", "lap coaching": "LAP",
    "positive coach": "POS", "positive calls": "POS", "positive coaching": "POS",
    "race coach": "RACE", "race code": "RACE", "race coaching": "RACE",
    # SPEED COACH hierarchy.
    "performance coach": "SPEED", "performance coaching": "SPEED", "speed coach": "SPEED", "speed coaching": "SPEED", "performance speed coach": "SPEED",
    "straight line coach": "STRAIGHT", "straight coach": "STRAIGHT", "straight coaching": "STRAIGHT",
    "straight line voice": "SLVOICE", "straight voice": "SLVOICE",
    # CORNER COACH controls.
    "corner coach pre": "CCPRE", "corner coach post": "CCPOST",
    "corner coach": "CORNER", "current coach": "CORNER", "carver coach": "CORNER", "cc": "CORNER",
    "corner coach voice": "CCVOICE", "corner voice": "CCVOICE", "cc voice": "CCVOICE",
    "corner pre": "CCPRE", "cc pre": "CCPRE",
    "corner post": "CCPOST", "cc post": "CCPOST",
    "map gain loss": "GAINLOSS", "gain loss map": "GAINLOSS", "gain loss": "GAINLOSS",
    "gain loss voice": "GAINLOSSVOICE", "gain loss wife": "GAINLOSSVOICE", "g l voice": "GAINLOSSVOICE",
    "corner gain loss voice": "GAINLOSSVOICE", "corner g l voice": "GAINLOSSVOICE", "corner gl voice": "GAINLOSSVOICE",
    "corner gain loss wife": "GAINLOSSVOICE", "corner g l wife": "GAINLOSSVOICE", "corner gl wife": "GAINLOSSVOICE",
    "damage coach": "DMGCOACH", "damage coaching": "DMGCOACH",
    # Radio/control-center infrastructure.
    "tts": "TTS", "speech": "TTS", "voice output": "TTS",
    "ptt": "PTT", "push to talk": "PTT",
    "stt": "STT", "speech recognition": "STT", "voice recognition": "STT",
    "llm": "LLM", "ai reasoning": "LLM",
    "recording": "REC", "telemetry recording": "REC", "recorder": "REC",
}

_MODES = {
    "auto": "auto", "automatic": "auto",
    "race engineer": "race_engineer",
    "performance coach": "performance_coach", "coach": "performance_coach",
    "track learning": "track_learning", "track learn": "track_learning",
    "qualifying": "qualifying", "qualifying mode": "qualifying",
    "time trial": "time_trial", "time trial mode": "time_trial",
    "silent analysis": "silent_analysis", "silent": "silent_analysis",
}

_VERBOSITY = {
    "minimal": "minimal", "short": "minimal", "brief": "minimal",
    "normal": "normal", "standard": "normal",
    "detailed": "detailed", "detail": "detailed", "verbose": "detailed",
}

_SPEEDS = {
    "slow": "slow", "slower": "slow", "low": "slow",
    "normal": "normal", "default": "normal",
    "fast": "fast", "faster": "fast",
}


def _plain(text: str) -> str:
    text = re.sub(r"[^a-z0-9/ +.-]+", " ", str(text or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _resolve_alias(text: str) -> str | None:
    # Longest alias first prevents "gain loss" from stealing "gain loss voice".
    for alias, target in sorted(_CONTROL_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return target
    return None


def parse_runtime_radio_command(text: str) -> RuntimeRadioCommand | None:
    t = _plain(text)
    if not t:
        return None

    # Help/status requests first so words like "enable" inside docs never matter.
    if any(p in t for p in ("radio control help", "control commands", "voice control help", "what can i control", "list controls",
                              "help for buttons", "button help", "buttons help", "radio commands", "radio command", "radio comment")):
        return RuntimeRadioCommand("HELP")
    if any(p in t for p in ("control status", "radio control status", "coach control status", "what is enabled")):
        return RuntimeRadioCommand("STATUS")

    if any(p in t for p in ("coaching mode", "coach mode", "set mode", "switch mode", "change mode")):
        for phrase, mode in sorted(_MODES.items(), key=lambda kv: -len(kv[0])):
            if phrase in t:
                return RuntimeRadioCommand("MODE", value=mode)
        return RuntimeRadioCommand("MODE_STATUS")

    if any(p in t for p in ("verbosity", "radio detail", "coach detail", "response detail")):
        for phrase, value in _VERBOSITY.items():
            if phrase in t:
                return RuntimeRadioCommand("VERBOSITY", value=value)
        return RuntimeRadioCommand("VERBOSITY_STATUS")

    if any(p in t for p in ("voice speed", "speech speed", "talk speed")):
        for phrase, value in _SPEEDS.items():
            if phrase in t:
                return RuntimeRadioCommand("VOICE_SPEED", value=value)
        return RuntimeRadioCommand("VOICE_SPEED_STATUS")

    if any(p in t for p in ("next voice", "change voice", "switch voice", "alternate voice")):
        return RuntimeRadioCommand("NEXT_VOICE")
    m = re.search(r"(?:use|select|set) voice (.+)$", t)
    if m:
        return RuntimeRadioCommand("VOICE_SELECT", value=m.group(1).strip())
    if any(p in t for p in ("which voice", "voice model", "current voice")):
        return RuntimeRadioCommand("VOICE_STATUS")

    # Combined CORNER COACH PRE + POST commands are intentionally handled
    # before single-target alias resolution so neither side is lost.
    has_corner = "corner" in t or "cc" in t
    has_pre = bool(re.search(r"\bpre\b", t))
    has_post = bool(re.search(r"\bpost\b", t))
    if has_corner and has_pre and has_post:
        enable = bool(re.search(r"\b(enable|enabled|on|start|activate|unmute|resume)\b", t))
        disable = bool(re.search(r"\b(disable|disabled|off|stop|deactivate|mute|pause)\b", t))
        if enable ^ disable:
            return RuntimeRadioCommand("CONTROL_MULTI_SET", value=enable, targets=("CCPRE", "CCPOST"))

    target = _resolve_alias(t)
    if target is None:
        return None

    if (any(p in t for p in ("status", "state", "is on", "is off", "is enabled", "is disabled", "check"))
            or re.search(r"\bis\b.*\b(enabled|disabled|on|off)\b", t)):
        return RuntimeRadioCommand("CONTROL_STATUS", target=target)

    enable = bool(re.search(r"\b(enable|enabled|on|start|activate|unmute|resume)\b", t))
    disable = bool(re.search(r"\b(disable|disabled|off|stop|deactivate|mute|pause)\b", t))
    if enable and not disable:
        return RuntimeRadioCommand("CONTROL_SET", target=target, value=True)
    if disable and not enable:
        return RuntimeRadioCommand("CONTROL_SET", target=target, value=False)
    if any(p in t for p in ("toggle", "switch")):
        return RuntimeRadioCommand("CONTROL_TOGGLE", target=target)
    return RuntimeRadioCommand("CONTROL_STATUS", target=target)


CONTROL_LABELS = {
    "ENGR":"Race Engineer", "PRE":"PRE coach", "POST":"POST coach", "LAP":"lap summary",
    "POS":"positive coaching", "RACE":"race coaching", "SPEED":"Performance Coach", "CORNER":"CORNER COACH", "STRAIGHT":"STRAIGHT LINE COACH",
    "CCVOICE":"Performance Coach voice", "CCPRE":"CORNER COACH PRE", "CCPOST":"CORNER COACH POST", "SLVOICE":"STRAIGHT LINE COACH voice",
    "GAINLOSS":"map gain/loss", "GAINLOSSVOICE":"gain/loss voice", "DMGCOACH":"damage coaching",
    "TTS":"speech output", "PTT":"push to talk", "STT":"speech recognition", "LLM":"AI reasoning",
    "REC":"recording",
}
