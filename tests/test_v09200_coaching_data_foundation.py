from src.coaching_analysis import build_corner_analyses
from src.measured_performance import MeasuredPerformanceRecorder, Sample


def _sample(d, *, t=None, speed=200.0, throttle=1.0, brake=0.0, steering=0.0, gear=6):
    return Sample(
        d=float(d), t=float(t if t is not None else d / 50.0), speed=float(speed),
        throttle=float(throttle), brake=float(brake), steering=float(steering),
        gear=gear, rpm=11000, g_lat=0.0, g_long=0.0, slip=0.02,
        ers_j=2_000_000.0, fuel=20.0,
    )


def test_recorder_derives_v0920_corner_measurements():
    rec = MeasuredPerformanceRecorder()
    rows = []
    for d in range(0, 301, 5):
        brake = 0.0
        throttle = 1.0
        steering = 0.0
        speed = 220.0
        gear = 7
        if 100 <= d <= 165:
            brake = max(0.12, 0.90 - abs(d - 120) / 100.0)
            throttle = 0.0
            speed = 220.0 - (d - 100) * 1.35
            gear = 5 if d >= 130 else 6
        if 130 <= d <= 205:
            steering = 0.25
        if 170 <= d < 190:
            throttle = 0.30
            speed = 130.0 + (d - 170) * 1.0
            gear = 5
        if d >= 190:
            throttle = 1.0
            speed = 150.0 + (d - 190) * 0.55
            gear = 5 if d < 220 else 6
        rows.append(_sample(d, speed=speed, throttle=throttle, brake=brake, steering=steering, gear=gear))

    sections = rec._segments(rows)
    assert len(sections) == 1
    s = sections[0]
    assert s["start_m"] == 100.0
    assert s["brake_release_m"] >= 165.0
    assert s["turn_in_m"] == 130.0
    assert s["throttle_pickup_m"] >= s["min_speed_m"]
    assert s["full_throttle_m"] >= s["throttle_pickup_m"]
    assert s["brake_duration_m"] >= 60.0
    assert s["trail_brake_m"] >= 0.0
    assert s["entry_gear"] == 6
    assert s["apex_method"] == "min_speed_proxy"
    assert s["analysis_sample_count"] >= 10
    assert s["peak_abs_steering"] >= 0.25


def _lap(section, time_offset=0.0, local_loss=0.0):
    samples = {}
    for d in range(0, 401, 5):
        t = d / 50.0 + time_offset
        if d >= 200:
            t += local_loss
        samples[float(d)] = {
            "d": float(d), "t": t, "speed": 200.0, "throttle": 1.0,
            "brake": 0.0, "steering": 0.0, "gear": 6,
        }
    return {
        "lap": 2,
        "valid": True,
        "lap_time_s": 8.0 + time_offset + local_loss,
        "sections": [section],
        "_samples": samples,
    }


def test_corner_analysis_exposes_deltas_confidence_and_time_loss():
    ref_section = {
        "id": 1, "start_m": 100.0, "brake_release_m": 155.0, "brake_duration_m": 55.0,
        "turn_in_m": 130.0, "trail_brake_m": 25.0, "min_speed_m": 165.0,
        "min_speed_kph": 130.0, "apex_method": "min_speed_proxy",
        "throttle_pickup_m": 175.0, "full_throttle_m": 195.0,
        "pickup_to_full_throttle_m": 20.0, "coasting_m": 10.0,
        "end_m": 220.0, "exit_speed_kph": 185.0, "peak_brake": 0.90,
        "entry_gear": 6, "apex_gear": 4, "exit_gear": 5, "gear_shift_count": 3,
        "peak_abs_steering": 0.45, "steering_reversals": 0, "analysis_sample_count": 25,
    }
    cur_section = dict(ref_section)
    cur_section.update({
        "start_m": 90.0, "brake_release_m": 160.0, "brake_duration_m": 70.0,
        "turn_in_m": 125.0, "trail_brake_m": 35.0, "min_speed_m": 165.0,
        "min_speed_kph": 124.0, "throttle_pickup_m": 190.0, "full_throttle_m": 215.0,
        "pickup_to_full_throttle_m": 25.0, "coasting_m": 20.0,
        "exit_speed_kph": 178.0, "peak_brake": 0.85,
    })

    analyses = build_corner_analyses(_lap(cur_section, local_loss=0.20), _lap(ref_section))
    assert len(analyses) == 1
    a = analyses[0]
    assert a.brake_onset_delta_m == -10.0
    assert a.brake_release_delta_m == 5.0
    assert a.min_speed_delta_kph == -6.0
    assert a.throttle_pickup_delta_m == 15.0
    assert a.exit_speed_delta_kph == -7.0
    assert a.coasting_delta_m == 10.0
    assert a.time_loss_s is not None and a.time_loss_s > 0.15
    assert 0.0 <= a.confidence <= 1.0
    assert a.confidence > 0.75
    assert a.apex_method == "min_speed_proxy"


def test_old_section_schema_remains_safe_for_corner_analysis():
    old = {
        "id": 1, "start_m": 100.0, "brake_end_m": 150.0, "end_m": 220.0,
        "min_speed_m": 165.0, "min_speed_kph": 130.0, "full_throttle_m": 195.0,
        "exit_speed_kph": 185.0, "peak_brake": 0.9,
    }
    result = build_corner_analyses(_lap(old), _lap(old))
    assert len(result) == 1
    assert result[0].brake_onset_delta_m == 0.0
    assert result[0].brake_release_m is None
    assert result[0].confidence < 0.75
