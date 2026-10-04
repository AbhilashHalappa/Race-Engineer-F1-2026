from pathlib import Path
import ast


def _load_epoch_helper():
    source = Path('src/overlay/widgets.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_current_distance_epoch_start')
    mod = ast.Module(body=[fn], type_ignores=[])
    ns = {}
    exec(compile(mod, '<epoch-helper>', 'exec'), ns)
    return ns['_current_distance_epoch_start']


def test_epoch_starts_after_real_lap_distance_wrap():
    fn = _load_epoch_helper()
    assert fn([4300.0, 4500.0, 4700.0, 3.0, 40.0, 120.0]) == 3


def test_small_distance_jitter_does_not_split_epoch():
    fn = _load_epoch_helper()
    assert fn([100.0, 120.0, 118.5, 140.0]) == 0


def test_multiple_wraps_keep_only_newest_epoch():
    fn = _load_epoch_helper()
    assert fn([5000.0, 10.0, 100.0, 5100.0, 5.0, 50.0]) == 4


def test_input_trace_renderer_filters_older_distance_epoch():
    source = Path('src/overlay/widgets.py').read_text(encoding='utf-8')
    section = source.split('class InputTraceWidget', 1)[1].split('class ERSBatteryTraceWidget', 1)[0]
    assert 'epoch_start = _current_distance_epoch_start(distances)' in section
    assert 'if i < epoch_start:' in section


def test_ers_renderer_filters_older_distance_epoch():
    source = Path('src/overlay/widgets.py').read_text(encoding='utf-8')
    section = source.split('class ERSBatteryTraceWidget', 1)[1].split('class DeltaTraceWidget', 1)[0]
    assert 'epoch_start = _current_distance_epoch_start(ds_all)' in section
    assert 'if i < epoch_start:' in section


def test_release_banner():
    source = Path('src/main.py').read_text(encoding='utf-8')
    assert 'V0.9.17.2.9.10 CURRENT-LAP TRACE ISOLATION' in source
