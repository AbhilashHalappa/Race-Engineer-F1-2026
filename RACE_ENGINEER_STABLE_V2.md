# Race Engineer — Stable V2

**Telemetry • Strategy • Coaching**

**Internal build:** V2.9.1.3.5.49  
**Release candidate:** Stable V2 RC4 — One-Script Ubuntu Server Setup

## Purpose of this file

This is the single maintained documentation file for the Race Engineer repository and release package. During development, every checkpoint, hotfix, validation pass, roadmap revision, continuation prompt and release note was kept as a separate Markdown/text file so work could be audited and resumed safely. That was useful while the product was changing rapidly, but it created hundreds of documentation files that are not appropriate for the Stable V2 repository/package.

For RC3, the historical documentation has been consolidated here and the redundant standalone checkpoint/note files have been removed. Generated test logs and obsolete launch artifacts are intentionally not retained because they can be regenerated and are not authoritative runtime inputs.

## Stable V2 RC3 cleanup scope

- Uses V2.9.1.3.5.47 Stable V2 RC2 as the functional base.
- No telemetry, scoring, Corner Coach, strategy, replay, hardware, server-sync, data ownership, backup/restore, TTS/STT or LLM behavior is changed.
- Keeps one Markdown documentation file: `RACE_ENGINEER_STABLE_V2.md`.
- Keeps `requirements.txt`, `runtime_dependencies.json` and `V2_SOURCE_FREEZE_MANIFEST.json` because they are active build/runtime/validation inputs, not documentation clutter.
- Removes historical version-specific `.md` files after preserving their contents below.
- Removes old note `.txt` files after preserving useful content below.
- Removes generated regression/smoke logs and obsolete historical validation outputs that can be regenerated.
- Removes obsolete version-specific V1 launcher batch files, the old PyInstaller spec/reference path, and an accidental source backup file.
- Release packaging now copies this single documentation file instead of three separate Markdown files.

## Current first-run summary

Run `RaceEngineer.exe` from the extracted package. The launcher checks Python 3.13, the local virtual environment, required Python packages, Piper voice, Whisper STT, Ollama and the configured local LLM model. Large runtimes/models are not embedded in the EXE. Missing dependencies are offered only with user confirmation.

Useful launcher switches: `--check-only`, `--safe-mode`, `--setup`, and `--console`.

User data, downloaded voices, recordings, settings, references, maps, logs and analysis data remain outside the launcher binary and are preserved by the installer/update rules.

## Current release validation status

The V2.9.1.3.5.47 RC2 base had already passed the Stable V2 automated audit and the branded portable build was confirmed by the user to launch successfully and restore data from backup. RC3 is a repository/package cleanup pass only; functional source is kept frozen except for release/version metadata and documentation/build references. The complete RC3 regression passes **1339 tests + 383 subtests with 0 failures**.

## Stable V2 RC4 one-script Ubuntu server setup

- Uses V2.9.1.3.5.48 RC3 as the application/runtime base.
- Adds one self-contained root script: `SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh`.
- Intended for a fresh Ubuntu installation; no separate server deployment files need to be copied to the Ubuntu machine.
- Installs OpenSSH, Samba, Python/venv, SQLite/curl tools and UFW prerequisites.
- Creates `/srv/race-engineer` storage, data, database, cache and verified backup trees.
- Installs the current S14.4 FastAPI/Uvicorn backend and systemd service.
- Installs the verified daily backup service/timer and runs an initial verified backup.
- Configures the `RaceEngineer` Samba share and prompts for the Samba password instead of hard-coding credentials.
- Configures firewall rules for SSH, Samba and TCP 8765.
- Sets the default server hostname to `race-server` and prints the Windows `net use R:` command at completion.
- Does not force a static IP because LAN/router configuration is site-specific; use a DHCP reservation for the server laptop.
- No Race Engineer telemetry, coaching, scoring, strategy, replay, hardware or client persistence behavior is changed.

Fresh Ubuntu usage:

```bash
chmod +x SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
sudo ./SETUP_RACE_ENGINEER_SERVER_UBUNTU.sh
```

The script defaults to Ubuntu/Samba user `raceadmin` and hostname `race-server`. Optional overrides can be supplied through `RACE_SERVER_USER`, `RACE_SERVER_HOSTNAME`, `RACE_SERVER_SHARE_NAME`, and `RACE_SERVER_API_PORT`.

---

# Consolidated documentation archive

The sections below preserve the contents of the previous documentation/checkpoint files so development history remains available without hundreds of separate files.


---

## Archived source: `README.md`

# Race Engineer — Stable V2

**Telemetry • Strategy • Coaching**

Stable V2 RC2 introduces the official Race Engineer visual identity: a shared application/installer icon, branded Control Center header, consistent Windows titles, and release assets under `assets/brand/`. Runtime dependency policy remains unchanged: Python/packages, Piper, Whisper and the local LLM are checked/downloaded separately and are not bundled into `RaceEngineer.exe`.

> **V2.0.1.4 hotfix:** Live Corner Feedback now publishes per physical T-corner instead of waiting for a multi-turn CoachingZone to finish. N/A metrics disable the scale/marker and show an explicit missing-evidence reason. Corner Performance uses the 0-100 score on its bar and shows measured time gain/loss separately.

> **V2.0.1 Live Corner Intelligence:** adds visual-only completed-corner score/grade, dominant measured issue and compact reference-relative deltas on top of the V2.0.0 evidence contract. The existing CORNER COACH measurement pipeline remains authoritative; no extra speech queue is introduced. The former SPEED COACH UI is now PERFORMANCE COACH, Control Center overlay launchers show full names, and Track Learning is separated as proactive instructional guidance rather than reference-relative performance judgment. All driving overlays still start closed.

> **V2.0.0 Score Contract & Evidence Model:** adds transparent evidence-backed technique scoring downstream of the protected V1.9.2.1 deterministic measurement pipeline. Missing or incompatible evidence remains N/A; Control Center opens normally while all driving overlays start closed; detailed post-LIVE V2 Performance Review narrative will use the free local LLM path without giving the LLM authority over measurements or decisions.

> **V1.9.2.1 Performance History Correctness:** preserves V1.9.2.0 source hardening while fixing LIVE history persistence when auto reports are disabled, preventing replay coach-report generation from mutating legacy driver history, synchronizing final refreshed coach data to the Performance Hub, and restricting wins/podiums to actual race sessions. Windows EXE/installer work remains unchanged.

> **V1.9.2.0 Final Source Hardening:** full local/F1 source audit, clean-stint pit-strategy evidence gates, supplied 210,860-packet real-race validation, long-replay/high-rate telemetry hardening, Control Center coaching selectors, runtime radio cooldown integration, golden validation fixtures, SQLite-safe Performance Hub diagnostics, and 845-test regression closure. Windows EXE/installer work is intentionally unchanged in this source-only pass.

> **V1.8.0.0 Driving Performance Engine Completion:** SPEED COACH now uses geometry-first physical turn segmentation across all supported F1 tracks, path-curvature apex authority, true apex-speed measurement, time-domain coasting/throttle-pickup comparisons, richer steering-shape analysis, stronger corner confidence/outlier rejection, and reference-relative minimum-speed/throttle-pickup/exit-speed efficiency. Legacy references without usable world-path data retain an explicit low-confidence minimum-speed proxy fallback rather than being silently relabeled.

> **V1.7.0.0 Speed Coach + Straight Line Coach Integration:** The former CORNER COACH overlay is now **SPEED COACH**, with independently switchable **CORNER COACH** and **STRAIGHT LINE COACH** children. Straight coaching reuses the same compiled reference/full-track performance model, reports only measured same-distance time/speed/input differences, protects upcoming corner PRE airtime, and writes into the unified Speed Coach transcript. Straight coaching defaults OFF on upgrade so existing users get no surprise radio chatter.

> **V1.5.0.0 Pre-Release Hardening:** formal benchmark instrumentation, automatic compact validation bundles, coaching refinements, measured strategy evidence upgrades, and consolidated local setup/validation UI.

> **V1.4.0.1 Weekend Transition + Transcript + Pit Window Hotfix:** Session Best updates remain lap-boundary-safe without fragmenting validation, Practice/Qualifying/Race transitions reset stale session state, persistent Race Engineer/CORNER COACH transcripts are written under `analysis/transcripts`, and EA game pit-window laps are now first-class deterministic pit evidence.

#
> **V1.4.0.0 Replay / Session Analysis:** `/sessions` now supports cached replay indexing, corner jump, coaching timeline, selected-lap comparison, two-session comparison, distance-aligned telemetry/delta traces, search/filtering, and explicit report/validation association.
 V1.3.5.0 — Parallel Plan Completion

This build completes the agreed parallel A–E implementation plan on top of the frozen V1.3.0.3 live radio/CORNER COACH/reference baseline.

## Completed workstreams

- **A — Coach Intelligence**: deterministic advice-outcome memory, repeated-attempt tracking, improve/stable/regress/solve states, focus retirement/promotion, radio improvement queries.
- **B — Driver Analytics**: technique consistency, chronological trends, persisted driver history, cross-session per-corner aggregation, recurring-issue resolution, session-vs-session deterministic comparison.
- **C — Track Intelligence**: matched-distance line comparison, robust world-position outlier gate, geometry-derived apex, early/late apex classification, pinched-exit evidence, steering-correction comparison, explicit track/board/kerb/SF/pit landmark store and PRE distance overrides.
- **D — Analysis/UI**: expanded post-session JSON/HTML, driver/reference telemetry traces, racing-line visualization, stable latest report aliases, dedicated read-only LAN coaching page at `/coach`, coaching/history JSON endpoints.
- **E — Validation/Data Quality**: evidence-bearing lap/reference compatibility, potential-lap source evidence, rejection/warning summaries, reconciliation evidence and standalone `*_validation.json` output.

## Frozen/high-risk systems deliberately preserved

The live map/player pointer, rival reference compiler, UDP decoder core, CORNER COACH PRE/POST ownership, and existing driver-radio priority path were not redesigned.

## Run

From PowerShell:

```powershell
cd D:\Abhilash\ChatGPT\Racing_Engineer
.\.venv\Scripts\python.exe -m src.main --overlay
```

or use:

```text
RUN_RACE_ENGINEER_V1.3.5.0.bat
```

When the LAN dashboard is enabled, the normal F1 dashboard remains at `/` and the coaching analysis page is available at `/coach`.

## Validation

Final regression for this package:

```text
717 tests passed
383 subtests passed
0 failures
```

The implementation remains deterministic: unavailable measurements remain unavailable, incompatible samples are not silently mixed, and line/technique classifications are suppressed when supporting evidence is insufficient.


## V2.0.3.2 Legacy Performance DB Migration Hotfix

Fixes startup on existing V1/V2/V3 Performance History databases by migrating the `sessions` table before creating indexes that depend on V4 profile columns. Existing live history is preserved and assigned to the migrated local driver profile.

## V2.0.3.1 Local Driver Profiles
Performance history is owned by a local human profile selected at application startup. In-game F1 driver/team changes are session metadata and do not split the human driver history. Performance Hub uses the same interactive browser UI inside Control Center and supports session/game-mode filtering.

## V2.0.3.4 Selected Reference Analysis + Detailed Corner + AI Summary
- Analysis Reference now updates a separate deterministic selected-reference comparison instead of changing graphs only.
- DELTA is recalculated from the selected reference speed traces, so rival selection visibly changes the comparison.
- Detailed corner review exposes recorded-reference braking, release, trail, turn-in, apex, minimum speed, throttle, full-throttle and exit evidence.
- Selected-reference corner comparison is shown separately and never rewrites the historical authoritative score/diagnosis.
- Full-session and per-corner deterministic data summaries are separate from on-demand local Ollama AI explanations.
- AI summaries are explanation-only; deterministic measurements remain authoritative.


## V2.0.3.5 Live History Autosave + Backend Track Learning + Hub Navigation
- Performance Hub now autosaves LIVE analysis after every completed lap even when REC is OFF.
- Autosave is coalesced on a dedicated worker; full .areplay packet recording remains optional.
- Same-session rows are progressively updated, so multi-lap sessions retain the latest lap count and review evidence.
- Persistent track-map learning/refinement is backend-owned at authoritative lap boundaries; dashboard code is render-only.
- Performance Hub adds BACK and REFRESH controls.


---

## Archived source: `FIRST_RUN.md`

# Race Engineer Stable V2 — first run

## Launch

Start `RaceEngineer.exe` from the extracted Stable V2 folder. The EXE is a small Windows bootstrapper; it does **not** contain Python, Piper voice files, Whisper weights, Ollama, or the LLM model.

On every launch it performs a quick dependency check. It only asks about components that are missing, and it does not download anything without your confirmation.

## Dependency flow

1. **Python 3.13** — required. If it is missing, the launcher offers to open the official Python Windows download page. Install 64-bit Python 3.13, then run `RaceEngineer.exe` again.
2. **Local `.venv` + Python packages** — required. The launcher asks before creating `.venv` and before installing `requirements.txt` from PyPI.
3. **Piper engineer voice** — feature dependency for TTS. If the configured voice is missing, the launcher can download `en_GB-alan-medium` from the official `rhasspy/piper-voices` repository and validates the ONNX SHA-256.
4. **Whisper `small.en`** — feature dependency for PTT/STT. If it is not already cached, the launcher can download the official `Systran/faster-whisper-small.en` model through Hugging Face.
5. **Ollama + `qwen2.5:3b`** — feature dependency for the free local LLM explanation path. If Ollama is missing, the launcher offers the official Windows download page. If Ollama is installed but the model is missing, it asks before running `ollama pull qwen2.5:3b`.
6. **PTT** — no separate model/download exists for PTT itself. HID/audio requirements are covered by the Python package check and PTT transcription uses the Whisper model above.

If an optional feature dependency is declined or unavailable, Race Engineer can still launch with its deterministic telemetry/core features; the launcher clearly lists which feature will be unavailable.

## First application setup

After dependencies are ready, the existing local setup wizard opens on first application launch.

1. In EA F1 telemetry settings enable UDP telemetry, set UDP IP to `127.0.0.1`, and use UDP port `20777` unless you changed it.
2. Select the microphone and engineer output device.
3. Select/confirm the wheel HID device and PTT logical button if PTT is required.
4. Select the GamePad Pro Receiver COM port or leave it on Auto-detect.
5. Enable the LAN dashboard if required.
6. The Private-network Windows Firewall rule is optional and is only added after explicit user action.
7. Save setup and restart Race Engineer.

## Useful launcher switches

- `RaceEngineer.exe --check-only` — dependency check only; do not start the app.
- `RaceEngineer.exe --safe-mode` — start without PTT/wheel bridge; optional AI/voice model downloads are skipped during that launch.
- `RaceEngineer.exe --setup` — reopen the setup wizard.
- `RaceEngineer.exe --console` — launch with the Python console visible for troubleshooting.

## Diagnostics

- `logs/bootstrapper/stable_v2_launcher.log` records dependency checks/download results.
- `analysis/diagnostics/bootstrapper_status.json` records the latest dependency state.
- `logs/crash/` contains application crash reports.


---

## Archived source: `RADIO_COMMAND_REFERENCE.md`

# Race Engineer Radio Command Reference

This release keeps the radio deterministic and offline. Runtime control commands call the same receiver setters as the UI, so the on-screen buttons and voice-control state remain synchronized.

## Race Engineer controls
Use `enable`, `disable`, `toggle`, or `status` with:
- Race Engineer
- PRE coach
- POST coach
- lap summary
- positive coach
- race coach

## CORNER COACH controls
Use `enable`, `disable`, `toggle`, or `status` with:
- CORNER COACH
- corner voice
- corner PRE
- corner POST
- map gain loss
- gain loss voice
- damage coach

## Radio system controls
- speech / TTS
- push to talk / PTT
- speech recognition / STT
- LLM / AI reasoning
- recording

## Coaching profile
- `set coaching mode auto`
- `set coaching mode race engineer`
- `set coaching mode performance coach`
- `set coaching mode track learning`
- `set coaching mode qualifying`
- `set coaching mode time trial`
- `set coaching mode silent analysis`
- `set radio detail minimal|normal|detailed`
- `voice speed slow|normal|fast`
- `next voice`
- `use voice <installed Piper voice name>`

## Help
- `voice control help`
- `control status`
- `radio commands` for the existing telemetry/factual command help

The same page is served by the LAN dashboard at `/radio-help`.

## SPEED COACH hierarchy (V1.7.0.0)

- `enable/disable Speed Coach` — parent master for the shared Speed Coach runtime/overlay.
- `enable/disable Corner Coach` — independently controls corner coaching.
- `enable/disable Straight Line Coach` — independently controls straight-line coaching.
- `enable/disable Straight Voice` — controls spoken completed-straight feedback without disabling straight analysis/visuals.
- Corner PRE/POST remain corner-only controls; Map G/L remains the shared full-track measured performance layer.
- Straight Line Coach defaults OFF after upgrade; enabling it starts from the current point and does not replay already-completed straights.


---

## Archived source: `LOCAL_DATA_LAYOUT.md`

# Race Engineer local data layout — V2.0.3.9

Race Engineer now keeps mutable runtime data separate from source code and packaged assets.

```text
Racing_Engineer/
├─ settings/                         # user configuration (kept stable)
├─ voices/                           # packaged/local TTS models
├─ analysis/
│  ├─ performance_history_live.sqlite3  # authoritative LIVE performance history (compatibility-stable)
│  └─ driver_history.json               # legacy/compatibility driver history
└─ user_data/
   ├─ sessions/
   │  ├─ session_library.json
   │  ├─ reports/
   │  └─ replay_index/
   ├─ recordings/
   │  └─ archive/
   ├─ tracks/
   │  ├─ track_landmarks.json
   │  └─ maps/
   ├─ references/
   │  ├─ uploaded/
   │  └─ imported/                   # created when imported packages are installed
   ├─ validation/
   │  ├─ bundles/
   │  ├─ corner_coach/
   │  └─ transcripts/
   ├─ diagnostics/
   ├─ logs/
   │  ├─ crash/
   │  └─ ptt/
   └─ cache/
```

## Migration behavior

At normal application startup, `src.app_paths.migrate_legacy_layout()` creates the structure and moves legacy mutable folders/files into their matching locations without overwriting a newer destination. Locked files do not block startup.

The authoritative Performance History SQLite database and `driver_history.json` intentionally remain in `analysis/` in this release. Their paths are part of the protected V1.9.2.1 history contract and moving them would risk creating an empty second database on an upgraded installation. A future schema migration can relocate them only with an explicit database hand-off/verification step.

## Storage ownership

- `REC OFF`: compact live Performance Hub evidence remains in the authoritative performance database plus bounded session analysis data.
- `REC ON`: the same performance data is kept, plus full `.areplay` files under `user_data/recordings/`.
- Track learning writes to `user_data/tracks/`.
- Rival/reference packages write to `user_data/references/`.
- Replay indexes, reports, validation traces and diagnostics are separated so they can be cleaned independently without touching authoritative performance history.


---

## Archived source: `STABLE_V2_RELEASE_AUDIT.md`

# Stable V2 Release Audit — RC1

**Audit candidate:** V2.9.1.3.5.46 Stable V2 Release Audit RC1  
**Product version:** V2.0.0  
**Audit base:** `RE_V2.9.1.3.5.45_WEATHER_FUEL_CLIPPING_HOTFIX_FULL.zip`  
**Base SHA-256:** `643faa883c96801a820002c06641b63650fbf66892af7e1786fe23e08ad2bb95`  
**Protected core baseline:** V2.0.6.4 policy / V2.0.11 source-freeze manifest baseline V2.9.1.3.5.37 with documented justified deviations.

## Audit status

The automated Stable V2 audit phase passes. The V2 validation matrix passes **92 tests**. The complete regression passes **1330 tests + 383 subtests with 0 failures**. Windows release static validation passes all checks, Python source compilation passes, and the CLI smoke test identifies the product as **Race Engineer Stable V2 / V2.0.0**.

This is an **RC1**, not the final Stable V2 freeze/tag. Two external acceptance gates remain: (1) run the new Windows launcher on the real Race Engineer Windows PC through at least one missing-dependency path, and (2) complete/attach the trusted recording acceptance required by V2.0.11. No final Git tag should be created until those gates are accepted.

## Release-audit findings and fixes

### Runtime issue fixed — first server-retention pass

`src/server_sync.py` initialized the last-retention monotonic timestamp to `0.0`. That unintentionally tied the first retention decision to Windows uptime, so a PC booted less than the configured retention interval ago could skip the first idle verified retention pass. RC1 uses `None` to mean that no pass has run yet. The first idle pass now runs once immediately; later passes retain the same throttle interval.

Validation: `tests/test_v291_storage_retention_driver_soft_delete.py::test_verified_bulk_retention_keeps_latest_10_recording_sessions_and_prunes_other_classes` and the complete regression.

### Upgrade/config-export compatibility fixed

`src/settings_ui.py` exported the HID/PTT mapping only from the new canonical path. An older installation could still have `logs/ptt/hid_mapping.json` before the data-layout migration runs. RC1 checks the canonical and legacy locations and writes one mapping into the configuration export. No PTT runtime behavior was changed.

### Release branding corrected

`src/main.py` still showed old V1.8 / V2.9.1.3.5.14 wording in console/help output and an old V1.9.2.0 folder warning. RC1 changes those user-visible strings to **Stable V2 / V2.0.0** only; runtime behavior is unchanged.

### Test-harness maintenance

The audit found stale tests rather than product failures: one schema assertion hard-coded DB schema 4 while the current schema is 6, and three old practice tests depended on sibling historical extraction folders. Those checks now use the current schema constant and the V2 source-freeze manifest, which is the current authority for justified post-baseline changes.

## Stable V2 Windows EXE design

`RaceEngineer.exe` is now a small Windows x64 **dependency bootstrapper**, not a PyInstaller dependency bundle. It must stay beside the application `src` folder and `runtime_dependencies.json` in the portable/installed package.

On launch it checks:

- **Python 3.13**. If absent, it asks before opening the official Python Windows download page.
- **Local `.venv`**. If absent, it asks before creating it.
- **Python packages** from `requirements.txt`: PySide6, Piper runtime, sounddevice, pygame, HID, serial, QR code and faster-whisper. It asks before installing missing packages from PyPI.
- **Piper engineer voice**. A valid configured custom voice is respected. Otherwise it asks before downloading `en_GB-alan-medium`; the default ONNX is checksum-verified.
- **PTT/STT**. PTT itself has no separate model; HID/audio Python dependencies are checked and Whisper `small.en` is checked as the PTT transcription model. If absent, it asks before downloading it.
- **Local LLM**. Ollama is checked separately. If Ollama is absent the launcher asks before opening its official Windows download page. If Ollama is present but `qwen2.5:3b` is missing, it asks before `ollama pull qwen2.5:3b`.
- **ffmpeg** is informational only; the current faster-whisper/PyAV path does not treat external ffmpeg as a hard dependency.

Optional voice/STT/LLM dependencies may be declined; the deterministic telemetry/overlay core can still launch after a clear warning. Core Python/runtime requirements may not be skipped.

No Python runtime, Piper ONNX, Whisper model, Ollama runtime or LLM model is embedded in the EXE.

**RaceEngineer.exe**  
Size: **2,527,232 bytes**  
SHA-256: `20b2b8a5723f23681a8e15f889a1fccca999646faa65ae4064bb2a33406ac27c`

The installer rules were also updated to explicitly preserve `user_data` and downloaded `voices` in addition to legacy mutable folders, and the release staging script removes Python bytecode/cache files.

## Automated evidence

- Full regression: `STABLE_V2_FULL_REGRESSION.txt` — **1330 passed, 383 subtests passed**.
- V2.0.11 automated matrix: `V2_STABLE_AUDIT_REPORT.json` — **92 passed**, source freeze valid.
- Windows release static checks: `STABLE_V2_WINDOWS_STATIC_VALIDATION.json` — all checks true.
- CLI smoke: `STABLE_V2_CLI_SMOKE.txt` — Stable V2 identity and arguments load successfully.
- `python -m compileall -q src tools` — pass.
- Windows PE build: Go cross-build succeeded as PE32+ x86-64 GUI executable.

## What has deliberately not changed

The Stable V2 audit did not redesign telemetry decoding, scoring, corner-coach logic, strategy decisions, reference compilation, replay mechanics, driver-skill calculations, hardware telemetry protocol, overlays beyond the already user-verified V2.9.1.3.5.45 clipping fix, or server synchronization architecture. The only runtime-source changes introduced by this audit are the justified retention first-pass correction, HID mapping export compatibility, and release-identification strings.

## Remaining release gates

1. On the actual Windows Race Engineer PC, extract the portable RC1 to a fresh short path and run `RaceEngineer.exe --check-only`. Test at least one intentionally missing optional dependency and confirm the Yes/No prompt, download/install path, second-run detection and `bootstrapper_status.json` result.
2. Run `RaceEngineer.exe` normally and confirm Control Center, F1 UDP telemetry, audio output, microphone/PTT, wheel/HID, wheel-dashboard serial telemetry, LAN dashboard and Ollama-backed post-LIVE explanation path as applicable.
3. Attach the trusted recording acceptance required by the V2.0.11 matrix. The automated report currently records that acceptance as pending because no trusted `.areplay` input is present in this audit environment.
4. After those gates pass, freeze the final Stable V2 package and create the final Git tag. Do not change proven core behavior during that last step.


---

## Archived source: `STABLE_V2_RC2_BRANDING_VALIDATION.md`

# Stable V2 RC2 Branding Validation

Build: **V2.9.1.3.5.47**  
Release label: **Stable V2 RC2 — Branded**

## Visual identity

Product: **Race Engineer**  
Release family: **Stable V2**  
Tagline: **Telemetry • Strategy • Coaching**

Primary assets are stored in `assets/brand/`:

- `race_engineer.ico` — Windows multi-resolution icon
- `race_engineer_icon_*.png` — native/app icon ladder
- `race_engineer_mark.svg` — scalable product mark
- `race_engineer_wordmark.png` — horizontal wordmark
- `race_engineer_header.png` — compact application header
- `installer_wizard.bmp` / `installer_small.bmp` — Inno Setup branding
- `brand_preview.jpg` — identity preview
- `BRAND.md` — color/usage summary

## Functional validation

Full automated regression executed after the branding changes:

`1335 passed, 383 subtests passed, 0 failed`

The protected V2 source-freeze check also passes. The only newly justified protected-file deviation is the Control Center/window presentation change in `src/overlay/window.py`.

## EXE branding build rule

`build_exe.ps1` now uses `go-winres` when it is present on the Windows build machine. This embeds:

- Race Engineer EXE icon
- per-monitor-aware GUI manifest
- file/product version metadata
- File Description: `Race Engineer Stable V2`

The prebuilt portable launcher remains small and continues to keep large runtimes/models external.


---

## Archived source: `RACE_ENGINEER_V2_REVISED_ROADMAP.md`

# Race Engineer V2 Roadmap
## V2.0 Performance Intelligence, Live Coach & Performance Review

**Baseline:** RaceEngineer V1.9.2.1 Performance History Correctness  
**Scope:** local/personal F1 25/26 Windows application.  
**Primary design rule:** measurements and deterministic diagnosis remain authoritative; scores are a visual/analysis representation of those measurements, not the source of race or coaching decisions.

---

# 1. Architecture change from the first V2 draft

The first V2 roadmap treated scoring too uniformly. The revised system separates performance intelligence into three execution lanes:

## A. LIVE PERFORMANCE — during driving
Fast, bounded, low-distraction calculations that are useful immediately after a corner.

Allowed live outputs:
- completed-corner score/grade,
- brake-point delta,
- minimum/apex-speed delta,
- throttle-pickup delta,
- full-throttle delay,
- exit-speed delta,
- corner time loss/gain,
- dominant high-confidence issue,
- confidence/quality internally,
- current-focus progress.

Live UI rule:
- normally show one result only,
- auto-hide quickly,
- no radar charts,
- no full technique report,
- no expensive cross-session aggregation,
- no low-confidence conclusions.

## B. LAP / STINT INTELLIGENCE — after sufficient evidence
Calculations that need a complete lap or repeated valid observations.

Outputs:
- lap technique score,
- valid-corner coverage,
- biggest loss,
- recurring mistake,
- improvement/regression,
- realistic available gain,
- next-lap focus,
- short stint focus,
- technique-group provisional averages where sample count is sufficient.

## C. PERFORMANCE REVIEW — post-session / analysis mode
Detailed calculations that benefit from multiple laps and can use more CPU.

Outputs:
- overall session technique score,
- technique radar,
- every-corner scoring,
- braking/mid/exit breakdown,
- steering smoothness/corrections,
- racing-line consistency,
- multi-lap consistency,
- replay-linked telemetry,
- interactive performance map,
- setup A/B analysis,
- persistent skill profile,
- cross-session trends,
- 20-minute practice plan.

---

# 2. Core scoring principles

## 2.1 Score is downstream of measurement

Authoritative flow:

`Telemetry -> Quality Gates -> Measurements -> Diagnosis -> Estimated Time Cost -> Coaching`

Scoring is a parallel presentation layer:

`Measurements + Diagnosis + Confidence + Compatibility -> Score`

A low score must never be used by itself to generate a coaching claim.

## 2.2 Evidence tiers

### Tier 1 — Single-corner evidence
Suitable for:
- live corner score,
- brake-point score,
- min-speed score,
- throttle-pickup score,
- exit score,
- immediate grade.

### Tier 2 — Multi-corner / complete-lap evidence
Required for:
- lap technique score,
- lap-level braking/throttle groups,
- next-lap focus,
- realistic gain ranking.

### Tier 3 — Multi-lap evidence
Required for:
- trail-braking consistency,
- steering smoothness score,
- racing-line consistency,
- session technique groups,
- recurring weakness,
- session radar.

### Tier 4 — Multi-session LIVE history
Required for:
- driver skill profile,
- long-term strengths/weaknesses,
- five-session trends,
- solved issues,
- setup trend conclusions.

Replay may analyse all tiers temporarily but must not mutate persistent live history.

## 2.3 Score quality rules
- Missing/untrusted input = `N/A`, never 50/100.
- Invalid/compromised laps do not contribute.
- Wet/dry incompatibility blocks direct scoring where comparison would mislead.
- Traffic, pit phase, SC/VSC, significant damage and incompatible tyre/fuel states remain authoritative quality gates.
- A score always stores its confidence and sample count.
- Do not publish a session/group score until minimum evidence is satisfied.
- Score weighting must be explicit and inspectable.
- Store the raw measurements behind every score.

## 2.4 Score model versioning
Every stored score must include:
- `score_model_version`,
- reference identity/version,
- measurement confidence,
- sample count,
- compatibility state,
- raw evidence IDs.

Historical raw measurements remain authoritative so future scoring models can be recalculated without rewriting the original telemetry evidence.

---

# 3. Fine-tuning changes to the current system before V2 UI work

These are architectural refinements required by the new requirements.

## 3.1 Reuse existing measurements instead of recalculating telemetry
V2 must consume the existing CornerAnalysis / CoachingZone / reference measurement pipeline wherever possible.

Do not create a second independent braking/apex/throttle detector for scoring.

## 3.2 Separate live compute from review compute
Add two explicit paths:

`LivePerformanceAccumulator`
- bounded state,
- no heavy historical queries,
- produces fast corner/lap summaries,
- cadence-safe with existing high-rate telemetry decoupling.

`PerformanceReviewBuilder`
- runs at session finalization or on-demand,
- can aggregate complete session telemetry/history,
- creates detailed review artifacts.

## 3.3 Preserve the existing coach priority system
Live scores must not create another speech queue.

Live visual scoring submits through the existing race-context/coaching arbitration if speech is requested.

Priority remains:
1. critical/race control/damage/pit,
2. tyre/brake danger,
3. required race engineering,
4. CORNER COACH PRE,
5. eligible post-corner performance feedback,
6. summaries/low-priority information.

## 3.4 Use measured time loss as the primary importance signal
Technique scores are descriptive.

Issue priority remains primarily based on:
- measured time cost,
- confidence,
- repetition,
- actionability,
- recent response to coaching.

This prevents a visually low score in a low-value corner from outranking a larger time loss elsewhere.

## 3.5 Stabilize scores
Scores must not oscillate heavily because of tiny measurement changes.

Use:
- deadbands,
- bounded normalization,
- confidence weighting,
- minimum sample counts,
- robust median/trimmed aggregation for multi-lap summaries.

Do not smooth raw telemetry evidence itself merely to make scores look better.

## 3.6 Reference-relative, not universal-driver judgment
Initial V2 scores are based on comparison with the active compatible reference and the driver's own consistency.

Do not claim an absolute universal driving-skill score without a validated population dataset.

UI wording should say:
- `Technique score vs active reference`
or
- `Session technique score`

not:
- `Global skill rating`.

## 3.7 Session-condition segmentation
If conditions materially change during a session, split review evidence into compatible segments rather than averaging incompatible laps together.

Examples:
- dry -> wet,
- major setup change,
- major damage state,
- materially different tyre state where required,
- restarted session.

---

# 4. Revised delivery roadmap

## V2.0.0 — Performance Measurement & Score Contract

Goal: build the scoring kernel without changing existing race/coaching behaviour.

Implement:
- `TechniqueMetricEvidence`
- `TechniqueScore`
- `CornerTechniqueScore`
- `LapTechniqueScore`
- confidence/sample-count fields
- score-model versioning
- explicit N/A state
- deterministic normalization functions
- raw evidence links
- compatibility checks
- score monotonicity tests

Initial score dimensions:
- braking point,
- brake release,
- trail braking,
- turn-in,
- min/apex speed,
- throttle pickup,
- time to full throttle,
- exit speed,
- steering control,
- racing-line consistency.

No major UI redesign in this release.

Acceptance:
- same telemetry produces the same score,
- worsening a trusted metric cannot improve its score,
- insufficient evidence stays N/A,
- no existing deterministic coaching decision changes.

---

## V2.0.1 — Live Corner Intelligence

Goal: useful immediate feedback with minimal distraction.

Compute after confirmed eligible corner exit:
- corner score,
- corner grade,
- dominant issue,
- estimated loss/gain,
- brake-point delta,
- min-speed delta,
- throttle-pickup delta,
- exit-speed delta.

Optional compact overlay examples:
- `T4  82 GOOD`
- `BRAKE 9 m EARLY`
- `MIN SPEED -5 km/h`
- `THROTTLE +0.32 s LATE`

Behaviour:
- one primary live result,
- auto-hide,
- confidence gate,
- no live radar,
- no session score,
- no heavy history queries,
- suppressed when race context owns attention.

Acceptance:
- does not measurably regress telemetry latency,
- no extra audio queue,
- no spam in pit/SC/VSC/damage contexts.

---

## V2.0.2 — Lap & Stint Intelligence

Goal: convert repeated corner measurements into useful next-lap direction.

After each valid lap:
- lap technique score,
- valid scored-corner coverage,
- biggest measured loss,
- best improvement,
- repeated issue,
- realistic available gain,
- current focus,
- next-lap focus.

After enough observations:
- provisional braking score,
- provisional throttle score,
- provisional corner-speed score,
- consistency indicator.

Rules:
- complete-lap evidence required,
- no score from one isolated corner,
- no group score below minimum sample count.

---

## V2.0.3 — Performance Review Core

Goal: generate the detailed post-session analysis.

Produce:
- session technique score,
- average measured time available,
- best/potential/reference laps,
- per-lap score/delta table,
- full corner table,
- technique-group averages,
- confidence/data-quality summary,
- strengths,
- biggest opportunities,
- session improvement trend.

Technique groups:
- big braking zones,
- medium/light corners,
- braking,
- trail braking,
- throttle,
- steering,
- control/consistency,
- min/apex speed,
- exits,
- racing line.

This is where the radar/spider chart belongs.

---

## V2.0.4 — Detailed Corner Technique Breakdown

For every eligible corner:

### Braking
- brake-point delta,
- peak pressure,
- release,
- trail distance/time,
- phase time cost.

### Mid-corner
- turn-in,
- path/apex,
- minimum speed,
- steering corrections,
- phase time cost.

### Exit
- throttle pickup,
- time to full throttle,
- exit speed,
- traction/slip evidence when trustworthy,
- phase time cost.

Output:
- one dominant diagnosis,
- secondary evidence in review only,
- confidence,
- total measured time loss.

---

## V2.0.5 — Every-Corner Performance Map

Upgrade the existing map for review mode.

Show:
- corner number,
- score,
- grade,
- dominant diagnosis,
- measured time cost.

Heat-map modes:
- score,
- time loss/gain,
- speed deficit,
- braking delta,
- throttle delta,
- racing-line deviation.

Clicking a corner opens its full analysis.

Live map remains lightweight; detailed heat maps are review-mode features.

---

## V2.0.6 — Replay-Linked Telemetry Workstation

Create synchronized review charts for:
- speed,
- brake,
- throttle,
- steering,
- gear,
- ERS,
- delta,
- reliable G channels.

Features:
- shared distance cursor,
- driver/reference traces,
- map follows cursor,
- current corner follows cursor,
- click graph -> seek replay,
- click map/corner -> zoom graphs,
- jump to brake point/apex/throttle pickup,
- next/previous coaching event,
- replay play/pause/speed.

Do not duplicate or abandon the indexed/memory-mapped replay architecture.

---

## V2.0.7 — Next-Lap Focus & 20-Minute Practice Planner

### Live/lap component
After a valid lap select only 1–2 focus items.

### Review component
Create a structured short practice plan:

1. Baseline — 2–3 valid laps
2. Primary issue — highest measured time-cost recurring weakness
3. Verification — determine whether it improved
4. Secondary issue — only after primary issue improves
5. Summary — time recovered, remaining opportunity, next-session focus

The plan is generated from measured evidence, not generic coaching templates.

---

## V2.0.8 — Setup Lab

Local setup library:
- setup values,
- track,
- session,
- conditions,
- tyre,
- assists where relevant,
- notes,
- measured result.

A/B comparison requires comparable evidence.

Compare:
- lap/sectors,
- straight speed,
- braking stability,
- min speed,
- throttle/exit,
- tyre temperatures,
- wear,
- ERS/fuel context,
- consistency.

Output observations only.

Never claim an optimal setup without evidence.

Example:
`Setup B gained 0.12 s through T3–T5 but lost 3 km/h on the main straight.`

If conditions are incompatible:
`No reliable comparison.`

---

## V2.0.9 — Driver Skill Profile

Persistent LIVE-only per-driver/per-track profile.

Track:
- braking,
- trail braking,
- throttle,
- steering,
- control,
- line consistency,
- corner speed,
- exit technique.

Show:
- latest session,
- recent robust average,
- personal best,
- five-session trend,
- recurring weakness,
- recently solved issue,
- measured time recovered.

Replay is read-only for persistent history.

---

## V2.0.10 — Performance Hub V2

Keep Control Center a normal Windows application window.

Performance Hub tabs:

### OVERVIEW
- session technique score,
- measured available gain,
- current primary focus,
- technique radar,
- recent trend.

### LAPS
- lap time,
- delta,
- score,
- quality,
- biggest loss,
- improvement.

### CORNERS
- every-corner score,
- diagnosis,
- time cost,
- confidence.

### TELEMETRY
- synchronized traces.

### MAP
- interactive heat maps.

### REPLAY
- linked timeline and events.

### PRACTICE
- next-lap and 20-minute plans.

### SETUP LAB
- setup library and A/B evidence.

### PROGRESS
- live cross-session skill profile.

Detailed review UI is separate from the minimal live overlay.

---

## V2.0.11 — Validation, Calibration & Source Freeze

### Scoring
- unit tests,
- monotonicity,
- boundary/deadband tests,
- N/A behaviour,
- confidence gates,
- sample-count gates,
- score-version migration/recalculation.

### Telemetry quality
- invalid lap,
- pit/outlap,
- traffic,
- SC/VSC,
- damage,
- wet/dry,
- tyre/fuel compatibility,
- session restart.

### Runtime
- live latency benchmark,
- no-spam overlay,
- arbitration tests,
- memory bounds,
- long-session stability.

### Review
- live/replay parity,
- replay read-only persistence,
- multi-driver isolation,
- graph/map/replay cursor synchronization,
- setup comparability gates,
- session-condition segmentation.

### Recording acceptance
Re-run all existing trusted evidence:
- supplied Melbourne damage/SC/pit recording,
- full Practice -> Qualifying -> Race weekend recording,
- stored Time Trial / Qualifying / Race recordings,
- CORNER COACH validation corpus.

---

# 5. Live vs Review ownership matrix

| Feature | Live | Lap/Stint | Performance Review |
|---|---|---|---|
| Raw corner measurements | Yes | Yes | Yes |
| Corner score | Yes | Yes | Yes |
| Corner grade | Yes | Yes | Yes |
| Dominant issue | Yes | Yes | Yes |
| Immediate time-loss estimate | Yes | Yes | Yes |
| Brake-point score | Yes | Yes | Yes |
| Min/apex-speed score | Yes | Yes | Yes |
| Throttle-pickup score | Yes | Yes | Yes |
| Exit score | Yes | Yes | Yes |
| Detailed trail-brake score | Limited | Yes | Yes |
| Steering-shape analysis | Internal/minimal | Limited | Full |
| Racing-line consistency | No | Limited | Full |
| Lap technique score | No | Yes | Yes |
| Technique-group score | No | Provisional | Full |
| Session technique score | No | No | Yes |
| Radar chart | No | No | Yes |
| Every-corner report | No | No | Yes |
| Full phase breakdown | No | No | Yes |
| Next-lap focus | No | Yes | Yes |
| 20-minute practice plan | No | No | Yes |
| Replay-linked telemetry | No | No | Yes |
| Interactive heat map | Minimal current map only | No | Yes |
| Setup A/B analysis | No | No | Yes |
| Persistent skill profile | No | No | LIVE sessions update after review |

---

# 6. What we should NOT copy from the inspiration

The screenshots are useful as product inspiration, but Race Engineer should not blindly copy:
- proprietary score formulas,
- proprietary labels/thresholds,
- visual artwork/layout,
- generic AI causality claims,
- setup recommendations without F1 telemetry evidence.

We will implement equivalent product capabilities using our own deterministic F1 telemetry model and UI.

---

# 7. Preservation rules

- V1.9.2.1 is the protected baseline.
- Preserve all V1.9.2.0 source hardening and V1.9.2.1 Performance History fixes.
- Do not change pit/strategy logic without new evidence.
- Do not regress supplied-real-race validation.
- Keep persistent Performance Hub history LIVE-only and driver-scoped.
- Replay remains read-only for persistent history.
- Preserve normal-window Control Center.
- Preserve indexed/memory-mapped replay and bounded checkpoints.
- Preserve weekend session stitching.
- Preserve high-rate telemetry/decision decoupling.
- Preserve clean-stint tyre/pit strategy evidence gates.
- Preserve CORNER COACH PRE/POST scheduling and race-critical priority unless a failing regression requires change.
- Unknown remains unknown.
- Scores are transparent and evidence-backed.
- Windows EXE/PyInstaller/Inno work remains untouched unless explicitly requested.

---

# 8. Recommended implementation order

1. V2.0.0 — Score Contract & Evidence Model
2. V2.0.1 — Live Corner Intelligence
3. V2.0.2 — Lap/Stint Intelligence
4. V2.0.3 — Performance Review Core
5. V2.0.4 — Detailed Corner Breakdown
6. V2.0.5 — Every-Corner Performance Map
7. V2.0.6 — Replay-Linked Telemetry Workstation
8. V2.0.7 — Practice Planner
9. V2.0.8 — Setup Lab
10. V2.0.9 — Driver Skill Profile
11. V2.0.10 — Performance Hub V2
12. V2.0.11 — Validation / Calibration / Source Freeze

This order intentionally builds the measurement/score contract before UI, keeps the live path lightweight, and delays expensive analysis to the review path.

---

# User-approved V2 execution addendum

These rules are authoritative additions to the revised roadmap:

1. **Post-LIVE Performance Review LLM** — Detailed Performance Review narrative/explanation features from V2.0.3 onward must use the free local LLM path (Ollama/local model), while deterministic measurements, quality gates, diagnoses, time-cost estimates and scores remain authoritative. The LLM may explain/summarize trusted evidence; it may not invent telemetry facts, replace quality gates, change persistent measurements, or become the source of a coaching/race decision.
2. **Startup visibility** — Control Center remains a normal Windows application window. No driving overlay opens automatically. Coach, Corner Coach, Race Engineer/Qualifying Engineer, Driver/Reference, delta/lap, tyres/fuel/weather/standings/history/ERS, F1 Dash and replay overlays are user-opened only.
3. **Protected baseline** — V1.9.2.1 deterministic systems remain frozen unless new evidence or a failing regression justifies reopening them.

---

## V2.0.11 execution status addendum — 2026-10-03

- Started from protected Git baseline **V2.9.1.3.5.37**.
- **V2.0.8 Setup Lab remains cancelled by user scope**; its V2.0.11 setup-comparability validation item is N/A / skipped and must not reopen Setup Lab.
- V2.0.11 Phase 1 uses `V2_SOURCE_FREEZE_MANIFEST.json` plus `tools/run_v2_final_validation.py` to enforce protected-source and automated-validation coverage.
- Final source freeze is not allowed until trusted recording acceptance and the final full regression are complete.


---

## Archived source: `FEATURES_ROADMAP.md`

# Race Engineer — Feature Roadmap

Target benchmark: Trophi.ai-level driving coaching, while preserving Race Engineer's deterministic F1 race-engineering, strategy, telemetry, replay, hardware, native overlay, and LAN dashboard strengths.

Current development: **V1.5.0.0 — Pre-Release Hardening**

Frozen CORNER COACH baseline: **V1.2.0.4 — Replay Timeline + Reference Marker Hotfix**

Frozen native/LAN UI baseline: **V0.9.19.8.6.24**

V1.3.0.1 adds the CORNER COACH **DMG COACH** override. Damage remains measured and reported, but when the user explicitly enables the switch, damage alone does not invalidate the lap for coaching. All non-damage validity/quality gates remain authoritative.

V1.3.0.2 makes DMG COACH authoritative in the live CORNER COACH path as well as offline/report eligibility. With the switch OFF, significant damage suppresses PRE/POST/G-L voice while map/progress/measurement continue; with it ON, coaching resumes from the current point without stale back-fill. PTT microphone-open failures now release radio ownership correctly and cannot permanently silence coaching.

V1.3.5.0 completes the agreed parallel A–E implementation plan without reopening the frozen live-map/reference baseline. It adds deterministic advice-outcome memory, cross-session per-corner progress/comparison, geometry-aware racing-line diagnostics, verified landmark/SF/pit metadata with PRE overrides, a dedicated LAN coaching page/editor, expanded post-session reporting, and standalone machine-readable validation artifacts. Final regression: **718 tests passed + 383 subtests passed**.

V1.6.0.0 completes the source-side Windows productization layer: packaged launcher, first-run device/setup UI, upgrade-safe local data, crash/update/firewall/QR tooling, portable/installer build definitions, and Windows display diagnostics. Full regression: **786 tests passed + 383 subtests passed**. Actual EXE/installer compilation and physical Windows device/DPI validation remain target-machine acceptance steps.

## Active product scope

The active roadmap is now **local/personal Windows use only**. Cloud accounts/backups, hosted/community leaderboards or reference services, mobile/VR products, team telemetry services, and additional-sim adapters are deferred and are not release blockers.

V1.0.1 polish adds live packet-freshness gates, front/rear close-traffic suppression, compromised-lap latching for pit/traffic/race-control/damage conditions, stronger coaching queue replacement/staleness, corrected Performance Coach PRE behavior, and local settings/diagnostic command-line tools.
V1.0.1.1 restores visible coaching switch names in Control Center and adds reference-aligned coaching turn numbers to native/LAN track maps.
V1.0.1.2 seeds first-lap PRE guidance from a preloaded external reference, resumes technique coaching after stable moderate aero damage, suppresses damage-sensitive speed-outcome calls, and persists turn IDs with learned map geometry for immediate later-run labels.
V1.0.1.3 elevates PRE-corner coaching above all routine radio/coaching traffic, evaluates PRE before lap/positive summaries, allows PRE to interrupt an in-progress lap summary, and reduces stable moderate-damage recovery to 3 seconds while preserving critical safety priority.
V1.0.1.5 adds an ENGR runtime voice switch for coach-only sessions and removes race coaching per-lap/cooldown quotas so external-reference PRE can cover every reference turn from lap 1 and POST can report every deterministically eligible slower corner.

V1.1.0.12 adds an automatic asynchronous CORNER COACH validation trace under `analysis/corner_coach_validation/`. The trace records physical-corner order, CoachingZone order, phase transitions, 10 m live distance/timing samples, PRE/POST eligibility and suppression reasons, generated coach radio, actual audio start, diagnoses, zone/straight attribution, and per-lap reconciliation. It is the acceptance artifact for Melbourne/Austria/Shanghai end-to-end validation and removes the need to diagnose coach sequencing from screenshots. Pace-only rival diagnosis is also hardened so untrusted raw ghost peak-brake/speed channels cannot drive coaching claims.
V1.1.0.13 fixes every issue exposed by the first five-lap Melbourne trace: CORNER COACH PRE/POST receive dedicated radio scheduling, T1 PRE wraps across S/F and is attributed to the next lap, CoachingZone event ownership no longer leaks T12 slowdown into T13-T14, approach starts are clamped to physical geometry, the exact S/F endpoint finalizes the last straight/reconciliation, and final-lap distance wrap closes the race even when EA does not increment current_lap after the chequered flag. Validation schema v2 tracks circular PRE delivery by target lap.
V1.1.0.14 adds a deadline-driven single-channel CORNER COACH speech sequencer: POST is full/compact/suppressed based on protected next-PRE airtime, urgent PRE pre-empts POST or an older PRE when required, exact Piper WAV duration is checked before playback, and stale coaching is never allowed to continue into the next zone. Validation schema v3 records deterministic delivery outcomes. The Race Engineer TURN bars now hide unsupported braking/throttle comparisons for pace-only Time Trial rivals and use the clean compiled speed model for minimum/exit speed. Normal Session Recording is OFF by default while Rival Reference Capture remains independent.

V1.1.0.15 is the reliability-recovery/internal-validation snapshot after the V1.1.0.14 live trace showed excessive PRE drops and POST suppression. Speech budgeting is calibrated to the measured en_GB-alan-medium Piper voice, compact PRE is the real-time default, POST airtime reservation skips PRE calls already emitted, and the CORNER COACH visual transcript is decoupled from actual audio start. Melbourne Race, Melbourne Qualifying, Austria Time Trial, and all three stored rival references (Melbourne/Austria/Shanghai) are now part of the internal regression set.

V1.2.0.0 closes the current three-track P0 milestone: CORNER COACH generation now models its one-channel speech backlog in game time before submitting radio, PRE may pre-empt only when required to meet its hard deadline, POST is full/compact/micro or visual-only depending on real remaining airtime, and impossible replay/live distance jumps are treated as compromised telemetry instead of dozens of false missed corners. The Lap-End Coach Summary, Potential Lap Engine, quality/condition compatibility gates, automatic coach report, pace-only TURN metrics, and offline delivery benchmark are now integrated and regression-tested.
V1.2.0.1 fixes runtime PRE/POST toggle semantics exposed by the Melbourne mode-matrix test: POST-only ignores disabled PRE airtime, PRE/POST re-enabled mid-lap never back-fill already-passed zones, disabled message-family reservations are released immediately, and validation records live `coach_config_change` transitions.

---

## Status legend

- [ ] Not started
- [~] In progress / partial
- [x] Complete
- [!] Needs validation / redesign

Priority:
- **P0** = required for next coaching milestone
- **P1** = high value
- **P2** = important polish / expansion
- **P3** = later / ecosystem

---

# 1. Driving Performance Engine — P0

Goal: mathematically measure *why* the driver is gaining or losing time against the active reference lap.

- [x] Corner segmentation for every supported F1 track — generic measured-geometry pipeline plus published physical-turn-count coverage for the full supported circuit set
- [x] Automatic corner start / braking / turn-in / apex / exit boundaries — measured braking/turn-in/exit plus V1.8 path-curvature apex with physical-geometry fallback
- [x] Braking point detection
- [x] Brake onset distance comparison vs reference
- [x] Peak brake pressure comparison
- [x] Brake-release distance comparison
- [x] Trail-braking distance measurement
- [x] Brake duration comparison
- [x] Coasting distance and time detection per corner — `coasting_m` and `coasting_s` are measured and compared deterministically
- [x] Turn-in point detection with sustained steering threshold/hysteresis
- [x] Apex point detection — V1.8 path-curvature apex is primary when measured world-path geometry is trustworthy, with physical/min-speed fallback
- [x] Minimum corner speed comparison
- [x] Apex speed comparison — true path/physical apex speed is measured separately from minimum-speed proxy and compared reference-relative
- [x] Throttle pickup point detection
- [x] Pickup-to-full-throttle distance and time comparison — both metre and seconds domains are retained and compared
- [x] Exit speed comparison
- [x] Entry/apex/exit gear and per-corner shift-count capture
- [x] Rich steering-shape comparison — mean/peak steering rate, corrections, smoothness and unwind time/distance are measured reference-relative
- [x] Entry / mid / exit time-loss attribution in CornerAnalysis
- [x] Corner-level time-gain / time-loss calculation
- [x] Straight-line loss separation from corner-driving loss — V0.9.25.0 matched-distance straight analysis
- [x] Corner measurement confidence/data-quality score — completeness, density, continuity, geometry and apex confidence feed deterministic diagnosis confidence
- [x] Outlier/data-quality gates — invalid/start-anchor checks plus speed/steering spike rejection, monotonic-time filtering, continuity and geometry-quality penalties

Acceptance target:
- Every valid corner produces a structured deterministic analysis object.
- No coaching statement is spoken unless the underlying measurement passes confidence and validity checks.

---

# 2. Corner Intelligence Engine — P0

Goal: convert raw telemetry differences into one clear, actionable diagnosis per corner.

- [x] Detect early braking
- [x] Detect late braking
- [x] Detect excessive brake pressure
- [x] Detect insufficient brake pressure
- [x] Detect abrupt brake release — V0.9.25.0 brake-release ramp distance/time analysis
- [x] Detect weak trail braking
- [x] Detect excessive trail braking
- [x] Detect excessive coasting
- [x] Detect low minimum speed
- [x] Detect early turn-in
- [x] Detect late turn-in
- [x] Detect early apex — based on the current minimum-speed apex proxy
- [x] Detect late apex — based on the current minimum-speed apex proxy
- [x] Detect throttle pickup too late
- [x] Detect throttle pickup too early / traction-limited application — only when extra measured slip supports it
- [x] Detect slow transition to full throttle
- [x] Detect wrong / inefficient gear choice — current implementation compares apex gear
- [x] Detect poor exit-speed conversion
- [x] Detect line / path deviation when position telemetry supports it — V0.9.25.0 matched-distance world X/Z deviation
- [x] Determine whether loss is primarily ENTRY / MID / EXIT
- [x] Estimate time cost of each issue from measured phase/corner loss
- [x] Select the dominant issue instead of listing every difference

Output example structure:

```text
CornerAnalysis
  corner
  time_loss_s
  phase
  diagnosis
  brake_point_delta_m
  min_speed_delta_kph
  throttle_point_delta_m
  exit_speed_delta_kph
  repeat_count
  confidence
  actionability
```

---

# 3. Coaching Priority Engine — P0

Goal: speak only the most valuable correction at the right time.

- [x] Candidate issue scoring — V0.9.20.2 ranks already loss-guarded primary candidates
- [x] Time-cost weighting
- [x] Confidence weighting
- [x] Repeat-frequency weighting
- [x] Actionability weighting
- [x] Suppress tiny / low-value differences — V0.9.20.1.2 whole-corner + V0.9.20.1.1 per-phase guards
- [x] Avoid multiple corrections in one message — V0.9.20.3 post-corner speech emits one deterministic correction at a time
- [x] Cooldown per corner / issue
- [x] Avoid repeating unchanged advice every lap
- [x] Promote repeated mistakes over one-off mistakes
- [x] Detect improvement after previous coaching — first-vs-latest measured issue cost with 15 ms trend deadband
- [x] Move focus to the next issue once the current one improves — V0.9.25.0 also adds explicit improvement acknowledgement
- [x] Respect critical race-engineer message priority
- [x] Suppress coaching during heavy race-control / damage / pit events
- [x] Speech-window calculation based on distance to next braking zone
- [x] Queue or drop messages when there is insufficient safe speaking time

Suggested deterministic score:

```text
priority = estimated_time_cost × confidence × repeat_factor × actionability
```

---

# 4. Immediate Post-Corner Coaching — P0

Goal: provide short feedback after a corner while the information is still useful.

- [x] Trigger analysis at confirmed corner exit
- [x] Speak only when the corner produced meaningful loss / gain
- [x] Short one-sentence correction
- [x] Positive reinforcement when a coached issue improves
- [x] Skip speech if another braking zone is imminent — V0.9.20.3 requires >=3.5 s to next measured braking zone and drops at <=1.5 s
- [x] Avoid overlapping with engineer / race-control messages
- [x] Configurable post-corner coaching frequency — persistent runtime POST switch plus deterministic limits
- [x] Option to disable positive calls and speak only corrections — POS switch

Example calls:

```text
"Turn 6, braking about ten metres too early."
"Turn 9, good entry, but throttle was late on exit."
"Turn 3 improved — seven metres later on the brake."
```

---

# 5. Multi-Lap Pattern Detection — P0

Goal: coach persistent habits rather than reacting to single-lap noise.

- [x] Store per-corner issue history
- [x] Mean / median braking-point error — generic issue magnitude statistics cover brake-point issues
- [x] Mean minimum-speed deficit — generic issue magnitude statistics cover minimum-speed issues
- [x] Mean throttle-pickup error — generic issue magnitude statistics cover throttle-pickup issues
- [x] Repeat-count tracking
- [x] Issue persistence score
- [x] Improvement trend detection
- [x] Regression detection
- [x] Consistency measurement per corner — V1.3.1.0 adds stddev/range plus chronological observed trends
- [x] Session-wide recurring driving-pattern detection
- [x] Promote recurring high-cost issues to coaching focus

Example:

```text
T6 early braking
  laps observed: 4
  mean error: 11.4 m early
  estimated mean loss: 0.17 s
  confidence: 0.94
```

---

# 6. Lap-End Coach Summary — P0

Goal: automatically summarize each valid lap in a few seconds.

- [x] Lap time
- [x] Delta vs active reference
- [x] Delta vs previous lap
- [x] Biggest time-loss corner
- [x] Second-biggest opportunity when useful
- [x] Best-improved corner
- [x] Current coaching focus
- [x] Potential lap estimate
- [x] Skip summary when race context is too busy
- [x] Separate Time Trial / Practice / Qualifying / Race wording

Example:

```text
"1:24.308, three tenths quicker. Biggest loss is Turn 9 braking, about two tenths."
```

---

# 7. Potential Lap Engine — P0

Goal: show what lap time the driver has already demonstrated in pieces.

- [x] Sector theoretical best
- [x] Corner-segment theoretical best
- [x] Filter invalid / compromised segments
- [x] Avoid combining incompatible track-condition samples
- [x] Potential lap vs current best
- [x] Potential lap vs reference
- [x] Show remaining realistic gain

Dashboard / report metrics:

```text
BEST LAP
POTENTIAL LAP
REFERENCE LAP
REALISTIC AVAILABLE GAIN
```

---

# 8. Post-Session Coach Report — P1

Goal: automatically turn every recorded session into a useful coaching report.

- [x] Automatic report generation when session ends
- [x] Best lap
- [x] Reference lap
- [x] Potential lap
- [x] Total reference gap
- [x] Ranked biggest time-loss corners
- [x] Entry / mid / exit breakdown
- [x] Recurring driving patterns
- [x] Braking consistency
- [x] Throttle consistency
- [x] Corner-speed consistency
- [x] Best strengths
- [x] Biggest opportunities
- [x] Improvement trend through the session
- [x] Per-corner telemetry drill-down
- [x] Speed trace
- [x] Brake trace
- [x] Throttle trace
- [x] Gear trace
- [x] ERS trace where available
- [x] Delta trace
- [x] Driver vs reference overlay
- [x] Export JSON
- [x] Export HTML report
- [ ] Optional PDF report — deferred; HTML/JSON are authoritative local report formats for current scope

---

# 9. Interactive Performance Coach Radio — P1

Goal: allow natural questions about measured driving performance.

Add deterministic intents for:

- [x] "Where am I losing time?"
- [x] "Why am I slow in Turn X?"
- [x] "Am I braking too early?"
- [x] "Where should I brake for Turn X?"
- [x] "How is my braking?"
- [x] "How is my throttle application?"
- [x] "Which corner should I work on?"
- [x] "Did I improve Turn X?"
- [x] "Compare this lap with reference."
- [x] "What is my biggest mistake?"
- [x] "What is my potential lap?"
- [x] "Where did I gain time?"
- [x] "Where did I lose time this lap?"
- [x] "How consistent am I?"
- [x] "What should I focus on next lap?"

Rule:
- The deterministic analysis object is authoritative.
- Optional LLM may rephrase/explain, but never invent measurements.

---

# 10. Session Coach Memory — P1

Goal: make coaching behave like an engineer who remembers previous advice.

- [x] Track last advice per corner/issue — V1.3.1.0 `AdviceOutcomeMemory`
- [x] Track whether advice outcome improved/worsened using measured evidence; driver intent is deliberately never inferred
- [x] Detect improvement relative to previous coached lap
- [x] Avoid repeating solved advice as active focus
- [x] Confirm successful correction with conservative repeated-clear evidence
- [x] Retire solved issue
- [x] Promote next-highest unresolved issue
- [x] Keep session coaching focus state
- [x] Preserve focus through normal lap transitions and short pauses/replay pause
- [x] Reset correctly on session/reference change; track change is covered by session reset

V1.3.1.0 rule: one absent issue is only `improved`; two consecutive measured clear attempts retire it as `solved`, unless measured cost has already fallen below the solved threshold.

---

# 11. Coaching Modes — P1

Goal: adapt behavior to the driver's purpose.

- [x] RACE ENGINEER mode
- [x] PERFORMANCE COACH mode
- [x] TRACK LEARNING mode
- [x] QUALIFYING mode
- [x] TIME TRIAL mode
- [x] SILENT ANALYSIS mode
- [x] User-selectable coaching verbosity
- [x] Mode-specific message priorities — existing safety/radio/coaching arbitration remains authoritative
- [x] Mode-specific dashboard focus — shared native/LAN focus metadata is driven by coaching mode and exposed through the Control Center/dashboard snapshot

Suggested behavior:

## Race Engineer
Race control, damage, tyres, brakes, fuel, ERS, pit strategy, gaps. Minimal driving coaching.

## Performance Coach
Maximum driver-technique analysis with critical race alerts still allowed.

## Track Learning
Pre-corner guidance + post-corner correction.

## Qualifying
Tyre preparation, traffic, ERS, out-lap, push-lap, delta and focused coaching.

## Time Trial
Maximum performance comparison and rapid iteration.

## Silent Analysis
Record and analyze only; no speech.

---

# 12. Track Learning / Pre-Corner Guidance — P1

Goal: help drivers learn circuits before they can drive them consistently.

- [x] Braking-point preview — reference-backed PRE target
- [x] Suggested gear from trusted reference where available
- [x] Corner-number call
- [x] Corner-sequence call for CoachingZone complexes
- [x] Reference-based target speed
- [x] Configurable PRE timing window + per-track/per-corner distance override through TrackLandmarkStore metadata
- [x] Detailed coaching verbosity profile
- [x] Minimal coaching verbosity profile
- [x] Disable automatically in race mode unless race coaching is explicitly enabled
- [x] Avoid calls during race-control emergencies; race PRE has deliberate close-traffic exceptions for coach-first coverage

Example:

```text
"Turn 1, brake just after the 100 board, fourth gear."
```

---

# 13. Track Landmark Database — P1

Goal: replace abstract distances with landmarks drivers can see.

- [x] Local track landmark metadata format
- [x] Verified 150/100/50/braking-board metadata supported and automatically imported when explicit reference/track metadata provides it; visual boards are never inferred from distance alone
- [x] Manual verified kerb start/end metadata supported
- [x] Pit-entry and pit-exit landmark metadata
- [x] Start/finish landmark exposure in the landmark store
- [x] Corner-number metadata
- [x] Manual calibrated distances plus explicit metadata import/export workflow
- [x] Per-track manual overrides
- [x] Local human-editable LAN workflow complete; hosted/community sharing is explicitly deferred P3

---

# 14. Racing Line Analysis — P1

Goal: compare actual vehicle path against reference path.

- [x] World-position sample coverage plus robust median/MAD path-deviation outlier filtering
- [x] Local reference-tangent coordinate transform for signed lateral offset
- [x] Driver path reconstruction at matched 5 m distance bins
- [x] Reference path reconstruction at matched 5 m distance bins
- [x] Absolute and signed lateral deviation measurement
- [x] Entry phase path-deviation comparison
- [x] Apex-window path-deviation comparison
- [x] Exit phase path-deviation comparison
- [x] Early / late apex classification from geometry-derived peak curvature
- [x] Pinched-exit detection using turn-direction-aware signed lateral exit evidence
- [x] Path-aware steering-correction comparison against reference
- [x] Driver/reference racing-line visualization in post-session report and LAN coaching page

---

# 15. Deterministic Technique Metrics — P1

Goal: provide transparent driver-development metrics without opaque AI scores.

- [x] Braking-point consistency
- [x] Brake-release consistency
- [x] Trail-braking consistency
- [x] Minimum-speed consistency/trend + reference-relative efficiency metric
- [x] Apex/min-speed-position consistency
- [x] Throttle-pickup consistency/trend + reference-relative efficiency metric
- [x] Exit-speed consistency/trend + reference-relative efficiency metric
- [x] Gear-choice consistency
- [x] Overall lap-time consistency and chronological progress
- [x] Explain how every metric is calculated in exported metadata
- [x] Consistency metrics require at least three eligible samples

---

# 16. Driver Progress History — P1

Goal: show improvement across sessions and dates.

- [x] Persist session summary history locally
- [x] Track best lap progression
- [x] Track potential-lap progression
- [x] Track best/reference and potential/reference gap progression
- [x] Cross-session per-corner technique trend aggregation
- [x] Cross-session per-corner technique aggregation
- [x] Cross-session consistency aggregation
- [x] Recurring issue persistence and measured resolution across stored sessions
- [x] Track-specific history data is exposed on the LAN coaching page/API
- [x] Latest-vs-previous and selectable data-model session comparison exposed to LAN analysis clients

---

# 17. Reference Lap Ecosystem — P1/P2

Goal: move beyond only personal references.

- [x] Personal best reference support — current-session best remains a first-class reference mode
- [x] Rival/reference capture support — existing auto-armed TT rival workflow preserved
- [x] Friend reference import — portable checksummed ZIP packages install locally without replacing existing references
- [x] Reference export — selected stored references export from Control Center as portable friend packages
- [x] Reference metadata schema — V2 package manifest covers game/track/car/driver/session/assists/setup/conditions/tyre/fuel plus provenance
- [x] Game version validation — new captures retain packet/game identity; known cross-game mismatches are blocked while legacy unknowns remain explicit
- [x] Track validation — track ID and length are compatibility blockers when both are known
- [x] Car/team validation where relevant — team mismatch blocks only for known unequal-performance contexts
- [x] Assists metadata — TC/ABS/gearbox values are preserved and compared as warnings
- [x] Setup metadata — formal setup object plus custom-setup provenance is preserved when available
- [x] Weather / track-condition metadata — weather and temperatures preserved; condition mismatches surfaced without guessing
- [x] Tyre metadata — formal tyre object is preserved/compared when source telemetry provides it
- [x] Fuel metadata — formal fuel object is preserved/compared when source telemetry provides it
- [ ] Community reference packs — intentionally deferred/out of current local-only scope
- [ ] Curated fast-driver reference packs — intentionally deferred/out of current local-only scope
- [x] Install reference from UI — Control Center IMPORT REF validates and installs local packages; hosted download remains deferred with community services
- [x] Reference quality / validity checks — compiler quality, package checksums, raw fingerprint and authenticated compiled-model authority are validated

---

# 18. Coaching UI / Performance Pages — P1

Native overlay remains frozen until explicitly reopened for redesign.

LAN / future analysis UI additions:

- [x] Dedicated `/coach` LAN coaching summary page
- [x] Current focus/advice-outcome card
- [x] Corner drill-down table exposes measured diagnosis evidence
- [x] Biggest-loss corners list
- [x] Potential-lap display
- [x] Reference-gap display
- [x] Driver measured strengths/opportunities
- [x] Corner technique/diagnosis table
- [x] Session trend data/history + dedicated local Performance Hub trend visualization
- [x] Post-session speed/brake/throttle/gear/ERS/delta driver-reference graphs
- [x] Technique metrics/history panel
- [x] Coaching mode selector — persistent Control Center selector wired to runtime coaching settings
- [x] Speech verbosity selector — persistent Control Center selector wired to runtime speech/coaching verbosity

---

# 19. Race Engineer + Performance Coach Integration — P1

Goal: make race context override coaching when appropriate.

- [x] Unified message arbitration — V1.3.8.0 final race-context arbiter runs after Race Engineer + CORNER COACH + Performance Coach generation and preserves critical/TTS priority ownership
- [x] Critical damage always overrides coaching — explicit critical race-context gate added on top of existing damage suppression
- [x] Race-control calls override routine coaching — Safety Car/VSC/pit context suppresses routine technique coaching through the unified arbiter
- [x] Pit decisions override routine coaching — pit-active/service context owns the message path and suppresses technique coaching
- [x] Tyre / brake danger overrides routine coaching — critical wear/puncture/brake-temperature gates added
- [x] Suppress technique coaching while defending / attacking when required — deterministic close-combat gate added
- [x] Prefer race-exit advice during close combat — combat entry emits a short traction/exit-focused race message and suppresses normal technique PRE/POST
- [x] Adapt coaching based on tyre condition — allowed technique calls are adapted with tyre-conservation context
- [x] Adapt coaching based on fuel / ERS state — allowed technique calls are adapted for fuel-save and low-ERS contexts
- [x] Adapt coaching based on damage — stable damage-aware coaching is supported while severe damage remains a hard blocker
- [x] Adapt coaching based on wet/dry conditions — wet-context technique calls prioritize traction and forecast transition state is exposed
- [x] Resume performance coaching when race context calms down — arbiter is stateless against current measured context, so normal coaching resumes automatically when blockers clear

Long-term target behavior:

```text
"You're losing two tenths in Turn 3 from early braking, but don't chase it now — rear tyres are overheating. Focus on clean exits."
```

---

# 20. Strategy / Race Engineering Expansion — P1

Preserve and improve current strengths while coaching work progresses.

- [x] Better undercut / overcut estimation — measured-only conditional gates use pit-cycle evidence, gap, tyre degradation and opponent tyre-age evidence; unavailable inputs stay unavailable
- [x] Pit-loss estimation per circuit — observed pit-affected lap loss is persisted per track and reused only for the same circuit
- [x] Safety-car pit opportunity model — neutralisation + deterministic pit-service trigger exposed
- [x] VSC pit opportunity model — VSC-specific deterministic opportunity exposed
- [x] Tyre degradation projection — robust same-set completed-lap median trend plus next-five-lap loss projection
- [x] Fuel target projection — fuel-to-finish margin is converted to deterministic save/on-target/surplus target state
- [x] ERS target projection — current store plus observed harvest/deployment balance produces an end-of-race projection and target state
- [x] Damage-vs-pace-loss estimation — repeated clean-vs-damaged lap evidence is learned and persisted per circuit when comparable evidence exists
- [x] Wing-damage pit threshold based on measured pace loss — pit consideration requires both measured pace loss and material wing damage; otherwise result remains unavailable
- [x] Wet-weather tyre transition model — dry↔wet forecast transition plus rain percentage produces deterministic tyre-transition trigger state
- [x] Weather forecast confidence handling — EA forecast accuracy is propagated with transition assessment
- [x] Opponent strategy inference where telemetry allows — ahead-car tyre age/compound evidence is used when available and returns unavailable otherwise
- [x] Better mandatory-compound / race-rule checks — observed dry compounds, wet exemption context, serviceable penalties and session rule-set context are retained without inventing unavailable regulations

---

# 21. Speech / Radio Quality — P1

- [x] Message deduplication audit — replaceable live/coaching families including PRE/LAP/POS
- [x] Context-sensitive wording — runtime control replies now explain master/child gating and current mode/state
- [x] More natural short engineer calls — response-layer concise wording with minimal/normal/detailed profiles
- [x] Interruptibility rules
- [x] Critical-message interruption
- [x] Resume / discard interrupted low-priority calls — stale/superseded low-priority lines are discarded
- [x] Per-category cooldown tuning — local cooldown profile is integrated into the runtime engineer emit path; explicit safety/event overrides remain authoritative
- [x] Spoken number formatting — TTS-wide unit, symbol, acronym and decimal normalization applied before synthesis
- [x] Track/corner pronunciation dictionary — local pronunciation dictionary now applied at TTS output
- [x] Driver-name pronunciation dictionary — same local dictionary supports driver names
- [x] Voice speed profiles — slow/normal/fast radio-selectable profiles with persistent local settings
- [x] Optional alternate engineer voices — installed Piper voices can be selected/cycled by radio and persist locally
- [x] Spoken coaching verbosity levels — minimal/normal/detailed are persistent and radio-selectable

---

# 22. Product / Installation Experience — P1 before public release

Goal: make the application usable by someone who did not build it.

- [x] One-click Windows installer — Inno Setup per-user installer definition + build pipeline; Windows compilation remains target-machine validation
- [x] Standalone EXE packaging — dedicated PyInstaller launcher/spec with external writable runtime data
- [x] First-run setup wizard — local graphical `/setup` wizard opens automatically on first packaged launch
- [x] Automatic F1 UDP setup instructions — guided setup text + saved UDP port wired to receiver
- [x] Controller / wheel detection wizard — HID gamepad + Receiver COM discovery and persisted binding
- [x] Audio output selector
- [x] Microphone selector
- [x] PTT binding UI — HID identity + logical button persisted; verified bit calibration remains runtime-safe
- [x] Overlay enable/disable UI
- [x] LAN dashboard QR code — generated offline by local server
- [x] Firewall guidance / automated rule option — localhost-only explicit action with UAC fallback
- [x] Settings persistence
- [x] Reset-to-default settings — Control/API store plus V1.0.1 CLI reset
- [x] Update checker — opt-in GitHub release check; never auto-downloads or installs
- [x] Crash logs — main/thread unhandled exceptions saved and included in diagnostics
- [x] Diagnostic bundle export
- [x] Built-in telemetry health check
- [x] Built-in latency health check

---

# 23. Replay / Analysis Workflow — P1

- [x] Telemetry recording — lossless ARERPL01 recording with explicit report/validation linkage for new sessions
- [x] Replay playback — deterministic ReplayController with seek/checkpoints/range/speed controls
- [x] Replay browser — `/sessions` now provides search/filter, metadata, lap selection, timeline and comparisons
- [x] Session library UI — local LAN `/sessions` analysis page
- [x] Session metadata cards — name/tags/favorite/session UID/laps/report/validation/sidecars
- [x] Rename / tag sessions — local metadata API
- [x] Favorite sessions — local metadata API
- [x] Delete/archive recordings safely — archive/restore; permanent delete only from archive
- [x] Automatically attach generated coach report — explicit recorder→report→validation→CORNER trace linkage for new recordings, UID discovery for legacy sessions
- [x] Jump directly to a selected corner in replay — timeline/reference geometry resolves the deterministic replay packet and drives `ReplayController.seek()`
- [x] Replay coaching events on timeline — PRE/POST/blocked/suppressed/zone/lap-summary events from the matching CORNER COACH validation trace
- [x] Compare two recorded sessions — same-track/formula validation plus interactive telemetry/delta comparison
- [x] Compare multiple laps from same session — measured 10 m distance alignment for speed/brake/throttle/gear/ERS/delta/racing-line traces

---

# 24. Data Quality / Validation — P0 ongoing

- [x] Strict stale-data handling for coaching — V1.0.1 packet-family freshness gates
- [x] Missing packet-family handling — V1.2.0.0 quality gate rejects explicit missing packet-family and large internal distance gaps
- [x] Outlier rejection — V1.2.0.0 rejects impossible speed samples and live same-lap distance discontinuities
- [x] Lap-boundary correctness — exact S/F finalization plus same-lap-number final-race wrap handling
- [x] Pause correctness — paused laps/live context are blocked from performance coaching
- [x] Replay seek correctness — recorded seek flags and impossible live/replay distance jumps compromise the lap instead of generating false coaching
- [x] Session restart correctness — restarted/partial sessions are excluded from compatible performance comparisons
- [x] Wet/dry condition separation — incompatible reference conditions are rejected
- [x] Invalid-lap exclusion
- [x] Pit-lap exclusion from performance reference — V1.0.1 latches pit-phase compromise
- [x] Traffic-compromised lap detection — V1.0.1 front/rear proximity latching
- [x] Yellow / SC / VSC compromised segment detection — V1.0.1 race-control compromise latching
- [x] Damage-compromised reference filtering — V1.0.1 significant-damage latching
- [x] Tyre-condition mismatch warnings — deterministic warning without inventing pace correction
- [x] Fuel-load mismatch handling — deterministic medium/large mismatch warnings
- [x] Machine-readable analysis validation artifact — V1.3.1.0 writes `*_validation.json` with rejection reasons, compatibility evidence, Potential Lap sources and reconciliation checks

---

# 25. Testing / Benchmarking — P0 ongoing

- [~] Unit tests for coaching metrics — V1.3.1.0 adds dedicated parallel-integration coverage; legacy/new coverage is broad but not literally every field
- [x] Synthetic telemetry tests — V1.3.1.0 covers advice outcomes, line phases, landmarks, history and validation
- [x] Recorded-lap regression fixtures — Melbourne Race/Qual, Austria TT and Shanghai replay are used for V1.2.0.0 internal acceptance
- [x] Known-corner expected-result fixtures — golden deterministic early-brake/late-throttle/deadband fixture added in finalization
- [x] Latency tests — deterministic latency-health boundary plus high-rate replay/decision cadence regressions
- [x] Message-priority tests — CORNER COACH PRE/POST deadline/pre-emption cases covered
- [x] No-spam tests — per-zone emission/suppression and stale/duplicate guards covered
- [~] Replay/live parity tests — game-time scheduling makes fast replay deterministic; final physical Windows audio/device parity remains environment-dependent
- [x] LAN/native state parity tests — shared coaching mode/verbosity/focus payload parity covered
- [x] Track-map regression tests — all supported physical circuits require a closed fallback map; learned-map tests remain alongside it
- [x] F1 game-version compatibility tests — format-2026 traffic accepts Season Pack game-year 25/26 and rejects unsupported years
- [ ] Performance benchmark on target PC
- [~] Memory usage benchmark — container fast-replay peak RSS recorded for the V1.2.0.0 acceptance set; target Windows PC benchmark remains later
- [x] Long-session stability test — Austria/Melbourne fixtures plus supplied 210,860-packet ~19.9-minute Melbourne race validated in bounded deep-session chunks; physical Windows endurance remains a separate target-PC item

---

# 26. Multi-Sim Expansion — P3

Do only after the F1 coaching system is mature.

- [ ] Abstract simulator telemetry interface — deferred/out of current F1-only scope
- [ ] Separate game-specific adapters — deferred/out of current F1-only scope
- [ ] F1 remains reference implementation — deferred/out of current F1-only scope
- [ ] ACC adapter evaluation — deferred/out of current F1-only scope
- [ ] iRacing adapter evaluation — deferred/out of current F1-only scope
- [ ] LMU adapter evaluation — deferred/out of current F1-only scope
- [ ] AMS2 adapter evaluation — deferred/out of current F1-only scope
- [ ] Preserve deterministic coaching model across sims — deferred/out of current F1-only scope

---

# 27. Community / Cloud Features — P3

Optional future expansion; core app should remain usable locally.

- [x] Local F1 driver profiles — live-only multi-driver Performance Hub profiles/history; broader account/cloud profiles are out of current scope
- [ ] Cloud session backup — intentionally deferred/out of current local-only scope
- [ ] Shared reference laps — intentionally deferred/out of current local-only scope
- [ ] Community leaderboards — intentionally deferred/out of current local-only scope
- [ ] Shared track landmark packs — intentionally deferred/out of current local-only scope
- [ ] Shared coaching profiles — intentionally deferred/out of current local-only scope
- [ ] Shared setups — intentionally deferred/out of current local-only scope
- [ ] Team telemetry sharing — intentionally deferred/out of current local-only scope
- [ ] Coach/student session sharing — intentionally deferred/out of current local-only scope

---

# 28. Release Milestones

## V1.3.1.0 — Parallel Coaching Intelligence Integration — COMPLETE

- [x] Advice outcome memory + solved-issue retirement
- [x] Persistent current coaching focus
- [x] Technique consistency + chronological observed trends
- [x] Track-specific Driver History summaries
- [x] Signed/phase-aware racing-line comparison
- [x] Manual verified braking-board/kerb landmark metadata
- [x] Post-session advice outcomes
- [x] Machine-readable `*_validation.json`
- [x] Interactive radio uses advice memory for improvement/focus queries
- [x] Full regression clean: 710 tests + 383 subtests

## V1.3.2.0 — Driver Progress + Cross-Session Comparison — COMPLETE

- [x] Cross-session per-corner technique trend aggregation
- [x] Cross-session consistency trend aggregation
- [x] Recurring weakness resolution across dates/sessions
- [x] Track-specific history LAN page/data
- [x] Deterministic session-vs-session comparison model

## V1.3.3.0 — Racing-Line Geometry Intelligence — COMPLETE

- [x] Stronger world-position/outlier validation
- [x] Path-curvature apex extraction
- [x] Early/late apex classification from geometry
- [x] Pinched-exit detection
- [x] Path-aware steering-correction classification
- [x] Visual driver/reference racing-line overlay in report/LAN UI

## V1.3.4.0 — Track Learning + Visual Landmarks — COMPLETE FOR LOCAL/VERIFIED METADATA

- [x] 150/100/50 board mapping when explicit metadata provides those real landmarks
- [x] Pit-entry / pit-exit landmarks
- [x] Start/finish landmark exposure
- [x] Per-track/per-corner PRE call-distance overrides
- [x] Human-editable local landmark LAN/API workflow
- [x] Import/export verified landmark packs locally

## V1.3.5.0 — Coaching Analysis UI / Parallel Plan Completion — COMPLETE

- [x] Dedicated coaching summary LAN page (`/coach`)
- [x] Current-focus/advice-outcome card
- [x] Corner table and deterministic session trend/history data
- [x] Racing-line visualization
- [x] Driver-history/session-comparison data/pages
- [x] Landmark editor/API
- [x] Validation/rejection reason summaries
- [x] Full regression clean: 718 tests + 383 subtests

## V1.3.6.0 — Race/Strategy Expansion

Pending:
- [x] Strategy estimation improvements from Section 20 — completed; finalization adds clean-stint tyre-projection evidence gates and opening-lap protection
- [x] Unified race-context/performance-coach arbitration refinements — completed in V1.3.8+ and preserved through finalization
- [x] Wet/dry, tyre, fuel and damage-aware coaching adaptation hardening — completed; finalization adds fuel semantics and real-race pit/damage validation guards

## V1.4.0.0 — Productization

Pending:
- [ ] Standalone EXE / installer
- [x] First-run setup wizard — local graphical `/setup` wizard opens automatically on first packaged launch
- [x] Update/diagnostics polish — diagnostic export now snapshots the WAL-backed live Performance Hub database through SQLite backup
- [ ] Long-session Windows target-PC validation

---

# 29. Core Product Principles

These rules should stay true as features are added:

1. **Telemetry first, language second.** Measurements and decisions must come from deterministic data wherever possible.
2. **Never invent unavailable telemetry.** Unknown stays unknown.
3. **One useful correction is better than five observations.**
4. **Race-critical information always outranks coaching.**
5. **Low latency matters.** A correct message delivered too late is not useful.
6. **Do not spam the driver.** Silence is part of good race engineering.
7. **Every score and recommendation should be explainable.**
8. **Reference comparisons must be distance-aligned and track/session compatible.**
9. **The application should remain useful offline.** Cloud/LLM features are optional enhancements.
10. **Native overlay baseline remains frozen unless deliberately reopened.** New coaching UI work should initially target LAN/post-session interfaces unless a native change is explicitly approved.

---

# 30. Immediate Next Task

The agreed parallel A–E development plan is complete in **V1.3.5.0**.

Next product-development phase: **V1.3.6.0 — Race/Strategy Expansion**. This is intentionally separate from the completed coaching/analytics parallel plan because it touches higher-risk live race decision arbitration.

Keep frozen unless a failing regression proves a dependency:
- live map/player pointer
- rival reference compiler
- UDP decoder core
- CORNER COACH PRE/POST ownership/timing

Remaining later-scope items such as community/cloud sharing, multi-sim adapters and Windows installer/productization remain on the roadmap; they were not part of the A–E parallel completion plan.

---

# V0.9.20.0 Implementation Status — Coaching Data Foundation

Implemented:

- [x] New authoritative `src/coaching_analysis.py` module.
- [x] `CornerAnalysis` dataclass with current/reference measurements and deltas.
- [x] Brake onset, release and duration measurements.
- [x] Sustained steering-based turn-in detection.
- [x] Minimum-speed apex proxy with explicit `apex_method`.
- [x] Throttle pickup and pickup-to-full-throttle measurements.
- [x] Per-corner trail-brake and coasting distances.
- [x] Entry/apex/exit gear, shift-count, peak steering and steering-reversal capture.
- [x] Entry/mid/exit and whole-corner measured time-loss attribution.
- [x] Current/reference/match quality plus deterministic confidence score.
- [x] Rich `corner_analyses` added to live completed-lap comparison and JSON session analysis.
- [x] Old `section_comparisons` and analysis JSON version retained for backwards compatibility.
- [x] Native overlay and LAN dashboard source remain frozen.
- [x] Full regression: 512 tests + 383 subtests passed.

Not yet implemented in V0.9.20.0:

- Corner diagnosis labels (early brake, low minimum speed, late throttle, etc.).
- Repeat-pattern/session coaching memory.
- Coaching priority/actionability scoring.
- Safe speech-window scheduler/post-corner calls — implemented in V0.9.20.3.
- Lap-end coaching summary/potential lap.
- World-position racing-line analysis.

# V0.9.20 Capability Audit Status

Initial source-code audit completed against baseline **V0.9.19.8.6.24**.

Detailed audit: `V0.9.20_TELEMETRY_COACHING_CAPABILITY_AUDIT.md`

Key result: the core P0 coaching telemetry is already available. V0.9.20 should focus on structured corner derivations, confidence, multi-lap pattern memory, priority/speech timing, lap summaries, and potential-lap logic rather than rewriting telemetry acquisition.

V0.9.20.0 coaching data foundation and V0.9.20.1 Corner Intelligence are implemented. **V0.9.20.1.1 Diagnosis Loss-Guard Hotfix** adds whole-corner and per-phase measured-loss guards plus supporting-only min-speed-proxy apex evidence. **V0.9.20.1.2 Coaching Deadband Hotfix** adds a 20 ms minimum whole-corner loss threshold before corrective coaching. **V0.9.20.2 Coaching Priority + Multi-Lap Pattern Memory** adds deterministic per-lap issue ranking, recurrence/persistence statistics, trend detection, and session focus. **V0.9.20.3 Immediate Post-Corner Coaching + Safe Speech Timing** adds live loss-guarded corner corrections, low-workload straight detection, next-braking-zone safety gating, stale/unsafe drop rules, per-lap call limits and repeated-advice cooldown. Next milestone: **V0.9.20.4 — Lap-End Coaching Summary + next-focus handoff**.


## V1.5.0.0 — Pre-Release Hardening — COMPLETE

- [x] Formal validation / benchmark instrumentation (latency, CPU/RAM, packet continuity, replay/live signature helper)
- [x] Automatic per-session and weekend validation bundles; raw `.areplay` recordings are hashed/referenced, never embedded
- [x] Persistent strategy, pit, reference, warning/error and performance evidence
- [x] CORNER PRE timing/blocker diagnostics, pit/out-lap gate, first-flying-lap re-arm, long-session wording memory
- [x] Separate measured normal/SC/VSC pit-cycle evidence
- [x] Observed opponent pit/compound events and measured matched-stop gap effect
- [x] EA pit-window status and mandatory-compound urgency exposed in advanced strategy
- [x] Consolidated `/settings` page with device/readiness status, reference inventory, transcript viewer, validation bundles, diagnostics, config export/import and resets
- [x] Per-session benchmark reset across Practice -> Qualifying -> Race
- [x] Four supplied replay indexes + five Austria validation traces checked by the formal validator

Still requiring live evidence rather than synthetic claims: exact 500+ MB Austria long-race packet parity, a real wet/dry transition, and a real SC/VSC stop cycle. V1.5.0.0 automatically captures the evidence needed when those occur.

## V1.7.0.0 — SPEED COACH / Straight Line Coach Integration

- [x] Rename the combined live coaching surface to **SPEED COACH**.
- [x] Independent **CORNER COACH** and **STRAIGHT LINE COACH** child enables under the Speed Coach master.
- [x] Reuse authoritative full-track turn/straight segmentation and compiled reference model; no parallel geometry system.
- [x] Deterministic completed-straight diagnosis from measured local time change, speed and trusted throttle/S-Mode/ERS evidence.
- [x] PRE-safe single-radio scheduling: straight feedback waits for low workload and cannot occupy reserved upcoming corner PRE airtime.
- [x] Long-session straight repetition memory and no stale back-fill after enabling a child/voice mid-lap.
- [x] Unified Speed Coach transcript with source identity (`corner_coach` / `straight_line_coach`) plus legacy corner-only transcript compatibility.
- [x] Unified overlay controls and straight live metrics/map highlighting.
- [x] Radio controls for Speed Coach, Corner Coach, Straight Line Coach and Straight Voice.
- [x] Existing Corner Coach PRE/POST, damage override, gain/loss and reference behavior preserved.



## V1.8.0.0 — Driving Performance Engine Completion — COMPLETE

- [x] Full physical-corner segmentation coverage for every F1 track/reference with published turn-count authority.
- [x] Geometry-first corner start/apex/end with measured brake onset, turn-in and exit/recovery action boundaries.
- [x] Path/curvature apex authority with sustained-curvature plateau centering and explicit legacy fallback only when path data is unavailable.
- [x] True apex-speed comparison separate from minimum-speed measurement.
- [x] Time-domain coasting comparison.
- [x] Time-domain throttle-pickup-after-apex comparison.
- [x] Steering rate, correction count, smoothness, unwind time/distance and unwind monotonicity.
- [x] Stronger per-corner confidence/data-quality scoring including sample density, distance gaps, speed/path coverage and time continuity.
- [x] Additional isolated-value and short stale-path burst rejection without bridging missing circuit sections.
- [x] Reference-relative minimum-speed, throttle-pickup and exit-speed efficiency metrics.
- [x] Same metrics integrated into offline reports and live CORNER COACH POST diagnosis.
- [x] Real-recording geometry validation: Melbourne 14/14, Austria 10/10, Shanghai 16/16 with curvature-apex/time-domain/steering coverage.


## V1.9.0.0 — Local Driver Performance Hub

- [x] Persistent LIVE-only local SQLite driver performance database (`analysis/performance_history_live.sqlite3`)
- [x] Driver profile created from F1 ParticipantData/session identity (name, race number, team, driver/team/nationality/platform IDs, game metadata)
- [x] Automatic completed-session persistence outside the live telemetry hot path
- [x] Hard authority gate: replay sessions never update driver profile/history/best laps/trends
- [x] Track-by-track browser performance overview at `/performance`
- [x] Track trend history for best lap, potential lap and reference gap
- [x] Full per-session summaries with results, laps, warnings, penalties, tyre state and coaching metrics
- [x] Latest measured corner opportunities and strengths by track
- [x] Multiple local F1 driver profiles selectable in the browser
- [x] Browser Performance Hub retained at `/performance`
- [x] Control Center converted from overlay to normal desktop application window
- [x] Native PERFORMANCE HUB tab added inside Control Center
- [x] Legacy/mixed V1.9 database left untouched; new live-only database starts clean
- [x] Local-only storage; no cloud account or external database required
- [x] Regression coverage for profile extraction, persistence, migration and browser APIs
- [ ] Long-term UI polish based on real multi-track driver history (future validation)


## V1.9.1.0 — Live History Authority + Control Center Application — COMPLETE

- [x] Persistent performance history accepts LIVE F1 telemetry only.
- [x] Replay reports remain available for validation but never change driver profile, best laps, track totals or trends.
- [x] New authoritative database: `analysis/performance_history_live.sqlite3`.
- [x] Old V1.9 mixed-source database is ignored by the new hub.
- [x] Control Center is a normal native application window with OS title bar/minimize/maximize/close.
- [x] CONTROL and PERFORMANCE HUB tabs in the same window.
- [x] Performance tab shows driver/team, totals, track table and session history.
- [x] Browser `/performance` page remains available as an optional full-page view.
- [x] Click-through/topmost behavior remains limited to racing overlays; Control Center stays interactive.

---

# V1.9.2.0 — Final Source Hardening

- [x] Full local/F1 source and roadmap audit
- [x] Opening-lap false pit projection protection with clean-stint evidence
- [x] Real-race damage / Safety Car / pit / restart validation
- [x] Semantic pit-call repeat suppression
- [x] Tyre-temperature and pass-event radio spam hardening
- [x] Fuel margin semantics correction
- [x] Social STT filler suppression
- [x] Long-replay high-rate telemetry decision decoupling
- [x] Runtime category cooldown integration
- [x] Control Center coaching mode / radio detail selectors
- [x] LAN/native coaching state parity regression
- [x] Golden known-corner expected-result fixture
- [x] F1 game-year compatibility regression
- [x] Supported-track map regression coverage
- [x] SQLite-safe Performance Hub diagnostic backup
- [x] Supplied 210,860-packet real-race recording validation
- [x] Complete source regression suite
- [ ] Windows EXE / installer finalization — intentionally excluded from this source-only pass
- [ ] Physical Windows target-PC endurance benchmark — requires user target machine


---

## Archived source: `DRIVER_PROFILE_MULTI_GAME_PLATFORM_ROADMAP.md`

# Race Engineer — Driver Profile & Multi-Game Platform Roadmap

## Target Architecture

```text
DRIVER PROFILE
│
├── Personal Identity
│   ├── Name
│   ├── Avatar
│   ├── Country / Region
│   ├── Preferred Units
│   └── Profile Created / Last Active
│
├── Career Summary
│   ├── Total Driving Hours
│   ├── Total Sessions
│   ├── Total Laps / Distance
│   └── Active Game
│
├── F1 26 PROFILE
│   ├── Formula Skill Score
│   ├── Skill Breakdown
│   ├── Skill Trends
│   ├── Track Performance
│   ├── Session History
│   ├── Driving Hours
│   └── Existing Performance Hub data
│
├── ACC PROFILE
│   ├── GT Skill Score
│   ├── Skill Breakdown
│   ├── Skill Trends
│   ├── GT3 / GT4 / Cup / Super Trofeo
│   ├── Car Performance
│   ├── Track Performance
│   └── Sprint / Endurance / Wet / Race history
│
└── DIRT RALLY 2.0 PROFILE
    ├── Rally Skill Score
    ├── Skill Breakdown
    ├── Skill Trends
    ├── Surface Performance
    ├── Car/Class Performance
    ├── Stage Performance
    └── Rally History
```

---

## Phase 1 — Driver Profile Foundation

### Goal
Introduce a proper persistent person-level profile independent of any game.

### Build

| Feature | Requirement |
|---|---|
| Driver ID | Unique internal ID; never tied to driver name |
| Display name | Editable |
| Avatar | Optional profile image |
| Country/region | Optional |
| Units | Metric / Imperial |
| Created date | Automatically stored |
| Last active | Automatically stored |
| Active game | F1 / ACC / Dirt |
| Total driving hours | Sum of supported game profiles |
| Profile storage | Local/server-ready |
| Multiple drivers | Supported from architecture start |

### Data structure

```text
user_data/
  drivers/
    DRIVER_ID/
      profile.json
      career/
      games/
```

### Acceptance
- More than one driver can exist on the same Race Engineer installation.
- Driver histories never overwrite each other.
- Changing display name does not create a new driver.
- Existing telemetry logic remains untouched.

---

## Phase 2 — First-Run Profile Setup

This should appear only when there is no existing driver.

### Startup flow

```text
WELCOME TO RACE ENGINEER
        ↓
CREATE DRIVER PROFILE
        ↓
Name
Avatar
Country
Units
        ↓
SELECT GAME
        ↓
F1 26
ACC
Dirt Rally 2.0
        ↓
CREATE GAME PROFILE
        ↓
CONTROL CENTER
```

Initially:
- F1 26 — Available
- ACC — Future support
- Dirt Rally 2.0 — Future support

The future game-profile containers can still exist before telemetry adapters are implemented.

### Normal startup afterward

```text
Launch
 ↓
Load last driver
 ↓
Load last active game
 ↓
Control Center
```

No repeated setup screen.

---

## Phase 3 — Permanent Driver Profile Control

Add a compact profile control in the top-right corner of the Control Center.

Example:

```text
┌─────────────────────────────┐
│ AH  ABHILASH                │
│ F1 26 • Skill 78.4  ↑0.3    │
└─────────────────────────────┘
```

Clicking it opens:

```text
DRIVER PROFILE

OVERVIEW | SKILLS | TRENDS | HISTORY | GAME PROFILES
```

The profile control remains visible regardless of the active Control Center section.

---

## Phase 4 — Game Profile Architecture

A Driver represents the person.

A Game Profile represents performance within a motorsport discipline/game.

| Game | Discipline | Internal type |
|---|---|---|
| F1 26 | Formula | `formula` |
| ACC | GT | `gt` |
| Dirt Rally 2.0 | Rally | `rally` |

Example:

```json
{
  "game_id": "f1_26",
  "discipline": "formula",
  "driver_id": "...",
  "created_at": "...",
  "driving_seconds": 0,
  "sessions": 0
}
```

This prevents the profile database from being designed around F1-only assumptions.

---

## Phase 5 — Existing F1 Data Migration

Existing Performance Hub data must be attached to the new F1 Game Profile.

Existing data to preserve:

```text
Sessions
Laps
Tracks
Telemetry
References
Corner performance
Performance analysis
Assists
Driver/game information
Recorded history
```

Migration should be non-destructive.

Old data:

```text
user_data/performance/...
```

becomes logically associated with:

```text
drivers/<driver>/games/f1_26/
```

Physical migration can be deferred if compatibility is safer initially.

---

## Phase 6 — Accurate Driving-Hours Tracking

Do not count application-open time.

Track actual telemetry-active driving.

For F1:

```text
TOTAL F1 DRIVING
├── Practice
├── Time Trial
├── Qualifying
├── Sprint
└── Race
```

Example:

```text
F1 Driving Time       84 h 26 min
Race                  31 h 17 min
Qualifying            12 h 05 min
Time Trial            28 h 44 min
Practice              12 h 20 min
```

Pause/menu/inactive telemetry should not artificially inflate hours.

---

## Phase 7 — Skill Evidence Engine

Do not directly convert one lap into a career skill rating.

Use:

```text
LIVE TELEMETRY
      ↓
Measured driving events
      ↓
Session-level evidence
      ↓
Validated skill evidence
      ↓
Career skill history
      ↓
Current Skill Score
```

Every stored skill measurement should include:

```text
skill
value
confidence
sample_count
track
conditions
session_type
timestamp
reference_quality
```

---

## Phase 8 — F1 Skill Model

F1 gets implemented first.

### Formula Driver Skills

| Skill | Description |
|---|---|
| Pace | Absolute measured performance against valid reference |
| Consistency | Lap and corner repeatability |
| Braking | Brake point/application/release |
| Corner Entry | Entry execution and turn-in |
| Apex / Minimum Speed | Mid-corner efficiency |
| Traction / Exit | Throttle application and exit speed |
| Car Control | Slip, lockups, instability and corrections |
| Racecraft | Attacking, defending and traffic |
| Tyre Management | Performance versus tyre condition |
| Wet Driving | Wet-condition performance |

Example:

```text
F1 DRIVER SKILL
78.4 / 100

Pace                  82
Consistency           76
Braking               84
Corner Entry          74
Apex                   77
Traction              81
Car Control           79
Racecraft             72
Tyre Management       75
Wet Driving           N/A
```

### Critical rule
**N/A remains N/A.**

Never manufacture a rating when insufficient evidence exists.

---

## Phase 9 — Skill Confidence

Every skill should show how trustworthy it is.

Example:

```text
BRAKING
84

Confidence: HIGH
Measured corners: 1,428
Sessions: 37
Tracks: 9
```

Compared with:

```text
WET DRIVING
71

Confidence: LOW
Measured corners: 24
Sessions: 1
```

This prevents misleading scores.

---

## Phase 10 — Skill Trend System

Each skill gets historical snapshots.

Example:

```text
BRAKING
Current       84.2
10 sessions   +3.4
30 sessions   +7.1
Personal Best 86.0
```

### Trend graph filters

```text
SKILL TREND

Overall
Pace
Consistency
Braking
Cornering
Traction
Car Control
Racecraft
Tyre Management

[10 Sessions] [30 Sessions] [3 Months] [All Time]
```

Trend snapshots should primarily be stored at session completion, not every telemetry frame or every corner.

Also support:
- Career skill trend
- Per-game skill trend
- Per-track trend
- Per-car trend
- Wet/dry trend

---

## Phase 11 — Per-Track Skill

Example:

```text
F1 TRACK PERFORMANCE

Silverstone     84
Spa             81
Monza           79
Melbourne       76
Monaco          68
```

Clicking a circuit opens:

```text
MONACO

Overall             68
Braking             74
Corner Entry        62
Traction            69
Consistency         65

Trend               ↑ +4.8
Sessions            11
Best Performance    74
```

Reuse the existing Performance Hub track hierarchy where practical.

---

## Phase 12 — Driver Profile Overview

Example:

```text
ABHILASH

Formula Driver

F1 26 Skill        78.4 ↑0.3
Driving Time       84h 26m
Sessions           126
Tracks Driven      18

CURRENT STRENGTHS
Braking             84
Pace                82
Traction            81

DEVELOPMENT AREAS
Racecraft           72
Corner Entry        74
Tyre Management     75

RECENT TREND
       ╭─────╮
  ╭────╯     ╰───
──╯

Last 10 sessions: +2.1
```

---

## Phase 13 — Profile History

Add a career timeline.

Example:

```text
Sep 2026
Braking reached 80

Sep 2026
New Silverstone personal best

Aug 2026
50 F1 driving hours

Aug 2026
Consistency improved 70 → 75
```

These milestones should be derived from real measurements.

---

## Phase 14 — Multiple Game Profile UI

Example:

```text
GAME PROFILES

┌──────────────────┐
│ F1 26            │
│ FORMULA           │
│ Skill 78         │
│ 84h              │
│ ACTIVE           │
└──────────────────┘

┌──────────────────┐
│ ACC              │
│ GT               │
│ Not configured   │
└──────────────────┘

┌──────────────────┐
│ Dirt Rally 2.0   │
│ RALLY            │
│ Not configured   │
└──────────────────┘
```

Selecting a game changes the active Game Profile but not the person.

---

## Phase 15 — ACC / GT Architecture

ACC should be treated as the GT racing profile.

Within ACC:

```text
ACC
│
├── Overall GT Skill
│
├── GT3
├── GT4
├── Cup
└── Super Trofeo
```

These are class breakdowns, not separate driver profiles.

ACC should also understand:

```text
Practice
Hotlap
Hotstint
Qualifying
Sprint Race
Endurance Race
Multiplayer
Wet
```

Each session type contributes differently to skills.

---

## Phase 16 — ACC Skills

Suggested future GT skills:

```text
Pace
Consistency
Braking
Corner Entry
Mid-Corner Control
Traction / Exit
Car Control
Racecraft
Tyre Management
Stint Management
Traffic Management
Wet Driving
Endurance
Car Adaptability
```

Example:

```text
ACC DRIVER SKILL
76

GT3           79
GT4           73
Cup           N/A
Super Trofeo  68
```

ACC's native in-game ratings should remain separate from Race Engineer's own skill calculation.

---

## Phase 17 — Dirt Rally 2.0 / Rally Architecture

Rally uses a different skill model.

Suggested Rally skills:

```text
Stage Pace
Stage Consistency
Braking
Car Control
Weight Transfer
Throttle Control
Surface Adaptation
Recovery
High-Speed Confidence
Low-Speed Technical Driving
Wet Driving
Car/Class Adaptability
```

Breakdowns can include:

```text
Tarmac
Gravel
Snow
Wet
Dry

RWD
FWD
AWD

Car class
Location
Stage
```

---

## Phase 18 — Cross-Game Driver Overview

Once multiple supported games contain enough evidence:

```text
DRIVER

Total Driving       326h

FORMULA
F1 26               78

GT
ACC                 74

RALLY
Dirt Rally 2.0      69
```

Do not create one combined 0–100 Overall Driver Score initially.

Formula, GT and Rally should remain separate until a defensible normalization method exists.

---

## Phase 19 — Server Integration

Long-term architecture:

```text
GAMING PC
│
├── live telemetry processing
├── overlays
├── voice
└── current-session cache
        │
        ▼
SERVER LAPTOP
├── Driver Profiles
├── Game Profiles
├── Session History
├── Skill Evidence
├── Skill Trends
├── References
└── Performance History
```

The system must continue to work locally if the server is unavailable.

---

## Phase 20 — Profile Backup / Export

Add later:

```text
Export Driver Profile
Import Driver Profile
Backup
Restore
```

This becomes important once long-term performance history accumulates.

---

# Recommended Release Plan

| Release | Scope |
|---|---|
| **V2.1.0** | Driver Profile foundation + first-run setup |
| **V2.1.1** | Top-right profile control + profile Overview |
| **V2.1.2** | Game Profile architecture |
| **V2.1.3** | Existing F1 data migration |
| **V2.2.0** | Accurate driving-hours engine |
| **V2.3.0** | Skill evidence engine |
| **V2.4.0** | F1 Driver Skill V1 |
| **V2.4.1** | Confidence/sample system |
| **V2.5.0** | Skill Trends |
| **V2.5.1** | Per-track skill/trends |
| **V2.6.0** | Career history/milestones |
| **V2.7.0** | Multi-driver switching |
| **V2.8.0** | Server-backed profile/history support |
| **V3.x** | ACC telemetry + GT profile |
| **V4.x** | Dirt Rally telemetry + Rally profile |

---

# Recommended Immediate Starting Point

Start with **V2.1.0 — Driver Profile Foundation**.

That release should contain:

1. First-run setup
2. Persistent Driver ID
3. Basic personal information
4. Game-profile container
5. Multiple-driver-safe storage
6. Active-profile loading

Do **not** calculate the Driver Skill Score yet.

First establish the identity and storage model correctly. Then attach the existing F1 Performance Hub history. After that, build the skill evidence and trend engine on top of stable data.


---

## Archived source: `RACE_ENGINEER_UI_REFINEMENT_ROADMAP.md`

# Race Engineer — UI Refinement Roadmap

## Purpose
This roadmap is UI/UX-only. It must not change telemetry authority, coaching logic, scoring, reference logic, race-strategy decisions, persistence semantics, replay behavior, or performance-analysis math.

The goal is to modernize Race Engineer so its UI matches the depth of its underlying features: cleaner hierarchy, stronger visual consistency, better interaction, less clutter, more responsive layouts, and more capable overlays.

The screenshots supplied from AiMotor are treated as interaction/layout references only. Race Engineer should keep its own visual identity and data model.

---

## UI-R0 — Design System & Visual Foundation

### Goals
- Establish one shared visual language across Control Center, Performance Hub, browser views, native overlays, and F1 Dash.
- Remove the current mixture of legacy Qt controls, web cards, and inconsistent spacing/typography.

### Work
- Define shared tokens for:
  - background / surface / elevated surface
  - border and divider strength
  - primary accent
  - semantic green / amber / red / cyan / grey
  - heading / label / body / numeric typography
  - spacing scale
  - border radius
  - shadow / glow policy
  - disabled / hover / selected / active states
- Standardize button classes:
  - primary
  - secondary
  - destructive
  - icon-only
  - segmented control
  - toggle
- Standardize cards and sections.
- Create compact and comfortable density modes internally, even if only one is exposed initially.
- Unify scrollbars for Qt and web surfaces.
- Unify loading, waiting, empty, disconnected, N/A, warning and error states.

### Acceptance
- Same semantic colors mean the same thing everywhere.
- Headings, buttons, cards and scrollbars visually match across Control Center and Performance Hub.
- No UI logic changes.

---

## UI-R1 — Control Center Rebuild

### Goals
- Make Control Center look like a modern application shell instead of a long form.
- Group related controls and reduce vertical scrolling.

### Work
- Convert current Control Center into grouped cards:
  - Session / runtime
  - Race Engineer
  - Performance Coach
  - Reference
  - Hardware
  - Audio
  - Overlay manager
- Use compact two/three-column responsive layout on wide windows.
- Collapse low-frequency sections.
- Add status chips instead of raw text for Enabled / Disabled / Live / Off / Disconnected.
- Improve reference selector presentation.
- Rebuild overlay launcher as an Overlay Manager instead of a button matrix.

### Overlay Manager
Each overlay row/card should show:
- name
- on/off toggle
- live status
- lock state
- opacity
- open / focus control
- optional settings expansion

### Acceptance
- Common controls visible without excessive scrolling at 1080p.
- Small window remains usable with scrolling.
- No large unused blank regions.

---

## UI-R2 — Unified Overlay Framework

### Goals
Give every overlay the same interaction model.

### Standard overlay chrome
Every overlay should support:
- close
- minimize where appropriate
- lock / unlock position
- zoom in
- zoom out
- reset zoom
- opacity / transparency
- drag only while unlocked
- optional compact mode
- saved geometry / scale / opacity per overlay

### Interaction rules
- Locked overlay: no accidental drag or resize.
- Click-through remains compatible with lock state.
- Hover chrome can auto-hide after a short delay.
- Overlay settings persist locally.

### Acceptance
- Same controls and keyboard/mouse behavior on all overlays.
- No overlay-specific ad-hoc window controls.

---

## UI-R3 — Progressive Pre-Corner Overlay

### Goals
Replace the current static pre-corner presentation with a progressive, glanceable approach overlay.

### Layout
Compact card containing:
- Corner label: T1 / T2 etc.
- approach progress bar
- phase state: APPROACHING / BRAKING / TURN-IN / APEX / EXIT
- primary action
- optional secondary action
- reference delta / confidence when trusted

### Progressive behavior
As car approaches the corner:
1. Far approach — corner ID and distance-to-zone only.
2. Coaching range — primary instruction appears.
3. Final approach — progress bar becomes more prominent.
4. At braking/turn-in — instruction locks to avoid flicker.
5. After corner entry — fade or hand off to POST feedback.

### Voice alignment
- Overlay and PRE voice must use the same authoritative diagnosis/action.
- Visual progress must not change coaching timing logic.

### Acceptance
- Readable in <1 second at speed.
- No dense telemetry during approach.
- Smooth progression with no flashing/reflow.

---

## UI-R4 — Live Corner Feedback / Accuracy UI

### Goals
Make post-corner feedback more visual and less text-heavy.

### Work
- Replace large text blocks with 2–4 compact metric rings/bars depending on selected mode.
- Examples:
  - brake accuracy
  - apex/min-speed accuracy
  - throttle pickup accuracy
  - gear/reference accuracy
- Grade and measured time cost remain prominent.
- Keep one actionable recommendation.
- Add expandable details for advanced metrics.

### Acceptance
- Main feedback understandable without reading paragraphs.
- Detailed evidence still accessible on demand.

---

## UI-R5 — Performance Hub Information Architecture

### Goals
Make Performance Hub feel like a professional telemetry workstation rather than one long web page.

### Structure
Top-level workspace:
- Track overview
- Session review
- Lap review
- Corner review
- Telemetry

### Work
- Sticky session header with:
  - track
  - session type
  - driver
  - selected lap
  - selected reference
  - lap time
  - gap
- Convert large page sections into panels/tabs/drawers.
- Keep key context visible while scrolling.
- Use side panel or split view for selected corner details.
- Use consistent card density and spacing.
- Reduce duplicated labels and repeated explanatory text.

### Acceptance
- User always knows current track/session/lap/reference.
- Switching between overview/telemetry/corners does not feel like navigating unrelated pages.

---

## UI-R6 — Telemetry Workstation Redesign

### Goals
Bring graph interaction closer to a modern analysis tool while preserving Race Engineer's richer data.

### Core channels
Always available when data exists:
- Speed
- Brake
- Throttle
- Steering
- Gear
- ERS
- Delta

### Expandable advanced channels
- RPM
- lateral acceleration
- longitudinal acceleration
- tyre temperatures
- tyre pressures
- brake temperatures
- other trusted recorded channels

### Graph behavior
- aligned shared distance axis
- shared hover cursor across all visible charts
- corner boundaries and corner labels
- driver/reference overlays
- click corner to zoom all charts
- drag to select distance range
- reset whole lap
- optional graph reorder
- compact / expanded graph height
- clearer reference legend

### Acceptance
- One interaction affects every linked graph consistently.
- No need to scroll between unrelated charts to identify the same corner.

---

## UI-R7 — Every-Corner Review Refinement

### Goals
Turn the current corner table + detail page into a dense but readable engineering review.

### Work
- Sticky corner table header.
- Reliable horizontal scrolling on narrow windows.
- Column chooser for low-priority metrics.
- Sort by:
  - corner number
  - score
  - time loss
  - speed deficit
  - braking delta
  - throttle delta
- Heat tint only on data cells, not whole rows.
- Selected corner receives one clear highlight.
- Corner detail becomes split panel on wide displays and stacked view on narrow displays.
- Selected Analysis Reference metrics remain in their own visual group.

### Acceptance
- Full table usable at narrow width.
- Wide screen makes full use of available space.
- User can identify worst corners immediately.

---

## UI-R8 — Race / Strategy Overlay Visual Refresh

### Goals
Modernize race-context overlays without changing their logic.

### Target overlays
- weather / forecast
- fuel
- standings / relatives
- penalties
- tyre / brake status
- ERS
- delta
- session summary
- radio transcript

### Work
- concise header
- icon + status color
- most important value large
- supporting values grouped below
- consistent footer/status strip
- no unnecessary borders or nested boxes
- expand-on-demand for secondary data

### Acceptance
- Critical information readable at a glance.
- Common window controls identical to UI-R2.

---

## UI-R9 — F1 Dash & Secondary Display Polish

### Goals
Preserve existing functional F1 Dash while modernizing visual hierarchy.

### Work
- normalize typography and spacing
- consistent tab/header treatment
- subtle surface separation instead of heavy borders
- improve waiting/disconnected states
- consistent back/navigation affordance
- responsive scaling on browser/LAN and native views
- preserve 800×480 reference layout behavior

### Acceptance
- Native and LAN views remain visually aligned.
- No regression to telemetry refresh rate or map smoothness.

---

## UI-R10 — Animation, Feedback & Micro-interactions

### Goals
Make state changes feel intentional without distracting the driver.

### Work
- 120–200 ms hover/selection transitions
- smooth progress-bar movement
- subtle card selection animation
- fade-in/out for temporary overlays
- no large motion during active driving
- loading skeletons for review pages
- toast-style success/error messages instead of blocking alerts where safe

### Acceptance
- UI feels responsive, never sluggish.
- Animation cannot block telemetry processing or driver interaction.

---

## UI-R11 — Responsive Layout Matrix

### Required validation widths
- ~800 px narrow Control Center
- ~1024 px
- ~1280 px
- 1920×1080 full screen
- secondary browser/tablet widths
- 800×480 F1 Dash

### Rules
- Wide: use columns and split views.
- Medium: reduce columns before reducing font size.
- Narrow: stack panels and preserve horizontal scrolling where tables require it.
- Never shrink telemetry text below readable minimum.
- Never hide critical state merely to make a layout fit.

---

## UI-R12 — Accessibility & Input Consistency

### Work
- keyboard focus styles
- tab navigation for major controls
- tooltips for icon-only buttons
- larger click targets for overlay controls
- color + text/icon status, never color alone
- contrast audit
- consistent mouse-wheel behavior
- support high-DPI Windows scaling

---

## UI-R13 — Performance & Rendering Guardrails

UI refinement must not reintroduce earlier latency issues.

### Rules
- no high-rate DOM rebuilds for static structures
- update only changed telemetry values
- requestAnimationFrame for web visual updates
- bounded chart point counts / decimation
- no blocking database work on render path
- overlay animation disabled or reduced under load
- preserve high-rate telemetry / low-rate decision separation

### Validation
- live telemetry smoothness
- long replay stability
- Control Center resize stress
- repeated overlay open/close
- full Performance Hub review
- LAN dashboard parity

---

# Recommended Implementation Sequence

## UI Phase 1 — Foundation
**UI-R0 + UI-R2**

Design system and unified overlay chrome first, because every later UI change depends on them.

## UI Phase 2 — Driver-Facing Live UI
**UI-R3 + UI-R4 + UI-R8**

Progressive pre-corner overlay, post-corner accuracy view, and race overlays.

## UI Phase 3 — Control Center
**UI-R1**

Modern control/settings experience and full overlay manager.

## UI Phase 4 — Performance Workspace
**UI-R5 + UI-R7**

Reorganize Performance Hub and finish the corner workflow.

## UI Phase 5 — Telemetry Workstation
**UI-R6**

Linked multi-channel telemetry graphs and advanced analysis interactions.

## UI Phase 6 — Dash / Responsive Polish
**UI-R9 + UI-R10 + UI-R11 + UI-R12**

Final consistency, responsiveness, interaction, accessibility and DPI work.

## UI Phase 7 — Performance / Regression Freeze
**UI-R13**

Full validation before calling the UI redesign complete.

---

# Suggested Version Track

Keep this UI work separate from the functional V2 roadmap so feature development remains easy to audit.

Suggested branch/version naming:

- UI 1.0 — Design System + Overlay Framework
- UI 1.1 — Progressive Pre-Corner + Live Feedback
- UI 1.2 — Control Center / Overlay Manager
- UI 1.3 — Performance Hub Workspace
- UI 1.4 — Telemetry Workstation
- UI 1.5 — Race Overlay Refresh
- UI 1.6 — F1 Dash / Responsive / Accessibility
- UI 1.7 — Final UI Validation Freeze

When integrated into Race Engineer builds, keep the normal application version and record the UI milestone in the checkpoint, for example:

`V2.0.5.x + UI 1.0`

This avoids confusing UI-only work with deterministic engine changes.

---

# Non-Negotiable Preservation Rules

1. Do not change deterministic measurement or coaching logic as part of UI work.
2. Do not let visual scores become coaching authority.
3. Do not invent missing telemetry to make charts look complete.
4. N/A remains N/A.
5. Replay remains read-only for persistent live history.
6. UI rendering must never block telemetry ingestion.
7. Existing user data remains compatible.
8. Native / LAN / browser views should share components and styling wherever practical.
9. Overlay settings remain local and persistent.
10. The redesign should use AiMotor only as a usability reference, not as a visual clone.


---

## Archived source: `assets/brand/BRAND.md`

# Race Engineer Stable V2 — Brand

- Product name: **Race Engineer**
- Release family: **Stable V2**
- Tagline: **Telemetry • Strategy • Coaching**
- Primary background: `#080D12`
- Surface: `#101820`
- Text: `#EEF6FB`
- Accent cyan: `#4DD9FF`
- Go / positive green: `#2ED486`
- Muted text: `#8395A8`
- Border: `#273746`

The icon combines an RE monogram, a telemetry/speed arc, a green apex target, and a small data trace. Use the square icon for executables/shortcuts/windows and the horizontal wordmark for app/about/installer surfaces.


---

## Archived source: `server_deploy/README_S14.txt`

Race Engineer Server Consolidated Deployment (S8-S14)

Copy this server_deploy folder to race-server, then run:
  cd <copied-folder>
  bash install_s14.sh

The script upgrades the existing S4 API in place and preserves /srv/race-engineer/database.
After deployment the gaming PC publishes the local LIVE Performance History SQLite via HTTP.
The active gaming-PC SQLite database is never used directly from Samba.

Endpoints:
  /api/health
  /api/snapshots
  /api/drivers
  /api/sessions
  /performance-hub


---

## Archived source: `CHECKPOINT_FINALIZATION_A.md`

# FINALIZATION CHECKPOINT A — Full Audit + Real Race Evidence

Base: V1.9.1.5 Weekend Replay Transition Hotfix.
Windows EXE/installer work is explicitly excluded.

## Baseline
- Full pytest: 827 passed + 383 subtests.
- Real validation corpus includes telemetry-20260926T175930Z-429413eb.areplay (211,173,492 bytes) plus race/weekend transcripts.
- Full fast replay of this 211 MB file exceeded the 120 s execution window, which itself is retained as performance evidence and will be addressed/tested with focused replay/unit benchmarks.

## Confirmed defects from real race transcript
1. False opening-stint tyre-life pit call: ~2.1% wear at 41 s followed by lap-2 projection 124% and 'Box soon'.
2. Repeated identical damage pit calls.
3. Tyre-temperature threshold spam (115 then 120 repeatedly).
4. Position/pass spam while entering/in pit lane and under SC transitions.
5. Pass/overtake flip-flop announcements on the same opponent.
6. Social/noise STT phrases produce unsupported-request replies.
7. CLI/version banner still reports V1.8.0.0 despite V1.9.x source package.
8. Roadmap contains stale unchecked items already completed in V1.8+.

## Planned implementation
- Add completed-lap quality metadata and robust clean same-stint tyre wear projection with minimum sample count.
- Preserve hard damage, current weather/compound, game pit window, SC/VSC and penalty exceptions.
- Add repeated strategy/pit-call suppression and thermal alert hysteresis/cooldown.
- Gate position calls in pit/SC instability and debounce pass state.
- Silently ignore common conversational/Whisper filler phrases.
- Close relevant non-EXE roadmap/test gaps and reconcile stale roadmap status.
- Full compile, pytest, targeted real-recording validation, package final source ZIP.


---

## Archived source: `CHECKPOINT_FINALIZATION_B.md`

# CHECKPOINT FINALIZATION B

Base: V1.9.1.5 Weekend Replay Transition Hotfix.

Completed since Checkpoint A:
- Full regression restored clean: 835 tests + 383 subtests after tyre-temperature spam fix preserved the existing 115 C threshold but removed the second 120 C voice crossing.
- Strategy degradation hardening: clean same-stint laps only; first/standing-start lap cannot generate tyre-life box projection; pit/SC/VSC/damage/set-change laps excluded; robust median requires >=2 clean samples.
- Pit lap tyre-set attribution corrected to lap-start fitted set.
- Repeated semantically-identical pit recommendations suppressed for 120 s unless severity/reason/service changes.
- Pit-lane/SC/VSC position narration suppressed and same-opponent pass/re-pass flapping debounced.
- Fuel margin semantics corrected in auto/voice wording.
- Common social/STT filler phrases ignored silently.
- Per-category speech cooldown integration added without overriding explicit immediate cooldowns.
- Control Center coaching mode and radio-detail selectors added and wired to live coaching settings.
- LAN dashboard payload now carries coaching mode/verbosity and mode-specific default focus; manual page selection remains authoritative, while damage/pit auto-pages retain priority.

Still to do:
- Add/finalize tests for dashboard mode focus and Control Center selectors.
- Close roadmap test gaps: golden corner fixtures, latency, LAN/native parity, track map coverage, game-version compatibility.
- Diagnostics SQLite-safe backup and polish.
- Real recording focused replay validation using 2026-09-26 race recording.
- Full roadmap reconciliation/version metadata/release notes.
- Full final regression/compile/startup/package. No EXE/installer changes.


---

## Archived source: `CHECKPOINT_FINALIZATION_C_REAL_RACE_HARDENING.md`

# CHECKPOINT FINALIZATION C — Real-Race Strategy / Radio Hardening (APPLIED)

Working base: V1.9.1.5 Weekend Replay Transition Hotfix source tree under `/mnt/data/final_audit/work/re_ui_lag`.
Windows EXE/installer work remains excluded.

Applied and validated:
- Added completed-lap strategy-quality metadata to `MeasuredLapFact`.
- Completed-lap tyre-set attribution now uses the set fitted at lap start and retains end set separately.
- Pit-lap, SC/VSC, significant-damage and tyre-set-change conditions are latched for completed-lap strategy evidence.
- Tyre-life projection rejects lap 1 / standing-start evidence.
- Tyre-life projection requires >=2 clean same-stint completed laps.
- Pit/outlap, SC/VSC, damage-compromised and set-change laps are excluded from tyre degradation rate.
- Both `pit_strategy` and `strategy_engine` use the same clean-evidence gate.
- Automatic pit recommendations use semantic 120 s repeat suppression while allowing urgency/reason/service changes through.
- Automatic tyre temperature alert has one 115 C band (removes 115+120 duplicate pair); recovery/re-arm remains.
- Overtake/pass event narration suppressed in pit lane and active SC/VSC.
- Same-opponent pass/re-pass narration debounced for 8 s.
- Fuel radio wording now explicitly treats EA m_fuelRemainingLaps as MFD fuel margin rather than literal remaining range.
- Common social PTT filler (`thank you very much`, `bye-bye`, `can I ask you a question`) is silently ignored.
- Added real-race regression tests reproducing the false lap-2 pit projection shape from the supplied recording.

Validation:
- Full pytest: 832 passed + 383 subtests.

Next checkpoint:
- Performance/stability growth audit (unbounded state/history lists, snapshot/deepcopy cost, long replay).
- Control Center coaching mode/radio-detail selectors + native/LAN dashboard focus closure.
- Test-gap closure: golden corner fixture, latency, LAN/native parity, track-map coverage, game-version compatibility.
- Diagnostics SQLite-safe backup.
- Focused validation against uploaded 211 MB race recording.
- Roadmap/version reconciliation, final regression, compile/startup, packaging.


---

## Archived source: `CHECKPOINT_FINALIZATION_D_LONG_REPLAY_PERFORMANCE.md`

# CHECKPOINT FINALIZATION D — Long Replay / High-Rate Telemetry Performance

## Base
Working tree: `/mnt/data/final_audit/work/re_ui_lag`
Base release lineage: V1.9.1.5 Weekend Replay Transition Hotfix.
Windows EXE/installer work remains explicitly excluded.

## Applied source changes

### High-rate decision/coaching decoupling (`src/race_state_receiver.py`)
Both `telemetry` and `lap` packet families are now treated as high-rate sources for expensive engineer/coaching evaluation.

- Raw packets are still decoded and applied to RaceState at full rate.
- Heavy Automatic Engineer evaluation is cadence-gated across the combined `telemetry` + `lap` stream.
- Heavy CORNER COACH / Performance Coach evaluation is cadence-gated across the combined `telemetry` + `lap` stream.
- Critical/session/event paths remain immediate.
- Cadence clocks reset on telemetry-mode and session transitions.

This addresses the user-observed pattern where the map remained smooth while speed/gear/inputs/tyres/ERS became choppy: Motion packets remained cheap, while LapData + CarTelemetry were previously sharing expensive decision work.

### Long-session bounded-state guard
Verified the existing `decision_audit` history is already bounded to the newest 200 entries. Added regression coverage rather than introducing a second conflicting cap.

## Real recording benchmark evidence
Validation recording: `telemetry-20260926T175930Z-429413eb.areplay` (~211 MB, 210,860 packets).

Before this D change, the problematic 70k–80k packet window took approximately 8.08 s in the local replay-processing benchmark. After the combined LapData + CarTelemetry cadence gate, the same window was approximately 4.81 s. Earlier 10k windows remained around 2.3–3.1 s.

Packet-family profiling showed the largest improvement in:
- Packet 2 / LapData: ~2.98 ms avg -> ~1.80 ms avg in the deep window.
- Packet 6 / CarTelemetry: ~1.58 ms avg -> ~0.67 ms avg.

No telemetry packets are intentionally dropped by this change.

## Tests added
- `tests/test_finalization_d_high_rate_decoupling.py`
- `tests/test_finalization_d_long_session_bounds.py`

## Regression status
Full suite after Checkpoint D:
- **834 tests passed**
- **383 subtests passed**
- elapsed ~11.68 s

## Preserved earlier fixes
- Checkpoint C real-race tyre-degradation sample quality gates.
- Opening-lap false pit projection prevention.
- semantic repeated-pit-call suppression.
- pit/SC pass narration suppression and opponent debounce.
- tyre-temperature alert consolidation.
- fuel margin semantics.
- social STT filler suppression.
- V1.9.1.3 memory-mapped indexed replay architecture and bounded replay checkpoints.
- V1.9.1.5 weekend session-transition clock stitching.
- live-only multi-driver Performance Hub and dark Control Center UI.

## Next checkpoint
Checkpoint E: finish genuine non-EXE feature gaps in Control Center / coaching settings and mode-specific dashboard focus, with compatibility tests.


---

## Archived source: `CHECKPOINT_FINALIZATION_E_CONTROL_CENTER_COACHING.md`

# CHECKPOINT FINALIZATION E — Control Center Coaching / Dashboard Focus

## Base
Working tree: `/mnt/data/final_audit/work/re_ui_lag`
Continues from Checkpoint D. Windows EXE/installer work remains excluded.

## Verified implementation
- Control Center exposes persistent Coaching Mode selector.
- Control Center exposes persistent Speech/Radio Verbosity selector.
- Controls are wired to `RaceStateReceiver.set_coaching_mode()` and `set_coaching_verbosity()`.
- Current coaching mode and verbosity propagate through overlay/shared snapshot state.
- Dashboard payload exposes coaching mode, verbosity and focus page metadata.
- Existing radio commands for coaching mode/verbosity remain supported.

## Validation
- `tests/test_finalization_e_control_center_coaching_focus.py`: 4 passed.

## Next checkpoint
Checkpoint F: close validation/test roadmap gaps and reconcile stale roadmap flags:
- known-corner expected-result fixtures
- latency bounds
- LAN/native state parity
- track-map regression coverage
- F1 game-version compatibility
- per-category cooldown integration
- diagnostics SQLite-safe backup verification


---

## Archived source: `CHECKPOINT_FINALIZATION_F_VALIDATION_CLOSURE.md`

# CHECKPOINT FINALIZATION F — Validation / Test-Gap Closure

## Base
Working tree: `/mnt/data/final_audit/work/re_ui_lag`
Continues from Checkpoint E. Windows EXE/installer work remains excluded.

## Applied / verified
- Added deterministic game-version compatibility coverage for format-2026 traffic reporting game years 25 and 26; rejects unsupported years.
- Added fallback track-map coverage regression for every circuit in `PHYSICAL_TURN_COUNTS`; every supported circuit has a closed fallback outline.
- Added LAN/native coaching-state parity coverage for coaching mode, verbosity and dashboard focus metadata.
- Added deterministic latency-health boundary regression around the 100 ms health threshold.
- Added golden known-corner expected-result fixture covering early braking, late throttle and below-deadband suppression.
- Hardened diagnostics export: the live Performance Hub SQLite DB is snapshotted via SQLite backup API rather than raw-copying a WAL-backed file.
- Added regression verifying the diagnostic SQLite snapshot is readable and consistent.

## Validation
Focused A-F regression set: **17 passed**.
`tests/test_finalization_f_validation_closure.py`: **6 passed**.

## Next checkpoint
Checkpoint G:
- integrate category cooldown defaults into runtime engineer path without weakening explicit critical/event timing;
- reconcile stale roadmap checkboxes for completed selectors/test coverage;
- focused replay validation against uploaded 211 MB race recording;
- inspect remaining non-EXE roadmap items and close only genuine local/F1 scope gaps.


---

## Archived source: `CHECKPOINT_FINALIZATION_G_RUNTIME_ROADMAP.md`

# CHECKPOINT FINALIZATION G — Runtime Cooldowns / Roadmap Reconciliation

## Base
Working tree: `/mnt/data/final_audit/work/re_ui_lag`
Continues from Checkpoint F. Windows EXE/installer work remains excluded.

## Applied
- Runtime engineer now imports and uses the shared `DEFAULT_COOLDOWNS_S` profile through a deterministic key/priority category classifier.
- Coaching assist calls that previously hard-coded the same 6 s value now use the runtime category profile.
- Explicit safety/event/rule cooldown overrides remain authoritative; critical calls are not weakened.
- Added `tests/test_finalization_g_cooldown_runtime.py`.
- Reconciled stale roadmap flags for features already implemented/verified during finalization:
  - supported-track corner segmentation coverage
  - mode-specific dashboard focus
  - Control Center coaching-mode selector
  - Control Center speech-verbosity selector
  - per-category cooldown runtime integration
  - known-corner golden fixture
  - latency regression coverage
  - LAN/native coaching-state parity
  - track-map regression coverage
  - F1 game-version compatibility
  - strategy/arbitration/adaptation finalization items
  - diagnostics polish

## Validation
- Runtime cooldown + real-race guard focused tests: 6 passed.
- A-F focused regression set immediately before this checkpoint: 17 passed.

## Replay validation status
- Uploaded validation recording: `/mnt/data/final_audit/telemetry-20260926T175930Z-429413eb.areplay` (~211 MB / known 210,860 packets).
- A monolithic `--replay-fast` validation invocation exceeded the 45 s execution window before completion; no correctness conclusion is drawn from that timeout.
- Next step is chunked/packet-range replay validation so each validation stage completes within the tool window while preserving the same source recording.

## Next checkpoint
Checkpoint H:
- chunked validation of the supplied 211 MB race recording, with emphasis on opening-lap pit strategy, damage, SC, pit entry/exit, restart and race-end continuity;
- inspect remaining local/F1 non-EXE pending roadmap items;
- then full regression + compile/startup + final source packaging.


---

## Archived source: `CHECKPOINT_FINALIZATION_H_REAL_RECORDING_VALIDATION.md`

# CHECKPOINT FINALIZATION H — Supplied Real-Race Recording Validation

## Base
Working tree: `/mnt/data/final_audit/work/re_ui_lag`
Continues from Checkpoint G. Windows EXE/installer work remains excluded.

## Validation recording
`/mnt/data/final_audit/telemetry-20260926T175930Z-429413eb.areplay`
- 210,860 packets
- logical game duration: ~1191.63 s
- session UID: 17550237624876286868
- Melbourne race recording with damage, SC, pit stop and restart.

## Why validation was chunked
A monolithic fast replay exceeded the tool execution window. The recording was therefore replayed sequentially in bounded packet ranges with deterministic engine checkpoints persisted between ranges:
- 0–40,000
- 40,000–80,000
- 80,000–120,000
- 120,000–160,000
- 160,000–200,000
- 200,000–210,860

This keeps each validation run safely below the execution timeout while preserving RaceState/performance history between chunks.

## Results
### Opening-race pit strategy
- No automatic pit recommendation was emitted from packet 0 through 80,000 (~448 s / five completed laps).
- This directly validates the Checkpoint C clean-stint evidence gate against the supplied race recording: the former lap-2 false tyre-projection pit call is gone.

### Damage pit decision
- First deterministic strategy pit call appeared at session time ~675.248 s:
  `Box this lap. Front wing damage 100 percent. Fit Soft, set 5. Replace front wing.`
- This is a legitimate damage-service exception and remains allowed.

### Safety Car / pit sequence
Observed in correct order:
- Safety Car deployed ~678.235 s.
- Pit lane entry ~743.208 s.
- Pit exit ~786.550 s.
- Safety Car returning ~960.689 s.
- Safety Car returned to pits ~1004.693 s.
- Race resumed / green ~1017.719 s.

### Pit-lane pass spam
- No pass/overtake narration was emitted during the actual pit-lane interval in the chunked validation.
- Pass narration resumes only after pit exit / resumed track running.

### Tyre-temperature spam
- No repeated 115/120 C duplicate tyre-temperature message pair was emitted in the supplied replay after the consolidation fix.

### Important chunk-validation limitation
The artificial validation harness restores only the deterministic RaceState replay checkpoint between chunks. `AutomaticEngineer` semantic cooldown state intentionally resets on restore, so the first post-boundary range can re-emit a still-active pit plan once. That is a harness artifact, not a continuous-production replay result; it is not counted as a duplicate-call failure.

## Performance evidence
Chunk processing times stayed bounded across the race:
- 0–40k: ~11.48 s
- 40–80k: ~15.30 s
- 80–120k: ~19.00 s
- 120–160k: ~13.30 s
- 160–200k: ~13.73 s
- 200k–end: ~6.00 s
No monotonic growth pattern was observed across these equal-size deep-race chunks.

## Next checkpoint
Checkpoint I:
- audit remaining genuine local/F1 P0/P1 non-EXE roadmap items versus stale/deferred entries;
- close feasible metric/data-quality gaps without expanding into cloud/community/multi-sim/installer scope;
- full regression suite;
- compile/startup checks;
- version/release-note reconciliation and final source ZIP packaging.


---

## Archived source: `CHECKPOINT_FINALIZATION_I_FULL_REGRESSION.md`

# CHECKPOINT FINALIZATION I — Local/F1 Scope Closure + Full Regression

## Base
Working tree: `/mnt/data/final_audit/work/re_ui_lag`
Continues from Checkpoint H. Windows EXE/installer work remains excluded.

## Roadmap reconciliation
Audited remaining P0/P1 local/F1 entries against current source. Several partial/stale boxes were already implemented in later code and are now reconciled:
- measured path-curvature apex and apex speed comparison
- coasting distance + time metrics
- pickup-to-full-throttle distance + time comparison
- rich steering-shape metrics (rate, corrections, smoothness, unwind)
- corner confidence/data-quality + outlier rejection
- per-track/per-corner PRE distance override
- reference-relative minimum-speed/throttle-pickup/exit-speed efficiency
- session trend visualization
- measured advice-outcome tracking without intent inference

Explicitly deferred/out-of-current-scope items are now labelled as such rather than appearing as accidental local/F1 gaps:
- hosted/community reference packs
- multi-sim adapters/abstraction
- cloud/team/community sharing
- optional PDF report
- Windows EXE/installer and target-PC-only validation

## Code hardening preserved
- Checkpoint C real-race pit/tyre/fuel/radio guards
- Checkpoint D long-replay/high-rate decoupling
- Checkpoint E Control Center coaching selectors/focus
- Checkpoint F golden fixtures/version/map/parity/diagnostics SQLite backup
- Checkpoint G runtime cooldown integration
- Checkpoint H supplied 211 MB real-race validation

## Full regression
- **845 tests passed**
- **383 subtests passed**
- elapsed ~12.25 s

## Next checkpoint
Checkpoint J / finalization:
- bump/reconcile source version and release notes for the completed source-only build
- compile all source/tools
- startup/import smoke test
- ZIP integrity validation
- create final full source package only (no EXE/installer build changes)


---

## Archived source: `CHECKPOINT_FINALIZATION_J_FINAL_PACKAGE.md`

# CHECKPOINT FINALIZATION J — V1.9.2.0 Final Source Package

## Release
V1.9.2.0 — Final Source Hardening

## Scope
- Complete local/F1 source finalization through Checkpoints A–I.
- Windows EXE/PyInstaller/Inno installer work intentionally not modified/finalized.
- Physical Windows target-PC endurance remains a machine-side acceptance item, not a source-code gap.

## Final validation
- Supplied real-race recording: 210,860 packets / ~1191.63 s validated in six bounded sequential chunks.
- No false opening/early tyre-projection pit recommendation through first five completed laps.
- Legitimate 100% front-wing damage pit call retained.
- Safety Car -> pit entry -> pit exit -> SC return -> green restart retained.
- Pit-lane pass narration suppression and tyre-temperature duplicate suppression validated.
- Full pytest: 845 passed + 383 subtests.
- Python compileall: passed.
- `python -m src.main --help`: passed.

## Final package hygiene
The final source ZIP excludes runtime-generated `analysis/`, `recordings/`, `.pytest_cache`, `__pycache__`, and `.pyc` files. Source, tests, tools, docs, maps/default metadata, references, settings, and unchanged installer source definitions remain included.

## Resume point
If future work is required, use `NEXT_CONTINUATION_PROMPT_V1.9.2.0.md` and this checkpoint. Do not reopen already-closed finalization items without new evidence from live telemetry, replay, tests, or a concrete code audit.


---

## Archived source: `CHECKPOINT_PERFORMANCE_HUB_1.md`

# Performance Hub checkpoint 1

Completed:
- Added dependency-free SQLite performance history store (`src/performance_history.py`).
- Persistent driver profiles from F1 participant/session identity.
- Persistent session summary + coaching metrics by track.
- Read APIs in storage layer for overview, per-track history and individual session drill-down.

Next checkpoint:
- Wire complete ParticipantData identity into RaceState.
- Persist sessions automatically at authoritative session summary boundaries.
- Add browser API/routes and Performance Hub UI.


---

## Archived source: `CHECKPOINT_PERFORMANCE_HUB_2.md`

# Performance Hub checkpoint 2

Completed:
- Extended F1 player identity to retain driver ID, team ID, nationality ID, platform ID and My Team flag.
- Automatic SQLite persistence at session/report boundary; no database work in live packet processing.
- Added browser Performance Hub UI with driver profile, track cards, track trend, session history, opportunities and strengths.

Next checkpoint:
- Wire HTTP routes/APIs.
- Add migration/import for existing JSON history.
- Add tests, roadmap/update notes and package.


---

## Archived source: `CHECKPOINT_PERFORMANCE_HUB_3.md`

# Performance Hub checkpoint 3 — implementation complete

Completed:
- Persistent local driver/profile/session database.
- Automatic F1 identity capture and session persistence.
- Existing JSON coaching history migration.
- `/performance` browser UI and three read-only JSON APIs.
- New V1.9 regression tests.
- Roadmap and release notes updated.

Resume point if further work is required:
1. Run full regression suite and compile/startup checks.
2. Package full project as V1.9.0.0.
3. User validation: complete/replay several sessions across at least two tracks, then open `/performance` and verify driver, track grouping, trends and session counts.


---

## Archived source: `CHECKPOINT_V1.9.1.0_1_LIVE_HISTORY_AUTHORITY.md`

# V1.9.1.0 Checkpoint 1 — Live History Authority

Completed:
- Added a hard live/replay authority gate before all persistent personal-history writes.
- Replay continues to produce temporary reports/validation only.
- Switched authoritative Performance Hub storage to `analysis/performance_history_live.sqlite3`.
- Old `performance_history.sqlite3` is not read by the new hub, avoiding replay contamination from V1.9.0.0.


---

## Archived source: `CHECKPOINT_V1.9.1.0_2_CONTROL_CENTER_APP.md`

# V1.9.1.0 Checkpoint 2 — Control Center Application

Completed:
- Control Center converted from frameless/topmost Tool overlay to normal Qt application window.
- Native OS minimize/maximize/close behavior.
- CONTROL tab contains existing runtime controls and overlay launchers.
- PERFORMANCE HUB tab embeds live-only driver/track/session history.
- Browser Performance Hub remains available through Open in Browser.
- Control Center is never click-through or forced topmost.


---

## Archived source: `CHECKPOINT_V1.9.1.0_3_VALIDATION.md`

# V1.9.1.0 Checkpoint 3 — Validation

Implementation complete.

Validation target:
- Full regression suite.
- Compile all Python sources.
- Main CLI startup/import check.
- ZIP integrity.

User validation after install:
1. Run a replay and verify Performance Hub totals do not change.
2. Switch to live F1 and complete a session.
3. Verify the live session appears in the PERFORMANCE HUB tab and `/performance`.
4. Verify Control Center behaves as a normal desktop window while racing overlays remain topmost/click-through capable.

Completed validation:
- 817 tests passed.
- 383 subtests passed.
- 113 Python source/tool files compiled successfully.
- `python -m src.main --help` startup/import check passed.


---

## Archived source: `CHECKPOINT_V1.9.1.1_LONG_REPLAY_STABILITY.md`

# V1.9.1.1 Long Replay Stability Checkpoint

Base: V1.9.1.0.

Completed:
- Preserved the V1.8.0.0.3 smooth replay scheduler and multi-session stitching.
- Strategy decisions still compute at up to 4 Hz.
- Heavy validation persistence is decoupled from strategy cadence: 1 s live, 5 s replay.
- Validation bundle strategy/event buffers now have hard upper bounds.
- Finalized-session validation rows are released from memory after the ZIP is written.
- Added regression coverage for bounded buffers and finalized-session cleanup.
- Full suite: 818 tests + 383 subtests passed.

Reason:
Long weekend recordings could become progressively heavier once the race section began because full strategy validation payloads were retained in memory and written at strategy-assessment cadence. This hotfix preserves decision logic while bounding validation overhead.


---

## Archived source: `CHECKPOINT_V1.9.1.2_TELEMETRY_DECISION_DECOUPLING.md`

# V1.9.1.2 Checkpoint — Telemetry / Decision Decoupling

## Symptom
Long replay remained smooth on the map (Motion packets) while speed/gear/inputs/telemetry became choppy.

## Root cause
Car Telemetry packets were eligible to execute heavyweight Automatic Engineer + CORNER COACH + Performance Coach evaluation at the raw telemetry packet rate. Motion packets use a much lighter path, explaining the map/telemetry split.

## Fix
- Full telemetry state decode/update remains per packet.
- Automatic Engineer telemetry evaluation capped at 20 Hz.
- CORNER COACH + integrated Performance Coach telemetry evaluation capped at 20 Hz.
- Lap and non-telemetry critical packet families remain immediate.
- Cadence anchors reset on session/source changes.
- No telemetry samples are deliberately dropped by replay transport.

## Resume
Continue from V1.9.1.2 and validate a long full-weekend replay at x1 without touching the seek slider.


---

## Archived source: `CHECKPOINT_V1.9.1.3_LONG_REPLAY_MEMORY_ARCHITECTURE.md`

# V1.9.1.3 checkpoint — Long Replay Memory Architecture

## Root cause found
Interactive ReplayController previously called `read_replay()` and materialised every UDP payload as a Python `bytes` object. A ~541 MB weekend recording therefore consumed roughly the whole payload size plus Python object/list overhead before playback. During playback, full serialized engine checkpoints were also retained at lap/packet boundaries, so memory/GC/page pressure increased as the replay progressed.

## Fix
- Interactive replay now uses `_IndexedReplayRecords`: compact numeric arrays + an OS memory map.
- Only the current packet payload is copied into Python when it is replayed.
- The game-time timeline is built from indexed header metadata without loading packet bodies.
- Seek rebuild iterates indexed records directly and never materialises a large slice.
- Automatic checkpoints are sparse: initial/session-boundary/131072-packet anchors, not every lap.
- Checkpoint cache is hard-bounded to 6 entries and 48 MiB total.
- Oversized single checkpoints are skipped rather than consuming the replay memory budget.
- Existing replay timing/session stitching/no-catch-up behavior is preserved.

## Validation
- Added `tests/test_v1913_long_replay_memory.py`.
- Full suite: 820 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V1.9.1.4_MULTI_DRIVER_PERFORMANCE_HUB.md`

# V1.9.1.4 Checkpoint — Multi-Driver Performance Hub

Completed:
- Performance history remains LIVE-game-only.
- Session identity is now driver-scoped so identical EA session UID/track/type cannot reassign a stored session to another driver.
- Existing V1.9 live-history databases migrate to schema V3 by driver-scoping legacy session keys.
- First stored driver becomes the initial preferred profile; later live sessions from other drivers are stored independently and do not silently change the viewed profile.
- Control Center Performance Hub has a DRIVER selector with persistent preferred-driver selection.
- Browser Performance Hub already supported multi-driver querying and now remembers its selected driver in localStorage.
- Native Performance Hub tables, headers, selection, scrollbars and empty viewport now use the Control Center dark theme.
- Row-number vertical headers are hidden for a cleaner dark UI.

Resume from this checkpoint if interrupted. Base includes all V1.9.1.3 long-replay memory fixes.


---

## Archived source: `CHECKPOINT_V1.9.1.5_WEEKEND_REPLAY_TRANSITION.md`

# Checkpoint V1.9.1.5 — Weekend Replay Transition

Base: V1.9.1.4 Multi-Driver Performance Hub + Dark UI.

Completed:
- Fixed indexed replay clock regression that could leave long logical gaps at Practice -> Qualifying and Qualifying -> Race boundaries.
- Replay clock now extracts session UID/time from transition headers even when player index is 255.
- Large same-session sessionTime discontinuities are collapsed to a bounded frame step instead of becoming dead wall-clock waits.
- Session UID changes and sessionTime resets remain authoritative weekend boundaries.
- Long-replay mmap/index memory architecture from V1.9.1.3 is preserved.
- No telemetry packets are dropped.
- Added regression coverage for player-index-255 handoff, same-UID loading jumps, and full Practice -> Qualifying -> Race auto continuation.


---

## Archived source: `CHECKPOINT_V1.9.2.1_FINAL.md`

# CHECKPOINT V1.9.2.1 — Performance History Correctness Final

## Baseline
V1.9.2.0 FINAL SOURCE HARDENING.

## Concrete source defects fixed
- LIVE Performance Hub persistence is independent of optional `auto_reports`.
- Final completed-lap coach-report refresh upserts the same driver-scoped Performance Hub session.
- Replay coach-report generation cannot mutate legacy persistent `driver_history.json`.
- Wins/podiums count only actual EA race session types (`Race`, `Race 2`, `Race 3`), not Qualifying/Time Trial positions.

## Tests
- Added `tests/test_v1921_performance_history_completion.py`.
- Updated the older live-history source-structure regression to reflect the deliberately decoupled persistence architecture.
- Full regression: **849 passed + 383 subtests**.
- Python compileall: passed.
- `python -m src.main --help`: passed.

## Preservation
- No deterministic race/coaching decision behavior changed.
- V1.9.2.0 supplied-real-race strategy behavior preserved.
- Indexed/memory-mapped replay, weekend stitching, high-rate decoupling, clean-stint pit evidence gates, multi-driver Performance Hub and normal-window Control Center preserved.
- Windows EXE/PyInstaller/Inno files were not modified.

## Resume
Use `NEXT_CONTINUATION_PROMPT_V1.9.2.1.md`.


---

## Archived source: `CHECKPOINT_V1.9.2.1_PERFORMANCE_HISTORY_CORRECTNESS.md`

# CHECKPOINT V1.9.2.1 — Performance History Correctness Audit

## Baseline
RaceEngineer V1.9.2.0 FINAL SOURCE HARDENING.

## Concrete source defects found
1. Persistent Performance Hub history was still written only from inside the optional `auto_reports` block. With automatic HTML/JSON coach reports disabled, LIVE sessions were not persisted at all.
2. A final coach-report refresh after the completed-lap set grew did not refresh the existing Performance Hub session row, so final stored coach data could remain an earlier partial snapshot.
3. Performance Hub wins/podium totals counted any P1/P2/P3 session, including Qualifying and Time Trial, rather than only EA race session types 15..17 (`Race`, `Race 2`, `Race 3`).

## Applied fixes
- Imported `build_coach_report` and made LIVE Performance Hub persistence independent of `auto_reports`.
- When reports are disabled, the deterministic coach report is built in memory only; no report files are forced.
- Replay remains read-only for persistent history.
- Final coach-report refresh now idempotently upserts the LIVE Performance Hub row as well.
- Wins/podium aggregates now only count `Race`, `Race 2`, and `Race 3` session rows.

## Tests added
`tests/test_v1921_performance_history_completion.py`
- race-only wins/podium semantics
- LIVE persistence with `auto_reports=False`
- replay remains read-only with `auto_reports=False`

Targeted result: 3 passed.

## Preservation rules
No Windows EXE/PyInstaller/Inno changes. No race/coach deterministic decision behavior changed. All V1.9.2.0 replay, strategy, UI, Performance Hub multi-driver, and validation behavior is preserved.

## Next
Run full regression, then continue source audit for additional concrete defects only.

## Additional concrete defect closed
`save_coach_report()` itself updated legacy `analysis/driver_history.json` unconditionally. Therefore replay auto-report generation could still mutate persistent driver history even though the receiver's explicit persistence path was LIVE-only.

### Fix
- Added `record_driver_history` keyword to `save_coach_report()`.
- LIVE receiver report saves pass the live-history authority gate.
- Replay final report in `src/main.py` explicitly passes `record_driver_history=False`.
- Report JSON now truthfully records whether legacy driver history was actually updated.

### Additional regression
Added a replay report test proving report files can be generated while legacy persistent history remains untouched.
Targeted combined result: 10 passed.


---

## Archived source: `CHECKPOINT_V2.0.0_SCORE_CONTRACT_EVIDENCE_MODEL.md`

# CHECKPOINT V2.0.0 — Score Contract & Evidence Model

## Protected baseline
RaceEngineer V1.9.2.1 Performance History Correctness.

The V1.9.2.1 deterministic systems remain protected: LIVE-only driver-scoped Performance Hub persistence, replay read-only history, normal-window Control Center, indexed/memory-mapped replay, weekend stitching, high-rate telemetry/decision decoupling, clean-stint strategy evidence, CORNER COACH scheduling and existing supplied-recording validation behavior.

## V2.0.0 implemented
Added `src/performance_scoring.py` as a downstream presentation/analysis layer. It does not detect corners or re-derive braking/apex/throttle telemetry.

Contracts:
- `TechniqueMetricEvidence`
- `TechniqueScore`
- `CornerTechniqueScore`
- `LapTechniqueScore`
- `EvidenceTier`
- `CompatibilityState`
- explicit `N/A` score state
- `score_model_version = 2.0.0`
- reference identity/version
- confidence and sample counts
- raw evidence IDs and serialized raw measurement evidence

Initial dimensions:
- braking point
- brake release
- trail braking
- turn-in
- min/apex speed
- throttle pickup
- time to full throttle
- exit speed
- steering control
- racing-line consistency (explicit Tier-3 N/A at single-corner level)

## Deterministic scoring rules
- deadbands and bounded normalization are explicit and inspectable
- same input produces same output
- trusted metric worsening cannot improve its score
- directional performance metrics do not penalize simply exceeding the active reference where the metric semantics support that
- missing/untrusted/incompatible evidence is `N/A`, never 50/100
- confidence bounds presentation-score departure without rewriting raw evidence
- lap score requires Tier-2 evidence: at least two scored corners and minimum coverage (default 60%)
- compatibility reuses existing `data_quality.reference_compatible()` gates rather than adding a second independent quality model

## Startup visibility rule
`OverlaySuite.show()` now hides every driving overlay first and opens only Control Center. All driving overlays require an explicit user launcher action.

This preserves Control Center as the normal application window while meeting the requirement that no overlays open by default.

## Free LLM rule for post-LIVE review
The V2 roadmap addendum records that V2.0.3+ Performance Review narrative/explanations use the free local Ollama LLM path. The LLM is downstream of deterministic review evidence only and is not permitted to invent telemetry, alter scores/evidence, or make deterministic race/coaching decisions.

V2.0.0 itself does not move authoritative scoring into the LLM and does not enable LLM work on the live telemetry hot path.

## Validation
New regression file: `tests/test_v200_score_contract.py`

Covers:
- startup overlay visibility contract
- deterministic/monotonic normalization
- directional score semantics
- N/A behavior
- model/reference/confidence/sample/raw-evidence serialization
- CornerAnalysis reuse
- condition incompatibility blocking
- Tier-2 lap evidence/coverage gates
- reuse of existing quality compatibility gates

Result after changes:
- **859 tests passed**
- **383 subtests passed**

The previous 849-test baseline remains green; V2.0.0 adds 10 tests.

## Next implementation checkpoint
V2.0.1 — Live Corner Intelligence.

Use the V2.0.0 score/evidence contract. Consume confirmed eligible completed-corner `CornerAnalysis` only. Keep live work bounded, no heavy history queries, one primary visual result, fast auto-hide, confidence gate, no additional audio queue, and race-context suppression remains authoritative.


---

## Archived source: `CHECKPOINT_V2.0.1.1_LIVE_CORNER_FEEDBACK_UI_HOTFIX.md`

# V2.0.1.1 — Live Corner Feedback UI Hotfix

## Purpose
Align V2.0.1 with the original V2 requirement for a dedicated, glanceable live post-corner scoring/feedback overlay.

## Changes
- Added a standalone **Live Corner Feedback** overlay launcher in Control Center.
- Overlay remains OFF/closed by default. Opening the launcher arms the transient card.
- A new eligible corner result automatically pops the card up; the existing authoritative 4-second result expiry hides it again.
- UI is compact and inspired by the requested reference style without copying proprietary artwork.
- Dynamic metric presentation for MIN CORNER SPEED, BRAKING POINT, THROTTLE PICKUP, EXIT SPEED, or generic CORNER PERFORMANCE.
- Shows TURN, technique score, grade, one dominant correction, and a five-zone reference-relative bar.
- Uses existing `live_corner_result`; no second detector and no new speech queue.
- Performance Coach remains the detailed coaching overlay.
- Track Learning remains instructional; Performance Coach remains reference-relative.

## Roadmap alignment
The original V2 requirement explicitly includes a live post-corner scoring/feedback overlay, every-corner scoring, lap/stint separation, and post-session Performance Review. V2 continues to follow the three-lane design: LIVE PERFORMANCE, LAP/STINT INTELLIGENCE, and POST-SESSION PERFORMANCE REVIEW.

## Validation
- 867 tests passed
- 383 subtests passed
- 0 failures


---

## Archived source: `CHECKPOINT_V2.0.1.2_LIVE_CORNER_FEEDBACK_PERSISTENCE_HOTFIX.md`

# V2.0.1.2 — Live Corner Feedback Persistence Hotfix

## Issue
The manually opened Live Corner Feedback overlay closed on the next UI refresh whenever no active `live_corner_result` was present. This made the launcher appear to open and immediately close before the next eligible corner completed.

## Fix
- The overlay now stays visible once manually enabled.
- Between eligible corner results it displays `WAITING FOR ELIGIBLE CORNER`.
- When a new result arrives, the existing V2 live corner result is displayed immediately.
- When the result's four-second authoritative window expires, the panel returns to the waiting state instead of closing.
- The overlay closes/disables only when the user explicitly closes it.
- It remains OFF by default at application startup.
- No telemetry, scoring, coaching, speech, arbitration, replay, or persistence logic was changed.

## Validation
- Targeted V2 tests: 9 passed.
- Full regression: 868 tests + 383 subtests passed, 0 failures.


---

## Archived source: `CHECKPOINT_V2.0.1.3_SELECTABLE_INSTANT_CORNER_FEEDBACK.md`

# V2.0.1.3 — Selectable Instant Corner Feedback Hotfix

## Scope
- Fix delayed Live Corner Feedback publication.
- Add selectable one-at-a-time live metrics requested from the reference UI.
- Preserve V1.9.2.1 / V2.0.0 deterministic authority and existing POST voice timing.

## Changes
- Live visual result now publishes on the first authoritative timing sample at or beyond corner exit; it no longer waits for the 8 m POST-voice safety distance.
- POST voice logic remains unchanged and retains its existing timing/arbitration window.
- Live Corner Feedback metric selector supports:
  - Corner Performance
  - Hitting Apex
  - Min Corner Speed
  - Trail Braking
  - Throttle Points
  - Brake Points
- Only one metric is displayed at a time.
- New live result evidence exports brake-release delta, apex-position delta and apex-speed delta in addition to the existing brake/min-speed/throttle/exit evidence.
- Overlay remains manually enabled and stays open between corners in WAITING state.
- No new speech queue or independent telemetry detector was added.

## Validation
- `python -m compileall -q src`: PASS
- Full pytest: 871 passed + 383 subtests passed, 0 failures.


---

## Archived source: `CHECKPOINT_V2.0.1.4_PHYSICAL_CORNER_LATENCY_NA_CLARITY.md`

# V2.0.1.4 — Physical-Corner Latency + N/A Clarity Hotfix

## User-reported problems
- Live Corner Feedback could arrive noticeably after a turn, especially where one CoachingZone contains multiple physical turns (for example T1–T2).
- N/A metrics still showed the marker in the centre of the green band, which visually implied a perfect result.
- Corner Performance displayed a 0–100 number while the bar position represented time loss, making the number/bar relationship unclear.

## Fixes
- Live feedback is now closed/published against each compiled `PhysicalCorner.end_m` using `_performance_boundaries`, while reusing the existing deterministic `_diagnose()` and score pipeline.
- Multi-turn CoachingZones remain authoritative for PRE/POST voice scheduling; this change affects only the visual V2 live-corner result.
- A lightweight per-physical-corner `CoachingZone` view narrows existing compiled reference evidence. It does not create a new detector.
- Missing metric evidence now renders a disabled grey scale with no position marker and explicit text such as `NO VALID BRAKE POINT DATA`.
- Corner Performance bar now represents the 0–100 technique score. Measured `LOST/GAINED/MATCHED` time is displayed separately underneath.

## Preservation
- No new speech queue.
- Existing CORNER COACH PRE/POST timing is unchanged.
- No replay persistence changes.
- No pit/strategy changes.
- All overlays still start closed.

## Validation
- `874 passed, 383 subtests passed`
- Added regression tests for per-physical-corner publication, N/A disabled-marker semantics, and score/time-loss visual separation.


---

## Archived source: `CHECKPOINT_V2.0.1.5_LIVE_APEX_EVIDENCE_HOTFIX.md`

# V2.0.1.5 — Live Apex Evidence Hotfix

## Goal
Make HITTING APEX available at the first physical-corner exit whenever both current and reference path geometry contain sufficient trustworthy evidence, without delaying live feedback or fabricating apex data.

## Changes
- Live single-physical-corner (`LIVE_Tx`) diagnosis now runs geometry comparison directly even when timing attribution has not produced a dominant-loss corner.
- `path_curvature_apex()` now supports short physical corners with 5–6 valid X/Z samples using a narrower curvature chord and appropriately reduced confidence.
- Apex-position delta is published only when both current and reference traces have real path-curvature apex evidence. A physical-apex fallback can still support phase boundaries but can no longer masquerade as measured HITTING APEX data.
- Added `apex_position_trusted` and `apex_position_confidence` to live result evidence for inspection/debugging.
- Existing first-exit publication path, POST voice timing, race arbitration, scoring authority, replay persistence and V1.9.2.1 protected systems are unchanged.

## Validation
- Focused V2.0.1 tests: 18 passed.
- Full suite: 877 tests passed + 383 subtests passed.
- 0 failures.

## Expected UI behavior
- HITTING APEX shows EARLY/LATE/on-target data as soon as the physical corner is complete when both traces have sufficient path evidence.
- Short corners no longer fail solely because they have fewer than seven 5 m geometry bins.
- If actual path geometry is genuinely unavailable or insufficient, the UI continues to show NO VALID APEX DATA rather than a fake center/perfect result.


---

## Archived source: `CHECKPOINT_V2.0.1.6_ADAPTIVE_PHYSICAL_TRACK_AUTHORITY.md`

# V2.0.1.6 — Adaptive Physical Track Authority

## Goal
Use one shared physical-track model everywhere and let it improve gradually from additional clean completed laps.

## Implemented
- Added persistent adaptive per-track geometry learning on the game's lap-distance axis.
- Only complete clean laps are accepted: valid, start-line anchored, no pit lap, traffic compromise, race-control compromise, significant damage, pause, replay seek, or session restart.
- First clean lap establishes the canonical measured path and physical T1..Tn model.
- Later clean laps refine the canonical path with a bounded robust running update; one lap cannot move the model wholesale.
- Added whole-lap geometry sanity gates and per-point movement caps.
- Added geometry fingerprints so replaying/processing the exact same lap repeatedly does not bias the learned track model.
- Persisted learning metadata in the existing per-track map file: accepted clean-lap count, last lap and recent geometry fingerprints.
- Physical turn boundaries are re-derived from the refined canonical geometry and stabilised against the previous T1..Tn model.
- Reference compilation now prefers the shared persisted physical-track authority when available.
- Loaded compiled references are rebound to the current shared physical geometry while preserving their own reference driving events.
- CORNER COACH refreshes the shared physical geometry once on the next lap so map, physical turns, apex feedback and coaching use the same latest authority.
- Existing V5 per-track file format remains compatible; new learning metadata is additive.

## Important scope
This learns the measured canonical driving-path geometry and physical turn/apex model from clean telemetry. It does not claim to reconstruct exact track-edge or kerb polygons that the game does not transmit directly.

## Validation
- New adaptive-track tests: clean-lap gating, gradual update/capping, shared reference authority.
- Full regression: 880 tests + 383 subtests passed, 0 failures.


---

## Archived source: `CHECKPOINT_V2.0.1_LIVE_CORNER_INTELLIGENCE.md`

# Checkpoint — V2.0.1 Live Corner Intelligence

Baseline: V2.0.0 Score Contract & Evidence Model, preserving V1.9.2.1 deterministic behavior.

## Implemented

- Added Tier-1 live corner scoring directly downstream of the existing CORNER COACH `Diagnosis` measurements.
- No second brake/apex/throttle detector was introduced.
- Live result contains:
  - corner/zone identity,
  - score and grade,
  - dominant measured issue,
  - measured loss/gain,
  - brake-point delta,
  - minimum-speed delta,
  - throttle-pickup delta,
  - exit-speed delta,
  - confidence/sample count,
  - score model version.
- Missing evidence remains `N/A`.
- Result is visual-only: no new speech queue or TTS ownership.
- Compact result auto-expires after 4 seconds of session time.
- Existing race-context arbitration suppresses the visual result when technique coaching does not own attention.

## UI naming cleanup

- User-facing `SPEED COACH` window renamed to `PERFORMANCE COACH`.
- Performance Coach master control now displays `COACH` rather than `SPEED`.
- Radio parser accepts `performance coach` / `performance coaching` while retaining legacy `speed coach` aliases for compatibility.
- Control Center overlay launcher buttons now display full names instead of abbreviations.
- Internal launcher keys remain stable to preserve validated routing.

## Performance Coach vs Track Learning

- Performance Coach remains reference-relative and performance-judgment oriented.
- Track Learning now uses dedicated proactive instructional PRE wording describing the upcoming corner target without reference-relative judgment wording.
- Track Learning suppresses the V2 live score/result and comparative POST feedback so it remains instructional rather than evaluative.
- Existing deterministic measurement/reference data remains the source of any learning target shown.

## Preservation

- Control Center remains a normal application window.
- Driving overlays still start closed.
- Replay/history/strategy/weekend stitching/high-rate telemetry architecture unchanged.
- No pit/strategy logic changed.
- No extra coaching speech queue added.
- V2 scoring remains presentation-only and does not drive deterministic coaching decisions.

## Validation

Full regression:

- 865 tests passed
- 383 subtests passed
- 0 failures

This is additive to the V2.0.0 suite (859 tests + 383 subtests).


---

## Archived source: `CHECKPOINT_V2.0.2.0_LAP_STINT_INTELLIGENCE.md`

# V2.0.2.0 — Lap & Stint Intelligence

Built from V2.0.1.6 Adaptive Physical Track Authority.

## Implemented
- Added bounded `LivePerformanceAccumulator` consuming the already-authoritative V2.0.1 physical-corner results.
- No second corner/brake/apex/throttle detector was added.
- Finalizes a deterministic lap result at the authoritative lap boundary.
- Produces lap technique score only when the lap is valid, at least two corner scores are available, and scored-corner coverage is >= 60%.
- Reports scored/eligible corner coverage and confidence.
- Finds biggest measured loss using measured time cost as the primary importance signal.
- Computes best same-corner improvement versus previous completed lap.
- Detects repeated issue only after at least two occurrences in the lap.
- Computes realistic available gain from positive measured corner losses.
- Produces current/next-lap focus from the largest trusted time loss, not the lowest score.
- Adds provisional braking/throttle/corner-speed scores only after >=3 trusted metric observations, using a bounded recent-lap window.
- Keeps a bounded 24-lap session history in memory; no heavy persistent-history query is added to the packet path.
- Invalid/compromised laps remain N/A for lap technique score.
- Exposes `lap_stint_intelligence` and `last_lap_intelligence` through CORNER COACH status.
- Performance Coach briefly shows the completed-lap score, coverage, and next-lap focus for 8 seconds when no live corner result owns the panel.
- Live corner results still have display priority over lap summary.

## Validation
- New V2.0.2 targeted tests cover coverage gate, N/A behavior, time-cost focus, same-corner improvement, repeated issue, minimum-sample provisional groups, and invalid-lap handling.
- Full suite: 887 passed + 383 subtests passed, 0 failures.


---

## Archived source: `CHECKPOINT_V2.0.2.1_REFERENCE_SELECTION_OVERLAY_SNAPSHOT_HOTFIX.md`

# V2.0.2.1 — Reference Selection Overlay Snapshot Hotfix

## Failure reproduced
Selecting/activating a rival reference while the overlay refresh loop was running could repeatedly fail in `build_overlay_snapshot()` with:

`NameError: name 'session_time_s' is not defined`

The V2.0.2 lap/stint result expiry branch referenced a local name that had never been assigned. Because the overlay refresh calls `provider.snapshot()` continuously, the same exception was printed on every refresh cycle.

## Fix
- Resolve the authoritative `current_session_s` from `state.session.session_time_s` once before evaluating either lap/stint or live-corner results.
- Use the same session clock for `last_lap_intelligence` expiry and `live_corner_result` expiry.
- Preserve replay-deterministic/session-time expiry semantics; no wall-clock substitution.
- No changes to rival reference selection, reference compilation, score logic, CORNER COACH diagnosis, track authority, strategy, or persistent history.
- Updated displayed release marker to V2.0.2.1.

## Regression coverage
Added tests proving:
1. a live `last_lap_intelligence` snapshot no longer raises and remains exposed before its session-time expiry;
2. the result disappears after its authoritative session-time expiry.

## Validation
- Targeted V2.0.2 tests: 9 passed.
- Full suite: 889 passed, 383 subtests passed.
- `python -m compileall -q src`: passed.


---

## Archived source: `CHECKPOINT_V2.0.2.2_UI_OWNERSHIP_APEX_SUMMARY_HOTFIX.md`

# V2.0.2.2 — UI Ownership, Apex Fallback, Dedicated Lap Summary Hotfix

## Issues fixed
1. HITTING APEX could remain N/A even when the Performance Coach had enough usable corner evidence to estimate where the car's low-speed/apex region occurred.
2. Lap/Stint Intelligence was only visible when no live corner result owned the Performance Coach driver panel.
3. The same completed-corner verdict was shown in both Performance Coach and Live Corner Feedback.

## Changes
- Added lower-confidence apex estimate based on current vs reference minimum-speed location when path-curvature apex evidence is unavailable.
- Path-curvature apex remains authoritative; the fallback is explicitly tagged `min_speed_location` and does not fake `apex_position_trusted`.
- HITTING APEX consumes the authoritative path apex first, then the tagged estimate when trusted.
- Added a dedicated `LapStintSummaryPanel` to Performance Coach.
- Latest completed-lap summary remains visible until replaced by the next lap/session reset instead of expiring after 8 seconds.
- Removed completed-corner score/diagnosis from the Performance Coach driver/reference panel. Live Corner Feedback is now the sole post-corner verdict surface.
- Performance Coach driver panel now stays focused on current phase plus live driver/reference bars.

## Validation
- `PYTHONPATH=. pytest -q`: 893 passed, 383 subtests passed.
- `python -m compileall -q src`: passed.


---

## Archived source: `CHECKPOINT_V2.0.2.3_ACTIONABLE_LIVE_CORNER_FEEDBACK.md`

# V2.0.2.3 — Actionable Live Corner Feedback

## Goal
Make the completed-corner card tell the driver one specific thing to work on instead of only showing score/grade and measured time loss.

## Changes
- Added `CornerCoachEngine._live_action_text()` as a pure presentation translation of the existing deterministic `Diagnosis`.
- The action is downstream of diagnosis and never derives a new cause from the 0–100 score.
- `live_corner_result` now publishes exactly one `action_text`.
- Corner Performance card now shows a fourth line:
  - `WORK ON: ...` for a trusted dominant issue,
  - `KEEP: KEEP CURRENT APPROACH` for gain/match,
  - `ACTION: NO TRUSTED ACTION YET` when time loss exists but no trusted corrective cause exists.
- Added deterministic action wording for brake point, brake release/trail braking, over-braking, coasting, minimum/apex speed, throttle pickup, full throttle, exit speed, turn-in, steering corrections/smoothness/unwind.
- Increased Live Corner Feedback height from 178 px to 204 px so the action line has its own space.
- No new telemetry detector, no score-to-coaching dependency, no new speech/audio queue.

## Examples
- `WORK ON: BRAKE ~12 m LATER`
- `WORK ON: TRAIL BRAKE ~9 m LONGER`
- `WORK ON: CARRY ~7 km/h MORE MIN SPEED`
- `WORK ON: PICK UP THROTTLE ~0.18 s EARLIER`
- `WORK ON: REMOVE ~2 STEERING CORRECTIONS`

## Validation
- Focused V2.0.1/V2.0.2 tests: 34 passed.
- Full regression: 896 passed, 383 subtests passed, 0 failures.
- `python -m compileall -q src`: passed.


---

## Archived source: `CHECKPOINT_V2.0.3.0_PERFORMANCE_REVIEW_CORE_INTERACTIVE.md`

# V2.0.3.0 — Performance Review Core + Interactive Review

## Scope
Built on V2.0.2.3 without changing the protected packet-rate measurement/diagnosis path.

## Deterministic review core
- Added `src/performance_review.py`.
- Consumes stored session coach measurements and existing `CornerAnalysis` rows only; no second corner/brake/apex/throttle detector.
- Produces session technique score only after at least two scored eligible laps.
- Produces per-lap score/grade/confidence/coverage and delta-to-recorded-reference.
- Produces every-corner robust score/grade/confidence plus stored dominant issue, phase and measured mean loss.
- Produces technique group summaries (braking, trail braking, turn-in, corner speed, throttle, exit, steering) only when >=3 trusted metric observations exist.
- Preserves explicit N/A rather than synthesizing neutral scores.
- Carries data-quality/eligible/excluded-lap evidence, biggest opportunities, strengths, recurring patterns and improvement trend.
- `build_coach_report()` now stores the review object at session finalization; legacy stored sessions are built on-demand in `PerformanceHistoryStore.review_detail()`.

## Interactive Performance Review browser screen
Click any stored session in Performance Hub to open an embedded review area with:
- session score / best lap / potential / confidence cards,
- interactive technique profile radar,
- lap trend graph,
- biggest opportunities,
- data-quality coverage,
- every-corner table,
- interactive physical track map using the shared adaptive physical-track authority when available,
- corner click -> telemetry zoom around that physical turn,
- linked distance-domain telemetry charts for SPEED / BRAKE / THROTTLE / GEAR / ERS / DELTA,
- pointer cursor readout on telemetry charts,
- full-lap reset.

## Review reference selector
- Added `/api/performance/reference-options` and `/api/performance/review`.
- Review can use the recorded active reference or another stored same-driver/same-track session as a visual graph reference.
- Historical visual reference choice is persisted in the browser per track.
- Selecting a different visual reference deliberately does NOT rewrite historical deterministic scores/diagnoses; those remain tied to the reference active when the session was recorded.

## Preservation
- LIVE-only Performance Hub persistence remains driver-scoped.
- Replay remains read-only for persistent history.
- No packet-rate DB/history queries were added.
- CORNER COACH / race engineer / strategy / voice arbitration unchanged.
- Indexed replay architecture unchanged.

## Validation
- Python source compilation: PASS.
- Browser JavaScript syntax (`node --check`): PASS.
- Full regression: 899 tests + 383 subtests passed, 0 failures.


---

## Archived source: `CHECKPOINT_V2.0.3.10_DASH_TRACK_DELETE_REFERENCE_SELECTOR_GRAPH.md`

# V2.0.3.10 — Dash / Track Delete / Reference Selector / Graph Visibility

## Fixes
- Added BACK navigation to the F1 Dash web UI; returns to Performance Hub.
- Added DELETE TRACK DATA to Overall Track Performance with two confirmation prompts.
- Track deletion removes all Performance Hub sessions for the selected local profile/track only. Learned physical maps and installed references are preserved.
- Deleting one session now preserves the current track selection when other sessions for that track remain.
- Track Performance list is now alphabetical (case-insensitive) instead of latest-session order.
- Performance Review installed-reference discovery now reads the structured `user_data/references` root introduced in V2.0.3.9, restoring rival reference options after local-data migration.
- Recorded active reference telemetry is now explicitly exposed to the review visual-reference layer, so the cyan reference trace is available for graphs.
- Reference telemetry is drawn as a cyan dashed trace on top of the amber driver trace so overlapping traces remain visible.

## Safety / authority
- Session/track deletes remain local-PC-only actions.
- Track delete does not remove reusable map/reference assets.
- Historical deterministic scores remain tied to the recorded authoritative reference; selecting another analysis reference remains comparison-only.

## Validation
- `python -m py_compile src/performance_history.py src/performance_hub_ui.py src/dashboard_server.py` — PASS
- Full pytest regression — 929 passed + 383 subtests, 0 failures.


---

## Archived source: `CHECKPOINT_V2.0.3.11_TRACK_DELETE_DASH_BACK_VISIBILITY_HOTFIX.md`

# V2.0.3.11 — Track Delete + F1 Dash Back Visibility Hotfix

## Fixed
- `Unknown` track entries now resolve legacy sessions whose `track_name` and `track_id` are both NULL. Track detail and DELETE TRACK DATA use the same canonical Unknown-track semantics as the overview list.
- Full-track deletion now successfully removes Unknown-track Performance Hub sessions for the selected local driver profile.
- F1 Dash BACK control moved out of the page-tab group and is now a dedicated `← BACK TO HUB` button at the top-left of the 800×480 dash stage.
- BACK remains above the WAITING FOR TELEMETRY overlay, so it is available even when no F1 UDP data is currently arriving.

## Preserved
- Double confirmation for full track deletion.
- Learned physical track maps and installed references are not deleted by Performance Hub track-history deletion.
- Driver-profile scoping and live-only Performance History authority.

## Validation
- Full test suite: 930 passed + 383 subtests, 0 failures.
- Added regression for NULL/Unknown track detail and deletion.


---

## Archived source: `CHECKPOINT_V2.0.3.12_F1_DASH_BACK_OVERLAY_HOTFIX.md`

# V2.0.3.12 — F1 Dash Back Overlay Hotfix

## Fixed
- `← BACK TO HUB` now renders above the `WAITING FOR TELEMETRY` blackout layer.
- The waiting overlay no longer intercepts pointer events, so BACK remains clickable with no UDP telemetry.
- Back navigation continues to route to `/performance` and remains available on all F1 Dash pages.

## Root cause
- The 800x480 dash stylesheet assigned the waiting overlay `z-index:99` while the back button used `z-index:40`, so the button was present but visually dimmed underneath the blackout layer.

## Validation
- Full test suite: 931 passed + 383 subtests, 0 failures.
- Python compile check passed for `src/dashboard_server.py`.
- Added regression coverage for back-button stacking and waiting-overlay pointer behavior.


---

## Archived source: `CHECKPOINT_V2.0.3.13_RESPONSIVE_CONTROL_SESSION_DELETE.md`

# V2.0.3.13 — Responsive Control Center + Replay Delete

Implemented:
- Replay / Session Analysis now exposes DELETE RECORDING on every recorded session and in the opened-session detail.
- Deletion requires an explicit confirmation and is local-machine only.
- Deletes the `.areplay`, recorder sidecar, replay-analysis cache entry and session-library metadata; Performance Hub history and analysis reports are intentionally preserved.
- Control Center CONTROL tab is now a widget-resizable QScrollArea with vertical/horizontal scrollbars as needed.
- Legacy tiny Control Center fonts are raised to a readable minimum, launcher buttons are larger, and the overlay launcher grid reflows from 5 to 2 columns as the window narrows.
- Performance Hub CSS now uses the full available width with responsive breakpoints for embedded and browser use.
- Existing protected telemetry/coaching/reference logic unchanged.

Validation:
- 936 tests + 383 subtests passed.
- Python compileall passed.
- Session Analysis and Performance Hub JavaScript syntax checks passed with node --check.


---

## Archived source: `CHECKPOINT_V2.0.3.14_CONTROL_CENTER_SCROLL_THEME_HOTFIX.md`

# V2.0.3.14 — Control Center Scroll Theme Hotfix

## Issue
V2.0.3.13 made the Control Center scrollable, but on Windows the QScrollArea viewport retained the native light palette. This painted a white scroll surface underneath the existing dark-themed controls.

## Fix
- Explicitly names and dark-themes the Control Center QScrollArea, its viewport, and the scroll content widget.
- Enables styled backgrounds on the viewport/content so Qt actually paints the requested dark surface.
- Adds dark vertical/horizontal scrollbar styling with visible hover states.
- Does not change the existing control logic, launcher reflow, Performance Hub behavior, telemetry, coaching, or recording paths.

## Validation
- Targeted responsive UI/theme tests: 6 passed.
- Full regression: 937 tests + 383 subtests passed, 0 failures.
- Python compileall: PASS.


---

## Archived source: `CHECKPOINT_V2.0.3.1_LOCAL_DRIVER_PROFILE_UNIFIED_PERFORMANCE_HUB.md`

# V2.0.3.1 — Local Driver Profile + Unified Performance Hub

## Changes
- Performance history ownership is now the explicitly selected local human driver profile, not the F1 in-game participant name.
- Startup profile selector runs before live UDP processing. Profiles can be created, selected and renamed.
- Game driver/team/number remain stored as per-session metadata only. Driving as different F1 drivers no longer splits one human profile.
- Existing V3 history is migrated into one `Local Driver` profile so legacy game identities are merged instead of treated as different people.
- Session context is persisted and filterable by broad session group (Practice / Time Trial / Qualifying / Sprint / Race / Other) and game mode (Driver Career / My Team Career / Grand Prix / Time Trial / etc.; unknown IDs remain visible rather than guessed).
- The Control Center Performance Hub now embeds the exact `/performance` browser page with QtWebEngine when available, eliminating native/browser UI divergence. A native fallback remains for minimal Qt installations.
- Browser/embedded UI now exposes PROFILE, SESSION and MODE filters, while each session row retains the in-game driver identity for context.
- Review-reference compatibility is now local-profile + track scoped rather than game-driver + track scoped.

## Preservation
- Persistent history remains LIVE-only.
- Replay remains read-only for personal history.
- Game driver identity is not discarded; it is metadata for each session.
- Existing deterministic scores, diagnoses, review reference rules and telemetry graphs are unchanged.

## Validation
- `pytest -q`: 902 tests + 383 subtests passed.
- `python -m compileall -q src`: PASS.
- Performance Hub JavaScript syntax (`node --check`): PASS.


---

## Archived source: `CHECKPOINT_V2.0.3.2_LEGACY_PERFORMANCE_DB_MIGRATION_HOTFIX.md`

# CHECKPOINT — V2.0.3.2 Legacy Performance DB Migration Hotfix

## Failure fixed
Existing Performance History databases created before schema V4 crashed at application startup with:

`sqlite3.OperationalError: no such column: user_profile_fk`

Cause: `_schema()` attempted to create `idx_sessions_profile_track` before the legacy `sessions` table had been ALTERed to add `user_profile_fk`. `CREATE TABLE IF NOT EXISTS` does not add columns to an existing SQLite table.

## Fix
- Keep legacy-safe indexes in the initial schema script.
- Run V4 `ALTER TABLE` migrations first.
- Create `idx_sessions_profile_track` only after `user_profile_fk` exists.
- Preserve and migrate existing session rows into the local human Driver Profile.
- Added an explicit V3 -> V4 migration regression test using a real legacy-shaped SQLite schema.

## Validation
- Full pytest: 903 passed + 383 subtests passed.
- Python compileall: PASS.


---

## Archived source: `CHECKPOINT_V2.0.3.3_PERFORMANCE_REVIEW_REFERENCE_GRAPH_CLARITY_HOTFIX.md`

# V2.0.3.3 Performance Review Reference + Graph Clarity Hotfix

## Fixed
- Performance Review no longer renders missing numeric evidence as `0` merely because JavaScript coerces `null` to zero.
- Legacy sessions recorded before V2 detailed review evidence explicitly show `LEGACY SUMMARY ONLY` instead of blank/ambiguous review charts.
- Legacy lap-trend panel preserves Session Best fact while stating that trustworthy per-lap trend evidence was not stored.
- Legacy telemetry panel explicitly states when raw telemetry traces were not persisted.
- Visual Reference selector now always exposes the reviewed session's `Session best`.
- Recorded active reference is shown when the stored session actually has a recorded reference time/trace.
- New live sessions preserve `reference_mode`, allowing recorded external/rival references to be identified correctly.
- Installed same-track Race Engineer reference files, including `references/<TRACK>/rival_reference.json`, are enumerated as visual reference choices.
- Stored same-profile/same-track session-best references remain supported.
- Review API now accepts reference selectors for session best, recorded reference, installed external/rival reference, or stored session.

## Important legacy limitation
A pre-V2.0.3 session cannot be given telemetry traces or per-lap scoring evidence that was never persisted. The UI now says this explicitly instead of fabricating data. Session summary facts such as best lap remain available.

## Validation
- Full pytest: 906 passed + 383 subtests passed.
- Python compilation: PASS.


---

## Archived source: `CHECKPOINT_V2.0.3.4_SELECTED_REFERENCE_DETAILED_CORNER_AI_SUMMARY.md`

# CHECKPOINT — V2.0.3.4 Selected Reference Analysis + Detailed Corner + AI Summary

## Completed
- Fixed the Performance Review reference selector so a newly selected rival/stored/session-best reference affects a dedicated deterministic comparison layer.
- Recomputed the DELTA chart against the selected reference from distance-aligned speed traces; the previous build could leave DELTA tied to the originally recorded reference.
- Added selected-reference per-corner comparisons for brake onset, minimum speed, throttle pickup and exit speed where traces support them.
- Preserved historical score/diagnosis authority: recorded scores remain tied to the reference used during the live session.
- Added detailed per-corner evidence aggregation for braking point, brake release, trail braking, turn-in, apex, min speed, throttle pickup, full throttle, exit speed, steering and entry/mid/exit time loss.
- Added separate deterministic DATA-BASED SUMMARY sections for the full session and each corner.
- Added separate on-demand AI SESSION SUMMARY and AI CORNER SUMMARY sections using local Ollama. AI receives only compact deterministic evidence and is explanation-only.
- Added UI labels that distinguish ANALYSIS REFERENCE from recorded authoritative scoring.

## Validation
- Full pytest: 909 passed + 383 subtests, 0 failures.
- Performance Hub JavaScript syntax check: PASS (node --check).
- Python compile checks for modified modules: PASS.

## Preservation
- No change to live telemetry packet path, CORNER COACH scheduling, race strategy, pit logic, or persistent history authority.
- Replay remains read-only for persistent history.


---

## Archived source: `CHECKPOINT_V2.0.3.5_LIVE_HISTORY_BACKEND_MAP_HUB_NAVIGATION.md`

# V2.0.3.5 — Live History Autosave + Backend Track Learning + Hub Navigation

## Fixes
1. LIVE sessions are now autosaved after every completed measured lap, independent of REC.
2. Report/review generation and SQLite writes happen on a dedicated coalescing worker so the telemetry path is not blocked.
3. Same session UID/track/type is upserted, preserving one session row while laps_completed advances.
4. Persistent track geometry learning is backend-owned by MeasuredPerformanceRecorder at authoritative lap boundaries. Dashboard code no longer writes/refines track geometry.
5. Performance Hub now has BACK and REFRESH buttons. BACK closes the review first; REFRESH reloads overview/track/current review data.

## Storage policy
REC OFF: persistent compact performance analysis only.
REC ON: same performance analysis plus full .areplay packet recording.
Replay playback remains read-only for persistent live history.

## Validation
913 tests + 383 subtests passed.
Python compile checks passed for modified modules.


---

## Archived source: `CHECKPOINT_V2.0.3.6_AUTHORITATIVE_LIVE_LAP_DAMAGE_HISTORY.md`

# V2.0.3.6 — Authoritative Live Lap + Damage History Hotfix

## Problem
V2.0.3.5 triggered REC-OFF Performance Hub autosaves primarily from the measured-performance `completed` list. In practice, that list can lag the game's actual completed-lap counter or exclude compromised analysis laps, so a Practice session could show fewer/no laps even while the live Performance Coach had progressed to later laps.

## Fix
- The F1 game lap counter is now authoritative for `laps_completed` in live Performance History.
- Autosave triggers when either the game completed-lap count or the analysis-completed count advances.
- Analysis laps may lag without hiding actual completed laps.
- The autosave now reuses `SessionSummaryTracker` so REC-OFF history also carries the live session's damage/wear/warnings summary.
- Damage-compromised laps remain counted as completed session laps, but existing V2 quality gates can exclude them from trusted technique scoring/diagnosis.
- No raw packet recording is required; REC remains optional.

## Validation
- 914 tests passed
- 383 subtests passed
- 0 failures


---

## Archived source: `CHECKPOINT_V2.0.3.7_PERFORMANCE_REVIEW_EVIDENCE_MAP_AI_HOTFIX.md`

# V2.0.3.7 — Performance Review Evidence / Map / AI Hotfix

## Problems reproduced from user screenshots
1. Session row showed the authoritative game lap count (8) and best lap, while Performance Review showed 0 eligible laps, no scored corners and no technique profile.
2. Telemetry trace existed, but the review map said no stored physical track geometry.
3. Selected rival comparison reported 0 corners compared because review geometry/corner evidence was absent.
4. AI summary returned `Unexpected token 'N', "Not found" is not valid JSON`.

## Root causes
- REC-OFF autosave persisted the legacy/full-lap performance recorder but did not persist the V2 live Lap/Stint Intelligence accumulator that powers the on-track Performance Coach.
- Review geometry was resolved opportunistically from the current runtime map store rather than being snapshotted with the session.
- The `/api/performance/ai-summary` implementation had been placed in the GET handler while the UI correctly called it using POST, causing HTTP 404 text `Not found` and JSON parse failure.

## Changes
- Persist V2 live lap/corner intelligence on every LIVE history autosave.
- Enrich saved live lap intelligence with authoritative lap time and data-quality status when matching raw lap evidence exists.
- Performance Review falls back to this V2 evidence when legacy `lap_comparisons` are unavailable.
- Compromised laps/corners remain visible as observed evidence, but their scores remain N/A; damage/traffic cannot become trusted technique score evidence.
- Snapshot the shared backend physical track geometry into the stored session review.
- Review API prefers the session-stored geometry and only falls back to current persisted map data when necessary.
- Move AI summary endpoint into the POST handler so local Ollama requests return JSON correctly.
- Corner table distinguishes `TRUSTED` from `OBSERVED / COMPROMISED` evidence.

## Validation
- 918 tests passed
- 383 subtests passed
- 0 failures
- Modified Python modules compile successfully.


---

## Archived source: `CHECKPOINT_V2.0.3.8_LAP_TRACK_AI_MANAGEMENT_HOTFIX.md`

# V2.0.3.8 — Lap / Track / AI / Session Management Hotfix

## Completed
- Added SESSION OVERALL / LAP N selector inside Performance Review.
- Added compact REC-OFF per-lap telemetry persistence for SPEED/BRAKE/THROTTLE/GEAR/ERS/DELTA analysis.
- Added same-session individual laps as analysis-reference choices when their compact telemetry is stored.
- Analysis-reference changes now reload the selected review automatically; no manual Refresh required.
- Added local-only DELETE SESSION action with confirmation in the Performance Hub UI.
- Added explicit Performance Hub color key.
- Added deterministic cross-session track improvement summary.
- Added separate Overall Track Performance section, distinct from Session Data / Session Performance Review.
- Added overall predicted potential lap based only on stored measured potential evidence.
- Added separate deterministic track summary and on-demand local-Ollama AI track summary.
- Kept data-based and AI summaries separate for track, session and corner scopes.
- Increased local Ollama summary timeout from 18 s to 75 s and reduced prompt payload size to avoid cold-start/session-summary timeouts.
- Preserved historical score authority: changing a visual/analysis reference does not rewrite recorded scores.

## Storage policy
REC OFF continues to persist compact analysis data only. V2.0.3.8 additionally stores bounded per-lap distance-domain traces needed for lap-by-lap review and same-session lap comparison. Full raw UDP packets are still only stored by REC/.areplay.

## Validation
- 922 tests passed
- 383 subtests passed
- Python compilation passed
- Performance Hub JavaScript syntax passed


---

## Archived source: `CHECKPOINT_V2.0.3.9_LOCAL_DATA_DELETE_SESSION_NAVIGATION.md`

# V2.0.3.9 — Local Data / Delete / Session Navigation

Implemented:

- Fixed Performance Hub session deletion when Control Center is opened through the same PC's LAN address. Local destructive actions now accept loopback or an exact client-IP == Host-IP match; other LAN clients remain read-only.
- Added explicit BACK and REFRESH buttons to Replay / Session Analysis. BACK returns to `/performance`.
- Added centralized `src/app_paths.py` and startup legacy-data migration for mutable runtime data.
- Structured recordings, session metadata/reports/indexes, track maps/landmarks, references, validation artifacts, diagnostics, logs and cache under `user_data/`.
- Kept the authoritative LIVE Performance History SQLite database and legacy driver history in `analysis/` for protected upgrade compatibility.
- Added `LOCAL_DATA_LAYOUT.md` describing ownership and migration rules.

Validation:

- Full pytest: 925 passed + 383 subtests.
- Python compileall: PASS.


---

## Archived source: `CHECKPOINT_V2.0.4.0_DETAILED_CORNER_BREAKDOWN.md`

# V2.0.4.0 — Detailed Corner Technique Breakdown

Base: V2.0.3.14 stable tagged baseline.

Implemented:
- Review-model version advanced to 2.0.4.
- Every eligible corner now exposes explicit three-phase review evidence:
  - Braking/Entry: brake point, peak brake, brake release, release ramp, trail braking, entry time cost.
  - Mid-corner: turn-in, apex position, minimum speed, apex speed, steering corrections/smoothness, mid time cost.
  - Exit: throttle pickup, pickup timing, time-to-full-throttle, full-throttle point, exit speed, slip evidence, steering unwind, exit time cost.
- Total measured corner time loss retained separately from technique score.
- Secondary issue candidates are aggregated and shown as REVIEW ONLY; they cannot replace the dominant deterministic coaching diagnosis.
- Confidence and evidence status remain inherited from authoritative deterministic measurements.
- Missing/untrusted evidence remains N/A; no synthetic 50/100 or inferred steering/path/slip values.
- Live CORNER COACH persistence now carries additional already-measured fields and phase losses into future Performance Hub history.
- Selected analysis-reference comparison expanded to include brake onset, peak brake, brake release, min/apex/exit speed, throttle pickup, full throttle, pickup-to-full distance and selected-reference phase/total time-cost estimates from persisted distance traces.
- Selected-reference path/steering/slip metrics remain N/A when those channels were not persisted.
- Performance Hub Detailed Corner UI now renders separate Braking/Entry, Mid-Corner and Exit cards plus review-only secondary evidence and selected-reference detail.

Authority rules preserved:
- Coaching remains upstream and deterministic.
- Scores remain downstream of diagnosis.
- V2.0.4 review does not redetect physical corners or driving events.
- AI remains explanation-only.
- Replay remains read-only for persistent live history.

Validation:
- Full regression: 940 tests + 383 subtests passed, 0 failures.
- Python compilation passed for modified modules.

Next roadmap stage after user validation: V2.0.5 — Every-Corner Performance Map.


---

## Archived source: `CHECKPOINT_V2.0.4.1_PHASE_LOSSES_RUNTIME_HOTFIX.md`

# V2.0.4.1 — Phase Losses Runtime Hotfix

## Failure fixed
Live telemetry could terminate the application when a corner result was published with:

`'Diagnosis' object has no attribute 'phase_losses'`

## Root cause
`Diagnosis` defines the phase-loss contract as `phase_losses_s`, but the V2.0.4 live-corner publication path incorrectly read `diag.phase_losses` while copying the values into the Performance Hub/live result payload.

## Fix
`src/corner_coach.py` now reads `diag.phase_losses_s` and preserves the external payload field name `phase_losses` for downstream compatibility.

## Regression coverage
Added `tests/test_v2041_phase_losses_runtime_hotfix.py` which executes `_publish_v201_corner_result()` using a real `Diagnosis` object containing phase losses and verifies the published payload.

## Validation
- `python -m py_compile src/corner_coach.py`: PASS
- targeted runtime regression: 1 passed
- full suite: **941 passed, 383 subtests passed**


---

## Archived source: `CHECKPOINT_V2.0.4.2_PER_LAP_CORNER_VALIDITY_HOTFIX.md`

# V2.0.4.2 — Per-Lap Corner + Lap 1 Validity Hotfix

Base: V2.0.4.1.

## Fixed
1. Lap 1 validity authority
   - CORNER COACH now keeps sticky validity for the logical lap it owns.
   - At lap-number transition it no longer reads the new lap's validity to finalize the old lap.
   - Performance report reconciliation re-applies completed-lap validity/quality from MeasuredPerformance as the authoritative persisted lap fact.

2. Individual-lap corner selection
   - Every authoritative completed timed lap remains present in Performance Review even when no technique score/comparison row was generated.
   - Per-lap review consumes that lap's exact live CORNER COACH corner rows.
   - REC-ON/legacy exact per-lap CornerAnalysis rows are used as a measured fallback when the live accumulator row is absent.

3. Detailed corner breakdown for every lap
   - Individual lap review now carries its own corner score, loss/gain, diagnosis, confidence and braking/mid/exit detail.
   - Session aggregate rows are never substituted as if they were lap-specific evidence.
   - Missing per-lap evidence remains N/A rather than being invented.

## Validation
- Python compile: PASS
- Targeted V2.0.4 regression: 16 passed
- Full regression: 945 passed, 383 subtests passed, 0 failures


---

## Archived source: `CHECKPOINT_V2.0.4.3_GAME_STYLE_SUMMARY_AI_COACHING.md`

# V2.0.4.3 — Game-Style Session/Lap Summary + AI Coaching Prompt

Built on V2.0.4.2.

## Implemented
- Added deterministic game-style summary to Performance Hub for Session Overall and each selected lap.
- Summary shows lap time, S1/S2/S3, validity, warnings, track-limit warnings, penalties, captured assists, selected-reference lap time/gap, and session theoretical/potential lap where applicable.
- Gap is recalculated from the currently selected analysis/reference option on every review request.
- Lap view uses the selected lap's authoritative persisted lap facts; session view uses the best persisted timed lap for sector breakdown.
- Added human-readable assist labels (TC, ABS, gearbox, custom setup, equal performance) without inventing missing assists.
- Reworked local Ollama session/corner prompt into driver-facing prose facts instead of raw JSON/schema data.
- Prompt explicitly forbids discussing JSON, schemas, keys, field names, payloads, variables, or internal model structure.
- AI remains explanation-only; deterministic telemetry, scoring, diagnosis and time loss remain authoritative.

## Validation
- Full suite: 949 tests + 383 subtests passed, 0 failures.
- Python compilation passed for modified modules.
- Performance Hub JavaScript syntax checked with Node.


---

## Archived source: `CHECKPOINT_V2.0.4.4_SESSION_QUICK_GLANCE.md`

# V2.0.4.4 — Session Quick Glance

Built on V2.0.4.3.

## Added
- Additive game-style **SESSION LAP TIMES** panel shown immediately when a stored session is opened.
- Keeps existing Session/Lap Summary cards and all current tabs unchanged.
- Shows every completed stored lap in one table with:
  - rank (fastest order)
  - game lap number
  - lap time
  - gap to the currently selected Analysis Reference
  - S1 / S2 / S3
  - validity
  - warnings
  - penalties
  - captured assists
- Best lap is highlighted.
- Invalid laps remain visible but visually de-emphasized.
- Adds theoretical-best row using the best trusted stored S1/S2/S3 values.
- Changing Analysis Reference reloads the review and recalculates every lap gap plus theoretical-best gap.
- Read-only presentation only; no stored history is rewritten.

## Evidence behavior
- Existing sessions display whatever lap/sector/assist data was actually persisted by their original build.
- Missing legacy sector or assist evidence remains `--` / `N/A`; it is never invented.
- New sessions continue to persist authoritative Session History sector times through the existing measured-performance/session-report path.

## Validation
- 951 tests + 383 subtests passed.
- Python compile passed for modified modules.
- Performance Hub JavaScript syntax passed with Node `--check`.


---

## Archived source: `CHECKPOINT_V2.0.5.0_EVERY_CORNER_PERFORMANCE_MAP.md`

# V2.0.5.0 — Every-Corner Performance Map

Base: V2.0.4.4 Session Quick Glance.

Implemented the review-mode Every-Corner Performance Map without changing the protected live driving path.

## Review map
- Added a dedicated **EVERY-CORNER PERFORMANCE MAP** to the CORNERS review tab.
- Preserved the existing Telemetry tab map and linked telemetry behavior.
- Every stored physical corner is rendered against the persisted track geometry.
- Each corner provides:
  - corner number,
  - score and grade,
  - dominant diagnosis,
  - measured corner time cost,
  - active heat-map value.
- Added compact per-corner review cards below the map for quick scanning.
- Clicking a map marker or corner card selects that corner and opens/scrolls to its full V2.0.4 detailed analysis.

## Heat-map modes
- Score
- Time loss / gain
- Speed deficit
- Braking delta
- Throttle delta
- Racing-line deviation

Reference-relative modes use the currently selected Analysis Reference when persisted comparison traces support it. Recorded authoritative scores are never rewritten by reference selection.

Racing-line deviation uses only persisted geometric racing-line evidence. Missing per-corner path evidence remains N/A/grey; no path values are inferred from apex or steering proxies.

## Live-path preservation
The feature is review-only. No extra live corner detector, telemetry cadence, coaching arbitration, or speech work was added.

## Validation
- Python compilation: PASS
- Performance Hub JavaScript syntax: PASS
- Full regression: **953 tests + 383 subtests passed, 0 failures**


---

## Archived source: `CHECKPOINT_V2.0.5.10_LAP_VIEW_SCORE_RECOVERY.md`

# V2.0.5.10 — Lap View Continuity + Score Recovery

## Fixes
- Keeps all authoritative completed timed laps selectable in the Performance Hub VIEW selector, even if a stale cached performance review contains only the latest stint.
- Detects stale `performance_review` coverage after garage/resume and deterministically rebuilds it from merged `live_lap_intelligence`, `lap_comparisons`, `lap_facts`, and `lap_telemetry`.
- Merges cached `performance_review.laps` and `performance_review.lap_reviews` across same-session autosaves so later garage/resume snapshots no longer shrink the review to only the newest stint.
- Recovers authoritative lap/corner scores for existing sessions where the merged live intelligence is still present; missing evidence remains N/A.
- Preserves V2.0.5.9 assist icon semantics (green = used/active, gray = off/unavailable).

## Validation
- 978 tests + 383 subtests passed
- Python compilation passed


---

## Archived source: `CHECKPOINT_V2.0.5.1_CORNER_MAP_TABLE_PROGRESS_REFINEMENT.md`

# V2.0.5.1 Corner Map / Table / Progress Refinement

Base: V2.0.5.0 Every-Corner Performance Map

Changes:
- CORNERS map now uses the same map presentation/dimensions as the TELEMETRY tab (700x350 viewBox, same padding, line weight and corner marker sizing).
- Removed the duplicated per-corner card/chip strip below the map.
- Expanded EVERY CORNER table so all six review metrics are visible in one place: Score, Time loss/gain, Speed deficit, Braking delta, Throttle delta, Racing-line deviation.
- Added deterministic per-cell colour coding while preserving N/A grey when evidence is absent.
- Selecting any corner now shows six progress bars in Detailed Corner Analysis for Score, Time loss/gain, Speed deficit, Braking delta, Throttle delta and Racing-line deviation.
- Existing detailed braking/mid-corner/exit evidence, deterministic summary and local AI summary remain unchanged below the progress bars.
- Reference-relative values continue to use the currently selected Analysis Reference where persisted evidence allows it.

Validation:
- Python compilation PASS.
- Performance Hub JavaScript syntax PASS.
- Full regression: 956 tests + 383 subtests passed, 0 failures.


---

## Archived source: `CHECKPOINT_V2.0.5.2_PERFORMANCE_HUB_UI_UX_CLEANUP.md`

# V2.0.5.2 — Performance Hub UI/UX Cleanup

Base: V2.0.5.1 Every-Corner Performance Map refinement.

## Scope
UI-only organization and interaction cleanup. Deterministic telemetry, scoring, reference authority, history persistence, coaching logic, and analysis calculations are unchanged.

## Changes
- Reworked visual hierarchy with a sticky app toolbar, clearer section labels, compact context pills, improved spacing, and consistent hover/focus states.
- Grouped profile, track browser, track trend, overall track summary, session history, and session review into clearer information layers.
- Track filters are grouped as PROFILE / SESSION / MODE controls instead of mixed inline labels.
- Color/evidence legend and reference-authority explanation use progressive disclosure to reduce permanent clutter.
- Session history is visually separated and selected session highlighting is retained.
- Session quick-glance rows are now interactive: clicking a lap directly opens that lap review.
- Review tabs are visually consolidated into one navigation strip.
- Telemetry tab now groups the track map and selected-corner context in one panel, with linked telemetry in the adjacent panel.
- Corners tab now groups the every-corner map and performance table side-by-side on wide screens; detailed selected-corner analysis is full-width below them.
- Corner table remains the single all-corner data surface; row hover/selection is clearer.
- Detailed corner progress metrics use a denser responsive grid.
- Responsive breakpoints hide lower-priority session-history columns on smaller widths while preserving the core session/lap data.
- No measured values were removed; layout collapses responsively rather than clipping.

## Validation
- Python compilation: PASS
- Performance Hub JavaScript syntax: PASS
- Targeted V2.0.5.2 UI tests: 3 passed
- Full regression: 959 tests + 383 subtests passed, 0 failures


---

## Archived source: `CHECKPOINT_V2.0.5.3_CORNER_DETAIL_LAYOUT_REFINEMENT.md`

# V2.0.5.3 Corner Detail Layout Refinement

Built on V2.0.5.2.

## Changes
- Compacted Control Center overlay launcher buttons and increased columns at common widths.
- Added explicit horizontal scrollbar/gutter/styling to Every Corner table and a minimum table width so hidden columns remain reachable.
- Reworked Detailed Corner Analysis for wide screens:
  - six progress metrics remain two rows (3 columns x 2 rows)
  - Braking/Entry, Mid-Corner, Exit shown in one row on wide screens
  - Selected Analysis Reference uses a dedicated 5-column grid, producing two rows for nine metrics
  - responsive fallbacks preserve readability on narrower windows
- Added distinct semantic heading colors for map/table/detail and braking/mid/exit/reference sections.
- Preserved all deterministic measurements, reference behavior, scoring, and coaching logic.

## Validation
- Python compile: PASS
- Performance Hub JavaScript parse: PASS
- Full regression: 963 passed, 383 subtests passed, 0 failures


---

## Archived source: `CHECKPOINT_V2.0.5.4_WIDE_CORNER_DETAIL_TABLE_SCROLL.md`

# V2.0.5.4 — Wide Corner Detail + Table Scroll Hotfix

Base: V2.0.5.3

Changes:
- Removed the 95ch width constraint from the selected-corner detailed analysis so the full Performance Hub width is used on wide windows.
- Wide layout now keeps six progress bars at 3 columns x 2 rows.
- Wide layout keeps Braking / Entry, Mid-Corner and Exit as three phase cards in one row.
- Selected Analysis Reference uses 3 columns, producing two rows for the current nine reference metrics.
- Narrow layouts remain responsive: phase cards collapse below 1250 px; progress bars reduce to 2 columns and then 1 column; reference metrics reduce to 2 and then 1 column.
- Added a dedicated always-visible horizontal scrollbar above the Every Corner table when the table overflows horizontally.
- Added synchronized scrolling between the visible top scrollbar and the table body, including resize remeasurement.

Validation:
- 966 tests passed
- 383 subtests passed
- Python compilation passed
- Performance Hub JavaScript syntax passed


---

## Archived source: `CHECKPOINT_V2.0.5.5_PERSISTENT_CORNER_TABLE_SCROLLBAR.md`

# V2.0.5.5 — Persistent Corner Table Scrollbar Hotfix

## Scope
- Replaced the browser-native proxy horizontal scrollbar, which could be hidden by Chromium/WebView overlay-scrollbar behavior, with an explicit always-visible horizontal range control below the Every Corner table.
- The control is synchronized bidirectionally with the table's horizontal scroll position.
- It remains visible in narrow Control Center windows; when no overflow exists it is visibly disabled rather than disappearing.
- Existing mouse/touch/trackpad scrolling on the table remains supported.
- No telemetry, scoring, diagnosis, reference, or coaching logic changed.


---

## Archived source: `CHECKPOINT_V2.0.5.6_USABLE_CORNER_TABLE_SCROLLBAR.md`

# V2.0.5.6 — Usable Corner Table Scrollbar Hotfix

## Fix
The V2.0.5.5 range-input control was visible in Qt WebEngine but was not reliably draggable. It has been replaced by a real overflow-x scrollbar proxy synchronized bidirectionally with the Every Corner table.

## Interaction
- draggable native horizontal scrollbar
- mouse-wheel vertical motion over the proxy maps to horizontal movement
- left/right step buttons for deterministic fallback interaction
- percentage indicator remains synchronized
- control disables only when the table fully fits

## Validation
- 969 tests passed
- 383 subtests passed
- Python compile passed


---

## Archived source: `CHECKPOINT_V2.0.5.7_IST_ASSISTS_CORNER_AUTHORITY.md`

# V2.0.5.7 — IST + Assist Icons + Corner Authority Review Hotfix

## Fixed
- Performance Hub absolute session/review timestamps render explicitly in IST (Asia/Kolkata).
- Stored-session reference option timestamps are formatted in IST.
- Session quick-glance assist column uses compact icon badges with tooltips instead of long text.
- Shared physical-corner authority now reads the structured local-data track map root (`user_data/tracks/maps`) with legacy read fallback.
- Existing stored sessions whose track snapshot contains map points but no corner rows are hydrated read-only from the current shared physical track model.
- Telemetry map and Corner performance map therefore recover selectable physical-corner markers for affected sessions without inventing corner positions.
- Selected Analysis Reference corner metrics recover once the shared physical corner boundaries are available; missing evidence still remains N/A.

## Authority / safety
No score, diagnosis, telemetry, reference trace, or coaching authority changed. No synthetic corner positions are generated.

## Validation
- 972 tests + 383 subtests passed.
- Python compilation passed.
- Performance Hub JavaScript syntax passed (`node --check`).


---

## Archived source: `CHECKPOINT_V2.0.5.8_GARAGE_RESUME_LAP_HISTORY_CONTINUITY.md`

# V2.0.5.8 — Garage Resume Lap History Continuity

## Fix
Performance Hub live-session upserts now preserve per-lap evidence already stored for the same session when F1 returns to the garage and the live performance accumulator restarts.

Previously, a later partial autosave could replace `coach_json` with only the post-garage laps while the authoritative game/session summary still reported the cumulative lap count. This produced a session row showing (for example) 8 completed laps while `SESSION LAP TIMES` exposed only laps 6–8.

## Preserved across same-session upserts
- `lap_telemetry`
- `lap_facts`
- `live_lap_intelligence`
- `lap_comparisons`
- coaching quality lap membership
- fullest persisted track geometry snapshot
- session start timestamp
- monotonic cumulative lap count / warnings / penalties

Incoming data still owns current aggregate/session fields; replay remains read-only for persistent history.

## Validation
- Added `tests/test_v2058_time_trial_garage_resume_history.py`
- Simulates five pre-garage laps followed by a resumed three-lap snapshot (laps 6–8) for the same logical session.
- Confirms all eight laps remain available in stored telemetry/facts/intelligence/comparisons and reference selection.
- Full suite: 973 tests + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.0.5.9_CORNER_TABLE_AUTOSAVE_ASSIST_ICONS.md`

# V2.0.5.9 — Corner Table Autosave + Assist Icons

## Fixes
- Prevents the Performance Hub autosave edge from being consumed before CORNER COACH finalizes the same completed lap. This avoids storing a lap time without its per-corner evidence when the coaching cadence skips the exact lap-boundary packet.
- The autosave retries on a following live packet once the corner accumulator contains the completed lap.
- Every Corner table now uses the same effective corner evidence sources as the performance map: recorded per-lap corner rows first, then selected-reference comparison evidence, then physical-map-only placeholders. This prevents a colored/clickable map from being paired with an empty table.
- Detailed Corner Analysis uses the same effective corner row source, so selected-reference metrics remain inspectable even when an older persisted lap lacks a recorded score row.
- Assist icons now have one visual rule: active/used = green, inactive/unknown = grey. Hover text still exposes the exact state (e.g. Medium TC, Manual + Suggested, Off).

## Evidence policy
- Selected-reference-only rows are labelled `SELECTED REF`; they do not invent a recorded technique score or confidence.
- Geometry-only corners are labelled `MAP ONLY` and remain N/A for unavailable measurements.

## Validation
- Full suite: 976 tests + 383 subtests passed.
- Python compilation: PASS.
- Performance Hub JavaScript syntax: PASS.


---

## Archived source: `CHECKPOINT_V2.0.6.0_REPLAY_LINKED_TELEMETRY_WORKSTATION.md`

# V2.0.6.0 — Replay-Linked Telemetry Workstation

Built on V2.0.5.10.

## Implemented
- New Replay / Session Analysis telemetry workstation.
- Selected replay lap vs selectable reference lap.
- Shared distance cursor across all charts.
- Driver/reference traces for speed, brake, throttle, steering, gear, ERS and delta.
- Extended replay-index channels: RPM, lateral G, longitudinal G, vertical G.
- Linked world-position map with cursor following the same distance.
- Current corner follows the shared cursor where corner evidence is available.
- Clicking any telemetry graph seeks the active replay to the nearest recorded packet.
- Clicking the map selects/zooms the corresponding distance and seeks replay.
- Corner buttons zoom all charts around that corner.
- Deterministic jump anchors for brake point, apex/min-speed point and throttle pickup from recorded replay telemetry.
- Previous/next coaching-event navigation.
- Replay load/play/pause/speed/seek controls in the workstation.
- Existing indexed/memory-mapped ReplayController architecture is reused; no parallel replay engine was introduced.
- Workstation analysis is read-only and does not mutate live Performance History.

## Replay index
Replay analysis index version increased to 2. Real ARERPL01 recordings with a v1 cache are rescanned once to populate the new channels. Synthetic/legacy test caches remain readable.

## Validation
- 980 tests + 383 subtests passed.
- Python compilation passed for modified modules.
- Session-workstation JavaScript syntax passed Node syntax validation.


---

## Archived source: `CHECKPOINT_V2.0.6.1_REPLAY_WORKSTATION_RUNTIME_CORNER_HOTFIX.md`

# V2.0.6.1 — Replay Workstation Runtime + Corner Authority Hotfix

## Scope
Hotfix on top of V2.0.6.0 Replay-Linked Telemetry Workstation.

## Fixes
- Added the missing `pathlib.Path` runtime import used by replay load/seek/status endpoints. This removes the `name 'Path' is not defined` error shown beside the workstation controls.
- Replay indexing now stores a readable `track_name` from the existing telemetry TRACKS authority alongside `track_id`.
- Installed reference-zone lookup now uses the structured `user_data/references/uploaded` authority instead of only the old project-relative path.
- Legacy replay recordings with no CORNER COACH validation trace now recover physical T1..Tn markers from the shared persisted track model when available.
- If no persisted model is available, the workstation derives the same physical-corner geometry directly from the replay's measured world-position lap trace, using the known circuit turn count. This is read-only and does not modify live Performance History.

## Validation
- 982 tests + 383 subtests passed.
- Modified Python modules compile successfully.
- Added regression coverage for the missing Path runtime dependency and legacy replay physical-corner fallback.


---

## Archived source: `CHECKPOINT_V2.0.6.2_REPLAY_WORKSTATION_PLAYBACK_ACTIVATION_HOTFIX.md`

# V2.0.6.2 — Replay Workstation Playback Activation Hotfix

## Fixes
- Browser Replay / Session Analysis controls now activate the real replay runtime/worker instead of only changing `ReplayController.paused` while the receiver remains in live UDP mode.
- The first PLAY/PAUSE click no longer activates replay and immediately toggles it back to paused.
- Replay status now reports the actual replay-mode gate, not merely whether a replay file is loaded.
- The workstation polls replay status at 250 ms and links the current replay packet back to the shared distance cursor, charts, map pointer and current-corner display.
- Existing indexed/memory-mapped replay and deterministic seek architecture is preserved.

## Root cause
The HTTP workstation had access to `ReplayController`, but the dashboard server did not have the `set_replay_mode()` callback that creates the replay worker and gates `RaceStateReceiver` to replay input. As a result the UI could show `PLAYING` while no worker consumed replay packets. In addition, the workstation did not animate its shared cursor from controller packet position.

## Validation
- 984 tests passed
- 383 subtests passed
- Python compilation passed
- Added regression coverage for browser activation semantics and packet-position-to-workstation-cursor synchronization.


---

## Archived source: `CHECKPOINT_V2.0.6.3_SELECTED_LAP_PLAYBACK_SYNC.md`

# V2.0.6.3 — Selected Lap Playback Sync

## Fix
Replay workstation LOAD REPLAY is now synchronized with the selected analysis lap.

Previously the Lap selector changed only the workstation comparison data. The replay transport continued from its current packet, so selecting L3 while replay was on L1 and pressing LOAD REPLAY/PLAY kept playing L1.

V2.0.6.3 sends the selected lap with LOAD REPLAY. The server resolves the indexed `start_packet` for that lap, seeks the existing indexed/memory-mapped ReplayController to that packet, and then starts playback.

## Behavior
- select L1/L2/L3/etc. in the workstation Lap selector
- LOAD COMPARISON updates analysis traces only
- LOAD REPLAY now positions the real replay runtime at the selected lap start and starts playback
- existing pause/play/speed/seek/event controls remain unchanged
- replay remains read-only with respect to live Performance History

## Validation
- 986 tests passed
- 383 subtests passed
- 0 failures
- Python compilation passed


---

## Archived source: `CHECKPOINT_V2.0.6.4_RADIO_RESPONSE_LATENCY_OPTIMIZATION.md`

# V2.0.6.4 — Radio Response Latency Optimization

## Problem
Driver PTT responses could take ~5 seconds or more after button release before engineer audio began.

## Root cause
The deterministic command/response path itself is fast. The dominant synchronous stage after PTT release was offline STT: `small.en` on CPU was configured with beam search (`beam_size=5`) plus VAD scanning for every already-PTT-bounded clip. Dynamic Piper synthesis then adds a smaller second-stage delay before audio starts.

## Changes
- Added fast PTT transcription mode while preserving the existing `small.en` model and int8 CPU inference.
- Fast PTT mode uses greedy decoding (`beam_size=1`).
- Disables redundant VAD filtering for a clip already bounded by the physical PTT press/release.
- Disables timestamp decoding because radio intent parsing only needs text.
- Keeps temperature 0, prompt/hotword vocabulary and existing hallucination normalization/rejection.
- Added stage timing diagnostics:
  - STT inference latency
  - PTT release -> transcript
  - transcript -> response queued
  - response queued -> audio start
  - PTT release -> audio start total

This makes remaining latency measurable on the user's actual Windows machine instead of guessing whether STT, command processing, LLM, queueing or Piper is responsible.

## Safety / architecture
- No changes to telemetry hot path.
- No changes to deterministic radio intent logic.
- No model downgrade; still `small.en`.
- LLM requests remain background/asynchronous and naturally may take longer than deterministic radio commands.
- TTS priority/preemption behavior unchanged.

## Validation
- `987 passed, 383 subtests passed`
- Python compile passed.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.0_FOUNDATION.md`

# V2.0.6.4 + UI 1.0 — Design System & Overlay Framework Foundation

Base: `RaceEngineer_V2.0.6.4_RADIO_RESPONSE_LATENCY_OPTIMIZATION_FULL(1).zip`

## Scope
UI-only foundation. No telemetry, coaching, scoring, reference, strategy, replay, or performance-history authority changes.

## Implemented
- Added `src/ui_theme.py` as the shared native/web design-token authority.
- Standardized background/surface/elevated surface, borders, text, semantic green/amber/red/cyan/grey, radii, spacing, buttons, combos, tabs, tables, scrollbars, tooltips and status-chip styling.
- Applied the shared Qt theme to the normal Control Center application shell.
- Aligned Performance Hub root CSS variables to the same semantic color system.
- Added `src/ui_overlay_state.py` for UI-only local presentation state.
- Added common OverlayPanel state for lock, opacity, zoom and geometry.
- Added local persistence to `settings/ui_overlay_state.json` without touching session/performance persistence.
- Added common keyboard behavior: Ctrl+Plus zoom in, Ctrl+Minus zoom out, Ctrl+0 reset zoom, Ctrl+L lock/unlock.
- Locked overlays no longer drag accidentally.
- Overlay state restores on show and geometry is clamped to the active monitor.

## Validation
- Python compile validation passed for changed UI modules.
- Focused V2.0.6.4 radio-latency / Control Center / Performance Hub regression set: 14 passed.
- Full regression suite: 987 passed + 383 subtests passed.

## Next UI roadmap work
- UI 1.1: progressive pre-corner + live feedback presentation.
- UI 1.2: Control Center grouped-card rebuild + Overlay Manager.
- UI 1.3+: Performance Hub workspace, linked telemetry workstation, race overlay refresh, F1 Dash/responsive/accessibility polish.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.1_PROGRESSIVE_PRE_CORNER_OVERLAY.md`

# V2.0.6.4 + UI 1.1 — Progressive Pre-Corner Overlay

## Scope
Implements UI-R3 only on top of the V2.0.6.4 + UI 1.2.2 base. No deterministic telemetry, coaching, scoring, strategy, replay, persistence, or radio timing logic was changed.

## Changes
- Added a standalone `Pre-Corner Coach` overlay to the Control Center Overlay Manager.
- Added a presentation-only `corner_coach_pre_visual` snapshot payload derived from the existing compiled CoachingZone/reference authority.
- Progressive states: UPCOMING/FAR, APPROACHING, BRAKING, TURN-IN, APEX, EXIT.
- Far approach shows corner identity and distance to the authoritative coaching zone only.
- Coaching range reveals one primary instruction plus an optional secondary reference target.
- Braking/turn-in instruction is visually locked to prevent flicker/reflow.
- Added a progressive approach bar with phase markers.
- Trusted reference delta and presentation confidence are shown only when data exists.
- The new overlay remains closed at startup, preserving the V2 no-overlays-open-by-default policy.
- Position locking remains owned by the overlay chrome itself, not Control Center.

## Authority / preservation
- PRE voice scheduling is unchanged.
- Existing `_pre_text*`, `_pre_target_m`, compiled CoachingZone geometry and reference values remain authoritative.
- UI-R3 payload is read-only presentation data and cannot emit speech or modify coach timing.
- N/A/missing evidence is not invented.

## Validation
- `python -m py_compile src/corner_coach.py src/overlay/data.py src/overlay/window.py` — pass.
- Focused UI/Corner Coach/radio-latency regressions — 36 passed.
- Full repository suite — 987 passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.2.1_OVERLAY_MANAGER_REFERENCE_STYLE_HOTFIX.md`

# CHECKPOINT — V2.0.6.4 + UI 1.2.1 Overlay Manager Reference-Style Hotfix

Base: `RaceEngineer_V2.0.6.4_UI_1.2_CONTROL_CENTER_REBUILD_FULL.zip`

## Scope
UI-only correction based on the Control Center screenshots and overlay-manager reference image.

## Changes
- Fixed clipped/blank Control Center action buttons:
  - `OPEN PERFORMANCE COACH`
  - `IMPORT`
  - `EXPORT`
- Rebuilt Control Center overlay management into grouped card sections:
  - COACHING
  - RACE
  - TOOLS
- Each overlay card now contains:
  - overlay visibility switch
  - live/ready state
  - transparency percentage
  - transparency slider
- Added live `N on` count and `ALL OFF` action.
- Removed position-lock controls from Control Center Overlay Manager.
- Added overlay-owned position lock control to frameless driving overlays.
- Overlay position lock remains persistent locally and retains `Ctrl+L` shortcut.
- No telemetry, coaching, scoring, strategy, replay, reference-authority, radio-latency, or Performance Hub persistence logic changed.

## Validation
- Python source compilation passed.
- Focused Control Center / launcher / radio-latency regressions passed.
- Full regression suite: `987 passed, 383 subtests passed`.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.2.2_STARTUP_COLOR_TYPE_HOTFIX.md`

# V2.0.6.4 + UI 1.2.2 — Startup Color Type Hotfix

## Scope
UI-only startup hotfix on top of UI 1.2.1.

## Fixed
- Fixed Control Center startup crash caused by passing shared UI token hex strings (for example `TOKENS.cyan`) into `_rgba()`, which previously assumed every input was a `QColor`.
- `_rgba()` now safely accepts both shared token strings and `QColor` values.
- Fixed Overlay Manager live-status stylesheet conversion so `QColor` and string-token colors are rendered correctly.

## Preservation
No telemetry, coaching, scoring, strategy, radio, replay, reference authority, persistence, or Performance Hub logic changed.

## Validation
- `python -m py_compile src/overlay/window.py` — PASS
- Full pytest suite — 987 passed + 383 subtests


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.2.3_R0_R3_COMPLETION.md`

# V2.0.6.4 + UI 1.2.3 — R0–R3 Completion / Replay Path Hotfix

Base: V2.0.6.4 radio response latency optimization + UI 1.2.2 + UI-R3 progressive pre-corner overlay.

## UI-only scope preserved
No telemetry authority, coaching/scoring/reference logic, race strategy, replay semantics, performance-analysis math, or persistent live-history authority was changed.

## Fixes / completion
- Control Center Replay Recording selector now reads the authoritative `user_data/recordings` directory through `src.app_paths.RECORDINGS`, matching recorder/replay/session-library storage.
- UI-R0 adds shared control-class definitions (primary, secondary, destructive, icon, segmented, toggle) and internal compact/comfortable density presets.
- UI-R1 adds collapse/expand controls to low-frequency Reference, Hardware and Audio cards.
- Hardware WAITING / CONNECTED / DISCONNECTED states now use the same chip visual language as runtime status states.
- UI-R2 adds one shared hover overlay chrome to all frameless driving overlays:
  - lock/unlock position
  - zoom out / in
  - reset zoom
  - opacity cycle
  - compact mode
  - minimize
  - close/hide
- Overlay chrome auto-hides after 1.8 s and reappears on pointer entry/movement.
- Existing keyboard controls remain: Ctrl+L, Ctrl++, Ctrl+-, Ctrl+0.
- Geometry, opacity, scale, lock and compact presentation state remain local in `settings/ui_overlay_state.json`.
- UI-R3 EXIT phase now visually fades the PRE instruction and presents `HANDOFF → POST CORNER FEEDBACK`; this does not change PRE/POST voice timing or diagnosis authority.

## Validation
- `python -m py_compile src/overlay/window.py src/ui_theme.py`: PASS
- `python -m pytest -q`: **992 passed, 383 subtests passed**
- Added `tests/test_ui_r0_r3_completion.py` with 5 focused regression checks.

## Important runtime check
On Windows, verify that the Control Center Replay Recording dropdown now lists `.areplay` files from `user_data\\recordings`, and hover any overlay to confirm the common chrome appears and auto-hides.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.2.4_R4_LIVE_CORNER_FEEDBACK.md`

# V2.0.6.4 + UI 1.2.4 — UI-R4 Live Corner Feedback / Accuracy UI

## Base
Built directly on `V2.0.6.4 + UI 1.2.3 R0-R3 Completion`.

## Scope
UI/UX only. No telemetry authority, corner detection, scoring math, diagnosis, coaching authority, speech timing, replay semantics, reference logic, persistence semantics, or strategy logic was changed.

## UI-R4 changes
- Rebuilt `LiveCornerFeedbackOverlayWindow` as a glanceable post-corner accuracy surface.
- Default Corner Performance view shows four compact deterministic dimension-score bars:
  - Brake Point
  - Apex Speed
  - Throttle Pickup
  - Exit Speed
- Existing specialized views now show only their relevant 2–3 deterministic dimensions.
- Accuracy tiles consume the existing `live_corner_result.dimension_scores`; the UI does not normalize or derive new scores.
- N/A remains N/A and is never rendered as a perfect/centered score.
- Corner ID, overall deterministic score/grade, and measured time loss/gain are prominent at the top.
- Exactly one existing `action_text` remains the actionable recommendation.
- Added expandable `DETAILS` evidence view for measured deltas without cluttering the primary driving view.
- Preserved existing selectable views and legacy source labels for compatibility.
- Overlay remains user-armed and does not create speech or modify POST/PRE scheduling.

## Validation
- `python -m compileall -q src`: passed.
- Focused UI-R4 + V2.0.1/V2.0.2 corner-feedback tests: passed.
- Full regression: **998 passed + 383 subtests**, 0 failures.

## User validation
Enable `Live Corner Feedback` from the Overlay Manager, then drive/replay through several eligible corners. Check:
1. Corner Performance gives a readable four-metric glance in under a second.
2. Grade and measured loss/gain are easy to see immediately.
3. Only one recommendation is shown.
4. Specialized selector views show relevant metrics without dense text.
5. DETAILS expands raw evidence and N/A values remain visibly unavailable.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.2.5_R4_LAYOUT_HOTFIX.md`

# V2.0.6.4 + UI 1.2.5 — R4 Live Corner Feedback Layout Hotfix

## Base
- RaceEngineer V2.0.6.4
- UI 1.2.4 R4 Live Corner Feedback

## Fixes
1. Moved the Live Corner Feedback `DETAILS` control out of the top-right header area and into the overlay footer so the shared hover chrome (lock/zoom/reset/opacity/compact/minimize/close) cannot cover it.
2. Removed redundant overlay-specific minimize/close buttons from Live Corner Feedback; common overlay chrome remains the single interaction model.
3. Reserved header space for the shared overlay chrome by constraining the metric selector width.
4. Made Live Corner Feedback height content-driven. After persisted overlay state is restored, the overlay normalizes its height to the compact R4 content height while preserving saved position, width, opacity, lock and zoom.
5. Reduced the normal R4 base height from 286 px to 264 px; expanded evidence remains available through DETAILS.

## Preservation
No telemetry authority, scoring, diagnosis, coaching timing, strategy, replay semantics, reference logic, radio path, or persistence authority changed.

## Validation
- Full pytest suite: 1000 passed
- Subtests: 383 passed
- Added tests/test_ui_r4_1_live_corner_layout_hotfix.py


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.2.7_GLOBAL_TRUE_ZOOM_OVERLAY_CONTROLS.md`

# V2.0.6.4 + UI 1.2.7 — Global True Zoom / Overlay Controls

## Base
RaceEngineer V2.0.6.4 + UI 1.2.6 R4 True Zoom/Text Wrap Hotfix.

## Scope
UI-only. No telemetry, coaching, scoring, reference, race strategy, replay semantics, persistence semantics, or performance-analysis authority changes.

## Changes
- Reworked `OverlayPanel.set_overlay_scale()` so shared zoom scales actual overlay presentation instead of only changing outer window geometry.
- Added logical fixed-size support for overlays that previously used direct `QWidget.setFixedSize()` and therefore blocked zoom.
- Shared true-zoom now scales normal child-widget fonts, fixed control dimensions, layout margins, and spacing.
- Propagates `overlayVisualScale` to custom-painted child widgets; common overlay painter widgets now scale their fixed font sizes with the overlay.
- Progressive Pre-Corner overlay now renders through a logical painter transform and uses the shared overlay chrome exclusively.
- F1 Dash now participates in logical true zoom; its canvas scales with the window and its page buttons scale position, dimensions, padding, radius, and font size.
- F1 Dash visible lock/zoom/reset/opacity/compact/minimize/close controls are owned by shared overlay chrome. Legacy private header controls remain hidden for compatibility only.
- Preserved shared lock, opacity, compact, minimize, close, click-through compatibility, saved scale, and geometry behavior.

## Validation
- Python compile: PASS (`src/overlay/window.py`, `src/overlay/widgets.py`).
- New global zoom regression tests: 5 passed.
- Full repository suite: **1007 passed + 383 subtests**.

## User validation focus
1. Pre-Corner Coach: zoom +/−/1:1 must scale text, progress bar, spacing, and whole card.
2. F1 Dash: zoom +/−/1:1 must scale the complete native 800×480 design and page buttons together.
3. Other overlays: verify shared lock, zoom, reset, opacity, compact, minimize, close/hide.
4. Verify click-through still prevents interaction only while click-through is enabled.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.2.9_OVERLAY_CHROME_CONFLICT_HOTFIX.md`

# V2.0.6.4 + UI 1.2.9 — Overlay Chrome Conflict Hotfix

Base: UI 1.2.8 Global Zoom Constraint Audit.

## UI-only changes
- Driver Inputs and Reference Inputs T/B/ERS trace controls moved into a dedicated row below the overlay title so shared hover chrome cannot cover them.
- Removed all legacy per-overlay minimize/close controls from visible overlay layouts. Unified UI-R2 hover chrome is now the only window-control layer.
- Removed the hidden F1 Dash private minimize/close bar objects; shared chrome remains authoritative.
- Live Corner Feedback waiting state now mirrors the progressive Pre-Corner presentation with a clear POST-CORNER FEEDBACK state, WAITING FOR COMPLETED CORNER headline, and concise explanation.
- DI/RI logical heights increased to account for the dedicated trace-control row.
- No changes to telemetry authority, coaching/scoring logic, reference logic, replay behavior, strategy, persistence semantics, or performance math.

## Validation
- 1010 tests passed
- 383 subtests passed


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.2_CONTROL_CENTER_REBUILD.md`

# V2.0.6.4 + UI 1.2 — Control Center Rebuild / Overlay Manager

## Base
- `RaceEngineer_V2.0.6.4_UI_1.0_FOUNDATION_FULL`
- Functional baseline remains V2.0.6.4 radio-response-latency optimization.
- UI-only milestone implementing roadmap `UI-R1 — Control Center Rebuild`.

## Implemented
- Rebuilt the Control Center CONTROL tab as a responsive application workspace instead of a long form.
- Added grouped cards for:
  - Session / Runtime
  - Race Engineer
  - Performance Coach
  - Reference
  - Hardware
  - Audio
  - Overlay Manager
- Responsive card layout:
  - 3 columns on very wide windows
  - 2 columns on normal desktop widths
  - 1 stacked column on narrow windows
- Converted runtime state presentation to compact status-chip controls.
- Improved reference selector grouping and import/export presentation.
- Kept replay selection inside Session / Runtime.
- Preserved CORNER COACH control ownership inside its own overlay.
- Replaced the old launcher button matrix with a functional Overlay Manager.

## Overlay Manager
Each overlay entry now provides:
- full overlay name
- live READY/LIVE/N/A state
- SHOW/HIDE toggle
- LOCKED/UNLOCKED control
- opacity slider
- OPEN/focus control

The manager is connected to the actual overlay windows through `OverlaySuite`, so visibility, lock state and opacity reflect the real window state rather than decorative UI state.

## Visual consistency
- Control Center uses the same UI token system introduced in UI 1.0.
- Added shared card, divider, Overlay Manager row and slider styling.
- Control page background now uses the common application background token family, visually aligning it more closely with Performance Hub.
- Removed the cramped/truncated launcher-button presentation.

## Preservation
No changes were made to:
- telemetry authority
- coaching diagnosis/math
- scoring
- reference authority/selection semantics
- race strategy decisions
- replay data authority
- Performance Hub persistence
- radio/STT/TTS execution paths

Existing callbacks are reused; UI-R1 only changes organization/presentation plus overlay-window presentation controls.

## Validation
- Python compilation: PASS (`src/overlay/window.py`, `src/ui_theme.py`)
- Full regression suite: **987 passed + 383 subtests passed**
- Focused Control Center / Performance Hub / latency suite: **29 passed**
- Direct off-screen Qt render could not be executed in the packaging environment because `PySide6` is not installed there; repository Qt/source regression coverage remains green.

## Next UI roadmap step
The next planned milestone remains driver-facing live UI:
- UI-R3 Progressive Pre-Corner Overlay
- UI-R4 Live Corner Feedback / Accuracy UI
- UI-R8 Race / Strategy Overlay Visual Refresh


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.3.1_PERFORMANCE_HUB_NAVIGATION_ROLLBACK.md`

# V2.0.6.4 + UI 1.3.1 — Performance Hub Navigation Rollback

## Reason
UI 1.3 introduced a top-level Track/Session/Lap/Corner/Telemetry workspace switcher. In the real multi-track, multi-session history this forced an ambiguous default workspace before the user had explicitly selected the track and stored session, and it caused poor wide-screen layout behavior.

## Change
- Restored the proven Performance Hub hierarchy from UI 1.2.9:
  1. profile/filter
  2. track selection
  3. explicit session history selection
  4. selected-session review
  5. existing Overview / Telemetry / Corners tabs inside that selected session
- Removed the UI 1.3 top-level workspace navigation and sticky session-context strip.
- Removed the UI 1.3 wide-screen corner split layout that caused panels to collapse into narrow columns.
- Preserved the existing every-corner performance map/table, detailed corner analysis, linked telemetry, persistent horizontal scrollbar, selected-reference analysis, quick-glance lap flow, and all deterministic data behavior.
- No telemetry, scoring, reference, persistence, replay, coaching, or strategy logic changed.

## Validation
- Focused Performance Hub/corner review regressions pass.
- Full suite: 1014 tests passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.3_R5_R7_PERFORMANCE_WORKSPACE.md`

# Checkpoint — V2.0.6.4 + UI 1.3 — Performance Workspace / Every-Corner Review

## Base
- RaceEngineer V2.0.6.4
- UI 1.2.9 Overlay Chrome Conflict Hotfix

## Scope
UI-only implementation of UI-R5 and UI-R7 from the Race Engineer UI Refinement Roadmap.
No telemetry authority, coaching, scoring, reference authority, race strategy, replay persistence, or performance-analysis math was changed.

## UI-R5 — Performance Hub Information Architecture
- Added top-level workspace navigation:
  - Track Overview
  - Session Review
  - Lap Review
  - Corner Review
  - Telemetry
- Added persistent/sticky session context strip showing:
  - track
  - session type
  - game driver
  - selected lap/session view
  - selected analysis reference
  - lap time
  - gap to selected reference
- Track/history workspace is separated from an opened session review.
- Session, lap, corner, and telemetry views now behave as one linked workspace instead of unrelated page sections.
- Lap Review has a dedicated view while preserving the existing authoritative lap selector and quick-glance data.
- Responsive fallbacks remove sticky positioning and stack the context/workspaces on narrower widths.

## UI-R7 — Every-Corner Review Refinement
- Corner table retains sticky header and reliable horizontal scroll.
- Added persistent column chooser for lower-priority columns:
  - Grade
  - Racing-line deviation
  - Issue
  - Phase
  - Confidence
  - Evidence
- Added sortable columns for:
  - Corner number
  - Score
  - Time loss/gain
  - Speed deficit
  - Braking delta
  - Throttle delta
- Missing/N/A values sort after trusted numeric values.
- Heat tint remains on metric/data cells only.
- Selected corner retains one clear row highlight.
- Wide layouts now use a split engineering workspace:
  - map + table on the main side
  - selected corner detail/summary/AI explanation in a sticky side panel
- Narrow layouts stack the selected-corner detail below the map/table.
- Selected Analysis Reference metrics remain in their own visual group.

## Compatibility / Preservation
- Existing quick-glance behavior preserved.
- Existing reference comparison semantics preserved.
- Existing horizontal table scroll control preserved.
- Existing track/session delete behavior preserved.
- Existing Performance Hub APIs unchanged.
- Existing local AI remains explanation-only.

## Validation
- Python source compilation passed.
- JavaScript syntax checked with Node.js.
- Full repository regression suite:
  - 1014 tests passed
  - 383 subtests passed


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.4.1_R6_TRACK_MAP_UTILIZATION_HOTFIX.md`

# V2.0.6.4 UI 1.4.1 — R6 Track Map Utilization Hotfix

## Base
RaceEngineer V2.0.6.4 UI 1.4 R6 Telemetry Workstation.

## Scope
UI-only telemetry workstation refinement. No telemetry authority, replay behavior, scoring, coaching, reference, strategy, persistence semantics, or analysis math changes.

## Changes
- Expanded the telemetry workstation map panel to use the available vertical space on wide screens.
- Increased the left map column minimum width slightly for better circuit readability.
- Replaced the fixed wide 700x350 SVG coordinate canvas with a track-aspect-derived viewBox.
- The track geometry now scales tightly to its panel instead of occupying a small portion of a wide SVG canvas.
- Responsive map sizing retained for narrower windows and mobile-width layouts.
- Shared telemetry cursor, corner click/zoom, and map interaction behavior remain unchanged.

## Validation
- Added regression coverage for map-panel expansion and track-aspect-derived map rendering.
- Full suite: 1020 tests passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.4.2_REVIEW_SELECTOR_TABBAR_HOTFIX.md`

# V2.0.6.4 UI 1.4.2 — Review Selector Tab-Bar Hotfix

## Base
RaceEngineer V2.0.6.4 UI 1.4.1 R6 Track Map Utilization Hotfix.

## Change
- Moved the frequently used Performance Hub review selectors out of the session header.
- `VIEW` / lap selector now sits on the same responsive row as `OVERVIEW`, `TELEMETRY`, and `CORNERS`.
- `ANALYSIS REFERENCE · VISUAL REFERENCE` selector sits immediately beside the lap selector on that same row.
- `DELETE SESSION` and `CLOSE` remain in the session header.
- Existing element IDs and event handlers are unchanged, so selection/reference semantics are unchanged.
- Responsive behavior stacks the selector controls below the tabs on narrower windows.

## Preservation
No change to telemetry authority, score math, stored-session hierarchy, reference authority, replay behavior, coaching logic, persistence semantics, or performance-analysis math.

## Validation
- Python source compile: PASS
- Focused Performance Hub tests: PASS
- Full suite: 1021 passed + 383 subtests


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.4_R6_TELEMETRY_WORKSTATION.md`

# Race Engineer V2.0.6.4 + UI 1.4 — UI-R6 Telemetry Workstation

## Base
RaceEngineer_V2.0.6.4_UI_1.3.1_PERFORMANCE_HUB_NAVIGATION_ROLLBACK_FULL.zip

## Scope
UI-only implementation of UI-R6. The restored Profile -> Track -> Session -> Lap hierarchy is preserved. No telemetry authority, scoring, reference semantics, coaching, replay persistence, strategy, or analysis math changed.

## Implemented
- Rebuilt the existing Performance Hub TELEMETRY tab as a linked multi-channel workstation.
- Core channels are data-gated: Speed, Brake, Throttle, Steering, Gear, ERS, Delta.
- Advanced channels appear automatically only when persisted data exists: RPM, lateral/longitudinal acceleration, tyre temperatures/pressures, brake temperatures, plus future trusted stored channels.
- Multiple visible channel graphs share one aligned distance range.
- Shared hover cursor synchronizes all visible charts and the track-map cursor.
- Driver/reference traces remain overlaid with explicit selected-lap/reference legend labels.
- Physical corner start guides and apex labels are drawn on linked charts.
- Clicking a corner on the map or corner strip zooms every chart to that physical corner.
- Dragging on any graph selects a shared distance range for all charts.
- FULL LAP resets the shared range.
- Channel visibility is user-selectable without inventing unavailable telemetry.
- Graph order can be changed with per-chart up/down controls and persists locally.
- Compact/normal/expanded graph density persists locally.
- Responsive 2-column chart grid on wide displays and stacked layout on narrower displays.

## Preservation
- Existing track/session selection flow unchanged.
- Existing lap/reference selectors unchanged.
- N/A/missing telemetry remains missing and is not synthesized.
- Existing deterministic score and corner authority unchanged.

## Validation
- JavaScript syntax check: PASS.
- Repository regression suite: 1019 passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.5.1_R7_LAYOUT_REBALANCE.md`

# V2.0.6.4 UI 1.5.1 — R7 Layout Rebalance

Base: UI 1.5 R7 Every-Corner Review Refinement.

Changes:
- Rebalanced CORNERS workspace at normal desktop widths to avoid cramped three-column review.
- Selected-corner detail now stacks full-width below map/table until very-wide (>=1900px) layouts.
- Very-wide displays retain split selected-corner detail behavior.
- Map/table workspace gives more width to the table.
- Performance map panel now stretches to use its card height.
- Performance map SVG now derives height/aspect from stored circuit geometry instead of fixed 700x350 rendering.
- No scoring, telemetry, reference, replay, persistence or analysis-math changes.

Validation:
- 1025 tests passed
- 383 subtests passed


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.5.2_LAP_ASSIST_DISPLAY_CONSISTENCY.md`

# V2.0.6.4 UI 1.5.2 — Lap Assist Display Consistency

## Scope
UI/data-presentation hotfix only. No scoring, telemetry, reference, replay, coaching, or persistence semantics changed.

## Fix
- Session quick-glance lap rows now include the raw per-lap `assists` dictionary.
- The lap table therefore uses the same shared `assistIcons()` rendering/state semantics as the Session Overview.
- TC / ABS / gearbox / custom setup / equal-performance indicators now show the same active/partial/off styling in both locations when the underlying assist state is the same.

## Root cause
`_session_quick_glance()` exported only `assist_labels`, while the lap table renderer reads `row.assists`. Missing `assists` caused all lap-row assist icons to fall back to the muted/N/A state.

## Validation
- Added regression coverage for preserving raw assist state in quick-glance rows.
- Full suite: 1026 passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.5_R7_EVERY_CORNER_REVIEW_REFINEMENT.md`

# V2.0.6.4 UI 1.5 — UI-R7 Every-Corner Review Refinement

Base: `RaceEngineer_V2.0.6.4_UI_1.4.2_REVIEW_SELECTOR_TABBAR_HOTFIX_FULL.zip`

## Scope
UI/UX only. No telemetry authority, scoring, reference logic, replay behavior, persistence semantics, coaching logic, strategy logic, or performance-analysis math changed.

## Implemented
- Sticky corner-table header.
- Existing persistent horizontal scrollbar retained and validated.
- Persistent low-priority column chooser for Grade, Racing-line deviation, Issue, Phase, Confidence, and Evidence.
- Sortable columns for Corner, Score, Time loss/gain, Speed deficit, Braking delta, and Throttle delta.
- Sort state persists locally.
- Heat tint is applied only to metric/data cells, not full table rows.
- Selected corner has one explicit cyan row highlight.
- Wide-screen layout uses a split review: map/table browse area + selected-corner detail side panel.
- Narrow layouts stack the selected-corner detail below the browse area.
- Selected Analysis Reference remains in its own visually separated comparison group.
- Existing map/table click behavior and corner-analysis authority preserved.

## Validation
- Python compile successful.
- Generated Performance Hub JavaScript syntax check successful.
- Full repository suite: 1025 passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.6.0_R8_RACE_STRATEGY_OVERLAY_VISUAL_REFRESH.md`

# CHECKPOINT — V2.0.6.4 UI 1.6.0 R8 Race / Strategy Overlay Visual Refresh

## Scope
Visual refresh only. No strategy, telemetry, scoring, replay, coaching, persistence, or race-context decision logic changed.

## Updated overlays
- Radio Transcript
- Session Summary
- ERS
- Tyre Status
- Fuel
- Weather / Forecast
- Standings / Relatives
- Delta

## What changed
- Added a richer shared `DataOverlayWindow` presentation layer:
  - concise subtitle support
  - optional status/header chips
  - reusable soft cards
  - consistent footer/status strip
- Modernized visual hierarchy across the target overlays:
  - largest / most important value promoted
  - supporting values grouped below or in compact secondary rows
  - soft card surfaces instead of dense nested boxes
  - clearer at-a-glance state color emphasis
- Preserved the existing shared overlay chrome / controls behavior from earlier UI work.

## Notes
- This pass refreshes the currently existing standalone race/strategy overlays.
- Dedicated standalone penalties and standalone brake-status windows were not introduced in this checkpoint; penalty/brake information remains in the existing surfaces already present in this branch.

## Validation performed
- `python -m py_compile src/overlay/window.py`
- `PYTHONPATH=. pytest -q tests/test_ui_r2_global_true_zoom.py tests/test_ui_r4_overlay_chrome_conflict_hotfix.py tests/test_v09141_radio_transcript_overlay.py -k 'source or zoom or chrome or launcher or incremental'`

## Result
- 9 passed, 4 deselected


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.6.1_R8_VISUAL_CORRECTION_COMPLETION.md`

# CHECKPOINT — V2.0.6.4 UI 1.6.1 R8 Visual Correction + Completion

## Base
V2.0.6.4 UI 1.6.0 R8 Race / Strategy Overlay Visual Refresh.

## Scope
UI-only. No telemetry authority, strategy logic, scoring, coaching, replay behavior, reference logic, persistence semantics, or performance-analysis math changed.

## Corrections
- R8 data overlays now draw a stable near-opaque dark surface; the existing user opacity control still applies to the whole window.
- ERS overlay height/layout corrected so the primary percentage and energy values do not clip.
- Session Summary waiting state now collapses to a compact card and expands to the full summary view only when a real session summary exists.
- Radio Transcript row header changed to Qt-compatible role / timestamp markup so `ENGINEER` and timestamps no longer run together.
- Weather overlay given more vertical breathing room for the three short-forecast cards.

## R8 completion
Added two standalone overlays using existing snapshot telemetry only:
- Penalties
  - current penalty seconds
  - serve-penalty state
  - race-control footer state
- Brake Status
  - FL / FR / RL / RR brake temperatures
  - per-wheel brake damage
  - hottest-brake / damage summary

Both are routed through the existing Control Center Overlay Manager and inherit UI-R2 lock, zoom, opacity, compact, minimize and close behavior.

## Preserved
Fuel, Relatives and Delta layouts from UI 1.6.0 were intentionally preserved except for the common stable-dark background behavior.

## Validation
- `python -m py_compile src/overlay/window.py`
- focused R8 / overlay routing suite: 21 passed
- full repository regression: 1026 passed + 383 subtests


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.6.2_R8_BRAKE_WARNINGS_WEATHER_HOTFIX.md`

# CHECKPOINT — V2.0.6.4 UI 1.6.2 R8 Brake / Warnings / Weather Hotfix

## Scope
UI-only R8 follow-up. No strategy, coaching, scoring, replay, reference authority, or telemetry decision logic changed.

## Fixes
- Brake Status
  - temperature value now uses progressive presentation bands:
    - cool: cyan
    - working: green
    - hot: amber
    - critical: red
  - damage color behavior unchanged.
- Penalties / Warnings
  - renamed standalone overlay from PENALTIES to PENALTIES / WARNINGS.
  - now shows penalty seconds, total warnings, track-limit/corner-cutting warnings, and serve-penalty state.
  - uses existing LapState values only.
- Weather
  - fixed R8 regression where `weather_now` (a string) was incorrectly treated as a forecast-row object.
  - current condition now uses the authoritative live Session packet `weather` value.
  - current track/air temperatures are available even when EA supplies no zero-minute forecast row by prepending a UI-only NOW row from live Session packet values.
  - forecast cards still use the authoritative game forecast rows.

## Validation
- Focused overlay/strategy/shared-chrome tests: 15 passed.
- Full suite: 1026 passed + 383 subtests.
- Python compile check: src/overlay/window.py and src/overlay/data.py passed.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.7.0_R9_F1_DASH_SECONDARY_DISPLAY_POLISH.md`

# CHECKPOINT — V2.0.6.4 UI 1.7.0 R9 F1 Dash & Secondary Display Polish

## Scope
UI/UX-only polish for the native F1 Dash and LAN/browser secondary display. No telemetry, map authority, strategy, coaching, replay, scoring, or persistence logic changed.

## Native F1 Dash
- Preserved logical 800×480 reference canvas and shared true-zoom behavior.
- Refined page navigation into a consistent segmented-tab treatment.
- Normalized page header hierarchy and typography.
- Added subtle header divider/surface hierarchy.
- Replaced the plain disconnected screen with a compact F1 Dash waiting card and LAN address context.

## LAN / Browser Dash
- Matched the native segmented page-tab treatment.
- Normalized back/navigation affordance.
- Reduced heavy borders and strengthened subtle surface separation.
- Improved responsive spacing for smaller/tablet aspect ratios.
- Reworked offline/waiting state into a clear F1 telemetry reconnect message.
- Kept the existing SSE event stream and render/update functions unchanged.

## Acceptance / Validation
Focused F1 Dash suite:
- 43 tests passed

Full suite:
- 1026 tests passed
- 383 subtests passed

No telemetry refresh-rate or map-smoothness execution path was modified.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.7.1_R9_LAN_NATIVE_PARITY_HOTFIX.md`

# CHECKPOINT — V2.0.6.4 UI 1.7.1 R9 LAN / Native Parity Hotfix

## Scope
Presentation-only correction for the browser/LAN F1 Dash shell. Native F1 Dash logic, telemetry cadence, map authority, replay behavior, and page logic are unchanged.

## Fixes
- Hide the RPM-light strip on non-DASH browser/LAN pages.
- Reduce the browser-only Back-to-Hub affordance to a compact arrow so it no longer dominates the 800x480 shell.
- Move the page selector to a compact top-right header row on info pages.
- Match native page hierarchy more closely:
  - small `F1 DASH` eyebrow
  - smaller page title
  - tighter subtitle/divider spacing
- Rebalance MAP content area to use the 800x480 stage cleanly.
- Preserve existing `/performance` back routing.

## Validation
- Focused F1 Dash/LAN tests: 44 passed.
- Full suite: 1027 passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.8.0_R10_R13_FINAL_UI_STABILIZATION.md`

# CHECKPOINT — V2.0.6.4 + UI 1.8.0 R10–R13 Final UI Stabilization

Base: V2.0.6.4 + UI 1.7.1 R9 LAN/Native Parity Hotfix.

## Scope
UI/UX stabilization only. No telemetry authority, coaching logic, scoring, reference logic, race-strategy decisions, replay semantics, persistence semantics, or analysis math changed.

## UI-R10 — Animation, Feedback & Micro-interactions
- Added 160 ms web hover/selection/card transitions.
- Added smooth low-rate progress/fill transitions for review/dashboard presentation.
- Preserved the existing progressive Pre-Corner EXIT fade/handoff.
- Added shimmer-style loading feedback for Performance Hub review reloads.
- Added non-blocking toast UI for safe success/error notifications (destructive confirmations remain blocking by design).
- Added `prefers-reduced-motion` handling.
- No large motion added to active-driving overlays.

## UI-R11 — Responsive Layout Matrix
- Control Center card breakpoints rebalanced around ~800 / ~1024 / ~1280 / wide desktop widths.
- Overlay Manager reduces columns before any font reduction.
- Performance Hub now has explicit 1280, 1024, and 820 px layout rules.
- Wide layouts retain columns/split views; medium widths collapse columns; narrow widths stack panels.
- Corner/lap tables preserve horizontal scrolling instead of shrinking telemetry text.
- Telemetry workstation becomes a single-column graph workspace on narrow widths.
- Existing 800×480 F1 Dash reference geometry remains preserved.

## UI-R12 — Accessibility & Input Consistency
- Added keyboard-visible focus rings for Qt buttons/combos/table cells.
- Added browser `:focus-visible` treatment for buttons, selects, links, summaries and focusable controls.
- Shared overlay chrome hit targets increased to at least 28×28 px.
- Shared overlay chrome remains fully tooltip-labelled.
- Status presentation continues to pair color with text/state labels.
- Qt6/browser scaling paths remain DPI-aware; no forced telemetry-font shrink added.

## UI-R13 — Performance & Rendering Guardrails
- LAN dashboard SSE rendering is now requestAnimationFrame-coalesced.
- Only the newest pending dashboard snapshot is painted each frame; intermediate visual frames are dropped under load rather than queued.
- When repeated coalescing indicates rendering pressure, cosmetic transitions are temporarily disabled.
- Performance Hub linked chart rendering is presentation-decimated to a bounded point count while underlying stored telemetry remains untouched.
- Existing high-rate telemetry / low-rate decision separation is unchanged.
- No database work was added to render paths.

## Validation
- Full repository suite: 1027 tests passed + 383 subtests.
- Focused checks included:
  - shared overlay zoom/chrome
  - Control Center launcher/routing
  - Performance Hub telemetry workstation
  - F1 Dash native/LAN parity and page behavior
  - corner review/map behavior
  - radio transcript overlay
- Python source compilation succeeded for modified UI modules.

## Preservation
- No deterministic engine behavior changed.
- No persistent user-data format changed.
- No replay-write behavior introduced.
- No map/reference authority changed.


---

## Archived source: `CHECKPOINT_V2.0.6.4_UI_1.8.1_HELP_VOICE_COMMAND_REFERENCE.md`

# CHECKPOINT — V2.0.6.4 UI 1.8.1 Help / Voice Command Reference

## Scope
UI/help-only addition. No telemetry, coaching, scoring, strategy, replay, persistence, or radio-command execution logic changed.

## Added
- New **HELP** tab in Control Center beside CONTROL and PERFORMANCE HUB.
- HELP uses the existing shared `/radio-help` page when QtWebEngine is available.
- Native fallback remains available for minimal PySide installs.
- Search box for command phrases/functions.
- Function filter chips.
- Voice commands grouped by:
  - Tyres
  - Brakes & Setup
  - Power Unit & Car Condition
  - Position & Traffic
  - Laps & Timing
  - Fuel / ERS / Overtake Systems
  - Weather & Race Control
  - Race Strategy
  - Pit & Service
  - Driving & Performance
  - Race Engineer Controls
  - Performance / Speed Coach Controls
  - Radio & Runtime Controls
  - Coaching Mode / Detail / Voice
  - General Facts & Help

## Grounding
The reference reflects deterministic command families supported by `voice_commands.py` and runtime controls supported by `radio_controls.py`. It does not add new command execution behavior.

## Validation
- Python compile passed for `src/overlay/window.py` and `src/radio_help_page.py`.
- Dedicated HELP regressions added.
- Full suite: **1029 passed + 383 subtests**.


---

## Archived source: `CHECKPOINT_V2.0.6.5_VOICE_COMMAND_RECOGNITION_TOLERANCE_HOTFIX.md`

# CHECKPOINT — V2.0.6.5 Voice Command Recognition Tolerance Hotfix

## Base
- V2.0.6.4 + UI 1.8.1 Help / Voice Command Reference

## Scope
Radio/STT normalization only. No telemetry, coaching, scoring, strategy, replay, reference, persistence, or UI authority changes.

## Added high-confidence transcript-derived normalizations
- `pre coat` / `pre cut` / `pre code` -> `pre coach`
- enable/disable variants of the above
- `performance good` -> `performance coach`
- `straight line good` -> `straight line coach`
- `driitline voice` -> `straight line voice`
- `gain loss wise` -> `gain loss voice`
- `vise control help` / `vice control help` -> `voice control help`
- `set y speed normal/fast/low` -> `set voice speed normal/fast/slow`
- `set voice speed low` -> `set voice speed slow`
- `compare it previous` -> `compare with previous`

## Safety behavior preserved
- Exact / high-confidence normalization only.
- No broad fuzzy control activation was added.
- Ambiguous fragments such as `Be good` and `G4` remain unsupported and cannot change runtime control state.

## Validation
- New transcript-derived regression coverage added.
- Python compile checks passed.
- Full suite: 1034 passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.1.0.1_DRIVER_PROFILE_UI_THEME_HOTFIX.md`

# Race Engineer V2.1.0.1 — Driver Profile UI Theme Hotfix

## Base
V2.1.0 Driver Profile Foundation.

## Fix
- First-run Create Driver Profile dialog now uses the shared Race Engineer UI theme immediately.
- Replaced the unintended native Windows/Qt light appearance with the existing Control Center dark surfaces, borders, muted text and cyan accent.
- Reworked the setup layout into the same card/control visual language used by the Control Center.
- Added themed line edits, combos, avatar controls, secondary Cancel button and primary Create Profile button.

## Logic
No Driver Profile persistence, Performance Hub compatibility, telemetry, coaching, strategy, replay, radio or scoring logic was changed.

## Validation
- Python compile: PASS
- Full regression suite: 1039 tests passed + 383 subtests passed


---

## Archived source: `CHECKPOINT_V2.1.0_DRIVER_PROFILE_FOUNDATION.md`

# CHECKPOINT — V2.1.0 Driver Profile Foundation

Base: `V2.0.6.5_VOICE_COMMAND_RECOGNITION_TOLERANCE_HOTFIX_FULL`

## Implemented

- Added persistent person-level Driver Profile storage under `user_data/drivers/<DRIVER_ID>/`.
- Driver IDs use stable UUIDs and are never derived from display names.
- Added `profile.json`, `career/summary.json`, and `games/f1_26/profile.json` containers.
- Added optional avatar copy, country/region, Metric/Imperial units, created/last-active timestamps, and active game.
- Added multi-driver-safe `index.json` with last-active driver loading.
- Added editable personal-info API that preserves Driver ID on display-name changes.
- Added first-run Create Driver Profile UI.
- First-run game selection exposes F1 26; ACC and Dirt Rally 2.0 are visibly marked future support and disabled.
- Normal startup no longer asks the user to select a driver every launch; it loads the last active Driver Profile.
- Existing Performance Hub `user_profiles` ownership remains intact and is linked through `compatibility.performance_history_profile_id`.
- Existing telemetry/coaching/performance calculation logic was not changed.
- No Driver Skill Score is calculated in this release.

## Storage

```text
user_data/
  drivers/
    index.json
    DRIVER_ID/
      profile.json
      career/
        summary.json
      games/
        f1_26/
          profile.json
```

## Next roadmap release

V2.1.1 — permanent top-right profile control + Driver Profile Overview UI.


---

## Archived source: `CHECKPOINT_V2.1.1.1_DRIVER_PROFILE_ALIGNMENT_DIALOG_THEME_HOTFIX.md`

# V2.1.1.1 — Driver Profile Alignment + Dialog Theme Hotfix

Base: `V2.1.1 DRIVER PROFILE CONTROL OVERVIEW`

## Fixes
- Moved the compact Driver Profile control from the far-right side of the Control Center header to the far-left side.
- Fixed the `Edit Driver Profile` dialog so it uses the Race Engineer dark theme instead of the native light Windows/Qt palette.
- Added themed `QDialog` and `QLineEdit` styling to the shared UI stylesheet for consistent dark dialogs and text inputs.
- Applied styled-background handling to the edit dialog so the dark background is rendered correctly.

## Scope protection
- No changes to driver-profile storage/identity logic.
- No changes to telemetry, Performance Hub calculations, radio, coaching, strategy, replay, or scoring logic.


---

## Archived source: `CHECKPOINT_V2.1.1.2_DRIVER_PROFILE_TAB_ORDER_HOTFIX.md`

# V2.1.1.2 — Driver Profile Tab Order Hotfix

Base: `V2.1.1.1 DRIVER PROFILE ALIGNMENT + DIALOG THEME HOTFIX`

## Fix
- Moved the main `DRIVER PROFILE` tab to the far-left position in the top Control Center tab bar.
- New top-tab order:
  1. DRIVER PROFILE
  2. CONTROL
  3. PERFORMANCE HUB
  4. HELP

## Scope protection
- No changes to Driver Profile storage/identity logic.
- No changes to telemetry, Performance Hub calculations, radio, coaching, strategy, replay, or scoring logic.


---

## Archived source: `CHECKPOINT_V2.1.1_DRIVER_PROFILE_CONTROL_OVERVIEW.md`

# Race Engineer V2.1.1 — Driver Profile Control + Overview

Base: `V2.1.0.1 DRIVER PROFILE UI THEME HOTFIX`

## Implemented

- Permanent Driver Profile control above the Control Center tabs so it remains visible on CONTROL, DRIVER PROFILE, PERFORMANCE HUB and HELP.
- Compact identity card shows initials, display name, active game, and `Skill N/A` until the skill evidence releases are implemented.
- Added a DRIVER PROFILE workspace with nested tabs:
  - OVERVIEW
  - SKILLS
  - TRENDS
  - HISTORY
  - GAME PROFILES
- Overview displays person-level identity, persistent Driver ID, country/region, preferred units, created date and last-active timestamp.
- Existing F1 Performance History is read non-destructively to show session and track counts for the linked person-level profile.
- Driving time explicitly remains `Pending V2.2.0`; application uptime or synthetic estimates are not used.
- Skills, Trends and History tabs are intentionally evidence-gated placeholders matching the roadmap release order.
- Game Profiles shows F1 26 as active/configured and ACC / Dirt Rally 2.0 as future support.
- Added Edit Profile dialog for display name, country/region, units, avatar replacement and avatar clearing.
- Editing does not change the persistent Driver ID.
- Legacy Performance Hub local profile label is kept synchronized when the person-level display name is edited, without moving or rewriting session history.

## Persistence additions

`DriverProfileStore` now supports:

- `avatar_path(driver_id)`
- `update_avatar(driver_id, avatar_source)`

Avatar changes preserve Driver ID and existing game/history ownership.

## Deliberately not implemented in V2.1.1

- Driver Skill Score
- Skill evidence calculation
- Skill trends
- Career milestones
- Accurate telemetry-active driving hours
- ACC telemetry/profile calculations
- Dirt Rally telemetry/profile calculations

These remain assigned to later roadmap releases.

## Validation

- Focused V2.1.0 + V2.1.1 tests: 8 passed.
- Full regression suite: **1042 passed, 383 subtests passed**.
- Python compile validation passed for modified source files.
- Runtime Qt visual smoke test could not be executed in the Linux packaging environment because PySide6 is not installed there; source/static regression validation and the project's complete test suite passed.


---

## Archived source: `CHECKPOINT_V2.1.2_GAME_PROFILE_ARCHITECTURE.md`

# V2.1.2 — Game Profile Architecture

Base: `V2.1.1.2 DRIVER PROFILE TAB ORDER HOTFIX`

## Implemented
- Driver remains the person-level identity.
- Added explicit per-game profile APIs and references.
- Every driver now owns independent game-profile containers for:
  - F1 26 → `formula`
  - Assetto Corsa Competizione → `gt`
  - Dirt Rally 2.0 → `rally`
- Game profile layout remains under `drivers/<driver_id>/games/<game_id>/profile.json`.
- Added game-profile path/load/list/ensure-all APIs.
- Existing V2.1.x drivers are repaired non-destructively at load so missing ACC/Dirt containers are created automatically.
- Existing F1 counters/data in the game-profile container are preserved during repair.
- Future game containers do not make unsupported telemetry adapters selectable/active.
- Game Profiles UI now distinguishes a ready profile container from future telemetry support.

## Deliberately not included
- No F1 Performance Hub data migration yet (V2.1.3).
- No telemetry-active driving-hours engine (V2.2.0).
- No skill score/evidence/trend calculations.
- No ACC or Dirt telemetry adapters.

## Validation
- Focused V2.1.0/V2.1.1/V2.1.2 tests: 13 passed.
- Full regression: 1047 passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.1.3.1_ACTIVE_GAME_PROFILE_SELECTOR.md`

# V2.1.3.1 — Active Game Profile Selector

Base: `V2.1.3 EXISTING F1 DATA MIGRATION`

## Architecture rule
- A person-level Driver Profile owns multiple Game Profiles.
- Exactly one Game Profile is active at any given time.
- Switching Game Profile changes game/discipline context without changing Driver ID.

## UI
- Added `ACTIVE GAME PROFILE` selector to Driver Profile -> GAME PROFILES.
- Added explicit F1 26 / ACC / Dirt Rally 2.0 selection.
- Added per-game SELECT / ACTIVE buttons.
- Compact Driver Profile control and Overview immediately reflect the selected game.
- ACC/Dirt remain clearly marked `TELEMETRY FUTURE` while their profile containers can still be selected.

## Data isolation
- `profile.json.active_game` remains the authoritative single active game.
- Every per-game `profile.json` mirrors an `active` boolean so the invariant is inspectable on disk.
- Switching profiles atomically clears active state from the other game containers.
- Non-F1 Game Profiles no longer display F1 Performance Hub session/track totals in the Driver Profile Overview.
- F1 continues to show the migrated Performance Hub totals only when F1 26 is the active Game Profile.

## UI correction
- Updated the Driver Profile explanatory text from V2.1.2 to V2.1.3 migration wording.

## Validation
- Focused Driver/Game Profile suite: 20 passed.
- Full regression: 1,054 tests passed + 383 subtests passed.

## Not included
- No ACC telemetry adapter.
- No Dirt Rally telemetry adapter.
- No V2.2.0 driving-hours engine yet.
- No skill scoring or trends.


---

## Archived source: `CHECKPOINT_V2.1.3.2_GAME_PROFILE_CHECKBOX_SELECTOR_HOTFIX.md`

# V2.1.3.2 — Game Profile Checkbox Selector Hotfix

Base: `V2.1.3.1 ACTIVE GAME PROFILE SELECTOR`

## UI change
- Removed the separate Active Game Profile dropdown and SET ACTIVE control.
- Added one checkbox at the far-left of each Game Profile card.
- Checking a profile immediately makes it the only active Game Profile.
- The currently active profile remains checked; it cannot be left with no active game.
- Driver identity remains unchanged when switching profiles.

## Scope protection
- No changes to profile storage format or F1 migration binding.
- No changes to telemetry, Performance Hub calculations, radio, coaching, strategy, replay, or scoring logic.

## Validation
- Focused Driver/Game Profile suite: 20 passed.


---

## Archived source: `CHECKPOINT_V2.1.3_EXISTING_F1_DATA_MIGRATION.md`

# V2.1.3 — Existing F1 Data Migration

Base: `V2.1.2 GAME PROFILE ARCHITECTURE`

## Goal
Attach existing F1 Performance Hub history to the new person-level Driver Profile / F1 Game Profile without destructive physical migration.

## Implemented
- Added `src/f1_profile_migration.py` as the V2.1.3 migration coordinator.
- Existing Performance Hub SQLite history remains the authoritative store.
- F1 Game Profile records a stable `history_binding` with:
  - local Performance History profile ID
  - authoritative database path
  - logical-link storage mode
  - first attachment / last verification timestamps
  - inventory of sessions, tracks, laps and persisted evidence
  - content scope for sessions, laps, tracks, telemetry, session-recorded references, corner performance, performance analysis, assists, driver/game information and recorded history
- Existing Driver Profile compatibility ownership is preserved.
- Existing F1 session/lap/track totals are reflected into the F1 Game Profile and career summary.
- Driving seconds remain untouched/pending V2.2.0; no time is inferred from app uptime or historical lap totals.
- Installed reference/track assets remain shared Race Engineer assets and are not duplicated per driver.
- Startup verifies/repairs the F1 history binding for existing and newly created Driver Profiles.
- Added read-only `PerformanceHistoryStore.profile_inventory()`.
- Migration is idempotent; the first attachment timestamp is preserved on re-verification.

## Non-destructive guarantee
- No stored session rows are rewritten by the migration.
- No telemetry JSON is copied or deleted.
- No Performance Hub calculations, coaching, radio, strategy, replay, or scoring logic is changed.

## Validation
- Focused profile/migration tests: 17 passed.
- Full regression suite: 1,051 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.2.0.1_LIVE_ASSIST_STATE_AUTHORITY_HOTFIX.md`

# V2.2.0.1 — Live Assist State Authority Hotfix

Base: `V2.2.0 ACCURATE DRIVING HOURS ENGINE`

## Problem
Per-lap Performance Hub assist state could become stale in Time Trial when assists were changed during a session. The completed-lap summary started from live SessionData, but then overwrote TC / ABS / gearbox values with `m_playerSessionBestDataSet`. That dataset belongs to the session-best lap, not necessarily the lap currently being driven.

## Fix
- `PacketSessionData` / RaceState Session is now the current-lap authority for assist state.
- Added live RaceState fields for:
  - Traction Control
  - ABS
  - Gearbox Assist
  - Steering Assist
  - Braking Assist
  - Pit Assist
  - Pit Release Assist
  - ERS Assist
  - DRS Assist
- Equal-car-performance remains sourced from live SessionData.
- Removed Time Trial session-best data as an authority for the current lap's assist configuration.
- Added per-lap assist tracking:
  - start snapshot
  - final/current snapshot
  - mid-lap change list with lap time and track distance
  - `assist_changed_mid_lap` flag
- Existing compact Performance Hub assist icons use the final assist state actually observed on that lap.
- `custom_setup` is no longer inferred from a session-best Time Trial lap. If no current-lap authoritative source exists it remains unavailable rather than reporting stale data.

## Example
If TC changes Full -> Medium at 31.5 s / 1420 m, the completed lap retains:
- starting TC = Full
- finishing TC = Medium
- an explicit Full -> Medium change event

## Scope protection
No changes to scoring, coaching decisions, strategy, replay authority, Driver Profile identity, or driving-hours logic.

## Validation
- Focused assist/history regression: 10 passed
- Full suite: 1065 passed + 383 subtests


---

## Archived source: `CHECKPOINT_V2.2.0_ACCURATE_DRIVING_HOURS_ENGINE.md`

# V2.2.0 — Accurate Driving Hours Engine

Base: `V2.1.3.2 GAME PROFILE CHECKBOX SELECTOR HOTFIX`

## Implemented
- Added live F1 telemetry-active driving-time accounting.
- Counts only player telemetry while:
  - telemetry mode is LIVE,
  - F1 26 is the active Game Profile,
  - a real non-zero F1 session is active,
  - game is not paused,
  - user is not spectating,
  - session has not ended,
  - driver status is Flying lap / In lap / Out lap / On track,
  - player telemetry is present.
- Replay never contributes to career/game driving time.
- Garage/menu/inactive samples do not contribute.
- Long telemetry gaps are rejected rather than back-filled as driving time.
- Uses F1 session-time deltas rather than application uptime.

## F1 breakdown
Stored under the F1 Game Profile:
- Practice
- Time Trial
- Qualifying
- Sprint
- Race

`driving_seconds` stores the F1 total. `career/summary.json -> total_driving_seconds` is recalculated as the sum of all game-profile counters so the architecture remains multi-game ready.

## Persistence / safety
- Accumulates in memory and flushes periodically to avoid per-packet disk I/O.
- Flushes on application shutdown.
- Flushes pending F1 time before entering replay, switching Driver, or selecting a different active Game Profile.
- Profile identity/history migration logic is unchanged.

## UI
Driver Profile -> Overview now shows:
- active Game Profile driving time,
- F1 Practice / Time Trial / Qualifying / Sprint / Race breakdown.

## Historical data rule
V2.2.0 does not manufacture driving time for old sessions that predate this engine. Existing sessions/laps remain migrated, but accurate driving time begins accumulating from live telemetry after this release unless a future historical source can prove equivalent telemetry-active time without inference.

## Validation
- Focused V2.2 driving-time tests passed.
- Full regression: 1061 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.3.0.1_HISTORICAL_SKILL_EVIDENCE_BACKFILL.md`

# V2.3.0.1 — Historical Skill Evidence Backfill

Base: `V2.3.0 SKILL EVIDENCE ENGINE`

## Purpose
Backfill the V2.3 Skill Evidence store from already-persisted LIVE F1 Performance Hub sessions so existing driver history contributes immediately without requiring the driver to repeat old sessions.

## Implemented
- Added a read-only Performance History source API for skill-evidence backfill.
- Existing LIVE Performance Hub sessions are scanned non-destructively.
- The same deterministic V2.3 evidence builder is used for historical and new live sessions.
- Existing valid Pace, Consistency, Braking, Corner Entry, Apex/Minimum Speed, Traction/Exit, and Car Control measurements are recovered when the saved session contains sufficient evidence.
- Sessions with insufficient evidence remain zero-measurement/N/A rather than receiving fabricated values.
- Backfill is idempotent using stable historical session identity and a source signature marker.
- Reopening the application or Driver Profile does not duplicate evidence.
- Explicit replay markers are defensively rejected even though Performance History is LIVE-only by design.
- Driver Profile -> Skills now shows historical-backfill status and number of stored sessions scanned.
- Career F1 Driver Skill score remains uncalculated until V2.4.0.

## Files
- `src/skill_evidence.py`
- `src/performance_history.py`
- `src/overlay/window.py`
- `tests/test_v230_skill_evidence_engine.py`

## Validation
- Historical backfill focused tests: 7 passed.
- Full suite: 1,072 tests passed + 383 subtests passed.

## Safety
- No historical Performance Hub sessions are copied, edited, deleted, or rewritten.
- No replay-derived career evidence is accepted.
- No career skill score is calculated in this release.


---

## Archived source: `CHECKPOINT_V2.3.0_SKILL_EVIDENCE_ENGINE.md`

# V2.3.0 — Skill Evidence Engine

Base: `V2.2.0.1 LIVE ASSIST STATE AUTHORITY HOTFIX`

## Implemented
- Added `src/skill_evidence.py` as a persistent session-level evidence layer between measured live telemetry/review data and the future career F1 Driver Skill model.
- Evidence is stored per person-level Driver and per Game Profile under:
  - `user_data/drivers/<DRIVER_ID>/games/f1_26/skill_evidence/index.json`
  - `user_data/drivers/<DRIVER_ID>/games/f1_26/skill_evidence/sessions/<SESSION_KEY>.json`
- Logical live sessions are idempotently upserted; a later/final session snapshot replaces the same evidence file rather than creating duplicates.
- Evidence writes occur only through LIVE session finalization/history paths. Replay remains read-only.
- If a non-F1 Game Profile is active, F1 evidence is not written to it.

## Roadmap evidence contract
Every stored measurement contains:
- `skill`
- `value`
- `confidence`
- `sample_count`
- `track`
- `conditions`
- `session_type`
- `timestamp`
- `reference_quality`

Extra audit fields include `metric`, `unit`, and `source`.

## Evidence currently captured
- Pace: raw best-lap gap to a valid available reference (seconds).
- Consistency: raw lap-time population standard deviation (seconds), requiring at least two timed laps.
- Braking: session-level deterministic braking execution evidence.
- Corner Entry: session-level turn-in evidence.
- Apex / Minimum Speed: session-level corner-speed evidence.
- Traction / Exit: throttle-application and exit-speed evidence retained as separate measurements under the same future skill domain.
- Car Control: steering-control evidence.

Unsupported/insufficient measurements are omitted rather than fabricated. Tyre Management, Wet Driving, and Racecraft are not synthesized without defensible evidence.

## Critical scope rule
V2.3.0 does **not** calculate a career F1 Driver Skill score. Every evidence file explicitly stores `career_skill_score: null`. Career skill aggregation remains V2.4.0.

## UI
Driver Profile -> Skills now shows:
- evidence sessions
- total stored measurements
- per-domain evidence measurement/sample counts

It does not show a career skill value yet.

## Validation
- Focused Skill Evidence / Driver Profile tests: passed.
- Full regression: `1070 passed, 383 subtests passed`.


---

## Archived source: `CHECKPOINT_V2.4.0.1_SKILL_LAYOUT_CLIPPING_HOTFIX.md`

# V2.4.0.1 — Skill Layout Clipping Hotfix

Base: `V2.4.0 F1 DRIVER SKILL V1`

## Fix
- Prevented Driver Profile -> Skills numeric values from clipping/crowding.
- Skill name, score, and evidence details now use independent grid columns.
- Score column has a fixed minimum width suitable for `100.0`, `95.9`, and `N/A` under Windows display scaling.
- Skill scores are right-aligned for consistent scanning.
- Evidence details have a dedicated stretchable column.
- Added minimum row height to prevent vertical glyph clipping at different DPI/display scales.

## Scope protection
- UI-only hotfix.
- No changes to V2.4.0 scoring formulas, evidence values, historical backfill, confidence rules, telemetry, assists, driving hours, Performance Hub, coaching, strategy, radio, or replay behavior.

## Validation
- Focused V2.4 tests: 5 passed.
- Full suite: 1,077 tests + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.4.0_F1_DRIVER_SKILL_V1.md`

# V2.4.0 — F1 Driver Skill V1

Base: `V2.3.0.1 HISTORICAL SKILL EVIDENCE BACKFILL`

## Scope
- Added the first Formula Driver Skill model derived only from persisted Skill Evidence.
- No telemetry event re-detection and no direct scoring from replay/app uptime.
- Missing or unsupported domains remain N/A.
- Confidence labels remain deferred to V2.4.1.
- Trend history remains deferred to V2.5.0.

## Evidence normalization upgrade
- Pace evidence now stores both raw best-lap gap in seconds and circuit-independent percentage gap to a valid reference.
- Consistency evidence now stores both raw lap-time standard deviation and lap-time coefficient of variation (%).
- Evidence engine version bumped to V2.4.0 so historical LIVE Performance Hub sessions are idempotently rebuilt once with the new normalized metrics.

## F1 skill domains
Available when validated evidence exists:
- Pace
- Consistency
- Braking
- Corner Entry
- Apex / Minimum Speed
- Traction / Exit
- Car Control

Remain N/A until defensible source evidence exists:
- Racecraft
- Tyre Management
- Wet Driving

## Overall Formula Driver Skill
- Weighted only across available core skills.
- Requires at least 4 of 7 core skills.
- Requires scoreable evidence from at least 2 logical sessions.
- Missing skills are not treated as zero.

## Transparent normalization rules
- Pace: 100 at <=0% gap to valid reference; linear to 0 at +8%.
- Consistency: 100 at <=0.25% lap-time coefficient of variation; linear to 0 at >=3.0%.
- Technique domains use the authoritative 0..100 deterministic Performance Review technique scores.

## UI
- Driver Profile -> Skills now shows Formula Driver Skill /100 and each skill domain.
- Per-domain evidence session/measurement/sample counts remain visible.
- Compact Driver Profile control now shows the current F1 Skill instead of N/A when the overall score is available.

## Validation
- Focused V2.3/V2.4 tests: 12/12 passed.
- Full regression: 1,077 tests + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.4.1.1_SKILL_PROGRESS_BAR_LAYOUT_HOTFIX.md`

# V2.4.1.1 — Skill Progress Bar + Layout Hotfix

Base: `V2.4.1 SKILL CONFIDENCE / SAMPLE SYSTEM`

## UI fixes
- Widened the Skills table into four independent columns: skill, numeric score, progress bar, confidence/evidence detail.
- Added a horizontal 0–100 progress bar for every numeric skill score.
- Added score-band colors for presentation only:
  - Red: < 50
  - Amber: 50–69.9
  - Cyan: 70–84.9
  - Green: >= 85
- `N/A` skills show an empty neutral bar.
- Increased skill-name and confidence/evidence column widths and row height to prevent clipping at Windows DPI/display scaling.

## Logic protection
- No V2.4.0 scoring formulas changed.
- No V2.4.1 confidence calculations changed.
- No evidence, telemetry, history, replay, radio, coaching or strategy logic changed.

## Validation
- Focused V2.4 UI/skill tests: 6 passed.
- Full regression: 1,083 tests + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.4.1.2_SKILL_CARD_LAYOUT_LEGEND_HOTFIX.md`

# V2.4.1.2 — Skill Card Layout + Legend Hotfix

Base: `V2.4.1.1 SKILL PROGRESS BAR LAYOUT HOTFIX`

## UI fixes
- Replaced the row/table-style F1 skill list with individual skill cards.
- Each card now contains:
  - skill name
  - large numeric score / N/A
  - colored 0–100 progress bar
  - confidence plus sessions/tracks/measurements/samples detail
- Confidence/evidence text wraps within its own card so it cannot squeeze or clip the numeric score.
- Score labels use dedicated minimum width and right alignment for Windows DPI scaling.
- Added a bottom-right score-color legend:
  - Weak <50 — red
  - Developing 50–69.9 — amber
  - Strong 70–84.9 — cyan
  - Excellent 85–100 — green
  - N/A — neutral

## Scope protection
- No changes to V2.4 skill scoring formulas.
- No changes to V2.4.1 confidence calculations.
- No changes to Skill Evidence, Performance Hub, telemetry, radio, coaching, replay, or strategy logic.

## Validation
- Focused V2.4/V2.4.1 tests: 12 passed.
- Full regression: 1,084 tests + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.4.1.2_SKILL_VALUE_LEGEND_HOTFIX.md`

# V2.4.1.2 — Skill Value + Legend Hotfix

Base: V2.4.1.1 Skill Progress Bar + Layout Hotfix

## UI fixes
- Expanded the skill-score column from 74 px to a DPI-safe fixed 112 px.
- Added right padding so values such as `100.0`, `95.9`, `29.6`, and `N/A` remain fully visible at Windows display scaling.
- Added a lower-right score-color legend to the skill card:
  - RED <50
  - AMBER 50–69.9
  - CYAN 70–84.9
  - GREEN 85–100
  - EMPTY = N/A

## Scope protection
- No score formula changes.
- No confidence model changes.
- No evidence/history changes.
- No telemetry/coaching/radio/replay changes.


---

## Archived source: `CHECKPOINT_V2.4.1.3_SKILL_CARD_GRID_RENDER_HOTFIX.md`

# V2.4.1.3 — Skill Card Grid Render Hotfix

Base: `V2.4.1.2 SKILL CARD LAYOUT + LEGEND HOTFIX`

## Fixes
- Converted the Skills workspace into a vertically scrollable page so the skill-card grid is never compressed to fit a short Control Center viewport.
- Enforced five two-column grid rows with a 132 px minimum row height.
- Skill cards now keep a stable full-card height instead of collapsing into thin clipped strips.
- Preserved the existing score progress bars, confidence/evidence detail, N/A handling and score-color legend below the cards.
- Horizontal scrolling remains disabled; the two-column layout expands to available width.

## Scope protection
- No changes to F1 Driver Skill formulas.
- No changes to Skill Evidence, confidence calculations, historical backfill, telemetry, radio, coaching, strategy, replay, or Performance Hub logic.

## Validation
- Focused skill/evidence tests: 19 passed.
- Full regression: 1084 tests + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.4.1_SKILL_CONFIDENCE_SAMPLE_SYSTEM.md`

# V2.4.1 — Skill Confidence / Sample System

Base: `V2.4.0.1 SKILL LAYOUT CLIPPING HOTFIX`

## Scope
Adds evidence-trust confidence to the F1 Driver Skill model without changing the V2.4.0 driving-skill scoring formulas.

## Confidence model
Every available skill now stores:
- `confidence`: LOW / MEDIUM / HIGH
- `confidence_score`: internal 0..1 trust depth
- `session_count`
- `track_count`
- `measurement_count`
- `sample_count`
- `evidence_confidence`: weighted source-evidence confidence

Confidence is based on four independent evidence-depth dimensions:
- 45% session breadth
- 25% track breadth
- 15% sample depth
- 15% source evidence confidence

Thresholds:
- LOW: < 0.45
- MEDIUM: >= 0.45 and < 0.75
- HIGH: >= 0.75

The session/track breadth weights intentionally prevent one very dense session from being labelled HIGH confidence.

## Overall skill confidence
The Formula Driver Skill now also exposes an overall confidence label derived from the available core-skill confidence values. This confidence is presentation metadata only and does not alter the V2.4.0 skill score.

## UI
Driver Profile -> Skills now shows:
- overall `Confidence LOW / MEDIUM / HIGH`
- per-skill confidence
- session count
- track count
- measurement count
- sample count

Missing skill domains remain `N/A` with confidence `N/A`.

## Regression
- Focused V2.4/V2.4.1 tests: 10 passed
- Full suite: 1,082 tests passed + 383 subtests passed


---

## Archived source: `CHECKPOINT_V2.5.0.1_TREND_GRAPH_TRACK_FILTER_HOTFIX.md`

# V2.5.0.1 — Trend Graph + Track Filter Hotfix

Base: `V2.5.0 SKILL TRENDS`

## Fixes
- Increased the native Skill Trend graph bottom plot margin so x-axis labels and the final graph line are fully visible at Windows DPI scaling.
- Added a `TRACK` selector to Driver Profile -> Trends.
- Default track selection is `All Tracks`.
- The selector is populated from stored F1 Skill Evidence tracks.
- Selecting a specific track recalculates cumulative trend snapshots from that track's own evidence sessions only; it does not merely hide points from the all-track career series.
- Skill, Track and Range filters can be combined.
- Trend status text now identifies the selected track scope.

## Scope protection
- No V2.4 skill scoring formula changes.
- No V2.4.1 confidence formula changes.
- No telemetry, coaching, radio, strategy, replay, Performance Hub, or driving-hours logic changes.

## Validation
- Focused V2.5 trend tests: 7 passed.
- Full regression: 1,091 tests + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.5.0.2_TREND_AXIS_LABEL_HOTFIX.md`

# V2.5.0.2 — Trend Axis Label Hotfix

Base: V2.5.0.1 Trend Graph + Track Filter Hotfix

## Fix
- Removed circuit names from the Skill Trends graph X axis.
- X axis now represents ordered trend sessions using `S1 ... Sn`.
- `All Tracks` therefore reads as a session progression rather than a circuit comparison.
- Specific-track views use the same session-sequence axis because the selected circuit is already explicit in the TRACK selector and status line.
- No trend scoring, evidence, filtering, confidence, or telemetry logic changed.

## Validation
- Focused Skill Trends tests: 7 passed.
- Full regression: 1,091 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.5.0_SKILL_TRENDS.md`

# V2.5.0 — Skill Trends

Base: `V2.4.1.3 SKILL CARD GRID RENDER HOTFIX`

## Implemented
- Added persistent `skill_trends.json` under the active driver's F1 26 Game Profile.
- One cumulative trend snapshot is stored per logical Skill Evidence session.
- Existing evidence sessions are backfilled deterministically into trend history on first use.
- Trend storage is idempotent; refreshing/replacing the same evidence session does not create duplicate snapshots.
- Trend sources remain validated Skill Evidence only. Missing skills remain N/A and no interpolation/synthetic score is generated.
- Added Driver Profile -> Trends UI with:
  - Overall + individual F1 skill selector
  - 10 Sessions / 30 Sessions / 3 Months / All Time filters
  - Current score
  - Change over selected range
  - Personal best
  - Sessions shown
  - Native Qt line graph
- Live Skill Evidence persistence refreshes the trend store after session completion.
- Historical backfill refreshes trend history once after the evidence migration completes.

## Scope protection
- V2.4.0 skill scoring formulas are unchanged.
- V2.4.1 confidence calculations are unchanged.
- No telemetry, coaching, Performance Hub, radio, strategy, replay, or assist logic changed.
- Per-track skill/trends remain V2.5.1.
- Career milestone history remains V2.6.0.

## Validation
- Focused V2.4/V2.5 tests: 17 passed.
- Full suite: 1,089 tests + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.5.1.1_TRACK_CARD_UI_LANGUAGE_HOTFIX.md`

# V2.5.1.1 — Track Card UI Language Hotfix

Base: `V2.5.1 PER_TRACK_SKILL_TRENDS`

## Fixed
- Rebuilt Driver Profile > TRACKS into the same card-based UI language used across the Driver Profile pages.
- Removed the old split left-list/detail pattern.
- Removed the accidental literal `\n` rendering inside track rows.
- Replaced the track list with responsive track cards in a two-column grid.
- Each track card now shows:
  - Track name
  - Overall
  - Trend
  - Sessions
  - Personal Best
  - Full skill breakdown
  - Evidence / scoreable snapshot note
- Preserved the same evidence authority and scoring rules from V2.5.1.
- Added dark-theme-safe empty/error states so the page no longer shows white placeholder regions.

## Validation
- Focused V2.5/V2.5.1 tests: 10 passed.
- Full regression: 1,094 passed, 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.5.1.2_TRACK_CARD_STARTUP_HOTFIX.md`

# V2.5.1.2 — Track Card Startup Hotfix

Base: `V2.5.1.1 TRACK_CARD_UI_LANGUAGE_HOTFIX`

## Fixed
- Restored the shared `_clear_layout_widgets()` helper accidentally removed during the TRACKS card-UI refactor.
- Fixes Control Center startup crash in `_refresh_track_performance()`.
- Added a regression test that asserts the dynamic-layout cleanup helper exists and is used by the track-card refresh path.

## Scope
- No changes to track scoring, skill scoring, trends, evidence, telemetry, or profile data.
- V2.5.1.1 card-based TRACKS UI is preserved.

## Validation
- Focused V2.5/V2.5.1 tests: 11 passed.
- Full regression: 1,095 passed, 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.5.1.3_TRACK_SKILL_BAR_STYLE_HOTFIX.md`

# V2.5.1.3 — Track Skill Bars + Stylesheet Warning Hotfix

Base: `V2.5.1.2 TRACK CARD STARTUP HOTFIX`

## Fixed
- Removed invalid QLabel stylesheet values that caused repeated Qt warnings:
  `Could not parse stylesheet of object QLabel(...)`.
- Track summary colors now use valid CSS hex strings only.
- Added per-skill progress bars inside every TRACKS card.
- Progress-bar score bands match the main Skills page:
  - Red: < 50
  - Amber: 50–69.9
  - Cyan: 70–84.9
  - Green: 85–100
  - Neutral: N/A
- Added clearer typography/color hierarchy:
  - Track heading: cyan
  - Section headings: amber
  - Summary metric labels: muted blue
  - Skill labels: muted light blue
  - Numeric values: white / trend semantic color
- Preserved V2.5.1 per-track scoring, evidence, and trend logic unchanged.

## Validation
- Focused V2.5/V2.5.1 tests: 12 passed.
- Full regression: 1,096 passed, 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.5.1_PER_TRACK_SKILL_TRENDS.md`

# V2.5.1 — Per-Track Skill / Trends

Base: `V2.5.0.2 TREND AXIS LABEL HOTFIX`

## Added
- New Driver Profile `TRACKS` tab.
- Circuit list built from stored validated F1 Skill Evidence.
- Track cards show current track Overall skill when available, stored evidence sessions, and track trend.
- Selecting a circuit opens a detail panel with:
  - Overall
  - Trend
  - Sessions
  - Personal Best
  - Pace
  - Consistency
  - Braking
  - Corner Entry
  - Apex / Minimum Speed
  - Traction / Exit
  - Car Control
  - Racecraft
  - Tyre Management
  - Wet Driving
- Per-track scoring reuses the existing `SkillTrendStore` track-filtered evidence authority.
- One-session tracks may show individual skills while Overall remains N/A until the existing Overall evidence threshold is satisfied.
- N/A remains N/A; no synthetic track ratings are created.

## New module
- `src/track_skill.py`

## Validation
- Focused V2.5/V2.5.1 tests: 10 passed.
- Full regression: 1,094 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.6.0_CAREER_HISTORY_MILESTONES.md`

# V2.6.0 — Career History / Milestones

Base: `V2.5.1.3 TRACK SKILL BAR STYLE HOTFIX`

## Added
- New deterministic `career_history.py` engine.
- HISTORY tab rebuilt as a scrollable milestone timeline using the same card UI language as Driver Profile.
- Milestones are generated only from timestamped persisted F1 evidence / trend history.
- Supported milestone types:
  - F1 evidence-session count milestones: 5, 10, 25, 50, 100, 250, 500
  - Formula Driver Skill threshold milestones
  - Per-skill threshold milestones
  - Per-track Overall skill personal-best milestones
- History summary shows:
  - milestone count
  - latest milestone time
  - skill milestone count
  - track-PB milestone count
- Events are deterministic and idempotent.
- N/A / insufficient evidence remains absent.
- Existing aggregate driving-hours are intentionally not backdated because the exact threshold-crossing timestamp cannot be reconstructed safely.

## Storage
`drivers/<DRIVER_ID>/games/f1_26/career_history.json`

## Validation
- Focused V2.5/V2.6 tests: 16 passed.
- Full regression: 1,100 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.6.1.1_PROFILE_TIMEZONE_LATEST_FIRST_HOTFIX.md`

# V2.6.1.1 — Profile Time Zone + Latest-First Hotfix

Base: `V2.6.1 RACE RESULTS PERSONAL BEST MILESTONES`

## Profile time zone
- Added person-level `time_zone` field to Driver Profile.
- Uses IANA time-zone names such as `Asia/Kolkata`, `Europe/London`, `America/New_York`.
- Existing profiles without the field are repaired non-destructively to `UTC` until the user selects another zone.
- First-run profile setup includes Time Zone.
- Edit Driver Profile includes an editable Time Zone selector.
- Stored timestamps remain UTC. Only presentation is converted.

## Application presentation
The active Driver Profile time zone now drives visible timestamps in:
- Driver Profile Created / Last Active
- Career History timeline and Latest summary
- Native Performance Hub track/session timestamps
- Browser Performance Hub session/review timestamps
- Stored-session reference labels

The browser Performance Hub no longer hardcodes `Asia/Kolkata` / IST.

## Latest-first rule
Record/list/timeline surfaces are newest-first:
- Career History timeline
- recent Performance History sessions
- native track-session list
- browser track-session list

Trend graph source data deliberately remains chronological so trend direction is not reversed.

## Validation
- Focused profile/history/performance tests: 37 passed before final regression.
- New timezone/latest-first tests: 6 passed.
- Full regression: 1,111 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.6.1.3_ACHIEVEMENT_ICONOGRAPHY_HOTFIX.md`

# V2.6.1.3 — Achievement Iconography Hotfix

## Scope
Add deterministic achievement icons to Driver Profile → History milestone cards so each event is easier to scan.

## What changed
- Added `_career_history_icon_spec(event)` in `src/overlay/window.py`.
- Mapped milestone cards to compact icons and accent colors using stored event payload only.
- Added a circular icon badge beside each career-history card while preserving the existing colored category stripe.
- Kept latest-first ordering and existing timezone-aware timestamp formatting untouched.
- Updated the History page note string to `V2.6.1.3`.

## Icon mapping
- Race win / career wins → Trophy (`🏆`)
- Podium → Medal (`🥈`)
- Fastest lap / lap PB → Stopwatch (`⏱`)
- Pole position → Target (`◎`)
- Generic race result → Checkered flag (`🏁`)
- Skill milestone → Up-right arrow (`↗`)
- Track skill PB → Star (`★`)
- Session-count milestone → Check mark (`☑`)
- Other career milestones → Diamond (`◆`)

## Validation
- `python -m py_compile src/overlay/window.py src/career_history.py`


---

## Archived source: `CHECKPOINT_V2.6.1.4_NATIVE_ACHIEVEMENT_ICONS_HISTORY_TOP_FIX.md`

# V2.6.1.4 — Native Achievement Icons + History Top Fix

Base: V2.6.1.3 Achievement Iconography Hotfix

## Fixes
- Replaced Windows emoji-based History icons with native Qt-painted line icons.
- Added dedicated native icons for trophy/win, stopwatch/lap PB, target/pole, medal/podium, checkered flag/result, skill improvement, track PB, session milestone and general career milestone.
- Removed dependency on `Segoe UI Emoji` rendering for Career History.
- Fixed the newest History card being partially clipped by resetting the History scroll viewport to the top after dynamic rebuild.
- Latest-first event ordering, profile timezone conversion, event generation and scoring logic are unchanged.

## Validation
- Full regression: 1,111 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.6.1_RACE_RESULTS_PERSONAL_BEST_MILESTONES.md`

# V2.6.1 — Race Results & Personal Best Milestones

Base: `V2.6.0 CAREER_HISTORY_MILESTONES`

## Added
- Career History now reads the linked LIVE Performance History in addition to Skill Evidence/Trends.
- Finalized LIVE result milestones:
  - Grand Prix / race win
  - First Grand Prix win
  - P2/P3 podium
  - Pole position from completed qualifying
  - Race fastest lap when Final Classification proves the player set the field fastest lap
- Track lap personal-best milestones:
  - first stored LIVE timed lap establishes the track PB
  - later faster stored LIVE laps create a new PB milestone
- HISTORY summary now exposes Race Results and Lap PB counts separately.
- New history categories/colors for race results and lap PBs.

## Race-fastest-lap authority
`SessionSummaryTracker` now compares `m_bestLapTimeInMS` across the authoritative Final Classification packet for Race/Race 2/Race 3. The persisted summary stores:
- `race_fastest_lap`
- `race_fastest_lap_s`

Historical sessions that predate this field are not guessed to have race fastest lap.

## Safety / integrity rules
- Replay data is not used.
- P1 only becomes a win when the stored session result is Finished.
- Pole only comes from completed qualifying P1.
- Lap PBs use measured positive `best_lap_s` values in chronological LIVE history.
- No synthetic/backdated race-fastest-lap claims.

## Validation
- Focused session-summary/performance-history/history tests: 31 passed.
- Full regression: 1,105 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.7.0.1_MULTI_DRIVER_BUTTON_LABEL_VISIBILITY_HOTFIX.md`

# V2.7.0.1 — Multi-Driver Button Label Visibility Hotfix

Base: V2.7.0 Multi-Driver Switching

## Fixed
- Replaced multi-driver text actions that incorrectly used the overlay icon-button helper.
- Added application-sized `_driver_action_button()` for person-level Driver actions.
- Fixed visible labels for:
  - SWITCH DRIVER (top profile bar)
  - SWITCH (driver card)
  - + NEW DRIVER
  - CLOSE
  - CREATE DRIVER
  - CANCEL
  - CHOOSE AVATAR
  - CLEAR
- Preserved all V2.7.0 switching/context-isolation logic.

## Validation
- Focused multi-driver tests: 5 passed.
- Full regression: 1,116 passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.7.0.2_DRIVER_SWITCHER_DARK_BACKGROUND_HOTFIX.md`

# V2.7.0.2 — Driver Switcher Dark Background Hotfix

Base: V2.7.0.1 Multi-Driver Button Label Visibility Hotfix

## Fixed
- Explicitly themed the Switch Driver `QScrollArea` viewport/content surface.
- Removed the native Windows white background from unused space below Driver cards.
- Added matching dark vertical-scrollbar styling.
- Kept multi-driver ownership/switching logic unchanged.

## Validation
- Focused multi-driver tests: 6 passed.
- Full regression: 1,117 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.7.0_MULTI_DRIVER_SWITCHING.md`

# V2.7.0 — Multi-Driver Switching

Base: `V2.6.1.4 NATIVE ACHIEVEMENT ICONS HISTORY TOP FIX`

## Added
- Permanent `SWITCH DRIVER` control beside the compact Driver Profile card.
- Card-based Driver switcher using the existing Control Center dark UI language.
- `+ NEW DRIVER` flow available from the switcher.
- New Driver creation includes:
  - Display name
  - Country / region
  - Preferred units
  - Time zone
  - Active game
  - Optional avatar
- Switching changes the complete person-level context:
  - Driver ID
  - active Game Profile
  - profile time zone
  - Performance Hub owner
  - Skill Evidence
  - F1 Driver Skill
  - Skill Trends
  - Track Performance
  - Career History / milestones
- Creating another Driver starts with a fresh, empty Performance Hub owner. Existing Driver history is never copied or reassigned.
- Duplicate person display names remain supported because persistent Driver ID is the real identity.

## New architecture
- `src/driver_context.py`
  - `DriverContextManager.create(...)`
  - `DriverContextManager.activate(...)`
  - repairs missing legacy Performance History links with a new empty owner instead of adopting another Driver's history.
- `PerformanceHistoryStore.create_distinct_user_profile(...)`
  - guarantees a new compatibility owner even if the visible person name duplicates an existing one.

## Validation
- Focused multi-driver + existing foundation tests: 9 passed.
- Full regression: 1,115 tests passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.7.1.1_NEW_DRIVER_TIMEZONE_FALLBACK_HOTFIX.md`

# V2.7.1.1 — New Driver Time Zone Fallback Hotfix

Base: `V2.7.1 DRIVER DELETE ROUNDED ACTION BUTTONS`

## Fixed
- Restored the bundled IANA timezone database fallback that was accidentally lost when the V2.7 multi-driver branch was created.
- New Driver creation now uses the same timezone resolver as Driver Profile editing.
- `Asia/Kolkata` and other IANA zones work on Windows even when the Python/system zoneinfo database is unavailable.
- Existing UTC storage and profile-local display conversion remain unchanged.

## Regression coverage
- Forced no-system-zoneinfo test for `Asia/Kolkata` during new Driver creation.
- Bundled timezone DST validation remains covered.

## Validation
- Focused timezone + multi-driver tests: 13 passed.
- Full regression: 1,124 passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.7.1_DRIVER_DELETE_ROUNDED_ACTION_BUTTONS.md`

# V2.7.1 — Driver Delete + Rounded Action Buttons

Base: `V2.7.0.2 DRIVER SWITCHER DARK BACKGROUND HOTFIX`

## Added
- Permanent Driver deletion from the Switch Driver dialog.
- Two-step confirmation before destructive delete.
- Delete removes the selected Driver's complete `drivers/<DRIVER_ID>` tree.
- Delete also removes the linked Performance Hub owner and only that owner's sessions.
- Orphaned legacy game-driver lookup rows are cleaned after owned-session deletion.
- Active Driver deletion switches to another valid Driver first.
- Deleting the last remaining Driver is blocked.
- Switcher shows a DELETE action on every Driver card; disabled when only one Driver exists.

## UI
- Driver action buttons now use an 11 px corner radius.
- Top SWITCH DRIVER button height increased to 42 px for the same rounded application-control language as the profile card.
- Added red/danger styling for destructive Driver deletion.

## Validation
- Focused multi-driver suite: 9 passed.
- Full regression: 1,120 passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.8.0_S5_STORAGE_MANAGER_FOUNDATION.md`

# V2.8.0 — Server Roadmap S5 StorageManager Foundation

## Scope
- Added `src/storage_manager.py` as the single storage-abstraction owner.
- Added explicit states: LOCAL, CACHED, REMOTE, PENDING_SYNC, OFFLINE_FALLBACK.
- Routed `app_paths` through `DEFAULT_STORAGE` without changing live telemetry behavior.
- Centralized the existing LIVE Performance History DB path behind the manager; no S9 migration performed.
- Added local-only roadmap-facing helpers (`get_track_map`, `get_reference`, `save_session`, `save_recording`, `save_performance`, `queue_upload`, `sync_pending`).
- `queue_upload` only writes a local manifest; `sync_pending` intentionally performs zero network I/O until S6.

## Safety / architecture
- No HTTP, socket, Samba, mapped-drive, or server filesystem dependency was added to live Race Engineer code.
- Existing deterministic Race Engineer, Corner Coach, strategy, telemetry and audio behavior is unchanged.
- S6 is responsible for asynchronous/background remote synchronization and offline fallback execution.


---

## Archived source: `CHECKPOINT_V2.8.1_S6_BACKGROUND_SYNC_OFFLINE_FALLBACK.md`

# V2.8.1 — S6 Background Sync + Offline Fallback

Implemented from the validated V2.8.0 S5 StorageManager base.

## Scope
- Durable local pending queue with immutable staged payload copies.
- Background-only server synchronization; no network I/O in telemetry-critical modules.
- Offline fallback retains pending work across restarts.
- Server upload verification by size + SHA-256 before pending payload cleanup.
- Duplicate prevention for identical queued work and already-verified remote files.
- One-time current-local-data backup snapshot queued automatically on first V2.8.1 run.
- Backup target: `R:\backups\client_snapshots\<gaming-pc>\...` by default on Windows.
- Override share path with `RACE_ENGINEER_SERVER_SHARE`.
- Disable sync with `RACE_ENGINEER_SERVER_SYNC=0`.

## Local backup contents
The initial snapshot includes mutable `user_data`, `settings`, `analysis`, and remaining legacy mutable recording/reference folders when present. SQLite files are snapshotted using SQLite backup where possible.

## Manual validation
- `python -m src.server_sync --status`
- `python -m src.server_sync --backup-now`
- `python -m src.server_sync --sync-now`

The active local performance SQLite database is not moved to Samba; S9 remains responsible for authoritative performance-database migration.


---

## Archived source: `CHECKPOINT_V2.8.2_S7_BULK_HISTORICAL_DATA_MIGRATION.md`

# Checkpoint V2.8.2 — S7 Bulk Historical Data Migration

## Scope
Implements Server Roadmap S7 on top of the validated S5 StorageManager and S6 verified background sync/offline fallback transport.

## Server destinations
- Historical `.areplay` files -> `R:\data\replays\...`
- Other recording-side files -> `R:\data\recordings\...`
- Validation artifacts -> `R:\data\validation\...`
- Historical logs -> `R:\data\logs\...`
- Exports -> `R:\data\exports\...`
- Local backup artifacts -> `R:\backups\client_data\<PC>\...`

## Safety rules
- Current/recent recordings remain local while active.
- Recording candidates must be stable for 120 seconds before S7 queues them.
- S7 uses the S6 verified `.part` -> SHA-256/size verification -> atomic publish path.
- Historical migration references stable source files directly instead of duplicating multi-GB files into the pending payload cache.
- S7 does not delete migrated local sources. They remain as compatibility/cache copies for the existing replay/session UI until a later retention/cache phase explicitly changes this policy.
- No server/network access was added to the UDP telemetry path.

## Migration registry
`user_data/cache/server_sync/bulk_migration.json`

Tracks source size/mtime and remote destination so unchanged files are not re-queued. If a historical artifact changes, the changed version is queued again and atomically replaces the server copy after verification.

## CLI
```powershell
.\.venv\Scripts\python.exe -m src.server_sync --migration-status
.\.venv\Scripts\python.exe -m src.server_sync --migrate-now
.\.venv\Scripts\python.exe -m src.server_sync --sync-now
```

## Tests
- S5/S6/S7 focused suite: 18 passed.
- Full regression: 1,142 passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.9.0.2_SERVER_STATUS_ACCURACY_HOTFIX.md`

# V2.9.0.2 Server Status Accuracy Hotfix

- Dedicated API latency timing; UI no longer reports full coordinator-cycle time as Ping.
- SERVER tab shows Sync State, Pending Files, Pending Data, Current Transfer, Last Sync, Last Backup, Performance DB.
- Pending breakdown distinguishes S7 historical migration from normal S8/S9/S14 sync.
- Current .part transfer progress is surfaced when observable.
- Last Backup displays WAITING FOR FIRST BACKUP until server timer publishes a timestamp.
- Startup banner updated to V2.9.0.2.
- Focused tests: 26 passed.
- Full regression: 1150 passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.9.0.3_NATIVE_PERFORMANCE_HUB_RESTORE_HOTFIX.md`

# V2.9.0.3 Native Performance Hub Restore Hotfix

- Restores the native Qt Control Center PERFORMANCE HUB.
- Native hub continues to read local LIVE PerformanceHistoryStore data.
- Native hub Open in Browser uses the gaming-PC LAN dashboard.
- SERVER tab Open Performance Hub remains the separate server-hosted S14 browser hub.
- Server availability can no longer replace the Control Center Performance Hub UI.


---

## Archived source: `CHECKPOINT_V2.9.0.5_DRIVER_PROFILE_SERVER_MIGRATION.md`

# V2.9.0.5 — Driver Profile Server Migration

- Publishes the complete local `user_data/drivers` tree as a verified ZIP snapshot over the S14 API.
- Server atomically replaces `/srv/race-engineer/data/drivers` only after verification.
- Person-level Driver IDs are normalized into the server SQLite database and exposed at `/api/profile-drivers`.
- A full-tree snapshot propagates Driver deletion without a separate remote delete queue.
- Local Driver files remain the offline cache/fallback.
- Server backend revision: S14.1.
- Full regression: 1,155 tests + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.9.0.6_PROFILE_DRIVER_SCHEMA_ISOLATION_HOTFIX.md`

# V2.9.0.6 — Profile Driver Schema Isolation Hotfix

- S14.2 server schema adds dedicated `profile_drivers` table.
- Driver Profile snapshots no longer delete/replace the legacy/session `drivers` table.
- Existing session foreign keys cannot block person-level Driver Profile publication.
- `/api/profile-drivers` and health `driver_profiles.driver_count` use `profile_drivers`.
- Existing `/api/drivers` behavior remains unchanged.
- Driver tree still publishes atomically to `/srv/race-engineer/data/drivers`.


---

## Archived source: `CHECKPOINT_V2.9.0.7_S12_BACKUP_RECOVERY_VALIDATION.md`

# V2.9.0.7 — S12 Backup / Recovery Validation

- Added SERVER tab BACKUP NOW action.
- Added S14.3 `/api/backup` endpoint; backup starts detached and never blocks the gaming PC UI.
- Server backup now uses SQLite backup API + `PRAGMA quick_check` verification.
- Driver/reference/track/setup/server archives are verified by listing and extracting into a temporary restore directory.
- Backup writes `BACKUP_STATUS.json`, `LAST_SUCCESS_UTC`, and `LAST_VERIFY_UTC`.
- Retention target remains 7 daily / 4 weekly / 3 monthly.
- `/api/health` exposes backup verification state.
- SERVER tab displays verification beside Last Backup.
- Stale `PENDING_SYNC` with zero pending files is normalized immediately to `REMOTE` in both coordinator and UI refresh.
- Server backend version: S14.3.
- Full regression: 1156 passed, 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.9.0_S8_S14_CONSOLIDATED_SERVER_PLATFORM.md`

# V2.9.0 — S8-S14 Consolidated Server Platform

- S8: references/track data are mirrored as server master copies while local cache remains race-time authority.
- S9: LIVE Performance History SQLite is snapshotted with sqlite3 backup and published over HTTP to server-local storage.
- S10: Control Center/browser uses the server Performance Hub first, with local fallback.
- S11: SERVER tab shows API/database/sync/pending state and provides Sync/Open Hub/Open Folder controls.
- S12: server deployment kit installs daily backup timer with daily/weekly/monthly retention.
- S13: server integration remains outside live telemetry path; automated regression tool included.
- S14: server is persistent-data authority; gaming PC remains live-processing authority with offline fallback.

One-time deployment after installing this client build:
1. Copy `server_deploy` to race-server.
2. On race-server run `bash install_s14.sh` from that folder.
3. On gaming PC run `python -m src.server_platform` is not required; normal app startup starts background coordinator.


---

## Archived source: `CHECKPOINT_V2.9.1.0_STORAGE_RETENTION_DRIVER_SOFT_DELETE.md`

# V2.9.1.0 Storage Retention + Driver Soft Delete

## Storage retention
- Server remains the long-term master for historical replays/recordings, validation, logs, exports and backups.
- Gaming PC retains the newest 10 replay sessions locally after verified server migration.
- Older replay/sidecar pairs are removed locally only after the exact tracked local version has a verified server copy.
- Historical validation files, logs, exports and local backup artifacts are removed locally after verified server migration.
- References, track maps, Driver Profiles and live/current-session data remain cached/local for race-time and offline fallback.
- Server-only replays remain selectable; selection hydrates the replay back to the local cache before playback.

## Driver Profile deletion
- Local Driver Profile and linked local Performance Hub owner are removed immediately after confirmation.
- A durable local deletion tombstone is written before destructive local cleanup.
- The server soft-deletes the Driver into /srv/race-engineer/data/deleted_drivers/<driver_id>.
- A point-in-time server Performance History SQLite snapshot is retained with the deleted Driver.
- Active API/profile listing hides soft-deleted Drivers immediately.
- Recovery retention is 30 days; expired server recovery copies are purged automatically on server activity.
- Server publishing of post-delete Driver/Profile and Performance DB snapshots is held until every pending deletion tombstone is acknowledged, preserving recovery data during outages.
- Normal automated backup retention is unchanged; old backup archives expire on their existing 7 daily / 4 weekly / 3 monthly schedule.

## Server
- API version S14.4.
- Database schema version 4.
- Adds profile_driver_deletions.
- Adds POST /api/profile-drivers/{driver_id}/delete.
- Adds GET /api/profile-drivers/deleted.
- Adds POST /api/profile-drivers/purge.
- Automated backups include deleted_drivers during their retention period.

## Validation
- Focused storage/server/multi-driver regression: 48 passed.
- Full regression: 1,162 passed + 383 subtests passed.


---

## Archived source: `CHECKPOINT_V2.9.1.1_NONBLOCKING_SYNC_DARK_TAB_TRANSITIONS.md`

# V2.9.1.1 — Non-Blocking Sync + Dark Tab Transitions

- SYNC NOW wakes the existing background server coordinator and never runs server/file work on the Qt UI thread.
- Button shows SYNCING… temporarily and remains responsive.
- Performance Hub and Help WebEngine pages remain loaded between tab changes; no forced reload on tab switch.
- Dark background is applied to QTabWidget pane, page containers, and WebEngine pages to remove white transition flashes.
- Focused regression: 32 passed.
- Full regression: 1165 passed + 383 subtests.


---

## Archived source: `CHECKPOINT_V2.9.1.2_S13_LIVE_TELEMETRY_FRESHNESS_PERFORMANCE_HUB_AUTO_REFRESH.md`

# V2.9.1.2 — S13 Live Telemetry Freshness + Performance Hub Auto Refresh

## S13 live-latency correction
- Live UDP reception now drains the kernel receive queue before decoded/state work.
- Duplicate high-rate state families (Motion, Lap, Car Telemetry, Motion Ex, Lap Positions, Car Telemetry 2) are coalesced to their newest waiting frame.
- Low-rate session/event/status/damage/history/tyre evidence is never coalesced.
- Raw `.areplay` recording and packet capture remain lossless because every datagram is handed to raw consumers before live-state coalescing.
- This prevents the UI/state pipeline from replaying seconds of stale telemetry after F1 is paused when processing temporarily falls behind.
- Status diagnostics expose the cumulative stale-frame coalescing count.

## Performance Hub selection refresh correction
- View-lap and analysis-reference selectors refresh review data immediately.
- Both `input` and `change` are handled for QWebEngine/native select compatibility.
- Rapid selection changes are coalesced into one reload.
- In-flight review requests are aborted and guarded by a monotonically increasing request sequence, so an older/slower response cannot overwrite the newest selected lap/reference.
- Review API requests include a cache-busting query token in addition to `cache: no-store`.

## Preservation
- No deterministic Race Engineer, Corner Coach, scoring, strategy, reference-selection authority, or persistent-history rules changed.
- Server remains outside the live telemetry authority path.


---

## Archived source: `CHECKPOINT_V2.9.1.3.1_S13_HISTORICAL_SYNC_QUEUE_HOTFIX.md`

# V2.9.1.3.1 — S13 Historical Sync Queue Hotfix

## Base
V2.9.1.3 is the protected working base. No telemetry, radio, Race Engineer, Corner Coach, strategy, replay, or Performance Hub behavior is changed by this hotfix.

## Observed failure
A sync run could report hundreds of successful transfers yet still finish with hundreds of HIST files pending. The app started the legacy S6/S7 background sync worker and the S8-S14 platform coordinator; the platform coordinator created a second independent `ServerSyncWorker`, so two workers with different locks could process the same pending queue while historical discovery was also adding entries.

Mutable historical logs/validation/exports/backups were also queued as direct-source S7 entries. If one changed after queueing, strict verification could leave it permanently failed.

## Fix
- ServerPlatformCoordinator now reuses the process-wide default ServerSyncWorker instead of creating a second transport worker.
- Mutable historical classes are staged as immutable snapshots; large stable replay/recording files remain direct-source.
- Legacy direct-source mutable historical queue entries are repaired into immutable staged snapshots on the next sync.
- Superseded snapshots targeting the same historical remote path are compacted so only the newest pending version is transferred.
- Queue-maintenance counts are exposed in `--sync-now` output.

## Protected behavior
No changes to UDP telemetry, PTT/STT/TTS, automatic engineer, coaching, strategy, reference logic, scoring, replay, Driver Profile, Skill, or Performance Hub behavior.


---

## Archived source: `CHECKPOINT_V2.9.1.3.2_S13_ORPHAN_QUEUE_RECOVERY_HOTFIX.md`

# V2.9.1.3.2 — S13 Orphan Queue Recovery Hotfix

Base: V2.9.1.3.1 S13 Historical Sync Queue Hotfix.

## Scope
Server/storage sync only. No changes to radio/PTT/STT/TTS, live telemetry, Race Engineer, Corner Coach, strategy, reference, scoring, replay, Driver Profile, Skill, or Performance Hub behavior.

## Issue
A durable pending-sync manifest could survive after its local upload payload disappeared. This produced permanent `PENDING_SYNC` entries with `Pending payload missing` and increasing retry counts. A common case was temporary `logs/ptt/*.wav`; another was a staged validation transcript whose cached payload was no longer present.

## Fix
- If the payload is missing but the remote destination already matches the manifest size + SHA256, complete the manifest as already verified.
- If a mutable historical staged payload is missing and the original source still exists, retire the broken manifest, create a fresh immutable snapshot, and sync that snapshot.
- If both payload and original source are gone for disposable historical classes (`validation`, `historical_log`, `export`, `backup`), retire the impossible orphan rather than retrying forever.
- Replay/recording entries remain strict and are never silently pruned.
- Exclude transient `logs/ptt/*.wav` microphone captures from historical bulk migration so they cannot create new orphan sync entries.

## Validation
- Targeted S6/S7/S13 regression: 23 passed.
- Full project regression: 1177 passed, 383 subtests passed, 0 failed.


---

## Archived source: `CHECKPOINT_V2.9.1.3.3_PERFORMANCE_HUB_REACTIVE_SELECTION_TRACK_CONTEXT_RESET.md`

# V2.9.1.3.3 — Performance Hub Reactive Selection + Track Context Reset Hotfix

Base: V2.9.1.3.2 S13 Orphan Queue Recovery Hotfix.

## Scope
Performance Hub UI/state only. No changes to telemetry, radio/PTT/STT/TTS, Automatic Engineer, Corner Coach, strategy, reference compiler, scoring model, replay processing, server sync, Driver Profile or Skill engines.

## Issues fixed
1. Lap and Analysis Reference selectors appeared to require the manual Refresh button.
   - Root cause: the reactive selector handler called `setReviewBusy(...)`, but that function did not exist. The browser raised a JavaScript `ReferenceError` before `loadReview()` ran.
   - Fix: add the missing busy-state helper and make selector changes call the review reload path directly.
   - The duplicate `input` + `change` listeners were simplified to one `change` listener per selector.

2. Switching tracks could leave the previous track's SESSION PERFORMANCE review visible.
   - Fix: a track-context change now cancels any pending review request, clears review/session/lap/reference/corner/telemetry state immediately, and closes the stale review before loading the new track.
   - Driver/session-group/game-mode changes use the same reset path.
   - Track fetches are sequence guarded and abort the prior request so a slower old-track response cannot overwrite the newly selected track.

## Expected behavior
- Selecting another VIEW lap automatically reloads the session review; no manual Refresh is required.
- Selecting another Analysis Reference automatically reloads the comparison; no manual Refresh is required.
- Switching tracks immediately removes the previous SESSION PERFORMANCE review.
- The review stays blank/closed until the user selects a session belonging to the newly selected track.
- Rapid track switching cannot render an out-of-order old-track response.


---

## Archived source: `CHECKPOINT_V2.9.1.3.4_SYNC_OWNERSHIP.md`

# V2.9.1.3.4 — S13 Cross-Process Sync Ownership Hotfix

Base: V2.9.1.3.3.

## Proven issue
When Race Engineer was open, its background S7/S6 server worker and a separate
`python -m src.server_sync --sync-now` process could mutate the same local
pending-sync queue concurrently. The symptom was a successful manual run that
reported every attempted item synced while hundreds of new pending items were
added at the same time. With Race Engineer closed, the same queue drained to
`REMOTE / pending 0 / failed 0`, proving a cross-process ownership race.

## Fix
- Added a local atomic file ownership guard at
  `user_data/cache/server_sync/sync_owner.lock`.
- S6 upload/repair/completion/retention work now has one process owner.
- S7 bulk historical discovery/queueing respects the same owner.
- S8 reference/track queueing respects the same owner.
- Initial backup queue creation and standalone retention respect the same owner.
- A competing process returns `SYNC_BUSY` without mutating the queue or
  overwriting the active sync status.
- Stale locks from a dead process are reclaimed safely.
- Server Platform treats a busy transport as active/online (`SYNCING`), not as a
  server outage.

## Preserved
No changes to UDP telemetry, radio/PTT/STT/TTS, Automatic Engineer, strategy,
Corner Coach, references/scoring behavior, replay, Driver Profile/Skill logic,
or Performance Hub behavior from V2.9.1.3.3.

## Validation
- Cross-process ownership regression tests added.
- Focused server/storage suite: 37 passed.
- Full suite: 1184 passed + 383 subtests passed, 0 failed.

## Acceptance test
1. Start Race Engineer normally and leave it running.
2. In a second PowerShell window run:
   `\.\.venv\Scripts\python.exe -m src.server_sync --sync-now`
3. If the app owns sync at that instant, CLI must return `SYNC_BUSY` with zero
   attempted/synced/failed. If the lock is free, CLI may own the run and sync.
4. Re-run `--status`; queue must not balloon/repopulate because of the second
   process.
5. Allow normal background sync to finish and confirm `REMOTE / pending 0 /
   failed 0`.


---

## Archived source: `CHECKPOINT_V2.9.1.3_S13_SYNC_VERIFICATION_REPAIR.md`

# V2.9.1.3 — S13 Sync Verification Repair

## Purpose
Fix the S13 blocker where staged mutable files could remain in PENDING_SYNC forever with `Remote verification failed after copy`.

## Root cause
`StorageManager.queue_upload()` hashed and sized the live source before copying it into immutable staging. Append-only validation logs and other mutable files could change between those operations, leaving a staged payload whose bytes did not match its manifest.

## Changes
- Stage mutable uploads first, then compute SHA-256 and size from the staged snapshot.
- Self-repair legacy staged manifests by recalculating hash/size from the staged payload before upload.
- Preserve strict verification for non-staged historical migration sources.
- Process pending manifests chronologically so repeated snapshots targeting the same remote path finish with the newest queued state.
- Preserve V2.9.1.2 live telemetry freshness and Performance Hub auto-refresh fixes.

## Validation
- py_compile: PASS
- focused storage/sync tests: 14 passed
- full regression: 1169 passed + 383 subtests

## S13 status
Retest after pending queue reaches REMOTE / 0 pending.


---

## Archived source: `CP_V291351.md`

# V2.9.1.3.5.1 — S13 Sync Performance + Server Status Authority Hotfix

Base: V2.9.1.3.4.

Changes:
- retains V2.9.1.3.4 cross-process sync ownership;
- adds bounded background batches and continuous backlog draining;
- skips historical rescans while a queue is already draining;
- throttles retention maintenance until the queue is idle;
- removes redundant staged/local and post-publish SMB hashing while preserving remote temp SHA256 verification;
- preserves V2.9.1.3.4 server-platform fresh transport/status authority (`run_once()`), reverting the stale-status regression introduced in V2.9.1.3.5.

Packaging:
- runtime sync/status cache and Python/test caches are excluded from the release package.


---

## Archived source: `CP_V2913510_PERFORMANCE_DATA_CONSISTENCY.md`

# V2.9.1.3.5.10 Performance Data Consistency Hotfix

Scope: keep Performance Hub and Driver Profile derived skill/track data consistent after local session or track deletion.

Changes:
- Performance History remains authoritative.
- Skill Evidence rows with an exact `performance_history_session_id` that no longer exists are removed from the active Skill Evidence index.
- Raw evidence JSON is retained on disk for forensic recovery; only active derived indexing is removed.
- Session delete and track delete APIs immediately trigger Skill Evidence reconciliation and skill/trend rebuild.
- No telemetry, radio/PTT, Corner Coach, strategy, scoring, reference capture, or server sync core logic changed.

Validation:
- 46 focused tests passed across Performance Hub deletion, Skill Evidence, Driver Skill, Skill Trends, Track Skill, and track identity reconciliation.


---

## Archived source: `CP_V2913511_OFFLINE_SYNC_STATUS_AUTHORITY.md`

# V2.9.1.3.5.11 — Offline Sync Status Authority Hotfix

Scope is limited to S13/S14 server-status authority.

- LOCAL FALLBACK / API OFFLINE always exposes sync state OFFLINE_FALLBACK, even if a local queue worker returns SYNC_BUSY.
- SYNCING is shown only while the platform is online and work is actually pending/owned.
- Failed API connection timeout duration is no longer presented as Ping; offline Ping is `--`.
- Queue contents and sync worker behavior are unchanged.
- No telemetry, radio/PTT, coaching, strategy, scoring, reference, or performance-history logic changed.


---

## Archived source: `CP_V2913512_SESSION_AGGREGATE_AUTHORITY.md`

# V2.9.1.3.5.12 — Session Aggregate Authority Hotfix

Scope: Performance Hub session aggregation only.

- Per-lap eligibility, technique score, confidence, score weights, deadbands, corner scoring and quality gates are unchanged.
- Session Technique is rebuilt only from persisted score-bearing lap summaries.
- Session Confidence is rebuilt only from those same laps using the existing robust aggregation.
- Cached reviews with valid individual lap scores but stale/missing session aggregates are repaired at read time.
- Session eligible-lap display is synchronized with persisted score-bearing laps.
- No telemetry, radio/PTT, Corner Coach, strategy, reference, server sync or core scoring changes.


---

## Archived source: `CP_V2913513_SESSION_AGGREGATE_LAP_SCORE_TABLE.md`

# V2.9.1.3.5.13 — Session Aggregate + Lap Score Table Hotfix

## Scope
- Preserve all existing per-lap scoring, confidence, eligibility, weighting, deadband and grading logic.
- Fix session aggregation only.
- Session overall consumes the exact persisted per-lap score/confidence shown by the individual LAP view.
- Handle persisted `lap_reviews` where the lap number is stored on the outer row rather than duplicated inside `summary`.
- Add a SCORE column to SESSION LAP TIMES using those same persisted per-lap scores.
- N/A remains N/A; no score is fabricated and no lap is rescored.

## Protected core
No change to:
- corner scoring
- lap scoring
- confidence calculation
- data-quality/eligibility gates
- Corner Coach
- Race Engineer
- strategy/radio/PTT
- server sync/storage


---

## Archived source: `CP_V2913514_SESSION_BEST_AUTHORITY_SCORE_CONSISTENCY.md`

# V2.9.1.3.5.14 — Session Best Authority + Score Consistency Hotfix

Scope is deliberately narrow.

## Fixed
- Performance History session best is owned by valid completed laps from that stored session when lap evidence exists.
- A faster Time Trial personal/track best from Final Classification can no longer replace the selected session's own best lap.
- Existing persisted sessions are repaired in either direction from their own lap telemetry; repair no longer assumes a numerically faster stored value is always more authoritative.
- Session History, Session Overall Best Lap, session-best selector, and reference-gap read paths are synchronized to the same session-scoped best-lap authority.
- V2.9.1.3.5.13 lap-score aggregation and SCORE table behavior are preserved.

## Not changed
- Corner scoring model
- Lap score calculation
- Lap eligibility/data-quality gates
- Confidence calculation
- Robust session score aggregation math
- Corner Coach / Race Engineer / strategy / radio / PTT
- Server sync ownership/queue behavior

## Regression target
Catalunya 11-lap Time Trial case:
- current-session Lap 10 = 1:17.489
- unrelated/personal best = 1:17.212
- session best must remain 1:17.489
- theoretical = 1:17.488
- potential gain = 0.001 s
- existing seven scored laps continue to aggregate to the session technique result without rescoring.


---

## Archived source: `CP_V2913515_TECHNIQUE_PROFILE_EVIDENCE_DIAGNOSTIC.md`

# V2.9.1.3.5.15 — Technique Profile Evidence Diagnostic

## Scope
Performance Hub UI-only clarification. No score, confidence, lap eligibility, corner scoring, telemetry, coaching, strategy, radio/PTT, or server-sync logic is changed.

## Change
The Technique Profile empty state now reports the actual gate used by the radar: at least 3 technique groups must have numeric scores. It exposes the persisted `sample_count` for all technique groups and marks each group as `available` or `needs 3`.

This replaces the misleading generic text `Not enough multi-lap technique evidence.` with diagnostic evidence such as:

- `2 of 7 technique groups have sufficient repeated evidence. At least 3 available groups are required.`
- `Braking: 6 trusted samples · available`
- `Trail braking: 1 trusted sample · needs 3`

The existing backend rule remains unchanged: each technique group score is available only when its underlying dimension evidence has at least 3 trusted samples.


---

## Archived source: `CP_V2913516_LAP_SCORE_NA_DIAGNOSTIC.md`

# V2.9.1.3.5.16 — Lap Score N/A Diagnostic

Scope: Performance Hub presentation/read-path only.

Changes:
- Preserve the existing authoritative persisted per-lap score; no score/confidence recalculation.
- Expose stored scored-corner count, eligible-corner count, coverage and quality reasons in the Session Lap Times read model.
- When SCORE is N/A, show compact captured coverage as `N/A · scored/eligible` when available.
- Add a hover diagnostic explaining the persisted reason, including minimum scored-corner failure, <60% coverage, invalid lap, quality exclusion, or absence of stored corner-scoring coverage.
- No changes to scoring thresholds, weights, confidence math, lap/session aggregation, data-quality gates, Corner Coach, strategy, radio/PTT, telemetry, or server sync.

Validation:
- focused new diagnostic tests: 4 passed
- broader Performance Hub/scoring regression set: 32 passed
- Python compile check passed


---

## Archived source: `CP_V2913517_LAP1_PIT_OWNERSHIP_HOTFIX.md`

# V2.9.1.3.5.17 — Lap 1 Pit Ownership Hotfix

## Scope
Fix only first timed-lap ownership of startup/out-lap pit state.

## Issue
EA can expose lap 1 while the car is still in the garage/pit-exit startup phase. The recorder previously latched `pit_lap=True` before the first real start/finish timing anchor and carried that flag into the completed timed lap, making lap 1 ineligible for scoring.

## Fix
- When the first clean S/F anchor is reached on an already-observed unanchored lap, discard pre-anchor samples and reset pre-anchor quality flags.
- If startup pit status was present, ignore only that carry-over until pit status first clears.
- After pit status clears, the existing sticky pit-lap behavior resumes unchanged.
- A genuine later pit entry on the timed lap still sets `pit_lap=True` and remains excluded by the existing data-quality gate.

## Protected behavior unchanged
No changes to:
- lap/corner scoring formula
- score weights/deadbands
- confidence formula
- 60% scored-corner coverage requirement
- minimum scored-corner requirement
- session aggregation
- Corner Coach logic
- strategy/radio/PTT/server sync

## Validation
Focused regression suite: 35 passed.
Includes tests for:
1. startup/out-lap pit carry-over does not contaminate lap 1;
2. stale pit status after the first timing anchor is ignored only until it clears;
3. real pit entry later in lap 1 still marks the lap as a pit lap;
4. normal later-lap pit semantics remain unchanged.


---

## Archived source: `CP_V2913518_V207_PRACTICE_PLANNER.md`

# V2.9.1.3.5.18 / V2.0.7 Practice Planner

## Scope
Implements the original V2.0.7 roadmap item on top of the protected V2.9.1.3.5.17 baseline.

This is an integration feature only. It consumes existing measured evidence and does not introduce a second coaching/scoring engine.

## Added
- `src/practice_planner.py`
  - deterministic 20-minute planner
  - reuses quality-eligible laps
  - reuses recurring measured-loss patterns and ranked opportunities
  - reuses existing coaching-priority/next-lap-focus decisions
  - maximum two next-lap focus items
  - primary issue chosen from highest-priority active recurring measured weakness
  - secondary issue only after primary verification
  - existing +/- 0.015 s measured issue-cost trend deadband used for verification
  - no generic coaching recommendation when evidence is insufficient
- Performance Hub `PRACTICE` review tab
  - Plan status
  - Baseline evidence
  - Estimated 20-minute lap count
  - Remaining measured opportunity
  - Existing next-lap focus (max 2)
  - Baseline / Primary / Verification / Secondary / Summary timeline
  - Primary and secondary measured issue cards
  - Verification contract
- Practice plan persisted into newly saved Performance Review reports.
- Existing stored sessions receive a read-only plan at review time from their persisted measured evidence.

## Explicitly unchanged
The following protected core files are byte-for-byte unchanged from V2.9.1.3.5.17:
- `src/performance_scoring.py`
- `src/data_quality.py`
- `src/lap_stint_intelligence.py`
- `src/coaching_priority.py`
- `src/corner_coach.py`
- `src/race_state_receiver.py`

No changes to:
- score weights/deadbands
- lap/session score aggregation
- confidence formula
- eligibility gates
- Corner Coach detection/diagnosis
- radio/PTT
- strategy
- server sync
- reference selection/scoring authority

## Changed existing source files
- `src/performance_history.py` — expose practice plan in review payload only
- `src/performance_hub_ui.py` — PRACTICE tab and renderer only
- `src/session_coach_report.py` — persist planner output alongside existing review

## Validation
- Python compileall: PASS
- V2.0.7 focused test: PASS
- Recent scoring/session/lap-state regression suite: 33 passed
- Performance/Performance Hub regression suite: 82 passed

## Roadmap
V2.0.7 is now implemented for deterministic post-session 20-minute planning using the existing measurement and coaching-priority engines.
Next roadmap item: V2.0.8 Setup Lab.


---

## Archived source: `CP_V2913519_V207_PRACTICE_PLANNER_REFINEMENT.md`

# V2.9.1.3.5.19 — V2.0.7 Practice Planner Refinement

## Scope
UI/integration refinement only. Protected V2.0.6.4-era score, confidence, Corner Coach, coaching-priority and data-quality logic is unchanged.

## Fixes
- Reconciles Practice Planner with existing next-lap coaching priority when recurring-pattern history is absent.
- Such a focus is explicitly PROVISIONAL and must gain repeat clean-lap evidence before being treated as a recurring practice issue.
- Falls back to existing Performance Review measured opportunities if report-side opportunity ranking is absent.
- Clearly separates immediate next-lap focus from multi-lap structured-practice focus.

## UI
- Semantic phase colors: baseline blue, primary red, verification cyan, secondary amber, summary green.
- Interactive 20-minute practice clock with start/pause/reset and live phase/progress indication.
- Focus cards can be selected as the current practice focus.
- Focus cards can jump directly to the corresponding corner review.
- AI Practice Brief added through the existing local Ollama explanation path. AI receives deterministic plan facts only and cannot change issue selection or measured values.

## Validation
- New Practice Planner refinement tests: PASS.
- Focused score/session/lap-state regression: PASS.
- Python compileall: PASS.
- Browser JavaScript syntax check: PASS.
- Full suite: 1233 passed + 383 subtests; 2 failures reproduced unchanged on V2.9.1.3.5.18 baseline (legacy HID config-export expectation and old DB schema-version=4 expectation).


---

## Archived source: `CP_V2913520_V207_PRACTICE_PLANNER_FINAL_POLISH.md`

# V2.9.1.3.5.20 — V2.0.7 Practice Planner Final Polish

## Scope
Final V2.0.7 Practice Planner UI/workflow polish only. Protected scoring, confidence, data-quality, Performance History, Corner Coach, coaching-priority, lap/stint and race-state behavior remains byte-for-byte unchanged from V2.9.1.3.5.19.

## Changes
- Renamed the pace-only 20-minute estimate to **MAX TIMED LAPS** and explicitly states that pit/out-lap time is excluded.
- Manual focus selection is now visibly identified as **MANUAL FOCUS** and is persisted as a UI override only; deterministic evidence/ranking is not modified.
- Next-lap cards carry an **IMMEDIATE** badge; recurring structured-practice cards carry a **RECURRING** badge; provisional evidence remains explicitly marked.
- Practice timer is explicitly labeled **MANUAL PRACTICE TIMER** in the historical Performance Hub review context.
- Phase cards now show **CURRENT / COMPLETE / UPCOMING** state with stronger active highlighting and completed-phase checkmarks.
- READY status explains why the plan is ready by including eligible baseline-lap count and recurring-target count.
- Remaining Opportunity uses amber/opportunity styling instead of error-like red styling.
- Verification wording is user-facing while retaining the exact existing 0.015 s threshold.
- Secondary-selection contract is now documented: next-highest independently measured corner issue; the same technique may legitimately appear at a different corner when ranked next by measured evidence.
- AI Practice Brief now has READY / GENERATING / GENERATED / UNAVAILABLE states and displays the deterministic evidence used for the explanation. Manual focus override does not silently alter AI planner authority.

## Protected core verification
Byte-for-byte unchanged from V2.9.1.3.5.19:
- performance_scoring.py
- data_quality.py
- performance_review.py
- performance_history.py
- corner_coach.py
- coaching_priority.py
- lap_stint_intelligence.py
- race_state_receiver.py

## Validation
- New V2.0.7 polish tests: PASS
- V2.0.7 + session/score/lap-state focused regression: 28 passed
- Python compileall: PASS
- Browser JavaScript syntax (`node --check`): PASS
- Full suite: 1237 passed + 383 subtests; 2 failures
- The same 2 failures reproduce on V2.9.1.3.5.19 baseline:
  - legacy HID config-export expectation
  - legacy schema-version test expecting v4 while current DB schema is v6


---

## Archived source: `CP_V2913521_V207_TRACK_PRACTICE_WORKSPACE.md`

# V2.9.1.3.5.21 — V2.0.7 Track Practice Workspace

## Requirement
Practice Planner is track-specific, not session-specific. It consumes all stored LIVE Performance History sessions for the selected local driver and track. Older evidence contributes recurrence/trend history, while the newest session determines whether a weakness is still current. Practice is exposed as a dedicated Control Center tab next to Performance Hub.

## Changes
- Added dedicated Control Center `PRACTICE` tab after `PERFORMANCE HUB`.
- Added local dashboard `/practice` page and `/api/practice/track` endpoint.
- Added `PerformanceHistoryStore.practice_track_detail()` read path.
- Added `build_track_practice_plan()` integration layer.
- Current recurring issues must still be observed in the newest stored session; older-only issues are retained as `resolved_or_not_current` history and cannot remain current practice targets.
- Historical observations strengthen recurrence and track improving/stable/regressing direction.
- Latest-session opportunities / coaching-priority remain the current deterministic authority when repeated history is insufficient.
- AI Practice Brief can explain the track-level deterministic plan but cannot alter its targets or measurements.
- Removed visible session-level PRACTICE button from Performance Hub review tabs. Existing hidden compatibility markup remains non-navigable.

## Protected core
Unchanged from V2.9.1.3.5.20:
- performance_scoring.py
- data_quality.py
- performance_review.py
- corner_coach.py
- coaching_priority.py
- lap_stint_intelligence.py
- race_state_receiver.py

`performance_history.py` changed only to add the explicitly required track-scoped Practice read endpoint; no score/confidence/session-save logic was modified.

## Validation
- Track Practice focused regression: 24 passed.
- Full suite: 1242 passed, 383 subtests passed, 2 pre-existing failures.
- Pre-existing failures are unchanged: legacy HID export expectation and old schema-version-v4 assertion while current schema is v6.
- Python compileall: PASS.
- Practice page JavaScript syntax: PASS.


---

## Archived source: `CP_V2913522_V207_TRACK_PRACTICE_AUTHORITY_HOTFIX.md`

# V2.9.1.3.5.22 — V2.0.7 Track Practice Authority Hotfix

## Scope
Narrow Practice-workspace correction only. No changes to protected scoring, confidence, Corner Coach, coaching priority, lap/stint intelligence, race-state, radio, strategy, or telemetry core.

## Fixes
- Practice Driver selector now comes from authoritative `DriverProfileStore`, not historical Performance History identity rows.
- Driver Profile UUID is resolved through `compatibility.performance_history_profile_id` for Practice history reads.
- Track Practice states are separated into READY, PROVISIONAL, NO CURRENT ISSUE, and INSUFFICIENT.
- A current issue observed in only one stored session is PROVISIONAL until confirmed across another stored session.
- A track with adequate eligible evidence but no surviving newest-session issue is NO CURRENT ISSUE, not INSUFFICIENT.
- Practice summary now shows CURRENT FOCUS COST from the selected current primary issue instead of unrelated theoretical-lap potential.
- Practice timestamps are presented in the selected Driver Profile timezone.
- Latest-session immediate items are presentation-deduplicated when the same corner/time-cost is represented by equivalent diagnoses.
- AI Practice Brief is constrained to the final deterministic current primary/secondary plan. It cannot promote historical or immediate items. A NO CURRENT ISSUE state returns a deterministic clear-state brief without calling the LLM.

## Protected core verification
Byte-for-byte unchanged from V2.9.1.3.5.21:
- `src/performance_scoring.py`
- `src/data_quality.py`
- `src/performance_review.py`
- `src/corner_coach.py`
- `src/coaching_priority.py`
- `src/lap_stint_intelligence.py`
- `src/race_state_receiver.py`

## Validation
- Focused Practice + score/session/lap regression: 37 passed.
- New V2.9.1.3.5.22 authority tests: passed.
- Full suite: 1246 passed, 383 subtests passed, 2 pre-existing failures.
- Pre-existing failures reproduced: HID config export expectation; legacy schema-v4 expectation while current DB schema is v6.
- Python compile checks: PASS.
- Practice JavaScript syntax check (`node --check`): PASS.


---

## Archived source: `CP_V2913523_V207_PRACTICE_REFERENCE_AUTHORITY.md`

# V2.9.1.3.5.23 — V2.0.7 Practice Reference Authority

- Adds an explicit rival/reference selector to the top-level PRACTICE workspace.
- One selected rival becomes the Practice benchmark for the track.
- Cross-session Practice aggregation includes only stored sessions whose recorded external reference is verified compatible with the selected rival.
- Compatibility uses stored reference speed-trace identity when available, with an external-reference lap-time fallback for legacy compact history.
- Sessions with a different or unverifiable reference are shown as excluded rather than silently mixed.
- Existing session scores, Performance History records, Corner Coach, scoring/confidence, and reference files are not mutated or recalculated.
- AI Practice Brief receives the same selected Practice reference authority.

Important historical limitation: compact Performance History stores distance-domain overlay channels but not the full raw time-domain lap trace needed to losslessly re-run every historical corner diagnosis against a rival that was not the session's recorded reference. This release therefore refuses to mix incompatible references rather than fabricating cross-reference comparability.


---

## Archived source: `CP_V2913524_V207_PRACTICE_REFERENCE_LEGACY_RECOVERY.md`

# V2.9.1.3.5.24 — V2.0.7 Practice Reference Legacy Recovery

Purpose: restore track-level Practice plans for historical sessions that contain valid measured practice evidence but pre-date persistent rival-reference identity metadata.

Rules:
- Selected Practice Reference remains the benchmark/confirmation authority.
- Exact reference trace or matching stored reference lap time = VERIFIED history.
- Historical rows with no contradictory reference but missing identity metadata may contribute LEGACY PROVISIONAL evidence.
- Legacy evidence can never make the track plan READY by itself; a new verified session against the selected rival must confirm it.
- Explicitly conflicting stored reference traces/times remain excluded.
- No scoring, confidence, Corner Coach, coaching-priority, telemetry, radio, or strategy core changes.
- Practice status pill layout fixed so it remains a compact badge instead of stretching vertically.


---

## Archived source: `CP_V2913525_V207_TRACK_PRACTICE_WEATHER_SESSION_POLICY.md`

# V2.9.1.3.5.25 — V2.0.7 Track Practice Weather + Session Policy

## Purpose
Fix Track Practice so it is materially different from the old single-session planner: it aggregates eligible evidence across supported live session types for one driver + game profile + track, keeps weather conditions separate, and uses the selected rival as benchmark/confirmation authority without discarding older valid track evidence merely because an older session used another/unknown rival.

## Practice evidence policy
Included session types:
- Time Trial
- Free Practice
- Qualifying

Excluded session types:
- Race (including clean-air race laps)
- Sprint / Sprint Race
- Replay-derived sessions
- Unsupported/unknown session types

Existing lap quality gates remain authoritative inside included sessions, including pit, invalid, traffic-compromised, race-control-compromised, damage-compromised, replay-seek, partial/missing telemetry and related exclusions.

## Weather authority
- Practice evidence is bucketed as DRY / WET / UNKNOWN.
- Dry and wet evidence are never aggregated together.
- Practice UI has a TRACK CONDITION selector with stored-session counts.
- The selected condition is shown in the Practice scope and benchmark cards.
- New session lap facts now persist track_condition/weather_name/weather_code so future history retains explicit condition metadata.

## Reference behavior
- Selected rival remains the Practice benchmark and confirmation authority.
- Exact trace/time match = verified evidence.
- Older track+condition sessions with useful measured diagnoses but a different/unknown stored rival are retained as legacy provisional evidence instead of being discarded.
- Legacy evidence cannot by itself promote the plan to READY.
- Historical issues are not retired merely because an unverified/thin latest session omits them. Retirement requires sufficiently measured verified newer evidence.

## UI changes
- Shows Track + condition scope.
- Shows included/excluded session policy.
- Shows usable laps, verified-to-selected-rival count, legacy provisional count, weather-excluded count, and excluded-session-type count.
- Practice reference is stored per driver + track + condition.

## Protected core
Byte-for-byte unchanged from V2.9.1.3.5.24:
- performance_scoring.py
- data_quality.py
- performance_review.py
- corner_coach.py
- coaching_priority.py
- lap_stint_intelligence.py
- race_state_receiver.py

## Validation
- Focused Practice/Performance regressions: 54 passed.
- Python compileall: PASS.
- Practice JavaScript syntax: PASS.
- Protected core comparison: PASS.


---

## Archived source: `CP_V2913526_PRACTICE_REF_SCORE_DIAG.md`

# V2.9.1.3.5.26 — Practice Reference + Score Diagnostics Hotfix

## Trigger
Catalunya retest on V2.9.1.3.5.25 after deleting older sessions and recording a new dry Time Trial plus wet Practice session.

Observed from the supplied UI evidence:
- F1-valid laps could still show `SCORE N/A`, including rows with full recorded corner coverage such as `N/A · 14/14`.
- The wet Practice bucket had 5 game-valid laps but 0 coaching-eligible laps, so the deterministic planner correctly had no measured evidence from which to build a plan; the UI did not expose the concrete exclusion reasons.
- Practice Reference was effectively forced toward the installed/current Time Trial rival even for WET, although Time Trial provides a dry/ideal-condition reference.

## Root cause / contract clarification
Game lap validity and coaching-score eligibility are intentionally separate. The persisted score is suppressed when the lap fails a coaching data-quality gate even if all corner measurements were captured. V2.9.1.3.5.25 showed only counts, which made this look like a scoring failure.

The Practice workspace also exposed only installed rival/reference files. It did not offer same-condition stored session bests as first-class Practice References, and its condition switch could retain a previously selected dry reference when moving to WET.

## Changes
- Added same-condition `Session best` entries to the Practice Reference selector.
- Practice references are weather-scoped: a known DRY installed reference is not offered as the WET Practice benchmark.
- Default selection keeps the current rival for DRY when compatible; WET/UNKNOWN prefers the newest same-condition session best.
- Switching Practice condition now clears a stale reference unless that condition already has its own saved selection.
- Sessions with quality-eligible laps but no surviving weakness are now usable Practice evidence, allowing a deterministic `NO CURRENT ISSUE` result instead of being dropped as "no practice evidence".
- Added Practice quality diagnostics: timed-valid count, coaching-eligible count, excluded count, aggregate exclusion reasons, and per-lap exclusion reason samples.
- Performance Hub Data Quality now displays aggregate exclusion reasons.
- Quick-glance `SCORE N/A` explanation now prioritizes persisted quality-gate reasons over generic corner-coverage wording. No score is recalculated or fabricated.
- AI Practice Brief request now carries the selected weather condition.

## Protected core
No changes were made to:
- `src/performance_scoring.py`
- `src/data_quality.py`
- `src/performance_review.py`
- `src/corner_coach.py`
- `src/coaching_priority.py`
- `src/lap_stint_intelligence.py`
- `src/race_state_receiver.py`

This is a read/integration/UI hotfix; scoring thresholds, telemetry capture, live coaching and existing quality gates remain unchanged.

## Validation
New regression tests cover:
- WET defaulting to a same-condition Session Best while excluding a known DRY Time Trial rival from the WET Practice selector.
- DRY retaining the compatible current rival default while also offering Session Best.
- clean quality-eligible sessions remaining usable even with no current issue.
- Practice quality-exclusion diagnostics.
- full-corner-coverage `SCORE N/A` showing the actual quality exclusion reason.
- selected condition reaching the AI Practice Brief request.

Targeted Practice/authority suite: 15 passed.

Full suite comparison:
- V2.9.1.3.5.25 baseline: 1249 passed, 6 failed, 383 subtests passed.
- V2.9.1.3.5.26: 1254 passed, 6 failed, 383 subtests passed (5 new tests added).
- The same 6 pre-existing baseline failures remain; no new full-suite failure was introduced by this hotfix.


---

## Archived source: `CP_V2913527_TRAFFIC_LAPDATA.md`

# V2.9.1.3.5.27 — Practice Traffic + LapData Integrity Hotfix

Base: V2.9.1.3.5.26.

## Reproduced issues
1. A wet Practice session could show every game-valid lap as `traffic_compromised`, leaving 0 coaching-eligible laps and therefore no Practice plan.
2. Some valid Time Trial laps could be rejected as `missing_distance_packets` after the S13 live-UDP freshness optimization coalesced LapData to only the newest waiting frame.

## Traffic-quality correction
- Time Trial never rejects a lap from traffic-gap state.
- Practice and Qualifying ignore rear proximity as a lap-quality blocker.
- Practice and Qualifying require the car ahead to remain below the existing 1.0 s close-gap threshold for at least 2.0 continuous seconds before `traffic_compromised` is latched.
- Traffic duration is advanced only by a new LapData frame. Motion/telemetry packets cannot make one stale gap observation look sustained.
- Race and unknown-session behavior keep the existing strict immediate front/rear traffic rule.
- Per-lap factual traffic evidence is retained: minimum front/rear gap, maximum continuous close-front duration and the trigger used.

## LapData integrity correction
- Packet ID 2 (LapData) is removed from newest-only live UDP coalescing.
- Motion, Car Telemetry, Motion Ex, Lap Positions and Car Telemetry 2 remain coalesced exactly as before to preserve the S13 anti-backlog behavior.
- Raw recording/capture behavior remains unchanged and lossless.
- UDP diagnostics now retain coalesced counts by packet family and report LapData as protected.
- The existing `missing_distance_packets` quality threshold is unchanged; this fixes the ingestion cause instead of weakening the quality gate.

## Protected-core scope
This is an explicitly justified post-V2.0.6.4 core-path correction for reproduced quality exclusions.

Unchanged:
- `performance_scoring.py`
- `data_quality.py`
- `performance_review.py`
- `corner_coach.py`
- `coaching_priority.py`
- `lap_stint_intelligence.py`
- Practice-plan selection/scoring thresholds

Changed only where required:
- `src/measured_performance.py` — session-aware traffic evidence/qualification
- `src/race_state_receiver.py` — protect LapData from newest-only live coalescing + diagnostics
- `src/udp_receiver.py` — per-family coalescing counters only
- new regression tests

## Historical-session rule
Previously stored laps already marked `traffic_compromised` cannot be safely reclassified because the old build did not retain enough duration/direction evidence to prove that the traffic flag was false. Do not rewrite them. Validate this fix with a new Practice session; older sessions remain historical evidence.

## Validation
Targeted traffic/UDP/local-polish regression: 19 passed.
Practice/performance related regression: 117 passed; 3 environment-only historical-version path tests failed because their sibling V2.9.1.3.5.18/.19/.20 folders are not present in the isolated package tree.

Full-suite comparison in the same environment:
- V2.9.1.3.5.26: 1255 passed, 5 failed, 383 subtests passed.
- V2.9.1.3.5.27: 1262 passed, 5 failed, 383 subtests passed.
- The same 5 pre-existing failures remain; no new full-suite failure was introduced.


---

## Archived source: `CP_V2913528_PRACTICE_INTEGRITY.md`

# V2.9.1.3.5.28 — Practice Integrity Hotfix

Scope is intentionally narrow. The V2.9.1.3.5.27 LapData anti-coalescing fix is preserved.

Changes:
- Practice/Qualifying traffic exclusion now uses physical circuit position to identify a genuinely close car ahead. Rear cars do not invalidate a lap. Close-ahead traffic must persist for 2.0 s.
- Practice Session Best references are selected only from coaching-eligible laps; a faster excluded/N/A lap cannot become the practice reference.
- Late sector-only Session History updates now refresh completed-lap sector values.
- Potential/theoretical lap is clamped so it can never be slower than the best eligible observed lap, including repair/read paths for stored sessions.
- Practice primary/secondary targets cannot be two diagnoses of the same corner and phase.
- Practice summary remaining-opportunity uses the current measured primary issue cost when available, avoiding a 0.000 s contradiction while a measured issue exists.

Protected scoring/data-quality/coach core thresholds were not weakened.

Regression result:
- Focused affected-area tests: 26 passed.
- Full suite: 1268 passed, 6 pre-existing failures, 383 subtests passed.
- Baseline V2.9.1.3.5.27: 1261 passed, the same 6 failures, 383 subtests passed.


---

## Archived source: `CP_V2913529_REALTIME_TRACK_TRAFFIC_SYNC.md`

# V2.9.1.3.5.29 — Real-time Track + Practice Traffic Sync

- Performance History row id is attached to live Skill Evidence immediately.
- Skill Evidence is reconciled after each live/final history save.
- Legacy unlinked Unknown evidence can be repaired by unique session UID; stale Unknown rows are de-indexed when Performance History has no Unknown session.
- Driver Profile track choices are sourced from authoritative Performance History, while Skill Evidence remains the score source.
- Practice traffic interaction window tightened from ~1.0 s / 100 m to ~0.7 s / 55 m maximum, while preserving the 2.0 s sustained requirement and rear-car immunity.
- V2.9.1.3.5.27 LapData non-coalescing protection remains unchanged.


---

## Archived source: `CP_V2913531_V209_V210_SKILL_HUB_RECONCILIATION.md`

# V2.9.1.3.5.31 — V2.0.9 Driver Skill Reconciliation + V2.0.10 Performance Hub Integration

Base: frozen `V2.9.1.3.5.29` / V2.0.7 Practice Planner.

- V2.0.8 Setup Lab is intentionally skipped and is not included in this build.
- Adds a reconciliation/presentation layer over the existing Skill Evidence, Driver Skill, Skill Trends and LIVE Performance History. No second telemetry detector or career scoring engine was added.
- Reconciles the original V2.0.9 domains. Domains without dedicated persisted evidence (Trail Braking, Line Consistency) remain explicit N/A instead of being guessed from neighbouring scores.
- Exposes latest session, recent robust average, personal best, five-session trend, recurring weakness, recently solved issue, and track-specific measured opportunity reduction.
- Performance History remains the authoritative session/track identity; Skill Evidence is reconciled before progress is presented.
- Adds `/api/performance/progress` and a Performance Hub PROGRESS workspace. Practice remains the already-frozen standalone Control Center PRACTICE workspace; Performance Hub links to it rather than duplicating its logic.
- Replay remains read-only for persistent skill/history.


---

## Archived source: `CP_V2913532_V209_CANONICAL_SKILL_RECONCILIATION.md`

# V2.9.1.3.5.32 — V2.0.9 Canonical Driver Skill Reconciliation Hotfix

## Scope
Corrects V2.9.1.3.5.31 so Driver Profile and Performance Hub do not present two different Driver Skill models.

## Changes
- Performance Hub Driver Progress now consumes the canonical F1 Driver Skill categories only:
  Pace, Consistency, Braking, Corner Entry, Apex / Minimum Speed, Traction / Exit, Car Control, Racecraft, Tyre Management, Wet Driving.
- Removed Hub-only alternate Driver Skill categories such as Trail Braking and Line Consistency from the Driver Skill cards. Those remain diagnostic concepts elsewhere, not career skill scores.
- Global progress uses F1DriverSkillModel values directly.
- Track-scoped progress uses TrackSkillStore / SkillTrendStore values directly.
- Track scope no longer mixes global Formula Driver Skill with track-scoped session counts/opportunity data.
- Progress cards now distinguish stored evidence sessions from scoreable snapshots.
- Domain cards show canonical current value, personal best, five-session change and scoreable snapshot count.
- Driver Profile sync indicator is a status pill, not an action button.
- Driver Profile Trends label changed from `SESSIONS SHOWN` to `SNAPSHOTS SHOWN`, matching what is actually plotted.
- Added evidence diagnostics confirming that Wet Driving, Racecraft and Tyre Management remain N/A when no dedicated Skill Evidence producer exists. No synthetic score is created.
- V2.0.7 Practice Planner remains frozen and untouched.

## Validation
- Canonical reconciliation/track-scope/UI tests: 23/23 passed in the focused suite before the final label patch; final related suite 18/18 passed.
- Full suite: 1278 passed + 383 subtests, 6 failures.
- The six full-suite failures are pre-existing/environmental: config-export HID expectation, legacy schema-version expectation, three missing prior-build comparison folders, and storage-retention expectation.
- No protected scoring/coaching core file was modified by this hotfix.


---

## Archived source: `CP_V2913533_RELEASE_DATA_PRESERVATION_HOTFIX.md`

# V2.9.1.3.5.33 — Release Data Preservation Hotfix

## Root cause
The manually-created V2.9.1.3.5.32 FULL archive incorrectly included mutable runtime data, including `analysis/performance_history_live.sqlite3` and `user_data/`. The packaged SQLite database was an empty development/test database. Extracting that archive over an existing Race Engineer installation could therefore overwrite the user's authoritative local performance database and make Performance Hub / Driver Skill appear empty.

This violated the already-established productization rule that upgrades must preserve mutable user data.

## Fix
No V2.0.6.4-era runtime/core behavior was changed.

The V2.9.1.3.5.33 source release package excludes mutable/runtime locations:
- `analysis/`
- `user_data/`
- `settings/`
- `recordings/`
- `logs/`
- `references/`
- `maps/`
- `.venv/`, caches and generated bytecode

Extracting this package over the existing project therefore updates source/assets without replacing the user's local database, Driver Profile tree, settings, recordings, references, maps or sync cache.

## Important recovery note
If V2.9.1.3.5.32 has already overwritten `analysis/performance_history_live.sqlite3`, simply installing .33 cannot reconstruct those already-overwritten local bytes. Restore the database from the server-published snapshot / latest backup, then start .33. Driver Profile data may also need restoration if its `user_data/drivers` tree was overwritten or removed.

## Validation
The existing productization preservation contract remains authoritative: installer upgrades exclude settings, recordings, analysis, logs, references and maps. The .33 manual source archive now follows the same preservation principle and additionally excludes `user_data`.


---

## Archived source: `CP_V2913534_V209_V210_FINAL_RECONCILIATION_HOTFIX.md`

# V2.9.1.3.5.34 — V2.0.9 / V2.0.10 Final Reconciliation Hotfix

## Scope
Focused follow-up to V2.9.1.3.5.33 after restored real user data exposed the remaining reconciliation edge cases. V2.0.7 Practice remains frozen. No deterministic scoring, coaching, radio, strategy or replay core was changed.

## Fixes
1. **Performance History owns Skill Evidence session identity**
   - An unlinked legacy Skill Evidence row that cannot be mapped unambiguously to an existing Performance History session is now removed from the active evidence index even when it carries a plausible track name such as Catalunya.
   - The evidence JSON remains on disk for forensic recovery; it is not deleted.
   - Historical backfill recreates authoritative evidence from current LIVE Performance History rows.
   - This removes ghost/duplicate track-session counts such as 9 Catalunya evidence sessions when Performance Hub owns only 8 Catalunya sessions.

2. **Stored vs scoreable evidence wording**
   - Driver Profile Skills footer now labels the raw persisted count as **STORED EVIDENCE SESSIONS**.
   - Formula Driver Skill coverage now explicitly says **scoreable evidence sessions**.
   - This makes the intentional difference between stored history and score-producing evidence clear.

3. **Measured Time Recovered direction**
   - The deterministic calculation still clamps recovered time to >= 0.
   - The result now also publishes `direction = improved | worsened | unchanged` and the raw change.
   - Performance Hub no longer says an opportunity "reduced" when it actually increased. Worsening now reports the increase and leaves recovered time at 0.000 s.

4. **Driver Profile header clipping**
   - Added extra right-side layout margin so the EDIT PROFILE button remains inside the visible page at the affected Control Center widths/zoom levels.

## Preservation
The V2.9.1.3.5.34 release archive follows the V2.9.1.3.5.33 data-preservation rule and excludes mutable/runtime locations:
- `analysis/`
- `user_data/`
- `settings/`
- `recordings/`
- `logs/`
- `references/`
- `maps/`
- `.venv/`, caches and bytecode

Installing this source package over an existing project must not overwrite the restored Performance History database, Driver Profile tree, settings or recordings.

## Validation
- New focused hotfix tests: **4 passed**.
- Skill/reconciliation affected-area suite: **46 passed**.
- Full suite: **1283 passed + 383 subtests, 5 failures**.
- The 5 failures are the same pre-existing/environmental failures: legacy HID config-export expectation, old DB schema-version expectation, and three source-protection tests requiring unavailable historical `.18/.19/.20` folders.
- No new regression was introduced by this hotfix.


---

## Archived source: `CP_V2913535_SKILL_UI_POLISH.md`

# V2.9.1.3.5.35 — V2.0.9/V2.0.10 Skill UI Polish

## Scope
Focused polish only on the already reconciled Driver Skill / Performance Hub presentation. No scoring, coaching, Practice Planner, telemetry, race-engineer, or persistence authority changes.

## Fixes
- Performance Hub trend wording now uses the actual number of scoreable trend points used by the rolling comparison.
  - 3 available points -> `3-session ...`
  - 5 or more available points -> `5-session ...`
  - fewer than 2 points -> `trend N/A`
- Domain-card evidence count now says `domain evidence snapshots` so it cannot be confused with the Overall scoreable-snapshot total.
- Driver Profile skill headers increased from 8pt to 10pt and given a brighter muted label color for readability.
- Driver Profile evidence-detail text increased from 7pt to 8pt.
- Performance Hub skill-domain labels increased from 10px to 12px.

## Preservation
- V2.0.7 Practice Planner remains frozen and untouched.
- Protected scoring/coaching core remains untouched.
- Release package excludes mutable user/runtime data (`analysis`, `user_data`, `settings`, `recordings`, `logs`, `references`, `maps`).

## Validation
Targeted reconciliation/UI tests: 14 passed.
Full suite: 1287 passed + 383 subtests; 5 existing unrelated/environmental failures remain unchanged:
1. legacy config-export HID-map expectation;
2. old schema-version expectation (`4` vs current `6`);
3-5. three source-protection tests requiring unavailable sibling builds .18/.19/.20.

## User validation
Check Driver Profile > Skills and Performance Hub > Driver Progress:
- skill labels should be visibly larger;
- Austria with 3 available domain points should show `3-session`, not `5-session`;
- evidence wording should say `domain evidence snapshots`.


---

## Archived source: `CP_V2913536_ONE_CLICK_SERVER_BACKUP_RESTORE.md`

# V2.9.1.3.5.36 — One-Click Server Backup Restore

## Scope
Adds recovery UI before V2.0.11 final validation. No scoring, coaching, Practice Planner, telemetry, or Driver Skill calculation logic was changed.

## User workflow
SERVER tab now contains:
- RECENT BACKUP selector sourced from the existing mapped server backup folder (`R:\\backups\\automated` by default);
- RESTORE SELECTED one-click action;
- REFRESH BACKUPS action;
- Restore Status field.

The list uses existing automated S12 backup generations. No server-side upgrade is required for this feature.

## Restore behavior
When RESTORE SELECTED is used:
1. Restore is blocked while a live F1 telemetry session is active.
2. A local rollback snapshot is created first under `user_data/backups/pre_restore_<UTC>`.
3. The selected `performance_history_live_<timestamp>.sqlite3` is copied locally and verified with SQLite `PRAGMA quick_check`.
4. Matching `drivers_<timestamp>.tar.gz` is safely extracted when present.
5. Local Performance History and Driver Profile data are atomically replaced.
6. Skill Evidence is reconciled against restored Performance History.
7. Existing verified S9 snapshot publishing republishes the restored Performance DB and Driver Profile tree to the server.
8. Driver Profile, Performance Hub and Practice views refresh without requiring manual restore commands.

If the server API cannot be republished immediately, the local restore remains valid and the UI reports SERVER SYNC PENDING; normal background sync retries later.

## Safety
- No direct write into a live server SQLite file over SMB.
- Uses the server backup share only as a read source.
- Active background Performance/Driver publication is held during restore.
- Path-safe tar extraction.
- Local pre-restore rollback copy is always created before replacement.
- Release package excludes mutable `analysis`, `user_data`, `settings`, `recordings`, `logs`, `references`, and `maps` data.

## Validation
- New restore functional/UI tests: 2 passed.
- Affected server/storage/UI tests: 31 passed.
- Full regression: 1289 passed, 383 subtests passed, 5 pre-existing/environmental failures.
- Existing failures remain the legacy HID export expectation, legacy schema-version expectation, and three protected-core comparison tests requiring absent .18/.19/.20 folders.


---

## Archived source: `CP_V2913537_WINDOWS_LIVE_DB_RESTORE_HOTFIX.md`

# V2.9.1.3.5.37 — Windows Live-DB One-Click Restore Hotfix

## Issue found in real validation
V2.9.1.3.5.36 correctly listed and validated server restore points, but the actual restore attempted to replace `analysis/performance_history_live.sqlite3` with `os.replace()`. On Windows the running Control Center / embedded Performance Hub can retain a read handle to the SQLite file, causing `[WinError 5] Access is denied` even when no F1 session is active.

## Fix
The restore path now uses SQLite's native backup API to restore the verified server backup **into the existing local Performance History database**. It no longer deletes WAL/SHM sidecars or renames/replaces the live database file while the app is running.

This preserves the one-click workflow while remaining compatible with Windows readers already attached to Performance History. A local rollback snapshot is still created first, the incoming backup is still quick-checked, Driver Profiles are still restored, Skill Evidence is reconciled, and the restored state is republished to the server.

## Scope protection
No Practice, scoring, coaching, telemetry, Driver Skill formula, Performance Hub formula, radio, strategy or replay-core behavior changed.

## Packaging
Mutable runtime data remains excluded from the release archive (`analysis`, `user_data`, `settings`, `recordings`, `logs`, `references`, `maps`).


---

## Archived source: `CP_V2913538_V2011_VALIDATION_CALIBRATION_PHASE1.md`

# V2.9.1.3.5.38 — V2.0.11 Validation / Calibration / Source Freeze — Phase 1

## Baseline

- Started from the user-validated and Git-tagged baseline **V2.9.1.3.5.37**.
- `.37` remains the protected functional baseline.
- No scoring, coaching, Practice Planner, Driver Skill, Performance Hub calculation, server-sync or restore behavior is changed in this phase.

## Scope

V2.0.11 is a validation/freeze phase, not a feature-development phase. Phase 1 adds a deterministic audit harness which:

1. captures SHA-256 hashes for protected `.37` source files;
2. maps every automated V2.0.11 acceptance area to existing proven tests;
3. checks that the cancelled **V2.0.8 Setup Lab** has not re-entered the active product;
4. checks release-package hygiene so mutable user/runtime folders cannot be shipped accidentally;
5. separates automated validation from trusted real-recording acceptance;
6. refuses to declare the V2 source frozen until real-recording acceptance and the final full regression are attached.

## Setup Lab

**V2.0.8 remains cancelled by user scope.** The V2.0.11 roadmap item `setup comparability gates` is therefore recorded as **skipped_by_user_scope / N/A**, not reopened.

## New validation assets

- `src/v2_final_validation.py`
- `tools/run_v2_final_validation.py`
- `tests/test_v2011_validation_calibration_freeze.py`
- `V2_SOURCE_FREEZE_MANIFEST.json`
- `V2.0.11_AUTOMATED_VALIDATION_REPORT.json`

## Recording acceptance still required before final freeze

The release environment intentionally contains no private `.areplay` recordings. Final V2.0.11 freeze still requires real-machine acceptance against:

- Melbourne damage / SC / pit evidence;
- Practice -> Qualifying -> Race weekend evidence;
- stored Time Trial / Qualifying / Race recordings;
- CORNER COACH validation corpus.

These are not replaced by synthetic tests.

## Freeze rule

Any source hash change against `V2_SOURCE_FREEZE_MANIFEST.json` must be justified by a reproducible V2.0.11 validation failure or an explicit new requirement. Otherwise revert to the `.37` source.

## Automated validation result

- V2.0.11 targeted acceptance matrix: **92 passed / 0 failed**.
- V2.0.11 harness tests: **5 passed / 0 failed**.
- Full candidate suite: **1295 passed + 383 subtests, 5 failed**.
- `.37` baseline full suite: **1290 passed + 383 subtests, same 5 failed**.
- **New regressions: 0.**
- Source-freeze manifest: **14 protected `.37` files verified byte-for-byte**.
- Setup Lab active files: **0**.

The five full-suite failures are inherited from `.37`: one old HID config-export expectation, one stale schema-v4 expectation while the live schema is v6, and three environment-only comparisons against missing `.18/.19/.20` trees.

## Phase 1 conclusion

Automated V2.0.11 validation is green with no new regression and no calibration change justified. **Do not freeze V2 yet**: trusted real-recording acceptance is still pending.


---

## Archived source: `CP_V2913539_TIME_TRIAL_FIRST_LAP_RIVAL_COACH_HOTFIX.md`

# V2.9.1.3.5.39 — Time Trial First-Lap Rival Coach Hotfix

## Scope
Targeted V2.0.11 acceptance fix only. Protected V2.9.1.3.5.37 core remains unchanged except the reproduced Time Trial first-lap Corner Coach gate.

## Reproduced issue
A stored, already-selected Time Trial rival reference was active before the player's first flying lap, but Corner Coach PRE/POST calls did not begin until lap 2.

## Root cause
`CornerCoachEngine.observe()` applied the generic pit/out-lap suppression policy to every session profile. F1 Time Trial can transiently expose a non-zero pit/garage status while loading directly onto the first flying lap. That latched `_outlap_lap = 1`, suppressing all Corner Coach delivery for lap 1. The latch cleared only when the lap number advanced, so coaching began on lap 2.

## Fix
Pit/out-lap suppression remains unchanged for Practice/Qualifying/Race and other pit-capable sessions. The gate is bypassed for `event_context.profile == "time_trial"`, and any transient startup pit/out-lap latch is cleared so an already-active rival reference can coach from lap 1.

No reference selection, rival recording, coaching diagnosis, scoring, Practice Planner, Performance Hub, Driver Skill, server sync, or restore logic was changed.

## Regression coverage
Added `tests/test_v2913539_time_trial_first_lap_rival_coach.py`:
- Time Trial transient pit/garage status + active external rival => lap-1 PRE remains available.
- Non-Time-Trial pit status => existing out-lap suppression remains intact.

Targeted Corner Coach regression suite: **56 passed**.

## Acceptance expectation
With a previously recorded Monza rival selected and shown as `ACTIVE` before the session/flying lap begins, the first flying lap must be eligible for PRE coaching. No completed player lap is required to unlock that reference.


---

## Archived source: `CP_V291353_S13_ACCEPTANCE_HOTFIX.md`

# V2.9.1.3.5.3 — S13 Status + Recovered Session Aggregate Hotfix

Scope is limited to issues reproduced during the S13 live outage/reconnect acceptance test.

- Server platform polling reduced from 120 s to 10 s so offline/online state is detected promptly in the background.
- During an API outage, the last known verified backup timestamp/status is retained as cached historical metadata; live API/database/storage state still reports offline.
- After resumed/offline Time Trial data is merged, Best and measured sector-theoretical Potential are re-derived from merged completed-lap evidence so Performance Hub cannot retain the pre-outage stint summary.
- Session Best reference options and gaps use the effective best completed lap from merged lap telemetry.
- No Race Engineer, Corner Coach, strategy, reference-capture, radio, telemetry processing, or scoring logic changed.
- Missing sector fields are not fabricated. If a final lap has no persisted sector evidence, the UI remains `--` for those sectors.


---

## Archived source: `CP_V2913540_V2011_TIME_TRIAL_FIRST_TIMED_LAP_ANCHOR_HOTFIX.md`

# V2.9.1.3.5.40 — V2.0.11 Time Trial First-Timed-Lap Anchor Hotfix

## Real-machine failure
With a stored rival reference already selected and active before driving, Time Trial CORNER COACH produced no PRE/POST on the first timed lap and began coaching only on lap 2.

## Root cause
The earlier .39 pit/out-lap hypothesis was incomplete. EA F1 Time Trial can expose `current_lap == 1` while the car is still on the pre-line rolling-start segment near the end of the circuit. At the first real S/F crossing, lap distance wraps to zero while the lap number can remain 1. CORNER COACH interpreted that same-number wrap as a completed lap, set `_awaiting_lap_increment_from = 1`, and then suppressed the whole actual timed lap 1 until the game advanced to lap 2.

`MeasuredPerformance` already had the correct ownership rule from V2.9.1.3.5.17: a numbered lap is not owned as a timed lap until the first clean S/F timing anchor (`distance <= 25 m`, `lap time <= 2 s`). CORNER COACH now follows the same authority.

## Fix
- Track whether the current Corner Coach lap has reached a clean S/F timing anchor.
- If lap 1 was first observed before that anchor, rebase state when the clean anchor arrives with the same lap number.
- Discard the pre-line distance from wrap detection so the real timed lap is not finalized before it starts.
- Preserve any legitimate circular T1 PRE already spoken on the pre-line approach.
- Normal clean-lap S/F wrap handling remains unchanged.
- .39 Time Trial transient pit-status fix remains in place.

## Protected behavior
No scoring formula, Driver Skill, Practice Planner, Performance Hub, server sync/restore, strategy, reference selection, or non-Time-Trial pit/out-lap semantics were changed.

## Validation
- New synthetic reproduction: pre-line lap 1 -> same-number clean S/F -> PRE available on timed lap 1.
- Normal anchored lap wrap still enters the ordinary boundary path.
- Time Trial startup pit gate tests retained.
- Focused Corner Coach/reference suite: 51 passed.
- Full regression: 1297 passed + 383 subtests; 5 known baseline/environment failures remain. Two V2.0.11 freeze-manifest failures caused by this intentional source change were resolved by recording the hotfix as an explicit justified deviation from protected .37.

## Release-data protection
Mutable runtime folders remain excluded from release packaging: `analysis`, `user_data`, `settings`, `recordings`, `logs`, `references`, `maps`, validation bundles/recovery data.


---

## Archived source: `CP_V2913541_CONTROL_CENTER_FIRST_FULLSCREEN_GAME_PROFILE_SELECTOR_HOTFIX.md`

# V2.9.1.3.5.41 — Control Center first-fullscreen + Game Profile selector hotfix

## Scope
UI-only V2.0.11 acceptance fixes on top of the validated V2.9.1.3.5.40 Time Trial first-timed-lap anchor baseline.

## Fix 1 — first maximize/full-screen responsive layout
On Windows the Control Center could receive the top-level resize before the QScrollArea viewport had its final geometry. Responsive cards then measured the old narrow viewport and remained in a one-column/two-column arrangement until the window was minimized/restored.

The Control Center now performs its normal responsive reflow immediately and again after Qt/Windows completes the native maximize/full-screen geometry handshake. Reflow is scheduled on show, WindowStateChange and resize. No telemetry, coaching, scoring, replay, persistence or server behavior is changed.

## Fix 2 — Game Profile checkbox visibility
The Game Profile selector no longer relies on the native Windows checkbox artwork against the dark theme. It has explicit dark-theme indicator states with a cyan checked state and visible border in the unchecked state.

## Protected behavior
- V2.9.1.3.5.40 Time Trial first-lap rival coaching fix unchanged.
- Practice Planner remains frozen.
- Driver Profile / Skill calculations unchanged.
- Performance Hub calculations unchanged.
- Server sync / backup / restore unchanged.
- Release package must exclude mutable runtime data.


---

## Archived source: `CP_V2913542_HARDWARE_WORKSPACE_INTEGRATION.md`

# Checkpoint V2.9.1.3.5.42 — Hardware Workspace Integration

Base: `RE_V2.9.1.3.5.41_CONTROL_CENTER_FULLSCREEN_GAME_PROFILE_SELECTOR_HOTFIX_FULL`

Reference hardware application: `Wheel Companion Ultra Lite V1.5.0 FROZEN Git Ready`

## Explicit scope

This checkpoint implements the requested Hardware separation only:

- Removed the compact **HARDWARE** status card from the **CONTROL** tab.
- Added a dedicated top-level **HARDWARE** tab to Control Center.
- Embedded the three Wheel Companion Ultra Lite hardware pages as Hardware sub-tabs:
  - **HARDWARE**
  - **INPUT CALIBRATION**
  - **INPUT TESTER**
- Brought across the Receiver-side pedal calibration / curve protocol and live hardware diagnostics required by those pages.
- Did not bring across a second app, overlay system, LAN dashboard, replay system, map, coach, or Performance Hub code from Wheel Companion.

## Wheel dashboard telemetry preservation

The physical wheel-dashboard telemetry path is preserved deliberately:

- Race Engineer still owns the authoritative F1 telemetry receiver.
- Hardware UI uses that already-decoded Race Engineer telemetry for display.
- There is **no second UDP listener** in the embedded Hardware workspace.
- Race Engineer and Hardware UI share **one Receiver COM bridge**.
- The proven PC -> Receiver **RE/V1 15-byte telemetry frame** remains unchanged.
- The frame continues at the existing **50 Hz** rate.
- Receiver V8.3.x extended live pedal / MotorTemp and pedal-settings messages are multiplexed through the same serial worker, so calibration cannot fight the wheel-dashboard writer for the COM port.

## Protected-core impact

No scoring, coaching, performance review, practice planning, strategy, race-state calculation, server sync, or telemetry decoding core was changed.

Protected `src/overlay/window.py` changed only because the user explicitly required a new top-level Hardware workspace and removal of the old Control card. This deviation is recorded in `V2_SOURCE_FREEZE_MANIFEST.json`.

`src/wheel_telemetry.py` was upgraded only at the transport boundary so the existing wheel telemetry writer and the Wheel Companion hardware-management protocol share one serial connection. The RE/V1 output contract remains unchanged and the legacy wheel-link tests continue to pass.

## Validation

Targeted regression set: **21 passed** before final freeze-manifest update; final hardware/freeze validation set: **18 passed**.

Full project suite after this checkpoint: **1306 passed + 383 subtests passed**. Six unrelated pre-existing/environment-dependent tests remain red:

- one legacy configuration-export expectation,
- one legacy DB schema-version expectation,
- three historical-version byte-comparison tests whose old extracted folders are not present in this sandbox,
- one storage-retention expectation unrelated to Hardware.

No Hardware integration, wheel telemetry, source-freeze, or Control Center Hardware tests are failing.

The sandbox does not have PySide6 installed, so a live Qt render smoke test could not be executed here; the modified Qt modules were syntax-compiled successfully and the source/static regression suite passed.


---

## Archived source: `CP_V2913543_PRE_CORNER_PHASE_DELTA_BAR.md`

# Checkpoint V2.9.1.3.5.43 — PRE-CORNER Phase Delta Bar

## Requirement
Keep the existing PRE-CORNER phase instruction (BRAKE / TURN-IN / EXIT), but replace the lower whole-corner progress bar with a phase-specific driver-vs-reference comparison.

## Implemented behavior
- BRAKING: compares the driver's first brake application point against the coach/reference brake point.
- TURN-IN / APEX: compares the driver's first steering turn-in point against the trusted reference steering event when available. If reference input telemetry is not trusted (for example rival/ghost input data), the visual comparator falls back to the existing deterministic physical-corner geometry convention rather than inventing steering telemetry.
- EXIT: compares the driver's first throttle pickup point against the coach/reference throttle point.
- Bar center is the REFERENCE target. EARLY is left of center and LATE is right of center.
- Exact distance delta is shown in metres (for example `BRAKE 8 M EARLY`, `TURN-IN MATCHED REF`, `THROTTLE 10 M LATE`).
- If the reference target has already passed before the driver's action occurs, the bar shows a live growing late delta until the actual driver input is captured, then freezes at the real event point.
- The visual marker is clamped to +/-40 m only for drawing; the displayed numeric delta remains the actual value.
- Existing EXIT handoff to POST-CORNER feedback remains unchanged.

## Driver event thresholds used by the visual comparator
- Brake: first brake input >= 0.10 within the active approach-to-apex window.
- Turn-in: first absolute steering input >= 0.08 within the active approach-to-apex window.
- Throttle: first throttle input >= 0.20 from apex through the zone exit (+40 m allowance).
- First detected event is retained so the result does not wander after the action occurs.
- Comparator state resets on lap or coaching-zone change.

## Scope protection
This change is presentation/support only. It does not change CORNER COACH timing, PRE/POST scheduling, diagnosis, scoring, reference selection, voice/TTS, race engineering, Practice Planner, Performance Hub, server sync, Hardware workspace, or wheel-dashboard telemetry.

Protected core files were compared byte-for-byte with V2.9.1.3.5.42 and remain unchanged:
- `src/performance_scoring.py`
- `src/data_quality.py`
- `src/performance_review.py`
- `src/corner_coach.py`
- `src/coaching_priority.py`
- `src/lap_stint_intelligence.py`
- `src/race_state_receiver.py`

Files intentionally changed/added for this checkpoint:
- `src/overlay/window.py`
- `src/overlay/data.py`
- `src/pre_corner_delta.py` (new)
- `tests/test_v2913543_pre_corner_phase_delta_bar.py` (new)
- `V2_SOURCE_FREEZE_MANIFEST.json`
- `CP_V2913543_PRE_CORNER_PHASE_DELTA_BAR.md` (new)

## Validation
Targeted PRE/overlay validation:
- 14 passed.

Freeze + targeted validation:
- 19 passed.

Full V2.9.1.3.5.43 suite:
- 1311 passed
- 383 subtests passed
- 5 failed

Full V2.9.1.3.5.42 baseline suite in the same sandbox:
- 1307 passed
- 383 subtests passed
- the same 5 tests failed

The five remaining failures are baseline/environment-dependent and are not introduced by this checkpoint: one config-export expectation, one legacy schema-version expectation, and three protected-core comparison tests that require sibling historical release directories not present in the sandbox.

## Baseline
V2.9.1.3.5.42 remains the proven Hardware integration baseline. V2.9.1.3.5.43 adds only the PRE-CORNER phase delta presentation/support described above.


---

## Archived source: `CP_V2913544_PRE_CORNER_TRANSITION_READABILITY_HOTFIX.md`

# Checkpoint V2.9.1.3.5.44 — PRE-CORNER Transition + Readability Hotfix

## User issue reproduced from V2.9.1.3.5.43
The PRE-CORNER overlay had two presentation problems:

1. The visible state could appear to jump between BRAKE / TURN-IN / APEX / EXIT because the original coach phase model intentionally grouped several driving actions together. ENTRY and THROTTLE were not presented as their own readable steps.
2. The lower comparator labels and information text were too small for a driving overlay.

## Implemented behavior
The PRE-CORNER overlay now uses a presentation-only six-step sequence:

`BRAKE -> ENTRY -> TURN-IN -> APEX -> EXIT -> THROTTLE`

A compact phase strip shows all six stages and highlights the current stage so the progression is visible instead of looking like unrelated cards.

The main information area was enlarged and the important font sizes were increased. The logical overlay size is now 430 x 224 so the larger text does not collide with the comparator or shared overlay chrome.

## Phase-specific comparator
The lower EARLY / REF / LATE bar remains a driver-vs-reference comparator, never whole-corner progress. Each visible phase now owns the matching event:

- BRAKE -> brake onset point
- ENTRY -> brake release point
- TURN-IN -> steering turn-in point (trusted steering event when available, deterministic geometry fallback otherwise)
- APEX -> driver minimum-speed/apex position versus reference apex position
- EXIT -> throttle pickup point
- THROTTLE -> full-throttle point

The driver event is retained once established, so the displayed delta does not wander after the action is complete. APEX uses the minimum-speed position within the active corner window and freezes once the exit region is reached.

## Scope protection
This is still presentation/support only. It does not change CORNER COACH timing, PRE/POST scheduling, diagnosis, scoring, reference selection, speech/TTS, race engineering, Practice Planner, Performance Hub, server sync, Hardware workspace, or wheel-dashboard telemetry.

Protected core files were compared byte-for-byte with V2.9.1.3.5.43 and remain unchanged:

- `src/performance_scoring.py`
- `src/data_quality.py`
- `src/performance_review.py`
- `src/corner_coach.py`
- `src/coaching_priority.py`
- `src/lap_stint_intelligence.py`
- `src/race_state_receiver.py`

Files intentionally changed/added:

- `src/overlay/window.py`
- `src/pre_corner_delta.py`
- `tests/test_v2913543_pre_corner_phase_delta_bar.py` (extended for superseding phase behavior)
- `tests/test_v2913544_pre_corner_transition_readability.py` (new)
- `V2_SOURCE_FREEZE_MANIFEST.json`
- `CP_V2913544_PRE_CORNER_TRANSITION_READABILITY_HOTFIX.md` (new)

## Validation
Focused PRE / freeze / shared-overlay tests:

- 23 passed

Full suite:

- 1315 passed
- 383 subtests passed
- 5 failed

The five remaining failures are the same baseline/environment-dependent failures documented in V2.9.1.3.5.43: one configuration-export expectation, one legacy schema-version expectation, and three historical protected-core comparison tests whose sibling release directories are not present in the sandbox.

## Baseline
V2.9.1.3.5.42 remains the proven Hardware integration baseline. V2.9.1.3.5.43 introduced the phase delta comparator. V2.9.1.3.5.44 corrects only PRE-CORNER phase presentation/readability and expands the comparator to the six visible driving stages.


---

## Archived source: `CP_V2913545_WEATHER_FUEL_OVERLAY_CLIPPING_HOTFIX.md`

# Checkpoint V2.9.1.3.5.45 — Weather / Fuel Overlay Clipping Hotfix

Base: `RE_V2.9.1.3.5.44_PRE_CORNER_TRANSITION_READABILITY_HOTFIX_FULL`

## Scope

UI-only hotfix for the clipping visible in the WEATHER and FUEL information overlays. No telemetry parsing, race-engineer logic, strategy calculations, hardware support, recording, server sync, coaching logic, or data persistence behavior is changed.

## Changes

- FUEL logical overlay height increased from 300 to 335 px so the non-applicable banner, hero card, metrics and footer no longer force the large fuel values into a compressed/clipped row.
- WEATHER logical overlay height increased from 305 to 330 px so the applicability banner, current-condition card, three forecast cards and footer have independent vertical space.
- WEATHER and FUEL now create their existing footer during construction, before shared overlay zoom captures the visual baseline. This keeps footer fonts/margins/spacing on the same zoom path as the rest of each overlay and avoids late-added layout pressure.
- All existing weather/fuel data, colors, values, strategy applicability text and update logic are retained.

## Regression guard

Added `tests/test_v2913545_weather_fuel_clipping_hotfix.py` to lock the corrected logical heights, early footer creation, three-card weather layout and existing fuel/weather data paths.


---

## Archived source: `CP_V2913546_STABLE_V2_RELEASE_AUDIT_RC1.md`

# CP V2.9.1.3.5.46 — Stable V2 Release Audit RC1

Base: V2.9.1.3.5.45 Weather/Fuel clipping hotfix, user confirmed working.

Automated gate results: 1330 pytest tests passed, 383 subtests passed, V2 matrix 92/92 passed, Windows static packaging checks passed, source freeze passed.

Audit fixes: server-retention first-pass startup correctness; legacy/canonical HID mapping export compatibility; Stable V2 CLI branding; external-dependency Windows bootstrapper packaging; explicit user-data/voice preservation; portable-stage cache cleanup.

`RaceEngineer.exe` is intentionally a small external-dependency bootstrapper. It checks Python 3.13, Python packages, Piper voice, Whisper small.en for PTT/STT, and Ollama/qwen2.5:3b. Missing downloads require user confirmation and are not embedded in the EXE.

Release status: RC1. Hold final Stable V2 Git tag until physical Windows launcher/feature smoke testing and V2.0.11 trusted recording acceptance are complete.


---

## Archived source: `CP_V2913547_STABLE_V2_BRANDING_RC2.md`

# V2.9.1.3.5.47 — Stable V2 Branding RC2

## Scope

This build starts from the user-accepted V2.9.1.3.5.46 Stable V2 RC1 package, which itself contains the confirmed V2.9.1.3.5.45 Weather/Fuel clipping fix.

The .47 change is presentation/release-packaging only:

- adds the official Race Engineer product mark and wordmark under `assets/brand/`
- applies the shared icon to the Qt application so Control Center and overlay windows use the branded taskbar/window icon
- adds a branded Control Center product header with `RACE ENGINEER`, `STABLE V2`, and `Telemetry • Strategy • Coaching`
- standardizes visible native window titles from the legacy `AI Race Engineer - ...` format to `Race Engineer — ...`
- adds browser-tab favicons to non-protected HTML surfaces
- adds Inno Setup wizard/sidebar/small images and shortcut icons
- adds optional `go-winres` build integration so official Windows builds can embed the Explorer EXE icon, GUI manifest, and version metadata
- preserves the RC1 external-dependency policy: Python, Piper, Whisper, Ollama and the LLM model are not packed into the EXE

## Protected-core rule

No telemetry, decoding, scoring, data-quality, Corner Coach, coaching priority, strategy, replay, server-sync, Performance History, Driver Profile evidence, hardware transport, TTS/STT/LLM decision logic, or persistence behavior was changed.

`src/overlay/window.py` is a protected-source file, so its branding-only change is explicitly documented as a justified deviation in `V2_SOURCE_FREEZE_MANIFEST.json`.

## Validation

- full pytest regression: **1335 passed + 383 subtests, 0 failed**
- Stable V2 branding regression: pass
- external dependency launcher regression: pass
- Weather/Fuel clipping regression: pass
- Control Center application-window regression: pass
- V2 source-freeze verification: pass after recording the explicit branding-only deviation

## Release status

This is **Stable V2 RC2**, not the final Stable V2 Git tag. The branding should be visually checked on the real Windows PC before final freeze/tagging.


---

## Archived source: `CP_V291354_PTT_PATH_AUTHORITY_HOTFIX.md`

# V2.9.1.3.5.4 — PTT Persistent Path Authority Hotfix

## Evidence
A startup path split existed between the structured mutable-data migration and the PTT runtime. `migrate_legacy_layout()` moved `logs/ptt` into `user_data/logs/ptt` before PTT startup, while `PTTConfig.output_dir` still wrote/read `logs/ptt`. This could move `hid_mapping.json` and WAV captures away from the path the PTT runtime checked on the next start, creating repeated calibration/stale-mapping behavior and making recorded WAV files appear to disappear from `logs/ptt`.

## Fix
- `user_data/logs/ptt` is now the single authoritative PTT runtime directory.
- HID mapping and WAV captures use that directory.
- configuration export still stores the mapping in the portable archive path `logs/ptt/hid_mapping.json`.
- historical sync continues to exclude transient PTT WAV captures.
- no radio intent/STT/TTS/telemetry/coaching logic changed.


---

## Archived source: `CP_V291355_PH_CURRENT_REFERENCE_HOTFIX.md`

# V2.9.1.3.5.5 — Performance Hub Current Reference Authority Hotfix

Scope: Performance Hub reference selector only. No Race Engineer, Corner Coach, telemetry, radio, strategy, scoring, or reference capture logic changed.

## Reproduced issue
Control Center showed the newer Catalunya `rival_reference.json` (1:10.580), while Performance Hub exposed only the older session-recorded rival/reference (1:16.735).

## Root cause
`PerformanceHistoryStore._installed_review_references()` filtered out references whose quality grade was not accepted. The Control Center selector does not hide a loadable reference merely because its quality score is low. The newer current rival was therefore visible in Control Center but absent from Performance Hub. Legacy/missing track metadata could also prevent a valid per-track `rival_reference.json` from appearing.

## Fix
- Performance Hub now exposes loadable current references even if quality acceptance is false; quality is retained as metadata and shown in the label.
- Per-track `references/<TRACK>/rival_reference.json` may use its track folder as fallback track authority when metadata lacks a usable track name.
- Historical session-embedded reference is renamed `Session-recorded rival/reference` so it is not confused with the current installed rival.
- Current `rival_reference.json` is labelled `Current rival reference`.

## Validation
Focused reference-authority + reactive Performance Hub tests: 5 passed.


---

## Archived source: `CP_V291356_TRACK_ID_RECONCILIATION.md`

# V2.9.1.3.5.6 — Historical Track Identity Reconciliation Hotfix

Scope: Performance History only.

## Issue reproduced
The same live F1 session could be stored as `Unknown` before track identity was decoded and, after restarting Race Engineer while remaining in the same game session, be stored again under the authoritative circuit name (for example `Sakhir (Bahrain)`). Performance Hub then displayed two track buckets for one EA session.

## Fix
- schema version 5 reconciliation for existing duplicate rows sharing local profile + EA session UID + session type;
- only merges when there is one unambiguous known track identity;
- merges stored summary/coaching/lap telemetry evidence before removing the duplicate Unknown row;
- live autosave path now reuses a known track identity for the same session UID after app restart;
- preserves the canonical session row ID on subsequent autosaves;
- no guessing by lap time, date, or similarity.

## Protected scope
No radio, telemetry decoding, Corner Coach, strategy, scoring, reference capture, server sync, or Driver Profile logic changed.

## Validation
27 focused Performance Hub/history tests passed, including 3 new regression tests for Unknown->Bahrain reconciliation, row-ID stability, and migration of an already-stored duplicate.


---

## Archived source: `CP_V291357_SESSION_UID_AUTHORITY.md`

# V2.9.1.3.5.7 Session UID Authority Reconciliation Hotfix

## Problem reproduced
V2.9.1.3.5.6 grouped duplicate rows by local profile + EA session UID + session type. Immediately after an application restart the same live F1 session can temporarily save with session_type missing/Unknown, while the later authoritative snapshot contains `Time Trial` and the known circuit name. Because session_type differed, the rows were not reconciled and the Performance Hub accumulated `Unknown` sessions.

## Fix
- Session reconciliation authority is now local profile + EA session UID.
- Missing/Unknown session_type is treated as provisional rather than part of the hard identity.
- Merge proceeds only when the UID resolves to one unambiguous known track and at most one known session type.
- A later authoritative track/session type upgrades provisional rows.
- Existing V5 databases are repaired by schema migration V6.
- Lap telemetry/evidence, earliest session timestamp, best/potential data and the canonical known row are preserved.
- Conflicting known tracks or conflicting known session types are left untouched rather than guessed.

## Scope
Only `src/performance_history.py` and release banner in `src/main.py` changed. No telemetry decoding, radio, Corner Coach, strategy, scoring, reference capture or server-sync logic changed.

## Validation
26 focused Performance Hub/history tests passed, including new restart cases where one row has missing session_type and the later row has `Time Trial` + `Sakhir (Bahrain)`.


---

## Archived source: `CP_V291358_PTT_PERSISTENCE_EDGE.md`

# V2.9.1.3.5.8 — PTT Persistence + HID Edge Reliability Hotfix

Scope is limited to the reproduced PTT failure.

- `user_data/logs/ptt` is now excluded entirely from historical bulk migration/retention.
- Stale bulk-migration retention records pointing into the PTT runtime tree are forgotten before deletion.
- HID debounce now advances with elapsed poll time even if TinyUSB emits only one report on the press/release edge.
- No radio parser, STT, TTS, telemetry, Corner Coach, strategy, scoring, reference, or Performance History logic changed.


---

## Archived source: `CP_V291359_DRIVER_TRACK_EVIDENCE_RECONCILIATION.md`

# V2.9.1.3.5.9 Driver Track Evidence Reconciliation Hotfix

Scope: derived Driver Profile / Skill Evidence track identity only.

## Reproduced issue
Performance Hub no longer showed the provisional `Unknown` bucket, but Driver Profile > Tracks still showed `Unknown` because Track Skill is derived from a separate persisted Skill Evidence index. The previous Performance History repair did not update that derived store.

## Fix
- Performance History normalized `track_name` / `session_type` columns are authoritative when exporting sessions to Skill Evidence.
- Skill Evidence uses `performance_history_session_id` as the stable identity whenever available, so a provisional Unknown track/name cannot create another derived evidence session.
- Existing Skill Evidence entries are reconciled only when they contain an exact `performance_history_session_id` that still exists in Performance History.
- Track and session type are updated in both the evidence payload and its measurements.
- Multiple derived evidence rows pointing at the same exact Performance History row are de-indexed safely. Old JSON files are left on disk rather than deleted.
- Driver Skill and Track Trends are rebuilt after reconciliation.

## Safety
No matching by session UID, lap time, track similarity, or timestamp. No Performance History row is deleted or modified by the Skill Evidence reconciliation.

## Validation
Focused regression: 30 passed.


---

## Archived source: `docs/V0.3.md`

# V0.3 implementation and validation reference

## Scope and official sources

Only common-header identification, selected binary body decoding, deterministic
state normalization, local console output and optional bounded capture are
implemented. No AI, strategy, coaching, audio, GUI, databases or outbound telemetry.

Sources retrieved and compared on 2026-09-15:

- [EA specification announcement](https://forums.ea.com/blog/f1-games-game-info-hub-en/ea-sports%E2%84%A2-f1%C2%AE25-2026-season-pack-udp-specification/12187347)
- [Official 2026 C++ structures](https://forums.ea.com/t5/s/tghpe58374/attachments/tghpe58374/f1-games-game-info-hub-en/61/8/2026%20Season%20Pack%20Telemetry%20Output%20Structures%20%281%29.txt)
- [Official Season 8 PDF](https://forums.ea.com/t5/s/tghpe58374/attachments/tghpe58374/f1-games-game-info-hub-en/61/10/Data%20Output%20from%20F1%2025%202026%20Season%20Pack%20%28Season%208%29.pdf)

The source files are development references under ignored `logs/`, not runtime
dependencies. Their SHA-256 hashes were:

```text
TXT: 4f97867924f5f13f11b7fde6eb84ccb3aefcaf69062424bc077e387090647c72
PDF: 3f38858c3ca65b2faa55a90a35277dd2767bb9cea2911e741b61b370a39365ae
```

All 21 selected structure definitions (including the header and nested records)
were compared for field types, order and array counts between these documents.
The V0.2 header remains unchanged: packed little endian, 29 bytes. Format is
2026; game years 25 and 26 remain accepted for the validated Season Pack.

### Source discrepancies and limits

- The PDF spells two Car Status fields `m_vehicleFiaFlags` and
  `m_ersHarvestedLimitPerLap`; the structures TXT spells them `m_vehicleFIAFlags`
  and `m_ersHarvestLimitPerLap`. Types and positions agree. Raw dataclasses use
  the TXT spelling; normalized state uses `harvest_limit_j`.
- Some PDF structure closing delimiters are missing/malformed. The TXT supplies
  the complete declarations; the field lists and published sizes agree.
- The Season 8 PDF adds F2 2026 team IDs 489–499. These are included, alongside
  all other team IDs in that appendix. Unknown IDs retain their numeric value.
- EA describes fuel as mass/capacity but does not explicitly specify a unit in
  these documents. State therefore exposes `remaining_mass` and `capacity` in
  EA's raw units. It deliberately does not assert kg or litres.
- Energy is exposed in joules. No documented fixed maximum is used, so there is
  no ERS percentage calculation.
- There is no dedicated tyre-puncture flag in the selected packets. `punctured`
  remains `None`; damage percentages are not interpreted as punctures.
- Tyre Sets does not document an out-of-range `m_fittedIdx` sentinel. Values
  outside 0–19 remain in `fitted_set_index_raw`; normalized index becomes `None`.
- Session paused status is documented as network-game-only. A false value does
  not prove that an offline session is unpaused.
- Official zero lap/sector times are treated as unavailable for a completed
  previous lap or sector. Current lap time zero remains valid. Zero lap/position
  values do not become real lap numbers or race positions.

## Decoded packet structures and exact sizes

All sizes include the 29-byte header. Body version **1** is supported; other
versions remain identifiable but do not update RaceState.

- ID 1: `PacketSessionData`, **926 bytes**. Nested `MarshalZone` (5),
  `ActiveAeroZone` (8), `DRSZone` (8), `WeatherForecastSample` (8).
- ID 2: `PacketLapData`, **1399 bytes**. 24 `LapData` records (57 each), plus
  the two Time Trial car-index bytes.
- ID 3: `PacketEventData`, **45 bytes**. Four-byte event code and 12-byte union.
- ID 4: `PacketParticipantsData`, **1470 bytes**. Count plus 24 `ParticipantData`
  records (60 each), including four `LiveryColour` records (3 each) per participant.
- ID 6: `PacketCarTelemetryData`, **1448 bytes**. 24 `CarTelemetryData` records
  (59 each), two MFD bytes and signed suggested-gear byte.
- ID 7: `PacketCarStatusData`, **1445 bytes**. 24 `CarStatusData` records (59 each).
- ID 10: `PacketCarDamageData`, **1133 bytes**. 24 `CarDamageData` records (46 each).
- ID 12: `PacketTyreSetsData`, **231 bytes**. Car index, 20 `TyreSetData` records
  (10 each), fitted index.
- ID 16: `PacketCarTelemetry2Data`, **269 bytes**. 24 `CarTelemetry2Data` records
  (10 each).

All body lengths must match exactly. Count fields are validated before use.
Names use EA's 32-byte, null-terminated UTF-8 field; malformed bytes use replacement
characters and console control characters are neutralized. Fixed arrays must be
read to validate structure, but state only uses participant-count entries (or the
player's slot while Participants is missing). Packet size never identifies type.

Other IDs continue through V0.2 identification and counters without full decoding.

## Architecture and normalized fields

- `src/udp_receiver.py`: unchanged raw V0.1 networking and once-per-second timing.
- `src/telemetry_receiver.py`: unchanged V0.2 header/type statistics.
- `src/telemetry/layouts.py`: explicit immutable raw dataclasses and packed layouts
  for the eight selected bodies and their nested structures.
- `src/telemetry/binary.py`, `decoders.py`, `events.py`, `enums.py`: byte decoding,
  validation, event unions and official names. No state or advice.
- `src/race_state/models.py`: typed normalized consumer interface.
- `src/race_state/engine.py`: updates already-decoded data; never parses UDP bytes.
- `src/race_state/formatter.py`: readable display, N/A handling and freshness.
- `src/race_state_receiver.py`: connects decoding, diagnostics and the engine.
- `src/capture.py`: opt-in bounded local capture only.

The receiver and formatter run synchronously on one thread. No concurrency or
locks are needed. Future consumers can read `receiver.engine.state` in that
execution context. `dataclasses.asdict(state)` produces a JSON-compatible snapshot;
consumers must not mutate the engine's live object or access it concurrently.

### Consumer model

`RaceState` contains `session`, `player_index`, `secondary_player_index`, `player`,
`field` keyed by car index, participant count, immediate ahead/behind indices,
reported gap behind, category timestamps and a bounded event history.

`SessionState` exposes UID, session/track/weather raw IDs and names, air/track
temperatures, total laps, track length, remaining/duration seconds, pit speed
limit, safety-car status, paused/spectating flags, game forecast, forecast accuracy,
latest session timestamp and session-ended flag when an event supplies it.

Each `CarState` groups:

- `Identity`: safe driver name, team raw ID/name, AI/human, race number and public
  telemetry setting.
- `LapState`: position, lap, current/previous lap times, sector and sector times,
  lap/total distance, validity, pit status/count/timers, penalty-to-serve flag,
  penalty seconds, warnings, unserved penalties, grid and driver/result status,
  directly supplied deltas to the car in front and leader.
- `CarTelemetry`: speed km/h, throttle/brake fractions, clutch percent, steering,
  signed gear, RPM, DRS flag, rev-light percent/bits and engine temperature.
- `FuelState`: raw mass/capacity, MFD remaining laps and fuel mix.
- `EnergyState`: stored, harvested MGUK/MGUH, per-lap harvest limit and deployed
  energy in joules, plus deploy mode. Mode 3 is labelled Boost by the 2026 spec.
- `AeroOvertakeState`: active-aero mode, available flag and activation distance;
  Overtake available/active flags and activation distance; 2026-regulations and
  wrong-way flags; legacy DRS allowed/distance; raw Telemetry 2 flags for debugging.
- `TyreState`: compounds, age, wear/damage/blisters, surface/inner temperatures,
  pressures, 20 tyre sets with availability, recommendation, life values and
  signed lap delta, fitted set and raw fitted-index value.
- `DamageState`: wings, floor, diffuser, sidepod, DRS/ERS faults, gearbox/engine
  damage, six engine component wear values, blown/seized flags and brake damage.

EA wheel arrays are **RL, RR, FL, FR**. Raw tuples preserve this order; normalized
`Wheels` uses explicit `FL`, `FR`, `RL`, `RR` attributes. Temperatures are Celsius,
pressures PSI, distances metres, normalized times seconds. NaN/Inf measurements
become `None`; raw decoded values remain available for diagnostics.

Only directly supplied Overtake/active-aero fields are used. Distance zero retains
EA's “not available” distance semantics; availability is read from its own flag,
not derived from distance or ERS mode. No cooldown, time, usage counter or energy
threshold is invented. Unsupported boolean values become `None`; Telemetry 2 raw
flags are retained. Other unknown enum values become `UNKNOWN(n)` with raw IDs.

## Ordering, resets and gaps

- Every category carries receive time, overall frame and session time. The console
  labels data stale after five seconds; this is a display threshold, not a
  protocol rate expectation, and it never clears data.
- Per-category overall frames reject older/duplicate updates. Tyre-set ordering
  is per car because EA cycles through cars. Multiple events in a frame are allowed.
- Frame comparison supports uint32 wrap. Ordinary frame/session time can decrease
  after flashbacks; overall frame is used for ordering.
- A fully decoded packet with a new session UID resets session, cars, caches,
  timestamps and events atomically within the update call. Packet counters persist.
  The last 64 retired UIDs are remembered to reject delayed previous-session packets.
- Packets can arrive before Participants. Their newest decoded data is cached and
  reconciled when the official count arrives; inactive array slots are not field cars.
- Ahead/behind are chosen only by adjacent race position among active participants.
  Ambiguous/duplicate positions give no neighbour. Gaps are EA's lap deltas; the
  behind gap is that car's reported delta to its front car. They are not distance/
  speed estimates. Their validity in lapped, garage, qualifying or unusual sessions
  is limited by what EA reports; no interval reconstruction is attempted.

Known limitations: one game sender/session is expected; switching among two game
senders on the same port is not supported. Very old sessions outside the retired
UID window cannot be distinguished from new ones. Across a flashback, categories
refresh at their own rates rather than forming an atomic same-frame snapshot.
Multiplayer privacy may zero restricted fields; the public-telemetry flag is
retained, but zero values cannot always be distinguished from unavailable values.

## Events

Recognized codes: `SSTA`, `SEND`, `FTLP`, `RTMT`, `DRSE`, `DRSD`, `TMPT`, `CHQF`,
`RCWN`, `PENA`, `SPTP`, `STLG`, `LGOT`, `DTSV`, `SGSV`, `FLBK`, `BUTN`, `RDFL`,
`OVTK`, `SCAR`, `COLL`, `PMEN`, `PMDI`, `OVEN`, `OVDI`. The final four are 2026 Season 8 race-control events and carry no event-detail payload in the published structure. Payloads follow EA's union, including retirement reason,
DRS-disabled reason, stop-go duration and collision severity. Penalty/infringement
and event-detail numeric codes remain raw diagnostic values.

The latest 32 non-button events are retained. Buttons are decoded as raw event
metadata only and do not implement controls. Unknown event codes remain safe
diagnostics. `OVEN`/`OVDI` are race-control events and are independent from the per-car Telemetry 2 Overtake available/active fields. Session start/end update an explicit flag; no automatic engineer runs.

## Commands and capture

```powershell
python -m src.main
python -m src.main --packet-stats
python -m src.main --show-sizes
python -m src.main --packet-stats --show-sizes
python -m src.main --capture-packets 200
python -m unittest discover -s tests -v
```

Capture is off by default. Explicit capture accepts 1–2000 packets, saves under
ignored `logs/capture-*.bin`, closes after the requested count and keeps the
receiver running. Ctrl+C closes a partial capture too. Captures **may contain
participant/player names**; do not commit or share them unintentionally. Nothing
is uploaded. Disk errors disable capture while state reception continues.

Capture format: ASCII `ARECAP01`, then repeated little-endian uint32 packet length
followed by that many raw UDP bytes. No networking metadata is required to replay
bytes through `decode_packet`. A partial final record after an interrupted disk
write must be treated as truncated. A new filename is used for each run.

## Validation

All original 24 tests are preserved unchanged. New tests use a separate field/
offset reference transcribed from EA and checked against the Season 8 PDF, rather
than packing with the application's decoder. Tests cover selected layouts, enum
fallbacks, malformed bodies/names, a nonzero player index, wheel order, normalization,
session resets, multi-rate/out-of-order data, freshness, events and bounded capture.
Real localhost socket tests check idle operation, malformed and valid traffic,
clean stopping and rebinding the port.

A development benchmark with 24 cars processed 7,000 complete datagrams in about
3.9 seconds (~1,789/sec) on this machine, with zero malformed bodies. This excludes
console printing and is a local measurement, not a guaranteed throughput figure.

Application dependencies remain Python 3.11+ standard library only. PDF extraction
tools were used during development, not added to the application.

## Real-game validation to send back

1. Use UDP format 2026, destination 127.0.0.1, port 20777, rate 20 Hz.
2. Send two complete default summaries while driving, a few seconds apart.
3. Send one `--packet-stats --show-sizes` summary, especially any header/body errors.
4. Confirm driver/team, track/session, position/lap, speed/gear, tyre compound/age,
   temperatures/pressures and Overtake/active-aero flags agree with the game's display.
5. Report the game build, session mode, and any privacy/restricted telemetry setting.
6. Change session and report whether UID and state reset; stop with Ctrl+C and
   confirm the clean-stop message. If a field is suspicious, keep a bounded capture
   locally and report which field, expected value and displayed value first.

No Git commit or push is performed. Real-game validation precedes your V0.3 commit.


---

## Archived source: `docs/V0.4.md`

# V0.4 Automatic Race Engineer

V0.4 is the first deterministic decision/message layer. It consumes only the
normalized `RaceState` produced by V0.3. There is no LLM, network API, voice,
TTS, GUI, or direct car control in this milestone.

## Design

`src/engineer/engine.py` snapshots the player/session fields relevant to calls,
compares successive valid states, and emits typed `EngineerMessage` objects.
The first state of every session UID is a baseline and produces no messages.
A session UID change clears cooldown/threshold history.

Priorities are `CRITICAL`, `STRATEGY`, `INFORMATION`, `COACHING`. Delivery is
sorted by priority. Coaching is reserved in the model but deliberately has no
rules yet because V0.4 does not infer driving technique.

Thresholds are deterministic application policy, not claims about real F1 team
thresholds: tyre wear 25/50/70/85%, tyre damage 25/50/75%, front wing
20/50/80%, and rear wing/floor/engine/gearbox 25/50/75%. Each threshold is
latched per session so it is not repeated every telemetry packet. State-change
messages also use cooldowns.

Fuel warnings use EA's game-supplied `m_fuelRemainingLaps` value directly:
warning when it crosses down through 1.00 laps and critical at 0.25. V0.4 does
not estimate fuel consumption. Weather calls use the game's current weather and
forecast samples; a five-minute rain percentage crossing 20% is informational
and 50% is strategic. V0.4 does not make its own weather prediction.

## Automatic calls

- lap increment and position change
- pit entry/exit and fitted tyre-set change
- time penalty, drive-through, stop-go
- Safety Car / VSC deployment and ending
- current weather change and game forecast rain-risk thresholds
- game MFD fuel-laps thresholds
- tyre wear/damage threshold escalation with worst wheel
- front/rear wing, floor, engine and gearbox damage escalation
- DRS fault, ERS fault, engine blown/seized, wrong-way state
- Overtake becoming available

## Deliberately not in V0.4

No pit-window recommendation, undercut/overcut logic, tyre-life prediction,
fuel-burn model, ERS strategy, opponent prediction, driver coaching, LLM,
voice input, or TTS. Those require later milestones and must not be inferred
from incomplete telemetry here.

## Run

Full state plus engineer messages:

```powershell
.\.venv\Scripts\python.exe -m src.main
```

Engineer messages only:

```powershell
.\.venv\Scripts\python.exe -m src.main --engineer-only
```

Tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The V0.4 development suite contains 92 tests, including all 75 V0.3 tests and
17 deterministic automatic-engineer tests.


---

## Archived source: `docs/V0.6.md`

# V0.6 - Push-to-Talk + ERS and DRS/S Mode assists

V0.6 adds two independent deterministic driving assists and the first PTT input layer.

## Assists

Both assists are enabled by default.

- ERS Assist: when EA's 2026 `overtakeAvailable` is true but `overtakeActive` is false, calls `Overtake available. Use Overtake or Boost.` It repeats after a 6 s cooldown if the opportunity remains and the driver still has not activated it.
- DRS/S Mode Assist: under 2026 regulations, when Active Aero is available but the car is not in Straight mode, calls `S Mode available. Enable S Mode.` For legacy/non-2026 telemetry it uses `drsAllowed` + the actual DRS state and calls `DRS available. Enable DRS.`

These are advisory only. The program never presses a game control. The reminders use explicit EA availability/active fields and do not infer a zone from track position.

Disable independently:

    --no-ers-assist
    --no-drs-s-mode-assist

## Push-to-Talk

V0.6 PTT captures microphone audio to WAV only. STT/intent handling is V0.7.

Install dependencies:

    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Discover devices:

    .\.venv\Scripts\python.exe -m src.main --list-controllers
    .\.venv\Scripts\python.exe -m src.main --list-audio-devices

Run with PTT (example controller 0, button 5, microphone 2):

    .\.venv\Scripts\python.exe -m src.main --engineer-only --ptt --ptt-controller 0 --ptt-button 5 --mic-device 2

Hold the configured wheel button to record. Release it to save a 16 kHz mono WAV under `logs/ptt/`. UDP telemetry and TTS continue on separate execution paths.


---

## Archived source: `docs/V0.7.md`

# V0.7 — Offline Speech-to-Text / Voice Commands

## V0.7.1 STT integration

This development step connects the already validated V0.6 Button-6 PTT WAV capture to an asynchronous offline `faster-whisper` worker.

Default STT configuration:

```text
model        base.en
device       cpu
compute type int8
language     en
VAD          enabled
```

The Whisper model is loaded once in a background worker. Completed PTT WAV paths are queued to that worker, so HID polling and UDP telemetry do not wait for transcription.

A successful radio capture now continues as:

```text
[PTT] PRESSED - LISTENING
[PTT] RELEASED - capture complete
[PTT] WAV: logs\ptt\ptt_....wav
[STT] Transcribing: logs\ptt\ptt_....wav
[STT] "Can I box now?"
```

The proven V0.6 HID mapping/calibration and microphone recorder are unchanged except for a callback after a WAV has successfully been written.

This step intentionally stops at transcription. Deterministic intent parsing, RaceState answers and Piper voice replies are the next V0.7 steps.

Run the validated hardware path with:

```powershell
.\.venv\Scripts\python.exe -m src.main --ptt --ptt-button 6 --mic-device 2
```

Use `--no-stt` to retain V0.6-style WAV-only PTT capture, or `--stt-model` to select another faster-whisper model.

## V0.7.2 deterministic voice commands

After a successful PTT transcription, V0.7.2 parses the transcript locally and answers from a copied current `RaceState`. The parser is deterministic; unsupported speech is rejected rather than guessed. Initial intents cover tyres, fuel, ERS, position, direct gap ahead/behind, lap time, damage, penalties, weather, pit status, race-control status and a concise status update.

`Can I box now?` is recognized as `PIT_RECOMMENDATION`, but V0.7 intentionally does not invent a strategy recommendation. Optimized box/stay-out strategy remains V0.8 work.

Console diagnostics are:

```text
[STT] "Gap ahead."
[VOICE] Intent: GAP_AHEAD
[VOICE] Engineer: Gap ahead 1.234 seconds.
```

The response is submitted to the existing asynchronous Piper/Windows speech queue. STT, voice parsing and TTS do not move HID polling into the telemetry thread.

## V0.7.3 radio arbitration + concise tyre status

- Pressing PTT immediately takes the radio: current TTS playback is terminated and TTS remains silent through capture and STT processing.
- Non-critical speech queued before/during the driver's radio request is invalidated; critical calls are retained.
- Voice answers use Strategy queue priority so they outrank Information/Coaching chatter while remaining below Critical calls.
- Generic tyre status is intentionally short: `Tyres are good.` when known values are within the deterministic alert bands.
- Generic tyre status only names affected wheel(s) when wear/damage/temperature needs attention.
- Explicit `tyre wear` and `tyre temperatures` requests still return four-wheel numeric detail.
- Generic tyre alert bands: wear >=25%, tyre damage >=25%, surface temperature <70 C or >110 C. These are deterministic radio alert thresholds, not compound-specific strategy targets.


## V0.7.5 - Radio priority and low-latency assists

Radio scheduling is now independent from the engineer rule priority enum. Explicit driver PTT answers are spoken first, followed by critical game calls, immediate driver assists, strategy, information, and coaching. S Mode, DRS and Overtake assist calls are shortened to `S Mode.`, `DRS.`, and `Overtake available.` and may pre-empt ordinary background speech. A driver-requested answer is protected from assist pre-emption.


---

## Archived source: `docs/V0.8.md`

# V0.8 — Local-first radio + local LLM reasoning

## Rule
Direct telemetry/data questions never use the LLM. They are answered immediately from normalized RaceState. Only judgement, explanation, comparison, strategy, or calculation questions are routed to the local LLM.

Examples kept deterministic: tyres, tyre wear/temperature detail, fuel, ERS, position, gaps, lap time, damage, penalties, weather, pit status, flags/Safety Car and status.

Examples routed to LLM: "Why am I losing pace?", "What should I focus on?", "Should I push or save?", "What strategy do you recommend?", and "Should I box now?".

The LLM receives a compact normalized RaceState snapshot, never raw UDP. The system prompt forbids invented telemetry and asks for a short radio answer. Missing data stays missing.

## Local LLM
Default endpoint: `http://127.0.0.1:11434/api/chat`
Default model: `qwen2.5:3b`

Install Ollama separately and pull the model once:

```powershell
ollama pull qwen2.5:3b
```

Disable reasoning without affecting deterministic radio:

```powershell
python -m src.main --ptt --ptt-button 6 --mic-device 2 --no-llm
```

Choose another local Ollama model with `--llm-model MODEL`.

## Voice lock
When `--tts-backend piper` is selected, Piper never silently falls back to Microsoft Hazel. A Piper failure is logged and that message is skipped; the next message retries the same Alan voice. Explicit `--tts-backend windows` remains available for diagnostics.

## Tyre radio
Generic tyre questions are short. "How are my tyre temperatures?" is treated as status and returns "Tyres are good" unless a wheel is outside the configured alert bands. Four-corner temperatures require an explicit detail request such as "tyre temperatures" or "give me all tyre temperatures".


---

## Archived source: `NEXT_CONTINUATION_PROMPT.md`

Continue the Race Engineer project from the attached **RaceEngineer_V1.3.8.0_Race_Strategy_Integration_FINAL.zip** only. Treat V1.3.8.0 as the new working baseline and do not rebuild or regress the completed CORNER COACH, reference, Speech/Radio, or race-strategy systems.

First read `V1.3.8.0_FINAL_VALIDATION_REPORT.md`, `V1.3.8.0_RACE_STRATEGY_INTEGRATION_NOTES.md`, and `FEATURES_ROADMAP.md`. Then audit the roadmap against the actual source and work only on the next pending phase I request.

Preserve these V1.3.8.0 guarantees:
- unified race-context/coaching arbitration;
- critical/race-control/tyre/brake/damage ownership;
- combat suppression + race-exit advice + automatic coaching resume;
- tyre/fuel/ERS/damage/wet adaptations;
- measured-only pit loss, undercut/overcut, tyre/fuel/ERS/damage/weather/opponent/race-rule strategy;
- per-circuit strategy evidence persistence;
- strategy packet-family/cadence optimization;
- no fabricated values when evidence is missing.

Validation baseline:
- Qualifying replay: 38,358 packets PASS.
- Shanghai replay: 30,945 packets PASS.
- Race strategy-focused replay: 81,159 source packets / 14,490 strategy-relevant processed PASS.
- Time Trial strategy-focused replay: 92,262 source packets / 16,728 strategy-relevant processed PASS; no race logic leakage.
- Full tests: 745 passed + 383 subtests, 0 failures.

For any long work: split into internal batches, save a ZIP checkpoint immediately if approaching an execution timeout, and provide the checkpoint plus a continuation prompt so no work is lost. Do not ask me to test incremental builds unless actual Windows/live-game hardware validation is the only remaining step.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.4.0.0.md`

Use `RaceEngineer_V1.4.0.0_Replay_Session_Analysis.zip` as the new working baseline.

The completed major phases now include CORNER COACH, Potential Lap/post-session coaching, Speech/Radio voice controls, Race Engineer + Performance Coach integration, advanced deterministic race strategy, local Reference Ecosystem, and Replay / Session Analysis.

Next priority: audit `FEATURES_ROADMAP.md` from this V1.4.0.0 build and implement the highest-priority remaining LOCAL/PERSONAL F1 release block. Multi-sim and cloud/community remain deferred and are not release blockers.

Important workflow rules:
- preserve the existing deterministic core and reference compiler unless a failing test proves a dependency;
- do not rebuild or recapture working references unless there is a genuine incompatible data/schema requirement;
- use the supplied recordings/reference files for internal validation;
- do not give me every incremental build;
- work in small persisted batches and run focused tests internally;
- if an execution timeout is approaching, immediately package the current persisted source plus an exact checkpoint report so we can continue without losing work;
- only call a feature complete when source code and tests actually support it;
- after the phase, run the full regression suite once and package one final downloadable ZIP with release notes and validation report.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.5.0.0.md`

Continue Race Engineer from V1.5.0.0 Pre-Release Hardening. Treat this build as the current base. Do not rebuild existing references unless raw/schema incompatibility is proven. First inspect the newest `analysis/validation_bundles/WEEKEND_VALIDATION_BUNDLE_*.zip` (or per-session VALIDATION_BUNDLE files) from the next real weekend. Validate Practice -> Qualifying -> Race transitions, Session Best reference_update events, pit-window decisions, strategy evidence, CORNER PRE/POST delivery, packet gaps, CPU/RAM and latency. Fix only evidence-backed issues. Preserve fact-only deterministic logic and do not invent unavailable telemetry. After live validation is clean, proceed to Productization / Windows installer + standalone EXE. If execution-time risk appears, package a checkpoint recovery ZIP before continuing.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.6.0.0.md`

Continue Race Engineer from V1.6.0.0 Windows Productization. Preserve deterministic F1 logic and all V1.5 validation instrumentation. First perform target-Windows build validation using build_release.ps1, test the first-run /setup workflow, installer upgrade preservation, audio/HID/COM selection, UAC firewall option, QR/LAN access, and multi-monitor/DPI behavior. Fix only issues proven by that validation. Use checkpoint ZIPs before long/risky build steps and provide one final consolidated release package.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.7.0.0.md`

Continue the Race Engineer project from **V1.7.0.0 — SPEED COACH / Straight Line Coach Integration**.

Use `/mnt/data/RaceEngineer_V1.7.0.0_Speed_Coach_FINAL.zip` as the authoritative source package if available, or the user's extracted copy of that release.

Key architecture now:
- SPEED COACH is the parent/master overlay/runtime.
- CORNER COACH and STRAIGHT LINE COACH are independently switchable children.
- Corner PRE/POST behavior and existing deterministic reference pipeline are preserved.
- Straight Line Coach uses the same authoritative full-track segmentation/reference model and gives measured completed-straight feedback.
- Straight speech is PRE-safe and low-workload gated.
- Straight defaults OFF after upgrade.
- SPEED_COACH_TRANSCRIPT is the combined human-readable transcript; structured source distinguishes corner vs straight; legacy corner-only transcript remains for compatibility.

Final validation baseline:
- 794 tests passed + 383 subtests, zero failures.
- Real `.areplay` channel foundation validated against Melbourne Qual, Melbourne Race, Time Trial and Shanghai.
- Windows EXE/installer compilation is intentionally deferred until all feature work is finished.

Continue with the next non-EXE roadmap priority or with live Speed Coach validation artifacts supplied by the user. Preserve the checkpoint/recovery-package method before long/risky work.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.8.0.0.md`

Continue the Race Engineer project from `RaceEngineer_V1.8.0.0_Driving_Performance_FINAL.zip`.

V1.8.0.0 completes the Driving Performance Engine upgrade: 28/28 known F1 track physical-turn coverage, geometry-first action boundaries, path-curvature apex, true apex speed, time-domain coasting and throttle pickup, richer steering shape, stronger confidence/outlier rejection, and reference-relative minimum-speed/throttle-pickup/exit-speed efficiency.

Final validation baseline: 801 tests + 383 subtests, zero failures. Real replay geometry validation: Melbourne 14/14, Austria 10/10, Shanghai 16/16 with full curvature/time/steering coverage on selected geometry-complete valid laps.

Keep Windows EXE/installer compilation deferred until all remaining F1 features and live validation are complete.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.9.0.0.md`

Continue Race Engineer from V1.9.0.0 Local Driver Performance Hub.

Use the V1.9.0.0 full package as the working base. Preserve all V1.8.0.0.3 replay-continuity and V1.8.0.0.2 audio/STT fixes.

V1.9.0.0 adds a local SQLite-backed browser Performance Hub at `/performance` with F1 ParticipantData-derived driver profiles, track-by-track history, best/potential/reference trends, complete per-session records and measured opportunity/strength summaries. Existing `analysis/driver_history.json` is migrated once into the first real driver profile and remains supported for legacy coaching features.

Next validation should use real multi-track recordings/live sessions. Verify that sessions are stored once, driver identity is correct, track grouping is correct, historical trends update after every completed session, and no database activity affects replay/live telemetry smoothness. Fix only demonstrated issues, preserve checkpoint files, and rerun the complete regression suite before packaging the next build.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.9.1.0.md`

Continue Race Engineer from V1.9.1.0. Preserve the working V1.8.0.0.3 replay continuity/audio fixes and V1.9 Performance Hub. V1.9.1.0 establishes LIVE GAME ONLY performance history using `analysis/performance_history_live.sqlite3`, leaves replay data non-persistent, converts Control Center to a normal desktop application window, and embeds Performance Hub as a CONTROL/PERFORMANCE HUB tab. Check CHECKPOINT_V1.9.1.0_1_LIVE_HISTORY_AUTHORITY.md, CHECKPOINT_V1.9.1.0_2_CONTROL_CENTER_APP.md and CHECKPOINT_V1.9.1.0_3_VALIDATION.md before further work. Do not reintroduce replay-derived personal history.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.9.1.2.md`

Continue Race Engineer development from V1.9.1.2 TELEMETRY DECISION DECOUPLING HOTFIX. Preserve all prior fixes: Windows runtime/resource portability, audio I/O/STT device fixes, replay session stitching/no catch-up bursts, long-replay validation bounding, live-only Performance Hub history, and Control Center as a normal app window with Performance Hub tab. Current focus: validate long full-weekend replay at x1 where map previously stayed smooth but telemetry panels became choppy after ~30%. V1.9.1.2 keeps per-packet telemetry state updates but caps heavy Automatic Engineer/CORNER COACH/Performance Coach evaluation on telemetry packets at 20 Hz, with immediate handling for lap/session/event-critical families. If any lag remains, instrument packet-family processing time and UI snapshot lock wait before changing logic further. Use checkpoint files and preserve work before timeout.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.9.1.3.md`

Continue Race Engineer development from V1.9.1.3 LONG REPLAY MEMORY ARCHITECTURE HOTFIX. Preserve all prior fixes. The root cause for progressive long-replay degradation was addressed by replacing full in-memory interactive replay payload loading with an indexed mmap-backed record store and by bounding/sparsifying replay checkpoints (6 entries / 48 MiB / 131072-packet interval plus session boundaries). Full suite passed 820 tests + 383 subtests. Next validation: replay the same long full-weekend recording at x1 without seeking and verify speed/gear/throttle/brake/ERS/tyre telemetry stays smooth past the previous ~30% failure point while map remains smooth. If degradation remains, capture runtime benchmark and packet-family timing rather than changing scheduler/decision logic speculatively.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.9.1.4.md`

Continue Race Engineer from V1.9.1.4 Multi-Driver Performance Hub + Dark UI Hotfix. Preserve the LIVE-only performance-history authority, driver-scoped session identity, preferred-driver selector, dark Control Center Performance Hub UI, and all V1.9.1.3 long-replay memory fixes. Use CHECKPOINT_V1.9.1.4_MULTI_DRIVER_PERFORMANCE_HUB.md as the current checkpoint.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.9.1.5.md`

Continue from RaceEngineer V1.9.1.5 WEEKEND REPLAY TRANSITION HOTFIX. Preserve the memory-mapped indexed replay architecture, no-catch-up scheduler, multi-driver live-only Performance Hub and all existing coaching/strategy behavior. If replay still stalls, validate with the exact replay position/session boundary and inspect replay clock metadata around that packet range before changing unrelated systems.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.9.2.0.md`

Continue from RaceEngineer V1.9.2.0 FINAL SOURCE HARDENING. Preserve all source-only finalization fixes, the live-only multi-driver Performance Hub, the normal-window Control Center, indexed/memory-mapped replay architecture, weekend session stitching, high-rate telemetry/decision decoupling, clean-stint pit strategy evidence gates, and supplied-real-race validation behavior. Do not modify Windows EXE/PyInstaller/Inno installer work unless explicitly requested. Only change deterministic behavior when a live recording, replay, regression or concrete source audit demonstrates a problem.


---

## Archived source: `NEXT_CONTINUATION_PROMPT_V1.9.2.1.md`

Continue from RaceEngineer V1.9.2.1 PERFORMANCE HISTORY CORRECTNESS. Preserve every V1.9.2.0 source-only hardening fix plus V1.9.2.1 LIVE history independence from auto reports, replay read-only legacy history behavior, final Performance Hub refresh upsert, and race-only wins/podiums. Preserve the live-only multi-driver Performance Hub, normal-window Control Center, indexed/memory-mapped replay, weekend session stitching, high-rate telemetry/decision decoupling, clean-stint pit strategy evidence gates, and supplied-real-race validation behavior. Do not modify Windows EXE/PyInstaller/Inno installer work unless explicitly requested. Only change deterministic behavior when a live recording, replay, regression or concrete source audit demonstrates a problem.


---

## Archived source: `RADIO_COMMANDS.md`

# V0.9.14.4 Race Radio Command Guide

The radio is deliberately **telemetry-first**. These phrases and natural variants are handled deterministically when the required EA F1 telemetry exists. Missing game data is reported as unavailable rather than guessed.

## Tyres
- `Tyre information` / `How are my tyres?`
- `Tyre wear`
- `Tyre temperature` / `Tyre temperatures`
- `Tyre temperatures more detail`
- `Tyre pressure`
- `Tyre compound`
- `Tyre age` / `Stint age`
- `Tyre set` / `Fitted set`
- `Tyre damage`
- `Tyre blisters`
- `Puncture status`
- `Which tyres should I use?` / `Which compound?`

## Brakes and setup
- `Brake information`
- `Brake temperature`
- `Brake temperatures more detail`
- `Brake damage` / `Brake wear`
- `Brake bias`
- `Brake pressure`
- `Differential`
- `Engine braking`
- `Wing setting`
- `Setup`

## Power unit / car condition
- `Engine` / `Engine status`
- `Engine temperature`
- `Engine wear`
- `Gearbox status`
- `Damage report`
- `Wing status`
- `Floor status`
- `Fault status`

## Race position and traffic
- `Position information`
- `Grid position`
- `Gap ahead`
- `Gap behind`
- `Gap to leader`
- `Driver ahead`
- `Driver behind`
- `Positions gained` / `Positions lost`

## Laps and timing
- `Current lap`
- `Laps remaining`
- `Laps completed`
- `Current sector`
- `Sector times`
- `Lap time` / `Last lap`
- `Best lap`
- `Lap valid?`
- `Compare lap`
- `Session time remaining`

## Fuel and energy
- `Fuel status`
- `Fuel used`
- `Fuel mix`
- `ERS status`
- `ERS harvest`
- `DRS status`
- `S Mode status`
- `Overtake status`

## Weather and track
- `Weather information`
- `Track temperature`
- `Air temperature`
- `Rain chance`
- `Race control`
- `Safety Car` / `VSC`
- `Penalties`
- `Track limits`

## Strategy intelligence (V0.9.16.0)
- `Strategy update` / `Can I make it to the end?`
- `Can I make these tyres last?` / `Will these tyres last?`
- `Fuel to finish` / `How much fuel margin do I have?`
- `Gap trend` / `Am I catching the car ahead?`
- `Compare stint pace` / `Current stint pace`
- `Will I come out in traffic?` / `Where will I rejoin?`
- `Can I undercut the car ahead?` / `Is the undercut working?`
- `Is this a good Safety Car pit stop?`
- `Why should I box?`

Rejoin and undercut answers deliberately remain unavailable when no factual pit-loss/post-stop model exists; Race Engineer will not invent those values.

## Pit / strategy
- `Should I box?` / `Can I box now?`
- `Pit status`
- `Pit speed limit`
- `Pit stops`
- `Which tyres should I use?`
- `Change/repair front wing?`

## Driving / performance
- `Where am I losing time?`
- `Compare performance`
- `Braking compare`
- `Traction compare`
- `Driving issues`
- `Wheel slip`
- `G force`
- `Use this lap as reference`
- `Compare with previous`
- `Compare with best`

## General
- `Race status` / `Update`
- `Telemetry summary`
- `All facts`
- `Speed`
- `RPM`
- `Gear`
- `Radio commands` / `What can I ask?`

Free-form strategic questions such as `Why am I losing pace?`, `How can I improve?`, or `Push or save?` can use the optional local LLM explanation/fallback layer **only when Race Engineer is started with `--llm`**. The LLM is disabled by default. Known telemetry commands and race decisions are always resolved deterministically first, so the LLM cannot override telemetry facts or critical strategy logic.


## V0.9.14.5 additions

- `lap remaining`, `laps remaining`, `remaining lap`, `remaining laps`, `laps left`, `how many laps left` -> same deterministic laps-remaining answer.
- `sector` -> current sector.
- `ahead driver` / `behind driver` -> driver ahead / driver behind.
- `tyre information` / `tyre status` -> concise condition call. Use `tyre temperatures`, `tyre wear`, `tyre pressures` for numbers.
- `session summary`, `race summary`, `race result`, `final result` -> end-of-session summary once Final Classification is available.

## V0.9.16.1 strategy-radio reliability aliases

These variants are intentionally normalized to the same deterministic strategy intents:

- `Compare stint pace`, `Stint pace`, and conservative observed STT near-misses such as `Compare shift paste` / `Compassioned place`
- `Will I come out in traffic?` and `Will I come out in the traffic?`
- `Am I catching the car ahead?`, `Is the gap closing?`, `Gap trend`

Driver-requested replies have radio priority over routine S Mode / Track Limits / coaching chatter. Critical deterministic safety logic remains generated normally.

## V0.9.17.0 external reference coaching
An external reference lap can be loaded at startup with `--reference-lap <file>`.
The coach then compares the driver's measured lap trace against that reference instead of only the driver's own best lap.


## V0.9.18.0 deterministic-core policy

- LLM: disabled by default; enable explicitly with `--llm`.
- Deterministic commands: always first and authoritative.
- Strategy/safety decisions: deterministic only.
- Free-form LLM output: explanation/fallback only and never a source of telemetry facts.
- `Use this lap as reference`, `Compare with previous`, and `Compare with best` follow the same pending-until-start/finish behavior as the Control Center reference selector.

## SPEED COACH hierarchy (V1.7.0.0)

- `enable/disable Speed Coach` — parent master for the shared Speed Coach runtime/overlay.
- `enable/disable Corner Coach` — independently controls corner coaching.
- `enable/disable Straight Line Coach` — independently controls straight-line coaching.
- `enable/disable Straight Voice` — controls spoken completed-straight feedback without disabling straight analysis/visuals.
- Corner PRE/POST remain corner-only controls; Map G/L remains the shared full-track measured performance layer.
- Straight Line Coach defaults OFF after upgrade; enabling it starts from the current point and does not replay already-completed straights.


---

## Archived source: `README_V1.3.6.0.md`

# Race Engineer V1.3.6.0

Parallel Race Intelligence Foundation.

Start with `RUN_RACE_ENGINEER_V1.3.6.0.bat`.

New local pages:
- `/coach` — coaching analysis
- `/sessions` — session library

Optional readiness check: `RUN_FIRST_RUN_CHECK.bat`.

See `V1.3.6.0_PARALLEL_RACE_INTELLIGENCE_FOUNDATION_NOTES.md` and `FEATURES_ROADMAP.md` for details.


---

## Archived source: `V0.8.7_FULL_TELEMETRY_NOTES.md`

# V0.8.7 Full Telemetry + Deterministic Math

Built from the supplied V0.8.6 baseline.

## Added
- Exact-size body decoding for all 17 official 2026 Season Pack packet IDs (0..16).
- New body layouts for Motion, Car Setups, Final Classification, Lobby Info, Session History, Motion Ex, Time Trial and Lap Positions.
- Existing Session/Lap/Event/Participants/Telemetry/Status/Damage/Tyre Sets/Telemetry 2 decoding retained.
- RaceState retains extended packet bodies for deterministic offline use.
- `src/deterministic_math.py` computes exact arithmetic only: race/lap progress, laps remaining, tyre wear/temp/pressure/damage spreads and axle/side deltas, fuel laps, ERS harvest-limit usage, gaps, quantised G converted to G, 3D speed magnitude, setup values, wheel-speed/slip metrics, aero-height delta, valid-lap history, Time Trial PB delta, recorded lap position.
- Radio intents added for brake temperatures, tyre pressures, brake bias, setup, wheel slip, G-force, best lap, laps remaining and telemetry/math summary.
- Brake temperatures are now retained in normalized player telemetry.

## Safety / correctness boundary
No cloud data and no ML are used by deterministic_math. It does not invent hidden values. Existing strategy/automatic engineer rules remain in place. Missing/restricted telemetry remains unavailable.

## Tests in this package
- unittest: 171 passed locally
- pytest: 179 passed + 383 subtests locally
- New tests verify exact packet sizes for all 17 IDs, decoding of the 8 newly-supported bodies, extended-state retention, and new radio intent parsing.

## Real-game validation
Run `python -m src.main --packet-stats --show-sizes` with UDP Format 2026. The game remains the final validation for live field semantics and privacy-restricted multiplayer values.


---

## Archived source: `V0.8.8_NATURAL_RADIO_NOTES.md`

# V0.8.8 Natural Offline Radio

Base: V0.8.7 FullTelemetry + MathRadio.

## Change
Radio parsing now accepts short race-radio fragments and natural variants without an LLM. Examples include `Brake info`, `Brakes?`, `Brake temp`, `Brake damage`, `Tyre info`, `Fuel?`, `ERS?`, `Gap front`, `Gap rear`, `Lap info`, `Weather info`, `Pit info`, `Race control`, `Setup`, `Slip info`, `G info`, and `Telemetry info`.

Common STT `break`/`brake` variants are normalized locally.

Specific requests still override generic requests: `brake temp` returns temperatures, `brake damage` returns brake damage, `brake bias` returns bias, while `brake info` gives a short overall brake response.

Unknown factual/noise phrases remain UNKNOWN and are not sent to the LLM.

## Verification
- unittest: 175 passed
- pytest: 183 passed, 383 subtests passed


---

## Archived source: `V0.8.9_DETERMINISTIC_FACTS_NOTES.md`

# V0.8.9 Deterministic Facts Engine

This version extends V0.8.8 without adding future prediction.

## Hard rule
A result is exposed only when it is either (a) a decoded EA game value, (b) arithmetic on decoded values, or (c) a comparison between already-observed historical values. No future extrapolation, probability, ML inference, or invented hidden state is performed by the new facts layer.

## Added
- `src/deterministic_facts.py`: JSON-safe comprehensive factual view of current session/car state, four-corner statistics, all retained extended packets, and completed measured-lap history.
- Expanded `deterministic_math.py`: full setup arithmetic plus additional Motion Ex speed, slip, force, suspension, aero-height, roll/camber and angular-motion facts.
- Completed-lap observation in `RaceStateEngine`: records observed lap time, fuel used between observed endpoints, tyre-wear deltas, position change and gap-ahead change. Bounded to 50 completed laps and reset with session state.
- Natural offline radio intents for `lap delta`, `fuel used last lap`, `positions gained/lost`, and `all facts` / factual summary.
- Tests for the factual view and radio routing.

## Important semantics
`fuel_used` and tyre-wear deltas are measured between the first available observations of successive laps. Because F1 UDP packet categories arrive independently, they are historical observed deltas, not predictions and not claimed to be perfectly synchronized to the timing line.

## Existing functionality retained
All 17 F1 2026 packet categories from V0.8.7, V0.8.8 natural radio, deterministic pit logic, automatic engineer, PTT/STT/TTS, and optional local LLM remain present.


---

## Archived source: `V0.9.0_AUTOMATIC_SAFETY_NOTES.md`

# V0.9.0 Automatic Safety / Abnormal-State Monitor

Adds unsolicited deterministic radio alerts to the existing AutomaticEngineer.

Automatically monitored when telemetry supports an objective abnormal state or an explicit project alert band:
- tyre wear and tyre damage (existing)
- wing/floor/diffuser/sidepod/brake/engine/gearbox damage (existing)
- DRS/ERS faults, engine blown/seized, wrong-way and race-control/penalty transitions (existing)
- game MFD low-fuel state and game weather forecast thresholds (existing)
- tyre surface temperature: 110 C warning, 115 C critical (110 C matches the existing radio good-status upper band; 115 C matches the existing deterministic pit-strategy high-temp threshold)
- brake temperature: 1000 C warning, 1100 C critical project alert bands
- engine temperature: 120 C warning, 130 C critical project alert bands
- tyre blistering: 25/50/75 percent
- worst engine-component wear: 50/75/90 percent
- warning count / track-limit warning increases
- current-lap valid -> invalid transition

Anti-spam: threshold bands are latched per session; a value remaining in the same band is not repeatedly announced. A jump across multiple bands announces only the most severe newly crossed band.

Important scope rule: fields that are measurements but do not have a universal safe limit are NOT given invented alarms. Examples include tyre pressure, G-force, wheel slip, suspension movement, wheel force, setup values, gaps, speed and steering. They remain available as exact facts/on-demand radio data. This keeps the automatic layer deterministic rather than pretending a generic threshold is universally safe for every car/compound/condition.


---

## Archived source: `V0.9.10.0.1_STARTUP_HOTFIX_NOTES.md`

# V0.9.10.0.1 – Multi-Session Startup Hotfix

Fixes an AI Coach startup crash introduced by first-lap S-Mode support.

## Fix
- Initialize `_s_mode_visible` before the initial Coach height calculation calls `_s_mode_extra()`.
- No telemetry, strategy, replay, or coaching math changed.
- All V0.9.10.0 UI refinements remain included.

## Validation
- 274 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.10.0.2_ERS_GRAPH_TOPMOST_HOTFIX_NOTES.md`

# V0.9.10.0.2 - ERS Graph + Game Topmost Hotfix

- ERS charge/discharge **graph traces** are now mirrored around a center zero line.
  - Charge (green) is above the center line.
  - Discharge (red) is below the center line.
- Native Windows `HWND_TOPMOST` is reasserted whenever an overlay is shown.
- Topmost is also reapplied after Qt recreates a window while toggling click-through.
- Control Center click-through behavior remains unchanged.
- For game overlay use, F1 should be in Borderless or Windowed mode; exclusive fullscreen may bypass desktop overlays.

Validation: 274 tests passed + 383 subtests passed.


---

## Archived source: `V0.9.10.0_MULTI_SESSION_VALIDATION_NOTES.md`

# V0.9.10.0 – Multi-Session Validation

Built on the user's V0.9.9.11.3 baseline and validated against real Time Trial, Qualifying, and Race recordings.

## Fixes

- Qualifying weather forecast is filtered to the active session so next-session Race forecast samples are not mixed into the current Qualifying view.
- Post-chequered / terminal-state ghost lap samples are blocked so the final lap cannot be overwritten by cooldown packets that reset the lap timer while keeping the same lap number.
- Finished-session overlay state suppresses fake live lap timer/delta/segment coaching after the result becomes terminal.
- Fuel overlay no longer treats EA's fuel-remaining-laps value as absolute race range with old 8/4-lap thresholds; presentation now reflects it as the game's fuel-laps/MFD value, and raw fuel mass no longer invents an "EA" unit.
- Added Control Center recording status indicator: REC ON / REC OFF / REC ERROR. While recording, status metadata includes packet/file details.
- Optimized 100 m gain/loss lookup in measured-performance and lap-analysis paths using binary search instead of quadratic nearest-point scans, improving multi-lap Race replay performance.
- Version banner and analysis output version updated to V0.9.10.0.

## Validation

- 271 tests passed
- 383 subtests passed
- Real Qualifying recording: 38,358 packets, final restarted Qualifying session correctly isolated, authoritative valid lap retained at 98.417 s.
- Race-specific terminal-state and performance regressions covered by dedicated tests.


---

## Archived source: `V0.9.10.0_UI_REFINEMENT_NOTES.md`

# V0.9.10.0 – Multi-Session Validation UI Refinement

This updated V0.9.10.0 test build keeps the multi-session validation fixes and adds the requested overlay refinements.

## UI refinements

- Weather, Laptime History and Available Tyre Sets now pin their content to the top and use shorter panel heights, removing the large empty top gap seen in sparse/replay states.
- Overlay text and custom-painted widget text is increased by one point for better readability.
- The Control Center is slightly taller to accommodate the larger fonts and the new ERS Battery launcher without clipping.

## S-Mode from Lap 1

- S-Mode coaching is now rendered in its own AI Coach section.
- It does not wait for a reference lap.
- When 2026 Active Aero telemetry is applicable, the row can show WAIT / on-spot / measured metres-late behavior during the first lap.
- Normal straight/turn comparative coaching still remains reference-lap based.

## ERS overlays

- Added a standalone `ERS BATTERY` overlay, opened with the new `EB` button in Control Center.
- Battery level is shown as a percentage and as MJ against the 4.00 MJ game store, with a battery-style progress bar.
- The Driver Inputs ERS graph now displays separate **CHARGE** and **DISCHARGE** traces using EA's cumulative harvested and deployed energy telemetry for the current lap.
- The current ERS store and charging/discharging/steady state remain visible in the graph header.
- Replay/lap rewinds reset the ERS plot history to avoid drawing false cross-seek lines.

## Fuel overlay

- Added a capacity-normalized fuel progress bar using `fuel remaining mass / fuel capacity`.
- The bar color still follows the MFD fuel-lap margin: deficit = red, low positive margin = amber, healthy margin = green.
- Raw fuel mass and capacity are shown below the bar without inventing an unsupported physical unit.
- Existing measured per-lap usage history remains unchanged.

## Existing V0.9.10.0 validation fixes retained

- Active-session weather filtering.
- Qualifying restart/session isolation.
- Post-chequered ghost-lap suppression.
- Finished-session live-delta/lap-timer suppression.
- REC ON/OFF/ERROR Control Center indicator.
- Faster multi-lap 100 m gain/loss lookup.

## Validation

- 273 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.11.0_DETERMINISTIC_RACE_ENGINEER_NOTES.md`

# V0.9.11.0 – Deterministic Race Engineer

Adds the dedicated race-strategy overlay discussed during multi-session validation.

## Race Engineer overlay

New Control Center button: `RE`.

The window presents only telemetry-backed or deterministic values:

- position and race lap
- current tyre compound and stint age
- maximum current tyre wear
- measured tyre-life projection when enough wear history exists
- EA MFD fuel-lap margin
- front-wing damage
- current weather and current-session rain percentage
- penalties / serve-in-pit status
- pit status
- laps remaining
- least-worn condition-compatible tyre set **if a stop is required**
- Safety Car/VSC state
- deterministic pit decision and confidence

The decision is one of:

- `STAY OUT`
- `CONSIDER BOX`
- `BOX SOON`
- `BOX THIS LAP`
- `NO DECISION`
- `FINISHED`
- `NOT APPLICABLE`

`PIT WINDOW` and `REJOIN` deliberately remain `--` until the project has enough factual track-specific information to calculate them without guessing.

## Fuel semantics correction

EA `m_fuelRemainingLaps` is treated as the game's MFD fuel-lap margin. The pit strategy engine no longer subtracts race laps remaining from it a second time.

## Session gating

The Race Engineer strategy window is active only for Race sessions. Qualifying, Practice and Time Trial do not receive fabricated race pit calls.

## Carried forward

Includes all V0.9.10.0.2 fixes and UI work, including:

- active-session weather filtering
- race-finish ghost-lap protection
- REC state in Control Center
- larger/compact overlays
- first-lap S-Mode
- ERS battery overlay
- opposed ERS charge/discharge graph
- fuel progress bar
- Win32 topmost enforcement for Borderless/Windowed game mode

## Validation

- 278 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.11.1_RACE_ENGINEER_LIVE_SYNC_HOTFIX_NOTES.md`

# V0.9.11.1 – Race Engineer Live-Sync Hotfix

Fixes the Race Engineer window showing stale CURRENT values while the rest of the overlay had advanced to a newer lap.

## Changes

- Race Engineer CURRENT fields now read from the same top-level immutable overlay snapshot used by Driver Inputs, Fuel, Weather and Tyre overlays.
- Live-synced fields include:
  - position
  - current / total lap
  - current tyre compound
  - tyre age
  - current tyre wear
  - projected tyre life
  - MFD fuel-lap margin
  - front-wing damage
  - weather / rain
  - penalties / serve status
  - pit status
  - safety-car state
- Deterministic strategy output remains sourced from the strategy engine.
- Added a strategy-frame synchronization guard: if a strategy object ever belongs to a different lap than the live snapshot, the UI shows `NO DECISION / SYNCING` instead of displaying a stale pit call.
- `STAY OUT` explanation now says `no immediate serviceable pit trigger` rather than displaying a minor damage factor as though it were the reason to stay out.

## Real replay validation

Using `Race_telemetry-20260918T064535Z-d7412ccc.areplay` at packet 39,627:

- Lap: 3 / 5
- Position: P1
- Tyre: Soft, age 2 laps
- Max wear: ~6.45%
- Fuel margin: ~+1.66 laps
- Front wing: 36%
- Decision: STAY OUT

## Regression

- 279 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.11.2_RACE_ENGINEER_DEDICATED_REFRESH_NOTES.md`

# V0.9.11.2 - Race Engineer Dedicated Refresh Hotfix

Real Race replay screenshots showed that the general HUD could advance to Lap 2/Lap 3 while the Race Engineer panel retained the frame from when it was first opened.

This release changes the architecture instead of patching individual fields:

- Race Engineer is removed from the shared 30 Hz overlay update chain.
- A dedicated 10 Hz RE timer pulls a fresh `OverlayDataProvider.snapshot()` directly from the normalized receiver state.
- Opening RE triggers an immediate fresh update.
- Replay pauses still allow the reconstructed target state to be displayed.
- RE holds its last good frame only while an interactive replay seek is rebuilding deterministic state.
- Hidden RE does not perform redundant snapshot work.
- The dedicated timer is stopped cleanly on application exit.

The CURRENT rows still read top-level live snapshot facts, while `RaceEngineerState` supplies only deterministic strategy output.


---

## Archived source: `V0.9.11.3_RACE_ENGINEER_SHARED_SNAPSHOT_SYNC_FIX_NOTES.md`

# V0.9.11.3 - Race Engineer Shared-Snapshot Sync Fix

## Root cause
The main overlay refresh updated Control Center, Coach, Driver Inputs, ERS, Delta, Live Laptime, Tyres, Fuel, Weather, Standings, Lap History and Tyre Sets, but omitted `race_engineer.update_snapshot(snapshot)`. The RE window therefore retained the state from when it was opened.

V0.9.11.2 attempted to compensate with a second QTimer. That was the wrong architecture: the strategy panel should consume the same frame as every other overlay.

## Fix
- Race Engineer is updated directly inside the normal shared HUD refresh.
- It receives the exact same `OverlaySnapshot` instance as Driver Inputs and Live Laptime.
- The independent Race Engineer timer has been removed.
- Opening RE performs one immediate provider snapshot, then normal shared refresh takes over.
- Existing stale-strategy safety guard remains in place.

## Expected replay behaviour
At any displayed frame, RE lap/position/tyre age/wear/fuel/damage must correspond to the same state shown by Driver Inputs and Live Laptime.


---

## Archived source: `V0.9.11.4_RACE_ENGINEER_ATOMIC_RENDER_FIX_NOTES.md`

# V0.9.11.4 – Race Engineer Atomic Render Fix

## Problem
The Race Engineer overlay could remain visually frozen on the state from when it was opened (for example P2 / Lap 1, Soft 0L, 0% wear) while Driver Inputs and Live Laptime continued into later laps. Telemetry, snapshots, imports and the shared refresh path were verified correct.

## Fix
- Replaced the Race Engineer multi-label renderer with a single atomic rich-text body.
- Every HUD refresh rebuilds the entire Race Engineer display from one immutable `OverlaySnapshot`.
- Position, lap, tyre, tyre age, wear, fuel, damage, weather, penalties, pit status and strategy are swapped together.
- Forces the Race Engineer body to repaint after each snapshot update.
- Keeps the stale-strategy safety guard: if strategy and live lap differ, the decision shows `NO DECISION / SYNCING`.
- Removed the previous child-label rendering path entirely.

## Validation
- 285 tests passed
- 383 subtests passed
- Source/import/shared-snapshot checks from V0.9.11.3 remain intact.

This is a rendering-layer replacement; telemetry and deterministic strategy calculations are unchanged.


---

## Archived source: `V0.9.11.5_FINAL_LAP_RACE_FINISHED_STATE_NOTES.md`

# V0.9.11.5 – Final-Lap / Race-Finished Strategy State

Built on the working V0.9.11.4 atomic Race Engineer renderer.

## Changes

- When the player reaches the scheduled final lap (`current lap >= total laps`) and the race is still active, Race Engineer now switches to a dedicated **FINAL LAP** state.
- The deterministic decision becomes **FINISH THE RACE** with high confidence.
- Final-lap Race Engineer suppresses pit-only information that is no longer useful:
  - TYRE IF BOX
  - PIT WINDOW
  - REJOIN
- Live final-lap facts remain visible: position, tyre/age, wear, tyre-life estimate, fuel margin, damage, weather, penalties, pit status and Safety Car state.
- Once the race is terminal/finished, Race Engineer switches to **RACE FINISHED** and shows the final position plus final live facts, without continuing pit strategy.
- Existing normal-lap strategy decisions are unchanged.

## Validation

- 288 tests passed
- 383 subtests passed
- Added regression coverage for final-lap decision override and finished-session override.


---

## Archived source: `V0.9.12.0_QUALIFYING_ENGINEER_NOTES.md`

# V0.9.12.0 – Qualifying Engineer

## Added
- RE automatically switches to **QUALIFYING ENGINEER** when the active event profile is Qualifying.
- Current-run facts: position, current lap, session time left, driver/run status, lap validity, tyre/age, wear, best lap, live delta, MFD fuel margin and active-session weather.
- Qualifying run information: estimated time to the timing line, estimated ability to start another lap before the clock expires, available spare tyre-set count, fastest available set by EA-provided set delta, and the EA set delta.
- Deterministic decisions based on game state only: `PUSH LAP`, `PREPARE LAP`, `BOX`, `PREPARE RUN`, `LAP INVALID`, `FINISH LAP`, `SESSION COMPLETE`, and `QUALIFYING COMPLETE`.
- Qualifying-complete terminal view.

## Preserved
- V0.9.11.5 Race Engineer final-lap / race-finished behavior.
- V0.9.11.4 atomic rendering and all previous multi-session / overlay fixes.

## Important
`ANOTHER LAP` is explicitly marked `(EST.)`. It estimates whether the car can reach the timing line before the qualifying clock expires using measured current-lap progress/pace, falling back to the best/reference lap when necessary. It is not an invented game flag.


---

## Archived source: `V0.9.12.1_QUALIFYING_ENGINEER_ROUTING_FIX_NOTES.md`

# V0.9.12.1 – Qualifying Engineer Routing Fix

- Normalize `event_profile` before RE session routing.
- Route QUALIFYING explicitly before the Race Engineer fallback.
- Built from source only: packaged `__pycache__` and pytest caches are removed.
- Keeps V0.9.12.0 Qualifying Engineer logic and all V0.9.11.5 Race Engineer behavior.
- Real Qual replay packet 23412 resolves to `QUALIFYING`, One-Shot Qualifying, Flying lap, valid.


---

## Archived source: `V0.9.12.2_QUALIFYING_ENGINEER_SESSION_ROUTING_FIX_NOTES.md`

# V0.9.12.2 – Qualifying Engineer Session Routing Fix

- RE routing now recognizes qualifying from either the normalized event profile or the session-type name.
- One-Shot Qualifying, Short Qualifying and full qualifying sessions cannot fall through to the Race-only fallback merely because one routing field is stale or formatted differently.
- Default panel title changed to SESSION ENGINEER so the loaded overlay module can be visually identified before the first session snapshot arrives.
- Race and Qualifying renderers still use the same shared immutable overlay snapshot and atomic body renderer.


---

## Archived source: `V0.9.12.3.1_QUALIFYING_ENGINEER_STARTUP_HOTFIX_NOTES.md`

# V0.9.12.3.1 – Qualifying Engineer Startup Hotfix

Fixes a startup crash introduced in V0.9.12.3 where
`QualifyingEngineerOverlayWindow` inherited from `RaceEngineerOverlayWindow`
before the base class had been defined.

Changes:
- Move `QualifyingEngineerOverlayWindow` below `RaceEngineerOverlayWindow`.
- Preserve dedicated Race and Qualifying engineer windows and session-aware RE routing.
- Add a regression test for class declaration order.
- Update the startup/version banner to V0.9.12.3.1.

Validation:
- 307 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.12.3_DEDICATED_QUALIFYING_ENGINEER_WINDOW_NOTES.md`

# V0.9.12.3 – Dedicated Qualifying Engineer Window

## Fix
Qualifying no longer shares the same QWidget instance as Race Engineer.

- Added a dedicated `QualifyingEngineerOverlayWindow`.
- The Control Center `RE` button is now a session-engineer launcher.
- The shared snapshot router selects Race Engineer or Qualifying Engineer.
- If the session becomes qualifying while RE is already visible, the Race window is hidden and the Qualifying window is shown at the same screen position.
- Qualifying window directly calls the qualifying renderer; it contains no Race-only fallback path.
- Race Engineer remains separate and unchanged for Race sessions.

## Real replay validation
At Qual replay packet 28,463 / 38,358:
- event profile: QUALIFYING
- session type: One-Shot Qualifying
- lap: 1
- driver status: Flying lap
- lap valid: true
- dedicated routing result: Qualifying Engineer

## Regression
- 305 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.13.0_LOW_LATENCY_TELEMETRY_CORE_NOTES.md`

# V0.9.13.0 – Low-Latency Telemetry Core

This release keeps V0.9.12.3.1 Race/Qualifying Engineer behavior and focuses on reducing end-to-end software latency in the live telemetry, overlay, analysis and replay paths.

## Live telemetry / state hot path

- Reworked generic binary layout decoding to use index-based reads over one unpacked tuple instead of recursive generators / repeated `next()` calls.
- Reduced unnecessary whole-field car synchronization for packet categories that do not change car state.
- Tyre-set packets now update only their target car rather than rebuilding tyre-set state for the whole active field.
- Reduced unnecessary Automatic Engineer evaluation on packet families that cannot change an engineer decision.
- Pit-strategy evaluation is limited to relevant state changes.
- Cached event/session applicability data that is immutable within the active session.
- Removed expensive repeated recursive `dataclasses.asdict()` work from the telemetry hot path.
- Increased the UDP receive buffer and removed repeated per-packet socket timeout reconfiguration.

## Overlay hot path

- Overlay refresh target increased from about 30 Hz to about 60 Hz with a precise Qt timer.
- Reference-lap track structure is cached rather than rebuilt every frame.
- The aligned current-vs-reference trace is calculated once per overlay snapshot and reused by delta, marker, straight/turn coaching and segment history calculations.
- Repeated nearest-distance trace lookups use binary search.
- Removed repeated set construction / sorting from live straight comparison calculations.
- Snapshot construction was significantly reduced so the telemetry state lock is held for less time.

## Recording

- Raw telemetry recording now performs one buffered write per UDP datagram instead of multiple writes while preserving the ARERPL01 replay format.

## Interactive replay / seeking

- Replay checkpoints are now immutable serialized byte snapshots instead of recursive `deepcopy()` graphs.
- Checkpoint restore deserializes before taking the receiver state lock, then swaps state under a short lock.
- Periodic checkpoints are created every 4096 packets in addition to lap boundaries, bounding the amount of deterministic fast-forward required after a slider seek.
- Up to 64 checkpoints are retained per interactive replay.
- Legacy in-memory dictionary checkpoints remain supported for development/test compatibility.

## Measured validation

On the provided real recordings:

- Qualifying replay: 38,358 / 38,358 packets processed; 1 completed valid lap retained.
- Race replay: 81,159 / 81,159 packets processed; 5 completed laps retained; best valid lap 3.
- Time Trial replay: 92,262 / 92,262 packets processed; 7 completed laps retained; best valid lap 3.

Checkpoint benchmark around race packet 25,000 in this test environment:

- Old deep-copy checkpoint creation: ~43.9 ms
- V0.9.13 serialized checkpoint creation: ~9.6 ms
- V0.9.13 checkpoint restore: ~13.3 ms

Real replay cached-seek samples after checkpoint warm-up:

- packet 35,000: ~491 ms rebuild
- packet 49,000: ~225 ms rebuild

The exact timings will vary by CPU and active overlays, but the deterministic results are unchanged.

## Regression status

- 309 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.13.1_ZERO_DRIFT_LOW_LATENCY_CORE_NOTES.md`

# V0.9.13.1 – Zero-Drift Low-Latency Core

This release keeps V0.9.13.0 behavior as the functional baseline and focuses on two separate latency goals:

1. **No cumulative realtime drift**: at 1.0x replay, recorded/game time must stay locked to wall time instead of becoming progressively late because packet-processing cost is added to every interval.
2. **More CPU headroom in the live hot path**: packet decode and normalized state updates should consume substantially less of each telemetry frame, leaving more room for overlay, recording, TTS and Windows scheduling jitter.

## Drift-free interactive / overlay replay

V0.9.13.0 interactive replay waited each recorded packet interval *after* processing the previous packet. Even a small decode/state/engineer cost therefore accumulated continuously. For example, 0.2 ms of work across 300 packets/s adds about 60 ms of delay every real second.

V0.9.13.1 uses one absolute monotonic replay clock:

- Packet deadlines are derived from recorded timestamps and the current replay speed.
- Decode/state/engineer work is automatically absorbed by the following wait.
- If processing is briefly late, subsequent packets catch back up to the original clock instead of propagating the delay.
- Pause time is excluded from the replay clock.
- Seek, speed changes, timestamp-mode changes and range changes invalidate/re-anchor timing immediately.
- The controller exposes current `clock_drift_s` for validation/diagnostics.

A dedicated regression test deliberately adds 3 ms of processing work to every packet. For a 0.400 s recording:

- V0.9.13.0 interactive scheduler: ~0.468 s
- V0.9.13.1 absolute scheduler: ~0.403 s

The remaining ~3 ms is the final packet's deliberately injected processing cost, not cumulative drift.

## Compiled fixed-layout decoding

F1 packet schemas are fixed. V0.9.13.0 still interpreted each layout recursively after `struct.unpack_from`, repeatedly walking fields and nested 24-car records.

V0.9.13.1 compiles each layout once at import time into direct tuple-index constructors. Runtime decoding now jumps straight from the unpacked tuple to the same immutable typed dataclasses without re-interpreting the schema.

Representative 4,000-packet decode benchmark in this environment:

- V0.9.13.0: ~106.7 microseconds/packet (~9,374 packets/s)
- V0.9.13.1: ~49.4 microseconds/packet (~20,237 packets/s)

This is a decoder-only synthetic benchmark; real results vary by CPU and packet mix.

## Local-player-only high-rate state hydration

The normalized state previously rebuilt all active cars for every high-rate `telemetry`, `status`, `damage` and `telemetry2` packet even though current Race Engineer/overlay logic consumes those families only for the local player (and secondary local player, if present).

V0.9.13.1 now:

- keeps full-field `LapData` and `Participants` processing for positions, identities, gaps and neighbours;
- keeps primary and secondary local player telemetry/status/damage/aero fully current;
- avoids continuously rebuilding unused opponent high-rate car state.

This removes a large amount of object construction while preserving the field data actually consumed by the application.

## End-to-end synthetic hot-path benchmark

Representative 8,001-packet mix (20 active cars, repeated Lap/Telemetry/Status/Telemetry2 packets, TTS disabled):

- V0.9.13.0: ~221 microseconds/packet (~4,525 packets/s)
- V0.9.13.1: ~107 microseconds/packet (~9,300 packets/s)

That is roughly a 2x increase in packet-processing headroom in this test environment.

## Safety / behavior preservation

- No packet dropping or stale-state coalescing was introduced.
- Events, penalties, race-control data and lap packets still traverse the normal deterministic pipeline.
- Recording format remains `ARERPL01`.
- Replay checkpoints remain compatible with the V0.9.13.0 checkpoint schema within the same process/version workflow.
- Existing deterministic decision logic was not relaxed or throttled.

## Regression status

- Existing V0.9.13.0 suite retained.
- Added a dedicated no-cumulative-drift regression test.
- Full regression result: **311 tests passed, 383 subtests passed**.
- Re-run with `python -m pytest -q` from the project root.


---

## Archived source: `V0.9.14.0_REAL_TIME_DECISION_PIPELINE_NOTES.md`

# V0.9.14.0 – Real-Time Decision Pipeline

## Objective

V0.9.13.1 fixed cumulative replay drift and substantially reduced decode/state cost. V0.9.14.0 keeps that core and focuses on the complete live path:

`UDP receive -> decode -> normalized state -> deterministic decision -> radio queue -> Piper synthesis -> audio start`

The design goal is not artificial hard-real-time guarantees on Windows/Python. The goal is to remove avoidable software stalls, prevent stale/routine radio from blocking urgent calls, and make the remaining latency measurable.

## 1. UDP diagnostics moved off the hot path

Previously `UDPReceiver.run()` called the once-per-second `print_status()` directly from the same loop that drains the UDP socket. State formatting and terminal I/O can take many milliseconds depending on Windows console/UI scheduling.

V0.9.14.0 runs diagnostics in a dedicated reporter thread. The UDP thread now performs only:

1. `recvfrom()`
2. immediate monotonic receive timestamp
3. packet processing
4. return to `recvfrom()`

A slow console refresh therefore cannot deliberately stop packet reception.

## 2. Asynchronous lossless recorder

Live recording previously called `TelemetrySessionRecorder.record()` from `process_packet()`. Buffered files are normally fast, but an occasional filesystem/flush stall belongs nowhere near the decision path.

`AsyncTelemetrySessionRecorder` now queues the immutable UDP bytes and receive timestamp to a dedicated writer thread. The format remains exactly `ARERPL01`; no packet coalescing or dropping was introduced. Shutdown drains the queue before closing the replay file and metadata.

The live status display exposes pending recorder writes so a disk that cannot keep up is visible.

## 3. Immediate critical-radio pre-emption

V0.9.13.1 could terminate an already-playing lower-priority radio line, but if Piper was still synthesizing that sentence there was no playback process to terminate. An urgent flag/penalty/safety message could therefore wait for obsolete synthesis to finish.

V0.9.14.0 gives the active radio item a cancellation token. When a newly queued message has a higher radio rank:

- the current item is marked cancelled immediately;
- active playback is stopped;
- if Piper is still synthesizing, the old WAV is discarded before playback begins;
- the urgent message becomes the next queue item.

Track-limit priority behavior, driver-requested radio ownership, stale-message rules and replaceable live-state families are preserved.

## 4. Native Windows Piper WAV playback

The previous Piper path launched a new PowerShell process and `.NET SoundPlayer` for every sentence. Process creation adds variable startup time and jitter.

V0.9.14.0 first uses Python's Windows stdlib `winsound` for the synthesized WAV. Playback remains interruptible in 5 ms polling slices for PTT or higher-priority calls. The existing PowerShell SoundPlayer implementation remains as a compatibility fallback if native playback cannot be used.

A regression test supplies a fake Windows `winsound` module and verifies the native path does not call the PowerShell fallback.

## 5. Static urgent/assist prompt cache

Short repeated calls can reuse their synthesized WAV after the first occurrence. The cache is limited to known static phrases, including:

- Track limits
- DRS
- S Mode
- Overtake available
- Safety Car / Virtual Safety Car
- blue/yellow/green flag calls

The cache key includes the Piper model identity, voice speed, volume and text. Cached WAVs live under `logs/tts_cache/`, which is already ignored by Git. Dynamic telemetry sentences are not cached.

## 6. Removed redundant performance sampling

`RaceStateEngine.update()` previously ran completed-lap observation and measured-performance sampling for every accepted packet family. Several packet families cannot change any input used by those routines.

V0.9.14.0 limits those calls to relevant packet categories while keeping motion/lap/telemetry/status/aero/history/event/final observations needed by measured lap analysis.

## 7. Optional latency instrumentation

`--latency-stats` enables a rolling `LatencyMonitor` with no sorting/formatting in the packet path. Percentiles are calculated only when diagnostics request a snapshot.

Reported measurements include:

- decoder average/P95
- state-update average/P95
- deterministic-decision average/P95
- full packet-to-decision average/P95/max
- speech dispatch cost
- radio queue wait average/P95/max
- queue-to-audio-start average/P95/max
- current/max radio queue depth
- critical pre-emption count

Instrumentation is opt-in. With the flag disabled, per-packet high-resolution timing calls and TTS latency callbacks are skipped.

## Synthetic validation

Repeated 8,002-packet mixed workloads in this environment (TTS off, diagnostics off) produced averages of approximately:

- V0.9.13.1: **133.8 µs/packet**
- V0.9.14.0: **128.3 µs/packet**

That benchmark is synthetic and CPU-dependent. The architectural gains from removing console/file-I/O stalls are intended primarily to reduce worst-case jitter rather than only improve the mean.

## Regression status

- V0.9.13.1 zero-drift tests retained.
- Decoder parity tests retained.
- Added latency-monitor tests.
- Added lossless asynchronous-recorder drain/roundtrip test.
- Added synthesis-stage critical pre-emption test.
- Added static prompt-cache identity test.
- Added native Windows WAV playback/fallback isolation test.
- Updated old build-identity assertions to the V0.9.14.0 banner.
- Final result: **316 tests passed, 383 subtests passed**.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```


---

## Archived source: `V0.9.14.1_RADIO_TRANSCRIPT_OVERLAY_NOTES.md`

# V0.9.14.1 – Radio Transcript Overlay

## Goal

Add a dedicated overlay that answers three practical questions while driving:

1. What did the driver actually say over PTT?
2. What answer did the engineer give?
3. What other automatic messages were received over race radio?

The implementation must not put transcript formatting/rendering in the UDP telemetry hot path.

## Architecture

### Thread-safe radio history

`src/radio_transcript.py` provides a bounded `RadioTranscriptStore` containing immutable entries:

- sequence/revision
- role (`DRIVER` or `ENGINEER`)
- text
- game session time
- engineer message key/priority when applicable

The store uses its own very short lock and retains at most 200 entries.

### Driver transcript source

`RaceStateReceiver._on_transcript()` records the text produced by the existing offline faster-whisper worker. This means DRIVER entries are the same transcript used by deterministic voice-command routing / local LLM routing.

### Engineer transcript source

When TTS is enabled, an ENGINEER entry is created at `SpeechOutput._mark_audio_start()` rather than at decision generation or queue insertion. Therefore messages removed because they became stale or were superseded do not appear as received radio.

The callback is guarded so a transcript/UI failure cannot interrupt audio playback.

When TTS is disabled, generated engineer text is recorded at submission time so replay/debug sessions can still inspect what the radio system would have said.

## Overlay

`RadioTranscriptOverlayWindow` is an independent always-on-top panel.

Features:

- Control Center launcher: **RT**
- DRIVER and ENGINEER visual labels
- game-session timestamps
- rich-text word wrapping
- automatic scroll to newest entry
- bounded history
- `CLR` button
- hidden by default like strategy/session overlays
- click-through support inherited from the existing overlay framework

The 60 Hz overlay timer only snapshots/renders the transcript when the radio window is visible, and the window itself skips rebuilding unless the transcript revision changed.

## Overlay + PTT

V0.9.14.0 rejected all `--overlay --ptt` combinations. V0.9.14.1 permits the default raw-HID PTT backend with Qt overlays. Raw HID polling is safe on the receiver worker thread used by overlay runtime.

The pygame PTT backend remains rejected in combination with `--overlay`, because SDL/pygame controller polling can require the application/main UI thread on Windows.

Recommended live command:

```powershell
.\.venv\Scripts\python.exe -m src.main --overlay --ptt
```

## Low-latency behavior

No transcript rendering occurs on the UDP receive thread.

- DRIVER writes occur on the STT worker.
- Heard ENGINEER writes occur on the TTS worker at audio start.
- Qt reads occur on the UI thread.
- Silent (`--no-tts`) engineer transcript writes happen only when an engineer decision actually produces a message, not once per telemetry packet.

The V0.9.14.0 decision pipeline and V0.9.13.1 zero-drift scheduler remain unchanged.

## Validation

Final automated validation:

```text
321 passed
383 subtests passed
```

New tests cover:

- ordered DRIVER/ENGINEER history
- bounded history + clear revision
- audio-start transcript callback
- RT launcher and incremental refresh wiring
- raw-HID overlay/PTT compatibility guard

PySide6 is not installed in the development container, so the real Qt window itself could not be launched here. The existing project already treats PySide6 as a runtime dependency; source wiring/compilation and all automated regressions pass.


---

## Archived source: `V0.9.14.2_RACE_RADIO_STT_NOTES.md`

# V0.9.14.2 RACE-RADIO STT

Built directly on V0.9.14.1 Radio Transcript Overlay.

## Race-radio speech recognition

- Default faster-whisper model changed from `base.en` to `small.en`.
- Added an F1/race-engineer initial prompt covering tyres, brakes, fuel, ERS, DRS, S Mode, gaps, damage, weather, penalties, track limits, pit/box, wings, setup, lap time, position, Safety Car/VSC, undercut and overcut vocabulary.
- Added matching faster-whisper hotwords where supported.
- Uses deterministic beam search (`beam_size=5`, `temperature=0`).
- Each PTT recording is treated as an independent utterance (`condition_on_previous_text=False`) so a bad previous radio transcript cannot bias the next one.
- Short-radio VAD is tuned with lower speech threshold, short silence cutoff and 220 ms speech padding to reduce clipped first/last words.
- Compatibility fallback retains transcription on older faster-whisper versions that do not support hotwords/VAD parameter keywords.

## Control Center audio device selection

The Control Center now contains two detected-device selectors:

- `MIC` — PortAudio input device used by the next PTT recording.
- `OUT` — output endpoint used for Piper radio playback.

Both include `System default` and all compatible devices detected by `sounddevice` at application startup.

Changing the microphone while PTT is held is rejected safely; release PTT and select again. A concrete output endpoint uses a low-latency PortAudio `RawOutputStream`. `System default` retains the V0.9.14.0 native Windows `winsound` path.

CLI selection is also available:

```powershell
python -m src.main --overlay --ptt --mic-device 13 --audio-device 13
```

Use `--list-audio-devices` to print input/output capabilities and indices.

## Timing / architecture

- STT still runs entirely on its existing worker and never enters the UDP telemetry thread.
- Device enumeration happens during overlay/control-center setup, not per telemetry packet.
- PTT capture remains callback-based and isolated from telemetry.
- Explicit-device playback remains interruptible by PTT and higher-priority radio calls.
- V0.9.13.1 zero-drift replay and V0.9.14.x real-time decision pipeline are unchanged.

## Validation

- Python source compile check: passed.
- Full regression suite: **326 tests passed, 383 subtests passed**.


---

## Archived source: `V0.9.14.3_PIT_RADIO_RELIABILITY_HOTFIX_NOTES.md`

# V0.9.14.3 PIT RADIO RELIABILITY HOTFIX

Built directly on V0.9.14.2 RACE-RADIO STT.

## Fixes

- Corrected the no-live-car `PitAssessment` constructor, which omitted the `serve_penalty_in_pit` field and raised `TypeError` during a `Should I box?` request before the reply could be queued.
- When no player telemetry is available, pit radio now returns the already-safe explicit response: `Live car data is unavailable.`
- Added a defensive runtime fallback around the richer deterministic pit/service-plan path so an unexpected formatter/strategy exception cannot make a radio request silently disappear.

## Scope

No telemetry decoding, zero-drift scheduling, STT tuning, MIC/OUT device selection, deterministic strategy thresholds, or overlay rendering logic was changed by this hotfix.


---

## Archived source: `V0.9.14.4_RADIO_COMMAND_RELIABILITY_NOTES.md`

# V0.9.14.4 RADIO COMMAND RELIABILITY

Built directly on V0.9.14.3.

## Changes

- Added a conservative race-radio transcript normalizer before intent routing.
- Collapses Whisper repetition loops such as `brake temperature` repeated dozens of times.
- Recovers observed high-confidence near misses such as `lap behind` -> `gap behind` and `style should I use` -> `which tyres should I use`.
- Unknown conversation/noise is still left unknown rather than force-matched to a command.
- Driver transcript keeps the raw short recognition and shows the interpreted command when correction was applied.
- Pathological long repetition loops are displayed as the cleaned phrase so the transcript stays readable.
- Expanded deterministic radio coverage across tyres, brakes, setup, power unit, race progress, traffic, aero/overtake systems, pit status, weather, track limits, timing and performance.
- Added `RADIO_COMMANDS.md` as the supported command guide.
- Shortened common race answers: fuel is reported primarily in laps, gaps are rounded to hundredths, healthy low tyre wear is summarized rather than reading five-decimal values.
- Visible transcript session timestamps are clamped to heard/request order so queued older telemetry calls cannot make the transcript clock run backwards.
- S Mode assist now calls once per actual availability/mode opportunity and re-arms only after the state changes, preventing repeated S-Mode chatter.
- Known deterministic commands are normalized before LLM routing, preventing an STT near miss such as `style should I use?` from producing a conflicting LLM tyre recommendation.

## Validation

- Full regression suite plus V0.9.14.4 command reliability tests.
- Tests include the real failures observed in the Race replay: repeated brake-temperature hallucination, `lap behind`, `style should I use`, lap progress commands, and transcript ordering.


---

## Archived source: `V0.9.14.5_SESSION_SUMMARY_RADIO_POLISH_NOTES.md`

# V0.9.14.5 — Session Summary + Radio Polish

Built on V0.9.14.4.

## Finish and session summary
- Uses EA Final Classification as the authoritative finishing result.
- Position-dependent finish radio for win, podium, points, lower finishes, DNF/retirement, DSQ and not-classified states.
- Automatically builds and saves `analysis/session_summary-*.json` and `.txt`.
- Adds a dedicated **SS** Session Summary overlay in Control Center and auto-opens it when final classification arrives.
- Summary includes final/grid positions, laps, best/average valid lap when available, pit stops, penalties/warnings, tyre stints, peak tyre temperature/wear/damage, front-wing damage, engine/gearbox wear and weather changes.
- A concise spoken race summary follows the finish call.

## Radio polish
- `lap remaining`, `laps remaining`, `remaining lap`, `remaining laps`, `laps left`, `how many laps left` share one deterministic intent and answer.
- Correct singular/plural: `1 lap remaining`, `1 lap completed`.
- `sector` maps to current sector.
- `ahead driver` / `behind driver` map to driver ahead/behind.
- Generic tyre info/status is concise like brake info; exact temperatures remain available via `tyre temperature(s)` / detailed requests.
- Car-status tyre wear is rounded to one decimal.
- Best/fastest-lap radio falls back to measured completed laps and Final Classification when Session History is unavailable.
- S-Mode automatic reminder cooldown increased to reduce repeated chatter.


---

## Archived source: `V0.9.14.6_FINISH_PRIORITY_COLLAPSIBLE_COACH_NOTES.md`

# V0.9.14.6 — Finish Priority + Collapsible Coach

Built on V0.9.14.5.

## Finish/result radio reliability

- Final Classification remains the strongest/authoritative result source.
- Added fallback finish detection from player LapData result status (`Finished`, DNF, DSQ, not classified, retired).
- Added a replay-safe fallback for recordings that stop before Final Classification: once the chequered flag has been seen, completion of the scheduled final measured lap is enough to trigger the finish call.
- The position-dependent finish call is inserted ahead of ordinary lap/performance chatter.
- Final-lap automatic lap/performance summaries are suppressed when the finish call triggers on that packet.
- If Final Classification arrives later, the Session Summary overlay/files are refreshed with authoritative classification data without speaking the win/result call twice.
- Session-summary fallback now reports the full scheduled lap count when LapData already says `Finished`.

## AI Coach section controls

The AI Coach window now has independent `- / +` collapse controls for:

- Live Delta graph
- Real-Time Turn/Straight Coaching
- Current Lap / Previous Segments

Collapsing a section only hides that section's body and reduces the coach window height; it does not minimize or hide the AI Coach window. The existing whole-window collapse behavior remains available separately.

## Validation

- 344 pytest tests passed
- 383 unittest subtests passed
- Added V0.9.14.6 regression coverage for finished-LapData fallback, chequered-plus-final-lap fallback, and the three independent coach section controls.


---

## Archived source: `V0.9.15.0_WHEEL_TELEMETRY_BRIDGE_NOTES.md`

# V0.9.15.0 — Wheel Telemetry Bridge

- Built on V0.9.14.6 without changing race-engineer decision behaviour.
- Added non-blocking 50 Hz USB CDC telemetry bridge for GamePad Pro Receiver S3.
- Fixed 15-byte CRC-8/ATM frame; no text parsing.
- Sends only wheel-required fields: speed, gear, position, RPM/rev lights, shift light, flag, ERS mode, DRS, low fuel and low ERS.
- Supports live UDP and deterministic `.areplay` replay.
- `--wheel-port COMx` forces the receiver port; unique ESP32/TinyUSB port can auto-detect.
- `--no-wheel-telemetry` disables this output.


---

## Archived source: `V0.9.15.1.1_WHEEL_HEALTH_RX_HOTFIX_NOTES.md`

# V0.9.15.1.1 — Wheel Health RX Hotfix

- Keeps DTR asserted on the ESP32-S3 native USB CDC COM port.
- Fixes the asymmetric case where Race Engineer telemetry reached the Receiver but V8.3.1 health frames did not reach the PC.
- Improves `--wheel-health-check` diagnostics with explicit health-frame receive state.
- No deterministic engineer, replay, radio, overlay decision, telemetry payload, HID or firmware functional changes.
- GamePad Pro remains V8.3.1; no Receiver reflash is required for this hotfix.


---

## Archived source: `V0.9.15.1.2_RECEIVER_RECONNECT_HOTFIX_NOTES.md`

# V0.9.15.1.2 — Receiver Reconnect Hotfix

PC-only reliability hotfix. GamePad Pro V8.3.1 firmware is unchanged.

## Fixes

- Receiver USB CDC automatically reconnects after a physical S3 disconnect/reset.
- Remembers the Receiver USB identity and follows it if Windows assigns a different COM number after re-enumeration.
- Falls back to a unique ESP32/TinyUSB serial device when the requested COM port disappears and the Receiver returns on another COM number.
- Raw-HID PTT no longer exits permanently on `read error`; it waits for the Receiver HID interface to return and reopens it automatically.
- Existing verified PTT button mapping is reused after reconnect; no recalibration is required.
- Telemetry, deterministic engineer logic, radio logic, overlays and game-control firmware behavior are unchanged.

## Expected console sequence

```text
[WHEEL] Receiver USB link lost while reading: ...
[PTT] HID link lost: read error; waiting for Receiver...
[WHEEL] Receiver USB RECONNECTED: COM5 @ 115200
[PTT] HID RECONNECTED: TinyUSB HID | logical button 6
[WHEEL] Receiver peers: Wheel=CONNECTED | Pedals=CONNECTED | MotorTemp=CONNECTED
```


---

## Archived source: `V0.9.15.1.3_HIERARCHICAL_LINK_STATUS_HOTFIX_NOTES.md`

# V0.9.15.1.3 — Hierarchical Link Status Hotfix

PC-side-only hotfix. No GamePad Pro firmware reflash is required.

- Receiver USB is now the parent health state for Wheel, Pedals and MotorTemp.
- On Receiver USB loss, all downstream peer states are immediately invalidated and displayed as DISCONNECTED.
- Stale peer packet ages are cleared when the Receiver disappears.
- After Receiver USB reconnects, peer states show WAITING until the first fresh V8.3.1 health frame arrives.
- Existing reconnect, PTT HID recovery, telemetry, replay and engineer logic are unchanged.


---

## Archived source: `V0.9.15.1_WHEEL_LINK_RELIABILITY_NOTES.md`

# V0.9.15.1.1 — Wheel Health RX Hotfix

Built on V0.9.15.0 with no deterministic race-engineer behaviour changes.

## Changes

- Hardened GamePad Pro Receiver serial reconnect; retry cadence is 0.5 s.
- Added a receiver -> PC binary health frame (25 bytes, 2 Hz, CRC-8/ATM).
- Health reports Receiver USB, wheel ESP-NOW, pedal ESP-NOW, MotorTemp ESP-NOW, peer packet ages, and packet counters.
- Added LOST / RECONNECTED transition logging during live sessions and replays.
- Added Control Center hardware status for Receiver, Wheel, Pedals and Motor Temp.
- Added `--wheel-health-check --wheel-port COMx` for bench testing without starting F1.
- The health path is diagnostic only; it is never used by deterministic engineering logic.

## Compatibility

The V0.9.15.0 15-byte PC -> receiver telemetry frame is unchanged. V8.3.1 adds the reverse health frame while preserving HID controls and ESP-NOW input formats.


---

## Archived source: `V0.9.15.2.1_UI_STYLESHEET_HOTFIX_NOTES.md`

# V0.9.15.2.1 UI Stylesheet Hotfix

- Fixed malformed Control Center runtime-toggle `QToolButton` stylesheet.
- Removed the extra closing brace that caused repeated `Could not parse stylesheet of object QToolButton(...)` messages in the console.
- No runtime-toggle logic changes.
- No telemetry, radio, overlay behavior, wheel-link behavior, or GamePad Pro firmware changes.


---

## Archived source: `V0.9.15.2_CONTROL_CENTER_RUNTIME_TOGGLES_NOTES.md`

# V0.9.15.2 — Control Center Runtime Toggles

Built on the stable V0.9.15.1.3 Receiver/link baseline.

## New

The Control Center can now change these features while Race Engineer is already running:

- TTS — enable/disable engineer speech immediately.
- PTT — start/stop the raw-HID wheel PTT worker without restarting the app.
- STT — enable/disable offline Whisper transcription.
- LLM — enable/disable local Ollama reasoning. Deterministic radio remains independent.
- REC — start/stop lossless raw telemetry recording in a live session.

The status value itself is the control: click `Enabled/Disabled` (or `On/Off` for REC).

Existing `Pause` and `CT` controls remain unchanged. `Replay` remains a read-only mode/status indicator because replay file selection is still a launch-time choice. Recording is intentionally not runtime-toggleable while replaying, to avoid accidentally recording a recording.

## Runtime behavior

- CLI switches still define startup defaults and remain supported.
- UI changes apply immediately and are reflected back into the Control Center from the live receiver state.
- PTT runtime switching is supported with the raw HID backend used by the overlay.
- Enabling STT/LLM starts their workers lazily if they were not active at startup.
- Disabling TTS interrupts current non-critical playback and prevents new speech while deterministic engineer decisions continue normally.
- Turning REC on creates a normal `.areplay` recording in `recordings/`; turning it off flushes and closes that file cleanly.

No GamePad Pro firmware changes are required.


---

## Archived source: `V0.9.16.0_DETERMINISTIC_STRATEGY_ENGINE_NOTES.md`

# V0.9.16.0 Deterministic Strategy Engine

This release adds race-strategy calculations without changing the stable wheel telemetry bridge, Receiver health/reconnect path, runtime Control Center toggles, replay clock, or existing deterministic radio behavior.

## Deterministic inputs only

The strategy engine uses values already present in `RaceState`, the game's tyre-set packet and completed measured laps. It does not use an LLM for strategy decisions and does not invent track-specific pit loss, rejoin position, degradation curves or undercut gains.

## Added calculations

- Race laps remaining.
- EA fuel-laps margin classification: safe / tight / short.
- Median maximum-wheel tyre-wear rate from the last three completed laps on the fitted tyre set.
- Projected maximum tyre wear at the finish.
- Laps to 80% and 90% wear when a measured wear rate exists.
- Deterministic `tyres can finish` result when enough measured data exists.
- Completed-lap gap-ahead trend.
- Measured current-stint vs previous-stint average pace.
- Safety Car/VSC context combined with the existing deterministic pit recommendation.
- Race-distance-aware replacement tyre choice using game-reported usable life.

## Pit engine integration

The existing pit engine now treats a measured projection to 90%+ wear at the finish as a serviceable strategic trigger. A projection to 80%+ is elevated context. The calculation is based only on observed completed-lap wear deltas on the fitted set.

## New radio commands

- `Strategy update`
- `Can I make it to the end?`
- `Can I make these tyres last?`
- `How much fuel margin do I have?`
- `Fuel to finish`
- `Am I catching the car ahead?`
- `Gap trend`
- `Compare stint pace`
- `Will I come out in traffic?`
- `Can I undercut the car ahead?`
- `Is the undercut working?`
- `Is this a good Safety Car pit stop?`
- `Why should I box?`

`Why should I box?` stays inside the deterministic pit engine. Rejoin and undercut questions return an explicit data limitation until a factual pit-loss/post-stop model exists.

## Validation

- 368 pytest tests passed.
- 383 legacy subtests passed.


---

## Archived source: `V0.9.16.1.1_GAP_TREND_SANITY_HOTFIX_NOTES.md`

# V0.9.16.1.1 — Gap Trend Sanity Hotfix

Targeted hotfix only. GamePad Pro V8.3.1 is unchanged.

## Fixes
- Resets rolling gap history when the car ahead, race position, pit status, or pit-lane state changes.
- Resets after timer gaps/replay discontinuities and teleport-like gap jumps.
- Uses a robust median of consecutive same-opponent gap slopes instead of a first/last two-point extrapolation.
- Requires at least five samples / four seconds of stable data.
- Rejects implausible or highly scattered trends and reports the trend as unavailable rather than speaking nonsense.
- Ignores absurd completed-lap gap deltas (>5 s/lap) for the trend response.
- No changes to tyre, fuel, pit, radio priority, wheel telemetry, controls, or GamePad Pro firmware.


---

## Archived source: `V0.9.16.1_STRATEGY_RADIO_RELIABILITY_NOTES.md`

# V0.9.16.1 — Strategy Radio Reliability

Targeted fine-tuning on V0.9.16.0. No GamePad Pro changes.

- Driver-requested radio replies now outrank routine Track Limits / S Mode / coaching chatter.
- Routine playback that slips in while STT finishes is cancelled before the requested answer.
- Added conservative STT recovery for `compare stint pace`, including observed near-misses such as `compare shift paste` and `compassioned place`.
- `will I come out in the traffic` and equivalent wording route to deterministic rejoin-traffic logic.
- Added strategy vocabulary to Whisper prompt/hotwords: stint pace, traffic, rejoin, undercut, overcut, tyre life, fuel margin.
- Gap trend now prefers completed-lap evidence but can fall back to a factual 1 Hz rolling same-car gap window after 4 seconds. Rolling results are reported per 10 seconds rather than inventing a lap-time conversion.
- Stay-out pit calls with serviceable wing damage now say `If you pit, replace the front wing` instead of sounding internally contradictory.
- Underlying V0.9.16.0 strategy mathematics otherwise unchanged.


---

## Archived source: `V0.9.17.0_EXTERNAL_REFERENCE_LIVE_PERFORMANCE_COACH_NOTES.md`

# V0.9.17.0 — External Reference Live Performance Coach

## Goal
Use deterministic telemetry to train against either your own best lap or a compatible reference lap recorded by another driver.

## Added
- `--reference-lap FILE`: loads a full measured external lap as the live coach reference.
- `--export-reference-lap FILE`: exports the best valid lap from an `.areplay` as a reusable reference.
- `--reference-lap-number N`: exports a specific valid completed lap.
- External-reference coaching remains distance-aligned and deterministic.
- Completed laps receive concise actionable coaching such as braking-point, minimum-speed, throttle-pickup, exit-speed, and wheel-slip differences.
- Existing own-best/previous/manual reference modes remain unchanged.

## Important limitation
A leaderboard time, screenshot, or onboard video alone is not enough for metre-by-metre deterministic coaching. The reference must contain compatible telemetry samples (or be converted into the Race Engineer reference format).


---

## Archived source: `V0.9.17.1_AI_BENCHMARK_CAPTURE_NOTES.md`

# V0.9.17.1 — AI Benchmark Capture

This release adds deterministic benchmark capture from AI-controlled cars in the same EA F1 session.

## What is captured

Race Engineer uses EA's all-car UDP packets and records only AI-controlled participants (`m_aiControlled == 1`). It does not use or require AI car setup data.

Per 5 m distance bin the reference stores the benchmark car's:

- elapsed lap time and lap distance
- speed, throttle, brake, steering, clutch, gear and RPM
- DRS and rev-light percentage
- lateral/longitudinal G
- world XYZ position, velocity and yaw/pitch/roll for racing-line analysis
- brake temperatures, tyre surface/inner temperatures, tyre pressures and surface type when present

AI MotionEx wheel-slip is intentionally not copied because EA's MotionEx packet is player-specific rather than an all-car array. Missing data is left missing instead of substituting player data.

## Benchmark selection

- Participants packet identifies AI cars.
- Each AI lap is sampled independently.
- Invalid laps are rejected.
- A lap must have enough measured distance samples to become a reference.
- The fastest valid AI lap observed in the session becomes the active external coaching reference.
- A new faster AI lap automatically replaces the previous AI reference.
- Session metadata records AI difficulty, track id/length, session type, weather and equal-car-performance setting.
- An optional minimum AI difficulty prevents low-difficulty sessions from becoming benchmark references.

## CLI

Capture and use the fastest valid AI lap live:

```powershell
.\.venv\Scripts\python.exe -m src.main `
  --overlay `
  --wheel-port COM5 `
  --ai-reference `
  --ai-reference-min-difficulty 100
```

Also save the current fastest AI reference:

```powershell
.\.venv\Scripts\python.exe -m src.main `
  --overlay `
  --wheel-port COM5 `
  --ai-reference `
  --ai-reference-output ".\references\ai_best.json" `
  --ai-reference-min-difficulty 100
```

`--ai-reference-output` implies `--ai-reference`.

## Safety / architecture

The feature is read-only with respect to game telemetry. It does not touch GamePad Pro firmware, wheel display logic, telemetry transport, control inputs, strategy logic or car setup handling.


---

## Archived source: `V0.9.17.2.1_RIVAL_SANITY_REFERENCE_SELECTOR_NOTES.md`

# V0.9.17.2.1 — Rival Sanity + Reference Selector

## Rival telemetry sanity
EA Time Trial ghost telemetry can contain isolated one-bin speed/gear discontinuities. The capture now cleans local extrema that disagree strongly with both neighbouring 5 m bins, applies an absolute >380 km/h guard, and suppresses one-bin gear glitches. Gear-change counts require persistence across two bins.

When rival Motion G values are unavailable/zero, longitudinal G is derived from cleaned speed over time and lateral G from speed × yaw-rate. Values outside physically useful sanity bounds are ignored.

## Control Center reference selection
A new REFERENCE LAP combo lists validated `references/*.json` files. Selection takes effect immediately. The refresh button rescans the directory. `Auto` returns control to live TT-rival / AI / own-session-best selection. A manual stored reference stays locked and cannot be overwritten by live rival capture until Auto is selected.


---

## Archived source: `V0.9.17.2.2_REFERENCE_SELECTOR_STARTUP_HOTFIX_NOTES.md`

# V0.9.17.2.2 — Reference Selector Startup Hotfix

Fixes a startup crash introduced in V0.9.17.2.1 where the Control Center connected the reference combo box to `_reference_changed`, but the reference-selector methods had accidentally been inserted into `CoachOverlayWindow` instead of `ControlCenterWindow`.

## Fix
- Moved `refresh_reference_options`, `_reference_changed`, and `set_reference_selection` into `ControlCenterWindow`.
- No telemetry, rival capture, strategy, radio, or GamePad Pro behavior changes.
- Reference selector remains available in the Control Center.

## Validation
- Python compile check passed.
- 394 tests passed, 383 subtests passed.


---

## Archived source: `V0.9.17.2.3_REPLAY_RECORDING_SELECTOR_NOTES.md`

# V0.9.17.2.3 — Replay Recording Selector

Adds a Control Center `REPLAY RECORDING` dropdown alongside the existing reference-lap selector.

- Scans `recordings/*.areplay` newest-first.
- Shows file name and size.
- Changing the selection loads the new replay immediately without restarting Race Engineer.
- Resets replay state/checkpoints and starts the selected recording from packet zero.
- Refresh button rescans the recordings folder.
- Existing `--replay` command remains the startup default and existing replay speed/seek controls remain unchanged.
- Selector is enabled in replay mode and disabled during a live UDP session to avoid disturbing the live telemetry thread.

## Filename-free startup

`--replay-browser` selects the newest `recordings/*.areplay` as the initial replay so the user can launch the same command every time and pick the desired recording from Control Center.


---

## Archived source: `V0.9.17.2.4_LIVE_REPLAY_MODE_SWITCH_NOTES.md`

# V0.9.17.2.4 — Live / Replay Mode Switch

- Replay status in Control Center is now clickable.
- Live -> Replay starts the selected `.areplay` recording.
- Replay -> Live stops replay immediately, clears replay-derived state, and returns to live F1 UDP without closing the app.
- The live UDP socket stays bound while replay is active; live datagrams are gated out until Live mode is selected again.
- Replay recording selector is available in both modes. In Live mode it queues a recording; in Replay mode changing the selection loads and plays it.
- Existing `--replay` and `--replay-browser` still start directly in Replay mode.
- Replay packets are never written into a live telemetry recording.


---

## Archived source: `V0.9.17.2.5_REFERENCE_AUTHORITY_TRACK_SYNC_NOTES.md`

# V0.9.17.2.5 — Reference Authority + Track Sync

This hotfix makes stored/manual reference laps authoritative and removes implicit rival/AI promotion into coaching.

## Reference priority

1. If a stored reference is manually selected in Control Center, it is the coaching reference.
2. If the selector is cleared / set to `Session best`, Race Engineer uses the best valid measured lap from the current live or replay session.
3. Time Trial rival and AI benchmark capture continue to record/save benchmark files, but do not silently replace the active coaching reference.

## Replay / live persistence

A manually selected reference is cached by the receiver and reapplied after:
- replay state reset,
- switching Live -> Replay,
- switching Replay -> Live,
- replay checkpoint restore/seek.

This fixes the case where the UI still showed a manual reference while a newly-created RaceStateEngine had fallen back to session-best internally.

## Same-track guard

Stored references with a `track_id` are checked against the active EA track ID. A mismatched reference is rejected on manual selection. If the source later changes to another track, the selected reference is temporarily suspended and current-session best is used; it is automatically restored when the matching track returns.

References without verifiable track metadata are rejected once an active track is known.

## Lap-start stitching

Live/replay/reference traces are only compared when both contain the start/finish-line beginning of the lap. Partial mid-lap traces produced by starting/switching a source are not stitched to a stored reference and are not promoted as session-best laps.

Delta alignment now compares the EA lap clocks directly (`current t - reference t`) instead of re-zeroing both traces at the first common distance bin. Both traces therefore share the actual lap-start 00:00 origin.

External references remain valid even when their stored lap number equals the current session lap number; external lap numbers are identifiers from another session and no longer suppress live coaching.

## Validation

- `410 passed`
- `383 subtests passed`


---

## Archived source: `V0.9.17.2.6_LAP_BOUNDARY_REFERENCE_DRIVER_INPUTS_NOTES.md`

# V0.9.17.2.6 — Lap-Boundary Reference + Driver Inputs Visibility

- Reference changes made mid-lap are queued and activate only at the next start/finish crossing.
- The currently active reference remains authoritative for the rest of the in-progress lap.
- Clearing a manual reference mid-lap is also queued; session-best becomes active at the next lap start.
- Stored-reference track compatibility is rechecked when the queued reference activates.
- The Driver Inputs overlay (throttle/brake/ERS) is now clamped into the visible desktop work area instead of being positioned below 768px-tall screens.
- Control Center overlay launcher is labelled DI with a clear throttle/brake/ERS tooltip.


---

## Archived source: `V0.9.17.2.7_REFERENCE_RELATIVE_LAP_HISTORY_FIX_NOTES.md`

# V0.9.17.2.7 — Reference-Relative Lap History Fix

This hotfix corrects Lap Time History semantics after changing the active reference.

## Behaviour

- All completed session laps are recalculated against the reference that is currently active.
- The fastest valid lap from the current session remains the session BEST lap.
- External reference metadata such as `reference_lap_number` can never mark a same-numbered local lap as BEST.
- The BEST row retains its numeric delta to the active reference, e.g. `BEST +9.881`.
- If Session Best is the active reference, its own delta is `BEST +0.000`.
- Reference changes selected mid-lap still wait until the next lap boundary before becoming active for live coaching.

## Validation

- Added regression tests covering external reference lap-number collisions and recomputation of historical deltas after reference changes.
- Full test suite: 416 passed, 383 subtests passed.


---

## Archived source: `V0.9.17.2.8_ACTIVE_PENDING_REFERENCE_INPUTS_NOTES.md`

# V0.9.17.2.8 — Active/Pending Reference + Reference Inputs

## Control Center
The reference selector now distinguishes the requested selection from the reference currently used by live coaching. A mid-lap change is shown as PENDING and becomes ACTIVE only at the next clean lap start.

## Reference Inputs overlay
A new RI launcher opens a separate reference-lap telemetry panel. It follows the active reference at the same lap distance as the current live/replay lap and displays throttle, brake, speed, gear, reference elapsed time, and ERS store where the stored reference actually contains ERS data.

T, B and ERS buttons independently show/hide the three graph groups. Time Trial rivals often do not expose ERS energy, so that trace remains unavailable rather than being synthesized.


---

## Archived source: `V0.9.17.2.9.10_CURRENT_LAP_TRACE_ISOLATION_NOTES.md`

# V0.9.17.2.9.10 — Current-Lap Trace Isolation

- Fixes DI throttle/brake traces from earlier laps being drawn over the current lap after lap-distance wraps back to zero.
- DI sampling remains continuous and reference-independent; only rendering is restricted to the newest monotonic lap-distance epoch.
- The same epoch isolation is applied to ERS distance rendering as a safety guard.
- Reference changes mid-lap do not clear or restart DI.
- At a real start/finish crossing, previous-lap samples remain buffered but are no longer rendered at the same lap-distance coordinates.


---

## Archived source: `V0.9.17.2.9.1_KEYED_LAUNCHER_ROUTING_HOTFIX_NOTES.md`

# V0.9.17.2.9.1 — Keyed Launcher Routing Hotfix

Control Center launchers now use one semantic-key dispatcher owned by `OverlaySuite`.

Expected routes:
- `RE` → Race / Qualifying Engineer
- `RI` → Reference Inputs
- `W` → Weather

Each button stores its own immutable `overlayKey`; clicks are dispatched by that key rather than callback list position.


---

## Archived source: `V0.9.17.2.9.2_LAUNCHER_STARTUP_ROUTING_FIX_NOTES.md`

# V0.9.17.2.9.2 — Launcher Startup + Routing Fix

- Removed an accidental `on_show_overlay` assignment from `CoachOverlayWindow` that referenced a name not present in that constructor and caused startup to crash.
- Control Center remains the only owner of `on_show_overlay`.
- Kept semantic-key routing for launcher buttons.
- Added runtime smoke coverage for actual Qt button clicks: `RE`, `RI`, and `W` must emit their own semantic keys.
- No telemetry, radio, wheel, reference, replay, or coaching logic changed.


---

## Archived source: `V0.9.17.2.9.3_CONTROL_CENTER_CLICK_ROUTING_FIX_NOTES.md`

# V0.9.17.2.9.3 — Control Center Click Routing Fix

## Root cause
V0.9.17.2.9.2 accepted `on_show_overlay` in `ControlCenterWindow.__init__`, and every overlay launcher called `_dispatch_overlay()`, but the constructor never assigned the callback to `self._on_show_overlay`.

Therefore every launcher click reached `_dispatch_overlay()` and raised `AttributeError: 'ControlCenterWindow' object has no attribute '_on_show_overlay'`. Qt can report callback exceptions without terminating the main window, which made the buttons appear to do nothing.

## Fix
- Store `self._on_show_overlay = on_show_overlay` in `ControlCenterWindow`.
- Keep semantic-key routing through `OverlaySuite.show_overlay_by_key()`.
- Keep legacy callback fallback for safety.
- Confirm no stray `_on_show_overlay` assignment exists in `CoachOverlayWindow`.
- Add source/AST regression tests covering the initialization and all launcher routes.


---

## Archived source: `V0.9.17.2.9.4_CONTROL_CENTER_HITBOX_DIRECT_ROUTING_FIX_NOTES.md`

# V0.9.17.2.9.4 — Control Center Hitbox + Direct Routing Fix

Root causes found:

1. V0.9.17.2.8 added the ACTIVE/PENDING reference row and a 17th launcher (RI) but the Control Center remained too short. The lower launcher rows could extend outside the real parent-window input area. Clicks in that region could therefore reach another always-on-top overlay underneath instead of the visible launcher.
2. V0.9.17.2.9 then added a second semantic dispatch layer, which introduced separate startup/callback regressions without solving the geometry issue.

Fixes:

- Control Center height increased to 610 px so all four launcher rows are inside the actual input window.
- Every launcher row gets a 30 px minimum hit row.
- Removed the semantic dispatcher from Control Center launch buttons.
- Each visible button is directly and permanently bound to its own callback using `functools.partial`.
- Added console diagnostics such as `[UI] Launcher RI -> Reference Inputs — throttle / brake / ERS`.
- Kept explicit button positions and object names.


---

## Archived source: `V0.9.17.2.9.5_INPUT_TRACE_PAUSE_RIVAL_ERS_FIX_NOTES.md`

# V0.9.17.2.9.5 — Input Trace Pause + Rival ERS Fix

- Driver Inputs now appends graph points only when lap time/distance actually progresses, so paused replay frames no longer create artificial straight-line tails.
- Replay rewind/lap change clears Driver Inputs traces cleanly.
- Reference Inputs clock is explicitly labelled as reference elapsed time and now shows the reference-vs-current elapsed-time difference at the same lap distance.
- Time Trial rival capture now reads all-car Car Status packets and stores `m_ersStoreEnergy` in rival reference samples when EA provides it.
- Existing rival reference files captured before this version do not contain ERS store data and must be recaptured to populate RI ERS.


---

## Archived source: `V0.9.17.2.9.6_DISTANCE_INPUT_AXES_NOTES.md`

# V0.9.17.2.9.6 — Distance-Aligned Input Graph Axes

- Added track-distance x-axis labels to Driver Inputs and Reference Inputs throttle/brake graphs.
- Added the same distance labels to DI/RI ERS graphs where data is present.
- Both DI and RI are fed the current lap distance, so the graph x-axes represent the same physical section of track.
- Trace x-position uses telemetry distance when available; it falls back to sample spacing if distance is unavailable.
- DI footer now includes current lap distance.
- RI footer now includes the same comparison distance alongside reference elapsed time and time delta.
- Existing pause-freeze and rival ERS capture behavior from V0.9.17.2.9.5 is preserved.


---

## Archived source: `V0.9.17.2.9.7_DI_CONTINUOUS_REFERENCE_SWITCH_NOTES.md`

# V0.9.17.2.9.7 — DI Continuous Across Reference/Lap Boundary

- Driver Inputs (DI) is independent of reference selection.
- A mid-lap reference change remains pending until the next start/finish crossing.
- When that crossing occurs, DI no longer clears/restarts just because the lap number advances normally.
- DI continues as a rolling trace across normal lap boundaries.
- DI still clears on actual replay seek/rewind, source reset, lap-number rollback, or non-sequential lap jump.
- RI remains reference-dependent and may reset when the active reference changes, as intended.


---

## Archived source: `V0.9.17.2.9.8_SHARED_DISTANCE_AXIS_REFERENCE_STATUS_HOTFIX_NOTES.md`

# V0.9.17.2.9.8 — Shared Distance Axis + Reference Status Hotfix

- DI and RI input/ERS graphs now use one shared physical distance window: 0..current distance for the first 500 m, then a trailing 500 m window.
- Increased retained graph history so DI no longer starts later merely because it samples more frequently than RI.
- Graph points are positioned by actual lap distance inside the shared window, not by each widget's own first/last retained sample.
- Added missing AMBER import used by ACTIVE/PENDING reference status, fixing the NameError when a new reference is pending.
- Existing TT-rival references captured before ERS support still have no rival ERS data. Re-capture the rival with a recent build to populate `ers_j` samples.


---

## Archived source: `V0.9.17.2.9.9_10MS_DI_MASTER_INPUT_SAMPLING_NOTES.md`

# V0.9.17.2.9.9 — 10 ms DI-master input sampling

- Added a dedicated precise 10 ms input-overlay timer.
- DI progression is the sole sampling gate for DI/RI comparison traces.
- RI throttle/brake is sampled at the exact same current-car distance points as DI.
- DI ERS and RI ERS use the same DI-driven cadence and shared distance cursor.
- Duplicate snapshots are not appended, so 100 Hz polling does not create flat fake samples when EA telemetry has not advanced.
- Replay pause/rebuild and overlay pause freeze both input panels.
- Removed DI/RI sampling from the normal ~60 Hz overlay refresh to prevent double sampling.
- A 10 ms poll minimizes UI pickup latency; actual new-point frequency remains limited by the source telemetry rate.


---

## Archived source: `V0.9.17.2.9_CONTROL_CENTER_LAUNCHER_AUDIT_NOTES.md`

# V0.9.17.2.9 — Control Center Launcher Audit

All Control Center overlay launchers were cross-checked and converted to an explicit row/column registry.

| Button | Overlay |
|---|---|
| C | AI Coach |
| RE | Race / Qualifying Engineer |
| R | Replay Controls |
| RT | Radio Transcript |
| SS | Session Summary |
| DI | Driver Inputs |
| RI | Reference Inputs |
| Δ | Delta |
| L | Live Laptime |
| TW | Tyre Wear |
| F | Fuel |
| W | Weather |
| S | Standings |
| H | Laptime History |
| TS | Tyre Sets |
| EB | ERS Battery |

This prevents future feature insertions from shifting launcher positions or creating visual/callback ambiguity.


---

## Archived source: `V0.9.17.2_TIME_TRIAL_RIVAL_BENCHMARK_NOTES.md`

# V0.9.17.2 — Time Trial Rival Benchmark

This release adds a preferred benchmark source for the Live Performance Coach: the rival explicitly selected by the driver in EA F1 Time Trial.

- Reads `m_timeTrialRivalCarIdx` from Lap Data and `m_rivalDataSet` from the Time Trial packet.
- Captures the selected rival's all-car telemetry at 5 m distance bins: speed, throttle, brake, steering, gear, RPM, DRS, motion/racing-line data, temperatures and pressures when supplied by the all-car packets.
- Uses the Time Trial rival dataset lap/sector times and validity as authoritative benchmark metadata.
- Does not require or decode the rival's car setup.
- Detects ghost-lap completion by lap change or track-distance wrap, because a repeating Time Trial ghost need not behave like a normal race participant.
- The selected Time Trial rival has priority over AI benchmark capture when both features are enabled.
- MotionEx-only/player-only data such as rival wheel-slip remains unavailable rather than being fabricated.

Run:

```powershell
.\.venv\Scripts\python.exe -m src.main `
  --overlay `
  --wheel-port COM5 `
  --ptt `
  --rival-reference `
  --rival-reference-output ".\references\tt_rival.json"
```

Expected capture message:

```text
[TT RIVAL] Reference captured: <driver> 80.250s | <samples> samples
```


---

## Archived source: `V0.9.18.0_FINAL_DETERMINISTIC_CORE_NOTES.md`

# V0.9.18.0 — Final Deterministic Core

V0.9.18.0 is the source-finalization release built on the user-verified and Git-pushed V0.9.17.2.9.10 baseline. Windows executable packaging is intentionally deferred to the next step.

## Final fixes and optimizations

### Finish-line / lap-clock sanity
- Reference-file loading removes clear time-regression rows caused by asynchronous Time Trial rival packets after the start/finish crossing.
- Rival capture performs the same monotonic-time cleanup before saving a benchmark.
- Legacy Time Trial rival files are repaired on load: impossible speed/gear ghost runs are cleaned, missing kinematic G is reconstructed where possible, and stale summary/section metrics are rebuilt from the sanitized trace.
- Live and completed-lap delta builders independently reject time-regressed rows as a defensive backstop.
- Prevents final sections from reporting a bogus delta roughly equal to an entire lap.

### 10 ms DI-master path
- Added a lightweight `InputSnapshot` path for the dedicated 10 ms input timer.
- The 10 ms sampler no longer rebuilds standings, strategy, weather, session history and other full-overlay data 100 times per second.
- DI remains the sole progression gate. RI is sampled only when DI actually progresses.
- RI continuous channels are linearly interpolated at the exact DI distance. Gear and other discrete states remain nearest-neighbour.

### ERS graph alignment
- ERS store, harvest and deployment buffers now append exactly one slot for every sampled DI distance.
- Missing packet-family values are stored as `None`, avoiding channel/distance index drift.
- Current-lap epoch isolation remains active.

### Reference authority
- Voice measured-reference commands use the same ACTIVE/PENDING lap-boundary activation rule as Control Center selections.
- Previous/manual measured references are rejected when no completed lap exists.
- Control Center ACTIVE status now identifies Session best, Measured lap and Previous lap modes accurately.

### LLM isolation
- LLM is disabled by default.
- `--llm` explicitly enables the optional local Ollama explanation/fallback path.
- Deterministic telemetry commands, critical calls and strategy decisions remain authoritative and do not depend on the LLM.
- `--no-llm` remains accepted as a compatibility switch.

### Preserved stable behavior
- Zero-drift replay scheduler and low-latency telemetry path.
- Race/qualifying/time-trial deterministic routing.
- Critical > race-control > pit decision > performance > routine priority behavior.
- Stale-message rejection and radio preemption.
- Deterministic pit-strategy confidence calculation.
- DI/RI shared distance axes, 10 ms DI-master sampling and current-lap trace isolation.
- GamePad Pro wheel telemetry bridge and independent HID controls.

## Validation

The release includes dedicated regression coverage for finish-line time-wrap filtering, exact-distance RI interpolation, lightweight input snapshots, reference-boundary voice switching, ERS distance-buffer alignment, LLM opt-in behavior, and legacy Time Trial rival sanitation.

Final verification on the release tree:

- `python -m compileall -q src` — passed.
- `python -m pytest -q` — **477 passed, 383 subtests passed**.
- `python -m src.main --help` — startup/CLI smoke passed and exposes `--llm` as opt-in.
- The real previously captured `tt_rival.json` sanitizes from 1054 raw samples / 486 km/h / 269 raw gear changes to 1053 valid samples / 322 km/h / 57 gear changes, with the post-line 0.019 s row removed and derived G/sections rebuilt.


---

## Archived source: `V0.9.19.0_F1_DASH_LAN_WEB_DASHBOARD_NOTES.md`

# V0.9.19.0 — F1 Dash + LAN Web Dashboard

Adds a dedicated F1-style dashboard without changing the deterministic Race Engineer decision core.

## Native dashboard

- New `FD` launcher in Control Center.
- Opens an 800x480 always-on-top F1 Dash window.
- Displays live speed, gear, rev lights, RPM, position, lap, lap time, reference delta, DRS, ERS/overtake status, ERS state, fuel-lap estimate, throttle, brake and tyre/penalty context.
- Uses the exact same immutable overlay snapshot as the other Race Engineer windows; it does not decode UDP independently.

## Browser / second-device dashboard

With `--overlay`, Race Engineer starts a dependency-free LAN dashboard server by default.

Default URL:

```text
http://<PC-LAN-IP>:8765/
```

Open that address from a phone, tablet, laptop or other browser device on the same LAN/Wi-Fi. Race Engineer prints the exact local and LAN URLs at startup.

The browser dashboard receives state through Server-Sent Events (SSE). It only streams the latest already-built dashboard snapshot; it never participates in strategy, radio, controls or hardware input.

Options:

```text
--dash-port 8765
--dash-host 0.0.0.0
--no-web-dash
```

If Windows Firewall prompts on first use, allow Python/Race Engineer on the Private network so another device can reach the dashboard.

## Reliability / latency

- Browser requests do not rebuild strategy/overlay state.
- Qt remains the single producer of dashboard state at the normal Race Engineer overlay refresh cadence.
- HTTP/SSE threads only read the cached payload.
- The 10 ms DI/RI sampler, deterministic core, replay timing, wheel bridge and GamePad Pro control paths are unchanged.


---

## Archived source: `V0.9.19.1_UNIFIED_F1_DASH_SETUP_STATUS_STRIP_NOTES.md`

# V0.9.19.1 — Unified F1 Dash + Setup Status Strip

Built directly on V0.9.19.0 without changing the deterministic Race Engineer core.

## Native FD dashboard

- Keeps the native 800×480 F1 Dash layout.
- Adds `DIFF · BBAL · ENG BRK · WING · WEAR · PEN` below the four live bars.
- DIFF is EA on-throttle/off-throttle differential.
- BBAL and ENG BRK are direct EA car-setup packet values.
- WING is maximum current front-wing damage; WEAR is maximum current tyre wear; PEN is current penalty seconds.
- Missing setup-packet values display `--`; nothing is guessed.
- Footer is REF / RPM / TYRE / SECTOR.

## LAN / browser dashboard

- Mirrors the native compact hierarchy and the same six-value strip.
- Continues using the immutable overlay snapshot through SSE.
- Display only: no UDP decoding or decision/control participation.

## Core logic

No changes to deterministic strategy, engineer decisions, radio, replay, recorder, driver/reference analysis, wheel telemetry, or control routing.


---

## Archived source: `V0.9.19.2_UNIFIED_F1_DASH_LAYOUT_SYNC_FUEL_MODE_NOTES.md`

# V0.9.19.2 — Unified F1 Dash Layout Sync + Fuel Mode

- Native FD dashboard now matches the LAN dashboard more closely.
- Removed the extra native header/margins so the full 800x480 window is used by the dash canvas.
- Bottom status strip is now vertically stacked (label on top, larger value below) in both native and LAN layouts.
- Replaced WING and WEAR boxes with a single FUEL MODE box.
- Fixed `NameError: QPen is not defined` in the native FD paint path.
- This also prevents the cascading Qt paint warnings caused by the paint-event exception.


---

## Archived source: `V0.9.19.3_MULTI_PAGE_F1_DASH_NOTES.md`

# V0.9.19.3 — Multi-Page F1 Dash

- Added native overlay close button without changing the 800x480 dashboard canvas.
- Added in-window page switching: DASH / DAMAGE / TYRES / PIT.
- DAMAGE page: front-left/right wing, rear wing, floor, diffuser, sidepod, gearbox, engine, DRS/ERS fault status.
- TYRES page: brake temperature, inner/surface tyre temperature, wear, pressure and tyre damage for FL/FR/RL/RR.
- PIT page: pit status, pit stops, pit speed limit, lane/stop time, next tyre/set, penalties and serve-penalty status.
- Renamed the DASH DRS pill to S MODE and wired it to the F1 2026 active-aero (straight/corner mode) telemetry.
- LAN dashboard gets matching DASH / DAMAGE / TYRES / PIT pages.
- Retains the QPen import hotfix that prevents the QBackingStore active-painter cascade.


---

## Archived source: `V0.9.19.4_VISUAL_TYRE_BRAKE_DAMAGE_STATUS_NOTES.md`

# V0.9.19.4 — Visual Tyre / Brake / Damage Status

- TYRES page redesigned as a top-down car display.
- Each tyre changes color independently from tyre surface temperature.
- Each brake-disc marker changes color independently from brake temperature.
- Tyre border and wear readout change color from wear/damage severity.
- DAMAGE page redesigned as a top-down car with independently colored component zones.
- LAN and native FD pages use the same status concepts and thresholds.
- Thresholds reuse existing Race Engineer behavior: tyre cold below 70 C, tyre hot at 115 C+, brake warm at 1000 C+, brake hot at 1100 C+, and existing damage/wear bands.


---

## Archived source: `V0.9.19.5_F1_DASH_EVENT_PAGES_PAUSE_GRAPH_NOTES.md`

# V0.9.19.5 — F1 Dash Event Pages, Pause Freeze & 100 m Graph Grid

- Fixed TYRES left-side label/value overlap by using separate fixed label/value columns.
- Reworked DAMAGE into a more F1-like top-down silhouette with exposed wheels, split front wing, nose, sidepods/body, cockpit and rear wing.
- Damage percentages are rendered directly on/next to the corresponding component instead of in detached side lists.
- New damage increase automatically selects DAMAGE for 3 seconds, then returns to the user's prior page (or PIT if currently active).
- Active pit state / pit-lane timer automatically selects PIT; leaving pit restores the user's prior page.
- Game pause and replay/overlay pause freeze the F1 dash on the last fully rendered frame. Dashboard state publishing is also frozen while paused.
- LAN dashboard uses the same event-driven DAMAGE/PIT auto switching without wall-clock timers, so auto-page timing also freezes while telemetry publishing is paused.
- Driver Input / Reference Input and ERS distance axes now show track-distance labels at every 100 m within the current distance window.
- Existing deterministic race-engineer logic is unchanged; these are presentation/event-routing changes only.


---

## Archived source: `V0.9.19.6.1_OVERLAY_MINIMIZE_ALIGNMENT_HOTFIX_NOTES.md`

# V0.9.19.6.1 — Overlay Minimize Alignment Hotfix

- Reworked minimize controls so they are owned by each overlay's header layout instead of floating with absolute coordinates.
- Prevents overlap with title/context text, replay controls, graph visibility toggles, pause/click-through controls, and close buttons.
- Aligns minimize immediately before the close/hide button for Race Engineer, Control Center, Driver Inputs, Reference Inputs, Replay Controls, data overlays, Delta, and Live Laptime.
- F1 Dash keeps its custom absolute header and now uses an explicitly aligned minimize/close pair.
- No telemetry, strategy, replay, recording, or deterministic logic changed.
- Regression: 501 tests passed + 383 subtests passed.


---

## Archived source: `V0.9.19.6.2_F1_DASH_MAP_VISUAL_HOTFIX_NOTES.md`

# V0.9.19.6.2 — F1 Dash Map + Visual Hotfix

## Fixed
1. **F1 Dash minimize / close alignment**
   - Reworked the F1 Dash top-right controls into a shared layout-owned button bar.
   - This keeps the minimize and close buttons perfectly aligned and avoids the drift seen in the native F1 Dash window.

2. **MAP page startup / skip behaviour**
   - Added built-in full-circuit map outlines for supported tracks so the full map can appear immediately at session start instead of waiting for live tracing.
   - The position marker now uses **lap distance / track length** on those built-in maps.
   - Added replay/seek protection so large position jumps do not draw broken bridge-lines across the track.
   - Web/LAN F1 Dash map logic was updated too, so both native and remote dashboards behave consistently.

3. **Damage / tyres / engine visual refinement**
   - Reworked the native F1 Dash car wireframe to be closer to the supplied F1-style reference.
   - Refined the damage page with a cleaner single-seater silhouette, better placement cards and leader lines.
   - Refined the tyres page car silhouette to match the reference style more closely.
   - Refined the power-unit page central engine icon and kept the component boxes around it.

## Validation
- `PYTHONPATH=. pytest -q`
- Result: **501 passed, 383 subtests passed**


---

## Archived source: `V0.9.19.6_F1_DASH_MAP_ENGINE_RECORDING_MINIMIZE_NOTES.md`

# V0.9.19.6 — F1 Dash Map + Engine + Recording + Minimize

- Fixed intermittent ghost/diagonal Driver Inputs and ERS traces by removing prefilled placeholder samples and breaking plotted paths across missing/out-of-window distance samples.
- Reworked DAMAGE into a more realistic top-down 2026-style single-seater schematic with damage values placed beside the corresponding components.
- Reworked TYRES/BRAKES into an in-game-style vehicle-health view with live tyre damage/wear rings, tyre temperatures, brake temperatures and pressures.
- Added ENGINE page for ICE, CE, MGU-H, MGU-K, TC, ES, gearbox, overall engine damage, engine temperature and blown/seized state.
- Added MAP page. It builds the actual circuit shape from EA world-position telemetry and moves the player marker live on the reconstructed track.
- Live recording can now be toggled from Control Center even when replay capability is present. Recording is explicitly blocked only while Replay is the active telemetry source.
- Added a shared minimize button to every OverlayPanel-derived overlay.
- Existing automatic 3-second DAMAGE page, automatic PIT page, pause-freeze behavior, and 100 m graph marks remain intact.
- Full regression: 501 tests + 383 subtests passed.


---

## Archived source: `V0.9.19.7.1_SMOOTH_TRACK_MAP_START_MARKER_NOTES.md`

# V0.9.19.7.1 — Smooth Track Map + Start/Finish Marker

- Replaced angular display polylines with dense closed Catmull-Rom curves for all preloaded F1 26 tracks.
- Marker interpolation now follows the same smoothed curve, so YOU / REF / AHEAD / BEHIND remain on the rendered circuit.
- Added a permanent START marker to both the native FD map and LAN/browser map.
- Start marker is anchored to point 0 of each track map, which is also the lap-distance 0 anchor.
- No telemetry, strategy, decision, recording, replay or race-engineer logic changed.


---

## Archived source: `V0.9.19.7_FULL_TRACK_MAP_MULTI_CAR_F1_VISUALS_NOTES.md`

# V0.9.19.7 — Full Track Map + Multi-Car Markers + F1 Visuals

## Fixed / changed

1. **Native F1 Dash close/minimize alignment**
   - Minimize and close now live in one shared top-right header button bar.
   - Spacing and vertical alignment are controlled by the same layout.

2. **Instant full track map**
   - Added a preloaded track-map library covering every circuit currently exposed by the F1 26 track enum, including reverse layouts.
   - The circuit outline is available immediately when the MAP page opens.
   - Live/replay world-position tracing is retained only as a fallback for unknown tracks.
   - Large replay seek jumps are not connected into the fallback trace.

3. **Multi-car map markers**
   - Yellow: player.
   - Cyan: active reference lap position, interpolated from reference elapsed time.
   - Red / orange: up to two race positions ahead.
   - Green / purple: up to two race positions behind.
   - Nearby-car markers use each car's telemetry lap distance, not guessed time gaps.

4. **Damage / tyre / engine visuals**
   - Reworked the native car wireframe toward the supplied F1-style reference proportions.
   - Added clearer front/rear wings, narrow nose, cockpit/halo area, exposed wheel pods and sculpted body/floor.
   - Damage values use cleaner side cards with leader lines to the affected components.
   - Refined tyre-page central F1 silhouette.
   - Refined power-unit central engine/hybrid visual.
   - Updated LAN/web CSS to follow the same stronger F1 visual language.

5. **LAN parity**
   - LAN dashboard uses the same preloaded track-map library and map-marker model.
   - No `BUILDING TRACK MAP` wait state on supported tracks.

## Validation

`PYTHONPATH=. pytest -q`

Result: **506 passed, 383 subtests passed, 0 failures**.


---

## Archived source: `V0.9.19.8.1_MAPS_FOLDER_HORIZONTAL_DISPLAY_NOTES.md`

# V0.9.19.8.1 — Maps Folder + Horizontal Track Display

- Learned map cache moved to `maps/track_maps_cache.json`.
- Existing root-level `track_maps_cache.json` is migrated automatically, preserving learned circuits such as Melbourne.
- Portrait/tall learned circuits are rotated 90 degrees for display on the wide 800x480 F1 Dash.
- Rotation is display-only; the learned world-position geometry saved to disk is unchanged.
- Native FD and LAN/browser map views use the same orientation rule.
- Map drawing area increased and legend/footer spacing adjusted to reduce overlap.
- Full regression: 509 tests passed + 383 subtests passed.


---

## Archived source: `V0.9.19.8.2_DASH_FOOTER_LAYOUT_HOTFIX_NOTES.md`

# V0.9.19.8.2 — Dash Footer Layout Hotfix

- Removed reference-lap text from the main F1 Dash footer.
- Added a dedicated readable metadata line for RPM, tyre compound and sector.
- Kept the web dashboard URL alone on the bottom-most line.
- Reduced status-strip height slightly to prevent bottom-line clipping.
- Applied the same hierarchy to native FD and LAN/browser dashboards.
- No map, telemetry, strategy or decision logic changes.


---

## Archived source: `V0.9.19.8.3_DASH_META_PLACEMENT_HOTFIX_NOTES.md`

# V0.9.19.8.3 — Dash Meta Placement Hotfix

- Moved **SECTOR** directly below **LAP** on the left side of the main F1 dash.
- Moved **RPM** directly below the large **GEAR** in the centre.
- Removed **TYRE** from the main F1 dash metadata.
- Removed the intermediate metadata/footer row entirely.
- Kept **WEB** as the only bottom-most line.
- Native FD and LAN/browser dashboards use the same information placement.
- No telemetry, map, strategy or decision logic changed.


---

## Archived source: `V0.9.19.8.4_SECTOR_SIZE_RPM_REMOVAL_HOTFIX_NOTES.md`

# V0.9.19.8.4 — Sector Size + RPM Removal Hotfix

- Sector now uses the same visual treatment as LAP:
  - matching label size
  - matching large value size
  - placed directly below LAP
- RPM removed completely from the main F1 Dash.
- WEB link remains alone at the bottom.
- Applied to native FD and LAN/browser dashboards.
- No map, telemetry, strategy, or decision logic changes.

Validation: 509 tests passed + 383 subtests passed.


---

## Archived source: `V0.9.19.8.5.1_ENGINE_PAGE_RENDER_HOTFIX_NOTES.md`

# V0.9.19.8.5.1 — Engine Page Render Hotfix

- Fixed missing `QPointF` import in the native F1 Dash engine page.
- The missing import caused the paint event to stop after the first ES label, leaving the rest of the page blank.
- No telemetry, map, strategy, or decision logic changed.


---

## Archived source: `V0.9.19.8.5.2_ENGINE_REFERENCE_ALIGNMENT_HOTFIX_NOTES.md`

# V0.9.19.8.5.2 ENGINE REFERENCE ALIGNMENT HOTFIX

## What was fixed
- Reworked the **ENGINE / POWER UNIT** page to better match the supplied F1-style reference.
- Corrected the **leader / dotted line targets** so they now point to the intended components:
  - ES -> top module
  - CE -> side module
  - ICE -> main center body
  - MGU-K -> lower horizontal module
  - TC -> lower square module
  - GEARBOX -> right-side horizontal gearbox section
- Redesigned the power-unit silhouette to be more symmetric and visually closer to the reference image.
- Applied the same correction to both:
  - desktop overlay / native dash rendering
  - LAN web dashboard engine page

## Files changed
- `src/overlay/window.py`
- `src/dashboard_server.py`
- `src/main.py`

## Validation
- `509 passed, 383 subtests passed`


---

## Archived source: `V0.9.19.8.5.3_ENGINE_LEADER_POLISH_HOTFIX_NOTES.md`

# V0.9.19.8.5.3 ENGINE LEADER POLISH HOTFIX

## What was fixed
- Removed the purple fill artifact on the ENGINE page leader lines.
- Changed native overlay engine leaders from filled painter paths to explicit dotted line segments with no brush fill.
- Adjusted the leader targets for:
  - MGU-K
  - TC
  - GEARBOX
- Tightened the web dashboard SVG leader targets for TC and GEARBOX.
- Forced `fill:none` on SVG leader lines to prevent any accidental fill artifacts.

## Files changed
- `src/overlay/window.py`
- `src/dashboard_server.py`
- `src/main.py`


---

## Archived source: `V0.9.19.8.5_F1_STYLE_POWER_UNIT_VISUAL_NOTES.md`

# V0.9.19.8.5 — F1-Style Power Unit Visual

- Rebuilt ENGINE page around the supplied F1-style reference.
- Left-side component list: ES, CE, ICE, MGU-K, TC, GEARBOX.
- Dotted leader lines connect each value to the power-unit graphic.
- Large right-side power-unit diagram uses independent component coloring.
- Wear colors progress green -> yellow-green -> amber -> orange -> red.
- Engine fault state still overrides status in red.
- Native FD and LAN/browser ENGINE pages use the same layout concept.
- Main DASH and MAP logic are unchanged.

Validation: 509 tests passed + 383 subtests passed.


---

## Archived source: `V0.9.19.8.6.10_TYRE_PRESSURE_DISPLAY_HOTFIX_NOTES.md`

# V0.9.19.8.6.10 Tyre pressure display hotfix

Exact requested change only:
- Restored the main tyre pressure number (24.xx / 21.xx) to the large size.
- Kept the PSI unit small and separate so it does not overlap.
- OUTER, INNER, WEAR, TYRE DMG and BLISTER values remain one uniform size.
- Applied to native FD and LAN/browser.


---

## Archived source: `V0.9.19.8.6.11_PSI_NORMAL_ROW_HOTFIX_NOTES.md`

# V0.9.19.8.6.11 — PSI Normal Row Hotfix

- Removed the standalone large tyre-pressure display from TYRES & BRAKES.
- PSI is now a normal tyre-data row, exactly like OUTER / INNER / WEAR / TYRE DMG / BLISTER.
- PSI label uses the same label style as the other tyre rows.
- PSI value uses the same value font size, weight and alignment as the other tyre rows.
- Applied identically to native FD and LAN/browser.


---

## Archived source: `V0.9.19.8.6.12_NATIVE_TYRE_SCALE_UP_HOTFIX_NOTES.md`

# V0.9.19.8.6.12 — Native TYRES scale-up hotfix

## Scope
Native FD TYRES & BRAKES page only. LAN/browser layout is unchanged.

## Changes
- Increased FL/FR/RL/RR corner label size.
- Increased PSI/OUTER/INNER/WEAR/TYRE DMG/BLISTER label + value sizes.
- Increased row height and spacing for readability.
- Increased OUT/IN/BRK gauge width/height and gauge labels.
- Increased BRAKE and BRAKE DMG labels.
- Increased brake temperature and brake damage values.
- Increased SET and compound text slightly.
- Kept the current layout/order and symmetry unchanged.

## Validation
- Full regression: 509 passed, 383 subtests passed.


---

## Archived source: `V0.9.19.8.6.15_TYRE_CORNER_LABEL_BRAKE_CLIP_HOTFIX_NOTES.md`

# V0.9.19.8.6.15 – Tyre corner label + brake clipping hotfix

Native FD TYRES & BRAKES page only.

- Moved FL / FR / RL / RR into a dedicated corner-header line above the tyre data rows.
- Increased the vertical gap before the PSI row so corner IDs do not crowd the first data row.
- Widened the brake-information box so BRAKE temperature and BRAKE DMG are not clipped.
- Repositioned the right-side brake text box to preserve symmetry and avoid overlap with gauges.
- LAN/browser page unchanged.

Validation: targeted dash tests passed (10/10).


---

## Archived source: `V0.9.19.8.6.16_WEB_ADDRESS_SIZE_HOTFIX_NOTES.md`

# V0.9.19.8.6.16 – Web address size hotfix

- Increased only the native F1 DASH bottom WEB address font size.
- Kept the WEB address centered at the bottom.
- No tyre, map, strategy, telemetry, LAN, or other layout changes.


---

## Archived source: `V0.9.19.8.6.17_NATIVE_PAGE_SPACE_MAP_MARKER_HOTFIX_NOTES.md`

# V0.9.19.8.6.17 – Native page space + map marker hotfix

## Native DAMAGE page
- Reworked the CAR / AERO section to use the available area instead of one flat row.
- Aero/body cards are arranged spatially for faster recognition:
  - FL / FR wing at the front
  - sidepod / floor in the middle
  - diffuser / rear wing toward the rear
- Enlarged the POWER UNIT / HYBRID section and spread it across a 4 x 2 grid.

## Native TYRES page
- Header/tab overlap fixed by moving the page-tab row farther right.
- No tyre data/gauge logic changed.

## Native PIT page
- Enlarged the pit status and 8 service/status cards to use the previously empty lower area.
- Increased card labels and values for better readability.

## Native MAP page
- Track geometry/rendering unchanged.
- Increased moving marker sizes for YOU / REF / nearby cars.
- Increased bottom legend dots and labels for YOU / REF / AHEAD / BEHIND.

## Validation
- Python compile check passed.
- Targeted UI/map regression tests: 22 passed.


---

## Archived source: `V0.9.19.8.6.18_MAIN_DASH_GEAR_SETUP_STRIP_HOTFIX_NOTES.md`

# V0.9.19.8.6.18 — Main Dash Gear / Setup Strip Hotfix

## What changed
1. Reduced the native DASH page gear size slightly so it no longer dominates the center.
2. Used the freed-up vertical space to enlarge the lower setup/status strip (`DIFF`, `BBAL`, `ENG BRK`, `FUEL MODE`, `PEN`) for quicker readability.
3. Gave each setup/status cell its own semi-transparent tinted background while keeping the overall dark F1-style look.

## Scope
- Native 800x480 F1 dash only.
- No telemetry / decision logic changes.
- No LAN dashboard changes.

## Validation
- `py_compile` passed for `src/overlay/window.py`.


---

## Archived source: `V0.9.19.8.6.19_MAIN_DASH_OVERLAP_HOTFIX_NOTES.md`

# V0.9.19.8.6.19 — Main Dash Overlap Hotfix

## Fixed
- Moved the colored setup/status strip (`DIFF`, `BBAL`, `ENG BRK`, `FUEL MODE`, `PEN`) slightly lower.
- Reduced its height slightly to preserve the enlarged text while keeping the WEB footer clear.
- Added a visible gap between the THROTTLE/BRAKE/ERS/FUEL progress bars and the colored setup/status strip.

## Scope
- Native 800x480 F1 dash only.
- No telemetry logic changes.
- No LAN dashboard changes.

## Validation
- `py_compile` passed.
- `7` targeted dash tests passed.


---

## Archived source: `V0.9.19.8.6.1_DAMAGE_ALIGNMENT_TYRE_DATA_UI_HOTFIX_NOTES.md`

# V0.9.19.8.6.1 — Damage Alignment + Tyre Data UI Hotfix

## DAMAGE page
- Shortened the page title to `DAMAGE` so it no longer overlaps the navigation buttons.
- Reworked the page into a full-width stacked layout.
- CAR / AERO damage uses a single six-card row.
- DRS / ERS / engine state / engine temperature use a separate full-width status row.
- POWER UNIT / HYBRID wear uses full-width larger cards below.

## TYRES & BRAKES page
- Increased use of the full 800×480 area.
- Increased PSI, temperature, brake, wear and damage font sizes.
- Retained OUTER, INNER, BRAKE, WEAR, TYRE DMG, BRAKE DMG and BLISTER data for all four wheels.
- Added last-valid telemetry retention for:
  - tyre surface / outer temperature
  - tyre inner temperature
  - brake temperature
  - tyre pressure
- This avoids temporary `--` values when a snapshot/update does not carry those live channels.
- Same layout/data-retention behavior applied to LAN/browser dashboard.

## Validation
- 509 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.19.8.6.20_MAIN_DASH_BAR_SPACING_HOTFIX_NOTES.md`

# V0.9.19.8.6.20 — Main Dash Bar Spacing Hotfix

- Moved THROTTLE / BRAKE / ERS / FUEL progress bars upward.
- Restored the larger DIFF / BBAL / ENG BRK / FUEL MODE / PEN setup strip size from V0.9.19.8.6.18.
- Kept setup strip colors, fonts, and sizing unchanged.
- Native dash only; no LAN or telemetry logic changes.


---

## Archived source: `V0.9.19.8.6.21_MAIN_DASH_SETUP_STRIP_SCALE_UP_HOTFIX_NOTES.md`

# V0.9.19.8.6.21 Main Dash Setup Strip Scale-Up Hotfix

## What changed
- Increased the size of the bottom setup strip cards on the native DASH page.
- Used the spare space around the setup cards so DIFF, BBAL, ENG BRK, FUEL MODE and PEN are easier to read.
- Slightly widened the cards and reduced inter-card gaps.
- Increased the label and value font sizes inside the setup strip while preserving the moved-up THROTTLE / BRAKE / ERS / FUEL bars.

## Scope
- Native F1 DASH page layout only.
- No telemetry, LAN dashboard, strategy, or decision-making logic changes.


---

## Archived source: `V0.9.19.8.6.22_LAN_NATIVE_PARITY_REBUILD_NOTES.md`

# V0.9.19.8.6.22 — LAN Native-Parity Rebuild

## Native overlay frozen
- `src/overlay/window.py` is byte-for-byte unchanged from V0.9.19.8.6.21.
- SHA-256: `041155489af01e1ffc0a69ccf9be94b5c088bfc9a2ef5d1c5a4b53f452299534`.

## LAN UI rebuilt
The LAN/browser dashboard now renders on a fixed virtual 800×480 canvas and scales the complete canvas to the browser viewport. This prevents the LAN UI from drifting independently at different browser sizes and keeps native proportions.

### DASH
- Native-style 15-light rev strip.
- Native navigation placement.
- Frozen native gear/speed/status layout proportions.
- THROTTLE / BRAKE / ERS / FUEL bars positioned like native.
- DIFF / BBAL / ENG BRK / FUEL MODE / PEN setup strip uses the same enlarged card proportions and translucent per-card colors as native.
- Native-style WEB footer.

### DAMAGE
- Rebuilt to the frozen native spatial layout.
- Front wing boxes at the front, sidepod/floor through the middle, diffuser/rear wing toward the rear.
- DRS, ERS, engine state, and engine temperature occupy the side status positions.
- POWER UNIT / HYBRID wear uses the large 4×2 native-style lower grid.

### TYRES
- Rebuilt around the native four-corner geometry.
- Same corner labels, PSI/OUTER/INNER/WEAR/TYRE DMG/BLISTER rows, OUT/IN/BRK gauge grouping, brake info placement, centered SET pill, and mirrored left/right symmetry.

### MAP
- Uses the same visual area/proportions as native.
- Added the native-style YOU / REF / AHEAD / BEHIND legend.
- Increased live marker radii/font to native-equivalent display size.
- Track/map data logic is unchanged.

### PIT
- Rebuilt to the native 4×2 large-card service layout with larger status heading.

## Logic scope
- LAN presentation only (`src/dashboard_server.py`).
- No telemetry, strategy, radio, race-engineer, recording, map-cache, or native-overlay logic changes.

## Validation
- Relevant F1 dash tests: 29 passed.
- Full regression: 509 passed + 383 subtests passed.


---

## Archived source: `V0.9.19.8.6.23_LAN_NATIVE_PARITY_VERIFICATION_NOTES.md`

# V0.9.19.8.6.23 — LAN Native Parity Verification Build

- Corrected the startup version banner so CMD now clearly identifies the LAN parity build.
- LAN UI remains the rebuilt 800x480 frozen-native parity layout from V0.9.19.8.6.22.
- Native overlay file `src/overlay/window.py` is byte-for-byte unchanged from the frozen build.
- Browser response already uses no-cache/no-store headers.

Expected startup banner:
`V0.9.19.8.6.23 LAN NATIVE PARITY VERIFICATION BUILD`

Validation: 18 targeted dash/map tests passed.


---

## Archived source: `V0.9.19.8.6.24_LAN_TYRE_RIGHT_GAUGE_ALIGNMENT_HOTFIX_NOTES.md`

# V0.9.19.8.6.24 — LAN Tyre Right Gauge Alignment Hotfix

## Fixed
- Right-side LAN tyre gauges (FR/RR) no longer staircase diagonally.
- BRK / IN / OUT gauges are explicitly locked to the same grid row.
- Gauge labels are explicitly locked to the row beneath the gauges.
- Right-side order remains BRK | IN | OUT toward the outside, matching the frozen native layout.

## Scope
- LAN dashboard only (`src/dashboard_server.py`).
- Native overlay remains byte-for-byte unchanged.

## Validation
- Python compile passed.
- 16 targeted dashboard tests passed.


---

## Archived source: `V0.9.19.8.6.2_REFERENCE_TYRE_BRAKE_LAYOUT_NOTES.md`

# V0.9.19.8.6.2 — Reference Tyre / Brake Layout

- Removed the generic vertical health bars from TYRES & BRAKES.
- Rebuilt the page around the supplied four-corner reference layout.
- Large PSI values stay on the outer edge of each wheel quadrant.
- Tyre data stays grouped with the tyre: OUTER, INNER, WEAR, TYRE DMG, BLISTER.
- Brake data is separated on the inner side: BRAKE temperature and BRAKE DMG.
- Added a proper two-block tyre graphic near the centre of each wheel quadrant; its colour follows tyre condition.
- Central SET pill plus compound and tyre age retained.
- Native FD and LAN/browser page both updated.


---

## Archived source: `V0.9.19.8.6.3_TYRE_BRAKE_OVERLAP_HOTFIX_NOTES.md`

# V0.9.19.8.6.3 — Tyre / Brake Overlap Hotfix

## Fixed
- Added a real center gap between the four tyre quadrants.
- Moved the SET / compound / age block into its own reserved band.
- Moved brake temperature and brake damage into a dedicated inside lane for each wheel.
- Repositioned tyre icons so they no longer collide with brake values.
- Shortened/segmented center dividers so they do not run through the SET block.
- Applied the same layout logic to native FD and LAN/browser pages.

## Validation
- 509 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.19.8.6.4_TYRE_BRAKE_THREE_GAUGE_HOTFIX_NOTES.md`

# V0.9.19.8.6.4 — Tyre/Brake Three-Gauge Hotfix

- Fixed PSI unit overlap by putting `PSI` on its own line beneath the large pressure value.
- Removed tyre AGE from the TYRES page.
- The two tyre bars now independently show OUTER and INNER tyre temperatures.
- Added a third dedicated vertical BRAKE temperature progress gauge.
- Brake gauge fill is scaled from 0–1200 C and uses the existing brake-temperature colour thresholds.
- Brake temperature and brake damage text remain separate from tyre data.
- Native FD and LAN/browser layouts updated together.


---

## Archived source: `V0.9.19.8.6.5_UNIFIED_TYRE_BRAKE_LAYOUT_HOTFIX_NOTES.md`

# V0.9.19.8.6.5 — Unified Tyre / Brake Layout Hotfix

- Rebuilt native FD and LAN tyre pages from the same four-corner layout specification.
- Removed remaining AGE text from the tyre page.
- Reserved a wider centre gap for SET / compound.
- Pressure, PSI, tyre metrics, OUT/IN/BRK gauges and brake values now have non-overlapping dedicated regions.
- Added explicit OUT / IN / BRK labels under the three gauges on LAN.
- Native FD uses the same outside/inside data grouping and proportions.
- No telemetry, map, strategy or decision logic changes.
- Validation: 509 tests passed + 383 subtests passed.


---

## Archived source: `V0.9.19.8.6.6_TYRE_PSI_SYMMETRY_NATIVE_LAN_MATCH_HOTFIX_NOTES.md`

# V0.9.19.8.6.6 – Tyre PSI / symmetry / native-LAN layout match hotfix

## What was fixed
- Reduced and repositioned the `PSI` label so it no longer overlaps the main tyre pressure value.
- Increased the readability of the tyre metrics block and kept the tyre-related rows visually consistent.
- Reworked the four-corner tyre/brake layout so the LAN dashboard and native FD now follow the same structure.
- Enforced mirrored gauge symmetry:
  - Left-side cards: `OUT -> IN -> BRK` from outer edge toward the center.
  - Right-side cards: `BRK <- IN <- OUT` toward the outer edge, so the visual meaning stays symmetric.
- Kept the brake information on the inside side of each corner and the tyre information on the outside side.
- Removed remaining pressure/PSI crowding by splitting the pressure value and PSI label into separate placements.

## Files updated
- `src/dashboard_server.py`
- `src/overlay/window.py`

## Validation
- `python -m py_compile src/dashboard_server.py src/overlay/window.py`
- `PYTHONPATH=. pytest -q tests/test_v09193_multi_page_f1_dash.py tests/test_v09194_visual_status_dash.py tests/test_v09190_f1_dash.py tests/test_v09191_unified_f1_dash.py tests/test_v09195_dash_event_pages.py tests/test_v09196_dash_map_engine_recording_minimize.py`
- Result: `24 passed`


---

## Archived source: `V0.9.19.8.6.7_EXACT_TYRE_BRAKE_SYMMETRY_HOTFIX_NOTES.md`

# V0.9.19.8.6.7 — Exact Tyre/Brake Symmetry Hotfix

## Fixes
- Rebuilt the tyre/brake page using one mirrored layout blueprint for both native FD and LAN.
- Pressure and PSI are separated; PSI is intentionally small and cannot overlap the pressure value.
- All tyre rows use matching font sizing and spacing.
- Removed the combined two-bar tyre graphic; OUT, IN and BRK are now three independent equal gauges.
- Enforced symmetry:
  - Left wheels: OUT | IN | BRK from outside toward center.
  - Right wheels: BRK | IN | OUT from center toward outside.
- Brake temperature and brake damage stay on the inside side of every wheel.
- Tyre pressure/temperatures/wear/damage/blister stay on the outside side.
- Native pressure text box enlarged to avoid clipping.

## Validation
- `509 passed, 383 subtests passed`


---

## Archived source: `V0.9.19.8.6.8_TYRE_VALUE_FONT_UNIFICATION_HOTFIX_NOTES.md`

# V0.9.19.8.6.8 – Tyre value font unification hotfix

Only the requested font-sizing change was made.

## Fixed
- `PSI` text now uses the exact same size as the tyre data values.
- OUTER temperature, INNER temperature, WEAR, TYRE DMG and BLISTER values remain on that same shared size.
- Applied to both native FD and LAN/browser.
- Large tyre pressure number remains unchanged.

## Files changed
- `src/dashboard_server.py`
- `src/overlay/window.py`
- `src/main.py`


---

## Archived source: `V0.9.19.8.6.9_TYRE_PRESSURE_VALUE_SIZE_FIX_NOTES.md`

# V0.9.19.8.6.9 — Tyre pressure value size exact fix

This hotfix corrects the previous misunderstanding.

The tyre pressure value itself (for example `24.36` / `21.70`) is no longer rendered with a special large font. In both LAN and native FD, the following now use the same value font size as the OUTER temperature value:

- tyre pressure value
- PSI suffix
- OUTER temperature
- INNER temperature
- tyre wear
- tyre damage
- blister

No telemetry or decision logic changed.


---

## Archived source: `V0.9.19.8.6_COMBINED_DAMAGE_TYRE_QUAD_NOTES.md`

# V0.9.19.8.6 — Combined Damage + Tyre Quad

- Removed the separate ENGINE page from the F1 Dash navigation.
- DAMAGE now contains all car/aero damage plus all engine/hybrid wear channels in one page.
- TYRES & BRAKES redesigned as a four-corner compact panel inspired by the supplied reference image.
- Each corner retains PSI, outer/surface temp, inner temp, brake temp, wear, tyre damage, brake damage and blister data.
- Added a vertical health bar per wheel with dynamic severity color.
- Native FD and LAN/browser layouts updated together.


---

## Archived source: `V0.9.19.8_REAL_TELEMETRY_TRACK_MAP_CACHE_NOTES.md`

# V0.9.19.8 — Real Telemetry Track Map Cache

This release removes approximate hand-drawn track geometry from the live F1 Dash map path.

- First time on a circuit: the map is learned from real F1 26 world-position telemetry during one complete lap.
- A lap is accepted only when capture started near start/finish, reached at least 88% of game track length, contains at least 300 spatial samples, and advances normally to the next lap.
- The learned map is saved to `track_maps_cache.json` in the Race Engineer project folder.
- Future sessions/replays on that track load the learned map immediately from startup.
- Replay/live seek jumps do not create bridge lines across the circuit.
- Incomplete/partial first laps are discarded at the lap boundary rather than joined to the next lap.
- Native FD and LAN dashboard both use the same cached real map.
- YOU / REF / two ahead / two behind and START markers remain supported on learned maps.
- The map drawing area remains expanded to use the available F1 Dash screen.

No strategy, engineer decision, radio, telemetry decoding, or vehicle logic was changed.


---

## Archived source: `V0.9.1_UNIFIED_STRATEGY_NOTES.md`

# V0.9.1 Unified Deterministic Strategy

Built from the supplied V0.9.0 baseline.

## Changes
- Pit radio decisions remain 100% offline and deterministic; no Ollama/LLM is used.
- Added one central service plan shared by radio and automatic pit calls.
- Added fact-based replacement tyre selection from the actual available tyre-set inventory.
  - Current/game-provided weather determines dry/intermediate/wet class.
  - Within the matching class, the least already-worn available set is selected.
  - EA-provided lap delta is only a tie-breaker; the code does not invent future pace/degradation.
- Added natural radio intents for "which tyre/compound/set" and wing service/adjustment questions.
- Front-wing service is separated from non-serviceable damage.
- `m_nextFrontWingValue` is reported as the game-provided next front-wing value. The engineer never invents a wing click adjustment when that value is unavailable.
- Pit-service penalties feed the same service plan; drive-throughs are explicitly not assumed to be served by a normal tyre stop.
- Fuel uses EA's reported remaining-laps value only; refuelling is never assumed.
- Automatic pit calls are transition/cooldown controlled and use the same deterministic service-plan wording as radio.
- Critical safety messages retain higher priority than strategy calls.

## Important boundary
Setup recommendations that require causal inference (for example "add two clicks because of understeer") are intentionally NOT invented. Until measured track-distance handling evidence is implemented, the engineer can report the current setup and EA's game-provided next-front-wing value, and can call for repair when front-wing damage is serviceable.


---

## Archived source: `V0.9.20.0_COACHING_DATA_FOUNDATION_NOTES.md`

# V0.9.20.0 — Coaching Data Foundation

This release begins the deterministic performance-coach implementation on top of the frozen V0.9.19.8.6.24 native/LAN dashboard baseline.

## Added

- New authoritative `src/coaching_analysis.py` module.
- New `CornerAnalysis` data model shared by future coaching, radio and analysis layers.
- Per-corner measured braking anchors:
  - brake onset
  - brake release
  - brake duration
  - peak brake
  - trail-brake distance
- Per-corner cornering anchors:
  - sustained steering-based turn-in
  - minimum-speed point as an explicit `min_speed_proxy` apex method
  - minimum speed
- Per-corner exit/traction anchors:
  - initial meaningful throttle pickup
  - full throttle
  - pickup-to-full-throttle distance
  - coasting distance
  - exit speed
- Per-corner control facts:
  - entry/apex/exit gear
  - shift count
  - peak absolute steering
  - steering reversal count
- Distance-aligned current/reference comparisons for all of the above.
- Entry / mid / exit and whole-corner measured time-loss attribution.
- Deterministic current/reference data-quality, physical-match quality and combined confidence score.
- `corner_analyses` is now included in completed-lap comparisons and post-session JSON analysis.

## Compatibility

- Existing `section_comparisons` remains intact.
- Existing session-analysis JSON `version` stays `0.9.10.0` for compatibility; `coaching_schema_version: 0.9.20.0` identifies the new schema.
- Native overlay source is unchanged.
- LAN dashboard source is unchanged.
- No new spoken coaching is enabled yet. V0.9.20.0 is the measurement/data foundation only.

## Validation

- Python compile checks passed.
- New V0.9.20.0 foundation tests passed.
- Full regression: **512 tests passed + 383 subtests passed**.


---

## Archived source: `V0.9.20.1.1_DIAGNOSIS_LOSS_GUARD_HOTFIX_NOTES.md`

# V0.9.20.1.1 — Diagnosis Loss-Guard Hotfix

## Purpose
Prevent deterministic coaching from treating a telemetry difference as a mistake when the measured comparison does not show time loss.

## Changes
- Suppress all corrective diagnosis when the whole matched corner is equal or faster than the reference (`time_loss_s <= 0`).
- Require >15 ms measured positive loss in the issue's own ENTRY/MID/EXIT phase before that issue can become a coaching candidate.
- Preserve all raw telemetry differences and time measurements in `CornerAnalysis` even when coaching is suppressed.
- Add `coaching_eligible` and `coaching_suppression_reason` to make suppression explicit in exported analysis JSON.
- Keep min-speed-proxy `apex_early` / `apex_late` as supporting evidence only; they cannot be selected as the primary diagnosis until a true geometric apex model exists.
- Candidate JSON now includes `primary_eligible`.

## Why
The V0.9.20.1 Time Trial validation showed corners where the current lap gained time but still received correction such as `brake_pressure_high` or `brake_late`. The new guards prevent those false-positive coaching instructions.

## UI scope
No native or LAN dashboard changes.


---

## Archived source: `V0.9.20.1.2_COACHING_DEADBAND_HOTFIX_NOTES.md`

# V0.9.20.1.2 — Coaching Deadband Hotfix

This hotfix adds a 20 ms whole-corner coaching deadband on top of the V0.9.20.1.1 measured-loss guards.

## Change

- Corrective coaching is suppressed when measured whole-corner loss is **less than 0.020 s**.
- Faster/equal corners continue to use `corner_not_slower`.
- Positive losses below 20 ms use `corner_loss_below_deadband`.
- All raw measurements, phase losses and comparison data remain available for analysis.
- The existing per-phase >15 ms support guard remains unchanged.
- Min-speed-proxy apex timing remains supporting-only and cannot become the primary diagnosis.

This specifically prevents noise-level cases such as a +0.009 s net corner from producing a corrective call just because one phase temporarily lost more time before another phase recovered it.

Native and LAN dashboard layouts remain frozen.


---

## Archived source: `V0.9.20.1_CORNER_INTELLIGENCE_NOTES.md`

# V0.9.20.1 — Corner Intelligence / Deterministic Diagnosis Layer

This release builds directly on the V0.9.20.0 `CornerAnalysis` measurement model. It adds deterministic diagnosis only; it does not yet speak coaching messages or change the frozen native/LAN dashboards.

## Implemented

- Dominant loss phase: `ENTRY`, `MID`, or `EXIT` from measured aligned phase loss.
- Deterministic issue candidates with severity, confidence, actionability, score and estimated phase/corner time cost.
- Early/late braking.
- High/low peak brake pressure.
- Weak/excessive trail braking.
- Excessive coasting.
- Low minimum speed.
- Early/late turn-in.
- Early/late apex using the existing minimum-speed apex proxy.
- Late throttle pickup.
- Early throttle pickup only when increased measured wheel-slip supports a traction-limited interpretation.
- Slow transition from throttle pickup to full throttle.
- Apex-gear mismatch.
- Low exit speed.
- Dominant diagnosis selection so downstream coaching does not list every telemetry difference.
- Low-quality measurements suppress diagnosis.

## New `CornerAnalysis` outputs

- `dominant_phase`
- `diagnosis`
- `diagnosis_label`
- `diagnosis_severity`
- `diagnosis_confidence`
- `actionability`
- `estimated_time_cost_s`
- `issue_candidates`
- measured `max_slip`, reference slip and slip delta

## Deliberately not implemented yet

- Spoken coaching / message scheduling.
- Multi-lap repeat counters or coaching memory.
- Abrupt brake-release diagnosis.
- True path/racing-line deviation.
- Path-derived geometric apex.

These remain separate so the measurement and diagnosis layers stay deterministic and independently testable.


---

## Archived source: `V0.9.20.2_COACHING_PRIORITY_MULTI_LAP_MEMORY_NOTES.md`

# V0.9.20.2 — Coaching Priority + Multi-Lap Pattern Memory

## Scope

This release sits above the validated V0.9.20.1.2 deterministic diagnosis layer. It does not change telemetry acquisition, corner measurements, native dashboard geometry, or LAN dashboard geometry.

## Added

- New `src/coaching_priority.py` session-scoped deterministic coaching memory.
- Per-lap ranking of only `coaching_eligible` and `primary_eligible` issue candidates.
- Priority formula based on measured time cost × confidence × actionability × repeat factor.
- One selected coaching focus per lap comparison.
- Per-corner/per-issue observation history and opportunity counting.
- Repeat count and persistence (`observations / opportunities`).
- Mean/median issue magnitude and measured time cost.
- Total measured issue time cost, mean confidence and mean actionability.
- Improvement/regression/stable trend from first-to-latest measured issue cost with a 15 ms deadband.
- Recurring-pattern list and session coaching focus.
- Session-wide issue summary across corners.
- `comparisons_to_best[*].coaching_priority` in analysis JSON.
- Top-level `session_coaching` in analysis JSON.
- Coaching schema version `0.9.20.2`.

## Guardrails retained

- Whole-corner 20 ms correction deadband.
- Per-phase measured-loss requirement.
- Faster corners are never converted into corrective coaching.
- Min-speed-proxy apex candidates remain supporting-only.
- No causal claim is inferred from telemetry correlation.

## Still pending

- Live/post-corner speech trigger and safe speech windows.
- Engineer/race-control message arbitration for coaching speech.
- Per-issue spoken cooldown and unchanged-advice suppression.
- Richer consistency/dispersion metric beyond recurrence and median/mean statistics.
- Lap-end spoken coach summary and potential-lap engine.

## UI freeze

`src/overlay/window.py` and `src/dashboard_server.py` remain unchanged.


---

## Archived source: `V0.9.20.3.1_S_MODE_COACH_PRIORITY_HOTFIX_NOTES.md`

# V0.9.20.3.1 — S-Mode Coach Priority Hotfix

## Fix

The automatic 2026 `S Mode.` reminder no longer outranks or pre-empts immediate post-corner coaching.

- `coach:corner:*` keeps normal coaching rank.
- `assist:s_mode` is now lower-priority routine chatter.
- A post-corner coaching call can pre-empt a currently speaking S-Mode reminder.
- DRS and ERS assist reminder priority is unchanged.
- Critical, strategy and driver-requested radio priority is unchanged.

This fixes live/replay cases where repeated `S Mode.` calls occupied the speech window and caused a useful corner correction to become stale or be skipped.


---

## Archived source: `V0.9.20.3_IMMEDIATE_POST_CORNER_SAFE_SPEECH_NOTES.md`

# V0.9.20.3 — Immediate Post-Corner Coaching + Safe Speech Timing

## Scope

This release connects the validated deterministic corner intelligence to live radio delivery. It does not change the frozen native dashboard or LAN dashboard geometry.

## Added

- New `src/post_corner_coach.py` live deterministic coaching scheduler.
- Uses the existing `CornerAnalysis` loss guards and diagnosis output rather than a second coaching heuristic path.
- Evaluates a physical corner only after the current lap has passed the reference corner exit by 35 m.
- Generates short one-correction coaching lines for the existing deterministic diagnosis codes.
- Safe-speech gate requires the car to be settled: low brake, low steering workload, meaningful throttle and speed.
- Next-braking-zone timing gate requires at least 3.5 s before releasing a coaching call.
- Pending calls are dropped once braking is <=1.5 s away or after 8 s pending age.
- Coaching remains lowest radio priority, so critical/assist/strategy/information traffic keeps precedence.
- Coaching profiles default to Time Trial, Practice and Qualifying; Race performance coaching is silent.
- Maximum two post-corner calls per lap.
- Same corner + same issue has a two-lap spoken cooldown to prevent repetitive chatter.
- Minimum live priority score of 0.060 (`measured time cost × diagnosis confidence × actionability`).
- Runtime counters/status are exposed via `state.extended['post_corner_coaching']`.
- `MeasuredPerformanceRecorder.current_reference_lap()` and `current_lap_snapshot()` provide authoritative live coaching inputs.
- Queued coaching corrections for the same physical corner supersede older queued corrections.

## Guardrails retained

- Whole-corner 20 ms correction deadband.
- Per-phase measured-loss requirement.
- Faster corners are never converted into corrective coaching.
- Min-speed-proxy apex remains supporting-only.
- No causal claims or predictions.

## Radio safety

A coaching line is never released merely because a diagnosis exists. It is held until the driver is on a low-workload straight with adequate time before the next measured braking zone. If that window does not appear in time, the line is discarded rather than spoken late into the next corner.

## UI freeze

`src/overlay/window.py` and `src/dashboard_server.py` are unchanged.


---

## Archived source: `V0.9.20_TELEMETRY_COACHING_CAPABILITY_AUDIT.md`

# V0.9.20 — Telemetry / Coaching Capability Audit

Baseline audited: **V0.9.19.8.6.24**  
Roadmap target: deterministic coaching approaching Trophi.ai-style driver development while preserving Race Engineer's F1 race-engineering strengths.

This audit is based on the current source code, not on planned features.

## Audit status legend

- **AVAILABLE NOW** — the required measurement and usable implementation already exist.
- **PARTIALLY AVAILABLE** — useful logic exists, but it is incomplete, coarse, or not suitable as the final coaching authority.
- **NEEDS NEW DERIVATION** — the source telemetry is already available, but Race Engineer does not yet calculate the required metric/diagnosis.
- **NOT AVAILABLE** — neither a reliable current implementation nor a directly usable captured source exists in the current performance pipeline.

---

# 1. Executive summary

Race Engineer already has a much stronger coaching foundation than the roadmap checkboxes originally implied. The current application already records a distance-aligned driver trace, builds braking-zone-based sections, compares completed laps to a reference, computes live delta, measures local time gain/loss, provides live driver/reference input overlays, and exposes several measured-performance radio queries.

The main gap is **not telemetry acquisition**. Most of the P0 coaching inputs already exist. The main work for V0.9.20 is to convert those inputs into a more complete **corner model**, derive braking/turn-in/apex/throttle metrics, add confidence/validity gates, and create a persistent coaching-priority/memory layer.

### Current strengths already present

- 5 m distance-binned measured-performance samples.
- Current lap time and lap distance.
- Speed, throttle, brake, steering, gear and RPM traces.
- Lateral/longitudinal G.
- Wheel slip ratio.
- ERS store and fuel in the measured trace.
- Authoritative completed lap/sector timing from Session History.
- Sticky invalid-lap handling.
- Start/finish anchoring checks.
- External, session-best, previous and manual reference modes.
- AI/rival reference capture infrastructure.
- Distance-aligned live reference interpolation.
- Braking-zone section detection.
- Stable physical-distance section matching.
- Brake-point, minimum-speed, full-throttle, exit-speed, peak-brake and slip comparisons.
- Non-overlapping local time-loss attribution.
- Live and completed-lap coaching metrics in the overlay model.
- Existing measured-performance voice intents such as performance comparison, braking comparison, traction comparison and driving issues.
- JSON post-session lap analysis export.

### Biggest missing P0 capabilities

1. True corner segmentation instead of only braking-zone sections.
2. Brake release and trail-brake metrics.
3. Initial throttle pickup and throttle-ramp metrics.
4. Turn-in detection.
5. Better apex definition than minimum-speed proxy.
6. Per-corner gear and steering comparison.
7. Diagnosis confidence and data-quality scoring.
8. Persistent per-corner multi-lap issue history.
9. Coaching priority/memory and safe speech-window scheduling.
10. Potential-lap calculation.
11. Lap-end coaching summary using the new corner analysis.

---

# 2. Raw telemetry availability audit

| Required coaching source | F1 decoded now | Stored in measured-performance trace | Current use | Audit status |
|---|---:|---:|---|---|
| Lap distance | Yes | Yes (`d`) | Alignment, sections, live delta | **AVAILABLE NOW** |
| Lap clock | Yes | Yes (`t`) | Live/reference delta, local time loss | **AVAILABLE NOW** |
| Official completed lap time | Yes | Completed summary | Session History authority | **AVAILABLE NOW** |
| Sector times | Yes | Completed summary | Lap history/analysis | **AVAILABLE NOW** |
| Lap validity | Yes | Completed summary | Invalid-lap rejection | **AVAILABLE NOW** |
| Speed | Yes | Yes | Min/exit/max speed, traces | **AVAILABLE NOW** |
| Throttle | Yes | Yes | Full throttle, coast, overlap | **AVAILABLE NOW** |
| Brake | Yes | Yes | Brake sections, peak brake | **AVAILABLE NOW** |
| Steering | Yes | Yes | Steering reversals only | **AVAILABLE NOW** source / **NEEDS NEW DERIVATION** for corner coaching |
| Gear | Yes | Yes | Whole-lap gear-change count | **AVAILABLE NOW** source / **NEEDS NEW DERIVATION** for corner coaching |
| RPM | Yes | Yes | Trace/reference data | **AVAILABLE NOW** source |
| Lateral G | Yes | Yes | Whole-lap max | **AVAILABLE NOW** source |
| Longitudinal G | Yes | Yes | Whole-lap max braking G | **AVAILABLE NOW** source |
| Wheel slip ratio | Yes | Yes | Section max slip | **AVAILABLE NOW** |
| ERS store | Yes | Yes | Driver/reference traces | **AVAILABLE NOW** |
| Fuel mass | Yes | Yes | Whole-lap measured use | **AVAILABLE NOW** |
| World X/Y/Z | Yes in Motion packet | **No** | Used elsewhere for map learning, not coaching trace | **NEEDS NEW DERIVATION / capture extension** |
| Yaw/pitch/roll | Yes in Motion packet | **No** in measured trace | Legacy rival sanitisation can use yaw if present | **NEEDS NEW DERIVATION / capture extension** |
| Wheel slip angle | Yes in MotionEx | No | Not used by performance recorder | **NEEDS NEW DERIVATION / capture extension** |
| Wheel forces | Yes in MotionEx | No | Not used by performance recorder | **P2 candidate** |
| Track landmarks | No direct telemetry source | No | No database | **NOT AVAILABLE** until metadata is created |

### Important conclusion

For the V0.9.20 P0 coach we **do not need a new F1 packet family**. The essential channels for braking, throttle, minimum speed, steering, gear and time-loss coaching are already decoded and mostly already stored. Racing-line coaching is the main area requiring additional capture of Motion position/orientation channels.

---

# 3. P0 Driving Performance Engine audit

| Roadmap feature | Current implementation | Status | V0.9.20 action |
|---|---|---|---|
| Corner segmentation for every track | `_segments()` detects stable braking zones and merges secondary brake pulses | **PARTIALLY AVAILABLE** | Build stable true-corner model; retain braking-zone detector as input |
| Automatic corner start/braking/turn-in/apex/exit boundaries | Brake start/end, min-speed point and full-throttle/300 m exit already exist | **PARTIALLY AVAILABLE** | Add turn-in; improve apex/exit semantics |
| Braking point detection | Section `start_m` from brake threshold | **AVAILABLE NOW** | Keep; refine interpolation below 5 m if useful |
| Brake onset comparison vs reference | `brake_point_delta_m` | **AVAILABLE NOW** | Promote to CornerAnalysis authority |
| Peak brake pressure comparison | `peak_brake_delta` | **AVAILABLE NOW** | Keep |
| Brake-release timing comparison | Brake trace exists, section brake end exists but no comparison metric | **NEEDS NEW DERIVATION** | Detect release point/time and compare |
| Trail-braking measurement | Brake + steering/G traces exist | **NEEDS NEW DERIVATION** | Define deterministic trail metric |
| Brake duration comparison | Brake zone distance can be inferred; whole-lap brake distance already exists | **PARTIALLY AVAILABLE** | Add per-corner distance/time duration |
| Coasting duration detection | Whole-lap coasting distance exists | **PARTIALLY AVAILABLE** | Add per-corner coast start/end/time/distance |
| Turn-in point detection | Steering trace available | **NEEDS NEW DERIVATION** | Detect stable steering onset with hysteresis |
| Apex point detection | Minimum-speed location is currently used as anchor/apex proxy | **PARTIALLY AVAILABLE** | Define apex using speed + steering/path; keep min-speed point separately |
| Minimum corner speed comparison | `min_speed_delta_kph` | **AVAILABLE NOW** | Keep |
| Apex speed comparison | Current min speed is a proxy | **PARTIALLY AVAILABLE** | Separate actual/estimated apex speed from min speed |
| Throttle pickup point detection | Only first full-throttle point is stored | **PARTIALLY AVAILABLE** | Add initial meaningful throttle pickup threshold |
| Time-to-full-throttle comparison | Raw throttle/time/distance exists | **NEEDS NEW DERIVATION** | Measure pickup→full-throttle distance/time |
| Exit speed comparison | `exit_speed_delta_kph` | **AVAILABLE NOW** | Keep; standardise exit measurement location |
| Gear selection comparison | Gear trace exists | **NEEDS NEW DERIVATION** | Compare entry/apex/exit gear and shifts per corner |
| Steering-input comparison | Steering trace exists | **NEEDS NEW DERIVATION** | Compare turn-in, peak steer, correction count |
| Entry/apex/exit time-loss attribution | `build_driving_analysis()` partitions approach / braking_to_min_speed / exit | **PARTIALLY AVAILABLE** | Rename/rework phases to true ENTRY/MID/EXIT boundaries |
| Corner-level gain/loss | Non-overlapping region delta is already calculated | **PARTIALLY AVAILABLE** | Make stable true-corner regions authoritative |
| Straight-line loss separation | Track segmentation and straight coaching already exist in overlay | **PARTIALLY AVAILABLE** | Integrate into one common analysis object |
| Confidence score | No formal confidence model | **NOT AVAILABLE** | Build mandatory confidence/validity score |
| Reject invalid/noisy/incomplete comparisons | Invalid laps, start anchoring, section filters, legacy sanitising and stable matching exist | **PARTIALLY AVAILABLE** | Add coaching-specific completeness/outlier/compromise gates |

## P0 assessment

The Driving Performance Engine is approximately **half built at the measurement level**, but it is distributed across `measured_performance.py`, `lap_analysis.py`, `overlay/data.py`, and `performance_coach.py`. V0.9.20 should consolidate this into a single authoritative corner-analysis model rather than duplicating calculations in UI and radio layers.

---

# 4. Current section/corner model audit

Current `MeasuredPerformanceRecorder._segments()` does the following:

1. Detects brake applications at `brake >= 0.10`.
2. Merges nearby secondary braking pulses when the driver has not returned to full throttle.
3. Rejects tiny pedal corrections using distance, speed-drop and strong-short-brake thresholds.
4. Searches forward up to 300 m for full throttle.
5. Uses minimum speed as the section anchor.
6. Stores:
   - brake start
   - brake end
   - section end
   - brake-start speed
   - minimum speed and distance
   - first full-throttle distance
   - exit speed
   - peak brake
   - maximum slip

This is already useful and should **not be discarded**. It should become the braking-zone detector underneath a richer corner model.

### Limitation

A corner that requires little/no braking can be absent entirely. Complexes can also be represented according to brake applications rather than actual track corners. Therefore the existing section ID cannot yet be treated as a guaranteed real-world `Turn X` across every circuit.

---

# 5. Current reference comparison audit

The application already supports:

- session-best reference
- previous-lap reference
- manually selected completed lap
- external stored reference
- AI benchmark references
- Time Trial rival references
- lap-boundary-safe reference switching
- distance interpolation for live reference throttle/brake/speed/time/ERS

`compare_sections()` already calculates:

- brake-point delta
- minimum-speed delta
- full-throttle delta
- exit-speed delta
- peak-brake delta
- wheel-slip delta

`build_driving_analysis()` already calculates:

- common distance-aligned time delta
- largest clean 100 m gain/loss
- non-overlapping per-section time change
- approach time change
- braking-to-min-speed time change
- exit time change
- reconciliation against official lap-time delta

### Audit result

**Reference comparison infrastructure is already strong enough for V0.9.20.** It needs extension, not replacement.

---

# 6. P0 Corner Intelligence Engine audit

| Diagnosis | Current state | Status |
|---|---|---|
| Early braking | Existing coach interprets negative brake-point delta | **PARTIALLY AVAILABLE** |
| Late braking | Existing coach identifies reference braking earlier | **PARTIALLY AVAILABLE** |
| Excessive brake pressure | Peak brake delta exists; no diagnosis thresholds/context | **NEEDS NEW DERIVATION** |
| Insufficient brake pressure | Peak brake delta exists; no diagnosis thresholds/context | **NEEDS NEW DERIVATION** |
| Abrupt brake release | Raw brake trace available | **NEEDS NEW DERIVATION** |
| Weak trail braking | Raw brake/steering/G available | **NEEDS NEW DERIVATION** |
| Excessive trail braking | Raw brake/steering/G available | **NEEDS NEW DERIVATION** |
| Excessive coasting | Whole-lap metric exists; per-corner raw data available | **PARTIALLY AVAILABLE** |
| Low minimum speed | Existing coach can call it | **PARTIALLY AVAILABLE** |
| Early turn-in | No turn-in metric yet | **NEEDS NEW DERIVATION** |
| Late turn-in | No turn-in metric yet | **NEEDS NEW DERIVATION** |
| Early apex | Current min-speed anchor is insufficient | **NEEDS NEW DERIVATION** |
| Late apex | Current min-speed anchor is insufficient | **NEEDS NEW DERIVATION** |
| Throttle pickup too late | Full-throttle-late detection exists; initial pickup absent | **PARTIALLY AVAILABLE** |
| Throttle too early / traction limited | Max slip exists; no coupled throttle/slip diagnosis | **NEEDS NEW DERIVATION** |
| Slow transition to full throttle | Raw throttle trace available | **NEEDS NEW DERIVATION** |
| Inefficient gear choice | Gear trace available | **NEEDS NEW DERIVATION** |
| Poor exit-speed conversion | Exit-speed delta already used by coach | **PARTIALLY AVAILABLE** |
| Line/path deviation | Position telemetry decoded but not captured in performance trace | **NOT AVAILABLE in current coach pipeline** |
| ENTRY/MID/EXIT primary loss | Existing phases are close but use braking/min-speed proxies | **PARTIALLY AVAILABLE** |
| Estimate issue time cost | Region/phase time delta exists but cause-specific attribution does not | **PARTIALLY AVAILABLE** |
| Select dominant cause | `performance_coach` chooses highest heuristic candidate per section | **PARTIALLY AVAILABLE** |

### Existing coach logic worth preserving

`performance_coach.py` already performs a simple deterministic action selection for brake point, minimum speed, full throttle, exit speed and slip. This should be replaced by the new structured diagnosis engine only after regression tests reproduce or improve its valid behavior.

---

# 7. P0 Coaching Priority Engine audit

| Requirement | Current state | Status |
|---|---|---|
| Candidate issue scoring | Simple heuristic score in `performance_coach.py` | **PARTIALLY AVAILABLE** |
| Time-cost weighting | Local time loss exists but is not combined with diagnosis score | **NEEDS NEW DERIVATION** |
| Confidence weighting | No confidence model | **NOT AVAILABLE** |
| Repeat-frequency weighting | No per-corner issue history | **NOT AVAILABLE** |
| Actionability weighting | No explicit model | **NOT AVAILABLE** |
| Suppress tiny differences | Hard thresholds exist for some simple coach actions | **PARTIALLY AVAILABLE** |
| One correction per message | Existing corner action selection picks one candidate per section | **PARTIALLY AVAILABLE** |
| Cooldown per corner/issue | Race-engineer messaging has cooldown concepts; coach-specific memory absent | **NOT AVAILABLE** |
| Avoid repeated advice each lap | No persistent coaching issue memory | **NOT AVAILABLE** |
| Promote repeated mistakes | No | **NOT AVAILABLE** |
| Detect improvement after coaching | No coaching-memory model | **NOT AVAILABLE** |
| Move to next issue when solved | No | **NOT AVAILABLE** |
| Critical race-engineer priority | Existing race-engineer priority architecture exists | **PARTIALLY AVAILABLE** |
| Suppress during major race events | Existing global message architecture can support it; coach integration absent | **PARTIALLY AVAILABLE** |
| Safe speech window to next braking zone | Track segments/reference distances already available | **NEEDS NEW DERIVATION** |
| Queue/drop unsafe coach messages | TTS relevance/stale queue infrastructure exists; coach rule absent | **PARTIALLY AVAILABLE** |

### Audit result

This is the largest architectural gap. V0.9.20 needs a dedicated **CoachPriorityEngine** rather than putting more thresholds into `performance_coach.py`.

---

# 8. P0 Immediate Post-Corner Coaching audit

Current live UI already determines active turn/straight segments and live section metrics, but automatic spoken post-corner coaching is not yet a complete subsystem.

- Confirmed corner-exit trigger: **NEEDS NEW DERIVATION**
- Meaningful loss/gain gate: **PARTIALLY AVAILABLE** from local delta
- One-sentence deterministic correction: **PARTIALLY AVAILABLE**
- Positive reinforcement: **NOT AVAILABLE** as persistent coached-improvement logic
- Safe speech timing: **NOT AVAILABLE**
- Engineer/race-control arbitration: **PARTIALLY AVAILABLE** infrastructure
- Configurable frequency: **NOT AVAILABLE**
- Positive-call toggle: **NOT AVAILABLE**

---

# 9. P0 Multi-Lap Pattern Detection audit

The recorder stores up to 20 completed laps and therefore already retains enough session history. However, it does not currently aggregate the same corner diagnosis across laps.

### Available foundation

- up to 20 completed measured laps
- per-lap section summaries
- reference comparisons
- valid/invalid status
- distance-aligned samples

### Missing derivations

- per-corner issue history
- mean/median brake error
- mean min-speed deficit
- mean throttle-pickup error
- repeat count
- persistence score
- improvement/regression slope
- corner consistency
- session-wide recurring patterns

**Overall status: NEEDS NEW DERIVATION.**

---

# 10. P0 Lap-End Coach Summary audit

The application already has completed-lap detection, official lap times, reference delta and a general end-of-session summary system. It does not yet build the proposed performance-coach lap summary.

| Requirement | Status |
|---|---|
| Lap time | **AVAILABLE NOW** |
| Delta vs active reference | **AVAILABLE NOW** |
| Delta vs previous lap | **AVAILABLE NOW** source/logic |
| Biggest time-loss corner | **PARTIALLY AVAILABLE** from ranked measured loss regions |
| Second-biggest opportunity | **PARTIALLY AVAILABLE** |
| Best-improved corner | **NEEDS NEW DERIVATION** |
| Current coaching focus | **NOT AVAILABLE** until coach memory exists |
| Potential lap | **NOT AVAILABLE** |
| Busy race-context suppression | **PARTIALLY AVAILABLE** architecture |
| Mode-specific wording | **NOT AVAILABLE** |

---

# 11. P0 Potential Lap Engine audit

### Existing data

- official lap/sector times
- multiple completed valid laps
- non-overlapping measured track regions
- distance-aligned 5 m samples
- session best selection

### Missing implementation

- sector theoretical-best calculator
- corner/region theoretical-best calculator
- compatibility filters for conditions/tyres/fuel/damage
- realistic available gain

**Overall status: NEEDS NEW DERIVATION.**

Important: the data model already makes this feasible without changing UDP decoding.

---

# 12. P1 Post-Session Coach Report audit

Current `lap_analysis.py` already exports a structured JSON report containing:

- completed laps
- valid timed laps
- best valid lap
- comparisons to best
- matched corner/section comparisons
- distance-aligned delta trace
- largest 100 m loss/gain
- phase analysis
- ranked measured loss regions
- reconciliation information

Therefore:

- JSON analysis foundation: **AVAILABLE NOW**
- Trophi-style coaching interpretation: **PARTIALLY AVAILABLE**
- HTML report: **NOT AVAILABLE**
- interactive per-corner drill-down: **NOT AVAILABLE**
- technique consistency metrics: **NOT AVAILABLE**
- session trend summary: **NEEDS NEW DERIVATION**

---

# 13. Interactive performance radio audit

The roadmap originally marked this as entirely unimplemented, but the code already contains measured-performance voice support.

Existing intents include:

- performance comparison / "where am I losing"
- braking comparison
- traction comparison
- driving issues / coasting / overlap
- lap comparison
- reference controls

Existing deterministic answers can report:

- overall lap delta
- largest measured 100 m loss
- brake-start difference
- peak-brake difference
- first-full-throttle difference
- max-slip difference
- coasting / overlap / steering-reversal differences

### Status

**PARTIALLY AVAILABLE.**

The V0.9.20 work should extend this onto the new authoritative `CornerAnalysis` objects rather than adding another independent answer path.

Still missing:

- "Why am I slow in Turn X?"
- "Where should I brake for Turn X?"
- "Did I improve Turn X?"
- "What is my potential lap?"
- "What should I focus on next lap?"
- true session consistency queries

---

# 14. Racing-line capability audit

The F1 Motion packet already decodes:

- world X/Y/Z
- forward direction
- lateral/longitudinal/vertical G
- yaw/pitch/roll

The current measured-performance `Sample` does **not** store world position or yaw. Consequently a completed performance reference cannot yet provide a deterministic driver-vs-reference path comparison.

### Required V0.9.20/P1 extension

Add optional compact fields to the performance trace:

- `world_x`
- `world_y`
- `world_z`
- `yaw`

Potential later additions:

- wheel slip angle
- wheel lateral force
- wheel longitudinal force

This should be done without changing the frozen native dashboard.

---

# 15. Reference-lap ecosystem audit

The roadmap understated current capability.

| Reference capability | Status |
|---|---|
| Personal/session-best reference | **AVAILABLE NOW** |
| Previous-lap reference | **AVAILABLE NOW** |
| Manual completed-lap reference | **AVAILABLE NOW** |
| External reference import | **AVAILABLE NOW** |
| Reference export | **AVAILABLE NOW** |
| AI reference capture | **AVAILABLE NOW** |
| Time Trial rival reference | **AVAILABLE NOW** |
| Lap-boundary-safe switching | **AVAILABLE NOW** |
| Physical-distance interpolation | **AVAILABLE NOW** |
| Basic metadata dictionary | **PARTIALLY AVAILABLE** |
| Strict game/track/car/assist/setup/weather matching schema | **PARTIALLY AVAILABLE / needs expansion** |
| Friend/community distribution | **NOT AVAILABLE** |

---

# 16. Data-quality audit

Already implemented safeguards include:

- sticky lap invalidity
- authoritative Session History timing/validity
- start/finish-line trace anchoring
- no partial-lap promotion to session best
- asynchronous lap-clock regression rejection
- Time Trial rival sanitisation
- global physical-distance corner matching
- tiny brake-event rejection
- boundary guard for strongest local gain/loss
- explicit full-lap reconciliation residual
- finite-number checks
- event-context metric applicability

Still required for coaching:

- traffic-compromised segment detection
- SC/VSC/yellow compromised segment detection
- pit-entry/pit-exit performance exclusion
- damage mismatch checks
- tyre-age/compound mismatch warnings
- fuel-load mismatch handling
- wet/dry mismatch handling
- per-metric sample completeness
- per-diagnosis confidence
- local outlier rejection

**Overall status: PARTIALLY AVAILABLE, with a strong existing foundation.**

---

# 17. Recommended V0.9.20 architecture

Do not put the new logic directly into the UI or voice files.

Recommended modules:

```text
src/coaching/
    models.py
    corner_detector.py
    corner_metrics.py
    corner_diagnosis.py
    confidence.py
    pattern_history.py
    priority.py
    lap_summary.py
    potential_lap.py
```

Suggested authoritative object:

```text
CornerAnalysis
    lap_number
    corner_id
    region_start_m
    region_end_m

    brake_start_m
    brake_point_delta_m
    peak_brake
    peak_brake_delta
    brake_release_m
    brake_release_delta_m
    trail_brake_score
    trail_brake_delta

    turn_in_m
    turn_in_delta_m
    min_speed_m
    min_speed_kph
    min_speed_delta_kph
    apex_m
    apex_speed_kph

    throttle_pickup_m
    throttle_pickup_delta_m
    full_throttle_m
    full_throttle_delta_m
    throttle_ramp_distance_m
    exit_speed_kph
    exit_speed_delta_kph

    entry_time_loss_s
    mid_time_loss_s
    exit_time_loss_s
    total_time_loss_s

    diagnosis
    estimated_issue_cost_s
    confidence
    actionability
    valid
    invalid_reason
```

The UI, radio, lap summary and post-session report should all consume this same object.

---

# 18. Recommended implementation order for V0.9.20

## V0.9.20.0 — Coaching data foundation

1. Add `src/coaching/models.py`.
2. Consolidate current matched section metrics into `CornerAnalysis`.
3. Add metric validity/completeness flags.
4. Preserve all current outputs/tests.

## V0.9.20.1 — Brake dynamics

5. Brake-release point.
6. Per-corner brake duration.
7. Trail-brake metric.
8. Abrupt-release detection.

## V0.9.20.2 — Turn-in / throttle dynamics

9. Turn-in detection from steering.
10. Initial throttle pickup.
11. Pickup-to-full-throttle time/distance.
12. Per-corner gear selection/shift comparison.

## V0.9.20.3 — Corner phase and diagnosis

13. Stable ENTRY/MID/EXIT boundaries.
14. Cause candidates.
15. Cause-specific time-cost association.
16. Confidence score.
17. Dominant diagnosis selection.

## V0.9.20.4 — Multi-lap coach memory

18. Per-corner issue history.
19. Repeat/persistence score.
20. Improvement/regression detection.
21. Session coaching focus.

## V0.9.20.5 — Priority + spoken coach

22. Time-cost × confidence × repeat × actionability scoring.
23. Safe speech window.
24. Post-corner correction.
25. Positive improvement calls.
26. Race-engineer message arbitration.

## V0.9.20.6 — Lap summary / potential lap

27. Lap-end performance summary.
28. Sector theoretical best.
29. Corner-region theoretical best.
30. Realistic available gain.

## V0.9.20.7 — Report/radio integration

31. Extend performance radio questions.
32. Export new corner analyses in JSON.
33. Build initial HTML coach report.

Racing-line/path analysis should follow after the P0 coach is stable because it requires widening the recorded performance trace and substantially more validation.

---

# 19. Audit decision

**Proceed with V0.9.20.0.**

No telemetry decoder rewrite is required for the core P0 coach. We should first consolidate the already-existing measured-performance/reference calculations into a single structured coaching layer, then add the missing brake/turn-in/throttle derivations on top of the current 5 m trace.

The frozen native overlay and current LAN dashboard do not need to be changed during this foundation work.

---

# V0.9.20.0 implementation update

The first implementation milestone is complete. `src/coaching_analysis.py` now provides the authoritative `CornerAnalysis` comparison model. The measured-performance recorder derives brake release/duration, trail-brake distance, sustained steering turn-in, minimum-speed apex proxy, throttle pickup, pickup-to-full-throttle distance, per-corner coasting, gear/steering facts, and richer section metadata. Current/reference comparisons now include entry/mid/exit and whole-corner measured time loss plus deterministic data-quality/match-confidence scoring.

Still pending after this foundation: diagnosis labels, repeat-pattern memory, coaching priority/actionability, safe speech scheduling, post-corner calls, lap-end coaching summaries, potential lap, and racing-line/path analysis.

Validation: **512 tests passed + 383 subtests passed**. Native and LAN dashboard source hashes remain unchanged from the frozen V0.9.19.8.6.24 baseline.


---

## Archived source: `V0.9.25.0_INTEGRATED_PERFORMANCE_COACH_NOTES.md`

# V0.9.25.0 — Integrated Performance Coach

## Scope

This release consolidates the locally deliverable V1 performance-coaching roadmap into one build while preserving the existing deterministic race-engineer, strategy, replay, reference-lap, hardware, native dash and LAN dash foundations.

## Live coaching

- Persistent POST / PRE / LAP / POS / RACE switches in Control Center.
- Dynamic pre-corner reminder timing from current speed and distance to the measured reference braking onset.
- Safe post-corner correction delivery with next-braking-zone timing, stale-drop behavior and same-issue cooldown.
- Conservative race coaching with close-traffic, safety-car/VSC, pit, damage, invalid-lap, flag, braking/cornering and radio-priority suppression.
- Routine S-Mode reminders remain non-blocking to performance coaching; critical race-engineer traffic remains authoritative.
- Per-lap limits prevent coaching spam.

## Analysis and memory

- Multi-lap issue memory and deterministic priority.
- Positive improvement/resolution detection.
- Observed valid-sector potential lap.
- Explainable corner/lap consistency metrics.
- Straight-line loss separation.
- Brake-release-ramp distance/time analysis and abrupt-release diagnosis.
- World-position X/Z recording and matched-distance reference-relative racing-line deviation.
- Learned local corner landmarks with optional manual names/visual brake landmarks.

## Reports and interaction

- Deterministic PTT questions for focus, biggest mistake, potential lap, consistency, braking/throttle, Turn X loss/brake target/improvement.
- Automatic JSON and HTML coach reports.
- Persistent local driver-history summary.
- Coaching modes and verbosity remain available via settings/CLI.

## Compatibility

- Normal live launch command is unchanged.
- LAN dashboard source is unchanged.
- Native Control Center is intentionally changed only to add the requested coaching switches.
- Existing `state.extended["post_corner_coaching"]` remains available; the complete status is also under `state.extended["coaching_suite"]`.

## Deliberately outside this local V1 ZIP

Cloud/community reference sharing, a hosted reference library, broad multi-sim adapters, VR/mobile companion products, and a signed Windows installer/updater are ecosystem/distribution projects rather than local coaching-core code and are not represented as completed here.


---

## Archived source: `V0.9.2_MEASURED_PERFORMANCE_NOTES.md`

# V0.9.2 Measured Performance Engine

Built from the supplied V0.9.1 baseline.

## Facts-only design
The recorder bins already-observed player telemetry by lap distance (5 m bins) and compares completed laps. It does not extrapolate future pace, tyre life, fuel-to-finish, catch time, or setup effects.

## Recorded/compared data
- lap distance and elapsed lap time
- speed, throttle, brake, steering, gear and RPM
- Motion lateral/longitudinal G when present
- Motion Ex maximum absolute wheel-slip ratio when present
- ERS store and fuel endpoint changes when present
- braking start/end, measured braking distance and peak input
- first full-throttle position and full-throttle distance
- minimum/maximum speed, gear-change count
- point-by-point elapsed-time delta at common 5 m bins
- largest measured 100 m increase in elapsed-time deficit

Up to 20 completed sampled laps are retained in the performance recorder. The reference is the fastest previously completed valid sampled lap when a valid timed reference exists.

## Radio
Natural deterministic intents include:
- Where am I losing time?
- Where did I gain?
- Compare performance / compare with best
- Braking info / compare braking / braking point
- Traction info / compare traction / throttle compare / corner exit

## Automatic engineer
After a newly completed sampled lap, a concise coaching-priority factual comparison is generated only for a material measured difference (>=0.25 s lap delta or >=0.15 s largest measured 100 m loss). It is announced at most once for that completed lap and remains below safety/race-control/pit priorities.

## Important limitations
A detected distance section is reported by metres, not invented turn numbers. Correlation is not called causation. Endpoint fuel/ERS changes are observed differences. The engine does not issue predictive coaching or setup recommendations from these comparisons.

## Verification
- unittest: 188 tests, OK
- pytest: 196 passed, 383 subtests passed


---

## Archived source: `V0.9.3_INSTANT_TRACK_LIMITS_NOTES.md`

# V0.9.3 Instant Track-Limits Warning

Built from the supplied V0.9.2 baseline.

## Behaviour
- When EA Lap Data increments `m_cornerCuttingWarnings`, Automatic Engineer immediately queues the short CRITICAL call: `Track limits.`
- When EA's `PENA` event reports infringement 25..29 (corner cutting / running wide variants), the same short call is emitted.
- Both paths share the same message key and a 1-second cooldown to suppress near-simultaneous duplicate calls from asynchronous packet families.
- A warning-only track-limit PENA event does not additionally speak the longer `Warning for running wide...` message.
- If race control assigns an actual time, drive-through, stop-go, grid, or other penalty, that separate penalty call is preserved.
- Lap invalidation remains a separate factual `Current lap invalidated.` call because an invalid lap is not always proof that the car physically left the track.

## Facts-only boundary
The software does not infer track boundaries from world coordinates. It reacts only when F1 26 itself reports a corner-cutting/running-wide infringement or increments its corner-cutting warning counter.

## Verification
- pytest: 199 passed, 383 subtests passed
- unittest: 191 tests, OK


---

## Archived source: `V0.9.4_FINE_TUNE_AUDIT_NOTES.md`

# V0.9.4 Fine-Tune / Audit

Baseline: user-supplied V0.9.3.

This pass intentionally preserves the facts-only/no-software-prediction design.

## Fixes and refinements

- Re-armed reversible automatic alert thresholds after genuine recovery using hysteresis. V0.9.3 latched a crossed temperature/damage band for the rest of the session, so a later independent overheat after cooling could be missed.
  - tyre surface temperature: 5 C hysteresis
  - brake temperature: 50 C hysteresis
  - engine temperature: 5 C hysteresis
  - blister/damage/component bands: 5 percentage-point recovery hysteresis where the game reports a lower repaired/replaced value
- A newly fitted tyre set now resets tyre wear/damage/temperature/blister threshold latches so the new physical set is monitored independently.
- The instant `Track limits.` cue now outranks and can interrupt a driver radio answer. Other critical calls retain the existing radio-answer ownership behavior, avoiding a broad disruptive scheduling change.
- Expanded TTS replaceable-state families for tyre/brake/engine temperature and component damage so an older queued state can be superseded by a newer one rather than being spoken late.
- Fixed tyre-set sorting when EA fields such as set wear or lap delta are unavailable/unknown; unknown values no longer risk a Python comparison error.
- Immediate tyre compound selection now uses actual current weather plus an EA offset-0 rain sample when present. A future forecast sample is no longer treated as current weather.
- A future game-forecast weather transition remains factual context but no longer adds deterministic pit score or creates a serviceable pit trigger by itself. This keeps the pit engine within the facts-only rule.

## Audit findings retained deliberately

- Future EA weather forecasts may still be announced/reported as *game-provided forecasts*, but the deterministic engine does not convert them into its own predicted future outcome.
- Generic G-force, suspension, wheel-force, slip, pressure and setup measurements remain factual/on-demand unless a defensible game/project abnormal-state rule exists.
- Non-serviceable damage is reported but does not falsely become a normal pit-repair reason.

## Verification

- `pytest`: 202 passed, 383 subtests passed
- `unittest`: 194 tests, OK
- `compileall`: clean


---

## Archived source: `V0.9.5_MEASURED_DRIVING_INTELLIGENCE_NOTES.md`

# V0.9.5 — Measured Driving Intelligence

Built from the verified V0.9.4 Fine-Tuned baseline. This release remains facts-only: it compares telemetry that has already been observed and does not predict future lap time, tyre life, catch time, setup effect, or driver outcome.

## Added
- Corner/section detection from measured braking phases. Sections are numbered; turn names are not invented.
- Per-section measured facts: brake start, brake-start speed, minimum speed/location, full-throttle point, exit speed, peak brake, and maximum measured slip.
- Section-by-section comparison against the selected completed reference lap.
- Additional completed-lap observations: high-slip distance, throttle/brake overlap distance, coasting distance, and steering-direction reversals.
- Both largest measured 100 m loss and largest measured 100 m gain.
- Reference-lap manager: best valid measured lap (default), previous completed lap, or a manually pinned completed lap.
- Natural radio controls: “use this lap as reference”, “compare with previous”, “use best lap”, and “driving issues”.
- Deterministic decision audit log in `state.extended['decision_audit']`, retaining the latest 200 automatic calls with key, priority, exact spoken text, session time, and observed time.

## Definitions, not safety claims
- Brake-on sample: brake >= 10%.
- Full-throttle sample: throttle >= 98%.
- Coasting sample: throttle < 5% and brake < 5%.
- Throttle/brake overlap sample: both >= 10%.
- High-slip sample: absolute Motion Ex slip ratio >= 0.15. This is a measured-analysis classification, not a universal unsafe threshold.

## Radio examples
- “Where am I losing time?”
- “Compare performance.”
- “Braking info.”
- “Traction info.”
- “Driving issues.”
- “Use this lap as reference.”
- “Compare with previous.”
- “Use best lap.”

## Verification
- pytest: 207 passed, 383 subtests passed.
- unittest: 199 tests passed.


---

## Archived source: `V0.9.6.1_REALTIME_RADIO_FIX_NOTES.md`

# V0.9.6.1 Real-time Radio Fix

Built directly from the supplied V0.9.6 working baseline.

## Changes
- Added high-rate per-wheel surface type to RaceState and an immediate physical off-track cue when 3+ wheels are on rock/gravel/mud/sand/grass/water. Official F1 corner-cutting/penalty events remain the authoritative fallback.
- Track-limit cue remains `Track limits.` and has highest radio scheduling rank.
- Reduced stale-message windows so old automatic warnings are dropped rather than spoken late (critical 2 s, strategy 5 s, information 3 s).
- Generic tyre/brake temperature radio answers are now short. Exact four-wheel values require an explicit detail request such as `tyre temp more detail` or `brake temp more detail`.
- Reduced repetitive automatic temperature calls: tyre auto-alert bands are 115/120 C with 8 C recovery hysteresis and 20 s family cooldown; brake auto-alert bands are 1100/1200 C with 75 C recovery hysteresis and 20 s family cooldown. These are deterministic project alert bands; F1 26 does not expose the MFD colour state itself in UDP, so the code does not claim to read the MFD colour directly.
- Automatic temperature speech is shorter: `Tyres hot.` / `Brakes hot.` plus the worst wheel/value.
- Updated stale startup/help banner to V0.9.6.1.

## Validation
- pytest: 213 passed, 383 subtests passed
- unittest: 205 tests, OK


---

## Archived source: `V0.9.6.2_INTERACTIVE_REPLAY_RADIO_FIX_NOTES.md`

# V0.9.6.2 Interactive Replay Radio Fix

Baseline: V0.9.6.1 Real-Time Radio Fix.

## Fixed

- Replay now replaces only the UDP telemetry source. The normal interactive radio stack is started during replay too: PTT HID polling, microphone capture, Faster-Whisper STT, deterministic voice intents, and TTS.
- `--replay ... --ptt ...` therefore accepts new live questions against the current state of the recorded session.
- Replay completion cleanly stops the PTT/STT/LLM/TTS workers.
- Piper playback interrupted by a PTT press is explicitly marked as an intentional interruption. A race where the button was released before PowerShell returned can no longer be misreported as `Piper failed: PowerShell exit 1`.
- Startup/help version updated to V0.9.6.2.

## Validation

- pytest: 213 passed, 383 subtests passed.
- unittest: 205 tests passed.

## Interactive replay command

```powershell
.\.venv\Scripts\python.exe -m src.main --replay ".\recordings\telemetry-20260916T150550Z-39c1860a.areplay" --ptt --ptt-backend hid --ptt-button 6 --mic-device 2 --no-llm
```

Expected startup after model initialization includes the same PTT/STT readiness messages as live mode. During replay, pressing PTT must produce `[PTT] PRESSED`, a WAV, `[STT] ...`, `[VOICE] Intent: ...`, and `[VOICE] Engineer: ...` while telemetry continues to come from the recording.


---

## Archived source: `V0.9.6_TELEMETRY_RECORDER_REPLAY_NOTES.md`

# V0.9.6 — Telemetry Recorder + Deterministic Replay

## Purpose
Record a real F1 26 UDP session once and replay the exact raw datagrams through the normal Race Engineer processing path later, without running the game.

## Recording

```powershell
.\.venv\Scripts\python.exe -m src.main --record-telemetry
```

Files are created in `recordings/` as `telemetry-<UTC>-<id>.areplay` plus a small JSON metadata sidecar.

Choose a file explicitly:

```powershell
.\.venv\Scripts\python.exe -m src.main --recording-path recordings\my-session.areplay
```

Recording is opt-in. It stores raw UDP payload bytes and monotonic relative arrival timing. It does not upload anything.

## Replay
Original timing:

```powershell
.\.venv\Scripts\python.exe -m src.main --replay recordings\my-session.areplay --no-tts
```

Twice real speed:

```powershell
.\.venv\Scripts\python.exe -m src.main --replay recordings\my-session.areplay --replay-speed 2 --no-tts
```

Fast deterministic analysis (no sleeps):

```powershell
.\.venv\Scripts\python.exe -m src.main --replay recordings\my-session.areplay --replay-fast --no-tts
```

Remove `--no-tts` when you specifically want to hear the automatic engineer calls during replay.

## Deterministic path
Replay calls the same `RaceStateReceiver.process_packet()` used by live UDP. Therefore header/body decoding, normalized race state, automatic safety, pit strategy, track limits, measured performance, measured driving intelligence and decision evidence use the production processing path.

## File integrity
Format magic: `ARERPL01`. Each record stores an elapsed timestamp, packet length and exact UDP payload. Reader rejects invalid magic, truncated records and non-monotonic timestamps.

## Testing
V0.9.6 adds round-trip byte/timing, corrupt-file rejection, opt-in behavior and normal-pipeline replay tests.


---

## Archived source: `V0.9.7.1_DISTANCE_ALIGNED_ANALYSIS_FIX_NOTES.md`

# V0.9.7.1 Distance-Aligned Analysis Fix

- Merges close secondary brake applications when no full-throttle recovery occurs between them.
- Matches braking/corner sections monotonically by physical track-distance anchor (minimum-speed point), not section ordinal.
- Refuses to compare sections farther than 250 m apart.
- Adds reference section IDs, anchor deltas, and matched-corner counts to JSON.
- Keeps measured 5 m telemetry-bin comparison and all existing Race Engineer features.


---

## Archived source: `V0.9.7_LAP_CORNER_ANALYSIS_NOTES.md`

# V0.9.7 — Lap & Corner Analysis Engine

First foundation release for the broader sim-racing telemetry platform.

## Added
- Deterministic post-session lap analysis from the existing measured-performance recorder.
- Best valid completed lap selection.
- Per-lap comparison against the best valid lap.
- Per measured braking/corner section: brake point, minimum speed, full-throttle point, exit speed, peak brake and wheel-slip deltas.
- JSON export suitable for the future desktop telemetry UI/session database.
- New CLI option: `--analysis-output FILE`.

## Rules
- Uses measured telemetry only.
- Keeps the existing 5 m distance-bin methodology for this first foundation release.
- Sections are numbered measured braking/corner sections, not claimed F1 turn numbers yet.
- No future prediction and no AI-generated driving conclusions.

## Example
`python -m src.main --replay recordings/session.areplay --replay-fast --no-tts --analysis-output analysis/session.json`


---

## Archived source: `V0.9.8.1_NON_OVERLAPPING_DRIVING_REGIONS_FIX_NOTES.md`

# V0.9.8.1 — Non-Overlapping Driving Regions Fix

- Replaces overlapping corner analysis zones with mutually exclusive distance regions.
- Region boundaries are the midpoints between consecutive matched corner anchors.
- First and last regions extend to the first and last common distance-aligned samples.
- Approach, braking-to-min-speed, and exit phases are clipped to their owning region.
- Adds `region_delta_sum_s` and `region_reconciliation_error_s` so the report proves that regional gains/losses reconcile to the final normalised delta.
- Keeps measured-association wording; no causal or predictive claims are introduced.


---

## Archived source: `V0.9.8.2_FULL_LAP_RECONCILIATION_STABLE_ZONES_NOTES.md`

# V0.9.8.2 — Full-Lap Reconciliation + Stable Corner Zones

- Replaces greedy corner matching with global monotonic dynamic-programming alignment.
- Extra/weak braking events may remain unmatched instead of stealing the next physical reference corner.
- Keeps physical driving regions mutually exclusive over the common measured distance.
- Reconciles the analysis to the official completed-lap delta with an explicit `boundary_timing_residual_s`.
- The residual is never assigned to a corner because the common-distance telemetry cannot justify where it occurred.
- Adds `full_lap_accounted_delta_s`, `full_lap_reconciliation_error_s`, and `common_distance_fully_partitioned`.
- No prediction and no causal claims.


---

## Archived source: `V0.9.8.3_TIME_TRIAL_SESSION_PRESERVATION_FIX_NOTES.md`

# V0.9.8.3 — Time Trial Session-Preservation Fix

Real F1 26 Time Trial regression recording exposed that results/menu packets can use `m_sessionUID == 0` after the active non-zero session. V0.9.8.2 interpreted UID 0 as a new session and reset RaceState plus MeasuredPerformanceRecorder, so the final analysis contained zero completed laps even though the laps had been captured.

V0.9.8.3 ignores zero-session-UID packets at the race-state layer. Non-zero session UID changes retain the existing session reset behavior. Grand Prix behavior is therefore preserved.

Regression coverage verifies that a UID 0 packet cannot replace an active Time Trial session.


---

## Archived source: `V0.9.8.4_AUTHORITATIVE_LAP_TIMING_FIX.md`

# V0.9.8.4 — Authoritative Lap Timing + Session History Reconciliation

## Fixed
- Completed lap number, lap time and validity are reconciled against F1's Session History packet (`m_lapHistoryData`).
- `m_lapTimeInMS` is the authoritative completed-lap time; sampled start/finish timing is no longer used as the official result.
- `m_lapValidBitFlags & 1` is the authoritative whole-lap validity flag. Invalid Time Trial laps can no longer be marked valid because the next lap started valid.
- Sector 1/2/3 times from Session History are attached to each analysed lap.
- The final completed Time Trial lap can be closed from Session History even when no following `currentLapNum` increment arrives before the results screen.
- Duplicate completion is prevented if Session History closes a lap before the next LapData transition.
- Session History reconciliation is change-detected so it does not redo expensive comparison work on every UDP packet.
- Grand Prix/live transition fallback remains intact when authoritative Session History is not yet available.

## Preserved Austria regression evidence
The recording's Session History reports game laps 1..8 with lap 5 and lap 7 invalid. Valid ranking is:
1. Lap 4 — 69.617 s
2. Lap 6 — 70.488 s
3. Lap 3 — 70.832 s
4. Lap 8 — 72.065 s
5. Lap 1 — 74.579 s
6. Lap 2 — 75.509 s

The game's displayed top-five excludes slower Lap 2, matching the results screen.


---

## Archived source: `V0.9.8.5_EVENT_AWARE_ANALYSIS_NOTES.md`

# V0.9.8.5 Event-Aware Analysis + Driving Metric Fixes

## What changed

- Added an EA-session-derived `event_context` profile (`time_trial`, `practice`, `qualifying`, `race`, `unknown`).
- Preserves raw telemetry, but gates derived strategy/decision metrics by event applicability.
- Time Trial disables fuel strategy, ERS energy-management strategy, tyre-wear strategy, race-position strategy, pit strategy, Safety Car strategy, red-flag strategy, weather strategy and damage strategy while retaining driving/corner/lap analysis.
- Practice/qualifying/race enable only the strategy families that make sense for those session classes; race-only systems such as pit/position/SC/red-flag strategy are race gated.
- Session rules now retained from EA PacketSessionData: formula, network-game flag, game mode, rule set, equal performance, low-fuel mode, damage/rate, corner cutting, parc ferme, Safety Car and red-flag settings.
- Setup-change advice is disabled when Parc Ferme is active.
- Damage strategy is disabled when damage is off.
- 2026 Active Aero / Overtake analysis is gated by the observed 2026-regulations state when available.

## Current issue fixes

### False micro-brake corner sections
Tiny pedal taps remain part of whole-lap brake totals but no longer become corner sections unless they show enough duration, speed reduction, or a sufficiently strong short application.

### Steering reversals always zero
Replaced adjacent-sample sign-crossing with a deadband/hysteresis state machine. Steering can pass naturally through zero and still register a meaningful left/right direction change.

## Important behavior

Raw `fuel_used_observed` and `ers_store_change_j` remain in lap records because they are observations. Their comparison deltas are omitted when the event profile says fuel/ERS strategy is not applicable (e.g. Time Trial).


---

## Archived source: `V0.9.8.6_EVENT_PROFILE_ENFORCEMENT_NOTES.md`

# V0.9.8.6 - Event-Profile Enforcement + Time Trial Rule Hardening

## Why this revision exists

V0.9.8.5 correctly identified the replay as Time Trial and fixed the measured-driving issues, but the applicability layer was only enforced inside measured lap analysis. Other consumers (automatic engineer, deterministic radio summaries, local-LLM context and pit strategy) could still see or act on race-only/resource values.

The V0.9.8.5 replay also exposed an EA-context edge case: `m_parcFermeRules` was true in Time Trial, causing `setup_change_advice=false`. EA's F1 25 car-setup help explicitly documents loading setups from Time Trial leaderboard entries, so Time Trial must not be treated as setup-locked merely because that generic Session-packet flag is set.

## EA sources used

- EA SPORTS F1 25 / 2026 Season Pack UDP Specification, current Version 11.0.
  - Session packet supplies session type and rule settings.
  - Time Trial is session type 18.
  - TimeTrialDataSet exposes equal-car-performance, custom-setup and validity fields for session best / personal best / rival data.
- EA Help: "How to set up a car for different tracks in EA SPORTS F1 25".
  - Documents loading another driver's setup from Time Trial leaderboards.
  - Also notes that Ranked/some F1 World events can use fixed setups, so setup availability should be event-aware rather than inferred from one generic rule bit.

## Event-profile enforcement

The same `EventContext` now controls all derived/automatic consumers, while raw decoded telemetry remains available for diagnostics and explicit inspection.

### Time Trial

Enabled:
- lap timing and validity
- brake/throttle/steering driving analysis
- corner analysis and valid-lap comparison
- slip/traction measurements
- tyre/brake temperature and tyre pressure
- 2026 Active Aero and Overtake analysis when `m_2026Regulations==1`
- setup-change advice

Disabled as strategy inputs/automatic race calls:
- fuel strategy / fuel-use comparison
- ERS energy-store strategy
- tyre-wear/stint strategy
- race-position and traffic-gap strategy
- race pit strategy / pit-lane strategy calls
- Safety Car / red-flag strategy
- dynamic-weather strategy
- damage strategy when EA reports damage disabled

Raw fuel/ERS/damage fields are still preserved; they are simply not interpreted as Time Trial strategy variables.

### Practice / Qualifying / Race

Resource and weather analysis are enabled where the session can actually use them. Race-only strategy remains race-only. Practice/qualifying retain pit-lane guidance and traffic-gap analysis without being misclassified as race-position strategy.

## Additional hardening

- Unknown session context preserves legacy behaviour until the EA Session packet arrives; once the session is known, strict event gating takes over.
- 2026 Active Aero / Overtake are enabled only when `m_2026Regulations` is explicitly true for a known session. Unknown does not become a fabricated 2026 state.
- Safety Car and red-flag strategy require both a race session and an explicitly enabled EA rule setting.
- Time Trial setup advice ignores the generic parc-ferme bit.
- Pit strategy returns `not_applicable` outside race sessions instead of creating a race-style recommendation from irrelevant telemetry.
- Local LLM reasoning context excludes non-applicable fuel, ERS, damage and pit-strategy inputs in Time Trial.
- Voice/manual summaries no longer describe Time Trial's fixed resource values as fuel/ERS strategy or fuel consumption.

## V0.9.8.5 replay verification retained

The supplied Time Trial analysis confirmed:
- 7 completed laps
- valid laps 3, 4 and 5
- best valid lap 3 at 70.229 s
- all laps now contain 7 physical braking sections (micro-brake false sections removed)
- steering reversals are no longer stuck at zero
- Time Trial comparison output omits fuel and ERS deltas
- full-lap reconciliation remains exact for the two valid comparison laps

## Tests

V0.9.8.6 adds regression coverage for:
- Time Trial setup advice despite parc-ferme flag
- no assumed 2026 systems when the regulation flag is unknown in a known session
- qualifying traffic-gap vs race-position distinction
- Time Trial automatic suppression of fuel/wear/damage strategy calls while retaining lap invalidation
- Time Trial voice resource handling
- Time Trial LLM context filtering
- race profile preservation of fuel/ERS/tyre/pit/damage strategy

Validated test result: **244 passed, 383 subtests passed**.


---

## Archived source: `V0.9.8_TIME_GAIN_LOSS_DRIVING_ANALYSIS_NOTES.md`

# V0.9.8 — Time Gain/Loss & Driving Analysis Engine

Adds deterministic distance-aligned timing and phase analysis on top of V0.9.7.1.

- Normalises elapsed-time delta at the first common lap-distance sample, preventing arbitrary lap-start timestamp offsets from polluting the trace.
- Emits a compact 25 m time-delta trace suitable for the future desktop telemetry UI while retaining 5 m analysis bins internally.
- Excludes the first/last 150 m when searching for strongest 100 m gain/loss windows to reduce start/finish wrap artefacts.
- Breaks every distance-matched braking region into approach, braking-to-minimum-speed, and exit phases.
- Measures time-delta change plus mean speed/throttle/brake differences in each phase.
- Ranks the largest measured loss regions.
- Explicitly labels results as measured associations, not causal claims.


---

## Archived source: `V0.9.9.0_LIVE_OVERLAY_FOUNDATION_NOTES.md`

# V0.9.9.0 Live Overlay Foundation

V0.9.9.0 adds the first optional Windows UI overlay on top of the locked
V0.9.8.6 deterministic/event-aware backend.

## Added

- `--overlay` launches a frameless, transparent, always-on-top PySide6 overlay.
- Compact right-side coaching card inspired by the requested reference layout.
- Live speed, gear, lap number, lap time, validity and event profile.
- 5-second scrolling throttle/brake trace.
- Live physical-distance delta trace against the selected measured reference lap.
- Current section selection based on the best/reference lap's measured braking sections.
- Four measured coaching rows: braking point, minimum speed, full-throttle timing and exit speed.
- Previous-section measured time-delta list using the existing reconciled driving analysis.
- Drag-to-move window and F8 click-through toggle.
- Overlay reads immutable snapshots only; UDP decoding and deterministic calculations remain in the existing backend.

## Deliberate V0.9.9.0 limits

- Coaching rows are from the latest completed valid comparison lap, while the top delta trace is live.
  Fully live corner-phase coaching is planned for a later V0.9.9.x step.
- Track corner names are not guessed; sections are shown as `SECTION N` until a verified track/corner map is added.
- PTT is temporarily incompatible with `--overlay` because the current PTT runtime also expects ownership of the Windows UI thread.
- PySide6 is an optional runtime dependency and is imported only when `--overlay` is used.

## Run

Install/update dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Live F1 telemetry:

```powershell
.\.venv\Scripts\python.exe -m src.main --overlay --no-tts
```

Replay at real speed for UI testing:

```powershell
.\.venv\Scripts\python.exe -m src.main --overlay --replay ".\recordings\telemetry-20260917T121801Z-940696c8.areplay" --replay-speed 1 --no-tts
```

Use `--overlay-click-through` to start with mouse input ignored. Press F8 while the
window has focus to toggle click-through; Escape closes the overlay.


---

## Archived source: `V0.9.9.10_CONTROL_HUB_UI_POLISH_NOTES.md`

# V0.9.9.10 – Control Hub + UI polish

This update adds four requested overlay improvements:

1. **Laptime History invalid laps in red**
   - Any invalid lap row is now rendered in red instead of muted gray, so invalid laps are immediately obvious.

2. **Fuel / tyre wear near-end warnings**
   - Fuel Remaining overlay now changes the main remaining-laps value and fuel mass to amber/red as fuel gets low.
   - Fuel history `REMAIN` values also warn as the remaining laps get low.
   - Tyre Wear overlay now changes the estimated laps remaining to amber/red as tyre life gets short.
   - Tyre wear history values and LIFE percentages now also warn visually.

3. **AI Coach dynamic height growth**
   - The AI Coach window now grows as the bottom comparison/history rows grow.
   - This removes the resize flicker seen when more than 5 history rows are visible.

4. **New main overlay: Control Center**
   - A new **Control Center** overlay is now the primary panel.
   - It contains grouped controls/status for:
     - TTS / PTT / STT / LLM / Replay / Pause / Click-through
     - Overlay launcher buttons for Coach, Driver Inputs, Replay Controls, Delta, Laptime,
       Tyre Wear, Fuel, Weather, Standings, Laptime History, and Available Tyre Sets.
   - The AI Coach remains available, but it is no longer the sole “main” panel.
   - Closing the AI Coach now hides that panel instead of exiting the whole app.
   - Exiting Race Engineer is now done from the Control Center.

## Validation
- `266 passed, 383 subtests passed`


---

## Archived source: `V0.9.9.11.1_CLICK_THROUGH_CONTROL_CENTER_HOTFIX_NOTES.md`

# V0.9.9.11.1 – Click-Through Control Center Hotfix

## Fix
V0.9.9.11 applied Qt mouse click-through to every overlay window, including the
Control Center. Once CT was enabled, the user could no longer click CT again,
close/hide overlays, pause, reopen windows, or exit from the UI.

V0.9.9.11.1 makes the Control Center a permanent interactive escape hatch:

- CT applies only to driving/data/replay overlays.
- Control Center is never made mouse-transparent.
- CT can always be turned back off from the Control Center.
- Starting with `--overlay-click-through` also keeps Control Center interactive.
- All other click-through behavior is unchanged.

## Validation
- 267 tests passed
- 383 subtests passed
- Added a regression test ensuring the Control Center is excluded from the
  click-through target list.


---

## Archived source: `V0.9.9.11.2_AI_COACH_CLOSE_HOTFIX_NOTES.md`

# V0.9.9.11.2 – AI Coach Close Button Hotfix

- Restores the local `×` close/hide button in the AI Coach header.
- Clicking it hides only the AI Coach window.
- The Control Center `C` button brings AI Coach back.
- The Control Center remains the only global exit point.
- CT behavior from V0.9.9.11.1 is unchanged.


---

## Archived source: `V0.9.9.11.3_CT_LAYOUT_LOCK_HOTFIX_NOTES.md`

# V0.9.9.11.3 – CT Layout Lock Hotfix

- CT no longer reopens hidden overlay windows.
- Visible racing/data overlays stay visible and become click-through/non-draggable.
- Hidden overlays stay hidden.
- The Control Center remains interactive as the permanent CT escape hatch.
- Reopening a hidden overlay while CT is active shows it in the locked/click-through state.
- No telemetry, analysis, coaching, or strategy math changed.


---

## Archived source: `V0.9.9.11_COACH_HEADER_SECTOR_CONTEXT_NOTES.md`

# V0.9.9.11 – Coach Header + Sector Context

- Removed duplicated global overlay/control buttons from the AI Coach header.
- Control Center remains the single place for global overlay launchers and runtime controls.
- AI Coach header now shows current track segment (`STRAIGHT N` / `TURN N`), current sector (`S1` / `S2` / `S3`), and live delta.
- Freed header width prevents STRAIGHT/TURN labels being clipped or cramped.
- Coach history-height growth from V0.9.9.10 remains in place.

Validation: `266 passed, 383 subtests passed`.


---

## Archived source: `V0.9.9.1_OVERLAY_VISUAL_REFERENCE_REFINEMENT_NOTES.md`

# V0.9.9.1 - Overlay Visual + Reference-Lap Refinement

V0.9.9.1 refines the first working PySide6 overlay after the Windows rendering check of V0.9.9.0.

## Visual changes

- Reduced the overlay width/height and tightened spacing to better match the compact coaching-card reference.
- Added three automatic visual states instead of permanently rendering empty coaching rows:
  - **SETTING REFERENCE LAP** before the first valid reference exists.
  - **REFERENCE READY** once a valid best lap exists but no second valid comparison lap has completed yet.
  - **FULL COACHING** once measured comparison data exists.
- Removed the permanent drag/F8/Esc help footer to reclaim screen space.
- Reduced background opacity slightly so more of the game remains visible beneath the overlay.
- Kept the live delta number in the upper-right and made the delta trace denser.
- Tightened measured-coaching rows and status pills.
- Rebuilt previous-section rows with proper left/right alignment and hides unused rows instead of printing `--` placeholders.
- Kept and cleaned the live five-second throttle/brake trace.
- Tightened the bottom speed/gear/lap strip and highlights invalid current laps.

## Reference correctness fix

The overlay's `best` reference mode no longer falls back to the most recent invalid lap when no valid timed lap exists.  It now waits for the first valid timed lap, matching the authoritative session-history analysis behavior.  Manual/previous reference modes retain their explicit semantics.

## Deliberate limitation

Measured coaching rows still describe the latest completed valid lap versus the selected reference lap.  The delta trace is live.  Fully live per-corner coaching is a later overlay iteration so that V0.9.9.1 remains a visual/reference-state refinement rather than changing the validated deterministic analysis model.

## Validation

- Python syntax compilation passed for the overlay modules and main entry point.
- Full regression suite: **248 tests passed + 383 subtests passed**.
- GUI rendering must still be visually checked on Windows because PySide6 is not installed in the packaging environment.


---

## Archived source: `V0.9.9.2_MULTI_PANEL_REALTIME_COACH_NOTES.md`

# V0.9.9.2 - Multi-Panel Overlay + Real-Time Coaching

## Scope

This version refactors the V0.9.9.1 single-card overlay into three independent PySide6 windows while preserving the validated telemetry and deterministic decision backend.

### Independent windows

1. **Real-Time Coach**
   - current physical section
   - live lap delta to the selected valid reference
   - delta trace
   - braking point
   - minimum speed
   - full-throttle timing
   - exit speed
   - previous-section measured time deltas from the current lap
   - Pause/Resume and Close controls

2. **Driver Inputs**
   - scrolling throttle trace
   - scrolling brake trace

3. **Telemetry Strip**
   - speed
   - gear
   - current lap number / time / invalid state

All three windows are frameless, translucent, always-on-top and independently draggable.

## Real-time coaching semantics

Real-time coaching never predicts a future corner value. Values are unlocked only after the relevant measurement exists:

- **Braking point**: becomes available when braking begins. If the car has already passed the reference brake point without braking, the UI reports measured lateness-so-far.
- **Minimum speed**: becomes available after the car reaches/passes the reference minimum-speed location.
- **Throttle timing**: becomes available when full throttle is reached. If the reference full-throttle point has already been passed, the UI reports measured lateness-so-far.
- **Exit speed**: becomes available after the car reaches the reference section exit location.
- **Previous-section delta**: is derived from the current-vs-reference aligned timing trace as soon as a physical section region is complete.

The best-reference mode continues to require a completed **valid** timed lap. Invalid laps cannot bootstrap the coach reference.

## Pause behavior

- **Replay**: the Pause button freezes both UI updates and replay packet timing. Resume continues from the same replay point without a catch-up burst.
- **Live F1**: the Pause button freezes only the overlay display. UDP telemetry continues to be processed in the background so packet handling remains healthy.

Keyboard shortcuts while an overlay panel has focus:

- `P` or `Space`: Pause/Resume
- `Esc`: Close all overlay windows
- `F8`: Toggle click-through

## Tests

Regression result for this release candidate:

- **251 tests passed**
- **383 subtests passed**


---

## Archived source: `V0.9.9.3_REPLAY_CONTROLS_TURN_COACH_NOTES.md`

# V0.9.9.3 - Replay Controls + Turn Coach UI

## UI changes

- Adds a fourth independent **Replay Controls** window whenever `--overlay` is used with `--replay`.
- Replay controls provide:
  - Play / pause.
  - Packet-position slider with deterministic seek.
  - Independent replay-range start and end controls.
  - Live speed multiplier control from 0.25x to 4.00x.
  - Recorded timestamp timing or uniform/smoothed packet timing.
- Seeking rebuilds Race Engineer state deterministically from the beginning of the recording up to the selected packet before playback continues.
- Seek rebuilds suppress historical TTS/radio side effects.
- Reaching the end of the selected range pauses playback; Resume restarts from the selected range start.

## Coach wording

- User-visible `SECTION` labels are now `TURN`.
- Previous coaching history now reads `PREVIOUS TURNS` and `Turn N`.
- The current turn index is still the measured braking/coaching-zone index. It is not yet an official FIA circuit corner number/name; official track-corner mapping will be a separate feature.

## Live delta graph

The coach's top graph is now explicitly labelled **LIVE DELTA TO REFERENCE**.

- Dashed centre line: `0.000 s` relative to the reference lap at the same physical distance.
- Green / `GAIN (-)`: current lap is ahead of the reference.
- Red / `LOSS (+)`: current lap is behind the reference.
- The number in the coach header is the latest raw live delta.
- The plotted line receives a small display-only moving average to reduce 5 m sample/bin jitter. No deterministic coaching calculation is smoothed or altered.

## Reference validity

Automatic `best` reference selection continues to use only completed valid timed laps. In the Jeddah test replay, Laps 1 and 2 are marked invalid by EA Session History, so Lap 3 is the first eligible automatic reference.

## Regression

- 254 tests passed.
- 383 subtests passed.


---

## Archived source: `V0.9.9.4_SMOOTH_SEEK_MODULAR_OVERLAYS_NOTES.md`

# V0.9.9.4 - Smooth Replay Seek + Modular Overlay Controls

## Replay seek refinement

- Position slider now stays at the requested packet while a seek is being reconstructed instead of snapping back to the old playback position.
- Normal overlays freeze on the last complete frame during deterministic seek reconstruction, so they no longer visibly replay from Lap 1 while seeking.
- New seek requests supersede an in-progress obsolete seek quickly.
- Seek reconstruction runs in silent/fast mode and skips automatic engineer/radio evaluation; deterministic telemetry, lap history and measured-performance state are still rebuilt before playback resumes.

## Live delta graph

- The AI Coach graph now shows only the rolling **last 15 seconds** of live delta history.
- It is labelled `LIVE DELTA • LAST 15 S • REF Lx`.
- Header delta and all coaching calculations remain raw measured values; only the plotted line has display smoothing.

## Overlay layout

- Driver Inputs and Speed/Gear/Lap are merged into one independent **Driver Inputs** window.
- Driver Inputs has its own X button; it hides only that overlay.
- Replay Controls X hides only Replay Controls.
- Only the AI Coach X exits the Race Engineer application.
- AI Coach adds a minimize/collapse button.
- AI Coach adds `D` and `R` buttons to restore/bring forward the Driver Inputs and Replay Controls windows after they are hidden.
- Replay button is hidden in live-game mode where no replay controller exists.

## Reference validity

Automatic best reference selection remains valid-lap-only. Invalid EA Session History laps cannot become the automatic coaching reference.

## Regression

- 256 tests passed.
- 383 subtests passed.


---

## Archived source: `V0.9.9.5_DELTA_LAPTIME_ERS_SEEK_NOTES.md`

# V0.9.9.5 - Delta/Laptime Overlays + ERS Input Analysis

## Added overlay windows

- **Speed Delta**: compact live delta to the selected valid reference lap.
- **Live Laptime**: current lap time, current live delta, S1/S2 measured deltas when available, and reference lap/time.
- Both are independent, draggable, always-on-top windows.
- Their X buttons hide only that overlay. Only the AI Coach X exits the application.
- AI Coach adds `Δ` and `L` restore buttons alongside `D` and replay `R`.

## Driver Inputs

- Throttle and brake remain in the existing scrolling input trace.
- Added checkable `T`, `B`, and `ERS` controls.
- `T` hides/shows throttle; `B` hides/shows brake.
- `ERS` hides/shows the ERS battery panel.
- The panel dynamically shrinks when graph groups are hidden.
- ERS store is displayed in MJ from EA `m_ersStoreEnergy`; recent slope is labelled CHARGING / DISCHARGING / STEADY.
- In Time Trial this is expected to be essentially flat because the game holds ERS fixed there; it becomes analytically useful in Practice/Qualifying/Race.

## Replay seek responsiveness

- Large seek reconstruction stays deterministic.
- The replay worker now yields the Python GIL regularly while rebuilding so Qt remains responsive.
- Deterministic replay checkpoints are cached at lap transitions.
- A later seek restores the nearest earlier cached lap checkpoint, then replays only the remainder to the requested packet.
- The first seek beyond all existing checkpoints can still take time because the required history must be reconstructed once.
- Existing behavior is retained: overlays freeze on the last complete frame while seek reconstruction is in progress and the position slider remains at the requested target.

## Validation

- Existing deterministic backend behavior remains unchanged.
- Added regression coverage for ERS/sector fields exposed to overlay windows and replay checkpoint round-trip restore.
- Full suite: **258 tests passed + 383 subtests passed**.


---

## Archived source: `V0.9.9.6_SMODE_ADAPTIVE_DELTA_NOTES.md`

# V0.9.9.6 - S-Mode Timing + Adaptive Delta Visuals

V0.9.9.6 refines the Time Trial overlays toward the supplied reference UI while keeping the validated deterministic backend unchanged.

## Real-time AI Coach

- Adds **S Mode Enable** as a fifth coaching metric when 2026 Active Aero analysis is applicable.
- The delay is measured from the first sampled point where EA explicitly reports Active Aero available to the first sampled point where the car is in `Straight mode`.
- Up to 5 m is displayed as `on spot`; a larger measured delay is displayed as `Xm late`.
- The value is measured-only. No future activation point is predicted.

## Live Laptime

- `S1`, `S2`, and `S3` text remains neutral instead of changing text colour.
- Thin sector bars carry the completed-sector red/green result.
- Adds track-length adaptive local-delta dots, roughly one per 150 m with sensible min/max bounds.
- Each completed dot represents the time gained/lost inside that physical slice of track, not cumulative lap delta.
- Future/unreached dots remain neutral, so the strip fills across the lap.

## Delta overlay

- Adds a centred moving progress marker under the numeric delta.
- Negative delta moves to the gain side and displays green.
- Positive delta moves to the loss side and displays red.
- The displayed value remains the existing deterministic live time delta to the valid reference lap.

## Validation

- Full suite: **260 tests passed + 383 subtests passed**.


---

## Archived source: `V0.9.9.7_TRACK_STRUCTURE_COMPACT_GRID_NOTES.md`

# V0.9.9.7 — Track-Structure Delta + Compact Turn Grid

## Scope

This release is an overlay-only refinement on top of the validated deterministic/event-aware backend. It does not change lap validity, best-valid-lap selection, corner matching, or race-engineer strategy logic.

## Changes

### Live Laptime markers

The old approximately-150-m distance bins are removed. The marker row is now built from the valid reference lap's measured driving structure:

- straight before a coached turn
- coached turn from braking start through measured exit
- straight to the next coached turn
- repeated across the lap

The number of markers therefore changes with the number and spacing of detected coached turns on the circuit. Each marker reports the local change in aligned time delta across that one physical region. A marker is only populated after that region has been completed on the current lap.

Each structure marker is also assigned to S1/S2/S3 from the reference lap's measured sector times. The UI adds a small visual gap at sector transitions. Turn markers are slightly larger than straight markers.

### Delta overlay

The Delta window and numeric delta font remain unchanged. The centred gain/loss bar now uses nearly all available horizontal width inside the existing window.

### Replay Controls

Removed the visible `Replay timing` selector and the two radio controls. Replay continues to use its configured/default timing behavior internally.

### Previous-turn history

The old vertical five-row history is replaced by a compact four-column grid:

`Turn 1 | +0.123s | Turn 2 | -0.042s`

then the next two turns on the following row. This reduces wasted vertical space and supports more completed coached turns.

## Validation

`262 tests passed, 383 subtests passed`.

PySide6 is not installed in the packaging environment, so final visual rendering is validated on the user's Windows machine.


---

## Archived source: `V0.9.9.8_STRAIGHT_TURN_PERFORMANCE_NOTES.md`

# V0.9.9.8 - Straight + Turn Performance

## Goal
Extend the live deterministic performance analysis from coached turns to straights as well, so every physical track-structure segment can show where time is gained or lost.

## Changes
- The active coach header now switches between `STRAIGHT N` and `TURN N`.
- Straights use deterministic real-time metrics: `Straight Time`, `Entry Speed`, `Avg Speed`, and `Top Speed`.
- `S Mode Enable` is shown with straight coaching when 2026 Active Aero analysis applies.
- Previous-lap/current-lap history is now a mixed segment history (`Straight N` and `Turn N`) rather than turns only.
- Live Laptime structure markers calculate local delta for both straights and turns.
- The currently developing straight/turn marker can colour once enough of the segment has been measured; it no longer has to remain neutral until the whole segment is finished.
- Existing turn coaching remains unchanged: braking point, minimum speed, throttle timing, and exit speed.
- Increased history capacity to retain more mixed track segments in the compact 4-column grid.

## Deterministic interpretation
All straight metrics are measured against the same valid reference lap at the same physical track distance. No future value is predicted and no causal claim is made from the metric alone.

## Regression
- 264 tests passed
- 383 subtests passed


---

## Archived source: `V0.9.9.9.1_STARTUP_HOTFIX_NOTES.md`

# V0.9.9.9.1 Strategy Overlay Startup Hotfix

## Fix

- Fixed overlay startup crash in `CoachOverlayWindow.__init__`.
- `extra` is now initialized to `0` before the initial `setFixedSize(...)` call.
- Preserves all V0.9.9.9 strategy/session overlay features unchanged.

## Validation

- Python compile check passed.
- Full regression suite passed: **266 tests + 383 subtests**.

## Root cause

V0.9.9.9 added launcher-dependent height adjustments. The constructor used `self.NO_REFERENCE_HEIGHT + extra` before `extra` had been assigned. Runtime updates correctly computed `extra`, but the initial constructor path did not.


---

## Archived source: `V0.9.9.9_STRATEGY_SESSION_OVERLAY_PACK_NOTES.md`

# V0.9.9.9 Strategy + Session Overlay Pack

V0.9.9.9 extends the modular PySide6 overlay system with six data windows based on the normalized EA UDP state already maintained by the Race Engineer.

## New overlays

- **Tyre Wear** — FL/FR/RL/RR wear, current-stint history, and a measured laps-remaining estimate based only on observed wear-per-lap deltas.
- **Fuel Calculator** — EA `m_fuelRemainingLaps`, current raw fuel amount, and recent measured per-lap fuel usage. No Time Trial fuel strategy is inferred.
- **Weather Forecast** — EA forecast offsets, condition, rain percentage, track temperature and air temperature.
- **Standings** — five-car viewport around the player using normalized current position/gap/compound data.
- **Laptime History** — recent measured laps with best-valid reference delta and S1/S2/S3 values.
- **Available Tyre Sets** — available/fitted sets from EA `PacketTyreSetsData`, including compound, wear, recommended session, life, usable life and lap delta.

## Overlay launcher

The AI Coach header now has a compact `▦` launcher. Opening it exposes buttons for the six strategy/session overlays. These windows are hidden by default to keep the racing view uncluttered. Their own `X` buttons hide only that overlay; the AI Coach `X` remains the application exit.

## Session awareness

The new windows use the existing event-profile metrics. Time Trial keeps raw values available for diagnostics but marks fuel, tyre-wear, weather, standings and tyre-set strategy views not applicable rather than pretending static TT values are race strategy inputs.

## Deterministic history support

`MeasuredLapFact` now also retains end-of-lap fuel, tyre wear and fitted tyre set index. This allows the UI to show recent measured stint history without reconstructing or predicting data that EA did not provide.

## Validation

Regression suite: **266 tests passed + 383 subtests passed**.


---

## Archived source: `V1.0.0_LOCAL_RELEASE_CANDIDATE_NOTES.md`

# V1.0.0 — Local Release Candidate

This release consolidates the local/offline Race Engineer + Performance Coach roadmap into one codebase.

## Added in V1.0.0

- Richer lap-end summary: current lap, reference delta, previous-valid-lap delta, biggest measured opportunity, optional second opportunity and observed potential.
- Observed corner-window potential metrics in addition to authoritative best-valid-sector potential.
- Rich HTML coach report with technique-consistency table and embedded speed/brake/throttle/gear traces when raw samples are available.
- Portable reference package API with metadata, export/import and compatibility validation.
- Local session-library API with names/tags/favorites/archive support and report attachment discovery.
- Built-in telemetry/latency health helpers and diagnostic bundle export.
- Windows `build_exe.ps1` packaging script and first-run guide.
- Regression tests for all new V1.0.0 local-release components.

## Existing integrated coaching retained

- deterministic corner measurement and diagnosis
- loss/deadband guards
- coaching priority + multi-lap memory
- PRE / POST / LAP / POS / RACE switches
- current-speed/distance timed pre-corner reminders
- safe post-corner coaching
- race-context suppression and message arbitration
- potential-lap summary
- explainable technique metrics
- PTT performance questions
- JSON/HTML reports
- driver history
- straight-line analysis
- world-position racing-line comparison
- learned track landmarks

## Scope boundary

This is the complete **local/offline** release candidate. The roadmap's P3 external ecosystem items (cloud accounts/backups, community leaderboards/reference hosting, team sharing, mobile/VR products, and adapters for sims whose telemetry SDKs are not part of this repository) remain external projects rather than being falsely marked complete. The Windows EXE build script is supplied; code signing and installer signing require a Windows build/signing environment and certificate.


---

## Archived source: `V1.0.1.1_MAP_COACH_LABEL_HOTFIX_NOTES.md`

# V1.0.1.1 — Map + Coach Label Hotfix

## Fixed
- Control Center coaching buttons no longer collapse to generic `Enabled` / `Disabled`; they remain identifiable as `POST ON/OFF`, `PRE ON/OFF`, `LAP ON/OFF`, `POS ON/OFF`, and `RACE ON/OFF`.
- Native F1 Dash TRACK MAP now renders `T1`, `T2`, … labels at the active reference lap's detected corner apex/anchor positions.
- LAN/browser TRACK MAP receives and renders the same turn labels for native/LAN parity.
- Turn numbering deliberately uses the same detected corner IDs consumed by PRE/POST coaching, so map `T3` matches spoken `Turn 3`.

## Validation
- New map/label tests added.
- Full suite: 559 passed, 383 subtests passed.


---

## Archived source: `V1.0.1.2_EXTERNAL_REFERENCE_PERSISTENT_MAP_TURNS_NOTES.md`

# V1.0.1.2 — External Reference Coaching + Persistent Map Turns

## External reference from lap 1
- A selected external/rival reference now seeds PRE-corner guidance immediately.
- First-lap PRE guidance uses only measured reference targets (brake distance, apex gear, minimum speed); it does not claim the driver already made a mistake.
- POST coaching still compares the current driven corner with the reference and can speak from the first suitable corner on lap 1.
- After valid driver laps exist, measured diagnoses replace generic reference guidance corner-by-corner.

## Damage-aware race coaching
- Significant damage still blocks coaching immediately after the damage event.
- Moderate aero damage that remains unchanged for 8 seconds no longer silences the whole race.
- While driving with stable damage, pure speed-outcome coaching that may be distorted by aero loss is suppressed; input/technique coaching can continue when the live context is otherwise safe.
- Damaged completed laps remain excluded from clean reference/history learning.

## Persistent map turn IDs
- `maps/track_maps_cache.json` is upgraded to schema version 2.
- Each learned track entry stores both telemetry geometry and detected `T1`, `T2`, ... lap-distance anchors.
- Version-1 point-only caches are loaded without data loss and are upgraded when written.
- Once turn IDs have been learned from an active reference, later runs can draw the labels immediately from the map cache even if no reference is currently active.

## Validation
- Targeted external-reference/map/damage tests: 23 passed.
- Full regression: 563 passed, 383 subtests passed.


---

## Archived source: `V1.0.1.3_PRE_COACH_RADIO_PRIORITY_HOTFIX_NOTES.md`

# V1.0.1.3 — PRE-Coach Radio Priority Hotfix

## Changes
- PRE-corner coaching is now the highest-priority routine radio message.
- PRE is evaluated before pending LAP and POS coaching, so the approaching turn always gets first use of a safe coaching window.
- A PRE call can interrupt an in-progress lap summary, ordinary POST/POS coaching, strategy/information chatter, and routine assists.
- Driver-requested radio answers, instant track-limit cues, and CRITICAL safety messages remain higher priority than PRE.
- Stable moderate aero-damage coaching cooldown reduced from 8 seconds to 3 seconds.
- Damage-sensitive speed-outcome advice remains suppressed while significant aero damage is present.
- No native dashboard or LAN dashboard visual changes.


---

## Archived source: `V1.0.1.4.1_MULTI_MONITOR_STARTUP_HOTFIX_NOTES.md`

# V1.0.1.4.1 — Multi-Monitor Startup Hotfix

Fixes a startup crash introduced by V1.0.1.4.

- Imports `QSize` in `src/overlay/window.py` before Control Center geometry sizing uses it.
- Adds a regression test ensuring the geometry dependency remains imported.
- Keeps the V1.0.1.4 multi-monitor geometry changes unchanged.


---

## Archived source: `V1.0.1.4_MULTI_MONITOR_GEOMETRY_STABILITY_HOTFIX_NOTES.md`

# V1.0.1.4 — Multi-Monitor Geometry Stability Hotfix

- Removed conflicting fixed-size geometry constraints from Control Center.
- Control Center now uses a logical minimum/baseline and layout-driven final size.
- Added active-screen clamping for frameless overlay windows after show and drag.
- Default AI Coach placement uses the Control Center's actual runtime height.
- Prevents repeated QWindowsWindow::setGeometry / MINMAXINFO conflicts seen when moving between monitors with different DPI scaling.
- Retains V1.0.1.3 PRE-coach radio priority and 3-second stable-damage cooldown.


---

## Archived source: `V1.0.1.5_COACH_FIRST_RACE_RADIO_NOTES.md`

# V1.0.1.5 — Coach-First Race Radio

## Changes

- Added Control Center `ENGR` runtime toggle.
- `ENGR OFF` suppresses automatic race-engineer TTS (lights-out, collision, warnings, S Mode, fastest-lap, overtake, finish/result, etc.).
- PRE/POST/LAP/POS coaching and driver-requested PTT answers remain active with `ENGR OFF`.
- AutomaticEngineer still evaluates silently while muted, preventing stale transition bursts when re-enabled.
- External-reference PRE coverage expands to every reference turn from lap 1, overriding old low saved PRE quotas.
- Race POST coverage allows every deterministically eligible slower corner instead of one call per lap.
- Race same-issue cooldown is disabled so a still-slow corner can be coached again on the next lap.
- Race post-corner priority threshold is zeroed only after CornerAnalysis eligibility/deadband has passed; no raw/noisy difference bypasses the deterministic eligibility gate.
- Existing 3-second stable-damage recovery and PRE radio priority are retained.

## Validation

- Targeted coach/radio tests: 11 passed.
- Full regression: 574 passed, 383 subtests passed.
- `src/dashboard_server.py` unchanged from V1.0.1.4.1.
- `src/overlay/window.py` intentionally changed only to expose the ENGR control.


---

## Archived source: `V1.0.1.6_REFERENCE_TURN_COACHING_CONSISTENCY_NOTES.md`

# V1.0.1.6 — Reference-Turn Coaching Consistency

- External reference is now the authoritative turn-number source for map, PRE, POST, lap summaries, and coaching memory.
- Turn labels are sorted by lap distance and persisted sequentially, preventing T9-style live detector IDs from disagreeing with a T1-T6 map.
- Race PRE uses a coach-first safety gate: close traffic and invalid-lap state no longer silently erase a reference reminder; stale data, pit/flag states, braking/cornering, and active radio ownership still block it.
- External-reference race PRE delivery window expands to 1.5-8.0 s before the reference brake point so transient blockers are less likely to make a turn disappear.
- Race POST now has a deterministic fallback for a slower reference turn when brake-zone matching cannot produce a specific diagnosis. It uses measured elapsed-time loss across the reference turn window and, when available, minimum-speed deficit.
- Existing ENGR switch, 3 s stable-damage recovery, and PRE-first priority are retained.


---

## Archived source: `V1.0.1_LOCAL_POLISH_ROBUSTNESS_NOTES.md`

# V1.0.1 — Local Polish + Robustness

This release narrows the product to the agreed local/personal scope and hardens the integrated Race Engineer + Performance Coach rather than adding cloud/ecosystem features.

## Runtime coaching polish

- Performance Coach mode now keeps both PRE and POST coaching enabled when their user switches are enabled.
- Race coaching suppresses technique calls when a car is close behind as well as close ahead.
- Live coaching now rejects stale telemetry and stale lap-state packets using the race-state freshness timestamps.
- PRE-corner TTS reminders have a short 1.5 s stale window so a delayed reminder cannot be spoken after its useful moment.
- PRE, LAP-summary and POS coaching messages use replaceable queue families so obsolete queued coaching is superseded instead of played late.

## Reference/data-quality hardening

The measured-performance recorder now latches factual compromise flags across the whole lap:

- pit phase
- close traffic ahead/behind
- Safety Car / VSC / yellow or red marshal-zone conditions
- significant aero/engine damage

These flags are exported with the measured lap and are consumed by the existing `lap_quality()` gate, preventing compromised laps from becoming clean coaching/reference material.

## Local usability

New command-line helpers:

```powershell
.\.venv\Scripts\python.exe -m src.main --show-coaching-settings
.\.venv\Scripts\python.exe -m src.main --reset-coaching-settings
.\.venv\Scripts\python.exe -m src.main --diagnostic-bundle
```

The diagnostic bundle remains fully local.

## Validation

- Full suite: **556 passed, 383 subtests passed**
- New local-polish tests cover mode behavior, stale-data gates, front/rear traffic suppression, coaching queue supersession/staleness, and compromised-lap reference flags.
- Native F1 dash/overlay UI and LAN dashboard source files remain byte-for-byte unchanged in this release.


---

## Archived source: `V1.0.2.0_CONTINUOUS_DISTANCE_PERFORMANCE_NOTES.md`

# V1.0.2.0 — Continuous Distance Performance + Per-Track Map Storage

## 1. Start-line-gated first map capture

A new circuit no longer begins drawing from the car's position when the application is opened mid-lap. The learner waits for a credible start/finish event, then records exactly one complete lap. A valid start is either an initial near-zero lap clock at the line, a normal lap-number increment after the car was near the end of the circuit, or a credible high-distance-to-low-distance wrap. Partial mid-lap traces are not exposed as learned maps. The LAN/browser map uses the same behavior.

## 2. One file per track

New learned maps are stored as `maps/tracks/<TRACK>.json` with schema version 3. A file contains the track name, learned world-position points and persistent physical turn markers. Existing schema-v1/v2 combined `track_maps_cache.json` data is still readable and is materialized into separate per-track files when imported. New captures do not write the combined cache.

## 3. Continuous reference performance pipeline

The deterministic coaching data path is now:

`REFERENCE LAP -> distance interpolation -> full-track local gain/loss -> physical T1...Tn -> per-turn aggregation -> deterministic diagnosis -> PRE/POST coach`

`src/distance_performance.py` interpolates current and reference lap-clock values on a common distance grid. Positive delta means the current lap is slower. Local delta and rolling-window delta preserve where time was gained or lost along the whole circuit instead of comparing only isolated corner anchors.

Physical turn boundaries are taken from measured reference sections and canonicalized by lap order to T1...Tn. Coaching attribution starts before the physical brake-zone boundary so measured loss caused by early braking is not discarded; the actual physical turn start/end remains separately available as `physical_net_loss_s`. ENTRY/MID/EXIT attribution is based on approach-to-brake, brake-to-apex, and apex-to-exit respectively, preserving the existing deterministic diagnosis semantics.

`src/coaching_analysis.py` attaches measured diagnoses to these turn aggregates. `src/coaching_live.py` uses the canonical physical turn numbering for PRE and POST coaching, and `src/measured_performance.py` exposes both the full distance model and turn-performance data for downstream analysis/UI work.

## Validation

Full automated suite at release packaging: **582 passed, 383 subtests passed**.


---

## Archived source: `V1.0.2.1_MAP_REPLAY_PHYSICAL_TURNS_NOTES.md`

# V1.0.2.1 — Map Trace + Replay + Physical Turn Hotfix

This hotfix is based on V1.0.2.0 and addresses the three issues observed on the Shanghai replay.

## 1. First-map geometry is now distance-binned and S/F validated

The native and LAN map views no longer learn circuit geometry from the 60 Hz UI snapshot. F1 packet families are asynchronous, so near start/finish the lap-distance packet can move to the next lap while the most recent motion packet still contains an older world position. That produced the long diagonal/chord visible in the Shanghai map.

Map learning now consumes the `MeasuredPerformanceRecorder` 5 m distance bins, rejects isolated impossible world-position jumps, requires a start-anchored trace, and only persists a circuit after a complete S/F-to-S/F lap with spatial closure validation. A malformed dedicated track file is ignored as one atomic object, including any stale turn labels, and is replaced only after a new valid full lap is learned.

## 2. Per-track map schema V4

Each circuit remains stored independently at:

`maps/tracks/<TRACK>.json`

Schema V4 stores:

- measured world X/Z points;
- the matching game lap-distance axis (`point_distances_m`);
- game track length;
- geometry-derived physical T1...Tn markers.

Native and LAN dashboards interpolate car/reference/nearby/turn markers on this lap-distance axis instead of assuming geometric-polyline percentage equals game lap-distance percentage.

## 3. Replay selector first-click behavior

The Control Center can now enter Replay directly. If the replay list is visible but the user has not manually changed the combo yet, clicking Live/Replay first loads the currently visible recording and then switches to Replay. Once already in Replay, selecting another recording continues to hot-load that recording as before.

## 4. Physical turn numbering

V1.0.2.0 map labels were ultimately sourced from detected reference braking sections. That is not the same thing as physical circuit corners and can compress a circuit such as Shanghai into fewer labels.

V1.0.2.1 makes measured circuit curvature the T-number authority. The known physical corner count is used only to split/merge curvature events into T1...Tn; driver-specific braking sections are then attached to the nearest physical turn for diagnosis. They no longer create or renumber turns.

The continuous performance pipeline therefore remains:

REFERENCE LAP -> continuous distance performance -> full-track local gain/loss -> physical T1...Tn -> per-turn aggregation -> deterministic diagnosis -> PRE/POST coach.

Old/external reference files that do not contain world X/Z geometry retain the old braking-section ordering only as an explicit compatibility fallback.


---

## Archived source: `V1.0.2.2_LIVE_MAP_PLAYER_POINTER_HOTFIX_NOTES.md`

# V1.0.2.2 — Live Map Player Pointer Hotfix

## Symptom

After the Shanghai circuit geometry had been learned correctly, the yellow `YOU` marker could remain near the start/finish point even while the replay footer showed lap distance advancing. The same presentation path was used by the native F1 Dash and the LAN dashboard.

## Cause

The player marker was primarily reconstructed from `lap_distance_m` against the stored map distance axis (or from the last accepted learning-trace point). F1 UDP packet families are asynchronous, and replay seeks/lap transitions can temporarily leave those presentation inputs out of phase. The actual motion packet already contains the player's current world X/Z coordinate in exactly the same coordinate system from which the circuit map is learned.

## Fix

- `YOU` now uses the current player `world_position_x/world_position_z` as the primary map position.
- The stored distance axis remains the fallback when motion position is unavailable.
- First-lap learning also uses the live motion position for the yellow pointer rather than relying only on the final accepted trace sample.
- LAN/web map rendering follows the same authority order, so native and remote dashboards remain consistent.
- Reference and nearby-car markers continue to use deterministic lap-distance placement because their world coordinates are not supplied through the same snapshot interface.

No coaching, reference-lap, physical-turn, replay-selection, strategy, or telemetry-decision logic was changed.


---

## Archived source: `V1.0.3.0_FULL_PERFORMANCE_COACHING_PIPELINE_NOTES.md`

# V1.0.3.0 — Full Performance Coaching Pipeline

V1.0.3.0 integrates the complete deterministic coaching chain on top of the
V1.0.2.2 map and moving-player-pointer fixes:

REFERENCE LAP
    -> continuous distance-based performance model
    -> full-track local gain/loss map
    -> physical T1...Tn boundaries
    -> loss assigned to turns and straights
    -> deterministic diagnosis
    -> PRE coach
    -> drive corner
    -> POST coach

## 1. One physical turn authority

`src/track_geometry.py` no longer labels the N strongest individual curvature
samples. That method could place several labels on one hairpin or long complex.
The new geometry model:

- resamples the measured X/Z circuit trace on the lap-distance axis;
- builds a smoothed signed-curvature trace;
- finds sustained curvature regions instead of isolated peaks;
- rejects small geometric wiggles;
- splits broad complexes only when needed to reach the circuit's physical turn
  count;
- stores geometry-derived `start_m`, `apex_m`, `end_m`, direction, and curvature
  score for every T1...Tn marker.

Brake zones do not create or renumber physical turns. Measured reference brake
and turn-in events are attached to the physical geometry afterwards.

## 2. Track-map schema V5

Each track remains in its own `maps/tracks/<TRACK>.json` file. Schema V5 adds
persistent physical turn boundaries to the existing measured map geometry and
lap-distance axis.

Pre-V5 maps remain readable. Their old turn labels are treated as stale and are
re-derived from the saved measured geometry, then rewritten as V5 when possible.

## 3. Continuous distance-based comparison

`src/distance_performance.py` compares current and reference lap clocks on one
shared distance axis (5 m default). Each point contains:

- current/reference lap clock;
- cumulative delta;
- local delta;
- local gain/loss state;
- speed, throttle, brake, steering, and slip differences when available.

The trace is compressed into contiguous `GAIN`, `LOSS`, and `NEUTRAL` zones for
map display.

## 4. Turn + straight attribution and reconciliation

The physical lap is partitioned into non-overlapping TURN and STRAIGHT regions.
Every region receives measured net/gross gain/loss values.

The model exposes:

- `full_track_net_delta_s`;
- `partition_net_delta_s`;
- `reconciliation_error_s`.

For a complete lap, turn + straight attribution is required to reconcile with
the continuous full-lap delta. Coaching attribution separately allows the
approach/braking part owned by a turn so an early brake loss is not incorrectly
left without a corner diagnosis.

## 5. Deterministic physical-turn diagnosis

Matched historical brake sections are still used when available, but they are
mapped onto physical T IDs. A physical corner that has no independent detector
section can now be diagnosed directly from the measured distance trace.

Supported measured causes include:

- brake point early/late;
- peak brake high/low;
- brake-release/trail-brake differences where section telemetry supports them;
- turn-in early/late;
- low minimum speed;
- late throttle pickup;
- slow throttle ramp;
- low exit speed;
- other existing section-based deterministic diagnoses.

A corrective cause is emitted only when the relevant measured phase lost time.
If the physical turn measurably lost time but no supported cause clears a
threshold, the system reports a generic measured turn-pace loss instead of
inventing a cause.

## 6. PRE coach

PRE targets now come from physical T1...Tn. Reference brake point, turn-in,
apex, exit, minimum speed and apex gear are attached to the same physical turn.

A full measured reference can provide PRE targets even when it has no detector
section list; measured brake/steering events are recovered from the reference
distance trace.

External-reference mode can provide one PRE opportunity for every physical turn
per lap, subject to the existing safety/radio gates.

## 7. POST coach

POST analysis is now driven by the integrated performance pipeline and evaluates
a physical turn after its physical exit. It uses the same physical T number,
continuous local loss, diagnosis and reference target used by the rest of the
system.

The previous section-only path remains as a compatibility fallback for old or
sparse references before a continuous trace is available.

## 8. Native + LAN full-track gain/loss map

The Track Map page now consumes the same continuous performance model and draws
the completed comparison over the learned circuit:

- green = locally gaining time;
- red = locally losing time;
- neutral = approximately equal.

The footer can also show the last full-track measured delta. Native and LAN
views consume the same snapshot fields.

## 9. Compatibility fixes retained

- V1.0.2.1 start-line-gated map capture remains intact.
- One JSON file per circuit remains intact.
- V1.0.2.2 live/replay player pointer continues to prefer current world X/Z.
- Legacy section-only analysis still attributes early braking from the turn's
  approach, preserving existing deterministic coaching behaviour.

## Validation

Full automated suite after integration:

- 593 tests passed
- 383 subtests passed
- 0 failures


---

## Archived source: `V1.0.3.1_TURN_COACH_POSITION_SYNC_HOTFIX_NOTES.md`

# V1.0.3.1 — Turn Coach Position Sync Hotfix

This hotfix keeps the V1.0.3.0 full performance coaching pipeline and fixes one authority mismatch exposed by Melbourne replay testing.

## Root cause

The Track Map used the learned per-track physical T1..Tn geometry, while the live Turn Coach overlay still partitioned the reference lap from detected brake sections. Imported EA Time Trial rival references can contain fewer detector sections than physical corners. A detector section around 4030 m could therefore be labelled `TURN 5` while the map correctly placed the car at physical T11.

## Fix

- `physical_turn_boundaries()` now falls back to the persisted `maps/tracks/<TRACK>.json` physical turn model when a reference does not contain usable world X/Z geometry.
- External reference metadata now restores canonical `track_name` and `track_length_m` for older stored references.
- The Turn Coach active segment, turn history, and straight/turn partition now use the same physical boundaries as the map.
- Live turn metrics map the physical turn back to its attached detector section only for brake/min-speed/throttle measurements. Detector IDs never become public T numbers.
- PRE seed advice and POST coaching inherit the same physical authority through the shared boundary model.
- The continuous distance-performance pipeline uses the stored physical map turns for world-geometry-less external references.

## Expected Melbourne behaviour

At approximately 4063 m, where the learned Melbourne map identifies physical T11, the Turn Coach must display `TURN 11`. If the reference's fifth detected braking section supplies the technique data for that corner, it remains internal as `reference_section_id = 5`; spoken and displayed coaching remains Turn 11.

## Validation

- 597 pytest tests passed.
- 383 subtests passed.
- 0 failures.


---

## Archived source: `V1.1.0.0_CORNER_COACH_HYBRID_REFERENCE_SYSTEM_NOTES.md`

# V1.1.0.0 — CORNER COACH Hybrid Reference System

V1.1.0.0 replaces the old one-section/one-turn coaching assumption with a hybrid reference architecture while preserving the working V1.0.3.1 map/player-pointer foundation.

## Core model

- `PhysicalCorner`: stable physical circuit T1...Tn geometry.
- `DrivingEvent`: reference-driver brake, release, lift, steering, steering reversal, minimum-speed and throttle events.
- `CoachingZone`: the actual coaching unit. It can contain one or multiple physical corners.
- `ReferenceTrace`: compiled distance-normalized best-rival trace.
- `PerformanceTrace`: current-lap/reference comparison on the same distance axis.
- `Diagnosis`: deterministic measured explanation of gain/loss.

Physical turn numbers are never generated from detector-section ordinals. Brake/session events are attached to physical turns and complexes but cannot rename them.

## Rival Reference Capture

Control Center now provides `Session Recording` and `Rival Reference Capture` modes. Rival Reference Capture keeps the normal player-session recorder off and samples only the selected EA Time Trial rival's all-car telemetry channels for the reference dataset.

The first partial lap is ignored. Capture waits for an S/F anchor, accepts only a complete valid S/F-to-S/F rival lap, validates distance/input/motion/timing continuity, and keeps the fastest valid complete lap (or the denser capture when the same TT rival lap repeats at identical time).

A valid capture is compiled into a per-track bundle:

```text
references/<TRACK>/
    rival_reference.json
    reference_model.json
    coaching_zones.json
```

`reference_model.json` is the normal CORNER COACH runtime format. When the raw stored rival reference is selected, the engine automatically prefers its sibling compiled model instead of rebuilding it every packet/session.

## Hybrid segmentation

Physical geometry and reference-driver events are analysed independently and then fused. Short left/right/left sequences remain distinct physical T numbers, while the hybrid model may group them into one CoachingZone when the reference drives them as one continuous problem.

Merge evidence includes shared braking, short separation, continuous steering and lack of meaningful full-throttle recovery. A meaningful recovery/new braking event keeps zones separate.

Example:

```text
Physical: T5 -> T6 -> T7
Driver:   one brake -> continuous direction changes -> one final throttle pickup
Coach:    CoachingZone T5-T7
```

The map still displays T5, T6 and T7 individually.

## Continuous performance and attribution

Current and reference traces are compared on the same lap-distance axis. Local loss is always calculated from the change in delta across the region:

```text
section_loss = delta_at_end - delta_at_start
```

The hybrid partition attributes measured loss to CoachingZones and straights and reports a reconciliation residual against the full-track delta.

## Deterministic diagnosis

POST diagnosis compares measured values only, including:

- brake point and peak brake;
- brake release;
- turn-in timing;
- minimum speed;
- throttle pickup and full-throttle point;
- exit speed;
- phase-specific time loss;
- dominant physical corner inside a multi-corner zone when supported.

If the system can prove the loss but not its cause, it reports the measured loss without inventing a causal instruction.

## PRE / POST synchronization

Map position, active CoachingZone, PRE trigger, POST trigger, overlay state and performance comparison use the same current lap-distance source.

PRE instructions use remaining distance to the measured reference brake point. POST has a bounded after-zone window; replay seeks or packet jumps beyond that window silently expire the old zone instead of speaking stale coaching at a later corner.

When the V1.1 hybrid reference is available, the legacy live coach remains available for summaries/positive context but its old turn PRE/POST path is suppressed to avoid duplicate/conflicting calls.

## New CORNER COACH overlay

A dedicated resizable CORNER COACH overlay is added rather than renaming the old Turn Coach panel.

- approximately 75% live track map / 25% live driver panel;
- working V1.0.3.1 track map and player-position authority is reused;
- every physical T number remains visible;
- reference braking path runs light red -> dark red toward the physical apex;
- green begins at the physical apex and strengthens toward/after reference throttle pickup;
- measured gain/loss can be drawn underneath the reference driving layer;
- live REF vs YOU bars show brake, throttle, steering and speed;
- active CoachingZone and driving phase/progress are displayed;
- border/corner drag resizing is supported.

## Control Center

Added runtime controls for:

- CORNER COACH
- CORNER COACH VOICE
- PRE
- POST
- GAIN/LOSS MAP
- Session Recording / Rival Reference Capture mode
- rival capture/quality/model-ready status

## Validation

Final automated validation for this build:

- **610 tests passed**
- **383 subtests passed**
- Python source compile check passed
- **0 failures**

New V1.1 regression coverage includes rival-only sampling, complete-lap quality validation, compiled reference round-trip, hybrid multi-corner grouping, full-throttle separation, zone/straight reconciliation, nested reference discovery, recording-mode isolation, live T11 distance synchronization, dedicated overlay structure, dynamic PRE distance and stale POST seek suppression.

Real track/replay validation with a newly captured Time Trial rival remains the next user-side acceptance test; automated tests cannot substitute for an actual EA F1 UDP run.


---

## Archived source: `V1.1.0.0_CORNER_COACH_HYBRID_REFERENCE_SYSTEM_PLAN.md`

# V1.1.0.0 — CORNER COACH Hybrid Reference System

**Project:** Race Engineer  
**Status:** Agreed implementation plan  
**Base version:** V1.0.3.1  
**Date:** 2026-09-23

## 1. Core rule

The existing V1.0.3.1 map, replay, live player pointer, and stable Race Engineer functions are the frozen base.

The new CORNER COACH architecture must be built on top of that base without destabilizing the working map/pointer logic.

---

## 2. Rename Turn Coach

The existing **Turn Coach** concept is replaced by:

# CORNER COACH

A coaching unit is not assumed to equal one physical turn.

A coaching unit may represent:
- one physical corner,
- multiple connected physical corners,
- a chicane or esses sequence,
- a corner complex,
- or a corner/straight transition where the complete driving sequence needs to be analysed together.

---

## 3. Separate internal concepts

The implementation must keep these concepts separate:

### PhysicalCorner

Represents the actual circuit turn structure:

- T1
- T2
- T3
- ...
- Tn

Typical fields:
- physical turn number
- start distance
- apex distance
- end distance
- turn direction
- world/map position
- geometry/curvature information

### DrivingEvent

Represents what the reference driver actually does.

Examples:
- brake start
- peak brake
- brake release
- lift
- steering onset
- steering direction/reversal
- minimum speed
- throttle pickup
- full throttle
- gear
- exit speed

### CoachingZone

Represents the section that CORNER COACH actually analyses and coaches.

A CoachingZone may contain:
- one PhysicalCorner,
- multiple PhysicalCorners,
- one DrivingEvent,
- or multiple DrivingEvents.

### ReferenceTrace

The distance-normalized best rival telemetry trace.

### PerformanceTrace

The user's live/current lap trace aligned to the ReferenceTrace by lap distance.

### Diagnosis

The deterministic explanation of where and why time was gained or lost.

### Critical rule

`PhysicalCorner != DrivingEvent != CoachingZone`

They can reference one another, but must never be treated as the same object.

---

## 4. Hybrid segmentation model

CORNER COACH must use a hybrid model that combines:

- physical track geometry
- the earlier brake/session-based detection
- steering changes
- lift/throttle behaviour
- local speed behaviour
- continuous distance-based gain/loss

No single method is the sole authority.

### Physical model

Use the completed map geometry to identify the physical T1...Tn structure.

Signals include:
- signed curvature
- heading change
- curvature peaks
- curvature direction reversal
- local radius
- distance between peaks

Short tight sequences must not be merged only because they are close together.

Example:

`LEFT -> RIGHT -> LEFT`

must be able to remain:

`T5 -> T6 -> T7`

even when all three are close together.

### Driver-event model

Independently detect:
- braking
- release
- lifting
- steering onset
- steering reversal
- minimum speed
- throttle pickup
- full throttle
- acceleration
- gear behaviour

### Fusion

Physical geometry tells the system **what corners exist**.

Driver-event detection tells the system **how those corners are driven**.

The fusion layer decides the correct CoachingZones.

---

## 5. Stable physical turn numbering

Physical T1...Tn remain circuit facts.

Brake sections must never directly become public turn numbers.

For example:

`Detector Section 5` may be associated with `T11`.

The UI and voice must still call it **T11**, not Turn 5.

A single braking event may be associated with:
- one physical corner,
- multiple physical corners,
- or an entire corner complex.

---

## 6. Combine physical corners when required

Multiple physical turns may be grouped into a single CoachingZone.

Example:

Physical:
- T5
- T6
- T7

Coaching:

`Zone = T5-T7`

Combine corners when measurable evidence shows they should be treated as one driving problem, such as:
- one shared braking event
- very short physical spacing
- continuous steering activity
- no meaningful full-throttle recovery
- one corner directly controls the next
- no useful time gap for separate PRE messages
- continuous local time-loss behaviour

Keep them separate when a meaningful reset exists, for example:

`T5 -> meaningful acceleration/full-throttle recovery -> new braking event -> T6`

### Driver-facing naming

Do not speak internal Zone IDs.

Examples:
- single corner: `Turn 11`
- combined sequence: `T5 through 7`

---

## 7. Dedicated Time Trial Rival Reference Capture

Add two recording modes:

- Session Recording
- Rival Reference Capture

### Rival Reference Capture rules

When this mode is active:
- extract and persist the selected Time Trial rival's useful telemetry
- do not record the user's own driving telemetry into the reference dataset
- keep only the session/global metadata required to interpret the rival data

Reference channels should include useful data such as:
- lap distance
- lap time
- world X/Z
- speed
- gear
- throttle
- brake
- steering
- ERS where available/reliable
- other reliable telemetry required by CORNER COACH

---

## 8. Complete valid rival laps only

Reference capture must use a complete lap:

`START/FINISH -> full lap -> START/FINISH`

Do not accept:
- partial laps
- invalid laps
- laps with major telemetry gaps
- bad distance continuity
- insufficient input coverage
- broken motion/world-position coverage

If multiple valid rival laps are captured, the fastest complete valid lap becomes the primary reference.

Other valid laps may be retained for later validation/statistics, but they do not replace the primary reference unless they are faster and valid.

---

## 9. Reference Capture Quality validation

Before accepting a rival lap, validate:

- complete S/F-to-S/F lap
- valid lap
- near-complete distance coverage
- telemetry continuity
- motion/world-position coverage
- driver-input coverage
- no large packet gaps
- usable timing continuity

Example accepted status:

- Complete lap: PASS
- Valid lap: PASS
- Distance coverage: PASS
- Input coverage: PASS
- Motion coverage: PASS
- Packet continuity: PASS

Only then should the reference be accepted.

---

## 10. Compile a permanent per-track Reference Model

Do not require CORNER COACH to decode the full raw replay while driving.

After a valid reference is captured, compile it into a permanent per-track model.

Suggested layout:

```text
references/
    MELBOURNE/
        rival_reference.aref
        reference_model.json
        coaching_zones.json
```

The raw capture is source material.

The compiled Reference Model is what CORNER COACH should use during normal operation.

---

## 11. Distance-normalized reference model

Normalize the best rival lap onto a common lap-distance axis.

Suggested spacing:
- approximately 2-5 m

At each distance sample store useful reference information such as:
- distance
- elapsed lap time
- speed
- throttle
- brake
- steering
- gear
- world X
- world Z
- ERS
- other reliable reference channels

Conceptually:

`REFERENCE[d]`

The user's current lap becomes:

`YOU[d]`

Both are compared at the same lap distance.

---

## 12. Continuous distance-based performance model

During live driving compare:

`YOU[d] vs REFERENCE[d]`

For each small distance interval calculate:
- cumulative delta
- change in delta
- local gain/loss
- speed difference
- brake difference
- throttle difference
- steering difference
- other supported deterministic differences

### Critical timing rule

Local section loss must be:

`section_loss = delta_at_section_end - delta_at_section_start`

Do not use accumulated lap delta as the corner loss.

This prevents a deficit created earlier in the lap from being incorrectly blamed on a later corner.

---

## 13. Full-track gain/loss model

The entire circuit should be continuously classified as:
- gain
- neutral
- loss

The analysis should cover:
- physical corners
- CoachingZones
- straights
- transitions

The total attribution must reconcile with the measured lap delta within a small tolerance.

Conceptually:

`sum(zone losses + straight losses) ~= full lap delta`

If reconciliation quality is poor, the coach should suppress questionable diagnosis instead of inventing certainty.

---

## 14. CoachingZone phase analysis

Each CoachingZone should be divided into meaningful phases.

For a single corner:

`APPROACH -> BRAKE/LIFT -> ENTRY -> APEX -> EXIT`

For a multi-corner complex:

`APPROACH -> T5 -> TRANSITION -> T6 -> TRANSITION -> T7 -> EXIT`

Analyse the user's performance against the reference for each phase.

---

## 15. Deterministic diagnosis

Diagnosis must use measurable facts only.

Useful comparisons include:
- brake point
- braking amount
- peak braking
- brake duration
- brake release
- turn-in
- steering trace
- minimum speed
- throttle pickup
- full-throttle point
- exit speed
- gear
- ERS where relevant and reliable

Example measured differences:

- Brake point: 28 m early
- Brake release: 17 m early
- Minimum speed: -8 km/h
- Throttle pickup: 14 m late
- Exit speed: -11 km/h

Also measure where the time loss occurred:

- Approach: +0.08 s
- Entry: +0.11 s
- Middle: +0.03 s
- Exit: +0.14 s
- Zone total: +0.36 s

### Confidence rule

If the data proves the loss but not the cause, CORNER COACH should report the loss only.

Example:

`T11, lost about two tenths.`

It must not invent a braking, steering, or throttle explanation without sufficient evidence.

---

## 16. PRE coaching

PRE coaching operates on CoachingZones.

For a single physical corner:

`Turn 11 coming up. Brake about 95 metres, third gear.`

For a complex:

`T5 through 7 coming up. Brake at 100 metres and prioritise the final exit.`

PRE should provide only the highest-value actionable information.

Do not read every available telemetry parameter.

---

## 17. POST coaching

POST coaching happens only after the CoachingZone has been fully exited and enough data exists.

Examples:

`T11, lost two tenths. You braked about 20 metres early.`

`T5 through 7, lost three tenths. Most of it was through T6 and the exit.`

For improvement:

`T11 better. You gained a tenth on entry; throttle is still late.`

### Synchronization rule

The same authoritative current-lap distance source must control:
- map player position
- active CoachingZone
- PRE trigger
- POST trigger
- overlay title
- live performance comparison

This prevents the previous issue where the map showed one physical turn while the coach displayed an unrelated detector-section number.

---

# CORNER COACH Overlay

## 18. Create a brand-new overlay

Create a dedicated new overlay:

# CORNER COACH

Do not simply rename the old Turn Coach window.

The new overlay is designed specifically around the hybrid CoachingZone architecture.

---

## 19. Overlay layout

The overlay must be freely resizable by dragging its borders/corners.

Internal layout:

- approximately 75% = live track map
- approximately 25% = live driver/progress panel

Concept:

```text
+--------------------------------------+-------------+
|                                      |             |
|                                      | LIVE        |
|             TRACK MAP                | DRIVER      |
|                75%                   | PANEL       |
|                                      | 25%         |
|                                      |             |
+--------------------------------------+-------------+
```

The ratio should remain approximately consistent while resizing.

---

## 20. Live track map

Reuse the already working live map and player-position foundation from V1.0.3.1.

Do not destabilize the map/pointer code.

The map must show:
- live player position
- track geometry
- physical turn numbers
- active CoachingZone
- reference brake/throttle colouring
- gain/loss visualization where enabled

---

## 21. Physical corner labels

Every physical corner must remain individually numbered on the map:

- T1
- T2
- T3
- ...
- Tn

Even when several turns belong to one CoachingZone, the individual physical T numbers remain visible.

Example:

A CoachingZone may be `T5-T7`, but the map still displays:
- T5
- T6
- T7

---

## 22. Reference braking colour

For each corner/zone, draw the reference braking section on the map.

From the reference braking point toward the apex:
- begin with light red
- progressively deepen the red
- darkest red should occur near the deepest braking/apex region

Concept:

`BRAKE START -> light red -> medium red -> dark red -> APEX`

The colour represents the reference driving sequence, not merely local gain/loss.

---

## 23. Reference throttle colour

From the apex/exit phase onward:
- use green to indicate throttle pickup/exit acceleration
- continue the green through the relevant acceleration phase

Concept:

`APEX -> throttle pickup -> green -> stronger exit acceleration`

This should make the reference line visually communicate:

`brake -> rotate -> accelerate`

---

## 24. Multi-corner CoachingZone map handling

If one CoachingZone contains:

`T5 + T6 + T7`

the map should still display all three physical corner labels.

The active zone may additionally be identified as:

`ACTIVE: T5-T7`

but physical corner numbering must not disappear or be replaced by internal zone numbering.

---

## 25. 25% live driver panel

The right-side panel should use progress bars similar to the existing Race Engineer visual style.

Initial live parameters:

- Brake
- Throttle
- Steering
- Speed / Delta

Gear or another key value may be included if it does not overcrowd the panel.

The panel should emphasize comparison against the reference where useful.

Example:

```text
BRAKE
REF   ███████████░░░
YOU   █████████████░

THROTTLE
REF   ████████████░░
YOU   █████████░░░░░
```

---

## 26. CoachingZone progress indicator

The 25% panel should also show where the user currently is within the active driving sequence.

Single corner example:

`APPROACH -> BRAKE -> ENTRY -> APEX -> EXIT`

Complex example:

`BRAKE -> T5 -> T6 -> T7 -> EXIT`

A moving indicator should show current progress.

This provides both:
- geographic position on the map
- driving-phase position within the active CoachingZone

---

## 27. Control Center integration

Add controls for:

- CORNER COACH ON/OFF
- CORNER COACH VOICE ON/OFF
- PRE COACH ON/OFF
- POST COACH ON/OFF
- GAIN/LOSS MAP ON/OFF

Recording mode:

- Session Recording
- Rival Reference Capture

Reference capture status should expose:
- selected rival
- current track
- capture status
- lap being captured
- best valid lap
- capture quality
- compiled reference model status

---

## 28. Persistence layout

Keep track facts separate from reference-driver facts.

Suggested layout:

```text
maps/
    tracks/
        MELBOURNE.json

references/
    MELBOURNE/
        rival_reference.aref
        reference_model.json
        coaching_zones.json
```

### Track file

Stores:
- track geometry
- physical T1...Tn
- distance axis
- physical corner positions/boundaries

### Reference model

Stores:
- best rival telemetry trace
- distance-normalized telemetry
- driver events
- reference driving behaviour

### Coaching zone file

Stores:
- PhysicalCorner-to-DrivingEvent relationships
- CoachingZone boundaries
- physical corner members
- reference event members

---

## 29. Validation before full coaching

Before CORNER COACH becomes authoritative for a track/reference, validate:

- correct track
- complete physical corner sequence
- valid rival reference
- continuous reference distance
- valid CoachingZone segmentation
- no impossible overlapping zones
- map/current-distance synchronization
- PRE triggers before the correct zone
- POST triggers after the correct zone
- local loss attribution reconciles with lap delta
- every spoken/displayed T number matches the map T number

If validation fails, suppress unreliable coaching rather than silently using bad data.

---

# Final system flow

```text
TIME TRIAL RIVAL
      ↓
RIVAL-ONLY REFERENCE CAPTURE
      ↓
BEST COMPLETE VALID LAP
      ↓
DISTANCE-NORMALIZED REFERENCE MODEL
      ↓
CONTINUOUS DISTANCE PERFORMANCE MODEL
      ↓
FULL-TRACK LOCAL GAIN / LOSS
      ↓
PHYSICAL CORNERS + DRIVER EVENTS
      ↓
HYBRID SEGMENTATION
      ↓
COACHING ZONES
      ↓
ZONE / STRAIGHT LOSS ATTRIBUTION
      ↓
DETERMINISTIC DIAGNOSIS
      ↓
CORNER COACH
      ↓
PRE → DRIVE → POST
```

---

# Implementation order

Implement in this order:

1. New data classes
2. Rival Reference Capture
3. Reference compiler
4. Physical-corner analyser
5. Driver-event analyser
6. Hybrid CoachingZone builder
7. Continuous performance engine
8. Zone/straight gain-loss attribution
9. Deterministic diagnosis
10. PRE/POST state machine
11. New CORNER COACH overlay
12. Reference brake/throttle map colouring
13. Live comparison/progress bars
14. Control Center integration
15. Replay/reference validation
16. Full regression suite

---

# Frozen requirement

**Do not rewrite or destabilize the working V1.0.3.1 live map/player-pointer system while implementing this phase.**

The new CORNER COACH should consume that stable map/distance foundation.


---

## Archived source: `V1.1.0.10_CLEAN_RIVAL_PACE_REFERENCE_COMPILER_NOTES.md`

# V1.1.0.10 — Clean Rival Pace Reference Compiler

## Scope

This release intentionally does **not** modify live rival capture. `src/rival_benchmark.py` and `src/race_state_receiver.py` are byte-identical to V1.1.0.9. The proven V1.1.0.5 S/F capture, promotion, per-track folder, and raw-save behavior remains frozen.

## Root issue addressed

EA F1 Time Trial rival/shadow telemetry can expose a correct rival lap clock and lap-distance trace while speed and driver-input channels are not reliable enough to use as authoritative coaching data. Differentiating the quantized lap clock over individual 5 m bins also produced artificial speed spikes.

## Post-save compiler pipeline

1. Read the already-saved `rival_reference.json`.
2. Trust rival lap distance, rival lap clock, official sector/lap times, and usable world geometry.
3. Discard rival ghost speed/brake/throttle/steering/gear as coaching authority.
4. Build a 5 m time-distance grid with exact S/F endpoints.
5. Convert timing increments to seconds/metre, reject only extreme single-bin artefacts, apply a median pre-filter, then triangular smoothing.
6. Reintegrate the pace curve and piecewise anchor it to official S1, S1+S2, and full-lap timing.
7. Derive stable speed with a 50 m local linear regression.
8. Derive longitudinal acceleration only from the clean pace curve.
9. Build physical T1..Tn and Coaching Zones using the existing geometry authority.
10. Persist `reference_model.json` and `coaching_zones.json`; the raw recording is never overwritten.

## Validation gates

A V1.1.0.10 clean rival model must retain full S/F coverage, monotonic time, exact lap timing, <=3% reconstructed distance/time physics error, <=10 ms official timing-anchor error, and a derived speed range inside 20..390 km/h. Old rival models without the V1.1.0.10 clean-pace compiler marker are rejected and rebuilt from raw data in memory rather than silently reused.

## Supplied Melbourne validation

Thomas Ronhaar: 1:16.435 (26.382 / 17.824 / 32.229), track length 5276 m. The rebuilt model has 1057 samples including the exact 5276 m / 76.435 s endpoint, 14 physical turns, 10 Coaching Zones, derived speed 107.6..342.9 km/h, no >=350 km/h spikes, ~0.13% speed-distance error, ~0.03% speed-time error, and <1 ms maximum sector/lap anchor interpolation error.


---

## Archived source: `V1.1.0.11_REFERENCE_COMPILER_AUTHORITY_MODEL_FINGERPRINT_HOTFIX_NOTES.md`

# V1.1.0.11 Reference Compiler Authority + Model Fingerprint Hotfix

## Observed failure
A fresh Melbourne rival rerecord saved a new `rival_reference.json`, but the sibling `reference_model.json` still identified itself as quality validator v3 and retained the old 386 km/h derivative spikes. Manually compiling the same raw file with the V1.1.0.10 source produced the correct clean model. Therefore the capture itself was good; the runtime had not actually produced the saved model with the intended compiler.

## Fix
- Freeze live rival capture/save logic (`rival_benchmark.py`, `race_state_receiver.py`).
- Add startup compiler-source/version self-check.
- Add compiler id, schema version, validator version, pace compiler version, and raw-reference SHA-256 fingerprint to every compiled rival model.
- Invalidate old `reference_model.json` and `coaching_zones.json` as `.stale` immediately after a new raw lap is saved and before compiling.
- Verify the compiled file from disk before declaring it ready.
- Reject any model whose sibling raw reference fingerprint does not match.
- Reject models that do not start/end on exact authoritative timing/distance or whose clean derived speed exceeds the sanity bound.

## Melbourne validation
Using the user's fresh 1:22.239 Melbourne raw recording:
- exact endpoint: 5276.0 m / 82.239 s
- validator: 5
- pace compiler: 2
- compiler id: V1.1.0.11_CLEAN_RIVAL_PACE_V2
- derived speed: 97.73 to 346.26 km/h
- samples >= 350 km/h: 0
- speed-distance error: 0.128%
- speed-time error: 0.011%
- timing anchor max error: 0.51 ms
- physical turns: 14

## Regression
638 tests + 383 subtests passed.


---

## Archived source: `V1.1.0.12_CORNER_COACH_END_TO_END_VALIDATION_TRACE_NOTES.md`

# V1.1.0.12 — CORNER COACH End-to-End Validation Trace

## Purpose
V1.1.0.11 fixed and live-validated the rival reference capture/compiler pipeline. V1.1.0.12 moves to the next roadmap gate: validate CORNER COACH sequencing, timing attribution and voice delivery without relying on screenshots.

## Automatic validation artifact
When CORNER COACH has a usable reference, Race Engineer automatically creates:

`analysis/corner_coach_validation/CORNER_COACH_<TRACK>_<SESSION_UID>_<UTC>.jsonl`

The console prints the exact path once the trace starts.

The writer is asynchronous. Telemetry/audio threads only queue compact records; disk I/O runs on a daemon writer thread.

## What the file contains
- complete reference fingerprint/compiler/quality metadata
- PhysicalCorner definitions and expected T1...Tn sequence
- CoachingZone definitions and expected zone sequence
- 10 m distance-sampled player/reference timing state
- player speed, brake, throttle, steering and gear
- active CoachingZone, active phase and physical corner
- physical-corner enter/exit transitions
- CoachingZone enter/exit transitions
- phase transitions
- PRE emitted, blocked and missed events with exact reasons
- POST emitted, blocked and expired events with exact reasons
- deterministic POST diagnosis payload
- radio submission events
- actual TTS audio-start events
- per-lap zone/straight attribution and reconciliation
- generated-but-not-spoken coach calls
- duplicate/order checks in each lap summary

## Offline analysis
A saved trace can be summarized with:

```powershell
.\.venv\Scripts\python.exe -m src.corner_coach_validation ".\analysis\corner_coach_validation\<file>.jsonl"
```

The raw JSONL is the preferred artifact to send for detailed validation.

## Pace-only diagnosis safety
EA Time Trial rival raw brake/throttle/steering/gear/speed channels remain untrusted. V1.1.0.12 closes two remaining diagnosis leaks:
- peak-brake comparison is disabled when `input_telemetry_trusted=false`
- exit-speed comparison uses the clean compiled pace speed rather than raw rival ghost speed

This preserves factual pace coaching without inventing rival input claims.

## Reference pipeline
No changes were made to the validated V1.1.0.11 rival capture/save/compiler pipeline. The compiler authority remains:

`V1.1.0.11_CLEAN_RIVAL_PACE_V2 | validator 5 | pace 2`


## Regression

641 tests + 383 subtests passed.


---

## Archived source: `V1.1.0.13_CORNER_COACH_RADIO_CIRCULAR_PRE_LAP_BOUNDARY_FIX_NOTES.md`

# V1.1.0.13 — CORNER COACH Radio Delivery + Circular PRE + Lap Boundary Fix

## Why this release exists

The first real five-lap Melbourne V1.1.0.12 validation trace proved the physical T1-T14 and Z1-Z10 sequence was correct, but exposed four runtime defects and one wording defect:

1. 96 CORNER COACH messages were submitted but only 50 reached audio start because `corner:pre:` did not inherit the legacy PRE radio priority and CORNER COACH POST had no dedicated scheduling rank.
2. T1 PRE was missed on flying laps because the PRE search stopped at track length instead of wrapping to next-lap T1.
3. T12 and T13-T14 shared the same 4325 m slowdown event because the padded event search allowed the previous physical corner's pace event to leak into the next CoachingZone.
4. The final straight often remained incomplete because LapData wrapped from ~5270 m to the new lap without a sample at exact track length; the final race lap could also remain labelled as lap 5 after the chequered flag and append post-finish T1/T2 to lap 5.
5. POST speech used `You minimum speed...` rather than `Your minimum speed...`.

## Fixes

### Radio delivery

- `corner:pre:` uses the same rank (-2), replacement family and 1.5 s freshness window as legacy PRE.
- `corner:post:` uses dedicated rank 0: below CRITICAL/PRE, above routine assist/strategy/information/coaching traffic.
- queued CORNER PRE/POST are replaceable per CoachingZone so an obsolete previous-lap call cannot survive behind a newer one.

### Circular PRE

PRE candidates now operate on a circular lap axis. On the final straight, the distance to next-lap T1 is:

`(track_length - current_distance) + T1_target`

The call is keyed to the target lap (`corner:pre:<next lap>:Z1`) and carried across S/F so it is not emitted again or marked missed after the line.

### CoachingZone event ownership

Pace-derived events carrying `metadata.corner_id` may only belong to a CoachingZone containing that physical corner. Legacy/input events without corner IDs may not start before the previous zone's physical end. This removes the Melbourne Z10 contamination from T12. `approach_start_m` is also clamped to `<= start_m`.

### Exact lap-boundary finalization

At an official lap increment, `previous_lap_time_s` is used to append an exact `track_length_m` point to the incremental performance model before reset. This closes the last straight and makes zone/straight partition reconciliation complete even when no packet lands exactly on S/F.

A separate large-distance-wrap detector handles the final race lap. If the scheduled final lap wraps to near zero while EA leaves `current_lap` unchanged, the lap is finalized immediately and CORNER COACH enters a post-finish hold so T1/T2 are not appended to the completed race lap.

### Validation schema v2

Circular PRE submission/audio is attributed to its target lap rather than the lap on which it was spoken. This keeps per-lap `pre_emitted` and generated-vs-heard checks meaningful.

### Reference model compatibility

The clean pace algorithm itself is unchanged: validator 5, pace compiler 2. Only CoachingZone association semantics changed, so reference-model schema is now 3 and compiler ID is:

`V1.1.0.13_CLEAN_RIVAL_PACE_V2_ZONE_ASSOCIATION_V2`

Old schema-2 compiled models are rejected and rebuilt from sibling raw `rival_reference.json` at runtime. A freshly compiled Melbourne model separates Z9/T12 and Z10/T13-T14 correctly.

## Validation

Latest Melbourne 1:16.435 raw reference recompiles to:

- exact 5276.0 m / 76.435 s finish;
- 14 physical corners;
- 10 CoachingZones;
- max derived speed ~339.03 km/h;
- zero samples >=350 km/h;
- Z9/T12 slowdown event at 4325 m;
- Z10/T13-T14 slowdown event at 4530 m;
- T8 `approach_start_m = start_m = 2785 m`.

Regression suite: **648 tests + 383 subtests passed**.


---

## Archived source: `V1.1.0.14_CORNER_COACH_AIRTIME_SEQUENCER_TRUSTED_TURN_BARS_NOTES.md`

# V1.1.0.14 — CORNER COACH Airtime Sequencer + Trusted TURN Bars

## Why this release exists

The V1.1.0.13 Melbourne validation proved that physical T1–T14 order, CoachingZone Z1–Z10 order, circular T1 PRE, lap-boundary closure and zone event association were correct. The remaining problem was radio airtime: a valid PRE or POST could be generated while another sentence was still playing, then become irrelevant before it reached audio.

V1.1.0.14 changes CORNER COACH radio from queue-oriented delivery to **deadline-oriented delivery**.

## Airtime policy

```text
POST previous turn
       ↓
Can POST finish while preserving enough airtime for next PRE?
       ├─ Yes → full POST
       ├─ Tight → compact POST
       └─ No → POST suppressed
                         ↓
                  PRE next turn
                         ↓
              must finish before entry
```

Every CORNER COACH PRE/POST now carries an absolute monotonic finish deadline and an estimated speech duration. Piper output is measured again from the actual generated WAV before playback.

### PRE rules

- Full PRE is preferred when it fits.
- Compact PRE is used when the full sentence does not fit.
- If compact PRE cannot finish before entry, it is suppressed rather than queued late.
- If PRE arrives during POST, POST finishes only when both messages still fit before the PRE deadline; otherwise POST is stopped immediately.
- If a new PRE arrives during an older PRE on a tight corner sequence, the older PRE finishes only when the newer PRE can still finish in time; otherwise the older PRE is stopped.
- A PRE whose deadline is already passed is never started.

### POST rules

- The next PRE's full speech budget is reserved first.
- Full POST is preferred when remaining airtime allows it.
- Compact POST is used when full POST would consume the protected PRE window.
- If neither version fits, POST is intentionally suppressed.
- POST playback is stopped if its hard deadline is reached.

## Validation trace

Validation schema is now **3** and records deterministic radio outcomes, including:

- `SPOKEN_COMPLETE`
- `POST_FINISH_ALLOWED_BEFORE_PRE`
- `POST_PREEMPTED_FOR_PRE`
- `PRE_FINISH_ALLOWED_BEFORE_NEXT_PRE`
- `PRE_PREEMPTED_FOR_NEXT_PRE`
- `PRE_NO_AIRTIME`
- `PRE_STALE_AT_ENTRY`
- `POST_NO_AIRTIME`
- `DEADLINE_REACHED_DURING_AUDIO`
- higher-priority/PTT/family-disable pre-emption outcomes

This makes the JSONL trace sufficient to determine whether a call was spoken, shortened, deliberately omitted, pre-empted, or became invalid.

## Race Engineer TURN overlay trust rules

For Time Trial `rival_pace` references, raw rival brake/throttle/steering/gear channels remain untrusted. The Race Engineer TURN overlay therefore displays:

- **Braking Point:** WAIT
- **Throttle Timing:** WAIT
- **Min Speed:** player measured minimum versus clean compiled reference pace speed
- **Exit Speed:** player measured exit speed versus clean compiled reference pace speed

This prevents the TURN bars from presenting unsupported brake/throttle comparisons against EA ghost telemetry.

## Recording default

Normal Session Recording is OFF by default. It can still be enabled explicitly with `--record-telemetry`, `--recording-path`, or the Control Center REC switch. Rival Reference Capture is a separate mode and is unaffected.

## Reference compatibility

No rival capture/compiler changes are made in V1.1.0.14. It continues to require the V1.1.0.13 model authority:

- reference schema 3
- quality validator 5
- clean pace compiler 2
- compiler ID `V1.1.0.13_CLEAN_RIVAL_PACE_V2_ZONE_ASSOCIATION_V2`

Existing valid Melbourne `rival_reference.json` does not need to be rerecorded or modified.


---

## Archived source: `V1.1.0.15_PROGRESS_REPORT.md`

# V1.1.0.15 Progress Report — CORNER COACH Reliability Recovery

## Status

This is the current full-code internal validation snapshot, not the final sign-off build. It contains the fixes completed so far after analysing the V1.1.0.14 live Melbourne trace and replaying the supplied recordings.

## Problems confirmed from the V1.1.0.14 live trace

- The generic speech estimator materially under-estimated the actual `en_GB-alan-medium` Piper WAV duration. In the supplied trace, PRE lines that were estimated at 5.79 s commonly produced roughly 7.5–8.0 s WAVs; longer complex-zone PREs estimated at 7.75 s produced roughly 10 s WAVs.
- Because the scheduler trusted those short estimates, many PREs were accepted by CORNER COACH and then rejected later by TTS as `PRE_NO_AIRTIME`.
- POST scheduling reserved airtime for the numerically next zone even when that zone's PRE had already been emitted. This suppressed valid POST calls unnecessarily.
- CORNER COACH text was added to its transcript only at actual audio start, so a useful generated line disappeared from text whenever TTS later dropped or pre-empted it.

## Fixes completed in this snapshot

1. **Speech-budget calibration**
   - The deterministic estimator is calibrated for the project's normal Alan Piper voice at length scale 0.82.
   - The old 2.55 words/s estimate has been replaced by a conservative 1.85 words/s model with fixed synthesis/playback overhead.
   - Exact generated WAV duration is still the final authority before playback.

2. **Compact PRE as the real-time contract**
   - PRE now prefers the compact deterministic form when the rich sentence would consume too much approach time.
   - Full PRE is used only when substantial extra airtime exists.
   - PRE scheduling window is widened to 10.5 s so the compact cue can be delivered earlier without waiting until the corner becomes urgent.

3. **Correct pending-PRE reservation**
   - `_next_pre_context()` now searches for the next genuinely pending PRE.
   - It skips PRE calls already emitted on the current lap.
   - Circular next-lap PRE logic still works and also skips already-carried next-lap PREs.
   - POST reserves only the compact pending PRE duration, not an unnecessary verbose sentence.

4. **Visual text independent from audio delivery**
   - CORNER COACH's dedicated transcript now records generated PRE/POST text at radio submit time.
   - Actual audio start/delivery remains separately recorded in the validation JSONL.
   - The ordinary Race Engineer radio transcript remains heard-only.

5. **Existing safety retained**
   - PRE/POST remain single-channel with no intentional overlap.
   - A stale PRE is never allowed to begin after its deadline.
   - Urgent PRE can still pre-empt POST or an older PRE when there is genuinely insufficient time.
   - Session recording remains OFF by default.
   - Rival Reference Capture remains independent.
   - `rival_pace` brake/throttle claims remain hidden from the Race Engineer TURN bars.

## Automated tests

Full suite after the reliability changes:

- **659 tests passed**
- **383 subtests passed**

The new V1.1.0.15 tests specifically cover:

- conservative Alan/Piper duration estimation,
- skipping already-emitted PRE calls when calculating POST airtime,
- reserving compact rather than verbose PRE airtime.

## Supplied replay regression runs completed

### Melbourne Race

Input: `Race_telemetry-20260918T064535Z-d7412ccc(1).areplay`

- 81,159 packets processed
- 5 completed laps
- best valid lap: lap 3
- CORNER COACH replay traces generated without runtime exceptions
- on the replayed race laps analysed so far, no PRE-missed events and no POST airtime suppression were produced by the corrected scheduling logic

### Melbourne Qualifying

Input: `Qual_telemetry-20260918T062108Z-c38b7cfb(1).areplay`

- 38,358 packets processed
- 1 completed lap
- best valid lap: lap 1
- replay completed without runtime exceptions
- qualifying session routing remains intact

### Austria Time Trial

Input: `TimeTrial_telemetry-20260917T121801Z-940696c8(1).areplay`

- 92,262 packets processed
- 7 completed laps
- best valid lap: lap 3
- CORNER COACH traces generated without runtime exceptions
- analysed replay laps show no POST airtime suppression and no PRE-missed events under the corrected generation logic

### Shanghai

Only the small `.areplay.json` metadata sidecar is available in the supplied files, not the 30 MB `.areplay` payload itself. The metadata reports 30,945 packets and 30,627,113 UDP payload bytes. Therefore full packet replay of Shanghai cannot yet be performed from the currently supplied file set.

The **Shanghai rival reference itself was compiled and validated internally**, together with Melbourne and Austria.

## Three-track rival-reference validation

All three supplied raw rival references compile successfully through the current clean pace compiler/validator:

| Track | Lap | Track length | Physical turns | Coaching zones | Max derived speed | Speed-distance error | Speed-time error |
|---|---:|---:|---:|---:|---:|---:|---:|
| Melbourne | 1:16.435 | 5276 m | 14 | 10 | 339.03 km/h | 0.102% | 0.016% |
| Austria | 1:03.495 | 4323 m | 10 | 8 | 356.57 km/h | 0.126% | 0.013% |
| Shanghai | 1:30.153 | 5441 m | 16 | 8 | 354.19 km/h | 0.152% | 0.016% |

All three returned validator version 5, pace compiler version 2, accepted quality, sequential physical-corner numbering, and monotonic CoachingZone order.

## Roadmap audit — still pending before final sign-off

The roadmap still contains larger P0 work that is not yet complete and should not be falsely marked finished:

- Lap-End Coach Summary
- Potential Lap Engine
- remaining data-quality gates such as missing-packet/outlier/pause/replay-seek/session-restart handling
- tyre/fuel condition mismatch handling
- formal latency/no-spam/replay-live parity benchmarks
- long-session stability/performance/memory benchmarks

For CORNER COACH specifically, the major remaining acceptance item is a thorough offline multi-lap delivery simulation using realistic Piper durations across Melbourne, Austria and Shanghai, including close-zone stress cases and explicit proof that no PRE is late, no audio overlaps, and POST is only suppressed when there is truly no safe airtime.

## Important limitation of this progress snapshot

This package is the **current achieved state**. It is not being labelled “full and final” yet because Shanghai packet replay is unavailable and the final multi-track audio-delivery stress harness is still being completed. The code is packaged now because the user asked for the full code and a report of progress achieved so far.


---

## Archived source: `V1.1.0.1_RACE_ENGINEER_CORNER_COACH_SEPARATION_HOTFIX_NOTES.md`

# V1.1.0.1 — Race Engineer / CORNER COACH Separation Hotfix

Base: V1.1.0.0 CORNER COACH Hybrid Reference System.

## Fixed from first real replay validation

1. CORNER COACH slow/choppy behaviour
   - whole-lap distance/performance rebuilds are decoupled from raw telemetry packet rate;
   - full performance rebuild runs only after meaningful distance/time progress;
   - CORNER COACH visual refresh is capped near 30 Hz;
   - hidden CORNER COACH windows are not continuously refreshed;
   - map distance interpolation avoids repeated full-array allocation in the paint hot path.

2. POST OFF confusion / duplicate post coaching
   - legacy integrated PRE/POST corner output is always suppressed;
   - CORNER COACH is the sole owner of corner PRE/POST;
   - CC PRE / CC POST independently gate their own TTS message families, including already queued/current calls.

3. ENGR no longer controls CORNER COACH
   - `corner:*` messages are explicitly independent from the Automatic Race Engineer mute;
   - ENGR OFF suppresses Race Engineer automatic output while CORNER COACH continues according to CC / VOICE / PRE / POST controls.

4. Control Center separation
   - SYSTEM contains global TTS/PTT/STT/LLM/replay/recording/pause state;
   - RACE ENGINEER contains ENGR/LAP/POS/RACE controls;
   - CORNER COACH contains CC/VOICE/PRE/POST/G/L controls.

5. Transcript separation
   - ordinary Radio Transcript contains driver/race-engineer/race-control traffic;
   - CORNER COACH has its own transcript store embedded in the right-side 25% panel;
   - CORNER COACH messages no longer pollute the Race Engineer transcript.

## Validation

- 616 pytest tests passed.
- 383 subtests passed.
- 0 failures.
- Python source compilation passed.


---

## Archived source: `V1.1.0.2_HIERARCHICAL_CONTROLS_PERFORMANCE_OPTIMIZATION_NOTES.md`

# V1.1.0.2 — Hierarchical Controls + Performance Optimization Hotfix

## Purpose

This hotfix follows real replay validation of V1.1.0.1. Race Engineer / CORNER COACH separation remains intact. The release fixes parent/child switch behaviour, adds reference-relative visual quality feedback, and removes the global performance regression introduced by the first CORNER COACH runtime.

## 1. State-preserving hierarchy

### Race Engineer

`ENGR` is the parent for the Race Engineer coaching controls shown in the Control Center.

- ENGR OFF -> LAP/POS/RACE are effectively OFF and disabled in the UI.
- Their raw preferences are not modified.
- ENGR ON -> LAP/POS/RACE return to their exact pre-OFF states.

### CORNER COACH

`CC` is the parent for CORNER COACH.

- CC OFF -> VOICE/PRE/POST/G-L are effectively OFF and disabled in the UI.
- Their raw preferences are retained.
- CC ON -> each child returns to its previous individual state.

This supports mixed states such as PRE ON / POST OFF across a master OFF -> ON cycle.

## 2. CORNER COACH progress-bar quality gradient

Brake, Throttle, Steering and Speed now compare YOU against the cyan REF marker. The fill colour changes continuously according to measured reference deviation:

- green: close match / GOOD
- green-to-amber: small deviation / CLOSE
- amber-to-red: larger deviation / WORK
- red: large deviation / OFF

Speed quality is based on closeness to the reference speed, not simply whether the player is faster or slower. Steering uses absolute signed-input deviation while retaining the centre line and cyan reference marker.

## 3. Global lag root cause

The V1.1 CORNER COACH pipeline added expensive work to the telemetry path. A full distance-performance refresh repeatedly:

- interpolated unused channel deltas at every distance bin;
- rediscovered physical performance boundaries;
- rebuilt/sorted performance distance arrays many times during phase/zone attribution;
- asked the measured-performance recorder for a full current-lap summary, which recalculated sections/statistics and serialized every sample;
- propagated a much larger point payload toward UI state;
- repainted static CORNER COACH map content too frequently.

Because this work runs in Python on the same process, CPU/GIL pressure could make replay decoding and unrelated Qt overlays appear choppy too.

## 4. Performance changes

- Physical performance boundaries are compiled/cached once per CORNER COACH reference.
- Distance axes are built once and reused for binary-search interpolation.
- CoachingZone/straight attribution sorts the performance points once instead of once per segment.
- CORNER COACH calls `build_distance_performance_model(..., include_channel_deltas=False)` because live bars/diagnosis already consume raw input channels.
- A new `MeasuredPerformanceRecorder.current_lap_trace_snapshot()` supplies only the current raw trace and minimal lap/track metadata.
- The large 5 m point trace remains private to diagnosis; shared overlay status receives only compact gain/loss/segment summaries.
- Heavy comparison cadence remains decoupled from source packet rate, but a zone-exit crossing forces a refresh before POST diagnosis.
- Static CORNER COACH map layers are cached in a QPixmap. Fast visual refreshes only draw dynamic content unless static inputs change.
- Hidden overlays are not refreshed/polled unnecessarily.
- Control Center avoids repeating unchanged text/style/enabled-state work every refresh tick.

## 5. Local profiling

Representative synthetic full-lap profiling in the development environment:

- original CORNER COACH full comparison refresh: approximately 50 ms
- optimized full comparison path: under 10 ms
- previous full current-lap summary: approximately 6.8 ms/call
- new lightweight current-lap trace snapshot: approximately 0.02 ms/call

These measurements are development profiling results, not a guaranteed target-PC frame rate. Real replay/live validation is still required.

## 6. Switch meanings

### Race Engineer

- **ENGR** — master for automatic Race Engineer/race-session output.
- **LAP** — measured lap summary/comparison calls.
- **POS** — positive/improvement acknowledgement calls.
- **RACE** — allows Race Engineer coaching-policy calls during race sessions.

### CORNER COACH

- **CC** — master for CORNER COACH analysis/overlay coaching runtime.
- **VOICE** — speaks CORNER COACH messages via TTS.
- **PRE** — actionable reference instruction before the active CoachingZone.
- **POST** — measured feedback after the completed CoachingZone.
- **G/L** — shows measured local gain/loss on the CORNER COACH track map.

## 7. Validation

- 622 pytest tests passed
- 383 subtests passed
- 0 failures
- modified Python modules compile successfully

The next acceptance step is a real replay at 1.0x with CORNER COACH visible and then hidden, followed by a live Time Trial check. The expected result is that replay clock progression and all overlays remain smooth while CORNER COACH stays synchronized.


---

## Archived source: `V1.1.0.3_ZERO_BLOCKING_TELEMETRY_SMOOTH_REPLAY_HOTFIX_NOTES.md`

# V1.1.0.3 — Zero-Blocking Telemetry + Smooth Replay Hotfix

## Purpose

V1.1.0.2 fixed the largest CORNER COACH CPU costs, but real 1.0x replay testing still showed global timing bursts: lap time advanced in visible jumps and unrelated graphs/map markers moved in steps. This release removes the remaining recurrent whole-lap CORNER COACH rebuild from the packet-critical path.

Race Engineer / CORNER COACH separation, hierarchical master switches, the reference-relative quality bars, and the frozen V1.0.3.1 track-map/player-pointer foundation are retained.

## Root cause

Replay pacing is based on the recording timestamps. `process_packet()` is synchronous. In V1.1.0.2, CORNER COACH still rebuilt the complete distance-performance model periodically from inside that packet path. Even after the previous optimization, a multi-millisecond analysis spike meant the replay loop fell briefly behind and then processed following packets back-to-back to catch up.

That scheduling pattern presents visually as:

- lap time moving in steps;
- graphs receiving samples in bursts;
- map markers jumping rather than moving continuously;
- unrelated overlays appearing choppy even though the new work originated in CORNER COACH.

## Zero-blocking live performance model

The live CORNER COACH packet path now uses an incremental distance/timing model.

For each authoritative lap-time advance it performs only:

1. one reference-time lookup on the precompiled distance axis;
2. one current delta calculation;
3. one append/replace of the current distance point;
4. one short-window local gain/loss update;
5. completion checks for already-compiled turn/straight/CoachingZone boundaries.

It does **not** call the generic whole-lap `build_distance_performance_model()` from `CornerCoachEngine.observe()`.

Telemetry packets that repeat the same authoritative lap time do not create timing samples or trigger performance reconstruction. This makes the normal high-rate packet path effectively constant-time with respect to lap length.

## Compact live status

The full incremental timing point array remains private inside CORNER COACH. Shared overlay state receives only compact summaries:

- gain/loss spans;
- completed turn/straight attribution;
- completed CoachingZone attribution;
- full-track net delta/reconciliation values where available.

POST diagnosis still has access to the private measured points, but full-lap analysis is no longer rebuilt continuously.

## POST behaviour

POST remains deterministic and tied to the exact CoachingZone just exited.

- A richer current trace is requested only when a POST diagnosis is actually due.
- Replay seeks/large jumps expire stale zones even when no performance model is available.
- PRE/POST, ENGR/CC separation, and parent/child switch restoration are unchanged.

## CORNER COACH map rendering

The expensive static map layer is now isolated from live gain/loss and active-zone changes.

The following remain in the cached static layer:

- circuit geometry;
- physical T labels;
- reference brake red gradient;
- reference apex/throttle green gradient.

Gain/loss spans use a separate lightweight cache and draw directly over already-scaled map vertices. The active CoachingZone uses its own lightweight layer. The player marker remains the only always-live map element.

This prevents a changing gain/loss state from forcing the complete antialiased track/reference layer to be regenerated.

## Regression guarantees

New tests verify that:

- `CornerCoachEngine.observe()` contains no whole-lap distance-builder call;
- repeated telemetry packets with an unchanged authoritative lap time add no performance work;
- an advancing lap clock updates the incremental performance model;
- compact shared gain/loss state does not expose/copy the full live point trace;
- stale POST zones expire after replay seeks without requiring a performance rebuild;
- changing gain/loss/active-zone state does not invalidate the expensive static CORNER COACH map layer.

## Validation

- 627 pytest tests passed
- 383 subtests passed
- 0 failures

Real target-PC replay validation remains the final acceptance test because operating-system scheduling, GPU/Qt paint cost and the user's actual recorded packet density cannot be perfectly reproduced by the synthetic test environment.


---

## Archived source: `V1.1.0.4_GLOBAL_UI_PIPELINE_DASHBOARD_MAP_SMOOTHNESS_NOTES.md`

# V1.1.0.4 — Global UI Pipeline + Dashboard Map Smoothness Hotfix

## User-reported issue

V1.1.0.3 was substantially smoother, but occasional whole-application stepping remained. The normal dashboard map also showed the CORNER COACH local loss colour layer, which was not wanted there.

## Root causes found

1. Shared overlay snapshot construction still contained several O(n) reference/current-trace operations on a high-frequency Qt timer.
2. Physical turn derivation could still rescan/smooth the full world trace from UI/reference consumers even though the reference is immutable.
3. Reference ghost time→distance conversion rebuilt and sorted the reference time axis repeatedly.
4. The F1 dashboard MAP page rebuilt the same scaled circuit path every paint and its marker interpolation allocated multiple temporary lists per marker.
5. Browser dashboard payload generation repeatedly converted static track-map geometry into JSON lists.

## Fixes

### Dashboard map visual separation
- Native F1 dashboard MAP page no longer paints `map_gain_loss_zones`.
- Browser/LAN dashboard map no longer creates gain/loss performance paths.
- CORNER COACH remains the only overlay that renders local GAIN/LOSS colouring.

### Shared snapshot hot path
- `_trace_has_lap_start()` now checks start bins/prefix only.
- physical turn boundaries use a bounded cache keyed by reference identity + track/map signature.
- reference time-axis lookup is cached and uses binary search.
- aligned live delta trace is incrementally cached and extended as current-lap bins arrive.
- legacy section-only references keep deterministic T-label fallback without forcing geometry analysis.

### Native F1 dashboard MAP page
- learned map tuples are reused directly;
- scaled map geometry/QPainterPath is cached by track/map/window key;
- lap-distance interpolation works directly on immutable point/distance sequences without per-call copies;
- dynamic work is reduced to player/reference/nearby marker interpolation and drawing.

### LAN/browser publication
- static per-track map points/distances are converted once and cached for dashboard payloads.

## Validation target

Use the same 1.00x replay and watch all of these simultaneously:
- lap timer progression;
- delta/driver graphs;
- native F1 dashboard player marker;
- CORNER COACH player marker;
- replay position slider.

They should advance together without periodic burst/catch-up behaviour.


---

## Archived source: `V1.1.0.5_AUTO_ARMED_RIVAL_REFERENCE_CAPTURE_HOTFIX_NOTES.md`

# V1.1.0.5 — Auto-Armed Rival Reference Capture Hotfix

## Problem

Live testing showed contradictory recording states after selecting `Rival Reference Capture`:

- the dedicated rival capture engine could be enabled,
- the normal `REC` indicator still showed `Off`,
- and the reference row displayed `RECORDING` even with zero incoming F1 packets.

The cause was that the Control Center `REC` display was still driven by the raw session recorder while the dedicated rival capture used `TimeTrialRivalCapture.enabled`.

## Fix

- Selecting `Rival Reference Capture` now auto-arms the rival capture engine.
- Rival capture no longer depends on the normal `REC` switch.
- `REC` is explicitly treated as the raw **Session Recording** control.
- In rival mode the `REC` control displays `Auto`, is disabled, and explains that reference capture is automatic.
- Reference capture status now reports distinct states:
  - `ARMED • WAITING FOR TT TELEMETRY`
  - `ARMED • WAITING FOR RIVAL`
  - `ARMED • WAITING FOR S/F`
  - `CAPTURING`
  - quality / best lap / model-ready details when available.
- Switching from Session Recording to Rival Reference Capture closes the raw session recorder.
- Switching back to Session Recording restores the previous normal REC preference.
- Pressing/toggling normal REC while rival mode is active cannot accidentally disable rival capture.

## Intended operation

1. Select `Rival Reference Capture`.
2. Status becomes `ARMED` immediately.
3. Start/enter Time Trial and select a rival.
4. Capture waits for the required S/F anchor.
5. A full valid rival lap is captured and quality checked.
6. The best valid lap is compiled into the per-track CORNER COACH reference model.

Normal `REC` does not need to be ON for this workflow.


---

## Archived source: `V1.1.0.9_V1105_CAPTURE_RESTORE_SAFE_POST_SAVE_COMPILE_NOTES.md`

# V1.1.0.9 — V1.1.0.5 Capture Restore + Safe Post-Save Compile

## Why this release exists

V1.1.0.6–V1.1.0.8 changed the live Time Trial rival sampling/quality path while trying to repair unreliable ghost telemetry. Live testing showed that those changes could reject a complete rival lap before the original per-track save trigger ran. V1.1.0.8 exposed this as `LAST REJECT TIMING_CONTINUITY`.

## Capture path restored

The project was rebuilt from the user-provided V1.1.0.5 ZIP. `src/race_state_receiver.py` is unchanged from that base. `src/rival_benchmark.py` retains the V1.1.0.5 packet sampling, S/F anchoring, lap completion, rival selection and best-lap promotion logic. The only intentional capture-side change is that its acceptance check calls `validate_capture_lap()`, which is the V1.1.0.5 validator preserved verbatim as a capture-only gate.

## Save first, compile second

`save_reference_bundle()` now writes `references/<TRACK>/rival_reference.json` atomically before any strict CORNER COACH compilation. If model compilation fails, the raw reference remains on disk and can be rebuilt later.

## Safe compiled reference

For `EA_F1_TIME_TRIAL_RIVAL` sources, the compiler discards untrusted ghost pedal/steering/gear/speed channels, reconstructs speed from distance/time, derives longitudinal acceleration, validates pace physics, and builds pace events plus physical corners/coaching zones.

## Validation

- Full project suite: 628 tests + 383 subtests passed before release-specific tests.
- Earlier real references rebuild successfully: Austria 10 turns / 7 zones, Melbourne 14 / 10, Shanghai 16 / 12.
- Rebuilt speed-distance and speed-time errors remain below 0.7% for those three references.


---

## Archived source: `V1.2.0.0_FINAL_VALIDATION_REPORT.md`

# Race Engineer V1.2.0.0 — Final P0 Coaching Milestone

## Result

V1.2.0.0 is the internally validated final release for the current P0 coaching milestone. It is not a claim that every P1/P2/P3 roadmap item is finished.

## CORNER COACH reliability

- One coaching speech channel; PRE/POST are never intentionally overlapped.
- PRE uses a hard finish deadline and compact/micro wording when approach time is short.
- PRE can pre-empt an older POST only when waiting would make the incoming PRE late.
- POST reserves only genuinely pending PRE airtime. Already-emitted/circular PRE calls are not reserved twice.
- POST can be full, compact, micro, or visual-only when speech cannot safely fit. Visual-only POST still appears in CORNER COACH text.
- Lap-1 standing-start T1 now uses live-speed ETA instead of the flying-lap rival ETA, removing the final Melbourne T1 miss.
- Circular next-lap T1 PRE remains enabled.
- Stale/late calls are rejected instead of being spoken in the next corner.
- Same-lap impossible distance jumps/seeks compromise the lap and suppress false coaching.

## Trusted rival-pacing behavior

Time Trial rival raw brake/throttle/steering/gear remain untrusted. The clean model uses authoritative distance/time geometry and derives pace speed. Race Engineer TURN metrics use only defensible pace-derived quantities; unsupported rival brake/throttle timing stays unavailable.

## Added milestone features

- Lap-End Coach Summary: lap time, reference delta, previous-lap delta, biggest/second opportunity, improvement, current focus, potential, and session-specific wording.
- Potential Lap Engine: valid compatible sector theoretical plus optional corner-segment theoretical; invalid/compromised samples excluded.
- Data-quality gates: missing-distance packets, outlier speed, non-monotonic clock, pause, replay seek, session restart, wet/dry mismatch, tyre warning, fuel-load warning, traffic/race-control/pit/damage blockers.
- Automatic deterministic JSON + HTML coach report with best/reference/potential, recurring patterns, technique consistency, per-lap corner analyses, speed/brake/throttle/gear comparison traces, racing-line and straight analysis where data supports them.
- Session recording remains OFF by default; Rival Reference Capture remains independent.

## Automated test suite

- 668 pytest tests passed.
- 383 subtests passed.

## Replay acceptance

### Melbourne Race
- 81,159 packets; 5 completed laps; best valid lap 3.
- Clean rival reference: 1:16.435.
- 50 PRE generated; 45 POST spoken candidates + 5 intentional visual-only POST decisions.
- PRE missed: 0; PRE suppressed: 0; POST expired: 0; late messages: 0.
- Physical/zone ordering: PASS.
- Acceptance: PASS.
- Fast-replay benchmark in this container: 28.91 s, peak RSS ~209,580 KB.

### Melbourne Qualifying
- 38,358 packets; 1 completed lap; best valid lap 1.
- Multiple qualifying session fragments replayed without runtime errors.
- No late PRE, no PRE misses in accepted traces; ordering PASS.
- Acceptance: PASS.

### Austria Time Trial
- 92,262 packets; 7 completed laps; best valid lap 3.
- Clean rival reference: 1:03.495.
- 44 PRE and 42 POST emitted; no late, missed, suppressed PRE or expired POST.
- One recorded telemetry/session discontinuity is safely gated.
- Acceptance: SAFE_SUPPRESSION_ON_COMPROMISED_DATA.
- Fast-replay benchmark: 28.73 s, peak RSS ~221,356 KB.

### Shanghai
- 30,945 packets; 1 completed lap recognised; best valid lap 2.
- Clean rival reference: 1:30.153.
- The supplied recording contains three impossible same-lap distance jumps/seeks. V1.2.0.0 detects these and stops generating false corner misses/late radio.
- PRE missed: 0; PRE suppressed: 0; late: 0.
- Acceptance: SAFE_SUPPRESSION_ON_COMPROMISED_DATA.
- Fast-replay benchmark: 7.97 s, peak RSS ~144,652 KB.

## Three-track clean reference validation

| Track | Rival lap | Length | Physical turns | Coaching zones | Max derived speed | Distance integration error | Time integration error |
|---|---:|---:|---:|---:|---:|---:|---:|
| Melbourne | 1:16.435 | 5276 m | 14 | 10 | 339.03 km/h | 0.102% | 0.016% |
| Austria | 1:03.495 | 4323 m | 10 | 8 | 356.57 km/h | 0.126% | 0.013% |
| Shanghai | 1:30.153 | 5441 m | 16 | 8 | 354.19 km/h | 0.152% | 0.016% |

The stored raw rival-reference files were not rewritten while rebuilding stale compiled models.

## Scope / remaining roadmap

The current P0 milestone is complete enough for release. P1/P2/P3 items such as interactive performance-radio questions, richer session memory, track landmark packs, advanced line coaching, historical progress UI, installer/EXE polish, and ecosystem features remain roadmap work rather than blockers for this release.

## Environment limitation

The container can validate telemetry decoding, game-time radio scheduling, message deadlines, reference math, reports and replay behavior, but it cannot physically listen to the Windows speaker/headset path. The Piper exact-WAV duration/deadline checks remain in the runtime, and the offline acceptance harness verifies that generated calls fit the available game-time speech windows.


---

## Archived source: `V1.2.0.1_CORNER_COACH_RUNTIME_TOGGLE_HOTFIX_NOTES.md`

# V1.2.0.1 — CORNER COACH Runtime Toggle Hotfix

This hotfix is based on the user's Melbourne three-mode validation of V1.2.0.0.

## Fixed

- POST-only mode no longer reserves airtime for disabled PRE calls.
- PRE-only mode cannot create POST expiry/suppression after POST is disabled.
- PRE enabled mid-lap starts from the next still-upcoming target; already-passed targets are marked not-applicable rather than `pre_missed`.
- POST enabled mid-lap starts with zones not yet completed; completed zones are not back-filled or expired.
- Runtime PRE/POST/VOICE changes are written immediately to validation as `coach_config_change`.
- Disabling PRE or POST clears that family's deterministic game-time speech reservation so an obsolete disabled cue cannot block the other coach mode.
- Existing combined PRE+POST single-channel airtime sequencing is preserved.
- Rival reference capture and clean pace compiler are unchanged.

## Acceptance matrix

The regression suite explicitly covers PRE OFF/POST ON, PRE ON/POST OFF, mid-lap PRE enable, mid-lap POST enable, and reservation release on disable.


---

## Archived source: `V1.2.0.1_VALIDATION_REPORT.md`

# V1.2.0.1 Validation Report — CORNER COACH Runtime Toggle Hotfix

## Trigger

The Melbourne V1.2.0.0 user validation exercised three live control combinations:

- PRE OFF / POST ON: POST text appeared but most POST audio was suppressed.
- PRE ON / POST OFF: PRE delivery worked, but stale validation state could still classify disabled POST opportunities incorrectly.
- PRE ON / POST ON: combined sequencing was generally healthy.

The root cause was mode-state handling around the otherwise-correct one-channel airtime sequencer.

## Corrections

1. `_next_pre_context()` returns no reservation when PRE or CORNER COACH voice is disabled.
2. Enabling PRE mid-lap marks already-passed PRE targets not-applicable for that lap.
3. Enabling POST mid-lap marks already-completed zones not-applicable for that lap.
4. Disabling PRE/POST releases that family's game-time speech reservation immediately.
5. Validation records live `coach_config_change` events with previous/new states and not-applicable zone sets.
6. Combined PRE+POST deadline/pre-emption logic is otherwise unchanged.
7. Rival capture and clean pace compiler are unchanged.

## Tests

- Focused airtime/runtime-toggle suite: 15 passed.
- Full automated suite: **672 passed + 383 subtests passed**.
- Melbourne Race replay: 81,159 packets completed without runtime error.
- Shanghai replay: 30,945 packets completed without runtime error.
- Austria Time Trial was not used as a completion benchmark in this hotfix run because the local fast-replay process did not terminate within the execution window; the unchanged Austria/reference logic remains covered by the full automated suite and prior V1.2.0.0 acceptance.

## Files deliberately unchanged

The hotfix does not alter rival capture, raw-reference persistence, or the clean pace compiler authority.


---

## Archived source: `V1.2.0.2_CORNER_COACH_MAP_GAINLOSS_GAINLOSS_VOICE_NOTES.md`

# V1.2.0.2 — CORNER COACH MAP G/L + G/L Voice

## Changes

- Renamed the old `G/L` Control Center button to `MAP G/L`. It remains visual-only.
- Added an independent `G/L VOICE` toggle, OFF by default.
- G/L voice announces completed CoachingZone time gain/loss using measured distance-aligned performance only.
- Spoken threshold: absolute zone delta >= 0.05 s. Smaller changes remain on the map and are not spoken.
- PRE/POST retain priority. If the radio is busy or a pending PRE requires the airtime, G/L is kept as visual transcript text instead of delayed speech.
- Runtime toggle changes do not back-fill zones completed while G/L voice was disabled.
- Added an independent TTS family gate for `corner:gainloss:`.
- Added validation events `gain_loss_voice_emit` and `gain_loss_voice_suppressed`.
- Kept the proven Control Center geometry; the two G/L controls use a compact second CORNER COACH row.

## Validation

- Full suite: 680 passed + 383 subtests.
- Focused V1.2.0.2 tests: 8 passed.


---

## Archived source: `V1.2.0.3_CORNER_COACH_LOCAL_CONTROLS_EXCLUSIVE_POST_VOICE_NOTES.md`

# V1.2.0.3 — CORNER COACH Local Controls + Exclusive Post Voice

## Changes

- Moved all CORNER COACH runtime controls from Control Center into the CORNER COACH overlay:
  - CC
  - VOICE
  - PRE
  - POST
  - MAP G/L
  - G/L VOICE
- Control Center keeps only the CORNER COACH overlay launcher.
- POST and G/L VOICE are now mutually exclusive:
  - enabling POST disables G/L VOICE;
  - enabling G/L VOICE disables POST.
- PRE and MAP G/L remain independent from this mutual exclusion.
- `PRE ON / POST OFF / MAP G/L ON / G/L VOICE OFF` remains fully supported.
- The overlay buttons continuously sync to effective receiver state, including master CC dependency and automatic POST/G/L VOICE switching.
- Reference capture/compiler pipeline is unchanged.


---

## Archived source: `V1.2.0.3_VALIDATION_REPORT.md`

# V1.2.0.3 Validation Report

## Scope

V1.2.0.3 moves all CORNER COACH runtime buttons into the CORNER COACH overlay and makes POST / G/L VOICE mutually exclusive while leaving PRE and MAP G/L independent.

## Required behavior

- Enabling POST automatically disables G/L VOICE.
- Enabling G/L VOICE automatically disables POST.
- PRE ON / POST OFF / MAP G/L ON / G/L VOICE OFF remains valid.
- MAP G/L never changes POST or G/L VOICE.
- All CC controls now live in the CORNER COACH overlay: CC, VOICE, PRE, POST, MAP G/L, G/L VOICE.
- Control Center retains the CORNER COACH overlay launcher but no longer duplicates those runtime buttons.
- Overlay buttons continuously synchronize with the receiver's effective states.

## Regression tests

- Full suite: **685 tests passed**
- Subtests: **383 passed**
- Focused V1.2.0.1 / V1.2.0.2 / V1.2.0.3 control tests: **17 passed**

## Replay smoke test

Melbourne Race replay:

- 81,159 packets processed
- 5 completed laps
- best valid lap: 3
- no runtime exception
- CORNER COACH validation trace / session summary / coach report generation completed

## Frozen reference path

No change was made to rival capture or clean reference compiler authority. The existing validator / pace compiler / reference model pipeline remains unchanged.


---

## Archived source: `V1.2.0.4_REPLAY_TIMELINE_REFERENCE_MARKER_HOTFIX_NOTES.md`

# V1.2.0.4 Replay Timeline + Reference Marker Hotfix

## Why packet 62713 appeared to freeze

The Melbourne race recording is lossless and stores raw UDP arrival timestamps. Around packet 62713 the game itself did not pause: packets for frame 7143 all carry session time 350.369 s, but the recorded wall-clock arrival time contains a 1.1586 s gap before the Motion packet. The next frame advances normally to session time 350.420 s and then several packets arrive in a burst. Replaying raw arrival timing therefore reproduces an operating-system/receive scheduling stall as a visible freeze followed by a jump.

V1.2.0.4 keeps the ARERPL01 file and raw arrival timestamps unchanged, but interactive real-time replay now schedules packets from EA PacketHeader.m_sessionTime. Packets from one game frame are replayed together and normal frame-to-frame game timing is preserved. Session-time resets are stitched monotonically for robust replay switching.

## CORNER COACH visual change

The cyan reference marker on BRAKE / THROTTLE / STEERING / SPEED comparison bars is increased from 2 px to 4 px so it is easier to see without changing the underlying comparison values.

## Frozen systems

No change to rival capture, reference compilation, CoachingZone logic, PRE/POST/G-L behavior, or raw telemetry recording format.


---

## Archived source: `V1.2.0.4_VALIDATION_REPORT.md`

# V1.2.0.4 Validation Report

## Scope

This hotfix addresses the Melbourne interactive replay freeze/jump observed near packet 62713 and improves CORNER COACH reference-marker visibility.

## Root cause confirmed from the supplied Melbourne replay

The ARERPL01 recording stores raw UDP arrival timestamps. Near the visible freeze:

- packet 62713: Tyre Sets, game frame 7143, session time 350.369 s
- packet 62714: Lap Data, same frame/session time
- packet 62715: Motion, same frame/session time, but raw UDP arrival timestamp is **1.158575 s** after packet 62714
- packet 62720: Event, next frame 7144, session time 350.420 s

Therefore the game did not pause for 1.16 s. The replay scheduler was reproducing an incidental recorder/OS receive-time stall inside one game frame, followed by a burst. A second **2.242651 s** same-session-time arrival gap exists near packet 62810.

Across the full Melbourne recording, raw UDP arrival duration is about **486.926 s**, while EA game session time spans about **457.029 s**. The difference is recorder/arrival scheduling overhead, not game-driving time.

## Fix

Interactive realtime replay now builds its playback clock from the authoritative EA `PacketHeader.m_sessionTime` values while retaining the original packet bytes and raw ARERPL01 arrival timestamps unchanged.

- packets belonging to one game frame/session timestamp are processed together;
- normal game-frame time is preserved at 1.0x;
- incidental OS/UDP arrival stalls are not replayed as freezes;
- session-time resets are stitched monotonically;
- seek/checkpoint/state-rebuild behavior is unchanged;
- raw telemetry recording format and recorder path are unchanged.

At the exact affected sequence, the old/raw 1.158575 s wait at packet 62715 becomes 0.000000 s because it is the same game frame. The transition to frame 7144 retains the actual game-time advance of about 0.050995 s.

## CORNER COACH visual change

The cyan reference marker on BRAKE / THROTTLE / STEERING / SPEED bars is increased from **2 px to 4 px**. No values, thresholds, or coaching logic changed.

## Regression validation

- full suite: **688 tests passed**
- subtests: **383 passed**
- focused replay timeline/control tests: **6 passed**
- exact Melbourne packet 62712-62720 timing inspected against both raw arrival time and EA session time

## Frozen systems

No change to CORNER COACH coaching logic, PRE/POST/G-L controls, rival capture, clean reference compiler, CoachingZones, diagnosis, or raw telemetry recording format.


---

## Archived source: `V1.3.0.0_POST_SESSION_INTERACTIVE_COACH_NOTES.md`

# V1.3.0.0 — Post-Session Coach Report + Interactive Performance Coach

## Frozen baseline

CORNER COACH is frozen at V1.2.0.4. This release does not change physical turn detection, CoachingZone generation, PRE/POST scheduling, MAP G/L, G/L VOICE, reference capture, or clean rival pace compilation.

## Post-session report

The automatic JSON/HTML report now exposes:

- valid timed session laps separately from quality-eligible coaching laps;
- best lap and active-reference gap when available;
- deterministic Potential Lap values from compatible quality-eligible segments;
- ranked measured corner opportunities and repeatable strengths;
- entry / mid / exit loss ownership;
- session improvement/regression trend;
- recurring loss-supported patterns;
- deterministic technique consistency metrics;
- per-corner drill-down;
- speed, brake, throttle, gear, ERS-if-available, and distance-aligned delta traces;
- driver vs reference trace overlay;
- racing-line and straight-line analysis where supported;
- JSON and HTML output.

Traffic/damage/race-control compromised laps may still contribute factual session information such as lap time, but they cannot generate technique diagnoses or Potential Lap segments.

A final report is refreshed if Final Classification is received before the recorder completes its final-lap reconciliation.

## Interactive Performance Coach radio

Deterministic questions now include:

- Where am I losing time?
- Why am I slow in Turn X?
- Am I braking too early?
- Where should I brake for Turn X?
- How is my braking?
- How is my throttle application?
- Which corner should I work on?
- Did I improve Turn X?
- Compare this lap with reference.
- What is my biggest mistake?
- What is my potential lap?
- Where did I gain time?
- Where did I lose time this lap?
- How consistent am I?
- What should I focus on next lap?

All answers come from the current deterministic coaching suite. An optional LLM is not required and cannot replace missing measurements.


---

## Archived source: `V1.3.0.0_VALIDATION_REPORT.md`

# V1.3.0.0 Validation Report

## Release

**Race Engineer V1.3.0.0 — Post-Session Coach Report + Interactive Performance Coach**

Frozen CORNER COACH baseline: **V1.2.0.4**.

No CORNER COACH geometry, CoachingZone, PRE/POST scheduling, MAP G/L, G/L VOICE, rival capture, or clean reference compiler logic was changed in this release.

## Automated regression

Final source tree:

- **692 tests passed**
- **383 subtests passed**
- new V1.3.0.0 focused tests cover deterministic gain/loss radio answers, lap-vs-reference comparison, braking target, improvement trend, potential lap, consistency, unsupported brake-claim protection, and post-session report aggregation.

## Replay regression

### Melbourne Race

- 81,159 packets processed
- 5 completed laps
- best valid lap: lap 3
- no runtime exception
- final replay coach report generated after complete packet reconciliation
- report retained all 5 valid timed race laps as session facts
- 0 laps were allowed to generate technique coaching because all were flagged by existing quality gates for traffic/damage compromise; the report therefore does not fabricate driving-technique diagnoses from compromised race laps
- speed/brake/throttle/gear/delta overlay traces were generated in the HTML report

### Austria Time Trial

- 92,262 packets processed
- 7 completed laps
- best valid lap: lap 3
- no runtime exception
- final JSON/HTML coach report generated
- 3 quality-eligible timed laps available for deterministic technique/potential analysis
- Potential Lap and ranked measured corner opportunities generated

### Shanghai

- 30,945 packets processed
- 1 completed lap in the supplied replay
- best valid lap reported as lap 2 by the recorder
- no runtime exception
- final JSON/HTML coach report generated
- compromised-data quality gates remain active; no unsupported technique diagnosis is invented

## Post-session report acceptance

V1.3.0.0 report contains, when supported by quality-eligible data:

- best valid timed lap
- active-reference gap
- quality-gated Potential Lap
- ranked measured corner opportunities
- measured strengths
- ENTRY / MID / EXIT loss ownership
- session improvement/regression trend
- recurring patterns
- deterministic consistency metrics
- per-corner drill-down
- speed / brake / throttle / gear / ERS-if-available traces
- distance-aligned delta trace
- driver vs reference overlay
- racing-line and straight-line analysis where telemetry supports them
- JSON and HTML export

Final Classification arriving before final lap reconciliation no longer leaves the final report as an early empty/partial snapshot. Non-overlay replay also writes a final reconciled report after the complete packet stream.

## Interactive Performance Coach acceptance

Deterministic radio questions supported:

- Where am I losing time?
- Why am I slow in Turn X?
- Am I braking too early?
- Where should I brake for Turn X?
- How is my braking?
- How is my throttle application?
- Which corner should I work on?
- Did I improve Turn X?
- Compare this lap with reference.
- What is my biggest mistake?
- What is my potential lap?
- Where did I gain time?
- Where did I lose time this lap?
- How consistent am I?
- What should I focus on next lap?

The deterministic coaching-suite state is authoritative. Missing or untrusted measurements return an unavailable/no-loss-supported answer rather than an invented claim.


---

## Archived source: `V1.3.0.1_DAMAGE_COACHING_OVERRIDE_NOTES.md`

# V1.3.0.1 — Damage Coaching Override Hotfix

## User control

A new **DMG COACH** button lives in the CORNER COACH overlay and starts OFF.

- OFF: significant damage can exclude the lap from technique coaching.
- ON: `damage_compromised` is retained as a fact, but damage alone is no longer a coaching rejection reason.

The switch does not override invalid laps, pit laps, traffic compromise, race-control compromise, pauses, replay seeks, session restarts, missing telemetry, or telemetry outliers.

## Runtime behaviour

The receiver synchronizes the switch with the measured-performance recorder and live performance coach. Completed laps carry `damage_coaching_override`, and the post-session report marks override laps explicitly.

The existing CORNER COACH reference model, zone geometry, PRE/POST/G-L speech sequencing and replay-timeline hotfix are unchanged.


---

## Archived source: `V1.3.0.1_VALIDATION_REPORT.md`

# V1.3.0.1 Validation Report

## Scope

Damage coaching override only. V1.2.0.4 remains the frozen CORNER COACH baseline.

## Required behavior validated

- DMG COACH defaults OFF.
- Damage-compromised laps are rejected when override is OFF.
- Damage-compromised laps become coaching-eligible when override is ON and no other blocking quality reason exists.
- Damage remains recorded; the override is retained as `damage_coaching_override`.
- Traffic and other non-damage quality gates remain blocking even with the override ON.
- Live `significant_damage` suppression is removed only while the override is ON.
- Override preference survives measured-performance session reset.
- CORNER COACH overlay exposes DMG COACH without changing PRE/POST/MAP G/L/G/L VOICE relationships.
- Post-session report identifies laps analysed under the damage override.

## Automated regression

- Full suite: **698 tests passed**
- Subtests: **383 passed**
- New V1.3.0.1 focused tests: **6 passed**

## Replay smoke test

Melbourne Race replay:

- 81,159 packets processed
- replay completed without runtime exception
- session summary and JSON/HTML coach report generated

## Frozen paths

No changes were made to rival reference capture, reference compilation mathematics, physical-corner/CoachingZone geometry, PRE/POST radio sequencing, or V1.2.0.4 replay timing logic.


---

## Archived source: `V1.3.0.2_LIVE_DAMAGE_GATE_PTT_RECOVERY_NOTES.md`

# V1.3.0.2 — Live Damage Gate + PTT Recovery Hotfix

## Live DMG COACH authority

- **DMG COACH OFF**: significant damage (same deterministic threshold as the quality gate) suppresses CORNER COACH PRE, POST and G/L VOICE.
- MAP G/L, track map, progress, telemetry sampling and gain/loss measurement remain active.
- Targets passed while damage-blocked are marked not-applicable and are never spoken late if the override is enabled later.
- **DMG COACH ON**: damage remains measured/reported but coaching is allowed from the current point onward.
- Other invalidity/traffic/pit/race-control/telemetry protections remain independent.

## PTT failure recovery

The live trace showed `Microphone error: Error querying device -1`. The previous PTT handler reset its logical pressed state immediately after microphone-open failure. While the physical button remained held, HID polling repeatedly retriggered the failed press and `SpeechOutput.end_listening()` never ran, which could leave CORNER COACH silent.

V1.3.0.2 keeps the failed press latched until the physical release, aborts any partial recorder state, logs one actionable error per press, and executes the normal release callback. Telemetry and CORNER COACH therefore continue even if the selected/default microphone is invalid.

The microphone itself still must be a valid Windows/PortAudio input for STT replies. Select a concrete working MIC in Control Center if System default reports device -1.


---

## Archived source: `V1.3.0.2_VALIDATION_REPORT.md`

# V1.3.0.2 Validation Report

## Scope

Two live defects from the Melbourne test: live damage gating and PTT microphone-failure recovery. The frozen reference compiler, corner geometry and replay timeline remain unchanged.

## Required behavior validated

- Significant damage + DMG COACH OFF blocks live CORNER COACH speech while leaving measurement/map data active.
- DMG COACH ON preserves the damage fact but permits coaching.
- The deterministic significant-damage threshold remains unchanged.
- A failed microphone open no longer retriggers continuously while PTT is physically held.
- The normal PTT release callback still runs after microphone-open failure, so SpeechOutput can leave LISTENING state.
- The failure message explicitly tells the driver to release PTT and select a valid MIC device.

## Automated regression

- Full suite: **701 tests passed**
- Subtests: **383 passed**
- New V1.3.0.2 focused tests: **3 passed**
- V1.3.0.1 damage-override focused tests retained and passing.

## Live finding explained

`Error querying device -1` is a PortAudio/sounddevice input-device error from the selected `System default` microphone path. The hotfix prevents that hardware/configuration error from taking down radio/coaching state; a valid input device is still required to obtain STT replies.


---

## Archived source: `V1.3.0.3_DRIVER_RADIO_PRIORITY_HOTFIX_NOTES.md`

# V1.3.0.3 — Driver Radio Priority Hotfix

## Problem
When CORNER COACH was active, a coach message could be dequeued by the TTS worker while PTT/STT still owned the radio. The worker then waited on the listening gate. After STT produced the driver answer, the old coach item could continue first because its radio epoch had only been checked before that wait. This could delay or effectively hide the requested answer behind coaching traffic.

## Fix
- Driver-requested `voice:response` remains the highest radio rank.
- `prepare_radio_response()` now reserves the radio for the driver answer.
- Current non-driver audio is interrupted when a driver answer becomes ready.
- Fresh CORNER COACH/routine chatter is suppressed while the driver answer reservation is active.
- The TTS worker re-checks the radio epoch after the PTT listening wait, so a coach item popped during PTT cannot resume ahead of a later driver answer.
- The reservation is released only after the driver answer finishes (or is explicitly cancelled).
- Existing DMG COACH behavior is unchanged.

## Expected behavior
PTT press -> current coach audio stops -> STT -> deterministic/LLM answer -> answer is spoken immediately -> normal CORNER COACH resumes afterward.

## Validation
- Full suite: 704 tests passed + 383 subtests passed.
- Focused radio/coaching/PTT suite: 23 tests passed.
- Added regression tests for a coach message already popped by the worker during PTT, pending-answer channel reservation, and release after answer completion.


---

## Archived source: `V1.3.0.3_VALIDATION_REPORT.md`

# V1.3.0.3 Validation Report

## Scope
Driver PTT answers have authoritative radio priority over CORNER COACH and routine Race Engineer speech.

## Root cause reproduced
The TTS worker checked the radio epoch before waiting for PTT listening to finish. A CORNER COACH item could therefore be popped during PTT, wait, and then continue after release even though STT had invalidated it and queued the higher-priority driver answer.

## Fix verification
- voice:response remains rank -5 (highest normal radio rank).
- Driver answer preparation invalidates existing chatter and reserves the channel.
- Non-driver current playback is interrupted when the answer is ready.
- New CORNER COACH/routine lines cannot refill the channel while the answer is pending.
- Worker re-checks epoch after the listening wait.
- Answer reservation clears after the answer worker finishes.

## Tests
- Full suite: **704 passed**
- Subtests: **383 passed**
- Focused V1.3.0.3 + TTS + interactive coach + V1.3.0.2 tests: **23 passed**

## Unchanged
CORNER COACH geometry/reference/PRE/POST logic, DMG COACH behavior, reference compiler authority and replay timeline logic are unchanged.


---

## Archived source: `V1.3.1.0_FINAL_VALIDATION_REPORT.md`

# V1.3.1.0 Final Validation Report

## Result

PASS — full regression clean.

## Automated tests

- Pytest: 711 passed
- unittest subtests: 383 passed
- Failures: 0

## New coverage

`tests/test_v1310_parallel_integration.py` validates:

1. advice improvement and conservative solved-issue retirement;
2. technique consistency/progress output;
3. signed and phase-aware racing-line deviation;
4. manual landmark metadata separation from reference telemetry;
5. track-specific driver history progression;
6. quality/compatibility/Potential Lap validation evidence;
7. `improve on turn X` radio synonym using advice outcome memory.

## Compatibility decisions

- Coach report `version` remains `1.3.0.1` to preserve downstream schema expectations.
- New fields are advertised through `feature_schema_version = 1.3.1.0`.
- Existing Potential Lap interfaces and keys are unchanged.
- Existing V1.3.0.3 PTT/radio priority logic is unchanged.
- CORNER COACH live scheduling/state-machine code was not redesigned.


---

## Archived source: `V1.3.1.0_PARALLEL_COACHING_INTELLIGENCE_NOTES.md`

# V1.3.1.0 — Parallel Coaching Intelligence Integration

Base: V1.3.0.3 Driver Radio Priority Hotfix.

## Frozen paths

This release does not redesign the working live map/player-pointer, rival reference compiler, UDP decoder/core RaceState, CORNER COACH PRE/POST timing state machine, or V1.3.0.3 driver-radio priority behavior.

## Track A — Coach Intelligence

- Added `src/session_advice_memory.py`.
- Tracks coached issue by physical/reference corner and issue code.
- Measures subsequent comparable attempts only from deterministic CornerAnalysis data.
- Outcomes: `improved`, `stable`, `regressed`, `solved`.
- One clear disappearance is improvement; two consecutive measured clear attempts retire the issue by default.
- A low measured issue cost can solve immediately below the explicit threshold.
- Solved issues can reopen if the same issue later becomes dominant again.
- Persistent current focus is exposed through `coaching_suite.advice_memory` / `coaching_focus`.
- Memory resets on session reset and external reference change.
- Radio improvement queries use advice-outcome evidence first.
- Added support for natural phrase `improve on turn X`.

## Track B — Driver Analytics

- Technique metrics now include chronological observed trends alongside stddev/range consistency.
- Added lap-time progress facts: first/latest/best, first-to-latest and best-to-latest.
- Added per-corner observed trends for brake point, brake release, minimum speed, throttle pickup and exit speed.
- Driver History now supports track-specific retrieval and deterministic progress summaries.
- Stored session history now includes reference gap, potential/reference gap, advice outcomes and lap-time technique progress.

## Track C — Track Intelligence

- Racing-line comparison now calculates signed lateral deviation in a local reference-tangent frame.
- Per-corner path analysis now includes ENTRY/APEX/EXIT phase summaries.
- Existing absolute path-deviation output remains backward compatible.
- Track Landmark Store now supports manual verified braking-board and kerb start/end metadata without modifying reference telemetry.
- Added nearest visual-landmark lookup.

## Track D — Post-Session Analysis

- Existing coach report schema version `1.3.0.1` is preserved for compatibility.
- Added `feature_schema_version: 1.3.1.0`.
- Report now includes `advice_outcomes` and latest distance-performance reconciliation evidence.
- HTML includes active/solved advice counts and validation status.

## Track E — Validation / Data Quality

- Added `src/analysis_validation.py`.
- Every auto-saved coach report now also writes `<stem>_validation.json`.
- Validation artifact includes:
  - per-lap eligibility and rejection reasons;
  - condition/track/tyre/fuel compatibility evidence;
  - reference compatibility;
  - Potential Lap metrics and corner-region source laps;
  - distance reconciliation values and 50 ms check where available.

## Validation

- New V1.3.1.0 targeted tests: 7 passed.
- Full regression: **711 tests passed + 383 subtests passed**.
- `python -m src.main --help` smoke test: PASS.


---

## Archived source: `V1.3.5.0_FINAL_VALIDATION_REPORT.md`

# V1.3.5.0 Final Validation Report

## Scope

V1.3.5.0 completes the agreed parallel A–E implementation plan on top of the frozen V1.3.0.3 live radio/CORNER COACH/reference baseline.

### A — Coach Intelligence
- deterministic advice-outcome memory
- repeated-attempt improve/stable/regress/solve tracking
- solved-issue retirement and current-focus promotion
- interactive radio improvement/focus queries

### B — Driver Analytics
- technique consistency and observed chronological trends
- persistent per-track Driver History
- cross-session per-corner consistency aggregation
- recurring weakness resolution tracking
- deterministic session-vs-session comparison

### C — Track Intelligence
- signed matched-distance racing-line deviation
- robust median/MAD world-position outlier gate
- geometry-derived path apex extraction
- early/late apex classification
- turn-direction-aware pinched-exit evidence
- reference-relative steering-correction comparison
- verified 150/100/50/braking-board, kerb, S/F, pit-entry and pit-exit metadata
- per-track/per-corner PRE call-distance override
- local landmark import/export and LAN editor/API

### D — Analysis / UI
- expanded JSON/HTML coach report
- speed/brake/throttle/gear/ERS/delta traces
- driver/reference racing-line visualization
- stable latest-report aliases
- dedicated LAN coaching page at `/coach`
- coaching/history/landmark JSON APIs
- persisted driver-history rows generated from completed reports

### E — Data Quality / Validation
- evidence-bearing lap eligibility and compatibility
- Potential Lap source evidence
- reference compatibility evidence
- rejection/warning reason counts
- distance-reconciliation checks
- standalone `*_validation.json`

## Frozen/high-risk paths

The following were deliberately not redesigned:
- live map/player pointer
- rival reference compiler
- UDP decoder core
- CORNER COACH PRE/POST ownership/timing
- V1.3.0.3 driver-radio priority model

The PRE path only consumes an optional verified landmark distance override; when none is configured, existing timing behavior is unchanged.

## Automated validation

Final full suite:

```text
718 tests passed
383 subtests passed
0 failures
```

Additional completion coverage includes:
- cross-session corner progress/comparison
- recurring-issue resolution
- geometry apex/exit/steering evidence
- landmark metadata import/export
- LAN landmark GET/POST API
- validation rejection summaries
- LAN coach payload/page
- automatic Driver History persistence

## Smoke validation

```text
PYTHONPATH=. python -m src.main --help
PASS
```

## Deterministic safety rules retained

- no incompatible wet/dry samples are silently mixed
- invalid/partial/compromised samples stay excluded from coaching/potential calculations
- unknown visual landmarks remain unknown
- no braking board is invented from lap distance
- racing-line classifications are suppressed when geometry/input evidence is insufficient
- analysis/report/UI layers do not participate in UDP decoding or control decisions

## Release verdict

**PASS — suitable for live user validation as V1.3.5.0 Parallel Plan Completion.**


---

## Archived source: `V1.3.5.0_PARALLEL_PLAN_COMPLETION_NOTES.md`

# V1.3.5.0 — Parallel Plan Completion

This release completes the previously agreed A–E parallel implementation plan.

New user-facing additions:
- `/coach` LAN performance-coaching page
- cross-session driver progress and comparison
- richer racing-line/apex/exit diagnostics
- verified track-landmark editor/API
- post-session racing-line visualization
- automatic Driver History persistence
- detailed machine-readable validation/rejection evidence

Start with `RUN_RACE_ENGINEER_V1.3.5.0.bat`.


---

## Archived source: `V1.3.6.0_FINAL_VALIDATION_REPORT.md`

# V1.3.6.0 Final Validation Report

## Release
RaceEngineer V1.3.6.0 — Parallel Race Intelligence Foundation

## Parallel workstreams started
- A: deterministic race-context arbitration + measured strategy expansion
- B: local Replay/Session Library expansion + LAN `/sessions`
- C: local pronunciation/wording/cooldown speech-quality foundation
- D: deterministic first-run/product-readiness checks

## Frozen paths preserved
- CORNER COACH reference compiler/capture model
- working live track map/player pointer
- UDP telemetry decoder core
- existing V1.3.5.0 performance analysis pipeline

## Validation
- New V1.3.6.0 tests: 7 passed
- Targeted compatibility suite: 25 passed
- Full regression: 725 passed + 383 subtests passed
- Post-version focused regression: 10 passed
- `python -m src.main --help`: PASS
- `tools/first_run_check.py --udp-port 0`: PASS

## Notes
The validation container is Linux, so `windows=false` is expected in the first-run diagnostic. Windows-specific target-PC endurance and installer execution remain productization work; the Windows firewall command generator is deterministic and is never executed automatically.


---

## Archived source: `V1.3.6.0_PARALLEL_RACE_INTELLIGENCE_FOUNDATION_NOTES.md`

# V1.3.6.0 — Parallel Race Intelligence Foundation

This release starts the next four parallel workstreams while preserving the frozen CORNER COACH/reference/live-map core.

## A — Race / Strategy Intelligence
- New deterministic `race_context.py` arbitration object.
- Critical damage, puncture, critical tyre wear, brake-temperature danger, pit/neutralisation and close-combat context can suppress routine technique coaching.
- Context exposes tyre/fuel/ERS/damage/wet adaptations without inventing outcomes.
- New `strategy_expansion.py` uses measured pit-cycle samples when available.
- Measured-only rejoin margin, undercut trigger, SC/VSC opportunity, same-set pace trend, forecast transition/confidence, ERS percentage and optional measured damage pace loss.
- Radio rejoin/undercut/neutralisation responses now use the measured expansion and explicitly refuse unavailable pit-loss data.

## B — Replay / Session Library
- Expanded local `SessionLibrary` metadata cards.
- Rename, tags, favorites, notes, archive/restore and archive-only permanent deletion.
- Coach-report discovery and report metric comparison helper.
- New LAN `/sessions` page and `/api/sessions` GET/POST endpoints.

## C — Speech / Radio Polish
- Local pronunciation dictionary at `settings/pronunciation.json`, applied before TTS synthesis.
- Reusable concise wording and spoken-number utilities.
- Local category cooldown defaults for later runtime tuning.

## D — Validation / Product Readiness
- New deterministic local first-run readiness checks for Python, writable settings, recordings, Piper voices, UDP port and optional FFmpeg.
- `RUN_FIRST_RUN_CHECK.bat` and `tools/first_run_check.py`.
- Windows private-network firewall command generator; no command is executed automatically.

## Validation
- Targeted next-phase regression: 25/25 passed.
- Full suite: 725 tests passed + 383 subtests passed.
- Existing V1.3.5.0 coaching/reference/live-map behavior retained.


---

## Archived source: `V1.3.7.0_FINAL_VALIDATION_REPORT.md`

# V1.3.7.0 Final Validation Report — Speech / Radio Voice Control

## Base
V1.3.6.0 Parallel Race Intelligence Foundation supplied by the user.

## Implemented scope
- Natural concise wording for driver-requested radio responses with persistent minimal/normal/detailed verbosity.
- TTS-wide spoken unit/acronym/decimal formatting.
- Track pronunciation presets and user-overridable pronunciation dictionary for tracks, named corners and drivers.
- Persistent slow/normal/fast Piper voice-speed profiles.
- Optional installed Piper voice selection and cycling by radio.
- Expanded deterministic runtime-control synonym parser.
- Context-dependent status replies for master/child control relationships.
- Voice control routed through the same setters as the UI for:
  - Race Engineer master
  - PRE coach
  - POST coach
  - lap summary
  - positive coaching
  - race coaching
  - CORNER COACH master
  - CORNER COACH voice
  - CORNER COACH PRE
  - CORNER COACH POST
  - map gain/loss
  - gain/loss voice
  - damage coaching
  - TTS
  - PTT
  - STT
  - LLM
  - telemetry recording
- Coaching mode, verbosity, voice speed and installed voice selection by radio.
- Spoken `voice control help` summary.
- `RADIO_COMMAND_REFERENCE.md`.
- LAN `/radio-help` reference page.
- Existing `radio commands` help now points users to voice-control help.

## Control semantics verified
- UI and radio use the same receiver setter methods.
- CORNER COACH POST and G/L VOICE remain mutually exclusive.
- Child preferences survive master-off state.
- Status replies explain master suppression.
- TTS-off acknowledgement is spoken before the TTS disable action is applied.

## Automated validation
Final complete project suite:
- 735 tests passed
- 383 subtests passed
- 0 failures
- runtime: 9.22 s

Focused new V1.3.7.0 suite:
- 10 tests passed

Broad radio/control regression group before final full suite:
- 60 tests passed

## Real replay smoke validation
Recording:
- `Qual_telemetry-20260918T062108Z-c38b7cfb(2).areplay`

Result:
- 38,358 packets processed
- 1 completed lap
- best valid lap 1
- session summary generated
- coach report generated
- final analysis generated
- no Speech/Radio integration regression observed

## Notes
- Piper voice switching can only select `.onnx` voices actually installed in the project's `voices` directory.
- Driver/corner pronunciation can be overridden locally in `settings/pronunciation.json` without changing deterministic telemetry logic.
- Disabling PTT or STT by voice is intentionally allowed. If that removes the active voice-input path, re-enable it from the Control Center.


---

## Archived source: `V1.3.7.0_SPEECH_RADIO_VOICE_CONTROL_NOTES.md`

# V1.3.7.0 — Speech / Radio Voice Control

## Scope
Focused Speech/Radio polish release on top of V1.3.6.0. Core telemetry, CORNER COACH reference/compiler, map and strategy logic are unchanged.

## Implemented
- Unified deterministic radio-control parser routed before factual telemetry intents.
- Voice control for Race Engineer master, PRE, POST, LAP, POSITIVE and RACE coaching.
- Voice control for CORNER COACH master, voice, PRE, POST, map gain/loss, gain/loss voice and damage coaching.
- Voice control for TTS, PTT, STT, LLM and telemetry recording.
- Radio-selectable coaching mode and minimal/normal/detailed verbosity.
- Slow/normal/fast Piper speed profiles; persisted locally.
- Optional installed Piper voice selection/cycling; persisted locally.
- Natural concise response polishing for driver-requested radio answers.
- TTS-wide spoken unit/acronym/decimal normalization.
- Built-in track pronunciation overrides plus user `settings/pronunciation.json` overrides for tracks, named corners and driver names.
- Context-aware status replies when a master control suppresses a child preference.
- Expanded runtime-control synonyms.
- Spoken control help plus `RADIO_COMMAND_REFERENCE.md` and LAN `/radio-help` page.
- UI/radio synchronization by calling the exact receiver setters already used by Control Center / CORNER COACH buttons.

## Important behaviour
- CC POST and G/L VOICE remain mutually exclusive; voice commands obey the same rule as UI buttons.
- Child preferences are preserved while their master is off and restored when the master returns.
- Turning TTS off by radio acknowledges first, then disables speech after a short deferred interval.
- Disabling PTT or STT by radio is allowed, but further voice commands require re-enabling them from the UI if the radio path is no longer available.


---

## Archived source: `V1.3.7.1_RADIO_PARSER_RELIABILITY_HOTFIX_NOTES.md`

# V1.3.7.1 Radio Parser Reliability Hotfix

Driven by a real driver radio transcript.

## Fixed
- `help for buttons`, `radio command`, and common STT `radio comment` now open voice-control help.
- `lap code status` and `race code status` tolerate STT coach->code substitution.
- `current coach` / `carver coach` tolerate common CORNER COACH recognition errors.
- `corner coach PRE` and `corner coach POST` now resolve to child controls, not the CORNER COACH master.
- `enable/disable corner PRE and POST` changes both controls in one command.
- gain/loss `voice` misrecognized as `wife` is tolerated, including `corner GL wife`.
- Bare `disable race` remains intentionally unsupported because it is ambiguous between Race Engineer and Race Coach.

## Validation
- Transcript-driven focused tests: 14 passed.
- Broader radio/control regression group: 52 passed.


---

## Archived source: `V1.3.8.0_FINAL_VALIDATION_REPORT.md`

# V1.3.8.0 Final Validation Report — Race Strategy Integration

## Implemented scope
- Unified Race Engineer / CORNER COACH / Performance Coach arbitration.
- Critical damage, tyre/puncture/brake danger, pit-active and SC/VSC contexts override routine technique coaching.
- Active attack/defence suppresses normal technique PRE/POST and uses a short race-exit/traction focus call.
- Performance coaching resumes automatically when race context clears.
- Tyre-, fuel-, ERS-, damage- and wet-condition-aware coaching adaptation.
- Measured undercut/overcut conditional assessment.
- Per-circuit learned pit-loss evidence.
- SC and VSC pit opportunity states.
- Same-set tyre degradation and five-lap loss projection.
- Fuel-to-finish and ERS end-of-race target projections.
- Per-circuit measured damage-vs-pace evidence and wing pit threshold gate.
- Wet/dry forecast transition + confidence and tyre-transition trigger.
- Opponent tyre-age/compound inference where field telemetry permits.
- Dry-compound observation, wet exemption context and serviceable-penalty/race-rule status.
- Strategy computations throttled to strategy-relevant packet families / bounded cadence to protect live and replay latency.

## Replay-derived validation
### Full CLI replay passes
- Qualifying: PASS — 38,358 packets processed; 1 completed lap; report + analysis JSON generated.
- Shanghai: PASS — 30,945 packets processed; 1 completed lap; report + analysis JSON generated.

### Strategy-focused production-path replay validation
Long Race and Time Trial CLI runs exceed the execution wrapper's single-command limit. To validate strategy without discarding evidence, `tools/strategy_replay_validation.py` feeds strategy-relevant packets through the normal `RaceStateReceiver.process_packet()` path, preserving packet order and original timestamps while sampling redundant high-frequency frames.

- Race: PASS — source 81,159 packets; 14,490 strategy-relevant packets processed; 4 measured laps retained; no strategy exception.
  - Track: Melbourne; current lap 5.
  - Tyre degradation: 0.343 s/lap; projected five-lap loss 1.715 s.
  - Fuel margin: +0.83 laps; target `surplus`.
  - ERS: 47.8%; projected end state 95.6%; target `deployment_available`.
  - Wing damage: 40%; measured wing pit threshold remained `unavailable` because matched damage pace-loss evidence was not present.
  - Weather: stable dry; EA forecast confidence `perfect`; 10-minute rain percentage 21%.
  - Final race context: `critical` from close combat + severe damage; technique coaching disabled.
  - Observed context levels across replay: performance, combat, critical.
  - Opponent inference was seen as `same_or_unknown_strategy` when telemetry permitted and `unavailable` when it did not.
  - No pit-loss sample existed in this short race, therefore undercut/overcut stayed unavailable rather than fabricated.
- Time Trial: PASS — source 92,262 packets; 16,728 strategy-relevant packets processed; 7 measured laps retained; no race strategy/arbitration object leaked into Time Trial.

## Regression testing
- Focused post-performance-fix strategy/coaching tests: 22 passed.
- Full project suite: 745 passed + 383 subtests passed.
- Failures: 0.
- One legacy regression was intentionally updated: close combat now blocks Race PRE technique coaching, matching the V1.3.8.0 requirement.

## Important evidence rules
A strategy output is allowed to remain `unavailable` when the recording does not contain the required measured evidence. In particular, circuit pit loss, undercut/overcut and damage-vs-pace results are never synthesized from constants merely to fill a field.

## Release assessment
The requested Race Engineer + Performance Coach integration / advanced strategy scope is implemented and regression-clean. Real live-race validation with an actual pit stop, SC/VSC occurrence, changing weather and matched pre/post-damage laps will provide additional evidence for those conditional branches, but no code path is left intentionally unimplemented in this requested scope.


---

## Archived source: `V1.3.8.0_RACE_STRATEGY_CHECKPOINT_REPORT.md`

# V1.3.8.0 Race Strategy Integration — Continuation Checkpoint

## Why this is a checkpoint
The requested Time Trial replay validation exceeded the execution limit while processing the supplied 92k-packet recording. Per the user instruction, this source tree was preserved immediately so no implementation work is lost.

## Implemented and persisted in this checkpoint
- Unified Race Engineer / Performance Coach message arbitration.
- Critical damage suppresses routine coaching.
- Pit-active / Safety Car / VSC race-control context suppresses routine coaching.
- Tyre wear, puncture and brake-temperature danger outrank technique coaching.
- Close attack/defence suppresses CORNER COACH / Performance Coach technique calls.
- One short race-exit/traction focus message is generated when entering combat.
- Automatic performance-coaching resume message when context returns to clear running.
- Tyre-condition-aware, fuel-save, ERS-low, damage-aware and wet-condition adaptations applied to allowed technique calls.
- Advanced strategy assessment: measured circuit pit loss, same-set tyre degradation, 5-lap degradation projection, fuel-to-finish margin/target, ERS end projection/target, measured damage pace loss, front-wing pit threshold, weather transition/confidence, wet/dry tyre transition, opponent tyre-age/compound inference, undercut and overcut condition gates, SC/VSC service opportunity, mandatory-compound observation, service-penalty state and pit-window state.
- StrategyEvidenceLearner learns pit-affected lap loss versus clean local baseline and matched damage pace cost.
- Pit-loss and damage evidence are persisted per circuit in settings/strategy_history.json and never mixed between tracks.
- Current dry compounds are recorded for mandatory-compound observation.
- Receiver integration publishes advanced_strategy and race_message_arbitration into RaceState.extended.
- Advanced enrichment errors are isolated so telemetry processing cannot be blocked by the strategy layer.

## Validation completed before checkpoint
- New V1.3.8.0 strategy/arbitration tests: PASS.
- V1.3.6 strategy foundation tests: PASS.
- Integrated coaching suite regression: PASS.
- Existing race-context regression: PASS.
- Combined focused regression: 29 passed, 0 failed.

## Replay validation status
- Time Trial replay was started with the supplied TimeTrial_telemetry-20260917T121801Z-940696c8.areplay.
- It progressed through multiple session summaries/coach reports and CORNER COACH validation traces without a Python exception.
- The command itself exceeded the execution time limit before replay completion, so it is NOT marked as a completed replay validation.
- Qualifying, Race and Shanghai replay validation are still pending for the next continuation.

## Still required before final V1.3.8.0 release
- Complete each supplied replay separately without one long blocking command (or use replay-indexed/limited validation batches).
- Add replay-derived assertions for advanced_strategy on Race recording.
- Run the complete project regression suite.
- Audit requested feature list against implementation and close any gaps discovered.
- Final release notes, roadmap update, ZIP integrity and hash.


---

## Archived source: `V1.3.8.0_RACE_STRATEGY_INTEGRATION_NOTES.md`

# V1.3.8.0 Race Strategy Integration

This release completes the requested race-context/coaching arbitration and deterministic advanced strategy phase. All strategy decisions are evidence-gated; missing measured evidence produces `unavailable` rather than an invented recommendation.

Key reliability fix during replay validation: strategy evidence is updated only on relevant packet families, full strategy recomputation is capped at 4 Hz, and message arbitration remains immediate for generated messages. This removed unnecessary high-frequency strategy work while preserving safety ownership.


---

## Archived source: `V1.3.8.0_REPLAY_VALIDATION_CHECKPOINT_2.md`

# V1.3.8.0 Replay Validation Checkpoint 2

## Persisted source state
- Based on V1.3.8.0 Race Strategy Integration Checkpoint.
- No source rollback.
- Strategy/arbitration implementation remains intact.

## Replay validation completed
- Qualifying: PASS — 38,358 packets processed; 1 completed lap; best valid lap 1; coach report + analysis JSON generated.
- Shanghai: PASS — 30,945 packets processed; 1 completed lap; best valid lap 2; coach report + analysis JSON generated.

## Race replay
- Full Race replay was started in --replay-fast mode.
- The tool execution limit was reached before the command returned.
- This is not marked as a failed replay and not marked as a completed validation.
- Next continuation step: validate Race via smaller deterministic chunks / indexed replay inspection, then validate Time Trial similarly if needed.

## Prior focused validation
- Combined strategy/arbitration regression: 29 passed, 0 failed.

## Remaining before final release
- Race replay-derived advanced_strategy assertions.
- Time Trial replay completion or chunked validation.
- Full project regression suite.
- Requested feature audit / strategy gap closure.
- Final release notes, roadmap update, ZIP integrity, hash.


---

## Archived source: `V1.3.8.0_REPLAY_VALIDATION_CHECKPOINT_3.md`

# V1.3.8.0 Replay Validation Checkpoint 3

## New persisted fix since Checkpoint 2
- Advanced strategy evidence learning is now packet-family driven (session/lap/status/damage/tyre) instead of running on every telemetry packet.
- Full advanced strategy recomputation is capped at 4 Hz.
- Message arbitration remains immediate whenever a candidate message exists.
- Race-context transition evaluation is capped at 10 Hz on relevant packets when there is no candidate message.
- This fixes a replay/live-path performance regression without weakening critical/combat suppression.

## Focused validation after optimization
- Strategy / race-intelligence / integrated-coaching regression: 22 passed, 0 failed.

## Completed replay evidence carried forward
- Qualifying: PASS — 38,358 packets, 1 completed lap.
- Shanghai: PASS — 30,945 packets, 1 completed lap.

## Race replay
- Re-attempted after optimization in --replay-fast mode.
- Single-command execution still exceeded the tool execution limit before returning.
- Not marked failed; not marked complete.
- Next: use packet-chunk/checkpoint inspection or replay-index validation that avoids a single uninterrupted CLI command.

## Remaining before final release
- Race replay-derived advanced_strategy assertions.
- Time Trial replay completion/chunked validation.
- Full project regression suite.
- Requested feature audit and gap closure.
- Final packaging / roadmap / validation report / hash.


---

## Archived source: `V1.3.8.1_DAMAGE_AWARE_COACHING_HOTFIX_NOTES.md`

# V1.3.8.1 Damage-Aware Coaching Hotfix

## Problem reproduced
With DMG COACH enabled, moderate wing damage (20-39.9%) kept CORNER COACH active as intended, but the arbitration layer appended `allow for the damage` to every coaching message. This produced repetitive and misleading calls even on matched/gained corners and on losses with a specific technique diagnosis.

## Fix
- DMG COACH override behavior is unchanged: coaching can continue on damaged laps when explicitly enabled.
- Moderate damage alone no longer adds a generic damage suffix.
- Damage wording now requires measured `measured_damage_pace_loss_s >= 0.50 s`.
- Damage wording is suppressed for matched/gained corners.
- Damage wording is suppressed when the message already has a specific diagnosis such as braking, throttle pickup, coasting, steering, apex, entry/minimum/exit speed, gear, lift, or traction.
- When supported, generic loss/advice can say `damage is costing pace` rather than the vague `allow for the damage`.

## Validation
- Focused damage/override tests: 17 passed.
- Full regression: 747 tests passed + 383 subtests passed, 0 failures.


---

## Archived source: `V1.3.8.2_COMBAT_HYSTERESIS_HOTFIX_NOTES.md`

# V1.3.8.2 Combat Hysteresis Hotfix

## Problem reproduced from the recorded race
The race-context gate used the same close-car threshold for both entering and leaving combat. Gap jitter around the boundary caused repeated `Car close` / `Clear again` calls and unnecessary coaching state changes.

## Fix
- Combat entry remains immediate at <1.2 s ahead or <1.0 s behind.
- While combat is active, release uses wider thresholds: 1.8 s ahead / 1.5 s behind.
- Combat remains active for at least 4 s after entry.
- The car must remain beyond the release threshold for 3 continuous seconds before Performance Coach resumes.
- Re-entering the release zone resets the clear timer.
- `Car close` and `Clear again` announcements have independent 15 s repeat cooldowns.
- Critical damage and race-control states bypass the debounce immediately.
- Technique coaching remains suppressed throughout the stabilised combat state.
- V1.3.8.1 damage-aware coaching fix is preserved.

## Validation
- Focused combat/damage/strategy regression: 28/28 passed.
- Full suite: 751 tests + 383 subtests passed, 0 failures.


---

## Archived source: `V1.3.9.0_FINAL_VALIDATION_REPORT.md`

# V1.3.9.0 Final Validation Report — Reference Ecosystem

## Automated regression
- Full project suite: **757 passed + 383 subtests passed**
- Failures: **0**
- Focused Reference Ecosystem tests: **6/6 passed**
- Extended reference/compiler/selector regression group: **40/40 passed**

## Real stored-reference validation
Validated against the supplied `References.zip` without rebuilding or recapturing any reference.

- **MELBOURNE**: raw validator PASS; authenticated compiled model PASS; fingerprint match PASS; portable export/inspect/install PASS; quality A/92.
- **AUSTRIA**: legacy raw source fails the newer strict speed/time-distance validator, but the existing compiled model is accepted and fingerprint-matched to that exact raw source. Portable export/inspect/install PASS using compiled-model authority. No rebuild performed.
- **SHANGHAI**: same legacy-source case as Austria; compiled model accepted and fingerprint-matched. Portable export/inspect/install PASS. No rebuild performed.

## Compatibility behavior
- Known track ID mismatch: BLOCK.
- Known track-length mismatch beyond tolerance: BLOCK.
- Known game-year mismatch: BLOCK.
- Known formula mismatch: BLOCK.
- Known equal-performance mismatch: BLOCK.
- Team mismatch: BLOCK only when both contexts are explicitly unequal-performance.
- Assists/setup/weather/tyre/fuel differences: WARN, do not fabricate incompatibility.
- Unknown metadata: explicitly reported as unknown; not guessed.

## Package integrity
- SHA-256 per payload file.
- Raw-reference fingerprint bound to the package manifest.
- Optional compiled model accepted only when compiler validation passes and fingerprint matches the raw source.
- Imported references never overwrite existing references.

## UI
- Control Center `IMPORT REF`: validates and installs portable ZIP packages.
- Control Center `EXPORT REF`: exports the selected stored reference.
- Imported packages appear in the normal Reference Lap selector with quality/provenance.

## Scope boundary
Hosted community reference packs and curated online driver packs remain deferred under the roadmap's local/personal product scope.


---

## Archived source: `V1.3.9.0_REFERENCE_ECOSYSTEM_NOTES.md`

# V1.3.9.0 Reference Ecosystem

## Implemented
- Portable friend reference import/export using checksummed ZIP packages.
- Formal V2 metadata manifest for game, track, car/team, driver, session, assists, setup, conditions, tyre and fuel fields.
- Deterministic compatibility report with blockers, warnings, matches and unknown metadata.
- Track/game/formula/equal-performance hard compatibility gates when both sides are known.
- Team mismatch is only a hard blocker for known unequal-performance contexts.
- Assists/setup/weather/tyre/fuel mismatches are surfaced as warnings instead of silently changing coaching validity.
- Reference quality grade/score layered on the existing strict compiler validator.
- SHA-256 checksums and raw-reference fingerprint validation.
- Legacy raw references are preserved when their sibling compiled model is current, accepted and fingerprint-authenticated.
- Control Center IMPORT REF and EXPORT REF actions.
- Imported packages install under `references/imported/<TRACK>/<PACKAGE_ID>/` and never overwrite existing local references.
- Stored reference selector now discovers imported packages and shows quality grade/provenance.
- Newly captured TT rivals retain packet format and game version identity for future compatibility checks.

## Preserved behavior
- Existing Melbourne/Austria/Shanghai references are not rebuilt or recaptured.
- Existing CORNER COACH compiled-model/runtime loading remains authoritative.
- Session-best and rival-reference workflows remain unchanged.
- Hosted community/curated reference services remain deferred by the active local/personal product scope.


---

## Archived source: `V1.4.0.0_FINAL_VALIDATION_REPORT.md`

# V1.4.0.0 Final Validation Report — Replay / Session Analysis

## Automated regression

- Full pytest suite: **765 passed**
- Subtests: **383 passed**
- Failures: **0**
- New Replay / Session Analysis focused tests: **8 passed**
- Existing replay/dashboard/session targeted regression before full suite: **38 passed**
- `python -m src.main --help`: **PASS**

## Supplied recording validation

### Time Trial
- Source packets: **92,262**
- Session UID: **784557008734475799**
- Track ID: **17**
- Indexed laps: **8**
- Best eligible lap: **3**
- Best lap with usable trace: **3**
- Navigation samples: **10,440**
- Telemetry trace samples: **9,973**
- Coaching timeline events discovered: **167**

### Qualifying
- Source packets: **38,358**
- Session UID: **0** (legacy recording)
- Track ID: **0**
- Indexed laps: **2**
- Best lap / best trace lap: **1**
- Navigation samples: **4,055**
- Telemetry trace samples: **4,051**
- No authoritative legacy CORNER timeline was associated; corner navigation falls back to installed trusted Melbourne reference geometry.

### Race
- Source packets: **81,159**
- Session UID: **0** (legacy recording)
- Track ID: **0**
- Indexed laps: **5**
- Best lap / best trace lap: **3**
- Navigation samples: **9,228**
- Telemetry trace samples: **8,276**
- No authoritative legacy CORNER timeline was associated; corner navigation falls back to installed trusted Melbourne reference geometry.

### Shanghai
- Source packets: **30,945**
- Session UID: **840577582140208983**
- Track ID: **2**
- Indexed laps: **3**
- Nominal best lap: **1**
- Best lap with a usable telemetry trace: **2**
- Navigation samples: **3,516**
- Telemetry trace samples: **3,443**
- Associated CORNER timeline discovered and missing corner navigation is filled from trusted Shanghai reference geometry.

## Comparison validation

- Qualifying vs Race: same Track ID 0, comparison accepted.
- Comparison grid: **528 x 10 m points**.
- Qualifying selected lap: **1**.
- Race selected lap: **3**.
- Measured best-lap difference in these recordings: **-11.198 s** (Race minus Qualifying).
- Time Trial Track ID 17 vs Race Track ID 0: **correctly rejected** as a cross-track comparison.

## Data integrity rules

- Replay index is invalidated when recording size/mtime changes.
- Lap/session comparisons use measured samples only.
- Missing data is not synthesized.
- Corner jump uses actual CORNER COACH timeline positions where available; otherwise trusted installed reference-zone distances are used.
- New live recordings receive explicit report/validation/CORNER artifact linkage.
- Existing recording format is not modified.

## Result

**PASS — Replay / Analysis Workflow is complete for the local/personal F1 scope.**


---

## Archived source: `V1.4.0.0_REPLAY_SESSION_ANALYSIS_NOTES.md`

# V1.4.0.0 Replay / Session Analysis

This release closes the local Replay / Analysis Workflow roadmap block without changing the deterministic telemetry decoder, CORNER COACH diagnosis, reference compiler, or Race/Strategy decision logic.

## Added

- Cached `.areplay` analysis index (`analysis/replay_index/`)
  - session UID and game/header identity
  - packet count and deterministic packet navigation positions
  - lap boundaries, lap validity and measured lap times
  - distance-aligned telemetry traces
  - automatic report/validation/CORNER trace associations
- `/sessions` upgraded from a metadata list to a replay-analysis workspace.
- Search/filter sessions and preserve rename/tag/favorite/archive metadata.
- Selected-lap comparison on a shared 10 m distance grid.
- Same-track two-session comparison.
- Speed, brake, throttle, gear, ERS and elapsed-time delta comparison traces.
- World X/Z traces retained for racing-line comparison data.
- Coaching-event timeline from CORNER COACH validation records.
- Direct jump to a selected corner through the existing `ReplayController.seek()` path.
- Trusted-reference geometry fallback for legacy/no-UID recordings without an associated CORNER trace.
- Explicit recorder -> coach report -> validation -> CORNER trace association for newly recorded sessions.
- Legacy session-UID discovery remains available when an explicit association does not exist.
- Cross-track and cross-formula session comparisons are rejected rather than producing misleading results.

## No fabricated data

Missing telemetry channels remain unavailable. Session comparison is distance-aligned only when compatible. Corner navigation uses observed CORNER COACH events or installed trusted reference geometry; it never invents corner positions.

## Compatibility

Existing ARERPL01 recordings remain unchanged. The index is a derived cache and is automatically invalidated when the source recording size or modification time changes.


---

## Archived source: `V1.4.0.1_FINAL_VALIDATION_REPORT.md`

# V1.4.0.1 Final Validation Report

- Full pytest suite: **769 passed**
- unittest-style subtests: **383 passed**
- Failures: **0**
- Targeted pit/session/transcript/CORNER validation suite: **47/47 passed**
- Syntax compilation: PASS

## Confirmed behavior
1. Session Best can improve during a session without creating a new validation file; a `reference_update` record preserves the exact new fingerprint/geometry.
2. New session UID creates a clean runtime transition and persistent session marker.
3. Practice/Qualifying/Race transcript records are individually preserved plus one continuous weekend JSONL.
4. EA game pit-window ideal/latest laps are preserved in RaceState.
5. Current lap inside the reported game window produces at least `box_soon`; latest window lap produces `box_now`, preventing the previous contradictory routine stay-out call.


---

## Archived source: `V1.4.0.1_WEEKEND_TRANSCRIPT_PIT_WINDOW_HOTFIX_NOTES.md`

# V1.4.0.1 — Weekend Transition + Transcript + Pit Window Hotfix

## Changes
- Session Best remains dynamic by design, but reference improvements are recorded as `reference_update` inside the same CORNER COACH validation file instead of splitting the run.
- Session UID changes explicitly reset session-specific live coach, CORNER COACH runtime, race-context hysteresis, finish/summary state, while preserving user controls/reference preference.
- Added asynchronous persistent validation transcripts under `analysis/transcripts/`:
  - `RACE_ENGINEER_<track>_<session>_<uid>_<stamp>.txt`
  - `CORNER_COACH_TRANSCRIPT_<track>_<session>_<uid>_<stamp>.txt`
  - `VALIDATION_TRANSCRIPT_<track>_<session>_<uid>_<stamp>.jsonl`
  - `WEEKEND_TRANSCRIPT_<track>_<stamp>.jsonl` with Practice/Qualifying/Race session markers.
- Race Engineer and CORNER COACH message submission and delivery outcomes are logged asynchronously; driver STT is included.
- EA `m_pitStopWindowIdealLap` / `m_pitStopWindowLatestLap` are now copied into RaceState and used by deterministic pit strategy.
- Inside the game pit window the engineer cannot issue a contradictory routine `stay_out`; reaching the latest lap is `box_now`.

## Validation
- New/targeted tests: 47 passed.
- Full regression: 769 passed + 383 subtests, 0 failures.


---

## Archived source: `V1.5.0.0_FINAL_VALIDATION_REPORT.md`

# V1.5.0.0 Final Validation Report

## Result

- Full regression: **775 tests passed**
- Legacy deterministic subtests: **383 passed**
- Failures: **0**
- Focused pre-release/coaching/strategy/weekend regression: **57/57 passed** before the full-suite gate
- Python compileall: PASS
- Consolidated settings/validation UI smoke: PASS

## Supplied replay/index evidence

Direct replay-index benchmark using production `ReplayAnalysisService`:

| Recording | Index time | Indexed laps | Result |
|---|---:|---:|---|
| Qualifying Melbourne | 1.557 s | 2 | PASS |
| Race Melbourne | 3.489 s | 5 | PASS |
| Shanghai | 1.413 s | 3 | PASS |
| Time Trial | 3.851 s | 8 | PASS |

The indexer reads the actual packet streams and does not run TTS/UI, so it is appropriate for repeatable file-level benchmark validation.

## Austria weekend CORNER trace evidence

Five supplied Austria traces were parsed through the formal validator:

- UID 11343293348198147149 / trace 154148Z: 1,128 rows — PASS
- UID 11343293348198147149 / trace 154501Z: 746 rows — PASS
- UID 6445361529359574319 / trace 154848Z: 14 rows — PASS
- UID 4689088409239632245 / trace 155247Z: 554 rows — PASS
- UID 4689088409239632245 / trace 155400Z: 2,667 rows — PASS

No structural lap-regression faults were found by the validator. Session Best reference updates are allowed and remain lap-boundary/session-evidence events rather than being treated as accidental reference changes.

## Formal validation instrumentation implemented

- telemetry -> decode -> state -> decision -> dispatch latency statistics
- TTS queue and audio-start latency statistics
- per-session CPU time / single-core-equivalent utilization
- peak RSS memory
- per-packet-family packet counts
- inferred frame gaps, duplicates, out-of-order frames, maximum gap
- per-session reset after previous-session evidence finalization
- deterministic replay/live signature comparison helper
- transcript, CORNER trace and validation-bundle validators

## Automatic validation bundle

Per-session ZIP and weekend aggregate ZIP include when available:

- Race Engineer transcript
- CORNER COACH transcript
- structured validation transcript
- CORNER COACH validation JSONL
- strategy decision history
- pit decision history including EA ideal/latest pit window
- active reference history/fingerprint changes
- warnings/errors
- latency + CPU/RAM/packet-continuity metrics
- replay index
- recording pointer, byte size and SHA-256

Raw `.areplay` recordings are **never embedded** in the bundle.

## Coaching hardening

Validated changes:

- PRE useful-time window: 1.25–12.5 s
- PRE distance sanity ceiling: 525 m
- brake/steering blocker retained in missed-PRE diagnostics
- pit-lane and out-lap technique coaching suppressed
- first flying lap automatically re-armed
- repeated identical POST diagnosis shortened with periodic full reminder
- stale circular PRE after replay seek regression caught and fixed by full suite

## Strategy hardening

- normal / SC / VSC measured pit-cycle evidence stored separately
- observed opponent pit-entry/pit-exit/compound changes only
- measured matched-stop gap-before/gap-after effect
- EA pit-window status (before/open/latest-or-later)
- mandatory dry-compound urgency field
- wet/dry forecast transition remains telemetry/forecast-driven
- damage pace attribution remains measured-evidence driven
- undercut/overcut evidence remains conditional/measured, not predictive

## UI/usability hardening

New local `/settings` page provides:

- first-run/readiness state
- audio input/output inventory
- reference inventory
- transcript viewer
- validation bundle status
- diagnostics bundle creation
- configuration export/import
- layout reset
- settings reset

Existing dashboard, `/sessions`, replay comparison and `/coach` remain available.

## Scenarios intentionally not falsely claimed as live-verified

The following require real event evidence that is not present in the sandbox:

1. the user's 500+ MB Austria full-weekend recording at packet level;
2. an actual wet -> dry or dry -> wet race transition;
3. an actual Safety Car/VSC pit cycle from the user's current V1.5.0.0 build;
4. final Windows DPI/multi-monitor behavior on the user's physical monitors.

The release now automatically captures the evidence needed for those cases in the validation bundle. Synthetic/unit coverage exists, but this report does not label synthetic coverage as a live validation.


---

## Archived source: `V1.5.0.0_FORMAL_VALIDATION_EVIDENCE.md`

# V1.5.0.0 Formal Validation Report

- Checks: 9
- Passed: 9
- Failed/unverified: 0

## PASS — Replay index Qual_telemetry-20260918T062108Z-c38b7cfb.areplay
```json
{
  "ok": true,
  "elapsed_s": 1.5572,
  "laps": 2,
  "track_id": null,
  "session_uid": 0,
  "name": "Replay index Qual_telemetry-20260918T062108Z-c38b7cfb.areplay"
}
```

## PASS — Replay index Race_telemetry-20260918T064535Z-d7412ccc.areplay
```json
{
  "ok": true,
  "elapsed_s": 3.489,
  "laps": 5,
  "track_id": null,
  "session_uid": 0,
  "name": "Replay index Race_telemetry-20260918T064535Z-d7412ccc.areplay"
}
```

## PASS — Replay index SHANGHAI_telemetry-20260922T153410Z-de96f122.areplay
```json
{
  "ok": true,
  "elapsed_s": 1.4134,
  "laps": 3,
  "track_id": null,
  "session_uid": 840577582140208983,
  "name": "Replay index SHANGHAI_telemetry-20260922T153410Z-de96f122.areplay"
}
```

## PASS — Replay index TimeTrial_telemetry-20260917T121801Z-940696c8.areplay
```json
{
  "ok": true,
  "elapsed_s": 3.851,
  "laps": 8,
  "track_id": null,
  "session_uid": 784557008734475799,
  "name": "Replay index TimeTrial_telemetry-20260917T121801Z-940696c8.areplay"
}
```

## PASS — Austria trace CORNER_COACH_AUSTRIA_11343293348198147149_20260925T154148Z.jsonl
```json
{
  "ok": true,
  "rows": 1128,
  "event_counts": {
    "run_start": 1,
    "lap_start": 2,
    "coach_config": 2,
    "sample": 866,
    "pre_emit": 20,
    "radio_submit": 21,
    "audio_start": 20,
    "radio_delivery": 32,
    "zone_enter": 20,
    "phase_change": 70,
    "physical_corner_enter": 20,
    "zone_exit": 20,
    "physical_corner_exit": 20,
    "post_emit": 1,
    "coach_config_change": 1,
    "pre_blocked": 10,
    "lap_summary": 2
  },
  "reference_fingerprints": [
    "88d75f45786d52899fd4e9bd2f827dcb48116f82715718f72d54c343db112851"
  ],
  "problems": [],
  "name": "Austria trace CORNER_COACH_AUSTRIA_11343293348198147149_20260925T154148Z.jsonl"
}
```

## PASS — Austria trace CORNER_COACH_AUSTRIA_11343293348198147149_20260925T154501Z.jsonl
```json
{
  "ok": true,
  "rows": 746,
  "event_counts": {
    "run_start": 1,
    "lap_start": 2,
    "coach_config": 2,
    "sample": 577,
    "pre_emit": 15,
    "radio_submit": 15,
    "audio_start": 15,
    "radio_delivery": 23,
    "zone_enter": 13,
    "phase_change": 38,
    "physical_corner_enter": 13,
    "zone_exit": 13,
    "physical_corner_exit": 13,
    "pre_blocked": 3,
    "lap_summary": 2,
    "telemetry_discontinuity": 1
  },
  "reference_fingerprints": [
    "bcc3b76d8249507d3f29a1b153436d5c5649e9194b85ed4ebf01ef81900b8581"
  ],
  "problems": [],
  "name": "Austria trace CORNER_COACH_AUSTRIA_11343293348198147149_20260925T154501Z.jsonl"
}
```

## PASS — Austria trace CORNER_COACH_AUSTRIA_4689088409239632245_20260925T155247Z.jsonl
```json
{
  "ok": true,
  "rows": 554,
  "event_counts": {
    "run_start": 1,
    "lap_start": 1,
    "coach_config": 1,
    "zone_enter": 10,
    "physical_corner_enter": 10,
    "phase_change": 29,
    "sample": 433,
    "pre_missed": 1,
    "pre_emit": 9,
    "radio_submit": 11,
    "audio_start": 9,
    "radio_delivery": 15,
    "zone_exit": 10,
    "physical_corner_exit": 10,
    "pre_emit_next_lap": 2,
    "pre_blocked": 1,
    "lap_summary": 1
  },
  "reference_fingerprints": [
    "64ce2a248041c526b5bfa69c227320ec9c0ef387a51f383a277f7d4ce83d3d5d"
  ],
  "problems": [],
  "name": "Austria trace CORNER_COACH_AUSTRIA_4689088409239632245_20260925T155247Z.jsonl"
}
```

## PASS — Austria trace CORNER_COACH_AUSTRIA_4689088409239632245_20260925T155400Z.jsonl
```json
{
  "ok": true,
  "rows": 2667,
  "event_counts": {
    "run_start": 1,
    "lap_start": 19,
    "coach_config": 19,
    "sample": 1169,
    "pre_emit": 161,
    "radio_submit": 153,
    "zone_enter": 156,
    "phase_change": 216,
    "physical_corner_enter": 132,
    "radio_delivery": 190,
    "zone_exit": 152,
    "physical_corner_exit": 128,
    "audio_start": 86,
    "pre_blocked": 39,
    "pre_emit_next_lap": 18,
    "lap_summary": 19,
    "pre_missed": 9
  },
  "reference_fingerprints": [
    "b4b3f75d660849e291d4c757fcaec4646f3bc8f10e1de7b3ecd393329aea5577"
  ],
  "problems": [],
  "name": "Austria trace CORNER_COACH_AUSTRIA_4689088409239632245_20260925T155400Z.jsonl"
}
```

## PASS — Austria trace CORNER_COACH_AUSTRIA_6445361529359574319_20260925T154848Z.jsonl
```json
{
  "ok": true,
  "rows": 14,
  "event_counts": {
    "run_start": 1,
    "lap_start": 1,
    "coach_config": 1,
    "sample": 1,
    "pre_emit": 2,
    "radio_submit": 2,
    "radio_delivery": 3,
    "audio_start": 2,
    "lap_summary": 1
  },
  "reference_fingerprints": [
    "13aca215efb78cdc41e2d3005221ca2a7dad85f818b696d1d6a33eb4358f66da"
  ],
  "problems": [],
  "name": "Austria trace CORNER_COACH_AUSTRIA_6445361529359574319_20260925T154848Z.jsonl"
}
```


---

## Archived source: `V1.5.0.0_PRE_RELEASE_HARDENING_CHECKPOINT_REPORT.md`

# V1.5.0.0 Pre-Release Hardening Checkpoint

Persisted before the strategy/UI/final-validation phase.

Implemented so far:
- runtime CPU/RAM/packet continuity benchmark monitor
- automatic validation bundle manager with transcript/CORNER/decision/reference/performance artifacts
- recording pointer + SHA256 only (large .areplay files are never embedded)
- session/weekend transcript decision history support
- CORNER PRE timing refinement and blocker-aware miss classification
- pit-lane/out-lap coaching suppression + first flying-lap re-arm
- long-session repeated POST wording memory
- enhanced strategy-learning evidence foundation for SC/VSC pit cycles and observed opponent stop/compound changes

Validated checkpoint subsets:
- V1.3.8/V1.4.0.1 strategy/weekend: 12 passed
- CORNER/session-transition focused: 22 passed

Remaining in this phase:
- advanced strategy evidence exposure/rule refinements
- formal validator + scenario/benchmark report
- settings/device/reference/transcript/validation/diagnostics UI
- full regression + real-recording/trace validation


---

## Archived source: `V1.5.0.0_PRE_RELEASE_HARDENING_NOTES.md`

# V1.5.0.0 — Pre-Release Hardening

This release closes the requested formal-validation, validation-bundle, coaching-refinement, strategy-refinement and UI/usability hardening blocks without changing the deterministic fact-only policy.

## Validation / benchmark
- Always-on low-overhead telemetry pipeline latency statistics.
- Per-session CPU time, peak RSS, packet-family counts, inferred frame gaps, duplicate and out-of-order frames.
- Metrics reset only after the prior session evidence bundle is finalized.
- Deterministic replay/live signature comparison helper.
- Formal validators for CORNER JSONL, transcripts and validation bundles.

## Automatic validation bundles
- Per-session `VALIDATION_BUNDLE_*.zip` and weekend aggregate ZIP.
- Includes Race Engineer/CORNER transcripts, CORNER validation, strategy and pit decisions, reference history, warning/error history, latency/runtime metrics and replay index when available.
- `.areplay` files are never embedded; only source path, byte size and SHA-256 are stored.

## Coaching
- PRE useful window extended to 12.5 s with 1.25 s minimum safe airtime.
- PRE miss diagnostics retain whether braking/steering blocked the call instead of hiding every miss as `target_passed_without_emit`.
- Pit lane and out-lap technique coaching suppressed; first flying lap re-arms automatically.
- Repeated identical POST diagnoses become compact while periodic full wording is retained.

## Strategy
- Normal, Safety Car and VSC pit-cycle measurements stored separately.
- Observed opponent pit entry/exit and compound changes only; no guessed opponent strategy.
- Matched two-stop sequences expose measured gap-before/gap-after effect.
- Advanced strategy exposes EA game pit window, SC/VSC measured losses and mandatory-compound urgency.

## UI / usability
- New local `/settings` page: readiness/devices, references, transcript viewer, validation bundle status, diagnostics bundle button, config export/import, layout/settings reset.
- Existing `/sessions`, `/coach` and dashboard remain unchanged.


---

## Archived source: `V1.6.0.0_FINAL_VALIDATION_REPORT.md`

# Race Engineer V1.6.0.0 — Final Validation Report

## Scope
Windows productization / release readiness on top of V1.5.0.0 Pre-Release Hardening.

## Regression
- Full pytest suite: **786 passed**
- unittest subtests: **383 passed**
- Failures: **0**
- Python compileall: PASS
- Product launcher CLI smoke: PASS
- Windows release static validator: PASS

## Productization validated in this environment
- persistent product settings and schema migration
- graphical first-run setup page and API
- saved UDP port reaches the real UDP receiver path
- audio/microphone/HID/COM discovery is failure-safe
- PTT HID identity and logical button persistence
- LAN QR SVG generation is fully local/offline
- setup/settings mutations restricted to localhost
- explicit firewall action with Windows/UAC path
- opt-in update-check logic (no auto-update)
- crash-log generation and diagnostic inclusion
- upgrade user-data backup
- configuration export includes settings, maps, references and PTT mapping
- installer definition preserves mutable user data
- portable/package build definitions
- display/DPI/multi-monitor diagnostic path

## Windows-target validation still required
This execution environment is not Windows. Therefore the following are **implemented but not falsely claimed as compiled/live-verified here**:
- PyInstaller creation of the actual Windows `RaceEngineer.exe`
- Inno Setup compilation of the `.exe` installer
- UAC/firewall rule execution on Windows
- physical audio/HID/COM device selection on the user's PC
- actual multi-monitor/DPI rendering on Windows
- installer upgrade/uninstall behavior on a Windows filesystem

The included `build_release.ps1` performs the target-machine EXE + portable ZIP build and invokes Inno Setup when `ISCC.exe` is installed.


---

## Archived source: `V1.6.0.0_PRODUCTIZATION_CHECKPOINT_REPORT.md`

# V1.6.0.0 Windows Productization — Checkpoint

Checkpoint scope completed:
- packaged Windows launcher with crash handler and product settings
- persistent `settings/product.json` schema/migration
- graphical local first-run `/setup` wizard
- audio input/output selection
- PTT enable/button/HID identity binding UI
- wheel Receiver COM selection
- overlay + LAN dashboard startup settings
- offline LAN QR code endpoint
- local-only mutation guard for setup/settings APIs
- opt-in Windows Private firewall rule action with UAC fallback
- opt-in GitHub update checker (no automatic download/install)
- crash log capture under `logs/crash/`
- diagnostics bundle includes product settings/update state/recent crashes
- PyInstaller one-folder spec
- portable ZIP release script
- Inno Setup per-user installer definition preserving settings/references/recordings

Focused regression at checkpoint: 26 passed, 0 failed.

Remaining before final:
- release/version metadata cleanup
- upgrade migration/backup hardening
- DPI/multi-monitor startup validation helpers
- packaged-resource/readiness improvements
- installer/portable static validation
- full regression suite
- final release notes/report/package


---

## Archived source: `V1.6.0.0_WINDOWS_PRODUCTIZATION_NOTES.md`

# V1.6.0.0 — Windows Productization / Release Readiness

This release implements the remaining local Windows productization block on top of V1.5.0.0.

## Added
- dedicated packaged launcher (`src.product_launcher`)
- persistent product/device settings (`settings/product.json`)
- first-run `/setup` wizard
- saved F1 UDP port wired to the actual UDP receiver
- audio output and microphone selection
- PTT HID device identity + logical-button binding
- GamePad Pro Receiver COM discovery/selection
- native-overlay and LAN-dashboard startup controls
- offline LAN-dashboard QR code
- explicit localhost-only Windows Private firewall-rule action with UAC fallback
- opt-in release update checker (check only; no automatic install)
- unhandled main/thread crash reports under `logs/crash/`
- upgrade backup of local settings/maps/references/PTT mapping
- complete configuration export/import including references and PTT mapping
- Windows monitor/DPI environment diagnostics
- PyInstaller one-folder build spec
- portable ZIP build
- Inno Setup per-user installer preserving all mutable user data
- `--safe-mode` packaged startup path

## Security / determinism
- setup and settings mutation APIs reject non-local clients
- update checking is opt-in and never changes code
- firewall modification requires an explicit user action
- product/device settings do not change deterministic telemetry/strategy algorithms
- upgrades do not overwrite settings, references, recordings, validation output or map caches


---

## Archived source: `V1.7.0.0_FINAL_VALIDATION_REPORT.md`

# V1.7.0.0 Final Validation Report

## Release

**V1.7.0.0 — SPEED COACH / Straight Line Coach Integration**

Base: V1.6.0.0 Windows Productization source. The Windows EXE/installer build remains intentionally deferred.

## Final architecture

- **SPEED COACH** is the parent/master runtime and public overlay.
- **CORNER COACH** is an independently switchable child retaining the mature PRE/POST pipeline.
- **STRAIGHT LINE COACH** is an independently switchable child using the same authoritative compiled reference and full-track segmentation.
- Map gain/loss remains a shared Speed Coach full-track layer.
- Legacy internal APIs/file names are retained where necessary for compatibility.

## Straight Line Coach deterministic evidence

Completed straight analysis uses measured local time change and, where present/trusted:

- average speed delta,
- top-speed delta,
- straight-end speed delta,
- full-throttle fraction delta,
- S-Mode/straight-mode usage delta,
- ERS usage delta.

Missing or untrusted channels are not invented. Straight speech is lower priority than upcoming corner PRE and waits for low brake/steering workload plus available radio airtime.

## Toggle/refinement validation

Validated behavior:

- Speed Coach master can mute both children without deleting child preferences.
- Corner Coach and Straight Line Coach can be enabled independently.
- Straight Line Coach defaults OFF for upgrade compatibility/no surprise chatter.
- Enabling Straight Line Coach mid-lap does not back-fill already completed straights.
- Re-enabling Straight Voice discards stale pending speech.
- Straight completed analysis can be retained visually while speech waits.
- Upcoming Corner PRE airtime is protected from straight feedback.
- Existing Corner PRE/POST, damage override, gain/loss and race-radio priority remain intact.
- Legacy `feature_states()` / `preference_states()` contracts remain compatible; the live V1.7 runtime uses extended Speed Coach state accessors.

## Transcript validation

- Combined human-readable coach transcript: `SPEED_COACH_TRANSCRIPT_*.txt`.
- Structured transcript source remains explicit: `corner_coach` or `straight_line_coach`.
- Legacy corner-only `CORNER_COACH_TRANSCRIPT_*.txt` remains available for older tooling.

## Real-recording evidence

Direct replay-index validation was run against the four supplied recordings without replaying the entire application pipeline:

| Recording | Packets | Best trace lap | Trace samples | Index build |
|---|---:|---:|---:|---:|
| Melbourne Qualifying | 38,358 | 1 | 4,049 | 2.458 s |
| Melbourne Race | 81,159 | 3 | 1,498 | 5.509 s |
| Time Trial | 92,262 | 3 | 1,318 | 6.826 s |
| Shanghai | 30,945 | 2 | 2,979 | 2.148 s |

Every selected trace had >100 measured samples for distance, speed, throttle, brake, gear and lap time. ERS/status coverage was effectively complete on all four. This confirms the channels used by Straight Line Coach exist in real recordings.

## Regression results

- Focused Speed Coach tests: PASS.
- Broad coach/reference/radio integration subset: **94 passed**.
- Final full regression: **794 tests passed + 383 subtests**.
- Failures: **0**.
- `python -m compileall -q src`: PASS.
- `python -m src.main --help`: PASS.

The full regression initially exposed one compatibility failure because new Speed Coach keys had been added to legacy state dictionaries. This was fixed by preserving the historical APIs exactly and adding separate extended Speed Coach accessors. The entire suite then passed cleanly.

## Deferred by user request

- Actual Windows `RaceEngineer.exe` compilation.
- Inno Setup installer compilation/acceptance.

These remain intentionally last-stage tasks after all feature work is complete.


---

## Archived source: `V1.7.0.0_REAL_RECORDING_SPEED_COACH_EVIDENCE.md`

# V1.7.0.0 Real Recording Speed Coach Evidence

The Straight Line Coach data foundation was checked directly against four existing `.areplay` recordings using the cached replay indexer. This avoids the known timeout risk of running the full 80–90k-packet engine replay while still verifying the measured telemetry channels used by the feature.

| Recording | Packets | Best trace lap | Samples | Distance | Speed | Throttle | Brake | Gear | ERS | Lap time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qualifying Melbourne | 38,358 | 1 | 4,049 | 4,049 | 4,049 | 4,049 | 4,049 | 4,049 | 4,048 | 4,049 |
| Race Melbourne | 81,159 | 3 | 1,498 | 1,498 | 1,498 | 1,498 | 1,498 | 1,498 | 1,498 | 1,498 |
| Time Trial | 92,262 | 3 | 1,318 | 1,318 | 1,318 | 1,318 | 1,318 | 1,318 | 1,318 | 1,318 |
| Shanghai | 30,945 | 2 | 2,979 | 2,979 | 2,979 | 2,979 | 2,979 | 2,979 | 2,978 | 2,979 |

Result: **PASS**.

This proves channel availability in real recordings. It does not replace the next live-session validation of actual spoken straight coaching, which will be captured by the existing validation/transcript system.


---

## Archived source: `V1.7.0.0_SPEED_COACH_STRAIGHT_LINE_INTEGRATION_NOTES.md`

# V1.7.0.0 — SPEED COACH / Straight Line Coach Integration

## Architecture

The former public CORNER COACH system is now the **SPEED COACH** parent. It owns the shared overlay, reference authority, full-track performance map, speech arbitration and validation/transcript plumbing.

Two independent children sit under it:

- **CORNER COACH** — existing refined PRE/POST corner coaching.
- **STRAIGHT LINE COACH** — completed-straight measured comparison and coaching.

The existing `CornerCoachEngine`/legacy file names remain internally where required for compatibility; public controls and UI use the new hierarchy.

## Straight Line Coach

Straight coaching reuses the same authoritative compiled reference and full-track segment partition. It does not create a second segmentation model.

For each completed straight it may report measured:

- local time gained/lost,
- average speed difference,
- top-speed difference,
- end/exit-speed difference,
- full-throttle fraction difference when reference inputs are trusted,
- S-Mode/straight-mode usage difference when trusted,
- ERS usage difference when trusted.

No unavailable channel is invented. Causal-style wording is used only when the supporting reference input telemetry is trusted.

## Radio safety

Straight diagnosis is captured immediately, but speech waits until braking and steering workload are low. It also protects the next CORNER COACH PRE reservation, so a lower-urgency completed-straight message cannot mask an upcoming corner instruction.

## Runtime controls

- SPEED — parent master.
- CORNER — corner child.
- STRAIGHT — straight child.
- VOICE — shared Speed Coach voice master.
- PRE / POST — corner child speech styles.
- S/L VOICE — straight child speech.
- MAP G/L / G/L VOICE / DMG COACH — existing shared/compatible behavior.

Straight Line Coach defaults OFF after upgrade. Enabling Straight or Straight Voice mid-lap starts from the current point; completed old straights and stale queued calls are not replayed.

## Transcripts

New combined output is `SPEED_COACH_TRANSCRIPT_*.txt`. Structured transcript records preserve `corner_coach` versus `straight_line_coach` source identity. A legacy `CORNER_COACH_TRANSCRIPT_*.txt` corner-only file is retained for existing validators/tools.


---

## Archived source: `V1.8.0.0.1_WINDOWS_RUNTIME_VALIDATION_HOTFIX_NOTES.md`

# V1.8.0.0.1 Windows Runtime Validation Hotfix

## Fixed
- Removed the unconditional POSIX-only `resource` import that prevented Race Engineer from starting on Windows.
- `src/runtime_validation.py` now imports `resource` only when available.
- Windows runtime peak working-set memory is measured using the native Windows PSAPI through Python `ctypes`; no new dependency is required.
- Runtime benchmark memory measurement remains non-fatal: metrics failure cannot block Race Engineer startup or telemetry processing.

## Validation
- `python -m compileall -q src tools`: PASS
- `python -m src.main --help`: PASS
- Full pytest regression suite: 801 tests passed, 383 subtests passed.

## Scope
No Race Engineer decision logic, coaching logic, strategy logic, telemetry decoding, overlay behavior, wheel telemetry, PTT/STT, or replay logic was changed.


---

## Archived source: `V1.8.0.0.2_AUDIO_IO_STT_HOTFIX_NOTES.md`

# V1.8.0.0.2 AUDIO I/O + STT HOTFIX

## Why duplicate audio devices were shown
Windows exposes the same physical endpoint through multiple PortAudio host APIs (MME, DirectSound, WASAPI and WDM-KS). The previous UI showed only `index: name`, so the entries looked duplicated even though they were separate host-API endpoints.

## Fixes
- Audio selectors now show the host API for every endpoint.
- PortAudio default microphone/output are explicitly marked.
- System-default rows show which concrete endpoint they resolve to.
- Device lists are ordered with the system default first and modern WASAPI endpoints preferred.
- PTT microphone capture now falls back to the selected device's native sample rate when 16 kHz is rejected (important for Windows/Bluetooth devices).
- Each PTT capture prints RMS/peak microphone level and actual sample rate for diagnosis.
- Added stronger Whisper no-speech/hallucination controls.
- Known silence/noise hallucinations such as `Thanks for watching` and `See you in the next video` are discarded before radio parsing.
- Added conservative recovery for observed real-radio mis-hearings, including corner-coach status, straight-line-coach status and `Where I am losing?`.

## Validation
- 805 pytest tests passed.
- 383 subtests passed.


---

## Archived source: `V1.8.0.0.3_REPLAY_CONTINUITY_SMOOTHNESS_HOTFIX_NOTES.md`

# V1.8.0.0.3 REPLAY CONTINUITY + SMOOTHNESS HOTFIX

## User-observed faults
- 1x replay became visibly choppy and appeared to skip laps/corners.
- A single weekend recording appeared to stop at practice -> qualifying and qualifying -> race boundaries until the replay slider was moved manually.
- Playback became especially choppy after a manual seek.

## Root causes fixed
1. The interactive replay clock treated `m_sessionTime` reset as the main session-boundary signal. In a multi-session F1 weekend, the authoritative `m_sessionUID` can change even when the following session's `m_sessionTime` is not numerically lower. That allowed a large game/menu timing gap to remain in the logical replay timeline.
2. The absolute realtime scheduler tried to recover from processing stalls by running overdue packets as fast as possible. No packets were intentionally dropped, but the catch-up burst made UI/coach state jump through many updates between paint cycles, which looked like skipped laps/corners.
3. Full deterministic replay checkpoints were serialized every 4096 packets. Dense 2026 recordings can exceed 1000 packets/s, so this could inject periodic CPU hitches during otherwise realtime playback.

## Changes
- Session transitions are now stitched using `PacketHeader.m_sessionUID` as the authoritative boundary, with the previous session-time reset check retained as a fallback.
- Practice -> qualifying -> race transitions inside one `.areplay` file advance automatically with only a bounded frame-sized timeline step; recorder/menu/loading gaps do not stop interactive replay.
- Realtime replay now has a 75 ms catch-up budget. If processing falls farther behind, the wall-clock anchor is reset at the current logical game time instead of creating a high-speed packet burst. No telemetry packet is dropped.
- Periodic replay checkpoint spacing increased from 4096 to 32768 packets. Lap-change checkpoints are still retained, so deterministic seek reconstruction remains available while normal 1x playback does much less serialization work.
- Manual seek continues to rebuild deterministic state silently and then reanchors realtime playback from the requested game timestamp.

## Validation
- New weekend session-UID continuity regression: PASS.
- New injected 150 ms stall/no-catch-up-burst regression: PASS.
- Existing replay range/seek/timeline regressions: PASS.
- Full project regression suite: 807 tests + 383 subtests PASS.
- Full source/tool bytecode compilation: PASS.
- CLI startup/help import: PASS.

## Scope
No Race Engineer decision logic, strategy model, Speed Coach diagnosis, Corner Coach math, Straight Line Coach math, audio/STT behavior, telemetry decoding, or reference-selection logic was changed by this hotfix.


---

## Archived source: `V1.8.0.0_DRIVING_PERFORMANCE_ENGINE_NOTES.md`

# V1.8.0.0 — Driving Performance Engine Completion

This release completes the requested geometry/time-domain corner measurement upgrade on top of V1.7.0.0 SPEED COACH.

## Implemented

1. Full F1 physical-turn segmentation support using the published circuit turn count as the labeling authority.
2. Separate corner anchors for approach/brake onset, geometric start, measured turn-in, curvature apex, and exit/recovery.
3. Path-curvature apex replaces minimum-speed apex as the primary geometric authority whenever world X/Z data is available.
4. True apex speed is measured at the curvature apex and retained separately from minimum speed.
5. Coasting is compared in seconds as well as metres.
6. Throttle pickup after apex is compared in seconds as well as distance.
7. Steering shape now includes mean/peak steering rate, correction count, smoothness, unwind time/distance and unwind monotonicity.
8. Corner confidence now includes current/reference quality, sample density, distance-gap continuity, speed coverage, path coverage, time continuity and apex confidence.
9. Additional outlier/path cleanup rejects isolated telemetry spikes and short stale position bursts without bridging large missing circuit sections.
10. Reference-relative minimum-speed, throttle-pickup and exit-speed efficiency percentages are exposed to live and post-session analysis.

## Legacy behaviour

References without usable world-path geometry are not falsely promoted to curvature-apex authority. They keep an explicit `min_speed_proxy` fallback with reduced confidence until a geometry-capable reference is available.

## Real recording evidence

The supplied recordings produced exact physical-turn counts and complete upgraded metric coverage on a geometry-complete lap:
- Melbourne Qualifying: 14/14
- Melbourne Race: 14/14
- Austria Time Trial: 10/10
- Shanghai: 16/16

Windows EXE/installer build remains intentionally deferred.


---

## Archived source: `V1.8.0.0_FINAL_VALIDATION_REPORT.md`

# V1.8.0.0 Final Validation Report

Release: **V1.8.0.0 — Driving Performance Engine Completion**

## Requested scope

All ten requested items are implemented:

1. Full physical corner segmentation coverage for every F1 track/reference known to the decoder.
2. Improved corner action boundaries: approach/brake onset, geometric start, turn-in, curvature apex, exit/recovery.
3. Path/curvature-based apex is primary when measured X/Z geometry exists.
4. True apex-speed comparison is separate from minimum-speed measurement.
5. Coasting duration comparison in seconds.
6. Throttle-pickup-after-apex comparison in seconds.
7. Steering rate, correction count, smoothness, unwind time/distance and unwind monotonicity.
8. Stronger per-corner current/reference quality and combined confidence scoring.
9. Additional isolated-value, distance-gap and short stale-position-burst outlier handling.
10. Reference-relative minimum-speed, throttle-pickup and exit-speed efficiency percentages.

## F1 track coverage

The telemetry track enum currently exposes **28** non-negative F1 track identifiers. All **28/28** resolve to a published physical-turn-count definition. No known decoder track is missing from the physical-turn segmentation table.

## Real recording evidence

Using geometry-complete valid laps from the supplied recordings:

| Recording | Track | Derived turns | Curvature apex + true apex speed | Time-domain metrics | Steering-shape metrics |
|---|---|---:|---:|---:|---:|
| Qualifying | Melbourne | 14/14 | 14/14 | 14/14 | 14/14 |
| Race | Melbourne | 14/14 | 14/14 | 14/14 | 14/14 |
| Time Trial | Austria | 10/10 | 10/10 | 10/10 | 10/10 |
| Shanghai | Shanghai | 16/16 | 16/16 | 16/16 | 16/16 |

The validation deliberately chooses a valid **geometry-complete** trace rather than blindly accepting the nominal fastest trace when that trace lacks a complete measured path.

## Robustness fixes found during validation

- Duplicate/degenerate lap timestamps no longer discard time-domain corner metrics. When packet/lap timestamps are unusable, elapsed time is integrated only from **measured distance and measured speed**; no nominal or predicted pace is introduced.
- Short bursts of stale world-position samples can be skipped only when a nearby measured point reconnects the path within a strict distance bound. Large missing circuit sections are never bridged.
- Constant-radius corners use the curvature-weighted centre of the sustained high-curvature plateau instead of an unstable single curvature peak.
- Legacy references with no usable path geometry retain an explicit `min_speed_proxy` fallback and reduced confidence instead of being falsely labeled as curvature-apex references.

## Regression results

- Targeted geometry/reference/compiler batch: **40/40 passed**
- Speed Coach/live Corner Coach/radio batch: **55/55 passed**
- Replay/report/performance batch: **29/29 passed**
- Recovery-4 targeted batch: **29/29 passed**
- Full regression: **801 tests passed + 383 subtests**
- Failures: **0**
- Python compile check: **PASS**
- CLI help/startup smoke: **PASS**

## Release boundary

The Windows `RaceEngineer.exe` / installer is intentionally **not built** in this phase, per project instruction. This release remains a source/runtime validation build ready for live Speed Coach testing.


---

## Archived source: `V1.8.0.0_REAL_RECORDING_DRIVING_PERFORMANCE_EVIDENCE.md`

# V1.8.0.0 Real Recording Driving Performance Evidence

Validated recordings:

- `Qual_telemetry-20260918T062108Z-c38b7cfb.areplay` — MELBOURNE — 14/14 turns
- `Race_telemetry-20260918T064535Z-d7412ccc.areplay` — MELBOURNE — 14/14 turns
- `TimeTrial_telemetry-20260917T121801Z-940696c8.areplay` — AUSTRIA — 10/10 turns
- `SHANGHAI_telemetry-20260922T153410Z-de96f122.areplay` — SHANGHAI — 16/16 turns

For the selected geometry-complete valid lap in each recording, every derived physical corner had:

- path-curvature apex authority,
- measured apex speed,
- usable time-domain coasting/throttle-pickup evidence,
- steering-rate and steering-smoothness evidence.

This evidence confirms that the new V1.8 metrics are available in real replay telemetry and are not limited to synthetic unit-test fixtures.


---

## Archived source: `V1.9.0.0_PERFORMANCE_HUB_NOTES.md`

# V1.9.0.0 — Local Driver Performance Hub

## Goal
Create a persistent browser-based performance summary that stores the user's F1 driving history locally and groups measured performance by track.

## Implemented
- New dependency-free SQLite store: `analysis/performance_history.sqlite3`.
- Driver profile is sourced from EA F1 ParticipantData and session metadata: display name, driver ID, race number, team ID/name, nationality ID, platform ID, My Team flag, AI flag, game year/version.
- Completed session data is stored only at report/session boundaries, never in the packet-processing hot path.
- Full session and coaching JSON are retained in SQLite together with queryable headline metrics.
- Existing `analysis/driver_history.json` is imported once when the first real driver profile is available; the currently finishing session is excluded from migration to avoid duplication.
- Browser page: `http://<Race-Engineer-host>:8765/performance`.
- API endpoints:
  - `/api/performance/overview`
  - `/api/performance/track?track=...`
  - `/api/performance/session?id=...`
- Browser views: driver identity/profile, overall totals, track list, best/potential trend, full session history, latest measured opportunities and strengths.
- Multiple stored driver profiles are supported and selectable.

## Storage policy
All performance history is local to the Race Engineer installation. No cloud service is used. SQLite WAL mode and atomic database transactions provide durable history without repeatedly rewriting the complete archive.

## Compatibility
Legacy `analysis/driver_history.json` remains supported for existing coaching features. V1.9 adds SQLite as the long-term Performance Hub source rather than removing the legacy file.

## Validation
- New V1.9 Performance Hub tests: profile extraction, SQLite persistence, track grouping, full session drill-down, legacy migration and live HTTP routes.
- Full project regression suite must pass before packaging.


---

## Archived source: `V1.9.1.0_LIVE_HISTORY_CONTROL_CENTER_NOTES.md`

# V1.9.1.0 — Live History Authority + Control Center Application

## Changes
- Performance Hub personal history is authoritative LIVE F1 game telemetry only.
- Replay can still drive overlays, reports and validation but never persists driver/profile/performance records.
- New clean live-only SQLite database: `analysis/performance_history_live.sqlite3`.
- Control Center is now a normal desktop application window rather than a racing overlay.
- Added CONTROL and PERFORMANCE HUB tabs.
- Embedded performance summary includes driver/team, session/track/lap/win totals, per-track bests and detailed session history.
- Optional browser Performance Hub remains at `/performance`.

## Compatibility
No Race Engineer decision logic, strategy logic, Corner Coach, Straight Line Coach, replay pacing, audio/STT, wheel link or F1 Dash logic was changed.


---

## Archived source: `V1.9.1.1_LONG_REPLAY_STABILITY_HOTFIX_NOTES.md`

# V1.9.1.1 Long Replay Stability Hotfix

This release addresses progressive replay slowdown on long/full-weekend recordings.

## Changes
- No changes to strategy decisions or coaching logic.
- Strategy assessment remains capped at 4 Hz.
- Validation evidence sampling is now 1 Hz in live mode and 0.2 Hz (every 5 s) in replay mode.
- Validation evidence buffers are bounded.
- Evidence for finalized sessions is removed from process memory after bundle creation.
- Existing replay no-catch-up-burst and session-UID stitching logic is preserved.

## Validation
- 818 tests passed.
- 383 subtests passed.


---

## Archived source: `V1.9.1.2_TELEMETRY_DECISION_DECOUPLING_HOTFIX_NOTES.md`

# V1.9.1.2 Telemetry Decision Decoupling Hotfix

Fixes long-replay choppiness where Motion/map stayed smooth but Car Telemetry-derived displays lagged. Heavy decision/coaching work is now sampled from the latest state at 20 Hz while raw telemetry state continues to update for every decoded packet.


---

## Archived source: `V1.9.1.3_LONG_REPLAY_MEMORY_ARCHITECTURE_HOTFIX_NOTES.md`

# V1.9.1.3 — Long Replay Memory Architecture Hotfix

This release fixes the remaining long-replay scaling issue. Interactive replay no longer loads the full `.areplay` payload into Python heap memory. It indexes the recording and reads packet payloads on demand through an OS memory map. Replay seek checkpoints are also sparse and bounded by both count and total bytes.

This preserves the V1.8.0.0.3 scheduler/session-stitching fixes, V1.9 live-only Performance Hub, V1.9.1 Control Center application window, V1.9.1.1 validation bounds, and V1.9.1.2 decision decoupling. No race/coaching decision logic is changed.

Validation: 820 tests passed + 383 subtests passed.


---

## Archived source: `V1.9.1.4_MULTI_DRIVER_PERFORMANCE_HUB_DARK_UI_NOTES.md`

# V1.9.1.4 — Multi-Driver Performance Hub + Dark UI Hotfix

## Fixes
- Separate persistent LIVE-only history per F1 driver.
- Driver-scoped session keys prevent cross-driver session reassignment.
- Added native DRIVER selector and persistent preferred driver.
- Browser driver selection persists for the browser via localStorage.
- Restyled Performance Hub tables to match the Control Center dark UI.
- Preserves V1.9.1.3 long replay memory architecture and all prior replay/audio/coach fixes.


---

## Archived source: `V1.9.1.5_WEEKEND_REPLAY_TRANSITION_HOTFIX_NOTES.md`

# V1.9.1.5 Weekend Replay Transition Hotfix

## Fixed
- Full-weekend replay could appear to stop between Practice, Qualifying and Race after the V1.9.1.3 indexed replay refactor.
- Transition packets can temporarily report playerCarIndex=255; replay clock metadata now reads UID/time independently of production race-state header validation.
- Large sessionTime discontinuities (menu/loading/stale-session jumps) are collapsed to <=50 ms logical steps.
- UID changes and time resets continue to stitch sessions automatically.

## Preserved
- memory-mapped replay file access
- bounded checkpoint memory
- no packet dropping
- no catch-up bursts
- long-session stability changes
- live-only Performance Hub and multi-driver separation

## Validation
- 827 tests passed
- 383 subtests passed
- explicit Practice -> Qualifying -> Race transition regression passed


---

## Archived source: `V1.9.2.0_FINAL_SOURCE_HARDENING_NOTES.md`

# V1.9.2.0 — Final Source Hardening

Source-only finalization build. Windows EXE / PyInstaller / installer work is intentionally not part of this release pass.

## Correctness fixes
- Opening-lap/early-race tyre-degradation pit projections require at least two clean completed same-stint laps.
- Standing-start, pit/outlap, SC/VSC, significant-damage and tyre-set-change laps are excluded from tyre degradation evidence.
- Pit recommendation repeat suppression is semantic and still allows urgency/reason/service changes.
- Fuel radio wording treats EA `m_fuelRemainingLaps` as the MFD fuel-laps margin.
- Tyre-temperature automatic warning is consolidated to one 115 C band with hysteresis/re-arm.
- Pit-lane and SC/VSC pass narration suppression plus same-opponent pass/re-pass debounce.
- Common social PTT filler is silently ignored rather than answered as unsupported radio.

## Replay / performance hardening preserved and extended
- Indexed/memory-mapped replay storage and bounded replay checkpoints.
- Weekend Practice -> Qualifying -> Race timeline stitching.
- No catch-up packet bursts after stalls.
- High-rate LapData + CarTelemetry state updates remain full-rate while heavy engineer/coaching work is cadence-bounded.
- Long-session validation evidence is bounded and sampled.

## Control Center / Performance Hub
- Control Center remains a normal desktop application window.
- Embedded Performance Hub remains live-game-only, multi-driver and dark-themed.
- Persistent Coaching Mode and Radio Detail selectors are exposed in Control Center.
- Native/LAN dashboard focus metadata stays in sync with coaching mode.

## Validation / diagnostics
- Golden expected-corner fixture.
- Game-year 25/26 format-2026 compatibility regression.
- All supported physical circuits have closed fallback map regression coverage.
- LAN/native coaching-state parity and latency-health regressions.
- Diagnostic export snapshots the WAL-backed live Performance Hub DB using SQLite backup rather than raw file copy.
- Runtime category cooldown profile is integrated into the engineer emission path.

## Supplied real-race recording evidence
Validated against `telemetry-20260926T175930Z-429413eb.areplay` (210,860 packets, ~1191.63 s):
- no false opening/early tyre-projection pit call through the first five completed laps;
- legitimate 100% front-wing damage box call retained;
- Safety Car -> pit entry -> tyre service -> pit exit -> SC return -> green restart sequence retained;
- no pit-lane pass narration spam;
- no duplicate 115/120 C tyre-temperature alert pair.

## Regression
- 845 pytest tests passed.
- 383 subtests passed.


---

## Archived source: `V1.9.2.1_PERFORMANCE_HISTORY_CORRECTNESS_NOTES.md`

# V1.9.2.1 Performance History Correctness

## Concrete source defects fixed
- LIVE Performance Hub session persistence no longer depends on optional automatic HTML/JSON coach report generation.
- Final completed-lap coach-report refresh now upserts the same driver-scoped Performance Hub session row.
- Replay coach reports no longer mutate legacy persistent `driver_history.json`.
- Performance Hub wins and podiums now count only EA race session types `Race`, `Race 2`, and `Race 3`; Qualifying and Time Trial P1/P2/P3 no longer inflate race result totals.

## Preserved
- V1.9.2.0 deterministic race/coaching behavior and real-race validation.
- LIVE-only multi-driver Performance Hub.
- Normal-window Control Center.
- Indexed/memory-mapped replay and bounded checkpoints.
- Weekend session stitching.
- High-rate telemetry/decision decoupling.
- Clean-stint pit strategy evidence gates.
- Windows EXE/PyInstaller/Inno definitions unchanged.


---

## Archived source: `HID_BUTTON6_FIX_NOTES.txt`

V0.6 ESP32-S3 RAW HID PTT - BUTTON 6 FIX

Confirmed wheel raw HID descriptor:
  Product: TinyUSB HID
  Manufacturer: Espressif Systems
  VID:PID: 303A:1001
  Usage: 0001:0005 (Gamepad)

Changes:
- Raw HID PTT now selects the wheel by VID/PID + Usage, not the DirectInput name ESP32S3_DEV.
- Default PTT button changed from 7 to 6.
- HID mapping key includes VID/PID + usage + button number.
- Existing button-7 mapping will not be reused for button 6.
- First PTT run calibrates physical button 6 and saves logs/ptt/hid_mapping.json.

Test command:
  .\\.venv\\Scripts\\python.exe -m src.main --ptt --ptt-button 6 --mic-device 2

Expected first-run flow:
  [PTT] HID controller: TinyUSB HID | logical button 6
  [PTT] Calibration: PRESS AND HOLD wheel button 6 now...
  [PTT] Button detected. RELEASE button 6...
  [PTT] HID mapping saved. Calibration complete.
  [PTT] Ready - hold the configured button to talk.

Then hold button 6, speak, release. A WAV should be written under logs/ptt/.


---

## Archived source: `HID_BUTTON6_STABLE_FIX_NOTES.txt`

V0.6 HID Button 6 stable-calibration fix

- Old HID mappings are intentionally ignored unless they use schema version 2.
- Calibration now verifies one and only one binary bit across three phases:
  released -> held -> released.
- Bits that vary during a phase (axes/HAT/report noise) are rejected.
- Ambiguous multi-bit changes are rejected instead of being saved.
- Runtime PTT input has 50 ms debounce.
- ESP32-S3 HID binding remains 303A:1001, usage 0001:0005.
- PTT default remains logical Button 6.
- No microphone/audio changes in this patch.

Acceptance test:
1. Run with --ptt --ptt-button 6 --mic-device 2.
2. During calibration keep every control released, then press/hold ONLY Button 6 when asked, then release when asked.
3. After Ready, leave wheel untouched for 30 seconds: there must be zero PTT PRESSED/RELEASED messages.
4. Press Button 6 once: exactly one PRESSED. Release: exactly one RELEASED.


---

## Archived source: `HID_PTT_FIX_NOTES.txt`

V0.6 HID PTT Fix
================
- Default PTT input backend changed from pygame/DirectInput to hidapi.
- Avoids IDirectInputDevice8::Acquire() 0x80070005 seen with ESP32S3_DEV.
- First run calibrates the selected physical PTT button and saves mapping to logs/ptt/hid_mapping.json.
- Later runs load the saved mapping automatically.
- pygame backend remains available with --ptt-backend pygame.
- PTT still only records WAV; STT remains V0.7.
- Full tests: 122 passed.


---

## Archived source: `PATCH3_NOTES.txt`

V0.5 Relevance-Aware Speech Queue

- New queued live-state messages supersede older queued messages of the same family.
- Position, fuel, weather/forecast, front-wing, tyre-damage, tyre-wear and total-penalty calls collapse to latest queued state.
- Critical messages still outrank strategy/information messages.
- Stale calls expire before speech: Information 4s, Strategy 8s, Critical 12s.
- Event calls such as pit entry/exit, tyre fitted, lap completion, safety car and faults are not collapsed.
- The sentence already being spoken is never interrupted.
- Added counters for stale/superseded speech calls for diagnostics.
- Full suite: 106 tests passing.


---

## Archived source: `PATCH4_NOTES.txt`

V0.5 Race Control + Detailed Flags development patch

Adds deterministic, official-UDP-backed race-control calls:
- Detailed player penalty type + infringement reason from PENA events
- DRS enabled/disabled with official disabled reason
- Red flag, Safety Car/VSC event lifecycle
- Local marshal-zone Yellow/Blue/Green flag transitions
- 2026 Overtake enabled/disabled race-control events
- 2026 Partial Mode enabled/disabled (including official enable reason)
- Drive-through and stop-go served
- Player collision details with opponent name where Participants data is available
- Player retirement reason
- Team-mate pit, player fastest lap, chequered flag, lights out, overtake/overtaken calls

No reason is inferred: unknown EA IDs remain explicit unknown IDs.
Existing Piper neural TTS and relevance-aware queue are unchanged.


---

## Archived source: `PATCH_NOTES.txt`

V0.4 Development Patch 2

Fixes from live testing:
- Pit detection now uses a persistent pit-state latch and the real observed sequence:
  In lap/Pitting -> Out lap/Pitting -> Out lap/None.
- Engineer-only calls are printed immediately when generated, not held for the 1-second diagnostics tick.
- Initial weather acquisition is silent; only a genuine known->known weather change is announced.
- Added diffuser, sidepod, and individual brake damage warnings.
- Added regression tests for the real pit sequence, weather baseline, and major-accident components.

Validation on development copy:
Ran 95 tests in 5.042s
OK

Do not commit V0.4 yet; live validation is still in progress.


---

## Archived source: `V0.6_FLAG_RELEVANCE_FIX_NOTES.txt`

V0.6 Flag Relevance Fix
=======================

Based on the successful Button-6 human-paced PTT build.

Changes:
- Flag voice calls now consider only the player's current marshal zone and the immediately next marshal zone.
- Yellow in current zone: "Yellow flag..."
- Yellow in next zone: "Yellow flag ahead..."
- Yellow flags farther around the circuit are ignored until they become the next marshal zone.
- Entering a yellow zone already announced as "yellow ahead" does not repeat the warning.
- Green is announced only when the player's relevant yellow condition clears.
- Blue flag remains immediate when it applies to the player's current marshal zone.
- flag:local is now a replaceable TTS family so an obsolete queued flag state can be superseded before playback.
- PTT/HID Button 6, microphone recording, assists, telemetry and other engineer rules are unchanged.

Validation:
- 129 unit tests passed.
- Added tests for next-zone yellow, distant-yellow suppression, no duplicate on yellow-zone entry, and green only after relevant yellow clears.


---

## Archived source: `V0.6_PTT_FIX_NOTES.txt`

V0.6 PTT FIX

- On Windows, pygame/SDL controller polling now runs on the main thread.
- UDP telemetry runs in a separate daemon thread whenever PTT is enabled.
- PTT therefore works with F1 closed and while no UDP packets are arriving.
- Expected startup includes: [PTT] Ready - hold the configured button to talk.
- Config used for live test: controller 0, button 7, microphone device 2.
