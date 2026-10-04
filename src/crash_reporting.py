"""Crash capture for the packaged/local Windows release."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import platform
import sys
import threading
import traceback


_INSTALLED = False


def _write_crash(exc_type, exc_value, exc_tb, *, thread_name: str | None = None, root: str | Path = ".") -> Path:
    out = Path(root) / "logs" / "crash"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out / f"crash_{stamp}.log"
    header = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "thread": thread_name,
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "frozen": bool(getattr(sys, "frozen", False)),
    }
    body = json.dumps(header, indent=2) + "\n\n" + "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    path.write_text(body, encoding="utf-8", errors="replace")
    latest = out / "latest_crash.log"
    latest.write_text(body, encoding="utf-8", errors="replace")
    return path


def install_crash_handler(*, root: str | Path = ".") -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    old_sys = sys.excepthook
    old_thread = getattr(threading, "excepthook", None)

    def sys_hook(exc_type, exc_value, exc_tb):
        try:
            path = _write_crash(exc_type, exc_value, exc_tb, thread_name="MainThread", root=root)
            print(f"[CRASH] Report saved: {path}", file=sys.stderr, flush=True)
        except Exception:
            pass
        old_sys(exc_type, exc_value, exc_tb)

    def thread_hook(args):
        try:
            path = _write_crash(args.exc_type, args.exc_value, args.exc_traceback,
                                thread_name=getattr(args.thread, "name", None), root=root)
            print(f"[CRASH] Thread report saved: {path}", file=sys.stderr, flush=True)
        except Exception:
            pass
        if old_thread:
            old_thread(args)

    sys.excepthook = sys_hook
    if old_thread is not None:
        threading.excepthook = thread_hook
