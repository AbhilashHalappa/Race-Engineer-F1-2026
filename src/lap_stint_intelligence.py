"""V2.0.2 deterministic lap/stint intelligence.

Consumes already-authoritative V2.0.1 live corner results.  It does not detect
corners or driving events and never runs heavy history queries on the packet path.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import math
from typing import Any


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _mean(xs):
    xs=[float(x) for x in xs if _num(x)]
    return (sum(xs)/len(xs)) if xs else None

@dataclass(slots=True)
class LivePerformanceAccumulator:
    """Bounded session accumulator; one compact row per completed physical corner."""
    max_laps: int = 24
    min_group_samples: int = 3
    current_lap: int | None = None
    current: dict[int, dict[str, Any]] = field(default_factory=dict)
    completed: list[dict[str, Any]] = field(default_factory=list)

    def reset_session(self) -> None:
        self.current_lap=None; self.current.clear(); self.completed.clear()

    def begin_lap(self, lap_number: int | None) -> None:
        if isinstance(lap_number,int): self.current_lap=lap_number
        self.current={}

    def add_corner(self, result: dict[str, Any]) -> None:
        cid=result.get("corner_id")
        if not _num(cid): return
        # Last publication for a physical corner wins; bounded by track corner count.
        self.current[int(cid)]=dict(result)

    def _previous_corner(self, cid:int) -> dict[str,Any] | None:
        if not self.completed: return None
        for row in reversed(self.completed):
            corners=row.get("corners") or {}
            if cid in corners: return corners[cid]
            if str(cid) in corners: return corners[str(cid)]
        return None

    def finalize_lap(self, *, lap_number:int|None, eligible_corner_count:int, lap_valid:bool=True) -> dict[str,Any]:
        rows=[self.current[k] for k in sorted(self.current)]
        scored=[r for r in rows if _num(r.get("score")) and str(r.get("score_status"))=="available"]
        coverage=(len(scored)/eligible_corner_count) if eligible_corner_count>0 else 0.0
        lap_score=_mean(r.get("score") for r in scored) if lap_valid and len(scored)>=2 and coverage>=0.60 else None
        conf=_mean(r.get("confidence") for r in scored)

        losses=[r for r in rows if _num(r.get("estimated_loss_s"))]
        biggest=max(losses,key=lambda r:float(r.get("estimated_loss_s"))) if losses else None
        positive=[r for r in losses if float(r.get("estimated_loss_s"))>0.0]
        realistic_gain=sum(float(r.get("estimated_loss_s")) for r in positive)

        improvements=[]
        for r in rows:
            cid=int(r["corner_id"]); prev=self._previous_corner(cid)
            if prev and _num(prev.get("estimated_loss_s")) and _num(r.get("estimated_loss_s")):
                gain=float(prev["estimated_loss_s"])-float(r["estimated_loss_s"])
                improvements.append((gain,cid,r,prev))
        best_imp=max(improvements,key=lambda x:x[0]) if improvements else None

        issue_rows=[r for r in rows if r.get("dominant_issue") not in (None,"match","gain")]
        counts=Counter(str(r.get("dominant_issue")) for r in issue_rows)
        repeated=counts.most_common(1)[0] if counts and counts.most_common(1)[0][1]>=2 else None

        # Current focus is measured-time-cost first, consistent with the V2 contract.
        focus=None
        if biggest and float(biggest.get("estimated_loss_s") or 0.0)>0.0:
            focus={"corner_id":biggest.get("corner_id"),"issue":biggest.get("dominant_issue"),
                   "text":biggest.get("primary_text"),"loss_s":round(float(biggest["estimated_loss_s"]),3)}

        # Provisional technique groups require multiple trusted observations.
        dims=defaultdict(list)
        for lap in self.completed[-4:]:
            for r in (lap.get("corners") or {}).values():
                for metric,val in (r.get("dimension_scores") or {}).items():
                    if _num(val): dims[metric].append(float(val))
        for r in rows:
            for metric,val in (r.get("dimension_scores") or {}).items():
                if _num(val): dims[metric].append(float(val))
        def provisional(names):
            vals=[]
            for n in names: vals.extend(dims.get(n,()))
            return round(sum(vals)/len(vals),1) if len(vals)>=self.min_group_samples else None
        provisional_scores={
            "braking":provisional(("braking_point","brake_release")),
            "throttle":provisional(("throttle_pickup","time_to_full_throttle","exit_speed")),
            "corner_speed":provisional(("min_apex_speed",)),
        }

        out={
            "lap_number":lap_number,"status":"available" if _num(lap_score) else "n/a",
            "lap_score":round(float(lap_score),1) if _num(lap_score) else None,
            "confidence":round(float(conf),3) if _num(conf) else 0.0,
            "scored_corner_count":len(scored),"eligible_corner_count":int(eligible_corner_count),
            "coverage":round(coverage,3),"lap_valid":bool(lap_valid),
            "biggest_loss":({"corner_id":biggest.get("corner_id"),"loss_s":round(float(biggest["estimated_loss_s"]),3),
                              "issue":biggest.get("dominant_issue"),"text":biggest.get("primary_text")} if biggest else None),
            "best_improvement":({"corner_id":best_imp[1],"recovered_s":round(best_imp[0],3)} if best_imp and best_imp[0]>0.0 else None),
            "repeated_issue":({"issue":repeated[0],"count":repeated[1]} if repeated else None),
            "realistic_available_gain_s":round(realistic_gain,3),
            "current_focus":focus,"next_lap_focus":focus,
            "provisional_scores":provisional_scores,
            "corners":{int(r["corner_id"]):dict(r) for r in rows if _num(r.get("corner_id"))},
        }
        self.completed.append(out)
        if len(self.completed)>self.max_laps: self.completed=self.completed[-self.max_laps:]
        self.current={}
        return out

    def status(self) -> dict[str,Any]:
        return {"current_lap":self.current_lap,"completed_laps":len(self.completed),
                "last_lap":dict(self.completed[-1]) if self.completed else None}
