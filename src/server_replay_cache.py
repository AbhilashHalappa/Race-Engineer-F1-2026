"""On-demand cache for historical replays whose master copy lives on race-server."""
from __future__ import annotations

from pathlib import Path
import os
import shutil


def share_root() -> Path | None:
    raw=(os.environ.get("RACE_ENGINEER_SERVER_SHARE") or ("R:\\" if os.name=="nt" else "")).strip()
    return Path(raw) if raw else None


def remote_replay_root() -> Path | None:
    root=share_root()
    return (root/"data"/"replays") if root is not None else None


def available_remote_replays() -> list[Path]:
    root=remote_replay_root()
    if root is None:
        return []
    try:
        if not root.is_dir(): return []
        return sorted((p for p in root.rglob("*.areplay") if p.is_file()),key=lambda p:p.stat().st_mtime,reverse=True)
    except OSError:
        return []


def hydrate_replay(source: str | Path, local_root: Path) -> Path:
    """Copy one server-master replay into the local cache before playback."""
    src=Path(source)
    if not src.is_file():
        candidate=remote_replay_root()
        if candidate is not None:
            matches=list(candidate.rglob(src.name)) if candidate.exists() else []
            if matches: src=matches[0]
    if not src.is_file(): raise FileNotFoundError(src)
    local_root.mkdir(parents=True,exist_ok=True)
    dst=local_root/src.name
    if dst.is_file() and dst.stat().st_size==src.stat().st_size:
        return dst
    tmp=dst.with_name(dst.name+".part")
    shutil.copy2(src,tmp)
    if tmp.stat().st_size != src.stat().st_size:
        tmp.unlink(missing_ok=True); raise IOError("Replay cache verification failed")
    tmp.replace(dst)
    return dst
