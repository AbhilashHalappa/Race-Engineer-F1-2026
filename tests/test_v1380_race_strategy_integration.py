from src.race_state.models import RaceState,CarState,Wheels,MeasuredLapFact,Forecast
from src.telemetry.enums import EnumValue
from src.engineer.models import EngineerMessage,Priority
from src.advanced_race_strategy import assess_advanced_strategy,arbitrate_messages
from src.strategy_learning import StrategyEvidenceLearner

def ev(n): return EnumValue(0,n)
def s():
 x=RaceState(); c=CarState(0); x.player=c;x.field[0]=c;x.player_index=0;x.session.total_laps=20;x.session.session_type=ev('Race');x.session.weather=ev('Clear');x.session.safety_car=ev('None');x.session.forecast_accuracy=ev('Perfect');x.session.forecast=(Forecast(ev('Race'),5,ev('Light rain'),20,ev('No change'),18,ev('No change'),70),);c.lap.current_lap=10;c.lap.gap_to_car_in_front_s=1.0;c.fuel.remaining_laps=11;c.energy.store_j=2_000_000;c.energy.deployed_this_lap_j=200_000;c.energy.harvested_mguk_j=100_000;c.tyres.wear_percent=Wheels(65,65,65,65);c.tyres.punctured=Wheels(0,0,0,0);c.tyres.age_laps=8;c.tyres.visual_compound=ev('Medium');x.measured_laps=(MeasuredLapFact(7,90.0,fitted_tyre_set_index=1),MeasuredLapFact(8,90.2,fitted_tyre_set_index=1),MeasuredLapFact(9,90.5,fitted_tyre_set_index=1));return x

def test_strategy_projection_all_major_outputs():
 x=s();x.extended['_pit_cycle_samples_s']=(21.8,22.0,22.2);a=assess_advanced_strategy(x);assert a.pit_loss_s==22.0;assert a.tyre_degradation_s_per_lap==.25;assert a.fuel_target in {'on_target','surplus'};assert a.weather_transition=='dry_to_wet';assert a.tyre_transition=='consider_wet_or_intermediate';assert a.undercut in {'consider','no_trigger'}

def test_critical_and_combat_suppress_technique_and_resume():
 x=s(); msgs=[EngineerMessage('corner:pre',Priority.COACHING,'Brake later',0),EngineerMessage('penalty',Priority.CRITICAL,'Penalty',0)]
 r=arbitrate_messages(msgs,x,previous_level='performance'); assert 'corner:pre' in r.suppressed_keys and r.race_exit_message is not None and any(m.key=='penalty' for m in r.accepted)
 x.player.lap.gap_to_car_in_front_s=3.0; r2=arbitrate_messages([],x,previous_level='combat'); assert r2.resume_message is not None

def test_critical_damage_overrides():
 x=s();x.player.damage.front_left_wing_percent=50;r=arbitrate_messages([EngineerMessage('coach:x',Priority.COACHING,'x',0)],x);assert r.context['level']=='critical' and not r.accepted

def test_sc_vsc_service_opportunity_and_rules():
 x=s();x.player.tyres.wear_percent=Wheels(75,75,75,75);x.session.safety_car=ev('Safety car');a=assess_advanced_strategy(x);assert a.safety_car_pit=='consider';assert a.mandatory_compound_status=='only_one_dry_compound_observed' or a.mandatory_compound_status=='unavailable'

def test_damage_pace_and_wing_threshold():
 x=s();x.player.damage.front_left_wing_percent=30;x.extended['measured_damage_pace_loss_s']=0.8;a=assess_advanced_strategy(x);assert a.wing_pit_threshold=='pit_consideration_supported'

def test_learner_produces_pit_and_damage_evidence():
 l=StrategyEvidenceLearner();x=s();x.measured_laps=(MeasuredLapFact(1,90),MeasuredLapFact(2,90.2));l.observe(x);x.player.lap.current_lap=3;x.player.lap.pit_lane_timer_active=True;l.observe(x);x.measured_laps=x.measured_laps+(MeasuredLapFact(3,112),);l.observe(x);assert x.extended['_pit_cycle_samples_s']

def test_damage_override_does_not_append_generic_damage_to_every_corner_message():
 x=s();x.player.lap.gap_to_car_in_front_s=3.0;x.player.damage.front_left_wing_percent=30
 # Moderate damage keeps performance coaching eligible, but no measured pace-loss
 # evidence means damage must not be injected into unrelated coaching.
 r=arbitrate_messages([EngineerMessage('corner:post',Priority.COACHING,'Turn 7, gained 0.27',0)],x)
 assert len(r.accepted)==1 and 'damage' not in r.accepted[0].text.lower()


def test_measured_damage_cost_only_augments_generic_loss_not_specific_diagnosis():
 x=s();x.player.lap.gap_to_car_in_front_s=3.0;x.player.damage.front_left_wing_percent=30
 x.extended['measured_damage_pace_loss_s']=0.8
 generic=EngineerMessage('corner:post',Priority.COACHING,'Turn 6, lost 0.24',0)
 diagnosed=EngineerMessage('corner:post2',Priority.COACHING,'Turn 12, lost 0.29 seconds. Your throttle pickup was about 30 metres late',0)
 matched=EngineerMessage('corner:post3',Priority.COACHING,'Turn 3, matched the reference closely',0)
 r=arbitrate_messages([generic,diagnosed,matched],x)
 by={m.key:m.text for m in r.accepted}
 assert 'damage is costing pace' in by['corner:post']
 assert 'damage' not in by['corner:post2'].lower()
 assert 'damage' not in by['corner:post3'].lower()
