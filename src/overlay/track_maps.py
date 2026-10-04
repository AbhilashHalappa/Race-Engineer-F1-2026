"""Track-map storage for the F1 Dash.

The live dashboard deliberately does *not* trust hand-drawn approximations for
its circuit geometry. A track is learned from one complete start/finish-to-
start/finish telemetry lap, persisted as its own ``maps/tracks/<TRACK>.json``
file, and then re-used immediately on future sessions/replays. Legacy combined
caches are read only for compatibility/migration. The old built-in outlines are
retained only as a legacy fallback/data set; ``get_track_map()`` returns learned
geometry by default.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Iterable

from ..track_geometry import derive_physical_turns, measured_world_trace, trace_is_complete


def _close(points):
    pts = tuple((float(x), float(y)) for x, y in points)
    if not pts:
        return pts
    return pts if pts[0] == pts[-1] else pts + (pts[0],)


def _key(track_name: object) -> str | None:
    if not track_name:
        return None
    value = str(track_name).strip().upper()
    return value or None


# Legacy coarse shapes are retained for compatibility/testing only.  They are
# no longer selected by the native/LAN live map unless allow_fallback=True.
TRACK_MAPS = {
    "MELBOURNE": _close([(.38,.79),(.31,.70),(.24,.61),(.29,.51),(.19,.44),(.08,.35),(.16,.27),(.16,.14),(.37,.07),(.51,.05),(.71,.12),(.70,.26),(.66,.42),(.60,.55),(.67,.61),(.78,.73),(.83,.91),(.72,.92),(.67,.85),(.60,.87),(.52,.84),(.46,.81)]),
    "SHANGHAI": _close([(.72,.18),(.82,.19),(.88,.25),(.86,.35),(.77,.38),(.66,.34),(.55,.29),(.49,.22),(.40,.17),(.30,.19),(.22,.28),(.20,.40),(.27,.50),(.38,.57),(.53,.60),(.65,.65),(.73,.75),(.66,.84),(.52,.83),(.41,.75),(.33,.65),(.23,.62),(.13,.68),(.10,.58),(.16,.46),(.29,.39),(.45,.38),(.59,.42),(.72,.38)]),
    "SAKHIR (BAHRAIN)": _close([(.18,.18),(.68,.18),(.79,.22),(.83,.30),(.78,.36),(.63,.37),(.54,.42),(.56,.50),(.73,.54),(.82,.61),(.79,.70),(.68,.75),(.50,.70),(.39,.77),(.25,.74),(.16,.67),(.20,.58),(.35,.52),(.31,.44),(.16,.40),(.10,.31)]),
    "CATALUNYA": _close([(.12,.25),(.67,.24),(.80,.28),(.84,.37),(.76,.43),(.62,.41),(.52,.47),(.58,.57),(.74,.60),(.83,.67),(.80,.76),(.67,.81),(.55,.76),(.47,.66),(.38,.63),(.29,.69),(.18,.66),(.12,.56),(.20,.47),(.31,.42),(.25,.33)]),
    "MONACO": _close([(.30,.12),(.48,.13),(.62,.18),(.70,.27),(.67,.36),(.56,.41),(.50,.49),(.58,.57),(.69,.61),(.76,.69),(.73,.79),(.62,.85),(.50,.80),(.41,.70),(.31,.66),(.21,.70),(.13,.64),(.12,.53),(.20,.45),(.28,.38),(.24,.28),(.20,.20)]),
    "MONTREAL": _close([(.14,.20),(.68,.18),(.82,.24),(.84,.33),(.77,.39),(.62,.38),(.54,.44),(.62,.51),(.79,.54),(.86,.61),(.83,.69),(.70,.73),(.53,.69),(.42,.75),(.28,.73),(.18,.66),(.22,.57),(.38,.52),(.31,.43),(.16,.39),(.10,.31)]),
    "SILVERSTONE": _close([(.17,.25),(.30,.18),(.46,.20),(.56,.28),(.67,.22),(.79,.27),(.84,.38),(.77,.45),(.63,.44),(.58,.54),(.67,.62),(.78,.66),(.80,.76),(.70,.82),(.56,.78),(.47,.69),(.36,.73),(.25,.69),(.18,.60),(.22,.50),(.13,.43),(.10,.34)]),
    "HUNGARORING": _close([(.16,.23),(.61,.20),(.75,.24),(.82,.33),(.79,.42),(.67,.46),(.60,.54),(.67,.62),(.78,.66),(.77,.75),(.67,.82),(.54,.79),(.45,.70),(.34,.73),(.22,.68),(.16,.58),(.23,.49),(.33,.43),(.27,.34),(.15,.32)]),
    "SPA": _close([(.18,.70),(.12,.61),(.15,.48),(.25,.37),(.38,.26),(.50,.16),(.62,.09),(.73,.12),(.78,.21),(.74,.32),(.65,.41),(.58,.51),(.63,.62),(.75,.68),(.80,.77),(.73,.84),(.60,.82),(.49,.74),(.38,.78),(.26,.75)]),
    "MONZA": _close([(.22,.16),(.70,.16),(.81,.21),(.84,.29),(.79,.36),(.69,.39),(.68,.51),(.76,.59),(.78,.69),(.72,.78),(.60,.82),(.48,.77),(.40,.67),(.30,.65),(.20,.70),(.12,.64),(.12,.54),(.19,.46),(.26,.39),(.20,.30),(.14,.24)]),
    "SINGAPORE": _close([(.15,.18),(.62,.17),(.76,.22),(.80,.30),(.72,.34),(.58,.31),(.53,.38),(.66,.43),(.77,.49),(.78,.57),(.68,.61),(.57,.58),(.50,.66),(.58,.73),(.70,.77),(.68,.84),(.54,.86),(.44,.80),(.36,.70),(.24,.72),(.14,.66),(.12,.56),(.22,.49),(.30,.42),(.25,.34),(.13,.30)]),
    "SUZUKA": _close([(.21,.22),(.38,.17),(.54,.20),(.62,.29),(.56,.38),(.45,.42),(.36,.36),(.29,.40),(.32,.51),(.44,.57),(.58,.55),(.68,.61),(.75,.71),(.70,.81),(.58,.84),(.46,.78),(.35,.70),(.24,.74),(.15,.68),(.12,.58),(.19,.49),(.27,.44),(.22,.34),(.15,.29)]),
    "ABU DHABI": _close([(.16,.22),(.70,.20),(.81,.25),(.84,.34),(.79,.42),(.65,.43),(.56,.49),(.60,.58),(.74,.62),(.80,.70),(.76,.79),(.63,.83),(.52,.78),(.46,.68),(.35,.64),(.25,.70),(.16,.66),(.12,.57),(.19,.48),(.29,.42),(.23,.33),(.14,.30)]),
    "TEXAS": _close([(.15,.64),(.11,.55),(.16,.44),(.29,.34),(.42,.24),(.54,.17),(.65,.20),(.70,.29),(.65,.38),(.55,.44),(.60,.53),(.73,.58),(.81,.65),(.79,.74),(.68,.80),(.55,.76),(.45,.67),(.34,.72),(.23,.70)]),
    "BRAZIL": _close([(.17,.22),(.63,.20),(.75,.26),(.79,.36),(.74,.46),(.62,.52),(.57,.62),(.63,.72),(.58,.81),(.46,.85),(.35,.79),(.30,.67),(.21,.62),(.13,.54),(.15,.43),(.25,.36),(.22,.28)]),
    "AUSTRIA": _close([(.18,.19),(.67,.18),(.80,.24),(.84,.34),(.76,.43),(.63,.48),(.54,.58),(.57,.70),(.49,.80),(.37,.84),(.27,.77),(.23,.65),(.15,.58),(.11,.47),(.17,.37),(.26,.30)]),
    "MEXICO": _close([(.14,.22),(.70,.20),(.82,.26),(.84,.35),(.77,.42),(.64,.43),(.56,.50),(.63,.57),(.78,.60),(.83,.68),(.79,.77),(.66,.81),(.54,.76),(.46,.66),(.34,.64),(.24,.71),(.15,.67),(.11,.58),(.18,.48),(.28,.42),(.22,.33)]),
    "BAKU (AZERBAIJAN)": _close([(.12,.18),(.74,.18),(.82,.23),(.84,.31),(.78,.37),(.63,.37),(.60,.44),(.69,.49),(.75,.56),(.72,.64),(.60,.67),(.50,.62),(.43,.70),(.49,.77),(.60,.82),(.52,.87),(.39,.83),(.32,.73),(.22,.71),(.14,.65),(.16,.54),(.24,.45),(.17,.36),(.10,.30)]),
    "ZANDVOORT": _close([(.18,.20),(.60,.18),(.74,.23),(.81,.32),(.79,.42),(.69,.49),(.60,.56),(.65,.66),(.73,.75),(.68,.83),(.55,.86),(.44,.80),(.37,.70),(.27,.66),(.17,.60),(.14,.50),(.21,.41),(.27,.33),(.22,.26)]),
    "IMOLA": _close([(.17,.21),(.62,.19),(.75,.24),(.82,.33),(.78,.42),(.65,.46),(.57,.53),(.64,.61),(.76,.65),(.79,.74),(.71,.82),(.57,.84),(.46,.77),(.37,.68),(.25,.70),(.16,.64),(.13,.54),(.21,.45),(.28,.38),(.23,.29)]),
    "JEDDAH": _close([(.18,.17),(.73,.17),(.82,.22),(.85,.31),(.80,.41),(.70,.50),(.64,.60),(.66,.72),(.60,.82),(.48,.86),(.36,.81),(.30,.71),(.22,.62),(.15,.52),(.12,.41),(.15,.30)]),
    "MIAMI": _close([(.70,.14),(.82,.15),(.89,.22),(.86,.30),(.75,.33),(.66,.39),(.61,.48),(.62,.60),(.70,.72),(.78,.82),(.70,.87),(.55,.85),(.39,.82),(.25,.77),(.15,.70),(.12,.60),(.18,.50),(.29,.41),(.42,.32),(.56,.22)]),
    "LAS VEGAS": _close([(.14,.18),(.72,.18),(.83,.23),(.85,.31),(.79,.37),(.66,.38),(.61,.45),(.68,.51),(.80,.55),(.84,.63),(.81,.72),(.69,.76),(.53,.72),(.42,.78),(.28,.75),(.17,.68),(.20,.58),(.35,.52),(.29,.43),(.15,.39),(.10,.30)]),
    "LOSAIL": _close([(.17,.20),(.64,.18),(.77,.23),(.83,.32),(.80,.42),(.69,.49),(.58,.54),(.63,.64),(.73,.72),(.69,.81),(.56,.85),(.44,.79),(.36,.69),(.25,.66),(.16,.60),(.13,.50),(.20,.41),(.27,.33),(.22,.26)]),
    "MADRID": _close([(.16,.22),(.66,.20),(.78,.25),(.83,.34),(.78,.43),(.66,.47),(.58,.54),(.65,.61),(.78,.64),(.81,.73),(.73,.81),(.60,.84),(.50,.78),(.42,.68),(.31,.65),(.21,.71),(.13,.66),(.11,.56),(.18,.47),(.28,.41),(.23,.32)]),
}
for _reverse, _normal in (("SILVERSTONE (REVERSE)", "SILVERSTONE"), ("AUSTRIA (REVERSE)", "AUSTRIA"), ("ZANDVOORT (REVERSE)", "ZANDVOORT")):
    TRACK_MAPS[_reverse] = tuple(reversed(TRACK_MAPS[_normal]))

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
from ..app_paths import TRACKS as _MAPS_DIR, TRACK_MAPS as _TRACKS_DIR
# Legacy combined-cache locations are read/migrated only. New writes are always
# one JSON file per circuit under maps/tracks/.
_CACHE_PATH = _MAPS_DIR / "track_maps_cache.json"
_DEFAULT_CACHE_PATH = _CACHE_PATH
_LEGACY_CACHE_PATH = _PROJECT_ROOT / "track_maps_cache.json"
LEARNED_TRACK_MAPS: dict[str, tuple[tuple[float, float], ...]] = {}
LEARNED_TRACK_DISTANCES: dict[str, tuple[float, ...]] = {}
LEARNED_TRACK_LENGTHS: dict[str, float] = {}
LEARNED_TRACK_TURNS: dict[str, tuple[dict[str, object], ...]] = {}
# Adaptive physical-track model metadata.  Geometry is learned only from
# complete, clean laps and refined gradually so one unusual racing line cannot
# move every overlay/coach marker at once.
LEARNED_TRACK_OBSERVATIONS: dict[str, int] = {}
LEARNED_TRACK_LAST_LAP: dict[str, int] = {}
LEARNED_TRACK_FINGERPRINTS: dict[str, tuple[str, ...]] = {}
_INVALID_DEDICATED_TRACKS: set[str] = set()



def map_start_threshold(track_length_m: object) -> float:
    return max(60.0, min(150.0, float(track_length_m) * 0.02)) if isinstance(track_length_m, (int, float)) and track_length_m > 0 else 100.0


def verified_start_crossing(*, last_lap: object, last_distance_m: object, lap: object,
                            distance_m: object, track_length_m: object, lap_time_s: object) -> bool:
    """True only at a credible start/finish-line beginning of a lap.

    Starting the application midway around a lap must return False. A clean
    initial start is accepted only with a near-zero lap clock; later starts need
    either a normal lap-number increment or a high-to-low distance wrap.
    """
    if not isinstance(distance_m, (int, float)):
        return False
    threshold=map_start_threshold(track_length_m)
    if float(distance_m) > threshold:
        return False
    initial=(
        last_lap is None and isinstance(lap_time_s, (int, float))
        and 0.0 <= float(lap_time_s) <= 3.0
    )
    near_finish=(
        isinstance(track_length_m, (int, float)) and track_length_m > 1000
        and isinstance(last_distance_m, (int, float))
        and float(last_distance_m) >= float(track_length_m) * 0.85
    )
    normal=(isinstance(last_lap, int) and isinstance(lap, int) and lap == last_lap + 1 and near_finish)
    wrapped=(lap == last_lap and near_finish and float(distance_m) + threshold < float(last_distance_m))
    return bool(initial or normal or wrapped)

def _storage_dir() -> Path:
    """Return the per-track store, respecting tests that redirect _CACHE_PATH."""
    if _CACHE_PATH != _DEFAULT_CACHE_PATH:
        return _CACHE_PATH.parent / "tracks"
    return _TRACKS_DIR


def _safe_filename(track_name: object) -> str | None:
    name = _key(track_name)
    if not name:
        return None
    chars=[]
    last_sep=False
    for ch in name:
        if ch.isalnum():
            chars.append(ch)
            last_sep=False
        elif not last_sep:
            chars.append('_')
            last_sep=True
    stem=''.join(chars).strip('_')
    return (stem or 'TRACK') + '.json'


def _track_path(track_name: object) -> Path | None:
    filename=_safe_filename(track_name)
    return (_storage_dir() / filename) if filename else None


def _clean_turns(turns) -> tuple[dict[str, object], ...]:
    clean=[]
    seen=set()
    for turn in turns or ():
        if not isinstance(turn, dict):
            continue
        cid, dist = turn.get("corner_id"), turn.get("lap_distance_m")
        if not isinstance(cid, int) or cid <= 0 or cid in seen or not isinstance(dist, (int, float)):
            continue
        seen.add(cid)
        row={
            "corner_id": cid,
            "label": str(turn.get("label") or f"T{cid}"),
            "lap_distance_m": float(dist),
        }
        # V5+ physical-turn files retain geometry-derived corner boundaries so
        # turn/straight attribution and PRE/POST coaching share the same authority.
        for key in ("start_m", "apex_m", "end_m", "curvature_score"):
            value=turn.get(key)
            if isinstance(value,(int,float)):
                row[key]=float(value)
        direction=turn.get("turn_direction")
        if isinstance(direction,str) and direction:
            row["turn_direction"]=direction
        clean.append(row)
    clean.sort(key=lambda x: float(x["lap_distance_m"]))
    # Physical lap order is the only public turn numbering authority.
    for i, row in enumerate(clean, 1):
        row["corner_id"] = i
        row["label"] = f"T{i}"
    return tuple(clean)


def _geometry_payload_valid(points, distances=(), track_length_m=None) -> bool:
    if not isinstance(points, list) or len(points) < 20:
        return False
    try:
        pts=[(float(x),float(y)) for x,y in points]
    except (TypeError,ValueError,IndexError):
        return False
    if len(pts)>1 and pts[0]==pts[-1]:
        pts=pts[:-1]
    if len(pts)<20:
        return False
    # Dedicated V4 maps are captured every ~5 m. A huge adjacent chord is a
    # corrupt asynchronous S/F sample, not real circuit geometry.
    jumps=[((pts[i][0]-pts[i-1][0])**2+(pts[i][1]-pts[i-1][1])**2)**0.5 for i in range(1,len(pts))]
    if jumps:
        ordered=sorted(jumps)
        median=ordered[len(ordered)//2]
        if max(jumps) > max(45.0, median*8.0):
            return False
    if distances and len(distances) not in {len(pts),len(pts)+1}:
        return False
    return True


def _ingest_track_payload(name: object, item: object) -> bool:
    key=_key(name)
    if not key:
        return False
    version=0
    if isinstance(item, list):
        points, turns, distances, track_length = item, (), (), None
        learning={}
    elif isinstance(item, dict):
        points, turns = item.get("points", []), item.get("turns", [])
        distances=item.get("point_distances_m", [])
        track_length=item.get("track_length_m")
        learning=item.get("learning") if isinstance(item.get("learning"),dict) else {}
        try:
            version=int(item.get("version") or 0)
        except (TypeError, ValueError):
            version=0
    else:
        return False
    loaded=False
    has_points=isinstance(points, list) and bool(points)
    geometry_ok=_geometry_payload_valid(points, distances, track_length)
    # A dedicated payload containing geometry is one atomic map.  If that
    # geometry is corrupt, reject its turn labels as well; otherwise a stale
    # V3 Shanghai file could leave 11 brake-zone labels active after its bad
    # 250 m S/F chord was correctly rejected.
    if has_points and not geometry_ok:
        return False
    if geometry_ok:
        try:
            LEARNED_TRACK_MAPS[key] = _close(points)
            raw_dist=[float(x) for x in distances] if isinstance(distances,list) else []
            # points are persisted closed; distance axis is persisted unclosed.
            if raw_dist and len(raw_dist)==len(LEARNED_TRACK_MAPS[key]):
                raw_dist=raw_dist[:-1]
            if raw_dist and len(raw_dist)==len(LEARNED_TRACK_MAPS[key])-1:
                LEARNED_TRACK_DISTANCES[key]=tuple(raw_dist)
            if isinstance(track_length,(int,float)) and float(track_length)>1000:
                LEARNED_TRACK_LENGTHS[key]=float(track_length)
            try:
                obs=int(learning.get("accepted_clean_laps") or learning.get("observations") or 0)
            except (TypeError,ValueError):
                obs=0
            if obs>0:
                LEARNED_TRACK_OBSERVATIONS[key]=obs
            try:
                last_lap=int(learning.get("last_lap") or 0)
            except (TypeError,ValueError):
                last_lap=0
            if last_lap>0:
                LEARNED_TRACK_LAST_LAP[key]=last_lap
            fps=learning.get("recent_geometry_fingerprints")
            if isinstance(fps,list):
                clean_fps=tuple(str(x) for x in fps if isinstance(x,str) and x)
                if clean_fps:
                    LEARNED_TRACK_FINGERPRINTS[key]=clean_fps[-32:]
            loaded=True
        except (TypeError, ValueError, IndexError):
            pass
    # Pre-V5 markers did not retain physical corner start/end boundaries and
    # V4 used the old top-curvature-point selector. Re-derive them from the
    # saved geometry so V1.0.3 has one physical authority for all coaching.
    clean_turns=_clean_turns(turns) if version >= 5 else ()
    if not clean_turns and loaded and key in LEARNED_TRACK_MAPS:
        raw=list(LEARNED_TRACK_MAPS[key])
        if len(raw)>1 and raw[0]==raw[-1]:
            raw=raw[:-1]
        clean_turns=derive_physical_turns(
            key, raw,
            point_distances_m=LEARNED_TRACK_DISTANCES.get(key, ()),
            track_length_m=LEARNED_TRACK_LENGTHS.get(key),
        )
    if clean_turns:
        LEARNED_TRACK_TURNS[key]=tuple(clean_turns)
        loaded=True
    return loaded


def _write_track(track_name: object) -> Path | None:
    """Atomically persist exactly one circuit to exactly one JSON file."""
    name=_key(track_name)
    path=_track_path(name)
    if not name or path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    points=LEARNED_TRACK_MAPS.get(name, ())
    distances=LEARNED_TRACK_DISTANCES.get(name, ())
    payload={
        "version": 5,
        "track": name,
        "points": [[x, y] for x, y in points],
        "point_distances_m": list(distances),
        "track_length_m": LEARNED_TRACK_LENGTHS.get(name),
        "turns": [dict(x) for x in LEARNED_TRACK_TURNS.get(name, ())],
        "learning": {
            "accepted_clean_laps": int(LEARNED_TRACK_OBSERVATIONS.get(name, 0)),
            "last_lap": int(LEARNED_TRACK_LAST_LAP.get(name, 0)),
            "policy": "robust_running_geometry_mean_v1",
            "recent_geometry_fingerprints": list(LEARNED_TRACK_FINGERPRINTS.get(name, ())[-32:]),
        },
    }
    tmp=path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    return path


def _legacy_payloads() -> dict[str, object]:
    """Read old V1/V2 combined caches without ever writing that format again."""
    merged={}
    for path in (_CACHE_PATH, _LEGACY_CACHE_PATH):
        try:
            raw=json.loads(path.read_text(encoding='utf-8'))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            continue
        tracks=raw.get('tracks', {}) if isinstance(raw, dict) else {}
        if isinstance(tracks, dict):
            for name,item in tracks.items():
                merged.setdefault(str(name).upper(), item)
    return merged


def _load_cache() -> None:
    # V3/V4/V5: load every independent track file first.
    store=_storage_dir()
    try:
        paths=sorted(store.glob('*.json'))
    except OSError:
        paths=[]
    for path in paths:
        try:
            raw=json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(raw, dict):
            continue
        name=raw.get('track') or path.stem
        key=_key(name)
        loaded=_ingest_track_payload(name, raw)
        if not loaded and key:
            # A dedicated file is authoritative. If it is malformed, do not
            # silently resurrect an older combined-cache outline underneath it.
            _INVALID_DEDICATED_TRACKS.add(key)
        elif loaded and key:
            try:
                version=int(raw.get("version") or 0)
            except (TypeError,ValueError):
                version=0
            if version < 5:
                try:_write_track(key)
                except OSError:pass

    # One-time compatibility import: any circuit found only in a legacy combined
    # file is loaded, then immediately materialised as its own per-track file. The old
    # file is left untouched so rollback remains possible.
    for name,item in _legacy_payloads().items():
        key=_key(name)
        if key in LEARNED_TRACK_MAPS or key in LEARNED_TRACK_TURNS or key in _INVALID_DEDICATED_TRACKS:
            continue
        if _ingest_track_payload(key, item):
            try:
                _write_track(key)
            except OSError:
                pass


def _downsample(points: list[tuple[float, float]], max_points: int = 1600) -> list[tuple[float, float]]:
    if len(points) <= max_points:
        return points
    step = (len(points) - 1) / float(max_points - 1)
    out = [points[round(i * step)] for i in range(max_points)]
    out[-1] = points[-1]
    return out


def save_learned_track_map(track_name: object, points: Iterable[tuple[float, float]]) -> tuple[tuple[float, float], ...] | None:
    """Persist one complete start-line-to-start-line telemetry lap for a circuit."""
    name = _key(track_name)
    if not name:
        return None
    clean: list[tuple[float, float]] = []
    for item in points:
        try:
            x, y = float(item[0]), float(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if clean:
            dx, dy = x - clean[-1][0], y - clean[-1][1]
            if dx * dx + dy * dy < 1.0:
                continue
        clean.append((x, y))
    if len(clean) < 100:
        return None
    clean = _downsample(clean)
    learned = _close(clean)
    LEARNED_TRACK_MAPS[name] = learned
    try:
        _write_track(name)
    except OSError:
        pass
    return learned


def save_learned_track_map_samples(track_name: object, samples: object, track_length_m: object) -> tuple[tuple[float, float], ...] | None:
    """Persist a validated complete map from measured 5 m lap samples.

    This is the authoritative learner used by the live/replay dashboards. It
    rejects partial laps and asynchronous S/F position chords before writing.
    """
    name=_key(track_name)
    if not name:
        return None
    trace=measured_world_trace(samples, require_start=True)
    if not trace_is_complete(trace, track_length_m):
        return None
    # Downsample without losing the game lap-distance axis.
    if len(trace)>1600:
        step=(len(trace)-1)/1599.0
        trace=[trace[round(i*step)] for i in range(1600)]
    points=[(x,z) for _d,x,z in trace]
    distances=[float(d) for d,_x,_z in trace]
    learned=_close(points)
    LEARNED_TRACK_MAPS[name]=learned
    LEARNED_TRACK_DISTANCES[name]=tuple(distances)
    LEARNED_TRACK_LENGTHS[name]=float(track_length_m)
    turns=derive_physical_turns(name, points, point_distances_m=distances, track_length_m=float(track_length_m))
    if turns:
        LEARNED_TRACK_TURNS[name]=turns
    _INVALID_DEDICATED_TRACKS.discard(name)
    try:
        _write_track(name)
    except OSError:
        pass
    return learned



def _interp_trace_at_distances(trace: list[tuple[float,float,float]], targets: tuple[float,...]) -> list[tuple[float,float]]:
    """Interpolate a measured world trace onto the canonical lap-distance axis."""
    if len(trace)<2 or not targets:
        return []
    ds=[float(r[0]) for r in trace]
    out=[]
    j=1
    for td in targets:
        d=float(td)
        while j < len(ds) and ds[j] < d:
            j += 1
        if j >= len(ds):
            return []
        i=max(0,j-1)
        d0,d1=ds[i],ds[j]
        x0,z0=trace[i][1],trace[i][2]
        x1,z1=trace[j][1],trace[j][2]
        if d1 <= d0:
            out.append((float(x1),float(z1)))
        else:
            a=max(0.0,min(1.0,(d-d0)/(d1-d0)))
            out.append((float(x0+(x1-x0)*a),float(z0+(z1-z0)*a)))
    return out


def _blend_turn_models(old_turns, new_turns, *, alpha: float, track_length_m: float):
    """Stabilise T1..Tn while still allowing clean-data refinement.

    Turn identity never changes here. A newly derived boundary may move a little
    as the canonical path becomes less noisy, but a single lap cannot relabel or
    teleport a corner.
    """
    old=_clean_turns(old_turns)
    new=_clean_turns(new_turns)
    if not old or len(old)!=len(new):
        return tuple(new) if new else tuple(old)
    limit=max(45.0,min(110.0,float(track_length_m)*0.018))
    rows=[]
    for a,b in zip(old,new):
        row=dict(a)
        for key in ("start_m","apex_m","end_m","lap_distance_m"):
            av=a.get(key); bv=b.get(key)
            if isinstance(av,(int,float)) and isinstance(bv,(int,float)) and abs(float(bv)-float(av)) <= limit:
                row[key]=float(av)+(float(bv)-float(av))*alpha
        av=a.get("curvature_score");bv=b.get("curvature_score")
        if isinstance(av,(int,float)) and isinstance(bv,(int,float)):
            row["curvature_score"]=float(av)+(float(bv)-float(av))*alpha
        if b.get("turn_direction"):
            row["turn_direction"]=b.get("turn_direction")
        rows.append(row)
    return _clean_turns(rows)



def _geometry_fingerprint(trace: list[tuple[float,float,float]]) -> str:
    h=hashlib.sha1()
    stride=max(1,len(trace)//80)
    for d,x,z in trace[::stride]:
        h.update(f"{round(float(d),1)}:{round(float(x),1)}:{round(float(z),1)};".encode('ascii'))
    return h.hexdigest()[:20]


def clean_geometry_lap(lap: object) -> bool:
    """Return True only for laps safe to teach the persistent physical model."""
    if not isinstance(lap,dict) or lap.get("valid") is not True or lap.get("lap_start_anchored") is not True:
        return False
    blockers=("pit_lap","traffic_compromised","race_control_compromised","damage_compromised",
              "pause_compromised","replay_seek_detected","session_restart_detected")
    return not any(bool(lap.get(k)) for k in blockers)


def learn_track_model_from_clean_lap(track_name: object, lap: object, track_length_m: object):
    """Refine the one authoritative per-track geometry from another clean lap.

    The stored path is a robust running mean on the game's lap-distance axis.
    Every consumer (map markers, physical T1..Tn, live corner feedback and
    reference compilation) can therefore share one slowly improving geometry
    authority instead of independently rediscovering corners.
    """
    name=_key(track_name)
    if not name or not clean_geometry_lap(lap) or not isinstance(track_length_m,(int,float)) or float(track_length_m)<=1000:
        return None
    samples=lap.get("_samples") or {}
    trace=measured_world_trace(samples,require_start=True)
    if not trace_is_complete(trace,track_length_m):
        return None
    length=float(track_length_m)
    lap_no=lap.get("lap")
    fingerprint=_geometry_fingerprint(trace)
    if fingerprint in LEARNED_TRACK_FINGERPRINTS.get(name,()):
        return LEARNED_TRACK_MAPS.get(name)
    # First trustworthy lap establishes the canonical distance axis.
    if name not in LEARNED_TRACK_MAPS or not LEARNED_TRACK_DISTANCES.get(name):
        learned=save_learned_track_map_samples(name,samples,length)
        if learned:
            LEARNED_TRACK_OBSERVATIONS[name]=max(1,int(LEARNED_TRACK_OBSERVATIONS.get(name,0)))
            if isinstance(lap_no,int) and lap_no>0: LEARNED_TRACK_LAST_LAP[name]=lap_no
            LEARNED_TRACK_FINGERPRINTS[name]=(fingerprint,)
            try:_write_track(name)
            except OSError:pass
        return learned

    old_length=LEARNED_TRACK_LENGTHS.get(name,length)
    if abs(float(old_length)-length) > max(20.0,length*0.006):
        return None
    targets=LEARNED_TRACK_DISTANCES.get(name,())
    base=list(LEARNED_TRACK_MAPS.get(name,()))
    if base and base[0]==base[-1]: base=base[:-1]
    if not targets or len(base)!=len(targets):
        return None
    fresh=_interp_trace_at_distances(trace,targets)
    if len(fresh)!=len(base):
        return None
    deviations=[((nx-ox)**2+(nz-oz)**2)**0.5 for (ox,oz),(nx,nz) in zip(base,fresh)]
    ordered=sorted(deviations)
    median=ordered[len(ordered)//2] if ordered else 0.0
    p90=ordered[min(len(ordered)-1,int(len(ordered)*0.90))] if ordered else 0.0
    # A whole-lap displacement this large is almost certainly the wrong track,
    # stale motion data, or a broken S/F trace rather than racing-line variance.
    if median>14.0 or p90>28.0:
        return None
    obs=max(1,int(LEARNED_TRACK_OBSERVATIONS.get(name,1)))
    alpha=max(0.035,min(0.20,1.0/float(obs+1)))
    blended=[]
    max_step=8.0
    for (ox,oz),(nx,nz) in zip(base,fresh):
        dx,dz=nx-ox,nz-oz
        mag=(dx*dx+dz*dz)**0.5
        if mag>max_step and mag>0:
            scale=max_step/mag;dx*=scale;dz*=scale
        blended.append((ox+dx*alpha,oz+dz*alpha))
    new_turns=derive_physical_turns(name,blended,point_distances_m=targets,track_length_m=length)
    stable_turns=_blend_turn_models(LEARNED_TRACK_TURNS.get(name,()),new_turns,alpha=min(0.15,alpha),track_length_m=length)
    LEARNED_TRACK_MAPS[name]=_close(blended)
    LEARNED_TRACK_LENGTHS[name]=length
    if stable_turns:
        LEARNED_TRACK_TURNS[name]=stable_turns
    LEARNED_TRACK_OBSERVATIONS[name]=obs+1
    if isinstance(lap_no,int) and lap_no>0: LEARNED_TRACK_LAST_LAP[name]=lap_no
    fps=list(LEARNED_TRACK_FINGERPRINTS.get(name,()))
    fps.append(fingerprint)
    LEARNED_TRACK_FINGERPRINTS[name]=tuple(fps[-32:])
    _INVALID_DEDICATED_TRACKS.discard(name)
    try:_write_track(name)
    except OSError:pass
    return LEARNED_TRACK_MAPS[name]

def live_map_trace(samples: object) -> tuple[tuple[float,float], ...]:
    """Validated partial current-lap geometry for first-lap on-screen plotting."""
    trace=measured_world_trace(samples, require_start=True)
    if len(trace)<2:
        return ()
    # Never draw a trace containing a discontinuity; measured_world_trace returns
    # an empty list when it cannot safely repair one.
    points=[(x,z) for _d,x,z in trace]
    return tuple(points)


def get_track_map_distances(track_name: object) -> tuple[float, ...]:
    name=_key(track_name)
    return LEARNED_TRACK_DISTANCES.get(name, ()) if name else ()


def get_track_length(track_name: object) -> float | None:
    name=_key(track_name)
    return LEARNED_TRACK_LENGTHS.get(name) if name else None


def ensure_physical_turn_markers(track_name: object, *, track_length_m: object = None) -> tuple[dict[str, object], ...]:
    name=_key(track_name)
    if not name:
        return ()
    cached=LEARNED_TRACK_TURNS.get(name)
    if cached:
        return cached
    points=LEARNED_TRACK_MAPS.get(name)
    if not points:
        return ()
    raw=list(points)
    if len(raw)>1 and raw[0]==raw[-1]:
        raw=raw[:-1]
    distances=LEARNED_TRACK_DISTANCES.get(name, ())
    length=track_length_m if isinstance(track_length_m,(int,float)) else LEARNED_TRACK_LENGTHS.get(name)
    turns=derive_physical_turns(name, raw, point_distances_m=distances, track_length_m=length)
    if turns:
        LEARNED_TRACK_TURNS[name]=turns
        if isinstance(length,(int,float)) and float(length)>1000:
            LEARNED_TRACK_LENGTHS[name]=float(length)
        try:
            _write_track(name)
        except OSError:
            pass
    return LEARNED_TRACK_TURNS.get(name, ())


def save_track_turn_markers(track_name: object, turns: Iterable[object]) -> tuple[dict[str, object], ...]:
    """Persist physical T1..Tn geometry in the same per-track file."""
    name=_key(track_name)
    if not name:
        return ()
    rows=[]
    for turn in turns or ():
        get=(lambda k: turn.get(k)) if isinstance(turn,dict) else (lambda k:getattr(turn,k,None))
        cid,label,dist=get("corner_id"),get("label"),get("lap_distance_m")
        if not (isinstance(cid,int) and cid>0 and isinstance(dist,(int,float))):
            continue
        row={"corner_id":cid,"label":str(label or f"T{cid}"),"lap_distance_m":float(dist)}
        for key in ("start_m","apex_m","end_m","curvature_score"):
            value=get(key)
            if isinstance(value,(int,float)):
                row[key]=float(value)
        direction=get("turn_direction")
        if isinstance(direction,str) and direction:
            row["turn_direction"]=direction
        rows.append(row)
    value=_clean_turns(rows)
    if value and value!=LEARNED_TRACK_TURNS.get(name):
        LEARNED_TRACK_TURNS[name]=value
        try:_write_track(name)
        except OSError:pass
    return LEARNED_TRACK_TURNS.get(name,value)

def get_track_turn_markers(track_name: object) -> tuple[dict[str, object], ...]:
    name = _key(track_name)
    return LEARNED_TRACK_TURNS.get(name, ()) if name else ()


def get_track_map(track_name: object, *, allow_fallback: bool = False):
    """Return learned real geometry; optional coarse fallback is legacy-only."""
    name = _key(track_name)
    if not name:
        return None
    learned = LEARNED_TRACK_MAPS.get(name)
    if learned:
        return learned
    return TRACK_MAPS.get(name) if allow_fallback else None


def cache_path(track_name: object = None) -> Path:
    """Return the per-track file path, or the track-store directory."""
    if track_name is None:
        return _storage_dir()
    return _track_path(track_name) or _storage_dir()


_load_cache()
