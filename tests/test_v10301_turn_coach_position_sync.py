from src.coaching_live import IntegratedLiveCoach
from src.distance_performance import build_distance_performance_model, physical_turn_boundaries
from src.measured_performance import MeasuredPerformanceRecorder
from src.overlay.data import _active_segment, _track_segments
import src.overlay.track_maps as track_maps


def _melbourne_markers():
    apexes = [300, 650, 1050, 1400, 1750, 2100, 2450, 2800, 3150, 3550, 4060, 4425, 4775, 5125]
    return tuple({
        "corner_id": i,
        "label": f"T{i}",
        "lap_distance_m": float(apex),
        "start_m": float(apex - 65),
        "apex_m": float(apex),
        "end_m": float(apex + 70),
        "turn_direction": "RIGHT" if i % 2 else "LEFT",
    } for i, apex in enumerate(apexes, 1))


def _legacy_tt_rival_reference():
    samples = {}
    for d in range(0, 5301, 5):
        samples[float(d)] = {
            "d": float(d), "t": float(d) / 55.0,
            "speed": 200.0, "throttle": 1.0, "brake": 0.0,
            "steering": 0.0, "gear": 6,
        }
    # The old rival has only five detector/brake sections. The fifth is physically
    # around Melbourne T11, which reproduced TURN 5 in the UI at ~4063 m.
    sections = [
        {"id": 1, "start_m": 250.0, "min_speed_m": 310.0, "end_m": 365.0, "min_speed_kph": 145.0},
        {"id": 2, "start_m": 985.0, "min_speed_m": 1040.0, "end_m": 1110.0, "min_speed_kph": 114.0},
        {"id": 3, "start_m": 1810.0, "min_speed_m": 1760.0, "end_m": 1830.0, "min_speed_kph": 229.0},
        {"id": 4, "start_m": 2235.0, "min_speed_m": 2440.0, "end_m": 2515.0, "min_speed_kph": 143.0},
        {"id": 5, "start_m": 4030.0, "min_speed_m": 4070.0, "end_m": 4140.0, "min_speed_kph": 85.0, "apex_gear": 2},
    ]
    return {
        "lap": -1, "valid": True, "lap_time_s": 96.4,
        "lap_start_anchored": True, "_samples": samples, "sections": sections,
    }


def _install_melbourne_map(monkeypatch):
    key = "MELBOURNE"
    monkeypatch.setitem(track_maps.LEARNED_TRACK_TURNS, key, _melbourne_markers())
    monkeypatch.setitem(track_maps.LEARNED_TRACK_LENGTHS, key, 5300.0)


def test_external_reference_metadata_recovers_track_name_for_map_turn_authority(monkeypatch):
    _install_melbourne_map(monkeypatch)
    recorder = MeasuredPerformanceRecorder()
    recorder.set_external_reference(
        _legacy_tt_rival_reference(), name="TT rival",
        metadata={"track_id": 0, "track_length_m": 5300.0},
    )
    ref = recorder.external_reference
    assert ref["track_name"] == "MELBOURNE"
    turns = physical_turn_boundaries(ref)
    assert [t["corner_id"] for t in turns] == list(range(1, 15))
    assert all(t["physical_geometry"] for t in turns)
    assert all(t["physical_source"] == "stored_track_map" for t in turns)


def test_detector_section_five_attaches_to_physical_turn_eleven(monkeypatch):
    _install_melbourne_map(monkeypatch)
    recorder = MeasuredPerformanceRecorder()
    recorder.set_external_reference(
        _legacy_tt_rival_reference(), name="TT rival",
        metadata={"track_id": 0, "track_length_m": 5300.0},
    )
    ref = recorder.external_reference
    turns = physical_turn_boundaries(ref)
    t11 = next(t for t in turns if t["corner_id"] == 11)
    assert t11["reference_section_id"] == 5
    assert t11["brake_m"] == 4030.0

    seeded = IntegratedLiveCoach._reference_seed_advice(ref)
    assert sorted(seeded) == list(range(1, 15))
    assert seeded[11]["reference_brake_m"] == 4030.0
    assert seeded[5]["reference_brake_m"] != 4030.0


def test_turn_coach_header_uses_same_physical_segment_as_map(monkeypatch):
    _install_melbourne_map(monkeypatch)
    recorder = MeasuredPerformanceRecorder()
    recorder.set_external_reference(
        _legacy_tt_rival_reference(), name="TT rival",
        metadata={"track_id": 0, "track_length_m": 5300.0},
    )
    ref = recorder.external_reference
    segments = _track_segments(ref, 5300.0, track_name="Melbourne")
    active = _active_segment(ref, 4063.0, 5300.0, segments=segments)
    assert active is not None
    assert active["kind"] == "turn"
    assert active["number"] == 11
    assert active["section_id"] == 5


def test_distance_pipeline_uses_stored_physical_turns_for_worldless_reference(monkeypatch):
    _install_melbourne_map(monkeypatch)
    recorder = MeasuredPerformanceRecorder()
    recorder.set_external_reference(
        _legacy_tt_rival_reference(), name="TT rival",
        metadata={"track_id": 0, "track_length_m": 5300.0},
    )
    ref = recorder.external_reference
    current = dict(ref)
    current["track_name"] = "MELBOURNE"
    current["_samples"] = {d: dict(row, t=float(row["t"]) + (0.10 if d >= 4030.0 else 0.0)) for d, row in ref["_samples"].items()}
    model = build_distance_performance_model(current, ref)
    assert model["available"] is True
    assert len(model["turns"]) == 14
    t11 = next(t for t in model["turns"] if t["corner_id"] == 11)
    assert t11["reference_section_id"] == 5
