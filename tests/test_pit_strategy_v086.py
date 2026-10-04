from src.pit_strategy import assess_pit, format_pit_fallback
from src.race_state.models import RaceState, CarState, Wheels, TyreSet
from src.telemetry.enums import EnumValue

def ev(n): return EnumValue(0,n)
def base():
    s=RaceState(); s.player=CarState(0); s.session.total_laps=20; s.player.lap.current_lap=5
    s.player.tyres.wear_percent=Wheels(10,10,10,10); s.player.tyres.damage_percent=Wheels(0,0,0,0)
    s.player.tyres.surface_temperature_c=Wheels(90,90,90,90); s.player.tyres.age_laps=5
    s.player.damage.front_left_wing_percent=0; s.player.damage.front_right_wing_percent=0
    s.player.tyres.visual_compound=ev('C3'); s.session.weather=ev('Clear'); s.session.safety_car=ev('None')
    return s

def test_clean_car_stays_out_offline():
    s=base(); a=assess_pit(s); assert a.recommendation_hint=='stay_out'; assert format_pit_fallback(s).startswith('Stay out')
def test_destroyed_wing_boxes_now():
    s=base(); s.player.damage.front_left_wing_percent=100; a=assess_pit(s); assert a.recommendation_hint=='box_now'; assert 'Front wing damage 100' in format_pit_fallback(s)
def test_high_wear_boxes():
    s=base(); s.player.tyres.wear_percent=Wheels(92,50,50,50); assert assess_pit(s).recommendation_hint=='box_now'
def test_nonrepairable_floor_does_not_create_false_box():
    s=base(); s.player.damage.floor_percent=90; a=assess_pit(s); assert a.recommendation_hint=='stay_out'; assert a.nonserviceable_warnings
def test_fuel_shortfall_does_not_recommend_refuel_stop():
    s=base(); s.player.fuel.remaining_laps=-2; a=assess_pit(s); assert a.recommendation_hint=='stay_out'; assert any('refuelling' in x for x in a.nonserviceable_warnings)
def test_stop_go_is_pit_trigger():
    s=base(); s.player.lap.unserved_stop_go=1; assert assess_pit(s).recommendation_hint in ('box_soon','box_now')
def test_weather_mismatch_with_wet_set_boxes():
    s=base(); s.session.weather=ev('Heavy rain')
    s.player.tyres.sets=(TyreSet(1,ev('Intermediate'),ev('Intermediate'),0,True,ev('Race'),20,20,0.0,False),)
    assert assess_pit(s).recommendation_hint=='box_now'
def test_drive_through_not_misrepresented_as_normal_pit_stop():
    s=base(); s.player.lap.unserved_drive_through=1; a=assess_pit(s); assert a.recommendation_hint=='stay_out'; assert any('drive-through' in x for x in a.nonserviceable_warnings)
