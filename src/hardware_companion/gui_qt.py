from __future__ import annotations

import math
import sys

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QIntValidator, QLinearGradient, QBrush
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QProgressBar, QScrollArea, QSlider, QTabWidget, QVBoxLayout,
    QWidget, QSizePolicy, QCheckBox
)

from .pedal_curves import AxisCurve, INPUT_POINTS, PedalCurveSettings, RAW_MAX
from .pedal_auto_calibration import PedalCalibrationCapture
from .protocol import serial_ports
from .settings import load_settings, save_settings
from .models import LiveTelemetry


try:
    import pygame  # type: ignore
except Exception:  # pragma: no cover - optional dependency at runtime
    pygame = None


BG = "#080d12"
SURFACE = "#101820"
SURFACE_ELEVATED = "#151f29"
SURFACE_SOFT = "#0b1219"
BORDER = "#273746"
BORDER_STRONG = "#3b5265"
TEXT = "#eef6fb"
MUTED = "#8395a8"
ACCENT = "#4dd9ff"
GREEN = "#2ed486"
AMBER = "#f5bd4d"
RED = "#ff5967"


APP_QSS = f"""
QWidget {{ color:{TEXT}; font-family:'Segoe UI'; font-size:10pt; }}
QMainWindow, QWidget#appRoot {{ background:{BG}; }}
QLabel {{ background:transparent; }}
QFrame#card {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px; }}
QFrame#subCard {{ background:{SURFACE_SOFT}; border:1px solid {BORDER}; border-radius:8px; }}
QFrame#statusCard {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:9px; }}
QFrame#statusCard:hover {{ border-color:{BORDER_STRONG}; background:#111b24; }}
QLabel#eyebrow {{ color:{ACCENT}; font-size:8pt; font-weight:800; letter-spacing:1px; }}
QLabel#title {{ color:{TEXT}; font-size:21pt; font-weight:800; }}
QLabel#subtitle {{ color:{MUTED}; font-size:10pt; }}
QLabel#sectionTitle {{ color:{TEXT}; font-size:15pt; font-weight:800; }}
QLabel#cardTitle {{ color:{TEXT}; font-size:12pt; font-weight:800; }}
QLabel#muted {{ color:{MUTED}; }}
QLabel#value {{ color:{TEXT}; font-size:12pt; font-weight:800; }}
QLabel#statusGood {{ color:{GREEN}; font-weight:800; }}
QLabel#statusWarn {{ color:{AMBER}; font-weight:800; }}
QLabel#statusBad {{ color:{RED}; font-weight:800; }}
QPushButton {{ color:{TEXT}; background:{SURFACE_ELEVATED}; border:1px solid {BORDER}; border-radius:7px; padding:7px 12px; font-weight:700; }}
QPushButton:hover {{ background:#1c2a35; border-color:{BORDER_STRONG}; }}
QPushButton:pressed {{ background:#0d151d; }}
QPushButton#primary {{ background:#16384a; border-color:{ACCENT}; }}
QPushButton#primary:hover {{ background:#1a455b; }}
QPushButton:focus, QComboBox:focus, QLineEdit:focus {{ border:2px solid {ACCENT}; }}
QComboBox, QLineEdit {{ color:{TEXT}; background:{SURFACE_SOFT}; border:1px solid {BORDER}; border-radius:6px; padding:6px 8px; min-height:22px; }}
QComboBox:hover, QLineEdit:hover {{ border-color:{BORDER_STRONG}; }}
QComboBox QAbstractItemView {{ color:{TEXT}; background:{SURFACE}; border:1px solid {BORDER}; selection-background-color:#20394a; }}
QTabWidget::pane {{ border:1px solid {BORDER}; background:{BG}; top:-1px; }}
QTabBar::tab {{ background:{SURFACE_SOFT}; color:{MUTED}; border:1px solid {BORDER}; padding:10px 18px; min-width:105px; }}
QTabBar::tab:selected {{ background:{SURFACE_ELEVATED}; color:{TEXT}; border-bottom:2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color:{TEXT}; background:#182631; }}
QSlider::groove:horizontal {{ height:5px; background:#263542; border-radius:2px; }}
QSlider::handle:horizontal {{ width:14px; margin:-5px 0; background:{ACCENT}; border:1px solid #a5efff; border-radius:7px; }}
QSlider::sub-page:horizontal {{ background:#31586b; border-radius:2px; }}
QProgressBar {{ background:{SURFACE_SOFT}; border:1px solid {BORDER}; border-radius:5px; height:10px; text-align:center; color:transparent; }}
QProgressBar::chunk {{ background:{ACCENT}; border-radius:4px; }}
"""


def label(text: str = "", object_name: str | None = None) -> QLabel:
    w = QLabel(text)
    if object_name:
        w.setObjectName(object_name)
    return w


def card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    return f


def sub_card() -> QFrame:
    f = QFrame()
    f.setObjectName("subCard")
    return f


class CurveGraph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.curve = AxisCurve()
        self.x_axis_label = "INPUT %"
        self.x_axis_max: float | None = None
        self.setMinimumSize(170, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_curve(self, curve: AxisCurve) -> None:
        self.curve = curve.sanitized()
        self.update()

    def set_force_axis(self, max_force_kg: float | None) -> None:
        if max_force_kg is None:
            self.x_axis_label = "INPUT %"
            self.x_axis_max = None
        else:
            self.x_axis_label = "INPUT FORCE (kg)"
            self.x_axis_max = max(0.1, float(max_force_kg))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(SURFACE_SOFT))
        r = QRectF(46, 22, max(10, self.width()-68), max(10, self.height()-60))
        p.setFont(QFont("Segoe UI", 8))
        for v in range(0, 101, 20):
            x = r.left() + r.width() * v/100.0
            y = r.bottom() - r.height() * v/100.0
            p.setPen(QPen(QColor(BORDER), 1))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(QColor(MUTED))
            if self.x_axis_max is None:
                x_text = str(v)
            else:
                force = self.x_axis_max * v / 100.0
                x_text = f"{force:.0f}" if force >= 10 else f"{force:.1f}"
            p.drawText(QRectF(x-22, r.bottom()+8, 44, 18), Qt.AlignCenter, x_text)
            p.drawText(QRectF(4, y-9, 34, 18), Qt.AlignRight|Qt.AlignVCenter, str(v))
        p.setPen(QPen(QColor(TEXT), 1.5))
        p.drawLine(QPointF(r.left(), r.top()), QPointF(r.left(), r.bottom()))
        p.drawLine(QPointF(r.left(), r.bottom()), QPointF(r.right(), r.bottom()))
        pts=[]
        for x_pct, y_pct in zip(INPUT_POINTS, self.curve.outputs):
            x=r.left()+r.width()*x_pct/100.0
            y=r.bottom()-r.height()*y_pct/100.0
            pts.append(QPointF(x,y))
        p.setPen(QPen(QColor(ACCENT), 3))
        for a,b in zip(pts, pts[1:]):
            p.drawLine(a,b)
        p.setBrush(QColor(ACCENT)); p.setPen(Qt.NoPen)
        for pt in pts:
            p.drawEllipse(pt, 5, 5)
        p.setPen(QColor(MUTED)); p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(r.left(), self.height()-22, r.width(), 18), Qt.AlignCenter, self.x_axis_label)


class PedalCurveEditor(QFrame):
    def __init__(self, title: str, on_change, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.title = title
        self.on_change = on_change
        self._updating = False
        self.raw_value: int | None = None
        self.force_mode = False
        self.max_force_kg = 40.0

        root=QVBoxLayout(self); root.setContentsMargins(16,16,16,16); root.setSpacing(12)
        h=QHBoxLayout(); h.setSpacing(8)
        self.title_label = label(title.upper(), "cardTitle")
        h.addWidget(self.title_label)
        self.mode_badge = label("RECEIVER-SIDE SHAPING", "eyebrow")
        h.addWidget(self.mode_badge)
        h.addStretch(1)
        root.addLayout(h)

        top=sub_card(); top_l=QGridLayout(top); top_l.setContentsMargins(12,12,12,12); top_l.setHorizontalSpacing(10); top_l.setVerticalSpacing(8)
        top_l.addWidget(label("CURVE TYPE", "eyebrow"),0,0)
        self.curve_combo=QComboBox(); self.curve_combo.addItems(["Linear","Custom"]); self.curve_combo.setMinimumWidth(130)
        top_l.addWidget(self.curve_combo,1,0)
        self.bottom_label = label("BOTTOM DEADZONE", "eyebrow")
        top_l.addWidget(self.bottom_label,0,1)
        self.bottom=QLineEdit("0"); self.bottom.setValidator(QIntValidator(0,30,self)); self.bottom.setFixedWidth(72)
        top_l.addWidget(self.bottom,1,1)
        self.top_label = label("TOP DEADZONE", "eyebrow")
        top_l.addWidget(self.top_label,0,2)
        self.top=QLineEdit("0"); self.top.setValidator(QIntValidator(0,30,self)); self.top.setFixedWidth(72)
        top_l.addWidget(self.top,1,2)
        top_l.setColumnStretch(3,1)
        root.addWidget(top)

        self._body_layout_mode = None
        self.body = QBoxLayout(QBoxLayout.LeftToRight)
        self.body.setSpacing(12)
        left=sub_card(); self.left_panel = left; ll=QVBoxLayout(left); ll.setContentsMargins(12,12,12,12); ll.setSpacing(6)
        rowhead=QHBoxLayout(); rowhead.addWidget(label("INPUT", "eyebrow")); rowhead.addStretch(1); rowhead.addWidget(label("OUTPUT", "eyebrow"))
        ll.addLayout(rowhead)
        self.point_edits=[]; self.point_sliders=[]; self.point_input_labels=[]
        for i, in_pct in enumerate(INPUT_POINTS):
            row=QHBoxLayout(); row.setSpacing(8)
            inlab=label(f"{in_pct}%"); inlab.setFixedWidth(58)
            self.point_input_labels.append(inlab)
            slider=QSlider(Qt.Horizontal); slider.setRange(0,100); slider.setValue(in_pct); slider.setMinimumWidth(90)
            edit=QLineEdit(str(in_pct)); edit.setValidator(QIntValidator(0,100,self)); edit.setFixedWidth(54); edit.setAlignment(Qt.AlignCenter)
            row.addWidget(inlab); row.addWidget(slider,1); row.addWidget(edit)
            ll.addLayout(row)
            self.point_sliders.append(slider); self.point_edits.append(edit)
            slider.valueChanged.connect(lambda value, idx=i: self._slider_changed(idx,value))
            edit.editingFinished.connect(lambda idx=i: self._edit_changed(idx))
        self.body.addWidget(left,0)

        graphbox=sub_card(); self.graph_panel = graphbox; gl=QVBoxLayout(graphbox); gl.setContentsMargins(12,12,12,12); gl.setSpacing(8)
        gh=QHBoxLayout(); gh.addWidget(label("CURVE PREVIEW", "eyebrow")); gh.addStretch(1)
        self.curve_summary=label("0% bottom  ·  0% top", "muted"); gh.addWidget(self.curve_summary)
        gl.addLayout(gh)
        self.graph=CurveGraph(); gl.addWidget(self.graph,1)
        self.body.addWidget(graphbox,1)
        root.addLayout(self.body,1)

        live=sub_card(); liv=QVBoxLayout(live); liv.setContentsMargins(12,10,12,10); liv.setSpacing(6)
        lr=QHBoxLayout(); self.input_label=label("INPUT --", "muted"); self.output_label=label("ADJUSTED OUTPUT --", "value")
        lr.addWidget(self.input_label); lr.addStretch(1); lr.addWidget(self.output_label); liv.addLayout(lr)
        self.bar=QProgressBar(); self.bar.setRange(0,1000); self.bar.setValue(0); liv.addWidget(self.bar)
        root.addWidget(live)

        self.curve_combo.currentTextChanged.connect(self._curve_type_changed)
        self.bottom.editingFinished.connect(self._deadzone_changed)
        self.top.editingFinished.connect(self._deadzone_changed)
        self._refresh_graph()
        self._update_body_layout(force=True)

    def _update_body_layout(self, force: bool = False) -> None:
        width = self.width()
        mode = "vertical" if width < 760 else "horizontal"
        if not force and mode == self._body_layout_mode:
            return
        self._body_layout_mode = mode
        if mode == "vertical":
            self.body.setDirection(QBoxLayout.TopToBottom)
            self.body.setStretch(0, 0)
            self.body.setStretch(1, 1)
            self.graph.setMinimumHeight(210)
            self.graph_panel.setMinimumWidth(0)
        else:
            self.body.setDirection(QBoxLayout.LeftToRight)
            self.body.setStretch(0, 0)
            self.body.setStretch(1, 1)
            self.graph.setMinimumHeight(180)
            self.graph_panel.setMinimumWidth(260)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_body_layout()

    @staticmethod
    def _int(edit: QLineEdit, default: int) -> int:
        try: return int(edit.text())
        except ValueError: return default

    def _slider_changed(self, idx:int, value:int):
        if self._updating: return
        self.point_edits[idx].setText(str(value))
        self.curve_combo.setCurrentText("Custom")
        self._normalize_and_emit()

    def _edit_changed(self, idx:int):
        if self._updating: return
        value=max(0,min(100,self._int(self.point_edits[idx], INPUT_POINTS[idx])))
        self._updating=True
        self.point_edits[idx].setText(str(value)); self.point_sliders[idx].setValue(value)
        self.curve_combo.setCurrentText("Custom")
        self._updating=False
        self._normalize_and_emit()

    def _deadzone_changed(self):
        if self._updating: return
        b=max(0,min(30,self._int(self.bottom,0))); t=max(0,min(30,self._int(self.top,0)))
        self.bottom.setText(str(b)); self.top.setText(str(t))
        self._normalize_and_emit()

    def _curve_type_changed(self, mode:str):
        if self._updating: return
        if mode == "Linear":
            self._updating=True
            for i,v in enumerate(INPUT_POINTS):
                self.point_sliders[i].setValue(v); self.point_edits[i].setText(str(v))
            self._updating=False
        self._normalize_and_emit()

    def _normalize_and_emit(self):
        curve=self.get_curve().sanitized()
        self.set_curve(curve, notify=False)
        if self.on_change: self.on_change()

    def get_curve(self)->AxisCurve:
        vals=tuple(max(0,min(100,self._int(e, INPUT_POINTS[i]))) for i,e in enumerate(self.point_edits))
        return AxisCurve(self._int(self.bottom,0), self._int(self.top,0), vals).sanitized()

    def set_curve(self, curve:AxisCurve, notify:bool=False):
        c=curve.sanitized(); self._updating=True
        self.bottom.setText(str(c.bottom_deadzone)); self.top.setText(str(c.top_deadzone))
        for i,v in enumerate(c.outputs):
            self.point_sliders[i].setValue(v); self.point_edits[i].setText(str(v))
        is_linear=(c.outputs==INPUT_POINTS and c.bottom_deadzone==0 and c.top_deadzone==0)
        self.curve_combo.setCurrentText("Linear" if is_linear else "Custom")
        self._updating=False; self._refresh_graph()
        if notify and self.on_change: self.on_change()

    def set_input_mode(self, force_mode: bool, max_force_kg: float = 40.0) -> None:
        self.force_mode = bool(force_mode)
        self.max_force_kg = max(0.1, float(max_force_kg))
        if self.force_mode:
            self.title_label.setText(f"{self.title.upper()} · LOAD CELL")
            self.mode_badge.setText("FORCE-BASED INPUT")
            self.bottom_label.setText("FORCE DEADZONE")
            self.top_label.setText("TOP DEADZONE")
            self.graph.set_force_axis(self.max_force_kg)
            for lab, pct in zip(self.point_input_labels, INPUT_POINTS):
                force = self.max_force_kg * pct / 100.0
                lab.setText(f"{force:.1f}kg")
            self.curve_summary.setToolTip("Input points are shown as force based on the configured maximum handbrake force.")
        else:
            self.title_label.setText(self.title.upper())
            self.mode_badge.setText("POSITION-BASED INPUT")
            self.bottom_label.setText("BOTTOM DEADZONE")
            self.top_label.setText("TOP DEADZONE")
            self.graph.set_force_axis(None)
            for lab, pct in zip(self.point_input_labels, INPUT_POINTS):
                lab.setText(f"{pct}%")
            self.curve_summary.setToolTip("")
        self._refresh_graph()
        self._update_body_layout(force=True)

    def _refresh_graph(self):
        c=self.get_curve(); self.graph.set_curve(c)
        if self.force_mode:
            self.curve_summary.setText(f"{c.bottom_deadzone}% force DZ  ·  {c.top_deadzone}% top")
        else:
            self.curve_summary.setText(f"{c.bottom_deadzone}% bottom  ·  {c.top_deadzone}% top")
        if self.raw_value is not None: self.set_live(self.raw_value)

    def set_live(self, raw:int|None):
        self.raw_value=raw
        if raw is None:
            self.input_label.setText("INPUT --"); self.output_label.setText("ADJUSTED OUTPUT --"); self.bar.setValue(0); return
        raw=max(0,min(RAW_MAX,int(raw))); ip=raw*100.0/RAW_MAX; op=self.get_curve().output_percent(raw)
        if self.force_mode:
            force = self.max_force_kg * ip / 100.0
            self.input_label.setText(f"FORCE {force:5.1f} kg   ·   INPUT {ip:5.1f}%   ·   RAW {raw}")
        else:
            self.input_label.setText(f"INPUT {ip:5.1f}%   RAW {raw}")
        self.output_label.setText(f"ADJUSTED OUTPUT {op:5.1f}%")
        self.bar.setValue(int(round(op*10)))


class AxisGradientBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self.setMinimumHeight(18)

    def set_value(self, value: float) -> None:
        self._value = max(-1.0, min(1.0, float(value)))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(QColor(SURFACE_SOFT))
        p.drawRoundedRect(rect, 6, 6)

        inner = rect.adjusted(2, 2, -2, -2)
        if inner.width() <= 0 or inner.height() <= 0:
            return
        grad = QLinearGradient(inner.left(), 0, inner.right(), 0)
        grad.setColorAt(0.0, QColor(RED))
        grad.setColorAt(1.0, QColor(ACCENT))
        fill_w = max(0, min(inner.width(), int(round((self._value + 1.0) * 0.5 * inner.width()))))
        if fill_w > 0:
            fill_rect = QRectF(inner.left(), inner.top(), fill_w, inner.height())
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, 5, 5)

        zero_x = inner.left() + inner.width() * 0.5
        val_x = inner.left() + inner.width() * ((self._value + 1.0) * 0.5)
        p.setPen(QPen(QColor(MUTED), 1))
        p.drawLine(QPointF(zero_x, inner.top()), QPointF(zero_x, inner.bottom()))
        p.setPen(QPen(QColor(TEXT), 2))
        p.drawLine(QPointF(val_x, inner.top()), QPointF(val_x, inner.bottom()))


class ButtonIndicator(QFrame):
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.setObjectName("subCard")
        self.index = index
        self.setMinimumWidth(78)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        self.title = label(f"B{index}", "muted")
        self.value = label("0.00", "value")
        self.value.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        self.set_pressed(False)

    def set_pressed(self, pressed: bool) -> None:
        if pressed:
            self.setStyleSheet(f"QFrame#subCard {{ background:#12301f; border:1px solid {GREEN}; border-radius:8px; }}")
            self.value.setText("1.00")
        else:
            self.setStyleSheet("")
            self.value.setText("0.00")


class AxisIndicator(QFrame):
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.setObjectName("subCard")
        self.index = index
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.addWidget(label(f"AXIS {index}", "eyebrow"))
        row.addStretch(1)
        self.value = label("0.00000", "value")
        row.addWidget(self.value)
        layout.addLayout(row)
        self.bar = AxisGradientBar()
        layout.addWidget(self.bar)
        hint = label("-1.0                0                +1.0", "muted")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

    def set_value(self, value: float) -> None:
        v = max(-1.0, min(1.0, float(value)))
        self.value.setText(f"{v:.5f}")
        self.bar.set_value(v)


class InputTesterTab(QWidget):
    POLL_MS = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pygame_ready = False
        self._joystick = None
        self._last_device_count = -1
        self.button_widgets = []
        self.axis_widgets = []
        self._build_ui()
        self._init_backend()
        self.timer = QTimer(self)
        self.timer.setInterval(self.POLL_MS)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"QScrollArea {{ background:{BG}; border:0; }} QScrollArea > QWidget > QWidget {{ background:{BG}; }}")
        content = QWidget()
        content.setObjectName("appRoot")
        self.scroll.setWidget(content)
        root.addWidget(self.scroll)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(label("GAMEPAD TESTER", "eyebrow"))
        head.addWidget(label("LIVE BUTTON / AXIS INPUT TESTER", "sectionTitle"))
        desc = label("Reads the Windows game controller seen by the PC. Pressed buttons light up green. Axes are shown with red-to-blue gradient bars.", "subtitle")
        desc.setWordWrap(True)
        head.addWidget(desc)
        lay.addLayout(head)

        top = card()
        tl = QGridLayout(top)
        tl.setContentsMargins(14, 12, 14, 12)
        tl.setHorizontalSpacing(12)
        tl.setVerticalSpacing(8)
        tl.addWidget(label("DEVICE", "eyebrow"), 0, 0)
        self.status = label("WAITING FOR GAMEPAD", "statusWarn")
        tl.addWidget(self.status, 1, 0)
        tl.addWidget(label("SELECTED", "eyebrow"), 0, 1)
        self.device_name = label("--", "value")
        tl.addWidget(self.device_name, 1, 1)
        tl.addWidget(label("DETAILS", "eyebrow"), 0, 2)
        self.details = label("--", "muted")
        self.details.setWordWrap(True)
        tl.addWidget(self.details, 1, 2)
        self.rescan_btn = QPushButton("RESCAN GAMEPAD")
        self.rescan_btn.clicked.connect(self._rescan)
        tl.addWidget(self.rescan_btn, 1, 3)
        tl.setColumnStretch(1, 1)
        tl.setColumnStretch(2, 2)
        lay.addWidget(top)

        btn_card = card()
        bl = QVBoxLayout(btn_card)
        bl.setContentsMargins(14, 12, 14, 12)
        bl.setSpacing(10)
        bl.addWidget(label("BUTTONS", "eyebrow"))
        self.buttons_grid = QGridLayout()
        self.buttons_grid.setHorizontalSpacing(8)
        self.buttons_grid.setVerticalSpacing(8)
        bl.addLayout(self.buttons_grid)
        lay.addWidget(btn_card)

        axis_card = card()
        al = QVBoxLayout(axis_card)
        al.setContentsMargins(14, 12, 14, 12)
        al.setSpacing(10)
        al.addWidget(label("AXES", "eyebrow"))
        self.axes_grid = QGridLayout()
        self.axes_grid.setHorizontalSpacing(10)
        self.axes_grid.setVerticalSpacing(10)
        al.addLayout(self.axes_grid)
        lay.addWidget(axis_card)
        lay.addStretch(1)

    def _set_status(self, text: str, kind: str = "warn") -> None:
        self.status.setText(text)
        self.status.setObjectName("statusGood" if kind == "good" else "statusBad" if kind == "bad" else "statusWarn")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _init_backend(self) -> None:
        if pygame is None:
            self._set_status("PYGAME NOT INSTALLED", "bad")
            self.device_name.setText("Install pygame from requirements.txt")
            self.details.setText("Gamepad input tester requires pygame.")
            return
        if not self._pygame_ready:
            pygame.init()
            pygame.joystick.init()
            self._pygame_ready = True
        self._rescan()

    def _shutdown_current(self) -> None:
        if self._joystick is not None:
            try:
                self._joystick.quit()
            except Exception:
                pass
            self._joystick = None

    def shutdown(self) -> None:
        if hasattr(self, 'timer'):
            self.timer.stop()
        self._shutdown_current()
        if pygame is not None and self._pygame_ready:
            try:
                pygame.joystick.quit()
                pygame.quit()
            except Exception:
                pass
            self._pygame_ready = False

    def _rescan(self) -> None:
        if pygame is None or not self._pygame_ready:
            return
        try:
            pygame.event.pump()
            count = pygame.joystick.get_count()
        except Exception as exc:
            self._set_status("GAMEPAD BACKEND ERROR", "bad")
            self.details.setText(str(exc))
            return
        self._last_device_count = count
        if count <= 0:
            self._shutdown_current()
            self.device_name.setText("--")
            self.details.setText("Connect the wheel/gamepad HID device, then press Rescan.")
            self._set_status("NO GAMEPAD DETECTED", "warn")
            self._rebuild_buttons(0)
            self._rebuild_axes(0)
            return
        self._shutdown_current()
        joy = pygame.joystick.Joystick(0)
        joy.init()
        self._joystick = joy
        self.device_name.setText(joy.get_name() or "Gamepad 0")
        guid = ""
        try:
            guid = joy.get_guid()
        except Exception:
            guid = ""
        details = f"Index 0 · {joy.get_numbuttons()} buttons · {joy.get_numaxes()} axes"
        if guid:
            details += f" · GUID {guid}"
        self.details.setText(details)
        self._set_status("CONNECTED", "good")
        self._rebuild_buttons(joy.get_numbuttons())
        self._rebuild_axes(joy.get_numaxes())

    def _rebuild_buttons(self, count: int) -> None:
        while self.buttons_grid.count():
            item = self.buttons_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.button_widgets = []
        cols = 8 if self.scroll.viewport().width() >= 1200 else 6 if self.scroll.viewport().width() >= 900 else 4
        for i in range(count):
            widget = ButtonIndicator(i)
            self.button_widgets.append(widget)
            self.buttons_grid.addWidget(widget, i // cols, i % cols)
        for c in range(cols):
            self.buttons_grid.setColumnStretch(c, 1)

    def _rebuild_axes(self, count: int) -> None:
        while self.axes_grid.count():
            item = self.axes_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.axis_widgets = []
        cols = 2 if self.scroll.viewport().width() >= 980 else 1
        for i in range(count):
            widget = AxisIndicator(i)
            self.axis_widgets.append(widget)
            self.axes_grid.addWidget(widget, i // cols, i % cols)
        for c in range(cols):
            self.axes_grid.setColumnStretch(c, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.button_widgets:
            self._rebuild_buttons(len(self.button_widgets))
        if self.axis_widgets:
            self._rebuild_axes(len(self.axis_widgets))

    def _tick(self) -> None:
        if pygame is None or not self._pygame_ready:
            return
        try:
            pygame.event.pump()
            count = pygame.joystick.get_count()
        except Exception as exc:
            self._set_status("GAMEPAD BACKEND ERROR", "bad")
            self.details.setText(str(exc))
            return
        if count != self._last_device_count or (count > 0 and self._joystick is None):
            self._rescan()
            return
        if self._joystick is None:
            return
        try:
            if not self._joystick.get_init():
                self._rescan()
                return
            num_buttons = self._joystick.get_numbuttons()
            num_axes = self._joystick.get_numaxes()
            if num_buttons != len(self.button_widgets):
                self._rebuild_buttons(num_buttons)
            if num_axes != len(self.axis_widgets):
                self._rebuild_axes(num_axes)
            for i, w in enumerate(self.button_widgets):
                w.set_pressed(bool(self._joystick.get_button(i)))
            for i, w in enumerate(self.axis_widgets):
                w.set_value(float(self._joystick.get_axis(i)))
        except Exception as exc:
            self._set_status("READ ERROR", "bad")
            self.details.setText(str(exc))


class HardwareWorkspace(QMainWindow):
    POLL_MS = 100

    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.setObjectName("hardwareWorkspace")
        self.setWindowTitle("Race Engineer - Hardware")
        self.setMinimumSize(0, 0)
        self.settings = load_settings()
        self.runtime = runtime
        self._curve_stamp = None
        self._curve_supported = False
        self._clutch_supported = False
        self._handbrake_supported = False
        self._curve_timer = QTimer(self)
        self._curve_timer.setSingleShot(True)
        self._curve_timer.setInterval(140)
        self._curve_timer.timeout.connect(self._apply_curve_preview)
        self._pedal_calibration = PedalCalibrationCapture.create()
        self._pedal_calibrating = False
        self._build_ui()
        self.setStyleSheet(APP_QSS)
        self._refresh_ports()
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(self.POLL_MS)
        self.poll_timer.timeout.connect(self._poll)
        self.poll_timer.start()

    def update_snapshot(self, snapshot) -> None:
        if self.runtime is not None and hasattr(self.runtime, "update_snapshot"):
            self.runtime.update_snapshot(snapshot)

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 12, 14, 10)
        outer.setSpacing(12)

        header = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(1)
        left.addWidget(label("RACE ENGINEER · HARDWARE", "eyebrow"))
        left.addWidget(label("Wheel Hardware Companion", "title"))
        left.addWidget(label("Shared Race Engineer telemetry · Receiver · Wheel · Pedals · Shifter · Handbrake · MotorTemp", "subtitle"))
        header.addLayout(left)
        header.addStretch(1)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self.dashboard = QWidget()
        self.curves = QWidget()
        self.input_tester = InputTesterTab()
        self.tabs.addTab(self.dashboard, "HARDWARE")
        self.tabs.addTab(self.curves, "INPUT CALIBRATION")
        self.tabs.addTab(self.input_tester, "INPUT TESTER")
        self._build_dashboard()
        self._build_curves()

        foot = QHBoxLayout()
        self.error = label("", "muted")
        self.protocol = label("Receiver status protocol: waiting", "muted")
        foot.addWidget(self.error)
        foot.addStretch(1)
        foot.addWidget(self.protocol)
        outer.addLayout(foot)

    def _build_dashboard(self):
        tab_layout = QVBoxLayout(self.dashboard)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        self.dashboard_scroll = QScrollArea()
        self.dashboard_scroll.setWidgetResizable(True)
        self.dashboard_scroll.setFrameShape(QFrame.NoFrame)
        self.dashboard_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dashboard_scroll.setStyleSheet(
            f"QScrollArea {{ background:{BG}; border:0; }} QScrollArea > QWidget > QWidget {{ background:{BG}; }}"
        )
        content = QWidget()
        content.setObjectName("appRoot")
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.dashboard_scroll.setWidget(content)
        tab_layout.addWidget(self.dashboard_scroll)

        lay = QVBoxLayout(content)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)
        titlebox = QVBoxLayout()
        titlebox.addWidget(label("LIVE HARDWARE", "eyebrow"))
        titlebox.addWidget(label("WHEEL SYSTEM DASHBOARD", "sectionTitle"))
        lay.addLayout(titlebox)

        connection = card()
        cg = QGridLayout(connection)
        cg.setContentsMargins(14, 12, 14, 12)
        cg.setHorizontalSpacing(10)
        cg.setVerticalSpacing(8)
        cg.addWidget(label("CONNECTION", "eyebrow"), 0, 0, 1, 4)
        cg.addWidget(label("TELEMETRY SOURCE", "muted"), 1, 0)
        self.udp = QLineEdit("RACE ENGINEER (SHARED)")
        self.udp.setReadOnly(True)
        self.udp.setFixedWidth(180)
        cg.addWidget(self.udp, 1, 1)
        cg.addWidget(label("RECEIVER COM", "muted"), 1, 2)
        self.port = QComboBox()
        self.port.setMinimumWidth(180)
        cg.addWidget(self.port, 1, 3)
        self.rescan = QPushButton("RESCAN")
        self.rescan.clicked.connect(self._refresh_ports)
        cg.addWidget(self.rescan, 1, 4)
        self.apply = QPushButton("APPLY / RESTART")
        self.apply.setObjectName("primary")
        self.apply.clicked.connect(self._apply)
        cg.addWidget(self.apply, 1, 5)
        note = label("Uses the main Race Engineer telemetry pipeline and the existing wheel-dashboard link. No duplicate UDP listener is started.", "muted")
        cg.addWidget(note, 2, 0, 1, 6)
        cg.setColumnStretch(3, 1)
        lay.addWidget(connection)

        hw = QGridLayout()
        hw.setSpacing(10)
        self.hw = {}
        hardware_cards = (
            ("receiver", "RECEIVER USB"),
            ("wheel", "WHEEL"),
            ("pedals", "PEDALS"),
            ("shifter", "SHIFTER"),
            ("handbrake", "HANDBRAKE"),
            ("motor", "MOTOR TEMP"),
        )
        for i, (key, name) in enumerate(hardware_cards):
            c = QFrame()
            c.setObjectName("statusCard")
            cl = QVBoxLayout(c)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(5)
            cl.addWidget(label(name, "eyebrow"))
            state = label("WAITING", "statusWarn")
            value = label("--", "value")
            meta = label("--", "muted")
            value.setWordWrap(True)
            meta.setWordWrap(True)
            cl.addWidget(state)
            cl.addWidget(value)
            cl.addWidget(meta)
            row = i // 3
            col = i % 3
            hw.addWidget(c, row, col)
            self.hw[key] = (state, value, meta)
            hw.setColumnStretch(col, 1)
        lay.addLayout(hw)

        tele = card()
        tele.setMinimumHeight(250)
        tl = QVBoxLayout(tele)
        tl.setContentsMargins(14, 12, 14, 12)
        tl.setSpacing(10)
        tl.addWidget(label("F1 TELEMETRY FEED TO PHYSICAL WHEEL", "eyebrow"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        self.tel = {}
        items = (
            "UDP", "SOURCE", "PACKETS/S", "SPEED", "GEAR", "RPM", "REV LIGHTS", "POSITION",
            "LAP", "THROTTLE", "BRAKE", "STEERING", "DRS", "ERS", "FUEL", "FLAG",
        )
        for i, name in enumerate(items):
            c = i % 4
            r = i // 4
            box = QVBoxLayout()
            box.setSpacing(2)
            box.addWidget(label(name, "muted"))
            val = label("--", "value")
            box.addWidget(val)
            grid.addLayout(box, r, c)
            self.tel[name] = val
            grid.setColumnStretch(c, 1)
        tl.addLayout(grid)
        lay.addWidget(tele)
        lay.addStretch(1)

    def _build_curves(self):
        tab_layout = QVBoxLayout(self.curves)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        self.curve_scroll = QScrollArea()
        self.curve_scroll.setWidgetResizable(True)
        self.curve_scroll.setFrameShape(QFrame.NoFrame)
        self.curve_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.curve_scroll.setStyleSheet(
            f"QScrollArea {{ background:{BG}; border:0; }} QScrollArea > QWidget > QWidget {{ background:{BG}; }}"
        )
        content = QWidget()
        content.setObjectName("appRoot")
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.curve_scroll.setWidget(content)
        tab_layout.addWidget(self.curve_scroll)

        lay = QVBoxLayout(content)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        tb = QVBoxLayout()
        tb.setSpacing(2)
        tb.addWidget(label("PEDAL CALIBRATION", "eyebrow"))
        tb.addWidget(label("THROTTLE · BRAKE · CLUTCH · HANDBRAKE RESPONSE", "sectionTitle"))
        subtitle = label(
            "Throttle/Brake remain compatible with older Receivers. Clutch is optional. The handbrake UI can switch between Hall position mode and HX711 load-cell force mode while keeping the same Receiver-side HID Y output, calibration, deadzones and custom response curve.",
            "subtitle",
        )
        subtitle.setWordWrap(True)
        tb.addWidget(subtitle)
        lay.addLayout(tb)

        clutch_card = card()
        ccl = QHBoxLayout(clutch_card)
        ccl.setContentsMargins(14, 10, 14, 10)
        self.clutch_enable = QCheckBox("ENABLE CLUTCH PEDAL")
        self.clutch_enable.setEnabled(False)
        self.clutch_enable.toggled.connect(self._clutch_toggled)
        ccl.addWidget(self.clutch_enable)
        ccl.addStretch(1)
        self.clutch_capability = label("Waiting for Receiver capability", "muted")
        ccl.addWidget(self.clutch_capability)
        lay.addWidget(clutch_card)

        brake_card = card()
        bkc = QVBoxLayout(brake_card)
        bkc.setContentsMargins(14, 10, 14, 10)
        bk_top = QHBoxLayout()
        bk_top.addWidget(label("BRAKE SENSOR", "eyebrow"))
        bk_top.addStretch(1)
        self.brake_sensor_capability = label("Existing brake HID axis · no remapping", "muted")
        bk_top.addWidget(self.brake_sensor_capability)
        bkc.addLayout(bk_top)

        bk_cfg = QGridLayout()
        bk_cfg.setHorizontalSpacing(12); bk_cfg.setVerticalSpacing(6)
        self.brake_sensor = QComboBox()
        self.brake_sensor.addItem("Analog position sensor", "analog")
        self.brake_sensor.addItem("Load cell (HX711)", "load_cell")
        bk_cfg.addWidget(self.brake_sensor, 0, 0)

        self.brake_capacity_label = label("LOAD CELL CAPACITY (kg)", "eyebrow")
        bk_cfg.addWidget(self.brake_capacity_label, 0, 1)
        self.brake_capacity = QLineEdit(str(self.settings.get("brake_load_cell_capacity_kg", 40.0)))
        self.brake_capacity.setValidator(QIntValidator(1, 500, self)); self.brake_capacity.setFixedWidth(90)
        bk_cfg.addWidget(self.brake_capacity, 1, 1)

        self.brake_force_label = label("MAX FORCE FOR 100% (kg)", "eyebrow")
        bk_cfg.addWidget(self.brake_force_label, 0, 2)
        self.brake_max_force = QLineEdit(str(self.settings.get("brake_max_force_kg", 40.0)))
        self.brake_max_force.setValidator(QIntValidator(1, 500, self)); self.brake_max_force.setFixedWidth(90)
        bk_cfg.addWidget(self.brake_max_force, 1, 2)
        bk_cfg.setColumnStretch(3, 1)
        bkc.addLayout(bk_cfg)

        self.brake_sensor_note = label("", "subtitle")
        self.brake_sensor_note.setWordWrap(True)
        bkc.addWidget(self.brake_sensor_note)
        lay.addWidget(brake_card)

        brake_mode = str(self.settings.get("brake_sensor_mode", "analog"))
        brake_idx = self.brake_sensor.findData(brake_mode)
        self.brake_sensor.setCurrentIndex(max(0, brake_idx))
        self.brake_sensor.currentIndexChanged.connect(self._brake_sensor_changed)
        self.brake_capacity.editingFinished.connect(self._brake_sensor_changed)
        self.brake_max_force.editingFinished.connect(self._brake_sensor_changed)

        handbrake_card = card()
        hbc = QVBoxLayout(handbrake_card)
        hbc.setContentsMargins(14, 10, 14, 10)
        hb_top = QHBoxLayout()
        self.handbrake_enable = QCheckBox("ENABLE HANDBRAKE")
        self.handbrake_enable.setEnabled(False)
        self.handbrake_enable.toggled.connect(self._handbrake_toggled)
        hb_top.addWidget(self.handbrake_enable)
        hb_top.addStretch(1)
        self.handbrake_capability = label("Waiting for Receiver capability", "muted")
        hb_top.addWidget(self.handbrake_capability)
        hbc.addLayout(hb_top)

        hb_cfg = QGridLayout()
        hb_cfg.setHorizontalSpacing(12); hb_cfg.setVerticalSpacing(6)
        hb_cfg.addWidget(label("HANDBRAKE SENSOR", "eyebrow"), 0, 0)
        self.handbrake_sensor = QComboBox()
        self.handbrake_sensor.addItem("Hall sensor (analog)", "hall")
        self.handbrake_sensor.addItem("Load cell (HX711)", "load_cell")
        hb_cfg.addWidget(self.handbrake_sensor, 1, 0)

        self.hb_capacity_label = label("LOAD CELL CAPACITY (kg)", "eyebrow")
        hb_cfg.addWidget(self.hb_capacity_label, 0, 1)
        self.handbrake_capacity = QLineEdit(str(self.settings.get("handbrake_load_cell_capacity_kg", 40.0)))
        self.handbrake_capacity.setValidator(QIntValidator(1, 500, self)); self.handbrake_capacity.setFixedWidth(90)
        hb_cfg.addWidget(self.handbrake_capacity, 1, 1)

        self.hb_force_label = label("MAX FORCE FOR 100% (kg)", "eyebrow")
        hb_cfg.addWidget(self.hb_force_label, 0, 2)
        self.handbrake_max_force = QLineEdit(str(self.settings.get("handbrake_max_force_kg", 40.0)))
        self.handbrake_max_force.setValidator(QIntValidator(1, 500, self)); self.handbrake_max_force.setFixedWidth(90)
        hb_cfg.addWidget(self.handbrake_max_force, 1, 2)
        hb_cfg.setColumnStretch(3, 1)
        hbc.addLayout(hb_cfg)

        self.handbrake_sensor_note = label("", "subtitle")
        self.handbrake_sensor_note.setWordWrap(True)
        hbc.addWidget(self.handbrake_sensor_note)
        lay.addWidget(handbrake_card)

        sensor_mode = str(self.settings.get("handbrake_sensor_mode", "hall"))
        idx = self.handbrake_sensor.findData(sensor_mode)
        self.handbrake_sensor.setCurrentIndex(max(0, idx))
        self.handbrake_sensor.currentIndexChanged.connect(self._handbrake_sensor_changed)
        self.handbrake_capacity.editingFinished.connect(self._handbrake_sensor_changed)
        self.handbrake_max_force.editingFinished.connect(self._handbrake_sensor_changed)

        status_row = QHBoxLayout()
        status_row.addStretch(1)
        self.curve_status = label("Waiting for Receiver V8.3.4+", "muted")
        self.curve_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.curve_status.setWordWrap(True)
        status_row.addWidget(self.curve_status, 1)
        lay.addLayout(status_row)

        actions = QHBoxLayout()
        self.load_btn = QPushButton("LOAD FROM RECEIVER")
        self.reset_btn = QPushButton("RESET DEFAULT")
        self.save_btn = QPushButton("SAVE TO RECEIVER")
        self.save_btn.setObjectName("primary")
        self.load_btn.clicked.connect(self._load_curves)
        self.reset_btn.clicked.connect(self._reset_curves)
        self.save_btn.clicked.connect(self._save_curves)
        actions.addWidget(self.load_btn)
        actions.addWidget(self.reset_btn)
        actions.addStretch(1)
        actions.addWidget(self.save_btn)
        lay.addLayout(actions)

        calibration = card()
        cal = QVBoxLayout(calibration)
        cal.setContentsMargins(14, 12, 14, 12)
        cal.setSpacing(10)
        cal_title = QHBoxLayout()
        cal_title.addWidget(label("AUTO DEADZONE CALIBRATION", "eyebrow"))
        cal_title.addStretch(1)
        self.cal_state = label("READY", "muted")
        cal_title.addWidget(self.cal_state)
        cal.addLayout(cal_title)
        cal_desc = label(
            "Release the enabled pedals, start calibration, then fully press and release each enabled pedal 2–3 times. Finish & Save learns physical endpoints while preserving each response curve.",
            "subtitle",
        )
        cal_desc.setWordWrap(True)
        cal.addWidget(cal_desc)
        cal_grid = QGridLayout()
        cal_grid.setHorizontalSpacing(18)
        cal_grid.setVerticalSpacing(6)
        for col, name in enumerate(("THROTTLE", "BRAKE", "CLUTCH", "HANDBRAKE")):
            cal_grid.addWidget(label(name, "eyebrow"), 0, col)
        self.cal_throttle = label("RAW RANGE --  ·  TRAVEL --  ·  DZ -- / --", "muted")
        self.cal_brake = label("RAW RANGE --  ·  TRAVEL --  ·  DZ -- / --", "muted")
        self.cal_clutch = label("DISABLED", "muted")
        self.cal_handbrake = label("DISABLED", "muted")
        for col, w in enumerate((self.cal_throttle, self.cal_brake, self.cal_clutch, self.cal_handbrake)):
            w.setWordWrap(True)
            cal_grid.addWidget(w, 1, col)
            cal_grid.setColumnStretch(col, 1)
        cal.addLayout(cal_grid)
        cal_buttons = QHBoxLayout()
        self.cal_start_btn = QPushButton("START CALIBRATION")
        self.cal_start_btn.setObjectName("primary")
        self.cal_finish_btn = QPushButton("FINISH & SAVE")
        self.cal_cancel_btn = QPushButton("CANCEL")
        self.cal_finish_btn.setEnabled(False)
        self.cal_cancel_btn.setEnabled(False)
        self.cal_start_btn.clicked.connect(self._start_pedal_calibration)
        self.cal_finish_btn.clicked.connect(self._finish_pedal_calibration)
        self.cal_cancel_btn.clicked.connect(self._cancel_pedal_calibration)
        cal_buttons.addWidget(self.cal_start_btn)
        cal_buttons.addWidget(self.cal_finish_btn)
        cal_buttons.addWidget(self.cal_cancel_btn)
        cal_buttons.addStretch(1)
        cal.addLayout(cal_buttons)
        lay.addWidget(calibration)

        self.curve_cards = QWidget()
        self.curve_cards.setObjectName("appRoot")
        self.curve_cards.setMinimumWidth(0)
        self.curve_cards.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.curve_grid = QGridLayout(self.curve_cards)
        self.curve_grid.setContentsMargins(0, 0, 0, 0)
        self.curve_grid.setSpacing(12)
        self.throttle = PedalCurveEditor("Throttle", self._curve_changed)
        self.brake = PedalCurveEditor("Brake", self._curve_changed)
        self.clutch = PedalCurveEditor("Clutch", self._curve_changed)
        self.handbrake = PedalCurveEditor("Handbrake", self._curve_changed)
        for w in (self.throttle, self.brake, self.clutch, self.handbrake):
            w.setMinimumWidth(0)
            w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.clutch.setEnabled(False)
        self.handbrake.setEnabled(False)
        self._curve_layout_mode = None
        self._brake_sensor_changed()
        self._handbrake_sensor_changed()
        lay.addWidget(self.curve_cards)
        lay.addStretch(1)
        self._update_curve_layout(force=True)

    def _update_curve_layout(self, force: bool = False):
        if not hasattr(self, "curve_grid"):
            return
        width = self.curve_scroll.viewport().width() if hasattr(self, "curve_scroll") else self.width()
        # Four full curve editors are too cramped on a normal 1920px desktop.
        # Keep a roomy 2x2 layout through common Full-HD/QHD widths and only
        # use four columns on genuinely ultra-wide viewports.
        mode = 4 if width >= 2800 else 2 if width >= 1040 else 1
        if not force and mode == self._curve_layout_mode:
            return
        self._curve_layout_mode = mode
        editors = (self.throttle, self.brake, self.clutch, self.handbrake)
        for w in editors: self.curve_grid.removeWidget(w)
        if mode == 4:
            for c, w in enumerate(editors): self.curve_grid.addWidget(w, 0, c); self.curve_grid.setColumnStretch(c, 1)
        elif mode == 2:
            for i, w in enumerate(editors): self.curve_grid.addWidget(w, i // 2, i % 2)
            self.curve_grid.setColumnStretch(0, 1); self.curve_grid.setColumnStretch(1, 1)
        else:
            for r, w in enumerate(editors): self.curve_grid.addWidget(w, r, 0)
            self.curve_grid.setColumnStretch(0, 1)
        min_h = 500 if mode == 1 else (480 if mode == 2 else 0)
        for w in editors: w.setMinimumHeight(min_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_curve_layout)

    def _refresh_ports(self):
        current = getattr(getattr(self.runtime, "receiver", None), "requested_port", None) or self.settings.get("receiver_port", "auto") or "auto"
        vals = ["auto"] + [d for d, _ in serial_ports()]
        self.port.clear()
        self.port.addItems(vals)
        self.port.setCurrentText(current if current in vals else "auto")

    def _start_runtime(self):
        # The embedded Hardware workspace shares Race Engineer's already-running
        # wheel bridge. It must never create a second UDP or serial owner.
        return

    def _stop_runtime(self):
        # Lifetime is owned by RaceStateReceiver, not this page.
        return

    def _apply(self):
        selected = self.port.currentText() or "auto"
        self.settings["receiver_port"] = selected
        save_settings(self.settings)
        self.error.setText("")
        self._curve_stamp = None
        receiver = getattr(self.runtime, "receiver", None) if self.runtime is not None else None
        if receiver is None:
            self.error.setText("Receiver bridge is not available")
            return
        try:
            if hasattr(receiver, "reconfigure_port"):
                receiver.reconfigure_port(selected)
            else:
                receiver.requested_port = selected
            self.error.setText(f"Receiver COM selection applied: {selected}")
        except Exception as exc:
            self.error.setText(f"Could not change Receiver COM: {exc}")

    def _clutch_toggled(self, checked: bool):
        if checked and not self._clutch_supported:
            self.clutch_enable.blockSignals(True)
            self.clutch_enable.setChecked(False)
            self.clutch_enable.blockSignals(False)
            self.curve_status.setText("CLUTCH REQUIRES RECEIVER + PEDALS V8.3.6+")
            return
        self.clutch.setEnabled(bool(checked and self._clutch_supported))
        self._refresh_calibration_labels()
        self._curve_changed()

    def _brake_sensor_changed(self, *_args):
        if not hasattr(self, "brake_sensor"):
            return
        mode = self.brake_sensor.currentData() or "analog"
        try:
            capacity = max(1.0, float(self.brake_capacity.text() or 40.0))
        except ValueError:
            capacity = 40.0
        try:
            max_force = max(1.0, float(self.brake_max_force.text() or capacity))
        except ValueError:
            max_force = capacity
        if max_force > capacity:
            max_force = capacity
        self.brake_capacity.setText(f"{capacity:g}")
        self.brake_max_force.setText(f"{max_force:g}")
        is_load_cell = mode == "load_cell"
        for w in (self.brake_capacity_label, self.brake_capacity, self.brake_force_label, self.brake_max_force):
            w.setVisible(is_load_cell)
        if is_load_cell:
            self.brake_sensor_note.setText(
                f"FORCE MODE · {capacity:g} kg brake cell · {max_force:g} kg = 100% brake. "
                "The brake curve X-axis is shown in kg. Pedal firmware Config.h must use BRAKE_SENSOR_HX711 and its counts-per-kg value must be calibrated."
            )
        else:
            self.brake_sensor_note.setText(
                "POSITION MODE · Existing analog brake sensor on GPIO35. Calibration learns released/full-travel endpoints and the curve input is shown as travel %."
            )
        if hasattr(self, "brake"):
            self.brake.set_input_mode(is_load_cell, max_force)
        self.settings["brake_sensor_mode"] = mode
        self.settings["brake_load_cell_capacity_kg"] = capacity
        self.settings["brake_max_force_kg"] = max_force
        save_settings(self.settings)
        if hasattr(self, "cal_state") and not self._pedal_calibrating:
            hb_load = hasattr(self, "handbrake_sensor") and self.handbrake_sensor.currentData() == "load_cell"
            if is_load_cell and hb_load:
                self.cal_state.setText("READY · BRAKE + HANDBRAKE FORCE CALIBRATION")
            elif is_load_cell:
                self.cal_state.setText("READY · BRAKE LOAD-CELL FORCE CALIBRATION")
            elif hb_load:
                self.cal_state.setText("READY · HANDBRAKE LOAD-CELL FORCE CALIBRATION")
            else:
                self.cal_state.setText("READY · POSITION CALIBRATION")
        self._refresh_calibration_labels() if hasattr(self, "cal_brake") else None

    def _handbrake_sensor_changed(self, *_args):
        if not hasattr(self, "handbrake_sensor"):
            return
        mode = self.handbrake_sensor.currentData() or "hall"
        try:
            capacity = max(1.0, float(self.handbrake_capacity.text() or 40.0))
        except ValueError:
            capacity = 40.0
        try:
            max_force = max(1.0, float(self.handbrake_max_force.text() or capacity))
        except ValueError:
            max_force = capacity
        if max_force > capacity:
            max_force = capacity
        self.handbrake_capacity.setText(f"{capacity:g}")
        self.handbrake_max_force.setText(f"{max_force:g}")
        is_load_cell = mode == "load_cell"
        for w in (self.hb_capacity_label, self.handbrake_capacity, self.hb_force_label, self.handbrake_max_force):
            w.setVisible(is_load_cell)
        if is_load_cell:
            self.handbrake_sensor_note.setText(
                f"FORCE MODE · {capacity:g} kg cell · {max_force:g} kg = 100% target. "
                "The curve X-axis is displayed in kg. Firmware Config.h must use HANDBRAKE_SENSOR_HX711 and its HX711 full-scale setting must be calibrated to the same 100% pull force."
            )
        else:
            self.handbrake_sensor_note.setText(
                "POSITION MODE · Analog Hall input on GPIO0. Calibration learns released/full-travel endpoints; curve input is shown as travel %. Firmware Config.h must use HANDBRAKE_SENSOR_HALL."
            )
        if hasattr(self, "handbrake"):
            self.handbrake.set_input_mode(is_load_cell, max_force)
        self.settings["handbrake_sensor_mode"] = mode
        self.settings["handbrake_load_cell_capacity_kg"] = capacity
        self.settings["handbrake_max_force_kg"] = max_force
        save_settings(self.settings)
        if hasattr(self, "cal_state") and not self._pedal_calibrating:
            brake_load = hasattr(self, "brake_sensor") and self.brake_sensor.currentData() == "load_cell"
            if is_load_cell and brake_load:
                self.cal_state.setText("READY · BRAKE + HANDBRAKE FORCE CALIBRATION")
            elif is_load_cell:
                self.cal_state.setText("READY · HANDBRAKE LOAD-CELL FORCE CALIBRATION")
            elif brake_load:
                self.cal_state.setText("READY · BRAKE LOAD-CELL FORCE CALIBRATION")
            else:
                self.cal_state.setText("READY · POSITION CALIBRATION")
        self._refresh_calibration_labels() if hasattr(self, "cal_handbrake") else None

    def _handbrake_toggled(self, checked: bool):
        if checked and not self._handbrake_supported:
            self.handbrake_enable.blockSignals(True); self.handbrake_enable.setChecked(False); self.handbrake_enable.blockSignals(False)
            self.curve_status.setText("HANDBRAKE REQUIRES RECEIVER + SHIFTER/HANDBRAKE C3 V8.3.8+")
            return
        self.handbrake.setEnabled(bool(checked and self._handbrake_supported))
        self._refresh_calibration_labels(); self._curve_changed()

    def _curve_changed(self):
        self._curve_timer.start()

    def _curve_settings(self):
        return PedalCurveSettings(
            self.throttle.get_curve(),
            self.brake.get_curve(),
            self.clutch.get_curve(),
            self.clutch_enable.isChecked() and self._clutch_supported,
            self.handbrake.get_curve(),
            self.handbrake_enable.isChecked() and self._handbrake_supported,
        ).sanitized()

    def _apply_curve_preview(self):
        if not self.runtime:
            return
        _s, supported, _stamp, _version = self.runtime.receiver.pedal_settings_snapshot()
        self._curve_supported = supported
        if not supported:
            self.curve_status.setText("Receiver V8.3.4+ required")
            return
        self.runtime.receiver.apply_pedal_settings(self._curve_settings(), save=False)
        self.curve_status.setText("PREVIEW APPLIED · SAVE TO KEEP")

    def _load_curves(self):
        if self.runtime:
            self.runtime.receiver.request_pedal_settings()
            self.curve_status.setText("LOADING FROM RECEIVER…")

    def _reset_curves(self):
        defaults = PedalCurveSettings()
        self.throttle.set_curve(defaults.throttle)
        self.brake.set_curve(defaults.brake)
        self.clutch.set_curve(defaults.clutch)
        self.handbrake.set_curve(defaults.handbrake)
        self.clutch_enable.setChecked(False)
        self.handbrake_enable.setChecked(False)
        if self.runtime:
            _s, supported, _stamp, _version = self.runtime.receiver.pedal_settings_snapshot()
            if supported:
                self.runtime.receiver.apply_pedal_settings(defaults, save=False)
                self.curve_status.setText("LINEAR DEFAULTS APPLIED · CLUTCH/HANDBRAKE OFF · SAVE TO KEEP")
            else:
                self.curve_status.setText("Receiver V8.3.4+ required")

    def _save_curves(self):
        if not self.runtime:
            return
        _s, supported, _stamp, _version = self.runtime.receiver.pedal_settings_snapshot()
        if not supported:
            self.curve_status.setText("Receiver V8.3.4+ required")
            return
        self.runtime.receiver.apply_pedal_settings(self._curve_settings(), save=True)
        self.curve_status.setText("SAVING TO RECEIVER…")

    def _start_pedal_calibration(self):
        if not self.runtime:
            self.cal_state.setText("RECEIVER NOT AVAILABLE")
            return
        h = self.runtime.receiver.health_snapshot()
        if not h.serial_connected or not h.extended_status_active or h.pedal_throttle_raw is None or h.pedal_brake_raw is None:
            self.cal_state.setText("WAITING FOR LIVE PEDAL DATA")
            return
        if self.clutch_enable.isChecked() and (not h.clutch_supported or h.pedal_clutch_raw is None):
            self.cal_state.setText("WAITING FOR LIVE CLUTCH DATA"); return
        if self.handbrake_enable.isChecked() and (not h.handbrake_supported or h.handbrake_raw is None):
            self.cal_state.setText("WAITING FOR LIVE HANDBRAKE DATA"); return
        _settings, supported, _stamp, _version = self.runtime.receiver.pedal_settings_snapshot()
        if not supported:
            self.cal_state.setText("RECEIVER V8.3.4+ REQUIRED")
            return
        self._pedal_calibration.reset()
        self._pedal_calibrating = True
        self.cal_start_btn.setEnabled(False)
        self.cal_finish_btn.setEnabled(True)
        self.cal_cancel_btn.setEnabled(True)
        axes = ["THROTTLE", "BRAKE"]
        if self.clutch_enable.isChecked(): axes.append("CLUTCH")
        if self.handbrake_enable.isChecked(): axes.append("HANDBRAKE")
        axes = ", ".join(axes)
        force_steps = []
        if self.brake_sensor.currentData() == "load_cell":
            force_steps.append(f"PRESS BRAKE TO TARGET MAX FORCE ({self.brake_max_force.text()} kg) 2–3 TIMES")
        if self.handbrake_enable.isChecked() and self.handbrake_sensor.currentData() == "load_cell":
            force_steps.append(f"PULL HANDBRAKE TO TARGET MAX FORCE ({self.handbrake_max_force.text()} kg) 2–3 TIMES")
        if force_steps:
            self.cal_state.setText("CALIBRATING · " + " · ".join(force_steps) + f" · FULLY CYCLE OTHER ENABLED AXES · {axes}")
        else:
            self.cal_state.setText(f"CALIBRATING · FULLY PRESS AND RELEASE {axes}")
        self._observe_pedal_calibration(h.pedal_throttle_raw, h.pedal_brake_raw, h.pedal_clutch_raw, h.handbrake_raw)

    def _cancel_pedal_calibration(self):
        self._pedal_calibrating = False
        self._pedal_calibration.reset()
        self.cal_start_btn.setEnabled(True)
        self.cal_finish_btn.setEnabled(False)
        self.cal_cancel_btn.setEnabled(False)
        self.cal_state.setText("CANCELLED · CURRENT RECEIVER SETTINGS UNCHANGED")
        self._refresh_calibration_labels()

    def _observe_pedal_calibration(self, throttle_raw: int | None, brake_raw: int | None, clutch_raw: int | None, handbrake_raw: int | None):
        if not self._pedal_calibrating:
            return
        self._pedal_calibration.observe(
            throttle_raw,
            brake_raw,
            clutch_raw if self.clutch_enable.isChecked() else None,
            handbrake_raw if self.handbrake_enable.isChecked() else None,
        )
        self._refresh_calibration_labels()

    @staticmethod
    def _calibration_text(capture) -> str:
        if capture.min_raw is None or capture.max_raw is None:
            return "RAW RANGE --  ·  TRAVEL --  ·  DZ -- / --"
        bottom, top = capture.proposed_deadzones()
        ready = "READY" if capture.ready and capture.within_supported_range else "KEEP MOVING"
        return f"RAW {capture.min_raw} → {capture.max_raw}  ·  TRAVEL {capture.travel_percent:.1f}%  ·  DZ {bottom}% / {top}%  ·  {ready}"

    def _refresh_calibration_labels(self):
        self.cal_throttle.setText(self._calibration_text(self._pedal_calibration.throttle))
        if hasattr(self, "brake_sensor") and self.brake_sensor.currentData() == "load_cell":
            c = self._pedal_calibration.brake
            if c.min_raw is None or c.max_raw is None:
                brake_text = f"FORCE RANGE -- → {self.brake_max_force.text()} kg · RAW -- · DZ -- / --"
            else:
                bottom, top = c.proposed_deadzones()
                ready = "READY" if c.ready and c.within_supported_range else "KEEP PRESSING"
                brake_text = f"TARGET 0 → {self.brake_max_force.text()} kg · RAW {c.min_raw} → {c.max_raw} · DZ {bottom}% / {top}% · {ready}"
            self.cal_brake.setText(brake_text)
        else:
            self.cal_brake.setText(self._calibration_text(self._pedal_calibration.brake))
        self.cal_clutch.setText(self._calibration_text(self._pedal_calibration.clutch) if self.clutch_enable.isChecked() else "DISABLED")
        if self.handbrake_enable.isChecked():
            if self.handbrake_sensor.currentData() == "load_cell":
                c = self._pedal_calibration.handbrake
                if c.min_raw is None or c.max_raw is None:
                    hb_text = f"FORCE RANGE -- → {self.handbrake_max_force.text()} kg · RAW -- · DZ -- / --"
                else:
                    bottom, top = c.proposed_deadzones()
                    ready = "READY" if c.ready and c.within_supported_range else "KEEP PULLING"
                    hb_text = f"TARGET 0 → {self.handbrake_max_force.text()} kg · RAW {c.min_raw} → {c.max_raw} · DZ {bottom}% / {top}% · {ready}"
                self.cal_handbrake.setText(hb_text)
            else:
                self.cal_handbrake.setText(self._calibration_text(self._pedal_calibration.handbrake))
        else:
            self.cal_handbrake.setText("DISABLED")

    def _finish_pedal_calibration(self):
        if not self._pedal_calibrating or not self.runtime:
            return
        axes = [
            ("throttle", self._pedal_calibration.throttle),
            ("brake", self._pedal_calibration.brake),
        ]
        if self.clutch_enable.isChecked(): axes.append(("clutch", self._pedal_calibration.clutch))
        if self.handbrake_enable.isChecked(): axes.append(("handbrake", self._pedal_calibration.handbrake))
        problems = []
        for name, capture in axes:
            if not capture.ready:
                problems.append(f"{name} needs more travel")
            elif not capture.within_supported_range:
                problems.append(f"{name} endpoint exceeds 30% deadzone limit")
        if problems:
            self.cal_state.setText("CALIBRATION NOT SAVED · " + " · ".join(problems).upper())
            return

        tb, tt = self._pedal_calibration.throttle.proposed_deadzones()
        bb, bt = self._pedal_calibration.brake.proposed_deadzones()
        current_t = self.throttle.get_curve()
        current_b = self.brake.get_curve()
        current_c = self.clutch.get_curve()
        current_h = self.handbrake.get_curve()
        cb, ct = (0, 0)
        if self.clutch_enable.isChecked(): cb, ct = self._pedal_calibration.clutch.proposed_deadzones()
        hb, ht = (0, 0)
        if self.handbrake_enable.isChecked(): hb, ht = self._pedal_calibration.handbrake.proposed_deadzones()
        calibrated = PedalCurveSettings(
            AxisCurve(tb, tt, current_t.outputs),
            AxisCurve(bb, bt, current_b.outputs),
            AxisCurve(cb, ct, current_c.outputs) if self.clutch_enable.isChecked() else current_c,
            self.clutch_enable.isChecked(),
            AxisCurve(hb, ht, current_h.outputs) if self.handbrake_enable.isChecked() else current_h,
            self.handbrake_enable.isChecked(),
        ).sanitized()
        self.throttle.set_curve(calibrated.throttle)
        self.brake.set_curve(calibrated.brake)
        self.clutch.set_curve(calibrated.clutch)
        self.handbrake.set_curve(calibrated.handbrake)
        self.runtime.receiver.apply_pedal_settings(calibrated, save=True)
        self._pedal_calibrating = False
        self.cal_start_btn.setEnabled(True)
        self.cal_finish_btn.setEnabled(False)
        self.cal_cancel_btn.setEnabled(False)
        extra = f" · CLUTCH DZ {cb}%/{ct}%" if self.clutch_enable.isChecked() else ""
        if self.handbrake_enable.isChecked(): extra += f" · HANDBRAKE DZ {hb}%/{ht}%"
        self.cal_state.setText(f"CALIBRATION SAVED · THROTTLE DZ {tb}%/{tt}% · BRAKE DZ {bb}%/{bt}%{extra}")
        self.curve_status.setText("CALIBRATION SAVED TO RECEIVER")

    @staticmethod
    def _state_text(connected: bool, known=True):
        return "CONNECTED" if connected and known else ("DISCONNECTED" if known else "WAITING")

    def _set_state(self, q: QLabel, text: str):
        q.setText(text)
        q.setObjectName("statusGood" if text == "CONNECTED" else "statusBad" if text == "DISCONNECTED" else "statusWarn")
        q.style().unpolish(q)
        q.style().polish(q)

    def _poll(self):
        rt = self.runtime
        if not rt:
            return
        live, _ = rt.decoder.snapshots()
        h = rt.receiver.health_snapshot()
        known = h.serial_connected and h.status_fresh
        self._set_state(self.hw["receiver"][0], self._state_text(h.serial_connected, True))
        self.hw["receiver"][1].setText(h.port or "--")
        self.hw["receiver"][2].setText(f"{h.status_frames_received} status frames · V{h.status_protocol_version or '--'}")
        self._set_state(self.hw["wheel"][0], self._state_text(h.wheel_connected, known))
        self.hw["wheel"][1].setText("Telemetry TX 50 Hz")
        self.hw["wheel"][2].setText(f"{h.wheel_age_ms if h.wheel_age_ms is not None else '--'} ms · {h.wheel_packets} packets")
        self._set_state(self.hw["pedals"][0], self._state_text(h.pedals_connected, known))
        if h.pedal_throttle_percent is None:
            pedal_text = "--"
        else:
            pedal_text = f"T {h.pedal_throttle_percent:.1f}%   B {h.pedal_brake_percent:.1f}%"
            if h.clutch_supported:
                pedal_text += "   C --" if h.pedal_clutch_percent is None else f"   C {h.pedal_clutch_percent:.1f}%"
        self.hw["pedals"][1].setText(pedal_text)
        capability = " · Clutch V2" if h.clutch_supported else " · 2-axis V1"
        brake_mode_label = " · Brake HX711" if hasattr(self, "brake_sensor") and self.brake_sensor.currentData() == "load_cell" else " · Brake Analog"
        self.hw["pedals"][2].setText(f"{h.pedals_age_ms if h.pedals_age_ms is not None else '--'} ms · {h.pedal_packets} packets{capability}{brake_mode_label}")

        # WL/V3 capability tells us the Receiver firmware knows about the
        # combined shifter/handbrake node.  It does *not* mean that the C3 is
        # currently online.  The Receiver sends 0xFFFF for handbrakeRaw when
        # the C3 link is timed out, which the PC decoder exposes as None.
        shifter_link_known = bool(known and h.handbrake_supported)
        shifter_connected = bool(shifter_link_known and h.handbrake_raw is not None)
        self._set_state(self.hw["shifter"][0], self._state_text(shifter_connected, shifter_link_known))
        if shifter_connected:
            self.hw["shifter"][1].setText("Buttons 30 · 31 · 32")
            self.hw["shifter"][2].setText("ESP32-C3 wireless link active · V8.3.8+")
        elif shifter_link_known:
            self.hw["shifter"][1].setText("--")
            self.hw["shifter"][2].setText("ESP32-C3 not receiving · check power / MAC / ESP-NOW")
        else:
            self.hw["shifter"][1].setText("--")
            self.hw["shifter"][2].setText("Waiting for V8.3.8+ Receiver capability")

        # Handbrake has two independent states: the shared C3 radio link and
        # whether the handbrake HID axis is enabled in Receiver settings.
        hb_enabled = bool(self.handbrake_enable.isChecked() and self._handbrake_supported)
        if not self._handbrake_supported:
            self._set_state(self.hw["handbrake"][0], "WAITING" if not known else "DISCONNECTED")
            self.hw["handbrake"][1].setText("--")
            self.hw["handbrake"][2].setText("Waiting for V8.3.8+ handbrake capability")
        elif not hb_enabled:
            self._set_state(self.hw["handbrake"][0], "DISABLED")
            self.hw["handbrake"][1].setText("Y axis OFF")
            self.hw["handbrake"][2].setText(
                "C3 link active · input ignored" if shifter_connected else "C3 offline · handbrake disabled"
            )
        else:
            self._set_state(self.hw["handbrake"][0], self._state_text(shifter_connected, shifter_link_known))
            if shifter_connected and h.handbrake_percent is not None:
                self.hw["handbrake"][1].setText(f"Y {h.handbrake_percent:.1f}%")
            else:
                self.hw["handbrake"][1].setText("Y axis --")
            hb_mode = self.handbrake_sensor.currentText()
            self.hw["handbrake"][2].setText(
                f"Shared ESP32-C3 link · {hb_mode}" if shifter_connected else "Waiting for ESP32-C3 input"
            )

        self._set_state(self.hw["motor"][0], self._state_text(h.motor_temp_connected, known))
        self.hw["motor"][1].setText("--" if h.motor_temp_c is None else f"{h.motor_temp_c:.2f} °C")
        self.hw["motor"][2].setText(f"{h.motor_temp_age_ms if h.motor_temp_age_ms is not None else '--'} ms · {h.motor_temp_packets} packets")

        vals = {
            "UDP": "CONNECTED" if live.udp_connected else "WAITING",
            "SOURCE": live.source,
            "PACKETS/S": f"{live.packets_per_second:.0f}",
            "SPEED": f"{live.speed_kph} km/h",
            "GEAR": "R" if live.gear < 0 else "N" if live.gear == 0 else str(live.gear),
            "RPM": str(live.engine_rpm),
            "REV LIGHTS": f"{live.rpm_percent}%",
            "POSITION": str(live.position or "--"),
            "LAP": str(live.lap_number or "--"),
            "THROTTLE": f"{live.throttle_percent}%",
            "BRAKE": f"{live.brake_percent}%",
            "STEERING": f"{live.steering_percent:+d}%",
            "DRS": "ACTIVE" if live.drs_active else "AVAILABLE" if live.drs_available else "OFF",
            "ERS": "--" if live.ers_percent is None else f"{live.ers_percent:.0f}% · mode {live.ers_mode}",
            "FUEL": "--" if live.fuel_percent is None else f"{live.fuel_percent:.0f}%",
            "FLAG": str(live.flag_status),
        }
        for k, v in vals.items():
            self.tel[k].setText(v)

        self._clutch_supported = bool(h.clutch_supported)
        self._handbrake_supported = bool(h.handbrake_supported)
        self.clutch_enable.setEnabled(self._clutch_supported)
        self.clutch_capability.setText("CLUTCH CAPABLE · V8.3.6+" if self._clutch_supported else "CLUTCH DISABLED · V8.3.5 COMPATIBILITY MODE")
        self.handbrake_enable.setEnabled(self._handbrake_supported)
        self.handbrake_capability.setText("HANDBRAKE CAPABLE · V8.3.8+" if self._handbrake_supported else "HANDBRAKE UNAVAILABLE")

        settings, supported, stamp, settings_version = rt.receiver.pedal_settings_snapshot()
        self._curve_supported = supported
        if supported and stamp is not None and stamp != self._curve_stamp:
            self._curve_stamp = stamp
            self.throttle.set_curve(settings.throttle)
            self.brake.set_curve(settings.brake)
            self.clutch.set_curve(settings.clutch)
            self.handbrake.set_curve(settings.handbrake)
            self.clutch_enable.blockSignals(True)
            self.clutch_enable.setChecked(bool(settings.clutch_enabled and self._clutch_supported))
            self.clutch_enable.blockSignals(False)
            self.clutch.setEnabled(self.clutch_enable.isChecked() and self._clutch_supported)
            self.handbrake_enable.blockSignals(True)
            self.handbrake_enable.setChecked(bool(settings.handbrake_enabled and self._handbrake_supported))
            self.handbrake_enable.blockSignals(False)
            self.handbrake.setEnabled(self.handbrake_enable.isChecked() and self._handbrake_supported)
            self._refresh_calibration_labels()
            self.curve_status.setText(f"RECEIVER SETTINGS LOADED / APPLIED · PC/PS V{settings_version}")
        elif h.serial_connected and not supported:
            self.curve_status.setText("Receiver V8.3.4+ required")
        elif not h.serial_connected:
            self.curve_status.setText("WAITING FOR RECEIVER")

        self.throttle.set_live(h.pedal_throttle_raw)
        self.brake.set_live(h.pedal_brake_raw)
        self.clutch.set_live(
            h.pedal_clutch_raw
            if h.clutch_supported and self.clutch_enable.isChecked()
            else None
        )
        self.handbrake.set_live(
            h.handbrake_raw
            if h.handbrake_supported and self.handbrake_enable.isChecked()
            else None
        )
        self._observe_pedal_calibration(h.pedal_throttle_raw, h.pedal_brake_raw, h.pedal_clutch_raw, h.handbrake_raw)
        self.protocol.setText(
            "Receiver: RS/V1 + WL/V3 clutch/handbrake" if h.handbrake_supported else ("Receiver: RS/V1 + WL/V2 clutch" if h.clutch_supported else "Receiver: RS/V1 + WL/V1")
        )
        errs = [x for x in (rt.udp.last_error, h.last_error) if x]
        self.error.setText(" | ".join(errs))

    def closeEvent(self, event):
        self.poll_timer.stop()
        self._curve_timer.stop()
        if hasattr(self, "input_tester"):
            self.input_tester.shutdown()
        event.accept()
