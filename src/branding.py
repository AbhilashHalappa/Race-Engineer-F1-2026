"""Race Engineer Stable V2 product branding.

Presentation-only metadata and asset helpers.  This module must not influence
telemetry, coaching, scoring, strategy, replay, server-sync or persistence
logic.
"""
from __future__ import annotations

from pathlib import Path

PRODUCT_NAME = "Race Engineer"
PRODUCT_FAMILY = "Stable V2"
RELEASE_LABEL = "Stable V2 RC3"
PRODUCT_VERSION = "2.0.0-rc3"
INTERNAL_BUILD = "V2.9.1.3.5.48"
TAGLINE = "Telemetry • Strategy • Coaching"
ORGANIZATION_NAME = "Race Engineer"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def brand_dir() -> Path:
    return project_root() / "assets" / "brand"


def asset(name: str) -> Path:
    return brand_dir() / name


def configure_qt_application(app) -> None:
    """Apply product metadata and the shared Windows/taskbar icon to Qt."""
    try:
        from PySide6.QtGui import QIcon
    except Exception:
        return
    app.setApplicationName(PRODUCT_NAME)
    try:
        app.setApplicationDisplayName(PRODUCT_NAME)
    except Exception:
        pass
    try:
        app.setApplicationVersion(PRODUCT_VERSION)
        app.setOrganizationName(ORGANIZATION_NAME)
    except Exception:
        pass
    icon_path = asset("race_engineer.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
