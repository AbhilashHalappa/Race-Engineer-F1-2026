from types import SimpleNamespace

from src.measured_performance import MeasuredPerformanceRecorder


def _enum(name, raw=0):
    return SimpleNamespace(name=name, raw=raw)


def _state(*, lap_no=1, d=100.0, t=5.0, pit='None', valid=True):
    lap = SimpleNamespace(
        current_lap=lap_no,
        lap_distance_m=d,
        current_lap_time_s=t,
        lap_valid=valid,
        previous_lap_time_s=None,
        pit_status=_enum(pit),
        gap_to_car_in_front_s=None,
        warnings=0,
        penalties_s=0,
        corner_cutting_warnings=0,
        result_status=_enum('Active', 2),
    )
    telemetry = SimpleNamespace(speed_kph=100.0, throttle=0.5, brake=0.0, steering=0.0, gear=4, rpm=9000)
    player = SimpleNamespace(
        lap=lap,
        telemetry=telemetry,
        damage=SimpleNamespace(front_left_wing_percent=0, front_right_wing_percent=0, floor_percent=0,
                               engine_blown=False, engine_seized=False),
        energy=SimpleNamespace(store_j=None),
        fuel=SimpleNamespace(remaining_mass=None),
        tyres=None,
        aero=SimpleNamespace(active_aero_mode=None, active_aero_available=None, regulations_2026=True),
    )
    session = SimpleNamespace(
        uid=123,
        ended=False,
        paused=False,
        safety_car=_enum('None', 0),
        marshal_zones=(),
        track_length_m=5000.0,
        track='CATALUNYA',
        weather=None,
        track_temperature_c=None,
        air_temperature_c=None,
        session_type=_enum('Time Trial', 18),
    )
    return SimpleNamespace(player=player, session=session, gap_behind_s=None, extended={}, player_index=0)


def test_first_timed_lap_drops_pre_anchor_pit_carryover():
    r = MeasuredPerformanceRecorder()

    # Startup/out-lap phase: EA already calls this lap 1 and reports pit status.
    r.observe(_state(lap_no=1, d=300.0, t=8.0, pit='Pitting'))
    assert r.current_lap == 1
    assert r.current_lap_started_clean is False
    assert r.current_lap_pit is True
    assert r.samples

    # First timing anchor: re-base ownership.  A stale pitStatus is allowed to
    # carry for a few packets without contaminating the timed lap.
    r.observe(_state(lap_no=1, d=5.0, t=0.5, pit='Pitting'))
    assert r.current_lap_started_clean is True
    assert r.current_lap_pit is False
    assert r._ignore_startup_pit_until_clear is True
    assert 300.0 not in r.samples

    # Once pit status clears, normal lap-quality ownership resumes.
    r.observe(_state(lap_no=1, d=80.0, t=2.5, pit='None'))
    assert r.current_lap_pit is False
    assert r._ignore_startup_pit_until_clear is False


def test_real_pit_entry_after_lap1_start_still_marks_pit_lap():
    r = MeasuredPerformanceRecorder()

    # Same startup path as above.
    r.observe(_state(lap_no=1, d=300.0, t=8.0, pit='Pitting'))
    r.observe(_state(lap_no=1, d=5.0, t=0.5, pit='Pitting'))
    r.observe(_state(lap_no=1, d=80.0, t=2.5, pit='None'))

    # A later genuine pit entry on the timed lap must still latch pit_lap.
    r.observe(_state(lap_no=1, d=4500.0, t=70.0, pit='Pitting'))
    assert r.current_lap_pit is True


def test_normal_lap_transition_keeps_existing_pit_semantics():
    r = MeasuredPerformanceRecorder()
    # Start already clean, so there is no startup grace state.
    r.observe(_state(lap_no=2, d=5.0, t=0.5, pit='None'))
    assert r.current_lap_started_clean is True
    assert r._ignore_startup_pit_until_clear is False
    r.observe(_state(lap_no=2, d=4200.0, t=60.0, pit='Pitting'))
    assert r.current_lap_pit is True
