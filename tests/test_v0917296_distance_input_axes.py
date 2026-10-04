from pathlib import Path


def test_current_banner_v0917296():
    source = Path('src/main.py').read_text(encoding='utf-8')
    assert 'V0.9.17.2.9.6 DISTANCE-ALIGNED INPUT GRAPH AXES' in source


def test_input_trace_records_and_draws_distance_axis():
    source = Path('src/overlay/widgets.py').read_text(encoding='utf-8')
    assert 'self.distances = deque' in source
    assert 'def add_sample(self, throttle: float, brake: float, distance_m=None)' in source
    assert 'Track-distance axis' in source
    assert 'f"{d:.0f} m"' in source


def test_driver_and_reference_feed_same_track_distance_to_graphs():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'self.input_trace.add_sample(s.throttle, s.brake, s.lap_distance_m)' in source
    assert 'self.input_trace.add_sample(s.reference_throttle or 0.0, s.reference_brake or 0.0, s.lap_distance_m)' in source


def test_ers_graphs_receive_distance_too():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 's.lap_time_s, s.lap_distance_m)' in source
    assert 's.reference_time_s, s.lap_distance_m)' in source
