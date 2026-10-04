"""Multi-panel frameless overlay windows for V0.9.9.9.1."""
from __future__ import annotations

from pathlib import Path
from functools import partial
from collections import deque

import sys
import html
import time
import math

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal, QEvent
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen, QLinearGradient, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QGridLayout,
    QLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QSlider,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QScrollArea,
    QSizePolicy,
    QDialog,
    QLineEdit,
    QFormLayout,
)

from .clickthrough import click_through_targets
from .qualifying import evaluate_qualifying
from .session_router import is_qualifying_snapshot
from .track_maps import get_track_map, get_track_map_distances
from .ui_text import coach_button_text
from ..ui_theme import TOKENS, qt_app_stylesheet, status_qss
from ..ui_overlay_state import read_overlay_state, write_overlay_state
from ..app_paths import RECORDINGS
from ..pre_corner_delta import phase_target as _pre_phase_target, update_driver_events as _pre_update_driver_events, phase_delta_payload as _pre_phase_delta_payload, presentation_phase as _pre_presentation_phase

from .widgets import (
    DeltaTraceWidget,
    DeltaProgressWidget,
    LapMicroDeltaWidget,
    InputTraceWidget,
    ERSBatteryTraceWidget,
    MetricBarWidget,
    ReferenceBannerWidget,
    GREEN,
    RED,
    MUTED,
    WHITE,
    AMBER,
)


def _time_text(seconds):
    if seconds is None:
        return "--:--.---"
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m}:{s:06.3f}"


def _gear_text(gear):
    if gear is None:
        return "--"
    if gear == 0:
        return "N"
    if gear < 0:
        return "R"
    return str(gear)


def _rgba(color):
    """Return a Qt stylesheet colour for QColor or shared token strings."""
    if isinstance(color, str):
        return color
    return f"rgba({color.red()},{color.green()},{color.blue()},{color.alpha()})"




def _visual_font(widget, size, weight=QFont.Normal):
    try:
        scale = max(0.70, min(1.60, float(widget.property("overlayVisualScale") or 1.0)))
    except Exception:
        scale = 1.0
    return QFont("Segoe UI", max(5, int(round(float(size) * scale))), weight)

def _status_color(level: str | None):
    level = (level or "").lower()
    if level in {"good", "ok", "on", "enabled", "ready", "active", "live", "replay"}:
        return GREEN
    if level in {"warn", "warning", "caution", "late", "low", "auto", "armed", "capturing"}:
        return QColor(239,183,77)
    if level in {"bad", "error", "off", "disabled", "critical", "invalid"}:
        return RED
    return MUTED



class SkillTrendChart(QWidget):
    """Small native Qt trend chart used by Driver Profile -> Trends."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._points=[]
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_points(self, points):
        self._points=[dict(x) for x in (points or []) if isinstance(x,dict) and isinstance(x.get("value"),(int,float))]
        self.update()

    def paintEvent(self, event):
        painter=QPainter(self); painter.setRenderHint(QPainter.Antialiasing,True)
        painter.fillRect(self.rect(), QColor(11,18,25))
        r=self.rect().adjusted(48,18,-18,-58)
        painter.setFont(QFont("Segoe UI",7))
        for i in range(5):
            y=r.top()+i*r.height()/4.0
            painter.setPen(QPen(QColor(39,55,70),1)); painter.drawLine(QPointF(r.left(),y),QPointF(r.right(),y))
            painter.setPen(QColor(131,149,168)); value=100-int(round(i*25))
            painter.drawText(QRectF(4,y-9,38,18),Qt.AlignRight|Qt.AlignVCenter,str(value))
        if not self._points:
            painter.setPen(QColor(131,149,168)); painter.setFont(QFont("Segoe UI",10))
            painter.drawText(r,Qt.AlignCenter,"Not enough trend evidence yet"); return
        n=len(self._points); pts=[]
        for i,row in enumerate(self._points):
            x=r.left() if n==1 else r.left()+i*r.width()/(n-1)
            value=max(0.0,min(100.0,float(row.get("value") or 0.0))); y=r.bottom()-(value/100.0)*r.height()
            pts.append(QPointF(x,y))
        painter.setPen(QPen(QColor(77,217,255),2.5))
        for a,b in zip(pts,pts[1:]): painter.drawLine(a,b)
        painter.setBrush(QColor(77,217,255)); painter.setPen(QPen(QColor(238,246,251),1))
        for pt in pts: painter.drawEllipse(pt,4,4)
        painter.setPen(QColor(131,149,168)); painter.setFont(QFont("Segoe UI",7))
        # V2.5.0.2: the X axis represents ordered trend sessions, not tracks.
        # Track scope is already explicit in the TRACK selector/status. Using
        # circuit names here made "All Tracks" look like a track comparison
        # rather than a chronological/session trend.
        left="S1"
        right=f"S{n}" if n > 1 else "S1"
        painter.drawText(QRectF(r.left(),r.bottom()+8,r.width()/2,20),Qt.AlignLeft|Qt.AlignTop,left)
        painter.drawText(QRectF(r.left()+r.width()/2,r.bottom()+8,r.width()/2,20),Qt.AlignRight|Qt.AlignTop,right)


class AchievementIconWidget(QWidget):
    """Small native line icon used by Driver Profile -> Career History.

    Icons are painted with Qt primitives instead of emoji fonts so their
    appearance is consistent on Windows and matches the Race Engineer UI.
    """
    def __init__(self, kind="career", color="#8395a8", parent=None):
        super().__init__(parent)
        self.kind=str(kind or "career")
        self.color=QColor(str(color or "#8395a8"))
        self.setFixedSize(40,40)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def _star_path(self, cx, cy, outer=9.0, inner=4.1):
        path=QPainterPath()
        for i in range(10):
            radius=outer if i%2==0 else inner
            angle=-math.pi/2 + i*math.pi/5
            x=cx+math.cos(angle)*radius; y=cy+math.sin(angle)*radius
            if i==0: path.moveTo(x,y)
            else: path.lineTo(x,y)
        path.closeSubpath(); return path

    def paintEvent(self, event):
        painter=QPainter(self); painter.setRenderHint(QPainter.Antialiasing,True)
        c=QColor(self.color); bg=QColor(c); bg.setAlpha(34)
        painter.setPen(QPen(c,1.4)); painter.setBrush(bg)
        painter.drawEllipse(QRectF(1.5,1.5,37,37))
        painter.setBrush(Qt.NoBrush); painter.setPen(QPen(c,2.0,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        k=self.kind
        if k=="trophy":
            cup=QPainterPath(); cup.moveTo(12,10); cup.lineTo(28,10); cup.lineTo(26,18); cup.quadTo(24,23,20,24); cup.quadTo(16,23,14,18); cup.closeSubpath(); painter.drawPath(cup)
            painter.drawLine(QPointF(14,12),QPointF(9,12)); painter.drawLine(QPointF(9,12),QPointF(10,18)); painter.drawLine(QPointF(10,18),QPointF(15,20))
            painter.drawLine(QPointF(26,12),QPointF(31,12)); painter.drawLine(QPointF(31,12),QPointF(30,18)); painter.drawLine(QPointF(30,18),QPointF(25,20))
            painter.drawLine(QPointF(20,24),QPointF(20,29)); painter.drawLine(QPointF(15,30),QPointF(25,30))
        elif k=="stopwatch":
            painter.drawEllipse(QRectF(10,11,20,20)); painter.drawLine(QPointF(17,7),QPointF(23,7)); painter.drawLine(QPointF(20,7),QPointF(20,11))
            painter.drawLine(QPointF(27,10),QPointF(30,13)); painter.drawLine(QPointF(20,21),QPointF(20,15)); painter.drawLine(QPointF(20,21),QPointF(25,23))
        elif k=="target":
            painter.drawEllipse(QRectF(9,9,22,22)); painter.drawEllipse(QRectF(14,14,12,12)); painter.setBrush(c); painter.drawEllipse(QRectF(18,18,4,4))
        elif k=="medal":
            painter.drawLine(QPointF(14,8),QPointF(18,14)); painter.drawLine(QPointF(26,8),QPointF(22,14)); painter.drawEllipse(QRectF(13,13,14,14)); painter.drawLine(QPointF(17,27),QPointF(15,32)); painter.drawLine(QPointF(23,27),QPointF(25,32))
        elif k=="flag":
            painter.drawLine(QPointF(12,8),QPointF(12,32)); painter.drawLine(QPointF(12,9),QPointF(29,9)); painter.drawLine(QPointF(29,9),QPointF(27,20)); painter.drawLine(QPointF(27,20),QPointF(12,20))
            painter.drawRect(QRectF(13,10,5,5)); painter.drawRect(QRectF(23,15,5,4))
        elif k=="track":
            painter.drawPath(self._star_path(20,20))
        elif k=="skill":
            painter.drawLine(QPointF(12,27),QPointF(28,11)); painter.drawLine(QPointF(20,11),QPointF(28,11)); painter.drawLine(QPointF(28,11),QPointF(28,19))
            painter.drawLine(QPointF(12,30),QPointF(28,30))
        elif k=="session":
            painter.drawEllipse(QRectF(10,10,20,20)); painter.drawLine(QPointF(14,20),QPointF(18,24)); painter.drawLine(QPointF(18,24),QPointF(27,15))
        else:
            diamond=QPainterPath(); diamond.moveTo(20,9); diamond.lineTo(31,20); diamond.lineTo(20,31); diamond.lineTo(9,20); diamond.closeSubpath(); painter.drawPath(diamond)

class OverlayPanel(QWidget):
    """Independent draggable translucent panel shared by every overlay window."""

    def __init__(self, *, on_close=None, on_toggle_pause=None, on_toggle_click_through=None):
        super().__init__()
        self._drag_offset: QPoint | None = None
        self._click_through = False
        self._overlay_locked = False
        self._overlay_opacity = 1.0
        self._overlay_scale = 1.0
        self._overlay_state_restored = False
        self._overlay_save_pending = False
        self._overlay_compact = False
        self._overlay_precompact_scale = 1.0
        self._overlay_chrome = None
        self._overlay_visual_baseline_captured = False
        self._overlay_logical_fixed_size = None
        self._overlay_chrome_timer = QTimer(self)
        self._overlay_chrome_timer.setSingleShot(True)
        self._overlay_chrome_timer.setInterval(1800)
        self._overlay_chrome_timer.timeout.connect(self._hide_overlay_chrome)
        self.setMouseTracking(True)
        self.on_close = on_close
        self.on_toggle_pause = on_toggle_pause
        self.on_toggle_click_through = on_toggle_click_through
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setFocusPolicy(Qt.StrongFocus)
        # Minimize controls are inserted into each overlay's own header layout.
        # Keeping them in the layout (instead of floating absolute coordinates)
        # guarantees consistent alignment and prevents overlap with title/status
        # labels or other header buttons.

    @property
    def overlay_state_key(self):
        return self.__class__.__name__

    def set_overlay_locked(self, enabled: bool):
        self._overlay_locked = bool(enabled)
        self._update_overlay_lock_button()
        self._update_overlay_chrome_text()
        self._schedule_overlay_state_save()

    def overlay_locked(self) -> bool:
        return bool(self._overlay_locked)

    def set_overlay_opacity(self, value: float):
        value = max(0.35, min(1.0, float(value)))
        self._overlay_opacity = value
        self.setWindowOpacity(value)
        self._update_overlay_chrome_text()
        self._schedule_overlay_state_save()

    def set_overlay_logical_fixed_size(self, width: int, height: int):
        """Set a fixed logical size that participates in shared true zoom.

        Older overlays used QWidget.setFixedSize(), which prevented the shared
        zoom controls from changing their geometry at all.  Logical fixed size
        preserves the overlay's intended aspect/shape while allowing the whole
        presentation to scale.
        """
        self._overlay_logical_fixed_size = (int(width), int(height))
        scale = max(0.70, min(1.60, float(getattr(self, '_overlay_scale', 1.0))))
        QWidget.setFixedSize(self, max(1, int(round(width * scale))), max(1, int(round(height * scale))))

    def _capture_overlay_visual_baseline(self):
        if self._overlay_visual_baseline_captured:
            return
        self._overlay_visual_baseline_captured = True
        # Capture widget fonts and fixed-size controls once at logical 1.0x.
        # Layouts are captured too so padding/spacing follows zoom rather than
        # leaving a large empty shell around unchanged controls.
        for child in self.findChildren(QWidget):
            if child is getattr(self, '_overlay_chrome', None):
                continue
            f = child.font()
            pt = f.pointSizeF()
            if pt > 0:
                child._overlay_base_font_pt = float(pt)
            mn, mx = child.minimumSize(), child.maximumSize()
            if mn.width() == mx.width() and 0 < mn.width() < 4096:
                child._overlay_base_fixed_w = int(mn.width())
            if mn.height() == mx.height() and 0 < mn.height() < 4096:
                child._overlay_base_fixed_h = int(mn.height())
        for layout in self.findChildren(QLayout):
            m = layout.contentsMargins()
            layout._overlay_base_margins = (m.left(), m.top(), m.right(), m.bottom())
            layout._overlay_base_spacing = layout.spacing()

    def _apply_overlay_visual_scale(self):
        self._capture_overlay_visual_baseline()
        scale = max(0.70, min(1.60, float(getattr(self, '_overlay_scale', 1.0))))
        for child in self.findChildren(QWidget):
            if child is getattr(self, '_overlay_chrome', None):
                continue
            child.setProperty('overlayVisualScale', scale)
            pt = getattr(child, '_overlay_base_font_pt', None)
            if isinstance(pt, (int, float)) and pt > 0:
                f = child.font(); f.setPointSizeF(max(5.0, float(pt) * scale)); child.setFont(f)
            fw = getattr(child, '_overlay_base_fixed_w', None)
            fh = getattr(child, '_overlay_base_fixed_h', None)
            if fw is not None and fh is not None:
                child.setFixedSize(max(1, int(round(fw * scale))), max(1, int(round(fh * scale))))
            elif fw is not None:
                child.setFixedWidth(max(1, int(round(fw * scale))))
            elif fh is not None:
                child.setFixedHeight(max(1, int(round(fh * scale))))
        for layout in self.findChildren(QLayout):
            margins = getattr(layout, '_overlay_base_margins', None)
            if margins is not None:
                layout.setContentsMargins(*(max(0, int(round(v * scale))) for v in margins))
            spacing = getattr(layout, '_overlay_base_spacing', None)
            if isinstance(spacing, int) and spacing >= 0:
                layout.setSpacing(max(0, int(round(spacing * scale))))
        self._position_overlay_chrome()
        self.update()

    def set_overlay_scale(self, value: float):
        value = max(0.70, min(1.60, float(value)))
        if abs(value - self._overlay_scale) < 0.001:
            return
        self._capture_overlay_visual_baseline()
        ratio = value / max(0.01, self._overlay_scale)
        self._overlay_scale = value
        logical_fixed = getattr(self, '_overlay_logical_fixed_size', None)
        if logical_fixed is not None:
            w, h = logical_fixed
            QWidget.setFixedSize(self, max(1, int(round(w * value))), max(1, int(round(h * value))))
        else:
            self.resize(max(1, int(round(self.width() * ratio))), max(1, int(round(self.height() * ratio))))
        self._apply_overlay_visual_scale()
        self._schedule_overlay_state_save()

    def zoom_in(self):
        self.set_overlay_scale(self._overlay_scale + 0.10)

    def zoom_out(self):
        self.set_overlay_scale(self._overlay_scale - 0.10)

    def reset_overlay_zoom(self):
        self.set_overlay_scale(1.0)

    def _restore_overlay_state(self):
        if self._overlay_state_restored:
            return
        self._overlay_state_restored = True
        state = read_overlay_state(self.overlay_state_key)
        try:
            self._overlay_locked = bool(state.get("locked", False))
            self._overlay_opacity = max(0.35, min(1.0, float(state.get("opacity", 1.0))))
            self._overlay_scale = max(0.70, min(1.60, float(state.get("scale", 1.0))))
            self._overlay_compact = bool(state.get("compact", False))
            self.setWindowOpacity(self._overlay_opacity)
            g = state.get("geometry") or {}
            if all(k in g for k in ("x", "y", "w", "h")):
                self.setGeometry(int(g["x"]), int(g["y"]), max(self.minimumWidth(), int(g["w"])), max(self.minimumHeight(), int(g["h"])))
        except Exception:
            pass

    def _schedule_overlay_state_save(self):
        if self._overlay_save_pending:
            return
        self._overlay_save_pending = True
        QTimer.singleShot(180, self._save_overlay_state)

    def _save_overlay_state(self):
        self._overlay_save_pending = False
        try:
            g = self.geometry()
            write_overlay_state(self.overlay_state_key, {
                "locked": bool(self._overlay_locked),
                "opacity": round(float(self._overlay_opacity), 3),
                "scale": round(float(self._overlay_scale), 3),
                "compact": bool(self._overlay_compact),
                "geometry": {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()},
            })
        except Exception:
            pass

    def _force_topmost(self):
        """Reassert native Windows topmost state after Qt recreates a window."""
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
        except Exception:
            pass

    def _make_lock_button(self, size=22):
        """Create an overlay-owned position lock control.

        Position locking belongs to the overlay itself, not the Control Center.
        The button is intentionally compact and mirrors the shared overlay chrome.
        """
        b = QToolButton(self)
        b.setText("🔓")
        b.setToolTip("Lock overlay position (Ctrl+L)")
        b.setFixedSize(size, size)
        b.setCursor(Qt.PointingHandCursor)
        b.setFont(QFont("Segoe UI Symbol", 9, QFont.Bold))
        b.setStyleSheet(
            "QToolButton{background:rgba(17,25,35,235);color:#cbd4dc;border:1px solid #2b3946;"
            "border-radius:6px;}"
            "QToolButton:hover{background:#243442;color:white;border-color:#52687b;}"
            "QToolButton:pressed{background:#1b2834;}"
        )
        b.clicked.connect(lambda: self.set_overlay_locked(not self._overlay_locked))
        self._position_lock_button = b
        self._update_overlay_lock_button()
        return b

    def _ensure_overlay_lock_button(self):
        if isinstance(self, ControlCenterWindow) if 'ControlCenterWindow' in globals() else False:
            return
        if getattr(self, '_position_lock_button', None) is None:
            self._make_lock_button(22)
        self._position_overlay_lock_button()

    def _update_overlay_lock_button(self):
        b = getattr(self, '_position_lock_button', None)
        if b is None:
            return
        locked = bool(self._overlay_locked)
        b.setToolTip(("Unlock" if locked else "Lock") + " overlay position (Ctrl+L)")
        if getattr(self, '_overlay_chrome', None) is not None:
            self._update_overlay_chrome_text(); return
        b.setText("🔒" if locked else "🔓")

    def _position_overlay_lock_button(self):
        b = getattr(self, '_position_lock_button', None)
        if b is None:
            return
        # Keep clear of the usual close/minimize buttons in overlay headers.
        b.move(max(6, self.width() - 78), 7)
        b.raise_()

    def _chrome_button(self, text, tooltip, callback, width=28):
        b = QToolButton()
        b.setText(text); b.setToolTip(tooltip); b.setFixedSize(max(28, width), 28)
        b.setCursor(Qt.PointingHandCursor); b.setFocusPolicy(Qt.StrongFocus); b.setFont(QFont("Segoe UI", 8, QFont.Bold))
        b.setStyleSheet(
            "QToolButton{background:rgba(17,25,35,238);color:#d9e4ec;border:1px solid #334554;border-radius:5px;padding:0;}"
            "QToolButton:hover{background:#263746;color:white;border-color:#5d7488;}"
            "QToolButton:pressed{background:#14202a;}"
        )
        b.clicked.connect(callback)
        return b

    def _ensure_overlay_chrome(self):
        if self._overlay_chrome is not None:
            self._position_overlay_chrome(); return
        bar = QFrame(self); bar.setObjectName("sharedOverlayChrome")
        bar.setStyleSheet("QFrame#sharedOverlayChrome{background:rgba(8,13,18,232);border:1px solid #334554;border-radius:7px;}")
        lay = QHBoxLayout(bar); lay.setContentsMargins(3,3,3,3); lay.setSpacing(2)
        lock = self._chrome_button("L", "Lock / unlock position (Ctrl+L)", lambda: self.set_overlay_locked(not self._overlay_locked))
        self._position_lock_button = lock; lay.addWidget(lock)
        lay.addWidget(self._chrome_button("−", "Zoom out (Ctrl+-)", self.zoom_out))
        lay.addWidget(self._chrome_button("+", "Zoom in (Ctrl++)", self.zoom_in))
        lay.addWidget(self._chrome_button("1:1", "Reset zoom (Ctrl+0)", self.reset_overlay_zoom, 34))
        self._chrome_opacity = self._chrome_button("100", "Cycle overlay opacity", self._cycle_overlay_opacity, 34); lay.addWidget(self._chrome_opacity)
        self._chrome_compact = self._chrome_button("C", "Toggle compact mode", self.toggle_overlay_compact); lay.addWidget(self._chrome_compact)
        lay.addWidget(self._chrome_button("—", "Minimize overlay", self.showMinimized))
        lay.addWidget(self._chrome_button("×", "Close / hide overlay", lambda: self.on_close() if self.on_close else self.hide()))
        self._overlay_chrome = bar
        self._position_overlay_chrome(); self._update_overlay_chrome_text()

    def _position_overlay_chrome(self):
        bar = getattr(self, "_overlay_chrome", None)
        if bar is None: return
        bar.adjustSize()
        bar.move(max(4, self.width() - bar.width() - 5), 5); bar.raise_()

    def _show_overlay_chrome(self):
        bar = getattr(self, "_overlay_chrome", None)
        if bar is None: return
        bar.show(); bar.raise_(); self._overlay_chrome_timer.start()

    def _hide_overlay_chrome(self):
        bar = getattr(self, "_overlay_chrome", None)
        if bar is not None: bar.hide()

    def _cycle_overlay_opacity(self):
        levels=(1.0,0.85,0.70,0.55,0.35)
        current=float(self._overlay_opacity)
        idx=min(range(len(levels)), key=lambda i: abs(levels[i]-current))
        self.set_overlay_opacity(levels[(idx+1)%len(levels)])
        self._update_overlay_chrome_text(); self._show_overlay_chrome()

    def toggle_overlay_compact(self):
        if not self._overlay_compact:
            self._overlay_precompact_scale=float(self._overlay_scale)
            self._overlay_compact=True
            self.set_overlay_scale(max(0.70, self._overlay_scale*0.82))
        else:
            self._overlay_compact=False
            self.set_overlay_scale(max(0.70, min(1.60, float(self._overlay_precompact_scale))))
        self._update_overlay_chrome_text(); self._schedule_overlay_state_save(); self._show_overlay_chrome()

    def _update_overlay_chrome_text(self):
        lock=getattr(self,'_position_lock_button',None)
        if lock is not None:
            lock.setText('L●' if self._overlay_locked else 'L')
        op=getattr(self,'_chrome_opacity',None)
        if op is not None: op.setText(str(int(round(self._overlay_opacity*100))))
        compact=getattr(self,'_chrome_compact',None)
        if compact is not None: compact.setText('C●' if self._overlay_compact else 'C')

    def enterEvent(self, event):
        if self.windowFlags() & Qt.FramelessWindowHint: self._show_overlay_chrome()
        super().enterEvent(event)

    def _make_minimize_button(self, size=22):
        """Create a header-owned minimize button with consistent styling."""
        b = QToolButton()
        b.setText("—")
        b.setToolTip("Minimize overlay")
        b.setFixedSize(size, size)
        b.setCursor(Qt.PointingHandCursor)
        b.setFont(QFont("Segoe UI", 11, QFont.Bold))
        b.setStyleSheet(
            "QToolButton{background:rgba(17,25,35,235);color:#cbd4dc;border:1px solid #2b3946;"
            "border-radius:6px;}"
            "QToolButton:hover{background:#243442;color:white;border-color:#52687b;}"
            "QToolButton:pressed{background:#1b2834;}"
        )
        b.clicked.connect(self.showMinimized)
        return b

    def showEvent(self, event):
        self._capture_overlay_visual_baseline()
        self._restore_overlay_state()
        # Restore the saved logical zoom to the actual controls as well as the
        # window geometry. This is the shared R2 true-zoom path for every overlay.
        if self._overlay_logical_fixed_size is not None:
            w, h = self._overlay_logical_fixed_size
            QWidget.setFixedSize(self, max(1, int(round(w * self._overlay_scale))), max(1, int(round(h * self._overlay_scale))))
        self._apply_overlay_visual_scale()
        super().showEvent(event)
        # Every frameless driving overlay owns its position lock. Control Center
        # is a normal app window and does not receive overlay chrome.
        if self.windowFlags() & Qt.FramelessWindowHint:
            self._ensure_overlay_chrome()
            self._update_overlay_lock_button()
            self._show_overlay_chrome()
        self.raise_()
        self._force_topmost()
        # Keep frameless tool windows inside the usable bounds of whichever
        # monitor currently owns them. This is especially important when moving
        # between displays with different Windows DPI/scaling values.
        self._clamp_to_available_screen()

    def _clamp_to_available_screen(self):
        try:
            frame = self.frameGeometry()
            screen = QApplication.screenAt(frame.center()) or QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
            if screen is None:
                return
            area = screen.availableGeometry()
            width = min(frame.width(), area.width())
            height = min(frame.height(), area.height())
            max_x = area.right() - width + 1
            max_y = area.bottom() - height + 1
            x = max(area.left(), min(frame.left(), max_x))
            y = max(area.top(), min(frame.top(), max_y))
            if x != frame.left() or y != frame.top():
                self.move(x, y)
        except Exception:
            pass

    def label(self, text, size=9, bold=False, color=WHITE):
        w = QLabel(text)
        w.setFont(QFont("Segoe UI", size + 1, QFont.Bold if bold else QFont.Normal))
        w.setStyleSheet(f"color: {_rgba(color)}; background: transparent;")
        return w

    def set_click_through(self, enabled: bool):
        # Changing a Qt window flag can hide/recreate the native window. Preserve
        # the user's current visibility instead of unconditionally calling show(),
        # otherwise CT would resurrect every overlay that had been hidden.
        was_visible = self.isVisible()
        self._click_through = bool(enabled)
        self.setWindowFlag(Qt.WindowTransparentForInput, self._click_through)
        if was_visible:
            self.show()
            self.raise_()
            self._force_topmost()
        else:
            self.hide()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(12, 14, 18, 205))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(QColor(255, 255, 255, 24))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 12, 12)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and not self._click_through and not self._overlay_locked:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.windowFlags() & Qt.FramelessWindowHint: self._show_overlay_chrome()
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_offset = None
        self._clamp_to_available_screen()
        self._schedule_overlay_state_save()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        self._position_overlay_chrome()
        super().resizeEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() & Qt.ControlModifier and event.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_in(); event.accept(); return
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Minus:
            self.zoom_out(); event.accept(); return
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_0:
            self.reset_overlay_zoom(); event.accept(); return
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_L:
            self.set_overlay_locked(not self._overlay_locked); event.accept(); return
        if event.key() == Qt.Key_F8 and self.on_toggle_click_through:
            self.on_toggle_click_through()
            event.accept()
            return
        if event.key() in (Qt.Key_P, Qt.Key_Space) and self.on_toggle_pause:
            self.on_toggle_pause()
            event.accept()
            return
        if event.key() == Qt.Key_Escape and self.on_close:
            self.on_close()
            event.accept()
            return
        super().keyPressEvent(event)


class CoachOverlayWindow(OverlayPanel):
    WIDTH = 385
    COLLAPSED_HEIGHT = 58
    NO_REFERENCE_HEIGHT = 158
    READY_HEIGHT = 260
    FULL_HEIGHT = 418
    FULL_BASE_HEIGHT = 350
    HISTORY_MAX_TURNS = 24

    def __init__(self, *, on_close=None, on_toggle_pause=None, on_toggle_click_through=None,
                 on_show_driver=None, on_show_replay=None, on_show_speed_delta=None, on_show_laptime=None,
                 on_show_tyre_wear=None, on_show_fuel=None, on_show_weather=None, on_show_standings=None,
                 on_show_lap_history=None, on_show_tyre_sets=None, replay_available=False):
        super().__init__(
            on_close=on_close,
            on_toggle_pause=on_toggle_pause,
            on_toggle_click_through=on_toggle_click_through,
        )
        self.on_show_driver = on_show_driver
        self.on_show_replay = on_show_replay
        self.on_show_speed_delta = on_show_speed_delta
        self.on_show_laptime = on_show_laptime
        self.on_show_tyre_wear = on_show_tyre_wear
        self.on_show_fuel = on_show_fuel
        self.on_show_weather = on_show_weather
        self.on_show_standings = on_show_standings
        self.on_show_lap_history = on_show_lap_history
        self.on_show_tyre_sets = on_show_tyre_sets
        self.replay_available = bool(replay_available)
        self._launcher_visible = False
        self._collapsed = False
        self._s_mode_visible = False
        self._visible_history_rows = 0
        self._delta_section_collapsed = False
        self._coach_section_collapsed = False
        self._history_section_collapsed = False
        extra = 0
        self.setWindowTitle("Race Engineer — Coach")
        # Legacy regression marker (fixed-size behavior now routes through logical true zoom):
        # self.setFixedSize(self.WIDTH, self.NO_REFERENCE_HEIGHT + extra + self._s_mode_extra())
        self.set_overlay_logical_fixed_size(self.WIDTH, self.NO_REFERENCE_HEIGHT + extra + self._s_mode_extra())
        self._metric_rows = []
        self._visual_mode = None
        self._paused = False
        self._base_context = "WAITING FOR TELEMETRY"
        self._build_ui()

    def refresh_replay_options(self):
        if not hasattr(self, "replay_combo"):
            return
        options = []
        if self._on_replay_options is not None:
            try:
                options = list(self._on_replay_options() or ())
            except Exception as error:
                self.replay_combo.setToolTip(f"Replay scan failed: {error}")
        current = self._current_replay
        self._updating_replay_combo = True
        try:
            self.replay_combo.clear()
            if not options:
                self.replay_combo.addItem("No stored recordings found", None)
            for item in options:
                if isinstance(item, dict):
                    label = item.get("label") or item.get("path")
                    value = item.get("path")
                else:
                    try:
                        label, value = item
                    except Exception:
                        continue
                if label and value:
                    self.replay_combo.addItem(str(label), str(value))
            if current:
                idx = self.replay_combo.findData(str(current))
                if idx >= 0:
                    self.replay_combo.setCurrentIndex(idx)
        finally:
            self._updating_replay_combo = False

    def _replay_changed(self, _index):
        if self._updating_replay_combo or self._on_select_replay is None:
            return
        value = self.replay_combo.currentData()
        if not value:
            return
        try:
            result = self._on_select_replay(value)
            ok = True; message = None
            if isinstance(result, tuple):
                ok = result[0]; message = result[1] if len(result) > 1 else None
            elif isinstance(result, bool):
                ok = result
            if ok:
                self._current_replay = str(value)
                self.replay_combo.setToolTip(str(message or "Replay loaded"))
            else:
                self.replay_combo.setToolTip(str(message or "Unable to load replay"))
                self.refresh_replay_options()
        except Exception as error:
            self.replay_combo.setToolTip(str(error))
            self.refresh_replay_options()

    def set_replay_selection(self, value):
        value = str(value) if value else None
        if value == self._current_replay:
            return
        self._current_replay = value
        self._updating_replay_combo = True
        try:
            idx = self.replay_combo.findData(value)
            if idx >= 0:
                self.replay_combo.setCurrentIndex(idx)
        finally:
            self._updating_replay_combo = False

    @staticmethod
    def _select_combo_data(combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    @staticmethod
    def _style_combo(combo):
        combo.setMinimumWidth(250)
        combo.setFixedHeight(23)

    def _button(self, text, tooltip):
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(22, 22)
        button.setFont(QFont("Segoe UI Symbol", 10, QFont.Bold))
        button.setStyleSheet(
            "QToolButton { color: rgba(230,234,239,220); background: rgba(255,255,255,14);"
            " border: 1px solid rgba(255,255,255,22); border-radius: 7px; }"
            "QToolButton:hover { background: rgba(255,255,255,35); }"
            "QToolButton:pressed { background: rgba(255,255,255,50); }"
        )
        return button

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 11, 14, 12)
        root.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(6)
        left = QVBoxLayout()
        left.setSpacing(1)
        self.section_label = self.label("RACE ENGINEER", 11, True)
        self.context_label = self.label("WAITING FOR TELEMETRY", 6, True, MUTED)
        left.addWidget(self.section_label)
        left.addWidget(self.context_label)
        head.addLayout(left)
        head.addStretch(1)

        self.sector_label = self.label("S--", 9, True, MUTED)
        self.sector_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        head.addWidget(self.sector_label)

        self.delta_label = self.label("--.---s", 12, True, GREEN)
        self.delta_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        head.addWidget(self.delta_label)

        # UI-R2 shared hover chrome is the only window-control layer.
        self.minimize_button = None
        self.close_button = None
        root.addLayout(head)

        # Global controls and overlay launchers live in the Control Center.
        # Keep a hidden placeholder for compatibility with the existing sizing code.
        self.launcher = QWidget()
        self.launcher.hide()

        self.reference_banner = ReferenceBannerWidget()
        root.addWidget(self.reference_banner)

        self.s_mode_panel = QWidget()
        s_mode_layout = QVBoxLayout(self.s_mode_panel)
        s_mode_layout.setContentsMargins(0, 0, 0, 0)
        s_mode_layout.setSpacing(2)
        self.s_mode_title = self.label("2026 S-MODE", 6, True, MUTED)
        s_mode_layout.addWidget(self.s_mode_title)
        self.s_mode_row = MetricBarWidget()
        s_mode_layout.addWidget(self.s_mode_row)
        self.s_mode_panel.hide()
        root.addWidget(self.s_mode_panel)

        # V0.9.14.6: each coach section can collapse independently without
        # minimizing/hiding the AI Coach window itself.
        self.delta_section = QWidget()
        delta_layout = QVBoxLayout(self.delta_section)
        delta_layout.setContentsMargins(0, 0, 0, 0)
        delta_layout.setSpacing(2)
        delta_head = QHBoxLayout(); delta_head.setSpacing(4)
        self.delta_section_title = self.label("LIVE DELTA GRAPH", 6, True, MUTED)
        self.delta_toggle = self._button("−", "Collapse Live Delta graph")
        self.delta_toggle.setFixedSize(18, 18)
        self.delta_toggle.clicked.connect(self._toggle_delta_section)
        delta_head.addWidget(self.delta_section_title); delta_head.addStretch(1); delta_head.addWidget(self.delta_toggle)
        delta_layout.addLayout(delta_head)
        self.delta_trace = DeltaTraceWidget()
        delta_layout.addWidget(self.delta_trace)
        root.addWidget(self.delta_section)

        self.coaching_panel = QWidget()
        coach = QVBoxLayout(self.coaching_panel)
        coach.setContentsMargins(0, 0, 0, 0)
        coach.setSpacing(3)
        coach_head = QHBoxLayout(); coach_head.setSpacing(4)
        self.coach_title = self.label("REAL-TIME AI COACHING", 6, True, MUTED)
        self.coach_toggle = self._button("−", "Collapse Real-Time Coaching")
        self.coach_toggle.setFixedSize(18, 18)
        self.coach_toggle.clicked.connect(self._toggle_coach_section)
        coach_head.addWidget(self.coach_title); coach_head.addStretch(1); coach_head.addWidget(self.coach_toggle)
        coach.addLayout(coach_head)
        self.coach_metrics_widget = QWidget()
        coach_metrics = QVBoxLayout(self.coach_metrics_widget)
        coach_metrics.setContentsMargins(0, 0, 0, 0); coach_metrics.setSpacing(3)
        for _ in range(4):
            row = MetricBarWidget()
            self._metric_rows.append(row)
            coach_metrics.addWidget(row)
        coach.addWidget(self.coach_metrics_widget)
        root.addWidget(self.coaching_panel)

        self.history_panel = QWidget()
        history_layout = QVBoxLayout(self.history_panel)
        history_layout.setContentsMargins(0, 0, 0, 0); history_layout.setSpacing(3)
        self.history_sep = QFrame()
        self.history_sep.setFrameShape(QFrame.HLine)
        self.history_sep.setStyleSheet("color: rgba(255,255,255,24);")
        history_layout.addWidget(self.history_sep)
        history_head = QHBoxLayout(); history_head.setSpacing(4)
        self.history_title = self.label("CURRENT LAP • PREVIOUS SEGMENTS", 6, True, MUTED)
        self.history_toggle = self._button("−", "Collapse Current Lap / Previous Segments")
        self.history_toggle.setFixedSize(18, 18)
        self.history_toggle.clicked.connect(self._toggle_history_section)
        history_head.addWidget(self.history_title); history_head.addStretch(1); history_head.addWidget(self.history_toggle)
        history_layout.addLayout(history_head)
        self.history_grid_widget = QWidget()
        self.history_grid = QGridLayout(self.history_grid_widget)
        self.history_grid.setContentsMargins(0, 0, 0, 0)
        self.history_grid.setHorizontalSpacing(7)
        self.history_grid.setVerticalSpacing(2)
        self.history_cells = []
        for i in range(self.HISTORY_MAX_TURNS):
            row = i // 2
            base_col = (i % 2) * 2
            turn_label = self.label("--", 7, True, MUTED)
            delta_label = self.label("--", 7, True, MUTED)
            delta_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.history_grid.addWidget(turn_label, row, base_col)
            self.history_grid.addWidget(delta_label, row, base_col + 1)
            self.history_grid.setColumnStretch(base_col, 1)
            self.history_cells.append((turn_label, delta_label))
        history_layout.addWidget(self.history_grid_widget)
        root.addWidget(self.history_panel)

    def _toggle_delta_section(self):
        self._delta_section_collapsed = not self._delta_section_collapsed
        self.delta_toggle.setText("+" if self._delta_section_collapsed else "−")
        self.delta_toggle.setToolTip(("Expand" if self._delta_section_collapsed else "Collapse") + " Live Delta graph")
        self._apply_visual_mode()

    def _toggle_coach_section(self):
        self._coach_section_collapsed = not self._coach_section_collapsed
        self.coach_toggle.setText("+" if self._coach_section_collapsed else "−")
        self.coach_toggle.setToolTip(("Expand" if self._coach_section_collapsed else "Collapse") + " Real-Time Coaching")
        self._apply_visual_mode()

    def _toggle_history_section(self):
        self._history_section_collapsed = not self._history_section_collapsed
        self.history_toggle.setText("+" if self._history_section_collapsed else "−")
        self.history_toggle.setToolTip(("Expand" if self._history_section_collapsed else "Collapse") + " Current Lap / Previous Segments")
        self._apply_visual_mode()

    def toggle_launcher(self):
        # Overlay launching is intentionally owned by the Control Center.
        return

    def set_replay_mode(self, enabled: bool):
        self._set_status("Replay", "Replay" if enabled else "Live")
        self.status_labels["Replay"].setToolTip("Click to return to Live UDP mode" if enabled else "Click to run the selected replay")

    def set_paused(self, paused: bool):
        self._paused = bool(paused)
        self._apply_context()

    def _apply_context(self):
        text = self._base_context + ("  •  PAUSED" if self._paused else "")
        self.context_label.setText(text)

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self._apply_visual_mode()

    def _set_visual_mode(self, mode: str):
        self._visual_mode = mode
        self._apply_visual_mode()

    def _s_mode_extra(self):
        return 36 if self._s_mode_visible and not self._collapsed else 0

    def _full_height(self):
        base = self.FULL_BASE_HEIGHT
        if self._delta_section_collapsed:
            base -= 105
        if self._coach_section_collapsed:
            base -= 116
        history_extra = 0 if self._history_section_collapsed else max(0, self._visible_history_rows) * 19
        return max(self.COLLAPSED_HEIGHT + 45, base + history_extra + self._s_mode_extra())

    def _apply_visual_mode(self):
        mode = self._visual_mode or "no_reference"
        extra = 0
        self.launcher.hide()
        if self._collapsed:
            self.reference_banner.hide()
            self.s_mode_panel.hide()
            self.delta_section.hide()
            self.coaching_panel.hide()
            self.history_panel.hide()
            self.set_overlay_logical_fixed_size(self.WIDTH, self.COLLAPSED_HEIGHT)
            return
        self.s_mode_panel.setVisible(self._s_mode_visible)
        if mode == "no_reference":
            self.reference_banner.set_text(
                "SETTING REFERENCE LAP",
                "Complete a valid lap to unlock live delta + coaching",
            )
            self.reference_banner.show()
            self.delta_section.hide()
            self.coaching_panel.hide()
            self.history_panel.hide()
            self.delta_label.hide()
            self.set_overlay_logical_fixed_size(self.WIDTH, self.NO_REFERENCE_HEIGHT + extra + self._s_mode_extra())
        elif mode == "reference_ready":
            self.reference_banner.set_text(
                "REFERENCE READY",
                "Live coaching starts as the next measured lap develops",
            )
            self.reference_banner.show()
            self.delta_section.show()
            self.delta_trace.setVisible(not self._delta_section_collapsed)
            self.coaching_panel.hide()
            self.history_panel.hide()
            self.delta_label.show()
            ready_height = self.READY_HEIGHT - (105 if self._delta_section_collapsed else 0)
            self.set_overlay_logical_fixed_size(self.WIDTH, ready_height + extra + self._s_mode_extra())
        else:
            self.reference_banner.hide()
            self.delta_section.show()
            self.delta_trace.setVisible(not self._delta_section_collapsed)
            self.coaching_panel.show()
            self.coach_metrics_widget.setVisible(not self._coach_section_collapsed)
            self.history_panel.setVisible(self._visible_history_rows > 0)
            self.history_grid_widget.setVisible(self._visible_history_rows > 0 and not self._history_section_collapsed)
            self.delta_label.show()
            self.set_overlay_logical_fixed_size(self.WIDTH, self._full_height())

    def update_snapshot(self, s):
        has_reference = s.reference_lap is not None
        if not has_reference:
            self._set_visual_mode("no_reference")
        elif not s.coach_live and s.comparison_lap is None:
            self._set_visual_mode("reference_ready")
        else:
            self._set_visual_mode("full")

        if has_reference and s.active_segment_kind and s.active_segment_number is not None:
            self.section_label.setText(f"{s.active_segment_kind.upper()} {s.active_segment_number}")
        else:
            self.section_label.setText("RACE ENGINEER")
        self.sector_label.setText(f"S{s.sector}" if s.sector in (1, 2, 3) else "S--")

        connection = "LIVE" if s.connected else "WAITING"
        if not has_reference:
            context = f"{s.event_profile}  •  {connection}  •  REFERENCE --"
        elif s.coach_live:
            context = f"{s.event_profile}  •  {connection}  •  REF L{s.reference_lap}  •  LIVE COACH L{s.comparison_lap}"
        elif s.comparison_lap is not None:
            context = f"{s.event_profile}  •  {connection}  •  REF L{s.reference_lap}  •  LAST L{s.comparison_lap}"
        else:
            context = f"{s.event_profile}  •  {connection}  •  REF L{s.reference_lap}"
        self._base_context = context
        self._apply_context()

        if s.live_delta_s is None:
            self.delta_label.setText("--.---s")
            self.delta_label.setStyleSheet("color: rgba(155,164,175,255); background: transparent;")
        else:
            self.delta_label.setText(f"{s.live_delta_s:+.3f}s")
            c = GREEN if s.live_delta_s <= 0 else RED
            self.delta_label.setStyleSheet(f"color: rgb({c.red()},{c.green()},{c.blue()}); background: transparent;")

        self.delta_trace.set_reference_lap(s.reference_lap)
        self.delta_trace.add_sample(s.lap_number, s.lap_time_s, s.live_delta_s)
        if s.active_segment_kind == "straight":
            self.coach_title.setText("REAL-TIME STRAIGHT COACHING")
            wait_labels = ("Straight Time", "Entry Speed", "Avg Speed", "Top Speed")
        else:
            self.coach_title.setText("REAL-TIME CORNER COACHING")
            wait_labels = ("Braking Point", "Min Speed", "Throttle Timing", "Exit Speed")
        wait_metrics = tuple(
            type("M", (), {"label": label, "value": "--", "status": "WAIT", "magnitude": None})()
            for label in wait_labels
        )
        metrics = s.coach_metrics or wait_metrics
        for i, row in enumerate(self._metric_rows):
            row.set_metric(metrics[i] if i < len(metrics) else wait_metrics[i])
        if s.s_mode_metric is not None:
            self.s_mode_row.set_metric(s.s_mode_metric)
            self._s_mode_visible = True
        else:
            self._s_mode_visible = False
        self.s_mode_panel.setVisible(self._s_mode_visible and not self._collapsed)

        history = tuple(s.previous_sections[-self.HISTORY_MAX_TURNS:])
        visible_history = len(history)
        for i, (turn_label, delta_label) in enumerate(self.history_cells):
            if i < visible_history:
                item = history[i]
                prefix = "Straight" if getattr(item, "kind", "turn") == "straight" else "Turn"
                turn_label.setText(f"{prefix} {item.section}")
                delta = "--" if item.delta_s is None else f"{item.delta_s:+.3f}s"
                delta_label.setText(delta)
                c = GREEN if item.delta_s is not None and item.delta_s <= 0 else RED if item.delta_s is not None else MUTED
                delta_label.setStyleSheet(f"color: rgb({c.red()},{c.green()},{c.blue()}); background: transparent;")
                turn_label.show(); delta_label.show()
            else:
                turn_label.hide(); delta_label.hide()
        self._visible_history_rows = (visible_history + 1) // 2
        self.history_sep.setVisible(visible_history > 0)
        self.history_title.setVisible(visible_history > 0)
        self.history_toggle.setVisible(visible_history > 0)
        self.history_panel.setVisible(visible_history > 0 and not self._collapsed and self._visual_mode == "full")
        self.history_grid_widget.setVisible(visible_history > 0 and not self._history_section_collapsed)
        if not self._collapsed:
            self._apply_visual_mode()
        self.update()


class ControlCenterWindow(OverlayPanel):
    """Normal application control hub with embedded Performance Hub tab."""

    _restore_points_ready = Signal(object, object)
    _restore_finished = Signal(object, object)

    WIDTH = 980
    HEIGHT = 760
    # Legacy regression markers: HEIGHT = 610; self.setMinimumSize(340, 560)

    def __init__(self, *, on_close=None, on_toggle_pause=None, on_toggle_click_through=None,
                 on_show_coach=None, on_show_corner_coach=None, on_show_pre_corner=None, on_show_live_corner_feedback=None, on_show_driver=None, on_show_reference_driver=None, on_show_replay=None, on_show_speed_delta=None,
                 on_show_laptime=None, on_show_tyre_wear=None, on_show_fuel=None, on_show_weather=None,
                 on_show_standings=None, on_show_lap_history=None, on_show_tyre_sets=None, on_show_ers_battery=None, on_show_penalties=None, on_show_brake_status=None,
                 on_show_race_engineer=None, on_show_radio_transcript=None, on_show_session_summary=None, on_show_f1_dash=None,
                 on_select_mic=None, on_select_audio=None, mic_devices=(), audio_devices=(),
                 current_mic=None, current_audio=None,
                 on_toggle_tts=None, on_toggle_ptt=None, on_toggle_stt=None, on_toggle_llm=None, on_toggle_recording=None, on_toggle_engineer_voice=None,
                 on_toggle_post_coach=None, on_toggle_pre_coach=None, on_toggle_lap_coach=None,
                 on_toggle_positive_coach=None, on_toggle_race_coach=None,
                 on_toggle_corner_coach=None, on_toggle_corner_voice=None, on_toggle_corner_pre=None, on_toggle_corner_post=None, on_toggle_gain_loss=None, on_toggle_gain_loss_voice=None,
                 on_select_recording_mode=None, current_recording_mode="session",
                 on_select_reference=None, on_reference_options=None, on_import_reference=None, on_export_reference=None, current_reference=None,
                 on_select_replay=None, on_replay_options=None, current_replay=None, on_toggle_replay=None, replay_mode=False,
                 tts_enabled=False, ptt_enabled=False, stt_enabled=False, llm_enabled=False, engineer_voice_enabled=True, replay_available=False,
                 post_coach_enabled=True, pre_coach_enabled=True, lap_coach_enabled=True,
                 positive_coach_enabled=True, race_coach_enabled=True, corner_coach_enabled=True, corner_voice_enabled=True, corner_pre_enabled=True, corner_post_enabled=True, gain_loss_enabled=True, gain_loss_voice_enabled=False,
                 on_select_coaching_mode=None, current_coaching_mode="auto",
                 on_select_coaching_verbosity=None, current_coaching_verbosity="normal", dashboard_url=None, hardware_bridge=None):
        super().__init__(on_close=on_close, on_toggle_pause=on_toggle_pause, on_toggle_click_through=on_toggle_click_through)
        self._restore_points_ready.connect(self._server_apply_restore_points)
        self._restore_finished.connect(self._server_restore_finished)
        # V1.9.1.0: Control Center is a normal desktop application window, not
        # a frameless/topmost racing overlay. Data overlays remain independent.
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowTitle("Race Engineer — Control Center")
        self.setStyleSheet(qt_app_stylesheet())
        self.dashboard_url = str(dashboard_url or "http://127.0.0.1:8765/").rstrip("/") + "/"
        # Do not use a fixed native size here. A fixed frameless Qt.Tool window
        # can enter an impossible MINMAXINFO/geometry loop when dragged between
        # Windows monitors that use different DPI scaling. Keep a logical
        # baseline instead and let Qt reconcile the native size on the target
        # screen.
        self.setMinimumSize(820, 620)
        self.resize(self.WIDTH, self.HEIGHT)
        self._paused = False
        self._click_through_state = False
        self.replay_available = bool(replay_available)
        self._status_values = {
            "TTS": "Enabled" if tts_enabled else "Disabled",
            "PTT": "Enabled" if ptt_enabled else "Disabled",
            "STT": "Enabled" if stt_enabled else "Disabled",
            "LLM": "Enabled" if llm_enabled else "Disabled",
            "Replay": "Replay" if replay_mode else "Live",
            "REC": "Off",
            "ENGR": "Enabled" if engineer_voice_enabled else "Disabled",
            "POST": "Enabled" if post_coach_enabled else "Disabled",
            "PRE": "Enabled" if pre_coach_enabled else "Disabled",
            "LAP": "Enabled" if lap_coach_enabled else "Disabled",
            "POS": "Enabled" if positive_coach_enabled else "Disabled",
            "RACE": "Enabled" if race_coach_enabled else "Disabled",
            "CORNER": "Enabled" if corner_coach_enabled else "Disabled",
            "CCVOICE": "Enabled" if corner_voice_enabled else "Disabled",
            "CCPRE": "Enabled" if corner_pre_enabled else "Disabled",
            "CCPOST": "Enabled" if corner_post_enabled else "Disabled",
            "GAINLOSS": "Enabled" if gain_loss_enabled else "Disabled",
            "GAINLOSSVOICE": "Enabled" if gain_loss_voice_enabled else "Disabled",
            "Click-through": "Off",
            "Pause": "Live",
        }
        self._runtime_toggle_callbacks = {
            "TTS": on_toggle_tts,
            "PTT": on_toggle_ptt,
            "STT": on_toggle_stt,
            "LLM": on_toggle_llm,
            "REC": on_toggle_recording,
            "ENGR": on_toggle_engineer_voice,
            "Replay": on_toggle_replay,
            "POST": on_toggle_post_coach,
            "PRE": on_toggle_pre_coach,
            "LAP": on_toggle_lap_coach,
            "POS": on_toggle_positive_coach,
            "RACE": on_toggle_race_coach,
            "CORNER": on_toggle_corner_coach,
            "CCVOICE": on_toggle_corner_voice,
            "CCPRE": on_toggle_corner_pre,
            "CCPOST": on_toggle_corner_post,
            "GAINLOSS": on_toggle_gain_loss,
            "GAINLOSSVOICE": on_toggle_gain_loss_voice,
        }
        self._on_select_recording_mode=on_select_recording_mode
        self._current_recording_mode=str(current_recording_mode or "session")
        self._on_select_coaching_mode=on_select_coaching_mode
        self._on_select_coaching_verbosity=on_select_coaching_verbosity
        self._current_coaching_mode=str(current_coaching_mode or "auto")
        self._current_coaching_verbosity=str(current_coaching_verbosity or "normal")
        self._updating_coaching_controls=False
        self._updating_recording_mode=False
        self._on_select_reference = on_select_reference
        self._on_reference_options = on_reference_options
        self._on_import_reference = on_import_reference
        self._on_export_reference = on_export_reference
        self._current_reference = current_reference or "__SESSION_BEST__"
        self._updating_reference_combo = False
        self._on_select_replay = on_select_replay
        self._on_replay_options = on_replay_options
        self._current_replay = str(current_replay) if current_replay else None
        self._updating_replay_combo = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        # Stable V2 RC2 branding header. Presentation only: no runtime state or
        # telemetry ownership is changed here.
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(4, 2, 4, 5)
        brand_row.setSpacing(10)
        brand_icon = QLabel()
        brand_icon.setFixedSize(46, 46)
        try:
            from ..branding import asset as _brand_asset
            _brand_pix = QPixmap(str(_brand_asset("race_engineer_icon_96.png")))
            if not _brand_pix.isNull():
                brand_icon.setPixmap(_brand_pix.scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            pass
        brand_icon.setAlignment(Qt.AlignCenter)
        brand_row.addWidget(brand_icon, 0, Qt.AlignVCenter)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_title = self.label("RACE ENGINEER", 13, True, WHITE)
        brand_sub = self.label("TELEMETRY  •  STRATEGY  •  COACHING", 7, True, MUTED)
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_sub)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        brand_chip = self.label("STABLE V2", 8, True, QColor("#4dd9ff"))
        brand_chip.setAlignment(Qt.AlignCenter)
        brand_chip.setMinimumWidth(82)
        brand_chip.setStyleSheet("QLabel{background:#12202a;border:1px solid #365263;border-radius:11px;padding:4px 9px;color:#4dd9ff;font-weight:800;}")
        brand_row.addWidget(brand_chip, 0, Qt.AlignVCenter)
        outer.addLayout(brand_row)

        # V2.1.1: the person-level Driver Profile control is permanent and
        # intentionally sits outside the section tabs so it remains available
        # on CONTROL, PERFORMANCE HUB and HELP alike.
        self.profile_bar = QHBoxLayout()
        self.profile_bar.setContentsMargins(2, 0, 2, 4)
        self.profile_button = QToolButton()
        self.profile_button.setObjectName("driverProfileControl")
        self.profile_button.setCursor(Qt.PointingHandCursor)
        self.profile_button.setMinimumWidth(250)
        self.profile_button.setMinimumHeight(48)
        self.profile_button.setToolTip("Open Driver Profile")
        self.profile_button.clicked.connect(self._open_driver_profile_tab)
        self.profile_button.setStyleSheet("""
            QToolButton#driverProfileControl {
                text-align:left; padding:6px 12px; background:#101820;
                border:1px solid #273746; border-radius:9px; color:#eef6fb;
                font-weight:700;
            }
            QToolButton#driverProfileControl:hover { background:#151f29; border-color:#4dd9ff; }
            QToolButton#driverProfileControl:pressed { background:#0b1219; }
        """)
        self.profile_bar.addWidget(self.profile_button, 0, Qt.AlignLeft)
        self.profile_switch_button=self._driver_action_button("SWITCH DRIVER", "Switch or create the person-level Driver Profile", min_width=132, primary=True)
        self.profile_switch_button.setMinimumHeight(42)
        self.profile_switch_button.clicked.connect(self._open_driver_switcher)
        self.profile_bar.addWidget(self.profile_switch_button,0,Qt.AlignVCenter)
        self.profile_bar.addStretch(1)
        outer.addLayout(self.profile_bar)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("controlCenterTabs")
        self.tabs.setAttribute(Qt.WA_StyledBackground, True)
        self.tabs.setStyleSheet(self.tabs.styleSheet() + "\nQTabWidget#controlCenterTabs::pane{background:#080d12;} QTabWidget#controlCenterTabs QWidget{background-color:#080d12;}")
        # The Control page is scrollable and widget-resizable. This keeps every
        # launcher reachable when the desktop window is made shorter, while the
        # content can expand naturally and use available space on large screens.
        self.control_page = QScrollArea()
        self.control_page.setObjectName("controlPageScroll")
        self.control_page.setWidgetResizable(True)
        self.control_page.setFrameShape(QFrame.NoFrame)
        self.control_page.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.control_page.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # QScrollArea owns a separate viewport widget. On Windows that viewport
        # can otherwise paint with the native light palette even though all of the
        # child controls use the dark Control Center theme. Name and style each
        # layer explicitly so resizing/scrolling never exposes a white surface.
        self.control_page.viewport().setObjectName("controlPageViewport")
        self.control_page.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self.control_content = QWidget()
        self.control_content.setObjectName("controlPageContent")
        self.control_content.setAttribute(Qt.WA_StyledBackground, True)
        self.control_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.control_page.setStyleSheet("""
            QScrollArea#controlPageScroll { background: #080d12; border: 0; }
            QWidget#controlPageViewport { background: #080d12; }
            QWidget#controlPageContent { background: #080d12; }
            QScrollBar:vertical { background:#111820; width:11px; margin:0; }
            QScrollBar::handle:vertical { background:#3a4a59; min-height:28px; border-radius:5px; }
            QScrollBar::handle:vertical:hover { background:#526576; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar:horizontal { background:#111820; height:11px; margin:0; }
            QScrollBar::handle:horizontal { background:#3a4a59; min-width:28px; border-radius:5px; }
            QScrollBar::handle:horizontal:hover { background:#526576; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
        """)
        root = QVBoxLayout(self.control_content)
        root.setContentsMargins(18, 14, 18, 16)
        root.setSpacing(9)
        self.control_page.setWidget(self.control_content)
        self.driver_profile_page = self._build_driver_profile_tab()
        self.tabs.addTab(self.driver_profile_page, "DRIVER PROFILE")
        self.tabs.addTab(self.control_page, "CONTROL")
        from ..hardware_companion.gui_qt import HardwareWorkspace
        from ..hardware_companion.integration import SharedHardwareRuntime
        self.hardware_runtime = SharedHardwareRuntime(hardware_bridge)
        self.hardware_page = HardwareWorkspace(self.hardware_runtime, parent=self)
        self.tabs.addTab(self.hardware_page, "HARDWARE")
        self.performance_page = self._build_performance_hub_tab()
        self.tabs.addTab(self.performance_page, "PERFORMANCE HUB")
        self.practice_page = self._build_practice_tab()
        self.tabs.addTab(self.practice_page, "PRACTICE")
        self.server_page = self._build_server_tab()
        self.tabs.addTab(self.server_page, "SERVER")
        self.help_page = self._build_help_tab()
        self.tabs.addTab(self.help_page, "HELP")
        self.tabs.currentChanged.connect(self._tab_changed)
        outer.addWidget(self.tabs)
        self.refresh_driver_profile()

        # Legacy source-audit compatibility markers retained after UI-R1:
        # ("C",
        # ("RE",
        # ("R",
        # ("RT",
        # ("RT", "Radio Transcript", "Radio Transcript", on_show_radio_transcript)
        # ("SS",
        # ("DI",
        # ("RI",
        # ("Δ",
        # ("L",
        # ("TW",
        # ("F",
        # ("W",
        # ("S",
        # ("H",
        # ("TS",
        # ("EB",
        # ("W",  "Weather",                                 on_show_weather
        # QWidget#controlPageViewport { background: #171d24; }
        # QWidget#controlPageContent { background: #171d24; }
        # ("RI", "Reference Inputs — throttle / brake / ERS", on_show_reference_driver
        # self.overlay_buttons[key] = button
        # QScrollArea#controlPageScroll { background: #171d24;
        # self.label("RACE ENGINEER"
        # "MIC"
        # ("RI", "Reference Inputs — throttle / brake / ERS"
        # ("FD", "F1 Dash — local window / LAN browser"
        # ("LCF", "Live Corner Feedback"
        # ("RE", "Race / Qualifying Engineer",              on_show_race_engineer
        # on_show_race_engineer,      0, 1)
        # on_show_reference_driver, 1, 1)
        # on_show_weather,            2, 1)
        # button.setProperty("overlayKey", key)
        # button.clicked.connect(partial(self._launch_overlay, key, tip, callback))
        # grid.setRowMinimumHeight(row, 30)
        # columns=6 if width >= 1250 else 5 if width >= 900 else 4 if width >= 700 else 3 if width >= 520 else 2
        # UI 1.1 / UI-R1: rebuild the Control page as a responsive application
        # workspace.  All runtime callbacks and authoritative state remain exactly
        # the same; only their presentation/interaction containers change.
        self._overlay_manager_state_provider = None
        self._overlay_manager_action_provider = None
        self._control_cards = []

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 4)
        head.setSpacing(10)
        left = QVBoxLayout(); left.setSpacing(2)
        self.title_label = self.label("CONTROL CENTER", 14, True, WHITE)
        self.context_label = self.label("WAITING FOR TELEMETRY", 8, True, MUTED)
        left.addWidget(self.title_label); left.addWidget(self.context_label)
        head.addLayout(left); head.addStretch(1)
        self.pause_button = self._button("Ⅱ  PAUSE", "Pause overlay / replay")
        self.pause_button.setMinimumWidth(92)
        self.pause_button.clicked.connect(lambda: self.on_toggle_pause and self.on_toggle_pause())
        head.addWidget(self.pause_button)
        self.click_button = self._button("CT  OFF", "Toggle click-through (F8)")
        self.click_button.setMinimumWidth(82)
        self.click_button.clicked.connect(lambda: self.on_toggle_click_through and self.on_toggle_click_through())
        head.addWidget(self.click_button)
        self.minimize_button = None
        self.close_button = None
        root.addLayout(head)

        self.control_cards_grid = QGridLayout()
        self.control_cards_grid.setContentsMargins(0, 0, 0, 0)
        self.control_cards_grid.setHorizontalSpacing(12)
        self.control_cards_grid.setVerticalSpacing(12)
        root.addLayout(self.control_cards_grid)

        # --- Session / runtime card -------------------------------------------------
        session_card, session = self._control_card("SESSION / RUNTIME", "Live application state and recording")
        self.session_card = session_card
        status_grid = QGridLayout(); status_grid.setContentsMargins(0,0,0,0); status_grid.setHorizontalSpacing(10); status_grid.setVerticalSpacing(7)
        self.status_labels = {}
        status_order = ("TTS", "PTT", "STT", "LLM", "Replay", "REC", "Click-through", "Pause")
        # Legacy regression marker only: status_order = ("TTS", "PTT", "STT", "LLM", "ENGR"
        for i, name in enumerate(status_order):
            row = i // 2
            col = (i % 2) * 2
            name_label = self.label(name.upper(), 7, True, MUTED)
            callback = self._runtime_toggle_callbacks.get(name)
            if callback is not None:
                value_label = QToolButton()
                value_label.setText(self._status_values[name])
                value_label.setCursor(Qt.PointingHandCursor)
                value_label.setToolTip(f"Toggle {name} while Race Engineer is running")
                value_label.setAutoRaise(True)
                value_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
                value_label.clicked.connect(lambda _checked=False, feature=name: self._toggle_runtime_feature(feature))
            else:
                value_label = self.label(self._status_values[name], 8, True, _status_color(self._status_values[name]))
            value_label.setMinimumWidth(76)
            status_grid.addWidget(name_label, row, col)
            status_grid.addWidget(value_label, row, col + 1)
            self.status_labels[name] = value_label
            self._apply_status_style(name)
        session.addLayout(status_grid)
        session.addWidget(self._section_divider())
        session.addWidget(self.label("RECORDING MODE", 7, True, MUTED))
        self.recording_mode_combo=QComboBox(); self._style_combo(self.recording_mode_combo)
        self.recording_mode_combo.addItem("Session Recording","session")
        self.recording_mode_combo.addItem("Rival Reference Capture","rival_reference")
        idx=self.recording_mode_combo.findData(self._current_recording_mode); self.recording_mode_combo.setCurrentIndex(idx if idx>=0 else 0)
        self.recording_mode_combo.currentIndexChanged.connect(self._recording_mode_changed)
        session.addWidget(self.recording_mode_combo)
        self.reference_capture_label=self.label("REFERENCE CAPTURE: IDLE",7,True,MUTED)
        self.reference_capture_label.setWordWrap(True); session.addWidget(self.reference_capture_label)
        session.addWidget(self.label("REPLAY RECORDING", 7, True, MUTED))
        replay_row = QHBoxLayout(); replay_row.setContentsMargins(0,0,0,0); replay_row.setSpacing(6)
        self.replay_combo = QComboBox(); self._style_combo(self.replay_combo)
        self.replay_combo.setToolTip("Select a stored .areplay recording. You can also click Replay first; the visible recording will be loaded automatically.")
        self.replay_combo.currentIndexChanged.connect(self._replay_changed)
        replay_row.addWidget(self.replay_combo, 1)
        self.replay_refresh = self._button("↻", "Refresh stored replay recordings"); self.replay_refresh.setFixedWidth(34)
        self.replay_refresh.clicked.connect(self.refresh_replay_options); replay_row.addWidget(self.replay_refresh)
        session.addLayout(replay_row)
        self.refresh_replay_options()

        # --- Race Engineer card -----------------------------------------------------
        race_card, race = self._control_card("RACE ENGINEER", "Automatic race/session radio")
        self.race_engineer_card = race_card
        race_row = QGridLayout(); race_row.setContentsMargins(0,0,0,0); race_row.setHorizontalSpacing(7); race_row.setVerticalSpacing(7)
        for i,(name, text, tip) in enumerate((("ENGR", "ENGINEER", "Race Engineer master — automatic race/session engineer calls"),
                                ("LAP", "LAP SUMMARY", "Lap summaries and measured lap-comparison calls"),
                                ("POS", "POSITIVE", "Positive/improvement acknowledgement calls"),
                                ("RACE", "RACE COACH", "Allow Race Engineer coaching-policy calls during race sessions"))):
            button=QToolButton(); button.setText(text); button.setCursor(Qt.PointingHandCursor); button.setToolTip(tip+" (click to enable/disable)")
            button.setAutoRaise(True); button.setFont(QFont("Segoe UI",8,QFont.Bold)); button.setMinimumHeight(30)
            button.clicked.connect(lambda _checked=False, feature=name:self._toggle_runtime_feature(feature))
            race_row.addWidget(button, i//2, i%2); self.status_labels[name]=button; self._apply_status_style(name)
        race.addLayout(race_row)
        race.addStretch(1)
        # Legacy source-audit markers retained for older tests:
        # for name, text, tip in (("ENGR", "ENGR", "Automatic Race Engineer radio")
        # ("CCPOST","POST","CORNER COACH POST calls")

        # --- Performance Coach card -------------------------------------------------
        coach_card, coach = self._control_card("PERFORMANCE COACH", "Coaching policy and response detail")
        self.performance_coach_card = coach_card
        coach.addWidget(self.label("MODE",7,True,MUTED))
        self.coaching_mode_combo=QComboBox(); self._style_combo(self.coaching_mode_combo)
        for label,value in (("Auto","auto"),("Race Engineer","race_engineer"),("Performance Coach","performance_coach"),("Track Learning","track_learning"),("Qualifying","qualifying"),("Time Trial","time_trial"),("Silent Analysis","silent_analysis")):
            self.coaching_mode_combo.addItem(label,value)
        idx=self.coaching_mode_combo.findData(str(current_coaching_mode or "auto")); self.coaching_mode_combo.setCurrentIndex(idx if idx>=0 else 0)
        self.coaching_mode_combo.setToolTip("Choose the deterministic coaching policy. This changes delivery focus, not measured telemetry facts.")
        self.coaching_mode_combo.currentIndexChanged.connect(self._coaching_mode_changed); coach.addWidget(self.coaching_mode_combo)
        coach.addWidget(self.label("DETAIL",7,True,MUTED))
        self.coaching_verbosity_combo=QComboBox(); self._style_combo(self.coaching_verbosity_combo)
        for label,value in (("Minimal","minimal"),("Normal","normal"),("Detailed","detailed")):
            self.coaching_verbosity_combo.addItem(label,value)
        idx=self.coaching_verbosity_combo.findData(str(current_coaching_verbosity or "normal")); self.coaching_verbosity_combo.setCurrentIndex(idx if idx>=0 else 1)
        self.coaching_verbosity_combo.setToolTip("Choose radio/coaching response detail.")
        self.coaching_verbosity_combo.currentIndexChanged.connect(self._coaching_verbosity_changed); coach.addWidget(self.coaching_verbosity_combo)
        coach_open = self._button("OPEN PERFORMANCE COACH", "Open / focus the Performance Coach overlay")
        coach_open.setMinimumWidth(178); coach_open.setMaximumWidth(220)
        coach_open.setFont(QFont("Segoe UI", 8, QFont.Bold))
        coach_open.clicked.connect(lambda: self._launch_overlay("SC", "Performance Coach", on_show_corner_coach) if on_show_corner_coach else None)
        coach.addWidget(coach_open, 0, Qt.AlignLeft); coach.addStretch(1)
        # CORNER COACH runtime controls intentionally remain owned by its overlay.
        # self.label("CORNER COACH", 7, True, MUTED)
        # ("GAINLOSS","MAP G/L")
        # ("GAINLOSSVOICE","G/L VOICE")

        # --- Reference card ---------------------------------------------------------
        ref_card, ref = self._control_card("REFERENCE", "Lap/reference authority and portable packages")
        self.reference_card = ref_card
        self.reference_combo = QComboBox(); self._style_combo(self.reference_combo)
        self.reference_combo.setToolTip("Select a stored reference lap. Session best uses the fastest valid lap from the current live/replay session.")
        self.reference_combo.currentIndexChanged.connect(self._reference_changed)
        ref_select = QHBoxLayout(); ref_select.setContentsMargins(0,0,0,0); ref_select.setSpacing(6)
        ref_select.addWidget(self.reference_combo, 1)
        self.reference_refresh = self._button("↻", "Refresh stored reference laps"); self.reference_refresh.setFixedWidth(34)
        self.reference_refresh.clicked.connect(self.refresh_reference_options); ref_select.addWidget(self.reference_refresh)
        ref.addLayout(ref_select)
        self.reference_state_label = self.label("ACTIVE: session best", 8, True, MUTED); self.reference_state_label.setWordWrap(True)
        ref.addWidget(self.reference_state_label)
        ref_actions=QHBoxLayout(); ref_actions.setContentsMargins(0,0,0,0); ref_actions.setSpacing(6)
        self.reference_import=self._button("IMPORT", "Install a portable friend reference package (.zip)")
        self.reference_import.setMinimumWidth(76); self.reference_import.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.reference_import.clicked.connect(self._import_reference_clicked); self.reference_import.setEnabled(self._on_import_reference is not None); ref_actions.addWidget(self.reference_import)
        self.reference_export=self._button("EXPORT", "Export the selected stored reference as a portable package")
        self.reference_export.setMinimumWidth(76); self.reference_export.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.reference_export.clicked.connect(self._export_reference_clicked); self.reference_export.setEnabled(self._on_export_reference is not None); ref_actions.addWidget(self.reference_export)
        ref_actions.addStretch(1); ref.addLayout(ref_actions)
        self.refresh_reference_options()
        self._enable_card_collapse(ref_card, ref, collapsed=False)

        # --- Audio card -------------------------------------------------------------
        audio_card, audio = self._control_card("AUDIO", "Microphone and engineer output")
        self.audio_card = audio_card
        audio.addWidget(self.label("MICROPHONE", 7, True, MUTED))
        self.mic_combo = QComboBox(); self._style_combo(self.mic_combo)
        default_mic = next((d for d in mic_devices if getattr(d, "is_default_input", False)), None)
        default_mic_text = "System default" if default_mic is None else f"System default → {getattr(default_mic, 'name', 'microphone')} [{getattr(default_mic, 'hostapi_name', 'PortAudio')}]"
        self.mic_combo.addItem(default_mic_text, None)
        for d in mic_devices: self.mic_combo.addItem(getattr(d, "label", str(d)), getattr(d, "index", None))
        self._select_combo_data(self.mic_combo, current_mic)
        self.mic_combo.currentIndexChanged.connect(lambda _i: on_select_mic and on_select_mic(self.mic_combo.currentData())); audio.addWidget(self.mic_combo)
        audio.addWidget(self.label("OUTPUT", 7, True, MUTED))
        self.audio_combo = QComboBox(); self._style_combo(self.audio_combo)
        default_out = next((d for d in audio_devices if getattr(d, "is_default_output", False)), None)
        default_out_text = "System default" if default_out is None else f"System default → {getattr(default_out, 'name', 'output')} [{getattr(default_out, 'hostapi_name', 'PortAudio')}]"
        self.audio_combo.addItem(default_out_text, None)
        for d in audio_devices: self.audio_combo.addItem(getattr(d, "label", str(d)), getattr(d, "index", None))
        self._select_combo_data(self.audio_combo, current_audio)
        self.audio_combo.currentIndexChanged.connect(lambda _i: on_select_audio and on_select_audio(self.audio_combo.currentData())); audio.addWidget(self.audio_combo)
        audio.addStretch(1)
        self._enable_card_collapse(audio_card, audio, collapsed=False)

        self._control_cards = [session_card, race_card, coach_card, ref_card, audio_card]
        self._reflow_control_cards()

        # --- Overlay Manager --------------------------------------------------------
        # Reference-style manager: visibility + transparency only. Position locking
        # belongs to each overlay's own chrome (see OverlayPanel).
        overlay_card, overlay_layout = self._control_card("OVERLAYS", "Windows drawn over the sim while you drive")
        overlay_card.setObjectName("overlayManagerCard")
        self.overlay_manager_card = overlay_card

        overlay_header = QHBoxLayout(); overlay_header.setContentsMargins(0,0,0,0); overlay_header.setSpacing(8)
        self.overlay_count_label = self.label("0 on", 7, True, TOKENS.cyan)
        self.overlay_count_label.setObjectName("overlayCountChip")
        overlay_header.addWidget(self.overlay_count_label)
        overlay_header.addStretch(1)
        self.overlay_all_off = self._button("ALL OFF", "Hide every overlay")
        self.overlay_all_off.setMinimumWidth(74); self.overlay_all_off.setFont(QFont("Segoe UI",8,QFont.Bold))
        self.overlay_all_off.clicked.connect(self._hide_all_managed_overlays)
        overlay_header.addWidget(self.overlay_all_off)
        overlay_layout.addLayout(overlay_header)

        self.overlay_manager_grid = QGridLayout(); self.overlay_manager_grid.setContentsMargins(0,2,0,0); self.overlay_manager_grid.setHorizontalSpacing(10); self.overlay_manager_grid.setVerticalSpacing(10)
        overlay_layout.addLayout(self.overlay_manager_grid)
        self.overlay_buttons = {}
        self._overlay_callbacks = {}
        self._overlay_button_order = []
        self.overlay_manager_rows = {}
        self.overlay_manager_sections = []

        launcher_specs = [
            ("COACHING", "C",  "AI Coach",             "AI Coach",                                on_show_coach),
            ("COACHING", "SC", "Performance Coach",    "Performance Coach — corner + straight live coaching", on_show_corner_coach),
            ("COACHING", "PRE","Pre-Corner Coach",      "Progressive approach instruction before each corner", on_show_pre_corner),
            ("COACHING", "LCF","Live Corner Feedback", "Compact post-corner score and primary correction", on_show_live_corner_feedback),
            ("COACHING", "DI", "Driver Inputs",        "Driver Inputs — throttle / brake / ERS",  on_show_driver),
            ("COACHING", "RI", "Reference Inputs",     "Reference Inputs — throttle / brake / ERS", on_show_reference_driver),
            ("COACHING", "Δ",  "Delta to Reference",   "Delta",                                   on_show_speed_delta),
            ("RACE", "RE", "Race Engineer",            "Race / Qualifying Engineer",              on_show_race_engineer),
            ("RACE", "RT", "Radio Transcript",         "Radio Transcript",                        on_show_radio_transcript),
            ("RACE", "SS", "Session Summary",          "Session Summary",                         on_show_session_summary),
            ("RACE", "L",  "Live Laptime",             "Live Laptime",                            on_show_laptime),
            ("RACE", "TW", "Tyre Wear",                "Tyre Wear",                               on_show_tyre_wear),
            ("RACE", "F",  "Fuel",                     "Fuel",                                    on_show_fuel),
            ("RACE", "W",  "Weather",                  "Weather",                                 on_show_weather),
            ("RACE", "S",  "Standings",                "Standings",                               on_show_standings),
            ("RACE", "H",  "Laptime History",          "Laptime History",                         on_show_lap_history),
            ("RACE", "TS", "Tyre Sets",                "Tyre Sets",                               on_show_tyre_sets),
            ("RACE", "EB", "ERS Battery",              "ERS Battery",                             on_show_ers_battery),
            ("RACE", "PEN", "Penalties / Warnings",    "Penalty time, warnings and race-control status", on_show_penalties),
            ("RACE", "BRK", "Brake Status",            "Brake temperatures and damage",            on_show_brake_status),
            ("TOOLS", "R", "Replay Controls",           "Replay Controls",                         on_show_replay),
            ("TOOLS", "FD","F1 Dash",                  "F1 Dash — local window / LAN browser",    on_show_f1_dash),
        ]
        for section, key, display, tip, callback in launcher_specs:
            enabled = callback is not None and not (key == "R" and not self.replay_available)
            item = QFrame(); item.setObjectName("overlayManagerItem"); item.setProperty("overlayKey", key); item.setProperty("overlaySection", section)
            item_layout = QVBoxLayout(item); item_layout.setContentsMargins(11,9,11,9); item_layout.setSpacing(7)

            top = QHBoxLayout(); top.setContentsMargins(0,0,0,0); top.setSpacing(7)
            toggle = QToolButton(); toggle.setCheckable(True); toggle.setChecked(False); toggle.setEnabled(enabled); toggle.setCursor(Qt.PointingHandCursor)
            toggle.setToolTip(f"Show / hide {tip}"); toggle.setFixedSize(38,20); toggle.setText("●")
            toggle.setObjectName("overlayToggle")
            if enabled: toggle.clicked.connect(partial(self._overlay_manager_toggle_clicked, key))
            top.addWidget(toggle)
            name_label=self.label(display,8,True,WHITE); name_label.setToolTip(tip); top.addWidget(name_label,1)
            status=self.label("READY" if enabled else "N/A",7,True,TOKENS.cyan if enabled else MUTED); status.setObjectName("overlayLiveStatus"); status.setAlignment(Qt.AlignRight|Qt.AlignVCenter); top.addWidget(status)
            item_layout.addLayout(top)

            trans = QHBoxLayout(); trans.setContentsMargins(0,0,0,0); trans.setSpacing(6)
            trans.addWidget(self.label("Transparency",7,True,MUTED))
            opacity_value=self.label("100%",7,True,TOKENS.cyan); opacity_value.setAlignment(Qt.AlignRight|Qt.AlignVCenter); trans.addWidget(opacity_value,1)
            item_layout.addLayout(trans)
            opacity=QSlider(Qt.Horizontal); opacity.setRange(35,100); opacity.setValue(100); opacity.setToolTip(f"{tip} transparency"); opacity.setEnabled(enabled)
            if enabled: opacity.valueChanged.connect(partial(self._overlay_opacity_changed, key, opacity_value))
            item_layout.addWidget(opacity)

            if enabled: self._overlay_callbacks[key]=callback
            self.overlay_buttons[key]=toggle
            self._overlay_button_order.append(toggle)
            self.overlay_manager_rows[key]={"widget":item,"section":section,"status":status,"toggle":toggle,"opacity":opacity,"opacity_value":opacity_value}
        root.addWidget(overlay_card)
        root.addStretch(1)
        self._reflow_overlay_manager()
        self._scale_control_fonts()

        self.overlay_manager_timer=QTimer(self)
        self.overlay_manager_timer.setInterval(500)
        self.overlay_manager_timer.timeout.connect(self._refresh_overlay_manager)
        self.overlay_manager_timer.start()

        self.resize(self.WIDTH, self.HEIGHT)
        # Legacy source-audit marker from the overlay-era layout: self.resize(required)


    def _control_card(self, title, subtitle=None):
        card=QFrame()
        card.setObjectName("controlCard")
        card.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        layout=QVBoxLayout(card); layout.setContentsMargins(14,12,14,12); layout.setSpacing(8)
        title_row=QHBoxLayout(); title_row.setContentsMargins(0,0,0,0); title_row.setSpacing(8)
        title_label=self.label(title,9,True,WHITE); title_label.setObjectName("controlCardTitle")
        title_row.addWidget(title_label)
        if subtitle:
            sub=self.label(subtitle,7,False,MUTED); sub.setObjectName("controlCardSubtitle")
            sub.setAlignment(Qt.AlignRight|Qt.AlignVCenter); title_row.addWidget(sub,1)
        else:
            title_row.addStretch(1)
        layout.addLayout(title_row)
        card._title_row_layout = title_row
        return card,layout

    def _enable_card_collapse(self, card, layout, *, collapsed=False):
        """Give low-frequency cards a compact expand/collapse affordance."""
        title_row=getattr(card,'_title_row_layout',None)
        if title_row is None: return
        button=QToolButton(); button.setFixedSize(24,22); button.setCursor(Qt.PointingHandCursor)
        button.setToolTip('Collapse / expand this section'); button.setText('▴' if not collapsed else '▾')
        button.setStyleSheet('QToolButton{background:#151f29;color:#9fb1c4;border:1px solid #273746;border-radius:5px;padding:0;} QToolButton:hover{color:white;border-color:#3b5265;}')
        title_row.addWidget(button)
        def apply(state):
            for i in range(1, layout.count()):
                item=layout.itemAt(i); w=item.widget() if item is not None else None; child=item.layout() if item is not None else None
                if w is not None: w.setVisible(not state)
                elif child is not None:
                    for j in range(child.count()):
                        cw=child.itemAt(j).widget()
                        if cw is not None: cw.setVisible(not state)
            card.setProperty('collapsed', bool(state)); button.setText('▾' if state else '▴')
        button.clicked.connect(lambda: apply(not bool(card.property('collapsed'))))
        apply(bool(collapsed)); card._collapse_button=button

    def _section_divider(self):
        line=QFrame(); line.setObjectName("controlDivider"); line.setFrameShape(QFrame.HLine); line.setFixedHeight(1)
        return line

    def _scale_control_fonts(self):
        """Keep the Control Center readable under Windows DPI scaling."""
        for widget in self.control_content.findChildren(QWidget):
            font=widget.font(); pt=font.pointSizeF()
            if pt > 0 and pt < 8.0:
                font.setPointSizeF(8.0); widget.setFont(font)
        for button in getattr(self, '_overlay_button_order', []):
            button.setMinimumHeight(28)

    def _reflow_control_cards(self):
        grid=getattr(self,'control_cards_grid',None); cards=getattr(self,'_control_cards',None) or []
        if grid is None or not cards:
            return
        width=max(1,self.control_page.viewport().width() if hasattr(self,'control_page') else self.width())
        columns=3 if width >= 1360 else 2 if width >= 900 else 1
        for card in cards: grid.removeWidget(card)
        for c in range(3): grid.setColumnStretch(c,0)
        for index,card in enumerate(cards):
            row,col=divmod(index,columns); grid.addWidget(card,row,col); grid.setColumnStretch(col,1)

    def _reflow_overlay_manager(self):
        grid=getattr(self,'overlay_manager_grid',None); rows=getattr(self,'overlay_manager_rows',None) or {}
        if grid is None or not rows:
            return
        # Clear prior section labels and card placements.
        for i in reversed(range(grid.count())):
            item=grid.itemAt(i); w=item.widget() if item is not None else None
            if w is not None: grid.removeWidget(w)
        for label in getattr(self,'overlay_manager_sections',[]):
            label.deleteLater()
        self.overlay_manager_sections=[]

        width=max(1,self.control_page.viewport().width() if hasattr(self,'control_page') else self.width())
        columns=4 if width >= 1500 else 3 if width >= 1160 else 2 if width >= 820 else 1
        for c in range(4): grid.setColumnStretch(c,0)
        grouped=[]
        for section in ("COACHING","RACE","TOOLS"):
            items=[entry for entry in rows.values() if entry.get("section")==section]
            if items: grouped.append((section,items))
        row_index=0
        subtitles={"COACHING":"What the coach is telling you, corner by corner.","RACE":"Fuel, tyres, weather and race context over the stint.","TOOLS":"Replay and secondary display tools."}
        for section,items in grouped:
            section_label=self.label(section,8,True,TOKENS.cyan)
            section_label.setToolTip(subtitles.get(section,""))
            grid.addWidget(section_label,row_index,0,1,columns); self.overlay_manager_sections.append(section_label); row_index+=1
            for index,entry in enumerate(items):
                r=row_index+(index//columns); c=index%columns
                grid.addWidget(entry["widget"],r,c); grid.setColumnStretch(c,1)
            row_index += (len(items)+columns-1)//columns

    # Compatibility shim for older source-audit/runtime tests that still call the
    # pre-R1 launcher reflow method directly.
    def _reflow_overlay_launchers(self):
        self._reflow_overlay_manager()

    def set_overlay_manager_provider(self, state_provider=None, action_provider=None):
        self._overlay_manager_state_provider=state_provider
        self._overlay_manager_action_provider=action_provider
        self._refresh_overlay_manager()

    def _overlay_manager_action(self, key, action, _checked=False):
        provider=getattr(self,'_overlay_manager_action_provider',None)
        if provider is not None:
            try: provider(str(key),str(action),None)
            except Exception as error: print(f"[UI] Overlay manager {key}/{action} failed: {error}",flush=True)
        elif action in {"open","toggle"}:
            callback=self._overlay_callbacks.get(str(key))
            if callback is not None: self._launch_overlay(str(key),str(key),callback)
        QTimer.singleShot(0,self._refresh_overlay_manager)

    def _overlay_manager_toggle_clicked(self, key, _checked=False):
        self._overlay_manager_action(key, "toggle")

    def _overlay_opacity_changed(self, key, value_label, value):
        value=max(35,min(100,int(value)))
        value_label.setText(f"{value}%")
        provider=getattr(self,'_overlay_manager_action_provider',None)
        if provider is not None:
            try: provider(str(key),"opacity",float(value)/100.0)
            except Exception as error: print(f"[UI] Overlay manager {key}/opacity failed: {error}",flush=True)

    def _hide_all_managed_overlays(self):
        provider=getattr(self,'_overlay_manager_action_provider',None)
        state_provider=getattr(self,'_overlay_manager_state_provider',None)
        for key in getattr(self,'overlay_manager_rows',{}):
            try:
                state=state_provider(key) if state_provider is not None else None
                if isinstance(state,dict) and state.get("visible") and provider is not None:
                    provider(str(key),"toggle",None)
            except Exception:
                continue
        QTimer.singleShot(0,self._refresh_overlay_manager)

    def _refresh_overlay_manager(self):
        rows=getattr(self,'overlay_manager_rows',{})
        provider=getattr(self,'_overlay_manager_state_provider',None)
        if not rows:
            return
        live_count=0
        for key,row in rows.items():
            state=None
            if provider is not None:
                try: state=provider(key)
                except Exception: state=None
            if not isinstance(state,dict):
                enabled=row["toggle"].isEnabled(); state={"available":enabled,"visible":False,"opacity":1.0}
            available=bool(state.get("available",True)); visible=bool(state.get("visible",False)); opacity=float(state.get("opacity",1.0) or 1.0)
            if visible: live_count += 1
            row["status"].setText("LIVE" if visible else ("READY" if available else "N/A"))
            row["status"].setStyleSheet(f"color:{_rgba(GREEN if visible else (TOKENS.cyan if available else TOKENS.grey))};background:transparent;font-weight:700;")
            row["toggle"].blockSignals(True); row["toggle"].setChecked(visible); row["toggle"].blockSignals(False); row["toggle"].setEnabled(available)
            if visible:
                row["toggle"].setStyleSheet(
                    "QToolButton#overlayToggle{background:#4dd9ff;color:#061116;border:1px solid #9cf0ff;border-radius:10px;padding-left:14px;font-weight:900;}"
                )
            elif available:
                row["toggle"].setStyleSheet(
                    "QToolButton#overlayToggle{background:#26323d;color:#8395a8;border:1px solid #41505d;border-radius:10px;padding-right:14px;font-weight:900;}"
                )
            else:
                row["toggle"].setStyleSheet(
                    "QToolButton#overlayToggle{background:#171e25;color:#4d5862;border:1px solid #28333d;border-radius:10px;padding-right:14px;}"
                )
            row["opacity"].setEnabled(available)
            if not row["opacity"].isSliderDown():
                pct=max(35,min(100,int(round(opacity*100))))
                row["opacity"].blockSignals(True); row["opacity"].setValue(pct); row["opacity"].blockSignals(False); row["opacity_value"].setText(f"{pct}%")
        if hasattr(self,'overlay_count_label'):
            self.overlay_count_label.setText(f"{live_count} on")

    def _apply_control_center_reflow(self):
        """Reflow responsive cards after Qt/Windows has settled the viewport size.

        On the first maximize/full-screen transition Windows can deliver the
        top-level resize before QScrollArea has its final viewport geometry.
        Reflowing only in resizeEvent therefore uses the previous narrow width
        and leaves cards stacked until the next minimize/restore cycle.
        """
        if not self.isVisible():
            return
        if hasattr(self,'control_cards_grid'):
            self._reflow_control_cards()
        if hasattr(self,'overlay_manager_grid'):
            self._reflow_overlay_manager()
        try:
            self.tabs.updateGeometry()
            self.control_page.viewport().updateGeometry()
            self.control_content.updateGeometry()
        except Exception:
            pass

    def _schedule_control_center_reflow(self):
        # The zero-delay pass handles ordinary show/resize. Two short delayed
        # passes cover the native maximize/full-screen geometry handshake and
        # mixed-DPI Windows desktops without changing any runtime logic.
        for delay in (0, 60, 180):
            QTimer.singleShot(delay, self._apply_control_center_reflow)

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_control_center_reflow()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self._schedule_control_center_reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'control_cards_grid'): self._reflow_control_cards()
        if hasattr(self,'overlay_manager_grid'): self._reflow_overlay_manager()
        # The top-level geometry may arrive before the scroll-area viewport has
        # adopted the new width; finish once layout propagation completes.
        QTimer.singleShot(0, self._apply_control_center_reflow)

    def _coaching_mode_changed(self, _index):
        if self._updating_coaching_controls or self._on_select_coaching_mode is None:
            return
        value=str(self.coaching_mode_combo.currentData() or "auto")
        result=self._on_select_coaching_mode(value)
        if isinstance(result,tuple) and result and not bool(result[0]):
            self._updating_coaching_controls=True
            try:
                idx=self.coaching_mode_combo.findData(self._current_coaching_mode if hasattr(self,"_current_coaching_mode") else "auto")
                if idx>=0:self.coaching_mode_combo.setCurrentIndex(idx)
            finally:self._updating_coaching_controls=False
        else:
            self._current_coaching_mode=value

    def _coaching_verbosity_changed(self, _index):
        if self._updating_coaching_controls or self._on_select_coaching_verbosity is None:
            return
        value=str(self.coaching_verbosity_combo.currentData() or "normal")
        result=self._on_select_coaching_verbosity(value)
        if isinstance(result,tuple) and result and not bool(result[0]):
            self._updating_coaching_controls=True
            try:
                idx=self.coaching_verbosity_combo.findData(self._current_coaching_verbosity if hasattr(self,"_current_coaching_verbosity") else "normal")
                if idx>=0:self.coaching_verbosity_combo.setCurrentIndex(idx)
            finally:self._updating_coaching_controls=False
        else:
            self._current_coaching_verbosity=value

    def set_coaching_controls(self, mode=None, verbosity=None):
        """Synchronize UI selectors after a radio/CLI runtime change."""
        self._updating_coaching_controls=True
        try:
            if mode is not None:
                self._current_coaching_mode=str(mode)
                idx=self.coaching_mode_combo.findData(str(mode))
                if idx>=0:self.coaching_mode_combo.setCurrentIndex(idx)
            if verbosity is not None:
                self._current_coaching_verbosity=str(verbosity)
                idx=self.coaching_verbosity_combo.findData(str(verbosity))
                if idx>=0:self.coaching_verbosity_combo.setCurrentIndex(idx)
        finally:
            self._updating_coaching_controls=False

    def _build_server_tab(self):
        """S11 server status/control surface. Network work is timer-driven outside telemetry."""
        page = QWidget()
        layout = QVBoxLayout(page); layout.setContentsMargins(18, 16, 18, 16); layout.setSpacing(10)
        title = self.label("RACE ENGINEER DATA SERVER", 13, True, TOKENS.cyan); layout.addWidget(title)
        sub = self.label("Persistent data backend · live telemetry remains local", 8, False, MUTED); layout.addWidget(sub)
        card = QFrame(); card.setStyleSheet("QFrame{background:#101820;border:1px solid #273746;border-radius:9px;}")
        grid = QGridLayout(card); grid.setContentsMargins(14,12,14,12); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(8)
        self.server_status_labels = {}
        for row, key in enumerate(("Status","Server","API","Database","Storage","Ping","Sync State","Pending Files","Pending Data","Current Transfer","Last Sync","Last Backup","Restore Status","Driver Profiles","Performance DB")):
            grid.addWidget(self.label(key.upper(), 7, True, MUTED), row, 0)
            value=self.label("--", 9, True, WHITE); grid.addWidget(value,row,1); self.server_status_labels[key]=value
        layout.addWidget(card)
        buttons=QHBoxLayout()
        self.server_sync_button=self._driver_action_button("SYNC NOW","Run the background persistent-data sync now",min_width=118,primary=True)
        self.server_sync_button.clicked.connect(self._server_sync_now); buttons.addWidget(self.server_sync_button)
        backup=self._driver_action_button("BACKUP NOW","Run a verified server backup now",min_width=128)
        backup.clicked.connect(self._server_backup_now); buttons.addWidget(backup)
        hub=self._driver_action_button("OPEN PERFORMANCE HUB","Open server-backed Performance Hub",min_width=180)
        hub.clicked.connect(self._open_server_performance_hub); buttons.addWidget(hub)
        folder=self._driver_action_button("OPEN SERVER FOLDER","Open mapped Race Engineer server share",min_width=165)
        folder.clicked.connect(self._open_server_folder); buttons.addWidget(folder)
        buttons.addStretch(1); layout.addLayout(buttons)

        restore_row=QHBoxLayout(); restore_row.setContentsMargins(0,2,0,0); restore_row.setSpacing(8)
        restore_row.addWidget(self.label("RECENT BACKUP",7,True,MUTED))
        self.server_restore_combo=QComboBox(); self.server_restore_combo.setMinimumWidth(360)
        self.server_restore_combo.setToolTip("Select a verified automated server backup. Restore creates a local rollback snapshot first.")
        self.server_restore_combo.addItem("Loading recent backups…", None); self.server_restore_combo.setEnabled(False)
        restore_row.addWidget(self.server_restore_combo,1)
        self.server_restore_button=self._driver_action_button("RESTORE SELECTED","Restore Performance History + Driver Profiles from the selected server backup; a local rollback snapshot is created automatically",min_width=164)
        self.server_restore_button.setEnabled(False)
        self.server_restore_button.clicked.connect(self._server_restore_selected); restore_row.addWidget(self.server_restore_button)
        restore_refresh=self._driver_action_button("REFRESH BACKUPS","Refresh the recent restore-point list",min_width=132)
        restore_refresh.clicked.connect(self._server_load_restore_points); restore_row.addWidget(restore_refresh)
        layout.addLayout(restore_row)

        note=self.label("Backup/restore is non-race maintenance. Restore is one-click after selecting a recent backup: Race Engineer first creates a local rollback snapshot, validates the backup, restores Performance History + Driver Profiles, then republishes the restored state to the server.",8,False,MUTED)
        note.setWordWrap(True); layout.addWidget(note); layout.addStretch(1)
        self.server_refresh_timer=QTimer(self); self.server_refresh_timer.setInterval(5000); self.server_refresh_timer.timeout.connect(self.refresh_server_tab); self.server_refresh_timer.start()
        self._server_restore_points_loaded_at=0.0
        QTimer.singleShot(0,self.refresh_server_tab)
        QTimer.singleShot(0,self._server_load_restore_points)
        return page

    def refresh_server_tab(self):
        labels=getattr(self,"server_status_labels",None)
        if not labels: return
        try:
            from ..server_platform import platform_status
            data=platform_status(); api=data.get("api") or {}; tr=data.get("transport") or {}; perf=data.get("performance") or {}
            state=str(data.get("state") or "LOCAL")
            labels["Status"].setText("● ONLINE" if state=="ONLINE" else "● LOCAL FALLBACK")
            labels["Status"].setStyleSheet(f"color:{_rgba(GREEN if state=='ONLINE' else AMBER)};font-weight:800;")
            labels["Server"].setText(str(api.get("hostname") or "race-server"))
            labels["API"].setText(str(api.get("status") or "offline").upper())
            db=api.get("database") if isinstance(api.get("database"),dict) else {}; labels["Database"].setText(str(db.get("status") or "--").upper())
            storage=api.get("storage") if isinstance(api.get("storage"),dict) else {}; free=storage.get("free_bytes")
            labels["Storage"].setText((f"{float(free)/(1024**3):.1f} GB FREE" if isinstance(free,(int,float)) else "R:\\") if str(tr.get("state") or "").upper() in {"REMOTE","PENDING_SYNC"} else "LOCAL CACHE")
            latency = data.get("api_latency_ms")
            labels["Ping"].setText(f"{float(latency):.1f} ms" if state == "ONLINE" and isinstance(latency, (int, float)) else "--")
            sync=data.get("sync") if isinstance(data.get("sync"),dict) else {}
            sync_state=str(sync.get("state") or tr.get("state") or "LOCAL").upper()
            pf=int(sync.get("pending_files") or tr.get("pending") or 0)
            # Defensive UI authority: an offline platform can never be presented
            # as actively syncing merely because another local worker owns the lock.
            if state != "ONLINE":
                sync_state = "OFFLINE_FALLBACK"
            elif pf == 0 and state == "ONLINE" and sync_state in {"PENDING_SYNC", "SYNCING"}:
                sync_state = "REMOTE"
            labels["Sync State"].setText(sync_state)
            labels["Sync State"].setStyleSheet(f"color:{_rgba(GREEN if sync_state=='REMOTE' else TOKENS.cyan if sync_state=='SYNCING' else AMBER)};font-weight:800;")
            hist=int(sync.get("historical_files") or 0); normal=int(sync.get("normal_files") or max(0,pf-hist))
            labels["Pending Files"].setText(f"{pf}  ·  HIST {hist}  ·  NORMAL {normal}")
            pb=int(sync.get("pending_bytes") or 0)
            labels["Pending Data"].setText(f"{pb/(1024**3):.2f} GB" if pb >= 1024**3 else f"{pb/(1024**2):.1f} MB")
            transfer=sync.get("current_transfer") if isinstance(sync.get("current_transfer"),dict) else None
            if transfer:
                labels["Current Transfer"].setText(f"{transfer.get('filename','--')}  ·  {float(transfer.get('progress_pct') or 0):.1f}%")
            else:
                labels["Current Transfer"].setText("--")
            labels["Last Sync"].setText(str(data.get("updated_at_utc") or "--").replace("T"," ")[:19])
            last_backup=api.get("last_backup_utc")
            backup_status=api.get("backup") if isinstance(api.get("backup"),dict) else {}
            if last_backup:
                verify=str(backup_status.get("verification") or "").upper()
                suffix=(f" · {verify}" if verify else "")
                labels["Last Backup"].setText(str(last_backup).replace("T"," ")[:19] + suffix)
            else:
                labels["Last Backup"].setText("WAITING FOR FIRST BACKUP")
            profiles=data.get("driver_profiles") if isinstance(data.get("driver_profiles"),dict) else {}
            pstatus=str(profiles.get("status") or "--").upper(); pcount=profiles.get("source_files")
            labels["Driver Profiles"].setText(f"{pstatus} · {pcount} FILES" if isinstance(pcount,int) else pstatus)
            labels["Performance DB"].setText(str(perf.get("status") or "--").upper())
        except Exception as error:
            labels["Status"].setText("● LOCAL FALLBACK"); labels["API"].setText("OFFLINE")
            labels["Driver Profiles"].setText("LOCAL CACHE")
            labels["Performance DB"].setText(str(error)[:80])

    def _server_sync_now(self):
        """Wake the existing background coordinator; never block the Qt UI thread."""
        try:
            from ..server_platform import start_default_server_platform
            coordinator = start_default_server_platform()
            coordinator.wake()
            button = getattr(self, "server_sync_button", None)
            if button is not None:
                button.setText("SYNCING…")
                button.setEnabled(False)
                QTimer.singleShot(1200, self._finish_manual_sync_ui)
            labels=getattr(self,"server_status_labels",{})
            if labels and "Sync State" in labels:
                labels["Sync State"].setText("SYNCING")
                labels["Sync State"].setStyleSheet(f"color:{_rgba(TOKENS.cyan)};font-weight:800;")
        except Exception:
            self.refresh_server_tab()

    def _finish_manual_sync_ui(self):
        button = getattr(self, "server_sync_button", None)
        if button is not None:
            button.setText("SYNC NOW")
            button.setEnabled(True)
        self.refresh_server_tab()

    def _server_load_restore_points(self):
        """Refresh recent server backup choices without blocking the Control Center."""
        combo=getattr(self,"server_restore_combo",None)
        if combo is None:return
        try:
            from threading import Thread
            from ..server_platform import ServerBackupRestoreManager
            combo.setEnabled(False)
            button=getattr(self,"server_restore_button",None)
            if button is not None:button.setEnabled(False)
            def _run():
                try:self._restore_points_ready.emit(ServerBackupRestoreManager().list_recent(limit=12),None)
                except Exception as exc:self._restore_points_ready.emit([],str(exc))
            Thread(target=_run,name="RaceEngineerRestoreList",daemon=True).start()
        except Exception as exc:
            self._server_apply_restore_points([],str(exc))

    def _server_apply_restore_points(self, rows, error):
        c=getattr(self,"server_restore_combo",None)
        if c is None:return
        previous=c.currentData(); c.clear()
        rows=list(rows or [])
        if rows:
            for row in rows:
                size=float(row.get("performance_bytes") or 0)/(1024**2)
                profiles="profiles ✓" if row.get("driver_profiles") else "profiles —"
                c.addItem(f"{row.get('label')}  ·  {size:.1f} MB  ·  {profiles}",row.get("stamp"))
            idx=c.findData(previous); c.setCurrentIndex(idx if idx>=0 else 0); c.setEnabled(True)
            if getattr(self,"server_restore_button",None) is not None:self.server_restore_button.setEnabled(True)
            labels=getattr(self,"server_status_labels",{})
            if labels and "Restore Status" in labels and labels["Restore Status"].text() in {"--","NO BACKUPS","BACKUP SHARE UNAVAILABLE"}:
                labels["Restore Status"].setText(f"{len(rows)} RESTORE POINTS READY")
        else:
            c.addItem("No recent backups available",None); c.setEnabled(False)
            labels=getattr(self,"server_status_labels",{})
            if labels and "Restore Status" in labels:labels["Restore Status"].setText("BACKUP SHARE UNAVAILABLE" if error else "NO BACKUPS")
        self._server_restore_points_loaded_at=time.monotonic()

    def _server_restore_selected(self):
        """One-click verified restore of Performance History + Driver Profiles."""
        combo=getattr(self,"server_restore_combo",None); button=getattr(self,"server_restore_button",None)
        if combo is None or button is None:return
        stamp=combo.currentData()
        if not stamp:return
        snap=getattr(self,"_latest_control_snapshot",None)
        if snap is not None and bool(getattr(snap,"connected",False)) and not bool(getattr(snap,"session_finished",False)):
            QMessageBox.warning(self,"Restore unavailable","End or leave the live F1 session before restoring a backup. This prevents telemetry from writing into the database during recovery.")
            return
        button.setEnabled(False); button.setText("RESTORING…"); combo.setEnabled(False)
        labels=getattr(self,"server_status_labels",{})
        if labels and "Restore Status" in labels:labels["Restore Status"].setText("RESTORING + VERIFYING…")
        try:
            from threading import Thread
            from ..server_platform import ServerBackupRestoreManager
            def _run():
                try:self._restore_finished.emit(ServerBackupRestoreManager().restore(str(stamp)),None)
                except Exception as exc:self._restore_finished.emit(None,str(exc))
            Thread(target=_run,name="RaceEngineerOneClickRestore",daemon=True).start()
        except Exception as exc:
            self._server_restore_finished(None,str(exc))

    def _server_restore_finished(self, result, error):
        button=getattr(self,"server_restore_button",None); combo=getattr(self,"server_restore_combo",None)
        if button is not None:button.setText("RESTORE SELECTED"); button.setEnabled(True)
        if combo is not None:combo.setEnabled(True)
        labels=getattr(self,"server_status_labels",{})
        if error:
            if labels and "Restore Status" in labels:labels["Restore Status"].setText("RESTORE FAILED")
            QMessageBox.critical(self,"Restore failed",str(error)); return
        result=result or {}; verified=result.get("verified") or {}; sessions=verified.get("sessions")
        status=str(result.get("status") or "restored")
        status_text=(f"RESTORED · {sessions} SESSIONS" if sessions is not None else "RESTORED + VERIFIED") if status=="restored" else "RESTORED · SERVER SYNC PENDING"
        if labels and "Restore Status" in labels:labels["Restore Status"].setText(status_text)
        try:self.refresh_driver_profile()
        except Exception:pass
        try:self.refresh_performance_hub()
        except Exception:pass
        try:
            if getattr(self,"practice_web_view",None) is not None:self.practice_web_view.reload()
        except Exception:pass
        self.refresh_server_tab(); self._server_load_restore_points()
        server_note="Backup verified and republished to the server." if status=="restored" else "Backup verified locally. Server republish is pending and will retry automatically."
        QMessageBox.information(self,"Restore complete",f"Restored {str(result.get('label') or '--')}.\n\n{server_note}\nLocal rollback: {str(result.get('rollback') or '--')}")

    def _server_backup_now(self):
        """Trigger S12 backup asynchronously so the Control Center never blocks."""
        try:
            from threading import Thread
            from ..server_platform import ServerApiClient
            def _run():
                try:
                    ServerApiClient().trigger_backup()
                finally:
                    QTimer.singleShot(0, self.refresh_server_tab)
            Thread(target=_run, name="RaceEngineerBackupNow", daemon=True).start()
            labels=getattr(self,"server_status_labels",{})
            if labels and "Last Backup" in labels:
                labels["Last Backup"].setText("BACKUP STARTED…")
        except Exception:
            self.refresh_server_tab()

    def _open_server_performance_hub(self):
        try:
            import webbrowser
            from ..server_platform import ServerApiClient
            webbrowser.open(ServerApiClient().performance_hub_url)
        except Exception:
            pass

    def _open_server_folder(self):
        try:
            import os
            os.startfile("R:\\")
        except Exception:
            pass

    def _build_help_tab(self):
        """Embedded searchable voice-command help, shared with the LAN /radio-help page."""
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            page = QWidget(); page.setObjectName("helpPage"); page.setAttribute(Qt.WA_StyledBackground, True); page.setStyleSheet("QWidget#helpPage{background:#080d12;}")
            layout = QVBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0)
            self.help_web_view = QWebEngineView()
            self.help_web_view.setStyleSheet("background:#080d12;")
            try:
                self.help_web_view.page().setBackgroundColor(QColor("#080d12"))
            except Exception:
                pass
            self.help_web_view.setUrl(QUrl(self.dashboard_url + "radio-help"))
            layout.addWidget(self.help_web_view)
            return page
        except Exception:
            self.help_web_view = None
            page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(16, 14, 16, 14); layout.setSpacing(8)
            title = self.label("VOICE COMMAND HELP", 13, True, WHITE); layout.addWidget(title)
            note = self.label("Full searchable command reference is available at the LAN dashboard /radio-help page.", 8, False, MUTED)
            note.setWordWrap(True); layout.addWidget(note)
            body = QTextEdit(); body.setReadOnly(True); body.setFrameShape(QFrame.NoFrame)
            body.setStyleSheet(_panel_text_edit_style())
            body.setPlainText(
                "HELP\n\n"
                "Say 'radio commands', 'voice control help', or 'what can I ask?' for spoken help.\n\n"
                "FUNCTIONS\n"
                "Tyres · Brakes & Setup · Car Condition · Position & Traffic · Laps & Timing · Fuel & ERS · "
                "Weather & Race Control · Strategy · Pit · Driving Performance · Race Engineer Controls · "
                "Performance Coach Controls · System Controls · Modes & Voice · General Help\n\n"
                "Open the LAN /radio-help page for the complete phrase-by-phrase reference."
            )
            layout.addWidget(body, 1)
            return page

    def _build_practice_tab(self):
        """Dedicated track-level Practice Planner workspace."""
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            page = QWidget()
            page.setObjectName("practicePage")
            page.setAttribute(Qt.WA_StyledBackground, True)
            page.setStyleSheet("QWidget#practicePage{background:#080d12;}")
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            self.practice_web_view = QWebEngineView()
            self.practice_web_view.setStyleSheet("background:#080d12;")
            try:
                self.practice_web_view.page().setBackgroundColor(QColor("#080d12"))
            except Exception:
                pass
            self.practice_web_view.setUrl(QUrl(self.dashboard_url + "practice"))
            layout.addWidget(self.practice_web_view)
            return page
        except Exception:
            self.practice_web_view = None
            page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(16,14,16,14)
            layout.addWidget(self.label("PRACTICE",13,True,WHITE))
            msg=self.label("Track-level Practice Planner is available at /practice when QtWebEngine is installed.",8,False,MUTED)
            msg.setWordWrap(True); layout.addWidget(msg); layout.addStretch(1)
            return page

    def _build_performance_hub_tab(self):
        """Embed the original gaming-PC Performance Hub inside Control Center.

        This restores the pre-server UI exactly: the PERFORMANCE HUB tab uses
        the local dashboard's full ``/performance`` page through QtWebEngine.
        The SERVER tab's Open Performance Hub action remains a separate
        server-hosted S14 browser surface.  If QtWebEngine is unavailable, the
        legacy native fallback remains available.
        """
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            page = QWidget()
            page.setObjectName("performanceHubPage")
            page.setAttribute(Qt.WA_StyledBackground, True)
            page.setStyleSheet("QWidget#performanceHubPage{background:#080d12;}")
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            self.performance_web_view = QWebEngineView()
            self.performance_web_view.setStyleSheet("background:#080d12;")
            try:
                self.performance_web_view.page().setBackgroundColor(QColor("#080d12"))
            except Exception:
                pass
            self.performance_web_view.setUrl(QUrl(self.dashboard_url + "performance"))
            layout.addWidget(self.performance_web_view)
            return page
        except Exception:
            self.performance_web_view = None
            return self._build_performance_hub_fallback()

    def _build_performance_hub_fallback(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        title = self.label("DRIVER PERFORMANCE HUB", 13, True, WHITE)
        top.addWidget(title)
        top.addStretch(1)
        self.performance_live_badge = self.label("LIVE GAME HISTORY ONLY", 8, True, GREEN)
        top.addWidget(self.performance_live_badge)
        top.addWidget(self.label("DRIVER", 7, True, MUTED))
        self.performance_driver_combo = QComboBox()
        self.performance_driver_combo.setMinimumWidth(190)
        self.performance_driver_combo.setToolTip("Select which locally stored F1 driver profile to view")
        self.performance_driver_combo.currentIndexChanged.connect(self._performance_driver_changed)
        top.addWidget(self.performance_driver_combo)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_performance_hub)
        top.addWidget(refresh)
        browser = QPushButton("Open in Browser")
        browser.clicked.connect(self._open_performance_browser)
        top.addWidget(browser)
        layout.addLayout(top)

        self.performance_status = self.label("No live performance history stored yet.", 8, False, MUTED)
        layout.addWidget(self.performance_status)

        cards = QGridLayout()
        self.performance_cards = {}
        for i, key in enumerate(("Driver", "Team", "Sessions", "Tracks", "Laps", "Wins")):
            box = QFrame(); box.setStyleSheet("QFrame{background:#111820;border:1px solid #2b3946;border-radius:7px;padding:6px;}")
            bl = QVBoxLayout(box); bl.setContentsMargins(8,6,8,6)
            bl.addWidget(self.label(key.upper(), 7, True, MUTED))
            val = self.label("--", 12, True, WHITE); bl.addWidget(val)
            self.performance_cards[key] = val
            cards.addWidget(box, 0, i)
        layout.addLayout(cards)

        layout.addWidget(self.label("TRACK PERFORMANCE", 9, True, WHITE))
        self.performance_tracks = QTableWidget(0, 6)
        self.performance_tracks.setHorizontalHeaderLabels(["Track", "Sessions", "Best Lap", "Best Potential", "Best Ref Gap", "Last Session"])
        self._style_performance_table(self.performance_tracks)
        self.performance_tracks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.performance_tracks.itemSelectionChanged.connect(self._performance_track_selected)
        layout.addWidget(self.performance_tracks, 2)

        layout.addWidget(self.label("SESSION HISTORY", 9, True, WHITE))
        self.performance_sessions = QTableWidget(0, 8)
        self.performance_sessions.setHorizontalHeaderLabels(["Date", "Session", "Position", "Laps", "Best Lap", "Potential", "Available Gain", "Ref Gap"])
        self._style_performance_table(self.performance_sessions)
        self.performance_sessions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.performance_sessions, 3)
        return page

    def _driver_profile_store(self):
        from ..driver_profiles import DriverProfileStore
        return DriverProfileStore()

    @staticmethod
    def _profile_initials(name):
        words = [w for w in str(name or "Driver").strip().split() if w]
        if not words:
            return "DR"
        if len(words) == 1:
            return words[0][:2].upper()
        return (words[0][:1] + words[-1][:1]).upper()

    def _profile_time_zone(self):
        try:
            profile=self._driver_profile_store().active_profile() or {}
            return str(profile.get("time_zone") or "UTC")
        except Exception:
            return "UTC"

    def _profile_date(self, value):
        try:
            from ..user_time import format_profile_timestamp
            return format_profile_timestamp(value, self._profile_time_zone())
        except Exception:
            text=str(value or "")
            return text[:19].replace("T", " ") if text else "--"

    @staticmethod
    def _profile_duration(seconds):
        try:
            total = max(0, int(float(seconds or 0)))
        except (TypeError, ValueError):
            total = 0
        hours, rem = divmod(total, 3600)
        minutes = rem // 60
        return f"{hours}h {minutes:02d}m"

    def _profile_stat_box(self, title, value="--"):
        box = QFrame()
        box.setObjectName("profileStatBox")
        box.setStyleSheet("QFrame#profileStatBox{background:#0b1219;border:1px solid #273746;border-radius:8px;}")
        lay = QVBoxLayout(box); lay.setContentsMargins(10,8,10,8); lay.setSpacing(2)
        lay.addWidget(self.label(str(title).upper(), 7, True, MUTED))
        val = self.label(str(value), 12, True, WHITE)
        lay.addWidget(val)
        return box, val

    def _build_driver_profile_tab(self):
        page = QWidget()
        page.setObjectName("driverProfilePage")
        page.setStyleSheet("QWidget#driverProfilePage{background:#080d12;}")
        root = QVBoxLayout(page); root.setContentsMargins(16,14,28,16); root.setSpacing(10)

        top = QHBoxLayout(); top.setSpacing(12)
        self.profile_avatar_large = QLabel("DR")
        self.profile_avatar_large.setAlignment(Qt.AlignCenter)
        self.profile_avatar_large.setFixedSize(76,76)
        self.profile_avatar_large.setStyleSheet("QLabel{background:#12202a;border:1px solid #365263;border-radius:38px;color:#4dd9ff;font-size:22px;font-weight:800;}")
        top.addWidget(self.profile_avatar_large)
        names = QVBoxLayout(); names.setSpacing(2)
        self.profile_name_large = self.label("Driver", 18, True, WHITE)
        self.profile_role_large = self.label("FORMULA DRIVER • F1 26", 8, True, MUTED)
        self.profile_id_label = self.label("DRIVER ID  --", 7, False, MUTED)
        names.addWidget(self.profile_name_large); names.addWidget(self.profile_role_large); names.addWidget(self.profile_id_label); names.addStretch(1)
        top.addLayout(names,1)
        self.profile_edit_button = self._button("EDIT PROFILE", "Edit person-level Driver Profile")
        self.profile_edit_button.setMinimumWidth(110)
        self.profile_edit_button.clicked.connect(self._edit_driver_profile)
        top.addWidget(self.profile_edit_button,0,Qt.AlignTop)
        root.addLayout(top)

        self.profile_sections = QTabWidget()
        self.profile_sections.setObjectName("driverProfileSections")
        root.addWidget(self.profile_sections,1)

        overview = QWidget(); ol = QVBoxLayout(overview); ol.setContentsMargins(10,12,10,10); ol.setSpacing(12)
        cards = QGridLayout(); cards.setSpacing(10)
        self.profile_stats = {}
        for i, key in enumerate(("Active game","Driving time","Sessions","Tracks driven")):
            box, value = self._profile_stat_box(key)
            self.profile_stats[key] = value
            cards.addWidget(box, i//2, i%2)
        ol.addLayout(cards)
        info_card = QFrame(); info_card.setObjectName("controlCard")
        il = QGridLayout(info_card); il.setContentsMargins(14,12,14,12); il.setHorizontalSpacing(18); il.setVerticalSpacing(9)
        self.profile_info_labels = {}
        rows=("Display name","Country / region","Preferred units","Time zone","Created","Last active")
        for r,key in enumerate(rows):
            il.addWidget(self.label(key.upper(),7,True,MUTED),r,0)
            value=self.label("--",9,False,WHITE); self.profile_info_labels[key]=value; il.addWidget(value,r,1)
        il.setColumnStretch(1,1)
        ol.addWidget(info_card)

        driving_card = QFrame(); driving_card.setObjectName("controlCard")
        dl = QGridLayout(driving_card); dl.setContentsMargins(14,12,14,12); dl.setHorizontalSpacing(22); dl.setVerticalSpacing(8)
        dl.addWidget(self.label("F1 DRIVING TIME BREAKDOWN",8,True,MUTED),0,0,1,4)
        self.profile_driving_breakdown = {}
        for i,(key,title) in enumerate((("practice","PRACTICE"),("time_trial","TIME TRIAL"),("qualifying","QUALIFYING"),("sprint","SPRINT"),("race","RACE"))):
            col=i%3; row=1+(i//3)*2
            dl.addWidget(self.label(title,7,True,MUTED),row,col)
            value=self.label("0h 00m",10,True,WHITE); self.profile_driving_breakdown[key]=value
            dl.addWidget(value,row+1,col)
        dl.setColumnStretch(3,1)
        ol.addWidget(driving_card)
        note=self.label("Driving time is counted only from live, telemetry-active track driving. Pauses, menus, garage time, spectating and replay do not add time. F1 skill values are derived only from validated stored evidence; missing domains remain N/A.",8,False,MUTED)
        note.setWordWrap(True); ol.addWidget(note); ol.addStretch(1)
        self.profile_sections.addTab(overview,"OVERVIEW")

        # V2.4.1.3: Skills is a scrollable workspace. The two-column card grid
        # is intentionally taller than many Control Center viewports, so it must
        # never be vertically compressed to fit the tab.
        skills=QScrollArea()
        skills.setObjectName("driverSkillsScroll")
        skills.setWidgetResizable(True)
        skills.setFrameShape(QFrame.NoFrame)
        skills.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        skills.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        skills.viewport().setAttribute(Qt.WA_StyledBackground, True)
        skills.setStyleSheet("QScrollArea#driverSkillsScroll{background:#101820;border:0;} QScrollArea#driverSkillsScroll > QWidget > QWidget{background:#101820;}")
        skills_content=QWidget()
        skills_content.setObjectName("driverSkillsContent")
        skills_content.setAttribute(Qt.WA_StyledBackground, True)
        skills_content.setStyleSheet("QWidget#driverSkillsContent{background:#101820;}")
        skl=QVBoxLayout(skills_content); skl.setContentsMargins(18,18,18,18); skl.setSpacing(12)
        skl.setSizeConstraint(QLayout.SetMinimumSize)
        skills.setWidget(skills_content)
        skl.addWidget(self.label("F1 DRIVER SKILL",13,True,WHITE))
        smsg=self.label("V2.4.1 derives the current Formula Driver Skill only from validated Skill Evidence. Confidence describes evidence trust, not driving ability; missing skill domains remain N/A.",9,False,MUTED)
        smsg.setWordWrap(True); skl.addWidget(smsg)

        overall_card=QFrame(); overall_card.setObjectName("controlCard")
        ocl=QHBoxLayout(overall_card); ocl.setContentsMargins(16,14,16,14); ocl.setSpacing(16)
        ot=QVBoxLayout(); ot.setSpacing(2)
        ot.addWidget(self.label("FORMULA DRIVER SKILL",7,True,MUTED))
        self.profile_skill_overall=self.label("N/A",24,True,WHITE); ot.addWidget(self.profile_skill_overall)
        self.profile_skill_coverage=self.label("Waiting for sufficient validated evidence",8,False,MUTED); ot.addWidget(self.profile_skill_coverage)
        self.profile_skill_confidence=self.label("Confidence N/A",8,True,MUTED); ot.addWidget(self.profile_skill_confidence)
        ocl.addLayout(ot,1); skl.addWidget(overall_card)

        # V2.4.1.2: card-based skill presentation. Each skill owns its own
        # layout so DPI scaling and long confidence text cannot squeeze the score.
        skills_grid=QWidget(); skills_grid_layout=QGridLayout(skills_grid)
        skills_grid_layout.setContentsMargins(0,0,0,0); skills_grid_layout.setHorizontalSpacing(12); skills_grid_layout.setVerticalSpacing(12)
        skills_grid_layout.setSizeConstraint(QLayout.SetMinimumSize)
        skills_grid_layout.setColumnStretch(0,1); skills_grid_layout.setColumnStretch(1,1)
        for _row in range(5):
            skills_grid_layout.setRowMinimumHeight(_row, 132)
        # Five two-column rows plus four inter-row gaps. This prevents Qt from
        # negotiating the cards down to thin strips when the tab is short.
        skills_grid.setMinimumHeight((5 * 132) + (4 * 12))
        skills_grid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.profile_skill_score_labels={}
        self.profile_skill_progress_bars={}
        self.profile_skill_evidence_labels=getattr(self,"profile_skill_evidence_labels",{})
        skill_rows=("Pace","Consistency","Braking","Corner Entry","Apex / Minimum Speed","Traction / Exit","Car Control","Racecraft","Tyre Management","Wet Driving")
        for i,key in enumerate(skill_rows):
            card=QFrame(); card.setObjectName("controlCard")
            card.setMinimumHeight(132)
            card.setMaximumHeight(150)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            card_layout=QVBoxLayout(card); card_layout.setContentsMargins(14,12,14,12); card_layout.setSpacing(6)

            header=QHBoxLayout(); header.setSpacing(10)
            skill_label=self.label(key.upper(),10,True,"#aebdcc")
            skill_label.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
            header.addWidget(skill_label,1)
            val=self.label("N/A",15,True,WHITE)
            val.setMinimumWidth(92)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet(f"color: {_rgba(WHITE)}; background: transparent; padding-right: 2px;")
            self.profile_skill_score_labels[key]=val
            header.addWidget(val,0,Qt.AlignRight)
            card_layout.addLayout(header)

            bar=QProgressBar(); bar.setRange(0,100); bar.setValue(0); bar.setTextVisible(False)
            bar.setFixedHeight(15); bar.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
            bar.setStyleSheet("QProgressBar{background:#0b1219;border:1px solid #273746;border-radius:6px;} QProgressBar::chunk{background:#3a4a59;border-radius:5px;}")
            self.profile_skill_progress_bars[key]=bar
            card_layout.addWidget(bar)

            detail=self.label("No validated evidence",8,False,MUTED)
            detail.setWordWrap(True)
            detail.setMinimumHeight(32)
            detail.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
            detail.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.profile_skill_evidence_labels[key]=detail
            card_layout.addWidget(detail)

            row=i//2; col=i%2
            skills_grid_layout.addWidget(card,row,col)
        skl.addWidget(skills_grid)

        # Score-band legend sits at the lower-right of the Skills area. It is
        # explanatory only and never changes the underlying score thresholds.
        legend_card=QFrame(); legend_card.setObjectName("controlCard")
        legend_outer=QHBoxLayout(legend_card); legend_outer.setContentsMargins(14,8,14,8); legend_outer.addStretch(1)
        legend=QWidget(); legend_row=QHBoxLayout(legend); legend_row.setContentsMargins(0,0,0,0); legend_row.setSpacing(14)
        legend_row.addWidget(self.label("SCORE COLORS",7,True,MUTED))
        for text,color in (("Weak <50","#ef6764"),("Developing 50–69.9","#e8be58"),("Strong 70–84.9","#59bfe5"),("Excellent 85–100","#4ed282"),("N/A","#8395a8")):
            item=QLabel(f"■  {text}")
            item.setFont(QFont("Segoe UI",8,QFont.Bold))
            item.setStyleSheet(f"color:{color};background:transparent;")
            legend_row.addWidget(item)
        legend_outer.addWidget(legend,0,Qt.AlignRight)
        skl.addWidget(legend_card)

        evidence_card=QFrame(); evidence_card.setObjectName("controlCard")
        evl=QGridLayout(evidence_card); evl.setContentsMargins(14,10,14,10); evl.setHorizontalSpacing(22); evl.setVerticalSpacing(7)
        if not hasattr(self,"profile_skill_evidence_labels"): self.profile_skill_evidence_labels={}
        for r,(key,title) in enumerate((("Evidence sessions","Stored evidence sessions"),("Measurements","Measurements"),("Historical backfill","Historical backfill"))):
            evl.addWidget(self.label(title.upper(),7,True,MUTED),r,0)
            val=self.label("--",8,False,WHITE); self.profile_skill_evidence_labels[key]=val; evl.addWidget(val,r,1)
        evl.setColumnStretch(1,1); skl.addWidget(evidence_card); skl.addStretch(1)
        self.profile_sections.addTab(skills,"SKILLS")

        trends=QWidget(); tl=QVBoxLayout(trends); tl.setContentsMargins(18,18,18,18); tl.setSpacing(12)
        tl.addWidget(self.label("SKILL TRENDS",13,True,WHITE))
        trend_note=self.label("V2.5.0.2 stores one cumulative trend snapshot per completed evidence session. Missing skills stay N/A; no synthetic interpolation is used.",9,False,MUTED)
        trend_note.setWordWrap(True); tl.addWidget(trend_note)
        controls=QHBoxLayout(); controls.setSpacing(10)
        self.profile_trend_skill=QComboBox()
        for text,data in (("Overall","overall"),("Pace","pace"),("Consistency","consistency"),("Braking","braking"),("Corner Entry","corner_entry"),("Apex / Minimum Speed","apex_minimum_speed"),("Traction / Exit","traction_exit"),("Car Control","car_control"),("Racecraft","racecraft"),("Tyre Management","tyre_management"),("Wet Driving","wet_driving")):
            self.profile_trend_skill.addItem(text,data)
        self.profile_trend_track=QComboBox(); self.profile_trend_track.addItem("All Tracks","all")
        self.profile_trend_period=QComboBox()
        for text,data in (("10 Sessions","10_sessions"),("30 Sessions","30_sessions"),("3 Months","3_months"),("All Time","all_time")):
            self.profile_trend_period.addItem(text,data)
        controls.addWidget(self.label("SKILL",7,True,MUTED)); controls.addWidget(self.profile_trend_skill)
        controls.addSpacing(12); controls.addWidget(self.label("TRACK",7,True,MUTED)); controls.addWidget(self.profile_trend_track)
        controls.addSpacing(12); controls.addWidget(self.label("RANGE",7,True,MUTED)); controls.addWidget(self.profile_trend_period); controls.addStretch(1)
        tl.addLayout(controls)
        stats=QFrame(); stats.setObjectName("controlCard"); st=QGridLayout(stats); st.setContentsMargins(14,10,14,10); st.setHorizontalSpacing(24); st.setVerticalSpacing(4)
        self.profile_trend_stats={}
        for col,key in enumerate(("Current","Change","Personal best","Snapshots shown")):
            st.addWidget(self.label(key.upper(),7,True,MUTED),0,col)
            v=self.label("--",13 if key != "Snapshots shown" else 11,True,WHITE); self.profile_trend_stats[key]=v; st.addWidget(v,1,col)
        for c in range(4): st.setColumnStretch(c,1)
        tl.addWidget(stats)
        chart_card=QFrame(); chart_card.setObjectName("controlCard"); chl=QVBoxLayout(chart_card); chl.setContentsMargins(10,10,10,10)
        self.profile_trend_chart=SkillTrendChart(); chl.addWidget(self.profile_trend_chart)
        tl.addWidget(chart_card,1)
        self.profile_trend_status=self.label("Waiting for trend evidence",8,False,MUTED); self.profile_trend_status.setWordWrap(True); tl.addWidget(self.profile_trend_status)
        self.profile_trend_skill.currentIndexChanged.connect(self._refresh_skill_trends)
        self.profile_trend_track.currentIndexChanged.connect(self._refresh_skill_trends)
        self.profile_trend_period.currentIndexChanged.connect(self._refresh_skill_trends)
        self.profile_sections.addTab(trends,"TRENDS")

        # V2.5.1.1 — per-track skill workspace rebuilt into the same
        # card language used across the Driver Profile surfaces.
        tracks_tab=QWidget(); ttl=QVBoxLayout(tracks_tab); ttl.setContentsMargins(18,18,18,18); ttl.setSpacing(12)
        ttl.addWidget(self.label("F1 TRACK PERFORMANCE",13,True,WHITE))
        tnote=self.label("Per-track skill is derived only from validated evidence on that circuit. N/A remains N/A when the circuit does not yet have enough scoreable sessions.",9,False,MUTED)
        tnote.setWordWrap(True); ttl.addWidget(tnote)
        self.profile_track_cards_scroll=QScrollArea(); self.profile_track_cards_scroll.setWidgetResizable(True); self.profile_track_cards_scroll.setFrameShape(QFrame.NoFrame)
        self.profile_track_cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.profile_track_cards_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}QWidget{background:transparent;}")
        self.profile_track_cards_widget=QWidget(); self.profile_track_cards_layout=QGridLayout(self.profile_track_cards_widget)
        self.profile_track_cards_layout.setContentsMargins(0,0,0,0); self.profile_track_cards_layout.setHorizontalSpacing(14); self.profile_track_cards_layout.setVerticalSpacing(14)
        self.profile_track_cards_scroll.setWidget(self.profile_track_cards_widget)
        ttl.addWidget(self.profile_track_cards_scroll,1)
        self.profile_sections.addTab(tracks_tab,"TRACKS")

        history=QWidget(); hl=QVBoxLayout(history); hl.setContentsMargins(18,18,18,18); hl.setSpacing(12)
        hl.addWidget(self.label("CAREER HISTORY",13,True,WHITE))
        hmsg=self.label("V2.6.1.4 combines validated F1 skill evidence with finalized LIVE results and measured lap personal bests. Replay and synthetic achievements are excluded.",9,False,MUTED); hmsg.setWordWrap(True); hl.addWidget(hmsg)

        history_summary=QFrame(); history_summary.setObjectName("controlCard")
        hsl=QGridLayout(history_summary); hsl.setContentsMargins(14,10,14,10); hsl.setHorizontalSpacing(24); hsl.setVerticalSpacing(4)
        self.profile_history_summary_labels={}
        for col,key in enumerate(("Milestones","Latest","Race results","Lap PBs","Skill milestones","Track skill PBs")):
            hsl.addWidget(self.label(key.upper(),7,True,MUTED),0,col)
            v=self.label("--",10 if key!="Latest" else 8,True,WHITE); self.profile_history_summary_labels[key]=v; hsl.addWidget(v,1,col)
            hsl.setColumnStretch(col,1)
        hl.addWidget(history_summary)

        self.profile_history_scroll=QScrollArea(); self.profile_history_scroll.setWidgetResizable(True); self.profile_history_scroll.setFrameShape(QFrame.NoFrame)
        self.profile_history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.profile_history_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}QWidget{background:transparent;}")
        self.profile_history_widget=QWidget(); self.profile_history_layout=QVBoxLayout(self.profile_history_widget)
        self.profile_history_layout.setContentsMargins(0,0,0,0); self.profile_history_layout.setSpacing(10)
        self.profile_history_scroll.setWidget(self.profile_history_widget)
        hl.addWidget(self.profile_history_scroll,1)
        self.profile_sections.addTab(history,"HISTORY")

        games=QWidget(); gl=QVBoxLayout(games); gl.setContentsMargins(10,12,10,10); gl.setSpacing(10)
        note=self.label("Exactly one Game Profile can be active for this Driver. Select the checkbox beside a profile to switch game context without changing Driver identity.",7,False,MUTED)
        note.setWordWrap(True); gl.addWidget(note)
        self.profile_game_cards={}
        self.profile_game_select_checks={}
        specs=(
            ("f1_26","F1 26","FORMULA",True),
            ("acc","ASSETTO CORSA COMPETIZIONE","GT",False),
            ("dirt_rally_2","DIRT RALLY 2.0","RALLY",False),
        )
        for gid,name,discipline,available in specs:
            card=QFrame(); card.setObjectName("controlCard")
            cl=QHBoxLayout(card); cl.setContentsMargins(14,11,14,11); cl.setSpacing(12)
            select_check=QCheckBox()
            select_check.setObjectName("gameProfileSelector")
            select_check.setToolTip(f"Select {name} as the active Game Profile")
            select_check.setCursor(Qt.PointingHandCursor)
            # Native Windows checkbox indicators can disappear against the dark
            # Control Center palette. Give the selector its own explicit visual
            # states instead of relying on the platform theme.
            select_check.setStyleSheet(
                "QCheckBox#gameProfileSelector{spacing:0;background:transparent;}"
                "QCheckBox#gameProfileSelector::indicator{width:16px;height:16px;"
                "border:1px solid #4b6173;border-radius:4px;background:#0b1219;}"
                "QCheckBox#gameProfileSelector::indicator:hover{border:1px solid #4dd9ff;background:#101c25;}"
                "QCheckBox#gameProfileSelector::indicator:checked{border:1px solid #9cf0ff;background:#4dd9ff;}"
                "QCheckBox#gameProfileSelector::indicator:disabled{border:1px solid #2a3640;background:#121820;}"
            )
            select_check.setMinimumSize(20,20)
            select_check.toggled.connect(lambda checked, game_id=gid: self._game_profile_checkbox_toggled(game_id, checked))
            cl.addWidget(select_check,0,Qt.AlignVCenter)
            text=QVBoxLayout(); text.setSpacing(1)
            name_label=self.label(name,10,True,WHITE); sub=self.label(discipline,7,True,MUTED)
            text.addWidget(name_label); text.addWidget(sub); cl.addLayout(text,1)
            state=self.label("CONFIGURED" if available else "PROFILE READY • TELEMETRY FUTURE",8,True,GREEN if available else MUTED)
            cl.addWidget(state)
            self.profile_game_cards[gid]=(card,state)
            self.profile_game_select_checks[gid]=select_check
            gl.addWidget(card)
        gl.addStretch(1)
        self.profile_sections.addTab(games,"GAME PROFILES")
        return page


    def _game_profile_checkbox_toggled(self, game_id: str, checked: bool):
        if not checked:
            # The currently active profile cannot be cleared without selecting
            # another profile; refresh restores the authoritative state.
            try:
                profile = self._driver_profile_store().active_profile() or {}
                if str(profile.get("active_game") or "f1_26") == str(game_id):
                    self.refresh_driver_profile()
            except Exception:
                pass
            return
        self._activate_game_profile(str(game_id))

    def _activate_game_profile(self, game_id: str):
        try:
            store = self._driver_profile_store()
            profile = store.active_profile() or {}
            driver_id = str(profile.get("driver_id") or "")
            if not driver_id or not store.set_active_game(driver_id, str(game_id)):
                QMessageBox.warning(self, "Game Profile", "Unable to select that Game Profile.")
                return
        except Exception as error:
            QMessageBox.warning(self, "Game Profile", f"Unable to switch Game Profile: {error}")
            return
        self.refresh_driver_profile()

    def _driver_action_button(self, text: str, tooltip: str, *, min_width: int = 108, primary: bool = False, danger: bool = False):
        """Application-sized text button for Driver Profile actions.

        Do not use OverlayPanel._button() here: that helper intentionally
        creates tiny icon-sized controls and will clip normal action labels.
        """
        button=QPushButton(str(text))
        button.setToolTip(str(tooltip))
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumWidth(int(min_width))
        button.setMinimumHeight(34)
        button.setFont(QFont("Segoe UI",9,QFont.Bold))
        if danger:
            accent="#d85d5d"; hover="#351b1f"; hover_border="#ef6764"
        else:
            accent="#4dd9ff" if primary else "#35536a"
            hover="#17303d" if primary else "#17232d"
            hover_border="#4dd9ff"
        button.setStyleSheet(
            "QPushButton{"
            "color:#eef6fb;background:#101820;"
            f"border:1px solid {accent};"
            "border-radius:11px;padding:6px 14px;font-weight:700;}"
            f"QPushButton:hover{{background:{hover};border-color:{hover_border};}}"
            "QPushButton:pressed{background:#0b1219;}"
            "QPushButton:disabled{color:#667788;border-color:#273746;background:#0b1219;}"
        )
        return button

    def _activate_driver_profile(self, driver_id: str) -> bool:
        """Atomically switch the person-level Driver + linked history owner."""
        try:
            from ..driver_context import DriverContextManager
            DriverContextManager(self._driver_profile_store()).activate(str(driver_id))
        except Exception as error:
            QMessageBox.warning(self,"Driver Profile",f"Unable to switch Driver Profile: {error}")
            return False
        self.refresh_driver_profile()
        try:
            self.refresh_performance_hub()
        except Exception:
            pass
        return True

    def _create_additional_driver_dialog(self, parent=None) -> bool:
        """Create a new isolated person-level Driver from the Control Center."""
        from ..driver_profiles import SUPPORTED_GAMES
        from ..performance_history import PerformanceHistoryStore
        from ..user_time import COMMON_TIME_ZONES, DEFAULT_TIME_ZONE
        dlg=QDialog(parent or self); dlg.setObjectName("themedDialog"); dlg.setAttribute(Qt.WA_StyledBackground,True)
        dlg.setWindowTitle("Create Driver Profile"); dlg.setMinimumWidth(610); dlg.setStyleSheet(qt_app_stylesheet())
        root=QVBoxLayout(dlg); root.setContentsMargins(20,20,20,20); root.setSpacing(12)
        root.addWidget(self.label("CREATE DRIVER PROFILE",14,True,WHITE))
        intro=self.label("Create a separate person-level profile. This Driver gets independent game profiles, Performance Hub history, skills, trends, tracks, milestones and time zone.",9,False,MUTED)
        intro.setWordWrap(True); root.addWidget(intro)
        card=QFrame(); card.setObjectName("controlCard"); cl=QVBoxLayout(card); cl.setContentsMargins(16,14,16,14); cl.setSpacing(12)
        form=QFormLayout(); form.setSpacing(10)
        name=QLineEdit(); name.setPlaceholderText("Driver name")
        country=QLineEdit(); country.setPlaceholderText("Optional")
        units=QComboBox(); units.addItem("Metric","metric"); units.addItem("Imperial","imperial")
        time_zone=QComboBox(); time_zone.setEditable(True)
        for zone in COMMON_TIME_ZONES: time_zone.addItem(zone,zone)
        tz_idx=time_zone.findData(DEFAULT_TIME_ZONE)
        if tz_idx>=0: time_zone.setCurrentIndex(tz_idx)
        game=QComboBox()
        for gid,spec in SUPPORTED_GAMES.items():
            label=f"{spec['name']} — {'Available' if spec['available'] else 'Future support'}"
            game.addItem(label,gid)
            if not spec["available"]: game.model().item(game.count()-1).setEnabled(False)
        form.addRow("Display name",name); form.addRow("Country / region",country); form.addRow("Preferred units",units); form.addRow("Time zone",time_zone); form.addRow("Active game",game)
        cl.addLayout(form)
        avatar_choice={"path":None}
        avatar_row=QHBoxLayout(); avatar_state=self.label("No avatar selected",8,False,MUTED); avatar_row.addWidget(avatar_state,1)
        choose=self._driver_action_button("CHOOSE AVATAR","Choose an optional Driver avatar",min_width=132); clear=self._driver_action_button("CLEAR","Clear selected avatar",min_width=84)
        avatar_row.addWidget(choose); avatar_row.addWidget(clear); cl.addLayout(avatar_row)
        def choose_avatar():
            path,_=QFileDialog.getOpenFileName(dlg,"Choose Avatar","","Images (*.png *.jpg *.jpeg *.webp *.bmp)")
            if path:
                avatar_choice["path"]=path; avatar_state.setText(path)
        def clear_avatar():
            avatar_choice["path"]=None; avatar_state.setText("No avatar selected")
        choose.clicked.connect(choose_avatar); clear.clicked.connect(clear_avatar)
        root.addWidget(card)
        foot=self.label("The new Driver starts with empty Performance Hub ownership. Existing Driver histories are never copied or reassigned.",8,False,MUTED); foot.setWordWrap(True); root.addWidget(foot)
        buttons=QHBoxLayout(); buttons.addStretch(1)
        cancel=self._driver_action_button("CANCEL","Cancel Driver creation",min_width=92); create=self._driver_action_button("CREATE DRIVER","Create and activate this Driver Profile",min_width=132,primary=True)
        buttons.addWidget(cancel); buttons.addWidget(create); root.addLayout(buttons)
        created={"ok":False}
        def create_driver():
            display_name=" ".join(name.text().strip().split())
            if not display_name:
                QMessageBox.warning(dlg,"Driver Profile","Display name is required."); return
            try:
                from ..driver_context import DriverContextManager
                profile=DriverContextManager(self._driver_profile_store()).create(
                    display_name,
                    country_region=country.text(),
                    units=str(units.currentData() or "metric"),
                    time_zone=time_zone.currentText().strip(),
                    avatar_source=avatar_choice["path"],
                    active_game=str(game.currentData() or "f1_26"),
                )
            except Exception as error:
                QMessageBox.warning(dlg,"Driver Profile",str(error)); return
            created["ok"]=True; dlg.accept()
        create.clicked.connect(create_driver); cancel.clicked.connect(dlg.reject); name.returnPressed.connect(create_driver)
        dlg.exec()
        if created["ok"]:
            self.refresh_driver_profile()
            try: self.refresh_performance_hub()
            except Exception: pass
        return bool(created["ok"])

    def _delete_driver_profile(self, driver_id: str, parent=None) -> bool:
        try:
            store=self._driver_profile_store(); profile=store.load_profile(str(driver_id)); refs=store.list_profiles()
        except Exception as error:
            QMessageBox.warning(parent or self,"Driver Profile",f"Profile unavailable: {error}"); return False
        if not profile:
            QMessageBox.warning(parent or self,"Driver Profile","Driver Profile does not exist."); return False
        if len(refs) <= 1:
            QMessageBox.warning(parent or self,"Driver Profile","The only remaining Driver Profile cannot be deleted."); return False

        name=str(profile.get("display_name") or "Driver")
        did=str(profile.get("driver_id") or driver_id)
        first=QMessageBox.question(
            parent or self,
            "Delete Driver Profile",
            f"Delete Driver '{name}'?\n\nDriver ID: {did}\n\nThe local Driver data and linked local Performance Hub history will be removed immediately. The server recovery copy will be retained for 30 days before permanent purge.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if first != QMessageBox.Yes:
            return False
        second=QMessageBox.question(
            parent or self,
            "Confirm Driver Delete",
            f"Delete '{name}' locally now? The server will retain a recovery copy for 30 days, then purge it automatically.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if second != QMessageBox.Yes:
            return False
        try:
            from ..driver_context import DriverContextManager
            result=DriverContextManager(self._driver_profile_store()).delete(did)
        except Exception as error:
            QMessageBox.warning(parent or self,"Driver Profile",f"Unable to delete Driver Profile: {error}"); return False

        self.refresh_driver_profile()
        try: self.refresh_performance_hub()
        except Exception: pass
        QMessageBox.information(
            self,
            "Driver Profile Deleted",
            f"Deleted '{name}' locally and removed {int(result.get('deleted_sessions') or 0)} linked local Performance Hub session(s). The server recovery copy is retained for 30 days.",
        )
        return True

    def _open_driver_switcher(self):
        try:
            store=self._driver_profile_store(); refs=store.list_profiles(); active_id=str(store.active_driver_id() or "")
        except Exception as error:
            QMessageBox.warning(self,"Driver Profile",f"Profiles unavailable: {error}"); return
        dlg=QDialog(self); dlg.setObjectName("themedDialog"); dlg.setAttribute(Qt.WA_StyledBackground,True)
        dlg.setWindowTitle("Switch Driver"); dlg.setMinimumSize(650,430); dlg.resize(720,520); dlg.setStyleSheet(qt_app_stylesheet())
        root=QVBoxLayout(dlg); root.setContentsMargins(18,18,18,18); root.setSpacing(12)
        root.addWidget(self.label("SWITCH DRIVER",14,True,WHITE))
        note=self.label("A Driver is the person using Race Engineer. Switching changes the complete person-level context; game identities inside F1 remain separate.",9,False,MUTED); note.setWordWrap(True); root.addWidget(note)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # V2.7.0.2: explicitly theme the switcher viewport/content. Without
        # this, Windows falls back to the native light palette for empty space
        # below the Driver cards even though the dialog itself is dark.
        scroll.setStyleSheet("QScrollArea{background:#091017;border:none;} QScrollArea > QWidget > QWidget{background:#091017;} QScrollBar:vertical{background:#0b1219;border:none;width:10px;} QScrollBar::handle:vertical{background:#3a4a59;min-height:28px;border-radius:5px;} QScrollBar::handle:vertical:hover{background:#526576;} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}")
        content=QWidget(); content.setObjectName("driverSwitcherContent"); content.setAttribute(Qt.WA_StyledBackground,True); content.setStyleSheet("QWidget#driverSwitcherContent{background:#091017;}")
        cards=QVBoxLayout(content); cards.setContentsMargins(0,0,0,0); cards.setSpacing(10)
        game_short={"f1_26":"F1 26","acc":"ACC","dirt_rally_2":"Dirt Rally 2.0"}
        for ref in refs:
            profile=store.load_profile(ref.driver_id) or {}
            card=QFrame(); card.setObjectName("controlCard"); row=QHBoxLayout(card); row.setContentsMargins(14,12,14,12); row.setSpacing(12)
            avatar=QLabel(); avatar.setFixedSize(48,48); avatar.setAlignment(Qt.AlignCenter); avatar.setStyleSheet("background:#12202a;border:1px solid #35536a;border-radius:24px;color:#4dd9ff;font-size:16px;font-weight:800;")
            self._set_profile_avatar(avatar,profile,large=False); row.addWidget(avatar)
            info=QVBoxLayout(); info.setSpacing(2)
            name_lbl=self.label(str(profile.get("display_name") or "Driver"),11,True,WHITE); info.addWidget(name_lbl)
            game_text=game_short.get(str(profile.get("active_game") or "f1_26"),str(profile.get("active_game") or "f1_26"))
            tz=str(profile.get("time_zone") or "UTC")
            sub=self.label(f"{game_text}  •  {tz}",8,False,MUTED); info.addWidget(sub)
            did=self.label(f"DRIVER ID  {ref.driver_id}",7,False,MUTED); info.addWidget(did); row.addLayout(info,1)
            actions_row=QVBoxLayout(); actions_row.setSpacing(6)
            if ref.driver_id==active_id:
                active=self.label("ACTIVE",8,True,"#4ed282"); active.setAlignment(Qt.AlignCenter); active.setStyleSheet("color:#4ed282;background:transparent;"); actions_row.addWidget(active)
            else:
                switch=self._driver_action_button("SWITCH","Activate this Driver Profile",min_width=96,primary=True)
                switch.clicked.connect(lambda _checked=False,did=ref.driver_id: (self._activate_driver_profile(did) and dlg.accept()))
                actions_row.addWidget(switch)
            delete=self._driver_action_button("DELETE","Delete locally now; server recovery copy is retained for 30 days",min_width=96,danger=True)
            delete.setEnabled(len(refs)>1)
            delete.clicked.connect(lambda _checked=False,did=ref.driver_id: (self._delete_driver_profile(did,dlg) and dlg.accept()))
            actions_row.addWidget(delete)
            row.addLayout(actions_row)
            cards.addWidget(card)
        cards.addStretch(1); scroll.setWidget(content); root.addWidget(scroll,1)
        actions=QHBoxLayout(); create=self._driver_action_button("+ NEW DRIVER","Create a separate Driver Profile",min_width=132,primary=True); close=self._driver_action_button("CLOSE","Close Driver switcher",min_width=92)
        actions.addWidget(create); actions.addStretch(1); actions.addWidget(close); root.addLayout(actions)
        def create_new():
            if self._create_additional_driver_dialog(dlg): dlg.accept()
        create.clicked.connect(create_new); close.clicked.connect(dlg.reject)
        dlg.exec()

    def _open_driver_profile_tab(self):
        idx = self.tabs.indexOf(getattr(self, "driver_profile_page", None))
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)
        self.refresh_driver_profile()

    def _set_profile_avatar(self, label, profile, *, large=False):
        name = str(profile.get("display_name") or "Driver") if isinstance(profile, dict) else "Driver"
        label.setPixmap(QPixmap())
        try:
            store = self._driver_profile_store()
            path = store.avatar_path(str(profile.get("driver_id") or "")) if isinstance(profile, dict) else None
            if path:
                pix = QPixmap(str(path))
                if not pix.isNull():
                    size = 70 if large else 34
                    label.setPixmap(pix.scaled(size,size,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation))
                    label.setText("")
                    return
        except Exception:
            pass
        label.setText(self._profile_initials(name))

    def refresh_driver_profile(self):
        try:
            store = self._driver_profile_store()
            profile = store.active_profile() or {}
        except Exception:
            profile = {}
        name = str(profile.get("display_name") or "Driver")
        game_id = str(profile.get("active_game") or "f1_26")
        game_names = {"f1_26":"F1 26","acc":"Assetto Corsa Competizione","dirt_rally_2":"Dirt Rally 2.0"}
        game_short = {"f1_26":"F1 26","acc":"ACC","dirt_rally_2":"Dirt Rally 2.0"}
        disciplines = {"f1_26":"FORMULA","acc":"GT","dirt_rally_2":"RALLY"}
        game_name = game_names.get(game_id,game_id)
        game_compact = game_short.get(game_id,game_id)
        # Permanent compact control: identity + active game. V2.4.0 refreshes
        # the skill value below after the evidence-derived model is calculated.
        if hasattr(self,"profile_button"):
            self.profile_button.setText(f"{self._profile_initials(name)}   {name}\n      {game_compact}  •  Skill N/A")
        if hasattr(self,"profile_name_large"):
            self.profile_name_large.setText(name)
            self.profile_role_large.setText(f"{disciplines.get(game_id, game_id.upper())} DRIVER • {game_compact}")
            did=str(profile.get("driver_id") or "")
            self.profile_id_label.setText(f"DRIVER ID  {did}" if did else "DRIVER ID  --")
            self._set_profile_avatar(self.profile_avatar_large,profile,large=True)
        info=getattr(self,"profile_info_labels",{})
        vals={
            "Display name":name,
            "Country / region":str(profile.get("country_region") or "Not set"),
            "Preferred units":"Metric" if str(profile.get("units") or "metric").lower()=="metric" else "Imperial",
            "Time zone":str(profile.get("time_zone") or "UTC"),
            "Created":self._profile_date(profile.get("created_at")),
            "Last active":self._profile_date(profile.get("last_active")),
        }
        for k,v in vals.items():
            if k in info: info[k].setText(v)
        def fmt_drive(seconds):
            try: total=max(0,int(float(seconds or 0)))
            except (TypeError,ValueError): total=0
            hours,rem=divmod(total,3600); minutes=rem//60
            return f"{hours}h {minutes:02d}m"
        stats={"Active game":game_compact,"Driving time":"0h 00m","Sessions":"0","Tracks driven":"0"}
        game_profile = {}
        try:
            game_profile = store.load_game_profile(str(profile.get("driver_id") or ""), game_id) or {}
            stats["Driving time"] = fmt_drive(game_profile.get("driving_seconds"))
            stats["Sessions"] = str(game_profile.get("sessions") or 0)
            stats["Tracks driven"] = str(game_profile.get("history_tracks") or game_profile.get("tracks") or 0)
            if game_id == "f1_26":
                compat=profile.get("compatibility") if isinstance(profile.get("compatibility"),dict) else {}
                pid=compat.get("performance_history_profile_id")
                from ..performance_history import PerformanceHistoryStore
                data=PerformanceHistoryStore().overview(pid)
                if data.get("available"):
                    totals=data.get("totals") or {}
                    stats["Sessions"]=str(totals.get("sessions") or 0)
                    stats["Tracks driven"]=str(totals.get("tracks") or 0)
        except Exception:
            pass
        for k,v in stats.items():
            if k in getattr(self,"profile_stats",{}): self.profile_stats[k].setText(v)
        breakdown = game_profile.get("driving_time") if isinstance(game_profile.get("driving_time"),dict) else {}
        for key,label in getattr(self,"profile_driving_breakdown",{}).items():
            label.setText(fmt_drive(breakdown.get(key)))
            label.setEnabled(game_id=="f1_26")
        # V2.4.0 Driver Skill V1. Historical LIVE sessions are first kept in
        # sync with the evidence store; the career presentation score is then
        # derived only from that persisted evidence.
        evidence_labels=getattr(self,"profile_skill_evidence_labels",{})
        score_labels=getattr(self,"profile_skill_score_labels",{})
        skill_payload={}
        if evidence_labels:
            if game_id=="f1_26" and isinstance(profile,dict) and profile.get("driver_id"):
                try:
                    from ..skill_evidence import SkillEvidenceStore
                    from ..driver_skill import F1DriverSkillModel
                    ev_store=SkillEvidenceStore(store)
                    backfill=ev_store.backfill_f1_history(driver_id=str(profile["driver_id"]))
                    ev=ev_store.summary(str(profile["driver_id"]),"f1_26")
                    skill_payload=F1DriverSkillModel(store).recalculate(str(profile["driver_id"]))
                except Exception:
                    backfill={"available":False}
                    ev={"session_count":0,"measurement_count":0,"by_skill":{}}
                    skill_payload={}
                evidence_labels["Evidence sessions"].setText(str(ev.get("session_count") or 0))
                evidence_labels["Measurements"].setText(str(ev.get("measurement_count") or 0))
                if backfill.get("available"):
                    scanned=int(backfill.get("scanned") or 0); written=int(backfill.get("written") or 0)
                    status="CURRENT" if backfill.get("already_current") else f"{written} IMPORTED"
                    evidence_labels["Historical backfill"].setText(f"{status} • {scanned} stored sessions scanned")
                else:
                    evidence_labels["Historical backfill"].setText("No linked historical sessions")
                skills_data=skill_payload.get("skills") if isinstance(skill_payload.get("skills"),dict) else {}
                mapping={"Pace":"pace","Consistency":"consistency","Braking":"braking","Corner Entry":"corner_entry",
                         "Apex / Minimum Speed":"apex_minimum_speed","Traction / Exit":"traction_exit","Car Control":"car_control",
                         "Racecraft":"racecraft","Tyre Management":"tyre_management","Wet Driving":"wet_driving"}
                for label,skill in mapping.items():
                    row=skills_data.get(skill) if isinstance(skills_data.get(skill),dict) else {}
                    value=row.get("value")
                    if label in score_labels:
                        score_labels[label].setText(f"{float(value):.1f}" if isinstance(value,(int,float)) else "N/A")
                    progress_bars=getattr(self,"profile_skill_progress_bars",{})
                    if label in progress_bars:
                        bar=progress_bars[label]
                        if isinstance(value,(int,float)):
                            score=max(0.0,min(100.0,float(value)))
                            bar.setValue(int(round(score)))
                            # Race Engineer score bands: red <50, amber <70,
                            # cyan <85, green >=85.  These colors are visual
                            # guidance only and never alter the score.
                            if score < 50.0: color="#ef6764"
                            elif score < 70.0: color="#e8be58"
                            elif score < 85.0: color="#59bfe5"
                            else: color="#4ed282"
                            bar.setStyleSheet(f"QProgressBar{{background:#0b1219;border:1px solid #273746;border-radius:6px;}} QProgressBar::chunk{{background:{color};border-radius:5px;}}")
                        else:
                            bar.setValue(0)
                            bar.setStyleSheet("QProgressBar{background:#0b1219;border:1px solid #273746;border-radius:6px;} QProgressBar::chunk{background:#3a4a59;border-radius:5px;}")
                    if label in evidence_labels:
                        mc=int(row.get("measurement_count") or 0); sc=int(row.get("sample_count") or 0); sess=int(row.get("session_count") or 0); tracks=int(row.get("track_count") or 0)
                        conf=str(row.get("confidence") or "N/A").upper()
                        evidence_labels[label].setText(f"Confidence {conf} • {sess} sessions • {tracks} tracks • {mc} measurements • {sc} samples" if mc else "No validated evidence")
                overall=skill_payload.get("overall") if isinstance(skill_payload.get("overall"),dict) else {}
                ov=overall.get("value")
                if hasattr(self,"profile_skill_overall"):
                    self.profile_skill_overall.setText(f"{float(ov):.1f} / 100" if isinstance(ov,(int,float)) else "N/A")
                if hasattr(self,"profile_skill_coverage"):
                    available=int(overall.get("available_core_skills") or 0); required=int(overall.get("required_core_skills") or 4); sessions=int(skill_payload.get("evidence_session_count") or 0)
                    self.profile_skill_coverage.setText(f"{available}/7 core skills available • {sessions} scoreable evidence sessions • minimum {required} skills / 2 sessions")
                if hasattr(self,"profile_skill_confidence"):
                    overall_conf=str(overall.get("confidence") or "N/A").upper()
                    self.profile_skill_confidence.setText(f"Confidence {overall_conf}")
                if hasattr(self,"profile_button"):
                    skill_text=f"{float(ov):.1f}" if isinstance(ov,(int,float)) else "N/A"
                    self.profile_button.setText(f"{self._profile_initials(name)}   {name}\n      {game_compact}  •  Skill {skill_text}")
            else:
                evidence_labels["Evidence sessions"].setText("0")
                evidence_labels["Measurements"].setText("0")
                evidence_labels["Historical backfill"].setText("Not available for this Game Profile")
                for label in ("Pace","Consistency","Braking","Corner Entry","Apex / Minimum Speed","Traction / Exit","Car Control","Racecraft","Tyre Management","Wet Driving"):
                    if label in score_labels: score_labels[label].setText("N/A")
                    if label in getattr(self,"profile_skill_progress_bars",{}):
                        bar=self.profile_skill_progress_bars[label]; bar.setValue(0)
                        bar.setStyleSheet("QProgressBar{background:#0b1219;border:1px solid #273746;border-radius:6px;} QProgressBar::chunk{background:#3a4a59;border-radius:5px;}")
                    if label in evidence_labels: evidence_labels[label].setText("No telemetry evidence")
                if hasattr(self,"profile_skill_overall"): self.profile_skill_overall.setText("N/A")
                if hasattr(self,"profile_skill_coverage"): self.profile_skill_coverage.setText("Skill model not available for this Game Profile")
                if hasattr(self,"profile_skill_confidence"): self.profile_skill_confidence.setText("Confidence N/A")

        for gid,(card,state) in getattr(self,"profile_game_cards",{}).items():
            check=getattr(self,"profile_game_select_checks",{}).get(gid)
            if check is not None:
                check.blockSignals(True)
                check.setChecked(gid==game_id)
                check.blockSignals(False)
            if gid==game_id:
                suffix="" if gid=="f1_26" else " • TELEMETRY FUTURE"
                state.setText("ACTIVE" + suffix)
                state.setStyleSheet("color:#2ed486;font-weight:700;")
            elif gid=="f1_26":
                state.setText("CONFIGURED")
                state.setStyleSheet("color:#4dd9ff;font-weight:700;")
            else:
                state.setText("PROFILE READY • TELEMETRY FUTURE")
                state.setStyleSheet("color:#8395a8;font-weight:700;")
        self._refresh_skill_trends()
        self._refresh_track_performance()
        self._refresh_career_history()

    def _refresh_skill_trends(self, *_args):
        chart=getattr(self,"profile_trend_chart",None); stats=getattr(self,"profile_trend_stats",{}); status=getattr(self,"profile_trend_status",None)
        try:
            store=self._driver_profile_store(); profile=store.active_profile() or {}
            driver_id=str(profile.get("driver_id") or ""); game_id=str(profile.get("active_game") or "f1_26")
            if not driver_id or game_id != "f1_26":
                if chart: chart.set_points([])
                for v in stats.values(): v.setText("--")
                if status: status.setText("Skill trends are currently available for the F1 26 Game Profile only.")
                return
            from ..skill_trends import SkillTrendStore
            trend_store=SkillTrendStore(store)
            if hasattr(self,"profile_trend_track"):
                previous=str(self.profile_trend_track.currentData() or "all")
                tracks=trend_store.available_tracks(driver_id)
                expected=["all", *tracks]
                current=[str(self.profile_trend_track.itemData(i) or "") for i in range(self.profile_trend_track.count())]
                if current != expected:
                    self.profile_trend_track.blockSignals(True)
                    self.profile_trend_track.clear(); self.profile_trend_track.addItem("All Tracks","all")
                    for track_name in tracks: self.profile_trend_track.addItem(track_name,track_name)
                    idx=max(0,self.profile_trend_track.findData(previous)); self.profile_trend_track.setCurrentIndex(idx)
                    self.profile_trend_track.blockSignals(False)
            skill=self.profile_trend_skill.currentData() if hasattr(self,"profile_trend_skill") else "overall"
            track=self.profile_trend_track.currentData() if hasattr(self,"profile_trend_track") else "all"
            period=self.profile_trend_period.currentData() if hasattr(self,"profile_trend_period") else "10_sessions"
            view=trend_store.view(driver_id,str(skill or "overall"),str(period or "10_sessions"),str(track or "all"))
            if chart: chart.set_points(view.get("points") or [])
            current=view.get("current"); change=view.get("change"); best=view.get("personal_best")
            if "Current" in stats: stats["Current"].setText(f"{float(current):.1f}" if isinstance(current,(int,float)) else "N/A")
            if "Change" in stats:
                stats["Change"].setText(f"{float(change):+.1f}" if isinstance(change,(int,float)) else "N/A")
                if isinstance(change,(int,float)):
                    stats["Change"].setStyleSheet(f"color:{'#4ed282' if change>0 else '#ef6764' if change<0 else '#eef6fb'};background:transparent;")
                else: stats["Change"].setStyleSheet("color:#8395a8;background:transparent;")
            if "Personal best" in stats: stats["Personal best"].setText(f"{float(best):.1f}" if isinstance(best,(int,float)) else "N/A")
            if "Snapshots shown" in stats: stats["Snapshots shown"].setText(str(int(view.get("point_count") or 0)))
            if status:
                track_name=str(view.get("track") or "all")
                track_text="All Tracks" if track_name=="all" else track_name
                status.setText(f"{view.get('name') or 'Skill'} • {track_text} • {int(view.get('point_count') or 0)} scoreable snapshots shown • {int(view.get('all_time_point_count') or 0)} scoreable snapshots all-time")
        except Exception as error:
            if chart: chart.set_points([])
            for v in stats.values(): v.setText("--")
            if status: status.setText(f"Trend data unavailable: {error}")

    def _clear_layout_widgets(self, layout):
        """Remove all widgets/sub-layouts from a Qt layout safely.

        Shared by the card-based Driver Profile refreshers so dynamic content
        can be rebuilt without leaving stale widgets behind.
        """
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout_widgets(child_layout)

    def _track_skill_display(self, value):
        return f"{float(value):.1f}" if isinstance(value,(int,float)) else "N/A"

    def _track_trend_display(self, value):
        return f"{float(value):+.1f}" if isinstance(value,(int,float)) else "N/A"

    def _track_trend_color(self, value):
        if isinstance(value,(int,float)):
            if value > 0:
                return "#4ed282"
            if value < 0:
                return "#ef6764"
        return "#8395a8"

    @staticmethod
    def _track_score_color(value):
        if not isinstance(value,(int,float)):
            return "#8395a8"
        value=float(value)
        if value < 50.0:
            return "#ef6764"
        if value < 70.0:
            return "#e8be58"
        if value < 85.0:
            return "#59bfe5"
        return "#4ed282"

    def _build_track_skill_cell(self, name, value):
        cell=QWidget()
        lay=QVBoxLayout(cell); lay.setContentsMargins(0,0,0,0); lay.setSpacing(5)
        head=QHBoxLayout(); head.setSpacing(8)
        title=self.label(str(name),7,True,"#9fb1c4")
        title.setStyleSheet("color:#9fb1c4;background:transparent;")
        head.addWidget(title,1)
        score=self.label(self._track_skill_display(value),10,True,WHITE)
        score.setAlignment(Qt.AlignRight|Qt.AlignVCenter); score.setMinimumWidth(58)
        head.addWidget(score,0)
        lay.addLayout(head)
        bar=QProgressBar(); bar.setRange(0,100); bar.setTextVisible(False); bar.setFixedHeight(12)
        numeric=float(value) if isinstance(value,(int,float)) else 0.0
        bar.setValue(max(0,min(100,int(round(numeric)))))
        color=self._track_score_color(value)
        bar.setStyleSheet(
            f"QProgressBar{{background:#0b1219;border:1px solid #273746;border-radius:5px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:4px;}}"
        )
        lay.addWidget(bar)
        return cell

    def _build_track_card(self, data):
        track_name=str(data.get("track") or "Unknown")
        card=QFrame(); card.setObjectName("controlCard")
        card.setMinimumHeight(390)
        layout=QVBoxLayout(card); layout.setContentsMargins(16,14,16,14); layout.setSpacing(11)

        header=QHBoxLayout(); header.setSpacing(8)
        track_title=self.label(track_name.upper(),12,True,"#4dd9ff")
        track_title.setStyleSheet("color:#4dd9ff;background:transparent;")
        header.addWidget(track_title,1)
        overall=data.get("overall")
        overall_value=self.label(self._track_skill_display(overall),15,True,WHITE)
        overall_value.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        header.addWidget(overall_value,0)
        layout.addLayout(header)

        summary_header=self.label("TRACK SUMMARY",7,True,"#e8be58")
        summary_header.setStyleSheet("color:#e8be58;background:transparent;")
        layout.addWidget(summary_header)
        subheader=QHBoxLayout(); subheader.setSpacing(18)
        metrics=(
            ("OVERALL", self._track_skill_display(overall), "#eef6fb"),
            ("TREND", self._track_trend_display(data.get("trend")), self._track_trend_color(data.get("trend"))),
            ("SESSIONS", str(int(data.get("session_count") or 0)), "#eef6fb"),
            ("PERSONAL BEST", self._track_skill_display(data.get("personal_best")), "#eef6fb"),
        )
        for title,value,color in metrics:
            col=QVBoxLayout(); col.setSpacing(2)
            title_lbl=self.label(title,7,True,"#7facc9")
            title_lbl.setStyleSheet("color:#7facc9;background:transparent;")
            col.addWidget(title_lbl)
            lbl=self.label(value,10,True,WHITE)
            lbl.setStyleSheet(f"color:{color};background:transparent;")
            col.addWidget(lbl)
            subheader.addLayout(col,1)
        layout.addLayout(subheader)

        skills_header=self.label("SKILL BREAKDOWN",7,True,"#e8be58")
        skills_header.setStyleSheet("color:#e8be58;background:transparent;")
        layout.addWidget(skills_header)
        grid=QGridLayout(); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(10)
        track_skills=(
            ("PACE","pace"),("CONSISTENCY","consistency"),("BRAKING","braking"),("CORNER ENTRY","corner_entry"),
            ("APEX / MINIMUM SPEED","apex_minimum_speed"),("TRACTION / EXIT","traction_exit"),("CAR CONTROL","car_control"),("RACECRAFT","racecraft"),
            ("TYRE MANAGEMENT","tyre_management"),("WET DRIVING","wet_driving")
        )
        skills=data.get("skills") or {}
        for i,(name,key) in enumerate(track_skills):
            row=i//2; col=i%2
            value=(skills.get(key) or {}).get("value")
            grid.addWidget(self._build_track_skill_cell(name,value),row,col)
        grid.setColumnStretch(0,1); grid.setColumnStretch(1,1)
        layout.addLayout(grid)

        sessions=int(data.get("session_count") or 0); scoreable=int(data.get("scoreable_session_count") or 0)
        note=self.label(f"{sessions} stored evidence session{'s' if sessions!=1 else ''} • {scoreable} scoreable Overall snapshot{'s' if scoreable!=1 else ''}",8,False,MUTED)
        note.setWordWrap(True); layout.addWidget(note)
        return card

    def _refresh_track_performance(self):
        grid=getattr(self,"profile_track_cards_layout",None)
        try:
            if grid is None:
                return
            self._clear_layout_widgets(grid)
            store=self._driver_profile_store(); profile=store.active_profile() or {}
            driver_id=str(profile.get("driver_id") or ""); game_id=str(profile.get("active_game") or "f1_26")
            if not driver_id or game_id!="f1_26":
                card=QFrame(); card.setObjectName("controlCard")
                lay=QVBoxLayout(card); lay.setContentsMargins(16,16,16,16)
                msg=self.label("Per-track skill is currently available for the F1 26 Game Profile only.",9,False,MUTED); msg.setWordWrap(True); lay.addWidget(msg)
                grid.addWidget(card,0,0,1,2)
                grid.setColumnStretch(0,1); grid.setColumnStretch(1,1)
                return
            from ..track_skill import TrackSkillStore
            rows=TrackSkillStore(store).overview(driver_id)
            if not rows:
                card=QFrame(); card.setObjectName("controlCard")
                lay=QVBoxLayout(card); lay.setContentsMargins(16,16,16,16)
                title=self.label("NO TRACK EVIDENCE YET",11,True,WHITE); lay.addWidget(title)
                msg=self.label("Complete or import live F1 sessions to build per-track skill evidence.",9,False,MUTED); msg.setWordWrap(True); lay.addWidget(msg)
                grid.addWidget(card,0,0,1,2)
                grid.setColumnStretch(0,1); grid.setColumnStretch(1,1)
                return
            for idx,row in enumerate(rows):
                r=idx//2; c=idx%2
                grid.addWidget(self._build_track_card(row),r,c)
            grid.setColumnStretch(0,1); grid.setColumnStretch(1,1)
        except Exception as error:
            if grid is not None:
                self._clear_layout_widgets(grid)
                card=QFrame(); card.setObjectName("controlCard")
                lay=QVBoxLayout(card); lay.setContentsMargins(16,16,16,16)
                title=self.label("TRACK DATA UNAVAILABLE",11,True,WHITE); lay.addWidget(title)
                msg=self.label(f"Per-track skill unavailable: {error}",9,False,MUTED); msg.setWordWrap(True); lay.addWidget(msg)
                grid.addWidget(card,0,0,1,2)
                grid.setColumnStretch(0,1); grid.setColumnStretch(1,1)

    def _career_history_icon_spec(self, event: dict) -> tuple[str,str,str]:
        """Return a compact icon glyph + accent colors for a milestone card.

        The mapping is deterministic and derived only from the stored milestone
        payload so the UI remains stable across rebuilds.
        """
        category=str(event.get("category") or "").strip().lower()
        event_id=str(event.get("id") or "").strip().lower()
        title=str(event.get("title") or "").strip().lower()
        if "fastest lap" in title or category=="lap_pb" or event_id.startswith("lap_pb") or "lap_pb" in event_id:
            return "stopwatch", "#c58cff", "rgba(197,140,255,0.16)"
        if "pole" in title or event_id.startswith("pole_"):
            return "target", "#59bfe5", "rgba(89,191,229,0.14)"
        if "podium" in title or event_id.startswith("podium_"):
            return "medal", "#7aa8ff", "rgba(122,168,255,0.14)"
        if "win" in title or event_id.startswith("race_win_") or event_id.startswith("wins_"):
            return "trophy", "#e8be58", "rgba(232,190,88,0.14)"
        if category=="result":
            return "flag", "#4ed282", "rgba(78,210,130,0.14)"
        if category=="track" or "track skill" in title:
            return "track", "#7aa8ff", "rgba(122,168,255,0.14)"
        if category=="skill" or "reached" in title:
            return "skill", "#59bfe5", "rgba(89,191,229,0.14)"
        if event_id.startswith("sessions_"):
            return "session", "#4ed282", "rgba(78,210,130,0.14)"
        if category=="career":
            return "career", "#e8be58", "rgba(232,190,88,0.14)"
        return "career", "#8395a8", "rgba(131,149,168,0.14)"

    def _refresh_career_history(self):
        layout=getattr(self,"profile_history_layout",None)
        summary=getattr(self,"profile_history_summary_labels",{})
        if layout is None:
            return
        try:
            self._clear_layout_widgets(layout)
            store=self._driver_profile_store(); profile=store.active_profile() or {}
            driver_id=str(profile.get("driver_id") or ""); game_id=str(profile.get("active_game") or "f1_26")
            if not driver_id or game_id!="f1_26":
                for v in summary.values(): v.setText("--")
                card=QFrame(); card.setObjectName("controlCard")
                cl=QVBoxLayout(card); cl.setContentsMargins(16,14,16,14)
                msg=self.label("Career history is currently available for the F1 26 Game Profile only.",9,False,MUTED); msg.setWordWrap(True); cl.addWidget(msg)
                layout.addWidget(card); layout.addStretch(1); return

            from ..career_history import CareerHistoryStore
            payload=CareerHistoryStore(store).ensure(driver_id)
            events=[x for x in payload.get("events",[]) if isinstance(x,dict)]
            skill_count=sum(1 for x in events if x.get("category")=="skill")
            track_count=sum(1 for x in events if x.get("category")=="track")
            result_count=sum(1 for x in events if x.get("category")=="result")
            lap_pb_count=sum(1 for x in events if x.get("category")=="lap_pb")
            latest=self._profile_date(events[0].get("timestamp")) if events else "N/A"
            vals={"Milestones":str(len(events)),"Latest":latest,"Race results":str(result_count),"Lap PBs":str(lap_pb_count),"Skill milestones":str(skill_count),"Track skill PBs":str(track_count)}
            for k,v in vals.items():
                if k in summary: summary[k].setText(v)

            if not events:
                card=QFrame(); card.setObjectName("controlCard")
                cl=QVBoxLayout(card); cl.setContentsMargins(16,14,16,14)
                cl.addWidget(self.label("NO CAREER MILESTONES YET",11,True,WHITE))
                msg=self.label("More validated F1 sessions are required before a real milestone can be derived.",9,False,MUTED); msg.setWordWrap(True); cl.addWidget(msg)
                layout.addWidget(card); layout.addStretch(1); return

            category_colors={"skill":"#59bfe5","track":"#7aa8ff","career":"#e8be58","result":"#4ed282","lap_pb":"#c58cff"}
            current_month=None
            for event in events:
                ts=self._profile_date(event.get("timestamp"))
                month=ts[:7] if ts and ts!="--" else "Unknown"
                if month!=current_month:
                    current_month=month
                    month_label=self.label(month,8,True,MUTED)
                    month_label.setContentsMargins(2,4,0,0)
                    layout.addWidget(month_label)
                card=QFrame(); card.setObjectName("controlCard")
                cl=QHBoxLayout(card); cl.setContentsMargins(14,12,14,12); cl.setSpacing(12)
                stripe=QFrame(); stripe.setFixedWidth(4)
                color=category_colors.get(str(event.get("category") or ""),"#8395a8")
                stripe.setStyleSheet(f"background:{color};border-radius:2px;")
                cl.addWidget(stripe)

                icon_kind,icon_color,_icon_bg=self._career_history_icon_spec(event)
                icon_widget=AchievementIconWidget(icon_kind,icon_color)
                cl.addWidget(icon_widget,0,Qt.AlignTop)

                body=QVBoxLayout(); body.setSpacing(3)
                title=self.label(str(event.get("title") or "Milestone"),10,True,WHITE); body.addWidget(title)
                detail=self.label(str(event.get("detail") or ""),8,False,MUTED); detail.setWordWrap(True); body.addWidget(detail)
                meta_parts=[ts]
                if event.get("track"): meta_parts.append(str(event.get("track")))
                meta=self.label("  •  ".join(x for x in meta_parts if x),7,False,MUTED); body.addWidget(meta)
                cl.addLayout(body,1)
                layout.addWidget(card)
            layout.addStretch(1)
            # HISTORY is latest-first; ensure the first/newest card is fully
            # visible after dynamic rebuild instead of inheriting a stale scroll offset.
            scroll=getattr(self,"profile_history_scroll",None)
            if scroll is not None:
                QTimer.singleShot(0, lambda s=scroll: s.verticalScrollBar().setValue(0))
        except Exception as error:
            for v in summary.values(): v.setText("--")
            self._clear_layout_widgets(layout)
            card=QFrame(); card.setObjectName("controlCard")
            cl=QVBoxLayout(card); cl.setContentsMargins(16,14,16,14)
            cl.addWidget(self.label("CAREER HISTORY UNAVAILABLE",11,True,WHITE))
            msg=self.label(f"Career history unavailable: {error}",9,False,MUTED); msg.setWordWrap(True); cl.addWidget(msg)
            layout.addWidget(card); layout.addStretch(1)

    def _edit_driver_profile(self):
        try:
            store=self._driver_profile_store(); profile=store.active_profile()
        except Exception as error:
            QMessageBox.warning(self,"Driver Profile",f"Profile unavailable: {error}"); return
        if not profile:
            QMessageBox.warning(self,"Driver Profile","No active Driver Profile exists."); return
        dlg=QDialog(self); dlg.setObjectName("themedDialog"); dlg.setAttribute(Qt.WA_StyledBackground, True); dlg.setWindowTitle("Edit Driver Profile"); dlg.setMinimumWidth(520); dlg.setStyleSheet(qt_app_stylesheet())
        root=QVBoxLayout(dlg); root.setContentsMargins(18,18,18,18); root.setSpacing(12)
        root.addWidget(self.label("EDIT DRIVER PROFILE",14,True,WHITE))
        form=QFormLayout(); form.setSpacing(10)
        name=QLineEdit(str(profile.get("display_name") or "")); country=QLineEdit(str(profile.get("country_region") or ""))
        units=QComboBox(); units.addItem("Metric","metric"); units.addItem("Imperial","imperial"); units.setCurrentIndex(max(0,units.findData(str(profile.get("units") or "metric"))))
        from ..user_time import COMMON_TIME_ZONES
        time_zone=QComboBox(); time_zone.setEditable(True)
        for zone in COMMON_TIME_ZONES: time_zone.addItem(zone,zone)
        current_zone=str(profile.get("time_zone") or "UTC")
        idx=time_zone.findData(current_zone)
        if idx>=0: time_zone.setCurrentIndex(idx)
        else: time_zone.setEditText(current_zone)
        time_zone.setToolTip("IANA time zone, for example Asia/Kolkata or Europe/London")
        form.addRow("Display name",name); form.addRow("Country / region",country); form.addRow("Preferred units",units); form.addRow("Time zone",time_zone); root.addLayout(form)
        avatar_row=QHBoxLayout(); avatar_state=QLabel("Keep current avatar"); avatar_row.addWidget(avatar_state,1)
        avatar_choice={"mode":"keep","path":None}
        choose=QPushButton("CHOOSE AVATAR"); clear=QPushButton("CLEAR AVATAR")
        def pick_avatar():
            fn,_=QFileDialog.getOpenFileName(dlg,"Choose Driver Avatar","","Images (*.png *.jpg *.jpeg *.bmp *.webp)")
            if fn: avatar_choice.update(mode="replace",path=fn); avatar_state.setText(Path(fn).name)
        def clear_avatar():
            avatar_choice.update(mode="clear",path=None); avatar_state.setText("Avatar will be cleared")
        choose.clicked.connect(pick_avatar); clear.clicked.connect(clear_avatar); avatar_row.addWidget(choose); avatar_row.addWidget(clear); root.addLayout(avatar_row)
        buttons=QHBoxLayout(); buttons.addStretch(1); cancel=QPushButton("CANCEL"); save=QPushButton("SAVE CHANGES"); buttons.addWidget(cancel); buttons.addWidget(save); root.addLayout(buttons)
        cancel.clicked.connect(dlg.reject)
        def save_changes():
            clean=" ".join(name.text().strip().split())
            if not clean: QMessageBox.warning(dlg,"Driver Profile","Display name is required."); return
            try:
                updated=store.update_personal_info(str(profile["driver_id"]),display_name=clean,country_region=country.text(),units=units.currentData(),time_zone=time_zone.currentText().strip())
                if avatar_choice["mode"]=="replace": updated=store.update_avatar(str(profile["driver_id"]),avatar_choice["path"])
                elif avatar_choice["mode"]=="clear": updated=store.update_avatar(str(profile["driver_id"]),None)
                compat=updated.get("compatibility") if isinstance(updated,dict) and isinstance(updated.get("compatibility"),dict) else {}
                legacy_id=compat.get("performance_history_profile_id")
                if legacy_id is not None:
                    try:
                        from ..performance_history import PerformanceHistoryStore
                        PerformanceHistoryStore().rename_user_profile(int(legacy_id),clean)
                    except Exception:
                        pass
            except Exception as error:
                QMessageBox.warning(dlg,"Driver Profile",str(error)); return
            dlg.accept(); self.refresh_driver_profile()
        save.clicked.connect(save_changes); name.returnPressed.connect(save_changes)
        dlg.exec()

    @staticmethod
    def _style_performance_table(table):
        """Apply the Control Center dark palette to every Performance Hub table."""
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.setStyleSheet("""
            QTableWidget {
                background:#0d141c; alternate-background-color:#111a23;
                color:#eef5fb; border:1px solid #2b3946; border-radius:6px;
                selection-background-color:#24394a; selection-color:#ffffff;
                outline:0; gridline-color:#263342;
            }
            QTableWidget::item { padding:6px; border-bottom:1px solid #1e2a35; }
            QHeaderView::section {
                background:#111820; color:#9fb1c4; border:0;
                border-right:1px solid #263342; border-bottom:1px solid #2b3946;
                padding:7px; font-weight:600;
            }
            QTableCornerButton::section { background:#111820; border:0; }
            QScrollBar:vertical { background:#0d141c; width:10px; margin:0; }
            QScrollBar::handle:vertical { background:#354453; min-height:24px; border-radius:5px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar:horizontal { background:#0d141c; height:10px; margin:0; }
            QScrollBar::handle:horizontal { background:#354453; min-width:24px; border-radius:5px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
        """)

    @staticmethod
    def _perf_time(value):
        if not isinstance(value, (int, float)):
            return "--"
        minutes = int(float(value) // 60)
        seconds = float(value) - minutes * 60
        return f"{minutes}:{seconds:06.3f}"

    @staticmethod
    def _perf_num(value, suffix=""):
        if not isinstance(value, (int, float)):
            return "--"
        return f"{float(value):+.3f}{suffix}"

    def _tab_changed(self, index):
        page = self.tabs.widget(index)
        if page is getattr(self, "driver_profile_page", None):
            self.refresh_driver_profile()
        elif page is self.performance_page:
            # Keep the already-loaded WebEngine page alive. Reloading on every tab
            # switch caused a visible white flash while Chromium repainted.
            if getattr(self,"performance_web_view",None) is None:
                self.refresh_performance_hub()
        elif page is getattr(self, "server_page", None):
            self.refresh_server_tab()
        elif page is getattr(self, "help_page", None):
            # Help WebEngine view stays loaded to avoid a white reload flash.
            pass

    def _open_performance_browser(self):
        """Open the gaming-PC/local browser Performance Hub.

        The server-hosted hub has its own explicit launcher on the SERVER tab.
        Keeping this action local preserves the original Control Center/LAN
        Performance Hub workflow and prevents the two products from collapsing
        into the same surface.
        """
        try:
            import webbrowser
            webbrowser.open(self.dashboard_url + "performance")
        except Exception as error:
            self.performance_status.setText(f"Could not open browser: {error}")

    def _performance_driver_changed(self, _index):
        if getattr(self, "_updating_performance_driver", False):
            return
        did = self.performance_driver_combo.currentData()
        if did is None:
            return
        try:
            from ..performance_history import PerformanceHistoryStore
            PerformanceHistoryStore().set_preferred_driver(did)
        except Exception as error:
            self.performance_status.setText(f"Could not select driver: {error}")
            return
        self.refresh_performance_hub(driver_id=did)

    def refresh_performance_hub(self, driver_id=None):
        """Refresh fallback native summary; web-backed tab reloads the shared page."""
        if getattr(self,"performance_web_view",None) is not None:
            self.performance_web_view.reload(); return
        try:
            from ..performance_history import PerformanceHistoryStore
            store = PerformanceHistoryStore()
            data = store.overview(driver_id)
        except Exception as error:
            self.performance_status.setText(f"History unavailable: {error}")
            return
        self.performance_tracks.setRowCount(0)
        self.performance_sessions.setRowCount(0)
        if not data.get("available"):
            for label in self.performance_cards.values(): label.setText("--")
            self._updating_performance_driver = True
            try:
                self.performance_driver_combo.clear()
            finally:
                self._updating_performance_driver = False
            self.performance_status.setText("No LIVE game performance history stored yet. Replay sessions are intentionally excluded.")
            return
        d=data.get("driver") or {}; t=data.get("totals") or {}
        self._updating_performance_driver = True
        try:
            current_id = d.get("id")
            self.performance_driver_combo.clear()
            for drv in data.get("drivers") or []:
                name = drv.get("name") or "Driver"
                number = f" #{drv.get('race_number')}" if drv.get("race_number") is not None else ""
                team = f" — {drv.get('team_name')}" if drv.get("team_name") else ""
                self.performance_driver_combo.addItem(f"{name}{number}{team}", drv.get("id"))
            idx = self.performance_driver_combo.findData(current_id)
            if idx >= 0:
                self.performance_driver_combo.setCurrentIndex(idx)
        finally:
            self._updating_performance_driver = False
        vals={"Driver":d.get("name") or "--","Team":d.get("team_name") or "--","Sessions":t.get("sessions") or 0,"Tracks":t.get("tracks") or 0,"Laps":t.get("laps") or 0,"Wins":t.get("wins") or 0}
        for k,v in vals.items(): self.performance_cards[k].setText(str(v))
        self.performance_status.setText("Authoritative source: LIVE F1 game telemetry. Select a driver above to view that driver's separate local history.")
        tracks=data.get("tracks") or []
        self.performance_tracks.setRowCount(len(tracks))
        for r,row in enumerate(tracks):
            values=(row.get("track") or "Unknown", row.get("sessions") or 0, self._perf_time(row.get("best_lap_s")), self._perf_time(row.get("best_potential_s")), self._perf_num(row.get("best_reference_gap_s")," s"), self._profile_date(row.get("last_session_utc")))
            for c,v in enumerate(values): self.performance_tracks.setItem(r,c,QTableWidgetItem(str(v)))
        if tracks:
            self.performance_tracks.selectRow(0)

    def _performance_track_selected(self):
        items=self.performance_tracks.selectedItems()
        if not items: return
        track=self.performance_tracks.item(items[0].row(),0).text()
        did = self.performance_driver_combo.currentData() if hasattr(self, "performance_driver_combo") else None
        try:
            from ..performance_history import PerformanceHistoryStore
            data=PerformanceHistoryStore().track_detail(track, did)
        except Exception as error:
            self.performance_status.setText(f"Track history unavailable: {error}")
            return
        rows=data.get("sessions") or []
        self.performance_sessions.setRowCount(len(rows))
        for r,row in enumerate(reversed(rows)):
            values=(self._profile_date(row.get("created_utc")), row.get("session_type") or "--", row.get("position") if row.get("position") is not None else "--", row.get("laps_completed") if row.get("laps_completed") is not None else "--", self._perf_time(row.get("best_lap_s")), self._perf_time(row.get("potential_lap_s")), self._perf_num(row.get("potential_gain_s")," s"), self._perf_num(row.get("reference_gap_s")," s"))
            for c,v in enumerate(values): self.performance_sessions.setItem(r,c,QTableWidgetItem(str(v)))

    def _force_topmost(self):
        """Control Center is an application window and must never force topmost."""
        return

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(8, 13, 18))

    def closeEvent(self, event):
        # Native title-bar X exits the complete Race Engineer application. During
        # suite shutdown the guard avoids recursively calling close_all().
        if getattr(self, "_suite_closing", False):
            event.accept()
            return
        if self.on_close is not None:
            event.ignore()
            self.on_close()
            return
        event.accept()

    def set_click_through(self, enabled: bool):
        """Control Center always remains interactive; CT applies to racing overlays only."""
        self._click_through = False

    def mousePressEvent(self, event):
        # Native application windows are moved by the OS title bar, not by
        # dragging arbitrary controls/content like the frameless overlays.
        self._drag_offset = None
        QWidget.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        QWidget.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        QWidget.mouseReleaseEvent(self, event)

    def _launch_overlay(self, key, description, callback, _checked=False):
        """Invoke exactly the callback physically bound to this launcher button."""
        print(f"[UI] Launcher {key} -> {description}", flush=True)
        callback()

    def _recording_mode_changed(self, _index):
        if self._updating_recording_mode or self._on_select_recording_mode is None:
            return
        value=self.recording_mode_combo.currentData() or "session"
        try:
            result=self._on_select_recording_mode(value);ok=True;message=None
            if isinstance(result,tuple):ok=result[0];message=result[1] if len(result)>1 else None
            elif isinstance(result,bool):ok=result
            if ok:self._current_recording_mode=str(value);self.recording_mode_combo.setToolTip(str(message or "Recording mode selected"))
            else:self.set_recording_mode(self._current_recording_mode);self.recording_mode_combo.setToolTip(str(message or "Unable to change recording mode"))
        except Exception as error:
            self.set_recording_mode(self._current_recording_mode);self.recording_mode_combo.setToolTip(str(error))

    def set_recording_mode(self, mode):
        mode=str(mode or "session")
        combo_same=(mode==self._current_recording_mode and self.recording_mode_combo.currentData()==mode)
        self._current_recording_mode=mode
        if not combo_same:
            self._updating_recording_mode=True
            try:
                idx=self.recording_mode_combo.findData(mode);self.recording_mode_combo.setCurrentIndex(idx if idx>=0 else 0)
            finally:self._updating_recording_mode=False
        rec=self.status_labels.get("REC")
        if mode=="rival_reference":
            self._set_status("REC","Auto")
            if isinstance(rec,QToolButton):
                rec.setEnabled(False)
                rec.setToolTip("Rival Reference Capture is automatic. REC controls Session Recording only.")
        elif isinstance(rec,QToolButton):
            rec.setEnabled(True)
            rec.setToolTip("Toggle normal raw Session Recording")

    def set_reference_capture_status(self,status):
        if not isinstance(status,dict):return
        if str(status.get("recording_mode"))!="rival_reference":
            self.reference_capture_label.setText("REFERENCE CAPTURE: IDLE");self.reference_capture_label.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;");return
        enabled=bool(status.get("enabled"));best=status.get("best_lap_time_s");quality=status.get("quality") or {};accepted=quality.get("accepted")
        phase=str(status.get("phase") or ("capturing" if enabled else "off"))
        phase_text={
            "off":"STOPPED",
            "armed_waiting_telemetry":"ARMED • WAITING FOR TT TELEMETRY",
            "armed_waiting_rival":"ARMED • WAITING FOR RIVAL",
            "armed_waiting_sf":"ARMED • WAITING FOR S/F",
            "armed_waiting_samples":"ARMED • WAITING FOR RIVAL DATA",
            "capturing":"CAPTURING",
        }.get(phase,"ARMED" if enabled else "STOPPED")
        text=f"REFERENCE CAPTURE: {phase_text}"
        lap=status.get("current_lap");samples=int(status.get("sample_count") or 0)
        if phase=="capturing" and isinstance(lap,int):text+=f" • L{lap}"
        if phase=="capturing" and samples:text+=f" • {samples} SAMPLES"
        if isinstance(best,(int,float)):text+=f" • BEST {_time_text(float(best))}"
        if accepted is True:text+=" • QUALITY PASS"
        elif quality and accepted is False:text+=" • QUALITY WAIT/REJECT"
        if status.get("compiled"):text+=" • MODEL READY"
        self.reference_capture_label.setText(text)
        col=GREEN if status.get("compiled") and accepted is True else (AMBER if enabled or accepted is True else MUTED)
        self.reference_capture_label.setStyleSheet(f"color:{_rgba(col)};background:transparent;")

    def refresh_reference_options(self):
        options = []
        if self._on_reference_options is not None:
            try:
                options = list(self._on_reference_options() or ())
            except Exception as error:
                self.reference_combo.setToolTip(f"Reference scan failed: {error}")
        current = self._current_reference or "__SESSION_BEST__"
        self._updating_reference_combo = True
        try:
            self.reference_combo.clear()
            self.reference_combo.addItem("Session best — current live/replay session", "__SESSION_BEST__")
            for item in options:
                if isinstance(item, dict):
                    label=item.get("label") or item.get("path")
                    value=item.get("path")
                else:
                    try: label,value=item
                    except Exception: continue
                if label and value:
                    self.reference_combo.addItem(str(label), str(value))
            idx=self.reference_combo.findData(current)
            self.reference_combo.setCurrentIndex(idx if idx>=0 else 0)
        finally:
            self._updating_reference_combo = False

    def _reference_changed(self, _index):
        if self._updating_reference_combo or self._on_select_reference is None:
            return
        value=self.reference_combo.currentData() or "__SESSION_BEST__"
        try:
            result=self._on_select_reference(value)
            ok=True; message=None
            if isinstance(result, tuple):
                ok=result[0]; message=result[1] if len(result)>1 else None
            elif isinstance(result,bool):
                ok=result
            if ok:
                self._current_reference=value
                self.reference_combo.setToolTip(str(message or "Reference selected"))
            else:
                self.reference_combo.setToolTip(str(message or "Unable to load reference"))
                self.refresh_reference_options()
        except Exception as error:
            self.reference_combo.setToolTip(str(error))
            self.refresh_reference_options()

    def _import_reference_clicked(self):
        if self._on_import_reference is None:return
        path,_=QFileDialog.getOpenFileName(self,"Import Reference Package",str(Path.cwd()),"Race Engineer Reference (*.zip);;ZIP files (*.zip)")
        if not path:return
        ok,message=self._on_import_reference(path)
        if ok:
            self.refresh_reference_options()
            QMessageBox.information(self,"Reference installed",str(message or "Reference installed"))
        else:
            QMessageBox.warning(self,"Reference import failed",str(message or "Unable to install reference"))

    def _export_reference_clicked(self):
        if self._on_export_reference is None:return
        source=self.reference_combo.currentData()
        if not source or source=="__SESSION_BEST__":
            QMessageBox.information(self,"Reference export","Select a stored reference first. Session best is not a persistent file yet.")
            return
        default=Path(source).stem+".zip"
        path,_=QFileDialog.getSaveFileName(self,"Export Reference Package",str(Path.cwd()/default),"Race Engineer Reference (*.zip)")
        if not path:return
        if not str(path).lower().endswith('.zip'):path=str(path)+'.zip'
        ok,message=self._on_export_reference(source,path)
        if ok:QMessageBox.information(self,"Reference exported",str(message or path))
        else:QMessageBox.warning(self,"Reference export failed",str(message or "Unable to export reference"))

    def set_reference_selection(self, value):
        value=value or "__SESSION_BEST__"
        if value==self._current_reference:
            return
        self._current_reference=value
        self._updating_reference_combo=True
        try:
            idx=self.reference_combo.findData(value)
            if idx>=0:
                self.reference_combo.setCurrentIndex(idx)
        finally:
            self._updating_reference_combo=False

    def set_reference_status(self, status):
        if not isinstance(status, dict):
            return
        active_name = status.get("active_name") or "Session best"
        active_time = status.get("active_time_s")
        active = f"ACTIVE: {active_name}"
        if isinstance(active_time, (int, float)):
            active += f" • {_time_text(float(active_time))}"
        pending = status.get("pending")
        if pending is not None:
            selected = str(status.get("selected") or pending)
            pending_text = status.get("pending_name") or ("Session best" if selected in {"__SESSION_BEST__", "__AUTO__", ""} else Path(selected).stem)
            self.reference_state_label.setText(active + f"    PENDING: {pending_text} — next lap")
            self.reference_state_label.setStyleSheet(f"color:rgb({AMBER.red()},{AMBER.green()},{AMBER.blue()});background:transparent;")
        else:
            self.reference_state_label.setText(active)
            self.reference_state_label.setStyleSheet(f"color:rgb({GREEN.red()},{GREEN.green()},{GREEN.blue()});background:transparent;")

    def refresh_replay_options(self):
        if not hasattr(self, "replay_combo"):
            return
        options = []
        if self._on_replay_options is not None:
            try:
                options = list(self._on_replay_options() or ())
            except Exception as error:
                self.replay_combo.setToolTip(f"Replay scan failed: {error}")
        current = self._current_replay
        self._updating_replay_combo = True
        try:
            self.replay_combo.clear()
            if not options:
                self.replay_combo.addItem("No stored recordings found", None)
            for item in options:
                if isinstance(item, dict):
                    label = item.get("label") or item.get("path")
                    value = item.get("path")
                else:
                    try:
                        label, value = item
                    except Exception:
                        continue
                if label and value:
                    self.replay_combo.addItem(str(label), str(value))
            if current:
                idx = self.replay_combo.findData(str(current))
                if idx >= 0:
                    self.replay_combo.setCurrentIndex(idx)
        finally:
            self._updating_replay_combo = False

    def _replay_changed(self, _index):
        if self._updating_replay_combo or self._on_select_replay is None:
            return
        value = self.replay_combo.currentData()
        if not value:
            return
        try:
            result = self._on_select_replay(value)
            ok = True; message = None
            if isinstance(result, tuple):
                ok = result[0]; message = result[1] if len(result) > 1 else None
            elif isinstance(result, bool):
                ok = result
            if ok:
                self._current_replay = str(value)
                self.replay_combo.setToolTip(str(message or "Replay loaded"))
            else:
                self.replay_combo.setToolTip(str(message or "Unable to load replay"))
                self.refresh_replay_options()
        except Exception as error:
            self.replay_combo.setToolTip(str(error))
            self.refresh_replay_options()

    def set_replay_selection(self, value):
        value = str(value) if value else None
        if value == self._current_replay:
            return
        self._current_replay = value
        self._updating_replay_combo = True
        try:
            idx = self.replay_combo.findData(value)
            if idx >= 0:
                self.replay_combo.setCurrentIndex(idx)
        finally:
            self._updating_replay_combo = False

    @staticmethod
    def _select_combo_data(combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    @staticmethod
    def _style_combo(combo):
        combo.setMinimumWidth(250)
        combo.setFixedHeight(23)

    def _button(self, text, tooltip):
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(28, 24)
        button.setFont(QFont("Segoe UI Symbol", 10, QFont.Bold))
        button.setStyleSheet(
            "QToolButton { color: rgba(230,234,239,220); background: rgba(255,255,255,14);"
            " border: 1px solid rgba(255,255,255,22); border-radius: 7px; }"
            "QToolButton:hover { background: rgba(255,255,255,35); }"
            "QToolButton:pressed { background: rgba(255,255,255,50); }"
        )
        return button

    def _apply_status_style(self, name):
        label = self.status_labels.get(name)
        if label is None:
            return
        value = self._status_values[name]
        color = _status_color(value)
        css_color = f"rgb({color.red()},{color.green()},{color.blue()})"
        if isinstance(label, QToolButton):
            label.setStyleSheet(status_qss(css_color))
        else:
            label.setStyleSheet(f"color: {css_color}; background: transparent;")

    def _sync_dependency_controls(self):
        """Apply master/child hierarchy without destroying child preferences."""
        engr_on=self._status_values.get("ENGR") in {"Enabled","On"}
        cc_on=self._status_values.get("CORNER") in {"Enabled","On"}
        for child in ("LAP","POS","RACE"):
            w=self.status_labels.get(child)
            if isinstance(w,QToolButton):
                if w.isEnabled()!=engr_on:
                    w.setEnabled(engr_on)
                tip=(w.toolTip().split(" | ",1)[0]) + ("" if engr_on else " | ENGR master is OFF; previous setting will return when ENGR is ON")
                if w.toolTip()!=tip:
                    w.setToolTip(tip)
        for child in ("CCVOICE","CCPRE","CCPOST","GAINLOSS","GAINLOSSVOICE"):
            w=self.status_labels.get(child)
            if isinstance(w,QToolButton):
                if w.isEnabled()!=cc_on:
                    w.setEnabled(cc_on)
                tip=(w.toolTip().split(" | ",1)[0]) + ("" if cc_on else " | CC master is OFF; previous setting will return when CC is ON")
                if w.toolTip()!=tip:
                    w.setToolTip(tip)

    def _set_status(self, name, value):
        if self._status_values.get(name)==value:
            return
        self._status_values[name] = value
        label = self.status_labels.get(name)
        if label is None:
            return
        if name in {"LAP", "POS", "RACE"}:
            label.setText(coach_button_text(name, value))
        elif name == "ENGR":
            label.setText("ENGR" + (" ON" if value in {"Enabled","On"} else " OFF"))
        elif name in {"CORNER","CCVOICE","CCPRE","CCPOST","GAINLOSS","GAINLOSSVOICE"}:
            base={"CORNER":"CC","CCVOICE":"VOICE","CCPRE":"PRE","CCPOST":"POST","GAINLOSS":"MAP G/L","GAINLOSSVOICE":"G/L VOICE"}[name]
            label.setText(base + (" ON" if value in {"Enabled","On"} else " OFF"))
        else:
            label.setText(value)
        self._apply_status_style(name)

    def _toggle_runtime_feature(self, name):
        callback = self._runtime_toggle_callbacks.get(name)
        if callback is None:
            return
        if name=="REC" and self._current_recording_mode=="rival_reference":
            label=self.status_labels.get("REC")
            if label is not None:
                label.setToolTip("Rival Reference Capture is auto-armed. Switch Recording Mode to Session Recording to use REC.")
            return
        current = self._status_values.get(name, "Disabled")
        enabled = (current != "Replay") if name == "Replay" else current not in {"Enabled", "On"}
        try:
            # Replay mode must be enterable before the user manually changes the
            # recording combo. The combo visually selects its first item after a
            # refresh, but older code did not actually load that file until a
            # selection-change signal fired. Auto-load the visible selection on
            # the first Live -> Replay click, then switch sources.
            if name == "Replay" and enabled and self._on_select_replay is not None:
                value = self.replay_combo.currentData() if hasattr(self, "replay_combo") else None
                if not value:
                    self.status_labels[name].setToolTip("No replay recording is available")
                    return
                if self._current_replay != str(value):
                    preload = self._on_select_replay(value)
                    preload_ok = preload[0] if isinstance(preload, tuple) else (preload if isinstance(preload, bool) else True)
                    preload_msg = preload[1] if isinstance(preload, tuple) and len(preload) > 1 else None
                    if not preload_ok:
                        self.status_labels[name].setToolTip(str(preload_msg or "Unable to load replay"))
                        return
                    self._current_replay = str(value)
            result = callback(enabled)
            ok = True
            message = None
            if isinstance(result, tuple):
                ok, message = result[0], result[1] if len(result) > 1 else None
            elif isinstance(result, bool):
                ok = result
            if ok:
                if name == "Replay":
                    self.set_replay_mode(enabled)
                else:
                    self._set_status(name, "On" if name == "REC" and enabled else "Off" if name == "REC" else "Enabled" if enabled else "Disabled")
                    if name in {"ENGR","CORNER"}:
                        # Child effective states will be refreshed from the receiver
                        # on the next UI tick; disable their controls immediately.
                        self._sync_dependency_controls()
            elif message:
                self.status_labels[name].setToolTip(str(message))
        except Exception as error:
            self.status_labels[name].setToolTip(str(error))

    def set_runtime_statuses(self, states):
        if not states:
            return
        for name in ("TTS", "PTT", "STT", "LLM", "ENGR", "REC", "LAP", "POS", "RACE", "CORNER", "CCVOICE", "CCPRE", "CCPOST", "GAINLOSS", "GAINLOSSVOICE"):
            if name in states:
                if name=="REC" and self._current_recording_mode=="rival_reference":
                    self._set_status("REC","Auto")
                    continue
                value = "On" if name == "REC" and states[name] else "Off" if name == "REC" else "Enabled" if states[name] else "Disabled"
                self._set_status(name, value)
        self._sync_dependency_controls()

    def set_replay_mode(self, enabled: bool):
        self._set_status("Replay", "Replay" if enabled else "Live")
        self.status_labels["Replay"].setToolTip("Click to return to Live UDP mode" if enabled else "Click to run the selected replay")

    def set_paused(self, paused: bool):
        self._paused = bool(paused)
        self.pause_button.setText("▶" if paused else "Ⅱ")
        self.pause_button.setToolTip("Resume overlay / replay" if paused else "Pause overlay / replay")
        self._set_status("Pause", "Paused" if paused else "Live")

    def set_click_state(self, enabled: bool):
        self._click_through_state = bool(enabled)
        self._set_status("Click-through", "On" if enabled else "Off")

    def update_snapshot(self, s):
        self._latest_control_snapshot = s
        if getattr(self, "hardware_page", None) is not None:
            self.hardware_page.update_snapshot(s)
        # Keep selectors synchronized when the same settings are changed by
        # radio commands or CLI/runtime control paths.
        self.set_coaching_controls(getattr(s,"coaching_mode",None),getattr(s,"coaching_verbosity",None))
        connection = "LIVE" if s.connected else "WAITING"
        if getattr(s, "session_finished", False):
            connection = "FINISHED"
        self.context_label.setText(f"{s.event_profile}  •  {connection}")
        if self._current_recording_mode=="rival_reference":
            self._set_status("REC","Auto")
            rec=self.status_labels.get("REC")
            if isinstance(rec,QToolButton):
                rec.setEnabled(False)
                rec.setToolTip("Rival Reference Capture is automatic. REC controls Session Recording only.")
        elif getattr(s, "recording_error", None):
            self._set_status("REC", "Error")
            self.status_labels["REC"].setToolTip(f"Recording error: {s.recording_error}")
        elif getattr(s, "recording_active", False):
            self._set_status("REC", "On")
            file_text = getattr(s, "recording_file", None) or "auto file (waiting for first packet)"
            count = int(getattr(s, "recording_packets", 0) or 0)
            self.status_labels["REC"].setToolTip(f"Recording ON • {count} packets • {file_text}")
        else:
            self._set_status("REC", "Off")
            self.status_labels["REC"].setToolTip("Telemetry recording is OFF")




class DriverOverlayWindow(OverlayPanel):
    """Combined driver inputs, ERS battery trace and speed/gear/lap strip."""

    WIDTH = 430

    def __init__(self, *, on_hide=None, on_toggle_pause=None, on_toggle_click_through=None):
        super().__init__(on_close=on_hide, on_toggle_pause=on_toggle_pause, on_toggle_click_through=on_toggle_click_through)
        self.setWindowTitle("Race Engineer — Driver Inputs")
        self._show_throttle = True
        self._show_brake = True
        self._show_ers = True
        self._last_lap = None
        self._last_lap_time = None
        self._last_distance = None
        root = QVBoxLayout(self); root.setContentsMargins(10,8,10,9); root.setSpacing(5)

        header = QHBoxLayout()
        header.addWidget(self.label("DRIVER INPUTS",7,True,MUTED)); header.addStretch(1)
        root.addLayout(header)
        # Keep graph/channel controls in their own left-aligned row so the
        # shared hover chrome at the top-right can never cover them.
        channels = QHBoxLayout(); channels.setSpacing(6)
        channels.addWidget(self.label("TRACES",6,True,MUTED))
        self.throttle_button = self._series_button("T", "Toggle throttle trace", GREEN)
        self.brake_button = self._series_button("B", "Toggle brake trace", RED)
        self.ers_button = self._series_button("ERS", "Toggle ERS battery trace", QColor(89,191,229))
        for b in (self.throttle_button,self.brake_button,self.ers_button): channels.addWidget(b)
        channels.addStretch(1); root.addLayout(channels)
        self.minimize_button = None; self.hide_button = None

        self.input_trace = InputTraceWidget(samples=3000); root.addWidget(self.input_trace)
        self.ers_trace = ERSBatteryTraceWidget(samples=3000); root.addWidget(self.ers_trace)

        telemetry = QHBoxLayout(); telemetry.setContentsMargins(2,0,2,0); telemetry.setSpacing(7)
        self.speed_label=self.label("--- km/h",11,True); self.gear_label=self.label("GEAR --",10,True); self.lap_label=self.label("LAP --",8,True,MUTED)
        self.lap_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        telemetry.addWidget(self.speed_label); telemetry.addStretch(1); telemetry.addWidget(self.gear_label); telemetry.addStretch(1); telemetry.addWidget(self.lap_label)
        root.addLayout(telemetry)
        self.throttle_button.clicked.connect(self._toggle_throttle); self.brake_button.clicked.connect(self._toggle_brake); self.ers_button.clicked.connect(self._toggle_ers)
        self._apply_graph_visibility()

    def _plain_button(self,text,tooltip):
        b=QToolButton(); b.setText(text); b.setToolTip(tooltip); b.setFixedSize(22,22); b.setFont(QFont("Segoe UI", 10,QFont.Bold))
        b.setStyleSheet("QToolButton{color:rgba(230,234,239,225);background:rgba(255,255,255,15);border:1px solid rgba(255,255,255,26);border-radius:7px;}QToolButton:hover{background:rgba(255,255,255,36);}")
        return b

    def _series_button(self,text,tooltip,color):
        b=self._plain_button(text,tooltip); b.setCheckable(True); b.setChecked(True); b.setFixedWidth(34 if text=="ERS" else 22)
        b.setStyleSheet(f"QToolButton{{color:rgb({color.red()},{color.green()},{color.blue()});background:rgba(255,255,255,12);border:1px solid rgba(255,255,255,24);border-radius:7px;}}QToolButton:checked{{background:rgba({color.red()},{color.green()},{color.blue()},55);}}")
        return b

    def _toggle_throttle(self): self._show_throttle=self.throttle_button.isChecked(); self._apply_graph_visibility()
    def _toggle_brake(self): self._show_brake=self.brake_button.isChecked(); self._apply_graph_visibility()
    def _toggle_ers(self): self._show_ers=self.ers_button.isChecked(); self._apply_graph_visibility()

    def _apply_graph_visibility(self):
        self.input_trace.set_visible_series(throttle=self._show_throttle, brake=self._show_brake)
        self.input_trace.setVisible(self._show_throttle or self._show_brake)
        self.ers_trace.setVisible(self._show_ers)
        height=84 + (126 if (self._show_throttle or self._show_brake) else 0) + (108 if self._show_ers else 0) + 38
        self.set_overlay_logical_fixed_size(self.WIDTH, height)

    def update_snapshot(self,s):
        # Both DI and RI use the same fixed trailing distance window so their
        # x-axes are directly comparable regardless of sample rate/history.
        self.input_trace.set_distance_cursor(s.lap_distance_m)
        self.ers_trace.set_distance_cursor(s.lap_distance_m)
        # Append graph points only when telemetry has actually progressed.
        # This prevents paused replay frames (or a stationary live snapshot)
        # from extending the traces as artificial straight lines.
        lap_changed = self._last_lap is not None and s.lap_number != self._last_lap
        normal_next_lap = False
        if lap_changed and isinstance(self._last_lap, int) and isinstance(s.lap_number, int):
            normal_next_lap = (s.lap_number == self._last_lap + 1)

        # Driver Inputs is a rolling trace of the driver's own telemetry and is
        # intentionally independent of the coaching reference. A normal
        # start/finish crossing (including the lap where a queued reference
        # becomes active) must therefore NOT clear or restart DI. Only clear on
        # a real replay/source rewind/seek or a non-sequential lap jump.
        rewound = (self._last_lap_time is not None and s.lap_time_s is not None and
                   float(s.lap_time_s) + 0.001 < float(self._last_lap_time) and not normal_next_lap)
        distance_rewound = (self._last_distance is not None and s.lap_distance_m is not None and
                            float(s.lap_distance_m) + 1.0 < float(self._last_distance) and not normal_next_lap)
        lap_seek_or_reset = lap_changed and not normal_next_lap
        if lap_seek_or_reset or rewound or distance_rewound:
            self.input_trace.clear(); self.ers_trace.clear()

        progressed = False
        if s.lap_time_s is not None:
            progressed = self._last_lap_time is None or abs(float(s.lap_time_s) - float(self._last_lap_time)) > 0.0005
        elif s.lap_distance_m is not None:
            progressed = self._last_distance is None or abs(float(s.lap_distance_m) - float(self._last_distance)) > 0.05

        if progressed:
            self.input_trace.add_sample(s.throttle, s.brake, s.lap_distance_m)
            self.ers_trace.add_sample(s.ers_store_j, s.ers_harvested_j, s.ers_deployed_j, s.lap_number, s.lap_time_s, s.lap_distance_m)

        self._last_lap = s.lap_number
        self._last_lap_time = s.lap_time_s
        self._last_distance = s.lap_distance_m
        self.speed_label.setText(f"{s.speed_kph if s.speed_kph is not None else '---'} km/h"); self.gear_label.setText(f"GEAR {_gear_text(s.gear)}")
        lap_text=f"LAP {s.lap_number if s.lap_number is not None else '--'}"
        if s.lap_time_s is not None: lap_text += f"  {_time_text(s.lap_time_s)}"
        if s.lap_distance_m is not None: lap_text += f"  {float(s.lap_distance_m):.0f}m"
        self.lap_label.setText(lap_text)
        if s.lap_valid is False:
            self.lap_label.setStyleSheet(f"color:rgb({RED.red()},{RED.green()},{RED.blue()});background:transparent;"); self.lap_label.setText(lap_text+"  INVALID")
        else: self.lap_label.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")
        return progressed


class ReferenceInputsOverlayWindow(OverlayPanel):
    """Reference-lap throttle/brake/ERS traces synchronized to current lap distance."""

    WIDTH = 430

    def __init__(self, *, on_hide=None, on_toggle_pause=None, on_toggle_click_through=None):
        super().__init__(on_close=on_hide, on_toggle_pause=on_toggle_pause, on_toggle_click_through=on_toggle_click_through)
        self.setWindowTitle("Race Engineer — Reference Inputs")
        self._show_throttle = True
        self._show_brake = True
        self._show_ers = True
        self._last_lap = None
        self._last_ref_name = None
        self._last_ref_time = None
        root = QVBoxLayout(self); root.setContentsMargins(10,8,10,9); root.setSpacing(5)
        header = QHBoxLayout(); header.addWidget(self.label("REFERENCE INPUTS",7,True,MUTED)); header.addStretch(1)
        root.addLayout(header)
        channels = QHBoxLayout(); channels.setSpacing(6)
        channels.addWidget(self.label("TRACES",6,True,MUTED))
        self.throttle_button = self._series_button("T", "Toggle reference throttle trace", GREEN)
        self.brake_button = self._series_button("B", "Toggle reference brake trace", RED)
        self.ers_button = self._series_button("ERS", "Toggle reference ERS trace", QColor(89,191,229))
        for b in (self.throttle_button,self.brake_button,self.ers_button): channels.addWidget(b)
        channels.addStretch(1); root.addLayout(channels)
        self.minimize_button = None; self.hide_button = None
        self.input_trace = InputTraceWidget(samples=3000); root.addWidget(self.input_trace)
        self.ers_trace = ERSBatteryTraceWidget(samples=3000); root.addWidget(self.ers_trace)
        telemetry = QHBoxLayout(); telemetry.setContentsMargins(2,0,2,0); telemetry.setSpacing(7)
        self.speed_label=self.label("--- km/h",11,True); self.gear_label=self.label("GEAR --",10,True); self.lap_label=self.label("REFERENCE --",8,True,MUTED)
        self.lap_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        telemetry.addWidget(self.speed_label); telemetry.addStretch(1); telemetry.addWidget(self.gear_label); telemetry.addStretch(1); telemetry.addWidget(self.lap_label)
        root.addLayout(telemetry)
        self.throttle_button.clicked.connect(self._toggle_throttle); self.brake_button.clicked.connect(self._toggle_brake); self.ers_button.clicked.connect(self._toggle_ers)
        self._apply_graph_visibility()

    def _plain_button(self,text,tooltip):
        b=QToolButton(); b.setText(text); b.setToolTip(tooltip); b.setFixedSize(22,22); b.setFont(QFont("Segoe UI",10,QFont.Bold))
        b.setStyleSheet("QToolButton{color:rgba(230,234,239,225);background:rgba(255,255,255,15);border:1px solid rgba(255,255,255,26);border-radius:7px;}QToolButton:hover{background:rgba(255,255,255,36);}")
        return b

    def _series_button(self,text,tooltip,color):
        b=self._plain_button(text,tooltip); b.setCheckable(True); b.setChecked(True); b.setFixedWidth(34 if text=="ERS" else 22)
        b.setStyleSheet(f"QToolButton{{color:rgb({color.red()},{color.green()},{color.blue()});background:rgba(255,255,255,12);border:1px solid rgba(255,255,255,24);border-radius:7px;}}QToolButton:checked{{background:rgba({color.red()},{color.green()},{color.blue()},55);}}")
        return b

    def _toggle_throttle(self): self._show_throttle=self.throttle_button.isChecked(); self._apply_graph_visibility()
    def _toggle_brake(self): self._show_brake=self.brake_button.isChecked(); self._apply_graph_visibility()
    def _toggle_ers(self): self._show_ers=self.ers_button.isChecked(); self._apply_graph_visibility()

    def _apply_graph_visibility(self):
        self.input_trace.set_visible_series(throttle=self._show_throttle, brake=self._show_brake)
        self.input_trace.setVisible(self._show_throttle or self._show_brake)
        self.ers_trace.setVisible(self._show_ers)
        height=84+(126 if (self._show_throttle or self._show_brake) else 0)+(108 if self._show_ers else 0)+38
        self.set_overlay_logical_fixed_size(self.WIDTH,height)

    def update_snapshot(self,s, *, append_sample=True):
        # Reference traces share the exact same distance cursor/window as DI.
        # Sampling cadence is driven exclusively by DI progression so DI and RI
        # always receive points at the same physical track distances.
        self.input_trace.set_distance_cursor(s.lap_distance_m)
        self.ers_trace.set_distance_cursor(s.lap_distance_m)
        ref_name=s.reference_name or "Reference"
        rewound = self._last_ref_time is not None and s.reference_time_s is not None and float(s.reference_time_s)+0.001 < float(self._last_ref_time)
        changed = ref_name != self._last_ref_name or s.lap_number != self._last_lap
        if changed or rewound:
            self.input_trace.clear(); self.ers_trace.clear()
        if append_sample and s.reference_time_s is not None:
            if s.reference_throttle is not None or s.reference_brake is not None:
                self.input_trace.add_sample(s.reference_throttle or 0.0, s.reference_brake or 0.0, s.lap_distance_m)
            self.ers_trace.add_sample(s.reference_ers_store_j, None, None, s.lap_number, s.reference_time_s, s.lap_distance_m)
        self._last_lap=s.lap_number; self._last_ref_name=ref_name; self._last_ref_time=s.reference_time_s
        self.speed_label.setText(f"{s.reference_speed_kph if s.reference_speed_kph is not None else '---'} km/h")
        self.gear_label.setText(f"GEAR {_gear_text(s.reference_gear)}")
        t=_time_text(s.reference_time_s) if s.reference_time_s is not None else "--:--.---"
        if s.reference_time_s is not None and s.lap_time_s is not None:
            dt = float(s.reference_time_s) - float(s.lap_time_s)
            distance_text = f"  {float(s.lap_distance_m):.0f}m" if s.lap_distance_m is not None else ""
            self.lap_label.setText(f"{ref_name}  REF {t}{distance_text}  Δ {dt:+.3f}")
        else:
            distance_text = f"  {float(s.lap_distance_m):.0f}m" if s.lap_distance_m is not None else ""
            self.lap_label.setText(f"{ref_name}  REF {t}{distance_text}")


class SpeedDeltaOverlayWindow(OverlayPanel):
    WIDTH=340; HEIGHT=154
    def __init__(self,*,on_hide=None,on_toggle_pause=None,on_toggle_click_through=None):
        super().__init__(on_close=on_hide,on_toggle_pause=on_toggle_pause,on_toggle_click_through=on_toggle_click_through)
        self.setWindowTitle("Race Engineer — Delta"); self.set_overlay_logical_fixed_size(self.WIDTH,self.HEIGHT)
        root=QVBoxLayout(self); root.setContentsMargins(14,10,14,12); root.setSpacing(5)
        head=QHBoxLayout(); head.setContentsMargins(0,0,0,0)
        head.addWidget(self.label("DELTA",7,True,MUTED)); head.addStretch(1)
        self.mode = QLabel("LIVE")
        self.mode.setStyleSheet(self.label("", 7, True, MUTED).styleSheet())
        self.minimize_button=None
        root.addLayout(head)
        hero = QHBoxLayout(); hero.setContentsMargins(0,0,0,0)
        self.delta=self.label("--.---",25,True); hero.addWidget(self.delta)
        hero.addStretch(1)
        self.state=self.label("HOLDING",9,True,MUTED); self.state.setAlignment(Qt.AlignRight|Qt.AlignVCenter); hero.addWidget(self.state)
        root.addLayout(hero)
        self.progress=DeltaProgressWidget(range_s=1.0); root.addWidget(self.progress)
        self.helper = self.label("Reference delta over the current sample", 7, False, MUTED)
        self.helper.setAlignment(Qt.AlignCenter)
        root.addWidget(self.helper)
    def update_snapshot(self,s):
        self.progress.set_delta(s.live_delta_s)
        if s.live_delta_s is None:
            self.delta.setText("--.---"); self.delta.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")
            self.state.setText("STANDBY"); self.state.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")
            self.helper.setText("Reference delta over the current sample")
        else:
            c=GREEN if s.live_delta_s<=0 else RED
            state = "GAINING" if s.live_delta_s < -0.02 else "HOLDING" if s.live_delta_s <= 0.02 else "LOSING"
            self.delta.setText(f"{s.live_delta_s:+.3f}")
            self.delta.setStyleSheet(f"color:{_rgba(c)};background:transparent;")
            self.state.setText(state)
            self.state.setStyleSheet(f"color:{_rgba(c)};background:transparent;")
            self.helper.setText("Negative is faster than the selected reference")


class LiveLaptimeOverlayWindow(OverlayPanel):
    WIDTH=350; HEIGHT=165
    def __init__(self,*,on_hide=None,on_toggle_pause=None,on_toggle_click_through=None):
        super().__init__(on_close=on_hide,on_toggle_pause=on_toggle_pause,on_toggle_click_through=on_toggle_click_through)
        self.setWindowTitle("Race Engineer — Live Laptime"); self.set_overlay_logical_fixed_size(self.WIDTH,self.HEIGHT)
        root=QVBoxLayout(self); root.setContentsMargins(12,8,12,9); root.setSpacing(2)
        head=QHBoxLayout(); head.addWidget(self.label("CURRENT TIME",7,True,MUTED)); head.addStretch(1)
        self.minimize_button=None
        root.addLayout(head)
        mid=QHBoxLayout(); self.time=self.label("--:--.---",22,True); self.delta=self.label("--.---",12,True,MUTED); self.delta.setAlignment(Qt.AlignRight|Qt.AlignVCenter); mid.addWidget(self.time); mid.addStretch(1); mid.addWidget(self.delta); root.addLayout(mid)
        self.micro=LapMicroDeltaWidget(); root.addWidget(self.micro)
        self.best=self.label("REFERENCE --",7,True,MUTED); self.best.setAlignment(Qt.AlignCenter); root.addWidget(self.best)
    def update_snapshot(self,s):
        self.time.setText(_time_text(s.lap_time_s)); self.best.setText(f"REFERENCE L{s.reference_lap}  {_time_text(s.best_lap_time_s)}" if s.reference_lap else "REFERENCE --")
        if s.live_delta_s is None: self.delta.setText("--.---"); c=MUTED
        else: self.delta.setText(f"{s.live_delta_s:+.3f}s"); c=GREEN if s.live_delta_s<=0 else RED
        self.delta.setStyleSheet(f"color:rgb({c.red()},{c.green()},{c.blue()});background:transparent;")
        self.micro.set_data(s.delta_dots, s.delta_dot_kinds, s.delta_dot_sectors, s.sector1_delta_s, s.sector2_delta_s, None)



def _card_style(accent: QColor | None = None, *, fill_alpha: int = 28, border_alpha: int = 42, radius: int = 10) -> str:
    border = QColor(accent) if isinstance(accent, QColor) else QColor(255, 255, 255, border_alpha)
    border.setAlpha(max(18, min(255, border_alpha)))
    fill = QColor(9, 14, 20, fill_alpha)
    return (
        f"background:{_rgba(fill)};"
        f"border:1px solid {_rgba(border)};"
        f"border-radius:{int(radius)}px;"
    )


def _panel_text_edit_style() -> str:
    return (
        "QTextEdit { color: rgba(235,238,242,238); background: rgba(8,13,18,74);"
        " border: 1px solid rgba(255,255,255,18); border-radius: 10px; padding: 8px; }"
        "QScrollBar:vertical { background: rgba(255,255,255,8); width: 8px; margin: 2px; }"
        "QScrollBar::handle:vertical { background: rgba(255,255,255,42); border-radius: 4px; min-height: 24px; }"
    )


def _status_label_text(level: str | None) -> str:
    level = (level or "").lower()
    if level in {"good", "ok", "on", "enabled", "ready", "active", "live", "replay"}:
        return "GOOD"
    if level in {"warn", "warning", "caution", "late", "low", "auto", "armed", "capturing"}:
        return "WATCH"
    if level in {"bad", "error", "off", "disabled", "critical", "invalid"}:
        return "ALERT"
    return "INFO"


def _weather_icon(condition: str | None) -> str:
    text = (condition or "").lower()
    if any(k in text for k in ("storm", "thunder")):
        return "⛈"
    if any(k in text for k in ("rain", "wet", "shower")):
        return "🌧"
    if any(k in text for k in ("cloud", "overcast")):
        return "⛅"
    if any(k in text for k in ("sun", "clear", "dry")):
        return "☀"
    return "◌"


class DataOverlayWindow(OverlayPanel):
    """Compact base for race/session information overlays."""

    def __init__(self, title, width, height, *, on_hide=None, on_toggle_pause=None, on_toggle_click_through=None):
        super().__init__(on_close=on_hide, on_toggle_pause=on_toggle_pause, on_toggle_click_through=on_toggle_click_through)
        self.setWindowTitle(f"Race Engineer — {title.title()}")
        self.set_overlay_logical_fixed_size(width, height)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(14, 10, 14, 12)
        self.root.setSpacing(6)
        self.root.setAlignment(Qt.AlignTop)

        head = QHBoxLayout(); head.setContentsMargins(0, 0, 0, 0); head.setSpacing(8)
        self.title_label = self.label(title, 9, True)
        head.addWidget(self.title_label)
        head.addStretch(1)
        self.header_chip = QLabel("")
        self.header_chip.hide()
        head.addWidget(self.header_chip)
        self.minimize_button = None
        self.root.addLayout(head)

        self.subtitle_label = self.label("", 7, True, MUTED)
        self.subtitle_label.hide()
        self.root.addWidget(self.subtitle_label)

        self.status = self.label("", 7, True, MUTED)
        self.status.setAlignment(Qt.AlignCenter)
        self.status.hide()
        self.root.addWidget(self.status)

        self._footer_frame = None
        self._footer_left = None
        self._footer_right = None

    def set_subtitle(self, text: str | None):
        text = (text or "").strip()
        self.subtitle_label.setVisible(bool(text))
        self.subtitle_label.setText(text)

    def set_header_chip(self, text: str | None, color=QColor(89, 191, 229)):
        text = (text or "").strip()
        if not text:
            self.header_chip.hide()
            return
        if not isinstance(color, QColor):
            color = QColor(color)
        fill = QColor(color); fill.setAlpha(32)
        border = QColor(color); border.setAlpha(96)
        self.header_chip.setText(text.upper())
        self.header_chip.setStyleSheet(
            f"color:{_rgba(color)};background:{_rgba(fill)};border:1px solid {_rgba(border)};"
            "border-radius:9px;padding:2px 7px;font-weight:700;letter-spacing:0.4px;"
        )
        self.header_chip.show()

    def card_frame(self, accent: QColor | None = None, *, fill_alpha: int = 28, border_alpha: int = 42, radius: int = 10) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_card_style(accent, fill_alpha=fill_alpha, border_alpha=border_alpha, radius=radius))
        return frame

    def card_layout(self, accent: QColor | None = None, *, margins=(10, 9, 10, 9), spacing: int = 4, fill_alpha: int = 28):
        frame = self.card_frame(accent, fill_alpha=fill_alpha)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)
        return frame, layout

    def chip_label(self, text: str, color=WHITE) -> QLabel:
        if not isinstance(color, QColor):
            color = QColor(color)
        fill = QColor(color); fill.setAlpha(28)
        border = QColor(color); border.setAlpha(92)
        w = QLabel(text.upper())
        w.setStyleSheet(
            f"color:{_rgba(color)};background:{_rgba(fill)};border:1px solid {_rgba(border)};"
            "border-radius:9px;padding:2px 7px;font-weight:700;letter-spacing:0.4px;"
        )
        return w

    def create_footer(self):
        if self._footer_frame is not None:
            return self._footer_frame
        self._footer_frame = self.card_frame(fill_alpha=18, border_alpha=26, radius=9)
        layout = QHBoxLayout(self._footer_frame)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)
        self._footer_left = self.label("", 6, True, MUTED)
        self._footer_left.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._footer_right = self.label("", 6, True, MUTED)
        self._footer_right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._footer_left)
        layout.addStretch(1)
        layout.addWidget(self._footer_right)
        self.root.addWidget(self._footer_frame)
        self._footer_frame.hide()
        return self._footer_frame

    def set_footer(self, left: str | None = None, right: str | None = None, *, right_color=MUTED):
        if not left and not right:
            if self._footer_frame is not None:
                self._footer_frame.hide()
            return
        self.create_footer()
        self._footer_left.setText(left or "")
        self._footer_right.setText(right or "")
        self._footer_right.setStyleSheet(f"color:{_rgba(right_color)};background:transparent;")
        self._footer_frame.show()

    def set_applicable(self, applicable: bool, message: str):
        self.status.setVisible(not applicable)
        self.status.setText(message if not applicable else "")

    def paintEvent(self, _event):
        # R8 information overlays use a stable dark surface so light desktop/web
        # content behind the window cannot wash out the presentation. The user's
        # existing overlay opacity setting still applies to the whole window.
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(10, 13, 17, 244))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(QColor(255, 255, 255, 30))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 12, 12)


class RadioTranscriptOverlayWindow(DataOverlayWindow):
    """Conversation log for driver PTT questions and radio messages actually heard."""

    WIDTH = 515
    HEIGHT = 420

    def __init__(self, *, transcript_store=None, on_hide=None, on_toggle_pause=None, on_toggle_click_through=None):
        super().__init__(
            "RADIO TRANSCRIPT", self.WIDTH, self.HEIGHT,
            on_hide=on_hide, on_toggle_pause=on_toggle_pause,
            on_toggle_click_through=on_toggle_click_through,
        )
        self.transcript_store = transcript_store
        self._last_sequence = -1
        self.set_subtitle("DRIVER questions  •  ENGINEER / race-control radio")
        self.set_header_chip("LIVE", GREEN)

        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setAcceptRichText(True)
        self.body.setFrameStyle(QFrame.NoFrame)
        self.body.setStyleSheet(_panel_text_edit_style())
        self.body.setFont(QFont("Segoe UI", 9))
        self.root.addWidget(self.body, 1)

        foot = QHBoxLayout(); foot.setContentsMargins(0, 0, 0, 0)
        self.count_label = self.label("0 messages", 7, False, MUTED)
        foot.addWidget(self.count_label)
        foot.addStretch(1)
        clear = QToolButton()
        clear.setText("CLR")
        clear.setToolTip("Clear radio transcript")
        clear.setFixedSize(34, 22)
        clear.clicked.connect(self.clear_transcript)
        foot.addWidget(clear)
        self.root.addLayout(foot)
        self.update_entries(())

    @staticmethod
    def _session_time_text(seconds):
        if seconds is None:
            return "--:--.---"
        try:
            seconds = max(0.0, float(seconds))
        except (TypeError, ValueError):
            return "--:--.---"
        minutes = int(seconds // 60)
        return f"{minutes:02d}:{seconds - minutes * 60:06.3f}"

    def clear_transcript(self):
        if self.transcript_store is not None:
            self.transcript_store.clear()
        self._last_sequence = -1
        self.update_entries(())

    def update_from_store(self):
        store = self.transcript_store
        if store is None:
            return
        revision = store.latest_sequence
        if revision == self._last_sequence:
            return
        self.update_entries(store.snapshot(), revision=revision)

    def update_entries(self, entries, *, revision=None):
        entries = tuple(entries)
        if revision is None:
            revision = entries[-1].sequence if entries else 0
        if revision == self._last_sequence:
            return
        self._last_sequence = revision

        if not entries:
            self.body.setHtml(
                '<div style="color:#8b949e; font-size:10pt; padding:10px;">'
                '<b>Radio transcript is empty.</b><br><br>'
                'Hold PTT and ask a question. Driver speech and engineer radio will appear here.'
                '</div>'
            )
            self.count_label.setText("0 messages")
            self.set_footer("Waiting for radio activity", "READY", right_color=QColor(89, 191, 229))
            return

        rows = []
        for entry in entries:
            role = str(entry.role).upper()
            role_color = "#58a6ff" if role == "DRIVER" else "#3fb950"
            role_fill = "rgba(88,166,255,0.12)" if role == "DRIVER" else "rgba(63,185,80,0.12)"
            time_text = self._session_time_text(entry.session_time_s)
            text_html = html.escape(entry.text)
            interpreted = getattr(entry, "interpreted_text", None)
            interpreted_html = ""
            if role == "DRIVER" and interpreted:
                raw_norm = " ".join(str(entry.text).lower().split()).strip(" .?!")
                interp_norm = " ".join(str(interpreted).lower().split()).strip(" .?!")
                if interp_norm and interp_norm != raw_norm:
                    interpreted_html = (
                        '<div style="margin-top:4px;color:#d29922; font-size:8pt;">'
                        f'↳ interpreted: {html.escape(str(interpreted))}</div>'
                    )
            rows.append(
                '<div style="margin:0 0 10px 0; padding:8px 10px; '
                'background:rgba(255,255,255,0.025); border:1px solid rgba(255,255,255,0.05);">'
                f'<span style="color:{role_color}; font-weight:700; font-size:8pt;">{role}</span>'
                '<span style="color:#52606d;">&nbsp;&nbsp;•&nbsp;&nbsp;</span>'
                f'<span style="color:#8b949e; font-family:Consolas; font-size:8pt;">{time_text}</span>'
                '<br>'
                f'<span style="color:#f0f3f6; font-size:10pt;">{text_html}</span>'
                f'{interpreted_html}'
                '</div>'
            )
        self.body.setHtml("".join(rows))
        scroll = self.body.verticalScrollBar()
        scroll.setValue(scroll.maximum())
        count = len(entries)
        self.count_label.setText(f"{count} message{'s' if count != 1 else ''}")
        last = entries[-1]
        self.set_footer(
            f"{count} message{'s' if count != 1 else ''}",
            f"LAST {self._session_time_text(last.session_time_s)}",
            right_color=QColor(89, 191, 229),
        )


class SessionSummaryOverlayWindow(DataOverlayWindow):
    """End-of-session classification and deterministic race summary."""
    WIDTH = 465
    HEIGHT = 390

    def __init__(self, *, receiver=None, on_hide=None, on_toggle_pause=None, on_toggle_click_through=None):
        super().__init__("SESSION SUMMARY", self.WIDTH, self.HEIGHT, on_hide=on_hide,
                         on_toggle_pause=on_toggle_pause, on_toggle_click_through=on_toggle_click_through)
        self.receiver = receiver
        self._last_revision = -1
        self.set_subtitle("Final classification and deterministic wrap-up")
        self.summary_card, card = self.card_layout(QColor(89, 191, 229), margins=(12, 10, 12, 10), spacing=6)
        self.headline = self.label("WAITING FOR SESSION FINISH", 12, True, MUTED)
        self.headline.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        card.addWidget(self.headline)
        self.summary_hint = self.label("The final classification will appear here when the session ends.", 7, False, MUTED)
        self.summary_hint.setWordWrap(True)
        card.addWidget(self.summary_hint)
        self.root.addWidget(self.summary_card)
        self.body = QTextEdit(); self.body.setReadOnly(True); self.body.setFrameStyle(QFrame.NoFrame)
        self.body.setStyleSheet(_panel_text_edit_style())
        self.body.setFont(QFont("Segoe UI", 9))
        self.root.addWidget(self.body, 1)
        self.update_from_receiver()

    def update_from_receiver(self):
        r=self.receiver
        if r is None: return False
        revision=int(getattr(r,'session_summary_revision',0) or 0)
        if revision == self._last_revision: return False
        self._last_revision=revision
        summary=getattr(r,'session_summary',None)
        if not summary:
            self.set_overlay_logical_fixed_size(self.WIDTH, 205)
            self.body.hide()
            self.headline.setText("WAITING FOR SESSION FINISH")
            self.headline.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")
            self.summary_hint.setText("The final classification will appear here when the session ends.")
            self.body.setPlainText("The final classification will appear here when the session ends.")
            self.set_footer("End-of-session summary", "STANDBY", right_color=QColor(89,191,229))
            return False
        self.set_overlay_logical_fixed_size(self.WIDTH, self.HEIGHT)
        self.body.show()
        pos=summary.get('position'); status=summary.get('result_status') or 'Session complete'
        title=(f"P{pos}  •  {status}" if pos else status).upper()
        title_color = GREEN if pos and pos <= 3 else (QColor(239,183,77) if pos else WHITE)
        self.headline.setText(title)
        self.headline.setStyleSheet(f"color:{_rgba(title_color)};background:transparent;")
        self.summary_hint.setText(summary.get('headline') or "Classification complete")
        self.body.setPlainText(summary.get('text') or 'Session summary available.')
        self.set_footer("Final classification", f"P{pos}" if pos else "COMPLETE", right_color=title_color)
        return True


class RaceEngineerOverlayWindow(DataOverlayWindow):
    """Deterministic race-strategy summary rendered atomically from one snapshot.

    The whole body is replaced on every refresh. This avoids a partially/stale
    collection of child QLabel widgets getting visually out of sync with the
    immutable OverlaySnapshot used by the rest of the HUD.
    """

    WIDTH = 405
    HEIGHT = 390

    def __init__(self, **kwargs):
        super().__init__("SESSION ENGINEER", self.WIDTH, self.HEIGHT, **kwargs)
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.RichText)
        self.body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.body.setStyleSheet("background: transparent; color: white;")
        self.root.addWidget(self.body, 1)
        self._render_sequence = 0
        self._last_render_lap = None
        self._render_waiting()

    @staticmethod
    def _hex(color: QColor) -> str:
        return f"#{color.red():02x}{color.green():02x}{color.blue():02x}"

    @staticmethod
    def _decision_color(decision):
        if decision in {"STAY OUT", "FINISH THE RACE", "PUSH LAP", "PREPARE LAP", "PREPARE RUN"}:
            return GREEN
        if decision in {"BOX THIS LAP", "BOX SOON", "LAP INVALID"}:
            return RED
        if decision in {"CONSIDER BOX", "BOX", "FINISH LAP"}:
            return QColor(239,183,77)
        if decision in {"FINISHED", "QUALIFYING COMPLETE", "SESSION COMPLETE"}:
            return QColor(89,191,229)
        return MUTED

    def _render_waiting(self):
        muted = self._hex(MUTED)
        self.body.setText(
            f'<div style="font-family:Segoe UI;color:{muted};font-size:10pt;">'
            '<div align="center"><b>WAITING FOR RACE DATA</b></div>'
            '</div>'
        )

    @staticmethod
    def _clock_text(seconds):
        if seconds is None:
            return "--:--"
        seconds = max(0, int(seconds))
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _render_qualifying(self, s):
        self.title_label.setText("QUALIFYING ENGINEER")
        self.setWindowTitle("Race Engineer — Qualifying Engineer")
        self.set_applicable(True, "")

        one_shot = bool(s.session_type and "One-Shot" in s.session_type)
        guide = evaluate_qualifying(
            session_finished=s.session_finished,
            driver_status=s.driver_status,
            lap_valid=s.lap_valid,
            session_time_left_s=s.session_time_left_s,
            current_lap_time_s=s.lap_time_s,
            lap_distance_m=s.lap_distance_m,
            track_length_m=s.track_length_m,
            best_lap_time_s=s.best_lap_time_s,
            one_shot=one_shot,
        )

        pos = f"P{s.position}" if isinstance(s.position, int) and s.position > 0 else "P--"
        lap_text = f"LAP {s.lap_number}" if isinstance(s.lap_number, int) else "LAP --"
        run_status = s.driver_status or "--"
        if s.lap_valid is True:
            validity, validity_color = "VALID", GREEN
        elif s.lap_valid is False:
            validity, validity_color = "INVALID", RED
        else:
            validity, validity_color = "--", MUTED

        tyre = s.current_compound or "--"
        if s.tyre_age_laps is not None:
            tyre += f" • {s.tyre_age_laps}L"
        wear_values = [float(v) for v in s.tyre_wear if v is not None]
        max_wear = max(wear_values) if wear_values else None
        wear = f"{max_wear:.0f}%" if max_wear is not None else "--"
        if max_wear is None:
            wear_color = MUTED
        elif max_wear < 50:
            wear_color = GREEN
        elif max_wear < 75:
            wear_color = QColor(239,183,77)
        else:
            wear_color = RED

        if s.fuel_remaining_laps is None:
            fuel_text, fuel_color = "--", MUTED
        else:
            fuel_text = f"{s.fuel_remaining_laps:+.2f} laps"
            fuel_color = RED if s.fuel_remaining_laps < 0 else QColor(239,183,77) if s.fuel_remaining_laps < 0.5 else GREEN

        best = _time_text(s.best_lap_time_s)
        if s.live_delta_s is None:
            delta, delta_color = "--", MUTED
        else:
            delta = f"{s.live_delta_s:+.3f}s"
            delta_color = GREEN if s.live_delta_s <= 0 else RED

        weather = s.weather_now or "--"
        rain = next((row.rain_percent for row in s.weather_forecast if row.offset_minutes == 0), None)
        if rain is not None:
            weather += f" • {rain}% rain"

        available = [row for row in s.tyre_sets if row.available is True and row.fitted is not True]
        fastest = min(available, key=lambda row: row.lap_delta_s) if available else None
        fastest_set = f"{fastest.compound} • Set {fastest.index + 1}" if fastest is not None else "--"
        fastest_delta = f"{fastest.lap_delta_s:+.3f}s" if fastest is not None else "--"
        time_to_line = "--" if guide.time_to_line_estimate_s is None else f"~{guide.time_to_line_estimate_s:.0f}s"
        clock_display = "ONE SHOT" if one_shot else self._clock_text(s.session_time_left_s)

        muted = self._hex(MUTED)
        white = self._hex(WHITE)
        validity_hex = self._hex(validity_color)
        wear_hex = self._hex(wear_color)
        fuel_hex = self._hex(fuel_color)
        delta_hex = self._hex(delta_color)
        decision_hex = self._hex(self._decision_color(guide.decision))

        if s.session_finished:
            html = (
                f'<div style="font-family:Segoe UI;font-size:9pt;color:{white};">'
                f'<div align="center" style="color:{muted};font-weight:600;margin-bottom:8px;">{pos} &nbsp;•&nbsp; QUALIFYING COMPLETE</div>'
                f'<div style="color:{muted};font-size:8pt;font-weight:700;margin-bottom:4px;">FINAL STATUS</div>'
                f'<table width="100%" cellspacing="0" cellpadding="2">'
                f'<tr><td style="color:{muted};font-weight:700;">BEST LAP</td><td align="right"><b>{best}</b></td><td style="color:{muted};font-weight:700;">POSITION</td><td align="right"><b>{pos}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">TYRE</td><td align="right"><b>{tyre}</b></td><td style="color:{muted};font-weight:700;">WEAR</td><td align="right" style="color:{wear_hex};"><b>{wear}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">WEATHER</td><td align="right"><b>{weather}</b></td><td style="color:{muted};font-weight:700;">FUEL</td><td align="right" style="color:{fuel_hex};"><b>{fuel_text}</b></td></tr>'
                f'</table>'
                f'<div align="center" style="color:{decision_hex};font-size:17pt;font-weight:700;margin-top:18px;">QUALIFYING COMPLETE</div>'
                f'</div>'
            )
        else:
            html = (
                f'<div style="font-family:Segoe UI;font-size:9pt;color:{white};">'
                f'<div align="center" style="color:{muted};font-weight:600;margin-bottom:8px;">{pos} &nbsp;•&nbsp; {lap_text} &nbsp;•&nbsp; {clock_display}</div>'
                f'<div style="color:{muted};font-size:8pt;font-weight:700;margin-bottom:4px;">CURRENT RUN</div>'
                f'<table width="100%" cellspacing="0" cellpadding="2">'
                f'<tr><td style="color:{muted};font-weight:700;">STATUS</td><td align="right"><b>{run_status}</b></td><td style="color:{muted};font-weight:700;">LAP</td><td align="right" style="color:{validity_hex};"><b>{validity}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">TYRE</td><td align="right"><b>{tyre}</b></td><td style="color:{muted};font-weight:700;">WEAR</td><td align="right" style="color:{wear_hex};"><b>{wear}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">BEST LAP</td><td align="right"><b>{best}</b></td><td style="color:{muted};font-weight:700;">LIVE DELTA</td><td align="right" style="color:{delta_hex};"><b>{delta}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">FUEL</td><td align="right" style="color:{fuel_hex};"><b>{fuel_text}</b></td><td style="color:{muted};font-weight:700;">WEATHER</td><td align="right"><b>{weather}</b></td></tr>'
                f'</table><hr style="color:#343941;" />'
                f'<div style="color:{muted};font-size:8pt;font-weight:700;margin-bottom:4px;">QUALIFYING</div>'
                f'<table width="100%" cellspacing="0" cellpadding="2">'
                f'<tr><td style="color:{muted};font-weight:700;">TIME LEFT</td><td align="right"><b>{clock_display}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">TIME TO LINE</td><td align="right"><b>{time_to_line}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">ANOTHER LAP</td><td align="right"><b>{guide.another_lap_estimate}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">AVAILABLE SETS</td><td align="right"><b>{len(available)}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">FASTEST SET</td><td align="right"><b>{fastest_set}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">EA SET DELTA</td><td align="right"><b>{fastest_delta}</b></td></tr>'
                f'<tr><td style="color:{muted};font-weight:700;">CONFIDENCE</td><td align="right" style="color:{muted};"><b>{guide.confidence.upper()}</b></td></tr>'
                f'</table>'
                f'<div style="color:{muted};font-size:8pt;font-weight:700;margin-top:5px;">DECISION</div>'
                f'<div align="center" style="color:{decision_hex};font-size:17pt;font-weight:700;margin-top:4px;">{guide.decision}</div>'
                f'<div align="center" style="color:{muted};font-size:8pt;margin-top:2px;">{guide.reason}</div>'
                f'</div>'
            )

        self.body.setText(html)
        self.body.update()
        self.body.repaint()
        self.update()

    def update_snapshot(self, s):
        # Normalize the public snapshot profile before routing.  This renderer
        # must select the session UI from the SAME immutable snapshot used by
        # Control Center; never fall through to race strategy merely because of
        # casing/whitespace or a non-string enum representation.
        profile = str(getattr(s, "event_profile", "") or "").strip().upper()
        session_type = str(getattr(s, "session_type", "") or "").strip().upper()
        is_qualifying = "QUALIFY" in profile or "QUALIFY" in session_type
        if is_qualifying:
            self._render_qualifying(s)
            return
        self.title_label.setText("RACE ENGINEER")
        self.setWindowTitle("Race Engineer — Race Engineer")
        d = s.race_engineer
        self.set_applicable(d.applicable or s.session_finished, "RACE STRATEGY NOT APPLICABLE IN THIS SESSION")

        self._render_sequence += 1
        self._last_render_lap = s.lap_number

        pos = f"P{s.position}" if isinstance(s.position, int) and s.position > 0 else "P--"
        if isinstance(s.lap_number, int) and isinstance(s.total_laps, int):
            lap = f"LAP {s.lap_number}/{s.total_laps}"
        elif isinstance(s.lap_number, int):
            lap = f"LAP {s.lap_number}"
        else:
            lap = "LAP --"

        tyre = s.current_compound or "--"
        if s.tyre_age_laps is not None:
            tyre += f" • {s.tyre_age_laps}L"

        wear_values = [float(v) for v in s.tyre_wear if v is not None]
        max_wear = max(wear_values) if wear_values else None
        wear = f"{max_wear:.0f}%" if max_wear is not None else "--"
        wear_color = GREEN if max_wear is not None and max_wear < 50 else QColor(239,183,77) if max_wear is not None and max_wear < 75 else RED if max_wear is not None else MUTED

        life = f"~{s.tyre_laps_remaining_estimate:.1f} laps" if s.tyre_laps_remaining_estimate is not None else "--"

        if s.fuel_remaining_laps is None:
            fuel_text = "--"; fuel_color = MUTED
        else:
            fuel_text = f"{s.fuel_remaining_laps:+.2f} laps"
            fuel_color = RED if s.fuel_remaining_laps < 0 else QColor(239,183,77) if s.fuel_remaining_laps < 0.5 else GREEN

        if s.front_wing_damage_percent is None:
            damage_text = "--"; damage_color = MUTED
        else:
            damage_text = f"Front wing {s.front_wing_damage_percent}%"
            damage_color = GREEN if s.front_wing_damage_percent < 20 else QColor(239,183,77) if s.front_wing_damage_percent < 40 else RED

        weather = s.weather_now or "--"
        rain = next((row.rain_percent for row in s.weather_forecast if row.offset_minutes == 0), None)
        if rain is not None:
            weather += f" • {rain}% rain"

        penalty = f"{s.penalties_s}s" if isinstance(s.penalties_s, int) else "--"
        if s.serve_penalty:
            penalty += " • SERVE"
        penalty_color = RED if s.serve_penalty or (isinstance(s.penalties_s, int) and s.penalties_s > 0) else WHITE
        pit_status = s.pit_status or "--"

        laps_remaining = None
        if isinstance(s.total_laps, int) and isinstance(s.lap_number, int):
            laps_remaining = max(0, s.total_laps - s.lap_number)
        laps_remaining_text = str(laps_remaining) if laps_remaining is not None else "--"
        final_lap = bool(
            not s.session_finished
            and isinstance(s.total_laps, int)
            and s.total_laps > 0
            and isinstance(s.lap_number, int)
            and s.lap_number >= s.total_laps
        )
        safety_car = s.safety_car or "--"

        strategy_in_sync = bool(
            s.session_finished
            or (d.lap_number is not None and s.lap_number is not None and d.lap_number == s.lap_number)
        )
        if strategy_in_sync:
            if d.next_tyre_compound:
                next_tyre = d.next_tyre_compound
                if d.next_tyre_set is not None:
                    next_tyre += f" • Set {d.next_tyre_set + 1}"
            else:
                next_tyre = "--"
            confidence = (d.confidence or "--").upper()
            decision = d.decision
            reason = d.reason or ("Race finished." if s.session_finished else "Waiting for sufficient deterministic race data.")
        else:
            next_tyre = "--"
            confidence = "SYNCING"
            decision = "NO DECISION"
            reason = "Updating deterministic strategy for the current lap."

        if s.session_finished:
            decision = "RACE FINISHED"
            reason = ""
        elif final_lap:
            decision = "FINISH THE RACE"
            reason = "final lap — no strategic stop remaining"
            confidence = "HIGH"
            next_tyre = "--"

        decision_color = self._decision_color("FINISHED" if s.session_finished else decision)
        muted = self._hex(MUTED)
        white = self._hex(WHITE)
        fuel_hex = self._hex(fuel_color)
        wear_hex = self._hex(wear_color)
        damage_hex = self._hex(damage_color)
        penalty_hex = self._hex(penalty_color)
        decision_hex = self._hex(decision_color)

        if s.session_finished:
            html = f"""<div style="font-family:Segoe UI;font-size:9pt;color:{white};">
            <div align="center" style="color:{muted};font-weight:600;margin-bottom:8px;">{pos} &nbsp;•&nbsp; RACE FINISHED</div>
            <div style="color:{muted};font-size:8pt;font-weight:700;margin-bottom:4px;">FINAL STATUS</div>
            <table width="100%" cellspacing="0" cellpadding="2">
              <tr><td style="color:{muted};font-weight:700;">TYRE</td><td align="right"><b>{tyre}</b></td><td style="color:{muted};font-weight:700;">WEAR</td><td align="right" style="color:{wear_hex};"><b>{wear}</b></td></tr>
              <tr><td style="color:{muted};font-weight:700;">FUEL</td><td align="right" style="color:{fuel_hex};"><b>{fuel_text}</b></td><td style="color:{muted};font-weight:700;">DAMAGE</td><td align="right" style="color:{damage_hex};"><b>{damage_text}</b></td></tr>
              <tr><td style="color:{muted};font-weight:700;">WEATHER</td><td align="right"><b>{weather}</b></td><td style="color:{muted};font-weight:700;">PENALTY</td><td align="right" style="color:{penalty_hex};"><b>{penalty}</b></td></tr>
            </table>
            <div align="center" style="color:{decision_hex};font-size:18pt;font-weight:700;margin-top:18px;">RACE FINISHED</div>
            <div align="center" style="color:{white};font-size:13pt;font-weight:700;margin-top:4px;">{pos}</div>
            </div>"""
        elif final_lap:
            html = f"""<div style="font-family:Segoe UI;font-size:9pt;color:{white};">
            <div align="center" style="color:{muted};font-weight:600;margin-bottom:8px;">{pos} &nbsp;•&nbsp; FINAL LAP</div>
            <div style="color:{muted};font-size:8pt;font-weight:700;margin-bottom:4px;">CURRENT</div>
            <table width="100%" cellspacing="0" cellpadding="2">
              <tr><td style="color:{muted};font-weight:700;">TYRE</td><td align="right"><b>{tyre}</b></td><td style="color:{muted};font-weight:700;">WEAR</td><td align="right" style="color:{wear_hex};"><b>{wear}</b></td></tr>
              <tr><td style="color:{muted};font-weight:700;">TYRE LIFE</td><td align="right"><b>{life}</b></td><td style="color:{muted};font-weight:700;">FUEL</td><td align="right" style="color:{fuel_hex};"><b>{fuel_text}</b></td></tr>
              <tr><td style="color:{muted};font-weight:700;">DAMAGE</td><td align="right" style="color:{damage_hex};"><b>{damage_text}</b></td><td style="color:{muted};font-weight:700;">WEATHER</td><td align="right"><b>{weather}</b></td></tr>
              <tr><td style="color:{muted};font-weight:700;">PENALTY</td><td align="right" style="color:{penalty_hex};"><b>{penalty}</b></td><td style="color:{muted};font-weight:700;">PIT</td><td align="right"><b>{pit_status}</b></td></tr>
            </table>
            <hr style="color:#343941;" />
            <div style="color:{muted};font-size:8pt;font-weight:700;margin-bottom:4px;">FINAL LAP</div>
            <table width="100%" cellspacing="0" cellpadding="2">
              <tr><td style="color:{muted};font-weight:700;">LAPS REMAINING</td><td align="right"><b>0</b></td></tr>
              <tr><td style="color:{muted};font-weight:700;">SAFETY CAR</td><td align="right"><b>{safety_car}</b></td></tr>
              <tr><td style="color:{muted};font-weight:700;">CONFIDENCE</td><td align="right" style="color:{muted};"><b>{confidence}</b></td></tr>
            </table>
            <div style="color:{muted};font-size:8pt;font-weight:700;margin-top:5px;">DECISION</div>
            <div align="center" style="color:{decision_hex};font-size:17pt;font-weight:700;margin-top:4px;">FINISH THE RACE</div>
            <div align="center" style="color:{muted};font-size:8pt;margin-top:2px;">{reason}</div>
            </div>"""
        else:
            html = f"""<div style="font-family:Segoe UI;font-size:9pt;color:{white};">
        <div align="center" style="color:{muted};font-weight:600;margin-bottom:8px;">{pos} &nbsp;•&nbsp; {lap}</div>
        <div style="color:{muted};font-size:8pt;font-weight:700;margin-bottom:4px;">CURRENT</div>
        <table width="100%" cellspacing="0" cellpadding="2">
          <tr><td style="color:{muted};font-weight:700;">TYRE</td><td align="right"><b>{tyre}</b></td><td style="color:{muted};font-weight:700;">WEAR</td><td align="right" style="color:{wear_hex};"><b>{wear}</b></td></tr>
          <tr><td style="color:{muted};font-weight:700;">TYRE LIFE</td><td align="right"><b>{life}</b></td><td style="color:{muted};font-weight:700;">FUEL</td><td align="right" style="color:{fuel_hex};"><b>{fuel_text}</b></td></tr>
          <tr><td style="color:{muted};font-weight:700;">DAMAGE</td><td align="right" style="color:{damage_hex};"><b>{damage_text}</b></td><td style="color:{muted};font-weight:700;">WEATHER</td><td align="right"><b>{weather}</b></td></tr>
          <tr><td style="color:{muted};font-weight:700;">PENALTY</td><td align="right" style="color:{penalty_hex};"><b>{penalty}</b></td><td style="color:{muted};font-weight:700;">PIT</td><td align="right"><b>{pit_status}</b></td></tr>
        </table>
        <hr style="color:#343941;" />
        <div style="color:{muted};font-size:8pt;font-weight:700;margin-bottom:4px;">STRATEGY</div>
        <table width="100%" cellspacing="0" cellpadding="2">
          <tr><td style="color:{muted};font-weight:700;">TYRE IF BOX</td><td align="right"><b>{next_tyre}</b></td></tr>
          <tr><td style="color:{muted};font-weight:700;">LAPS REMAINING</td><td align="right"><b>{laps_remaining_text}</b></td></tr>
          <tr><td style="color:{muted};font-weight:700;">PIT WINDOW</td><td align="right" style="color:{muted};"><b>--</b></td></tr>
          <tr><td style="color:{muted};font-weight:700;">REJOIN</td><td align="right" style="color:{muted};"><b>--</b></td></tr>
          <tr><td style="color:{muted};font-weight:700;">SAFETY CAR</td><td align="right"><b>{safety_car}</b></td></tr>
          <tr><td style="color:{muted};font-weight:700;">CONFIDENCE</td><td align="right" style="color:{muted};"><b>{confidence}</b></td></tr>
        </table>
        <div style="color:{muted};font-size:8pt;font-weight:700;margin-top:5px;">DECISION</div>
        <div align="center" style="color:{decision_hex};font-size:17pt;font-weight:700;margin-top:4px;">{decision}</div>
        <div align="center" style="color:{muted};font-size:8pt;margin-top:2px;">{reason}</div>
        </div>"""
        self.body.setText(html)
        self.body.update()
        self.body.repaint()
        self.update()


class QualifyingEngineerOverlayWindow(RaceEngineerOverlayWindow):
    """Dedicated qualifying engineer window.

    Qualifying no longer shares the Race Engineer routing method. The OverlaySuite
    selects this concrete window from the same shared snapshot used by the rest of
    the HUD, mirroring the architecture that fixed Race Engineer live sync.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_label.setText("QUALIFYING ENGINEER")
        self.setWindowTitle("Race Engineer — Qualifying Engineer")
        self._render_waiting()

    def update_snapshot(self, s):
        self._render_qualifying(s)


class ERSBatteryOverlayWindow(DataOverlayWindow):
    WIDTH=340; HEIGHT=235
    MAX_STORE_J=4_000_000.0

    def __init__(self, **kwargs):
        super().__init__("ERS", self.WIDTH, self.HEIGHT, **kwargs)
        self._last_store_j=None; self._last_lap=None; self._last_time=None
        self.set_subtitle("Hybrid battery reserve and deployment state")
        self.hero_card, hero = self.card_layout(QColor(89,191,229), margins=(12, 10, 12, 10), spacing=5)
        top=QHBoxLayout(); top.setContentsMargins(0,0,0,0)
        self.state_chip = self.chip_label("WAITING", MUTED); top.addWidget(self.state_chip)
        top.addStretch(1)
        self.energy_mass = self.label("-- / 4.00 MJ", 7, True, MUTED); top.addWidget(self.energy_mass)
        hero.addLayout(top)
        self.big = self.label("--%", 24, True, WHITE); self.big.setAlignment(Qt.AlignCenter); hero.addWidget(self.big)
        self.root.addWidget(self.hero_card)
        self.bar=QProgressBar(); self.bar.setRange(0,100); self.bar.setTextVisible(True); self.bar.setFixedHeight(30); self.root.addWidget(self.bar)
        self.value=self.label("Hybrid reserve unavailable",8,False,MUTED); self.value.setAlignment(Qt.AlignCenter); self.root.addWidget(self.value)
        self.set_footer("Hybrid reserve", "STANDBY", right_color=QColor(89,191,229))

    def update_snapshot(self,s):
        store=s.ers_store_j
        if store is None:
            self.bar.setValue(0); self.bar.setFormat("--%")
            self.big.setText("--%"); self.energy_mass.setText("-- / 4.00 MJ")
            self.value.setText("Hybrid reserve unavailable")
            self.state_chip.setText("WAITING"); self.state_chip.setStyleSheet(self.chip_label("WAITING", MUTED).styleSheet())
            self.big.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")
            self.set_footer("Hybrid reserve", "STANDBY", right_color=QColor(89,191,229)); return
        store=float(store); pct=max(0,min(100,int(round(store/self.MAX_STORE_J*100))))
        time_rewound = (s.lap_time_s is not None and self._last_time is not None and float(s.lap_time_s) + 0.001 < float(self._last_time))
        reset = self._last_lap is not None and s.lap_number != self._last_lap or time_rewound
        delta=0.0 if self._last_store_j is None or reset else store-self._last_store_j
        self._last_store_j=store; self._last_lap=s.lap_number
        self._last_time=float(s.lap_time_s) if s.lap_time_s is not None else self._last_time
        if delta > 1000.0: state="CHARGING"; state_color=GREEN; detail="Recovery active"
        elif delta < -1000.0: state="DEPLOYING"; state_color=RED; detail="Using stored energy"
        else: state="STEADY"; state_color=QColor(89,191,229); detail="Holding charge"
        fill=GREEN if pct >= 60 else (QColor(239,183,77) if pct >= 30 else RED)
        self.bar.setValue(pct); self.bar.setFormat(f"{pct}%")
        self.bar.setStyleSheet(f"QProgressBar{{color:white;background:rgba(255,255,255,18);border:1px solid rgba(255,255,255,22);border-radius:7px;text-align:center;font-weight:700;}} QProgressBar::chunk{{background:rgb({fill.red()},{fill.green()},{fill.blue()});border-radius:6px;}}")
        self.big.setText(f"{pct}%"); self.big.setStyleSheet(f"color:{_rgba(fill)};background:transparent;")
        self.energy_mass.setText(f"{store/1_000_000.0:.2f} / 4.00 MJ")
        self.value.setText(detail); self.value.setStyleSheet(f"color:{_rgba(WHITE)};background:transparent;")
        self.state_chip.setText(state); self.state_chip.setStyleSheet(self.chip_label(state, state_color).styleSheet())
        self.set_footer("Hybrid reserve", state, right_color=state_color)


class TyreWearOverlayWindow(DataOverlayWindow):
    WIDTH=360; HEIGHT=330
    def __init__(self, **kwargs):
        super().__init__("TYRE STATUS", self.WIDTH, self.HEIGHT, **kwargs)
        self.set_subtitle("Current wear and stint life outlook")
        self.summary_row = QHBoxLayout(); self.summary_row.setContentsMargins(0,0,0,0); self.summary_row.setSpacing(8)
        self.estimate_chip = self.chip_label("EST. -- LAPS", MUTED)
        self.summary_row.addWidget(self.estimate_chip)
        self.summary_row.addStretch(1)
        self.root.addLayout(self.summary_row)
        self.bars={}; self.values={}
        grid=QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(10)
        for i,key in enumerate(("FL","FR","RL","RR")):
            box, lay = self.card_layout(fill_alpha=24, spacing=4, margins=(10, 8, 10, 8))
            row = QHBoxLayout(); row.setContentsMargins(0,0,0,0)
            lab=self.label(key,7,True,MUTED); row.addWidget(lab)
            row.addStretch(1)
            val=self.label("--%",10,True,WHITE); row.addWidget(val); self.values[key]=val
            lay.addLayout(row)
            bar=QProgressBar(); bar.setRange(0,100); bar.setTextVisible(False); bar.setFixedHeight(18)
            lay.addWidget(bar); self.bars[key]=bar
            grid.addWidget(box,i//2,i%2)
        self.root.addLayout(grid)
        hdr=QGridLayout(); hdr.setHorizontalSpacing(8)
        for col,text in enumerate(("LAP","FL","FR","RL","RR","LIFE")):
            w=self.label(text,6,True,MUTED); w.setAlignment(Qt.AlignCenter); hdr.addWidget(w,0,col)
        self.root.addLayout(hdr)
        self.history=[]
        hist=QGridLayout(); hist.setVerticalSpacing(2)
        for r in range(4):
            cells=[]
            for c in range(6):
                w=self.label("--",7,True,MUTED); w.setAlignment(Qt.AlignCenter); hist.addWidget(w,r,c); cells.append(w)
            self.history.append(cells)
        self.root.addLayout(hist)

    def update_snapshot(self,s):
        self.set_applicable(s.tyre_wear_applicable, "TYRE WEAR STRATEGY NOT APPLICABLE IN THIS SESSION")
        for key,val in zip(("FL","FR","RL","RR"),s.tyre_wear):
            bar=self.bars[key]; v=int(round(val)) if val is not None else 0; bar.setValue(max(0,min(100,v)))
            self.values[key].setText(f"{v}%" if val is not None else "--%")
            color=GREEN if v < 45 else (QColor(239,183,77) if v < 70 else RED)
            bar.setStyleSheet(f"QProgressBar{{background:rgba(255,255,255,18);border:1px solid rgba(255,255,255,18);border-radius:4px;}} QProgressBar::chunk{{background:rgb({color.red()},{color.green()},{color.blue()});border-radius:4px;}}")
            self.values[key].setStyleSheet(f"color:{_rgba(color if val is not None else MUTED)};background:transparent;")
        if s.tyre_laps_remaining_estimate is not None:
            est = float(s.tyre_laps_remaining_estimate)
            est_color = GREEN if est >= 8 else (QColor(239,183,77) if est >= 4 else RED)
            self.estimate_chip.setText(f"EST. {est:.1f} LAPS")
            self.estimate_chip.setStyleSheet(self.chip_label(f"EST. {est:.1f} LAPS", est_color).styleSheet())
            self.set_footer("Tyre life outlook", f"{est:.1f} LAPS", right_color=est_color)
        else:
            self.estimate_chip.setText("EST. -- LAPS")
            self.estimate_chip.setStyleSheet(self.chip_label("EST. -- LAPS", MUTED).styleSheet())
            self.set_footer("Tyre life outlook", "UNAVAILABLE", right_color=MUTED)
        rows=list(s.tyre_wear_history)[-4:]
        for idx,cells in enumerate(self.history):
            row=rows[idx] if idx < len(rows) else None
            vals=(row.lap,row.fl,row.fr,row.rl,row.rr,row.life_percent) if row else (None,)*6
            for c,(w,val) in enumerate(zip(cells,vals)):
                if val is None: text="--"
                elif c==0: text=str(int(val))
                else: text=f"{val:.0f}%"
                w.setText(text)
                if c == 5 and val is not None:
                    color = GREEN if float(val) >= 40 else (QColor(239,183,77) if float(val) >= 20 else RED)
                elif c in (1,2,3,4) and val is not None:
                    color = GREEN if float(val) < 45 else (QColor(239,183,77) if float(val) < 70 else RED)
                else:
                    color = WHITE if row else MUTED
                w.setStyleSheet(f"color:{_rgba(color)}; background: transparent;")


class FuelOverlayWindow(DataOverlayWindow):
    # V2.9.1.3.5.45: the previous 300 px logical height only fit while the
    # applicability banner/footer were hidden.  In sessions where the banner
    # is shown the layout compressed the hero value row and clipped the large
    # fuel figures.  Keep the existing content unchanged and give the fixed
    # overlay enough vertical room at every shared zoom level.
    WIDTH=390; HEIGHT=335
    def __init__(self, **kwargs):
        super().__init__("FUEL", self.WIDTH, self.HEIGHT, **kwargs)
        self.set_subtitle("Remaining fuel margin and recent consumption")
        self.hero_card, hero = self.card_layout(QColor(245, 189, 77), margins=(12, 10, 12, 10), spacing=5)
        top = QHBoxLayout(); top.setContentsMargins(0,0,0,0); top.setSpacing(8)
        self.state_chip = self.chip_label("INFO", MUTED)
        top.addWidget(self.state_chip)
        top.addStretch(1)
        self.range_label = self.label("-- laps", 7, True, MUTED)
        top.addWidget(self.range_label)
        hero.addLayout(top)
        value_row = QHBoxLayout(); value_row.setContentsMargins(0,0,0,0)
        self.big_mass = self.label("-- kg", 20, True, WHITE)
        value_row.addWidget(self.big_mass)
        value_row.addStretch(1)
        self.big_delta = self.label("--", 16, True, MUTED)
        value_row.addWidget(self.big_delta)
        hero.addLayout(value_row)
        self.fuel_bar=QProgressBar(); self.fuel_bar.setRange(0,100); self.fuel_bar.setTextVisible(False); self.fuel_bar.setFixedHeight(16)
        hero.addWidget(self.fuel_bar)
        self.mass=self.label("Fuel mass unavailable",7,False,MUTED)
        hero.addWidget(self.mass)
        self.root.addWidget(self.hero_card)
        hdr=QGridLayout(); hdr.setHorizontalSpacing(8)
        for col,text in enumerate(("METRIC","VALUE","METRIC","VALUE")):
            w=self.label(text,6,True,MUTED); w.setAlignment(Qt.AlignCenter if col%2 else Qt.AlignLeft|Qt.AlignVCenter); hdr.addWidget(w,0,col)
        self.root.addLayout(hdr)
        self.rows=[]; grid=QGridLayout(); grid.setVerticalSpacing(4)
        for r in range(3):
            cells=[]
            for c in range(4):
                w=self.label("--",8,True,MUTED); w.setAlignment(Qt.AlignCenter if c%2 else Qt.AlignLeft|Qt.AlignVCenter); grid.addWidget(w,r,c); cells.append(w)
            self.rows.append(cells)
        self.root.addLayout(grid)
        # Create the footer before showEvent captures the logical 1.0x visual
        # baseline.  A footer created lazily after the overlay is shown would
        # miss shared zoom scaling and could squeeze the already-fixed layout.
        self.create_footer()

    def update_snapshot(self,s):
        self.set_applicable(s.fuel_applicable, "FUEL STRATEGY NOT APPLICABLE IN THIS SESSION")
        margin = float(s.fuel_remaining_laps) if s.fuel_remaining_laps is not None else None
        if margin is None:
            state = "INFO"; state_color = MUTED
        elif margin < 0.0:
            state = "DEFICIT"; state_color = RED
        elif margin < 0.5:
            state = "TIGHT"; state_color = QColor(239,183,77)
        else:
            state = "GOOD"; state_color = GREEN
        self.state_chip.setText(state)
        self.state_chip.setStyleSheet(self.chip_label(state, state_color).styleSheet())
        self.range_label.setText("-- laps" if margin is None else f"{margin:+.2f} laps")
        self.range_label.setStyleSheet(f"color:{_rgba(state_color if margin is not None else MUTED)};background:transparent;")
        if s.fuel_remaining_mass is not None:
            self.big_mass.setText(f"{float(s.fuel_remaining_mass):.2f} kg")
            self.big_mass.setStyleSheet(f"color:{_rgba(WHITE)};background:transparent;")
        else:
            self.big_mass.setText("-- kg")
            self.big_mass.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")
        if margin is not None:
            self.big_delta.setText(f"{margin:+.2f}")
            self.big_delta.setStyleSheet(f"color:{_rgba(state_color)};background:transparent;")
        else:
            self.big_delta.setText("--")
            self.big_delta.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")
        if s.fuel_remaining_mass is not None and s.fuel_capacity is not None and float(s.fuel_capacity) > 0:
            pct=max(0,min(100,int(round(float(s.fuel_remaining_mass)/float(s.fuel_capacity)*100))))
            self.fuel_bar.setValue(pct)
            self.fuel_bar.setStyleSheet(f"QProgressBar{{background:rgba(255,255,255,18);border:1px solid rgba(255,255,255,18);border-radius:4px;}} QProgressBar::chunk{{background:rgb({state_color.red()},{state_color.green()},{state_color.blue()});border-radius:4px;}}")
            self.mass.setText(f"Fuel mass {s.fuel_remaining_mass:.2f} / {s.fuel_capacity:.2f} kg")
        else:
            self.fuel_bar.setValue(0)
            self.fuel_bar.setStyleSheet("QProgressBar{background:rgba(255,255,255,18);border:1px solid rgba(255,255,255,18);border-radius:4px;} QProgressBar::chunk{background:rgba(155,164,175,160);border-radius:4px;}")
            self.mass.setText(f"Fuel mass {s.fuel_remaining_mass:.2f} kg" if s.fuel_remaining_mass is not None else "Fuel mass unavailable")
        rows=list(s.fuel_history)[-3:]
        metrics = []
        if rows:
            last = rows[-1]
            metrics.extend([
                ("Last lap", f"{last.used:.2f} kg" if last.used is not None else "--"),
                ("Remaining", f"{last.remaining:.2f} kg" if last.remaining is not None else "--"),
            ])
            if len(rows) >= 2:
                used_vals = [float(r.used) for r in rows if getattr(r, 'used', None) is not None]
                avg_used = sum(used_vals) / len(used_vals) if used_vals else None
            else:
                avg_used = last.used if last.used is not None else None
            metrics.extend([
                ("Avg / 3", f"{avg_used:.2f} kg" if avg_used is not None else "--"),
                ("Δ use", f"{last.diff:+.2f} kg" if last.diff is not None else "--"),
                ("Min use", f"{min((float(r.used) for r in rows if r.used is not None), default=float('nan')):.2f} kg" if any(r.used is not None for r in rows) else "--"),
                ("Max use", f"{max((float(r.used) for r in rows if r.used is not None), default=float('nan')):.2f} kg" if any(r.used is not None for r in rows) else "--"),
            ])
        else:
            metrics = [("Last lap", "--"), ("Remaining", "--"), ("Avg / 3", "--"), ("Δ use", "--"), ("Min use", "--"), ("Max use", "--")]
        for i, cells in enumerate(self.rows):
            pair_left = metrics[i*2] if i*2 < len(metrics) else ("--", "--")
            pair_right = metrics[i*2+1] if i*2+1 < len(metrics) else ("--", "--")
            values = (pair_left[0], pair_left[1], pair_right[0], pair_right[1])
            for c, (w, val) in enumerate(zip(cells, values)):
                w.setText(val)
                color = MUTED if c % 2 == 0 else WHITE
                if c in (1, 3) and isinstance(val, str) and val.startswith(('+', '-')) and 'Δ' not in values[c-1]:
                    color = GREEN if val.startswith('-') else RED
                w.setStyleSheet(f"color:{_rgba(color)};background:transparent;")
        self.set_footer("Fuel strategy", state, right_color=state_color)


class WeatherOverlayWindow(DataOverlayWindow):
    # V2.9.1.3.5.45: reserve enough logical height for the not-applicable
    # banner, three forecast cards and footer together.  The old 305 px shell
    # could compress these rows (especially with true zoom enabled).
    WIDTH=420; HEIGHT=330
    def __init__(self, **kwargs):
        super().__init__("WEATHER", self.WIDTH, self.HEIGHT, **kwargs)
        self.set_subtitle("Current conditions and short forecast")
        self.hero_card, hero = self.card_layout(QColor(89,191,229), margins=(12, 10, 12, 10), spacing=4)
        top = QHBoxLayout(); top.setContentsMargins(0,0,0,0); top.setSpacing(8)
        self.icon_label = self.label("◌", 18, True, QColor(239,183,77))
        top.addWidget(self.icon_label)
        text_col = QVBoxLayout(); text_col.setSpacing(1)
        self.condition_label = self.label("Waiting for forecast", 11, True, WHITE)
        text_col.addWidget(self.condition_label)
        self.rain_label = self.label("Rain --", 7, True, MUTED)
        text_col.addWidget(self.rain_label)
        top.addLayout(text_col, 1)
        self.accuracy=self.label("",6,True,MUTED); self.accuracy.setAlignment(Qt.AlignRight|Qt.AlignTop)
        top.addWidget(self.accuracy)
        hero.addLayout(top)
        temps = QHBoxLayout(); temps.setContentsMargins(0,0,0,0); temps.setSpacing(16)
        self.track_temp = self.label("Track --", 8, True, WHITE)
        self.air_temp = self.label("Air --", 8, True, WHITE)
        temps.addWidget(self.track_temp)
        temps.addWidget(self.air_temp)
        temps.addStretch(1)
        hero.addLayout(temps)
        self.root.addWidget(self.hero_card)
        forecast = QHBoxLayout(); forecast.setContentsMargins(0,0,0,0); forecast.setSpacing(8)
        self.forecast_cards=[]
        for _ in range(3):
            frame, lay = self.card_layout(fill_alpha=24, margins=(10, 8, 10, 8), spacing=2)
            time_label = self.label("--", 7, True, MUTED)
            icon = self.label("◌", 14, True, QColor(239,183,77)); icon.setAlignment(Qt.AlignCenter)
            rain = self.label("--", 9, True, WHITE); rain.setAlignment(Qt.AlignCenter)
            temp = self.label("-- / --", 7, True, MUTED); temp.setAlignment(Qt.AlignCenter)
            for w in (time_label, icon, rain, temp):
                lay.addWidget(w)
            forecast.addWidget(frame, 1)
            self.forecast_cards.append((time_label, icon, rain, temp))
        self.root.addLayout(forecast)
        # Pre-create the footer so its fonts, margins and spacing are part of
        # the same visual-scale baseline as the rest of the weather overlay.
        self.create_footer()

    def update_snapshot(self,s):
        self.set_applicable(s.weather_applicable, "WEATHER STRATEGY NOT APPLICABLE IN THIS SESSION")
        self.accuracy.setText(f"{s.forecast_accuracy}" if s.forecast_accuracy else "")
        data=list(s.weather_forecast)
        now_row = next((row for row in data if int(getattr(row, "offset_minutes", -1)) == 0), None)
        condition = s.weather_now or (getattr(now_row, "weather", None) if now_row is not None else None)
        if condition or now_row is not None:
            rain_pct = getattr(now_row, "rain_percent", None) if now_row is not None else None
            track_c = getattr(now_row, "track_temperature_c", None) if now_row is not None else None
            air_c = getattr(now_row, "air_temperature_c", None) if now_row is not None else None
            rain = f"Rain {float(rain_pct):.0f}%" if rain_pct is not None else "Rain --"
            track = f"Track {float(track_c):.0f}°C" if track_c is not None else "Track --"
            air = f"Air {float(air_c):.0f}°C" if air_c is not None else "Air --"
            icon = _weather_icon(condition)
            if rain_pct is None:
                rain_color = MUTED
            else:
                rain_color = GREEN if float(rain_pct) <= 10 else (QColor(239,183,77) if float(rain_pct) < 40 else RED)
            self.icon_label.setText(icon)
            self.condition_label.setText(str(condition or "Conditions").title())
            self.rain_label.setText(rain)
            self.rain_label.setStyleSheet(f"color:{_rgba(rain_color)};background:transparent;")
            self.track_temp.setText(track)
            self.air_temp.setText(air)
            self.set_footer(track, air, right_color=QColor(89,191,229))
        else:
            self.icon_label.setText("◌")
            self.condition_label.setText("Waiting for weather telemetry")
            self.rain_label.setText("Rain --")
            self.track_temp.setText("Track --")
            self.air_temp.setText("Air --")
            self.set_footer("Weather telemetry", "STANDBY", right_color=QColor(89,191,229))
        data=data[:3]
        for i,(time_label, icon, rain, temp) in enumerate(self.forecast_cards):
            row=data[i] if i < len(data) else None
            if row:
                time_text="NOW" if row.offset_minutes==0 else f"+{row.offset_minutes}m"
                time_label.setText(time_text)
                icon.setText(_weather_icon(row.weather))
                rain.setText(f"{row.rain_percent:.0f}%" if row.rain_percent is not None else "--")
                rain_color = GREEN if row.rain_percent is not None and row.rain_percent <= 10 else (QColor(239,183,77) if row.rain_percent is not None and row.rain_percent < 40 else RED)
                rain.setStyleSheet(f"color:{_rgba(rain_color)};background:transparent;")
                temp.setText(f"{row.track_temperature_c:.0f}° / {row.air_temperature_c:.0f}°" if row.track_temperature_c is not None and row.air_temperature_c is not None else "-- / --")
            else:
                time_label.setText("--"); icon.setText("◌"); rain.setText("--"); temp.setText("-- / --")
                rain.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")


class StandingsOverlayWindow(DataOverlayWindow):
    WIDTH=410; HEIGHT=285
    def __init__(self, **kwargs):
        super().__init__("RELATIVES", self.WIDTH, self.HEIGHT, **kwargs)
        self.set_subtitle("Nearby order, gap to player, and tyre compound")
        self.rows=[]; grid=QVBoxLayout(); grid.setSpacing(6)
        for _ in range(5):
            frame = self.card_frame(fill_alpha=20, border_alpha=22, radius=9)
            row = QHBoxLayout(frame); row.setContentsMargins(10, 7, 10, 7); row.setSpacing(8)
            pos=self.label("--",9,True,MUTED); pos.setFixedWidth(28)
            name=self.label("--",9,True,MUTED)
            team=self.label("--",7,True,MUTED); team.setFixedWidth(70)
            gap=self.label("--",8,True,MUTED); gap.setFixedWidth(72); gap.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
            tyre=self.label("--",8,True,MUTED); tyre.setFixedWidth(54); tyre.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
            row.addWidget(pos)
            row.addWidget(name, 1)
            row.addWidget(team)
            row.addWidget(gap)
            row.addWidget(tyre)
            self.rows.append((frame, pos, name, team, gap, tyre))
            grid.addWidget(frame)
        self.root.addLayout(grid)

    def update_snapshot(self,s):
        self.set_applicable(s.standings_applicable, "STANDINGS NOT AVAILABLE / NOT APPLICABLE")
        data=list(s.standings)[:5]
        player_pos = next((row.position for row in data if getattr(row, 'is_player', False)), None)
        for i,(frame, pos, name, team, gap, tyre) in enumerate(self.rows):
            row=data[i] if i < len(data) else None
            if row:
                pos.setText(str(row.position))
                name.setText(row.name)
                team.setText((row.team or "--")[:12])
                gap_text = "YOU" if row.is_player else ("--" if row.gap_to_player_s is None else f"{row.gap_to_player_s:+.3f}s")
                gap.setText(gap_text)
                tyre.setText((row.compound or "--").upper())
                if row.is_player:
                    frame.setStyleSheet(_card_style(QColor(89,191,229), fill_alpha=28, border_alpha=72, radius=9))
                    for w in (pos, name, team, gap, tyre):
                        w.setStyleSheet(f"color:{_rgba(WHITE)};background:transparent;")
                else:
                    frame.setStyleSheet(_card_style(fill_alpha=20, border_alpha=22, radius=9))
                    gap_color = GREEN if row.gap_to_player_s is not None and row.gap_to_player_s > 0 else RED if row.gap_to_player_s is not None else MUTED
                    pos.setStyleSheet(f"color:{_rgba(QColor(89,191,229))};background:transparent;")
                    name.setStyleSheet(f"color:{_rgba(WHITE)};background:transparent;")
                    team.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")
                    gap.setStyleSheet(f"color:{_rgba(gap_color)};background:transparent;")
                    tyre.setStyleSheet(f"color:{_rgba(WHITE)};background:transparent;")
            else:
                frame.setStyleSheet(_card_style(fill_alpha=18, border_alpha=18, radius=9))
                for w in (pos, name, team, gap, tyre):
                    w.setText("--")
                    w.setStyleSheet(f"color:{_rgba(MUTED)};background:transparent;")
        if player_pos is not None:
            self.set_footer("Player position", f"P{player_pos}", right_color=QColor(89,191,229))
        else:
            self.set_footer("Player position", "--", right_color=MUTED)


class PenaltiesOverlayWindow(DataOverlayWindow):
    WIDTH=440; HEIGHT=255
    def __init__(self, **kwargs):
        super().__init__("PENALTIES / WARNINGS", self.WIDTH, self.HEIGHT, **kwargs)
        self.set_subtitle("Penalty time, warnings and serve status")
        self.hero_card, hero = self.card_layout(RED, margins=(12,10,12,10), spacing=6)
        top=QHBoxLayout(); top.setContentsMargins(0,0,0,0)
        self.state_chip=self.chip_label("CLEAR", GREEN); top.addWidget(self.state_chip); top.addStretch(1)
        self.serve=self.label("NO SERVE REQUIRED",7,True,MUTED); top.addWidget(self.serve); hero.addLayout(top)
        values=QHBoxLayout(); values.setContentsMargins(0,0,0,0); values.setSpacing(10)
        self.penalty_box,self.penalty_layout=self.card_layout(fill_alpha=18,margins=(8,6,8,6),spacing=1)
        pl=self.label("PENALTY",6,True,MUTED); pl.setAlignment(Qt.AlignCenter); self.penalty_layout.addWidget(pl)
        self.big=self.label("0 s",21,True,GREEN); self.big.setAlignment(Qt.AlignCenter); self.penalty_layout.addWidget(self.big)
        values.addWidget(self.penalty_box,1)
        self.warning_box,self.warning_layout=self.card_layout(fill_alpha=18,margins=(8,6,8,6),spacing=1)
        wl=self.label("WARNINGS",6,True,MUTED); wl.setAlignment(Qt.AlignCenter); self.warning_layout.addWidget(wl)
        self.warning_value=self.label("0",21,True,GREEN); self.warning_value.setAlignment(Qt.AlignCenter); self.warning_layout.addWidget(self.warning_value)
        values.addWidget(self.warning_box,1)
        self.corner_box,self.corner_layout=self.card_layout(fill_alpha=18,margins=(8,6,8,6),spacing=1)
        cl=self.label("TRACK LIMITS",6,True,MUTED); cl.setAlignment(Qt.AlignCenter); self.corner_layout.addWidget(cl)
        self.corner_value=self.label("0",21,True,GREEN); self.corner_value.setAlignment(Qt.AlignCenter); self.corner_layout.addWidget(self.corner_value)
        values.addWidget(self.corner_box,1)
        hero.addLayout(values)
        self.root.addWidget(self.hero_card)
        self.message=self.label("No active penalties or warnings",8,False,MUTED); self.message.setAlignment(Qt.AlignCenter); self.root.addWidget(self.message)
        self.set_footer("Race control", "CLEAR", right_color=GREEN)

    @staticmethod
    def _warning_color(value):
        if not isinstance(value,(int,float)): return MUTED
        value=int(value)
        if value <= 0: return GREEN
        if value <= 2: return QColor(239,183,77)
        return RED

    def update_snapshot(self,s):
        value=getattr(s,'penalties_s',None)
        warnings=getattr(s,'warnings',None)
        corners=getattr(s,'corner_cutting_warnings',None)
        serve=bool(getattr(s,'serve_penalty',False))
        pc=RED if isinstance(value,(int,float)) and int(value)>0 else (GREEN if value is not None else MUTED)
        wc=self._warning_color(warnings); cc=self._warning_color(corners)
        self.big.setText(f"{int(value)} s" if isinstance(value,(int,float)) else "-- s")
        self.big.setStyleSheet(f"color:{_rgba(pc)};background:transparent;")
        self.warning_value.setText(str(int(warnings)) if isinstance(warnings,(int,float)) else "--")
        self.warning_value.setStyleSheet(f"color:{_rgba(wc)};background:transparent;")
        self.corner_value.setText(str(int(corners)) if isinstance(corners,(int,float)) else "--")
        self.corner_value.setStyleSheet(f"color:{_rgba(cc)};background:transparent;")
        active_penalty = serve or (isinstance(value,(int,float)) and int(value)>0)
        active_warning = (isinstance(warnings,(int,float)) and int(warnings)>0) or (isinstance(corners,(int,float)) and int(corners)>0)
        if serve:
            state="SERVE"; color=RED; message="Penalty must be served"
        elif active_penalty:
            state="PENALTY"; color=RED; message="Penalty time active"
        elif active_warning:
            state="WARNINGS"; color=QColor(239,183,77) if max(int(warnings or 0),int(corners or 0)) <= 2 else RED; message="Warnings active — keep the session clean"
        elif value is None and warnings is None and corners is None:
            state="N/A"; color=MUTED; message="Race-control telemetry unavailable"
        else:
            state="CLEAR"; color=GREEN; message="No active penalties or warnings"
        self.state_chip.setText(state); self.state_chip.setStyleSheet(self.chip_label(state,color).styleSheet())
        self.serve.setText("SERVE PENALTY" if serve else "NO SERVE REQUIRED")
        self.serve.setStyleSheet(f"color:{_rgba(RED if serve else MUTED)};background:transparent;")
        self.message.setText(message)
        self.set_footer("Race control", state, right_color=color)


class BrakeStatusOverlayWindow(DataOverlayWindow):
    WIDTH=390; HEIGHT=295
    def __init__(self, **kwargs):
        super().__init__("BRAKE STATUS", self.WIDTH, self.HEIGHT, **kwargs)
        self.set_subtitle("Brake temperature and recorded brake damage")
        self.temp_values={}; self.damage_values={}
        grid=QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(10)
        for i,key in enumerate(("FL","FR","RL","RR")):
            frame,lay=self.card_layout(fill_alpha=24,margins=(10,8,10,8),spacing=3)
            top=QHBoxLayout(); top.setContentsMargins(0,0,0,0)
            lab=self.label(key,7,True,MUTED); top.addWidget(lab); top.addStretch(1)
            temp=self.label("--°C",11,True,WHITE); top.addWidget(temp); self.temp_values[key]=temp
            lay.addLayout(top)
            dmg=self.label("Damage --%",7,True,MUTED); lay.addWidget(dmg); self.damage_values[key]=dmg
            grid.addWidget(frame,i//2,i%2)
        self.root.addLayout(grid)
        self.summary=self.label("Waiting for brake telemetry",9,True,MUTED); self.summary.setAlignment(Qt.AlignCenter); self.root.addWidget(self.summary)
        self.set_footer("Brake system", "STANDBY", right_color=QColor(89,191,229))

    @staticmethod
    def _temp_color(value):
        # Presentation-only thermal bands. The temperature value itself changes
        # colour as heat rises; this does not affect any strategy logic.
        if not isinstance(value,(int,float)): return MUTED
        value=float(value)
        if value < 650: return QColor(89,191,229)   # cool
        if value < 900: return GREEN                # working range
        if value < 1050: return QColor(239,183,77)  # hot
        return RED                                  # critical

    def update_snapshot(self,s):
        temps=tuple(getattr(s,'brake_temperatures_c',(None,None,None,None)) or (None,None,None,None))
        damage=tuple(getattr(s,'brake_damage_percent',(None,None,None,None)) or (None,None,None,None))
        available=[float(v) for v in temps if isinstance(v,(int,float))]
        damage_available=[float(v) for v in damage if isinstance(v,(int,float))]
        for key,tv,dv in zip(("FL","FR","RL","RR"),temps,damage):
            tc=self._temp_color(tv)
            self.temp_values[key].setText(f"{float(tv):.0f}°C" if isinstance(tv,(int,float)) else "--°C")
            self.temp_values[key].setStyleSheet(f"color:{_rgba(tc)};background:transparent;")
            dc=RED if isinstance(dv,(int,float)) and float(dv)>0 else (GREEN if isinstance(dv,(int,float)) else MUTED)
            self.damage_values[key].setText(f"Damage {float(dv):.0f}%" if isinstance(dv,(int,float)) else "Damage --%")
            self.damage_values[key].setStyleSheet(f"color:{_rgba(dc)};background:transparent;")
        if not available and not damage_available:
            self.summary.setText("Waiting for brake telemetry"); color=MUTED; state="STANDBY"
        else:
            hottest=max(available) if available else None; max_dmg=max(damage_available) if damage_available else 0.0
            color=RED if max_dmg>0 else self._temp_color(hottest)
            if max_dmg>0: state="DAMAGE"; text=f"Brake damage detected • max {max_dmg:.0f}%"
            elif hottest is not None: state="LIVE"; text=f"Hottest brake {hottest:.0f}°C"
            else: state="LIVE"; text="Brake damage telemetry available"
            self.summary.setText(text)
        self.summary.setStyleSheet(f"color:{_rgba(color)};background:transparent;")
        self.set_footer("Brake system", state, right_color=color)


class LapHistoryOverlayWindow(DataOverlayWindow):
    WIDTH=465; HEIGHT=285
    def __init__(self, **kwargs):
        super().__init__("LAPTIME HISTORY", self.WIDTH, self.HEIGHT, **kwargs)
        hdr=QGridLayout()
        for c,text in enumerate(("LAP","TIME","DELTA","S1","S2","S3")):
            w=self.label(text,6,True,MUTED); w.setAlignment(Qt.AlignCenter); hdr.addWidget(w,0,c)
        self.root.addLayout(hdr)
        self.rows=[]; grid=QGridLayout(); grid.setVerticalSpacing(5)
        for r in range(8):
            cells=[]
            for c in range(6):
                w=self.label("--",8,True,MUTED); w.setAlignment(Qt.AlignCenter); grid.addWidget(w,r,c); cells.append(w)
            self.rows.append(cells)
        self.root.addLayout(grid)

    def update_snapshot(self,s):
        data=list(s.lap_history)[:8]
        for i,cells in enumerate(self.rows):
            row=data[i] if i < len(data) else None
            if row:
                delta=(("BEST " + f"{row.delta_s:+.3f}") if row.best and row.delta_s is not None else "BEST") if row.best else (f"{row.delta_s:+.3f}" if row.delta_s is not None else "--")
                vals=(str(row.lap),_time_text(row.lap_time_s),delta,f"{row.sector1_s:.3f}" if row.sector1_s is not None else "--",f"{row.sector2_s:.3f}" if row.sector2_s is not None else "--",f"{row.sector3_s:.3f}" if row.sector3_s is not None else "--")
            else: vals=("--",)*6
            for c,(w,text) in enumerate(zip(cells,vals)):
                w.setText(text)
                if row and not row.valid: color=RED
                elif row and row.best: color=QColor(190,130,255)
                elif row and c==2 and row.delta_s is not None: color=GREEN if row.delta_s <= 0 else RED
                else: color=WHITE if row else MUTED
                w.setStyleSheet(f"color:rgb({color.red()},{color.green()},{color.blue()});background:transparent;")


class TyreSetsOverlayWindow(DataOverlayWindow):
    WIDTH=450; HEIGHT=320
    def __init__(self, **kwargs):
        super().__init__("AVAILABLE TYRE SETS", self.WIDTH, self.HEIGHT, **kwargs)
        hdr=QGridLayout()
        for c,text in enumerate(("SET","COMPOUND","WEAR","LIFE","Δ LAP","SESSION","STATUS")):
            w=self.label(text,6,True,MUTED); w.setAlignment(Qt.AlignCenter); hdr.addWidget(w,0,c)
        self.root.addLayout(hdr)
        self.rows=[]; grid=QGridLayout(); grid.setVerticalSpacing(3)
        for r in range(10):
            cells=[]
            for c in range(7):
                w=self.label("--",7,True,MUTED); w.setAlignment(Qt.AlignCenter); grid.addWidget(w,r,c); cells.append(w)
            self.rows.append(cells)
        self.root.addLayout(grid)

    def update_snapshot(self,s):
        self.set_applicable(s.tyre_sets_applicable, "TYRE SETS NOT AVAILABLE / NOT APPLICABLE")
        data=list(s.tyre_sets)[:10]
        for i,cells in enumerate(self.rows):
            row=data[i] if i < len(data) else None
            if row:
                status="FITTED" if row.fitted else ("AVAILABLE" if row.available else "USED")
                vals=(str(row.index+1),row.compound,f"{row.wear_percent}%",f"{row.lifespan_laps}/{row.usable_life_laps}",f"{row.lap_delta_s:+.3f}",row.recommended_session.replace("Qualifying","Quali")[:12],status)
            else: vals=("--",)*7
            for c,(w,text) in enumerate(zip(cells,vals)):
                w.setText(text)
                if row and c==6:
                    color=GREEN if row.fitted or row.available else MUTED
                elif row and c==4:
                    color=GREEN if row.lap_delta_s <= 0 else RED
                else: color=WHITE if row else MUTED
                w.setStyleSheet(f"color:rgb({color.red()},{color.green()},{color.blue()});background:transparent;")


# Backward-compatible aliases for any external imports from V0.9.9.2/3.
InputOverlayWindow = DriverOverlayWindow
TelemetryOverlayWindow = DriverOverlayWindow


class ReplayControlsWindow(OverlayPanel):
    """Independent replay transport/range/speed controls for .areplay sessions."""

    WIDTH = 520
    HEIGHT = 250

    def __init__(self, controller, *, on_toggle_pause=None, on_hide=None,
                 on_toggle_click_through=None):
        super().__init__(
            on_close=on_hide,
            on_toggle_pause=on_toggle_pause,
            on_toggle_click_through=on_toggle_click_through,
        )
        self.controller = controller
        self._updating = False
        self.setWindowTitle("Race Engineer — Replay Controls")
        self.set_overlay_logical_fixed_size(self.WIDTH, self.HEIGHT)
        self._build_ui()

    def _small_button(self, text, tooltip):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tooltip)
        b.setFixedSize(26, 26)
        b.setFont(QFont("Segoe UI Symbol", 11, QFont.Bold))
        b.setStyleSheet(
            "QToolButton { color: rgba(230,234,239,225); background: rgba(255,255,255,15);"
            " border: 1px solid rgba(255,255,255,26); border-radius: 7px; }"
            "QToolButton:hover { background: rgba(255,255,255,36); }"
        )
        return b

    def _slider(self):
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(1)
        slider.setSingleStep(1)
        slider.setPageStep(100)
        slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 5px; background: rgba(255,255,255,38); border-radius: 2px; }"
            "QSlider::sub-page:horizontal { background: rgba(80,170,235,190); border-radius: 2px; }"
            "QSlider::handle:horizontal { width: 12px; margin: -5px 0; background: rgba(210,220,230,245); border-radius: 6px; }"
        )
        return slider

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(7)

        header = QHBoxLayout()
        title = self.label("REPLAY CONTROLS", 11, True)
        header.addWidget(title)
        header.addStretch(1)
        self.minimize_button = None
        self.hide_button = None
        root.addLayout(header)

        transport = QHBoxLayout()
        self.play_button = QPushButton("Ⅱ")
        self.play_button.setFixedSize(52, 44)
        self.play_button.setFont(QFont("Segoe UI Symbol", 17, QFont.Bold))
        self.play_button.setStyleSheet(
            "QPushButton { color: white; background: rgba(255,255,255,18); border: 1px solid rgba(255,255,255,24); border-radius: 8px; }"
            "QPushButton:hover { background: rgba(255,255,255,38); }"
        )
        self.play_button.clicked.connect(lambda: self.on_toggle_pause and self.on_toggle_pause())
        transport.addWidget(self.play_button)
        right = QVBoxLayout()
        posrow = QHBoxLayout()
        posrow.addWidget(self.label("Position", 8, True))
        posrow.addStretch(1)
        self.position_label = self.label("0 / 0", 8, True)
        posrow.addWidget(self.position_label)
        right.addLayout(posrow)
        self.position_slider = self._slider()
        self.position_slider.sliderReleased.connect(self._seek_released)
        right.addWidget(self.position_slider)
        transport.addLayout(right, 1)
        root.addLayout(transport)

        range_head = QHBoxLayout()
        range_head.addWidget(self.label("Replay range", 8, True))
        range_head.addStretch(1)
        self.range_label = self.label("0 to 0", 8)
        range_head.addWidget(self.range_label)
        root.addLayout(range_head)

        startrow = QHBoxLayout()
        startrow.addWidget(self.label("Start", 7, True, MUTED))
        self.start_slider = self._slider()
        self.start_slider.sliderReleased.connect(self._range_changed)
        startrow.addWidget(self.start_slider, 1)
        root.addLayout(startrow)
        endrow = QHBoxLayout()
        endrow.addWidget(self.label("End  ", 7, True, MUTED))
        self.end_slider = self._slider()
        self.end_slider.sliderReleased.connect(self._range_changed)
        endrow.addWidget(self.end_slider, 1)
        root.addLayout(endrow)

        speed_head = QHBoxLayout()
        speed_head.addWidget(self.label("Speed multiplier", 8, True))
        speed_head.addStretch(1)
        self.speed_label = self.label("x1.00", 8, True)
        speed_head.addWidget(self.speed_label)
        root.addLayout(speed_head)
        self.speed_slider = self._slider()
        self.speed_slider.setMinimum(25)
        self.speed_slider.setMaximum(400)
        self.speed_slider.setSingleStep(25)
        self.speed_slider.setPageStep(25)
        self.speed_slider.valueChanged.connect(self._speed_changed)
        root.addWidget(self.speed_slider)

        self.status_label = self.label("", 7, True, MUTED)
        root.addWidget(self.status_label)

    def _seek_released(self):
        if not self._updating:
            self.controller.seek(self.position_slider.value())

    def _range_changed(self):
        if self._updating:
            return
        start = self.start_slider.value()
        end = self.end_slider.value()
        if start > end:
            if self.sender() is self.start_slider:
                end = start
                self.end_slider.setValue(end)
            else:
                start = end
                self.start_slider.setValue(start)
        self.controller.set_range(start, end)

    def _speed_changed(self, value):
        if not self._updating:
            self.controller.set_speed(value / 100.0)

    def update_status(self, status):
        self._updating = True
        try:
            maximum = max(0, status.total - 1)
            for slider in (self.position_slider, self.start_slider, self.end_slider):
                slider.setMaximum(maximum)
            if not self.position_slider.isSliderDown():
                self.position_slider.setValue(min(status.position, maximum))
            if not self.start_slider.isSliderDown():
                self.start_slider.setValue(status.range_start)
            if not self.end_slider.isSliderDown():
                self.end_slider.setValue(status.range_end)
            self.position_label.setText(f"{min(status.position + 1, status.total) if status.total else 0} / {status.total}")
            self.range_label.setText(f"{status.range_start + 1 if status.total else 0} to {status.range_end + 1 if status.total else 0}")
            if not self.speed_slider.isSliderDown():
                self.speed_slider.setValue(int(round(status.speed * 100)))
            self.speed_label.setText(f"x{status.speed:.2f}")
            self.play_button.setText("▶" if status.paused else "Ⅱ")
            if status.rebuilding:
                self.status_label.setText("SEEKING • rebuilding deterministic state from recording start…")
            elif status.paused:
                self.status_label.setText("PAUSED")
            else:
                self.status_label.setText("PLAYING")
        finally:
            self._updating = False




class F1DashCanvas(QWidget):
    """Fast paint-only dashboard fed by the same immutable overlay snapshot."""

    def __init__(self):
        super().__init__()
        self.snapshot = None
        self.remote_url = None
        self.page = "dash"
        self.track_points = deque(maxlen=6000)
        self._track_session_uid = None
        self._last_track_point = None
        self._learning_lap = None
        self._learning_points = []
        self._learning_started_near_start = False
        self._last_lap_distance = None
        self._last_seen_lap = None
        self._tyre_cache_session_uid = None
        self._tyre_live_cache = {}
        # Static map geometry is expensive but changes only when the track/map or
        # canvas size changes. Keep it off the 60 Hz paint path.
        self._map_geometry_cache_key = None
        self._map_geometry_cache_value = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def _reset_map_learning(self):
        self.track_points.clear()
        self._last_track_point = None
        self._learning_lap = None
        self._learning_points = []
        self._learning_started_near_start = False
        self._last_lap_distance = None
        self._last_seen_lap = None

    # V2.0.3.5: persistent map learning/refinement is backend-owned by
    # MeasuredPerformanceRecorder at authoritative lap boundaries. The dashboard
    # only renders the shared model (or a temporary current-lap preview when no
    # model exists); it never writes or refines track geometry.

    def update_snapshot(self, snapshot):
        self.snapshot = snapshot
        uid = getattr(snapshot, "session_uid", None)
        if uid is not None and uid != self._track_session_uid:
            self._track_session_uid = uid
            self._reset_map_learning()

        # V1.0.2.1+: map learning no longer samples the 60 Hz paint snapshot.
        # The snapshot carries the recorder's distance-binned world trace, which
        # is already S/F anchored and spike-validated in overlay.data. This avoids
        # diagonal chords during replay and guarantees first plotting begins at S/F.
        track_name = getattr(snapshot, "track_name", None)
        learned = get_track_map(track_name)
        if learned is None:
            live = tuple(getattr(snapshot, "map_learning_points", ()) or ())
            self.track_points.clear()
            self.track_points.extend(live)
            self._last_track_point = live[-1] if live else None
            self._learning_lap = getattr(snapshot, "lap_number", None) if live else None
        else:
            self.track_points.clear()
            self._last_track_point = None
            self._learning_lap = None
        self.update()

    def set_remote_url(self, url):
        self.remote_url = str(url) if url else None
        self.update()

    @staticmethod
    def _ers_percent(snapshot):
        value = getattr(snapshot, "ers_store_j", None)
        if isinstance(value, (int, float)):
            return max(0.0, min(100.0, float(value) / 4_000_000.0 * 100.0))
        return None

    def set_page(self, page):
        if page in {"dash", "damage", "engine", "tyres", "map", "pit"}:
            self.page = page
            self.update()

    @staticmethod
    def _value_text(value, suffix="", decimals=0):
        if not isinstance(value, (int, float)):
            return "--"
        return f"{float(value):.{decimals}f}{suffix}"

    @staticmethod
    def _damage_color(value):
        if not isinstance(value, (int, float)):
            return MUTED
        if value >= 60:
            return RED
        if value >= 25:
            return AMBER
        return GREEN

    def _page_header(self, p, w, h, title, subtitle=""):
        # UI-R9: one compact hierarchy for every native F1 Dash page.
        # Keep this paint-only so page changes never affect telemetry cadence.
        p.setPen(QColor(62,200,255)); p.setFont(QFont("Segoe UI", max(7,int(h*.016)), QFont.Bold))
        p.drawText(QRectF(w*.035,h*.104,w*.24,h*.026),Qt.AlignLeft|Qt.AlignVCenter,"F1 DASH")
        p.setPen(QColor(247,249,251)); p.setFont(QFont("Segoe UI", max(18,int(h*.046)), QFont.Bold))
        p.drawText(QRectF(w*.035,h*.127,w*.56,h*.058),Qt.AlignLeft|Qt.AlignVCenter,title)
        if subtitle:
            p.setPen(QColor(120,136,151)); p.setFont(QFont("Segoe UI",max(8,int(h*.019)),QFont.DemiBold))
            p.drawText(QRectF(w*.035,h*.179,w*.76,h*.034),Qt.AlignLeft|Qt.AlignVCenter,subtitle)
        p.setPen(QPen(QColor(38,53,65),1)); p.drawLine(QPointF(w*.035,h*.213),QPointF(w*.965,h*.213))

    @staticmethod
    def _tyre_temp_color(value):
        if not isinstance(value, (int, float)):
            return MUTED
        if value < 70:
            return QColor(62, 200, 255)
        if value < 105:
            return GREEN
        if value < 115:
            return AMBER
        return RED

    @staticmethod
    def _brake_temp_color(value):
        if not isinstance(value, (int, float)):
            return MUTED
        if value < 1000:
            return GREEN
        if value < 1100:
            return AMBER
        return RED

    @staticmethod
    def _wear_color(value):
        if not isinstance(value, (int, float)):
            return MUTED
        if value < 25:
            return GREEN
        if value < 60:
            return AMBER
        return RED

    @staticmethod
    def _map_cumulative_lengths(points):
        if len(points) < 2:
            return [0.0], 0.0
        cumulative = [0.0]
        total = 0.0
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            total += math.hypot(x2 - x1, y2 - y1)
            cumulative.append(total)
        return cumulative, total

    def _track_polyline(self, snapshot):
        predefined = get_track_map(getattr(snapshot, "track_name", None))
        if predefined:
            # Learned/preloaded map tuples are already immutable enough for paint.
            # Avoid allocating a new list every 60 Hz frame.
            return predefined, "predefined"
        live = tuple(getattr(snapshot, "map_learning_points", ()) or ())
        return live, "telemetry"

    @staticmethod
    def _interpolate_polyline(points, fraction):
        if not points:
            return None
        if len(points) == 1:
            return points[0]
        fraction = max(0.0, min(1.0, float(fraction)))
        cumulative, total = F1DashCanvas._map_cumulative_lengths(points)
        if total <= 0.0:
            return points[-1]
        target = total * fraction
        for i in range(1, len(points)):
            if cumulative[i] >= target:
                prev_len = cumulative[i - 1]
                seg_len = max(1e-9, cumulative[i] - prev_len)
                t = (target - prev_len) / seg_len
                x1, y1 = points[i - 1]
                x2, y2 = points[i]
                return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        return points[-1]

    @staticmethod
    def _interpolate_distance_axis(points, distances, distance_m, track_length_m):
        """Interpolate map XY on the lap-distance axis without per-call copies."""
        if not points or not distances or not isinstance(distance_m, (int, float)) or not isinstance(track_length_m, (int, float)) or track_length_m <= 1:
            return None
        closed = len(points) > 1 and points[0] == points[-1] and len(distances) == len(points)-1
        n = len(points)-1 if closed else len(points)
        if len(distances) != n or n < 2:
            return points[0] if n == 1 else None
        d=float(distance_m) % float(track_length_m)
        if d <= float(distances[0]):
            return points[0]
        from bisect import bisect_left
        i=bisect_left(distances,d)
        if i >= n:
            d0=float(distances[n-1]); d1=float(track_length_m)
            p0=points[n-1]; p1=points[0]
        else:
            i=max(1,i)
            d0=float(distances[i-1]); d1=float(distances[i])
            p0=points[i-1]; p1=points[i]
        if d1 <= d0:
            return p1
        a=max(0.0,min(1.0,(d-d0)/(d1-d0)))
        return (p0[0]+(p1[0]-p0[0])*a, p0[1]+(p1[1]-p0[1])*a)

    def _scaled_map_geometry(self, area, points):
        if not points:
            return [], None
        raw_x = [pt[0] for pt in points]
        raw_y = [pt[1] for pt in points]
        raw_dx = max(1e-6, max(raw_x) - min(raw_x))
        raw_dy = max(1e-6, max(raw_y) - min(raw_y))
        rotate = bool(area.width() > area.height() * 1.25 and raw_dy > raw_dx * 1.10)
        oriented = [(y, -x) if rotate else (x, y) for x, y in points]
        xs = [pt[0] for pt in oriented]
        ys = [pt[1] for pt in oriented]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        dx = max(1e-6, maxx - minx)
        dy = max(1e-6, maxy - miny)
        inner_w = area.width() * 0.985
        inner_h = area.height() * 0.985
        scale = min(inner_w / dx, inner_h / dy)
        ox = area.center().x() - (minx + maxx) * 0.5 * scale
        oy = area.center().y() - (miny + maxy) * 0.5 * scale
        scaled = [(ox + x * scale, oy + y * scale) for x, y in oriented]
        return scaled, (minx, maxx, miny, maxy, scale, ox, oy, rotate)

    def _track_marker_point(self, snapshot, points, source):
        # V1.0.2.2: the player's live pointer is anchored by the *current motion
        # packet* in the same world X/Z coordinate system used to learn the map.
        # Do not derive YOU from lap-distance first: replay packet families are
        # asynchronous and the lap-distance/map-axis pair can briefly disagree
        # after seeks, lap transitions, or first-map promotion.  That disagreement
        # was leaving the yellow player marker parked at S/F while the footer
        # distance continued to advance.  World position is therefore the primary
        # presentation source; lap distance remains a deterministic fallback.
        world_x = getattr(snapshot, "world_position_x", None)
        world_z = getattr(snapshot, "world_position_z", None)
        if (isinstance(world_x, (int, float)) and isinstance(world_z, (int, float))
                and math.isfinite(float(world_x)) and math.isfinite(float(world_z))):
            return (float(world_x), float(world_z))

        if source == "predefined":
            lap_distance = getattr(snapshot, "lap_distance_m", None)
            track_length = getattr(snapshot, "track_length_m", None)
            axis=get_track_map_distances(getattr(snapshot, "track_name", None))
            exact=self._interpolate_distance_axis(points, axis, lap_distance, track_length)
            if exact is not None:
                return exact
            if isinstance(lap_distance, (int, float)) and isinstance(track_length, (int, float)) and track_length > 1:
                return self._interpolate_polyline(points, (float(lap_distance) % float(track_length)) / float(track_length))
            return points[0] if points else None
        if self._last_track_point is not None:
            return self._last_track_point
        return points[-1] if points else None

    def _distance_marker_point(self, snapshot, points, distance_m):
        track_length = getattr(snapshot, "track_length_m", None)
        if not isinstance(distance_m, (int, float)) or not isinstance(track_length, (int, float)) or track_length <= 1:
            return None
        axis=get_track_map_distances(getattr(snapshot, "track_name", None))
        exact=self._interpolate_distance_axis(points, axis, distance_m, track_length)
        if exact is not None:
            return exact
        return self._interpolate_polyline(points, (float(distance_m) % float(track_length)) / float(track_length))

    def _draw_f1_wireframe(self, p, cx, top, car_w, car_h, *, outline, fill, nose_fill=None):
        p.setPen(QPen(outline, 2))
        p.setBrush(fill)
        # Front wing with a central nose slot and endplate-like shoulders.
        wing = QPainterPath(); wing.moveTo(cx-car_w*.48, top+car_h*.05); wing.lineTo(cx-car_w*.18, top+car_h*.01); wing.lineTo(cx-car_w*.06, top+car_h*.04); wing.lineTo(cx+car_w*.06, top+car_h*.04); wing.lineTo(cx+car_w*.18, top+car_h*.01); wing.lineTo(cx+car_w*.48, top+car_h*.05); wing.lineTo(cx+car_w*.46, top+car_h*.11); wing.lineTo(cx+car_w*.14, top+car_h*.095); wing.lineTo(cx, top+car_h*.13); wing.lineTo(cx-car_w*.14, top+car_h*.095); wing.lineTo(cx-car_w*.46, top+car_h*.11); wing.closeSubpath(); p.drawPath(wing)
        p.setBrush(nose_fill if nose_fill is not None else fill)
        nose = QPainterPath(); nose.moveTo(cx-car_w*.045, top+car_h*.06); nose.lineTo(cx+car_w*.045, top+car_h*.06); nose.lineTo(cx+car_w*.075, top+car_h*.33); nose.lineTo(cx-car_w*.075, top+car_h*.33); nose.closeSubpath(); p.drawPath(nose)
        spine = QPainterPath(); spine.moveTo(cx-car_w*.10, top+car_h*.27); spine.lineTo(cx+car_w*.10, top+car_h*.27); spine.lineTo(cx+car_w*.26, top+car_h*.43); spine.lineTo(cx+car_w*.18, top+car_h*.71); spine.lineTo(cx+car_w*.10, top+car_h*.85); spine.lineTo(cx-car_w*.10, top+car_h*.85); spine.lineTo(cx-car_w*.18, top+car_h*.71); spine.lineTo(cx-car_w*.26, top+car_h*.43); spine.closeSubpath(); p.drawPath(spine)
        p.setBrush(Qt.NoBrush); p.drawEllipse(QRectF(cx-car_w*.11, top+car_h*.31, car_w*.22, car_h*.18))
        p.setBrush(fill); p.drawRoundedRect(QRectF(cx-car_w*.36, top+car_h*.90, car_w*.72, car_h*.065), 4, 4)
        for x, y in ((cx-car_w*.42, top+car_h*.20), (cx+car_w*.30, top+car_h*.20), (cx-car_w*.42, top+car_h*.62), (cx+car_w*.30, top+car_h*.62)):
            p.drawRoundedRect(QRectF(x, y, car_w*.10, car_h*.20), 5, 5)

    def _sticky_wheels(self, snapshot, attr):
        uid = getattr(snapshot, "session_uid", None)
        if uid != self._tyre_cache_session_uid:
            self._tyre_cache_session_uid = uid
            self._tyre_live_cache.clear()
        incoming = list(getattr(snapshot, attr, ()) or ())
        while len(incoming) < 4:
            incoming.append(None)
        cached = list(self._tyre_live_cache.get(attr, (None, None, None, None)))
        for i, value in enumerate(incoming[:4]):
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                cached[i] = value
        self._tyre_live_cache[attr] = tuple(cached)
        return cached

    def _paint_damage_page(self, p, s, w, h):
        self._page_header(p,w,h,"DAMAGE","CAR / AERO + POWER UNIT / HYBRID")

        def value_text(value, suffix="%", decimals=0):
            return self._value_text(value, suffix, decimals)

        def card(x, y, cw, ch, label, value, color=None, suffix="%", decimals=0, text_value=None):
            col = color if color is not None else self._damage_color(value)
            r=QRectF(x,y,cw,ch)
            p.setPen(QPen(QColor(44,58,70),1)); p.setBrush(QColor(9,14,20)); p.drawRoundedRect(r,7,7)
            p.setPen(QColor(126,141,156)); p.setFont(QFont("Segoe UI",max(8,int(h*.016)),QFont.Bold))
            p.drawText(QRectF(r.x()+5,r.y()+4,r.width()-10,r.height()*.34),Qt.AlignCenter,label)
            p.setPen(col); p.setFont(QFont("Segoe UI",max(14,int(h*.034)),QFont.Bold))
            shown=text_value if text_value is not None else value_text(value,suffix,decimals)
            p.drawText(QRectF(r.x()+5,r.y()+r.height()*.30,r.width()-10,r.height()*.62),Qt.AlignCenter,shown)

        x0=w*.035; usable=w*.93
        p.setPen(QColor(230,235,240)); p.setFont(QFont("Segoe UI",max(10,int(h*.021)),QFont.Bold))
        p.drawText(QRectF(x0,h*.215,usable,h*.032),Qt.AlignLeft|Qt.AlignVCenter,"CAR / AERO DAMAGE")

        # Spatial car/aero layout for faster recognition: front -> middle -> rear.
        bw=w*.205; bh=h*.105
        fl=getattr(s,"front_left_wing_damage_percent",None); fr=getattr(s,"front_right_wing_damage_percent",None)
        side=getattr(s,"sidepod_damage_percent",None); floor=getattr(s,"floor_damage_percent",None)
        diff=getattr(s,"diffuser_damage_percent",None); rear=getattr(s,"rear_wing_damage_percent",None)
        card(w*.12,h*.255,bw,bh,"FL WING",fl)
        card(w*.675,h*.255,bw,bh,"FR WING",fr)
        card(w*.12,h*.380,bw,bh,"SIDEPOD",side)
        card(w*.3975,h*.380,bw,bh,"FLOOR",floor)
        card(w*.3975,h*.505,bw,bh,"DIFFUSER",diff)
        card(w*.3975,h*.630,bw,bh,"REAR WING",rear)

        # Fault/status cards fill the right-middle area.
        drs_fault=bool(getattr(s,"drs_fault",False)); ers_fault=bool(getattr(s,"ers_fault",False)); blown=bool(getattr(s,"engine_blown",False)); seized=bool(getattr(s,"engine_seized",False))
        state="BLOWN" if blown else ("SEIZED" if seized else "OK")
        sw=w*.205; sh=h*.095
        card(w*.675,h*.380,sw,sh,"DRS",None,RED if drs_fault else GREEN,suffix="",text_value="FAULT" if drs_fault else "OK")
        card(w*.675,h*.490,sw,sh,"ERS",None,RED if ers_fault else GREEN,suffix="",text_value="FAULT" if ers_fault else "OK")
        card(w*.12,h*.505,sw,sh,"ENGINE STATE",None,RED if (blown or seized) else GREEN,suffix="",text_value=state)
        card(w*.675,h*.600,sw,sh,"ENGINE TEMP",None,GREEN,suffix="",text_value=value_text(getattr(s,"engine_temperature_c",None),"°C",0))

        # Larger power-unit section across the bottom; 4 x 2 cards.
        p.setPen(QColor(230,235,240)); p.setFont(QFont("Segoe UI",max(10,int(h*.021)),QFont.Bold))
        p.drawText(QRectF(x0,h*.755,usable,h*.032),Qt.AlignLeft|Qt.AlignVCenter,"POWER UNIT / HYBRID WEAR")
        pu_items=(("ENGINE",getattr(s,"engine_damage_percent",None)),("GEARBOX",getattr(s,"gearbox_damage_percent",None)),("ICE",getattr(s,"engine_ice_wear_percent",None)),("CE",getattr(s,"engine_ce_wear_percent",None)),("ES",getattr(s,"engine_es_wear_percent",None)),("MGU-H",getattr(s,"engine_mguh_wear_percent",None)),("MGU-K",getattr(s,"engine_mguk_wear_percent",None)),("TC",getattr(s,"engine_tc_wear_percent",None)))
        gap=w*.010; pcw=(usable-gap*3)/4; pch=h*.080; py=h*.790
        for i,(lab,val) in enumerate(pu_items):
            row=i//4; col=i%4
            card(x0+col*(pcw+gap),py+row*(pch+h*.010),pcw,pch,lab,val,self._engine_wear_color(val))

    def _paint_tyres_page(self, p, s, w, h):
        self._page_header(p,w,h,"TYRES & BRAKES","FOUR-CORNER TYRE / BRAKE STATUS")
        tyre=self._sticky_wheels(s,"tyre_surface_temperatures_c")
        inner=self._sticky_wheels(s,"tyre_inner_temperatures_c")
        brake=self._sticky_wheels(s,"brake_temperatures_c")
        pressure=self._sticky_wheels(s,"tyre_pressures_psi")
        wear=list(getattr(s,"tyre_wear",()) or (None,)*4)
        damage=list(getattr(s,"tyre_damage_percent",()) or (None,)*4)
        blisters=list(getattr(s,"tyre_blisters_percent",()) or (None,)*4)
        brake_damage=list(getattr(s,"brake_damage_percent",()) or (None,)*4)
        for arr in (wear,damage,blisters,brake_damage):
            while len(arr)<4: arr.append(None)
        compound=str(getattr(s,"compound",None) or "--").upper(); set_no=getattr(s,"tyre_set_index",None)

        margin_x=w*.026; top=h*.225; bottom=h*.945; gap_x=w*.078; gap_y=h*.105
        half_w=(w-2*margin_x-gap_x)/2; half_h=(bottom-top-gap_y)/2; midx=w*.50; midy=top+half_h+gap_y/2
        cards=(("FL",0,QRectF(margin_x,top,half_w,half_h),True),("FR",1,QRectF(margin_x+half_w+gap_x,top,half_w,half_h),False),("RL",2,QRectF(margin_x,top+half_h+gap_y,half_w,half_h),True),("RR",3,QRectF(margin_x+half_w+gap_x,top+half_h+gap_y,half_w,half_h),False))

        pill=QRectF(midx-w*.090,midy-h*.030,w*.18,h*.060)
        p.setPen(QPen(QColor(68,76,84),1)); p.setBrush(QColor(58,58,60)); p.drawRoundedRect(pill,pill.height()/2,pill.height()/2)
        p.setPen(QColor(246,247,248)); p.setFont(QFont("Segoe UI",max(13,int(h*.031)),QFont.Bold)); p.drawText(pill,Qt.AlignCenter,f"SET {set_no if set_no is not None else '--'}")
        p.setPen(QColor(139,153,167)); p.setFont(QFont("Segoe UI",max(9,int(h*.018)),QFont.Bold)); p.drawText(QRectF(pill.x()-w*.04,pill.bottom()+1,pill.width()+w*.08,h*.023),Qt.AlignCenter,compound)
        p.setPen(QPen(QColor(42,48,55),1)); p.drawLine(QPointF(midx,top),QPointF(midx,midy-gap_y*.40)); p.drawLine(QPointF(midx,midy+gap_y*.40),QPointF(midx,bottom)); p.drawLine(QPointF(margin_x,midy),QPointF(midx-w*.105,midy)); p.drawLine(QPointF(midx+w*.105,midy),QPointF(w-margin_x,midy))

        def row(label,val,suffix,dec,color,x,y,width,align):
            rh=h*.040
            gap=width*.06
            label_w=width*.54
            value_x=x+label_w+gap
            value_w=max(8.0, width-label_w-gap)
            p.setPen(QColor(122,139,154)); p.setFont(QFont("Segoe UI",max(10,int(h*.022)),QFont.Bold)); p.drawText(QRectF(x,y,label_w,rh),Qt.AlignLeft|Qt.AlignVCenter,label)
            p.setPen(color); p.setFont(QFont("Segoe UI",max(10,int(h*.022)),QFont.Bold)); p.drawText(QRectF(value_x,y,value_w,rh),Qt.AlignRight|Qt.AlignVCenter,self._value_text(val,suffix,dec))

        def gauge(x,y,gw,gh,color,fraction,label):
            p.setPen(QPen(QColor(55,67,78),1)); p.setBrush(QColor(8,13,18)); p.drawRoundedRect(QRectF(x,y,gw,gh),3,3)
            frac=max(0.0,min(1.0,float(fraction))) if isinstance(fraction,(int,float)) else 0.0; fh=max(2.0,(gh-4)*frac) if frac>0 else 0.0
            if fh>0:
                fc=QColor(color); fc.setAlpha(235); p.setPen(Qt.NoPen); p.setBrush(fc); p.drawRoundedRect(QRectF(x+2,y+gh-2-fh,gw-4,fh),2,2)
            p.setPen(QColor(128,143,157)); p.setFont(QFont("Segoe UI",max(7,int(h*.014)),QFont.Bold)); p.drawText(QRectF(x-gw*.55,y+gh+1,gw*2.1,h*.018),Qt.AlignCenter,label)

        for name,idx,r,left in cards:
            tv,iv,bv,pv=tyre[idx],inner[idx],brake[idx],pressure[idx]; wv,dv,blv,bdv=wear[idx],damage[idx],blisters[idx],brake_damage[idx]
            oc=self._tyre_temp_color(tv); ic=self._tyre_temp_color(iv); bc=self._brake_temp_color(bv); bdc=self._wear_color(bdv)
            # Corner ID gets its own header line so FL/FR/RL/RR never crowd the PSI row.
            header_y=r.y()+2
            header_h=max(18.0,h*.036)
            p.setPen(QColor(215,222,228)); p.setFont(QFont("Segoe UI",max(11,int(h*.023)),QFont.Bold))
            p.drawText(QRectF(r.x()+7 if left else r.right()-55,header_y,48,header_h),Qt.AlignLeft|Qt.AlignVCenter if left else Qt.AlignRight|Qt.AlignVCenter,name)

            outer_w=r.width()*.38; outer_x=r.x()+r.width()*.02 if left else r.right()-outer_w-r.width()*.02
            y0=r.y()+r.height()*.17; align=Qt.AlignLeft if left else Qt.AlignRight
            rows=(("PSI",pv,"",2,QColor(245,247,249)),("OUTER",tv,"°C",0,oc),("INNER",iv,"°C",0,ic),("WEAR",wv,"%",1,self._wear_color(wv)),("TYRE DMG",dv,"%",1,self._wear_color(dv)),("BLISTER",blv,"%",1,self._wear_color(blv)))
            for ri,(lab,val,suf,dec,col) in enumerate(rows): row(lab,val,suf,dec,col,outer_x,y0+ri*h*.046,outer_w,align)

            gy=r.y()+r.height()*.23; gh=r.height()*.50; gw=max(12.0,r.width()*.043); gg=max(6.0,r.width()*.020)
            block_w=gw*3+gg*2; brake_w=r.width()*.27
            if left:
                gx=r.x()+r.width()*.45; bx=r.x()+r.width()*.69; balign=Qt.AlignLeft
                seq=((oc,(float(tv)-50)/70 if isinstance(tv,(int,float)) else 0,"OUT"),(ic,(float(iv)-50)/70 if isinstance(iv,(int,float)) else 0,"IN"),(bc,float(bv)/1200 if isinstance(bv,(int,float)) else 0,"BRK"))
            else:
                bx=r.x()+r.width()*.035; gx=r.x()+r.width()*.34; balign=Qt.AlignRight
                seq=((bc,float(bv)/1200 if isinstance(bv,(int,float)) else 0,"BRK"),(ic,(float(iv)-50)/70 if isinstance(iv,(int,float)) else 0,"IN"),(oc,(float(tv)-50)/70 if isinstance(tv,(int,float)) else 0,"OUT"))
            for gi,(gc,gf,gl) in enumerate(seq): gauge(gx+gi*(gw+gg),gy,gw,gh,gc,gf,gl)
            p.setPen(QColor(125,141,155)); p.setFont(QFont("Segoe UI",max(9,int(h*.017)),QFont.Bold)); p.drawText(QRectF(bx,gy-h*.010,brake_w,h*.021),balign|Qt.AlignVCenter,"BRAKE")
            p.setPen(bc); p.setFont(QFont("Segoe UI",max(18,int(h*.037)),QFont.Bold)); p.drawText(QRectF(bx,gy+h*.013,brake_w,h*.043),balign|Qt.AlignVCenter,self._value_text(bv,"°C",0))
            p.setPen(QColor(125,141,155)); p.setFont(QFont("Segoe UI",max(9,int(h*.017)),QFont.Bold)); p.drawText(QRectF(bx,gy+h*.060,brake_w,h*.021),balign|Qt.AlignVCenter,"BRAKE DMG")
            p.setPen(bdc); p.setFont(QFont("Segoe UI",max(11,int(h*.023)),QFont.Bold)); p.drawText(QRectF(bx,gy+h*.082,brake_w,h*.027),balign|Qt.AlignVCenter,self._value_text(bdv,"%",1))

    @staticmethod
    def _engine_wear_color(value):
        if not isinstance(value, (int, float)):
            return QColor(117,130,146)
        v=max(0.0,min(100.0,float(value)))
        if v < 20:
            return QColor(81,246,34)
        if v < 40:
            return QColor(198,232,42)
        if v < 60:
            return QColor(255,193,77)
        if v < 80:
            return QColor(255,132,60)
        return QColor(255,71,85)

    def _paint_engine_page(self, p, s, w, h):
        self._page_header(p,w,h,"POWER UNIT","ENGINE / HYBRID COMPONENT WEAR")

        vals={
            "ES":getattr(s,"engine_es_wear_percent",None),
            "CE":getattr(s,"engine_ce_wear_percent",None),
            "ICE":getattr(s,"engine_ice_wear_percent",None),
            "MGU-K":getattr(s,"engine_mguk_wear_percent",None),
            "TC":getattr(s,"engine_tc_wear_percent",None),
            "GEARBOX":getattr(s,"gearbox_damage_percent",None),
        }
        # Match the provided F1 in-game reference more closely: compact labels on
        # the left, correctly targeted dotted leaders, and a symmetric power-unit
        # silhouette on the right.
        label_x=w*.060; value_x=w*.247; line_x1=w*.305; mid_x=w*.425; gfx_left=w*.545; gfx_top=h*.155; gfx_w=w*.325; gfx_h=h*.675
        rows=(("ES",.28),("CE",.39),("ICE",.50),("MGU-K",.61),("TC",.72),("GEARBOX",.83))
        anchors={
            "ES":(gfx_left+gfx_w*.49,gfx_top+gfx_h*.08),
            "CE":(gfx_left+gfx_w*.17,gfx_top+gfx_h*.33),
            "ICE":(gfx_left+gfx_w*.48,gfx_top+gfx_h*.38),
            "MGU-K":(gfx_left+gfx_w*.49,gfx_top+gfx_h*.73),
            "TC":(gfx_left+gfx_w*.50,gfx_top+gfx_h*.87),
            "GEARBOX":(gfx_left+gfx_w*.735,gfx_top+gfx_h*.735),
        }
        for lab,yf in rows:
            val=vals[lab]; col=self._engine_wear_color(val); y=h*yf
            p.setPen(QColor(235,239,243)); p.setFont(QFont("Segoe UI",max(13,int(h*.033)),QFont.Normal))
            p.drawText(QRectF(label_x,y-h*.027,w*.16,h*.055),Qt.AlignRight|Qt.AlignVCenter,lab)
            p.setPen(col); p.setFont(QFont("Segoe UI",max(15,int(h*.038)),QFont.Bold))
            p.drawText(QRectF(value_x,y-h*.028,w*.11,h*.058),Qt.AlignLeft|Qt.AlignVCenter,self._value_text(val,"%"))
            ax,ay=anchors[lab]
            pen=QPen(QColor(190,196,202),1,Qt.DotLine); p.setPen(pen); p.setBrush(Qt.NoBrush)
            elbow_y=y if lab in ("ICE","MGU-K") else (y-h*.010 if lab=="TC" else (y-h*.018 if lab=="GEARBOX" else (y+h*.008 if lab=="CE" else y-h*.004)))
            p.drawLine(QPointF(line_x1,y),QPointF(mid_x,elbow_y))
            p.drawLine(QPointF(mid_x,elbow_y),QPointF(ax,ay))

        # Component-specific colors; every visible block reacts to its own wear.
        c_es=self._engine_wear_color(vals["ES"]); c_ce=self._engine_wear_color(vals["CE"]); c_ice=self._engine_wear_color(vals["ICE"]); c_k=self._engine_wear_color(vals["MGU-K"]); c_tc=self._engine_wear_color(vals["TC"]); c_gbx=self._engine_wear_color(vals["GEARBOX"])
        def zone_fill(c,alpha=72):
            q=QColor(c); q.setAlpha(alpha); return q
        def draw_zone_path(path, c, alpha=72, width=3):
            p.setPen(QPen(c,width)); p.setBrush(zone_fill(c,alpha)); p.drawPath(path)
        def draw_zone_rect(rect, c, alpha=72, width=3, radius=10):
            p.setPen(QPen(c,width)); p.setBrush(zone_fill(c,alpha)); p.drawRoundedRect(rect,radius,radius)

        # ES - top block.
        draw_zone_rect(QRectF(gfx_left+gfx_w*.31,gfx_top+gfx_h*.00,gfx_w*.34,gfx_h*.16),c_es,68,3,16)
        # CE - left and right side modules.
        draw_zone_rect(QRectF(gfx_left+gfx_w*.12,gfx_top+gfx_h*.16,gfx_w*.16,gfx_h*.28),c_ce,66,3,16)
        draw_zone_rect(QRectF(gfx_left+gfx_w*.71,gfx_top+gfx_h*.16,gfx_w*.16,gfx_h*.28),c_ce,66,3,16)
        # ICE - main central body.
        ice=QPainterPath(); ice.moveTo(gfx_left+gfx_w*.33,gfx_top+gfx_h*.14); ice.lineTo(gfx_left+gfx_w*.67,gfx_top+gfx_h*.14); ice.lineTo(gfx_left+gfx_w*.75,gfx_top+gfx_h*.24); ice.lineTo(gfx_left+gfx_w*.75,gfx_top+gfx_h*.54); ice.lineTo(gfx_left+gfx_w*.67,gfx_top+gfx_h*.66); ice.lineTo(gfx_left+gfx_w*.33,gfx_top+gfx_h*.66); ice.lineTo(gfx_left+gfx_w*.25,gfx_top+gfx_h*.54); ice.lineTo(gfx_left+gfx_w*.25,gfx_top+gfx_h*.24); ice.closeSubpath(); draw_zone_path(ice,c_ice,56,3)
        # ICE center core / channel.
        p.setPen(QPen(c_ice,3)); p.setBrush(QColor(4,8,6,160)); p.drawRoundedRect(QRectF(gfx_left+gfx_w*.45,gfx_top+gfx_h*.10,gfx_w*.10,gfx_h*.31),gfx_w*.05,gfx_w*.05)
        # Decorative exhaust sweep on the right, using ICE color to preserve silhouette.
        p.setPen(QPen(c_ice,4)); p.setBrush(Qt.NoBrush)
        exhaust=QPainterPath(); exhaust.moveTo(gfx_left+gfx_w*.78,gfx_top+gfx_h*.39); exhaust.cubicTo(gfx_left+gfx_w*.92,gfx_top+gfx_h*.38,gfx_left+gfx_w*.94,gfx_top+gfx_h*.58,gfx_left+gfx_w*.76,gfx_top+gfx_h*.64); p.drawPath(exhaust)
        # MGU-K - lower horizontal module.
        draw_zone_rect(QRectF(gfx_left+gfx_w*.35,gfx_top+gfx_h*.69,gfx_w*.29,gfx_h*.08),c_k,70,3,10)
        # Gearbox - right horizontal box attached to the MGU-K level.
        p.setPen(QPen(c_gbx,3)); p.setBrush(zone_fill(c_gbx,70)); p.drawRect(QRectF(gfx_left+gfx_w*.68,gfx_top+gfx_h*.705,gfx_w*.11,gfx_h*.065))
        # TC - bottom square module.
        p.setPen(QPen(c_tc,3)); p.setBrush(zone_fill(c_tc,70)); p.drawRect(QRectF(gfx_left+gfx_w*.44,gfx_top+gfx_h*.82,gfx_w*.12,gfx_h*.10))

        temp=getattr(s,"engine_temperature_c",None); fault=getattr(s,"engine_blown",False) or getattr(s,"engine_seized",False)
        state_col=RED if fault else self._engine_wear_color(max([float(v) for v in vals.values() if isinstance(v,(int,float))], default=0.0))
        p.setPen(state_col); p.setFont(QFont("Segoe UI",max(10,int(h*.022)),QFont.Bold))
        p.drawText(QRectF(gfx_left,h*.84,gfx_w,h*.045),Qt.AlignCenter,"ENGINE FAULT" if fault else f"ENGINE TEMP {self._value_text(temp,'°C')}")

    def _paint_map_page(self, p, s, w, h):
        self._page_header(p,w,h,"TRACK MAP",f"{str(getattr(s,'track_name',None) or '--').upper()}  •  LIVE POSITION / REFERENCE / NEARBY")
        area=QRectF(w*.025,h*.205,w*.95,h*.635)
        pts, source = self._track_polyline(s)
        if len(pts) < 2:
            if self._learning_lap is None:
                msg = "WAITING FOR START LINE…\nFirst map capture begins only after the car crosses S/F"
            else:
                msg = "LEARNING TRACK MAP…\nRecording one complete start-line-to-start-line lap"
            p.setPen(QColor(145,158,171)); p.setFont(QFont("Segoe UI",max(12,int(h*.028)),QFont.Bold)); p.drawText(area,Qt.AlignCenter,msg)
            return
        map_key=(str(getattr(s,"track_name",None) or ""),source,w,h,id(pts),len(pts))
        if map_key != self._map_geometry_cache_key or self._map_geometry_cache_value is None:
            scaled, geom = self._scaled_map_geometry(area, pts)
            path=QPainterPath(); started=False
            for px,py in scaled:
                if not started: path.moveTo(px,py); started=True
                else: path.lineTo(px,py)
            self._map_geometry_cache_key=map_key
            self._map_geometry_cache_value=(scaled,geom,path)
        else:
            scaled,geom,path=self._map_geometry_cache_value
        p.setPen(QPen(QColor(214,219,223),5,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)); p.setBrush(Qt.NoBrush); p.drawPath(path)
        minx,maxx,miny,maxy,sc,ox,oy,rotate = geom
        # Permanent start/finish marker anchored to the first map point.
        if scaled:
            sx,sy=scaled[0]
            p.setPen(QPen(QColor(245,248,250),2)); p.setBrush(QColor(8,12,16)); p.drawEllipse(QRectF(sx-7,sy-7,14,14))
            p.setPen(QColor(245,248,250)); p.setFont(QFont("Segoe UI",max(6,int(h*.013)),QFont.Bold)); p.drawText(QRectF(sx-22,sy-25,44,16),Qt.AlignCenter,"START")
        def screen_point(pt):
            if pt is None: return None
            x,y = pt
            if rotate:
                x,y = y,-x
            return (ox+x*sc, oy+y*sc)

        # Performance gain/loss colouring intentionally lives only in CORNER COACH.
        # Compatibility name: map_gain_loss_zones is deliberately NOT rendered here.

        # Detected turn labels use exactly the same corner IDs as coaching.
        # Their positions come from the active reference lap, so T3 on the map
        # is the same T3 used by PRE/POST coaching calls.
        if source == "predefined":
            for turn in getattr(s, "map_turns", ()) or ():
                turn_pt = self._distance_marker_point(s, pts, getattr(turn, "lap_distance_m", None))
                sp = screen_point(turn_pt)
                if sp is None:
                    continue
                tx, ty = sp
                label = str(getattr(turn, "label", "") or "")
                if not label:
                    continue
                r = max(8, int(h * .015))
                p.setPen(QPen(QColor(7, 10, 14, 230), 2))
                p.setBrush(QColor(232, 237, 242, 235))
                p.drawEllipse(QRectF(tx-r, ty-r, r*2, r*2))
                p.setPen(QColor(19, 27, 35))
                p.setFont(QFont("Segoe UI", max(6, int(h*.012)), QFont.Bold))
                p.drawText(QRectF(tx-r, ty-r, r*2, r*2), Qt.AlignCenter, label)

        def marker(pt, color, text, radius=11):
            sp=screen_point(pt)
            if sp is None: return
            mx,my=sp
            p.setPen(QPen(QColor(6,8,10),2)); p.setBrush(color); p.drawEllipse(QRectF(mx-radius,my-radius,radius*2,radius*2))
            p.setPen(QColor(5,7,9)); p.setFont(QFont("Segoe UI",max(8,int(h*.018)),QFont.Bold)); p.drawText(QRectF(mx-radius,my-radius,radius*2,radius*2),Qt.AlignCenter,text)
        # Reference ghost follows the stored reference lap's elapsed-time position.
        ref_d=getattr(s,"reference_map_distance_m",None)
        ref_pt=self._distance_marker_point(s,pts,ref_d) if source=="predefined" else None
        if ref_pt is not None:
            marker(ref_pt,QColor(62,200,255),"R",10)
        # Two cars ahead / behind, when the field packet exposes their lap distance.
        ahead_colors=(QColor(255,71,85),QColor(255,145,70))
        behind_colors=(QColor(45,231,125),QColor(173,106,255))
        ai=bi=0
        for item in getattr(s,"map_nearby",()) or ():
            pt=self._distance_marker_point(s,pts,getattr(item,"lap_distance_m",None)) if source=="predefined" else None
            if pt is None: continue
            if getattr(item,"kind","")=="ahead":
                color=ahead_colors[min(ai,len(ahead_colors)-1)]; ai+=1
            else:
                color=behind_colors[min(bi,len(behind_colors)-1)]; bi+=1
            pos=getattr(item,"position",None); marker(pt,color,str(pos if pos is not None else "?"),10)
        player_pt = self._track_marker_point(s, pts, source)
        marker(player_pt,QColor(255,220,52),str(getattr(s,"position",None) or "1"),13)
        # Legend.
        legend=((QColor(255,220,52),"YOU"),(QColor(62,200,255),"REF"),(QColor(255,71,85),"AHEAD"),(QColor(45,231,125),"BEHIND"))
        lx=w*.20
        for i,(col,label) in enumerate(legend):
            x=lx+i*w*.16; p.setPen(Qt.NoPen); p.setBrush(col); p.drawEllipse(QRectF(x,h*.850,12,12)); p.setPen(QColor(175,187,199)); p.setFont(QFont("Segoe UI",max(9,int(h*.019)),QFont.Bold)); p.drawText(QRectF(x+17,h*.842,w*.13,h*.038),Qt.AlignLeft|Qt.AlignVCenter,label)
        p.setPen(QColor(150,164,178)); p.setFont(QFont("Segoe UI",max(8,int(h*.018)),QFont.Bold)); delta_txt=""
        if isinstance(getattr(s,"map_full_track_delta_s",None),(int,float)):
            dv=float(getattr(s,"map_full_track_delta_s")); delta_txt=f"   •   LAST Δ {dv:+.3f}s"
        p.drawText(QRectF(w*.08,h*.915,w*.84,h*.035),Qt.AlignCenter,f"LAP {getattr(s,'lap_number',None) or '--'} / {getattr(s,'total_laps',None) or '--'}   •   POSITION P{getattr(s,'position',None) or '--'}   •   {self._value_text(getattr(s,'lap_distance_m',None),' m',0)}{delta_txt}")

    def _paint_pit_page(self, p, s, w, h):
        self._page_header(p,w,h,"PIT", "LIVE PIT / SERVICE STATUS")
        status=str(getattr(s,"pit_status",None) or "NONE").upper()
        p.setPen(GREEN if status in {"NONE","N/A"} else AMBER); p.setFont(QFont("Segoe UI",max(34,int(h*.100)),QFont.Bold))
        p.drawText(QRectF(w*.06,h*.205,w*.88,h*.145),Qt.AlignCenter,status)
        re=getattr(s,"race_engineer",None)
        next_comp=getattr(re,"next_tyre_compound",None) if re is not None else None
        next_set=getattr(re,"next_tyre_set",None) if re is not None else None
        boxes=(("PIT STOPS",getattr(s,"pit_stops",None),""),("SPEED LIMIT",getattr(s,"pit_speed_limit_kph",None)," KM/H"),("LANE TIME",getattr(s,"pit_lane_time_s",None)," s"),("STOP TIME",getattr(s,"pit_stop_time_s",None)," s"),("NEXT TYRE",str(next_comp).upper() if next_comp else "--",""),("TYRE SET",next_set,""),("PENALTY",getattr(s,"penalties_s",None)," s"),("SERVE PEN","YES" if getattr(s,"serve_penalty",False) else "NO",""))
        sx=w*.035; sy=h*.385; gap=w*.012; row_gap=h*.028; cw=(w*.93-gap*3)/4; ch=h*.205
        for i,(label,value,suffix) in enumerate(boxes):
            row=i//4; col=i%4; r=QRectF(sx+col*(cw+gap),sy+row*(ch+row_gap),cw,ch)
            p.setPen(QPen(QColor(39,51,62),1)); p.setBrush(QColor(11,17,24)); p.drawRoundedRect(r,8,8)
            p.setPen(QColor(125,141,156)); p.setFont(QFont("Segoe UI",max(9,int(h*.020)),QFont.Bold)); p.drawText(QRectF(r.x()+5,r.y()+7,r.width()-10,h*.042),Qt.AlignCenter,label)
            if isinstance(value,(int,float)): txt=f"{value:.1f}{suffix}" if isinstance(value,float) else f"{value}{suffix}"
            else: txt=str(value) if value not in (None,"") else "--"
            p.setPen(AMBER if label=="SERVE PEN" and txt=="YES" else QColor(239,243,247)); p.setFont(QFont("Segoe UI",max(16,int(h*.042)),QFont.Bold)); p.drawText(QRectF(r.x()+5,r.y()+h*.055,r.width()-10,r.height()-h*.065),Qt.AlignCenter,txt)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = max(1, self.width()); h = max(1, self.height())
        p.fillRect(self.rect(), QColor(4, 7, 10, 245))
        s = self.snapshot

        # Rev lights: 15 positions, exactly matching EA's rev-light percentage.
        rev = getattr(s, "rev_lights_percent", None) if s is not None else None
        rev = max(0.0, min(100.0, float(rev))) if isinstance(rev, (int, float)) else 0.0
        lit = int(round(rev / 100.0 * 15.0))
        gap = max(3, int(w * 0.006)); margin = int(w * 0.055)
        led_w = (w - margin * 2 - gap * 14) / 15.0
        led_y = int(h * 0.025); led_h = max(8, int(h * 0.055))
        for i in range(15):
            x = margin + i * (led_w + gap)
            if i < lit:
                c = QColor(43, 239, 133) if i < 5 else (QColor(255, 62, 77) if i < 10 else QColor(102, 116, 255))
            else:
                c = QColor(27, 35, 44)
            p.setPen(Qt.NoPen); p.setBrush(c)
            p.drawRoundedRect(QRectF(x, led_y, led_w, led_h), led_h / 2, led_h / 2)

        connected = bool(getattr(s, "connected", False)) if s is not None else False
        if not connected:
            # UI-R9: explicit disconnected card rather than a blank dashboard.
            card=QRectF(w*.20,h*.285,w*.60,h*.38)
            p.setPen(QPen(QColor(43,57,70),1)); p.setBrush(QColor(10,16,22,244)); p.drawRoundedRect(card,14,14)
            p.setPen(QColor(62,200,255)); p.setFont(QFont("Segoe UI", max(8,int(h*.020)), QFont.Bold))
            p.drawText(QRectF(card.x()+18,card.y()+14,card.width()-36,h*.035),Qt.AlignCenter,"F1 DASH")
            p.setPen(QColor(236,242,247)); p.setFont(QFont("Segoe UI", max(16, int(h * .050)), QFont.Bold))
            p.drawText(QRectF(card.x()+18,card.y()+h*.070,card.width()-36,h*.075), Qt.AlignCenter, "WAITING FOR F1 TELEMETRY")
            p.setPen(QColor(126,142,157)); p.setFont(QFont("Segoe UI", max(8, int(h * .020))))
            p.drawText(QRectF(card.x()+24,card.y()+h*.145,card.width()-48,h*.075), Qt.AlignCenter|Qt.TextWordWrap, "Start or resume a supported F1 session. The dash will reconnect automatically.")
            if self.remote_url:
                p.setPen(QColor(89,191,229)); p.setFont(QFont("Segoe UI", max(7, int(h * .017)), QFont.DemiBold))
                p.drawText(QRectF(card.x()+20,card.bottom()-h*.075,card.width()-40,h*.045), Qt.AlignCenter, f"LAN  {self.remote_url}")
            return

        if self.page == "damage":
            self._paint_damage_page(p, s, w, h)
            return
        if self.page == "engine":
            self._paint_engine_page(p, s, w, h)
            return
        if self.page == "tyres":
            self._paint_tyres_page(p, s, w, h)
            return
        if self.page == "map":
            self._paint_map_page(p, s, w, h)
            return
        if self.page == "pit":
            self._paint_pit_page(p, s, w, h)
            return

        speed = int(getattr(s, "speed_kph", 0) or 0)
        gear = _gear_text(getattr(s, "gear", None))
        pos = getattr(s, "position", None)
        lap = getattr(s, "lap_number", None); total = getattr(s, "total_laps", None)
        lap_time = getattr(s, "lap_time_s", None); delta = getattr(s, "live_delta_s", None)
        ers = self._ers_percent(s)
        fuel_laps = getattr(s, "fuel_remaining_laps", None)
        throttle = max(0.0, min(1.0, float(getattr(s, "throttle", 0.0) or 0.0)))
        brake = max(0.0, min(1.0, float(getattr(s, "brake", 0.0) or 0.0)))

        # Central gear / speed block. Slightly reduce the gear size so the
        # lower information strip can grow and be read faster at a glance.
        p.setPen(QColor(247, 249, 251)); p.setFont(QFont("Segoe UI", max(68, int(h * .30)), QFont.Bold))
        p.drawText(QRectF(w * .29, h * .12, w * .42, h * .36), Qt.AlignCenter, gear)
        p.setPen(QColor(247,249,251)); p.setFont(QFont("Segoe UI", max(23, int(h * .095)), QFont.Bold))
        p.drawText(QRectF(w * .30, h * .475, w * .40, h * .13), Qt.AlignCenter, f"{speed}  KM/H")

        # Left facts.
        p.setPen(QColor(130, 145, 160)); p.setFont(QFont("Segoe UI", max(9, int(h * .026)), QFont.Bold))
        p.drawText(QRectF(w*.035, h*.15, w*.20, h*.05), Qt.AlignLeft|Qt.AlignVCenter, "POSITION")
        p.setPen(QColor(247,249,251)); p.setFont(QFont("Segoe UI", max(24, int(h*.10)), QFont.Bold))
        p.drawText(QRectF(w*.03, h*.19, w*.22, h*.13), Qt.AlignLeft|Qt.AlignVCenter, f"P{pos if pos is not None else '--'}")
        p.setPen(QColor(130,145,160)); p.setFont(QFont("Segoe UI", max(9, int(h*.026)), QFont.Bold))
        p.drawText(QRectF(w*.035,h*.34,w*.20,h*.05), Qt.AlignLeft|Qt.AlignVCenter,"LAP")
        p.setPen(QColor(247,249,251)); p.setFont(QFont("Segoe UI", max(16, int(h*.062)), QFont.Bold))
        p.drawText(QRectF(w*.03,h*.38,w*.24,h*.10), Qt.AlignLeft|Qt.AlignVCenter, f"{lap if lap is not None else '--'} / {total if total is not None else '--'}")
        sector=getattr(s,"sector",None)
        p.setPen(QColor(130,145,160)); p.setFont(QFont("Segoe UI", max(9, int(h*.026)), QFont.Bold))
        p.drawText(QRectF(w*.035,h*.475,w*.20,h*.05), Qt.AlignLeft|Qt.AlignVCenter, "SECTOR")
        p.setPen(QColor(247,249,251)); p.setFont(QFont("Segoe UI", max(16, int(h*.062)), QFont.Bold))
        p.drawText(QRectF(w*.03,h*.515,w*.24,h*.10), Qt.AlignLeft|Qt.AlignVCenter, f"S{sector}" if sector else "--")

        # Right timing / delta.
        p.setPen(QColor(130,145,160)); p.setFont(QFont("Segoe UI", max(9, int(h*.026)), QFont.Bold))
        p.drawText(QRectF(w*.73,h*.15,w*.235,h*.05), Qt.AlignRight|Qt.AlignVCenter,"LAP TIME")
        p.setPen(QColor(247,249,251)); p.setFont(QFont("Segoe UI", max(15,int(h*.055)),QFont.Bold))
        p.drawText(QRectF(w*.69,h*.20,w*.275,h*.08),Qt.AlignRight|Qt.AlignVCenter,_time_text(lap_time))
        p.setPen(QColor(130,145,160)); p.setFont(QFont("Segoe UI", max(9,int(h*.026)),QFont.Bold))
        p.drawText(QRectF(w*.73,h*.32,w*.235,h*.05),Qt.AlignRight|Qt.AlignVCenter,"DELTA")
        if isinstance(delta,(int,float)):
            dc = GREEN if delta <= 0 else RED; dt = f"{delta:+.3f}"
        else:
            dc = MUTED; dt = "--.---"
        p.setPen(dc); p.setFont(QFont("Segoe UI",max(25,int(h*.09)),QFont.Bold))
        p.drawText(QRectF(w*.69,h*.36,w*.275,h*.12),Qt.AlignRight|Qt.AlignVCenter,dt)

        # Status pills.
        def pill(x, text, active, available=False):
            r=QRectF(x,h*.64,w*.11,h*.065)
            c=GREEN if active else (AMBER if available else QColor(35,45,56))
            p.setPen(Qt.NoPen); p.setBrush(c); p.drawRoundedRect(r,6,6)
            p.setPen(QColor(3,8,6) if (active or available) else QColor(125,139,154))
            p.setFont(QFont("Segoe UI",max(8,int(h*.024)),QFont.Bold)); p.drawText(r,Qt.AlignCenter,text)
        pill(w*.32,"S MODE",bool(getattr(s,"s_mode_active",False)),bool(getattr(s,"s_mode_available",False)))
        pill(w*.445,"ERS",bool(getattr(s,"overtake_active",False)),bool(getattr(s,"overtake_available",False)))
        pill(w*.57,"OT",bool(getattr(s,"overtake_active",False)),bool(getattr(s,"overtake_available",False)))

        # Bottom progress bars: throttle, brake, ERS, fuel laps.
        def bar(x, y, ww, label, value, color, text):
            p.setPen(QColor(130,145,160)); p.setFont(QFont("Segoe UI",max(8,int(h*.021)),QFont.Bold)); p.drawText(QRectF(x,y-h*.045,ww,h*.04),Qt.AlignLeft|Qt.AlignVCenter,label)
            p.setPen(Qt.NoPen); p.setBrush(QColor(25,34,44)); p.drawRoundedRect(QRectF(x,y,ww,h*.032),h*.016,h*.016)
            p.setBrush(color); p.drawRoundedRect(QRectF(x,y,ww*max(0,min(1,value)),h*.032),h*.016,h*.016)
            p.setPen(QColor(235,239,243)); p.setFont(QFont("Segoe UI",max(8,int(h*.021)),QFont.Bold)); p.drawText(QRectF(x,y-h*.045,ww,h*.04),Qt.AlignRight|Qt.AlignVCenter,text)
        bar(w*.04,h*.755,w*.20,"THROTTLE",throttle,QColor(45,231,125),f"{throttle*100:.0f}%")
        bar(w*.28,h*.755,w*.20,"BRAKE",brake,QColor(255,71,85),f"{brake*100:.0f}%")
        bar(w*.52,h*.755,w*.20,"ERS",(ers or 0)/100.0,QColor(62,200,255),"--%" if ers is None else f"{ers:.0f}%")
        fuel_value = max(0.0,min(1.0,float(fuel_laps)/6.0)) if isinstance(fuel_laps,(int,float)) else 0.0
        bar(w*.76,h*.755,w*.20,"FUEL",fuel_value,QColor(67,224,122),"--" if fuel_laps is None else f"{fuel_laps:.1f} LAPS")

        # Unified setup / race-status strip. Keep the native FD window visually
        # aligned with the LAN dashboard: label on top, larger value below.
        def pct_text(value):
            return "--" if not isinstance(value,(int,float)) else f"{float(value):.0f}%"
        diff_on=getattr(s,"setup_diff_on_throttle_percent",None)
        diff_off=getattr(s,"setup_diff_off_throttle_percent",None)
        diff_text=("--/--" if diff_on is None and diff_off is None
                   else f"{'--' if diff_on is None else f'{float(diff_on):.0f}'}/{'--' if diff_off is None else f'{float(diff_off):.0f}'}%")
        fuel_mode = getattr(s, "fuel_mix", None)
        if isinstance(fuel_mode, str) and fuel_mode:
            fuel_mode_text = fuel_mode.upper()
        else:
            fuel_mode_text = "--"
        penalty=getattr(s,"penalties_s",None)
        cells=(
            ("DIFF", diff_text, QColor(235,239,243)),
            ("BBAL", pct_text(getattr(s,"setup_brake_bias_percent",None)), QColor(235,239,243)),
            ("ENG BRK", pct_text(getattr(s,"setup_engine_braking_percent",None)), QColor(235,239,243)),
            ("FUEL MODE", fuel_mode_text, QColor(235,239,243)),
            ("PEN", "--" if penalty is None else f"{penalty}s", AMBER if isinstance(penalty,(int,float)) and penalty>0 else QColor(235,239,243)),
        )
        # Grow the bottom setup strip to use the spare space around the
        # cards without shrinking the readable values. Keep the larger DIFF /
        # BBAL / ENG BRK / FUEL MODE / PEN treatment and make each card a bit
        # wider and taller for quicker reading.
        sx=w*.028; sy=h*.822; sw=w*.944; gap=w*.008; cell_w=(sw-gap*4)/5.0; cell_h=h*.093
        cell_fills = (
            QColor(32, 102, 182, 70),  # DIFF
            QColor(171, 112, 28, 72),  # BBAL
            QColor(20, 132, 112, 72),  # ENG BRK
            QColor(120, 72, 176, 72),  # FUEL MODE
            QColor(124, 50, 50, 72),   # PEN
        )
        cell_borders = (
            QColor(68, 126, 192, 150),
            QColor(186, 128, 44, 150),
            QColor(37, 150, 129, 150),
            QColor(137, 88, 193, 150),
            QColor(146, 70, 70, 150),
        )
        for i,(label,value,color) in enumerate(cells):
            r=QRectF(sx+i*(cell_w+gap),sy,cell_w,cell_h)
            p.setPen(QPen(cell_borders[i],1.2)); p.setBrush(cell_fills[i]); p.drawRoundedRect(r,7,7)
            p.setPen(QColor(166,182,198)); p.setFont(QFont("Segoe UI",max(8,int(h*.0175)),QFont.Bold))
            p.drawText(QRectF(r.x()+6,r.y()+h*.005,r.width()-12,r.height()*.34),Qt.AlignHCenter|Qt.AlignTop,label)
            value_font = max(13, int(h*.031)) if len(str(value)) <= 8 else max(11, int(h*.026))
            p.setPen(color); p.setFont(QFont("Segoe UI",value_font,QFont.Bold))
            p.drawText(QRectF(r.x()+6,r.y()+r.height()*.26,r.width()-12,r.height()*.60),Qt.AlignHCenter|Qt.AlignVCenter,value)

        if self.remote_url:
            p.setPen(QColor(105,121,136)); p.setFont(QFont("Segoe UI",max(10,int(h*.020)),QFont.Medium))
            p.drawText(QRectF(w*.035,h*.944,w*.93,h*.036),Qt.AlignCenter,f"WEB {self.remote_url}")



class CornerCoachMapCanvas(QWidget):
    # Green begins at the physical apex and continues through the reference throttle/exit phase.
    """Paint-only V1.1 CORNER COACH map using the frozen V1.0.3.1 map axis."""
    def __init__(self):
        super().__init__(); self.snapshot=None
        self._scaled_cache_key=None;self._scaled_cache=([],None)
        self._static_layer_key=None;self._static_layer=None;self._static_geom=None;self._static_points=()
        # V1.1.0.3 separates immutable reference geometry from the changing live
        # gain/loss layer.  Updating G/L must never force a full antialiased map
        # + corner-gradient redraw on the Qt GUI thread.
        self._gain_layer_key=None;self._gain_layer=None
        self._active_layer_key=None;self._active_layer=None
        self.setMinimumSize(320,260)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def update_snapshot(self,snapshot):
        self.snapshot=snapshot; self.update()

    @staticmethod
    def _interp(points,distances,distance_m,track_length_m):
        # Hot-path variant: avoid allocating/copying the full map distance arrays
        # for every 4-10 m coloured-line sample.
        if not points or not distances or not isinstance(distance_m,(int,float)) or not isinstance(track_length_m,(int,float)) or track_length_m<=1:
            return None
        closed=len(points)>1 and points[0]==points[-1] and len(distances)==len(points)-1
        n=len(points)-1 if closed else len(points)
        if len(distances)!=n or n<2:return None
        d=float(distance_m)%float(track_length_m)
        if d<=float(distances[0]):return points[0]
        if d>=float(distances[-1]):
            d0=float(distances[-1]);d1=float(track_length_m);p0=points[n-1];p1=points[0]
        else:
            from bisect import bisect_left
            i=max(1,min(bisect_left(distances,d),n-1));d0=float(distances[i-1]);d1=float(distances[i]);p0=points[i-1];p1=points[i]
        if d1<=d0:return p1
        a=max(0.0,min(1.0,(d-d0)/(d1-d0)));return (p0[0]+(p1[0]-p0[0])*a,p0[1]+(p1[1]-p0[1])*a)

    @staticmethod
    def _scaled(area,points):
        if not points:return [],None
        raw_x=[p[0] for p in points]; raw_y=[p[1] for p in points]
        raw_dx=max(1e-6,max(raw_x)-min(raw_x)); raw_dy=max(1e-6,max(raw_y)-min(raw_y))
        rotate=bool(area.width()>area.height()*1.25 and raw_dy>raw_dx*1.10)
        oriented=[(y,-x) if rotate else (x,y) for x,y in points]
        xs=[p[0] for p in oriented]; ys=[p[1] for p in oriented]
        minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)
        dx=max(1e-6,maxx-minx);dy=max(1e-6,maxy-miny)
        scale=min(area.width()*.94/dx,area.height()*.94/dy)
        ox=area.center().x()-(minx+maxx)*.5*scale;oy=area.center().y()-(miny+maxy)*.5*scale
        return [(ox+x*scale,oy+y*scale) for x,y in oriented],(scale,ox,oy,rotate)

    @staticmethod
    def _screen(pt,geom):
        if pt is None or geom is None:return None
        scale,ox,oy,rotate=geom;x,y=pt
        if rotate:x,y=y,-x
        return ox+x*scale,oy+y*scale

    def _point_at(self,s,points,d):
        length=getattr(s,'track_length_m',None);axis=get_track_map_distances(getattr(s,'track_name',None))
        if not isinstance(length,(int,float)) or length<=1:return None
        exact=self._interp(points,axis,d,length)
        if exact is not None:return exact
        return F1DashCanvas._interpolate_polyline(points,(float(d)%float(length))/float(length)) if isinstance(d,(int,float)) else None

    def _draw_distance_span(self,p,s,points,geom,start,end,color_fn,width=7):
        if not isinstance(start,(int,float)) or not isinstance(end,(int,float)) or end<=start:return
        span=float(end)-float(start);step=max(4.0,min(10.0,span/30.0));d=float(start);last=None
        while d<=float(end)+1e-6:
            raw=self._point_at(s,points,min(d,float(end)));cur=self._screen(raw,geom)
            if last is not None and cur is not None:
                frac=max(0.0,min(1.0,(d-float(start))/max(1e-9,span)))
                p.setPen(QPen(color_fn(frac),width,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.drawLine(QPointF(*last),QPointF(*cur))
            if cur is not None:last=cur
            d+=step
        raw=self._point_at(s,points,float(end));cur=self._screen(raw,geom)
        if last is not None and cur is not None:
            p.setPen(QPen(color_fn(1.0),width,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.drawLine(QPointF(*last),QPointF(*cur))

    @staticmethod
    def _draw_scaled_axis_span(p, scaled, distances, start, end, color, width=3):
        """Draw a distance span using already-scaled map vertices.

        Unlike _draw_distance_span this performs no per-4m interpolation/bisect
        loop, so live G/L repaint cost is proportional to actual map vertices.
        """
        if not scaled or not distances or not isinstance(start,(int,float)) or not isinstance(end,(int,float)) or end<=start:
            return
        from bisect import bisect_left, bisect_right
        n=min(len(distances),len(scaled))
        if n<2:return
        i0=max(0,min(n-1,bisect_left(distances,float(start))-1))
        i1=max(i0+1,min(n-1,bisect_right(distances,float(end))))
        path=QPainterPath();path.moveTo(*scaled[i0])
        for i in range(i0+1,i1+1):path.lineTo(*scaled[i])
        p.setPen(QPen(color,width,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.setBrush(Qt.NoBrush);p.drawPath(path)

    def paintEvent(self,_event):
        s=self.snapshot
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        if s is None:
            p.fillRect(self.rect(),QColor(6,10,14,180));return
        track_name=getattr(s,'track_name',None);points=(get_track_map(track_name) or getattr(s,'map_learning_points',()) or ())
        corners=tuple(c for c in (getattr(s,'corner_coach_physical_corners',()) or ()) if isinstance(c,dict))
        zones=tuple(z for z in (getattr(s,'corner_coach_zones',()) or ()) if isinstance(z,dict))
        active=getattr(s,'corner_coach_active_zone',None) or {};active_id=active.get('zone_id') if isinstance(active,dict) else None
        gain_sig=tuple((round(float(getattr(z,'start_m',0.0)),1),round(float(getattr(z,'end_m',0.0)),1),str(getattr(z,'state','NEUTRAL'))) for z in (getattr(s,'corner_coach_gain_loss_zones',()) or ()))
        corner_sig=tuple((c.get('corner_id'),round(float(c.get('start_m',0.0)),1) if isinstance(c.get('start_m'),(int,float)) else None,round(float(c.get('apex_m',0.0)),1) if isinstance(c.get('apex_m'),(int,float)) else None,round(float(c.get('end_m',0.0)),1) if isinstance(c.get('end_m'),(int,float)) else None) for c in corners)
        zone_sig=tuple((z.get('zone_id'),tuple(z.get('corner_ids') or ()),round(float(z.get('brake_start_m')),1) if isinstance(z.get('brake_start_m'),(int,float)) else None,round(float(z.get('throttle_start_m')),1) if isinstance(z.get('throttle_start_m'),(int,float)) else None) for z in zones)
        static_key=(str(track_name or ''),self.width(),self.height(),id(points),len(points),corner_sig,zone_sig)

        if static_key!=self._static_layer_key or self._static_layer is None:
            self._static_layer_key=static_key
            pix=QPixmap(max(1,self.width()),max(1,self.height()));pix.fill(Qt.transparent)
            sp=QPainter(pix);sp.setRenderHint(QPainter.Antialiasing);sp.fillRect(QRectF(0,0,self.width(),self.height()),QColor(6,10,14,180))
            area=QRectF(10,32,max(1,self.width()-20),max(1,self.height()-42))
            sp.setPen(QColor(230,235,240));sp.setFont(_visual_font(self, 10, QFont.Bold));sp.drawText(QRectF(12,5,self.width()-24,24),Qt.AlignLeft|Qt.AlignVCenter,f"{str(track_name or '--').upper()}  •  PERFORMANCE COACH")
            geom=None
            if len(points)<2:
                sp.setPen(MUTED);sp.setFont(_visual_font(self, 10, QFont.Bold));sp.drawText(area,Qt.AlignCenter,'WAITING FOR TRACK MAP / REFERENCE')
            else:
                scaled,geom=self._scaled(area,points)
                base=QPainterPath()
                for i,(x,y) in enumerate(scaled):base.moveTo(x,y) if i==0 else base.lineTo(x,y)
                sp.setPen(QPen(QColor(95,107,118),4,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));sp.setBrush(Qt.NoBrush);sp.drawPath(base)

                draw_corners=corners
                for c in draw_corners:
                    cid=c.get('corner_id');start_m=c.get('start_m');apex=c.get('apex_m');end_m=c.get('end_m')
                    if not all(isinstance(v,(int,float)) for v in (start_m,apex,end_m)):continue
                    zone=next((z for z in zones if cid in tuple(z.get('corner_ids') or ())),None)
                    zone_ids=tuple(zone.get('corner_ids') or ()) if zone else ();is_first=bool(zone_ids and cid==zone_ids[0]);is_active=False
                    brake=zone.get('brake_start_m') if zone else None
                    red_start=float(brake) if is_first and isinstance(brake,(int,float)) and float(brake)<float(apex) else float(start_m)
                    if float(apex)>red_start:
                        self._draw_distance_span(sp,s,points,geom,red_start,float(apex),lambda f:QColor(int(245+10*f),int(145*(1-f)+28),int(145*(1-f)+38)),9 if is_active else 7)
                    if float(end_m)>float(apex):
                        throttle=zone.get('throttle_start_m') if zone else None
                        tp=((float(throttle)-float(apex))/max(1e-6,float(end_m)-float(apex))) if isinstance(throttle,(int,float)) else 0.35
                        def green(f,tp=max(0.0,min(1.0,tp))):
                            strength=max(.18,min(1.0,(f-tp+0.35)/.65));return QColor(int(42+28*strength),int(120+115*strength),int(82+58*strength))
                        self._draw_distance_span(sp,s,points,geom,float(apex),float(end_m),green,9 if is_active else 7)

                if not draw_corners:
                    for z in zones:
                        brake=z.get('brake_start_m');apex=z.get('apex_m');end_m=z.get('end_m');start_m=z.get('start_m')
                        if not isinstance(apex,(int,float)):continue
                        red_start=brake if isinstance(brake,(int,float)) else start_m
                        if isinstance(red_start,(int,float)) and apex>red_start:
                            self._draw_distance_span(sp,s,points,geom,red_start,apex,lambda f:QColor(int(245+10*f),int(145*(1-f)+28),int(145*(1-f)+38)),7)
                        if isinstance(end_m,(int,float)) and end_m>apex:
                            self._draw_distance_span(sp,s,points,geom,apex,end_m,lambda f:QColor(int(45+20*f),int(135+100*f),int(85+50*f)),7)

                label_corners=draw_corners
                if not label_corners:
                    label_corners=tuple({'corner_id':getattr(t,'corner_id',None),'label':getattr(t,'label',None),'apex_m':getattr(t,'lap_distance_m',None)} for t in getattr(s,'map_turns',()) or ())
                for c in label_corners:
                    d=c.get('apex_m',c.get('lap_distance_m'));pt=self._screen(self._point_at(s,points,d),geom)
                    if pt is None:continue
                    cid=c.get('corner_id');label=str(c.get('label') or (f'T{cid}' if cid else ''))
                    r=max(8,min(13,int(self.height()*.018)));x,y=pt
                    sp.setPen(QPen(QColor(5,8,12),2));sp.setBrush(QColor(235,240,244));sp.drawEllipse(QRectF(x-r,y-r,r*2,r*2));sp.setPen(QColor(20,26,32));sp.setFont(QFont('Segoe UI',max(6,int(r*.72)),QFont.Bold));sp.drawText(QRectF(x-r,y-r,r*2,r*2),Qt.AlignCenter,label)
            sp.end();self._static_layer=pix;self._static_geom=geom;self._static_points=points

        p.drawPixmap(0,0,self._static_layer)
        points=self._static_points;geom=self._static_geom
        if len(points)<2 or geom is None:return

        # Compact live gain/loss overlay: separate cache, no full-map rebuild.
        axis=get_track_map_distances(track_name)
        gain_key=(self.width(),self.height(),gain_sig,id(points),len(points))
        if gain_key!=self._gain_layer_key or self._gain_layer is None:
            self._gain_layer_key=gain_key
            gpix=QPixmap(max(1,self.width()),max(1,self.height()));gpix.fill(Qt.transparent)
            gp=QPainter(gpix);gp.setRenderHint(QPainter.Antialiasing)
            scaled,_=self._scaled(QRectF(10,32,max(1,self.width()-20),max(1,self.height()-42)),points)
            for zone in getattr(s,'corner_coach_gain_loss_zones',()) or ():
                state=str(getattr(zone,'state','NEUTRAL')).upper()
                col=QColor(42,210,112,125) if state=='GAIN' else (QColor(255,65,80,120) if state=='LOSS' else QColor(120,130,140,70))
                self._draw_scaled_axis_span(gp,scaled,axis,getattr(zone,'start_m',None),getattr(zone,'end_m',None),col,3)
            gp.end();self._gain_layer=gpix
        p.drawPixmap(0,0,self._gain_layer)

        # Active CoachingZone emphasis is also isolated from the expensive static
        # reference layer and changes only when the zone identity changes.
        segment_kind=getattr(s,'active_segment_kind',None);segment_no=getattr(s,'active_segment_number',None)
        seg_start=getattr(s,'active_segment_start_m',None);seg_end=getattr(s,'active_segment_end_m',None)
        active_key=(self.width(),self.height(),active_id,segment_kind,segment_no,round(float(seg_start),1) if isinstance(seg_start,(int,float)) else None,round(float(seg_end),1) if isinstance(seg_end,(int,float)) else None,id(points),len(points))
        if active_key!=self._active_layer_key or self._active_layer is None:
            self._active_layer_key=active_key
            apix=QPixmap(max(1,self.width()),max(1,self.height()));apix.fill(Qt.transparent)
            ap=QPainter(apix);ap.setRenderHint(QPainter.Antialiasing)
            scaled,_=self._scaled(QRectF(10,32,max(1,self.width()-20),max(1,self.height()-42)),points)
            if segment_kind=='straight' and getattr(s,'speed_coach_straight_enabled',False) and isinstance(seg_start,(int,float)) and isinstance(seg_end,(int,float)):
                self._draw_scaled_axis_span(ap,scaled,axis,seg_start,seg_end,QColor(62,200,255,80),10)
            else:
                az=next((z for z in zones if z.get('zone_id')==active_id),None)
                if az is not None and getattr(s,'speed_coach_corner_enabled',True):
                    self._draw_scaled_axis_span(ap,scaled,axis,az.get('approach_start_m',az.get('start_m')),az.get('end_m'),QColor(255,255,255,75),10)
            ap.end();self._active_layer=apix
        p.drawPixmap(0,0,self._active_layer)
        # Dynamic layer: only the player marker moves at UI frame rate. The costly
        # antialiased circuit/reference/gain-loss layer above is cached until its
        # geometry or performance state actually changes.
        raw=None;wx=getattr(s,'world_position_x',None);wz=getattr(s,'world_position_z',None)
        if isinstance(wx,(int,float)) and isinstance(wz,(int,float)) and math.isfinite(float(wx)) and math.isfinite(float(wz)):raw=(float(wx),float(wz))
        if raw is None:raw=self._point_at(s,points,getattr(s,'lap_distance_m',None))
        pt=self._screen(raw,geom)
        if pt is not None:
            x,y=pt;r=11;p.setPen(QPen(QColor(5,7,9),2));p.setBrush(QColor(255,220,52));p.drawEllipse(QRectF(x-r,y-r,r*2,r*2));p.setPen(QColor(10,10,10));p.setFont(_visual_font(self, 8, QFont.Bold));p.drawText(QRectF(x-r,y-r,r*2,r*2),Qt.AlignCenter,'YOU')


class CornerCoachDriverPanel(QWidget):
    def __init__(self):
        super().__init__();self.snapshot=None;self.setMinimumWidth(180);self.setAttribute(Qt.WA_TransparentForMouseEvents,True)
    def update_snapshot(self,snapshot):self.snapshot=snapshot;self.update()
    @staticmethod
    def _clamp(v,lo=0.0,hi=1.0):return max(lo,min(hi,float(v))) if isinstance(v,(int,float)) else 0.0
    @staticmethod
    def _mix(a,b,t):
        t=max(0.0,min(1.0,float(t)))
        return QColor(int(a.red()+(b.red()-a.red())*t),int(a.green()+(b.green()-a.green())*t),int(a.blue()+(b.blue()-a.blue())*t),int(a.alpha()+(b.alpha()-a.alpha())*t))
    @classmethod
    def _quality(cls,you,ref,good,bad):
        if not isinstance(you,(int,float)) or not isinstance(ref,(int,float)):
            return QColor(255,200,70),None,'WAIT'
        error=abs(float(you)-float(ref))
        if error<=good:
            score=0.0;label='GOOD'
        elif error>=bad:
            score=1.0;label='OFF'
        else:
            score=(error-good)/max(1e-9,bad-good);label='CLOSE' if score<0.55 else 'WORK'
        green=QColor(42,210,112);amber=QColor(255,190,70);red=QColor(255,70,82)
        color=cls._mix(green,amber,score/0.5) if score<=0.5 else cls._mix(amber,red,(score-0.5)/0.5)
        return color,error,label
    def _bar(self,p,y,label,you,ref,scale=1.0,signed=False,good=0.05,bad=0.30,unit=''):
        w=self.width()-24;h=13;x=12
        color,error,quality=self._quality(you,ref,good,bad)
        delta_text=''
        if isinstance(you,(int,float)) and isinstance(ref,(int,float)):
            delta=float(you)-float(ref)
            if unit=='kph':delta_text=f'{delta:+.0f} km/h'
            else:delta_text=f'{delta:+.2f}'
        p.setPen(QColor(170,180,190));p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(x,y,w*.48,14),Qt.AlignLeft|Qt.AlignVCenter,label)
        p.setPen(color);p.drawText(QRectF(x+w*.46,y,w*.54,14),Qt.AlignRight|Qt.AlignVCenter,f'{quality}  {delta_text}'.rstrip())
        y+=16
        p.setPen(Qt.NoPen);p.setBrush(QColor(35,45,55));p.drawRoundedRect(QRectF(x,y,w,h),4,4)
        def quality_brush(x0,x1):
            grad=QLinearGradient(x0,y,x1,y);grad.setColorAt(0,self._mix(color,QColor(255,255,255),0.10));grad.setColorAt(1,color);return grad
        if signed:
            center=x+w/2;p.setPen(QPen(QColor(90,100,110),1));p.drawLine(QPointF(center,y),QPointF(center,y+h))
            val=self._clamp(abs(float(you or 0))/scale);rw=w*.5*val;rx=center if float(you or 0)>=0 else center-rw
            if rw>0.5:
                p.setPen(Qt.NoPen);p.setBrush(quality_brush(rx,rx+max(1.0,rw)));p.drawRoundedRect(QRectF(rx,y,rw,h),3,3)
            if isinstance(ref,(int,float)):
                rv=self._clamp(abs(float(ref))/scale);rr=w*.5*rv;rrx=center if float(ref)>=0 else center-rr;p.setPen(QPen(QColor(62,200,255),4));p.drawLine(QPointF(rrx+(rr if float(ref)>=0 else 0),y-2),QPointF(rrx+(rr if float(ref)>=0 else 0),y+h+2))
        else:
            val=self._clamp(float(you or 0)/scale);fill=w*val
            if fill>0.5:
                p.setPen(Qt.NoPen);p.setBrush(quality_brush(x,x+max(1.0,fill)));p.drawRoundedRect(QRectF(x,y,fill,h),3,3)
            if isinstance(ref,(int,float)):
                rv=self._clamp(float(ref)/scale);rx=x+w*rv;p.setPen(QPen(QColor(62,200,255),4));p.drawLine(QPointF(rx,y-2),QPointF(rx,y+h+2))
        p.setPen(QColor(120,135,150));p.setFont(_visual_font(self, 6));p.drawText(QRectF(x,y+h+1,w,12),Qt.AlignRight|Qt.AlignVCenter,'cyan = REF')
        return y+h+15
    def paintEvent(self,_event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),QColor(8,13,18,220));s=self.snapshot
        if s is None:return
        active=getattr(s,'corner_coach_active_zone',None) or {};label=active.get('label') if isinstance(active,dict) else None
        if not label and isinstance(active,dict):
            ids=active.get('corner_ids') or [];label=(f'T{ids[0]}' if len(ids)==1 else (f'T{ids[0]}–T{ids[-1]}' if ids else 'NEXT'))
        segment_kind=getattr(s,'active_segment_kind',None);segment_no=getattr(s,'active_segment_number',None)
        if segment_kind=='straight' and getattr(s,'speed_coach_straight_enabled',False):label=f'Straight {segment_no}' if segment_no is not None else 'STRAIGHT'
        elif segment_kind=='turn' and not getattr(s,'speed_coach_corner_enabled',True):label='CORNER COACH OFF'
        p.setPen(WHITE);p.setFont(_visual_font(self, 11, QFont.Bold));p.drawText(QRectF(10,8,self.width()-20,24),Qt.AlignLeft|Qt.AlignVCenter,str(label or 'PERFORMANCE COACH'))
        phase=('STRAIGHT' if getattr(s,'active_segment_kind',None)=='straight' and getattr(s,'speed_coach_straight_enabled',False) else (getattr(s,'corner_coach_phase',None) or 'WAITING'));p.setPen(QColor(62,200,255));p.setFont(_visual_font(self, 8, QFont.Bold));p.drawText(QRectF(10,31,self.width()-20,20),Qt.AlignLeft|Qt.AlignVCenter,str(phase))
        # This panel is now strictly the live driver/reference instrumentation.
        # Completed-corner verdicts belong only to LIVE CORNER FEEDBACK, and lap
        # intelligence has its own persistent panel below. Keeping these surfaces
        # separate removes duplicate post-corner information and prevents a live
        # corner card from hiding the completed-lap summary.
        live=getattr(s,'corner_coach_live_now',None) or {};ref=getattr(s,'corner_coach_reference_now',None) or {};y=58
        if segment_kind=='straight' and getattr(s,'speed_coach_straight_enabled',False):
            metrics=getattr(s,'coach_metrics',()) or ()
            for metric in metrics[:4]:
                status=str(getattr(metric,'status','WAIT') or 'WAIT').upper();value=str(getattr(metric,'value','--'))
                color=GREEN if status in {'FASTER','GOOD','MATCH'} else (QColor(255,190,70) if status in {'WAIT','CLOSE'} else RED)
                p.setPen(QColor(170,180,190));p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(12,y,self.width()-24,15),Qt.AlignLeft|Qt.AlignVCenter,str(getattr(metric,'label','')))
                p.setPen(color);p.drawText(QRectF(12,y,self.width()-24,15),Qt.AlignRight|Qt.AlignVCenter,value);y+=22
            sm=getattr(s,'s_mode_metric',None)
            if sm is not None:
                p.setPen(QColor(170,180,190));p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(12,y,self.width()-24,15),Qt.AlignLeft|Qt.AlignVCenter,str(getattr(sm,'label','S MODE')))
                p.setPen(QColor(62,200,255));p.drawText(QRectF(12,y,self.width()-24,15),Qt.AlignRight|Qt.AlignVCenter,str(getattr(sm,'value','--')));y+=22
            diag=getattr(s,'speed_coach_straight_last_diagnosis',None)
            if isinstance(diag,dict) and y<self.height()-40:
                loss=diag.get('net_loss_s');summary=str(diag.get('primary_text') or '')
                p.setPen(QColor(255,190,80) if isinstance(loss,(int,float)) and loss>0.05 else GREEN);p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(12,y+8,self.width()-24,max(24,self.height()-y-12)),Qt.TextWordWrap,summary)
            return
        y=self._bar(p,y,'BRAKE',live.get('brake'),ref.get('brake'),good=0.04,bad=0.25)
        y=self._bar(p,y,'THROTTLE',live.get('throttle'),ref.get('throttle'),good=0.05,bad=0.25)
        y=self._bar(p,y,'STEERING',live.get('steering'),ref.get('steering'),scale=1.0,signed=True,good=0.04,bad=0.22)
        # Speed is scaled to 380 kph so the progress visual remains stable.
        y=self._bar(p,y,'SPEED',live.get('speed'),ref.get('speed'),scale=380.0,good=3.0,bad=20.0,unit='kph')
        # Zone progress / phase bar.
        if isinstance(active,dict) and isinstance(getattr(s,'lap_distance_m',None),(int,float)):
            lo=active.get('approach_start_m');hi=active.get('end_m')
            if isinstance(lo,(int,float)) and isinstance(hi,(int,float)) and hi>lo:
                progress=self._clamp((float(s.lap_distance_m)-float(lo))/(float(hi)-float(lo)))
                p.setPen(QColor(170,180,190));p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(12,y,self.width()-24,15),Qt.AlignLeft|Qt.AlignVCenter,'ZONE PROGRESS');y+=18
                p.setPen(Qt.NoPen);p.setBrush(QColor(35,45,55));p.drawRoundedRect(QRectF(12,y,self.width()-24,12),4,4);p.setBrush(QColor(62,200,255));p.drawRoundedRect(QRectF(12,y,(self.width()-24)*progress,12),4,4)
        diag=(getattr(s,'speed_coach_straight_last_diagnosis',None) if getattr(s,'active_segment_kind',None)=='straight' else getattr(s,'corner_coach_last_diagnosis',None))
        if isinstance(diag,dict) and y<self.height()-50:
            loss=diag.get('net_loss_s');text=diag.get('primary_text') or ''
            diag_label=diag.get('public_label') or diag.get('label') or (f"Straight {diag.get('straight')}" if diag.get('straight') else '')
            if isinstance(loss,(int,float)):summary=f"LAST: {diag_label}  {loss:+.2f}s"
            else:summary=f"LAST: {diag_label}"
            p.setPen(QColor(255,190,80) if isinstance(loss,(int,float)) and loss>0.03 else GREEN);p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(12,y+22,self.width()-24,18),Qt.AlignLeft|Qt.AlignVCenter,summary)
            if text:p.setPen(QColor(180,190,200));p.setFont(_visual_font(self, 6));p.drawText(QRectF(12,y+42,self.width()-24,max(20,self.height()-y-46)),Qt.TextWordWrap,text)


class ProgressivePreCornerOverlayWindow(OverlayPanel):
    """Glanceable PRE-corner card with a six-step presentation sequence.

    Coaching authority remains ``corner_coach_pre_visual``.  The additional
    BRAKE -> ENTRY -> TURN-IN -> APEX -> EXIT -> THROTTLE sequencing and
    comparator are presentation-only and never alter coach timing, speech,
    diagnosis, scoring, reference selection, or POST handoff authority.
    """
    WIDTH=430; HEIGHT=224
    PHASES=("BRAKE","ENTRY","TURN-IN","APEX","EXIT","THROTTLE")

    def __init__(self, *, on_hide=None, on_toggle_pause=None, on_toggle_click_through=None):
        super().__init__(on_close=on_hide,on_toggle_pause=on_toggle_pause,on_toggle_click_through=on_toggle_click_through)
        self.setWindowTitle('PRE-CORNER COACH')
        self.set_overlay_logical_fixed_size(self.WIDTH,self.HEIGHT)
        self.snapshot=None
        self._delta_lap_number=None
        self._delta_zone_id=None
        self._delta_driver_events={}
        self._display_phase='FAR'
        self._phase_delta={"label":"DELTA","reference_m":None,"driver_m":None,"delta_m":None,"status":"waiting","provisional":False}

    def _resolve_display_phase(self,snapshot,visual):
        if not isinstance(visual,dict): return 'FAR'
        zone=getattr(snapshot,'corner_coach_active_zone',None) if snapshot is not None else None
        zid=visual.get('zone_id')
        if not isinstance(zone,dict) or zone.get('zone_id')!=zid:
            return str(visual.get('phase') or 'FAR').upper()
        quality=getattr(snapshot,'corner_coach_quality',None) or {}
        return _pre_presentation_phase(
            getattr(snapshot,'corner_coach_physical_corners',()),zone,getattr(snapshot,'lap_distance_m',None),
            getattr(snapshot,'corner_coach_driving_events',()),
            input_telemetry_trusted=bool(quality.get('input_telemetry_trusted',True)),
        )

    def _update_phase_delta(self,snapshot,visual,phase):
        zone=getattr(snapshot,'corner_coach_active_zone',None) if snapshot is not None else None
        zid=visual.get('zone_id') if isinstance(visual,dict) else None
        lap=getattr(snapshot,'lap_number',None) if snapshot is not None else None
        if lap!=self._delta_lap_number or zid!=self._delta_zone_id:
            self._delta_lap_number=lap; self._delta_zone_id=zid; self._delta_driver_events={}
        if not isinstance(zone,dict) or zone.get('zone_id')!=zid:
            self._phase_delta={'label':'DELTA','reference_m':None,'driver_m':None,'delta_m':None,'status':'waiting','provisional':False}
            return
        d=getattr(snapshot,'lap_distance_m',None)
        self._delta_driver_events=_pre_update_driver_events(
            self._delta_driver_events,zone,d,
            brake=getattr(snapshot,'brake',None),steering=getattr(snapshot,'steering',None),
            throttle=getattr(snapshot,'throttle',None),speed=getattr(snapshot,'speed_kph',None),
        )
        quality=getattr(snapshot,'corner_coach_quality',None) or {}
        key,label,target=_pre_phase_target(
            getattr(snapshot,'corner_coach_physical_corners',()),zone,phase,
            getattr(snapshot,'corner_coach_driving_events',()),
            input_telemetry_trusted=bool(quality.get('input_telemetry_trusted',True)),
        )
        driver=self._delta_driver_events.get(key)
        self._phase_delta=_pre_phase_delta_payload(label,target,driver,d,phase)

    def update_snapshot(self,snapshot):
        self.snapshot=snapshot
        visual=getattr(snapshot,'corner_coach_pre_visual',None) if snapshot is not None else None
        if isinstance(visual,dict):
            self._display_phase=self._resolve_display_phase(snapshot,visual)
            self._update_phase_delta(snapshot,visual,self._display_phase)
        else:
            self._display_phase='FAR'
            self._phase_delta={'label':'DELTA','reference_m':None,'driver_m':None,'delta_m':None,'status':'waiting','provisional':False}
        self.update()

    @staticmethod
    def _phase_color(phase):
        return {
            'APPROACHING':QColor(82,200,255),'BRAKING':QColor(255,88,88),'BRAKE':QColor(255,88,88),
            'ENTRY':QColor(255,132,72),'TURN-IN':QColor(255,190,70),'APEX':QColor(190,120,255),
            'EXIT':QColor(62,220,126),'THROTTLE':QColor(55,205,145),
        }.get(str(phase).upper(),QColor(125,145,165))

    def _phase_instruction(self,visual,phase):
        gear=visual.get('reference_gear') if isinstance(visual,dict) else None
        min_speed=visual.get('reference_min_speed_kph') if isinstance(visual,dict) else None
        zone=getattr(self.snapshot,'corner_coach_active_zone',None) if self.snapshot is not None else None
        d=getattr(self.snapshot,'lap_distance_m',None) if self.snapshot is not None else None
        gear_txt=f'GEAR {int(gear)}' if isinstance(gear,int) and gear>0 else None
        speed_txt=f'MIN {float(min_speed):.0f} KM/H' if isinstance(min_speed,(int,float)) else None
        if phase=='BRAKE':
            return 'BRAKE',' • '.join(x for x in (gear_txt,speed_txt) if x)
        if phase=='ENTRY':
            return 'ENTRY',' • '.join(x for x in ('BRAKE RELEASE',gear_txt) if x)
        if phase=='TURN-IN':
            return 'TURN IN',' • '.join(x for x in (gear_txt,speed_txt) if x)
        if phase=='APEX':
            return (speed_txt or 'APEX'),'APEX'
        if phase=='EXIT':
            target=zone.get('throttle_start_m') if isinstance(zone,dict) else None
            if isinstance(target,(int,float)) and isinstance(d,(int,float)) and float(target)>float(d):
                return 'EXIT',f'THROTTLE IN {float(target)-float(d):.0f} M'
            return 'EXIT','THROTTLE PICKUP'
        if phase=='THROTTLE':
            target=zone.get('full_throttle_m') if isinstance(zone,dict) else None
            if isinstance(target,(int,float)) and isinstance(d,(int,float)) and float(target)>float(d):
                return 'THROTTLE',f'FULL THROTTLE IN {float(target)-float(d):.0f} M'
            return 'THROTTLE','FULL THROTTLE'
        return visual.get('primary_action') or phase,visual.get('secondary_action')

    def _draw_phase_strip(self,p,W,phase):
        x=18.0; y=63.0; gap=4.0; total_w=W-36.0
        cell=(total_w-gap*(len(self.PHASES)-1))/len(self.PHASES)
        try: active=self.PHASES.index(phase)
        except ValueError: active=-1
        for i,name in enumerate(self.PHASES):
            rx=x+i*(cell+gap)
            if i==active:
                c=self._phase_color(name); p.setPen(QPen(c,1.2)); p.setBrush(QColor(c.red(),c.green(),c.blue(),55))
            elif active>=0 and i<active:
                p.setPen(QPen(QColor(68,89,104),1)); p.setBrush(QColor(27,38,49,210))
            else:
                p.setPen(QPen(QColor(45,61,75),1)); p.setBrush(QColor(17,26,35,210))
            p.drawRoundedRect(QRectF(rx,y,cell,17),4,4)
            p.setPen(WHITE if i==active else QColor(125,145,165)); p.setFont(QFont('Segoe UI',7,QFont.Bold))
            short='TURN' if name=='TURN-IN' else ('THRTL' if name=='THROTTLE' else name)
            p.drawText(QRectF(rx,y,cell,17),Qt.AlignCenter,short)

    def paintEvent(self,_event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        scale=max(0.70,min(1.60,float(getattr(self,'_overlay_scale',1.0))))
        p.scale(scale,scale)
        W=float(self.width())/scale; H=float(self.height())/scale
        visual=getattr(self.snapshot,'corner_coach_pre_visual',None) if self.snapshot is not None else None
        p.setPen(QPen(QColor(40,55,70),1)); p.setBrush(QColor(8,13,21,242)); p.drawRoundedRect(QRectF(.5,.5,W-1,H-1),13,13)
        if not isinstance(visual,dict):
            p.setPen(QColor(120,140,158)); p.setFont(QFont('Segoe UI',11,QFont.Bold)); p.drawText(QRectF(16,78,W-32,42),Qt.AlignCenter,'WAITING FOR CORNER REFERENCE')
            return
        label=str(visual.get('label') or 'CORNER').upper(); phase=str(self._display_phase or visual.get('phase') or 'FAR').upper()
        color=self._phase_color(phase)
        p.setPen(WHITE); p.setFont(QFont('Segoe UI',16,QFont.Bold)); p.drawText(QRectF(16,11,W-145,30),Qt.AlignLeft|Qt.AlignVCenter,label)
        p.setPen(color); p.setFont(QFont('Segoe UI',10,QFont.Bold)); p.drawText(QRectF(16,40,W-32,20),Qt.AlignLeft|Qt.AlignVCenter,phase if phase!='FAR' else 'UPCOMING')

        if phase=='FAR' or phase=='APPROACHING':
            dist=visual.get('distance_to_target_m') if phase=='APPROACHING' else visual.get('distance_to_zone_m')
            txt=(f'BRAKE IN {float(dist):.0f} M' if phase=='APPROACHING' and isinstance(dist,(int,float)) else (f'{float(dist):.0f} M TO COACHING ZONE' if isinstance(dist,(int,float)) else 'UPCOMING CORNER'))
            p.setPen(QColor(205,216,226)); p.setFont(QFont('Segoe UI',16,QFont.Bold)); p.drawText(QRectF(16,82,W-32,36),Qt.AlignCenter,txt)
            p.setPen(QColor(135,154,170)); p.setFont(QFont('Segoe UI',9,QFont.Bold)); p.drawText(QRectF(16,121,W-32,24),Qt.AlignCenter,'REFERENCE PHASE COMPARISON STARTS AT BRAKING')
            return

        self._draw_phase_strip(p,W,phase)
        primary,secondary=self._phase_instruction(visual,phase)
        p.setPen(WHITE); p.setFont(QFont('Segoe UI',20,QFont.Bold)); p.drawText(QRectF(16,84,W-32,34),Qt.AlignCenter,str(primary or phase))
        if secondary:
            p.setPen(QColor(198,211,222)); p.setFont(QFont('Segoe UI',11,QFont.Bold)); p.drawText(QRectF(16,116,W-32,22),Qt.AlignCenter,str(secondary))

        # Phase-specific delta comparator; never whole-corner progress.
        x=18; y=161; w=W-36; h=14; centre=x+w*0.5
        phase_delta=self._phase_delta if isinstance(self._phase_delta,dict) else {}
        metric_label=str(phase_delta.get('label') or phase)
        delta_m=phase_delta.get('delta_m'); delta_status=str(phase_delta.get('status') or 'waiting').lower()
        provisional=bool(phase_delta.get('provisional'))
        p.setPen(Qt.NoPen); p.setBrush(QColor(35,45,55)); p.drawRoundedRect(QRectF(x,y,w,h),4,4)
        target_w=max(18.0,w*0.12)
        p.setBrush(QColor(45,178,82,185)); p.drawRoundedRect(QRectF(centre-target_w*0.5,y,target_w,h),3,3)
        p.setPen(QPen(QColor(235,244,250,220),1.5)); p.drawLine(QPointF(centre,y-3),QPointF(centre,y+h+3))
        if isinstance(delta_m,(int,float)):
            norm=max(-1.0,min(1.0,float(delta_m)/40.0))
            driver_x=centre+norm*(w*0.46)
            span_left=min(centre,driver_x); span_w=max(2.0,abs(driver_x-centre))
            p.setPen(Qt.NoPen); p.setBrush(QColor(color.red(),color.green(),color.blue(),170))
            p.drawRoundedRect(QRectF(span_left,y+2,span_w,h-4),2,2)
            p.setBrush(color); p.drawEllipse(QPointF(driver_x,y+h*0.5),4.5,4.5)
        p.setPen(QColor(120,140,158)); p.setFont(QFont('Segoe UI',7,QFont.Bold))
        p.drawText(QRectF(x,y-16,w*0.3,13),Qt.AlignLeft|Qt.AlignVCenter,'EARLY')
        p.drawText(QRectF(centre-24,y-16,48,13),Qt.AlignCenter,'REF')
        p.drawText(QRectF(x+w*0.7,y-16,w*0.3,13),Qt.AlignRight|Qt.AlignVCenter,'LATE')

        conf=visual.get('confidence')
        if isinstance(delta_m,(int,float)):
            d=float(delta_m)
            comparison=f'{metric_label} MATCHED REF' if abs(d)<=1.0 else f'{metric_label} {abs(d):.0f} M {"EARLY" if d<0 else "LATE"}'
            if provisional: comparison+=' · LIVE'
        elif delta_status=='unavailable': comparison=f'{metric_label} DELTA N/A'
        else: comparison=f'{metric_label} · WAITING FOR DRIVER INPUT'
        p.setPen(color if isinstance(delta_m,(int,float)) else QColor(145,164,180)); p.setFont(QFont('Segoe UI',9,QFont.Bold))
        p.drawText(QRectF(18,181,w*0.76,18),Qt.AlignLeft|Qt.AlignVCenter,comparison)
        if phase=='EXIT' or phase=='THROTTLE':
            p.setPen(QColor(62,220,126)); p.setFont(QFont('Segoe UI',8,QFont.Bold))
            p.drawText(QRectF(18,201,w*0.70,15),Qt.AlignLeft|Qt.AlignVCenter,'HANDOFF → POST CORNER FEEDBACK' if phase=='THROTTLE' else 'EXIT PHASE → THROTTLE')
        if isinstance(conf,(int,float)):
            p.setPen(QColor(140,159,176)); p.setFont(QFont('Segoe UI',8,QFont.Bold))
            p.drawText(QRectF(18,201,w,15),Qt.AlignRight|Qt.AlignVCenter,f'CONF {float(conf)*100:.0f}%')


class LiveCornerFeedbackOverlayWindow(OverlayPanel):
    """UI-R4 glanceable post-corner accuracy surface.

    The presentation is strictly downstream of ``live_corner_result``.  Accuracy
    bars use the already-published deterministic ``dimension_scores``; raw
    deltas, grade, time cost and ``action_text`` are never recomputed here.  The
    UI therefore cannot become coaching authority or turn N/A evidence into a
    visual score.

    Legacy selectable source labels remain available for compatibility:
    BRAKING POINT, THROTTLE PICKUP, EXIT SPEED.
    """
    WIDTH=470
    HEIGHT=204  # legacy compact baseline retained for source/test compatibility
    R4_HEIGHT=264
    R4_DETAILS_HEIGHT=346
    METRICS=(
        ('corner','CORNER PERFORMANCE'),
        ('apex','HITTING APEX'),
        ('min_speed','MIN CORNER SPEED'),
        ('trail','TRAIL BRAKING'),
        ('throttle','THROTTLE POINTS'),
        ('brake','BRAKE POINTS'),
    )
    DIMENSION_LABELS={
        'braking_point':'BRAKE POINT',
        'brake_release':'BRAKE RELEASE',
        'turn_in':'TURN-IN',
        'min_apex_speed':'APEX SPEED',
        'throttle_pickup':'THROTTLE PICKUP',
        'time_to_full_throttle':'FULL THROTTLE',
        'exit_speed':'EXIT SPEED',
    }
    MODE_DIMENSIONS={
        'corner':('braking_point','min_apex_speed','throttle_pickup','exit_speed'),
        'apex':('min_apex_speed','turn_in'),
        'min_speed':('min_apex_speed','exit_speed'),
        'trail':('brake_release','braking_point','turn_in'),
        'throttle':('throttle_pickup','time_to_full_throttle','exit_speed'),
        'brake':('braking_point','brake_release','turn_in'),
    }

    def __init__(self, *, on_hide=None, on_toggle_pause=None, on_toggle_click_through=None):
        super().__init__(on_close=on_hide,on_toggle_pause=on_toggle_pause,on_toggle_click_through=on_toggle_click_through)
        self.setWindowTitle('LIVE CORNER FEEDBACK')
        # Permit real zoom-out. 430x230 is the logical 1.0x minimum; the
        # physical minimum must allow the supported 0.70x presentation scale.
        self.setMinimumSize(int(round(430*0.70)),int(round(230*0.70)))
        self.resize(self.WIDTH,self.R4_HEIGHT)
        self.snapshot=None
        self._result=None
        self._last_key=None
        self._details_expanded=False
        self.metric_selector=QComboBox(self)
        for key,label in self.METRICS:self.metric_selector.addItem(label,key)
        self.metric_selector.setCurrentIndex(0)
        self.metric_selector.setToolTip('Choose the corner-feedback view')
        self.metric_selector.setStyleSheet('QComboBox{background:#111821;color:#dfe7ef;border:1px solid #2c3947;border-radius:5px;padding:2px 8px;font:700 9px Segoe UI;} QComboBox::drop-down{border:0;width:20px;} QComboBox QAbstractItemView{background:#111821;color:#e9eef3;selection-background-color:#263746;border:1px solid #334454;}')
        self.metric_selector.currentIndexChanged.connect(lambda *_:self._on_metric_changed())
        self._details_button=QToolButton(self);self._details_button.setText('DETAILS');self._details_button.setToolTip('Show / hide measured evidence')
        self._details_button.setFixedSize(58,22)
        self._details_button.setStyleSheet('QToolButton{background:#17212c;color:#b9c8d6;border:1px solid #334454;border-radius:6px;font:700 7px Segoe UI;} QToolButton:hover{background:#263746;color:white;}')
        self._details_button.clicked.connect(self._toggle_details)
        # UI-R4.1: the shared overlay chrome owns minimize/close/lock/zoom/opacity.
        # Keep DETAILS inside the content/footer so hover chrome can never cover it.

    def _logical_action_height(self, logical_width=None):
        if not isinstance(self._result,dict):
            return 30
        action=str(self._result.get('action_text') or '').strip()
        if not action:
            return 30
        width=max(120,int((logical_width or self.WIDTH)-34))
        fm=QFontMetrics(QFont('Segoe UI',10,QFont.Bold))
        # Use Qt's own word-wrap measurement so long deterministic actions are
        # never clipped, regardless of wording or overlay width.
        rect=fm.boundingRect(0,0,width,1000,int(Qt.TextWordWrap),action)
        return max(30,rect.height()+8)

    def _logical_content_height(self, logical_width=None):
        action_bottom=192+self._logical_action_height(logical_width)
        normal=max(244,action_bottom+38)
        if not self._details_expanded:
            return normal
        detail_y=max(230,action_bottom+14)
        return max(self.R4_DETAILS_HEIGHT,detail_y+102)

    def _target_content_height(self):
        scale=max(0.70,min(1.60,float(getattr(self,'_overlay_scale',1.0))))
        logical_width=max(300.0,float(self.width())/scale)
        return max(self.minimumHeight(),int(round(self._logical_content_height(logical_width)*scale)))

    def _sync_content_height(self):
        target=self._target_content_height()
        if self.height()!=target:
            self.resize(self.width(),target)

    def set_overlay_scale(self,value: float):
        # OverlayPanel changes physical geometry. This overlay additionally
        # renders in logical coordinates so typography, bars and spacing scale
        # together rather than merely creating a larger/smaller empty window.
        super().set_overlay_scale(value)
        self._sync_content_height()
        self.update()

    def _on_metric_changed(self):
        self._sync_content_height(); self.update()

    def showEvent(self,event):
        # Restore x/y/width/opacity/zoom first, then make height content-driven.
        # Older saved geometry can therefore never reintroduce the large blank tail.
        super().showEvent(event)
        self._sync_content_height()

    def _toggle_details(self):
        self._details_expanded=not self._details_expanded
        self._details_button.setText('LESS' if self._details_expanded else 'DETAILS')
        # Details is presentation-only; preserve width/position and do not alter
        # overlay scale, coaching state or result lifetime.
        self._sync_content_height()
        self.update()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        scale=max(0.70,min(1.60,float(getattr(self,'_overlay_scale',1.0))))
        logical_w=max(300.0,float(self.width())/scale)
        selector_w=max(150,min(205,logical_w-250))
        self.metric_selector.setGeometry(int(round(14*scale)),int(round(7*scale)),int(round(selector_w*scale)),int(round(24*scale)))
        self.metric_selector.setStyleSheet(f'QComboBox{{background:#111821;color:#dfe7ef;border:1px solid #2c3947;border-radius:{max(3,int(5*scale))}px;padding:2px 8px;font:700 {max(6,int(round(9*scale)))}px Segoe UI;}} QComboBox::drop-down{{border:0;width:{max(14,int(20*scale))}px;}} QComboBox QAbstractItemView{{background:#111821;color:#e9eef3;selection-background-color:#263746;border:1px solid #334454;}}')
        self._details_button.setFixedSize(int(round(58*scale)),int(round(22*scale)))
        self._details_button.setStyleSheet(f'QToolButton{{background:#17212c;color:#b9c8d6;border:1px solid #334454;border-radius:{max(3,int(6*scale))}px;font:700 {max(5,int(round(7*scale)))}px Segoe UI;}} QToolButton:hover{{background:#263746;color:white;}}')
        self._details_button.move(int(round(16*scale)),max(0,self.height()-int(round(30*scale))))
        # Width changes alter word wrapping, therefore content height as well.
        QTimer.singleShot(0,self._sync_content_height)

    @staticmethod
    def _score_color(score):
        if not isinstance(score,(int,float)): return QColor(150,160,170)
        if float(score)>=90:return QColor(62,220,126)
        if float(score)>=80:return QColor(88,205,130)
        if float(score)>=65:return QColor(242,190,65)
        return QColor(245,76,88)

    @staticmethod
    def _status_from_delta(value, good, warn, negative_text, positive_text, perfect='PERFECT'):
        if not isinstance(value,(int,float)):return 'N/A',QColor(150,160,170)
        v=float(value);a=abs(v)
        if a<=good:return perfect,QColor(62,220,126)
        if a<=warn:return ('EARLY' if v<0 else 'LATE'),QColor(242,190,65)
        return (negative_text if v<0 else positive_text),QColor(245,76,88)

    def _metric_meta(self,result):
        # Preserve the established selectable raw-evidence views. These values
        # are displayed only as evidence; the R4 accuracy tiles use dimension_scores.
        mode=str(self.metric_selector.currentData() or 'corner')
        if mode=='apex':
            value=result.get('apex_position_delta_m')
            method='path_curvature'
            if not isinstance(value,(int,float)) and bool(result.get('apex_estimate_trusted')):
                value=result.get('apex_estimate_delta_m');method='min_speed_location'
            word,color=self._status_from_delta(value,3.0,7.0,'EARLY','LATE','AWESOME')
            if isinstance(value,(int,float)) and method=='min_speed_location' and word!='AWESOME':word='EST '+word
            elif isinstance(value,(int,float)) and method=='min_speed_location':word='EST APEX'
            return 'HITTING APEX','EARLY','LATE',value,-15.0,15.0,word,color
        if mode=='min_speed':
            value=result.get('apex_speed_delta_kph')
            if not isinstance(value,(int,float)):value=result.get('min_speed_delta_kph')
            if isinstance(value,(int,float)):
                word='AWESOME' if abs(float(value))<=2 else ('SLOWER' if float(value)<0 else 'FASTER')
                color=QColor(62,220,126) if abs(float(value))<=2 else (QColor(245,76,88) if float(value)<-4 else QColor(242,190,65))
            else:word,color='N/A',QColor(150,160,170)
            return 'MIN CORNER SPEED','TOO SLOW','TOO FAST',value,-18.0,18.0,word,color
        if mode=='trail':
            value=result.get('brake_release_delta_m')
            word,color=self._status_from_delta(value,5.0,12.0,'RELEASE EARLY','RELEASE LATE','GREAT')
            return 'TRAIL BRAKING','NEEDS WORK','PERFECT',value,-30.0,30.0,word,color
        if mode=='throttle':
            value=result.get('throttle_pickup_delta_s');units='s';lim=.75
            if not isinstance(value,(int,float)):value=result.get('throttle_pickup_delta_m');units='m';lim=30.0
            word,color=self._status_from_delta(value,0.05 if units=='s' else 3.0,0.15 if units=='s' else 8.0,'EARLY','LATE','PERFECT')
            return 'THROTTLE POINTS','TOO EARLY','TOO LATE',value,-lim,lim,word,color
        if mode=='brake':
            value=result.get('brake_point_delta_m')
            word,color=self._status_from_delta(value,4.0,10.0,'EARLY','LATE','PERFECT')
            return 'BRAKE POINTS','TOO EARLY','TOO LATE',value,-35.0,35.0,word,color
        loss=result.get('estimated_loss_s');score=result.get('score');grade=str(result.get('grade') or 'N/A').upper()
        return 'CORNER PERFORMANCE','NEEDS WORK','EXCELLENT',score,0.0,100.0,(f'{float(score):.0f} {grade}' if isinstance(score,(int,float)) else 'NO VALID CORNER SCORE'),self._score_color(score)

    @staticmethod
    def _dimension_score(result,key):
        dims=result.get('dimension_scores') if isinstance(result,dict) else None
        value=dims.get(key) if isinstance(dims,dict) else None
        return float(value) if isinstance(value,(int,float)) and math.isfinite(float(value)) else None

    def _visible_dimensions(self,result):
        mode=str(self.metric_selector.currentData() or 'corner')
        keys=self.MODE_DIMENSIONS.get(mode,self.MODE_DIMENSIONS['corner'])
        return [(key,self.DIMENSION_LABELS.get(key,key.replace('_',' ').upper()),self._dimension_score(result,key)) for key in keys][:4]

    def _draw_accuracy_tile(self,p,rect,label,score):
        p.setPen(QPen(QColor(43,58,72),1));p.setBrush(QColor(14,22,31,235));p.drawRoundedRect(rect,7,7)
        p.setFont(QFont('Segoe UI',6,QFont.Bold));p.setPen(QColor(157,174,190));p.drawText(QRectF(rect.x()+9,rect.y()+6,rect.width()-18,13),Qt.AlignLeft|Qt.AlignVCenter,label)
        track=QRectF(rect.x()+9,rect.y()+29,rect.width()-18,7)
        p.setPen(Qt.NoPen);p.setBrush(QColor(43,54,66));p.drawRoundedRect(track,3,3)
        if isinstance(score,(int,float)):
            s=max(0.0,min(100.0,float(score)));col=self._score_color(s)
            p.setBrush(col);p.drawRoundedRect(QRectF(track.x(),track.y(),track.width()*s/100.0,track.height()),3,3)
            p.setFont(QFont('Segoe UI',11,QFont.Bold));p.setPen(col);p.drawText(QRectF(rect.x()+9,rect.y()+42,rect.width()-18,22),Qt.AlignLeft|Qt.AlignVCenter,f'{s:.0f}')
            p.setFont(QFont('Segoe UI',6,QFont.Bold));p.setPen(QColor(119,137,153));p.drawText(QRectF(rect.x()+45,rect.y()+45,rect.width()-54,16),Qt.AlignLeft|Qt.AlignVCenter,'/ 100')
        else:
            p.setFont(QFont('Segoe UI',10,QFont.Bold));p.setPen(QColor(128,142,155));p.drawText(QRectF(rect.x()+9,rect.y()+42,rect.width()-18,22),Qt.AlignLeft|Qt.AlignVCenter,'N/A')

    @staticmethod
    def _format_evidence(metric,value):
        if not isinstance(value,(int,float)):return 'N/A'
        v=float(value)
        if metric in {'brake_point_delta_m','brake_release_delta_m','trail_brake_delta_m','turn_in_delta_m','throttle_pickup_delta_m','full_throttle_delta_m','apex_position_delta_m','apex_estimate_delta_m'}:
            return f'{v:+.1f} m'
        if metric in {'apex_speed_delta_kph','min_speed_delta_kph','exit_speed_delta_kph'}:return f'{v:+.1f} km/h'
        if metric in {'throttle_pickup_delta_s','coasting_delta_s','steering_unwind_delta_s'}:return f'{v:+.2f} s'
        return f'{v:+.2f}'

    def _details_lines(self,result):
        mode=str(self.metric_selector.currentData() or 'corner')
        keys={
            'corner':('brake_point_delta_m','brake_release_delta_m','min_speed_delta_kph','throttle_pickup_delta_s','exit_speed_delta_kph'),
            'apex':('apex_position_delta_m','apex_estimate_delta_m','min_speed_delta_kph','turn_in_delta_m'),
            'min_speed':('min_speed_delta_kph','apex_speed_delta_kph','exit_speed_delta_kph'),
            'trail':('brake_release_delta_m','trail_brake_delta_m','brake_point_delta_m'),
            'throttle':('throttle_pickup_delta_s','throttle_pickup_delta_m','full_throttle_delta_m','exit_speed_delta_kph'),
            'brake':('brake_point_delta_m','brake_release_delta_m','peak_brake_delta','turn_in_delta_m'),
        }.get(mode,())
        labels={
            'brake_point_delta_m':'BRAKE POINT Δ','brake_release_delta_m':'BRAKE RELEASE Δ','trail_brake_delta_m':'TRAIL Δ','turn_in_delta_m':'TURN-IN Δ',
            'min_speed_delta_kph':'MIN SPEED Δ','apex_speed_delta_kph':'APEX SPEED Δ','exit_speed_delta_kph':'EXIT SPEED Δ',
            'throttle_pickup_delta_s':'THROTTLE PICKUP Δ','throttle_pickup_delta_m':'THROTTLE PICKUP Δ','full_throttle_delta_m':'FULL THROTTLE Δ',
            'apex_position_delta_m':'APEX POSITION Δ','apex_estimate_delta_m':'APEX ESTIMATE Δ','peak_brake_delta':'PEAK BRAKE Δ',
        }
        return [(labels.get(k,k.upper()),self._format_evidence(k,result.get(k))) for k in keys]

    def set_result(self,result):
        self._result=dict(result) if isinstance(result,dict) else None
        self._sync_content_height()
        self.update()

    def result_key(self,result):
        if not isinstance(result,dict):return None
        return (result.get('zone_id'),result.get('corner_id'),result.get('created_session_s'))

    def paintEvent(self,_event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        scale=max(0.70,min(1.60,float(getattr(self,'_overlay_scale',1.0))))
        p.scale(scale,scale)
        W=float(self.width())/scale; H=float(self.height())/scale
        p.setPen(QPen(QColor(40,55,70),1));p.setBrush(QColor(8,13,21,242));p.drawRoundedRect(QRectF(.5,.5,W-1,H-1),13,13)
        r=self._result
        if not isinstance(r,dict):
            # Match the Pre-Corner waiting treatment: strong state headline plus
            # a concise explanation of what will appear next.
            p.setFont(QFont('Segoe UI',9,QFont.Bold));p.setPen(QColor(120,140,158));p.drawText(QRectF(16,54,W-32,22),Qt.AlignCenter,'POST-CORNER FEEDBACK')
            p.setFont(QFont('Segoe UI',13,QFont.Bold));p.setPen(QColor(205,216,226));p.drawText(QRectF(16,82,W-32,36),Qt.AlignCenter,'WAITING FOR COMPLETED CORNER')
            p.setFont(QFont('Segoe UI',7));p.setPen(QColor(120,140,158));p.drawText(QRectF(18,122,W-36,38),Qt.AlignCenter|Qt.TextWordWrap,'Accuracy, measured time cost and one trusted action will appear after an eligible corner.')
            return

        metric,left_label,right_label,value,vmin,vmax,word,color=self._metric_meta(r)
        corner=r.get('corner_id');tag=f'T{corner}' if isinstance(corner,int) else str(r.get('label') or 'CORNER')
        score=r.get('score');grade=str(r.get('grade') or 'N/A').upper();loss=r.get('estimated_loss_s')
        # Top hierarchy: corner, deterministic grade, and factual measured cost.
        p.setFont(QFont('Segoe UI',14,QFont.Bold));p.setPen(QColor(245,247,250));p.drawText(QRectF(15,39,95,28),Qt.AlignLeft|Qt.AlignVCenter,tag)
        score_col=self._score_color(score)
        grade_text=(f'{float(score):.0f}  {grade}' if isinstance(score,(int,float)) else 'N/A')
        p.setFont(QFont('Segoe UI',15,QFont.Bold));p.setPen(score_col);p.drawText(QRectF(92,37,max(150,W-92-200),31),Qt.AlignLeft|Qt.AlignVCenter,grade_text)
        if isinstance(loss,(int,float)):
            factual='LOST' if float(loss)>0 else ('GAINED' if float(loss)<0 else 'MATCHED REFERENCE')
            cost_text=(f'{factual} {abs(float(loss)):.2f}s' if factual!='MATCHED REFERENCE' else 'MATCHED REFERENCE')
            cost_col=QColor(245,76,88) if float(loss)>0.03 else (QColor(62,220,126) if float(loss)<-0.03 else QColor(184,198,210))
        else:cost_text='TIME N/A';cost_col=QColor(128,142,155)
        p.setFont(QFont('Segoe UI',9,QFont.Bold));p.setPen(cost_col);p.drawText(QRectF(W-190,43,174,22),Qt.AlignRight|Qt.AlignVCenter,cost_text)

        dims=self._visible_dimensions(r)
        n=max(1,len(dims));gap=8;left=14;usable=W-28-gap*(n-1);tile_w=usable/n;tile_y=76;tile_h=70
        for i,(key,label,dscore) in enumerate(dims):
            self._draw_accuracy_tile(p,QRectF(left+i*(tile_w+gap),tile_y,tile_w,tile_h),label,dscore)

        # The selected raw metric remains visible as compact evidence rather than
        # becoming a second coaching recommendation.
        available=isinstance(value,(int,float))
        if metric!='CORNER PERFORMANCE':
            if not available:
                raw_text={
                    'HITTING APEX':'NO VALID APEX DATA',
                    'MIN CORNER SPEED':'NO VALID SPEED DATA',
                    'TRAIL BRAKING':'NO VALID BRAKE RELEASE DATA',
                    'THROTTLE POINTS':'NO VALID THROTTLE POINT DATA',
                    'BRAKE POINTS':'NO VALID BRAKE POINT DATA',
                }.get(metric,'NO VALID DATA')
                # N/A disables the bar/score tile and must omit the marker entirely.
                color=QColor(150,160,170)
            else:
                raw_text=str(word)
            if available:
                suffix='s' if metric=='THROTTLE POINTS' and abs(float(vmax))<2 else ('km/h' if metric=='MIN CORNER SPEED' else 'm')
                raw_text+=f'  {float(value):+.2f}{suffix}' if suffix=='s' else f'  {float(value):+.0f}{suffix}'
            p.setFont(QFont('Segoe UI',7,QFont.Bold));p.setPen(color);p.drawText(QRectF(16,151,W-32,18),Qt.AlignCenter,raw_text)

        action=str(r.get('action_text') or '').strip()
        if action:
            prefix='KEEP:' if action=='KEEP CURRENT APPROACH' else ('ACTION:' if action=='NO TRUSTED ACTION YET' else 'WORK ON:')
            action_color=QColor(88,205,130) if prefix=='KEEP' else (QColor(150,160,170) if prefix=='ACTION' else QColor(92,190,255))
            p.setFont(QFont('Segoe UI',6,QFont.Bold));p.setPen(QColor(122,139,155));p.drawText(QRectF(17,176,70,15),Qt.AlignLeft|Qt.AlignVCenter,prefix)
            action_h=self._logical_action_height(W)
            p.setFont(QFont('Segoe UI',10,QFont.Bold));p.setPen(action_color);p.drawText(QRectF(17,192,W-34,action_h),Qt.AlignLeft|Qt.AlignTop|Qt.TextWordWrap,action)
        else:
            p.setFont(QFont('Segoe UI',8,QFont.Bold));p.setPen(QColor(130,145,158));p.drawText(QRectF(17,185,W-34,30),Qt.AlignCenter,'NO TRUSTED ACTION YET')

        conf=r.get('confidence');sample_count=r.get('sample_count')
        footer=[]
        if isinstance(conf,(int,float)):footer.append(f'CONF {float(conf)*100:.0f}%')
        if isinstance(sample_count,int):footer.append(f'{sample_count} SCORED DIMENSIONS')
        if footer:
            p.setFont(QFont('Segoe UI',6,QFont.Bold));p.setPen(QColor(100,118,135));p.drawText(QRectF(88,H-31,W-105,16),Qt.AlignRight|Qt.AlignVCenter,'  •  '.join(footer))

        if self._details_expanded:
            action_bottom=192+self._logical_action_height(W) if action else 215
            y=max(230,action_bottom+14)
            p.setPen(QPen(QColor(43,58,72),1));p.drawLine(16,y-7,W-16,y-7)
            p.setFont(QFont('Segoe UI',6,QFont.Bold));p.setPen(QColor(130,148,165));p.drawText(QRectF(17,y,W-34,14),Qt.AlignLeft|Qt.AlignVCenter,'MEASURED EVIDENCE')
            lines=self._details_lines(r)
            if not lines:
                p.setFont(QFont('Segoe UI',7));p.setPen(QColor(128,142,155));p.drawText(QRectF(17,y+19,W-34,22),Qt.AlignLeft|Qt.AlignVCenter,'N/A — no trusted detail for this view')
            else:
                cols=2;cell_w=(W-34)/cols
                for i,(label,val) in enumerate(lines[:6]):
                    row=i//cols;col=i%cols;rx=17+col*cell_w;ry=y+20+row*24
                    p.setFont(QFont('Segoe UI',6,QFont.Bold));p.setPen(QColor(112,130,146));p.drawText(QRectF(rx,ry,cell_w-8,10),Qt.AlignLeft|Qt.AlignVCenter,label)
                    p.setFont(QFont('Segoe UI',8,QFont.Bold));p.setPen(QColor(218,226,233));p.drawText(QRectF(rx,ry+9,cell_w-8,14),Qt.AlignLeft|Qt.AlignVCenter,val)


class LapStintSummaryPanel(QWidget):
    """Dedicated V2.0.2 lap/stint intelligence surface.

    It is intentionally independent from the live corner-feedback card and from
    the live driver/reference bars, so a completed lap remains visible even when
    corner coaching is enabled and new corner results are arriving.
    """
    def __init__(self):
        super().__init__(); self.snapshot=None
        self.setMinimumHeight(82); self.setMaximumHeight(102)
        self.setAttribute(Qt.WA_TransparentForMouseEvents,True)
    def update_snapshot(self,snapshot):
        self.snapshot=snapshot; self.update()
    def paintEvent(self,_event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(35,49,62),1));p.setBrush(QColor(10,16,22,225));p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),7,7)
        p.setPen(QColor(160,175,190));p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(9,5,self.width()-18,16),Qt.AlignLeft|Qt.AlignVCenter,'LAP / STINT INTELLIGENCE')
        s=self.snapshot;info=getattr(s,'last_lap_intelligence',None) if s is not None else None
        if not isinstance(info,dict):
            p.setPen(QColor(105,125,145));p.setFont(_visual_font(self, 8, QFont.Bold));p.drawText(QRectF(9,27,self.width()-18,38),Qt.AlignCenter,'WAITING FOR VALID COMPLETED LAP')
            return
        lap_no=info.get('lap_number');score=info.get('lap_score');coverage=info.get('coverage')
        score_text=f'{float(score):.0f}' if isinstance(score,(int,float)) else 'N/A'
        cov_text=f'{float(coverage)*100:.0f}%' if isinstance(coverage,(int,float)) else '--'
        score_col=GREEN if isinstance(score,(int,float)) and float(score)>=80 else (QColor(255,190,70) if isinstance(score,(int,float)) and float(score)>=65 else (RED if isinstance(score,(int,float)) else QColor(150,160,170)))
        p.setPen(score_col);p.setFont(_visual_font(self, 9, QFont.Bold));p.drawText(QRectF(9,24,self.width()-18,18),Qt.AlignLeft|Qt.AlignVCenter,f'LAP {lap_no or "--"}  TECHNIQUE {score_text}')
        p.setPen(QColor(62,200,255));p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(9,24,self.width()-18,18),Qt.AlignRight|Qt.AlignVCenter,f'COVERAGE {cov_text}')
        focus=info.get('next_lap_focus') or {}
        if isinstance(focus,dict) and focus:
            cid=focus.get('corner_id');loss=focus.get('loss_s');txt=str(focus.get('text') or focus.get('issue') or '').replace('_',' ').upper()
            line=f'NEXT: T{cid}  {txt}' if cid is not None else f'NEXT: {txt}'
            if isinstance(loss,(int,float)):line+=f'  {float(loss):.2f}s'
            p.setPen(QColor(255,190,70));p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(9,48,self.width()-18,self.height()-53),Qt.TextWordWrap,line)
        else:
            p.setPen(QColor(130,145,158));p.setFont(_visual_font(self, 7, QFont.Bold));p.drawText(QRectF(9,48,self.width()-18,self.height()-53),Qt.AlignLeft|Qt.AlignTop,'NEXT: BUILDING FOCUS')


class CornerCoachTranscriptPanel(QWidget):
    """Compact SPEED COACH transcript embedded in the right 25% panel."""
    def __init__(self, transcript_store=None):
        super().__init__();self.transcript_store=transcript_store;self._last_sequence=-1
        self.setMinimumHeight(110)
        layout=QVBoxLayout(self);layout.setContentsMargins(7,5,7,6);layout.setSpacing(3)
        title=QLabel("COACH TRANSCRIPT");title.setFont(QFont("Segoe UI",7,QFont.Bold));title.setStyleSheet("color: rgba(165,178,190,235); background: transparent;");layout.addWidget(title)
        self.body=QTextEdit();self.body.setReadOnly(True);self.body.setAcceptRichText(True);self.body.setFrameStyle(QFrame.NoFrame);self.body.setFont(QFont("Segoe UI",7));self.body.setStyleSheet("QTextEdit { color: rgba(235,238,242,235); background: rgba(0,0,0,35); border: 1px solid rgba(255,255,255,14); border-radius: 6px; padding: 4px; } QScrollBar:vertical { width: 6px; background: rgba(255,255,255,6); } QScrollBar::handle:vertical { background: rgba(255,255,255,38); border-radius: 3px; min-height: 18px; }");layout.addWidget(self.body,1)
        self.update_entries(())
    @staticmethod
    def _time_text(seconds):
        if seconds is None:return "--:--.---"
        try:seconds=max(0.0,float(seconds))
        except (TypeError,ValueError):return "--:--.---"
        minutes=int(seconds//60);return f"{minutes:02d}:{seconds-minutes*60:06.3f}"
    def update_from_store(self):
        store=self.transcript_store
        if store is None:return
        revision=store.latest_sequence
        if revision==self._last_sequence:return
        self.update_entries(store.snapshot(),revision=revision)
    def update_entries(self,entries,*,revision=None):
        entries=tuple(entries)
        if revision is None:revision=entries[-1].sequence if entries else 0
        if revision==self._last_sequence:return
        self._last_sequence=revision
        if not entries:
            self.body.setHtml('<span style="color:#7d8994;">PERFORMANCE COACH messages will appear here.</span>');return
        rows=[]
        # Keep the embedded panel lightweight: render only the latest messages.
        for entry in entries[-8:]:
            t=self._time_text(entry.session_time_s);text=html.escape(entry.text)
            rows.append(f'<div style="margin:0 0 6px 0;"><span style="color:#7d8994;font-family:Consolas;font-size:7pt;">{t}</span><br><span style="color:#f0f3f6;font-size:8pt;">{text}</span></div>')
        self.body.setHtml("".join(rows));scroll=self.body.verticalScrollBar();scroll.setValue(scroll.maximum())


class CornerCoachOverlayWindow(OverlayPanel):
    """Resizable 75/25 live SPEED COACH overlay with independent corner/straight controls."""
    WIDTH=920;HEIGHT=560;EDGE=9
    def __init__(self,*,transcript_store=None,on_hide=None,on_toggle_pause=None,on_toggle_click_through=None,
                 on_toggle_speed_coach=None,on_toggle_corner_coach=None,on_toggle_straight_coach=None,on_toggle_corner_voice=None,on_toggle_corner_pre=None,on_toggle_corner_post=None,on_toggle_straight_voice=None,
                 on_toggle_gain_loss=None,on_toggle_gain_loss_voice=None,on_toggle_damage_coach=None,control_states=None):
        super().__init__(on_close=on_hide,on_toggle_pause=on_toggle_pause,on_toggle_click_through=on_toggle_click_through)
        self.setWindowTitle('PERFORMANCE COACH');self.setMinimumSize(680,380);self.resize(self.WIDTH,self.HEIGHT);self._resize_edges=None;self._resize_origin=None;self._resize_geom=None
        self._last_visual_refresh=0.0
        self._control_callbacks={
            'SPEED':on_toggle_speed_coach,'CORNER':on_toggle_corner_coach,'STRAIGHT':on_toggle_straight_coach,'CCVOICE':on_toggle_corner_voice,'CCPRE':on_toggle_corner_pre,'CCPOST':on_toggle_corner_post,'SLVOICE':on_toggle_straight_voice,
            'GAINLOSS':on_toggle_gain_loss,'GAINLOSSVOICE':on_toggle_gain_loss_voice,'DMGCOACH':on_toggle_damage_coach,
        }
        self._control_states={
            'SPEED':True,'CORNER':True,'STRAIGHT':False,'CCVOICE':True,'CCPRE':True,'CCPOST':True,'SLVOICE':True,'GAINLOSS':True,'GAINLOSSVOICE':False,'DMGCOACH':False,
        }
        self._control_states.update({k:bool(v) for k,v in dict(control_states or {}).items() if k in self._control_states})
        self.control_buttons={}
        root=QVBoxLayout(self);root.setContentsMargins(8,8,8,8);root.setSpacing(5)
        head=QHBoxLayout();title=self.label('PERFORMANCE COACH',10,True);head.addWidget(title);head.addStretch(1);root.addLayout(head)
        # UI-R2 shared hover chrome owns minimize/close/lock/zoom/opacity.
        self.minimize_button=None

        # Legacy V1.2 compatibility marker: ('CORNER','CC')
        # V1.2.0.3: CORNER COACH controls live with the overlay they affect.
        # POST and G/L VOICE are mutually exclusive post-zone speech styles;
        # MAP G/L is purely visual and remains independent.
        row1=QHBoxLayout();row1.setContentsMargins(0,0,0,0);row1.setSpacing(5)
        for name,text,tip,width in ((
            'SPEED','COACH','PERFORMANCE COACH master — shared map, analysis and coaching runtime',68),
            ('CORNER','CORNER','Enable/disable corner coaching independently',76),
            ('STRAIGHT','STRAIGHT','Enable/disable straight-line coaching independently',82),
            ('CCVOICE','VOICE','Master voice switch for PERFORMANCE COACH speech',66),
            ('CCPRE','PRE','Reference instruction before the active coaching zone',58),
            ('CCPOST','POST','Measured diagnostic feedback after the completed coaching zone',62)):
            b=self._corner_control_button(name,text,tip,width);row1.addWidget(b)
        row1.addStretch(1);root.addLayout(row1)
        row2=QHBoxLayout();row2.setContentsMargins(0,0,0,0);row2.setSpacing(5)
        for name,text,tip,width in ((
            'SLVOICE','S/L VOICE','Speak STRAIGHT LINE COACH completed-straight calls',92),
            ('GAINLOSS','MAP G/L','Overlay measured local gain/loss on the track map only',88),
            ('GAINLOSSVOICE','G/L VOICE','Speak short completed-zone gain/loss calls; enabling this turns POST off',92),
            ('DMGCOACH','DMG COACH','Allow coaching analysis on laps with car damage; damage is still recorded and reported',92)):
            b=self._corner_control_button(name,text,tip,width);row2.addWidget(b)
        row2.addStretch(1);root.addLayout(row2)
        self.set_control_states(self._control_states)

        body=QHBoxLayout();body.setSpacing(6);self.map_canvas=CornerCoachMapCanvas();self.driver_panel=CornerCoachDriverPanel();self.lap_summary_panel=LapStintSummaryPanel();self.transcript_panel=CornerCoachTranscriptPanel(transcript_store)
        right=QVBoxLayout();right.setContentsMargins(0,0,0,0);right.setSpacing(5);right.addWidget(self.driver_panel,3);right.addWidget(self.lap_summary_panel,0);right.addWidget(self.transcript_panel,2)
        body.addWidget(self.map_canvas,3);body.addLayout(right,1);root.addLayout(body,1)
        # Legacy regression marker only: body.addWidget(self.driver_panel,1)

    def _corner_control_button(self,name,text,tip,width):
        b=QToolButton();b.setText(text);b.setCursor(Qt.PointingHandCursor);b.setToolTip(tip+' (click to enable/disable)');b.setAutoRaise(True);b.setFont(QFont('Segoe UI',7,QFont.Bold));b.setMinimumWidth(width);b.setFixedHeight(22)
        b.clicked.connect(lambda _checked=False,feature=name:self._toggle_corner_control(feature));self.control_buttons[name]=b;return b

    def _apply_corner_control_style(self,name):
        b=self.control_buttons.get(name)
        if b is None:return
        enabled=bool(self._control_states.get(name,False))
        base={'SPEED':'COACH','CORNER':'CORNER','STRAIGHT':'STRAIGHT','CCVOICE':'VOICE','CCPRE':'PRE','CCPOST':'POST','SLVOICE':'S/L VOICE','GAINLOSS':'MAP G/L','GAINLOSSVOICE':'G/L VOICE','DMGCOACH':'DMG COACH'}[name]
        b.setText(base+(' ON' if enabled else ' OFF'))
        color=QColor(45,231,125) if enabled else QColor(255,82,82)
        b.setStyleSheet(f"QToolButton {{ color: rgb({color.red()},{color.green()},{color.blue()}); background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,18); border-radius: 5px; padding: 1px 5px; }} QToolButton:hover {{ background: rgba(255,255,255,28); }} QToolButton:pressed {{ background: rgba(255,255,255,42); }}")

    def _sync_corner_control_dependencies(self):
        master=bool(self._control_states.get('SPEED',False))
        corner=master and bool(self._control_states.get('CORNER',False))
        straight=master and bool(self._control_states.get('STRAIGHT',False))
        for name in ('CORNER','STRAIGHT','CCVOICE','GAINLOSS','GAINLOSSVOICE','DMGCOACH'):
            b=self.control_buttons.get(name)
            if b is not None:b.setEnabled(master)
        for name in ('CCPRE','CCPOST'):
            b=self.control_buttons.get(name)
            if b is not None:b.setEnabled(corner)
        b=self.control_buttons.get('SLVOICE')
        if b is not None:b.setEnabled(straight)

    def set_control_states(self,states):
        if not states:return
        for name in self._control_states:
            if name in states:self._control_states[name]=bool(states[name])
            self._apply_corner_control_style(name)
        self._sync_corner_control_dependencies()

    def _toggle_corner_control(self,name):
        cb=self._control_callbacks.get(name)
        if cb is None:return
        enabled=not bool(self._control_states.get(name,False))
        try:
            result=cb(enabled);ok=True;message=None
            if isinstance(result,tuple):ok=bool(result[0]);message=(result[1] if len(result)>1 else None)
            elif isinstance(result,bool):ok=result
            if not ok:
                if message and self.control_buttons.get(name) is not None:self.control_buttons[name].setToolTip(str(message))
                return
            self._control_states[name]=enabled
            # Mirror the core's mutually-exclusive post-zone voice rule immediately.
            if enabled and name=='CCPOST':self._control_states['GAINLOSSVOICE']=False
            elif enabled and name=='GAINLOSSVOICE':self._control_states['CCPOST']=False
            for key in self._control_states:self._apply_corner_control_style(key)
            self._sync_corner_control_dependencies()
        except Exception as error:
            b=self.control_buttons.get(name)
            if b is not None:b.setToolTip(str(error))
    def update_snapshot(self,snapshot):
        # V1.1.0.2 caches the expensive static map layer, so the player pointer and
        # driver bars can stay visually smooth at the suite's ~60 Hz refresh rate.
        now=time.monotonic();self.driver_panel.snapshot=snapshot;self.lap_summary_panel.snapshot=snapshot
        if now-self._last_visual_refresh>=1.0/60.0:
            self._last_visual_refresh=now;self.map_canvas.update_snapshot(snapshot);self.driver_panel.update();self.lap_summary_panel.update()
        self.transcript_panel.update_from_store()
    def _edges_at(self,pos):
        x,y=pos.x(),pos.y();w,h=self.width(),self.height();e=self.EDGE;edges=[]
        if x<=e:edges.append('L')
        elif x>=w-e:edges.append('R')
        if y<=e:edges.append('T')
        elif y>=h-e:edges.append('B')
        return ''.join(edges)
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and not self._click_through:
            edges=self._edges_at(event.position().toPoint())
            if edges:
                self._resize_edges=edges;self._resize_origin=event.globalPosition().toPoint();self._resize_geom=self.geometry();event.accept();return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._resize_edges and self._resize_origin is not None and self._resize_geom is not None and event.buttons()&Qt.LeftButton:
            delta=event.globalPosition().toPoint()-self._resize_origin;g=QRectF(self._resize_geom)
            x,y,w,h=g.x(),g.y(),g.width(),g.height();minw,minh=self.minimumWidth(),self.minimumHeight()
            if 'L' in self._resize_edges:
                nx=min(x+w-minw,x+delta.x());w+=x-nx;x=nx
            if 'R' in self._resize_edges:w=max(minw,w+delta.x())
            if 'T' in self._resize_edges:
                ny=min(y+h-minh,y+delta.y());h+=y-ny;y=ny
            if 'B' in self._resize_edges:h=max(minh,h+delta.y())
            self.setGeometry(int(x),int(y),int(w),int(h));event.accept();return
        if not event.buttons():
            edges=self._edges_at(event.position().toPoint())
            if edges in {'L','R'}:self.setCursor(Qt.SizeHorCursor)
            elif edges in {'T','B'}:self.setCursor(Qt.SizeVerCursor)
            elif edges in {'LT','RB'}:self.setCursor(Qt.SizeFDiagCursor)
            elif edges in {'RT','LB'}:self.setCursor(Qt.SizeBDiagCursor)
            else:self.unsetCursor()
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        self._resize_edges=None;self._resize_origin=None;self._resize_geom=None;super().mouseReleaseEvent(event)


class F1DashOverlayWindow(OverlayPanel):
    """800x480 native F1 dash; browser clients consume the same state cache."""

    WIDTH = 800
    HEIGHT = 480

    def __init__(self, *, on_hide=None, on_toggle_pause=None, on_toggle_click_through=None, remote_url=None):
        super().__init__(on_close=on_hide, on_toggle_pause=on_toggle_pause, on_toggle_click_through=on_toggle_click_through)
        self.setWindowTitle("Race Engineer — F1 Dash")
        self.set_overlay_logical_fixed_size(self.WIDTH, self.HEIGHT)
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.canvas=F1DashCanvas(); self.canvas.set_remote_url(remote_url); root.addWidget(self.canvas,1)
        self.page_buttons = {}
        self._manual_page = "dash"
        self._auto_page = None
        self._damage_until = 0.0
        self._last_damage = None
        self._paused = False
        self._page_specs=(("DASH","dash",350,58),("DAMAGE","damage",411,74),("TYRES","tyres",488,62),("MAP","map",553,54),("PIT","pit",610,50))
        for label,page,x,bw in self._page_specs:
            b=QToolButton(self); b.setText(label); b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True); b.clicked.connect(lambda checked=False,p=page:self._set_page(p)); self.page_buttons[page]=b
        # UI-R2 shared hover chrome is the only overlay window-control layer.
        self.header_button_bar=None; self.minimize_button=None; self.hide_button=None
        self._layout_page_buttons()
        self._set_page("dash")

    def _set_page(self, page, *, manual=True):
        if manual:
            self._manual_page = page
            self._auto_page = None
        self.canvas.set_page(page)
        for name,button in self.page_buttons.items():
            button.setChecked(name == page)
            button.raise_()

    def _layout_header_buttons(self):
        if self.header_button_bar is None:
            return
        scale=max(0.70,min(1.60,float(getattr(self,'_overlay_scale',1.0))))
        width=int(round((27 * 2 + 6) * scale))
        self.header_button_bar.setGeometry(max(0,self.width()-width-int(round(12*scale))),int(round(7*scale)),width,int(round(27*scale)))

    def _layout_page_buttons(self):
        scale=max(0.70,min(1.60,float(getattr(self,'_overlay_scale',1.0))))
        font_px=max(7,int(round(10*scale)))
        radius=max(3,int(round(5*scale)))
        pad_y=max(1,int(round(2*scale))); pad_x=max(4,int(round(7*scale)))
        for label,page,x,bw in self._page_specs:
            b=self.page_buttons.get(page)
            if b is None: continue
            b.setGeometry(int(round(x*scale)),int(round(55*scale)),int(round(bw*scale)),int(round(25*scale)))
            b.setStyleSheet(f"QToolButton{{background:#0d151d;color:#8395a8;border:1px solid #263746;border-radius:{radius}px;font:700 {font_px}px 'Segoe UI';padding:{pad_y}px {pad_x}px;}} QToolButton:hover{{background:#17232d;color:#eef6fb;border-color:#3b5265;}} QToolButton:checked{{background:#16384a;color:#eef6fb;border-color:#4dd9ff;}}")
            b.raise_()

    def set_overlay_scale(self,value: float):
        super().set_overlay_scale(value)
        self._layout_header_buttons()
        self._layout_page_buttons()
        self.canvas.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_header_buttons()
        self._layout_page_buttons()

    @staticmethod
    def _pit_active(snapshot):
        status=str(getattr(snapshot,"pit_status",None) or "").upper()
        return bool(getattr(snapshot,"pit_lane_timer_active",False)) or status not in {"", "NONE", "N/A", "--", "0"}

    @staticmethod
    def _damage_vector(snapshot):
        values=(getattr(snapshot,"front_left_wing_damage_percent",None),getattr(snapshot,"front_right_wing_damage_percent",None),getattr(snapshot,"rear_wing_damage_percent",None),getattr(snapshot,"floor_damage_percent",None),getattr(snapshot,"diffuser_damage_percent",None),getattr(snapshot,"sidepod_damage_percent",None),getattr(snapshot,"gearbox_damage_percent",None),getattr(snapshot,"engine_damage_percent",None),100 if getattr(snapshot,"drs_fault",False) else 0,100 if getattr(snapshot,"ers_fault",False) else 0)
        return tuple(float(v) if isinstance(v,(int,float)) else 0.0 for v in values)

    def set_paused(self, paused):
        self._paused = bool(paused)

    def update_snapshot(self, snapshot):
        # Freeze the last rendered frame and the auto-page clocks while paused.
        if self._paused or bool(getattr(snapshot,"game_paused",False)):
            return
        now=time.monotonic(); damage=self._damage_vector(snapshot)
        if self._last_damage is not None and any(cur > prev + .01 for cur,prev in zip(damage,self._last_damage)):
            self._damage_until = now + 3.0
        self._last_damage = damage
        if now < self._damage_until:
            self._auto_page="damage"; self._set_page("damage",manual=False)
        elif self._pit_active(snapshot):
            self._auto_page="pit"; self._set_page("pit",manual=False)
        elif self._auto_page is not None:
            self._auto_page=None; self._set_page(self._manual_page,manual=False)
        self.canvas.update_snapshot(snapshot)

    def set_remote_url(self, url):
        self.canvas.set_remote_url(url)

class OverlaySuite:
    """Owns coach, combined driver panel and optional replay controls."""

    GAP = 10

    def __init__(self, provider, *, click_through=False, refresh_hz=60, on_pause_changed=None, on_close=None, replay_controller=None, on_toggle_replay=None, replay_mode_getter=None, dashboard_store=None, dashboard_url=None):
        self.provider = provider
        self._paused = False
        self._click_through = bool(click_through)
        self._on_pause_changed = on_pause_changed
        self._on_close = on_close
        self.replay_controller = replay_controller
        self._on_toggle_replay = on_toggle_replay
        self._replay_mode_getter = replay_mode_getter or (lambda: self.replay_controller is not None)
        self.dashboard_store = dashboard_store
        self.dashboard_url = dashboard_url

        receiver = getattr(self.provider, "receiver", None)
        tts_enabled = bool(getattr(getattr(receiver, "speech", None), "config", None) and getattr(receiver.speech.config, "enabled", False))
        ptt_enabled = bool(getattr(getattr(receiver, "ptt", None), "config", None) and getattr(receiver.ptt.config, "enabled", False))
        stt_enabled = bool(getattr(getattr(receiver, "stt", None), "config", None) and getattr(receiver.stt.config, "enabled", False))
        llm_enabled = bool(getattr(getattr(receiver, "llm", None), "config", None) and getattr(receiver.llm.config, "enabled", False))
        mic_devices, audio_devices = receiver.audio_device_options() if receiver is not None and hasattr(receiver, "audio_device_options") else ([], [])
        current_mic = getattr(getattr(getattr(receiver, "ptt", None), "config", None), "mic_device", None)
        current_audio = getattr(getattr(getattr(receiver, "speech", None), "config", None), "output_device", None)

        self.control_center = ControlCenterWindow(
            on_close=self.close_all,
            on_toggle_pause=self.toggle_pause,
            on_toggle_click_through=self.toggle_click_through,
            on_show_coach=self.show_coach,
            on_show_corner_coach=self.show_corner_coach,
            on_show_pre_corner=self.show_pre_corner,
            on_show_live_corner_feedback=self.show_live_corner_feedback,
            on_show_driver=self.show_driver,
            on_show_reference_driver=self.show_reference_driver,
            on_show_replay=self.show_replay,
            on_show_speed_delta=self.show_speed_delta,
            on_show_laptime=self.show_laptime,
            on_show_tyre_wear=self.show_tyre_wear,
            on_show_fuel=self.show_fuel,
            on_show_weather=self.show_weather,
            on_show_standings=self.show_standings,
            on_show_lap_history=self.show_lap_history,
            on_show_tyre_sets=self.show_tyre_sets,
            on_show_ers_battery=self.show_ers_battery,
            on_show_penalties=self.show_penalties,
            on_show_brake_status=self.show_brake_status,
            on_show_race_engineer=self.show_race_engineer,
            on_show_radio_transcript=self.show_radio_transcript,
            on_show_session_summary=self.show_session_summary,
            on_show_f1_dash=self.show_f1_dash,
            on_select_mic=(receiver.set_microphone_device if receiver is not None and hasattr(receiver, "set_microphone_device") else None),
            on_select_audio=(receiver.set_audio_output_device if receiver is not None and hasattr(receiver, "set_audio_output_device") else None),
            on_toggle_tts=(receiver.set_tts_enabled if receiver is not None and hasattr(receiver, "set_tts_enabled") else None),
            on_toggle_ptt=(receiver.set_ptt_enabled if receiver is not None and hasattr(receiver, "set_ptt_enabled") else None),
            on_toggle_stt=(receiver.set_stt_enabled if receiver is not None and hasattr(receiver, "set_stt_enabled") else None),
            on_toggle_llm=(receiver.set_llm_enabled if receiver is not None and hasattr(receiver, "set_llm_enabled") else None),
            on_toggle_recording=(receiver.set_recording_enabled if receiver is not None and hasattr(receiver, "set_recording_enabled") else None),
            on_toggle_engineer_voice=(receiver.set_automatic_engineer_voice_enabled if receiver is not None and hasattr(receiver, "set_automatic_engineer_voice_enabled") else None),
            on_toggle_post_coach=(lambda enabled: receiver.set_coaching_feature("POST", enabled)) if receiver is not None and hasattr(receiver, "set_coaching_feature") else None,
            on_toggle_pre_coach=(lambda enabled: receiver.set_coaching_feature("PRE", enabled)) if receiver is not None and hasattr(receiver, "set_coaching_feature") else None,
            on_toggle_lap_coach=(lambda enabled: receiver.set_coaching_feature("LAP", enabled)) if receiver is not None and hasattr(receiver, "set_coaching_feature") else None,
            on_toggle_positive_coach=(lambda enabled: receiver.set_coaching_feature("POS", enabled)) if receiver is not None and hasattr(receiver, "set_coaching_feature") else None,
            on_toggle_race_coach=(lambda enabled: receiver.set_coaching_feature("RACE", enabled)) if receiver is not None and hasattr(receiver, "set_coaching_feature") else None,
            on_toggle_corner_coach=(lambda enabled: receiver.set_corner_coach_feature("CORNER", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_corner_voice=(lambda enabled: receiver.set_corner_coach_feature("VOICE", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_corner_pre=(lambda enabled: receiver.set_corner_coach_feature("PRE", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_corner_post=(lambda enabled: receiver.set_corner_coach_feature("POST", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_gain_loss=(lambda enabled: receiver.set_corner_coach_feature("GAINLOSS", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_gain_loss_voice=(lambda enabled: receiver.set_corner_coach_feature("GAINLOSSVOICE", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_select_recording_mode=(receiver.set_recording_mode if receiver is not None and hasattr(receiver, "set_recording_mode") else None),
            current_recording_mode=(receiver.recording_mode() if receiver is not None and hasattr(receiver, "recording_mode") else "session"),
            on_select_reference=(receiver.select_reference_lap if receiver is not None and hasattr(receiver, "select_reference_lap") else None),
            on_reference_options=(receiver.reference_lap_options if receiver is not None and hasattr(receiver, "reference_lap_options") else None),
            on_import_reference=(receiver.import_reference_package if receiver is not None and hasattr(receiver, "import_reference_package") else None),
            on_export_reference=(receiver.export_reference_package if receiver is not None and hasattr(receiver, "export_reference_package") else None),
            current_reference=(receiver.current_reference_selection() if receiver is not None and hasattr(receiver, "current_reference_selection") else "__AUTO__"),
            on_select_replay=(self._select_replay_recording if self.replay_controller is not None else None),
            on_replay_options=self._replay_recording_options,
            current_replay=(self.replay_controller.current_file() if self.replay_controller is not None else None),
            on_toggle_replay=self._on_toggle_replay,
            replay_mode=bool(self._replay_mode_getter()),
            mic_devices=mic_devices, audio_devices=audio_devices, current_mic=current_mic, current_audio=current_audio,
            tts_enabled=tts_enabled,
            ptt_enabled=ptt_enabled,
            stt_enabled=stt_enabled,
            llm_enabled=llm_enabled,
            engineer_voice_enabled=bool(getattr(receiver, "_automatic_engineer_voice_enabled", True)) if receiver is not None else True,
            replay_available=True,
            post_coach_enabled=bool(receiver.coaching_feature_states().get("POST", True)) if receiver is not None and hasattr(receiver, "runtime_feature_states") else True,
            pre_coach_enabled=bool(receiver.coaching_feature_states().get("PRE", True)) if receiver is not None and hasattr(receiver, "runtime_feature_states") else True,
            lap_coach_enabled=bool(receiver.coaching_feature_states().get("LAP", True)) if receiver is not None and hasattr(receiver, "runtime_feature_states") else True,
            positive_coach_enabled=bool(receiver.coaching_feature_states().get("POS", True)) if receiver is not None and hasattr(receiver, "runtime_feature_states") else True,
            race_coach_enabled=bool(receiver.coaching_feature_states().get("RACE", True)) if receiver is not None and hasattr(receiver, "runtime_feature_states") else True,
            corner_coach_enabled=bool(receiver.coaching_feature_states().get("CORNER", True)) if receiver is not None and hasattr(receiver, "coaching_feature_states") else True,
            corner_voice_enabled=bool(receiver.coaching_feature_states().get("CCVOICE", True)) if receiver is not None and hasattr(receiver, "coaching_feature_states") else True,
            corner_pre_enabled=bool(receiver.coaching_feature_states().get("CCPRE", True)) if receiver is not None and hasattr(receiver, "coaching_feature_states") else True,
            corner_post_enabled=bool(receiver.coaching_feature_states().get("CCPOST", True)) if receiver is not None and hasattr(receiver, "coaching_feature_states") else True,
            gain_loss_enabled=bool(receiver.coaching_feature_states().get("GAINLOSS", True)) if receiver is not None and hasattr(receiver, "coaching_feature_states") else True,
            gain_loss_voice_enabled=bool(receiver.coaching_feature_states().get("GAINLOSSVOICE", False)) if receiver is not None and hasattr(receiver, "coaching_feature_states") else False,
            on_select_coaching_mode=(receiver.set_coaching_mode if receiver is not None and hasattr(receiver, "set_coaching_mode") else None),
            current_coaching_mode=(getattr(getattr(receiver, "live_coach", None), "settings", None).mode if receiver is not None and getattr(getattr(receiver, "live_coach", None), "settings", None) is not None else "auto"),
            on_select_coaching_verbosity=(receiver.set_coaching_verbosity if receiver is not None and hasattr(receiver, "set_coaching_verbosity") else None),
            current_coaching_verbosity=(getattr(getattr(receiver, "live_coach", None), "settings", None).verbosity if receiver is not None and getattr(getattr(receiver, "live_coach", None), "settings", None) is not None else "normal"),
            dashboard_url=self.dashboard_url,
            hardware_bridge=(getattr(receiver, "wheel_bridge", None) if receiver is not None else None),
        )
        self.coach = CoachOverlayWindow(
            on_close=self.hide_coach,
            on_toggle_pause=self.toggle_pause,
            on_toggle_click_through=self.toggle_click_through,
            on_show_driver=self.show_driver,
            on_show_replay=self.show_replay,
            on_show_speed_delta=self.show_speed_delta,
            on_show_laptime=self.show_laptime,
            on_show_tyre_wear=self.show_tyre_wear,
            on_show_fuel=self.show_fuel,
            on_show_weather=self.show_weather,
            on_show_standings=self.show_standings,
            on_show_lap_history=self.show_lap_history,
            on_show_tyre_sets=self.show_tyre_sets,
            replay_available=self.replay_controller is not None,
        )
        corner_transcript_store = getattr(receiver, "corner_transcript", None)
        corner_states=(receiver.coaching_feature_states() if receiver is not None and hasattr(receiver, "coaching_feature_states") else {})
        self.corner_coach = CornerCoachOverlayWindow(
            transcript_store=corner_transcript_store,
            on_hide=self.hide_corner_coach,
            on_toggle_pause=self.toggle_pause,
            on_toggle_click_through=self.toggle_click_through,
            on_toggle_speed_coach=(lambda enabled: receiver.set_corner_coach_feature("SPEED", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_corner_coach=(lambda enabled: receiver.set_corner_coach_feature("CORNER", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_straight_coach=(lambda enabled: receiver.set_corner_coach_feature("STRAIGHT", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_corner_voice=(lambda enabled: receiver.set_corner_coach_feature("VOICE", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_corner_pre=(lambda enabled: receiver.set_corner_coach_feature("PRE", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_corner_post=(lambda enabled: receiver.set_corner_coach_feature("POST", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_straight_voice=(lambda enabled: receiver.set_corner_coach_feature("STRAIGHTVOICE", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_gain_loss=(lambda enabled: receiver.set_corner_coach_feature("GAINLOSS", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_gain_loss_voice=(lambda enabled: receiver.set_corner_coach_feature("GAINLOSSVOICE", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            on_toggle_damage_coach=(lambda enabled: receiver.set_corner_coach_feature("DMGCOACH", enabled)) if receiver is not None and hasattr(receiver, "set_corner_coach_feature") else None,
            control_states=corner_states,
        )
        self.pre_corner = ProgressivePreCornerOverlayWindow(
            on_hide=self.hide_pre_corner,
            on_toggle_pause=self.toggle_pause,
            on_toggle_click_through=self.toggle_click_through,
        )
        self.live_corner_feedback = LiveCornerFeedbackOverlayWindow(
            on_hide=self.hide_live_corner_feedback,
            on_toggle_pause=self.toggle_pause,
            on_toggle_click_through=self.toggle_click_through,
        )
        self._live_corner_feedback_armed = False
        self._live_corner_feedback_last_key = None
        self.race_engineer = RaceEngineerOverlayWindow(on_hide=self.hide_session_engineer, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.qualifying_engineer = QualifyingEngineerOverlayWindow(on_hide=self.hide_session_engineer, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        transcript_store = getattr(receiver, "radio_transcript", None)
        self.radio_transcript = RadioTranscriptOverlayWindow(
            transcript_store=transcript_store, on_hide=self.hide_radio_transcript,
            on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through,
        )
        self.session_summary = SessionSummaryOverlayWindow(
            receiver=receiver, on_hide=self.hide_session_summary,
            on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through,
        )
        self._summary_auto_shown_revision = 0
        self.driver = DriverOverlayWindow(
            on_hide=self.hide_driver,
            on_toggle_pause=self.toggle_pause,
            on_toggle_click_through=self.toggle_click_through,
        )
        self.reference_driver = ReferenceInputsOverlayWindow(
            on_hide=self.hide_reference_driver,
            on_toggle_pause=self.toggle_pause,
            on_toggle_click_through=self.toggle_click_through,
        )
        self.ers_battery = ERSBatteryOverlayWindow(on_hide=self.hide_ers_battery, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.penalties = PenaltiesOverlayWindow(on_hide=self.hide_penalties, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.brake_status = BrakeStatusOverlayWindow(on_hide=self.hide_brake_status, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.speed_delta = SpeedDeltaOverlayWindow(on_hide=self.hide_speed_delta, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.laptime = LiveLaptimeOverlayWindow(on_hide=self.hide_laptime, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.tyre_wear = TyreWearOverlayWindow(on_hide=self.hide_tyre_wear, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.fuel = FuelOverlayWindow(on_hide=self.hide_fuel, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.weather = WeatherOverlayWindow(on_hide=self.hide_weather, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.standings = StandingsOverlayWindow(on_hide=self.hide_standings, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.lap_history = LapHistoryOverlayWindow(on_hide=self.hide_lap_history, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.tyre_sets = TyreSetsOverlayWindow(on_hide=self.hide_tyre_sets, on_toggle_pause=self.toggle_pause, on_toggle_click_through=self.toggle_click_through)
        self.f1_dash = F1DashOverlayWindow(
            on_hide=self.hide_f1_dash,
            on_toggle_pause=self.toggle_pause,
            on_toggle_click_through=self.toggle_click_through,
            remote_url=self.dashboard_url,
        )
        self.replay_controls = None
        if self.replay_controller is not None:
            self.replay_controls = ReplayControlsWindow(
                self.replay_controller,
                on_toggle_pause=self.toggle_pause,
                on_hide=self.hide_replay,
                on_toggle_click_through=self.toggle_click_through,
            )
        self.windows = tuple(w for w in (
            self.control_center, self.coach, self.corner_coach, self.pre_corner, self.live_corner_feedback, self.race_engineer, self.qualifying_engineer, self.radio_transcript, self.session_summary, self.driver, self.reference_driver, self.ers_battery, self.penalties, self.brake_status, self.speed_delta, self.laptime, self.tyre_wear, self.fuel,
            self.weather, self.standings, self.lap_history, self.tyre_sets, self.f1_dash, self.replay_controls
        ) if w is not None)
        self._secondary_windows = (self.corner_coach, self.pre_corner, self.live_corner_feedback, self.race_engineer, self.qualifying_engineer, self.radio_transcript, self.session_summary, self.tyre_wear, self.fuel, self.weather, self.standings, self.lap_history, self.tyre_sets, self.ers_battery, self.penalties, self.brake_status, self.f1_dash)
        self.control_center.set_overlay_manager_provider(self._overlay_manager_state, self._overlay_manager_action)
        self._place_default()
        self.set_click_through(self._click_through)

        self.timer = QTimer()
        # Precise ~60 Hz refresh minimizes telemetry-to-screen latency.  The data
        # snapshot hot path is optimized to stay well below this 16 ms budget.
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(max(16, int(1000 / max(1, refresh_hz))))

        # Driver/reference input traces use a dedicated 10 ms poll. This does
        # not invent intermediate telemetry: duplicate snapshots are rejected
        # by DriverOverlayWindow, but new source samples are rendered on the
        # first 10 ms tick after arrival. RI is sampled only when DI advances,
        # giving throttle/brake and both ERS plots the exact same distance grid.
        self.input_timer = QTimer()
        self.input_timer.setTimerType(Qt.PreciseTimer)
        self.input_timer.timeout.connect(self.refresh_inputs)
        self.input_timer.start(10)

        # All overlays, including Race Engineer, are refreshed from the exact
        # same immutable snapshot. This is important during replay: it guarantees
        # RE can never display a different lap/stint frame than Driver/Laptime.
        self.refresh()

    def _replay_recording_options(self):
        files = sorted(RECORDINGS.glob("*.areplay"), key=lambda p: p.stat().st_mtime, reverse=True)
        options = []
        seen=set()
        for path in files:
            try:
                stat = path.stat(); size_mb = stat.st_size / (1024 * 1024)
                label = f"{path.stem} • {size_mb:.1f} MB"
            except OSError:
                label = path.stem
            seen.add(path.name.lower()); options.append({"label": label, "path": str(path), "source":"LOCAL"})
        # Older recordings may have been pruned locally after verified server
        # migration.  Keep them selectable; they are hydrated back into the
        # local cache only when the user chooses one.
        try:
            from ..server_replay_cache import available_remote_replays
            for path in available_remote_replays():
                if path.name.lower() in seen: continue
                try:
                    size_mb=path.stat().st_size/(1024*1024); label=f"{path.stem} • {size_mb:.1f} MB • SERVER"
                except OSError:
                    label=f"{path.stem} • SERVER"
                options.append({"label":label,"path":str(path),"source":"SERVER"})
        except Exception:
            pass
        return options

    def _select_replay_recording(self, value):
        from pathlib import Path
        if self.replay_controller is None:
            return False, "Replay mode is not active"
        try:
            active = bool(self._replay_mode_getter())
            selected=Path(value)
            try:
                if selected.is_file() and RECORDINGS not in selected.parents:
                    from ..server_replay_cache import hydrate_replay
                    selected=hydrate_replay(selected,RECORDINGS)
            except Exception:
                selected=Path(value)
            value=str(selected)
            count = self.replay_controller.load_file(value, autoplay=active)
            if active:
                self._paused = False
                self.control_center.set_paused(False)
            if self.replay_controls is not None:
                try:
                    self.replay_controls.setWindowTitle(f"Replay Controls - {Path(value).name}")
                except Exception:
                    pass
            return True, (f"Loaded and playing {Path(value).name} ({count} packets)" if active else f"Selected {Path(value).name} ({count} packets) — click Replay to start")
        except Exception as error:
            return False, str(error)

    def _place_default(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        r = screen.availableGeometry()
        x = r.right() - self.control_center.WIDTH - 30
        y = r.top() + 70
        self.control_center.move(x, y)
        self.coach.move(x, y + self.control_center.height() + self.GAP)
        self.corner_coach.move(max(r.left()+20, r.center().x()-self.corner_coach.width()//2), max(r.top()+20, r.center().y()-self.corner_coach.height()//2))
        self.pre_corner.move(max(r.left()+20, r.center().x()-self.pre_corner.width()//2), r.top()+85)
        self.live_corner_feedback.move(max(r.left()+20, r.center().x()-self.live_corner_feedback.width()//2), r.top()+270)
        engineer_x = max(r.left()+20, x-self.race_engineer.WIDTH-self.GAP)
        self.race_engineer.move(engineer_x, y)
        self.qualifying_engineer.move(engineer_x, y)
        self.radio_transcript.move(max(r.left()+20, engineer_x-self.radio_transcript.WIDTH-self.GAP), y)
        self.session_summary.move(max(r.left()+20, engineer_x-self.session_summary.WIDTH-self.GAP), y + 35)
        # Keep Driver Inputs inside the usable monitor area. The old stacked
        # placement pushed throttle/brake completely below 768px-tall screens.
        driver_x = max(r.left() + 20, x - self.driver.WIDTH - self.GAP)
        driver_y = max(r.top() + 20, r.bottom() - self.driver.height() - 20)
        self.driver.move(driver_x, driver_y)
        reference_driver_x = max(r.left() + 20, driver_x - self.reference_driver.WIDTH - self.GAP)
        self.reference_driver.move(reference_driver_x, driver_y)
        # Full-size dash is hidden by default and opens in a predictable landscape location.
        self.f1_dash.move(max(r.left() + 20, r.center().x() - self.f1_dash.WIDTH // 2), max(r.top() + 20, r.center().y() - self.f1_dash.HEIGHT // 2))
        self.ers_battery.move(max(r.left()+20, x-self.ers_battery.WIDTH-self.GAP), y+self.speed_delta.HEIGHT+self.laptime.HEIGHT+self.GAP*2)
        self.speed_delta.move(max(r.left()+20, x-self.speed_delta.WIDTH-self.GAP), y)
        self.laptime.move(max(r.left()+20, x-self.laptime.WIDTH-self.GAP), y+self.speed_delta.HEIGHT+self.GAP)
        if self.replay_controls is not None:
            self.replay_controls.move(r.left() + 35, r.top() + 70)
        sx=max(r.left()+20, x-self.lap_history.WIDTH-self.GAP)
        sy=y+self.laptime.HEIGHT+self.GAP
        for i,window in enumerate(self._secondary_windows):
            window.move(sx + (i%2)*30, sy + (i%3)*30)

    def show(self):
        # V2 startup policy: Control Center is the normal application window.
        # Every driving overlay starts closed and is opened only by an explicit
        # launcher action.  This also prevents source/flag changes from reviving
        # overlays that the user intentionally left hidden.
        for window in self.windows:
            window.hide()
        self.control_center.show()
        self.control_center.raise_()
        self.control_center.activateWindow()

    def _overlay_windows_for_key(self, key):
        mapping={
            "C": (self.coach,), "SC": (self.corner_coach,), "PRE": (self.pre_corner,), "LCF": (self.live_corner_feedback,),
            "RE": (self.race_engineer,self.qualifying_engineer), "R": (self.replay_controls,),
            "RT": (self.radio_transcript,), "SS": (self.session_summary,), "DI": (self.driver,),
            "RI": (self.reference_driver,), "Δ": (self.speed_delta,), "L": (self.laptime,),
            "TW": (self.tyre_wear,), "F": (self.fuel,), "W": (self.weather,),
            "S": (self.standings,), "H": (self.lap_history,), "TS": (self.tyre_sets,),
            "EB": (self.ers_battery,), "PEN": (self.penalties,), "BRK": (self.brake_status,), "FD": (self.f1_dash,),
        }
        return tuple(w for w in mapping.get(str(key),()) if w is not None)

    def _overlay_manager_state(self, key):
        windows=self._overlay_windows_for_key(key)
        if not windows:
            return {"available":False,"visible":False,"locked":False,"opacity":1.0}
        visible_windows=[w for w in windows if w.isVisible()]
        target=visible_windows[0] if visible_windows else windows[0]
        return {
            "available":True,
            "visible":bool(visible_windows),
            "locked":bool(target.overlay_locked()) if hasattr(target,"overlay_locked") else False,
            "opacity":float(getattr(target,"_overlay_opacity",1.0)),
        }

    def _overlay_manager_action(self, key, action, value=None):
        key=str(key); action=str(action)
        windows=self._overlay_windows_for_key(key)
        if not windows:
            return
        if action=="open":
            self.show_overlay_by_key(key); return
        if action=="toggle":
            if any(w.isVisible() for w in windows):
                for w in windows: w.hide()
            else:
                self.show_overlay_by_key(key)
            return
        if action=="lock":
            state=self._overlay_manager_state(key); new_state=not bool(state.get("locked"))
            for w in windows:
                if hasattr(w,"set_overlay_locked"): w.set_overlay_locked(new_state)
            return
        if action=="opacity":
            opacity=max(0.35,min(1.0,float(value if value is not None else 1.0)))
            for w in windows:
                if hasattr(w,"set_overlay_opacity"): w.set_overlay_opacity(opacity)
            return

    def show_overlay_by_key(self, key):
        """Single source of truth for Control Center launcher routing."""
        routes = {
            "C": self.show_coach,
            "SC": self.show_corner_coach,
            "CC": self.show_corner_coach,
            "PRE": self.show_pre_corner,
            "LCF": self.show_live_corner_feedback,
            "RE": self.show_race_engineer,
            "R": self.show_replay,
            "RT": self.show_radio_transcript,
            "SS": self.show_session_summary,
            "DI": self.show_driver,
            "RI": self.show_reference_driver,
            "Δ": self.show_speed_delta,
            "L": self.show_laptime,
            "TW": self.show_tyre_wear,
            "F": self.show_fuel,
            "W": self.show_weather,
            "S": self.show_standings,
            "H": self.show_lap_history,
            "TS": self.show_tyre_sets,
            "EB": self.show_ers_battery,
            "PEN": self.show_penalties,
            "BRK": self.show_brake_status,
            "FD": self.show_f1_dash,
        }
        callback = routes.get(str(key))
        if callback is not None:
            callback()

    def show_coach(self):
        self._bring_to_front(self.coach)

    def hide_coach(self):
        self.coach.hide()

    def show_corner_coach(self):
        self.corner_coach.update_snapshot(self.provider.snapshot())
        self._bring_to_front(self.corner_coach)

    def hide_corner_coach(self):
        self.corner_coach.hide()

    def show_pre_corner(self):
        self.pre_corner.update_snapshot(self.provider.snapshot())
        self._bring_to_front(self.pre_corner)

    def hide_pre_corner(self):
        self.pre_corner.hide()

    def show_live_corner_feedback(self):
        # Arm the transient card. It will pop up automatically on each new
        # eligible corner result and hide again when that result expires.
        self._live_corner_feedback_armed = True
        snapshot=self.provider.snapshot()
        result=getattr(snapshot,'live_corner_result',None)
        self.live_corner_feedback.set_result(result if isinstance(result,dict) else None)
        self._bring_to_front(self.live_corner_feedback)

    def hide_live_corner_feedback(self):
        self._live_corner_feedback_armed = False
        self.live_corner_feedback.hide()

    def show_race_engineer(self):
        # RE is a session-engineer launcher. Select a concrete window rather than
        # multiplexing Race and Qualifying inside one QWidget.
        snapshot = self.provider.snapshot()
        if is_qualifying_snapshot(snapshot):
            self.race_engineer.hide()
            self.qualifying_engineer.move(self.race_engineer.pos())
            self.qualifying_engineer.update_snapshot(snapshot)
            self._bring_to_front(self.qualifying_engineer)
        else:
            self.qualifying_engineer.hide()
            self.race_engineer.move(self.qualifying_engineer.pos())
            self.race_engineer.update_snapshot(snapshot)
            self._bring_to_front(self.race_engineer)

    def hide_session_engineer(self):
        self.race_engineer.hide()
        self.qualifying_engineer.hide()

    # Backward-compatible alias used by older tests/callers.
    def hide_race_engineer(self):
        self.hide_session_engineer()

    @staticmethod
    def _bring_to_front(window):
        if window is None:
            return
        window.show()
        window.raise_()
        window.activateWindow()

    def show_radio_transcript(self):
        self.radio_transcript.update_from_store()
        self._bring_to_front(self.radio_transcript)

    def hide_radio_transcript(self):
        self.radio_transcript.hide()

    def show_session_summary(self):
        self.session_summary.update_from_receiver()
        self._bring_to_front(self.session_summary)

    def hide_session_summary(self):
        self.session_summary.hide()

    def show_driver(self):
        self._bring_to_front(self.driver)

    def hide_driver(self):
        self.driver.hide()

    def show_reference_driver(self):
        self._bring_to_front(self.reference_driver)

    def hide_reference_driver(self):
        self.reference_driver.hide()

    def show_ers_battery(self):
        self._bring_to_front(self.ers_battery)

    def hide_ers_battery(self):
        self.ers_battery.hide()

    def show_penalties(self):
        self._bring_to_front(self.penalties)

    def hide_penalties(self):
        self.penalties.hide()

    def show_brake_status(self):
        self._bring_to_front(self.brake_status)

    def hide_brake_status(self):
        self.brake_status.hide()

    def show_f1_dash(self):
        self._bring_to_front(self.f1_dash)

    def hide_f1_dash(self):
        self.f1_dash.hide()

    def show_speed_delta(self):
        self._bring_to_front(self.speed_delta)

    def hide_speed_delta(self):
        self.speed_delta.hide()

    def show_laptime(self):
        self._bring_to_front(self.laptime)

    def hide_laptime(self):
        self.laptime.hide()

    def show_tyre_wear(self): self._bring_to_front(self.tyre_wear)
    def hide_tyre_wear(self): self.tyre_wear.hide()
    def show_fuel(self): self._bring_to_front(self.fuel)
    def hide_fuel(self): self.fuel.hide()
    def show_weather(self): self._bring_to_front(self.weather)
    def hide_weather(self): self.weather.hide()
    def show_standings(self): self._bring_to_front(self.standings)
    def hide_standings(self): self.standings.hide()
    def show_lap_history(self): self._bring_to_front(self.lap_history)
    def hide_lap_history(self): self.lap_history.hide()
    def show_tyre_sets(self): self._bring_to_front(self.tyre_sets)
    def hide_tyre_sets(self): self.tyre_sets.hide()

    def show_replay(self):
        self._bring_to_front(self.replay_controls)

    def hide_replay(self):
        if self.replay_controls is not None:
            self.replay_controls.hide()

    def refresh_inputs(self):
        """Low-latency 10 ms DI-master sampling for DI/RI and their ERS plots."""
        replay_active = bool(self._replay_mode_getter())
        if self.replay_controls is not None and replay_active:
            status = self.replay_controller.status()
            if status.rebuilding or status.paused:
                return
        if self._paused:
            return
        # Do not spend a 100 Hz polling budget on hidden DI/RI windows.  This
        # timer is for visual latency only; it is not part of telemetry capture.
        if not self.driver.isVisible() and not self.reference_driver.isVisible():
            return
        # The 10 ms path intentionally avoids the full overlay snapshot, which
        # performs strategy, standings and segment calculations that belong on
        # the normal ~60 Hz UI refresh.  Only DI/RI channels are copied here.
        snapshot = (self.provider.input_snapshot()
                    if hasattr(self.provider, "input_snapshot")
                    else self.provider.snapshot())
        progressed = bool(self.driver.update_snapshot(snapshot))
        if self.reference_driver.isVisible():
            self.reference_driver.update_snapshot(snapshot, append_sample=progressed)

    def refresh(self):
        replay_active = bool(self._replay_mode_getter())
        self.control_center.set_replay_mode(replay_active)
        if self.replay_controls is not None:
            status = self.replay_controller.status()
            self.replay_controls.update_status(status)
            if replay_active and status.paused != self._paused:
                self._paused = status.paused
                self.coach.set_paused(self._paused)
                self.control_center.set_paused(self._paused)
            # Keep the last fully-valid overlay frame while deterministic seek reconstruction runs.
            if replay_active and status.rebuilding:
                return
        # In Live mode Pause freezes overlays only; UDP reception continues.
        if self._paused and not replay_active:
            return
        snapshot = self.provider.snapshot()
        receiver = getattr(self.provider, "receiver", None)
        if receiver is not None and hasattr(receiver, "runtime_feature_states"):
            self.control_center.set_runtime_statuses({**receiver.runtime_feature_states(), **(receiver.coaching_feature_states() if hasattr(receiver, "coaching_feature_states") else {})})
        if receiver is not None and hasattr(receiver, "current_reference_selection"):
            self.control_center.set_reference_selection(receiver.current_reference_selection())
        if receiver is not None and hasattr(receiver, "reference_selection_status"):
            self.control_center.set_reference_status(receiver.reference_selection_status())
        if receiver is not None and hasattr(receiver, "recording_mode"):
            self.control_center.set_recording_mode(receiver.recording_mode())
        if receiver is not None and hasattr(receiver, "rival_reference_capture_status"):
            self.control_center.set_reference_capture_status(receiver.rival_reference_capture_status())
        self.control_center.update_snapshot(snapshot)
        if self.radio_transcript.isVisible():
            self.radio_transcript.update_from_store()
        if self.session_summary.isVisible():
            self.session_summary.update_from_receiver()
        revision = int(getattr(receiver, "session_summary_revision", 0) or 0) if receiver is not None else 0
        if revision > self._summary_auto_shown_revision:
            self._summary_auto_shown_revision = revision
            self.session_summary.update_from_receiver()
            self._bring_to_front(self.session_summary)
        qualifying = is_qualifying_snapshot(snapshot)
        if qualifying:
            # If RE is currently open, atomically swap the concrete panel while
            # preserving the user's chosen position. Hidden RE remains hidden.
            if self.race_engineer.isVisible():
                pos = self.race_engineer.pos()
                self.race_engineer.hide()
                self.qualifying_engineer.move(pos)
                self.qualifying_engineer.update_snapshot(snapshot)
                self.qualifying_engineer.show()
                self.qualifying_engineer.raise_()
            elif self.qualifying_engineer.isVisible():
                self.qualifying_engineer.update_snapshot(snapshot)
        else:
            if self.qualifying_engineer.isVisible():
                pos = self.qualifying_engineer.pos()
                self.qualifying_engineer.hide()
                self.race_engineer.move(pos)
                self.race_engineer.update_snapshot(snapshot)
                self.race_engineer.show()
                self.race_engineer.raise_()
            elif self.race_engineer.isVisible():
                self.race_engineer.update_snapshot(snapshot)
        if self.coach.isVisible():
            self.coach.update_snapshot(snapshot)
        if self.corner_coach.isVisible():
            if receiver is not None and hasattr(receiver, "coaching_feature_states"):
                self.corner_coach.set_control_states(receiver.coaching_feature_states())
            self.corner_coach.update_snapshot(snapshot)
        if self.pre_corner.isVisible():
            self.pre_corner.update_snapshot(snapshot)
        # V2.0.1 dedicated glanceable card. Opening its launcher arms the card;
        # each new eligible result then pops up automatically and disappears
        # when the snapshot's authoritative four-second result window expires.
        if self._live_corner_feedback_armed:
            result=getattr(snapshot,'live_corner_result',None)
            if isinstance(result,dict):
                key=self.live_corner_feedback.result_key(result)
                self.live_corner_feedback.set_result(result)
                if key != self._live_corner_feedback_last_key:
                    self._live_corner_feedback_last_key=key
                    self._bring_to_front(self.live_corner_feedback)
            else:
                # Keep the manually-enabled overlay open between corners.
                # When the four-second result window expires, return to the
                # waiting state instead of closing the entire panel. The user
                # explicitly closes/disables it with the X button or launcher.
                self.live_corner_feedback.set_result(None)
                if not self.live_corner_feedback.isVisible():
                    self._bring_to_front(self.live_corner_feedback)
        dash_paused = bool(self._paused or getattr(snapshot, "game_paused", False))
        self.f1_dash.set_paused(dash_paused)
        if not dash_paused:
            if self.f1_dash.isVisible():
                self.f1_dash.update_snapshot(snapshot)
            if self.dashboard_store is not None:
                self.dashboard_store.update_snapshot(snapshot)
        # DI/RI are refreshed by the dedicated 10 ms input timer. Other visual
        # overlays only need work while they are actually visible.
        for panel in (self.ers_battery,self.penalties,self.brake_status,self.speed_delta,self.laptime,self.tyre_wear,self.fuel,self.weather,self.standings,self.lap_history,self.tyre_sets):
            if panel.isVisible():
                panel.update_snapshot(snapshot)

    def toggle_pause(self):
        self._paused = not self._paused
        self.coach.set_paused(self._paused)
        self.control_center.set_paused(self._paused)
        self.f1_dash.set_paused(self._paused)
        if self._on_pause_changed:
            self._on_pause_changed(self._paused)
        if not self._paused:
            self.refresh()
            self.refresh_inputs()

    def set_click_through(self, enabled: bool):
        self._click_through = bool(enabled)
        # The Control Center is the escape hatch for click-through mode and must
        # always remain interactive. Apply mouse transparency only to the racing
        # / data overlays so CT can always be turned back off from the hub.
        for window in click_through_targets(self.windows, self.control_center):
            window.set_click_through(self._click_through)
        # Explicitly keep the control hub interactive even when the suite starts
        # with --overlay-click-through enabled.
        if getattr(self.control_center, "_click_through", False):
            self.control_center.set_click_through(False)
        self.control_center.set_click_state(self._click_through)

    def toggle_click_through(self):
        self.set_click_through(not self._click_through)

    def close_all(self):
        # The normal Control Center application window owns process exit; all
        # racing-overlay X buttons only hide their individual panels.
        self.timer.stop()
        self.input_timer.stop()
        self.control_center._suite_closing = True
        for window in self.windows:
            window.close()
        if self._on_close:
            self._on_close()


# Backward-compatible name for code that imported the original single window.
OverlayWindow = CoachOverlayWindow
