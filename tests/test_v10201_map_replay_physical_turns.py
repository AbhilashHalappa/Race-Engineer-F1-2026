import math
from pathlib import Path
import src.overlay.track_maps as track_maps
from src.distance_performance import physical_turn_boundaries
from src.track_geometry import measured_world_trace


def test_async_start_finish_motion_spike_is_removed_from_live_trace():
    # Reproduces the Shanghai failure shape: lap distance resets at S/F before
    # the most recent motion packet catches up, producing an impossible ~250 m
    # first segment if UI snapshots are joined directly.
    samples = {
        0.0: {'world_x': 16.8, 'world_z': 315.4},
        5.0: {'world_x': 265.4, 'world_z': 290.6},
        10.0: {'world_x': 260.6, 'world_z': 291.6},
        15.0: {'world_x': 255.8, 'world_z': 292.6},
        20.0: {'world_x': 251.0, 'world_z': 293.6},
    }
    trace = measured_world_trace(samples, require_start=True)
    assert trace
    assert trace[0][0] == 5.0
    jumps = [math.hypot(b[1]-a[1], b[2]-a[2]) for a, b in zip(trace, trace[1:])]
    assert max(jumps) < 20.0


def test_corrupt_dedicated_geometry_rejects_stale_turns_as_one_payload():
    key = 'TEST CORRUPT SHANGHAI'
    for store in (track_maps.LEARNED_TRACK_MAPS, track_maps.LEARNED_TRACK_DISTANCES,
                  track_maps.LEARNED_TRACK_LENGTHS, track_maps.LEARNED_TRACK_TURNS):
        store.pop(key, None)
    points = [[0.0, 0.0], [249.8, 0.0]] + [[249.8 + i * 3.0, 0.0] for i in range(1, 30)]
    payload = {
        'version': 3, 'track': key, 'points': points,
        'turns': [{'corner_id': i, 'label': f'T{i}', 'lap_distance_m': i * 100.0} for i in range(1, 12)],
    }
    assert track_maps._ingest_track_payload(key, payload) is False
    assert key not in track_maps.LEARNED_TRACK_MAPS
    assert key not in track_maps.LEARNED_TRACK_TURNS


def _circle_reference(track_name='SHANGHAI', length=5000.0):
    samples = {}
    radius = length / (2.0 * math.pi)
    for i in range(1000):
        d = i * 5.0
        angle = 2.0 * math.pi * d / length
        samples[d] = {
            'd': d, 't': d / 60.0,
            'world_x': radius * math.cos(angle),
            'world_z': radius * math.sin(angle),
            'speed': 216.0, 'throttle': 1.0, 'brake': 0.0,
        }
    sections = [
        {'id': 7, 'start_m': 430.0, 'turn_in_m': 460.0, 'min_speed_m': 500.0, 'end_m': 560.0},
        {'id': 22, 'start_m': 1420.0, 'turn_in_m': 1450.0, 'min_speed_m': 1500.0, 'end_m': 1570.0},
        {'id': 91, 'start_m': 2420.0, 'turn_in_m': 2460.0, 'min_speed_m': 2500.0, 'end_m': 2580.0},
    ]
    return {'track_name': track_name, 'track_length_m': length, '_samples': samples, 'sections': sections}


def test_shanghai_physical_turn_authority_is_geometry_not_brake_section_count():
    reference = _circle_reference()
    turns = physical_turn_boundaries(reference)
    assert len(turns) == 16  # Shanghai physical count, not the three brake sections.
    assert [t['corner_id'] for t in turns] == list(range(1, 17))
    assert all(t['physical_geometry'] is True for t in turns)
    attached = [t['reference_section_id'] for t in turns if t['reference_section_id'] is not None]
    assert set(attached).issubset({7, 22, 91})


def test_first_replay_toggle_auto_loads_visible_recording_before_switching_source():
    source = (Path(__file__).resolve().parents[1] / 'src' / 'overlay' / 'window.py').read_text(encoding='utf-8')
    method = source[source.index('    def _toggle_runtime_feature(self, name):'):source.index('    def set_runtime_statuses', source.index('    def _toggle_runtime_feature(self, name):'))]
    assert 'self.replay_combo.currentData()' in method
    assert 'preload = self._on_select_replay(value)' in method
    assert method.index('preload = self._on_select_replay(value)') < method.index('result = callback(enabled)')


def test_native_player_marker_prefers_live_world_position_over_distance_axis():
    source = (Path(__file__).resolve().parents[1] / 'src' / 'overlay' / 'window.py').read_text(encoding='utf-8')
    method = source[source.index('    def _track_marker_point(self, snapshot, points, source):'):source.index('    def _distance_marker_point', source.index('    def _track_marker_point(self, snapshot, points, source):'))]
    assert 'world_position_x' in method
    assert 'world_position_z' in method
    assert method.index('world_position_x') < method.index('lap_distance =')
    assert 'return (float(world_x), float(world_z))' in method


def test_lan_player_marker_prefers_live_world_position_over_distance_axis():
    source = (Path(__file__).resolve().parents[1] / 'src' / 'dashboard_server.py').read_text(encoding='utf-8')
    marker = "let player=(Number.isFinite(s.world_position_x)&&Number.isFinite(s.world_position_z))?[s.world_position_x,s.world_position_z]:(pre?fracPoint(s.lap_distance_m):pts[pts.length-1]);"
    assert marker in source
