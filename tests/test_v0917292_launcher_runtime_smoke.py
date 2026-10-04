from pathlib import Path
import ast

SOURCE = Path('src/overlay/window.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)


def _class(name):
    return next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == name)


def _method(cls, name):
    return next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def test_coach_constructor_does_not_reference_control_center_dispatch_state():
    coach = _class('CoachOverlayWindow')
    init = _method(coach, '__init__')
    names = {n.id for n in ast.walk(init) if isinstance(n, ast.Name)}
    assert 'on_show_overlay' not in names


def test_control_center_has_direct_launcher_method():
    cc = _class('ControlCenterWindow')
    init = _method(cc, '__init__')
    args = {a.arg for a in init.args.args + init.args.kwonlyargs}
    assert 'on_show_race_engineer' in args
    assert 'on_show_reference_driver' in args
    assert 'on_show_weather' in args
    launch = _method(cc, '_launch_overlay')
    text = ast.get_source_segment(SOURCE, launch)
    assert 'callback()' in text


def test_suite_still_exposes_exact_show_methods():
    suite = _class('OverlaySuite')
    names = {n.name for n in suite.body if isinstance(n, ast.FunctionDef)}
    assert 'show_race_engineer' in names
    assert 'show_reference_driver' in names
    assert 'show_weather' in names
