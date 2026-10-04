#!/bin/bash
set -euo pipefail
ROOT=/srv/race-engineer
APP=$ROOT/server/app
mkdir -p "$APP/src" "$APP/logs" "$ROOT/database/snapshots" "$ROOT/backups/automated"
cp "$(dirname "$0")/main.py" "$APP/src/main.py"
cp "$(dirname "$0")/race-engineer-backup.sh" "$APP/race-engineer-backup.sh"
chmod +x "$APP/race-engineer-backup.sh"
if [ ! -x "$APP/.venv/bin/python" ]; then python3 -m venv "$APP/.venv"; fi
"$APP/.venv/bin/python" -m pip install --upgrade pip
"$APP/.venv/bin/pip" install fastapi 'uvicorn[standard]'
sudo cp "$(dirname "$0")/race-engineer-api.service" /etc/systemd/system/race-engineer-api.service
sudo cp "$(dirname "$0")/race-engineer-backup.service" /etc/systemd/system/race-engineer-backup.service
sudo cp "$(dirname "$0")/race-engineer-backup.timer" /etc/systemd/system/race-engineer-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now race-engineer-api.service
sudo systemctl enable --now race-engineer-backup.timer
sudo systemctl restart race-engineer-api.service
sleep 2
curl -fsS http://127.0.0.1:8765/api/health
printf '\nS14 server backend installed.\n'
