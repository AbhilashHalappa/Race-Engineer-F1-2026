"""Entry point used by the packaged Windows release."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import threading
import webbrowser
import json
import os

from .crash_reporting import install_crash_handler
from .product_settings import ProductSettingsStore
from .product_migration import create_upgrade_backup_if_needed


def main() -> int:
    # Shortcuts/installer set WorkingDir, but direct EXE launches do not always do so.
    # Keep all writable local data beside the one-folder executable.
    if getattr(sys, 'frozen', False):
        os.chdir(Path(sys.executable).resolve().parent)
    install_crash_handler()
    create_upgrade_backup_if_needed()
    parser=argparse.ArgumentParser(description="Race Engineer Stable V2 Windows launcher")
    parser.add_argument("--setup",action="store_true",help="Open the local setup page")
    parser.add_argument("--safe-mode",action="store_true",help="Start without PTT/wheel bridge")
    args=parser.parse_args()
    s=ProductSettingsStore().settings
    if s.update_check_enabled:
        def _update_background():
            try:
                from .update_checker import check_for_updates
                out=Path('analysis/diagnostics/update_status.json'); out.parent.mkdir(parents=True,exist_ok=True)
                out.write_text(json.dumps(check_for_updates(s.update_manifest_url).to_dict(),indent=2),encoding='utf-8')
            except Exception:
                pass
        threading.Thread(target=_update_background,name='race-engineer-update-check',daemon=True).start()
    # The setup UI is served by the dashboard thread, which is started by the
    # overlay runtime. A short timer opens it only after the HTTP listener exists.
    setup_requested=bool(args.setup or not s.setup_complete)
    if setup_requested:
        threading.Timer(1.5,lambda:webbrowser.open(f"http://127.0.0.1:{s.dash_port}/setup")).start()
    from .main import main as run
    return int(run(
        udp_port=s.udp_port,
        tts_enabled=s.tts_enabled,
        audio_device=s.audio_device,
        overlay=(s.overlay_enabled or setup_requested),
        overlay_click_through=s.overlay_click_through,
        web_dash=s.web_dash_enabled,
        dash_host=s.dash_host,
        dash_port=s.dash_port,
        ptt_enabled=(s.ptt_enabled and not args.safe_mode),
        ptt_controller=s.ptt_controller,
        ptt_button=s.ptt_button,
        ptt_backend=s.ptt_backend,
        ptt_hid_vendor_id=s.hid_vendor_id,
        ptt_hid_product_id=s.hid_product_id,
        ptt_hid_usage_page=s.hid_usage_page,
        ptt_hid_usage=s.hid_usage,
        mic_device=s.mic_device,
        stt_enabled=s.stt_enabled,
        wheel_telemetry=(s.wheel_telemetry_enabled and not args.safe_mode),
        wheel_port=s.wheel_port,
    ))


if __name__ == "__main__":
    raise SystemExit(main())
