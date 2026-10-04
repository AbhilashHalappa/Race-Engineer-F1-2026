from src.coaching_analysis import build_corner_analyses


def _section():
    return {
        "id": 1, "start_m": 100.0, "brake_release_m": 155.0, "brake_duration_m": 55.0,
        "turn_in_m": 130.0, "trail_brake_m": 25.0, "min_speed_m": 165.0,
        "min_speed_kph": 130.0, "apex_method": "min_speed_proxy",
        "throttle_pickup_m": 175.0, "full_throttle_m": 195.0,
        "pickup_to_full_throttle_m": 20.0, "coasting_m": 10.0,
        "end_m": 220.0, "exit_speed_kph": 185.0, "peak_brake": 0.90,
        "entry_gear": 6, "apex_gear": 4, "exit_gear": 5, "gear_shift_count": 3,
        "peak_abs_steering": 0.45, "steering_reversals": 0, "max_slip": 0.10,
        "analysis_sample_count": 25,
    }


def _lap(section, *, delay_after_m=None, delay_s=0.0):
    samples = {}
    for d in range(0, 401, 5):
        delay = delay_s if delay_after_m is not None and d >= delay_after_m else 0.0
        samples[float(d)] = {"d": float(d), "t": d / 50.0 + delay, "speed": 200.0,
                             "throttle": 1.0, "brake": 0.0, "steering": 0.0, "gear": 6}
    return {"lap": 2, "valid": True, "lap_time_s": 8.0 + max(0.0, delay_s),
            "sections": [section], "_samples": samples}


def test_early_braking_is_diagnosed_deterministically():
    ref = _section()
    cur = dict(ref, start_m=85.0, brake_duration_m=70.0)
    a = build_corner_analyses(_lap(cur, delay_after_m=50, delay_s=0.10), _lap(ref))[0]
    assert a.diagnosis == "brake_early"
    assert a.diagnosis_label == "Braking too early"
    assert a.diagnosis_confidence > 0.5
    assert a.actionability == 1.0
    assert a.issue_candidates[0]["code"] == "brake_early"


def test_late_throttle_pickup_is_diagnosed():
    ref = _section()
    cur = dict(ref, throttle_pickup_m=195.0, full_throttle_m=215.0)
    a = build_corner_analyses(_lap(cur, delay_after_m=180, delay_s=0.10), _lap(ref))[0]
    assert a.diagnosis == "throttle_late"
    assert a.issue_candidates[0]["phase"] == "EXIT"


def test_early_throttle_requires_measured_extra_slip():
    ref = _section()
    cur = dict(ref, throttle_pickup_m=160.0, max_slip=0.25)
    a = build_corner_analyses(_lap(cur, delay_after_m=180, delay_s=0.10), _lap(ref))[0]
    assert a.diagnosis == "throttle_early_traction_limited"


def test_low_quality_corner_suppresses_diagnosis():
    ref = _section()
    cur = {"id": 1, "start_m": 80.0, "end_m": 220.0, "min_speed_m": 165.0}
    a = build_corner_analyses(_lap(cur), _lap(ref))[0]
    assert a.confidence < 0.55
    assert a.diagnosis is None
    assert not a.issue_candidates


def test_faster_corner_suppresses_corrective_diagnosis():
    ref = _section()
    cur = dict(ref, peak_brake=1.0, start_m=115.0)
    a = build_corner_analyses(_lap(cur, delay_after_m=50, delay_s=-0.10), _lap(ref))[0]
    assert a.time_loss_s < 0.0
    assert a.diagnosis is None
    assert not a.issue_candidates
    assert a.coaching_eligible is False
    assert a.coaching_suppression_reason == "corner_not_slower"


def test_issue_requires_loss_in_its_own_phase():
    ref = _section()
    cur = dict(ref, peak_brake=1.0)
    # Lose time only after the apex: the entry brake-pressure difference must
    # remain measured but must not become corrective coaching.
    a = build_corner_analyses(_lap(cur, delay_after_m=180, delay_s=0.10), _lap(ref))[0]
    assert a.time_loss_s > 0.0
    assert all(x["code"] != "brake_pressure_high" for x in a.issue_candidates)


def test_min_speed_proxy_apex_is_supporting_only():
    ref = _section()
    cur = dict(ref, min_speed_m=150.0)
    a = build_corner_analyses(_lap(cur, delay_after_m=120, delay_s=0.10), _lap(ref))[0]
    apex = [x for x in a.issue_candidates if x["code"] == "apex_early"]
    assert apex and apex[0]["primary_eligible"] is False
    assert a.diagnosis != "apex_early"


def test_sub_20ms_whole_corner_loss_is_suppressed():
    ref = _section()
    cur = dict(ref, exit_speed_kph=175.0)
    # Net corner loss is only 9 ms, even though an exit difference exists.
    a = build_corner_analyses(_lap(cur, delay_after_m=180, delay_s=0.009), _lap(ref))[0]
    assert 0.0 < a.time_loss_s < 0.020
    assert a.diagnosis is None
    assert not a.issue_candidates
    assert a.coaching_eligible is False
    assert a.coaching_suppression_reason == "corner_loss_below_deadband"


def test_20ms_whole_corner_loss_is_not_suppressed_by_deadband():
    ref = _section()
    cur = dict(ref, throttle_pickup_m=195.0, full_throttle_m=215.0)
    a = build_corner_analyses(_lap(cur, delay_after_m=180, delay_s=0.020), _lap(ref))[0]
    assert a.time_loss_s >= 0.020 - 1e-9
    assert a.coaching_suppression_reason != "corner_loss_below_deadband"
