"""Persistent LIVE-only driver profile and cross-session performance history.

Dependency-free SQLite store used by the Performance Hub. Only live F1 game
sessions may be written here; replay data is deliberately excluded by the
receiver authority gate. Database work happens only at session boundaries.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import hashlib
import math
from pathlib import Path
import sqlite3
from typing import Any

DB_SCHEMA_VERSION = 6




def _profile_stamp(value: Any) -> str:
    if not value:
        return "--"
    try:
        from .driver_profiles import DriverProfileStore
        from .user_time import format_profile_timestamp
        profile=DriverProfileStore().active_profile() or {}
        return format_profile_timestamp(value, profile.get("time_zone") or "UTC")
    except Exception:
        return str(value)[:19].replace("T"," ")




def _merge_rows_by_key(old_rows: Any, new_rows: Any, key: str) -> list[dict[str, Any]]:
    """Merge persisted per-lap rows without losing an earlier stint/garage segment."""
    merged: dict[Any, dict[str, Any]] = {}
    order: list[Any] = []
    for rows in (old_rows, new_rows):
        for raw in rows or ():
            if not isinstance(raw, dict):
                continue
            ident = raw.get(key)
            if ident is None:
                continue
            if ident not in merged:
                order.append(ident)
                merged[ident] = {}
            base = dict(merged[ident])
            base.update(raw)
            merged[ident] = base
    def sort_key(v):
        try:
            return (0, int(v))
        except Exception:
            return (1, str(v))
    return [merged[k] for k in sorted(order, key=sort_key) if k in merged]


def _merge_live_coach_snapshots(old: dict[str, Any] | None, new: dict[str, Any] | None) -> dict[str, Any]:
    """Preserve earlier laps when the game returns to garage mid-session.

    F1 can restart the live telemetry/performance accumulator while retaining the
    same logical Time Trial session/lap counter.  The Performance Hub row is an
    idempotent upsert, so replacing coach_json with the newest accumulator used to
    drop the earlier laps.  Merge only lap-owned persisted evidence here; current
    aggregate/session fields still come from the newest authoritative snapshot.
    """
    old = dict(old or {})
    new = dict(new or {})
    if not old:
        return new
    out = dict(old)
    out.update(new)

    old_store = old.get('lap_telemetry') if isinstance(old.get('lap_telemetry'), dict) else {}
    new_store = new.get('lap_telemetry') if isinstance(new.get('lap_telemetry'), dict) else {}
    lap_store = {str(k): dict(v) if isinstance(v, dict) else v for k, v in old_store.items()}
    for k, v in new_store.items():
        lap_store[str(k)] = dict(v) if isinstance(v, dict) else v
    out['lap_telemetry'] = lap_store

    out['lap_facts'] = _merge_rows_by_key(old.get('lap_facts'), new.get('lap_facts'), 'lap')
    out['live_lap_intelligence'] = _merge_rows_by_key(old.get('live_lap_intelligence'), new.get('live_lap_intelligence'), 'lap_number')
    out['lap_comparisons'] = _merge_rows_by_key(old.get('lap_comparisons'), new.get('lap_comparisons'), 'lap')

    # Preserve/merge the derived review as well. The live accumulator can rebuild
    # performance_review from only the post-garage stint before the merged
    # live_lap_intelligence is written. Without this merge the VIEW selector can
    # shrink to only the latest laps even though lap_telemetry/reference options
    # still contain the full logical session. The read path below also detects and
    # repairs stale reviews, so old V2.0.5.8/.9 sessions benefit immediately.
    opr = old.get('performance_review') if isinstance(old.get('performance_review'), dict) else {}
    npr = new.get('performance_review') if isinstance(new.get('performance_review'), dict) else {}
    if opr or npr:
        pr = dict(opr); pr.update(npr)
        pr['laps'] = _merge_rows_by_key(opr.get('laps'), npr.get('laps'), 'lap')
        pr['lap_reviews'] = _merge_rows_by_key(opr.get('lap_reviews'), npr.get('lap_reviews'), 'lap')
        out['performance_review'] = pr

    # Preserve the fullest geometry snapshot. A garage transition can briefly
    # rebuild a report before the shared map/corner authority has republished.
    old_geo = old.get('track_geometry_snapshot') if isinstance(old.get('track_geometry_snapshot'), dict) else {}
    new_geo = new.get('track_geometry_snapshot') if isinstance(new.get('track_geometry_snapshot'), dict) else {}
    old_pts = old_geo.get('points') if isinstance(old_geo.get('points'), list) else []
    new_pts = new_geo.get('points') if isinstance(new_geo.get('points'), list) else []
    if len(old_pts) > len(new_pts):
        out['track_geometry_snapshot'] = old_geo

    # Keep counts monotonic and consistent with the merged lap-owned evidence.
    fact_count = len(out.get('lap_facts') or [])
    telem_count = len(out.get('lap_telemetry') or {})
    out['lap_count'] = max(int(old.get('lap_count') or 0), int(new.get('lap_count') or 0), fact_count, telem_count)
    out['timed_valid_lap_count'] = max(int(old.get('timed_valid_lap_count') or 0), int(new.get('timed_valid_lap_count') or 0), telem_count)

    oq = old.get('coaching_data_quality') if isinstance(old.get('coaching_data_quality'), dict) else {}
    nq = new.get('coaching_data_quality') if isinstance(new.get('coaching_data_quality'), dict) else {}
    if oq or nq:
        q = dict(oq); q.update(nq)
        eligible = sorted({int(x) for x in (oq.get('eligible_laps') or []) + (nq.get('eligible_laps') or []) if isinstance(x, int)})
        excluded = _merge_rows_by_key(oq.get('excluded_laps'), nq.get('excluded_laps'), 'lap')
        dmg = sorted({int(x) for x in (oq.get('damage_override_laps') or []) + (nq.get('damage_override_laps') or []) if isinstance(x, int)})
        q['eligible_laps'] = eligible
        q['excluded_laps'] = excluded
        q['damage_override_laps'] = dmg
        out['coaching_data_quality'] = q
        out['eligible_lap_count'] = max(int(old.get('eligible_lap_count') or 0), int(new.get('eligible_lap_count') or 0), len(eligible))

    return out


def _merge_live_session_summary(old: dict[str, Any] | None, new: dict[str, Any] | None) -> dict[str, Any]:
    old = dict(old or {})
    new = dict(new or {})
    if not old:
        return new
    out = dict(old); out.update(new)
    out['laps_completed'] = max(int(old.get('laps_completed') or 0), int(new.get('laps_completed') or 0))
    for k in ('warnings', 'corner_cutting_warnings', 'penalties_s', 'pit_stops'):
        vals=[v for v in (old.get(k), new.get(k)) if _finite(v)]
        if vals:
            out[k]=max(vals)
    vals=[float(v) for v in (old.get('best_lap_s'), new.get('best_lap_s')) if _finite(v) and float(v)>0]
    if vals:
        out['best_lap_s']=min(vals)
    return out


GAME_MODE_NAMES = {
    4: "Grand Prix", 5: "Time Trial", 6: "Splitscreen", 7: "Online Custom",
    15: "Online Weekly Event", 17: "Story Mode", 27: "My Team Career",
    28: "Driver Career", 29: "Online Career", 30: "Challenge Career",
    75: "Story Mode (APXGP)", 127: "Benchmark",
}

def session_group(session_type: Any) -> str:
    name = str(session_type or "").strip().lower()
    if "practice" in name:
        return "Practice"
    if "time trial" in name:
        return "Time Trial"
    if "qual" in name or "shootout" in name:
        return "Qualifying" if "shootout" not in name else "Sprint"
    if "sprint" in name:
        return "Sprint"
    if name.startswith("race") or name == "race":
        return "Race"
    return "Other"

def game_mode_name(value: Any) -> str:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return "Unknown"
    return GAME_MODE_NAMES.get(v, f"Game Mode {v}")


def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _name(v: Any) -> str | None:
    n = getattr(v, "name", None)
    return str(n) if n else (str(v) if isinstance(v, str) and v else None)


def _assist_label(key: str, value: Any) -> str:
    labels={
        "traction_control":"Traction Control", "anti_lock_brakes":"ABS",
        "gearbox_assist":"Gearbox", "steering_assist":"Steering Assist",
        "braking_assist":"Braking Assist", "pit_assist":"Pit Assist",
        "pit_release_assist":"Pit Release Assist", "ers_assist":"ERS Assist",
        "drs_assist":"DRS Assist", "custom_setup":"Custom Setup",
        "equal_car_performance":"Equal Performance",
    }
    label=labels.get(str(key), str(key).replace("_"," ").title())
    if value is None:
        return f"{label}: N/A"
    if key=="traction_control":
        try: state={0:"Off",1:"Medium",2:"Full"}.get(int(value),str(value))
        except Exception: state=str(value)
    elif key=="gearbox_assist":
        try: state={0:"Manual",1:"Manual + Suggested",2:"Automatic"}.get(int(value),str(value))
        except Exception: state=str(value)
    elif key=="braking_assist":
        try: state={0:"Off",1:"Low",2:"Medium",3:"High"}.get(int(value),str(value))
        except Exception: state=str(value)
    elif key in ("anti_lock_brakes","steering_assist","pit_assist","pit_release_assist",
                 "ers_assist","drs_assist","custom_setup","equal_car_performance"):
        try: state="On" if int(value) else "Off"
        except Exception: state=str(value)
    else:
        state=str(value)
    return f"{label}: {state}"


def _review_result_summary(payload: dict[str, Any], coach: dict[str, Any], view_lap: int | None) -> dict[str, Any]:
    """Build a game-style deterministic session/lap result summary.

    Uses already persisted authoritative lap facts only.  Reference gap is
    recalculated from the currently selected visual reference on every request.
    """
    session=payload.get("session") if isinstance(payload.get("session"),dict) else {}
    facts=[x for x in (coach.get("lap_facts") or []) if isinstance(x,dict)]
    lap_store=coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"),dict) else {}
    selected=None
    if isinstance(view_lap,int):
        selected=next((x for x in facts if x.get("lap")==view_lap),None)
        if selected is None:
            row=lap_store.get(str(view_lap)) or lap_store.get(view_lap)
            selected=dict(row) if isinstance(row,dict) else None
    else:
        timed=[x for x in facts if _finite(x.get("lap_time_s")) and float(x.get("lap_time_s"))>0]
        selected=min(timed,key=lambda x:float(x["lap_time_s"]),default=None)
        if selected is None and _finite(session.get("best_lap_s")):
            selected={"lap_time_s":session.get("best_lap_s"),"valid":True}
    current_time=(selected or {}).get("lap_time_s")
    vr=payload.get("visual_reference") if isinstance(payload.get("visual_reference"),dict) else {}
    ref_time=vr.get("lap_time_s")
    if not _finite(ref_time): ref_time=vr.get("best_lap_s")
    if not _finite(ref_time) and payload.get("reference_mode")=="recorded": ref_time=session.get("reference_lap_s")
    gap=round(float(current_time)-float(ref_time),6) if _finite(current_time) and _finite(ref_time) else None
    assists=dict((selected or {}).get("assists") or {})
    if not assists and facts:
        # Session view: report the stable assist configuration if one was captured.
        for x in facts:
            if isinstance(x.get("assists"),dict) and x.get("assists"):
                assists=dict(x["assists"]); break
    summary=session.get("summary") if isinstance(session.get("summary"),dict) else {}
    warnings=(selected or {}).get("warnings") if isinstance(view_lap,int) else summary.get("warnings",session.get("warnings"))
    penalties=(selected or {}).get("penalties_s") if isinstance(view_lap,int) else summary.get("penalties_s",session.get("penalties_s"))
    corner_warn=(selected or {}).get("corner_cutting_warnings") if isinstance(view_lap,int) else summary.get("corner_cutting_warnings")
    valid=(selected or {}).get("valid") if isinstance(selected,dict) else None
    pot=coach.get("potential") if isinstance(coach.get("potential"),dict) else {}
    theoretical=pot.get("potential_lap_s") if not isinstance(view_lap,int) else None
    if not _finite(theoretical) and not isinstance(view_lap,int): theoretical=session.get("potential_lap_s")
    return {
        "scope":"lap" if isinstance(view_lap,int) else "session",
        "lap":view_lap if isinstance(view_lap,int) else (selected or {}).get("lap"),
        "lap_time_s":current_time,
        "sector1_time_s":(selected or {}).get("sector1_time_s"),
        "sector2_time_s":(selected or {}).get("sector2_time_s"),
        "sector3_time_s":(selected or {}).get("sector3_time_s"),
        "reference_label":vr.get("label") or vr.get("kind") or "Recorded reference",
        "reference_lap_time_s":ref_time,
        "gap_to_selected_reference_s":gap,
        "valid":valid,
        "warnings":warnings,
        "corner_cutting_warnings":corner_warn,
        "penalties_s":penalties,
        "assists":assists,
        "assist_labels":[_assist_label(k,v) for k,v in assists.items()],
        "theoretical_potential_lap_s":theoretical,
        "potential_gain_s":session.get("potential_gain_s") if not isinstance(view_lap,int) else None,
    }



def _session_quick_glance(payload: dict[str, Any], coach: dict[str, Any]) -> dict[str, Any]:
    """Return a game-style all-laps table for the selected stored session.

    This is a read-only presentation model. It never rewrites persisted history.
    Gaps are recalculated against the currently selected visual reference.
    """
    session=payload.get("session") if isinstance(payload.get("session"),dict) else {}
    facts=[dict(x) for x in (coach.get("lap_facts") or []) if isinstance(x,dict)]
    lap_store=coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"),dict) else {}
    by_lap={}
    for x in facts:
        try: lap_no=int(x.get("lap"))
        except (TypeError,ValueError): continue
        by_lap[lap_no]=x
    for key,row in lap_store.items():
        if not isinstance(row,dict): continue
        try: lap_no=int(row.get("lap",key))
        except (TypeError,ValueError): continue
        base=by_lap.setdefault(lap_no,{"lap":lap_no})
        for k,v in row.items():
            if base.get(k) is None:
                base[k]=v
    # Score display uses the same persisted lap-level scoring result that
    # drives the individual LAP TECHNIQUE view. It does not recalculate score,
    # confidence, or eligibility.
    review=payload.get("review") if isinstance(payload.get("review"),dict) else {}
    score_by_lap={}
    for item in review.get("lap_reviews") or []:
        if not isinstance(item,dict):
            continue
        summary=item.get("summary") if isinstance(item.get("summary"),dict) else item
        lap=item.get("lap") if isinstance(item.get("lap"),int) else summary.get("lap")
        if not isinstance(lap,int):
            continue
        score_by_lap[int(lap)]={
            "score":summary.get("score"),
            "confidence":summary.get("confidence"),
            "coverage":summary.get("coverage"),
            "scored_corners":summary.get("scored_corners", summary.get("scored_corner_count")),
            "eligible_corners":summary.get("eligible_corners", summary.get("eligible_corner_count")),
            "status":summary.get("status"),
            "quality_reasons":list(summary.get("quality_reasons") or item.get("quality_reasons") or []),
        }
    for summary in review.get("laps") or []:
        if not isinstance(summary,dict) or not isinstance(summary.get("lap"),int):
            continue
        score_by_lap.setdefault(int(summary["lap"]),{
            "score":summary.get("score"),
            "confidence":summary.get("confidence"),
            "coverage":summary.get("coverage"),
            "scored_corners":summary.get("scored_corners", summary.get("scored_corner_count")),
            "eligible_corners":summary.get("eligible_corners", summary.get("eligible_corner_count")),
            "status":summary.get("status"),
            "quality_reasons":list(summary.get("quality_reasons") or []),
        })
    rows=[]
    vr=payload.get("visual_reference") if isinstance(payload.get("visual_reference"),dict) else {}
    ref_time=vr.get("lap_time_s")
    if not _finite(ref_time): ref_time=vr.get("best_lap_s")
    if not _finite(ref_time) and payload.get("reference_mode")=="recorded": ref_time=session.get("reference_lap_s")
    for lap_no in sorted(by_lap):
        x=by_lap[lap_no]
        lt=x.get("lap_time_s")
        if not _finite(lt) or float(lt)<=0:
            continue
        assists=x.get("assists") if isinstance(x.get("assists"),dict) else {}
        gap=round(float(lt)-float(ref_time),6) if _finite(ref_time) else None
        score_row=score_by_lap.get(lap_no) or {}
        scored_corners=score_row.get("scored_corners")
        eligible_corners=score_row.get("eligible_corners")
        coverage=score_row.get("coverage")
        score_reason=None
        if not _finite(score_row.get("score")):
            if x.get("valid") is False:
                score_reason="invalid lap"
            elif score_row.get("quality_reasons"):
                # Game validity and coaching eligibility are separate. Prefer the
                # concrete quality-gate reason over the corner-coverage fallback so
                # a VALID lap with 14/14 measured corners explains why its persisted
                # score was intentionally suppressed.
                score_reason="quality excluded: " + "; ".join(str(v).replace("_"," ") for v in score_row.get("quality_reasons") if v)
            elif isinstance(eligible_corners,(int,float)) and int(eligible_corners)>0:
                sc=int(scored_corners or 0); ec=int(eligible_corners)
                cov=float(coverage) if _finite(coverage) else (float(sc)/float(ec) if ec else 0.0)
                if sc < 2:
                    score_reason=f"only {sc}/{ec} corners scored; at least 2 required"
                elif cov < 0.60:
                    score_reason=f"{sc}/{ec} corners scored ({cov*100:.0f}% coverage); 60% required"
                else:
                    score_reason="stored lap score unavailable despite sufficient recorded coverage"
            else:
                score_reason="no stored corner-scoring coverage for this lap"
        rows.append({
            "lap":lap_no, "lap_time_s":lt,
            "score":score_row.get("score"),
            "score_confidence":score_row.get("confidence"),
            "score_coverage":coverage,
            "score_scored_corners":scored_corners,
            "score_eligible_corners":eligible_corners,
            "score_status":score_row.get("status"),
            "score_reason":score_reason,
            "gap_to_selected_reference_s":gap,
            "sector1_time_s":x.get("sector1_time_s"),
            "sector2_time_s":x.get("sector2_time_s"),
            "sector3_time_s":x.get("sector3_time_s"),
            "valid":x.get("valid"),
            "warnings":x.get("warnings"),
            "penalties_s":x.get("penalties_s"),
            "corner_cutting_warnings":x.get("corner_cutting_warnings"),
            "assists":dict(assists),
            "assist_labels":[_assist_label(k,v) for k,v in assists.items()],
        })
    valid_rows=[x for x in rows if x.get("valid") is not False]
    sector_bests=[]
    for key in ("sector1_time_s","sector2_time_s","sector3_time_s"):
        vals=[float(x[key]) for x in valid_rows if _finite(x.get(key)) and float(x[key])>0]
        sector_bests.append(min(vals) if vals else None)
    raw_theoretical=sum(sector_bests) if all(_finite(x) for x in sector_bests) else None
    best=min(valid_rows,key=lambda x:float(x["lap_time_s"]),default=None) if valid_rows else (min(rows,key=lambda x:float(x["lap_time_s"]),default=None) if rows else None)
    best_time=float(best["lap_time_s"]) if isinstance(best,dict) and _finite(best.get("lap_time_s")) else None
    theoretical=min(float(raw_theoretical),best_time) if _finite(raw_theoretical) and _finite(best_time) else (best_time if _finite(best_time) and raw_theoretical is None else raw_theoretical)
    return {
        "rows":rows,
        "reference_label":vr.get("label") or vr.get("kind") or "Recorded reference",
        "reference_lap_time_s":ref_time,
        "best_lap":best,
        "theoretical_lap_s":theoretical,
        "raw_sector_theoretical_lap_s":raw_theoretical,
        "theoretical_guarded_by_best_lap":bool(_finite(raw_theoretical) and _finite(best_time) and float(raw_theoretical)>float(best_time)),
        "theoretical_sectors_s":sector_bests,
    }

def driver_profile_from_state(state: Any) -> dict[str, Any]:
    car = getattr(state, "player", None)
    ident = getattr(car, "identity", None) if car is not None else None
    session = getattr(state, "session", None)
    profile = {
        "name": getattr(ident, "name", None),
        "driver_id": getattr(ident, "driver_id", None),
        "race_number": getattr(ident, "race_number", None),
        "nationality_id": getattr(ident, "nationality_id", None),
        "platform_id": getattr(ident, "platform_id", None),
        "team_id": getattr(ident, "team_id", None),
        "team_name": _name(getattr(ident, "team", None)),
        "my_team": getattr(ident, "my_team", None),
        "ai_controlled": getattr(ident, "ai_controlled", None),
        "game_year": getattr(session, "game_year", None),
        "game_version": getattr(session, "game_version", None),
    }
    return profile




def _unknown_track_value(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"", "unknown", "-1", "none", "n/a"}

def _known_track_identity(track_name: Any, track_id: Any) -> tuple[str | None, str | None]:
    name = None if _unknown_track_value(track_name) else str(track_name).strip()
    tid = None if _unknown_track_value(track_id) else str(track_id).strip()
    return name, tid

def _known_session_type(value: Any) -> str | None:
    text = str(value or "").strip()
    return None if text.lower() in {"", "unknown", "none", "n/a", "--"} else text

def _merge_duplicate_session_rows(rows: list[sqlite3.Row]) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    summary: dict[str, Any] = {}
    coach: dict[str, Any] = {}
    created: str | None = None
    for row in sorted(rows, key=lambda r: str(r["created_utc"] or "")):
        try:
            rs = json.loads(row["summary_json"] or "{}")
        except Exception:
            rs = {}
        try:
            rc = json.loads(row["coach_json"] or "{}")
        except Exception:
            rc = {}
        summary = _merge_live_session_summary(summary, rs)
        coach = _merge_live_coach_snapshots(coach, rc)
        if created is None or str(row["created_utc"] or "") < created:
            created = str(row["created_utc"] or "") or created
    return summary, coach, created

def _profile_key(profile: dict[str, Any]) -> str:
    # Name + race number is stable for the user's F1 profile while driver_id alone
    # may describe a built-in driver. Include platform when the game provides it.
    return "|".join(str(profile.get(k) if profile.get(k) is not None else "") for k in ("name", "race_number", "platform_id")) or "local-driver"


class PerformanceHistoryStore:
    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            from .app_paths import PERFORMANCE_DB
            path = PERFORMANCE_DB
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=5.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        self._schema(con)
        return con

    @staticmethod
    def _schema(con: sqlite3.Connection) -> None:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS drivers(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_key TEXT NOT NULL UNIQUE,
          name TEXT, driver_id INTEGER, race_number INTEGER, nationality_id INTEGER,
          platform_id INTEGER, team_id INTEGER, team_name TEXT, my_team INTEGER,
          ai_controlled INTEGER, game_year INTEGER, game_version TEXT,
          first_seen_utc TEXT NOT NULL, last_seen_utc TEXT NOT NULL,
          profile_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_profiles(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          created_utc TEXT NOT NULL,
          last_used_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_key TEXT NOT NULL UNIQUE,
          driver_fk INTEGER NOT NULL,
          user_profile_fk INTEGER,
          session_uid TEXT, created_utc TEXT NOT NULL,
          track_id TEXT, track_name TEXT, session_type TEXT,
          session_group TEXT, game_mode INTEGER, game_mode_name TEXT,
          result_status TEXT, position INTEGER, grid_position INTEGER,
          laps_completed INTEGER, best_lap_s REAL, average_lap_s REAL,
          potential_lap_s REAL, potential_gain_s REAL, reference_lap_s REAL,
          reference_gap_s REAL, potential_vs_reference_s REAL,
          warnings INTEGER, penalties_s INTEGER, pit_stops INTEGER,
          max_tyre_wear REAL, max_tyre_temp REAL,
          summary_json TEXT NOT NULL, coach_json TEXT NOT NULL,
          FOREIGN KEY(driver_fk) REFERENCES drivers(id),
          FOREIGN KEY(user_profile_fk) REFERENCES user_profiles(id)
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_driver_track ON sessions(driver_fk,track_name,created_utc);
        CREATE INDEX IF NOT EXISTS idx_sessions_uid ON sessions(session_uid);
        """)
        # V3: session identity is driver-scoped. Older builds used a globally
        # unique session key, so replaying/testing the same EA session identity
        # with another driver could move the row to the newest driver via the
        # ON CONFLICT update. Prefix all legacy keys with driver_fk once.
        version_row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        try:
            old_version = int(version_row[0]) if version_row else 0
        except (TypeError, ValueError):
            old_version = 0
        if old_version < 3:
            rows = con.execute("SELECT id,driver_fk,session_key FROM sessions").fetchall()
            for row in rows:
                prefix = f"{int(row['driver_fk'])}|"
                key = str(row['session_key'] or '')
                if not key.startswith(prefix):
                    con.execute("UPDATE sessions SET session_key=? WHERE id=?", (prefix + key, int(row['id'])))
        if old_version < 4:
            cols={str(r[1]) for r in con.execute("PRAGMA table_info(sessions)").fetchall()}
            for col,decl in (("user_profile_fk","INTEGER"),("session_group","TEXT"),("game_mode","INTEGER"),("game_mode_name","TEXT")):
                if col not in cols:
                    con.execute(f"ALTER TABLE sessions ADD COLUMN {col} {decl}")
            # Legacy history was keyed by in-game participant identity. V4 moves
            # ownership to a local human profile, so all existing sessions are
            # intentionally merged into one local profile until the user creates
            # additional profiles. This prevents Verstappen/Antonelli/etc. from
            # being treated as different people when the same human drove them.
            existing = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            if existing:
                row=con.execute("SELECT id FROM user_profiles ORDER BY id LIMIT 1").fetchone()
                if row:
                    pid=int(row[0])
                else:
                    now=datetime.now(timezone.utc).isoformat()
                    con.execute("INSERT INTO user_profiles(name,created_utc,last_used_utc) VALUES(?,?,?)",("Local Driver",now,now))
                    pid=int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
                con.execute("UPDATE sessions SET user_profile_fk=COALESCE(user_profile_fk,?)",(pid,))
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('active_user_profile_id',?)",(str(pid),))
            rows=con.execute("SELECT id,session_type,coach_json FROM sessions").fetchall()
            for r in rows:
                gm=None
                try:
                    coach=json.loads(r['coach_json'] or '{}')
                    ctx=coach.get('event_context') if isinstance(coach.get('event_context'),dict) else {}
                    gm=ctx.get('game_mode')
                except Exception:
                    pass
                con.execute("UPDATE sessions SET session_group=?,game_mode=?,game_mode_name=? WHERE id=?",(session_group(r['session_type']),gm,game_mode_name(gm),int(r['id'])))
        if old_version < 6:
            # V6: authoritative EA session identity is profile + session UID.
            # Earlier V5 also grouped by session_type, but that field can be
            # temporarily missing immediately after an application restart. That
            # allowed one physical F1 session to split into Unknown and known-track
            # rows. Reconcile across provisional/known session_type values only
            # when the UID resolves to one unambiguous known track and at most one
            # known session type.
            groups = con.execute("""
                SELECT user_profile_fk,session_uid,COUNT(*) n
                FROM sessions
                WHERE session_uid IS NOT NULL AND trim(session_uid)<>''
                GROUP BY user_profile_fk,session_uid
                HAVING COUNT(*)>1
            """).fetchall()
            for grp in groups:
                rows = con.execute("""
                    SELECT * FROM sessions
                    WHERE user_profile_fk IS ? AND session_uid=?
                    ORDER BY created_utc,id
                """, (grp['user_profile_fk'], grp['session_uid'])).fetchall()
                known=[]
                known_types=[]
                for r in rows:
                    name,tid=_known_track_identity(r['track_name'],r['track_id'])
                    if name or tid:
                        known.append((name,tid,r))
                    st=_known_session_type(r['session_type'])
                    if st:
                        known_types.append(st)
                if not known:
                    continue
                names={x[0].lower() for x in known if x[0]}
                tids={x[1] for x in known if x[1]}
                type_keys={x.lower() for x in known_types}
                if len(names)>1 or (not names and len(tids)>1) or len(type_keys)>1:
                    continue
                resolved_name=next((x[0] for x in known if x[0]),None)
                resolved_id=next((x[1] for x in known if x[1]),None)
                resolved_type=next((x for x in known_types),None)
                compatible=[]
                for r in rows:
                    name,tid=_known_track_identity(r['track_name'],r['track_id'])
                    st=_known_session_type(r['session_type'])
                    if name and resolved_name and name.lower()!=resolved_name.lower():
                        continue
                    if not resolved_name and tid and resolved_id and tid!=resolved_id:
                        continue
                    if st and resolved_type and st.lower()!=resolved_type.lower():
                        continue
                    compatible.append(r)
                if len(compatible)<2:
                    continue
                merged_summary,merged_coach,created=_merge_duplicate_session_rows(compatible)
                target=next((x[2] for x in reversed(known) if (resolved_name and x[0] and x[0].lower()==resolved_name.lower()) or (not resolved_name and x[1]==resolved_id)),compatible[-1])
                best_vals=[float(r['best_lap_s']) for r in compatible if _finite(r['best_lap_s']) and float(r['best_lap_s'])>0]
                pot_vals=[float(r['potential_lap_s']) for r in compatible if _finite(r['potential_lap_s']) and float(r['potential_lap_s'])>0]
                laps=max([int(r['laps_completed'] or 0) for r in compatible] or [0])
                canonical_track=resolved_name or resolved_id or ''
                canonical_type=resolved_type or _known_session_type(target['session_type']) or ''
                canonical_key=f"{int(target['user_profile_fk'])}|{target['session_uid']}|{canonical_track}|{canonical_type}"
                ids=[int(r['id']) for r in compatible if int(r['id'])!=int(target['id'])]
                if ids:
                    con.execute(f"DELETE FROM sessions WHERE id IN ({','.join('?'*len(ids))})",ids)
                con.execute("""UPDATE sessions SET session_key=?,created_utc=?,track_id=?,track_name=?,session_type=?,
                    session_group=?,laps_completed=?,best_lap_s=?,potential_lap_s=?,summary_json=?,coach_json=? WHERE id=?""",
                    (canonical_key,created or target['created_utc'],resolved_id,resolved_name,canonical_type or None,
                     session_group(canonical_type or None),laps,
                     min(best_vals) if best_vals else target['best_lap_s'],
                     min(pot_vals) if pot_vals else target['potential_lap_s'],
                     json.dumps(merged_summary,separators=(',',':'),default=str),
                     json.dumps(merged_coach,separators=(',',':'),default=str),int(target['id'])))

        # Create indexes that depend on V4 columns only after any legacy table
        # has been ALTERed. CREATE TABLE IF NOT EXISTS never adds new columns,
        # so creating this index earlier crashes existing V1/V2/V3 databases.
        con.execute("CREATE INDEX IF NOT EXISTS idx_sessions_profile_track ON sessions(user_profile_fk,track_name,created_utc)")
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(DB_SCHEMA_VERSION),))
        con.commit()

    def user_profiles(self) -> list[dict[str, Any]]:
        with self._connect() as con:
            return [dict(r) for r in con.execute("SELECT * FROM user_profiles ORDER BY last_used_utc DESC,name COLLATE NOCASE").fetchall()]

    def create_user_profile(self, name: str) -> int:
        clean = " ".join(str(name or "").strip().split())
        if not clean:
            raise ValueError("Profile name is required")
        now=datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            row=con.execute("SELECT id FROM user_profiles WHERE lower(name)=lower(?)",(clean,)).fetchone()
            if row:
                pid=int(row[0])
            else:
                con.execute("INSERT INTO user_profiles(name,created_utc,last_used_utc) VALUES(?,?,?)",(clean,now,now))
                pid=int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
            con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('active_user_profile_id',?)",(str(pid),))
            con.commit()
            return pid

    def create_distinct_user_profile(self, name: str) -> int:
        """Create a new Performance History owner even when the display name repeats.

        Person-level Driver IDs are the real Race Engineer identity. The legacy
        Performance History schema requires unique user-profile names, so a
        harmless numeric suffix is added only to this internal compatibility
        owner when necessary. Existing owners are never reused.
        """
        clean = " ".join(str(name or "").strip().split())
        if not clean:
            raise ValueError("Profile name is required")
        now=datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            candidate=clean
            suffix=2
            while con.execute("SELECT 1 FROM user_profiles WHERE lower(name)=lower(?)",(candidate,)).fetchone():
                candidate=f"{clean} ({suffix})"
                suffix+=1
            con.execute("INSERT INTO user_profiles(name,created_utc,last_used_utc) VALUES(?,?,?)",(candidate,now,now))
            pid=int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
            con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('active_user_profile_id',?)",(str(pid),))
            con.commit()
            return pid

    def delete_user_profile(self, profile_id: int) -> dict[str, int | bool]:
        """Delete one local human Performance Hub owner and all owned sessions.

        Game-driver rows are shared lookup identities, so only rows left orphaned
        after removing the owner's sessions are cleaned. Other human owners and
        their sessions are never touched.
        """
        try:
            pid = int(profile_id)
        except (TypeError, ValueError):
            return {"deleted": False, "sessions": 0}
        with self._connect() as con:
            if not con.execute("SELECT 1 FROM user_profiles WHERE id=?", (pid,)).fetchone():
                return {"deleted": False, "sessions": 0}
            session_count = int(con.execute(
                "SELECT COUNT(*) FROM sessions WHERE user_profile_fk=?", (pid,)
            ).fetchone()[0])
            con.execute("DELETE FROM sessions WHERE user_profile_fk=?", (pid,))
            con.execute("DELETE FROM user_profiles WHERE id=?", (pid,))
            # Remove game-identity rows no remaining session references.
            con.execute("DELETE FROM drivers WHERE id NOT IN (SELECT DISTINCT driver_fk FROM sessions)")

            active = con.execute("SELECT value FROM meta WHERE key='active_user_profile_id'").fetchone()
            active_deleted = False
            if active:
                try:
                    active_deleted = int(active[0]) == pid
                except (TypeError, ValueError):
                    active_deleted = True
            if active_deleted:
                replacement = con.execute(
                    "SELECT id FROM user_profiles ORDER BY last_used_utc DESC,id LIMIT 1"
                ).fetchone()
                if replacement:
                    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('active_user_profile_id',?)",
                                (str(int(replacement[0])),))
                else:
                    con.execute("DELETE FROM meta WHERE key='active_user_profile_id'")

            preferred = con.execute("SELECT value FROM meta WHERE key='preferred_driver_id'").fetchone()
            preferred_valid = False
            if preferred:
                try:
                    preferred_valid = bool(con.execute(
                        "SELECT 1 FROM drivers WHERE id=?", (int(preferred[0]),)
                    ).fetchone())
                except (TypeError, ValueError):
                    preferred_valid = False
            if not preferred_valid:
                replacement_driver = con.execute(
                    "SELECT driver_fk FROM sessions ORDER BY created_utc DESC,id DESC LIMIT 1"
                ).fetchone()
                if replacement_driver:
                    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('preferred_driver_id',?)",
                                (str(int(replacement_driver[0])),))
                else:
                    con.execute("DELETE FROM meta WHERE key='preferred_driver_id'")
            con.commit()
            return {"deleted": True, "sessions": session_count}

    def rename_user_profile(self, profile_id: int, name: str) -> bool:
        clean=" ".join(str(name or "").strip().split())
        if not clean:
            return False
        with self._connect() as con:
            try:
                cur=con.execute("UPDATE user_profiles SET name=? WHERE id=?",(clean,int(profile_id)))
                con.commit()
                return cur.rowcount>0
            except sqlite3.IntegrityError:
                return False

    def active_user_profile_id(self) -> int | None:
        with self._connect() as con:
            row=con.execute("SELECT value FROM meta WHERE key='active_user_profile_id'").fetchone()
            if row:
                try:
                    pid=int(row[0])
                    if con.execute("SELECT 1 FROM user_profiles WHERE id=?",(pid,)).fetchone():
                        return pid
                except (TypeError,ValueError):
                    pass
            row=con.execute("SELECT id FROM user_profiles ORDER BY last_used_utc DESC,id LIMIT 1").fetchone()
            return int(row[0]) if row else None

    def set_active_user_profile(self, profile_id: int) -> bool:
        try: pid=int(profile_id)
        except (TypeError,ValueError): return False
        now=datetime.now(timezone.utc).isoformat()
        with self._connect() as con:
            if not con.execute("SELECT 1 FROM user_profiles WHERE id=?",(pid,)).fetchone():
                return False
            con.execute("UPDATE user_profiles SET last_used_utc=? WHERE id=?",(now,pid))
            con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('active_user_profile_id',?)",(str(pid),))
            con.commit(); return True

    def ensure_active_user_profile(self, fallback_name: str | None = None) -> int:
        pid=self.active_user_profile_id()
        if pid is not None:
            return pid
        return self.create_user_profile(fallback_name or "Local Driver")

    def upsert_driver(self, profile: dict[str, Any]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        key = _profile_key(profile)
        with self._connect() as con:
            row = con.execute("SELECT id,first_seen_utc FROM drivers WHERE profile_key=?", (key,)).fetchone()
            first = row["first_seen_utc"] if row else now
            vals = (key, profile.get("name"), profile.get("driver_id"), profile.get("race_number"), profile.get("nationality_id"),
                    profile.get("platform_id"), profile.get("team_id"), profile.get("team_name"), int(bool(profile.get("my_team"))) if profile.get("my_team") is not None else None,
                    int(bool(profile.get("ai_controlled"))) if profile.get("ai_controlled") is not None else None, profile.get("game_year"), profile.get("game_version"),
                    first, now, json.dumps(profile, separators=(",", ":"), default=str))
            con.execute("""INSERT INTO drivers(profile_key,name,driver_id,race_number,nationality_id,platform_id,team_id,team_name,my_team,ai_controlled,game_year,game_version,first_seen_utc,last_seen_utc,profile_json)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(profile_key) DO UPDATE SET name=excluded.name,driver_id=excluded.driver_id,race_number=excluded.race_number,nationality_id=excluded.nationality_id,platform_id=excluded.platform_id,team_id=excluded.team_id,team_name=excluded.team_name,my_team=excluded.my_team,ai_controlled=excluded.ai_controlled,game_year=excluded.game_year,game_version=excluded.game_version,last_seen_utc=excluded.last_seen_utc,profile_json=excluded.profile_json""", vals)
            did = int(con.execute("SELECT id FROM drivers WHERE profile_key=?", (key,)).fetchone()[0])
            # The first driver becomes the initial visible profile. Later live
            # sessions from other drivers are stored independently and do not
            # silently switch the user's Performance Hub selection.
            if not con.execute("SELECT 1 FROM meta WHERE key='preferred_driver_id'").fetchone():
                con.execute("INSERT INTO meta(key,value) VALUES('preferred_driver_id',?)", (str(did),))
                con.commit()
            return did

    def record_session(self, profile: dict[str, Any], summary: dict[str, Any] | None, coach: dict[str, Any] | None) -> int:
        summary = dict(summary or {}); coach = dict(coach or {})
        driver_fk = self.upsert_driver(profile)
        user_profile_fk = self.ensure_active_user_profile(profile.get("name") or "Local Driver")
        ctx = coach.get("event_context") if isinstance(coach.get("event_context"), dict) else {}
        potential = coach.get("potential") if isinstance(coach.get("potential"), dict) else {}
        uid = summary.get("session_uid") if summary.get("session_uid") is not None else ctx.get("session_uid")
        # Compatibility only for callers that explicitly open the legacy V1.9.0.0
        # database. The default LIVE-only store never imports mixed-source JSON.
        if self.path == Path("analysis/performance_history.sqlite3"):
            self.import_legacy_history(driver_fk, exclude_session_uid=uid)
        track_name = summary.get("track") or ctx.get("track_name") or ctx.get("track")
        track_id = ctx.get("track_id")
        session_type = summary.get("session_type") or ctx.get("session_type")
        sess_group = session_group(session_type)
        game_mode = ctx.get("game_mode")
        mode_name = game_mode_name(game_mode)
        created = coach.get("created_utc") or datetime.now(timezone.utc).isoformat()
        # UID normally identifies an EA session. Include type/track to remain safe
        # with imported/synthetic reports that reuse a missing or placeholder UID.
        # Scope the authoritative session identity to the driver. This prevents
        # a second driver using the same EA session UID/track/type from replacing
        # the first driver's stored session.
        with self._connect() as con:
            # V5 track-identity reconciliation: if this exact EA session was
            # previously saved before track identity was available, fold those
            # partial rows into the now-authoritative row. Conversely, if this
            # snapshot is temporarily Unknown after an app restart but the same
            # session UID already has a known track, reuse that known identity.
            reconcile_siblings=[]
            if uid is not None:
                siblings=con.execute("""SELECT * FROM sessions WHERE user_profile_fk=? AND session_uid=? ORDER BY created_utc,id""",
                    (user_profile_fk,str(uid))).fetchall()
                known=[]
                known_types=[]
                cur_name,cur_id=_known_track_identity(track_name,track_id)
                cur_type=_known_session_type(session_type)
                if cur_name or cur_id:
                    known.append((cur_name,cur_id,None))
                if cur_type:
                    known_types.append(cur_type)
                for r in siblings:
                    n,t=_known_track_identity(r['track_name'],r['track_id'])
                    if n or t:
                        known.append((n,t,r))
                    st=_known_session_type(r['session_type'])
                    if st:
                        known_types.append(st)
                names={x[0].lower() for x in known if x[0]}
                tids={x[1] for x in known if x[1]}
                type_keys={x.lower() for x in known_types}
                if known and len(names)<=1 and (names or len(tids)<=1) and len(type_keys)<=1:
                    resolved_name=next((x[0] for x in known if x[0]),None)
                    resolved_id=next((x[1] for x in known if x[1]),None)
                    resolved_type=next((x for x in known_types),None)
                    track_name=resolved_name or track_name
                    track_id=resolved_id or track_id
                    session_type=resolved_type or session_type
                    sess_group=session_group(session_type)
                    compatible=[]
                    for r in siblings:
                        n,t=_known_track_identity(r['track_name'],r['track_id'])
                        st=_known_session_type(r['session_type'])
                        if n and resolved_name and n.lower()!=resolved_name.lower():
                            continue
                        if not resolved_name and t and resolved_id and t!=resolved_id:
                            continue
                        if st and resolved_type and st.lower()!=resolved_type.lower():
                            continue
                        compatible.append(r)
                    if compatible:
                        old_summary,old_coach,old_created=_merge_duplicate_session_rows(compatible)
                        summary=_merge_live_session_summary(old_summary,summary)
                        coach=_merge_live_coach_snapshots(old_coach,coach)
                        created=old_created or created
                        potential = coach.get("potential") if isinstance(coach.get("potential"), dict) else potential
                        reconcile_siblings=compatible
            session_key = f"{user_profile_fk}|{uid if uid is not None else created}|{track_name or track_id or ''}|{session_type or ''}"
            # Preserve the canonical row ID when it already exists. Remove only
            # duplicate Unknown/legacy siblings; the normal upsert below then
            # updates the canonical row in place.
            duplicate_ids=[int(r['id']) for r in reconcile_siblings if str(r['session_key']) != session_key]
            if duplicate_ids:
                con.execute(f"DELETE FROM sessions WHERE id IN ({','.join('?'*len(duplicate_ids))})",duplicate_ids)
            # A Time Trial can return to garage and resume while F1 keeps the
            # logical session/lap counter. The live performance accumulator may
            # restart at that point, so never let a later partial snapshot replace
            # already-persisted laps from the same session_key.
            prior=con.execute("SELECT created_utc,summary_json,coach_json FROM sessions WHERE session_key=?",(session_key,)).fetchone()
            if prior is not None:
                try: old_summary=json.loads(prior["summary_json"] or "{}")
                except Exception: old_summary={}
                try: old_coach=json.loads(prior["coach_json"] or "{}")
                except Exception: old_coach={}
                summary=_merge_live_session_summary(old_summary,summary)
                coach=_merge_live_coach_snapshots(old_coach,coach)
                # Session date means session start, not the most recent autosave.
                created=prior["created_utc"] or created
                potential = coach.get("potential") if isinstance(coach.get("potential"), dict) else potential

            # S13 acceptance hotfix: a resumed/offline Time Trial can merge new
            # completed laps into lap_telemetry while the latest potential/session
            # summary object still describes the pre-outage stint. Re-derive only
            # objective lap/sector aggregates from the merged completed-lap evidence
            # so Best/Potential/Session-best reference cannot remain stale.
            lap_store = coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"), dict) else {}
            completed = []
            for key, item in lap_store.items():
                if not isinstance(item, dict):
                    continue
                lt = item.get("lap_time_s")
                if not _finite(lt) or float(lt) <= 0:
                    continue
                completed.append(item)
            valid_completed = [item for item in completed if item.get("valid") is not False]
            aggregate_rows = valid_completed or completed
            if aggregate_rows:
                best_observed = min(float(item["lap_time_s"]) for item in aggregate_rows)
                # V2.9.1.3.5.14: once persisted lap_telemetry exists, it is
                # the session-best authority in both directions.  A numerically
                # faster top-level value may belong to a track/personal best and
                # must not contaminate this session.
                potential["best_lap_s"] = best_observed
                summary["best_lap_s"] = best_observed
                summary["laps_completed"] = max(int(summary.get("laps_completed") or 0), len(completed))
                sector_bests = []
                for sector_key in ("sector1_time_s", "sector2_time_s", "sector3_time_s"):
                    vals = [float(item[sector_key]) for item in aggregate_rows if _finite(item.get(sector_key)) and float(item[sector_key]) > 0]
                    sector_bests.append(min(vals) if vals else None)
                if all(_finite(v) for v in sector_bests):
                    measured_theoretical = sum(float(v) for v in sector_bests)
                    effective_theoretical = min(best_observed, measured_theoretical)
                    # An observed best lap is itself a valid lower-bound candidate;
                    # theoretical/potential must never be slower than that lap.
                    if not _finite(potential.get("potential_lap_s")) or effective_theoretical < float(potential.get("potential_lap_s")):
                        potential["potential_lap_s"] = effective_theoretical
                    elif float(potential.get("potential_lap_s")) > best_observed:
                        potential["potential_lap_s"] = best_observed
                    potential["sector_theoretical_best_s"] = measured_theoretical
                    potential["sector_bests_s"] = sector_bests
                    potential["potential_guarded_by_observed_best"] = measured_theoretical > best_observed
                    potential["potential_gain_s"] = max(0.0, best_observed - float(potential["potential_lap_s"]))
                    potential["realistic_available_gain_s"] = potential["potential_gain_s"]
                elif _finite(potential.get("potential_lap_s")) and float(potential.get("potential_lap_s")) > best_observed:
                    potential["potential_lap_s"] = best_observed
                    potential["potential_guarded_by_observed_best"] = True
                    potential["potential_gain_s"] = 0.0
                    potential["realistic_available_gain_s"] = 0.0
                coach["potential"] = potential

            row = (
                session_key, driver_fk, user_profile_fk, str(uid) if uid is not None else None, created,
                str(track_id) if track_id is not None else None, str(track_name) if track_name is not None else None, str(session_type) if session_type is not None else None,
                sess_group, int(game_mode) if isinstance(game_mode,(int,float)) else None, mode_name,
                summary.get("result_status"), summary.get("position"), summary.get("grid_position"), summary.get("laps_completed"),
                potential.get("best_lap_s") if _finite(potential.get("best_lap_s")) else summary.get("best_lap_s"), summary.get("average_valid_lap_s"),
                potential.get("potential_lap_s"), potential.get("realistic_available_gain_s") if potential.get("realistic_available_gain_s") is not None else potential.get("potential_gain_s"),
                potential.get("reference_lap_s"), coach.get("total_reference_gap_s"), potential.get("potential_vs_reference_s"),
                summary.get("warnings"), summary.get("penalties_s"), summary.get("pit_stops"), summary.get("max_tyre_wear_percent"), summary.get("max_tyre_temp_c"),
                json.dumps(summary, separators=(",", ":"), default=str), json.dumps(coach, separators=(",", ":"), default=str),
            )
            con.execute("""INSERT INTO sessions(session_key,driver_fk,user_profile_fk,session_uid,created_utc,track_id,track_name,session_type,session_group,game_mode,game_mode_name,result_status,position,grid_position,laps_completed,best_lap_s,average_lap_s,potential_lap_s,potential_gain_s,reference_lap_s,reference_gap_s,potential_vs_reference_s,warnings,penalties_s,pit_stops,max_tyre_wear,max_tyre_temp,summary_json,coach_json)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(session_key) DO UPDATE SET driver_fk=excluded.driver_fk,user_profile_fk=excluded.user_profile_fk,created_utc=excluded.created_utc,session_group=excluded.session_group,game_mode=excluded.game_mode,game_mode_name=excluded.game_mode_name,result_status=excluded.result_status,position=excluded.position,grid_position=excluded.grid_position,laps_completed=excluded.laps_completed,best_lap_s=excluded.best_lap_s,average_lap_s=excluded.average_lap_s,potential_lap_s=excluded.potential_lap_s,potential_gain_s=excluded.potential_gain_s,reference_lap_s=excluded.reference_lap_s,reference_gap_s=excluded.reference_gap_s,potential_vs_reference_s=excluded.potential_vs_reference_s,warnings=excluded.warnings,penalties_s=excluded.penalties_s,pit_stops=excluded.pit_stops,max_tyre_wear=excluded.max_tyre_wear,max_tyre_temp=excluded.max_tyre_temp,summary_json=excluded.summary_json,coach_json=excluded.coach_json""", row)
            return int(con.execute("SELECT id FROM sessions WHERE session_key=?", (session_key,)).fetchone()[0])


    def import_legacy_history(self, driver_fk: int, path: str | Path = "analysis/driver_history.json", exclude_session_uid: Any = None) -> int:
        """One-time best-effort import of pre-V1.9 JSON history into SQLite."""
        legacy=Path(path)
        if not legacy.exists(): return 0
        try:
            rows=json.loads(legacy.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): return 0
        if not isinstance(rows,list): return 0
        imported=0
        with self._connect() as con:
            active_profile=self._profile_id(con,None)
            if active_profile is None:
                now=datetime.now(timezone.utc).isoformat()
                con.execute("INSERT INTO user_profiles(name,created_utc,last_used_utc) VALUES(?,?,?)",("Local Driver",now,now))
                active_profile=int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('active_user_profile_id',?)",(str(active_profile),))
            already=con.execute("SELECT value FROM meta WHERE key='legacy_driver_history_imported'").fetchone()
            if already: return 0
            for idx,row in enumerate(rows):
                if not isinstance(row,dict): continue
                ctx=row.get("event_context") if isinstance(row.get("event_context"),dict) else {}
                uid=row.get("session_uid")
                if exclude_session_uid is not None and str(uid) == str(exclude_session_uid):
                    continue
                track=ctx.get("track_name") or ctx.get("track_id")
                st=ctx.get("session_type")
                created=row.get("created_utc") or f"legacy-{idx:06d}"
                key=f"legacy:{uid if uid is not None else idx}|{track or ''}|{st or ''}"
                coach={"event_context":ctx,"potential":{"best_lap_s":row.get("best_lap_s"),"potential_lap_s":row.get("potential_lap_s"),"potential_gain_s":row.get("potential_gain_s"),"reference_lap_s":row.get("reference_lap_s"),"potential_vs_reference_s":row.get("potential_vs_reference_s")},"total_reference_gap_s":row.get("reference_gap_s"),"technique_metrics":row.get("technique_metrics") or {},"recurring_patterns":row.get("recurring_patterns") or [],"advice_outcomes":row.get("advice_outcomes") or {}}
                sg=session_group(st); gm=ctx.get("game_mode"); gmn=game_mode_name(gm)
                vals=(key,driver_fk,active_profile,str(uid) if uid is not None else None,created,str(ctx.get("track_id")) if ctx.get("track_id") is not None else None,str(ctx.get("track_name")) if ctx.get("track_name") is not None else None,str(st) if st is not None else None,sg,int(gm) if isinstance(gm,(int,float)) else None,gmn,None,None,None,None,row.get("best_lap_s"),None,row.get("potential_lap_s"),row.get("potential_gain_s"),row.get("reference_lap_s"),row.get("reference_gap_s"),row.get("potential_vs_reference_s"),None,None,None,None,None,"{}",json.dumps(coach,separators=(",",":"),default=str))
                con.execute("INSERT OR IGNORE INTO sessions(session_key,driver_fk,user_profile_fk,session_uid,created_utc,track_id,track_name,session_type,session_group,game_mode,game_mode_name,result_status,position,grid_position,laps_completed,best_lap_s,average_lap_s,potential_lap_s,potential_gain_s,reference_lap_s,reference_gap_s,potential_vs_reference_s,warnings,penalties_s,pit_stops,max_tyre_wear,max_tyre_temp,summary_json,coach_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",vals)
                imported+=int(con.total_changes>0)
            con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('legacy_driver_history_imported',?)",(datetime.now(timezone.utc).isoformat(),))
        return imported

    @staticmethod
    def _driver_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row); d.pop("profile_json", None); return d

    def drivers(self) -> list[dict[str, Any]]:
        """Compatibility alias: V4 driver selectors are local human profiles."""
        return self.user_profiles()

    def preferred_driver_id(self) -> int | None:
        return self.active_user_profile_id()

    def set_preferred_driver(self, driver: int | str | None) -> bool:
        return False if driver is None else self.set_active_user_profile(int(driver))

    def _profile_id(self, con: sqlite3.Connection, profile: int | str | None) -> int | None:
        if profile is not None:
            try:
                row=con.execute("SELECT id FROM user_profiles WHERE id=?",(int(profile),)).fetchone()
                if row: return int(row[0])
            except (TypeError,ValueError):
                pass
        row=con.execute("SELECT value FROM meta WHERE key='active_user_profile_id'").fetchone()
        if row:
            try:
                pid=int(row[0])
                if con.execute("SELECT 1 FROM user_profiles WHERE id=?",(pid,)).fetchone():
                    return pid
            except (TypeError,ValueError):
                pass
        row=con.execute("SELECT id FROM user_profiles ORDER BY last_used_utc DESC,id LIMIT 1").fetchone()
        return int(row[0]) if row else None

    @staticmethod
    def _filters_sql(session_group_filter: str | None = None, game_mode_filter: str | None = None) -> tuple[str,list[Any]]:
        parts=[]; vals=[]
        if session_group_filter and str(session_group_filter).lower() not in {'all','*'}:
            parts.append("session_group=?"); vals.append(str(session_group_filter))
        if game_mode_filter and str(game_mode_filter).lower() not in {'all','*'}:
            parts.append("game_mode_name=?"); vals.append(str(game_mode_filter))
        return ((" AND "+" AND ".join(parts)) if parts else "", vals)

    def _repair_recovered_session_aggregates(self) -> int:
        """Repair stale session Best/Potential using already-persisted lap evidence.

        S13 recovery can merge offline/resumed lap_telemetry into an older session
        whose top-level aggregate columns were written before those laps arrived.
        This is deterministic backfill only; no telemetry, scoring, or corner data
        is synthesized or modified.
        """
        changed=0
        with self._connect() as con:
            rows=con.execute("SELECT id,best_lap_s,potential_lap_s,potential_gain_s,summary_json,coach_json FROM sessions").fetchall()
            for row in rows:
                try: summary=json.loads(row["summary_json"] or "{}")
                except Exception: summary={}
                try: coach=json.loads(row["coach_json"] or "{}")
                except Exception: coach={}
                lap_store=coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"),dict) else {}
                completed=[x for x in lap_store.values() if isinstance(x,dict) and _finite(x.get("lap_time_s")) and float(x.get("lap_time_s"))>0]
                valid=[x for x in completed if x.get("valid") is not False]
                agg=valid or completed
                if not agg:
                    continue
                best=min(float(x["lap_time_s"]) for x in agg)
                sector_bests=[]
                for k in ("sector1_time_s","sector2_time_s","sector3_time_s"):
                    vals=[float(x[k]) for x in agg if _finite(x.get(k)) and float(x[k])>0]
                    sector_bests.append(min(vals) if vals else None)
                raw_theoretical=sum(float(v) for v in sector_bests) if all(_finite(v) for v in sector_bests) else None
                theoretical=min(best,float(raw_theoretical)) if _finite(raw_theoretical) else best
                old_best=row["best_lap_s"]; old_pot=row["potential_lap_s"]
                potential=coach.get("potential") if isinstance(coach.get("potential"),dict) else {}
                potential=dict(potential)
                # Persisted completed laps own the session aggregate. Repair
                # stale values in either direction; "faster" is not sufficient
                # proof because a Time Trial PB can be faster than this session.
                needs_best=(not _finite(old_best)) or abs(best-float(old_best)) > 1e-9
                needs_summary_best=(not _finite(summary.get("best_lap_s"))) or abs(best-float(summary.get("best_lap_s"))) > 1e-9
                needs_coach_best=(not _finite(potential.get("best_lap_s"))) or abs(best-float(potential.get("best_lap_s"))) > 1e-9
                needs_pot=_finite(theoretical) and ((not _finite(old_pot)) or abs(float(theoretical)-float(old_pot)) > 1e-9)
                if not (needs_best or needs_summary_best or needs_coach_best or needs_pot):
                    continue
                if needs_best or needs_summary_best:
                    summary["best_lap_s"]=best
                potential["best_lap_s"]=best
                if needs_pot:
                    theoretical=float(theoretical)
                    potential["potential_lap_s"]=theoretical
                    potential["sector_theoretical_best_s"]=float(raw_theoretical) if _finite(raw_theoretical) else None
                    potential["sector_bests_s"]=sector_bests
                    potential["potential_guarded_by_observed_best"]=bool(_finite(raw_theoretical) and float(raw_theoretical)>best)
                    potential["potential_gain_s"]=max(0.0,best-theoretical)
                    potential["realistic_available_gain_s"]=potential["potential_gain_s"]
                summary["laps_completed"]=max(int(summary.get("laps_completed") or 0),len(completed))
                coach["potential"]=potential
                final_best=best if needs_best else old_best
                final_pot=float(theoretical) if needs_pot else old_pot
                final_gain=max(0.0,float(final_best)-float(final_pot)) if _finite(final_best) and _finite(final_pot) else row["potential_gain_s"]
                con.execute("UPDATE sessions SET best_lap_s=?,potential_lap_s=?,potential_gain_s=?,laps_completed=MAX(COALESCE(laps_completed,0),?),summary_json=?,coach_json=? WHERE id=?",
                    (final_best,final_pot,final_gain,len(completed),json.dumps(summary,separators=(",",":"),default=str),json.dumps(coach,separators=(",",":"),default=str),int(row["id"])))
                changed+=1
        return changed

    def overview(self, driver: int | str | None = None, *, session_group_filter: str | None = None, game_mode_filter: str | None = None) -> dict[str, Any]:
        self._repair_recovered_session_aggregates()
        with self._connect() as con:
            pid=self._profile_id(con,driver)
            profiles=[dict(x) for x in con.execute("SELECT * FROM user_profiles ORDER BY last_used_utc DESC,name COLLATE NOCASE").fetchall()]
            if pid is None:
                return {"available":False,"reason":"no_driver_history","drivers":profiles,"profiles":profiles}
            prow=con.execute("SELECT * FROM user_profiles WHERE id=?",(pid,)).fetchone()
            extra,vals=self._filters_sql(session_group_filter,game_mode_filter)
            race_names=("Race","Race 2","Race 3")
            tracks=con.execute(f"""SELECT COALESCE(track_name,track_id,'Unknown') track,COUNT(*) sessions,
              MIN(best_lap_s) best_lap_s,MIN(potential_lap_s) best_potential_s,MIN(reference_gap_s) best_reference_gap_s,
              MAX(created_utc) last_session_utc,
              SUM(CASE WHEN session_type IN (?,?,?) AND position=1 THEN 1 ELSE 0 END) wins,
              SUM(CASE WHEN session_type IN (?,?,?) AND position BETWEEN 1 AND 3 THEN 1 ELSE 0 END) podiums
              FROM sessions WHERE user_profile_fk=? {extra}
              GROUP BY COALESCE(track_name,track_id,'Unknown') ORDER BY track COLLATE NOCASE ASC""",(*race_names,*race_names,pid,*vals)).fetchall()
            totals=con.execute(f"""SELECT COUNT(*) sessions,COUNT(DISTINCT COALESCE(track_name,track_id)) tracks,
              SUM(CASE WHEN session_type IN (?,?,?) AND position=1 THEN 1 ELSE 0 END) wins,
              SUM(CASE WHEN session_type IN (?,?,?) AND position BETWEEN 1 AND 3 THEN 1 ELSE 0 END) podiums,
              COALESCE(SUM(laps_completed),0) laps FROM sessions WHERE user_profile_fk=? {extra}""",(*race_names,*race_names,pid,*vals)).fetchone()
            recent=con.execute(f"""SELECT s.id,s.session_uid,s.created_utc,s.track_name,s.track_id,s.session_type,s.session_group,
              s.game_mode,s.game_mode_name,s.position,s.best_lap_s,s.potential_lap_s,s.reference_gap_s,s.laps_completed,
              d.name game_driver_name,d.race_number game_race_number,d.team_name game_team_name
              FROM sessions s LEFT JOIN drivers d ON d.id=s.driver_fk WHERE s.user_profile_fk=? {extra.replace('session_group','s.session_group').replace('game_mode_name','s.game_mode_name')}
              ORDER BY s.created_utc DESC LIMIT 24""",(pid,*vals)).fetchall()
            groups=[r[0] for r in con.execute("SELECT DISTINCT session_group FROM sessions WHERE user_profile_fk=? AND session_group IS NOT NULL ORDER BY session_group",(pid,)).fetchall()]
            modes=[r[0] for r in con.execute("SELECT DISTINCT game_mode_name FROM sessions WHERE user_profile_fk=? AND game_mode_name IS NOT NULL ORDER BY game_mode_name",(pid,)).fetchall()]
            # Latest game identity is metadata only; it never owns the history.
            latest_game=con.execute("""SELECT d.* FROM sessions s JOIN drivers d ON d.id=s.driver_fk WHERE s.user_profile_fk=? ORDER BY s.created_utc DESC LIMIT 1""",(pid,)).fetchone()
            profile=dict(prow)
            if latest_game:
                profile.update({"race_number":latest_game["race_number"],"team_name":latest_game["team_name"],"game_driver_name":latest_game["name"]})
            return {"available":True,"driver":profile,"profiles":profiles,"drivers":profiles,"totals":dict(totals),
                    "tracks":[dict(x) for x in tracks],"recent_sessions":[dict(x) for x in recent],
                    "filters":{"session_groups":groups,"game_modes":modes,"session_group":session_group_filter or "All","game_mode":game_mode_filter or "All"}}

    def profile_inventory(self, driver: int | str | None = None) -> dict[str, Any]:
        """Return a read-only inventory of persisted F1 history for one local person.

        V2.1.3 uses this to attach the existing Performance Hub store to the new
        per-game profile without copying, rewriting, or deleting any session data.
        Rich lap/corner/reference/assist evidence remains embedded in each stored
        session's JSON snapshot and is merely counted here.
        """
        with self._connect() as con:
            pid = self._profile_id(con, driver)
            if pid is None:
                return {"available": False, "reason": "no_driver_history"}
            prow = con.execute("SELECT * FROM user_profiles WHERE id=?", (pid,)).fetchone()
            totals = con.execute("""SELECT COUNT(*) sessions,
                COUNT(DISTINCT COALESCE(track_name,track_id)) tracks,
                COALESCE(SUM(laps_completed),0) laps,
                COUNT(DISTINCT driver_fk) game_identities
                FROM sessions WHERE user_profile_fk=?""", (pid,)).fetchone()
            rows = con.execute("""SELECT id,session_type,reference_lap_s,summary_json,coach_json
                FROM sessions WHERE user_profile_fk=? ORDER BY created_utc ASC""", (pid,)).fetchall()

        evidence = {
            "telemetry_sessions": 0,
            "lap_telemetry_records": 0,
            "reference_sessions": 0,
            "corner_performance_sessions": 0,
            "performance_analysis_sessions": 0,
            "assist_sessions": 0,
            "recorded_history_sessions": len(rows),
        }
        session_types: set[str] = set()
        for row in rows:
            if row["session_type"]:
                session_types.add(str(row["session_type"]))
            try:
                summary = json.loads(row["summary_json"] or "{}")
            except Exception:
                summary = {}
            try:
                coach = json.loads(row["coach_json"] or "{}")
            except Exception:
                coach = {}
            lap_store = coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"), dict) else {}
            telemetry_overlay = coach.get("telemetry_overlay") if isinstance(coach.get("telemetry_overlay"), dict) else {}
            if lap_store or telemetry_overlay:
                evidence["telemetry_sessions"] += 1
            evidence["lap_telemetry_records"] += len(lap_store)
            if row["reference_lap_s"] is not None or coach.get("reference_mode") or any(
                isinstance(v, dict) and bool(v.get("reference")) for v in telemetry_overlay.values()
            ):
                evidence["reference_sessions"] += 1
            review = coach.get("performance_review") if isinstance(coach.get("performance_review"), dict) else {}
            if review.get("corners") or review.get("lap_reviews") or coach.get("live_lap_intelligence"):
                evidence["corner_performance_sessions"] += 1
            if review or coach.get("technique_metrics") or coach.get("ranked_biggest_opportunities") or coach.get("best_strengths"):
                evidence["performance_analysis_sessions"] += 1
            assist_found = False
            for fact in coach.get("lap_facts") or []:
                if isinstance(fact, dict) and isinstance(fact.get("assists"), dict) and fact.get("assists"):
                    assist_found = True
                    break
            if not assist_found and isinstance(summary.get("assists"), dict) and summary.get("assists"):
                assist_found = True
            if assist_found:
                evidence["assist_sessions"] += 1

        return {
            "available": True,
            "profile_id": int(pid),
            "profile_name": str(prow["name"] if prow else ""),
            "sessions": int(totals["sessions"] or 0),
            "tracks": int(totals["tracks"] or 0),
            "laps": int(totals["laps"] or 0),
            "game_identities": int(totals["game_identities"] or 0),
            "session_types": sorted(session_types),
            "evidence": evidence,
        }

    def skill_evidence_source_sessions(self, driver: int | str | None = None) -> list[dict[str, Any]]:
        """Return authoritative LIVE session snapshots for historical skill-evidence backfill.

        This is intentionally read-only. Performance History remains the source of
        truth and the Skill Evidence Engine derives a separate evidence artifact.
        Replay sessions are not stored in this database by design.
        """
        with self._connect() as con:
            pid = self._profile_id(con, driver)
            if pid is None:
                return []
            rows = con.execute(
                """SELECT id,session_key,session_uid,created_utc,track_id,track_name,session_type,
                          result_status,laps_completed,summary_json,coach_json
                   FROM sessions WHERE user_profile_fk=? ORDER BY created_utc ASC,id ASC""",
                (pid,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                summary = json.loads(row["summary_json"] or "{}")
            except Exception:
                summary = {}
            try:
                coach = json.loads(row["coach_json"] or "{}")
            except Exception:
                coach = {}
            if not isinstance(summary, dict):
                summary = {}
            if not isinstance(coach, dict):
                coach = {}
            # Fill identity/context only when the persisted JSON predates those
            # fields. Never overwrite richer historical payload values.
            summary = dict(summary)
            summary.setdefault("session_uid", row["session_uid"] if row["session_uid"] is not None else None)
            summary.setdefault("created_utc", row["created_utc"])
            # V2.9.1.3.5.9: normalized session columns are authoritative for
            # derived consumers. Older summary_json may still contain provisional
            # "Unknown" values from startup before track/session packets arrived.
            summary["track"] = row["track_name"] or row["track_id"] or summary.get("track") or "Unknown"
            summary["session_type"] = row["session_type"] or summary.get("session_type") or "Unknown"
            summary.setdefault("result_status", row["result_status"])
            summary.setdefault("laps_completed", row["laps_completed"])
            summary["performance_history_session_id"] = int(row["id"])
            summary["performance_history_session_key"] = str(row["session_key"] or "")
            out.append({
                "history_session_id": int(row["id"]),
                "history_session_key": str(row["session_key"] or ""),
                "summary": summary,
                "coach": coach,
            })
        return out

    def track_detail(self, track: str, driver: int | str | None = None, *, session_group_filter: str | None = None, game_mode_filter: str | None = None) -> dict[str, Any]:
        with self._connect() as con:
            pid=self._profile_id(con,driver)
            if pid is None: return {"available":False,"reason":"no_driver_history"}
            extra,vals=self._filters_sql(session_group_filter,game_mode_filter)
            extra=extra.replace('session_group','s.session_group').replace('game_mode_name','s.game_mode_name')
            if str(track).strip().lower()=="unknown":
                track_clause="(s.track_name IS NULL AND s.track_id IS NULL)"
                track_vals=()
            else:
                track_clause="(s.track_name=? OR s.track_id=?)"
                track_vals=(track,track)
            rows=con.execute(f"""SELECT s.*,d.name game_driver_name,d.race_number game_race_number,d.team_name game_team_name
              FROM sessions s LEFT JOIN drivers d ON d.id=s.driver_fk
              WHERE s.user_profile_fk=? AND {track_clause} {extra} ORDER BY s.created_utc ASC""",(pid,*track_vals,*vals)).fetchall()
            sessions=[]
            for r in rows:
                d=dict(r); coach=json.loads(d.pop("coach_json") or "{}"); summary=json.loads(d.pop("summary_json") or "{}")
                d["summary"]=summary; d["opportunities"]=(coach.get("ranked_biggest_opportunities") or [])[:8]; d["strengths"]=(coach.get("best_strengths") or [])[:6]
                d["technique_metrics"]=coach.get("technique_metrics") or {}; d["phase_loss_breakdown_s"]=coach.get("phase_loss_breakdown_s") or {}; d["advice_outcomes"]=coach.get("advice_outcomes") or {}; d["straight_line"]=coach.get("latest_straight_line_analysis") or {}
                review=coach.get("performance_review") if isinstance(coach.get("performance_review"),dict) else {}
                d["session_technique_score"]=review.get("session_technique_score")
                d["review_confidence"]=review.get("confidence")
                sessions.append(d)
            timed=[x for x in sessions if _finite(x.get("best_lap_s")) and float(x.get("best_lap_s"))>0]
            best=min((float(x["best_lap_s"]) for x in timed),default=None)
            potentials=[float(x["potential_lap_s"]) for x in sessions if _finite(x.get("potential_lap_s")) and float(x.get("potential_lap_s"))>0]
            potentials += [float(x["best_lap_s"])-max(0.0,float(x["potential_gain_s"])) for x in sessions if _finite(x.get("best_lap_s")) and _finite(x.get("potential_gain_s")) and float(x.get("best_lap_s"))>0]
            predicted=min(potentials,default=None)
            latest=sessions[-1] if sessions else {}
            previous=sessions[-2] if len(sessions)>1 else {}
            best_change=(float(latest["best_lap_s"])-float(previous["best_lap_s"])) if _finite(latest.get("best_lap_s")) and _finite(previous.get("best_lap_s")) else None
            score_change=(float(latest["session_technique_score"])-float(previous["session_technique_score"])) if _finite(latest.get("session_technique_score")) and _finite(previous.get("session_technique_score")) else None
            improvements=[]
            if _finite(best_change):
                improvements.append((f"Latest session best improved by {abs(best_change):.3f} s" if best_change<0 else f"Latest session best was {best_change:.3f} s slower than the previous session"))
            if _finite(score_change):
                improvements.append((f"Technique score improved by {score_change:.1f} points" if score_change>0 else f"Technique score changed by {score_change:.1f} points"))
            if not improvements: improvements.append("Not enough comparable session evidence yet to measure cross-session improvement.")
            summary_text=(f"Across {len(sessions)} stored sessions at {track}, best measured lap is {best:.3f} s" if _finite(best) else f"Across {len(sessions)} stored sessions at {track}, no trusted best lap is available yet")
            if _finite(predicted): summary_text+=f". Measured predicted potential is {predicted:.3f} s"
            summary_text+=". "+" ".join(improvements)
            track_summary={"best_lap_s":best,"predicted_potential_lap_s":predicted,"latest_best_change_s":best_change,"latest_technique_change":score_change,"improvements":improvements,"data_summary":summary_text}
            return {"available":bool(sessions),"track":track,"session_count":len(sessions),"sessions":sessions,"track_summary":track_summary}

    @staticmethod
    def _practice_reference_trace_match(coach: dict[str, Any], reference_lap: dict[str, Any]) -> bool | None:
        """Return whether a stored session reference trace matches a selected rival.

        Performance History stores compact distance-domain reference speed traces,
        which are enough to verify identity without mutating/re-scoring the session.
        None means the old session lacks enough trace evidence to decide.
        """
        try:
            overlay=coach.get("telemetry_overlay") if isinstance(coach.get("telemetry_overlay"),dict) else {}
            stored=((overlay.get("speed_kph") or {}).get("reference") if isinstance(overlay.get("speed_kph"),dict) else None) or []
            samples=reference_lap.get("_samples") if isinstance(reference_lap,dict) else {}
            if len(stored)<8 or not isinstance(samples,dict) or len(samples)<20:
                return None
            ref=[]
            for raw_d,row in samples.items():
                if not isinstance(row,dict): continue
                try: d=float(row.get("d",raw_d)); v=float(row.get("speed_kph",row.get("speed")))
                except (TypeError,ValueError): continue
                if math.isfinite(d) and math.isfinite(v): ref.append((d,v))
            ref.sort()
            if len(ref)<20: return None
            def interp(d):
                # compact linear interpolation; reference samples are distance sorted
                lo=None
                for item in ref:
                    if item[0]>=d:
                        if lo is None: return item[1]
                        hi=item
                        if hi[0]<=lo[0]: return hi[1]
                        t=(d-lo[0])/(hi[0]-lo[0])
                        return lo[1]+(hi[1]-lo[1])*t
                    lo=item
                return lo[1] if lo else None
            errors=[]
            step=max(1,len(stored)//32)
            for pt in stored[::step]:
                if not isinstance(pt,(list,tuple)) or len(pt)<2: continue
                try: d=float(pt[0]); v=float(pt[1])
                except (TypeError,ValueError): continue
                rv=interp(d)
                if rv is not None and math.isfinite(v): errors.append(abs(v-rv))
            if len(errors)<6: return None
            errors.sort()
            median=errors[len(errors)//2]
            return median <= 3.0
        except Exception:
            return None


    @staticmethod
    def _practice_session_policy(session_type: Any) -> tuple[bool, str]:
        """Return whether a stored session may feed technique Practice.

        V2.0.7 policy: Time Trial, Free Practice and Qualifying are allowed.
        Race/Sprint evidence is intentionally excluded from Practice even when a
        particular lap happened to be clean-air.  Lap-level quality gates still
        remove pit/invalid/traffic/damage/replay-compromised evidence inside the
        allowed session types.
        """
        raw=str(session_type or "").strip().lower().replace("-","_").replace(" ","_")
        if "replay" in raw:
            return False, "replay_session_excluded"
        if raw in {"time_trial","timetrial","tt"} or ("time" in raw and "trial" in raw):
            return True, "time_trial"
        if "practice" in raw or raw in {"fp1","fp2","fp3","free_practice"}:
            return True, "free_practice"
        if "qual" in raw or raw in {"q1","q2","q3"}:
            return True, "qualifying"
        if "race" in raw or "sprint" in raw or "grand_prix" in raw or raw=="gp":
            return False, "race_session_excluded"
        return False, "unsupported_session_type"

    @staticmethod
    def _practice_weather_condition(coach: dict[str, Any]) -> str:
        """Collapse persisted lap weather to a Practice condition bucket.

        Dry and wet are never aggregated together.  Unknown remains its own
        bucket rather than being guessed into either condition.
        """
        def cond(row):
            if not isinstance(row,dict): return None
            value=row.get("track_condition") or row.get("weather_name") or row.get("weather_code")
            if value is None: return None
            text=str(value).strip().lower()
            if any(x in text for x in ("wet","rain","storm")): return "wet"
            if any(x in text for x in ("dry","clear","cloud","overcast","sun")): return "dry"
            try: return "wet" if int(float(value))>=3 else "dry"
            except Exception: return None
        values=[]
        for row in (coach.get("best_lap"),coach.get("reference_lap")):
            c=cond(row)
            if c: values.append(c)
        for row in coach.get("lap_facts") or []:
            c=cond(row)
            if c: values.append(c)
        if not values: return "unknown"
        wet=sum(1 for x in values if x=="wet")
        dry=sum(1 for x in values if x=="dry")
        return "wet" if wet>dry else "dry"

    @staticmethod
    def _practice_eligible_session_best(coach: dict[str, Any], eligible_laps: list[int]) -> tuple[float | None, int | None]:
        """Return the fastest coaching-eligible lap, never merely game-valid best."""
        allowed={int(x) for x in (eligible_laps or []) if isinstance(x,int)}
        if not allowed:
            return None,None
        candidates=[]
        seen=set()
        best=coach.get("best_lap") if isinstance(coach.get("best_lap"),dict) else {}
        best_lap=best.get("lap"); best_time=best.get("lap_time_s")
        if isinstance(best_lap,int) and best_lap in allowed and _finite(best_time) and float(best_time)>0:
            candidates.append((float(best_time),best_lap)); seen.add(best_lap)
        for row in coach.get("lap_facts") or []:
            if not isinstance(row,dict): continue
            lap=row.get("lap"); lt=row.get("lap_time_s")
            if isinstance(lap,int) and lap in allowed and _finite(lt) and float(lt)>0:
                candidates.append((float(lt),lap)); seen.add(lap)
        store=coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"),dict) else {}
        for key,row in store.items():
            if not isinstance(row,dict): continue
            try: lap=int(row.get("lap",key))
            except (TypeError,ValueError): continue
            lt=row.get("lap_time_s")
            if lap in allowed and lap not in seen and _finite(lt) and float(lt)>0:
                candidates.append((float(lt),lap))
        return min(candidates,key=lambda x:x[0]) if candidates else (None,None)

    def practice_track_detail(self, track: str, driver: int | str | None = None, reference: str | None = None, condition: str | None = None) -> dict[str, Any]:
        """Track-scoped V2.0.7 Practice Planner.

        Practice is track + weather-condition scoped. Time Trial, Free Practice
        and Qualifying sessions may contribute; Race/Sprint sessions are excluded
        by policy. The Practice Reference may be either an installed rival/reference
        or a same-condition stored session best. Historical evidence measured
        against another/unknown reference remains provisional rather than vanishing.
        """
        installed_refs=self._installed_review_references(str(track))
        # Resolve installed-reference weather once so a dry Time Trial rival is not
        # silently reused as the Practice benchmark for a wet condition bucket.
        installed_ref_laps: dict[str, dict[str, Any] | None] = {}
        external_refs=[]
        for raw in installed_refs:
            row=dict(raw)
            lap=None
            try:
                from .reference_lap import load_reference_lap
                lap,_=load_reference_lap(row.get("_path"))
            except Exception:
                lap=None
            rid=str(row.get("id") or "")
            installed_ref_laps[rid]=lap if isinstance(lap,dict) else None
            row["weather_condition"]=self._practice_weather_condition({"reference_lap":lap or {}}) if lap else "unknown"
            external_refs.append(row)

        with self._connect() as con:
            pid=self._profile_id(con,driver)
            if pid is None:
                public_refs=[{k:v for k,v in x.items() if not str(k).startswith("_")} for x in external_refs]
                return {"available":False,"reason":"no_driver_history","reference_options":public_refs,"selected_reference":None}
            if str(track).strip().lower()=="unknown":
                track_clause="(s.track_name IS NULL AND s.track_id IS NULL)"; vals=(pid,)
            else:
                track_clause="(s.track_name=? OR s.track_id=?)"; vals=(pid,track,track)
            rows=con.execute(f"""SELECT s.* FROM sessions s
              WHERE s.user_profile_fk=? AND {track_clause}
              ORDER BY s.created_utc ASC""",vals).fetchall()

            prepared=[]
            condition_counts={"dry":0,"wet":0,"unknown":0}
            for r in rows:
                d=dict(r)
                try: coach=json.loads(d.get("coach_json") or "{}")
                except Exception: coach={}
                allowed,session_bucket=self._practice_session_policy(d.get("session_type"))
                weather=self._practice_weather_condition(coach)
                condition_counts[weather]=condition_counts.get(weather,0)+1
                review=coach.get("performance_review") if isinstance(coach.get("performance_review"),dict) else {}
                quality=coach.get("coaching_data_quality") if isinstance(coach.get("coaching_data_quality"),dict) else {}
                eligible=[x for x in quality.get("eligible_laps") or [] if isinstance(x,int)]
                if not eligible:
                    dq=review.get("data_quality") if isinstance(review.get("data_quality"),dict) else {}
                    eligible=[x for x in dq.get("eligible_laps") or [] if isinstance(x,int)]
                excluded_quality=[x for x in quality.get("excluded_laps") or [] if isinstance(x,dict)]
                if not excluded_quality:
                    dq=review.get("data_quality") if isinstance(review.get("data_quality"),dict) else {}
                    excluded_quality=[x for x in dq.get("excluded_laps") or [] if isinstance(x,dict)]
                prepared.append((d,coach,review,allowed,session_bucket,weather,eligible,excluded_quality))

            requested=str(condition or "").strip().lower()
            if requested not in {"dry","wet","unknown"}: requested=""
            available_conditions=[x for x in ("dry","wet","unknown") if condition_counts.get(x,0)>0]

            # An explicit reference can still seed the initial condition when the
            # caller has not chosen a condition yet. Session-best ids carry their
            # own stored condition; external refs carry their persisted weather.
            ref_hint_condition=None
            if reference:
                ref_text=str(reference)
                if ref_text.startswith("session_best:"):
                    try: hint_id=int(ref_text.split(":",1)[1])
                    except (TypeError,ValueError): hint_id=None
                    if hint_id is not None:
                        hit=next((x for x in prepared if int(x[0].get("id") or -1)==hint_id),None)
                        if hit: ref_hint_condition=hit[5]
                else:
                    ext=next((x for x in external_refs if str(x.get("id"))==ref_text),None)
                    if ext: ref_hint_condition=ext.get("weather_condition")
            selected_condition=requested or (ref_hint_condition if ref_hint_condition in available_conditions and ref_hint_condition!="unknown" else (available_conditions[0] if available_conditions else "unknown"))

            # Same-condition session bests are first-class Practice References.
            # Newest is listed first so wet Practice can use its own measured best
            # instead of being forced onto the dry Time Trial rival.
            session_refs=[]
            for d,coach,review,allowed,session_bucket,weather,eligible,excluded_quality in reversed(prepared):
                if not allowed or weather!=selected_condition:
                    continue
                eligible_best,eligible_best_lap=self._practice_eligible_session_best(coach,eligible)
                # Practice references must themselves be coaching-quality evidence.
                # A faster game-valid lap excluded for traffic/pit/telemetry cannot
                # become the benchmark that clean laps are asked to confirm.
                if not _finite(eligible_best) or float(eligible_best)<=0:
                    continue
                session_refs.append({
                    "kind":"session_best","id":f"session_best:{int(d['id'])}",
                    "label":f"Session best · {d.get('session_type') or 'Session'} · {_profile_stamp(d.get('created_utc'))}",
                    "lap_time_s":float(eligible_best),"lap":eligible_best_lap,
                    "session_id":int(d["id"]),"weather_condition":weather,"quality_eligible":True,
                })

            # Practice only offers references compatible with the selected weather.
            # Unknown-weather installed refs remain selectable because there is no
            # evidence proving they are incompatible.
            compatible_external=[x for x in external_refs if x.get("weather_condition") in {selected_condition,"unknown"}]
            ref_options=session_refs + compatible_external
            selected=None
            if reference:
                selected=next((x for x in ref_options if str(x.get("id"))==str(reference)),None)
            if selected is None:
                # Preserve the existing dry workflow: prefer the current rival when
                # it is weather-compatible. For wet/unknown, prefer the latest
                # same-condition session best when one exists.
                current_rival=next((x for x in compatible_external if str(x.get("label") or "").startswith("Current rival reference")),None)
                if selected_condition=="dry" and current_rival is not None:
                    selected=current_rival
                elif session_refs:
                    selected=session_refs[0]
                elif current_rival is not None:
                    selected=current_rival
                elif ref_options:
                    selected=ref_options[0]

            selected_lap=None
            selected_session_id=None
            if selected:
                if selected.get("kind")=="session_best":
                    try: selected_session_id=int(selected.get("session_id"))
                    except (TypeError,ValueError): selected_session_id=None
                else:
                    selected_lap=installed_ref_laps.get(str(selected.get("id") or ""))
            public_refs=[{k:v for k,v in x.items() if not str(k).startswith("_")} for x in ref_options]

            session_reports=[]; all_sessions=[]; verified_count=0; legacy_count=0; excluded_count=0
            session_type_excluded=0; weather_excluded=0
            quality_reason_counts: dict[str,int]={}
            quality_exclusion_rows=[]
            selected_condition_timed_valid=0
            selected_condition_eligible=0
            for d,coach,review,allowed,session_bucket,weather,eligible_laps,excluded_quality in prepared:
                match=False; usable=False; evidence_mode="excluded"; match_reason="no_selected_reference"
                measured_issue_evidence=bool(coach.get("recurring_patterns") or coach.get("ranked_biggest_opportunities") or coach.get("lap_comparisons") or review.get("opportunities"))
                # A clean session with quality-eligible laps is still valid Practice
                # evidence: the planner must be allowed to conclude NO CURRENT ISSUE.
                has_practice_evidence=bool(eligible_laps or measured_issue_evidence)
                if allowed and weather==selected_condition:
                    selected_condition_eligible += len(eligible_laps)
                    selected_condition_timed_valid += int(coach.get("timed_valid_lap_count") or len(eligible_laps)+len(excluded_quality))
                    for qrow in excluded_quality:
                        reasons=[str(x) for x in qrow.get("reasons") or [] if x]
                        for reason in reasons:
                            quality_reason_counts[reason]=quality_reason_counts.get(reason,0)+1
                        quality_exclusion_rows.append({
                            "session_id":d.get("id"),"session_type":d.get("session_type"),"created_utc":d.get("created_utc"),
                            "lap":qrow.get("lap"),"reasons":reasons,"warnings":[str(x) for x in qrow.get("warnings") or [] if x],
                        })
                if not allowed:
                    match_reason=session_bucket; session_type_excluded+=1
                elif weather!=selected_condition:
                    match_reason=f"weather_condition_mismatch:{weather}"; weather_excluded+=1
                elif selected and selected.get("kind")=="session_best":
                    if selected_session_id is not None and int(d.get("id") or -1)==selected_session_id:
                        match=True
                        if has_practice_evidence:
                            usable=True; evidence_mode="verified"; match_reason="selected_session_best"
                        else:
                            match_reason="selected_session_has_no_quality_evidence"
                    elif has_practice_evidence:
                        usable=True; evidence_mode="legacy_unverified"; match_reason="historical_session_against_selected_session_best"
                    else:
                        match_reason="no_practice_evidence"
                elif selected and selected_lap:
                    selected_time=selected.get("lap_time_s"); recorded_time=d.get("reference_lap_s")
                    time_match=bool(_finite(selected_time) and _finite(recorded_time) and abs(float(selected_time)-float(recorded_time))<=0.050)
                    trace_match=self._practice_reference_trace_match(coach,selected_lap)
                    if trace_match is True or time_match:
                        match=True
                        if has_practice_evidence:
                            usable=True; evidence_mode="verified"; match_reason=("reference_trace_match" if trace_match is True else "reference_time_match")
                        else:
                            match_reason="reference_matches_but_no_quality_evidence"
                    elif has_practice_evidence:
                        usable=True; evidence_mode="legacy_unverified"; match_reason=("historical_reference_differs" if trace_match is False else "historical_reference_unverified")
                    else:
                        match_reason="no_practice_evidence"
                elif has_practice_evidence:
                    usable=True; evidence_mode="legacy_unverified"; match_reason="selected_reference_trace_unavailable"

                if not usable: excluded_count+=1
                elif evidence_mode=="verified": verified_count+=1
                else: legacy_count+=1
                all_sessions.append({
                    "id":d.get("id"),"created_utc":d.get("created_utc"),"session_type":d.get("session_type"),"practice_session_bucket":session_bucket,
                    "weather_condition":weather,"best_lap_s":d.get("best_lap_s"),"reference_lap_s":d.get("reference_lap_s"),
                    "reference_compatible":match,"practice_usable":usable,"reference_evidence_mode":evidence_mode,"reference_match_reason":match_reason,
                    "quality_eligible_laps":list(eligible_laps),"quality_excluded_lap_count":len(excluded_quality),
                })
                if usable:
                    session_reports.append({
                        "session_id":d.get("id"),"created_utc":d.get("created_utc"),"track_id":d.get("track_id"),"track_name":d.get("track_name"),
                        "session_type":d.get("session_type"),"practice_session_bucket":session_bucket,"weather_condition":weather,
                        "best_lap_s":d.get("best_lap_s"),"reference_lap_s":d.get("reference_lap_s"),"report":coach,"review":review,
                        "reference_evidence_mode":evidence_mode,
                    })

            from .practice_planner import build_track_practice_plan
            plan=build_track_practice_plan(session_reports)
            plan["reference_authority"]={k:v for k,v in (selected or {}).items() if not str(k).startswith("_")} if selected else None
            plan["weather_condition"]=selected_condition
            plan["session_policy"]={
                "included":["time_trial","free_practice","qualifying"],
                "excluded":["race","sprint","replay"],
                "lap_quality":"game-valid laps still require coaching-quality gates; pit, partial, insufficient-sample, traffic, race-control, damage and replay/telemetry-compromised laps are excluded",
                "weather":"dry, wet and unknown are separate Practice evidence buckets",
            }
            plan["compatible_session_count"]=verified_count; plan["legacy_session_count"]=legacy_count
            plan["usable_session_count"]=len(session_reports); plan["excluded_reference_session_count"]=excluded_count
            plan["reference_identity_policy"]="selected same-condition Practice Reference is the benchmark/confirmation authority; historical same-condition evidence measured against another/unknown reference remains provisional"
            if legacy_count and plan.get("primary_focus") is not None:
                plan["status"]="provisional"; plan["reason"]="historical_evidence_needs_selected_reference_confirmation"
                plan["legacy_reference_notice"]="Historical measured issues from this track and weather condition are included provisionally when an older session used a different/unknown reference. Confirm the current focus in a new compatible session against the selected Practice Reference."
            if selected and not session_reports:
                plan["status"]="insufficient_evidence"
                plan["reason"]="no_quality_eligible_laps_for_selected_condition" if selected_condition_timed_valid and selected_condition_eligible==0 else "no_usable_sessions_for_selected_condition"

            quality_exclusion_summary=[{"reason":k,"count":v} for k,v in sorted(quality_reason_counts.items(),key=lambda kv:(-kv[1],kv[0]))]
            return {
                "available":bool(rows),"track":track,"session_count":len(rows),"selected_condition":selected_condition,
                "condition_options":[{"id":x,"label":x.upper(),"session_count":condition_counts.get(x,0)} for x in available_conditions],
                "condition_counts":condition_counts,"session_type_excluded_count":session_type_excluded,"weather_excluded_count":weather_excluded,
                "compatible_session_count":verified_count,"legacy_session_count":legacy_count,"usable_session_count":len(session_reports),
                "excluded_reference_session_count":excluded_count,"reference_options":public_refs,"selected_reference":plan.get("reference_authority"),
                "quality_summary":{"timed_valid_laps":selected_condition_timed_valid,"eligible_laps":selected_condition_eligible,"excluded_laps":len(quality_exclusion_rows),"reason_counts":quality_exclusion_summary,"excluded_lap_details":quality_exclusion_rows[:24]},
                "practice_plan":plan,"sessions":all_sessions,
            }

    def delete_session(self, session_id: int) -> bool:
        """Delete one local Performance Hub session only."""
        with self._connect() as con:
            cur=con.execute("DELETE FROM sessions WHERE id=?",(int(session_id),))
            con.commit(); return bool(cur.rowcount)

    def delete_track_sessions(self, track: str, driver: int | str | None = None) -> int:
        """Delete all Performance Hub sessions for one local profile/track.

        This deliberately does not delete learned physical maps or installed
        references. Those are independent reusable track assets.
        """
        name=str(track or "").strip()
        if not name:
            return 0
        with self._connect() as con:
            pid=self._profile_id(con,driver)
            if pid is None:
                return 0
            if name.lower()=="unknown":
                cur=con.execute("DELETE FROM sessions WHERE user_profile_fk=? AND track_name IS NULL AND track_id IS NULL",(pid,))
            else:
                cur=con.execute("DELETE FROM sessions WHERE user_profile_fk=? AND (track_name=? OR track_id=?)",(pid,name,name))
            con.commit(); return int(cur.rowcount or 0)

    def session_detail(self, session_id: int) -> dict[str, Any]:
        with self._connect() as con:
            r=con.execute("""SELECT s.*,p.name user_profile_name,d.name game_driver_name,d.race_number game_race_number,d.team_name game_team_name
              FROM sessions s LEFT JOIN user_profiles p ON p.id=s.user_profile_fk LEFT JOIN drivers d ON d.id=s.driver_fk WHERE s.id=?""",(int(session_id),)).fetchone()
            if not r: return {"available":False,"reason":"session_not_found"}
            d=dict(r); d["summary"]=json.loads(d.pop("summary_json") or "{}"); d["coach"]=json.loads(d.pop("coach_json") or "{}")
            return {"available":True,"session":d}

    @staticmethod
    def _reference_track_name(row: dict[str, Any]) -> str | None:
        md=row.get("metadata") if isinstance(row.get("metadata"),dict) else {}
        tr=md.get("track") if isinstance(md.get("track"),dict) else {}
        return str(tr.get("name") or tr.get("id") or "") or None

    def _installed_review_references(self, track: str) -> list[dict[str, Any]]:
        try:
            from .reference_ecosystem import list_installed_references
            from .app_paths import REFERENCES
            rows=list_installed_references(REFERENCES)
        except Exception:
            return []
        out=[]
        target=str(track or "").strip().upper()
        for row in rows:
            # V2.9.1.3.5.5: Performance Hub must expose the same loadable
            # reference files as the Control Center selector.  ``valid`` in
            # reference_ecosystem is the quality-acceptance flag, not a parse
            # success flag; a recorded rival can legitimately be loadable and
            # selectable while carrying a low quality grade.  Hiding those
            # rows made the Hub silently fall back to an older session-recorded
            # rival even though Control Center showed the newer reference.
            if not isinstance(row,dict):
                continue
            path=str(row.get("path") or "")
            if not path or not isinstance(row.get("metadata"),dict):
                # Rows without normalized metadata are actual load failures.
                continue
            name=self._reference_track_name(row)
            path_obj=Path(path)
            folder_track=(path_obj.parent.name if path_obj.name.lower()=="rival_reference.json" else "")
            def _track_key(value):
                return str(value or "").strip().replace(" ","_").upper()
            if _track_key(name)!=_track_key(target) and _track_key(folder_track)!=_track_key(target):
                continue
            token=hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]
            md=row.get("metadata") if isinstance(row.get("metadata"),dict) else {}
            drv=(md.get("driver") or {}).get("name") if isinstance(md.get("driver"),dict) else None
            is_current_rival=path_obj.name.lower()=="rival_reference.json" and bool(folder_track)
            kind="Current rival reference" if is_current_rival else "Stored reference"
            q=row.get("quality") if isinstance(row.get("quality"),dict) else {}
            grade=q.get("grade")
            score=q.get("score")
            quality_suffix=(f" · Q{grade} {score}" if grade is not None and score is not None else "")
            label=kind+(f" · {drv}" if drv else "")+quality_suffix
            out.append({"kind":"external","id":f"external:{token}","label":label,"lap_time_s":row.get("lap_time_s"),"_path":path,
                        "quality_accepted":bool(row.get("valid")),"quality":q})
        return out

    def review_reference_options(self, session_id: int) -> dict[str, Any]:
        self._repair_recovered_session_aggregates()
        with self._connect() as con:
            cur=con.execute("SELECT id,user_profile_fk,track_name,track_id,created_utc,session_type,best_lap_s,reference_lap_s,coach_json FROM sessions WHERE id=?",(int(session_id),)).fetchone()
            if not cur: return {"available":False,"reason":"session_not_found","options":[]}
            track=cur["track_name"] or cur["track_id"]
            coach=json.loads(cur["coach_json"] or "{}")
            lap_store=coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"),dict) else {}
            observed=[float(row.get("lap_time_s")) for row in lap_store.values() if isinstance(row,dict) and row.get("valid") is not False and _finite(row.get("lap_time_s")) and float(row.get("lap_time_s"))>0]
            effective_best=min(observed) if observed else cur["best_lap_s"]
            opts=[{"kind":"session_best","id":"session_best","label":"Session best","lap_time_s":effective_best}]
            seen_laps=set()
            for key,row in sorted(lap_store.items(),key=lambda kv:int(kv[0]) if str(kv[0]).isdigit() else 9999):
                if not isinstance(row,dict): continue
                try: lap_no=int(row.get("lap",key))
                except (TypeError,ValueError): continue
                seen_laps.add(lap_no)
                opts.append({"kind":"session_lap","id":f"lap:{lap_no}","label":f"This session · Lap {lap_no}","lap_time_s":row.get("lap_time_s")})
            telemetry=coach.get("telemetry_overlay") if isinstance(coach.get("telemetry_overlay"),dict) else {}
            has_recorded_ref=bool(cur["reference_lap_s"] is not None or any(((telemetry.get(k) or {}).get("reference") if isinstance(telemetry.get(k),dict) else []) for k in ("speed_kph","brake","throttle","gear","ers")))
            if has_recorded_ref:
                mode=str(coach.get("reference_mode") or "").lower()
                label="Session-recorded rival/reference" if mode=="external" else "Session-recorded active reference"
                opts.append({"kind":"recorded","id":"recorded","label":label,"lap_time_s":cur["reference_lap_s"]})
            rows=con.execute("SELECT id,created_utc,session_type,best_lap_s,reference_lap_s FROM sessions WHERE user_profile_fk=? AND (track_name=? OR track_id=?) ORDER BY created_utc DESC",(cur["user_profile_fk"],track,track)).fetchall()
            for r in rows:
                if int(r["id"])==int(session_id): continue
                opts.append({"kind":"session","id":int(r["id"]),"label":f"Stored session best · {r['session_type'] or 'Session'} · {_profile_stamp(r['created_utc'])}","lap_time_s":r["best_lap_s"]})
        for row in self._installed_review_references(str(track)):
            clean=dict(row); clean.pop("_path",None); opts.append(clean)
        return {"available":True,"track":track,"session_id":int(session_id),"options":opts}

    def review_detail(self, session_id: int, reference: int | str | None = None, view_lap: int | None = None) -> dict[str, Any]:
        self._repair_recovered_session_aggregates()
        base=self.session_detail(session_id)
        if not base.get("available"): return base
        session=base["session"]; coach=session.get("coach") if isinstance(session.get("coach"),dict) else {}
        # V2.9.1.3.5.14 read-path guard: session cards, reference gaps and
        # selected-reference comparisons must all see the same current-session
        # best derived from persisted completed laps.
        _lap_store_authority=coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"),dict) else {}
        _valid_session_times=[float(x.get("lap_time_s")) for x in _lap_store_authority.values() if isinstance(x,dict) and x.get("valid") is not False and _finite(x.get("lap_time_s")) and float(x.get("lap_time_s"))>0]
        if _valid_session_times:
            session["best_lap_s"]=min(_valid_session_times)
            if isinstance(session.get("summary"),dict):
                session["summary"]["best_lap_s"]=session["best_lap_s"]
            if isinstance(coach.get("potential"),dict):
                coach["potential"]["best_lap_s"]=session["best_lap_s"]
        review=coach.get("performance_review") if isinstance(coach.get("performance_review"),dict) else None
        has_review_evidence=bool(coach.get("lap_comparisons") or coach.get("telemetry_overlay") or review)

        # V2.0.5.10: a garage/resume snapshot can leave a stale persisted
        # performance_review containing only the latest stint while the merged
        # lap_telemetry/live_lap_intelligence correctly contains the whole
        # logical session. Rebuild deterministically whenever the source lap
        # coverage is wider than the cached review. This is read-only repair and
        # restores old sessions without inventing measurements.
        source_laps=set()
        for row in coach.get("live_lap_intelligence") or []:
            if isinstance(row,dict) and isinstance(row.get("lap_number"),int): source_laps.add(int(row["lap_number"]))
        for row in coach.get("lap_comparisons") or []:
            if isinstance(row,dict) and isinstance(row.get("lap"),int): source_laps.add(int(row["lap"]))
        for row in coach.get("lap_facts") or []:
            if isinstance(row,dict) and isinstance(row.get("lap"),int): source_laps.add(int(row["lap"]))
        lap_store0=coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"),dict) else {}
        for key,row in lap_store0.items():
            try: source_laps.add(int(row.get("lap",key) if isinstance(row,dict) else key))
            except (TypeError,ValueError): pass
        review_laps=set()
        if isinstance(review,dict):
            for row in review.get("lap_reviews") or review.get("laps") or []:
                if isinstance(row,dict) and isinstance(row.get("lap"),int): review_laps.add(int(row["lap"]))
        stale_review=bool(source_laps and not source_laps.issubset(review_laps))
        if review is None or stale_review or (coach.get("live_lap_intelligence") and not review.get("lap_reviews")):
            try:
                from .performance_review import build_performance_review
                review=build_performance_review(coach)
            except Exception:
                review=review or {"status":"n/a"}
        # V2.9.1.3.5.13: session score authority is the already-scored laps.
        # Never independently rescore the session from raw evidence here.
        # This also repairs cached reviews whose lap scores survived but whose
        # session aggregate/eligible-lap linkage became stale after reconciliation.
        try:
            from .performance_review import aggregate_session_from_lap_scores
            review=aggregate_session_from_lap_scores(review)
        except Exception:
            pass
        stored_geometry=coach.get("track_geometry_snapshot") if isinstance(coach.get("track_geometry_snapshot"),dict) else {}
        # V2.0.5.7: older/newly-recorded V2 snapshots can contain the measured
        # map polyline but no physical-corner rows because the geometry reader
        # was still looking in the pre-migration maps/tracks folder. Hydrate only
        # the missing corner authority from the current shared track model. This
        # is read-only review repair; persisted session measurements are unchanged.
        if not (stored_geometry.get("corners") if isinstance(stored_geometry,dict) else None):
            try:
                from .track_geometry import persisted_physical_turns
                track_name=session.get("track_name") or session.get("track_id")
                turns=[dict(x) for x in persisted_physical_turns(track_name)]
                if turns:
                    stored_geometry=dict(stored_geometry or {})
                    stored_geometry["track"]=stored_geometry.get("track") or track_name
                    stored_geometry["corners"]=turns
            except Exception:
                pass
        lap_store=coach.get("lap_telemetry") if isinstance(coach.get("lap_telemetry"),dict) else {}
        # VIEW availability follows authoritative completed-lap timing evidence,
        # not only score-bearing review rows. This keeps every persisted lap
        # selectable even when its technique score is legitimately N/A.
        all_by_lap={}
        for row in (review.get("laps") or []) if isinstance(review,dict) else []:
            if isinstance(row,dict) and isinstance(row.get("lap"),int): all_by_lap[int(row["lap"])]=dict(row)
        for row in coach.get("lap_facts") or []:
            if not isinstance(row,dict) or not isinstance(row.get("lap"),int): continue
            lap_no=int(row["lap"]); base=all_by_lap.setdefault(lap_no,{"lap":lap_no})
            for k,v in row.items():
                if base.get(k) is None: base[k]=v
        for key,row in lap_store.items():
            if not isinstance(row,dict): continue
            try: lap_no=int(row.get("lap",key))
            except (TypeError,ValueError): continue
            base=all_by_lap.setdefault(lap_no,{"lap":lap_no})
            for k,v in row.items():
                if base.get(k) is None: base[k]=v
        all_laps=[all_by_lap[k] for k in sorted(all_by_lap)]
        if isinstance(view_lap,int):
            selected=next((x for x in (review.get("lap_reviews") or []) if isinstance(x,dict) and x.get("lap")==view_lap),None) if isinstance(review,dict) else None
            if selected:
                review=dict(review); summary=selected.get("summary") if isinstance(selected.get("summary"),dict) else {}
                review["session_technique_score"]=summary.get("score"); review["session_grade"]=summary.get("grade"); review["confidence"]=summary.get("confidence") or 0.0
                review["laps"]=[summary]; review["corners"]=selected.get("corners") or []; review["view_scope"]="lap"; review["view_lap"]=view_lap
        payload={"available":True,"session":session,"review":review,"reference_mode":"recorded","visual_reference":None,"view_lap":view_lap,"available_laps":all_laps,
                 "track_geometry":stored_geometry,
                 # Session-overall racing-line geometry is descriptive review evidence
                 # from the latest eligible live lap vs the recorded reference.  Do not
                 # reuse it for an arbitrary per-lap view where exact path evidence was
                 # not persisted.
                 "racing_line":(coach.get("latest_racing_line") if not isinstance(view_lap,int) and isinstance(coach.get("latest_racing_line"),dict) else {"available":False}),
                 "review_evidence_status":"full" if has_review_evidence else "legacy_summary_only"}
        def finish():
            payload["result_summary"]=_review_result_summary(payload,coach,view_lap)
            payload["session_quick_glance"]=_session_quick_glance(payload,coach)
            # V2.0.7 Practice Planner is a read/integration layer only. It consumes
            # the already-persisted measured coaching/review evidence and never
            # recalculates telemetry, lap scores, confidence or diagnoses.
            try:
                from .practice_planner import build_practice_plan
                payload["practice_plan"] = build_practice_plan(coach, review)
            except Exception:
                payload["practice_plan"] = {"version":"2.0.7","status":"insufficient_evidence","reason":"planner_unavailable","phases":[]}
            return payload
        selector="recorded" if reference in (None,"","recorded") else str(reference)
        current_telem=coach.get("telemetry_overlay") if isinstance(coach.get("telemetry_overlay"),dict) else {}
        if isinstance(view_lap,int):
            lr=lap_store.get(str(view_lap)) or lap_store.get(view_lap)
            if isinstance(lr,dict) and isinstance(lr.get("telemetry"),dict): current_telem=lr["telemetry"]
        if selector=="recorded":
            # The recorded authoritative reference is already embedded in the
            # persisted telemetry overlay. Expose it through visual_reference
            # as well so the UI always draws both Driver and Reference traces.
            visual={}
            for key in ("speed_kph","brake","throttle","gear","ers","delta_s"):
                row=current_telem.get(key) if isinstance(current_telem.get(key),dict) else {}
                visual[key]={"driver":row.get("driver") or [],"reference":row.get("reference") or []}
            payload["visual_reference"]={"kind":"recorded","label":"Recorded active reference","lap_time_s":session.get("reference_lap_s"),"telemetry":visual}
            if _finite(session.get("best_lap_s")) and _finite(session.get("reference_lap_s")):
                payload["visual_reference"]["best_lap_gap_s"]=float(session["best_lap_s"])-float(session["reference_lap_s"])
            return finish()
        if selector=="session_best":
            best_row=None
            for row in lap_store.values():
                if isinstance(row,dict) and row.get("valid") is not False and _finite(row.get("lap_time_s")) and (best_row is None or float(row["lap_time_s"])<float(best_row["lap_time_s"])): best_row=row
            ref_telem=((best_row or {}).get("telemetry") if isinstance(best_row,dict) else current_telem) or {}
            visual={}
            for key in ("speed_kph","brake","throttle","gear","ers","delta_s"):
                cur=(current_telem.get(key) or {}).get("driver") if isinstance(current_telem.get(key),dict) else []
                ref=(ref_telem.get(key) or {}).get("driver") if isinstance(ref_telem.get(key),dict) else []
                visual[key]={"driver":cur or [],"reference":ref or []}
            effective_best=(best_row or {}).get("lap_time_s") if isinstance(best_row,dict) else session.get("best_lap_s")
            cur_time=(lap_store.get(str(view_lap)) or {}).get("lap_time_s") if isinstance(view_lap,int) else effective_best
            gap=float(cur_time)-float(effective_best) if _finite(cur_time) and _finite(effective_best) else 0.0
            payload["reference_mode"]="session_best"
            payload["visual_reference"]={"kind":"session_best","label":"Session best","best_lap_s":effective_best,"best_lap_gap_s":gap,"telemetry":visual}
            return finish()
        if selector.startswith("lap:"):
            try: ref_lap=int(selector.split(":",1)[1])
            except (ValueError,TypeError): return finish()
            rr=lap_store.get(str(ref_lap)) or lap_store.get(ref_lap)
            if not isinstance(rr,dict): payload["reference_warning"]="Selected lap telemetry is unavailable."; return finish()
            ref_telem=rr.get("telemetry") if isinstance(rr.get("telemetry"),dict) else {}
            visual={}
            for key in ("speed_kph","brake","throttle","gear","ers","delta_s"):
                cur=(current_telem.get(key) or {}).get("driver") if isinstance(current_telem.get(key),dict) else []
                ref=(ref_telem.get(key) or {}).get("driver") if isinstance(ref_telem.get(key),dict) else []
                visual[key]={"driver":cur or [],"reference":ref or []}
            cur_time=(lap_store.get(str(view_lap)) or {}).get("lap_time_s") if isinstance(view_lap,int) else session.get("best_lap_s")
            ref_time=rr.get("lap_time_s")
            payload["reference_mode"]="session_lap"; payload["visual_reference"]={"kind":"session_lap","label":f"This session · Lap {ref_lap}","lap":ref_lap,"lap_time_s":ref_time,"telemetry":visual}
            if _finite(cur_time) and _finite(ref_time): payload["visual_reference"]["best_lap_gap_s"]=float(cur_time)-float(ref_time)
            return finish()
        if selector.startswith("external:"):
            track=session.get("track_name") or session.get("track_id")
            match=None
            for row in self._installed_review_references(str(track)):
                if row.get("id")==selector:
                    match=row; break
            if not match:
                payload["reference_warning"]="Installed reference is no longer available."; return finish()
            try:
                from .reference_lap import load_reference_lap
                from .session_coach_report import _telemetry_overlay
                lap,_meta=load_reference_lap(match["_path"])
                ref_overlay=_telemetry_overlay(None,lap)
                visual={}
                for key in ("speed_kph","brake","throttle","gear","ers","delta_s"):
                    cur=(current_telem.get(key) or {}).get("driver") if isinstance(current_telem.get(key),dict) else []
                    ref=(ref_overlay.get(key) or {}).get("reference") if isinstance(ref_overlay.get(key),dict) else []
                    visual[key]={"driver":cur or [],"reference":ref or []}
                payload["reference_mode"]="external"
                payload["visual_reference"]={"kind":"external","label":match.get("label"),"lap_time_s":match.get("lap_time_s"),"telemetry":visual}
                if isinstance(session.get("best_lap_s"),(int,float)) and isinstance(match.get("lap_time_s"),(int,float)):
                    payload["visual_reference"]["best_lap_gap_s"]=float(session["best_lap_s"])-float(match["lap_time_s"])
            except Exception as error:
                payload["reference_warning"]=f"Installed reference could not be loaded: {error}"
            return finish()
        try: ref_id=int(selector)
        except (TypeError,ValueError): return finish()
        ref=self.session_detail(ref_id)
        if not ref.get("available"): return finish()
        rs=ref["session"]
        if rs.get("user_profile_fk")!=session.get("user_profile_fk") or (rs.get("track_name") or rs.get("track_id"))!=(session.get("track_name") or session.get("track_id")):
            payload["reference_warning"]="Selected reference is not the same local driver profile/track."; return finish()
        rcoach=rs.get("coach") if isinstance(rs.get("coach"),dict) else {}; rtelem=rcoach.get("telemetry_overlay") if isinstance(rcoach.get("telemetry_overlay"),dict) else {}
        visual={}
        for key in ("speed_kph","brake","throttle","gear","ers","delta_s"):
            cur=(current_telem.get(key) or {}).get("driver") if isinstance(current_telem.get(key),dict) else []; ref_driver=(rtelem.get(key) or {}).get("driver") if isinstance(rtelem.get(key),dict) else []
            visual[key]={"driver":cur or [],"reference":ref_driver or []}
        payload["reference_mode"]="stored_session"; payload["visual_reference"]={"kind":"stored_session","label":f"Stored session best · {rs.get('session_type') or 'Session'}","session_id":ref_id,"created_utc":rs.get("created_utc"),"session_type":rs.get("session_type"),"best_lap_s":rs.get("best_lap_s"),"telemetry":visual}
        if isinstance(session.get("best_lap_s"),(int,float)) and isinstance(rs.get("best_lap_s"),(int,float)):
            payload["visual_reference"]["best_lap_gap_s"]=float(session["best_lap_s"])-float(rs["best_lap_s"])
        return finish()

