"""Track landmark store for reference-learned and human-verified visual facts.

No visual board is invented from lap distance.  Automatic import occurs only when
reference/track metadata explicitly provides the landmark.  Manual edits remain
separate from learned reference driving data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TrackLandmarkStore:
    def __init__(self, path: str | Path | None = None) -> None:
        from .app_paths import TRACK_LANDMARKS
        self.path=Path(path) if path is not None else TRACK_LANDMARKS; self._data=self._load()

    def _load(self):
        try:
            if self.path.exists():
                data=json.loads(self.path.read_text(encoding="utf-8")); return data if isinstance(data,dict) else {}
        except (OSError,json.JSONDecodeError): pass
        return {}

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data,indent=2,sort_keys=True),encoding="utf-8"); tmp.replace(self.path)

    def _track(self,track_key: str) -> dict[str,Any]:
        return self._data.setdefault(str(track_key),{})

    def set_track_metadata(self,track_key: str,**fields: Any) -> dict[str,Any]:
        item=self._track(track_key); meta=item.setdefault("track",{})
        allowed={"track_name","track_length_m","start_finish_m","pit_entry_m","pit_exit_m","notes","default_pre_call_distance_m"}
        for key,value in fields.items():
            if key in allowed: meta[key]=value
        self.save(); return dict(meta)

    def track_metadata(self,track_key: str) -> dict[str,Any]:
        item=self._data.get(str(track_key)); return dict(item.get("track",{})) if isinstance(item,dict) and isinstance(item.get("track"),dict) else {}

    def set_manual_corner(self,track_key: str,corner_id: int,**fields: Any) -> dict[str,Any]:
        item=self._track(track_key); manual=item.setdefault("manual",{}); row=manual.setdefault(str(int(corner_id)),{})
        allowed={"name","visual_brake_landmark","braking_board_m","board_150_m","board_100_m","board_50_m",
                 "kerb_start_m","kerb_end_m","pre_call_distance_m","notes"}
        for key,value in fields.items():
            if key in allowed: row[key]=value
        self.save(); return dict(row)

    def import_metadata(self,track_key: str,metadata: dict[str,Any] | None) -> dict[str,Any]:
        """Import explicit track/landmark facts from a reference package or metadata file."""
        if not isinstance(metadata,dict): return {"track":self.track_metadata(track_key),"corners":self.corners(track_key)}
        track_fields={k:metadata.get(k) for k in ("track_name","track_length_m","start_finish_m","pit_entry_m","pit_exit_m","default_pre_call_distance_m") if metadata.get(k) is not None}
        if track_fields: self.set_track_metadata(track_key,**track_fields)
        landmarks=metadata.get("landmarks") or metadata.get("track_landmarks") or metadata.get("corners")
        if isinstance(landmarks,dict): landmarks=list(landmarks.values())
        if isinstance(landmarks,list):
            for row in landmarks:
                if not isinstance(row,dict): continue
                cid=row.get("corner_id") if row.get("corner_id") is not None else row.get("id")
                if not isinstance(cid,int): continue
                fields={k:row.get(k) for k in ("name","visual_brake_landmark","braking_board_m","board_150_m","board_100_m","board_50_m","kerb_start_m","kerb_end_m","pre_call_distance_m","notes") if row.get(k) is not None}
                if fields: self.set_manual_corner(track_key,cid,**fields)
        return {"track":self.track_metadata(track_key),"corners":self.corners(track_key)}

    def learn_from_reference(self,track_key: str,reference: dict[str,Any] | None) -> list[dict[str,Any]]:
        if not reference: return []
        key=str(track_key); existing=self._data.get(key,{}) if isinstance(self._data.get(key),dict) else {}; manual=existing.get("manual",{}) if isinstance(existing.get("manual"),dict) else {}
        meta=reference.get("metadata") if isinstance(reference.get("metadata"),dict) else {}
        explicit={**meta,**{k:reference.get(k) for k in ("track_length_m","start_finish_m","pit_entry_m","pit_exit_m") if reference.get(k) is not None}}
        self.import_metadata(key,explicit)
        corners=[]
        for sec in reference.get("sections") or []:
            if not isinstance(sec,dict) or not isinstance(sec.get("id"),int): continue
            cid=int(sec["id"]); override=manual.get(str(cid),{}) if isinstance(manual.get(str(cid)),dict) else {}
            corners.append({"corner_id":cid,"name":override.get("name") or f"Turn {cid}","brake_m":sec.get("start_m"),"turn_in_m":sec.get("turn_in_m"),
                            "apex_m":sec.get("apex_m") if sec.get("apex_m") is not None else sec.get("min_speed_m"),"exit_m":sec.get("end_m"),"reference_gear":sec.get("apex_gear"),"reference_min_speed_kph":sec.get("min_speed_kph"),
                            "visual_brake_landmark":override.get("visual_brake_landmark"),"braking_board_m":override.get("braking_board_m"),
                            "board_150_m":override.get("board_150_m"),"board_100_m":override.get("board_100_m"),"board_50_m":override.get("board_50_m"),
                            "kerb_start_m":override.get("kerb_start_m"),"kerb_end_m":override.get("kerb_end_m"),"pre_call_distance_m":override.get("pre_call_distance_m"),"notes":override.get("notes")})
        self._data[key]={**existing,"track":self.track_metadata(key),"learned":corners}; self.save(); return corners

    def corners(self,track_key: str) -> list[dict[str,Any]]:
        item=self._data.get(str(track_key)); return [x for x in item.get("learned",[]) if isinstance(x,dict)] if isinstance(item,dict) else []

    def corner(self,track_key: str,corner_id: int) -> dict[str,Any] | None:
        return next((x for x in self.corners(track_key) if x.get("corner_id")==int(corner_id)),None)

    def pre_call_distance_override(self,track_key: str,corner_id: int) -> float | None:
        row=self.corner(track_key,corner_id) or {}; value=row.get("pre_call_distance_m")
        if isinstance(value,(int,float)): return float(value)
        meta=self.track_metadata(track_key); value=meta.get("default_pre_call_distance_m")
        return float(value) if isinstance(value,(int,float)) else None

    def pre_call_distance(self,track_key: str,corner_id: int,default: float=180.0) -> float:
        value=self.pre_call_distance_override(track_key,corner_id)
        return float(value) if isinstance(value,(int,float)) else float(default)

    def start_finish_landmark(self,track_key: str) -> dict[str,Any] | None:
        value=self.track_metadata(track_key).get("start_finish_m")
        return {"kind":"start_finish","distance_m":float(value)} if isinstance(value,(int,float)) else None

    def pit_landmarks(self,track_key: str) -> list[dict[str,Any]]:
        meta=self.track_metadata(track_key); out=[]
        if isinstance(meta.get("pit_entry_m"),(int,float)): out.append({"kind":"pit_entry","distance_m":float(meta["pit_entry_m"])})
        if isinstance(meta.get("pit_exit_m"),(int,float)): out.append({"kind":"pit_exit","distance_m":float(meta["pit_exit_m"])})
        return out

    def nearest_visual_landmark(self,track_key: str,distance_m: float,*,max_distance_m: float=80.0) -> dict[str,Any] | None:
        candidates=[]
        for row in self.corners(track_key):
            for field,label in (("board_150_m","150 board"),("board_100_m","100 board"),("board_50_m","50 board"),("braking_board_m","braking board"),("kerb_start_m","kerb start"),("kerb_end_m","kerb end")):
                value=row.get(field)
                if isinstance(value,(int,float)): candidates.append((abs(float(value)-float(distance_m)),row.get("corner_id"),label,float(value)))
        for row in [self.start_finish_landmark(track_key),*self.pit_landmarks(track_key)]:
            if isinstance(row,dict): candidates.append((abs(float(row["distance_m"])-float(distance_m)),None,row["kind"].replace("_"," "),float(row["distance_m"])))
        if not candidates: return None
        gap,cid,label,value=min(candidates,key=lambda x:x[0])
        if gap>float(max_distance_m): return None
        return {"corner_id":cid,"landmark":label,"distance_m":value,"offset_m":float(distance_m)-value}

    def export_track(self,track_key: str,path: str | Path) -> Path:
        item=self._data.get(str(track_key),{}); out=Path(path); out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps({"format":"RACE_ENGINEER_TRACK_LANDMARKS","version":"1.3.2.0","track_key":str(track_key),"data":item},indent=2,sort_keys=True),encoding="utf-8")
        return out

    def import_track(self,path: str | Path,track_key: str | None=None) -> str:
        data=json.loads(Path(path).read_text(encoding="utf-8")); key=str(track_key or data.get("track_key") or "").strip()
        if not key: raise ValueError("track_key is required")
        payload=data.get("data") if isinstance(data.get("data"),dict) else data
        self._data[key]=payload; self.save(); return key
