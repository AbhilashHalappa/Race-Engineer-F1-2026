import json
from types import SimpleNamespace
from src.lap_analysis import build_session_analysis, compare_sections, write_session_analysis


def lap(n, t, brake=100, min_speed=100, throttle=220):
    return {"lap":n,"valid":True,"lap_time_s":t,"sections":[{"id":1,"start_m":brake,"min_speed_kph":min_speed,"full_throttle_m":throttle,"exit_speed_kph":180,"peak_brake":.9,"max_slip":.1}],"_samples":{}}

class Perf:
    def __init__(self): self.completed=[lap(2,90.0),lap(3,91.0,110,95,230)]
    @staticmethod
    def compare(cur, ref):
        return {"lap":cur["lap"],"reference_lap":ref["lap"],"lap_time_s_delta":cur["lap_time_s"]-ref["lap_time_s"]}

def test_report_selects_best_and_corner_deltas(tmp_path):
    p=Perf(); r=build_session_analysis(p)
    assert r["best_valid_lap"]==2
    assert r["comparisons_to_best"][0]["lap_time_s_delta"]==1.0
    c=r["comparisons_to_best"][0]["corners"][0]
    assert c["brake_point_delta_m"]==10
    assert c["min_speed_delta_kph"]==-5
    assert c["full_throttle_delta_m"]==10
    out=tmp_path/'analysis.json'; write_session_analysis(p,out)
    assert json.loads(out.read_text())["version"]=="0.9.10.0"

def test_section_comparison_handles_missing_values():
    a=lap(2,90); b=lap(3,91); a["sections"][0]["max_slip"]=None
    c=compare_sections(a,b)[0]
    assert c.max_slip_delta is None
