from pathlib import Path


def test_renderer_has_distinct_final_lap_and_finished_states_without_pit_fields():
    source = Path('src/overlay/window.py').read_text(encoding='utf-8')
    start = source.index('class RaceEngineerOverlayWindow')
    end = source.index('class ERSBatteryOverlayWindow')
    body = source[start:end]
    assert 'FINISH THE RACE' in body
    assert 'RACE FINISHED' in body
    assert 'elif final_lap:' in body
    final_branch = body.split('elif final_lap:', 1)[1].split('else:', 1)[0]
    assert 'TYRE IF BOX' not in final_branch
    assert 'PIT WINDOW' not in final_branch
    assert 'REJOIN' not in final_branch
