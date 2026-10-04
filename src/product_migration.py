"""Upgrade-safe local user-data backup/migration for packaged releases."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import zipfile
from .app_paths import PTT_LOGS

RELEASE_VERSION = "2.0.0"


def _user_files(root: Path):
    for base in (root/'settings', root/'maps', root/'references'):
        if not base.exists():
            continue
        for p in base.rglob('*'):
            if p.is_file() and p.stat().st_size <= 25*1024*1024:
                yield p
    # Canonical runtime location is user_data/logs/ptt. Keep legacy fallback
    # only for upgrades created before the structured data layout.
    hid = PTT_LOGS / 'hid_mapping.json'
    if hid.exists() and hid.is_file():
        yield hid
    else:
        legacy = root/'logs'/'ptt'/'hid_mapping.json'
        if legacy.exists() and legacy.is_file():
            yield legacy


def create_upgrade_backup_if_needed(*, root: str | Path = '.', version: str = RELEASE_VERSION) -> Path | None:
    root=Path(root)
    marker=root/'settings'/'.release_marker.json'
    previous=None
    try:
        if marker.exists(): previous=json.loads(marker.read_text(encoding='utf-8')).get('version')
    except Exception:
        previous=None
    # Existing user data with no marker means pre-productization installation.
    candidates=list(_user_files(root))
    backup=None
    if candidates and previous != version:
        outdir=root/'analysis'/'migrations'; outdir.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        prev=str(previous or 'legacy').replace('/','_')
        backup=outdir/f'user_data_before_{version}_from_{prev}_{stamp}.zip'
        with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('migration_manifest.json',json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'from_version':previous,'to_version':version},indent=2))
            for p in candidates:
                try:z.write(p,p.relative_to(root).as_posix())
                except (OSError,ValueError):pass
    marker.parent.mkdir(parents=True,exist_ok=True)
    marker.write_text(json.dumps({'version':version,'updated_utc':datetime.now(timezone.utc).isoformat()},indent=2),encoding='utf-8')
    return backup
