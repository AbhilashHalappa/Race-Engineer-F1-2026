from types import SimpleNamespace

from src.acc_engineer import ACCPriority, ACCRaceEngineer, evaluate_input_coaching


def test_acc_engineer_personal_best_and_fuel_warning():
    engineer = ACCRaceEngineer()
    engineer.evaluate(SimpleNamespace(lap_number=1, best_lap_time_ms=0, last_lap_time_ms=0,
                                      fuel_l=20.0, fuel_per_lap_l=5.0,
                                      is_in_pit=False, is_in_pit_lane=False), 0.0)
    messages = engineer.evaluate(SimpleNamespace(lap_number=2, best_lap_time_ms=90000,
                                                 last_lap_time_ms=89500,
                                                 fuel_l=7.0, fuel_per_lap_l=5.0,
                                                 is_in_pit=False, is_in_pit_lane=False), 10.0)
    assert any(m.key == "lap:personal-best" and m.priority == ACCPriority.INFORMATION for m in messages)
    assert any(m.key == "fuel:critical" and m.priority == ACCPriority.STRATEGY for m in messages)


def test_acc_input_coaching_is_reference_based():
    messages = evaluate_input_coaching(
        speed_kph=82.0,
        brake_percent=10.0,
        throttle_percent=40.0,
        reference_speed_kph=100.0,
        reference_brake_percent=60.0,
    )
    assert "Carry more speed into the corner." in messages
