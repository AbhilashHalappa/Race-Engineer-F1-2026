from pathlib import Path

def test_lap_and_telemetry_share_bounded_engineer_coach_cadence():
    src=Path('src/race_state_receiver.py').read_text(encoding='utf-8')
    assert src.count('if category in {"telemetry", "lap"}:') >= 2
    assert 'category in {"telemetry", "lap"} and engineer_due' in src
    assert 'if state_changed and category in {"lap", "telemetry"} and coach_due' in src
