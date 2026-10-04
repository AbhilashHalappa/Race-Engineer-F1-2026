"""Audio device discovery helpers for runtime mic/output selection.

Windows exposes the same physical endpoint through several PortAudio host APIs
(MME, DirectSound, WASAPI, WDM-KS).  Older Race Engineer builds displayed only
``index: name`` which made those endpoints look like accidental duplicates.
This module keeps every real PortAudio endpoint selectable, but labels it with
its host API and Windows/PortAudio default role so the user can choose the
intended microphone/output unambiguously.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioDeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    hostapi_index: int = -1
    hostapi_name: str = "Unknown"
    is_default_input: bool = False
    is_default_output: bool = False

    @property
    def input_capable(self) -> bool:
        return self.max_input_channels > 0

    @property
    def output_capable(self) -> bool:
        return self.max_output_channels > 0

    @property
    def label(self) -> str:
        roles: list[str] = []
        if self.is_default_input:
            roles.append("DEFAULT MIC")
        if self.is_default_output:
            roles.append("DEFAULT OUT")
        role = f" • {' / '.join(roles)}" if roles else ""
        return f"{self.index}: {self.name} [{self.hostapi_name}]{role}"


def _default_indices(sd) -> tuple[int | None, int | None]:
    try:
        raw = sd.default.device
        if isinstance(raw, (tuple, list)) and len(raw) >= 2:
            i = int(raw[0]) if raw[0] is not None and int(raw[0]) >= 0 else None
            o = int(raw[1]) if raw[1] is not None and int(raw[1]) >= 0 else None
            return i, o
    except Exception:
        pass
    return None, None


def query_audio_devices() -> list[AudioDeviceInfo]:
    """Return a compact stable snapshot of PortAudio devices.

    ``sounddevice`` remains a lazy dependency so telemetry/tests can run on
    systems without physical audio hardware.
    """
    import sounddevice as sd

    try:
        hostapis = list(sd.query_hostapis())
    except Exception:
        hostapis = []
    default_in, default_out = _default_indices(sd)

    result: list[AudioDeviceInfo] = []
    for index, raw in enumerate(sd.query_devices()):
        hostapi_index = int(raw.get("hostapi") if raw.get("hostapi") is not None else -1)
        hostapi_name = "Unknown"
        if 0 <= hostapi_index < len(hostapis):
            try:
                hostapi_name = str(hostapis[hostapi_index].get("name") or "Unknown")
            except Exception:
                pass
        result.append(AudioDeviceInfo(
            index=index,
            name=str(raw.get("name") or f"Device {index}"),
            max_input_channels=int(raw.get("max_input_channels") or 0),
            max_output_channels=int(raw.get("max_output_channels") or 0),
            default_samplerate=float(raw.get("default_samplerate") or 0.0),
            hostapi_index=hostapi_index,
            hostapi_name=hostapi_name,
            is_default_input=(index == default_in),
            is_default_output=(index == default_out),
        ))
    return result


def _api_rank(name: str) -> int:
    """Prefer modern shared-mode Windows endpoints without hiding alternatives."""
    n = str(name or "").lower()
    if "wasapi" in n:
        return 0
    if "directsound" in n:
        return 1
    if "mme" in n:
        return 2
    if "wdm" in n or "ks" in n:
        return 3
    return 4


def input_devices() -> list[AudioDeviceInfo]:
    devices = [device for device in query_audio_devices() if device.input_capable]
    return sorted(devices, key=lambda d: (not d.is_default_input, _api_rank(d.hostapi_name), d.name.lower(), d.index))


def output_devices() -> list[AudioDeviceInfo]:
    devices = [device for device in query_audio_devices() if device.output_capable]
    return sorted(devices, key=lambda d: (not d.is_default_output, _api_rank(d.hostapi_name), d.name.lower(), d.index))


def default_device(*, direction: str) -> AudioDeviceInfo | None:
    try:
        devices = query_audio_devices()
        for device in devices:
            if direction == "input" and device.is_default_input and device.input_capable:
                return device
            if direction == "output" and device.is_default_output and device.output_capable:
                return device
    except Exception:
        pass
    return None


def device_name(index: int | None, *, direction: str) -> str:
    if index is None:
        default = default_device(direction=direction)
        return f"System default → {default.label}" if default is not None else "System default"
    try:
        devices = query_audio_devices()
        if 0 <= int(index) < len(devices):
            device = devices[int(index)]
            capable = device.input_capable if direction == "input" else device.output_capable
            if capable:
                return device.label
    except Exception:
        pass
    return f"Device {index}"
