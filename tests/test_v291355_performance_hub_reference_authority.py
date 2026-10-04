from pathlib import Path

from src.performance_history import PerformanceHistoryStore
import src.reference_ecosystem as eco


def test_performance_hub_exposes_current_rival_even_when_quality_is_not_accepted(tmp_path, monkeypatch):
    ref = tmp_path / 'references' / 'CATALUNYA' / 'rival_reference.json'
    ref.parent.mkdir(parents=True)
    ref.write_text('{}', encoding='utf-8')

    def fake_list(_root):
        return [{
            'path': str(ref),
            'valid': False,  # quality F: loadable, but not quality-accepted
            'quality': {'grade': 'F', 'score': 32, 'accepted': False},
            'metadata': {'track': {'name': 'CATALUNYA'}, 'driver': {'name': 'Time Trial rival'}},
            'lap_time_s': 70.580,
        }]

    monkeypatch.setattr(eco, 'list_installed_references', fake_list)
    store = PerformanceHistoryStore(tmp_path / 'performance.sqlite3')
    rows = store._installed_review_references('Catalunya')
    assert len(rows) == 1
    assert rows[0]['lap_time_s'] == 70.580
    assert rows[0]['label'].startswith('Current rival reference')
    assert rows[0]['quality_accepted'] is False


def test_folder_name_can_authorize_track_when_legacy_metadata_lacks_name(tmp_path, monkeypatch):
    ref = tmp_path / 'references' / 'CATALUNYA' / 'rival_reference.json'
    ref.parent.mkdir(parents=True)
    ref.write_text('{}', encoding='utf-8')

    def fake_list(_root):
        return [{
            'path': str(ref),
            'valid': True,
            'quality': {'grade': 'A', 'score': 95, 'accepted': True},
            'metadata': {'track': {'name': None}, 'driver': {'name': 'Rival'}},
            'lap_time_s': 70.580,
        }]

    monkeypatch.setattr(eco, 'list_installed_references', fake_list)
    store = PerformanceHistoryStore(tmp_path / 'performance.sqlite3')
    rows = store._installed_review_references('Catalunya')
    assert len(rows) == 1
