from types import SimpleNamespace

from src.telemetry_pipeline import (
    TelemetryFrame,
    TelemetryPipeline,
    frame_from_acc,
    race_state_from_acc,
)


def test_pipeline_accepts_only_selected_game():
    pipeline = TelemetryPipeline()
    f1 = TelemetryFrame(game_id="f1_26", source="F1 UDP", received_at=1.0)
    acc = TelemetryFrame(game_id="acc", source="ACC Shared Memory", received_at=2.0)

    assert pipeline.publish(f1) is True
    assert pipeline.latest is f1
    assert pipeline.publish(acc) is False
    assert pipeline.latest is f1

    pipeline.select_game("acc")
    assert pipeline.latest is None
    assert pipeline.publish(f1) is False
    assert pipeline.publish(acc) is True
    assert pipeline.latest is acc


def test_pipeline_notifies_subscribers_without_leaking_listener_errors():
    pipeline = TelemetryPipeline()
    seen = []
    pipeline.subscribe(seen.append)
    pipeline.subscribe(lambda _frame: (_ for _ in ()).throw(RuntimeError("listener failure")))

    frame = TelemetryFrame(game_id="f1_26", source="F1 UDP", received_at=1.0)
    assert pipeline.publish(frame) is True
    assert seen == [frame]


def test_acc_adapter_normalizes_percentages_and_lap_times():
    live = SimpleNamespace(
        source="ACC Shared Memory",
        last_packet_monotonic=10.0,
        car="GT3",
        track="Monza",
        session=2,
        lap_number=4,
        position=7,
        speed_kph=180,
        gear=4,
        engine_rpm=6500,
        throttle_percent=75,
        brake_percent=20,
        steering_percent=-35,
        fuel_kg=42.5,
        last_lap_time_ms=101234,
        best_lap_time_ms=100500,
        is_in_pit=False,
        is_in_pit_lane=False,
        flag_status=7,
    )

    frame = frame_from_acc(live)
    assert frame.game_id == "acc"
    assert frame.throttle == 0.75
    assert frame.brake == 0.20
    assert frame.steering == -0.35
    assert frame.last_lap_time_s == 101.234
    assert frame.best_lap_time_s == 100.5
    assert frame.fuel_l == 42.5



def test_acc_adapter_populates_existing_race_state_without_fabricating_f1_data():
    from types import SimpleNamespace
    from src.race_state.models import RaceState
    from src.telemetry.enums import EnumValue

    live = SimpleNamespace(
        car="GT3",
        lap_number=5,
        position=3,
        speed_kph=212,
        gear=5,
        engine_rpm=7200,
        throttle_percent=82,
        brake_percent=0,
        steering_percent=-18,
        fuel_l=31.2,
        last_lap_time_ms=98450,
        is_in_pit=False,
        is_in_pit_lane=True,
    )
    state = race_state_from_acc(live, fuel_remaining_laps=4.2, session_uid=9)

    assert isinstance(state, RaceState)
    assert state.session.uid == 9
    assert state.player is not None
    assert state.player.identity.name == "GT3"
    assert state.player.lap.current_lap == 5
    assert state.player.lap.position == 3
    assert state.player.lap.previous_lap_time_s == 98.45
    assert state.player.lap.pit_status == EnumValue(1, "Pitting")
    assert state.player.telemetry.throttle == 0.82
    assert state.player.telemetry.brake == 0.0
    assert state.player.telemetry.steering == -0.18
    assert state.player.telemetry.speed_kph == 212
    assert state.player.fuel.remaining_laps == 4.2
    assert state.player.fuel.remaining_mass is None
    assert state.player.energy.store_j is None
    assert state.player.aero.drs_allowed is None
    assert state.player.tyres.pressure_psi is None


def test_acc_runtime_uses_existing_automatic_engineer():
    from src.acc_runtime import ACCRuntime
    from src.engineer import AutomaticEngineer

    runtime = ACCRuntime()
    assert isinstance(runtime.engineer, AutomaticEngineer)



def test_acc_runtime_feeds_converted_state_to_existing_engineer():
    from types import SimpleNamespace
    from src.acc_runtime import ACCRuntime

    runtime = ACCRuntime()
    runtime.start()

    def sample(lap, fuel, last_lap_ms=None):
        return SimpleNamespace(
            source="ACC Shared Memory",
            last_packet_monotonic=float(lap),
            car="GT3",
            track="Monza",
            session=2,
            lap_number=lap,
            position=4,
            speed_kph=190,
            gear=4,
            engine_rpm=6800,
            throttle_percent=70,
            brake_percent=10,
            steering_percent=-12,
            fuel_l=fuel,
            fuel_percent=None,
            flag_status=0,
            best_lap_time_ms=99000,
            last_lap_time_ms=last_lap_ms,
            is_in_pit=False,
            is_in_pit_lane=False,
        )

    assert runtime.update(sample(1, 50.0), now=1.0) == ()
    messages = runtime.update(sample(2, 48.0, 99500), now=2.0)
    assert any(message.key == "lap:2" for message in messages)
    assert runtime.status.fuel_kg == 48.0
    runtime.stop()



def test_acc_adapter_maps_real_tyre_temperature_pressure_and_environment():
    live = SimpleNamespace(
        source="ACC Shared Memory",
        last_packet_monotonic=15.0,
        car="GT3",
        track="Monza",
        session=2,
        session_type=2,
        lap_number=6,
        position=2,
        speed_kph=205,
        gear=5,
        engine_rpm=7100,
        throttle_percent=90,
        brake_percent=0,
        steering_percent=12,
        fuel_kg=35.0,
        fuel_estimated_laps=10.5,
        current_lap_time_ms=92345,
        last_lap_time_ms=91000,
        best_lap_time_ms=90000,
        is_in_pit=False,
        is_in_pit_lane=False,
        tyre_compound="Dry",
        tyre_pressures_psi=(26.1, 26.2, 26.3, 26.4),
        tyre_core_temperatures_c=(82.0, 83.0, 84.0, 85.0),
        brake_temperatures_c=(500.0, 510.0, 520.0, 530.0),
        brake_pressures=(10.0, 11.0, 12.0, 13.0),
        air_temperature_c=22.0,
        track_temperature_c=31.0,
        water_temperature_c=92.0,
        brake_bias=0.54,
        tc_level=3,
        abs_level=4,
        normalized_car_position=0.5,
        rain_intensity=0,
        track_grip_status=2,
    )

    state = race_state_from_acc(live)

    assert state.player.tyres.visual_compound.name == "Dry"
    assert state.player.tyres.core_temperature_c.FL == 82.0
    assert state.player.tyres.pressure_psi.RR == 26.4
    assert state.player.telemetry.brakes_temperature_c.FR == 510.0
    assert state.player.telemetry.brake_pressure.RL == 12.0
    assert state.player.telemetry.engine_temperature_c == 92
    assert state.session.air_temperature_c == 22
    assert state.session.track_temperature_c == 31
    assert state.player.fuel.remaining_laps == 10.5
    assert state.player.fuel.remaining_mass == 35.0
    assert state.player.fuel.mass_unit == "kg"
    assert state.extended["brake_bias"] == 0.54
    assert state.extended["tc_level"] == 3


def test_acc_common_frame_contains_extended_telemetry():
    live = SimpleNamespace(
        source="ACC Shared Memory",
        last_packet_monotonic=4.0,
        session=2,
        session_type=2,
        tyre_pressures_psi=(26.0, 26.1, 26.2, 26.3),
        tyre_core_temperatures_c=(80.0, 81.0, 82.0, 83.0),
        brake_temperatures_c=(500.0, 501.0, 502.0, 503.0),
        brake_pressures=(10.0, 10.1, 10.2, 10.3),
        clutch_percent=25,
        current_lap_time_ms=90000,
        air_temperature_c=21.0,
        track_temperature_c=30.0,
        water_temperature_c=90.0,
        fuel_kg=35.0,
        fuel_estimated_laps=8.5,
        max_fuel_kg=120.0,
        tc_level=2,
        abs_level=3,
    )

    frame = frame_from_acc(live)

    assert frame.session_type == "Race"
    assert frame.tyre_temperatures == (80.0, 81.0, 82.0, 83.0)
    assert frame.tyre_pressures == (26.0, 26.1, 26.2, 26.3)
    assert frame.brake_temperatures_c == (500.0, 501.0, 502.0, 503.0)
    assert frame.current_lap_time_s == 90.0
    assert frame.fuel_remaining_laps == 8.5
    assert frame.fuel_kg == 35.0
    assert frame.fuel_capacity_kg == 120.0
    assert frame.air_temperature_c == 21.0



def test_acc_radio_answers_tyre_and_car_temperatures_from_native_fields():
    from src.voice_commands import handle_voice_request, parse_intent, VoiceIntent

    live = SimpleNamespace(
        car="GT3",
        track="Monza",
        session=2,
        session_type=2,
        lap_number=3,
        position=5,
        speed_kph=180,
        gear=4,
        engine_rpm=6500,
        throttle_percent=50,
        brake_percent=0,
        steering_percent=0,
        tyre_compound="Dry",
        tyre_core_temperatures_c=(82.0, 84.0, 86.0, 88.0),
        tyre_pressures_psi=(26.0, 26.1, 26.2, 26.3),
        water_temperature_c=91.0,
        air_temperature_c=23.0,
        track_temperature_c=32.0,
    )
    state = race_state_from_acc(live)

    assert parse_intent("car temperature") == VoiceIntent.ENGINE_TEMPERATURE
    tyre = handle_voice_request("tyre temperature details", state)
    engine = handle_voice_request("car temperature", state)
    air = handle_voice_request("air temperature", state)
    track = handle_voice_request("track temperature", state)

    assert "core temperatures" in tyre.response.lower()
    assert "82" in tyre.response and "88" in tyre.response
    assert "91" in engine.response
    assert "23" in air.response
    assert "32" in track.response


def test_acc_overlay_snapshot_uses_acc_common_state_without_f1_pit_advice():
    from src.overlay.data import build_overlay_snapshot

    live = SimpleNamespace(
        car="GT3",
        track="Monza",
        session=2,
        session_type=2,
        lap_number=4,
        position=6,
        speed_kph=190,
        gear=5,
        engine_rpm=7000,
        throttle_percent=80,
        brake_percent=0,
        steering_percent=10,
        tyre_compound="Dry",
        tyre_core_temperatures_c=(80.0, 81.0, 82.0, 83.0),
        tyre_pressures_psi=(26.0, 26.1, 26.2, 26.3),
        air_temperature_c=22.0,
        track_temperature_c=30.0,
        fuel_l=35.0,
        max_fuel_kg=100.0,
        fuel_estimated_laps=8.5,
    )
    state = race_state_from_acc(live)
    snapshot = build_overlay_snapshot(state, None, connected=True)

    assert snapshot.connected is True
    assert snapshot.speed_kph == 190
    assert snapshot.tyre_core_temperatures_c == (80.0, 81.0, 82.0, 83.0)
    assert snapshot.tyre_pressures_psi == (26.0, 26.1, 26.2, 26.3)
    assert snapshot.fuel_kg == 35.0
    assert snapshot.fuel_capacity == 100.0
    assert snapshot.fuel_remaining_laps == 8.5
    assert snapshot.race_engineer.decision == "ACC STRATEGY NOT READY"


def test_acc_adapter_preserves_native_damage_values_and_radio_reports_them():
    from src.telemetry_pipeline import race_state_from_acc
    from src.voice_commands import handle_voice_request

    live = SimpleNamespace(
        car="GT3", track="Monza", session=2, session_type=2,
        car_damage=(0.12, 0.04, 0.01, 0.02, 0.00),
    )
    state = race_state_from_acc(live)

    assert state.player.damage.acc_values == (0.12, 0.04, 0.01, 0.02, 0.0)
    # The typed RaceState damage adapter remains sufficient even if the raw
    # extended/native page is not attached to a later consumer snapshot.
    state.extended.pop("car_damage", None)
    state.extended.pop("acc_physics", None)
    answer = handle_voice_request("car damage", state)
    assert "front 0.120" in answer.response
    assert "rear 0.040" in answer.response


def test_acc_map_learner_rejects_straight_line_and_accepts_closed_circuit():
    import math
    from src.acc_runtime import ACCRuntime

    straight = [(float(i) * 20.0, float(i) * 0.05) for i in range(200)]
    assert ACCRuntime._map_trace_is_valid(straight) is False

    circuit = [
        (900.0 * math.cos(2.0 * math.pi * i / 500.0),
         450.0 * math.sin(2.0 * math.pi * i / 500.0))
        for i in range(501)
    ]
    assert ACCRuntime._map_trace_is_valid(circuit) is True
