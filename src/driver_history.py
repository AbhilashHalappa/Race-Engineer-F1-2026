"""Local cross-session progress history for deterministic coaching metrics."""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _track_key(row: dict[str, Any]) -> str | None:
    ctx = row.get("event_context") if isinstance(row.get("event_context"), dict) else {}
    value = ctx.get("track_id") if ctx.get("track_id") is not None else ctx.get("track_name")
    return str(value).upper() if value is not None else None


def _metric_summary(values: list[float]) -> dict[str, Any] | None:
    if not values:
        return None
    return {
        "first": values[0], "latest": values[-1], "best": min(values),
        "first_to_latest": values[-1] - values[0], "samples": len(values),
        "mean": mean(values), "stddev": pstdev(values) if len(values) >= 2 else 0.0,
    }


def _direction(delta: float | None, deadband: float) -> str:
    if not _num(delta): return "insufficient_data"
    if float(delta) < -abs(deadband): return "improving"
    if float(delta) > abs(deadband): return "regressing"
    return "stable"


class DriverHistory:
    def __init__(self, path: str | Path = "analysis/driver_history.json", max_sessions: int = 500) -> None:
        self.path = Path(path); self.max_sessions = int(max_sessions)

    def load(self) -> list[dict[str, Any]]:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            pass
        return []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        rows = rows[-self.max_sessions:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def upsert(self, row: dict[str, Any], key: str = "session_uid") -> None:
        rows = self.load(); value = row.get(key)
        if value is not None:
            rows = [x for x in rows if not (isinstance(x, dict) and x.get(key) == value)]
        rows.append(dict(row)); self._save(rows)

    def append(self, row: dict[str, Any]) -> None:
        rows = self.load(); rows.append(dict(row)); self._save(rows)

    def track_rows(self, track: str | int | None) -> list[dict[str, Any]]:
        if track is None: return []
        key = str(track).upper()
        return [x for x in self.load() if isinstance(x, dict) and _track_key(x) == key]

    @staticmethod
    def _corner_rows(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
        by_corner: dict[int, list[dict[str, Any]]] = {}
        for sidx, row in enumerate(rows):
            metrics = row.get("technique_metrics") if isinstance(row.get("technique_metrics"), dict) else {}
            for corner in metrics.get("corners") or ():
                if not isinstance(corner, dict) or not isinstance(corner.get("corner_id"), int): continue
                item = dict(corner); item["_session_index"] = sidx; item["_session_uid"] = row.get("session_uid")
                by_corner.setdefault(int(corner["corner_id"]), []).append(item)
        return by_corner

    @staticmethod
    def _nested_metric(rows: list[dict[str, Any]], key: str, field: str = "stddev") -> list[float]:
        out=[]
        for row in rows:
            value=row.get(key)
            if isinstance(value,dict) and _num(value.get(field)): out.append(float(value[field]))
        return out

    def corner_progress(self, track: str | int | None) -> list[dict[str, Any]]:
        by_corner = self._corner_rows(self.track_rows(track)); result=[]
        metric_keys=("brake_point_consistency","brake_release_consistency","trail_brake_consistency",
                     "minimum_speed_consistency","apex_consistency","throttle_pickup_consistency",
                     "exit_speed_consistency","gear_choice_consistency")
        for cid, items in sorted(by_corner.items()):
            metrics={}
            for key in metric_keys:
                vals=self._nested_metric(items,key,"stddev"); s=_metric_summary(vals)
                if s: s["direction"]=_direction(s["first_to_latest"],0.5 if "speed" in key else 0.25)
                metrics[key]=s
            result.append({"corner_id":cid,"session_samples":len(items),"metrics":metrics,
                           "first_session_index":items[0].get("_session_index"),"latest_session_index":items[-1].get("_session_index")})
        return result

    def issue_resolution(self, track: str | int | None) -> dict[str, Any]:
        rows=self.track_rows(track); history: dict[tuple[Any,Any],list[int]]={}
        for idx,row in enumerate(rows):
            seen=set()
            for p in row.get("recurring_patterns") or ():
                if isinstance(p,dict):
                    key=(p.get("corner_id"),p.get("issue_code"))
                    if key[0] is not None and key[1]: seen.add(key)
            for key in seen: history.setdefault(key,[]).append(idx)
        recurring=[]; resolved=[]; latest_idx=len(rows)-1
        for (corner_id,issue_code),seen in history.items():
            item={"corner_id":corner_id,"issue_code":issue_code,"sessions_observed":len(seen),
                  "first_session_index":seen[0],"last_session_index":seen[-1]}
            if len(seen)>=2 and seen[-1]<latest_idx:
                item["resolved_for_sessions"]=latest_idx-seen[-1]; resolved.append(item)
            elif len(seen)>=2: recurring.append(item)
        recurring.sort(key=lambda x:(-x["sessions_observed"],x["corner_id"] or 0)); resolved.sort(key=lambda x:(-x["sessions_observed"],x["corner_id"] or 0))
        return {"recurring":recurring,"resolved":resolved}

    def progress_summary(self, track: str | int | None) -> dict[str, Any]:
        rows=self.track_rows(track)
        if not rows: return {"available":False,"track":track,"session_count":0}
        def summary(name): return _metric_summary([float(r[name]) for r in rows if _num(r.get(name))])
        issues=self.issue_resolution(track)
        return {"available":True,"track":track,"session_count":len(rows),"best_lap":summary("best_lap_s"),
                "potential_lap":summary("potential_lap_s"),"potential_gain":summary("potential_gain_s"),
                "reference_gap":summary("reference_gap_s"),"potential_vs_reference":summary("potential_vs_reference_s"),
                "corner_progress":self.corner_progress(track),"persistent_recurring_issues":issues["recurring"][:20],
                "resolved_recurring_issues":issues["resolved"][:20],
                "method":"chronological locally stored deterministic session summaries; no prediction"}

    def compare_sessions(self, track: str | int | None, first: int | str | None = None, second: int | str | None = None) -> dict[str, Any]:
        rows=self.track_rows(track)
        if len(rows)<2: return {"available":False,"reason":"need_two_sessions","track":track}
        def choose(value,fallback):
            if value is None: return rows[fallback]
            for row in rows:
                if row.get("session_uid")==value or str(row.get("session_uid"))==str(value): return row
            try: return rows[int(value)]
            except (ValueError,TypeError,IndexError): return None
        a,b=choose(first,-2),choose(second,-1)
        if not isinstance(a,dict) or not isinstance(b,dict): return {"available":False,"reason":"session_not_found","track":track}
        names=("best_lap_s","potential_lap_s","potential_gain_s","reference_gap_s","potential_vs_reference_s")
        deltas={k:(float(b[k])-float(a[k]) if _num(a.get(k)) and _num(b.get(k)) else None) for k in names}
        def cmap(row):
            m=row.get("technique_metrics") if isinstance(row.get("technique_metrics"),dict) else {}
            return {int(x["corner_id"]):x for x in m.get("corners") or () if isinstance(x,dict) and isinstance(x.get("corner_id"),int)}
        am,bm=cmap(a),cmap(b); corners=[]
        for cid in sorted(set(am)|set(bm)):
            ca,cb=am.get(cid,{}),bm.get(cid,{}); fields={}
            for key in ("brake_point_consistency","brake_release_consistency","trail_brake_consistency","minimum_speed_consistency",
                        "apex_consistency","throttle_pickup_consistency","exit_speed_consistency","gear_choice_consistency"):
                av=(ca.get(key) or {}).get("stddev") if isinstance(ca.get(key),dict) else None
                bv=(cb.get(key) or {}).get("stddev") if isinstance(cb.get(key),dict) else None
                fields[key]={"first":av,"second":bv,"delta":float(bv)-float(av) if _num(av) and _num(bv) else None}
            corners.append({"corner_id":cid,"consistency":fields})
        return {"available":True,"track":track,"first_session_uid":a.get("session_uid"),"second_session_uid":b.get("session_uid"),
                "metric_deltas":deltas,"corners":corners,
                "rule":"second minus first; lower measured value is descriptive and is not an automatic causal judgement"}
