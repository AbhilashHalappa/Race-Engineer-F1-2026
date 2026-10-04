from pathlib import Path
from src.race_state_receiver import RaceStateReceiver
from src.telemetry_recording import ReplayController


def test_replay_controller_can_start_empty_for_live_mode():
    controller = ReplayController(None)
    assert controller.current_file() is None
    assert controller.status().total == 0


def test_receiver_source_gate_ignores_live_packets_during_replay():
    receiver = RaceStateReceiver(tts_enabled=False, wheel_telemetry=False)
    receiver.set_telemetry_mode("replay", replay_thread_id=-12345)
    receiver.process_packet(b"bad", ("127.0.0.1", 20777), 0.0)
    assert receiver.total_packets == 0
    receiver.set_telemetry_mode("live")
    receiver.process_packet(b"bad", ("127.0.0.1", 20777), 0.0)
    assert receiver.total_packets == 1


def test_control_center_replay_status_is_clickable():
    source = Path("src/overlay/window.py").read_text(encoding="utf-8")
    assert '"Replay": on_toggle_replay' in source
    assert 'self.set_replay_mode(enabled)' in source
    assert 'click Replay to start' in source
