"""Adapters that embed Wheel Companion hardware UI into Race Engineer.

No UDP or serial transport is created here.  The workspace consumes the normal
Race Engineer overlay snapshot for display and uses the already-running
RaceStateReceiver.wheel_bridge for all hardware I/O.
"""
from __future__ import annotations

from types import SimpleNamespace

from .models import LiveTelemetry, WheelLinkHealth
from .pedal_curves import PedalCurveSettings

ERS_MAX_STORE_J = 4_000_000.0




class _NullReceiverBridge:
    requested_port = "auto"
    last_error = "Wheel telemetry bridge is disabled"

    def health_snapshot(self):
        return WheelLinkHealth(last_error=self.last_error)

    def pedal_settings_snapshot(self):
        return PedalCurveSettings(), False, None, 0

    def request_pedal_settings(self, **_kwargs):
        return None

    def apply_pedal_settings(self, *_args, **_kwargs):
        return None

    def reset_pedal_settings(self):
        return None

    def reconfigure_port(self, port):
        self.requested_port = str(port or "auto")

class SharedTelemetryDecoder:
    def __init__(self):
        self._snapshot = None

    def update_snapshot(self, snapshot) -> None:
        self._snapshot = snapshot

    @staticmethod
    def _pct01(value) -> int:
        try:
            return max(0, min(100, int(round(float(value) * 100.0))))
        except Exception:
            return 0

    @staticmethod
    def _steer_pct(value) -> int:
        try:
            return max(-100, min(100, int(round(float(value) * 100.0))))
        except Exception:
            return 0

    def snapshots(self):
        s = self._snapshot
        if s is None:
            live = LiveTelemetry(source="RACE ENGINEER")
            return live, live

        fuel_pct = None
        try:
            mass = getattr(s, "fuel_remaining_mass", None)
            capacity = getattr(s, "fuel_capacity", None)
            if mass is not None and capacity not in (None, 0):
                fuel_pct = max(0.0, min(100.0, 100.0 * float(mass) / float(capacity)))
        except Exception:
            fuel_pct = None

        ers_pct = None
        try:
            store = getattr(s, "ers_store_j", None)
            if store is not None:
                ers_pct = max(0.0, min(100.0, 100.0 * float(store) / ERS_MAX_STORE_J))
        except Exception:
            ers_pct = None

        drs_active = bool(getattr(s, "drs_active", False))
        drs_available = bool(getattr(s, "drs_allowed", False))
        live = LiveTelemetry(
            udp_connected=bool(getattr(s, "connected", False)),
            source="RACE ENGINEER",
            packets_per_second=0.0,
            speed_kph=int(getattr(s, "speed_kph", 0) or 0),
            gear=int(getattr(s, "gear", 0) or 0),
            engine_rpm=int(getattr(s, "rpm", 0) or 0),
            rpm_percent=int(getattr(s, "rev_lights_percent", 0) or 0),
            throttle_percent=self._pct01(getattr(s, "throttle", 0.0)),
            brake_percent=self._pct01(getattr(s, "brake", 0.0)),
            steering_percent=self._steer_pct(getattr(s, "steering", 0.0)),
            drs_active=drs_active,
            drs_available=drs_available,
            position=int(getattr(s, "position", 0) or 0),
            lap_number=int(getattr(s, "lap_number", 0) or 0),
            fuel_percent=fuel_pct,
            ers_percent=ers_pct,
            ers_mode=0,
            flag_status=0,
            session_uid=int(getattr(s, "session_uid", 0) or 0),
        )
        return live, live


class SharedHardwareRuntime:
    """Small runtime facade expected by the frozen Wheel Companion UI."""

    def __init__(self, receiver_bridge):
        self.receiver = receiver_bridge if receiver_bridge is not None else _NullReceiverBridge()
        self.decoder = SharedTelemetryDecoder()
        self.udp = SimpleNamespace(last_error=None)
        self.running = True

    def update_snapshot(self, snapshot) -> None:
        self.decoder.update_snapshot(snapshot)

    def start(self) -> None:
        # RaceStateReceiver owns the actual bridge lifetime.
        self.running = True

    def close(self, wait: bool = True) -> None:
        # Embedded UI must never stop the shared bridge.
        self.running = False
