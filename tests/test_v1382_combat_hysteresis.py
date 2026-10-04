from types import SimpleNamespace

from src.race_context import RaceContextHysteresis


def ev(name):
    return SimpleNamespace(name=name)


def state(front=5.0, behind=5.0):
    lap=SimpleNamespace(gap_to_car_in_front_s=front,pit_status=ev('None'),pit_lane_timer_active=False)
    tyres=SimpleNamespace(wear_percent=SimpleNamespace(FL=20,FR=20,RL=20,RR=20),punctured=SimpleNamespace(FL=False,FR=False,RL=False,RR=False))
    damage=SimpleNamespace(front_left_wing_percent=0,front_right_wing_percent=0,rear_wing_percent=0,floor_percent=0,diffuser_percent=0,sidepod_percent=0,engine_blown=False,engine_seized=False)
    telemetry=SimpleNamespace(brakes_temperature_c=SimpleNamespace(FL=700,FR=700,RL=650,RR=650))
    player=SimpleNamespace(lap=lap,tyres=tyres,damage=damage,telemetry=telemetry,fuel=SimpleNamespace(remaining_laps=5),energy=SimpleNamespace(store_j=2_000_000))
    session=SimpleNamespace(safety_car=ev('None'),weather=ev('Clear'),forecast=())
    return SimpleNamespace(player=player,session=session,gap_behind_s=behind)


def test_combat_enters_immediately_but_does_not_clear_on_threshold_jitter():
    h=RaceContextHysteresis()
    s=state(front=.9)
    assert h.update(s,0.0).level=='combat'
    s.player.lap.gap_to_car_in_front_s=1.3
    assert h.update(s,1.0).level=='combat'
    assert h.update(s,4.1).level=='combat'


def test_combat_requires_sustained_wide_clear_gap_before_resume():
    h=RaceContextHysteresis()
    s=state(front=.9)
    assert h.update(s,0.0).level=='combat'
    s.player.lap.gap_to_car_in_front_s=2.2
    assert h.update(s,4.1).level=='combat'
    assert h.update(s,6.9).level=='combat'
    assert h.update(s,7.2).level=='performance'


def test_brief_reentry_inside_release_threshold_resets_clear_timer():
    h=RaceContextHysteresis()
    s=state(front=.8)
    h.update(s,0.0)
    s.player.lap.gap_to_car_in_front_s=2.2
    h.update(s,4.1)
    s.player.lap.gap_to_car_in_front_s=1.6
    assert h.update(s,5.0).level=='combat'
    s.player.lap.gap_to_car_in_front_s=2.2
    assert h.update(s,5.2).level=='combat'
    assert h.update(s,8.1).level=='combat'
    assert h.update(s,8.3).level=='performance'


def test_critical_state_bypasses_combat_hysteresis_immediately():
    h=RaceContextHysteresis()
    s=state(front=.8)
    assert h.update(s,0.0).level=='combat'
    s.player.damage.front_left_wing_percent=50
    assert h.update(s,.1).level=='critical'
