from __future__ import annotations

from dataclasses import dataclass
import math

from .pedal_curves import RAW_MAX, MAX_DEADZONE_PERCENT

MIN_TRAVEL_PERCENT = 40.0


@dataclass(slots=True)
class AxisCalibrationCapture:
    min_raw: int | None = None
    max_raw: int | None = None
    samples: int = 0

    def reset(self) -> None:
        self.min_raw = None
        self.max_raw = None
        self.samples = 0

    def observe(self, raw: int | None) -> None:
        if raw is None:
            return
        value = max(0, min(RAW_MAX, int(raw)))
        self.min_raw = value if self.min_raw is None else min(self.min_raw, value)
        self.max_raw = value if self.max_raw is None else max(self.max_raw, value)
        self.samples += 1

    @property
    def span_raw(self) -> int:
        if self.min_raw is None or self.max_raw is None:
            return 0
        return max(0, self.max_raw - self.min_raw)

    @property
    def travel_percent(self) -> float:
        return self.span_raw * 100.0 / RAW_MAX

    @property
    def ready(self) -> bool:
        return self.samples >= 3 and self.travel_percent >= MIN_TRAVEL_PERCENT

    def proposed_deadzones(self) -> tuple[int, int]:
        if self.min_raw is None or self.max_raw is None:
            return 0, 0
        bottom = int(math.ceil(self.min_raw * 100.0 / RAW_MAX))
        top = int(math.ceil((RAW_MAX - self.max_raw) * 100.0 / RAW_MAX))
        bottom = max(0, min(MAX_DEADZONE_PERCENT, bottom))
        top = max(0, min(MAX_DEADZONE_PERCENT, top))
        if bottom + top >= 95:
            top = max(0, 94 - bottom)
        return bottom, top

    @property
    def within_supported_range(self) -> bool:
        if self.min_raw is None or self.max_raw is None:
            return False
        raw_bottom = int(math.ceil(self.min_raw * 100.0 / RAW_MAX))
        raw_top = int(math.ceil((RAW_MAX - self.max_raw) * 100.0 / RAW_MAX))
        return raw_bottom <= MAX_DEADZONE_PERCENT and raw_top <= MAX_DEADZONE_PERCENT


@dataclass(slots=True)
class PedalCalibrationCapture:
    throttle: AxisCalibrationCapture
    brake: AxisCalibrationCapture
    clutch: AxisCalibrationCapture
    handbrake: AxisCalibrationCapture

    @classmethod
    def create(cls) -> "PedalCalibrationCapture":
        return cls(AxisCalibrationCapture(), AxisCalibrationCapture(), AxisCalibrationCapture(), AxisCalibrationCapture())

    def reset(self) -> None:
        self.throttle.reset()
        self.brake.reset()
        self.clutch.reset()
        self.handbrake.reset()

    def observe(self, throttle_raw: int | None, brake_raw: int | None, clutch_raw: int | None = None, handbrake_raw: int | None = None) -> None:
        self.throttle.observe(throttle_raw)
        self.brake.observe(brake_raw)
        self.clutch.observe(clutch_raw)
        self.handbrake.observe(handbrake_raw)
