from pathlib import Path

from src.pre_corner_delta import phase_target, presentation_phase, update_driver_events

ROOT = Path(__file__).resolve().parents[1]
WINDOW = (ROOT / "src" / "overlay" / "window.py").read_text(encoding="utf-8")


def _zone():
    return {
        "zone_id": "Z1",
        "start_m": 120.0,
        "end_m": 250.0,
        "approach_start_m": 80.0,
        "corner_ids": [1],
        "brake_start_m": 100.0,
        "brake_release_m": 145.0,
        "apex_m": 180.0,
        "throttle_start_m": 210.0,
        "full_throttle_m": 235.0,
    }


def _corners():
    return ({"corner_id": 1, "start_m": 120.0, "apex_m": 180.0},)


def test_presentation_phase_walks_all_six_states_in_order():
    z = _zone()
    c = _corners()
    seen = []
    for d in range(100, 251):
        ph = presentation_phase(c, z, float(d), input_telemetry_trusted=False)
        if ph not in seen:
            seen.append(ph)
    assert seen == ["BRAKE", "ENTRY", "TURN-IN", "APEX", "EXIT", "THROTTLE"]


def test_each_visible_phase_has_its_own_reference_event():
    z = _zone(); c = _corners()
    assert phase_target(c,z,"BRAKE",input_telemetry_trusted=False) == ("brake_m","BRAKE",100.0)
    assert phase_target(c,z,"ENTRY",input_telemetry_trusted=False) == ("brake_release_m","BRAKE RELEASE",145.0)
    assert phase_target(c,z,"TURN-IN",input_telemetry_trusted=False) == ("turn_in_m","TURN-IN",150.0)
    assert phase_target(c,z,"APEX",input_telemetry_trusted=False) == ("apex_m","APEX",180.0)
    assert phase_target(c,z,"EXIT",input_telemetry_trusted=False) == ("throttle_m","THROTTLE PICKUP",210.0)
    assert phase_target(c,z,"THROTTLE",input_telemetry_trusted=False) == ("full_throttle_m","FULL THROTTLE",235.0)


def test_driver_event_capture_adds_release_apex_and_full_throttle_without_core_changes():
    z=_zone(); e={}
    e=update_driver_events(e,z,98.0,brake=.4,steering=0,throttle=0,speed=220)
    assert e["brake_m"]==98.0
    e=update_driver_events(e,z,142.0,brake=.03,steering=.15,throttle=0,speed=145)
    assert e["brake_release_m"]==142.0 and e["turn_in_m"]==142.0
    e=update_driver_events(e,z,178.0,brake=0,steering=.4,throttle=.05,speed=112)
    e=update_driver_events(e,z,184.0,brake=0,steering=.3,throttle=.15,speed=116)
    assert e["apex_m"]==178.0
    e=update_driver_events(e,z,206.0,brake=0,steering=.1,throttle=.30,speed=150)
    assert e["throttle_m"]==206.0
    e=update_driver_events(e,z,232.0,brake=0,steering=0,throttle=.96,speed=205)
    assert e["full_throttle_m"]==232.0


def test_overlay_has_visible_phase_strip_and_larger_information_fonts():
    block = WINDOW.split("class ProgressivePreCornerOverlayWindow",1)[1].split("class LiveCornerFeedbackOverlayWindow",1)[0]
    assert 'PHASES=("BRAKE","ENTRY","TURN-IN","APEX","EXIT","THROTTLE")' in block
    assert "_draw_phase_strip" in block
    assert "QFont('Segoe UI',20,QFont.Bold)" in block
    assert "QFont('Segoe UI',11,QFont.Bold)" in block
    assert "QFont('Segoe UI',9,QFont.Bold)" in block
    assert "WIDTH=430; HEIGHT=224" in block
    assert "w*progress" not in block
