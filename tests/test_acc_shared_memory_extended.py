import pytest

from src.acc_shared_memory_extended import (
    _Physics, _Graphics, _Static,
    PHYSICS_SIZE, GRAPHICS_SIZE, STATIC_SIZE,
    decode_physics_extended, decode_graphics_extended, decode_static_extended,
)


def _put_wide(target, value):
    for index, char in enumerate(value):
        target[index] = ord(char)


def test_acc_physics_layout_decodes_full_live_engineering_channels():
    page = _Physics()
    page.packet_id = 12
    page.throttle = 0.75
    page.brake = 0.15
    page.fuel_l = 42.5
    page.gear_raw = 4
    page.rpm = 6800
    page.steering = -0.25
    page.speed_kph = 190.0
    page.tyre_pressure_psi[:] = (26.1, 26.2, 26.3, 26.4)
    page.tyre_core_temp_c[:] = (82.0, 83.0, 84.0, 85.0)
    page.brake_temp_c[:] = (540.0, 550.0, 560.0, 570.0)
    page.air_temp_c = 22.0
    page.road_temp_c = 31.0
    page.water_temp_c = 92.0
    page.brake_bias = 0.54

    decoded = decode_physics_extended(bytes(page))

    assert PHYSICS_SIZE == len(bytes(page))
    assert decoded["packet_id"] == 12
    assert decoded["gear_raw"] == 4
    assert decoded["tyre_pressure_psi"] == pytest.approx((26.1, 26.2, 26.3, 26.4))
    assert decoded["tyre_core_temp_c"] == (82.0, 83.0, 84.0, 85.0)
    assert decoded["brake_temp_c"] == (540.0, 550.0, 560.0, 570.0)
    assert decoded["air_temp_c"] == 22.0
    assert decoded["road_temp_c"] == 31.0
    assert decoded["water_temp_c"] == 92.0
    assert decoded["brake_bias"] == pytest.approx(0.54)


def test_acc_graphics_layout_decodes_lap_timing_strategy_and_weather():
    page = _Graphics()
    page.status = 2
    page.session = 2
    page.completed_laps = 7
    page.position = 3
    page.current_time_ms = 90123
    page.last_time_ms = 89987
    page.best_time_ms = 88765
    page.session_time_left_s = 1200.0
    page.is_in_pit = 1
    page.sector = 2
    page.number_of_laps = 20
    _put_wide(page.tyre_compound, "Dry")
    page.flag = 2
    page.is_in_pit_lane = 1
    page.tc_level = 3
    page.tc_cut = 2
    page.engine_map = 1
    page.abs_level = 4
    page.fuel_per_lap = 2.7
    page.fuel_estimated_laps = 12.5
    page.track_grip_status = 2
    page.rain_intensity = 0
    page.rain_10min = 1
    page.rain_30min = 2

    decoded = decode_graphics_extended(bytes(page))

    assert GRAPHICS_SIZE == len(bytes(page))
    assert decoded["status"] == 2
    assert decoded["session"] == 2
    assert decoded["position"] == 3
    assert decoded["current_time_ms"] == 90123
    assert decoded["best_time_ms"] == 88765
    assert decoded["tyre_compound"] == "Dry"
    assert decoded["is_in_pit_lane"] is True
    assert decoded["fuel_estimated_laps"] == 12.5
    assert decoded["rain_30min"] == 2


def test_acc_static_layout_decodes_car_track_and_player_identity():
    page = _Static()
    _put_wide(page.car_model, "gt3_car")
    _put_wide(page.track, "monza")
    _put_wide(page.player_nickname, "Driver")
    page.max_rpm = 8500
    page.max_fuel_l = 120.0
    page.pit_window_start = 10
    page.pit_window_end = 20

    decoded = decode_static_extended(bytes(page))

    assert STATIC_SIZE == len(bytes(page))
    assert decoded["car_model"] == "gt3_car"
    assert decoded["track"] == "monza"
    assert decoded["player_nickname"] == "Driver"
    assert decoded["max_rpm"] == 8500
    assert decoded["max_fuel_l"] == 120.0
    assert decoded["pit_window_start"] == 10
    assert decoded["pit_window_end"] == 20
