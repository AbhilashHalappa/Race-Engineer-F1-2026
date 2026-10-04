from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.product_readiness import first_run_check, save_first_run_report, windows_firewall_command

def main():
    p=argparse.ArgumentParser(description='Race Engineer local first-run readiness check')
    p.add_argument('--udp-port',type=int,default=20777); p.add_argument('--root',default='.')
    p.add_argument('--save',default='analysis/diagnostics/first_run.json'); p.add_argument('--firewall-for')
    a=p.parse_args(); r=first_run_check(udp_port=a.udp_port,root=a.root)
    save_first_run_report(a.save,udp_port=a.udp_port,root=a.root)
    print(json.dumps(r.to_dict(),indent=2))
    if a.firewall_for: print('\nOptional private-network firewall command:\n'+windows_firewall_command(a.firewall_for))
if __name__=='__main__': main()
