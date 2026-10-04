#!/usr/bin/env bash
# Race Engineer Stable V2 - One-click Ubuntu server setup
# Run on a fresh Ubuntu Server/Desktop installation:
#   chmod +x SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
#   sudo ./SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
#
# Optional overrides before running:
#   RACE_SERVER_USER=raceadmin RACE_SERVER_HOSTNAME=race-server sudo -E ./SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
#
# This script installs and configures:
#   - OpenSSH server
#   - Samba file share (\\race-server\RaceEngineer)
#   - Python virtual environment + FastAPI/Uvicorn server
#   - Race Engineer S14.4 data API on TCP 8765
#   - Race Engineer data directories under /srv/race-engineer
#   - Daily verified backups with systemd timer
#   - UFW rules for SSH, Samba, and API
#
set -Eeuo pipefail

ROOT="/srv/race-engineer"
HOSTNAME_TARGET="${RACE_SERVER_HOSTNAME:-race-server}"
SERVER_USER="${RACE_SERVER_USER:-${SUDO_USER:-raceadmin}}"
if [[ "$SERVER_USER" == "root" || -z "$SERVER_USER" ]]; then SERVER_USER="raceadmin"; fi
SHARE_NAME="${RACE_SERVER_SHARE_NAME:-RaceEngineer}"
API_PORT="${RACE_SERVER_API_PORT:-8765}"
APP="$ROOT/server/app"
LOG="/var/log/race-engineer-server-setup.log"

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: Run this script with sudo: sudo ./$(basename "$0")" >&2
  exit 1
fi

exec > >(tee -a "$LOG") 2>&1
trap 'echo; echo "SETUP FAILED at line $LINENO. Review $LOG" >&2' ERR

say() { printf '
[1;36m==> %s[0m
' "$*"; }
ok()  { printf '[1;32m[OK][0m %s
' "$*"; }
warn(){ printf '[1;33m[WARN][0m %s
' "$*"; }

say "Race Engineer Stable V2 server setup"
echo "User       : $SERVER_USER"
echo "Hostname   : $HOSTNAME_TARGET"
echo "Share      : $SHARE_NAME"
echo "Data root  : $ROOT"
echo "API port   : $API_PORT"
echo "Setup log  : $LOG"

say "Installing Ubuntu packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y   openssh-server samba samba-common-bin   python3 python3-venv python3-pip   sqlite3 curl ca-certificates rsync tar gzip unzip   ufw
ok "Required Ubuntu packages installed"

say "Preparing server account"
if ! id "$SERVER_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$SERVER_USER"
  warn "Created Linux user '$SERVER_USER'. Set its Linux password now."
  passwd "$SERVER_USER"
else
  ok "Linux user '$SERVER_USER' already exists"
fi
SERVER_GROUP="$(id -gn "$SERVER_USER")"

say "Setting hostname"
CURRENT_HOST="$(hostnamectl --static 2>/dev/null || hostname)"
if [[ "$CURRENT_HOST" != "$HOSTNAME_TARGET" ]]; then
  hostnamectl set-hostname "$HOSTNAME_TARGET"
  if grep -qE '^127\.0\.1\.1[[:space:]]' /etc/hosts; then
    sed -i -E "s/^127\.0\.1\.1[[:space:]].*/127.0.1.1 $HOSTNAME_TARGET/" /etc/hosts
  else
    printf '127.0.1.1 %s\n' "$HOSTNAME_TARGET" >> /etc/hosts
  fi
fi
ok "Hostname configured as $HOSTNAME_TARGET"

say "Creating Race Engineer server storage"
mkdir -p   "$APP/src" "$APP/logs"   "$ROOT/database/snapshots"   "$ROOT/backups/automated" "$ROOT/backups/client_snapshots" "$ROOT/backups/client_data"   "$ROOT/data/drivers" "$ROOT/data/deleted_drivers" "$ROOT/data/references"   "$ROOT/data/track_maps" "$ROOT/data/setups" "$ROOT/data/replays"   "$ROOT/data/recordings" "$ROOT/data/validation" "$ROOT/data/logs" "$ROOT/data/exports"   "$ROOT/incoming" "$ROOT/cache" "$ROOT/server/deploy"
chown -R "$SERVER_USER:$SERVER_GROUP" "$ROOT"
chmod -R u+rwX,g+rwX,o-rwx "$ROOT"
ok "Storage tree ready"

say "Installing Race Engineer S14.4 server API"
cat > "$APP/src/main.py" <<'RACE_ENGINEER_MAIN_PY'
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
import hashlib, json, os, shutil, sqlite3, subprocess, tempfile, uuid, zipfile

APP_NAME="Race Engineer Data Server"; APP_VERSION="S14.4"
ROOT=Path("/srv/race-engineer"); DB_DIR=ROOT/"database"; DB=DB_DIR/"race_engineer.db"
PERF_DB=DB_DIR/"performance_history_live.sqlite3"; SNAP=DB_DIR/"snapshots"

def now(): return datetime.now(timezone.utc).isoformat()
def conn(path=DB):
    path.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(path,timeout=5); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

def init():
    DB_DIR.mkdir(parents=True,exist_ok=True); SNAP.mkdir(parents=True,exist_ok=True)
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL, applied_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS drivers(driver_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,active_game TEXT,timezone TEXT NOT NULL DEFAULT 'UTC',created_at_utc TEXT NOT NULL,updated_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY,driver_id TEXT NOT NULL,game TEXT NOT NULL,track TEXT,session_type TEXT,started_at_utc TEXT,ended_at_utc TEXT,source TEXT NOT NULL DEFAULT 'live',created_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS snapshots(kind TEXT PRIMARY KEY,sha256 TEXT NOT NULL,size_bytes INTEGER NOT NULL,source_host TEXT,updated_at_utc TEXT NOT NULL,path TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS profile_drivers(driver_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,active_game TEXT,timezone TEXT NOT NULL DEFAULT 'UTC',created_at_utc TEXT NOT NULL,updated_at_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS profile_driver_deletions(driver_id TEXT PRIMARY KEY,display_name TEXT,deleted_at_utc TEXT NOT NULL,purge_after_utc TEXT NOT NULL,status TEXT NOT NULL,deleted_path TEXT,performance_snapshot_path TEXT,updated_at_utc TEXT NOT NULL);
        ''')
        if not c.execute("SELECT 1 FROM schema_version LIMIT 1").fetchone(): c.execute("INSERT INTO schema_version VALUES(4,?)",(now(),))
        else: c.execute("UPDATE schema_version SET version=4,applied_at_utc=?",(now(),))
        c.commit()


def _parse_utc(value: str) -> datetime:
    text=str(value or "").strip().replace("Z","+00:00")
    dt=datetime.fromisoformat(text) if text else datetime.now(timezone.utc)
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def purge_expired_driver_deletions():
    root=ROOT/"data"/"deleted_drivers"
    stamp=datetime.now(timezone.utc)
    purged=[]
    with conn() as c:
        rows=c.execute("SELECT driver_id,purge_after_utc,deleted_path FROM profile_driver_deletions WHERE status='retained'").fetchall()
        for row in rows:
            try:
                if _parse_utc(row["purge_after_utc"]) > stamp:
                    continue
            except Exception:
                continue
            path=Path(str(row["deleted_path"] or root/row["driver_id"]))
            if path.exists(): shutil.rmtree(path,ignore_errors=True)
            c.execute("DELETE FROM profile_driver_deletions WHERE driver_id=?",(row["driver_id"],))
            purged.append(str(row["driver_id"]))
        c.commit()
    return purged


def soft_delete_profile_driver(driver_id: str, payload: dict):
    driver_id=str(driver_id or "").strip()
    if not driver_id: raise HTTPException(400,"driver_id required")
    deleted_at=_parse_utc(str(payload.get("deleted_at_utc") or now()))
    retention_days=max(1,min(365,int(payload.get("retention_days") or 30)))
    purge_after=deleted_at+timedelta(days=retention_days)
    active_root=ROOT/"data"/"drivers"
    active_dir=active_root/driver_id
    deleted_dir=ROOT/"data"/"deleted_drivers"/driver_id
    deleted_dir.mkdir(parents=True,exist_ok=True)
    profile_target=deleted_dir/"profile"
    if active_dir.exists() and not profile_target.exists():
        os.replace(active_dir,profile_target)
    elif active_dir.exists():
        shutil.rmtree(active_dir,ignore_errors=True)
    # Preserve the server-side performance history as it existed at delete time
    # before the gaming PC publishes its post-delete local database snapshot.
    perf_target=deleted_dir/"performance_history_at_delete.sqlite3"
    if PERF_DB.exists() and not perf_target.exists():
        src=sqlite3.connect(f"file:{PERF_DB.as_posix()}?mode=ro",uri=True,timeout=10)
        dst=sqlite3.connect(perf_target,timeout=10)
        try: src.backup(dst)
        finally: dst.close(); src.close()
    meta={k:v for k,v in payload.items() if k != "journal_path"}
    meta.update({"driver_id":driver_id,"deleted_at_utc":deleted_at.isoformat(),"purge_after_utc":purge_after.isoformat(),"status":"retained"})
    (deleted_dir/"DELETION.json").write_text(json.dumps(meta,indent=2,default=str)+"\n",encoding="utf-8")
    # Remove this Driver from the active index immediately if it still exists.
    idx=active_root/"index.json"
    if idx.exists():
        try:
            data=json.loads(idx.read_text(encoding="utf-8")); rows=data.get("drivers") if isinstance(data,dict) else None
            if isinstance(rows,list):
                rows=[r for r in rows if not (isinstance(r,dict) and str(r.get("driver_id") or "")==driver_id)]
                data["drivers"]=rows
                if str(data.get("active_driver_id") or "")==driver_id:
                    data["active_driver_id"]=str(rows[0].get("driver_id") or "") if rows else None
                idx.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
        except Exception: pass
    with conn() as c:
        row=c.execute("SELECT display_name FROM profile_drivers WHERE driver_id=?",(driver_id,)).fetchone()
        display=str(payload.get("display_name") or (row["display_name"] if row else "Driver"))
        c.execute("DELETE FROM profile_drivers WHERE driver_id=?",(driver_id,))
        c.execute("INSERT OR REPLACE INTO profile_driver_deletions(driver_id,display_name,deleted_at_utc,purge_after_utc,status,deleted_path,performance_snapshot_path,updated_at_utc) VALUES(?,?,?,?,?,?,?,?)",(
            driver_id,display,deleted_at.isoformat(),purge_after.isoformat(),"retained",str(deleted_dir),str(perf_target) if perf_target.exists() else None,now()))
        c.commit()
    return {"status":"retained","driver_id":driver_id,"deleted_at_utc":deleted_at.isoformat(),"purge_after_utc":purge_after.isoformat(),"path":str(deleted_dir),"retention_days":retention_days}


def publish_driver_profiles(archive: Path):
    target=ROOT/"data"/"drivers"
    staging=ROOT/"incoming"/f"drivers-{uuid.uuid4().hex}"
    backup=ROOT/"cache"/f"drivers-previous-{uuid.uuid4().hex}"
    staging.mkdir(parents=True,exist_ok=True)
    try:
        with zipfile.ZipFile(archive,"r") as zf:
            base=staging.resolve()
            for info in zf.infolist():
                name=info.filename.replace("\\","/")
                if name.startswith("/") or ".." in Path(name).parts:
                    raise HTTPException(400,"Unsafe Driver Profile archive path")
                out=(staging/Path(name)).resolve()
                if base not in out.parents and out != base:
                    raise HTTPException(400,"Unsafe Driver Profile archive path")
            zf.extractall(staging)
        index_path=staging/"index.json"
        index={}
        if index_path.exists():
            index=json.loads(index_path.read_text(encoding="utf-8"))
            if not isinstance(index,dict): raise ValueError("Invalid drivers index")
        profiles=[]
        for row in index.get("drivers",[]) if isinstance(index.get("drivers"),list) else []:
            if not isinstance(row,dict): continue
            driver_id=str(row.get("driver_id") or "").strip()
            if not driver_id: continue
            profile_path=staging/driver_id/"profile.json"
            if not profile_path.exists(): continue
            profile=json.loads(profile_path.read_text(encoding="utf-8"))
            if not isinstance(profile,dict) or str(profile.get("driver_id") or "") != driver_id: continue
            profiles.append(profile)
        if target.exists():
            backup.parent.mkdir(parents=True,exist_ok=True)
            os.replace(target,backup)
        target.parent.mkdir(parents=True,exist_ok=True)
        os.replace(staging,target)
        if backup.exists(): shutil.rmtree(backup,ignore_errors=True)
        with conn() as c:
            c.execute("DELETE FROM profile_drivers")
            stamp=now()
            for profile in profiles:
                created=str(profile.get("created_at") or stamp)
                updated=str(profile.get("last_active") or stamp)
                c.execute("INSERT INTO profile_drivers(driver_id,display_name,active_game,timezone,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,?)",(
                    str(profile.get("driver_id") or ""), str(profile.get("display_name") or "Driver"),
                    str(profile.get("active_game") or "f1_26"), str(profile.get("time_zone") or "UTC"), created, updated))
            c.commit()
        return {"driver_count":len(profiles),"path":str(target)}
    except Exception:
        if target.exists(): shutil.rmtree(target,ignore_errors=True)
        if backup.exists(): os.replace(backup,target)
        shutil.rmtree(staging,ignore_errors=True)
        raise

@asynccontextmanager
async def lifespan(app): init(); yield
app=FastAPI(title=APP_NAME,version=APP_VERSION,lifespan=lifespan)

@app.get("/api/health")
def health():
    try:
        purge_expired_driver_deletions()
        with conn() as c: ver=c.execute("SELECT max(version) v FROM schema_version").fetchone()["v"]
        perf={"status":"online" if PERF_DB.exists() else "awaiting_snapshot","size_bytes":PERF_DB.stat().st_size if PERF_DB.exists() else 0}
        usage=shutil.disk_usage(ROOT)
        backup_root=ROOT/"backups"/"automated"
        marker=backup_root/"LAST_SUCCESS_UTC"
        last_backup=marker.read_text(encoding="utf-8").strip() if marker.exists() else None
        backup_status={}
        status_file=backup_root/"BACKUP_STATUS.json"
        if status_file.exists():
            try:
                value=json.loads(status_file.read_text(encoding="utf-8"))
                if isinstance(value,dict): backup_status=value
            except Exception: pass
        drivers_root=ROOT/"data"/"drivers"
        with conn() as c:
            profile_driver_count=c.execute("SELECT count(*) FROM profile_drivers").fetchone()[0]
            retained_driver_count=c.execute("SELECT count(*) FROM profile_driver_deletions WHERE status='retained'").fetchone()[0]
        profiles={"status":"online" if drivers_root.exists() else "awaiting_snapshot","driver_count":profile_driver_count,"retained_deleted_count":retained_driver_count,"path":str(drivers_root)}
        return {"status":"online","service":APP_NAME,"version":APP_VERSION,"timestamp_utc":now(),"hostname":os.uname().nodename,"database":{"status":"online","path":str(DB),"schema_version":ver},"performance_database":perf,"driver_profiles":profiles,"storage":{"free_bytes":usage.free,"total_bytes":usage.total},"last_backup_utc":last_backup,"backup":backup_status}
    except Exception as e: return {"status":"degraded","error":str(e)}

@app.post("/api/backup")
def backup_now():
    script=ROOT/"server"/"app"/"race-engineer-backup.sh"
    if not script.exists(): raise HTTPException(503,"Backup script not installed")
    lock=ROOT/"backups"/"automated"/".backup.lock"
    # The script itself owns the authoritative flock.  Start it detached so the
    # API and gaming-PC Control Center are never blocked by a large backup.
    try:
        subprocess.Popen([str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception as exc:
        raise HTTPException(500,f"Backup start failed: {exc}")
    return {"status":"started","script":str(script),"lock":str(lock)}

@app.put("/api/snapshots/{kind}")
async def put_snapshot(kind:str, request:Request):
    body=await request.body(); expected=request.headers.get("x-race-engineer-sha256") or hashlib.sha256(body).hexdigest(); actual=hashlib.sha256(body).hexdigest()
    if expected.lower()!=actual.lower(): raise HTTPException(400,"SHA256 mismatch")
    safe=kind.replace("/","_").replace("..","_"); target=SNAP/safe; tmp=target.with_suffix(target.suffix+".part")
    tmp.write_bytes(body)
    if hashlib.sha256(tmp.read_bytes()).hexdigest()!=actual: tmp.unlink(missing_ok=True); raise HTTPException(500,"Snapshot verification failed")
    tmp.replace(target)
    published_driver_profiles=None
    if safe=="performance_history.sqlite3":
        probe=sqlite3.connect(f"file:{target.as_posix()}?mode=ro",uri=True); probe.execute("PRAGMA quick_check").fetchone(); probe.close()
        pub=PERF_DB.with_suffix(".sqlite3.part"); shutil.copy2(target,pub); pub.replace(PERF_DB)
    elif safe=="driver_profiles.zip":
        published_driver_profiles=publish_driver_profiles(target)
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO snapshots(kind,sha256,size_bytes,source_host,updated_at_utc,path) VALUES(?,?,?,?,?,?)",(safe,actual,len(body),request.headers.get("x-race-engineer-source"),now(),str(target))); c.commit()
    return {"status":"stored","kind":safe,"sha256":actual,"size_bytes":len(body),"path":str(target),"published":safe in {"performance_history.sqlite3","driver_profiles.zip"},"driver_profiles":published_driver_profiles}

@app.get("/api/snapshots")
def snapshots():
    with conn() as c: return {"snapshots":[dict(r) for r in c.execute("SELECT * FROM snapshots ORDER BY updated_at_utc DESC").fetchall()]}

@app.get("/api/drivers")
def drivers():
    if PERF_DB.exists():
        try:
            with conn(PERF_DB) as c:
                rows=c.execute("SELECT id,profile_key,name,team_name,last_seen_utc FROM drivers ORDER BY last_seen_utc DESC").fetchall()
                return {"drivers":[dict(r) for r in rows],"source":"performance_database"}
        except Exception: pass
    with conn() as c: return {"drivers":[dict(r) for r in c.execute("SELECT * FROM drivers ORDER BY created_at_utc DESC").fetchall()],"source":"server_database"}

@app.get("/api/profile-drivers")
def profile_drivers():
    with conn() as c:
        rows=c.execute("SELECT driver_id,display_name,active_game,timezone,created_at_utc,updated_at_utc FROM profile_drivers ORDER BY updated_at_utc DESC").fetchall()
        return {"drivers":[dict(r) for r in rows],"source":"driver_profiles","path":str(ROOT/"data"/"drivers")}


@app.post("/api/profile-drivers/{driver_id}/delete")
async def delete_profile_driver(driver_id:str, request:Request):
    purge_expired_driver_deletions()
    try:
        payload=await request.json()
        if not isinstance(payload,dict): payload={}
    except Exception:
        payload={}
    return soft_delete_profile_driver(driver_id,payload)

@app.get("/api/profile-drivers/deleted")
def deleted_profile_drivers():
    purge_expired_driver_deletions()
    with conn() as c:
        rows=c.execute("SELECT driver_id,display_name,deleted_at_utc,purge_after_utc,status,deleted_path,performance_snapshot_path FROM profile_driver_deletions ORDER BY deleted_at_utc DESC").fetchall()
        return {"drivers":[dict(r) for r in rows],"retention_days":30,"path":str(ROOT/"data"/"deleted_drivers")}

@app.post("/api/profile-drivers/purge")
def purge_profile_drivers():
    return {"purged":purge_expired_driver_deletions()}

@app.get("/api/sessions")
def sessions(limit:int=100):
    if PERF_DB.exists():
        try:
            with conn(PERF_DB) as c:
                rows=c.execute("SELECT s.id,s.session_key,s.created_utc,s.track_name,s.session_type,s.result_status,s.position,s.laps_completed,s.best_lap_s,d.name driver_name FROM sessions s LEFT JOIN drivers d ON d.id=s.driver_fk ORDER BY s.created_utc DESC LIMIT ?",(max(1,min(limit,1000)),)).fetchall()
                return {"sessions":[dict(r) for r in rows],"source":"performance_database"}
        except Exception as e: return {"sessions":[],"error":str(e)}
    return {"sessions":[]}

for route,key in (("laps","laps"),("sectors","sectors"),("corners","corners"),("performance","performance"),("references","references"),("recordings","recordings"),("tracks","tracks"),("setups","setups")):
    async def empty(key=key): return {key:[],"status":"ready"}
    app.add_api_route(f"/api/{route}",empty,methods=["GET"])

@app.get("/performance-hub",response_class=HTMLResponse)
def performance_hub():
    sessions=[]; driver_count=track_count=0; best=None
    if PERF_DB.exists():
        try:
            with conn(PERF_DB) as c:
                sessions=[dict(r) for r in c.execute("SELECT s.created_utc,s.track_name,s.session_type,s.result_status,s.position,s.laps_completed,s.best_lap_s,d.name driver_name FROM sessions s LEFT JOIN drivers d ON d.id=s.driver_fk ORDER BY s.created_utc DESC LIMIT 200").fetchall()]
                driver_count=c.execute("SELECT count(*) FROM drivers").fetchone()[0]; track_count=c.execute("SELECT count(distinct track_name) FROM sessions WHERE track_name is not null").fetchone()[0]
                best=c.execute("SELECT min(best_lap_s) FROM sessions WHERE best_lap_s>0").fetchone()[0]
        except Exception: pass
    rows=''.join(f"<tr><td>{x.get('created_utc','')}</td><td>{x.get('driver_name') or '--'}</td><td>{x.get('track_name') or '--'}</td><td>{x.get('session_type') or '--'}</td><td>{x.get('position') or '--'}</td><td>{x.get('laps_completed') or 0}</td><td>{x.get('best_lap_s') or '--'}</td></tr>" for x in sessions)
    return f'''<!doctype html><html><head><meta name="viewport" content="width=device-width"><title>Race Engineer Performance Hub</title><style>body{{margin:0;background:#080d12;color:#eef6fb;font:14px Segoe UI,Arial}}header{{padding:18px 24px;background:#0d151d;border-bottom:1px solid #263746}}h1{{margin:0;color:#4dd9ff;font-size:22px}}.sub{{color:#8395a5;margin-top:5px}}main{{padding:18px 24px}}.cards{{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:10px;margin-bottom:18px}}.card{{background:#101820;border:1px solid #273746;border-radius:9px;padding:14px}}.k{{color:#82909e;font-size:11px;font-weight:800}}.v{{font-size:22px;font-weight:900;margin-top:4px}}table{{width:100%;border-collapse:collapse;background:#0d141b;border:1px solid #273746}}th,td{{padding:9px 10px;border-bottom:1px solid #202d38;text-align:left}}th{{color:#4dd9ff;background:#111b24;position:sticky;top:0}}.ok{{color:#2def85}}</style></head><body><header><h1>RACE ENGINEER · PERFORMANCE HUB</h1><div class="sub"><span class="ok">● SERVER ONLINE</span> · race-server · S14.4</div></header><main><div class="cards"><div class="card"><div class="k">DRIVERS</div><div class="v">{driver_count}</div></div><div class="card"><div class="k">SESSIONS</div><div class="v">{len(sessions)}</div></div><div class="card"><div class="k">TRACKS</div><div class="v">{track_count}</div></div><div class="card"><div class="k">BEST LAP</div><div class="v">{best if best else '--'}</div></div></div><table><thead><tr><th>UTC</th><th>Driver</th><th>Track</th><th>Session</th><th>Pos</th><th>Laps</th><th>Best Lap</th></tr></thead><tbody>{rows}</tbody></table></main></body></html>'''
RACE_ENGINEER_MAIN_PY

cat > "$APP/race-engineer-backup.sh" <<'RACE_ENGINEER_BACKUP_SH'
#!/bin/bash
set -euo pipefail
ROOT=/srv/race-engineer
DEST=$ROOT/backups/automated
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
PY=$ROOT/server/app/.venv/bin/python
mkdir -p "$DEST" "$ROOT/cache"
exec 9>"$DEST/.backup.lock"
if ! flock -n 9; then
  exit 0
fi
TMP=$(mktemp -d "$ROOT/cache/backup-verify-XXXXXX")
trap 'rm -rf "$TMP"' EXIT
FILES=0
VERIFIED=0
SETUPS_FILES=0
SETUPS_STATUS="MISSING"
RUN_ARTIFACTS=()

backup_sqlite() {
  local DB="$1"
  [ -f "$DB" ] || return 0
  local BASE OUT
  BASE=$(basename "$DB")
  OUT="$DEST/${BASE%.sqlite3}_${STAMP}.sqlite3"
  "$PY" - "$DB" "$OUT" <<'PY'
import sqlite3, sys
src_path, dst_path = sys.argv[1], sys.argv[2]
src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True, timeout=10)
dst = sqlite3.connect(dst_path, timeout=10)
try:
    src.backup(dst)
finally:
    dst.close(); src.close()
probe = sqlite3.connect(f"file:{dst_path}?mode=ro", uri=True, timeout=10)
try:
    row = probe.execute("PRAGMA quick_check").fetchone()
    if not row or str(row[0]).lower() != "ok":
        raise SystemExit(f"quick_check failed: {row}")
finally:
    probe.close()
PY
  FILES=$((FILES+1)); VERIFIED=$((VERIFIED+1))
  RUN_ARTIFACTS+=("$(basename "$OUT")")
}

backup_tree() {
  local SRC="$1"
  [ -e "$SRC" ] || return 0
  local NAME OUT RESTORE
  NAME=$(basename "$SRC")
  OUT="$DEST/${NAME}_${STAMP}.tar.gz"
  tar -czf "$OUT" -C "$(dirname "$SRC")" "$NAME"
  tar -tzf "$OUT" >/dev/null
  RESTORE="$TMP/verify-$NAME"
  mkdir -p "$RESTORE"
  tar -xzf "$OUT" -C "$RESTORE"
  [ -e "$RESTORE/$NAME" ]
  FILES=$((FILES+1)); VERIFIED=$((VERIFIED+1))
  RUN_ARTIFACTS+=("$(basename "$OUT")")
}

backup_setups() {
  local SRC="$ROOT/data/setups"
  if [ ! -d "$SRC" ]; then
    SETUPS_STATUS="MISSING"
    SETUPS_FILES=0
    return 0
  fi
  SETUPS_FILES=$(find "$SRC" -type f | wc -l | tr -d ' ')
  if [ "$SETUPS_FILES" -eq 0 ]; then
    SETUPS_STATUS="EMPTY"
  else
    SETUPS_STATUS="POPULATED"
  fi
  backup_tree "$SRC"
}

backup_server_runtime() {
  local STAGE="$TMP/server-stage"
  local OUT="$DEST/server_${STAMP}.tar.gz"
  mkdir -p "$STAGE/server/app/src" "$STAGE/server/systemd"

  # Keep only rebuild-relevant server material. Never archive the virtualenv,
  # logs, bytecode/cache directories, or arbitrary runtime files.
  if [ -d "$ROOT/server/app/src" ]; then
    tar -cf - -C "$ROOT/server/app/src" --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' . \
      | tar -xf - -C "$STAGE/server/app/src"
  fi
  [ -f "$ROOT/server/app/race-engineer-backup.sh" ] && cp -p "$ROOT/server/app/race-engineer-backup.sh" "$STAGE/server/app/"
  for unit in race-engineer-api.service race-engineer-backup.service race-engineer-backup.timer; do
    [ -f "/etc/systemd/system/$unit" ] && cp -p "/etc/systemd/system/$unit" "$STAGE/server/systemd/$unit"
  done

  cat > "$STAGE/server/BACKUP_CONTENTS.txt" <<EOF
Race Engineer server rebuild backup
Created UTC: $STAMP
Included: server/app/src, race-engineer-backup.sh, installed systemd unit files
Excluded: server/app/.venv, server/app/logs, __pycache__, *.pyc, runtime/cache files
EOF

  tar -czf "$OUT" -C "$STAGE" server
  tar -tzf "$OUT" >/dev/null
  local RESTORE="$TMP/verify-server"
  mkdir -p "$RESTORE"
  tar -xzf "$OUT" -C "$RESTORE"
  [ -f "$RESTORE/server/BACKUP_CONTENTS.txt" ]
  FILES=$((FILES+1)); VERIFIED=$((VERIFIED+1))
  RUN_ARTIFACTS+=("$(basename "$OUT")")
}

create_periodic_bundle() {
  local KIND="$1" KEEP="$2"
  [ "${#RUN_ARTIFACTS[@]}" -gt 0 ] || return 0
  local OUT="$DEST/${KIND}_${STAMP}.tar.gz"
  tar -czf "$OUT" -C "$DEST" "${RUN_ARTIFACTS[@]}"
  tar -tzf "$OUT" >/dev/null
  ls -1t "$DEST"/${KIND}_*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f
}

backup_sqlite "$ROOT/database/race_engineer.db"
backup_sqlite "$ROOT/database/performance_history_live.sqlite3"
backup_tree "$ROOT/data/drivers"
backup_tree "$ROOT/data/deleted_drivers"
backup_tree "$ROOT/data/references"
backup_tree "$ROOT/data/track_maps"
backup_setups
backup_server_runtime

# Retention: 7 daily component generations, 4 weekly bundles, 3 monthly bundles.
find "$DEST" -maxdepth 1 -type f -mtime +7 ! -name 'weekly_*' ! -name 'monthly_*' ! -name 'LAST_*' ! -name 'BACKUP_STATUS.json' ! -name '.backup.lock' -delete
if [ "$(date -u +%u)" = "7" ]; then
  create_periodic_bundle weekly 4
fi
if [ "$(date -u +%d)" = "01" ]; then
  create_periodic_bundle monthly 3
fi
printf '%s\n' "$STAMP" > "$DEST/LAST_SUCCESS_UTC"
printf '%s\n' "$STAMP" > "$DEST/LAST_VERIFY_UTC"
cat > "$DEST/BACKUP_STATUS.json" <<EOF
{
  "status": "ok",
  "verification": "verified",
  "last_backup_utc": "$STAMP",
  "last_verify_utc": "$STAMP",
  "files_created": $FILES,
  "files_verified": $VERIFIED,
  "setups": {"status": "$SETUPS_STATUS", "files": $SETUPS_FILES},
  "server_archive": {"scope": "REBUILD_FILES_ONLY", "venv_included": false, "logs_included": false},
  "retention": {"daily": 7, "weekly": 4, "monthly": 3}
}
EOF
RACE_ENGINEER_BACKUP_SH
chmod +x "$APP/race-engineer-backup.sh"
chown -R "$SERVER_USER:$SERVER_GROUP" "$APP"

if [[ ! -x "$APP/.venv/bin/python" ]]; then
  sudo -u "$SERVER_USER" python3 -m venv "$APP/.venv"
fi
sudo -u "$SERVER_USER" "$APP/.venv/bin/python" -m pip install --upgrade pip
sudo -u "$SERVER_USER" "$APP/.venv/bin/pip" install fastapi 'uvicorn[standard]'
ok "Python API environment installed"

say "Installing systemd services"
cat > /etc/systemd/system/race-engineer-api.service <<EOF
[Unit]
Description=Race Engineer Data Server API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVER_USER
Group=$SERVER_GROUP
WorkingDirectory=$APP
ExecStart=$APP/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port $API_PORT
Restart=on-failure
RestartSec=5s
StandardOutput=append:$APP/logs/api.log
StandardError=append:$APP/logs/api-error.log

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/race-engineer-backup.service <<EOF
[Unit]
Description=Race Engineer Server Backup
After=local-fs.target

[Service]
Type=oneshot
User=$SERVER_USER
Group=$SERVER_GROUP
ExecStart=$APP/race-engineer-backup.sh
EOF

cat > /etc/systemd/system/race-engineer-backup.timer <<'EOF'
[Unit]
Description=Race Engineer Daily Backup Timer

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now race-engineer-api.service
systemctl enable --now race-engineer-backup.timer
ok "Race Engineer API and backup timer enabled"

say "Configuring Samba share"
cp -a /etc/samba/smb.conf "/etc/samba/smb.conf.pre-race-engineer.$(date +%Y%m%d%H%M%S)"
# Remove an older managed Race Engineer block, if present.
sed -i '/^# BEGIN RACE ENGINEER MANAGED SHARE$/,/^# END RACE ENGINEER MANAGED SHARE$/d' /etc/samba/smb.conf
cat >> /etc/samba/smb.conf <<EOF

# BEGIN RACE ENGINEER MANAGED SHARE
[$SHARE_NAME]
   comment = Race Engineer Stable V2 Data Server
   path = $ROOT
   browseable = yes
   read only = no
   guest ok = no
   valid users = $SERVER_USER
   force user = $SERVER_USER
   force group = $SERVER_GROUP
   create mask = 0660
   directory mask = 0770
   force create mode = 0660
   force directory mode = 0770
# END RACE ENGINEER MANAGED SHARE
EOF

testparm -s >/dev/null
if [[ -n "${RACE_SAMBA_PASSWORD:-}" ]]; then
  printf '%s
%s
' "$RACE_SAMBA_PASSWORD" "$RACE_SAMBA_PASSWORD" | smbpasswd -s -a "$SERVER_USER"
elif [[ -t 0 ]]; then
  echo
  echo "Set the Samba password for Windows access as '$SERVER_USER'."
  echo "You can use the same password as the Ubuntu account if you want."
  smbpasswd -a "$SERVER_USER"
else
  warn "No interactive terminal detected; Samba password was not set."
  warn "Run later: sudo smbpasswd -a $SERVER_USER"
fi
systemctl enable --now smbd
systemctl enable --now nmbd || true
systemctl restart smbd
ok "Samba share configured: \\$HOSTNAME_TARGET\$SHARE_NAME"

say "Enabling SSH"
systemctl enable --now ssh
ok "OpenSSH server enabled"

say "Configuring firewall"
ufw allow OpenSSH >/dev/null
ufw allow Samba >/dev/null
ufw allow "$API_PORT/tcp" >/dev/null
if ufw status | grep -q '^Status: inactive'; then
  ufw --force enable >/dev/null
fi
ok "UFW allows SSH, Samba and TCP $API_PORT"

say "Running validation"
systemctl restart race-engineer-api.service
sleep 3
curl -fsS "http://127.0.0.1:$API_PORT/api/health" | python3 -m json.tool
systemctl is-active --quiet race-engineer-api.service
systemctl is-enabled --quiet race-engineer-api.service
systemctl is-active --quiet race-engineer-backup.timer
systemctl is-enabled --quiet race-engineer-backup.timer
testparm -s >/dev/null
ok "API, backup timer and Samba configuration validated"

# Run one verified backup now. This is safe even before game data arrives.
say "Creating first verified server backup"
sudo -u "$SERVER_USER" "$APP/race-engineer-backup.sh"
if [[ -f "$ROOT/backups/automated/BACKUP_STATUS.json" ]]; then
  cat "$ROOT/backups/automated/BACKUP_STATUS.json" | python3 -m json.tool
fi
ok "Initial backup completed"

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[[ -n "$IP" ]] || IP="<server-ip>"

cat <<EOF

============================================================
 Race Engineer Stable V2 server setup COMPLETE
============================================================

Server hostname : $HOSTNAME_TARGET
Server IP       : $IP
Linux/Samba user: $SERVER_USER
Samba share     : \\$HOSTNAME_TARGET\$SHARE_NAME
Samba by IP     : \\$IP\$SHARE_NAME
API health      : http://$IP:$API_PORT/api/health
Server root     : $ROOT
Backups         : $ROOT/backups/automated
Setup log       : $LOG

On the Windows gaming PC, map the server share to R: using PowerShell/CMD:

  net use R: \\$HOSTNAME_TARGET\$SHARE_NAME /user:$SERVER_USER * /persistent:yes

If hostname discovery does not work, use the IP instead:

  net use R: \\$IP\$SHARE_NAME /user:$SERVER_USER * /persistent:yes

Then verify from Race Engineer / PowerShell:

  .\.venv\Scripts\python.exe -m src.server_sync --status

Useful Ubuntu server commands:

  systemctl status race-engineer-api --no-pager
  systemctl status race-engineer-backup.timer --no-pager
  curl http://127.0.0.1:$API_PORT/api/health
  sudo journalctl -u race-engineer-api -n 100 --no-pager
  sudo systemctl restart race-engineer-api
  sudo -u $SERVER_USER $APP/race-engineer-backup.sh

IMPORTANT:
- This script does not force a static IP because LAN/router settings vary.
- For a permanent server address, reserve $IP for this laptop in your router's DHCP settings.
- Race Engineer still uses the gaming PC for live processing; this server is persistent storage/API/backup authority.
============================================================
EOF
