from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.driver_skill_reconciliation import DriverSkillReconciliation
from src.performance_hub_ui import performance_hub_page_html


def test_performance_hub_exposes_reconciled_progress_workspace():
    html=performance_hub_page_html()
    assert 'DRIVER PROGRESS' in html
    assert '/api/performance/progress' in html
    assert 'OPEN PRACTICE' in html
    assert 'data-tab=practice' not in html  # frozen Practice remains separate


def test_reconciliation_does_not_invent_missing_original_domains(tmp_path: Path):
    ds=DriverProfileStore(tmp_path/'drivers')
    p=ds.create_profile('Driver')
    ds.set_active_driver(p['driver_id'])
    result=DriverSkillReconciliation(ds).build(p['driver_id'])
    assert 'trail_braking' not in result['domains']
    assert 'line_consistency' not in result['domains']
    assert result['persistent_history'].startswith('LIVE-only')
