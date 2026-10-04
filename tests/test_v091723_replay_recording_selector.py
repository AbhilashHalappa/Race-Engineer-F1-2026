from pathlib import Path

from src.telemetry_recording import ReplayController, TelemetrySessionRecorder


def _make_replay(path: Path, payloads):
    rec = TelemetrySessionRecorder(path=path)
    for i, payload in enumerate(payloads):
        rec.record(payload, now=100.0 + i * 0.02)
    rec.close()


def test_replay_controller_can_hot_load_new_recording(tmp_path):
    a = tmp_path / 'a.areplay'
    b = tmp_path / 'b.areplay'
    _make_replay(a, [b'a1', b'a2'])
    _make_replay(b, [b'b1', b'b2', b'b3'])
    controller = ReplayController(a)
    assert controller.status().total == 2
    assert controller.load_file(b, autoplay=True) == 3
    status = controller.status()
    assert status.total == 3
    assert status.position == 0
    assert not status.paused
    assert Path(controller.current_file()) == b


def test_control_center_contains_replay_recording_selector():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'REPLAY RECORDING' in source
    assert 'refresh_replay_options' in source
    assert '_select_replay_recording' in source
    assert 'recordings' in source and '*.areplay' in source


def test_current_banner():
    source = Path('src/main.py').read_text(encoding='utf-8')
    assert 'V0.9.17.2.3 REPLAY RECORDING SELECTOR' in source

def test_replay_browser_cli_exists():
    source = Path('src/main.py').read_text(encoding='utf-8')
    assert '--replay-browser' in source
    assert 'recordings' in source and '*.areplay' in source
