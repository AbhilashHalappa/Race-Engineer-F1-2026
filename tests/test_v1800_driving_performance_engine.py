import math

from src.corner_geometry_metrics import compare_corner, measure_corner, reject_sample_outliers
from src.track_geometry import PHYSICAL_TURN_COUNTS, canonical_track_name
from src.telemetry.enums import TRACKS


def _lap(*, slower=False, noisy=False, gap=False):
    samples={}
    t=0.0
    last_d=0.0
    for d in range(0,301,5):
        # Straight -> 100 m radius quarter-circle -> straight.
        if d < 100:
            x=float(d); z=0.0
        elif d <= 200:
            theta=(d-100)/100.0*(math.pi/2)
            x=100.0+100.0*math.sin(theta)
            z=100.0*(1.0-math.cos(theta))
        else:
            x=200.0; z=100.0+(d-200)
        speed=180.0
        if 100<=d<=200:
            speed=125.0 + abs(d-150)*0.75
            if slower: speed-=8.0 if 130<=d<=185 else 3.0
        # Integrate measured time from distance/speed.
        if d>0:
            t += (d-last_d) / max(1.0,speed/3.6)
        last_d=float(d)
        brake=0.0; throttle=1.0; steering=0.0
        if 70<=d<=125:
            brake=max(0.0,0.85-(d-95)**2/5000.0); throttle=0.0
        if 115<=d<=205:
            # Smooth reference, corrections on the slower lap.
            base=0.48*math.sin((d-115)/90.0*math.pi)
            steering=base + ((0.12 if ((d//10)%2==0) else -0.12) if noisy else 0.0)
        if 125<d<160:
            throttle=0.0; brake=0.0
        pickup_d=180 if slower else 165
        if pickup_d<=d<205:
            throttle=min(1.0,0.20+(d-pickup_d)/35.0)
        if d>=205: throttle=1.0
        row={"t":t,"speed":speed,"throttle":throttle,"brake":brake,"steering":steering,"gear":5,
             "world_x":x,"world_z":z,"g_long":None}
        if gap and d in (140,145,150,155):
            continue
        samples[float(d)]=row
    return {"_samples":samples,"track_length_m":300.0,"track_name":"TEST"}


def _turn():
    return {"corner_id":1,"label":"T1","ownership_start_m":50.0,"ownership_end_m":250.0,
            "start_m":100.0,"apex_m":150.0,"end_m":200.0,"turn_direction":"RIGHT",
            "physical_geometry":True}


def test_every_known_f1_track_has_physical_turn_count():
    missing=[]
    for raw,name in TRACKS.items():
        if raw < 0:
            continue
        canonical=canonical_track_name(name)
        if canonical not in PHYSICAL_TURN_COUNTS:
            missing.append(canonical)
    assert missing == []


def test_curvature_apex_is_separate_from_minimum_speed_proxy_and_has_true_apex_speed():
    m=measure_corner(_lap(),_turn())
    assert m["available"] is True
    assert m["apex_method"] == "path_curvature"
    assert 130.0 <= m["apex_m"] <= 170.0
    assert m["apex_speed_kph"] is not None
    assert m["min_speed_kph"] is not None
    # Both are independently retained facts even when close on this synthetic turn.
    assert "min_speed_m" in m and "physical_apex_m" in m


def test_time_domain_coast_pickup_steering_quality_and_efficiency():
    ref=_lap(slower=False,noisy=False)
    cur=_lap(slower=True,noisy=True)
    c=compare_corner(cur,ref,_turn())
    assert c["coasting_s_delta"] is not None
    assert c["throttle_pickup_after_apex_s_delta"] is not None
    assert c["throttle_pickup_after_apex_s_delta"] > 0
    assert c["apex_speed_kph_delta"] < 0
    assert c["exit_speed_efficiency_pct"] is not None
    assert c["minimum_speed_efficiency_pct"] < 100.0
    assert c["throttle_pickup_efficiency_pct"] < 100.0
    assert c["steering_corrections_delta"] is not None
    assert c["corner_confidence"] > 0.50


def test_outlier_rejection_removes_isolated_speed_spike_field():
    rows=[{"d":0.0,"t":0.0,"speed":100.0},{"d":5.0,"t":0.18,"speed":330.0},{"d":10.0,"t":0.36,"speed":102.0}]
    clean=reject_sample_outliers(rows)
    assert clean[1].get("speed") is None


def test_sparse_corner_has_lower_quality_than_dense_corner():
    dense=measure_corner(_lap(),_turn())
    sparse=measure_corner(_lap(gap=True),_turn())
    assert sparse["quality"] < dense["quality"]
    assert "low_sample_density" in sparse["quality_reasons"] or "large_distance_gap" in sparse["quality_reasons"]


def test_short_burst_of_stale_world_points_does_not_destroy_complete_geometry():
    from src.track_geometry import measured_world_trace
    samples={}
    # A valid path with two interleaved stale points. The cleaner may discard the
    # stale burst but must reconnect to the measured path without bridging a long gap.
    for d in range(0,101,5):
        samples[float(d)]={"world_x":float(d),"world_z":0.0}
    samples[20.0]={"world_x":500.0,"world_z":500.0}
    samples[25.0]={"world_x":500.0,"world_z":500.0}
    trace=measured_world_trace(samples,require_start=False)
    assert trace
    assert all(abs(x)<=110.0 for _,x,_ in trace)


def test_degenerate_timestamps_use_measured_distance_speed_for_time_metrics():
    lap=_lap(slower=True,noisy=True)
    for row in lap["_samples"].values():
        row["t"]=0.0
    m=measure_corner(lap,_turn())
    assert m["steering_rate_mean_per_s"] is not None
    assert m["steering_smoothness"] is not None
    assert m["throttle_pickup_after_apex_s"] is not None
    assert m["throttle_pickup_after_apex_s"] >= 0.0
