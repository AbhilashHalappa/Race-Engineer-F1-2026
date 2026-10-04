#!/usr/bin/env python3
"""Run the V2.0.11 automated validation/source-freeze preflight."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v2_final_validation import build_phase1_report, validation_matrix


def _pytest_targets() -> list[str]:
    out=[]
    for gate in validation_matrix():
        if gate.scope_status != "required":
            continue
        out.extend(gate.automated_evidence)
    # stable order, no duplicates
    return list(dict.fromkeys(out))


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--output", default="V2.0.11_AUTOMATED_VALIDATION_REPORT.json")
    ap.add_argument("--pytest", action="store_true", help="Run the V2.0.11 automated evidence tests.")
    ns=ap.parse_args()
    root=Path(ns.root).resolve()
    report=build_phase1_report(root)
    if ns.pytest:
        targets=_pytest_targets()
        proc=subprocess.run([sys.executable,"-m","pytest","-q",*targets],cwd=root,text=True,capture_output=True)
        report["pytest"]={"ok":proc.returncode==0,"returncode":proc.returncode,"targets":targets,"stdout":proc.stdout,"stderr":proc.stderr}
    else:
        report["pytest"]={"ok":None,"status":"not_run"}
    report["automated_phase_ok"] = bool(report.get("automated_structure_ok") and report["pytest"].get("ok") is not False)
    out=root/ns.output
    out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(out)
    if ns.pytest:
        print(report["pytest"]["stdout"], end="")
    return 0 if report["automated_phase_ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
