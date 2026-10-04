from pathlib import Path


def test_driver_inputs_dedupes_frozen_snapshots():
    src = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "Append graph points only when telemetry has actually progressed" in src
    assert "if progressed:" in src
    assert "self._last_lap_time = s.lap_time_s" in src


def test_reference_input_clock_is_explicit_reference_clock():
    src = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert 'REF {t}{distance_text}  Δ {dt:+.3f}' in src


def test_rival_capture_reads_all_car_status_for_ers():
    src = Path("src/rival_benchmark.py").read_text(encoding="utf-8")
    assert 'if pid == 7:' in src
    assert 'm_carStatusData' in src
    assert 'm_ersStoreEnergy' in src
    assert 'ers_j=' in src
