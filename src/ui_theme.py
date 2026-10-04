"""Shared UI design tokens for Race Engineer UI 1.0.

UI-only module.  It intentionally contains no telemetry, coaching, scoring,
strategy, replay or persistence-of-performance logic.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UiTokens:
    bg: str = "#080d12"
    surface: str = "#101820"
    surface_elevated: str = "#151f29"
    surface_soft: str = "#0b1219"
    border: str = "#273746"
    border_strong: str = "#3b5265"
    text: str = "#eef6fb"
    text_muted: str = "#8395a8"
    accent: str = "#4dd9ff"
    green: str = "#2ed486"
    amber: str = "#f5bd4d"
    red: str = "#ff5967"
    cyan: str = "#4dd9ff"
    grey: str = "#8395a8"
    radius_sm: int = 6
    radius_md: int = 10
    space_xs: int = 4
    space_sm: int = 8
    space_md: int = 12
    space_lg: int = 18


TOKENS = UiTokens()


# UI-R0 shared control classes and density presets. These are presentation-only
# tokens; runtime/telemetry code must not branch on them.
BUTTON_CLASSES = {
    "primary": "background:#16384a;color:#eef6fb;border:1px solid #4dd9ff;",
    "secondary": "background:#151f29;color:#eef6fb;border:1px solid #273746;",
    "destructive": "background:#32171c;color:#ff7c87;border:1px solid #6d3038;",
    "icon": "background:#151f29;color:#eef6fb;border:1px solid #273746;",
    "segmented": "background:#0b1219;color:#8395a8;border:1px solid #273746;",
    "toggle": "background:#0b1219;color:#8395a8;border:1px solid #273746;",
}

DENSITY_MODES = {
    "compact": {"spacing": 6, "control_height": 22, "card_padding": 10},
    "comfortable": {"spacing": 8, "control_height": 26, "card_padding": 14},
}

def button_class_qss(kind: str = "secondary") -> str:
    base = BUTTON_CLASSES.get(str(kind), BUTTON_CLASSES["secondary"])
    return (
        "QToolButton,QPushButton{" + base + "border-radius:6px;padding:5px 9px;font-weight:700;}"
        "QToolButton:hover,QPushButton:hover{background:#1c2a35;border-color:#3b5265;}"
        "QToolButton:pressed,QPushButton:pressed{background:#0d151d;}"
        "QToolButton:disabled,QPushButton:disabled{color:#5f6d79;background:#0d141b;border-color:#1c2933;}"
    )


def web_css_variables() -> str:
    t = TOKENS
    return (
        ":root{"
        f"--bg:{t.bg};--panel:{t.surface};--panel2:{t.surface_soft};"
        f"--panel3:{t.surface_elevated};--line:{t.border};--line-strong:{t.border_strong};"
        f"--text:{t.text};--muted:{t.text_muted};--accent:{t.accent};"
        f"--green:{t.green};--amber:{t.amber};--red:{t.red};--cyan:{t.cyan};"
        f"--radius-sm:{t.radius_sm}px;--radius-md:{t.radius_md}px;"
        "--shadow:0 8px 24px #00000024}"
    )


def qt_app_stylesheet() -> str:
    """Shared Control Center / native review styling.

    Object-specific overlay drawing remains in overlay/window.py because those
    windows use custom translucent QPainter surfaces.
    """
    t = TOKENS
    return f"""
    QWidget {{ color:{t.text}; font-family:'Segoe UI'; }}
    QDialog, QWidget#themedDialog {{ background:{t.bg}; }}
    QLabel {{ background:transparent; }}
    QTabWidget::pane {{ border:1px solid {t.border}; background:{t.surface}; border-radius:{t.radius_md}px; }}
    QTabBar::tab {{ background:{t.surface_soft}; color:{t.text_muted}; border:1px solid {t.border};
                    padding:8px 16px; min-height:20px; }}
    QTabBar::tab:selected {{ background:{t.surface_elevated}; color:{t.text}; border-bottom-color:{t.accent}; }}
    QTabBar::tab:hover {{ color:{t.text}; background:#182631; }}
    QToolButton, QPushButton {{ color:{t.text}; background:{t.surface_elevated}; border:1px solid {t.border};
                               border-radius:{t.radius_sm}px; padding:5px 9px; }}
    QToolButton:hover, QPushButton:hover {{ background:#1c2a35; border-color:{t.border_strong}; }}
    QToolButton:focus, QPushButton:focus, QComboBox:focus {{ border:2px solid {t.accent}; outline:0; }}
    QToolButton:pressed, QPushButton:pressed {{ background:#0d151d; }}
    QToolButton:disabled, QPushButton:disabled {{ color:#5f6d79; background:#0d141b; border-color:#1c2933; }}
    QComboBox {{ color:{t.text}; background:{t.surface_soft}; border:1px solid {t.border};
                 border-radius:{t.radius_sm}px; padding:5px 8px; min-height:20px; }}
    QComboBox:hover {{ border-color:{t.border_strong}; }}
    QComboBox QAbstractItemView {{ color:{t.text}; background:{t.surface}; border:1px solid {t.border};
                                  selection-background-color:#20394a; selection-color:#ffffff; }}
    QLineEdit {{ color:{t.text}; background:{t.surface_soft}; border:1px solid {t.border};
                border-radius:{t.radius_sm}px; padding:5px 8px; min-height:20px; selection-background-color:#20394a; }}
    QLineEdit:hover {{ border-color:{t.border_strong}; }}
    QLineEdit:focus {{ border:2px solid {t.accent}; background:{t.surface_soft}; }}
    QScrollArea {{ border:0; background:{t.surface}; }}
    QScrollBar:vertical {{ background:{t.surface_soft}; width:10px; margin:0; }}
    QScrollBar::handle:vertical {{ background:#354b5d; min-height:28px; border-radius:5px; }}
    QScrollBar::handle:vertical:hover {{ background:#4a6579; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
    QScrollBar:horizontal {{ background:{t.surface_soft}; height:10px; margin:0; }}
    QScrollBar::handle:horizontal {{ background:#354b5d; min-width:28px; border-radius:5px; }}
    QScrollBar::handle:horizontal:hover {{ background:#4a6579; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
    QTableWidget {{ background:{t.surface_soft}; alternate-background-color:#101922; color:{t.text};
                    border:1px solid {t.border}; border-radius:{t.radius_sm}px; selection-background-color:#20394a;
                    selection-color:#ffffff; outline:0; gridline-color:#1f2c37; }}
    QTableWidget::item {{ padding:6px; border-bottom:1px solid #1e2a35; }}
    QTableWidget::item:focus {{ border:1px solid {t.accent}; }}
    QHeaderView::section {{ background:#111a22; color:{t.text_muted}; border:0; border-right:1px solid {t.border};
                           border-bottom:1px solid {t.border}; padding:7px; font-weight:600; }}
    QToolTip {{ color:{t.text}; background:{t.surface_elevated}; border:1px solid {t.border_strong}; padding:5px; }}
    QFrame#controlCard {{ background:{t.surface}; border:1px solid {t.border}; border-radius:{t.radius_md}px; }}
    QLabel#controlCardTitle {{ color:{t.text}; background:transparent; border:0; font-weight:700; }}
    QLabel#controlCardSubtitle {{ color:{t.text_muted}; background:transparent; border:0; }}
    QFrame#controlDivider {{ background:{t.border}; border:0; }}
    QFrame#overlayManagerRow {{ background:{t.surface_soft}; border:1px solid {t.border}; border-radius:{t.radius_sm}px; }}
    QFrame#overlayManagerRow:hover {{ background:#101b24; border-color:{t.border_strong}; }}
    QFrame#overlayManagerItem {{ background:{t.surface_soft}; border:1px solid {t.border}; border-radius:{t.radius_md}px; }}
    QFrame#overlayManagerItem:hover {{ background:#101b24; border-color:{t.border_strong}; }}
    QLabel#overlayCountChip {{ color:{t.cyan}; background:#12202a; border:1px solid {t.border};
                               border-radius:9px; padding:2px 7px; font-weight:700; }}
    QSlider::groove:horizontal {{ height:4px; background:#263542; border-radius:2px; }}
    QSlider::handle:horizontal {{ width:12px; margin:-5px 0; background:{t.accent}; border:1px solid #a5efff; border-radius:6px; }}
    QSlider::sub-page:horizontal {{ background:#31586b; border-radius:2px; }}
    """


def status_qss(color: str) -> str:
    t = TOKENS
    return (
        f"QToolButton{{color:{color};background:{t.surface_soft};border:1px solid {t.border};"
        f"border-radius:{t.radius_sm}px;padding:2px 7px;font-weight:700;}}"
        f"QToolButton:hover{{background:{t.surface_elevated};border-color:{t.border_strong};}}"
        "QToolButton:disabled{color:#5f6d79;background:#0d141b;border-color:#1c2933;}"
    )
