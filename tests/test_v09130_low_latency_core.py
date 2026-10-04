from src.race_state.models import CarState
from src.race_state_receiver import RaceStateReceiver
from src.telemetry_recording import ReplayController, _CHECKPOINT_PACKET_INTERVAL


def test_replay_checkpoint_is_serialized_and_roundtrips_engine_state():
    receiver = RaceStateReceiver(tts_enabled=False)
    receiver.engine.state.session.uid = 9913
    receiver.engine.state.player_index = 0
    receiver.engine.state.player = CarState(index=0)
    receiver.engine.state.player.lap.current_lap = 4
    receiver._decoded_packet_at[2] = 12.5

    checkpoint = receiver.export_replay_checkpoint()
    assert isinstance(checkpoint, bytes)

    receiver.engine.state.player.lap.current_lap = 9
    receiver._decoded_packet_at[2] = 99.0
    receiver.restore_replay_checkpoint(checkpoint)

    assert receiver.engine.state.session.uid == 9913
    assert receiver.engine.state.player.lap.current_lap == 4
    assert receiver._decoded_packet_at[2] == 12.5
    receiver.speech.close(wait=False)


class _CheckpointReceiver:
    def __init__(self):
        self.engine = type("E", (), {})()
        state = type("S", (), {})()
        state.player = type("P", (), {})()
        state.player.lap = type("L", (), {"current_lap": 1})()
        self.engine.state = state
        self.exports = 0

    def export_replay_checkpoint(self):
        self.exports += 1
        return b"checkpoint-" + str(self.exports).encode()


def test_replay_controller_caches_periodic_checkpoint_within_same_lap(tmp_path):
    # The controller only needs a valid tiny replay file for construction.
    from src.telemetry_recording import TelemetrySessionRecorder
    path = tmp_path / "checkpoint.areplay"
    recorder = TelemetrySessionRecorder(path=path)
    recorder.record(b"a", 1.0)
    recorder.close()

    controller = ReplayController(path)
    receiver = _CheckpointReceiver()

    controller._cache_checkpoint_if_new_lap(receiver, 1)
    first_exports = receiver.exports
    assert first_exports == 1  # initial lap boundary

    controller._cache_checkpoint_if_new_lap(receiver, 1 + _CHECKPOINT_PACKET_INTERVAL - 1)
    assert receiver.exports == first_exports

    controller._cache_checkpoint_if_new_lap(receiver, 1 + _CHECKPOINT_PACKET_INTERVAL)
    assert receiver.exports == first_exports + 1
