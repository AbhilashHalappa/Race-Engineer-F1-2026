"""V2.6.1 deterministic F1 career milestones from persisted LIVE history.

Milestones are rebuilt from two authoritative local sources:
- validated Skill Evidence / Skill Trends for skill progression;
- LIVE Performance History for final results and measured lap personal bests.
Replay data is never used by the Performance History store.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .driver_profiles import DriverProfileStore
from .driver_skill import ALL_F1_SKILLS, DISPLAY_NAMES
from .skill_trends import SkillTrendStore
from .performance_history import PerformanceHistoryStore

HISTORY_VERSION = "2.6.1"
SKILL_THRESHOLDS = (50, 60, 70, 80, 90)
SESSION_THRESHOLDS = (5, 10, 25, 50, 100, 250, 500)
RACE_TYPES = {"Race", "Race 2", "Race 3"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts(value: Any) -> str:
    text=str(value or "").strip()
    return text or _utc_now()


def _finite_positive(value: Any) -> bool:
    return isinstance(value,(int,float)) and not isinstance(value,bool) and float(value)>0


def _lap_text(seconds: Any) -> str:
    if not _finite_positive(seconds):
        return "--:--.---"
    value=float(seconds); minutes=int(value//60); secs=value-minutes*60
    return f"{minutes}:{secs:06.3f}"


class CareerHistoryStore:
    def __init__(self, driver_store: DriverProfileStore | None = None,
                 performance_store: PerformanceHistoryStore | None = None) -> None:
        self.driver_store=driver_store or DriverProfileStore()
        self.trends=SkillTrendStore(self.driver_store)
        self.performance_store=performance_store or PerformanceHistoryStore()

    def root(self, driver_id: str) -> Path:
        return self.driver_store.root / str(driver_id) / "games" / "f1_26"

    def output_path(self, driver_id: str) -> Path:
        return self.root(driver_id) / "career_history.json"

    @staticmethod
    def _write_json_atomic(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp=path.with_suffix(path.suffix+".tmp")
        tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _highest_threshold(value: Any, thresholds=SKILL_THRESHOLDS) -> int | None:
        if not isinstance(value,(int,float)):
            return None
        reached=[x for x in thresholds if float(value) >= x]
        return max(reached) if reached else None

    def _linked_performance_profile_id(self, driver_id: str) -> int | None:
        profile=self.driver_store.load_profile(driver_id) or {}
        compat=profile.get("compatibility") if isinstance(profile.get("compatibility"),dict) else {}
        value=compat.get("performance_history_profile_id")
        try:
            return int(value) if value is not None else None
        except (TypeError,ValueError):
            return None

    def _live_sessions(self, driver_id: str) -> list[dict[str,Any]]:
        pid=self._linked_performance_profile_id(driver_id)
        if pid is None:
            return []
        rows=self.performance_store.skill_evidence_source_sessions(pid)
        out=[]
        for row in rows:
            if not isinstance(row,dict):
                continue
            summary=row.get("summary") if isinstance(row.get("summary"),dict) else {}
            out.append({
                "history_session_id":row.get("history_session_id"),
                "history_session_key":row.get("history_session_key"),
                "summary":dict(summary),
            })
        out.sort(key=lambda x:(str((x.get("summary") or {}).get("created_utc") or ""),int(x.get("history_session_id") or 0)))
        return out

    @staticmethod
    def _is_finished(summary: dict[str,Any]) -> bool:
        raw=summary.get("result_status_raw")
        status=str(summary.get("result_status") or "").strip().lower()
        return raw==3 or status=="finished"

    def _performance_events(self, driver_id: str) -> tuple[list[dict[str,Any]], list[str]]:
        rows=self._live_sessions(driver_id)
        events=[]
        keys=[]
        track_best: dict[str,float]={}
        win_count=0; podium_count=0; pole_count=0
        for row in rows:
            summary=row.get("summary") or {}
            key=str(row.get("history_session_key") or row.get("history_session_id") or "")
            keys.append(key)
            timestamp=_ts(summary.get("created_utc"))
            track=str(summary.get("track") or "Unknown")
            session_type=str(summary.get("session_type") or "Unknown")
            position=summary.get("position")
            finished=self._is_finished(summary)

            # Track-wide measured personal fastest lap. The first trusted timed
            # session establishes the baseline; later improvements create PBs.
            lap=summary.get("best_lap_s")
            if _finite_positive(lap):
                lap=float(lap); previous=track_best.get(track)
                if previous is None:
                    track_best[track]=lap
                    events.append({
                        "id":f"lap_pb_established_{key}","timestamp":timestamp,"category":"lap_pb",
                        "title":f"Established {track} personal fastest lap",
                        "detail":f"First stored LIVE personal best at {track}: {_lap_text(lap)}.",
                        "value":round(lap,3),"previous":None,"track":track,"session_type":session_type,
                    })
                elif lap < previous-0.0005:
                    track_best[track]=lap
                    events.append({
                        "id":f"lap_pb_{key}","timestamp":timestamp,"category":"lap_pb",
                        "title":f"New {track} personal fastest lap",
                        "detail":f"Improved the stored LIVE personal best to {_lap_text(lap)} from {_lap_text(previous)}.",
                        "value":round(lap,3),"previous":round(previous,3),"track":track,"session_type":session_type,
                    })

            if session_type in RACE_TYPES and finished and isinstance(position,int):
                if position==1:
                    win_count+=1; podium_count+=1
                    title=f"Grand Prix win — {track}" if session_type=="Race" else f"Race win — {track}"
                    events.append({
                        "id":f"race_win_{key}","timestamp":timestamp,"category":"result",
                        "title":title,"detail":f"Finished P1 at {track} in the completed LIVE {session_type} session.",
                        "value":1,"track":track,"session_type":session_type,"position":1,
                    })
                    if win_count in (1,5,10,25,50,100):
                        events.append({
                            "id":f"wins_{win_count}_{key}","timestamp":timestamp,"category":"career",
                            "title":"First Grand Prix win" if win_count==1 else f"{win_count} race wins",
                            "detail":f"Career LIVE race-win total reached {win_count}.","value":win_count,
                            "track":track,"session_type":session_type,
                        })
                elif position in (2,3):
                    podium_count+=1
                    events.append({
                        "id":f"podium_{key}","timestamp":timestamp,"category":"result",
                        "title":f"Podium — P{position} at {track}",
                        "detail":f"Finished P{position} at {track} in the completed LIVE {session_type} session.",
                        "value":position,"track":track,"session_type":session_type,"position":position,
                    })

                if summary.get("race_fastest_lap") is True:
                    fastest=summary.get("race_fastest_lap_s") or summary.get("best_lap_s")
                    events.append({
                        "id":f"race_fastest_lap_{key}","timestamp":timestamp,"category":"result",
                        "title":f"Race fastest lap — {track}",
                        "detail":f"Set the fastest lap of the completed LIVE race at {_lap_text(fastest)}.",
                        "value":round(float(fastest),3) if _finite_positive(fastest) else None,
                        "track":track,"session_type":session_type,
                    })

            if "Qualifying" in session_type and finished and position==1:
                pole_count+=1
                events.append({
                    "id":f"pole_{key}","timestamp":timestamp,"category":"result",
                    "title":f"Pole position — {track}",
                    "detail":f"Finished P1 in the completed LIVE {session_type} session at {track}.",
                    "value":1,"track":track,"session_type":session_type,
                })

        return events,keys

    def rebuild(self, driver_id: str) -> dict[str, Any]:
        trend_payload=self.trends.ensure(driver_id)
        snapshots=[x for x in trend_payload.get("snapshots",[]) if isinstance(x,dict)]
        events: list[dict[str,Any]]=[]

        for threshold in SESSION_THRESHOLDS:
            if len(snapshots) >= threshold:
                snap=snapshots[threshold-1]
                events.append({
                    "id":f"sessions_{threshold}","timestamp":_ts(snap.get("timestamp")),"category":"career",
                    "title":f"{threshold} F1 evidence sessions",
                    "detail":f"Reached {threshold} stored validated F1 evidence sessions.",
                    "value":threshold,"track":str(snap.get("track") or ""),
                })

        reached: dict[str,int]={}
        keys=("overall", *ALL_F1_SKILLS)
        for snap in snapshots:
            skills=snap.get("skills") if isinstance(snap.get("skills"),dict) else {}
            for key in keys:
                value=snap.get("overall") if key=="overall" else skills.get(key)
                threshold=self._highest_threshold(value)
                if threshold is None or threshold <= reached.get(key,0):
                    continue
                reached[key]=threshold
                name="Formula Driver Skill" if key=="overall" else DISPLAY_NAMES.get(key,key)
                events.append({
                    "id":f"skill_{key}_{threshold}","timestamp":_ts(snap.get("timestamp")),"category":"skill",
                    "title":f"{name} reached {threshold}",
                    "detail":f"{name} reached the {threshold} skill band from validated F1 evidence.",
                    "value":round(float(value),1),"threshold":threshold,"track":str(snap.get("track") or ""),
                })

        for track in self.trends.available_tracks(driver_id):
            snaps=self.trends._snapshots_for_track(driver_id,track); best=None
            for snap in snaps:
                value=snap.get("overall")
                if not isinstance(value,(int,float)):
                    continue
                if best is None or float(value)>best+0.05:
                    previous=best; best=float(value)
                    events.append({
                        "id":f"track_pb_{track}_{snap.get('session_key')}","timestamp":_ts(snap.get("timestamp")),
                        "category":"track","title":f"New {track} track skill personal best",
                        "detail":f"{track} Overall track skill improved to {best:.1f}."
                                 +(f" Previous best {previous:.1f}." if previous is not None else ""),
                        "value":round(best,1),"previous":round(previous,1) if previous is not None else None,"track":track,
                    })

        performance_events,performance_keys=self._performance_events(driver_id)
        events.extend(performance_events)
        # Deduplicate defensively by deterministic event id.
        by_id={str(x.get("id")):x for x in events if x.get("id")}
        events=list(by_id.values())
        events.sort(key=lambda x:(str(x.get("timestamp") or ""),str(x.get("id") or "")),reverse=True)
        payload={
            "format":"RACE_ENGINEER_F1_CAREER_HISTORY","version":HISTORY_VERSION,"driver_id":str(driver_id),
            "game_id":"f1_26","discipline":"formula","updated_at":_utc_now(),"event_count":len(events),
            "source_session_keys":[str(x.get("session_key") or "") for x in snapshots],
            "performance_history_session_keys":performance_keys,"events":events,
            "rules":{
                "source":"validated Skill Evidence / Skill Trends + linked LIVE Performance History",
                "race_results":"only completed stored LIVE final results create wins, podiums, poles or race-fastest-lap milestones",
                "lap_pb":"only measured stored LIVE best_lap_s values are compared chronologically per track",
                "driving_hours":"aggregate hours are not backdated without timestamped crossing data",
                "missing":"no synthetic milestones are created",
            },
        }
        self._write_json_atomic(self.output_path(driver_id),payload)
        return payload

    def ensure(self, driver_id: str) -> dict[str, Any]:
        return self.rebuild(driver_id)
