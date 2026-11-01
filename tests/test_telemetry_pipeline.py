from types import SimpleNamespace

from src.telemetry_pipeline import (
    TelemetryFrame,
    TelemetryPipeline,
    frame_from_acc,
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
        fuel_l=42.5,
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
