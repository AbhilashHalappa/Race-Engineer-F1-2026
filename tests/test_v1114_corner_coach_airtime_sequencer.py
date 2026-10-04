from __future__ import annotations

import inspect
import json
import time
from types import SimpleNamespace as NS

import pytest

from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, PhysicalCorner, ReferenceTrace
from src.corner_coach_validation import CornerCoachValidationRecorder, analyze_validation_file
from src.engineer.models import EngineerMessage, Priority, estimate_speech_duration_s
from src.main import main
from src.overlay.data import _live_coach_metrics
from src.tts import SpeechOutput, TTSConfig


def _model() -> ReferenceTrace:
    corner = PhysicalCorner(5, "T5", 100.0, 150.0, 200.0, "RIGHT", 1.0)
    zone = CoachingZone("Z5", 100.0, 200.0, 80.0, (5,), brake_start_m=80.0,
                        apex_m=150.0, reference_min_speed_kph=150.0, label="T5")
    samples = tuple({"d": float(d), "t": float(d) / 50.0, "speed": 180.0}
                    for d in range(0, 501, 5))
    return ReferenceTrace(
        "TEST", 500.0, 10.0, 5.0, samples, (corner,), (), (zone,),
        metadata={}, quality={"input_telemetry_trusted": False},
    )


def _msg(key: str, text: str, *, deadline_in: float | None = None,
         estimated: float | None = None) -> EngineerMessage:
    now = time.monotonic()
    return EngineerMessage(
        key, Priority.COACHING, text, now, 0.0,
        deadline_at_monotonic_s=(now + deadline_in) if deadline_in is not None else None,
        estimated_duration_s=estimated,
    )


def _prime_current(speech: SpeechOutput, message: EngineerMessage, *, remaining_s: float) -> None:
    with speech._lock:
        speech._current_message = message
        speech._current_rank = speech._radio_rank(message)
        speech._current_expected_end_at = time.monotonic() + remaining_s


def test_speech_duration_estimate_increases_with_message_length():
    short = estimate_speech_duration_s("T5, next.")
    long = estimate_speech_duration_s("Turn five coming up, minimum one hundred and fifty kph, focus on the exit.")
    assert short >= 0.45
    assert long > short


def test_post_may_finish_only_when_pre_still_fits_before_deadline():
    speech = SpeechOutput(TTSConfig(enabled=False))
    post = _msg("corner:post:2:Z4:min_speed_low", "T4, lost two tenths.", estimated=1.2)
    _prime_current(speech, post, remaining_s=1.0)

    pre = _msg("corner:pre:2:Z5", "T5 coming up.", deadline_in=4.0, estimated=1.2)
    preempt, outcome, details = speech._should_preempt_current(pre, speech._radio_rank(pre))
    assert preempt is False
    assert outcome == "POST_FINISH_ALLOWED_BEFORE_PRE"
    assert details["pre_deadline_in_s"] > details["pre_required_s"]

    urgent = _msg("corner:pre:2:Z5", "T5 coming up.", deadline_in=1.7, estimated=1.2)
    preempt, outcome, _ = speech._should_preempt_current(urgent, speech._radio_rank(urgent))
    assert preempt is True
    assert outcome == "POST_PREEMPTED_FOR_PRE"


def test_new_pre_can_preempt_older_pre_when_tight_corners_do_not_fit():
    speech = SpeechOutput(TTSConfig(enabled=False))
    old_pre = _msg("corner:pre:2:Z9", "T12 coming up.", estimated=1.6)
    _prime_current(speech, old_pre, remaining_s=1.5)

    next_pre = _msg("corner:pre:2:Z10", "T13 to T14 coming up.", deadline_in=2.2, estimated=1.3)
    preempt, outcome, _ = speech._should_preempt_current(next_pre, speech._radio_rank(next_pre))
    assert preempt is True
    assert outcome == "PRE_PREEMPTED_FOR_NEXT_PRE"

    roomy = _msg("corner:pre:2:Z10", "T13 to T14 coming up.", deadline_in=4.0, estimated=1.3)
    preempt, outcome, _ = speech._should_preempt_current(roomy, speech._radio_rank(roomy))
    assert preempt is False
    assert outcome == "PRE_FINISH_ALLOWED_BEFORE_NEXT_PRE"


def test_deadline_gate_never_starts_corner_pre_that_cannot_finish():
    events = []
    speech = SpeechOutput(
        TTSConfig(enabled=False),
        on_delivery_event=lambda message, outcome, details: events.append((message.key, outcome, details)),
    )
    pre = _msg("corner:pre:3:Z6", "T8 coming up.", deadline_in=0.20, estimated=1.0)
    assert speech._deadline_allows(pre, 1.0) is False
    assert events and events[-1][1] == "PRE_NO_AIRTIME"


def test_variant_selector_prefers_full_then_compact_then_drop():
    full = "Turn five coming up, reference slows in about three hundred metres, minimum about one hundred kph."
    compact = "T5, three hundred metres."
    full_est = estimate_speech_duration_s(full)
    compact_est = estimate_speech_duration_s(compact)
    margin = CornerCoachEngine.SPEECH_FINISH_MARGIN_S

    choice = CornerCoachEngine._choose_speech_variant(full, compact, full_est + margin + 0.1, margin_s=margin)
    assert choice is not None and choice[2] == "full"

    choice = CornerCoachEngine._choose_speech_variant(full, compact, compact_est + margin + 0.1, margin_s=margin)
    assert choice is not None and choice[2] == "compact"

    choice = CornerCoachEngine._choose_speech_variant(full, compact, compact_est + margin - 0.05, margin_s=margin)
    assert choice is None


def test_rival_pace_turn_overlay_hides_untrusted_brake_and_throttle_but_uses_clean_speed():
    performance = NS(samples={
        100.0: {"d": 100.0, "speed": 170.0, "brake": 1.0, "throttle": 0.0},
        140.0: {"d": 140.0, "speed": 142.0, "brake": 0.0, "throttle": 1.0},
        150.0: {"d": 150.0, "speed": 145.0, "brake": 0.0, "throttle": 1.0},
    })
    # Raw reference values are deliberately nonsense. They must not be consulted.
    reference = {"_samples": {100.0: {"d": 100.0, "speed": 999.0, "brake": 0.75, "throttle": 0.25}}}
    trusted = ({
        "corner_id": 5, "start_m": 100.0, "end_m": 200.0,
        "min_speed_m": 140.0, "min_speed_kph": 150.0, "exit_speed_kph": 190.0,
    },)
    metrics = _live_coach_metrics(
        performance, reference, 5, 150.0,
        input_telemetry_trusted=False, trusted_turn_metrics=trusted,
    )
    by_label = {m.label: m for m in metrics}
    assert by_label["Braking Point"].status == "WAIT"
    assert by_label["Throttle Timing"].status == "WAIT"
    assert by_label["Min Speed"].status == "SLOWER"
    assert "8 kph slower" in by_label["Min Speed"].value
    assert by_label["Exit Speed"].status == "WAIT"


def test_session_recording_is_off_by_default():
    assert inspect.signature(main).parameters["record_telemetry"].default is False


def test_validation_trace_records_delivery_outcome(tmp_path):
    recorder = CornerCoachValidationRecorder(tmp_path)
    model = _model()
    recorder.ensure_run(session_uid=123, track_name="TEST", model=model)
    recorder.begin_lap(2, distance_m=50.0)
    msg = _msg("corner:post:2:Z5:min_speed_low", "T5, lost two tenths.", deadline_in=1.0, estimated=1.5)
    recorder.radio_submit(msg)
    recorder.delivery_event(msg, "POST_NO_AIRTIME", remaining_s=0.5, required_s=1.5)
    recorder.finish_lap(reason="test")
    recorder.flush()
    path = recorder.path
    recorder.close()

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    delivery = next(row for row in rows if row.get("event") == "radio_delivery")
    assert delivery["outcome"] == "POST_NO_AIRTIME"
    summary = next(row for row in rows if row.get("event") == "lap_summary")
    outcomes = summary["checks"]["radio_delivery_outcomes"]
    assert outcomes["corner:post:2:Z5"]["POST_NO_AIRTIME"] == 1

    report = analyze_validation_file(path)
    assert any(key.endswith("|POST_NO_AIRTIME") for key in report["delivery_outcomes"])
