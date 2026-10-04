from pathlib import Path
import json
from src.race_state.models import RaceState, CarState, Wheels, MeasuredLapFact, Forecast
from src.telemetry.enums import EnumValue
from src.race_context import assess_race_context
from src.strategy_expansion import assess_expanded_strategy, format_rejoin_projection, format_undercut_projection
from src.session_library import SessionLibrary
from src.speech_quality import PronunciationDictionary, concise_engineer_text
from src.product_readiness import first_run_check, windows_firewall_command

def ev(name, raw=0): return EnumValue(raw,name)

def state():
    s=RaceState(); c=CarState(0); s.player=c; s.field[0]=c; s.player_index=0
    s.session.total_laps=20; s.session.weather=ev('Clear'); s.session.safety_car=ev('None')
    s.session.forecast_accuracy=ev('Perfect'); s.session.forecast=(Forecast(ev('Race'),5,ev('Light rain'),25,ev('No change'),20,ev('No change'),70),)
    c.lap.current_lap=10; c.lap.gap_to_car_in_front_s=2.0; s.gap_behind_s=3.0
    c.fuel.remaining_laps=.8; c.energy.store_j=1_000_000
    c.tyres.wear_percent=Wheels(60,60,60,60); c.tyres.punctured=Wheels(False,False,False,False)
    c.damage.front_left_wing_percent=0; c.damage.front_right_wing_percent=0; c.damage.floor_percent=0
    s.measured_laps=(MeasuredLapFact(7,90.0,fitted_tyre_set_index=1),MeasuredLapFact(8,90.2,fitted_tyre_set_index=1),MeasuredLapFact(9,90.5,fitted_tyre_set_index=1))
    return s

def test_race_context_suppresses_close_combat_and_reports_adaptations():
    s=state(); s.player.lap.gap_to_car_in_front_s=.7
    d=assess_race_context(s)
    assert d.level=='combat' and not d.technique_coaching_allowed and d.prefer_race_exit_advice
    assert 'wet_weather' in d.adaptations

def test_race_context_critical_damage_outranks_coaching():
    s=state(); s.player.damage.front_left_wing_percent=45
    d=assess_race_context(s)
    assert d.level=='critical' and 'severe_damage' in d.reasons

def test_expanded_strategy_uses_only_measured_pit_cycle():
    s=state(); s.extended['_pit_cycle_samples_s']=(22.0,22.4,22.2)
    a=assess_expanded_strategy(s)
    assert a.pit_cycle_time_s==22.2
    assert a.weather_transition=='dry_to_wet'
    assert a.tyre_degradation_s_per_lap==.25
    assert 'Measured pit cycle' in format_rejoin_projection(s)

def test_expanded_strategy_refuses_unknown_pit_loss():
    s=state()
    assert 'pit-loss' in format_rejoin_projection(s)
    assert 'pit-loss' in format_undercut_projection(s)

def test_session_library_safe_archive_restore_and_metadata(tmp_path):
    rec=tmp_path/'recordings'; rec.mkdir(); (rec/'a.areplay').write_bytes(b'abc')
    lib=SessionLibrary(rec,tmp_path/'meta.json',tmp_path/'reports')
    lib.rename('a.areplay','Race 1'); lib.tag('a.areplay','melbourne','race'); lib.favorite('a.areplay',True)
    row=lib.list()[0]; assert row['name']=='Race 1' and row['favorite'] and row['tags']==['melbourne','race']
    lib.archive('a.areplay'); assert lib.list()==[] and lib.list(include_archived=True)[0]['archived']
    lib.restore('a.areplay'); assert (rec/'a.areplay').exists()

def test_pronunciation_dictionary_and_minimal_wording(tmp_path):
    p=tmp_path/'pron.json'; d=PronunciationDictionary(p); d.set('ERS','E R S')
    assert d.apply('ERS available')=='E R S available'
    assert concise_engineer_text('At the moment, tyres are hot. Keep them clean.','minimal')=='tyres are hot.'

def test_product_readiness_and_firewall_command(tmp_path):
    (tmp_path/'voices').mkdir(); (tmp_path/'voices'/'voice.onnx').write_bytes(b'x')
    r=first_run_check(root=tmp_path,udp_port=0)
    assert r.writable_settings and r.recordings_dir and r.voices_present
    assert 'Race Engineer' in windows_firewall_command('RaceEngineer.exe')
