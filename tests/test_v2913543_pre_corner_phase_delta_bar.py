from pathlib import Path

from src.pre_corner_delta import phase_delta_payload, phase_target, update_driver_events


ROOT = Path(__file__).resolve().parents[1]
WINDOW = (ROOT / "src" / "overlay" / "window.py").read_text(encoding="utf-8")


def _zone():
    return {
        "zone_id": "Z1",
        "start_m": 120.0,
        "end_m": 250.0,
        "approach_start_m": 80.0,
        "corner_ids": [1, 2],
        "brake_start_m": 100.0,
        "brake_release_m": 145.0,
        "apex_m": 180.0,
        "throttle_start_m": 210.0,
        "full_throttle_m": 235.0,
    }


def test_phase_targets_are_brake_turn_in_and_throttle_reference_points():
    corners = (
        {"corner_id": 1, "start_m": 120.0, "apex_m": 180.0},
        {"corner_id": 2, "start_m": 190.0, "apex_m": 225.0},
    )
    zone = _zone()

    assert phase_target(corners, zone, "BRAKING") == ("brake_m", "BRAKE", 100.0)
    assert phase_target(corners, zone, "ENTRY") == ("brake_release_m", "BRAKE RELEASE", 145.0)
    # Without trusted steering input, turn-in uses the existing deterministic
    # physical-corner geometry rather than inventing ghost steering.
    assert phase_target(corners, zone, "TURN-IN", input_telemetry_trusted=False) == ("turn_in_m", "TURN-IN", 150.0)
    assert phase_target(corners, zone, "APEX", input_telemetry_trusted=False) == ("apex_m", "APEX", 180.0)
    assert phase_target(corners, zone, "EXIT") == ("throttle_m", "THROTTLE PICKUP", 210.0)
    assert phase_target(corners, zone, "THROTTLE") == ("full_throttle_m", "FULL THROTTLE", 235.0)

    trusted_zone=dict(zone,event_ids=["E1","E2"])
    events=(
        {"event_id":"E1","kind":"steering","start_m":142.0,"end_m":170.0},
        {"event_id":"E2","kind":"steering_reversal","start_m":155.0,"end_m":155.0},
    )
    assert phase_target(corners,trusted_zone,"TURN-IN",events,input_telemetry_trusted=True) == ("turn_in_m","TURN-IN",142.0)


def test_driver_events_capture_first_brake_turn_in_and_throttle_positions():
    zone = _zone()
    events = update_driver_events({}, zone, 92.0, brake=0.25, steering=0.0, throttle=0.0)
    assert events["brake_m"] == 92.0

    events = update_driver_events(events, zone, 140.0, brake=0.0, steering=0.20, throttle=0.0)
    assert events["turn_in_m"] == 140.0

    events = update_driver_events(events, zone, 220.0, brake=0.0, steering=0.0, throttle=0.35)
    assert events["throttle_m"] == 220.0

    # Original first events remain frozen even as the expanded presentation
    # captures later ENTRY / THROTTLE events for the new six-step sequence.
    events = update_driver_events(events, zone, 230.0, brake=0.9, steering=0.9, throttle=1.0)
    assert events["brake_m"] == 92.0
    assert events["turn_in_m"] == 140.0
    assert events["throttle_m"] == 220.0


def test_phase_delta_payload_reports_early_late_match_and_live_lateness():
    early = phase_delta_payload("BRAKE", 100.0, 92.0, 105.0, "BRAKING")
    assert early["delta_m"] == -8.0
    assert early["status"] == "early"
    assert early["provisional"] is False

    late = phase_delta_payload("THROTTLE", 210.0, 220.0, 220.0, "EXIT")
    assert late["delta_m"] == 10.0
    assert late["status"] == "late"
    assert late["provisional"] is False

    matched = phase_delta_payload("TURN-IN", 150.0, 150.5, 160.0, "TURN-IN")
    assert matched["status"] == "matched"

    live = phase_delta_payload("BRAKE", 100.0, None, 112.0, "BRAKING")
    assert live["delta_m"] == 12.0
    assert live["status"] == "late"
    assert live["provisional"] is True


def test_pre_corner_bar_is_phase_delta_comparator_not_corner_progress_fill():
    block = WINDOW.split("class ProgressivePreCornerOverlayWindow", 1)[1].split("class LiveCornerFeedbackOverlayWindow", 1)[0]
    assert "phase_delta=self._phase_delta" in block
    assert "_pre_update_driver_events" in block
    assert "_pre_phase_target" in block
    assert "_pre_phase_delta_payload" in block
    assert "EARLY" in block and "REF" in block and "LATE" in block
    assert "MATCHED REF" in block
    assert "WAITING FOR DRIVER INPUT" in block
    assert "float(delta_m)/40.0" in block
    assert "w*progress" not in block
    assert "HANDOFF → POST CORNER FEEDBACK" in block
    # Whole-lap time delta is no longer substituted for the phase-action delta.
    assert "getattr(self.snapshot,'live_delta_s'" not in block
