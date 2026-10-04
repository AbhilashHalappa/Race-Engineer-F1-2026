from pathlib import Path
from types import SimpleNamespace

from src.coaching_settings import CoachingSettingsStore
from src.coaching_live import IntegratedLiveCoach
from src.data_quality import lap_quality, live_context_blockers
from src.potential_lap import potential_summary
from src.racing_line import compare_racing_line
from src.session_coach_report import save_coach_report
from src.technique_metrics import session_technique_metrics
from src.coaching_analysis import build_corner_analyses


def _lap(n, t, s1, s2, s3, *, valid=True, anchored=True, sections=None, samples=None):
    return {
        "lap": n, "valid": valid, "lap_start_anchored": anchored, "sample_count": 800,
        "lap_time_s": t, "sector1_time_s": s1, "sector2_time_s": s2, "sector3_time_s": s3,
        "sections": sections or [], "_samples": samples or {},
    }


def test_coaching_settings_persist_runtime_switches(tmp_path):
    path = tmp_path / "coaching.json"
    store = CoachingSettingsStore(path)
    store.set(pre_corner=False, race_coaching=False, verbosity="detailed")
    again = CoachingSettingsStore(path)
    assert again.settings.pre_corner is False
    assert again.settings.race_coaching is False
    assert again.settings.verbosity == "detailed"


def test_legacy_reference_missing_anchor_metadata_is_not_automatically_partial():
    legacy = {"valid": True, "sample_count": 800, "lap_time_s": 70.0}
    assert lap_quality(legacy)["eligible"] is True
    legacy["lap_start_anchored"] = False
    assert "partial_lap" in lap_quality(legacy)["reasons"]


def test_sector_potential_uses_only_eligible_valid_laps():
    laps = [
        _lap(1, 70.4, 17.2, 31.2, 22.0),
        _lap(2, 70.1, 17.0, 31.4, 21.7),
        _lap(3, 69.0, 16.0, 30.0, 21.0, valid=False),
    ]
    out = potential_summary(laps)
    assert round(out["potential_lap_s"], 3) == 69.9
    assert round(out["best_lap_s"], 3) == 70.1
    assert round(out["potential_gain_s"], 3) == 0.2
    assert out["eligible_lap_count"] == 2


def test_technique_metrics_require_three_samples():
    section = lambda x: {"id": 1, "start_m": x, "brake_release_m": 150+x, "trail_brake_m": 20+x,
                         "min_speed_kph": 120+x, "min_speed_m": 165+x, "throttle_pickup_m": 175+x,
                         "exit_speed_kph": 180+x, "apex_gear": 4}
    two = [_lap(1,70,17,31,22,sections=[section(0)]), _lap(2,70.1,17,31,22.1,sections=[section(1)])]
    assert session_technique_metrics(two)["lap_time_consistency"] is None
    three = two + [_lap(3,69.9,16.9,31,22,sections=[section(2)])]
    out = session_technique_metrics(three)
    assert out["lap_time_consistency"]["samples"] == 3
    assert out["corners"][0]["brake_point_consistency"]["samples"] == 3


def test_racing_line_uses_world_position_at_matched_distance():
    ref = {}; cur = {}
    for d in range(0, 200, 5):
        ref[float(d)] = {"world_x": float(d), "world_z": 0.0}
        cur[float(d)] = {"world_x": float(d), "world_z": 1.0}
    out = compare_racing_line({"_samples":cur, "sections":[{"id":1,"start_m":20,"end_m":100}]}, {"_samples":ref})
    assert out["available"] is True
    assert round(out["mean_path_deviation_m"], 3) == 1.0
    assert out["corners"][0]["corner_id"] == 1


def test_pre_corner_reminder_uses_current_speed_and_distance(tmp_path):
    store = CoachingSettingsStore(tmp_path / "settings.json")
    store.set(post_corner=False, lap_summary=False, positive_calls=False, pre_corner=True,
              pre_corner_min_s=4.0, pre_corner_max_s=7.0)
    coach = IntegratedLiveCoach(store)
    coach._last_completed_count = 0
    coach._advice = {1: {"corner_id":1, "diagnosis":"minimum_speed_low", "diagnosis_label":"Minimum speed too low",
                          "estimated_time_cost_s":.12, "diagnosis_confidence":.95, "actionability":.9,
                          "issue_candidates":[{"code":"minimum_speed_low","magnitude":-10,"primary_eligible":True}]}}
    ref = {"lap_time_s":70.0, "valid":True, "sections":[{"id":1,"start_m":600.0,"min_speed_kph":120,"apex_gear":4}]}
    class Rec:
        event_context={"profile":"time_trial"}; completed=[]
        def current_reference_lap(self): return ref
    state = SimpleNamespace(
        player=SimpleNamespace(lap=SimpleNamespace(current_lap=2, lap_distance_m=300.0, lap_valid=True),
                               telemetry=SimpleNamespace(speed_kph=216.0, brake=0.0, steering=0.0)),
        session=SimpleNamespace(session_time_s=10.0, paused=False, safety_car=None, marshal_zones=[]),
    )
    out = coach.observe(Rec(), state, 10.0)
    assert len(out) == 1
    assert out[0].key.startswith("coach:pre:2:1:")
    assert out[0].text.startswith("Turn 1 coming up:")


def test_race_context_close_traffic_blocks_live_coaching():
    state = SimpleNamespace(
        player=SimpleNamespace(lap=SimpleNamespace(lap_valid=True, gap_to_car_in_front_s=.7, pit_status=None), damage=None),
        session=SimpleNamespace(paused=False, safety_car=None, marshal_zones=[]),
    )
    assert "close_traffic" in live_context_blockers(state, race_mode=True, traffic_gap_s=1.2)


def test_brake_release_abrupt_is_detected_when_mid_phase_loses_time():
    ref_sec = {
        "id":1,"start_m":100.0,"brake_release_m":155.0,"brake_duration_m":55.0,
        "brake_release_ramp_m":20.0,"brake_release_ramp_s":.22,
        "turn_in_m":130.0,"trail_brake_m":25.0,"min_speed_m":165.0,"min_speed_kph":130.0,
        "apex_method":"min_speed_proxy","throttle_pickup_m":175.0,"full_throttle_m":195.0,
        "pickup_to_full_throttle_m":20.0,"pickup_to_full_throttle_s":.35,"coasting_m":10.0,"coasting_s":.15,
        "end_m":220.0,"exit_speed_kph":185.0,"peak_brake":.9,"entry_gear":6,"apex_gear":4,"exit_gear":5,
        "gear_shift_count":3,"peak_abs_steering":.45,"steering_reversals":0,"max_slip":.1,"analysis_sample_count":25,
    }
    cur_sec = dict(ref_sec, brake_release_ramp_s=.05, brake_release_ramp_m=5.0)
    def lap(sec, delay=0.0):
        samples={}
        for d in range(0,401,5):
            samples[float(d)]={"d":float(d),"t":d/50.0+(delay if d>=120 else 0.0),"speed":200.0,"throttle":1.0,"brake":0.0,"steering":0.0,"gear":6}
        return {"lap":2,"valid":True,"lap_time_s":8+delay,"sections":[sec],"_samples":samples}
    a = build_corner_analyses(lap(cur_sec,.10), lap(ref_sec))[0]
    assert any(x["code"] == "brake_release_abrupt" for x in a.issue_candidates)


def test_session_report_writes_json_and_html(tmp_path):
    class Rec:
        completed=[]; event_context={"profile":"time_trial"}; reference_mode="session_best"; external_reference=None
    jp, hp, report = save_coach_report(Rec(), directory=tmp_path, stem="test")
    assert jp.exists() and hp.exists()
    assert report["format"] == "RACE_ENGINEER_COACH_REPORT"
    assert "Race Engineer" in hp.read_text(encoding="utf-8")
