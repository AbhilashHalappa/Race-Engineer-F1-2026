from pathlib import Path

WINDOW = Path('src/overlay/window.py').read_text(encoding='utf-8')
MAIN = Path('src/main.py').read_text(encoding='utf-8')


def test_input_timer_is_precise_10ms():
    assert 'self.input_timer.setTimerType(Qt.PreciseTimer)' in WINDOW
    assert 'self.input_timer.start(10)' in WINDOW
    assert 'self.input_timer.timeout.connect(self.refresh_inputs)' in WINDOW


def test_di_is_master_sampling_gate_for_reference():
    assert 'progressed = bool(self.driver.update_snapshot(snapshot))' in WINDOW
    assert 'self.reference_driver.update_snapshot(snapshot, append_sample=progressed)' in WINDOW
    assert 'def update_snapshot(self,s, *, append_sample=True):' in WINDOW
    assert 'if append_sample and s.reference_time_s is not None:' in WINDOW


def test_global_refresh_does_not_double_sample_di_ri():
    refresh = WINDOW.split('    def refresh(self):', 1)[1].split('    def toggle_pause(self):', 1)[0]
    assert 'self.driver.update_snapshot(snapshot)' not in refresh
    assert 'self.reference_driver.update_snapshot(snapshot)' not in refresh


def test_pause_freezes_input_sampler():
    block = WINDOW.split('    def refresh_inputs(self):',1)[1].split('    def refresh(self):',1)[0]
    assert 'if status.rebuilding or status.paused:' in block
    assert 'if self._paused:' in block


def test_release_banner():
    assert 'V0.9.17.2.9.9 10MS DI-MASTER INPUT SAMPLING' in MAIN
