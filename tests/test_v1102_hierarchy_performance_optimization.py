from pathlib import Path
from types import SimpleNamespace as NS

from src.corner_coach import CornerCoachEngine
from src.measured_performance import MeasuredPerformanceRecorder, Sample
from src.race_state_receiver import RaceStateReceiver


def test_corner_coach_master_preserves_child_preferences_and_restores_mixed_state():
    cc = CornerCoachEngine()
    cc.set_feature("VOICE", True)
    cc.set_feature("PRE", True)
    cc.set_feature("POST", False)
    cc.set_feature("GAINLOSS", True)
    assert cc.preference_states() == {"CCVOICE": True, "CCPRE": True, "CCPOST": False, "GAINLOSS": True, "GAINLOSSVOICE": False}

    cc.set_feature("CORNER", False)
    assert cc.feature_states() == {"CORNER": False, "CCVOICE": False, "CCPRE": False, "CCPOST": False, "GAINLOSS": False, "GAINLOSSVOICE": False}
    assert cc.preference_states() == {"CCVOICE": True, "CCPRE": True, "CCPOST": False, "GAINLOSS": True, "GAINLOSSVOICE": False}

    cc.set_feature("CORNER", True)
    assert cc.feature_states() == {"CORNER": True, "CCVOICE": True, "CCPRE": True, "CCPOST": False, "GAINLOSS": True, "GAINLOSSVOICE": False}


def test_race_engineer_master_preserves_child_preferences_and_restores_mixed_state():
    receiver = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    receiver.set_coaching_feature("LAP", True)
    receiver.set_coaching_feature("POS", False)
    receiver.set_coaching_feature("RACE", True)

    receiver.set_automatic_engineer_voice_enabled(False)
    states = receiver.coaching_feature_states()
    assert states["ENGR"] is False
    assert states["LAP"] is False
    assert states["POS"] is False
    assert states["RACE"] is False
    # Stored preferences were not destroyed.
    assert receiver.live_coach.settings.lap_summary is True
    assert receiver.live_coach.settings.positive_calls is False
    assert receiver.live_coach.settings.race_coaching is True

    receiver.set_automatic_engineer_voice_enabled(True)
    states = receiver.coaching_feature_states()
    assert states["ENGR"] is True
    assert states["LAP"] is True
    assert states["POS"] is False
    assert states["RACE"] is True


def test_corner_coach_prefers_lightweight_current_lap_trace_snapshot():
    calls = []
    recorder = NS(
        current_lap_trace_snapshot=lambda state: calls.append("trace") or {"_samples": {}},
        current_lap_snapshot=lambda state: calls.append("summary") or {"_samples": {}},
    )
    out = CornerCoachEngine._current_lap(recorder, object())
    assert out == {"_samples": {}}
    assert calls == ["trace"]


def test_measured_performance_lightweight_trace_keeps_sample_objects():
    recorder = MeasuredPerformanceRecorder()
    recorder.current_lap = 2
    recorder.current_lap_started_clean = True
    recorder.current_lap_valid = True
    sample = Sample(5.0, 0.1, 100.0, 0.5, 0.0, 0.1, 3, 9000)
    recorder.samples = {5.0: sample}
    state = NS(
        session=NS(track=NS(name="MELBOURNE"), track_length_m=5300.0),
        player=NS(lap=NS(current_lap_time_s=0.1)),
    )
    snap = recorder.current_lap_trace_snapshot(state)
    assert snap is not None
    assert snap["_samples"][5.0] is sample
    assert snap["track_length_m"] == 5300.0


def test_ui_has_state_preserving_hierarchy_quality_gradient_and_static_map_cache():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert "def _sync_dependency_controls" in source
    assert "previous setting will return when ENGR is ON" in source
    assert "previous setting will return when CC is ON" in source
    assert "def _quality" in source
    assert "QLinearGradient" in source
    assert "'GOOD'" in source and "'CLOSE'" in source and "'WORK'" in source and "'OFF'" in source
    assert "_static_layer_key" in source
    assert "QPixmap" in source
    assert "if self.corner_coach.isVisible()" in source


def test_corner_coach_hot_path_skips_unused_channel_delta_interpolation():
    source = Path("src/corner_coach.py").read_text(encoding="utf-8")
    assert "include_channel_deltas=False" in source
    assert "self._performance_boundaries" in source
    assert "current_lap_trace_snapshot" in source
