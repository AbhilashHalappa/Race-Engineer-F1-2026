"""Central local-user-data layout for Race Engineer.

Application source/assets stay at project root. Mutable runtime data lives under
``user_data`` so upgrades, backups and cleanup are predictable.
"""
from __future__ import annotations

from pathlib import Path
import shutil

from .storage_manager import DEFAULT_STORAGE, StorageState

ROOT = DEFAULT_STORAGE.project_root
USER_DATA = DEFAULT_STORAGE.local_root
PERFORMANCE = DEFAULT_STORAGE.local_path('performance')
SESSIONS = DEFAULT_STORAGE.local_path('sessions')
RECORDINGS = DEFAULT_STORAGE.local_path('recordings')
TRACKS = DEFAULT_STORAGE.local_path('tracks')
REFERENCES = DEFAULT_STORAGE.local_path('references')
REFERENCES_UPLOADED = REFERENCES / 'uploaded'
REPORTS = SESSIONS / 'reports'
REPLAY_INDEX = SESSIONS / 'replay_index'
DIAGNOSTICS = DEFAULT_STORAGE.local_path('diagnostics')
VALIDATION = DEFAULT_STORAGE.local_path('validation')
VALIDATION_BUNDLES = VALIDATION / 'bundles'
CORNER_VALIDATION = VALIDATION / 'corner_coach'
TRANSCRIPTS = VALIDATION / 'transcripts'
LOGS = DEFAULT_STORAGE.local_path('logs')
PTT_LOGS = LOGS / 'ptt'
CRASH_LOGS = LOGS / 'crash'
CACHE = DEFAULT_STORAGE.local_path('cache')
DRIVERS = DEFAULT_STORAGE.local_path('drivers')
EXPORTS = DEFAULT_STORAGE.local_path('exports')
BACKUPS = DEFAULT_STORAGE.local_path('backups')

# S5 centralises the existing authoritative LIVE DB path without moving it.
# The actual performance-database migration is reserved for Server Roadmap S9.
PERFORMANCE_DB = DEFAULT_STORAGE.performance_history_db
DRIVER_HISTORY = PERFORMANCE / 'driver_history.json'
SESSION_LIBRARY = SESSIONS / 'session_library.json'
TRACK_LANDMARKS = TRACKS / 'track_landmarks.json'
TRACK_MAPS = TRACKS / 'maps'

_LAYOUT_DIRS = (
    PERFORMANCE, SESSIONS, RECORDINGS, TRACKS, TRACK_MAPS, REFERENCES,
    REFERENCES_UPLOADED, REPORTS, REPLAY_INDEX, DIAGNOSTICS, VALIDATION,
    VALIDATION_BUNDLES, CORNER_VALIDATION, TRANSCRIPTS, LOGS, PTT_LOGS,
    CRASH_LOGS, CACHE, DRIVERS, EXPORTS, BACKUPS,
)

# Legacy -> structured paths.  Only mutable user/runtime data is migrated.
_LEGACY = {
    Path('analysis/session_library.json'): SESSION_LIBRARY,
    Path('analysis/reports'): REPORTS,
    Path('analysis/replay_index'): REPLAY_INDEX,
    Path('analysis/diagnostics'): DIAGNOSTICS,
    Path('analysis/validation_bundles'): VALIDATION_BUNDLES,
    Path('analysis/corner_coach_validation'): CORNER_VALIDATION,
    Path('analysis/transcripts'): TRANSCRIPTS,
    Path('recordings'): RECORDINGS,
    Path('maps/tracks'): TRACK_MAPS,
    Path('maps/track_landmarks.json'): TRACK_LANDMARKS,
    Path('references'): REFERENCES,
    Path('references_uploaded'): REFERENCES_UPLOADED,
    Path('logs/ptt'): PTT_LOGS,
    Path('logs/crash'): CRASH_LOGS,
}


def ensure_layout() -> None:
    DEFAULT_STORAGE.ensure_layout()
    for p in _LAYOUT_DIRS:
        p.mkdir(parents=True, exist_ok=True)


def _merge_move(src: Path, dst: Path) -> None:
    if not src.exists() or src.resolve() == dst.resolve():
        return
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.move(str(src), str(dst))
        return
    dst.mkdir(parents=True, exist_ok=True)
    for child in list(src.iterdir()):
        target = dst / child.name
        if child.is_dir():
            _merge_move(child, target)
        elif not target.exists():
            shutil.move(str(child), str(target))
    try:
        src.rmdir()
    except OSError:
        pass


def migrate_legacy_layout() -> None:
    """Move legacy mutable data into ``user_data`` without overwriting newer files."""
    ensure_layout()
    # Most-specific paths first so parent directories are not moved wholesale.
    for src, dst in sorted(_LEGACY.items(), key=lambda kv: len(kv[0].parts), reverse=True):
        try:
            _merge_move(src, dst)
        except OSError:
            # Startup must never fail solely because an old file is locked.
            continue
    ensure_layout()


def layout_manifest() -> dict[str, str]:
    return {
        'performance': str(PERFORMANCE),
        'sessions': str(SESSIONS),
        'recordings': str(RECORDINGS),
        'tracks': str(TRACKS),
        'references': str(REFERENCES),
        'diagnostics': str(DIAGNOSTICS),
        'validation': str(VALIDATION),
        'logs': str(LOGS),
        'cache': str(CACHE),
        'drivers': str(DRIVERS),
        'exports': str(EXPORTS),
        'backups': str(BACKUPS),
        'storage_state': StorageState.LOCAL.value,
        'pending_sync': str(DEFAULT_STORAGE.pending_root),
    }
