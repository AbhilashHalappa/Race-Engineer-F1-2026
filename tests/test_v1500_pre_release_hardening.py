from pathlib import Path
from types import SimpleNamespace as NS
import base64, json, zipfile

from src.runtime_validation import RuntimeBenchmarkMonitor, compare_replay_live_signatures
from src.validation_bundle import ValidationBundleManager
from src.formal_validation import validate_bundle, scenario_matrix
from src.settings_ui import export_configuration, import_configuration_b64
from src.advanced_race_strategy import assess_advanced_strategy


def _header(pid,frame): return NS(m_packetId=pid,m_frameIdentifier=frame)

def test_runtime_monitor_counts_real_gaps_not_duplicates():
    m=RuntimeBenchmarkMonitor(sample_interval_s=.25)
    for f in (10,11,14,14,13): m.observe_header(_header(6,f))
    s=m.snapshot(); assert s.inferred_frame_gaps==2; assert s.duplicate_frames==1; assert s.out_of_order_frames==1

def test_replay_live_signature_is_deterministic():
    assert compare_replay_live_signatures({'lap':2,'fuel':3.0},{'lap':2,'fuel':3.0001},tolerances={'fuel':.001})['match']

def test_validation_bundle_never_embeds_areplay(tmp_path):
    rec=tmp_path/'big.areplay'; rec.write_bytes(b'abc')
    mgr=ValidationBundleManager(output_dir=tmp_path/'bundles')
    state=NS(session=NS(uid=123,session_uid=123,session_type='Race',track=NS(name='Austria')),extended={})
    out=mgr.finalize_session(state,recording_path=rec,runtime={'packets':1},latency={'core_p95_ms':1.0})
    chk=validate_bundle(out); assert chk['ok']; assert not any(x.endswith('.areplay') for x in chk['files'])
    assert any(a.get('name')=='big.areplay' and a.get('embedded') is False for a in chk['manifest'].get('artifacts',[]))

def test_config_export_import_roundtrip(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path); Path('settings').mkdir(); Path('settings/x.json').write_text('{"a":1}')
    out=export_configuration('cfg.zip'); raw=base64.b64encode(out.read_bytes()).decode(); Path('settings/x.json').unlink()
    result=import_configuration_b64(raw); assert 'settings/x.json' in result['changed']; assert Path('settings/x.json').exists()

def test_formal_scenario_matrix_has_required_release_cases():
    ids={x['id'] for x in scenario_matrix()}
    assert {'weekend_transition','long_race','wet_dry','sc_vsc','pit_window','damage','combat','session_best','latency_load','replay_live_parity'} <= ids

def test_advanced_strategy_exposes_game_window_sc_vsc_and_observed_evidence():
    lap=NS(current_lap=10,gap_to_car_in_front_s=2.0,unserved_drive_through=0,unserved_stop_go=0)
    p=NS(lap=lap,fuel=NS(remaining_laps=10),energy=NS(store_j=2_000_000,deployed_this_lap_j=100_000,harvested_mguk_j=50_000,harvested_mguh_j=50_000),damage=NS(front_left_wing_percent=0,front_right_wing_percent=0),tyres=NS(wear_percent=None))
    state=NS(player=p,session=NS(total_laps=20,forecast=[],forecast_accuracy='perfect',weather='clear',session_type='Race',safety_car='none',pit_stop_window_ideal_lap=9,pit_stop_window_latest_lap=12),extended={'_sc_pit_cycle_samples_s':(9.1,9.3),'_vsc_pit_cycle_samples_s':(12.2,), '_used_dry_compounds':('medium',), 'measured_stop_sequence_effect':{'player_gap_gain_s':1.2},'opponent_strategy_inference':{'events':['pit_entry']}},field={},ahead_index=None,measured_laps=[])
    a=assess_advanced_strategy(state)
    assert a.game_pit_window_status=='open'; assert a.measured_sc_pit_loss_s==9.2; assert a.measured_vsc_pit_loss_s==12.2
    assert a.measured_stop_sequence_effect['player_gap_gain_s']==1.2

def test_validation_bundle_buffers_are_bounded_and_finalized_session_is_released(tmp_path):
    mgr=ValidationBundleManager(output_dir=tmp_path/'bundles')
    state=NS(session=NS(uid=77,session_uid=77,session_time_s=0.0,session_type='Race',track=NS(name='Austria')),extended={})
    # Simulate a pathological producer; the manager itself must remain bounded.
    for i in range(mgr._max_strategy_rows + 500):
        state.session.session_time_s=float(i)
        mgr.strategy(state, {'pit_window': 'hold', 'sample': i}, reason='strategy_sample')
    assert len(mgr._strategy_rows) == mgr._max_strategy_rows
    for i in range(mgr._max_event_rows + 100):
        state.session.session_time_s=float(i)
        mgr.warning(state, 'test', i)
    assert len(mgr._warnings) == mgr._max_event_rows
    out=mgr.finalize_session(state)
    assert out is not None and out.exists()
    assert not any(x.get('session_uid') == 77 for x in mgr._strategy_rows)
    assert not any(x.get('session_uid') == 77 for x in mgr._warnings)
