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
