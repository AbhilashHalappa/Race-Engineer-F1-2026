# Race Engineer — Stable V2

**Telemetry • Strategy • Coaching**

**Final Stable V2 baseline:** `V2.9.1.3.5.49`  
**Git tag:** `V2.9.1.3.5.49`  
**Repository:** `AbhilashHalappa/Race_Engineer`

Race Engineer is a local-first Windows companion application for EA SPORTS F1 telemetry. It combines live telemetry, race-engineer information, strategy, radio/PTT, coaching, replay analysis, driver performance history, hardware integration, a native/LAN F1 dashboard, and an optional Ubuntu storage/backup server.

Stable V2 is designed so that the racing PC performs the live telemetry and coaching work while large AI/voice components and persistent server storage remain separate from the main executable. The application can therefore remain lightweight while still supporting local TTS, STT and LLM features when they are installed.

---

## 1. Main features

Stable V2 includes the following major systems.

### Live Race Engineer

- EA F1 UDP telemetry receiver.
- Live session, lap, sector, tyre, brake, fuel, ERS, weather, damage and strategy information.
- Deterministic race-engineer decisions for time-critical calls.
- Automatic tyre/brake/temperature and safety-relevant alerts.
- Race, qualifying, practice and Time Trial aware behaviour.
- Game-derived pit-window and strategy information where available.
- Short, priority-aware radio calls intended for use while driving.

### CORNER COACH / Performance Coaching

- Physical-corner and hybrid coaching model.
- PRE-corner coaching before the upcoming corner.
- POST-corner measured feedback.
- Braking, entry, apex, turn, exit and throttle phase analysis.
- Reference-relative gain/loss analysis.
- Rival/reference trace support in Time Trial.
- Corner score and evidence system.
- Coaching-zone and physical-corner awareness.
- Track map with corner numbers and reference information.
- Straight-line/performance coaching support from the integrated coaching pipeline.

### Performance Hub and Driver Profile

- Local Driver Profile.
- Multiple Game Profiles under a single Driver Profile architecture.
- Exactly one active Game Profile at a time.
- Live-session performance history.
- Per-track history and analysis.
- Driver skill score and category scores.
- Skill evidence/confidence system.
- Per-track skill trends.
- Career history, milestones, race results and personal best tracking.
- Every-corner performance review.
- Session/lap/reference comparison tools.
- Replay-linked telemetry workstation.

Only live-game evidence is authoritative for the driver's persistent performance history. Replay is primarily an analysis/review tool and does not replace live evidence.

### F1 Dashboard

- Native dashboard.
- LAN/browser dashboard.
- Main telemetry page.
- Tyre/brake/damage pages.
- Engine/power-unit information.
- Track map and moving car markers.
- Setup/status information.
- Native/LAN layout and telemetry parity work from the Stable V2 development line.

### Radio, PTT, STT and TTS

- Controller/HID Push-To-Talk support.
- Speech-to-text using `faster-whisper`.
- Local Piper text-to-speech.
- Race Engineer voice commands.
- Radio command tolerance/synonym handling.
- Separate Race Engineer and coaching radio ownership/priorities.
- Configurable microphone and speaker selection.

### Hardware workspace

Stable V2 includes a dedicated Hardware main tab instead of placing hardware controls inside the normal Control Center page.

The hardware system retains support for the Wheel Dashboard telemetry bridge and the integrated hardware workspace introduced during the Stable V2 development cycle.

### Replay and recordings

- Telemetry recording.
- Replay playback.
- Multi-session/weekend replay handling.
- Replay-linked telemetry views.
- Selected-lap playback and seeking.
- Analysis without allowing replay data to overwrite authoritative live Driver Profile history.

### Local server integration

The optional Ubuntu server provides:

- Persistent Race Engineer storage.
- Performance-history snapshots.
- Driver Profile storage.
- Historical-data synchronization.
- Offline queue/fallback support from the Windows client.
- Samba access from Windows.
- Race Engineer server API.
- Automated verified backups.
- Driver deletion retention/recovery support.

The server is **not** used for real-time telemetry processing. The Windows gaming PC remains the live processing authority.

---

## 2. Stable V2 design principles

Race Engineer Stable V2 follows several rules that are important when maintaining or extending the application:

- Proven telemetry/core behaviour should not be changed without a reproducible issue or explicit new requirement.
- Live game data is authoritative for Driver Profile/performance history.
- Replay analysis must not silently mutate live history.
- Deterministic calculations own measurements, scores, strategy state and time-critical decisions.
- The local LLM can explain or summarize evidence but must not invent telemetry or replace deterministic measurements.
- Missing evidence should remain `N/A` rather than being fabricated.
- Driving overlays do not all open automatically at startup.
- User data must survive application upgrades.
- Large models/runtimes are external dependencies and are not embedded in `RaceEngineer.exe`.

---

# 3. Windows installation

## Recommended installation method

Extract the complete Stable V2 package to a normal writable folder, for example:

```text
D:\RaceEngineer
```

Do not run the application directly from inside the ZIP file.

The release root contains files similar to:

```text
RaceEngineer.exe
RUN_SETUP.bat
RUN_FIRST_RUN_CHECK.bat
requirements.txt
runtime_dependencies.json
SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
src\
assets\
installer\
tools\
tests\
```

Start with:

```powershell
.\RaceEngineer.exe
```

The launcher checks required runtime components before starting the main application.

---

## 4. Dependency policy

Stable V2 deliberately does **not** pack large runtimes and AI models into the executable.

The launcher checks for the following components and offers installation/download options when they are missing.

### Python

Required runtime:

```text
Python 3.13
```

The application uses a local virtual environment named:

```text
.venv
```

Required Python packages are defined in:

```text
requirements.txt
```

Core/import checks include packages used for:

- PySide6 UI
- Piper TTS
- sounddevice
- pygame
- HID/PTT
- serial hardware communication
- QR support
- faster-whisper STT

### Piper TTS

Default voice:

```text
voices\en_GB-alan-medium.onnx
```

with its matching JSON configuration.

The default voice model is approximately 64 MB and is downloaded separately when required.

### Speech-to-text

Default STT model:

```text
small.en
```

using Faster Whisper.

The model download is approximately 486 MB.

### Local LLM

Runtime:

```text
Ollama
```

Default model:

```text
qwen2.5:3b
```

Default local API:

```text
http://127.0.0.1:11434/api/chat
```

The LLM is used for free local explanations/summaries and optional reasoning requests. It does not own telemetry measurements or deterministic race decisions.

### FFmpeg

External FFmpeg is not a hard requirement for the current Faster Whisper/PyAV path. The launcher may report whether FFmpeg is available, but it is not mandatory for the normal Stable V2 configuration.

---

## 5. First-run commands

### Normal launch

```powershell
.\RaceEngineer.exe
```

### Check dependencies without starting the full application

```powershell
.\RaceEngineer.exe --check-only
```

### Run setup mode

```powershell
.\RaceEngineer.exe --setup
```

or:

```powershell
.\RUN_SETUP.bat
```

### Safe mode

```powershell
.\RaceEngineer.exe --safe-mode
```

### Console/debug launch

```powershell
.\RaceEngineer.exe --console
```

### First-run Python diagnostic

```powershell
.\RUN_FIRST_RUN_CHECK.bat
```

---

# 6. EA F1 telemetry setup

Race Engineer listens for the game's UDP telemetry feed. Configure the F1 game's telemetry options to match the Race Engineer receiver settings.

The established local setup uses:

```text
UDP address: 0.0.0.0 / local PC receiver
UDP port:    20777
```

For local use, the game sends telemetry to the same PC running Race Engineer. If using a different network layout, make sure Windows Firewall allows the configured UDP telemetry port.

After starting the game and entering a session, Race Engineer should begin receiving live telemetry automatically.

---

# 7. User data and upgrades

Stable V2 keeps runtime/user data outside the executable. Do not manually delete these folders when upgrading unless you intentionally want to remove that data.

Depending on the feature, Race Engineer maintains data such as:

- Driver Profile/history.
- Performance database.
- Track maps.
- References.
- Recordings/replays.
- Analysis files.
- Settings.
- Downloaded voices/models.
- Logs.
- Hardware configuration.

The release/update process is designed to preserve user data.

Before a major upgrade, use the application's backup functionality and keep at least one known-good backup separately from the installation folder.

---

# 8. Backup and restore

Stable V2 includes backup/restore work for both the Windows application data and the optional Ubuntu server.

Recommended release procedure:

1. Create a backup from the current working installation.
2. Keep the backup on a different disk or server location.
3. Install/update Race Engineer.
4. Start the application once.
5. Restore the backup if this is a clean installation or migration.
6. Verify Driver Profile, history, maps, settings and references before deleting the old installation.

The Stable V2 RC/Final testing process confirmed that the portable build could restore existing Race Engineer data from backup.

---

# 9. Optional Ubuntu Race Engineer server

The Ubuntu server is intended to be a lightweight always-on storage/API/backup machine for Race Engineer.

A dedicated one-script installer is included:

```text
SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
```

The script is designed for a fresh Ubuntu Desktop or Ubuntu Server installation.

## Default server configuration

```text
Hostname:       race-server
Linux user:     raceadmin   (or the sudo user running the script)
Samba share:    RaceEngineer
Server root:    /srv/race-engineer
API port:       8765
Backup folder:  /srv/race-engineer/backups/automated
Setup log:      /var/log/race-engineer-server-setup.log
```

The script installs/configures:

- OpenSSH Server.
- Samba.
- Python 3 and virtual environment support.
- FastAPI/Uvicorn Race Engineer server API.
- SQLite.
- Race Engineer server storage folders.
- systemd API service.
- systemd backup timer.
- verified server backups.
- UFW firewall rules.
- Samba access for the Race Engineer user.
- initial server health validation.
- initial verified backup.

---

# 10. Ubuntu server installation — step by step

## Step 1 — Install Ubuntu

Install a current supported Ubuntu Desktop or Ubuntu Server release on the server laptop/PC.

During Ubuntu installation, connect the machine to the same local network as the gaming PC.

A wired Ethernet connection is preferable for a permanent Race Engineer server, although Wi-Fi can work.

After installation, log into Ubuntu normally.

---

## Step 2 — Copy the setup script to Ubuntu

Copy:

```text
SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
```

to the Ubuntu machine, for example into the user's home directory.

Then open Terminal and run:

```bash
cd ~
chmod +x SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
sudo ./SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
```

The script writes its installation log to:

```text
/var/log/race-engineer-server-setup.log
```

If setup fails, inspect that file first.

---

## Step 3 — Samba password

During setup, the script asks for the Samba password for the server user.

Default user:

```text
raceadmin
```

You may use the same password as the Ubuntu account if desired, but Samba authentication is maintained separately.

If the setup was run non-interactively and the Samba password was not set, run:

```bash
sudo smbpasswd -a raceadmin
```

---

## Step 4 — What the server script creates

The main server root is:

```text
/srv/race-engineer
```

It creates storage areas for items such as:

```text
/srv/race-engineer/database
/srv/race-engineer/database/snapshots
/srv/race-engineer/backups/automated
/srv/race-engineer/backups/client_snapshots
/srv/race-engineer/backups/client_data
/srv/race-engineer/data/drivers
/srv/race-engineer/data/deleted_drivers
/srv/race-engineer/data/references
/srv/race-engineer/data/track_maps
/srv/race-engineer/data/setups
/srv/race-engineer/data/replays
/srv/race-engineer/data/recordings
/srv/race-engineer/data/validation
/srv/race-engineer/data/logs
/srv/race-engineer/data/exports
/srv/race-engineer/incoming
/srv/race-engineer/cache
```

The server-side application files are placed under:

```text
/srv/race-engineer/server/app
```

---

# 11. Server services

The setup script installs the Race Engineer API as a systemd service and the automated backup as a systemd timer.

### Check API service

```bash
systemctl status race-engineer-api --no-pager
```

### Restart API service

```bash
sudo systemctl restart race-engineer-api
```

### View recent API logs

```bash
sudo journalctl -u race-engineer-api -n 100 --no-pager
```

### Check backup timer

```bash
systemctl status race-engineer-backup.timer --no-pager
```

### Run a backup manually

```bash
sudo -u raceadmin /srv/race-engineer/server/app/race-engineer-backup.sh
```

---

# 12. Check the server API

On the Ubuntu server itself:

```bash
curl http://127.0.0.1:8765/api/health
```

For formatted JSON:

```bash
curl -s http://127.0.0.1:8765/api/health | python3 -m json.tool
```

From another PC on the LAN, replace the address with the Ubuntu server IP:

```text
http://SERVER-IP:8765/api/health
```

A healthy server should report an online service/database state.

---

# 13. Find the Ubuntu server IP

Run:

```bash
hostname -I
```

The setup script also prints the detected server IP when installation finishes.

For a permanent installation, the recommended approach is to reserve this IP for `race-server` in the router's DHCP reservation page.

The setup script intentionally does not force a static Linux IP because router/network configurations differ.

---

# 14. Connect Windows to the Ubuntu server

On the Windows gaming PC, open PowerShell or Command Prompt.

Map the Samba share as drive `R:`:

```powershell
net use R: \\race-server\RaceEngineer /user:raceadmin * /persistent:yes
```

Windows asks for the Samba password.

If hostname discovery does not work, use the Ubuntu server IP:

```powershell
net use R: \\SERVER-IP\RaceEngineer /user:raceadmin * /persistent:yes
```

Example:

```powershell
net use R: \\192.168.1.50\RaceEngineer /user:raceadmin * /persistent:yes
```

After mapping, `R:` should open in File Explorer.

---

# 15. Verify Race Engineer server synchronization

From the Race Engineer installation folder on Windows:

```powershell
.\.venv\Scripts\python.exe -m src.server_sync --status
```

A working connection should report the remote/server state rather than only local/offline storage.

The exact counters vary, but the status information includes items such as:

```text
state
pending
attempted
synced
failed
```

Stable V2 includes offline queue/fallback behaviour, so a temporary server outage should not stop live racing telemetry. Data that is eligible for synchronization can be queued and uploaded when the server becomes available again.

---

# 16. Server firewall

The one-click script enables UFW rules for:

- OpenSSH.
- Samba.
- Race Engineer API TCP port `8765`.

To inspect firewall state:

```bash
sudo ufw status
```

Expected relevant access includes SSH, Samba and TCP 8765.

---

# 17. Server backup system

Stable V2 configures an automated verified backup system on Ubuntu.

Backup root:

```text
/srv/race-engineer/backups/automated
```

The server tracks backup state including files such as:

```text
LAST_SUCCESS_UTC
LAST_VERIFY_UTC
BACKUP_STATUS.json
```

To inspect backup status:

```bash
cat /srv/race-engineer/backups/automated/BACKUP_STATUS.json | python3 -m json.tool
```

To trigger a backup manually:

```bash
sudo -u raceadmin /srv/race-engineer/server/app/race-engineer-backup.sh
```

The server API also contains a backup endpoint used by the Race Engineer integration.

---

# 18. Server restore / recovery

For recovery, keep the following principles:

- Do not overwrite a working database until a backup has been validated.
- Stop or isolate active writes before replacing authoritative database files.
- Keep the previous database/archive until the restored server passes its health checks.
- After restoring server data, verify the server API and then verify the Windows client's sync state.

Useful checks after a restore:

```bash
systemctl status race-engineer-api --no-pager
curl -s http://127.0.0.1:8765/api/health | python3 -m json.tool
```

Then on Windows:

```powershell
.\.venv\Scripts\python.exe -m src.server_sync --status
```

Race Engineer also contains client-side backup/restore functionality for migrating/restoring local data.

---

# 19. Server customization

The Ubuntu installer supports environment-variable overrides.

Example:

```bash
RACE_SERVER_USER=raceadmin \
RACE_SERVER_HOSTNAME=race-server \
sudo -E ./SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
```

Available script settings include:

```text
RACE_SERVER_USER
RACE_SERVER_HOSTNAME
RACE_SERVER_SHARE_NAME
RACE_SERVER_API_PORT
```

Defaults are:

```text
RACE_SERVER_USER       = current sudo user, otherwise raceadmin
RACE_SERVER_HOSTNAME   = race-server
RACE_SERVER_SHARE_NAME = RaceEngineer
RACE_SERVER_API_PORT   = 8765
```

For the standard Race Engineer configuration, keeping the defaults is recommended.

---

# 20. Common server troubleshooting

## Windows cannot open `\\race-server\RaceEngineer`

Check Ubuntu Samba:

```bash
systemctl status smbd --no-pager
```

Validate Samba configuration:

```bash
testparm -s
```

Check the server IP:

```bash
hostname -I
```

Then try mapping by IP instead of hostname.

### Recreate Samba password

```bash
sudo smbpasswd -a raceadmin
```

### Restart Samba

```bash
sudo systemctl restart smbd
```

---

## API is not responding

Check:

```bash
systemctl status race-engineer-api --no-pager
```

View logs:

```bash
sudo journalctl -u race-engineer-api -n 100 --no-pager
```

Restart:

```bash
sudo systemctl restart race-engineer-api
```

Test locally:

```bash
curl -s http://127.0.0.1:8765/api/health | python3 -m json.tool
```

---

## Windows mapped drive is stale

Remove the old mapping:

```powershell
net use R: /delete
```

Then reconnect:

```powershell
net use R: \\race-server\RaceEngineer /user:raceadmin * /persistent:yes
```

---

## Server is temporarily offline

Race Engineer Stable V2 is designed with local/offline fallback. Continue using the Windows application and restore the server connection later.

After the server is back online, check:

```powershell
.\.venv\Scripts\python.exe -m src.server_sync --status
```

Confirm pending items return to zero after successful synchronization.

---

# 21. Hardware notes

The Hardware workspace supports the Race Engineer hardware integrations without making the server responsible for live hardware communication.

The Windows gaming PC remains the main hardware/telemetry host. This includes Wheel Dashboard telemetry support and connected serial/HID devices configured in the application.

If a COM port changes after reconnecting a device, select the correct port again from the Hardware/Control Center configuration rather than editing server settings.

---

# 22. Network overview

Typical Stable V2 layout:

```text
                 EA SPORTS F1
                      |
                UDP telemetry
                      |
                      v
          +-------------------------+
          | Windows Gaming PC       |
          | RaceEngineer.exe        |
          |                         |
          | Telemetry / Coaching    |
          | PTT / STT / TTS / LLM   |
          | Performance Hub         |
          | Hardware / F1 Dashboard |
          +------------+------------+
                       |
             LAN sync / Samba / API
                       |
                       v
          +-------------------------+
          | Ubuntu Race Server      |
          | race-server             |
          |                         |
          | Persistent storage      |
          | API :8765               |
          | Samba RaceEngineer      |
          | Automated backups       |
          +-------------------------+
```

The server being unavailable should not stop the Windows application from receiving live F1 telemetry.

---

# 23. Development and release files

Important repository files include:

```text
RaceEngineer.exe
requirements.txt
runtime_dependencies.json
V2_SOURCE_FREEZE_MANIFEST.json
build_exe.ps1
build_release.ps1
SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
deploy_server_s14.ps1
src\
tests\
assets\
installer\
launcher\
tools\
```

`V2_SOURCE_FREEZE_MANIFEST.json` is part of the Stable V2 protected-source/release validation process and should not be removed merely as documentation cleanup.

---

# 24. Building the Windows release

The repository contains Windows build scripts including:

```powershell
.\build_exe.ps1
```

and:

```powershell
.\build_release.ps1
```

The release design keeps external AI/voice models outside the generated executable. The executable performs runtime checks and asks the user before downloading missing external components.

For the final branded Windows build, use the repository's supplied assets/build scripts so the Race Engineer icon, application metadata and installer branding are preserved.

---

# 25. Git LFS

`RaceEngineer.exe` is stored using Git LFS in the Stable V2 repository.

Verify with:

```powershell
git lfs ls-files
```

The expected result includes:

```text
RaceEngineer.exe
```

Do not remove `.gitattributes` or convert the executable back into a normal Git blob unless intentionally restructuring repository history.

---

# 26. Stable V2 release baseline

The final Stable V2 repository baseline is tagged:

```text
V2.9.1.3.5.49
```

This tag should remain unchanged.

Future development should use a new version/tag rather than modifying the contents represented by the Stable V2 final tag.

---

# 27. Quick installation checklist

For a completely new setup:

### Gaming PC

```text
1. Extract Race Engineer Stable V2.
2. Run RaceEngineer.exe --check-only.
3. Install/approve any required runtime dependencies.
4. Run RaceEngineer.exe.
5. Configure microphone, speaker, PTT and hardware as required.
6. Configure F1 UDP telemetry on port 20777.
7. Enter a game session and confirm live telemetry.
8. Restore an existing Race Engineer backup if migrating from another installation.
```

### Ubuntu server

```text
1. Install Ubuntu.
2. Copy SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh to Ubuntu.
3. chmod +x SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
4. sudo ./SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
5. Set the Samba password when requested.
6. Note the server IP printed at the end.
7. Reserve that IP in the router if possible.
8. Map \\race-server\RaceEngineer to R: on Windows.
9. Run src.server_sync --status on Windows.
10. Confirm pending=0 and successful remote/server state.
```

---

# 28. Useful command reference

### Windows

```powershell
# Dependency check
.\RaceEngineer.exe --check-only

# Normal startup
.\RaceEngineer.exe

# Setup mode
.\RaceEngineer.exe --setup

# Server sync status
.\.venv\Scripts\python.exe -m src.server_sync --status

# Map server share
net use R: \\race-server\RaceEngineer /user:raceadmin * /persistent:yes

# Remove server share mapping
net use R: /delete
```

### Ubuntu server

```bash
# API status
systemctl status race-engineer-api --no-pager

# Backup timer status
systemctl status race-engineer-backup.timer --no-pager

# API health
curl -s http://127.0.0.1:8765/api/health | python3 -m json.tool

# API logs
sudo journalctl -u race-engineer-api -n 100 --no-pager

# Restart API
sudo systemctl restart race-engineer-api

# Manual backup
sudo -u raceadmin /srv/race-engineer/server/app/race-engineer-backup.sh

# Samba status
systemctl status smbd --no-pager

# Samba config validation
testparm -s

# Server IP
hostname -I

# Firewall
sudo ufw status
```

---

## License / distribution

Race Engineer Stable V2 – License / Distribution Notice

This repository contains the Race Engineer Stable V2 project release.
It is provided solely for educational and experimental purposes.

- Not for commercial use
- Not for sales, resale, or monetization
- Intended for learning, testing, and non‑commercial experimentation

No open‑source license is currently applied.
Until a dedicated LICENSE file is explicitly added, the availability of this repository
must not be interpreted as granting rights under any particular open‑source license.
---

## Release status

**Race Engineer Stable V2 — V2.9.1.3.5.49** is the protected final baseline for this release line.
