"""Persistent product/launcher settings for the packaged Windows application.

These settings are intentionally separate from coaching settings. They control
local devices, startup presentation and LAN setup only; they never alter the
telemetry/strategy algorithms.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any
import json

PRODUCT_SETTINGS_SCHEMA = 2


@dataclass(frozen=True, slots=True)
class ProductSettings:
    schema: int = PRODUCT_SETTINGS_SCHEMA
    setup_complete: bool = False
    udp_port: int = 20777
    overlay_enabled: bool = True
    overlay_click_through: bool = False
    web_dash_enabled: bool = True
    dash_host: str = "0.0.0.0"
    dash_port: int = 8765
    tts_enabled: bool = True
    audio_device: int | None = None
    mic_device: int | None = None
    ptt_enabled: bool = False
    ptt_backend: str = "hid"
    ptt_controller: int = 0
    ptt_button: int = 6
    hid_vendor_id: int = 0x303A
    hid_product_id: int = 0x1001
    hid_usage_page: int = 0x0001
    hid_usage: int = 0x0005
    stt_enabled: bool = True
    wheel_telemetry_enabled: bool = True
    wheel_port: str | None = None
    firewall_private_enabled: bool = False
    update_check_enabled: bool = False
    update_manifest_url: str = "https://api.github.com/repos/AbhilashHalappa/Racing_Engineer/releases/latest"

    def validated(self) -> "ProductSettings":
        backend = self.ptt_backend if self.ptt_backend in {"hid", "pygame"} else "hid"
        host = str(self.dash_host or "0.0.0.0").strip() or "0.0.0.0"
        wheel = str(self.wheel_port).strip() if self.wheel_port not in (None, "", "auto") else None
        return replace(
            self,
            schema=PRODUCT_SETTINGS_SCHEMA,
            udp_port=max(1, min(65535, int(self.udp_port))),
            dash_port=max(1, min(65535, int(self.dash_port))),
            dash_host=host,
            ptt_backend=backend,
            ptt_controller=max(0, int(self.ptt_controller)),
            ptt_button=max(0, min(255, int(self.ptt_button))),
            hid_vendor_id=max(0, min(0xFFFF, int(self.hid_vendor_id))),
            hid_product_id=max(0, min(0xFFFF, int(self.hid_product_id))),
            hid_usage_page=max(0, min(0xFFFF, int(self.hid_usage_page))),
            hid_usage=max(0, min(0xFFFF, int(self.hid_usage))),
            wheel_port=wheel,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.validated())

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "ProductSettings":
        if not isinstance(value, dict):
            return cls()
        allowed = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in value.items() if k in allowed}
        try:
            return cls(**kwargs).validated()
        except (TypeError, ValueError):
            return cls()


class ProductSettingsStore:
    def __init__(self, path: str | Path = "settings/product.json") -> None:
        self.path = Path(path)
        self.settings = self.load()

    def load(self) -> ProductSettings:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                return ProductSettings.from_dict(raw)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
        return ProductSettings()

    def save(self, settings: ProductSettings | None = None) -> ProductSettings:
        if settings is not None:
            self.settings = settings.validated()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.settings.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
        return self.settings

    def set(self, **changes: Any) -> ProductSettings:
        allowed = {f.name for f in fields(ProductSettings)}
        filtered = {k: v for k, v in changes.items() if k in allowed and k != "schema"}
        self.settings = replace(self.settings, **filtered).validated()
        return self.save()

    def reset(self) -> ProductSettings:
        self.settings = ProductSettings()
        return self.save()
