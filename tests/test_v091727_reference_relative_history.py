from types import SimpleNamespace
from src.overlay.data import _lap_history_overlay_data


def _perf():
    return SimpleNamespace(completed=[
        {"lap":1,"valid":True,"lap_time_s":91.712,"sector1_time_s":35.188,"sector2_time_s":19.707,"sector3_time_s":36.815},
        {"lap":2,"valid":True,"lap_time_s":88.063,"sector1_time_s":30.163,"sector2_time_s":20.369,"sector3_time_s":37.530},
        {"lap":3,"valid":True,"lap_time_s":87.219,"sector1_time_s":30.178,"sector2_time_s":19.464,"sector3_time_s":37.576},
        {"lap":4,"valid":True,"lap_time_s":88.748,"sector1_time_s":29.606,"sector2_time_s":21.139,"sector3_time_s":38.002},
        {"lap":5,"valid":True,"lap_time_s":91.738,"sector1_time_s":32.057,"sector2_time_s":20.210,"sector3_time_s":39.471},
    ])


def test_external_reference_recomputes_all_history_deltas_and_best_is_session_fastest():
    # External reference says lap=2 on purpose. It must NOT make our lap 2 BEST.
    ref={"lap":2,"lap_time_s":77.338,"valid":True}
    rows=_lap_history_overlay_data(_perf(), ref)
    by_lap={r.lap:r for r in rows}
    assert by_lap[1].delta_s == 91.712 - 77.338
    assert by_lap[2].delta_s == 88.063 - 77.338
    assert by_lap[3].delta_s == 87.219 - 77.338
    assert by_lap[4].delta_s == 88.748 - 77.338
    assert by_lap[5].delta_s == 91.738 - 77.338
    assert by_lap[3].best is True
    assert by_lap[2].best is False


def test_changing_reference_recalculates_existing_history_against_new_reference():
    perf=_perf()
    rows_a=_lap_history_overlay_data(perf, {"lap_time_s":77.338})
    rows_b=_lap_history_overlay_data(perf, {"lap_time_s":88.063})
    a={r.lap:r for r in rows_a}; b={r.lap:r for r in rows_b}
    assert round(a[3].delta_s,3) == 9.881
    assert round(b[3].delta_s,3) == -0.844
    assert b[3].best is True
