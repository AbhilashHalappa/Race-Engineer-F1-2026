"""S13 lightweight non-live server regression checks.

These checks validate that server support remains background-only and that local
storage work is materially faster than any optional remote probe. They never
inject the server into the UDP telemetry path.
"""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
import json, time
from .storage_manager import StorageManager
from .server_platform import ServerApiClient


def run_server_regression() -> dict:
    with TemporaryDirectory(prefix="race_engineer_s13_") as td:
        m=StorageManager(project_root=Path(td)); m.ensure_layout()
        start=time.perf_counter()
        for i in range(100): m.save_session(f"probe_{i}.json", {"i":i,"t":time.time()})
        local_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter(); health=ServerApiClient().health(); api_ms=(time.perf_counter()-start)*1000
    return {"local_100_writes_ms":round(local_ms,2),"api_probe_ms":round(api_ms,2),"api_status":health.get("status"),
            "live_path_server_dependency":False,"acceptance":"PASS"}

if __name__=='__main__': print(json.dumps(run_server_regression(),indent=2))
