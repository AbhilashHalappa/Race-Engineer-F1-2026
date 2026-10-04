"""V0.7 deterministic radio intent parsing and RaceState answers."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from dataclasses import dataclass
from enum import Enum
from .race_state.models import RaceState, Wheels
from .event_context import build_event_context


class VoiceIntent(str, Enum):
    TYRE_STATUS = "TYRE_STATUS"
    TYRE_WEAR = "TYRE_WEAR"
    TYRE_TEMPERATURE = "TYRE_TEMPERATURE"
    TYRE_TEMPERATURE_DETAIL = "TYRE_TEMPERATURE_DETAIL"
    FUEL_STATUS = "FUEL_STATUS"
    ERS_STATUS = "ERS_STATUS"
    POSITION = "POSITION"
    GAP_AHEAD = "GAP_AHEAD"
    GAP_BEHIND = "GAP_BEHIND"
    LAP_TIME = "LAP_TIME"
    DAMAGE = "DAMAGE"
    PENALTIES = "PENALTIES"
    WEATHER = "WEATHER"
    PIT_STATUS = "PIT_STATUS"
    PIT_RECOMMENDATION = "PIT_RECOMMENDATION"
    TYRE_SELECTION = "TYRE_SELECTION"
    WING_SERVICE = "WING_SERVICE"
    RACE_CONTROL = "RACE_CONTROL"
    STATUS = "STATUS"
    MATH_STATUS = "MATH_STATUS"
    BRAKE_STATUS = "BRAKE_STATUS"
    BRAKE_TEMPERATURE = "BRAKE_TEMPERATURE"
    BRAKE_TEMPERATURE_DETAIL = "BRAKE_TEMPERATURE_DETAIL"
    BRAKE_DAMAGE = "BRAKE_DAMAGE"
    TYRE_PRESSURE = "TYRE_PRESSURE"
    BRAKE_BIAS = "BRAKE_BIAS"
    SETUP = "SETUP"
    WHEEL_SLIP = "WHEEL_SLIP"
    G_FORCE = "G_FORCE"
    BEST_LAP = "BEST_LAP"
    LAPS_REMAINING = "LAPS_REMAINING"
    LAP_COMPARISON = "LAP_COMPARISON"
    FUEL_USED = "FUEL_USED"
    POSITION_CHANGE = "POSITION_CHANGE"
    FACTS = "FACTS"
    PERFORMANCE_COMPARE = "PERFORMANCE_COMPARE"
    BRAKING_COMPARE = "BRAKING_COMPARE"
    TRACTION_COMPARE = "TRACTION_COMPARE"
    DRIVING_ISSUES = "DRIVING_ISSUES"
    REFERENCE_SET = "REFERENCE_SET"
    REFERENCE_PREVIOUS = "REFERENCE_PREVIOUS"
    REFERENCE_BEST = "REFERENCE_BEST"
    ENGINE_STATUS = "ENGINE_STATUS"
    ENGINE_TEMPERATURE = "ENGINE_TEMPERATURE"
    ENGINE_WEAR = "ENGINE_WEAR"
    GEARBOX_STATUS = "GEARBOX_STATUS"
    CURRENT_LAP = "CURRENT_LAP"
    LAPS_COMPLETED = "LAPS_COMPLETED"
    CURRENT_SECTOR = "CURRENT_SECTOR"
    SESSION_TIME = "SESSION_TIME"
    GAP_LEADER = "GAP_LEADER"
    DRIVER_AHEAD = "DRIVER_AHEAD"
    DRIVER_BEHIND = "DRIVER_BEHIND"
    TYRE_COMPOUND = "TYRE_COMPOUND"
    TYRE_AGE = "TYRE_AGE"
    TYRE_SET = "TYRE_SET"
    DRS_STATUS = "DRS_STATUS"
    S_MODE_STATUS = "S_MODE_STATUS"
    OVERTAKE_STATUS = "OVERTAKE_STATUS"
    PIT_SPEED_LIMIT = "PIT_SPEED_LIMIT"
    PIT_STOPS = "PIT_STOPS"
    TRACK_TEMPERATURE = "TRACK_TEMPERATURE"
    AIR_TEMPERATURE = "AIR_TEMPERATURE"
    RAIN_CHANCE = "RAIN_CHANCE"
    SPEED = "SPEED"
    RPM = "RPM"
    GEAR = "GEAR"
    FUEL_MIX = "FUEL_MIX"
    ERS_HARVEST = "ERS_HARVEST"
    GRID_POSITION = "GRID_POSITION"
    TRACK_LIMITS = "TRACK_LIMITS"
    SECTOR_TIMES = "SECTOR_TIMES"
    LAP_VALIDITY = "LAP_VALIDITY"
    TYRE_DAMAGE = "TYRE_DAMAGE"
    TYRE_BLISTERS = "TYRE_BLISTERS"
    PUNCTURE_STATUS = "PUNCTURE_STATUS"
    WING_STATUS = "WING_STATUS"
    FLOOR_STATUS = "FLOOR_STATUS"
    FAULT_STATUS = "FAULT_STATUS"
    DIFFERENTIAL = "DIFFERENTIAL"
    BRAKE_PRESSURE = "BRAKE_PRESSURE"
    ENGINE_BRAKING = "ENGINE_BRAKING"
    WING_SETTING = "WING_SETTING"
    RADIO_HELP = "RADIO_HELP"
    SESSION_SUMMARY = "SESSION_SUMMARY"
    STRATEGY_STATUS = "STRATEGY_STATUS"
    TYRE_LIFE = "TYRE_LIFE"
    FUEL_TO_FINISH = "FUEL_TO_FINISH"
    GAP_TREND = "GAP_TREND"
    STINT_COMPARE = "STINT_COMPARE"
    REJOIN_TRAFFIC = "REJOIN_TRAFFIC"
    UNDERCUT = "UNDERCUT"
    SAFETY_CAR_PIT = "SAFETY_CAR_PIT"
    COMPLEX_REASONING = "COMPLEX_REASONING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class VoiceResult:
    intent: VoiceIntent
    response: str


# Canonical radio phrases used only for conservative STT recovery.  These are
# deliberately short and factual; ambiguous free-form speech is never rewritten.
_CANONICAL_RADIO_PHRASES = (
    "gap ahead", "gap behind", "weather", "weather information", "damage report",
    "brake information", "brake temperature", "tyre information", "tyre wear",
    "tyre temperature", "fuel status", "ers status", "should i box",
    "which tyres should i use", "position information", "laps remaining",
    "laps completed", "current lap", "current sector", "engine status",
    "engine temperature", "engine wear", "gearbox status", "gap to leader",
    "driver ahead", "driver behind", "tyre compound", "tyre age", "tyre set",
    "drs status", "s mode status", "overtake status", "pit speed limit",
    "pit stops", "track temperature", "air temperature", "rain chance",
    "speed", "rpm", "gear", "fuel mix", "ers harvest", "grid position",
    "track limits", "penalties", "race control", "best lap", "lap time",
    "sector times", "lap valid", "tyre damage", "tyre blisters", "puncture status",
    "wing status", "floor status", "fault status", "differential", "brake pressure",
    "engine braking", "wing setting", "radio commands", "session summary", "race result",
    "strategy update", "can i make these tyres last", "fuel to finish", "fuel margin",
    "gap trend", "stint comparison", "compare stint pace", "rejoin traffic", "come out in traffic",
    "can i undercut", "safety car pit",
    "which corner should i work on", "what should i focus on next lap",
    "what is my biggest mistake", "what is my potential lap", "how consistent am i",
    "where am i losing time", "where did i gain time", "where did i lose time this lap",
    "how is my braking", "how is my throttle application",
    "compare this lap with reference", "am i braking too early",
    "speed coach status", "enable speed coach", "disable speed coach",
    "corner coach status", "enable corner coach", "disable corner coach",
    "straight line coach status", "enable straight line coach", "disable straight line coach",
)


def _plain(text: str) -> str:
    t = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower()).strip()
    return re.sub(r"\s+", " ", t)




_STT_HALLUCINATION_PHRASES = (
    "thank you for watching",
    "thanks for watching",
    "see you in the next video",
    "thank you for your attention",
    "subtitles by",
    "please subscribe",
    # Real PTT logs: conversational filler/noise should not produce an
    # "unsupported radio request" response and steal airtime from coaching.
    "thank you very much",
    "bye bye",
    "can i ask you a question",
)

def is_likely_stt_hallucination(text: str) -> bool:
    """Reject common Whisper silence/noise hallucinations seen in real PTT logs."""
    plain = _plain(text)
    if not plain:
        return False
    return any(p in plain for p in _STT_HALLUCINATION_PHRASES)


def _collapse_repeated_phrase(text: str) -> str:
    """Collapse Whisper loops such as 'brake temperature' repeated 50 times."""
    words = text.split()
    if len(words) < 6:
        return text
    # Exact periodic repetition is the common faster-whisper failure mode.
    for width in range(1, min(8, len(words) // 3) + 1):
        pattern = words[:width]
        repeats = 0
        pos = 0
        while pos + width <= len(words) and words[pos:pos + width] == pattern:
            repeats += 1
            pos += width
        if repeats >= 3 and pos >= len(words) - width:
            return " ".join(pattern)
    # Also cap identical consecutive n-grams inside a longer utterance.
    out = []
    i = 0
    while i < len(words):
        collapsed = False
        for width in range(min(6, (len(words)-i)//3), 0, -1):
            chunk = words[i:i+width]
            if words[i+width:i+2*width] == chunk and words[i+2*width:i+3*width] == chunk:
                out.extend(chunk)
                i += width
                while i + width <= len(words) and words[i:i+width] == chunk:
                    i += width
                collapsed = True
                break
        if not collapsed:
            out.append(words[i]); i += 1
    return " ".join(out)


def normalize_radio_text(text: str) -> str:
    """Clean an STT transcript without inventing race information.

    The resolver fixes only high-confidence, known race-radio near misses.  It is
    intentionally conservative so an arbitrary sentence cannot become a command.
    """
    original = " ".join(str(text or "").split()).strip()
    if not original:
        return ""
    if is_likely_stt_hallucination(original):
        return ""
    plain = _collapse_repeated_phrase(_plain(original))
    if not plain:
        return ""

    # Known Whisper substitutions observed in real PTT testing.
    exact = {
        "lap behind": "gap behind",
        "lap ahead": "gap ahead",
        "lap remaining": "laps remaining",
        "remaining lap": "laps remaining",
        "remaining laps": "laps remaining",
        "lap completed": "laps completed",
        "style should i use": "which tyres should i use",
        "which tire should i use": "which tyres should i use",
        "which tyre should i use": "which tyres should i use",
        "tire information": "tyre information",
        "tire wear": "tyre wear",
        "tire temperature": "tyre temperature",
        "ahead driver": "driver ahead",
        "behind driver": "driver behind",
        "will i come out in the traffic": "will i come out in traffic",
        "come out in the traffic": "come out in traffic",
        "compare shift paste": "compare stint pace",
        "compare shift pace": "compare stint pace",
        "compare stint place": "compare stint pace",
        "compassioned place": "compare stint pace",
        "compassionate place": "compare stint pace",
        # Observed V1.8 Windows PTT mis-hearings from the user's real radio log.
        # These are exact-only corrections so unrelated free speech is untouched.
        "table corner coach": "disable corner coach",
        "former coach status": "corner coach status",
        "corner put status": "corner coach status",
        "partner coach status": "corner coach status",
        "straight line code status": "straight line coach status",
        "eco status": "ers status",
        # V2.0.6.5: exact high-confidence PTT near-misses observed in the
        # user's UI 1.8.1 command-validation transcript. Keep these exact-only
        # so free speech cannot accidentally toggle runtime controls.
        "pre coat": "pre coach",
        "pre cut": "pre coach",
        "pre code": "pre coach",
        "enable pre coat": "enable pre coach",
        "enable pre cut": "enable pre coach",
        "enable pre code": "enable pre coach",
        "disable pre coat": "disable pre coach",
        "disable pre cut": "disable pre coach",
        "disable pre code": "disable pre coach",
        "performance good": "performance coach",
        "enable performance good": "enable performance coach",
        "disable performance good": "disable performance coach",
        "straight line good": "straight line coach",
        "enable straight line good": "enable straight line coach",
        "disable straight line good": "disable straight line coach",
        "enable driitline voice": "enable straight line voice",
        "driitline voice": "straight line voice",
        "gain loss wise": "gain loss voice",
        "enable gain loss wise": "enable gain loss voice",
        "disable gain loss wise": "disable gain loss voice",
        "vise control help": "voice control help",
        "vice control help": "voice control help",
        "set y speed normal": "set voice speed normal",
        "set y speed fast": "set voice speed fast",
        "set y speed low": "set voice speed slow",
        "set voice speed low": "set voice speed slow",
        "compare it previous": "compare with previous",
    }
    if plain in exact:
        return exact[plain]

    # Only fuzzy-correct short utterances that already look command-like.  A high
    # threshold avoids mapping normal conversation/hallucinations to telemetry calls.
    if len(plain.split()) <= 6:
        best = None
        best_ratio = 0.0
        for candidate in _CANONICAL_RADIO_PHRASES:
            ratio = SequenceMatcher(None, plain, candidate).ratio()
            if ratio > best_ratio:
                best, best_ratio = candidate, ratio
        if best is not None and best_ratio >= 0.88:
            return best

    return plain


def parse_intent(text: str) -> VoiceIntent:
    """Map natural/offline radio speech to a deterministic intent.

    The parser deliberately accepts short race-radio fragments ("brake info",
    "fuel?", "tyres", "gap front") as well as full questions.  It does not
    need an LLM and never routes an unknown factual phrase to reasoning.
    """
    t = normalize_radio_text(text)
    if not t:
        return VoiceIntent.UNKNOWN

    # Common STT homophones.  Only normalize in brake context so ordinary
    # uses of "break" elsewhere are not reinterpreted.
    if re.search(r"\bbreak(s|ing)?\b", t):
        t = re.sub(r"\bbreaks\b", "brakes", t)
        t = re.sub(r"\bbreak\b", "brake", t)

    def has(*phrases: str) -> bool:
        return any(p in t for p in phrases)

    if has("session summary", "race summary", "race result", "final result", "session result"):
        return VoiceIntent.SESSION_SUMMARY
    if has("radio commands", "what can i ask", "what can i say", "help radio", "radio help"):
        return VoiceIntent.RADIO_HELP

    # V0.9.16.0 deterministic strategy questions. Put these before generic tyre,
    # fuel, gap and race-control parsing so the specific strategy intent wins.
    if has("strategy update", "strategy status", "race strategy update", "how is the strategy", "can i make it to the end", "can i make the end", "can we make it to the end"):
        return VoiceIntent.STRATEGY_STATUS
    if has("can i make these tyres last", "will these tyres last", "tyres make the end",
           "tires make the end", "tyres to the end", "tire life projection"):
        return VoiceIntent.TYRE_LIFE
    if has("fuel to finish", "fuel margin", "fuel to the end", "make it to the end on fuel",
           "enough fuel to finish", "how much fuel margin"):
        return VoiceIntent.FUEL_TO_FINISH
    if has("gap trend", "am i catching", "am i closing", "is the gap closing", "is the gap opening"):
        return VoiceIntent.GAP_TREND
    if has("stint compare", "stint comparison", "compare stint", "compare stint pace", "stint pace", "current stint pace", "previous stint pace"):
        return VoiceIntent.STINT_COMPARE
    if has("rejoin traffic", "come out in traffic", "come out in the traffic", "where will i rejoin", "rejoin position", "pit exit traffic"):
        return VoiceIntent.REJOIN_TRAFFIC
    if has("undercut", "under cut", "can i undercut", "is the undercut working"):
        return VoiceIntent.UNDERCUT
    if (has("safety car", "virtual safety", "vsc") and
            has("pit", "box", "stop", "good time", "opportunity")):
        return VoiceIntent.SAFETY_CAR_PIT

    # Measured-performance reference controls and diagnostics.
    if has("use this lap as reference", "set this lap as reference", "save this lap as reference"):
        return VoiceIntent.REFERENCE_SET
    if has("compare with previous", "use previous lap", "previous lap reference"):
        return VoiceIntent.REFERENCE_PREVIOUS
    if has("use best lap", "best lap reference", "compare with best"):
        return VoiceIntent.REFERENCE_BEST
    if has("driving issues", "driving issue", "overlap info", "coasting info", "consistency issues"):
        return VoiceIntent.DRIVING_ISSUES

    # Directional facts before broad status words.
    if has("where am i losing", "where i am losing", "where did i lose", "where did i gain", "performance compare", "compare performance", "compare with best", "measured performance"):
        return VoiceIntent.PERFORMANCE_COMPARE
    if has("braking compare", "compare braking", "braking info", "brake point", "braking point"):
        return VoiceIntent.BRAKING_COMPARE
    if has("traction compare", "compare traction", "traction info", "throttle compare", "corner exit"):
        return VoiceIntent.TRACTION_COMPARE
    if has("gap ahead", "gap front", "car ahead", "car in front", "ahead gap", "front gap"):
        return VoiceIntent.GAP_AHEAD
    if has("gap behind", "gap back", "car behind", "behind gap", "rear gap", "gap rear"):
        return VoiceIntent.GAP_BEHIND
    if has("gap to leader", "leader gap", "gap leader", "how far to leader"):
        return VoiceIntent.GAP_LEADER
    if has("driver ahead", "who is ahead", "who is in front", "car name ahead"):
        return VoiceIntent.DRIVER_AHEAD
    if has("driver behind", "who is behind", "car name behind"):
        return VoiceIntent.DRIVER_BEHIND

    # Setup/condition-specific wing requests before pit service logic.
    if has("wing setting", "front wing setting", "rear wing setting", "wing settings"):
        return VoiceIntent.WING_SETTING
    if has("wing status", "wing condition", "front wing status", "rear wing status"):
        return VoiceIntent.WING_STATUS
    if has("floor status", "floor damage", "floor condition"):
        return VoiceIntent.FLOOR_STATUS
    if has("fault status", "car faults", "system faults", "drs fault", "ers fault"):
        return VoiceIntent.FAULT_STATUS

    # Service-plan specifics before broad pit strategy.
    if re.search(r"\b(tyre|tyres|tire|tires|compound|set)\b", t) and has("what tyre", "which tyre", "what compound", "which compound", "tyre for pit", "tires for pit", "pit tyre", "pit tire", "which set", "what set"):
        return VoiceIntent.TYRE_SELECTION
    if re.search(r"\b(wing|wings|front wing)\b", t) and has("pit", "box", "change", "adjust", "repair", "replace", "setting"):
        return VoiceIntent.WING_SERVICE

    # Pit strategy must precede generic pit status.
    pit_word = (re.search(r"\b(pit|pits|pitting|pitstop|box|boxing)\b", t) is not None
                or has("come in", "make a stop", "stop this lap"))
    pit_decision = pit_word and (
        has("can i", "can we", "should i", "should we", "do i", "do we", "need to",
            "time to", "good time", "this lap", "next lap", "now", "stay out",
            "when", "why", "recommend", "strategy", "window", "what about", "how about")
        or t in {"pit", "box", "boxing", "pitting"}
    )
    if pit_decision:
        return VoiceIntent.PIT_RECOMMENDATION

    # Power-unit / gearbox status.
    if re.search(r"\bengine\b", t):
        if has("temp", "temperature", "heat"):
            return VoiceIntent.ENGINE_TEMPERATURE
        if has("wear", "damage", "components", "component"):
            return VoiceIntent.ENGINE_WEAR
        return VoiceIntent.ENGINE_STATUS
    if has("gearbox", "transmission"):
        return VoiceIntent.GEARBOX_STATUS

    # 2026/legacy overtaking systems.
    if re.search(r"\bdrs\b", t):
        return VoiceIntent.DRS_STATUS
    if has("s mode", "smode", "active aero"):
        return VoiceIntent.S_MODE_STATUS
    if has("overtake mode", "overtake status", "overtake available"):
        return VoiceIntent.OVERTAKE_STATUS

    # Brakes: broad info/status is distinct from exact temperature/damage.
    if re.search(r"\bbrake(s|ing)?\b", t):
        if has("bias", "balance"):
            return VoiceIntent.BRAKE_BIAS
        if has("damage", "wear"):
            return VoiceIntent.BRAKE_DAMAGE
        if has("temp", "temperature", "temperatures", "temps", "heat"):
            if has("more info", "more detail", "details", "detailed", "all four", "exact", "numbers", "values"):
                return VoiceIntent.BRAKE_TEMPERATURE_DETAIL
            return VoiceIntent.BRAKE_TEMPERATURE
        if has("info", "status", "condition", "check", "how are", "how s", "okay", "ok", "good") or t in {"brake", "brakes"}:
            return VoiceIntent.BRAKE_STATUS

    # Tyres: specific measurement beats generic tyre status.
    if re.search(r"\b(tyre|tyres|tire|tires)\b", t):
        if has("pressure", "pressures", "psi"):
            return VoiceIntent.TYRE_PRESSURE
        if has("damage", "damaged"):
            return VoiceIntent.TYRE_DAMAGE
        if has("blister", "blisters", "blistering"):
            return VoiceIntent.TYRE_BLISTERS
        if has("puncture", "punctured", "flat"):
            return VoiceIntent.PUNCTURE_STATUS
        if has("wear", "worn", "life", "remaining life", "left on"):
            return VoiceIntent.TYRE_WEAR
        temp_words = has("temperature", "temperatures", "temp", "temps")
        if temp_words:
            if has("more info", "more detail", "details", "detailed", "all four", "exact", "numbers", "values"):
                return VoiceIntent.TYRE_TEMPERATURE_DETAIL
            return VoiceIntent.TYRE_TEMPERATURE
        if has("compound", "what compound", "current compound"):
            return VoiceIntent.TYRE_COMPOUND
        if has("age", "stint age", "how old"):
            return VoiceIntent.TYRE_AGE
        if has("set", "set number", "fitted set"):
            return VoiceIntent.TYRE_SET
        return VoiceIntent.TYRE_STATUS

    if has("fuel used", "fuel usage", "fuel consumption", "used last lap"):
        return VoiceIntent.FUEL_USED
    if has("fuel mix", "engine mix", "mixture"):
        return VoiceIntent.FUEL_MIX
    if has("fuel", "petrol", "fuel info", "fuel left", "fuel remaining"):
        return VoiceIntent.FUEL_STATUS
    if has("ers harvest", "energy harvest", "harvest status", "harvesting"):
        return VoiceIntent.ERS_HARVEST
    if re.search(r"\bers\b", t) or has("energy", "battery", "deployment", "deploy mode"):
        return VoiceIntent.ERS_STATUS
    if has("grid position", "starting position", "start position"):
        return VoiceIntent.GRID_POSITION
    if has("positions gained", "positions lost", "position change", "places gained", "places lost"):
        return VoiceIntent.POSITION_CHANGE
    if has("position", "what place", "where am i", "race position", "my place") or t in {"pos", "position"}:
        return VoiceIntent.POSITION
    if has("current lap", "what lap", "which lap", "lap number"):
        return VoiceIntent.CURRENT_LAP
    if has("laps completed", "lap completed", "completed laps", "how many completed"):
        return VoiceIntent.LAPS_COMPLETED
    if has("sector times", "sector time", "sector one time", "sector two time", "s1 time", "s2 time"):
        return VoiceIntent.SECTOR_TIMES
    if has("current sector", "what sector", "which sector", "sector number") or t == "sector":
        return VoiceIntent.CURRENT_SECTOR
    if has("lap valid", "lap validity", "is lap valid", "valid lap"):
        return VoiceIntent.LAP_VALIDITY
    if has("session time", "time remaining", "session remaining", "time left"):
        return VoiceIntent.SESSION_TIME
    if has("compare lap", "lap comparison", "last lap compared", "lap difference", "lap delta"):
        return VoiceIntent.LAP_COMPARISON
    if has("all facts", "factual summary", "fact summary", "full telemetry facts"):
        return VoiceIntent.FACTS
    if has("lap time", "last lap", "previous lap", "lap info", "lap status"):
        return VoiceIntent.LAP_TIME
    if has("best lap", "session best", "personal best", "pb", "fastest lap"):
        return VoiceIntent.BEST_LAP
    if has("laps remaining", "lap remaining", "remaining laps", "remaining lap", "laps left", "lap left", "how many laps", "race distance left", "how many laps left", "how many laps remaining"):
        return VoiceIntent.LAPS_REMAINING
    if has("damage", "wing", "car condition", "car damage", "damage info"):
        return VoiceIntent.DAMAGE
    if has("track limits", "corner cutting", "track limit warnings"):
        return VoiceIntent.TRACK_LIMITS
    if has("penalty", "penalties", "warning", "warnings"):
        return VoiceIntent.PENALTIES
    if has("track temperature", "track temp"):
        return VoiceIntent.TRACK_TEMPERATURE
    if has("air temperature", "air temp", "ambient temperature"):
        return VoiceIntent.AIR_TEMPERATURE
    if has("rain chance", "chance of rain", "rain percent", "rain percentage"):
        return VoiceIntent.RAIN_CHANCE
    if has("weather", "rain", "forecast", "weather info", "rain info"):
        return VoiceIntent.WEATHER
    if has("pit speed", "pit speed limit", "speed limit"):
        return VoiceIntent.PIT_SPEED_LIMIT
    if has("pit stops", "stops completed", "how many stops"):
        return VoiceIntent.PIT_STOPS
    if has("pit status", "pit stop", "pit lane", "am i pitting", "pit info"):
        return VoiceIntent.PIT_STATUS
    if has("flag", "flags", "safety car", "virtual safety", "vsc", "race control"):
        return VoiceIntent.RACE_CONTROL
    if has("differential", "diff setting", "diff settings", "on throttle diff", "off throttle diff"):
        return VoiceIntent.DIFFERENTIAL
    if has("brake pressure"):
        return VoiceIntent.BRAKE_PRESSURE
    if has("engine braking", "engine brake setting"):
        return VoiceIntent.ENGINE_BRAKING
    if has("car setup", "my setup", "setup settings", "setup info") or t == "setup":
        return VoiceIntent.SETUP
    if has("wheel slip", "tyre slip", "tire slip", "slip info", "traction slip"):
        return VoiceIntent.WHEEL_SLIP
    if has("g force", "g forces", "lateral g", "longitudinal g", "g info"):
        return VoiceIntent.G_FORCE
    if t in {"speed", "current speed", "car speed"} or has("what speed", "how fast"):
        return VoiceIntent.SPEED
    if t in {"rpm", "engine rpm", "revs"} or has("what rpm", "current rpm"):
        return VoiceIntent.RPM
    if t in {"gear", "current gear"} or has("what gear", "which gear"):
        return VoiceIntent.GEAR
    if has("math status", "telemetry summary", "data summary", "telemetry info", "car data"):
        return VoiceIntent.MATH_STATUS
    if re.search(r"\b(status|update)\b", t) or has("race update", "how am i doing", "race status"):
        return VoiceIntent.STATUS

    # LLM routing remains deliberately narrow.
    reasoning_phrases = ("why am i", "why is", "why are", "what should i", "should i",
                         "best strategy", "race strategy", "strategy from", "recommend",
                         "what do you recommend", "how can i improve", "where am i losing",
                         "why am i losing", "push or save", "save tyres", "save tires")
    if any(x in t for x in reasoning_phrases):
        return VoiceIntent.COMPLEX_REASONING
    return VoiceIntent.UNKNOWN


def _enum_name(value) -> str | None:
    return getattr(value, "name", None) if value is not None else None


def _wheels(w: Wheels | None, unit: str = "percent") -> str | None:
    if w is None or any(v is None for v in (w.FL, w.FR, w.RL, w.RR)):
        return None
    return f"front left {w.FL:g} {unit}, front right {w.FR:g}, rear left {w.RL:g}, rear right {w.RR:g}"


def _lap_time(seconds: float | None) -> str | None:
    if seconds is None or seconds <= 0:
        return None
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    return f"{minutes} minute {rest:.3f} seconds" if minutes else f"{rest:.3f} seconds"


def _driver_label(state: RaceState, index: int | None) -> str | None:
    if index is None or index == 255:
        return None
    car = state.field.get(index)
    if car is None:
        return None
    name = getattr(car.identity, "name", None)
    if name:
        return str(name).strip().upper()
    return f"car {index}"


def _wheel_values(w: Wheels | None) -> list[float]:
    if w is None:
        return []
    return [float(v) for v in (w.FL, w.FR, w.RL, w.RR) if v is not None]


def answer_intent(intent: VoiceIntent, state: RaceState) -> str:
    car = state.player
    if intent == VoiceIntent.UNKNOWN:
        return "I don't support that radio request yet."
    if intent == VoiceIntent.COMPLEX_REASONING:
        return "Reasoning request."  # handled asynchronously by LocalLLMEngineer
    if intent == VoiceIntent.RADIO_HELP:
        return 'Ask about tyres, brakes, fuel, ERS, engine, gaps, laps, weather, damage, penalties, race control, pit strategy, tyre life, fuel margin, gap trend, stint pace, or the session summary. Say voice control help for button and coach controls.'
    if intent == VoiceIntent.SESSION_SUMMARY:
        summary=state.extended.get('session_summary')
        return summary.get('spoken_summary','Session summary unavailable.') if isinstance(summary,dict) else 'Session summary unavailable.'
    if intent in (VoiceIntent.STRATEGY_STATUS, VoiceIntent.TYRE_LIFE, VoiceIntent.FUEL_TO_FINISH,
                  VoiceIntent.GAP_TREND, VoiceIntent.STINT_COMPARE, VoiceIntent.REJOIN_TRAFFIC,
                  VoiceIntent.UNDERCUT, VoiceIntent.SAFETY_CAR_PIT):
        from .strategy_engine import (format_strategy_summary, format_tyre_life,
            format_fuel_to_finish, format_gap_trend, format_stint_compare)
        from .strategy_expansion import (format_rejoin_projection, format_undercut_projection,
            format_neutralisation_strategy)
        fn = {
            VoiceIntent.STRATEGY_STATUS: format_strategy_summary,
            VoiceIntent.TYRE_LIFE: format_tyre_life,
            VoiceIntent.FUEL_TO_FINISH: format_fuel_to_finish,
            VoiceIntent.GAP_TREND: format_gap_trend,
            VoiceIntent.STINT_COMPARE: format_stint_compare,
            VoiceIntent.REJOIN_TRAFFIC: format_rejoin_projection,
            VoiceIntent.UNDERCUT: format_undercut_projection,
            VoiceIntent.SAFETY_CAR_PIT: format_neutralisation_strategy,
        }[intent]
        return fn(state)
    if car is None:
        return "Live car data is unavailable."

    ctx = build_event_context(state)
    metrics = ctx.metrics

    if intent in (VoiceIntent.PERFORMANCE_COMPARE, VoiceIntent.BRAKING_COMPARE, VoiceIntent.TRACTION_COMPARE, VoiceIntent.DRIVING_ISSUES):
        from .measured_performance import radio_summary
        topic = {VoiceIntent.BRAKING_COMPARE:'braking', VoiceIntent.TRACTION_COMPARE:'traction', VoiceIntent.DRIVING_ISSUES:'issues'}.get(intent, 'compare')
        return radio_summary(state, topic)
    if intent in (VoiceIntent.REFERENCE_SET, VoiceIntent.REFERENCE_PREVIOUS, VoiceIntent.REFERENCE_BEST):
        return 'Reference selection is handled by the live measured performance recorder.'

    if intent in (VoiceIntent.FACTS, VoiceIntent.LAP_COMPARISON, VoiceIntent.FUEL_USED, VoiceIntent.POSITION_CHANGE, VoiceIntent.MATH_STATUS, VoiceIntent.BRAKE_STATUS, VoiceIntent.BRAKE_TEMPERATURE, VoiceIntent.BRAKE_TEMPERATURE_DETAIL, VoiceIntent.BRAKE_DAMAGE, VoiceIntent.TYRE_PRESSURE, VoiceIntent.BRAKE_BIAS, VoiceIntent.SETUP, VoiceIntent.WHEEL_SLIP, VoiceIntent.G_FORCE, VoiceIntent.BEST_LAP, VoiceIntent.LAPS_REMAINING, VoiceIntent.ENGINE_STATUS, VoiceIntent.ENGINE_TEMPERATURE, VoiceIntent.ENGINE_WEAR, VoiceIntent.GEARBOX_STATUS, VoiceIntent.CURRENT_LAP, VoiceIntent.LAPS_COMPLETED, VoiceIntent.CURRENT_SECTOR, VoiceIntent.SESSION_TIME, VoiceIntent.GAP_LEADER, VoiceIntent.DRIVER_AHEAD, VoiceIntent.DRIVER_BEHIND, VoiceIntent.TYRE_COMPOUND, VoiceIntent.TYRE_AGE, VoiceIntent.TYRE_SET, VoiceIntent.DRS_STATUS, VoiceIntent.S_MODE_STATUS, VoiceIntent.OVERTAKE_STATUS, VoiceIntent.PIT_SPEED_LIMIT, VoiceIntent.PIT_STOPS, VoiceIntent.TRACK_TEMPERATURE, VoiceIntent.AIR_TEMPERATURE, VoiceIntent.RAIN_CHANCE, VoiceIntent.SPEED, VoiceIntent.RPM, VoiceIntent.GEAR, VoiceIntent.FUEL_MIX, VoiceIntent.ERS_HARVEST, VoiceIntent.GRID_POSITION, VoiceIntent.TRACK_LIMITS, VoiceIntent.SECTOR_TIMES, VoiceIntent.LAP_VALIDITY, VoiceIntent.TYRE_DAMAGE, VoiceIntent.TYRE_BLISTERS, VoiceIntent.PUNCTURE_STATUS, VoiceIntent.WING_STATUS, VoiceIntent.FLOOR_STATUS, VoiceIntent.FAULT_STATUS, VoiceIntent.DIFFERENTIAL, VoiceIntent.BRAKE_PRESSURE, VoiceIntent.ENGINE_BRAKING, VoiceIntent.WING_SETTING, VoiceIntent.RADIO_HELP):
        from .deterministic_math import snapshot, short_report
        d=snapshot(state)
        if intent == VoiceIntent.FACTS:
            from .deterministic_facts import factual_radio_summary
            return factual_radio_summary(state)
        if intent == VoiceIntent.LAP_COMPARISON:
            laps=state.measured_laps
            if len(laps)<2 or laps[-1].lap_time_s is None or laps[-2].lap_time_s is None: return 'Two completed measured laps are required.'
            x=laps[-1].lap_time_s-laps[-2].lap_time_s
            return f'Last lap was {abs(x):.3f} seconds {"slower" if x>0 else "faster" if x<0 else "the same"}.'
        if intent == VoiceIntent.FUEL_USED:
            if not metrics.fuel_strategy:
                return f'Fuel-use analysis is not applicable in {ctx.profile.replace("_", " " )}.'
            laps=state.measured_laps
            if not laps or laps[-1].fuel_used is None: return 'Completed-lap fuel usage is unavailable.'
            return f'Last completed lap used {laps[-1].fuel_used:.3f} raw fuel mass.'
        if intent == VoiceIntent.POSITION_CHANGE:
            if not metrics.race_position_strategy:
                return f'Race position-change analysis is not applicable in {ctx.profile.replace("_", " " )}.'
            laps=state.measured_laps
            if not laps or laps[-1].position_change is None: return 'Completed-lap position change is unavailable.'
            x=laps[-1].position_change
            return f'Last completed lap: {abs(x)} position{"s" if abs(x)!=1 else ""} {"gained" if x>0 else "lost" if x<0 else "changed"}.' if x else 'No position change on the last completed lap.'
        if intent == VoiceIntent.MATH_STATUS: return short_report(state)
        if intent == VoiceIntent.BRAKE_STATUS:
            temps = getattr(car.telemetry, 'brakes_temperature_c', None)
            damage = getattr(car.damage, 'brakes_percent', None)
            known_damage = _wheels(damage, 'percent') if damage else None
            if temps is None and damage is None:
                return 'Brake data unavailable.'
            # Generic brake info stays concise; exact numbers are available through
            # "brake temp" and "brake damage".
            if damage and any((getattr(damage, x) or 0) > 0 for x in ('FL','FR','RL','RR')):
                worst = max((getattr(damage, x) or 0, x) for x in ('FL','FR','RL','RR'))
                names={'FL':'front left','FR':'front right','RL':'rear left','RR':'rear right'}
                return f'Brakes: {names[worst[1]]} damage {worst[0]:g} percent.'
            return 'Brakes are good.'
        if intent in (VoiceIntent.BRAKE_TEMPERATURE, VoiceIntent.BRAKE_TEMPERATURE_DETAIL):
            w=getattr(car.telemetry, 'brakes_temperature_c', None)
            if not w: return 'Brake temperature data unavailable.'
            if intent == VoiceIntent.BRAKE_TEMPERATURE_DETAIL:
                return 'Brake temperatures: '+_wheels(w, 'degrees')+'.'
            vals=[v for v in (w.FL,w.FR,w.RL,w.RR) if v is not None]
            if not vals: return 'Brake temperature data unavailable.'
            mx=max(vals)
            return 'Brakes are hot.' if mx >= 1100 else 'Brakes are warm.' if mx >= 1000 else 'Brake temperatures are good.'
        if intent == VoiceIntent.BRAKE_DAMAGE:
            w=getattr(car.damage, 'brakes_percent', None)
            return _wheels(w, 'percent')+'.' if w else 'Brake damage data unavailable.'
        if intent == VoiceIntent.TYRE_PRESSURE:
            return _wheels(car.tyres.pressure_psi, 'PSI')+'.' if car.tyres.pressure_psi else 'Tyre pressure data unavailable.'
        if intent == VoiceIntent.BRAKE_BIAS:
            v=d.get('setup_brake_bias_percent'); return f'Brake bias {v:g} percent.' if v is not None else 'Brake bias data unavailable.'
        if intent == VoiceIntent.SETUP:
            if 'setup_front_wing' not in d: return 'Setup data unavailable.'
            return f"Wings {d['setup_front_wing']}/{d['setup_rear_wing']}. Brake bias {d['setup_brake_bias_percent']} percent. Brake pressure {d['setup_brake_pressure_percent']} percent."
        if intent == VoiceIntent.WHEEL_SLIP:
            v=d.get('wheel_slip_ratio_max'); return f'Maximum absolute wheel slip ratio {v:.3f}.' if v is not None else 'Wheel slip data unavailable.'
        if intent == VoiceIntent.G_FORCE:
            if 'g_lateral' not in d: return 'G force data unavailable.'
            return f"Lateral {d['g_lateral']:.2f} G. Longitudinal {d['g_longitudinal']:.2f} G."
        if intent == VoiceIntent.BEST_LAP:
            v=d.get('history_best_lap_s', d.get('tt_session_best_s'))
            if not v:
                final=state.extended.get('final')
                if final is not None and state.player_index is not None:
                    arr=getattr(final,'m_classificationData',())
                    if state.player_index < len(arr) and getattr(arr[state.player_index],'m_bestLapTimeInMS',0):
                        v=arr[state.player_index].m_bestLapTimeInMS/1000.0
            if not v:
                perf=state.extended.get('measured_performance',{})
                laps=perf.get('completed_laps',[]) if isinstance(perf,dict) else []
                vals=[x.get('lap_time_s') for x in laps if x.get('valid') and x.get('lap_time_s')]
                if vals: v=min(vals)
            return _lap_time(v)+'.' if v else 'Best lap data unavailable.'
        if intent == VoiceIntent.LAPS_REMAINING:
            if not metrics.race_position_strategy:
                return f'Race laps remaining are not applicable in {ctx.profile.replace("_", " " )}.'
            v=d.get('laps_remaining'); return (f'{v} lap remaining.' if v == 1 else f'{v} laps remaining.') if v is not None else 'Laps remaining unavailable.'
        if intent == VoiceIntent.ENGINE_STATUS:
            parts=[]
            if car.telemetry.engine_temperature_c is not None: parts.append(f"temperature {car.telemetry.engine_temperature_c} degrees")
            if car.damage.engine_percent is not None: parts.append(f"wear {car.damage.engine_percent:g} percent")
            if car.damage.engine_blown is True: return 'Engine blown.'
            if car.damage.engine_seized is True: return 'Engine seized.'
            if car.damage.ers_fault is True: parts.append('ERS fault')
            return 'Engine: ' + ', '.join(parts) + '.' if parts else 'Engine data unavailable.'
        if intent == VoiceIntent.ENGINE_TEMPERATURE:
            v=car.telemetry.engine_temperature_c
            return f'Engine temperature {v} degrees.' if v is not None else 'Engine temperature unavailable.'
        if intent == VoiceIntent.ENGINE_WEAR:
            vals=[]
            if car.damage.engine_percent is not None: vals.append(f"overall {car.damage.engine_percent:g} percent")
            vals += [f"{k.replace('_',' ')} {v:g} percent" for k,v in sorted(car.damage.engine_wear_percent.items()) if v is not None]
            return 'Engine wear: ' + ', '.join(vals) + '.' if vals else 'Engine wear data unavailable.'
        if intent == VoiceIntent.GEARBOX_STATUS:
            v=car.damage.gearbox_percent
            return f'Gearbox wear {v:g} percent.' if v is not None else 'Gearbox data unavailable.'
        if intent == VoiceIntent.CURRENT_LAP:
            lap=car.lap.current_lap
            total=state.session.total_laps
            if lap is None: return 'Current lap unavailable.'
            return f'Lap {lap} of {total}.' if total else f'Lap {lap}.'
        if intent == VoiceIntent.LAPS_COMPLETED:
            lap=car.lap.current_lap
            
            if lap is None: return 'Completed laps unavailable.'
            done=max(0,lap-1); return f'{done} lap completed.' if done == 1 else f'{done} laps completed.'
        if intent == VoiceIntent.CURRENT_SECTOR:
            sec=car.lap.sector
            return f'Sector {sec + 1}.' if sec is not None and sec in (0,1,2) else (f'Sector {sec}.' if sec is not None else 'Current sector unavailable.')
        if intent == VoiceIntent.SESSION_TIME:
            v=state.session.time_left_s
            if v is None: return 'Session time remaining unavailable.'
            m,s=divmod(max(0,int(v)),60)
            return f'{m} minutes {s} seconds remaining.' if m else f'{s} seconds remaining.'
        if intent == VoiceIntent.GAP_LEADER:
            v=car.lap.gap_to_leader_s
            return f'Gap to leader {v:.2f} seconds.' if v is not None else 'Gap to leader unavailable.'
        if intent == VoiceIntent.DRIVER_AHEAD:
            name=_driver_label(state,state.ahead_index)
            if not name: return 'Driver ahead unavailable.'
            gap=car.lap.gap_to_car_in_front_s
            return f'{name} ahead, {gap:.2f} seconds.' if gap is not None else f'{name} ahead.'
        if intent == VoiceIntent.DRIVER_BEHIND:
            name=_driver_label(state,state.behind_index)
            if not name: return 'Driver behind unavailable.'
            gap=state.gap_behind_s
            return f'{name} behind, {gap:.2f} seconds.' if gap is not None else f'{name} behind.'
        if intent == VoiceIntent.TYRE_COMPOUND:
            a=_enum_name(car.tyres.actual_compound); v=_enum_name(car.tyres.visual_compound)
            if a and v and a != v: return f'Tyres {v}, actual compound {a}.'
            return f'Tyres {v or a}.' if (v or a) else 'Tyre compound unavailable.'
        if intent == VoiceIntent.TYRE_AGE:
            v=car.tyres.age_laps
            return f'Tyre age {v} laps.' if v is not None else 'Tyre age unavailable.'
        if intent == VoiceIntent.TYRE_SET:
            idx=car.tyres.fitted_set_index
            return f'Fitted tyre set {idx}.' if idx is not None else 'Fitted tyre set unavailable.'
        if intent == VoiceIntent.DRS_STATUS:
            if car.aero.drs_allowed is None: return 'DRS status unavailable.'
            if car.telemetry.drs is True: return 'DRS open.'
            return 'DRS available.' if car.aero.drs_allowed else 'DRS unavailable.'
        if intent == VoiceIntent.S_MODE_STATUS:
            mode=_enum_name(car.aero.active_aero_mode)
            if mode: return f'S Mode {mode}.'
            if car.aero.active_aero_available is not None: return 'S Mode available.' if car.aero.active_aero_available else 'S Mode unavailable.'
            return 'S Mode status unavailable.'
        if intent == VoiceIntent.OVERTAKE_STATUS:
            if car.aero.overtake_active is True: return 'Overtake mode active.'
            if car.aero.overtake_available is True: return 'Overtake available.'
            if car.aero.overtake_available is False: return 'Overtake unavailable.'
            return 'Overtake status unavailable.'
        if intent == VoiceIntent.PIT_SPEED_LIMIT:
            v=state.session.pit_speed_limit_kph
            return f'Pit speed limit {v} kilometres per hour.' if v is not None else 'Pit speed limit unavailable.'
        if intent == VoiceIntent.PIT_STOPS:
            v=car.lap.pit_stops
            return f'{v} pit stop{"s" if v != 1 else ""} completed.' if v is not None else 'Pit stop count unavailable.'
        if intent == VoiceIntent.TRACK_TEMPERATURE:
            v=state.session.track_temperature_c
            return f'Track temperature {v} degrees.' if v is not None else 'Track temperature unavailable.'
        if intent == VoiceIntent.AIR_TEMPERATURE:
            v=state.session.air_temperature_c
            return f'Air temperature {v} degrees.' if v is not None else 'Air temperature unavailable.'
        if intent == VoiceIntent.RAIN_CHANCE:
            if state.session.forecast:
                return f'Forecast rain {state.session.forecast[0].rain_percent} percent.'
            return 'Rain forecast unavailable.'
        if intent == VoiceIntent.SPEED:
            v=car.telemetry.speed_kph
            return f'{v} kilometres per hour.' if v is not None else 'Speed unavailable.'
        if intent == VoiceIntent.RPM:
            v=car.telemetry.rpm
            return f'{v} RPM.' if v is not None else 'RPM unavailable.'
        if intent == VoiceIntent.GEAR:
            v=car.telemetry.gear
            return f'Gear {v}.' if v is not None else 'Gear unavailable.'
        if intent == VoiceIntent.FUEL_MIX:
            v=_enum_name(car.fuel.mix)
            return f'Fuel mix {v}.' if v else 'Fuel mix unavailable.'
        if intent == VoiceIntent.ERS_HARVEST:
            vals=[]
            if car.energy.harvested_mguk_j is not None: vals.append(f"MGU-K {car.energy.harvested_mguk_j/1000.0:.0f} kilojoules")
            if car.energy.harvested_mguh_j is not None: vals.append(f"MGU-H {car.energy.harvested_mguh_j/1000.0:.0f} kilojoules")
            return 'ERS harvested: ' + ', '.join(vals) + '.' if vals else 'ERS harvest data unavailable.'
        if intent == VoiceIntent.GRID_POSITION:
            v=car.lap.grid_position
            return f'Grid position P{v}.' if v is not None else 'Grid position unavailable.'
        if intent == VoiceIntent.TRACK_LIMITS:
            w=car.lap.corner_cutting_warnings
            total=car.lap.warnings
            if w is None and total is None: return 'Track-limit warning data unavailable.'
            return f'Track limits: {w or 0} corner-cutting warnings, {total or 0} total warnings.'
        if intent == VoiceIntent.SECTOR_TIMES:
            parts=[]
            if car.lap.sector1_time_s is not None: parts.append(f"S1 {car.lap.sector1_time_s:.3f}")
            if car.lap.sector2_time_s is not None: parts.append(f"S2 {car.lap.sector2_time_s:.3f}")
            return '. '.join(parts)+'.' if parts else 'Sector times unavailable.'
        if intent == VoiceIntent.LAP_VALIDITY:
            v=car.lap.lap_valid
            return 'Current lap is valid.' if v is True else 'Current lap is invalid.' if v is False else 'Lap validity unavailable.'
        if intent == VoiceIntent.TYRE_DAMAGE:
            w=car.tyres.damage_percent
            return ('Tyre damage: '+_wheels(w, 'percent')+'.') if w else 'Tyre damage data unavailable.'
        if intent == VoiceIntent.TYRE_BLISTERS:
            w=car.tyres.blisters_percent
            return ('Tyre blistering: '+_wheels(w, 'percent')+'.') if w else 'Tyre blistering data unavailable.'
        if intent == VoiceIntent.PUNCTURE_STATUS:
            w=car.tyres.punctured
            if w is None: return 'Puncture status is not explicitly available in this telemetry state.'
            bad=[name for name,key in (("front left","FL"),("front right","FR"),("rear left","RL"),("rear right","RR")) if getattr(w,key) is True]
            return ('Puncture: '+', '.join(bad)+'.') if bad else 'No puncture reported.'
        if intent == VoiceIntent.WING_STATUS:
            d=car.damage
            vals=[]
            if d.front_left_wing_percent is not None: vals.append(f"left {d.front_left_wing_percent:g}")
            if d.front_right_wing_percent is not None: vals.append(f"right {d.front_right_wing_percent:g}")
            if d.rear_wing_percent is not None: vals.append(f"rear {d.rear_wing_percent:g}")
            return 'Wing damage: '+', '.join(vals)+' percent.' if vals else 'Wing damage data unavailable.'
        if intent == VoiceIntent.FLOOR_STATUS:
            d=car.damage
            vals=[]
            if d.floor_percent is not None: vals.append(f"floor {d.floor_percent:g}")
            if d.diffuser_percent is not None: vals.append(f"diffuser {d.diffuser_percent:g}")
            if d.sidepod_percent is not None: vals.append(f"sidepod {d.sidepod_percent:g}")
            return 'Body damage: '+', '.join(vals)+' percent.' if vals else 'Floor/body damage data unavailable.'
        if intent == VoiceIntent.FAULT_STATUS:
            d=car.damage
            faults=[]
            if d.drs_fault is True: faults.append('DRS fault')
            if d.ers_fault is True: faults.append('ERS fault')
            if d.engine_blown is True: faults.append('engine blown')
            if d.engine_seized is True: faults.append('engine seized')
            return ', '.join(faults).capitalize()+'.' if faults else 'No reported system faults.'
        if intent == VoiceIntent.DIFFERENTIAL:
            on=d.get('setup_diff_on_throttle_percent'); off=d.get('setup_diff_off_throttle_percent')
            if on is None and off is None: return 'Differential setup unavailable.'
            return f'Differential: on throttle {on:g} percent, off throttle {off:g} percent.'
        if intent == VoiceIntent.BRAKE_PRESSURE:
            v=d.get('setup_brake_pressure_percent')
            return f'Brake pressure {v:g} percent.' if v is not None else 'Brake pressure setup unavailable.'
        if intent == VoiceIntent.ENGINE_BRAKING:
            v=d.get('setup_engine_braking_percent')
            return f'Engine braking {v:g} percent.' if v is not None else 'Engine-braking setup unavailable.'
        if intent == VoiceIntent.WING_SETTING:
            f=d.get('setup_front_wing'); r=d.get('setup_rear_wing')
            return f'Wing settings {f:g} front, {r:g} rear.' if f is not None and r is not None else 'Wing setup unavailable.'

    if intent == VoiceIntent.TYRE_STATUS:
        # Generic tyre radio mirrors brake info: concise by default. Exact numbers
        # remain available through tyre temperatures / wear / pressure / damage.
        wear=car.tyres.wear_percent; damage=car.tyres.damage_percent; temp=car.tyres.surface_temperature_c
        issues=[]
        if damage:
            vals=[(getattr(damage,k),k) for k in ('FL','FR','RL','RR') if getattr(damage,k) is not None]
            if vals and max(v for v,_ in vals) >= 25:
                v,k=max(vals); issues.append(f"{ {'FL':'front left','FR':'front right','RL':'rear left','RR':'rear right'}[k] } tyre damaged")
        if wear:
            vals=[(getattr(wear,k),k) for k in ('FL','FR','RL','RR') if getattr(wear,k) is not None]
            if vals and max(v for v,_ in vals) >= 25:
                v,k=max(vals); issues.append(f"{ {'FL':'front left','FR':'front right','RL':'rear left','RR':'rear right'}[k] } wear {v:g} percent")
        if temp:
            vals=[(getattr(temp,k),k) for k in ('FL','FR','RL','RR') if getattr(temp,k) is not None]
            if vals:
                mx=max(vals); mn=min(vals)
                names={'FL':'front left','FR':'front right','RL':'rear left','RR':'rear right'}
                if mx[0] >= 115: issues.append(f"{names[mx[1]]} hot")
                elif mn[0] < 70: issues.append(f"{names[mn[1]]} cold")
        if issues: return 'Tyres: ' + ', '.join(issues) + '.'
        if any(x is not None for x in (wear,damage,temp)): return 'Tyres are good.'
        return 'Tyre data unavailable.'

    if intent == VoiceIntent.TYRE_WEAR:
        if not metrics.tyre_wear_strategy:
            return f'Tyre-wear strategy is not applicable in {ctx.profile.replace("_", " " )}.'
        w=car.tyres.wear_percent
        if not w: return "Tyre wear data unavailable."
        vals=_wheel_values(w)
        if not vals: return "Tyre wear data unavailable."
        if max(vals) < 20:
            return f"Tyre wear around {sum(vals)/len(vals):.1f} percent. All four healthy."
        return f"Tyre wear: FL {float(w.FL):.1f}, FR {float(w.FR):.1f}, RL {float(w.RL):.1f}, RR {float(w.RR):.1f} percent."

    if intent in (VoiceIntent.TYRE_TEMPERATURE, VoiceIntent.TYRE_TEMPERATURE_DETAIL):
        w=car.tyres.surface_temperature_c
        if not w: return "Tyre temperature data unavailable."
        if intent == VoiceIntent.TYRE_TEMPERATURE_DETAIL:
            temp=_wheels(w, "degrees")
            return f"Tyre temperatures: {temp}." if temp else "Tyre temperature data unavailable."
        vals=[v for v in (w.FL,w.FR,w.RL,w.RR) if v is not None]
        if not vals: return "Tyre temperature data unavailable."
        mx=max(vals); mn=min(vals)
        return "Tyres are hot." if mx >= 115 else "Tyres are cold." if mn < 70 else "Tyre temperatures are good."

    if intent == VoiceIntent.FUEL_STATUS:
        f = car.fuel
        if not metrics.fuel_strategy:
            raw = f" Raw fuel mass {f.remaining_mass:.2f}." if f.remaining_mass is not None else ""
            return f"Fuel strategy is not applicable in {ctx.profile.replace('_',' ')}.{raw}"
        parts = []
        if f.remaining_laps is not None: return f"Fuel {f.remaining_laps:.1f} laps remaining."
        if f.remaining_mass is not None: return f"Fuel mass {f.remaining_mass:.1f}, EA raw units."
        return "Fuel data unavailable."

    if intent == VoiceIntent.ERS_STATUS:
        e = car.energy
        if not metrics.ers_energy_strategy:
            raw = f" Raw ERS store {e.store_j / 1000.0:.0f} kilojoules." if e.store_j is not None else ""
            extra = " Overtake and Active Aero are analysed separately." if metrics.overtake_analysis or metrics.active_aero_analysis else ""
            return f"ERS energy strategy is not applicable in {ctx.profile.replace('_',' ')}.{raw}{extra}"
        parts = []
        if e.store_j is not None: parts.append(f"ERS store {e.store_j / 1000.0:.0f} kilojoules")
        mode = _enum_name(e.deploy_mode)
        if mode: parts.append(f"deploy mode {mode}")
        return ". ".join(parts) + "." if parts else "ERS data unavailable."

    if intent == VoiceIntent.POSITION:
        if not metrics.race_position_strategy: return f'Race position is not applicable in {ctx.profile.replace("_", " " )}.'
        return f"You are P{car.lap.position}." if car.lap.position is not None else "Position unavailable."

    if intent == VoiceIntent.GAP_AHEAD:
        if not metrics.traffic_gap_analysis: return f'Traffic gap analysis is not applicable in {ctx.profile.replace("_", " " )}.'
        gap = car.lap.gap_to_car_in_front_s
        return f"Gap ahead {gap:.2f} seconds." if gap is not None else "Gap ahead unavailable."

    if intent == VoiceIntent.GAP_BEHIND:
        if not metrics.traffic_gap_analysis: return f'Traffic gap analysis is not applicable in {ctx.profile.replace("_", " " )}.'
        gap = state.gap_behind_s
        return f"Gap behind {gap:.2f} seconds." if gap is not None else "Gap behind unavailable."

    if intent == VoiceIntent.LAP_TIME:
        previous = _lap_time(car.lap.previous_lap_time_s)
        current = _lap_time(car.lap.current_lap_time_s)
        if previous: return f"Previous lap {previous}."
        if current: return f"Current lap time {current}."
        return "Lap time unavailable."

    if intent == VoiceIntent.DAMAGE:
        if not metrics.damage_strategy and ctx.car_damage == 0:
            return f'Car damage is disabled for this {ctx.profile.replace("_", " " )} session.'
        d = car.damage
        values = {
            "front left wing": d.front_left_wing_percent, "front right wing": d.front_right_wing_percent,
            "rear wing": d.rear_wing_percent, "floor": d.floor_percent,
            "diffuser": d.diffuser_percent, "sidepod": d.sidepod_percent,
            "gearbox": d.gearbox_percent, "engine": d.engine_percent,
        }
        known = [(name, val) for name, val in values.items() if val is not None]
        damaged = [(name, val) for name, val in known if val > 0]
        if damaged:
            return "Damage: " + ", ".join(f"{name} {val} percent" for name, val in damaged) + "."
        return "No reported car damage." if known else "Damage data unavailable."

    if intent == VoiceIntent.PENALTIES:
        lap = car.lap
        if all(v is None for v in (lap.penalties_s, lap.warnings, lap.unserved_drive_through, lap.unserved_stop_go)):
            return "Penalty data unavailable."
        parts = [f"{lap.penalties_s or 0} seconds of penalties", f"{lap.warnings or 0} warnings"]
        if lap.unserved_drive_through: parts.append(f"{lap.unserved_drive_through} unserved drive-through")
        if lap.unserved_stop_go: parts.append(f"{lap.unserved_stop_go} unserved stop-go")
        return ". ".join(parts) + "."

    if intent == VoiceIntent.WEATHER:
        s = state.session
        weather = _enum_name(s.weather)
        parts = [f"Current weather {weather}" if weather else None]
        if s.air_temperature_c is not None: parts.append(f"air {s.air_temperature_c} degrees")
        if s.track_temperature_c is not None: parts.append(f"track {s.track_temperature_c} degrees")
        if s.forecast:
            nxt = s.forecast[0]
            parts.append(f"forecast rain {nxt.rain_percent} percent")
        parts = [p for p in parts if p]
        return ". ".join(parts) + "." if parts else "Weather data unavailable."

    if intent == VoiceIntent.PIT_STATUS:
        status = _enum_name(car.lap.pit_status)
        return f"Pit status: {status}." if status else "Pit status unavailable."

    if intent == VoiceIntent.PIT_RECOMMENDATION:
        from .pit_strategy import service_plan
        return service_plan(state).automatic_summary

    if intent == VoiceIntent.TYRE_SELECTION:
        if ctx.profile == 'time_trial': return 'Pit tyre selection is not applicable in Time Trial.'
        from .pit_strategy import choose_tyre
        x=choose_tyre(state)
        return f"Fit {x.compound}, set {x.set_index}. {x.reason.capitalize()}." if x.available else x.reason.capitalize()+'.'

    if intent == VoiceIntent.WING_SERVICE:
        from .pit_strategy import service_plan
        p=service_plan(state)
        if p.front_wing_service:
            if p.front_wing_adjustment is not None: return f"Replace front wing. Game front-wing setting {p.front_wing_adjustment:g}."
            return "Replace front wing. No factual adjustment value is available from the game."
        if p.front_wing_adjustment is not None: return f"No wing repair trigger. Game front-wing setting {p.front_wing_adjustment:g}."
        return "No wing repair trigger and no factual adjustment value is available."

    if intent == VoiceIntent.RACE_CONTROL:
        sc = _enum_name(state.session.safety_car)
        if sc and sc.lower() != "none": return f"Race control: {sc}."
        return "No Safety Car reported." if sc else "Race-control status unavailable."

    if intent == VoiceIntent.STATUS:
        parts = []
        if metrics.race_position_strategy and car.lap.position is not None: parts.append(f"P{car.lap.position}")
        if car.lap.current_lap is not None: parts.append(f"lap {car.lap.current_lap}")
        if car.lap.previous_lap_time_s is not None: parts.append(f"last lap {car.lap.previous_lap_time_s:.3f}")
        if metrics.fuel_strategy and car.fuel.remaining_laps is not None: parts.append(f"fuel {car.fuel.remaining_laps:.1f} laps")
        if metrics.tyre_wear_strategy and car.tyres.wear_percent is not None:
            vals = [v for v in (car.tyres.wear_percent.FL, car.tyres.wear_percent.FR, car.tyres.wear_percent.RL, car.tyres.wear_percent.RR) if v is not None]
            if vals: parts.append(f"maximum tyre wear {max(vals):.1f} percent")
        return ". ".join(parts) + "." if parts else "Live status unavailable."

    return "I don't support that radio request yet."


def _coach_query_response(text: str, state: RaceState) -> str | None:
    """Answer performance-coach questions from authoritative measured state only.

    V1.3.0.0 intentionally keeps this deterministic: it reads the integrated
    coaching objects already produced by telemetry analysis and never infers an
    unseen braking/throttle/path event.
    """
    t = _plain(text)
    suite = state.extended.get("coaching_suite")
    if not isinstance(suite, dict):
        return None
    priority = suite.get("last_priority") or {}
    focus = priority.get("selected_focus") if isinstance(priority, dict) else None
    advice = suite.get("advice") if isinstance(suite.get("advice"), dict) else {}
    patterns = suite.get("session_patterns") if isinstance(suite.get("session_patterns"), list) else []
    turns = [x for x in (suite.get("turn_performance") or []) if isinstance(x, dict)]
    distance = suite.get("distance_performance") if isinstance(suite.get("distance_performance"), dict) else {}
    advice_memory = suite.get("advice_memory") if isinstance(suite.get("advice_memory"), dict) else {}
    memory_focus = advice_memory.get("current_focus") if isinstance(advice_memory.get("current_focus"), dict) else None

    def turn_number():
        m = re.search(r"(?:turn|corner)\s*(\d{1,2})", t)
        return int(m.group(1)) if m else None

    def turn_row(cid: int | None):
        if cid is None:
            return None
        for row in turns:
            if row.get("corner_id") == cid:
                return row
        return None

    def advice_row(cid: int | None):
        return advice.get(str(cid)) if cid is not None and isinstance(advice.get(str(cid)), dict) else None

    def issue_text(row: dict | None) -> str:
        if not isinstance(row, dict):
            return "measured issue"
        return str(row.get("diagnosis_label") or row.get("issue_label") or row.get("diagnosis") or row.get("issue_code") or "measured issue").lower()

    def loss_value(row: dict | None):
        if not isinstance(row, dict):
            return None
        for key in ("net_loss_s", "assigned_loss_s", "physical_net_loss_s", "time_loss_s", "estimated_time_cost_s"):
            v = row.get(key)
            if isinstance(v, (int, float)):
                return float(v)
        return None

    cid = turn_number()

    # Session/current-focus questions.
    if any(p in t for p in ("which corner should i work on", "what should i focus on", "biggest mistake", "focus next lap", "what am i working on")):
        active_focus = memory_focus if isinstance(memory_focus, dict) else focus
        if isinstance(active_focus, dict) and active_focus.get("corner_id") is not None:
            cost = active_focus.get("latest_cost_s") if isinstance(active_focus.get("latest_cost_s"),(int,float)) else active_focus.get("estimated_time_cost_s")
            cost_text = f", measured cost {float(cost):.3f} seconds" if isinstance(cost, (int,float)) else ""
            label = active_focus.get("issue_label") or active_focus.get("diagnosis_label") or active_focus.get("issue_code") or active_focus.get("diagnosis") or "measured issue"
            return f"Focus Turn {active_focus['corner_id']}: {str(label).lower()}{cost_text}."
        return "No loss-supported coaching focus is available yet."

    if "potential lap" in t:
        p = suite.get("potential") or {}
        v = p.get("potential_lap_s"); gain = p.get("potential_gain_s")
        if isinstance(v, (int,float)):
            extra = f". Observed gain available {float(gain):.3f} seconds" if isinstance(gain,(int,float)) and gain > 0 else ""
            return f"Observed potential lap {float(v):.3f} seconds{extra}."
        return "Potential lap needs enough compatible valid completed segments."

    if "consistent" in t or "consistency" in t:
        metric = (suite.get("technique_metrics") or {}).get("lap_time_consistency")
        if isinstance(metric, dict) and isinstance(metric.get("stddev"), (int,float)):
            return f"Lap-time consistency standard deviation {float(metric['stddev']):.3f} seconds across {int(metric.get('samples') or 0)} eligible laps."
        return "Consistency needs at least three eligible valid laps."

    # Direct corner diagnosis / target questions.
    if cid is not None and any(p in t for p in ("why am i slow", "why slow", "what am i doing", "how is turn", "how is corner")):
        a = advice_row(cid)
        if isinstance(a, dict):
            loss = loss_value(a)
            return f"Turn {cid}: {issue_text(a)}." + (f" Net measured corner loss {loss:.3f} seconds." if isinstance(loss,(int,float)) else "")
        return f"Turn {cid} has no current loss-supported diagnosis against the active reference."

    if cid is not None and ("where should i brake" in t or "brake point" in t):
        a = advice_row(cid)
        if isinstance(a, dict) and isinstance(a.get("reference_brake_onset_m"), (int,float)):
            return f"Turn {cid} reference brake onset is about {float(a['reference_brake_onset_m']):.0f} metres into the lap."
        if isinstance(a, dict) and isinstance(a.get("reference_brake_m"), (int,float)):
            return f"Turn {cid} reference brake onset is about {float(a['reference_brake_m']):.0f} metres into the lap."
        return f"Turn {cid} reference brake point is unavailable from the trusted reference."

    if cid is not None and ("did i improve" in t or "improve turn" in t or "improve on turn" in t or "improve corner" in t or "improve on corner" in t):
        memory_rows = [x for x in (advice_memory.get("active") or []) + (advice_memory.get("solved") or []) if isinstance(x,dict) and x.get("corner_id") == cid]
        if memory_rows:
            row = max(memory_rows, key=lambda x: int(x.get("last_advice_lap") or x.get("solved_lap") or -1))
            outcome = str(row.get("latest_outcome") or row.get("status") or "insufficient history")
            recovered = row.get("best_recovered_s")
            extra = f", recovered up to {float(recovered):.3f} seconds in the measured issue" if isinstance(recovered,(int,float)) and recovered > 0.015 else ""
            return f"Turn {cid}, {str(row.get('issue_label') or row.get('issue_code') or 'measured issue').lower()}: {outcome}{extra}."
        rows = [x for x in patterns if isinstance(x, dict) and x.get("corner_id") == cid]
        if rows:
            row = max(rows, key=lambda x: float(x.get("focus_score") or 0.0))
            trend = str(row.get("trend") or "insufficient history")
            return f"Turn {cid}, {issue_text(row)}: measured trend is {trend}."
        return f"Turn {cid} does not have enough repeated coaching history yet."

    # Braking/throttle summaries use only supported diagnoses. Pace-only rival
    # references therefore cannot create an unsupported brake/throttle claim.
    if "how is my braking" in t or "am i braking too early" in t:
        braking = [x for x in advice.values() if isinstance(x, dict) and (str(x.get("diagnosis") or "").startswith("brake_") or "trail_brake" in str(x.get("diagnosis") or ""))]
        if braking:
            a = max(braking, key=lambda x: float(x.get("estimated_time_cost_s") or 0.0))
            if "too early" in t and str(a.get("diagnosis")) != "brake_early":
                return "No current loss-supported early-braking issue is dominant."
            return f"Turn {a.get('corner_id')}: {issue_text(a)}."
        if "too early" in t:
            return "No current loss-supported early-braking issue is dominant."
        return "No current loss-supported braking issue is dominant."

    if "throttle application" in t or "how is my throttle" in t:
        rows = [x for x in advice.values() if isinstance(x, dict) and ("throttle" in str(x.get("diagnosis") or "") or str(x.get("diagnosis") or "") == "exit_speed_low")]
        if rows:
            a = max(rows, key=lambda x: float(x.get("estimated_time_cost_s") or 0.0))
            return f"Turn {a.get('corner_id')}: {issue_text(a)}."
        return "No current loss-supported throttle issue is dominant."

    # Full-lap / gain-loss questions use physical-turn time attribution.
    if "where am i losing time" in t or "where did i lose time" in t:
        losses = [(loss_value(r), r) for r in turns]
        losses = [(v, r) for v, r in losses if isinstance(v, (int,float)) and v > 0.015]
        if losses:
            losses.sort(key=lambda x: x[0], reverse=True)
            v, r = losses[0]
            a = advice_row(r.get("corner_id"))
            why = f", {issue_text(a)}" if isinstance(a, dict) and a.get("diagnosis") else ""
            return f"Largest measured loss is Turn {r.get('corner_id')}, {v:.3f} seconds{why}."
        net = distance.get("full_track_net_delta_s")
        if isinstance(net, (int,float)) and net > 0:
            return f"Measured full-lap loss is {float(net):.3f} seconds, but no single physical turn currently dominates."
        return "No meaningful measured turn loss is available yet."

    if "where did i gain time" in t or "where am i gaining time" in t:
        gains = [(loss_value(r), r) for r in turns]
        gains = [(v, r) for v, r in gains if isinstance(v, (int,float)) and v < -0.015]
        if gains:
            gains.sort(key=lambda x: x[0])
            v, r = gains[0]
            return f"Largest measured gain is Turn {r.get('corner_id')}, {abs(v):.3f} seconds faster than the reference through that turn."
        return "No meaningful measured turn gain is available yet."

    if "compare this lap" in t or "compare my lap" in t or "lap with reference" in t:
        net = distance.get("full_track_net_delta_s")
        if isinstance(net, (int,float)):
            state_word = "slower" if net > 0 else "faster"
            result = f"Current measured lap comparison is {abs(float(net)):.3f} seconds {state_word} than the reference"
            losses = [(loss_value(r), r) for r in turns]
            losses = [(v, r) for v, r in losses if isinstance(v,(int,float)) and v > 0.015]
            if losses:
                v, r = max(losses, key=lambda x:x[0])
                result += f". Biggest turn loss is Turn {r.get('corner_id')}, {v:.3f} seconds"
            return result + "."
        return "A full measured lap comparison is not available yet."

    return None

def handle_voice_request(text: str, state: RaceState) -> VoiceResult:
    normalized = normalize_radio_text(text)
    coach = _coach_query_response(normalized, state)
    if coach is not None:
        return VoiceResult(VoiceIntent.PERFORMANCE_COMPARE, coach)
    intent = parse_intent(normalized)
    return VoiceResult(intent, answer_intent(intent, state))
