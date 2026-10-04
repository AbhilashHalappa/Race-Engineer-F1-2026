"""Custom-painted PySide6 widgets for the compact race-engineer overlay."""
from __future__ import annotations

from collections import deque
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


WHITE = QColor(244, 246, 248)
MUTED = QColor(155, 164, 175)
GRID = QColor(255, 255, 255, 28)
GREEN = QColor(78, 210, 130)
RED = QColor(239, 103, 100)
AMBER = QColor(232, 190, 88)
CYAN = QColor(89, 191, 229)


def _overlay_visual_scale(widget):
    try:
        value = widget.property("overlayVisualScale")
        return max(0.70, min(1.60, float(value))) if value is not None else 1.0
    except Exception:
        return 1.0


def _overlay_font(widget, size, weight=QFont.Normal):
    return QFont("Segoe UI", max(5, int(round(float(size) * _overlay_visual_scale(widget)))), weight)


def _current_distance_epoch_start(distances, *, rewind_threshold_m=25.0):
    """Return the first sample index from the newest monotonic lap-distance epoch.

    Lap distance wraps from roughly track length back to zero at start/finish.
    DI intentionally keeps sampling continuously across that boundary, so the
    renderer must ignore same-distance samples retained from the previous lap
    rather than drawing both laps on top of each other. Small telemetry jitter
    is tolerated and does not create a new epoch.
    """
    start = 0
    previous = None
    for index, raw in enumerate(distances):
        if raw is None:
            continue
        try:
            current = float(raw)
        except (TypeError, ValueError):
            continue
        if previous is not None and current < previous - float(rewind_threshold_m):
            start = index
        previous = current
    return start


class ReferenceBannerWidget(QWidget):
    """Compact reference/coaching preparation banner used before full coaching is ready."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(62)
        self.title = "SETTING REFERENCE LAP"
        self.subtitle = "Complete a valid lap to unlock delta + coaching"

    def set_text(self, title: str, subtitle: str) -> None:
        self.title = title
        self.subtitle = subtitle
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.setBrush(QColor(8, 10, 13, 115))
        p.drawRoundedRect(r, 9, 9)

        p.setFont(_overlay_font(self, 10, QFont.Bold))
        p.setPen(WHITE)
        p.drawText(QRectF(r.left() + 12, r.top() + 10, r.width() - 24, 18), Qt.AlignCenter, self.title)
        p.setFont(_overlay_font(self, 8))
        p.setPen(MUTED)
        p.drawText(QRectF(r.left() + 12, r.top() + 32, r.width() - 24, 16), Qt.AlignCenter, self.subtitle)


class InputTraceWidget(QWidget):
    """Distance-aligned current-lap throttle/brake trace driven by DI."""

    def __init__(self, parent=None, *, samples=150):
        super().__init__(parent)
        self.setMinimumHeight(126)
        # Start empty. Prefilling with zero/None produced a visible diagonal
        # "ghost" trace when a distance axis became active before the deque had
        # been fully replaced by real samples.
        self.throttle = deque(maxlen=samples)
        self.brake = deque(maxlen=samples)
        self.distances = deque(maxlen=samples)
        self.show_throttle = True
        self.show_brake = True
        self.distance_cursor_m = None
        self.distance_window_m = 500.0

    def set_distance_cursor(self, distance_m, *, window_m=500.0):
        try:
            self.distance_cursor_m = float(distance_m) if distance_m is not None else None
        except (TypeError, ValueError):
            self.distance_cursor_m = None
        self.distance_window_m = max(50.0, float(window_m))
        self.update()

    def set_visible_series(self, *, throttle=None, brake=None):
        if throttle is not None:
            self.show_throttle = bool(throttle)
        if brake is not None:
            self.show_brake = bool(brake)
        self.update()

    def add_sample(self, throttle: float, brake: float, distance_m=None) -> None:
        self.throttle.append(max(0.0, min(1.0, float(throttle))))
        self.brake.append(max(0.0, min(1.0, float(brake))))
        try:
            self.distances.append(float(distance_m) if distance_m is not None else None)
        except (TypeError, ValueError):
            self.distances.append(None)
        self.update()

    def clear(self) -> None:
        self.throttle.clear(); self.brake.clear(); self.distances.clear(); self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.setBrush(QColor(8, 10, 13, 94))
        p.drawRoundedRect(r, 8, 8)

        plot = r.adjusted(10, 22, -10, -24)
        p.setFont(_overlay_font(self, 8, QFont.DemiBold))
        p.setPen(MUTED)
        p.drawText(QRectF(r.left() + 10, r.top() + 4, 95, 16), Qt.AlignLeft, "INPUT TRACE")
        if self.show_throttle:
            p.setPen(GREEN)
            p.drawText(QRectF(r.right() - 145, r.top() + 4, 65, 16), Qt.AlignRight, "THROTTLE")
        if self.show_brake:
            p.setPen(RED)
            p.drawText(QRectF(r.right() - 73, r.top() + 4, 63, 16), Qt.AlignRight, "BRAKE")

        p.setPen(QPen(GRID, 1))
        for frac in (0.33, 0.66):
            y = plot.bottom() - plot.height() * frac
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        distances = list(self.distances)
        # DI keeps sampling across normal lap boundaries. Only render the newest
        # monotonic lap-distance epoch so retained samples from lap N are never
        # overlaid on lap N+1 at the same 0..track-length coordinates.
        epoch_start = _current_distance_epoch_start(distances)
        valid_distances = [d for d in distances[epoch_start:] if d is not None]
        distance_axis = self.distance_cursor_m is not None
        if distance_axis:
            d1 = max(0.0, float(self.distance_cursor_m))
            d0 = max(0.0, d1 - self.distance_window_m)
            # During the first 500 m of a lap, both panels deliberately use
            # 0..current-distance. After that they use the same trailing 500 m.
            if d1 <= 0.5:
                distance_axis = False
        else:
            d0 = d1 = None

        def x_for_distance(distance):
            return plot.left() + ((distance - d0) / max(0.001, d1 - d0)) * plot.width()

        def path(values):
            vals = list(values)
            q = QPainterPath()
            if not vals:
                return q
            started = False
            for i, value in enumerate(vals):
                if i < epoch_start:
                    continue
                distance = distances[i] if i < len(distances) else None
                if distance_axis:
                    if distance is None:
                        started = False
                        continue
                    if distance < d0 - 0.5 or distance > d1 + 0.5:
                        started = False
                        continue
                    x = x_for_distance(distance)
                else:
                    x = plot.left() + i * (plot.width() / max(1, len(vals) - 1))
                y = plot.bottom() - value * plot.height()
                if not started:
                    q.moveTo(x, y); started = True
                else:
                    q.lineTo(x, y)
            return q

        if self.show_throttle:
            p.setPen(QPen(GREEN, 2.1))
            p.drawPath(path(self.throttle))
        if self.show_brake:
            p.setPen(QPen(RED, 2.1))
            p.drawPath(path(self.brake))

        # Track-distance axis. Shared track-distance axis. DI and RI are both forced to the same
        # 0..current or trailing-500m window, independent of retained samples.
        if distance_axis:
            axis_y = r.bottom() - 15
            p.setPen(QPen(QColor(255, 255, 255, 45), 1))
            p.drawLine(QPointF(plot.left(), axis_y), QPointF(plot.right(), axis_y))
            p.setFont(_overlay_font(self, 7))
            p.setPen(MUTED)
            first_tick=int(math.ceil(d0/100.0)*100); ticks=list(range(first_tick,int(math.floor(d1/100.0)*100)+1,100))
            for d in ticks:
                x=x_for_distance(float(d)); p.drawLine(QPointF(x,axis_y-2),QPointF(x,axis_y+2))
                width=52; left=max(r.left()+3,min(x-width/2,r.right()-width-3)); p.drawText(QRectF(left,axis_y+1,width,12),Qt.AlignCenter,f"{d:.0f} m")


class ERSBatteryTraceWidget(QWidget):
    """Recent ERS charge and discharge traces using EA per-lap energy counters."""

    def __init__(self, parent=None, *, samples=180):
        super().__init__(parent)
        self.setMinimumHeight(108)
        self.store_values = deque(maxlen=samples)
        self.charge_values = deque(maxlen=samples)
        self.discharge_values = deque(maxlen=samples)
        self.distances = deque(maxlen=samples)
        self._lap = None
        self._sample_time = None
        self.distance_cursor_m = None
        self.distance_window_m = 500.0

    def set_distance_cursor(self, distance_m, *, window_m=500.0):
        try:
            self.distance_cursor_m = float(distance_m) if distance_m is not None else None
        except (TypeError, ValueError):
            self.distance_cursor_m = None
        self.distance_window_m = max(50.0, float(window_m))
        self.update()

    def add_sample(self, store_j, harvested_j=None, deployed_j=None, lap_number=None, sample_time_s=None, distance_m=None):
        time_rewound = (
            sample_time_s is not None and self._sample_time is not None
            and float(sample_time_s) + 0.001 < float(self._sample_time)
        )
        if (lap_number is not None and lap_number != self._lap) or time_rewound:
            self.store_values.clear()
            self.charge_values.clear()
            self.discharge_values.clear()
            self.distances.clear()
        if lap_number is not None:
            self._lap = lap_number
        if sample_time_s is not None:
            self._sample_time = float(sample_time_s)

        # Every channel gets exactly one slot for every distance sample.  Missing
        # ERS counters are represented by None instead of shortening one deque;
        # otherwise a charge/discharge value can be drawn against the wrong
        # physical distance after packet-family gaps.
        def mj(value, *, positive=False):
            try:
                if value is None:
                    return None
                x=float(value)/1_000_000.0
                return max(0.0,x) if positive else x
            except (TypeError, ValueError):
                return None

        self.store_values.append(mj(store_j))
        self.charge_values.append(mj(harvested_j, positive=True))
        self.discharge_values.append(mj(deployed_j, positive=True))
        try:
            self.distances.append(float(distance_m) if distance_m is not None else None)
        except (TypeError, ValueError):
            self.distances.append(None)
        self.update()

    def clear(self) -> None:
        self.store_values.clear(); self.charge_values.clear(); self.discharge_values.clear(); self.distances.clear()
        self._lap = None; self._sample_time = None; self.update()

    @staticmethod
    def _opposed_path(values, plot, maximum, *, upper: bool):
        """Map positive ERS energy onto opposite sides of a zero center line."""
        vals = list(values)
        q = QPainterPath()
        if not vals:
            return q
        step = plot.width() / max(1, len(vals) - 1)
        center_y = plot.center().y()
        half_height = max(1.0, plot.height() / 2.0 - 2.0)

        def y(value):
            ratio = min(1.0, max(0.0, value) / maximum)
            offset = ratio * half_height
            return center_y - offset if upper else center_y + offset

        q.moveTo(plot.left(), y(vals[0]))
        for i, value in enumerate(vals[1:], 1):
            q.lineTo(plot.left() + i * step, y(value))
        return q

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(255,255,255,18),1))
        p.setBrush(QColor(8,10,13,94))
        p.drawRoundedRect(r,8,8)

        stores = list(self.store_values)
        charges = list(self.charge_values)
        discharges = list(self.discharge_values)
        known_stores = [v for v in stores if v is not None]
        current = known_stores[-1] if known_stores else None
        store_delta = (known_stores[-1] - known_stores[-2]) if len(known_stores) >= 2 else 0.0

        p.setFont(_overlay_font(self, 9, QFont.DemiBold))
        p.setPen(MUTED)
        p.drawText(QRectF(r.left()+10,r.top()+4,90,16), Qt.AlignLeft, "ERS ENERGY")
        p.setPen(GREEN)
        p.drawText(QRectF(r.left()+100,r.top()+4,70,16), Qt.AlignLeft, "CHARGE")
        p.setPen(RED)
        p.drawText(QRectF(r.left()+165,r.top()+4,90,16), Qt.AlignLeft, "DISCHARGE")
        if current is not None:
            state = "CHARGING" if store_delta > 0.001 else "DISCHARGING" if store_delta < -0.001 else "STEADY"
            color = GREEN if store_delta > 0.001 else RED if store_delta < -0.001 else CYAN
            p.setPen(color)
            p.drawText(QRectF(r.right()-150,r.top()+4,140,16), Qt.AlignRight, f"{current:.2f} MJ  {state}")

        plot = r.adjusted(10,24,-10,-22)
        center_y = plot.center().y()
        p.setPen(QPen(QColor(255,255,255,45),1))
        p.drawLine(QPointF(plot.left(), center_y), QPointF(plot.right(), center_y))
        p.setPen(QPen(GRID,1))
        upper_grid = plot.top() + plot.height() * 0.25
        lower_grid = plot.top() + plot.height() * 0.75
        p.drawLine(QPointF(plot.left(), upper_grid), QPointF(plot.right(), upper_grid))
        p.drawLine(QPointF(plot.left(), lower_grid), QPointF(plot.right(), lower_grid))

        ds_all = list(self.distances)
        epoch_start = _current_distance_epoch_start(ds_all)
        distance_axis = self.distance_cursor_m is not None and float(self.distance_cursor_m) > 0.5
        if distance_axis:
            d1 = max(0.0, float(self.distance_cursor_m)); d0 = max(0.0, d1 - self.distance_window_m)
        else:
            d0 = d1 = None

        def distance_path(vals, y_func):
            q = QPainterPath(); started = False
            ds = ds_all
            for i, value in enumerate(vals):
                if i < epoch_start:
                    continue
                if value is None:
                    started = False
                    continue
                distance = ds[i] if i < len(ds) else None
                if distance_axis:
                    if distance is None:
                        started = False
                        continue
                    if distance < d0 - 0.5 or distance > d1 + 0.5:
                        started = False
                        continue
                    x = plot.left() + ((distance - d0) / max(0.001, d1 - d0)) * plot.width()
                else:
                    x = plot.left() + i * (plot.width() / max(1, len(vals) - 1))
                y = y_func(value)
                if not started:
                    q.moveTo(x, y); started = True
                else:
                    q.lineTo(x, y)
            return q

        if len(known_stores) >= 2:
            maximum_store = max(4.0, max(known_stores))
            def sy(value):
                ratio = min(1.0, max(0.0, value) / maximum_store)
                return plot.bottom() - ratio * plot.height()
            p.setPen(QPen(CYAN,1.6))
            p.drawPath(distance_path(stores, sy))

        known_charges = [v for v in charges if v is not None]
        known_discharges = [v for v in discharges if v is not None]
        if len(known_charges) < 2 and len(known_discharges) < 2 and len(known_stores) < 2:
            p.setFont(_overlay_font(self, 9))
            p.setPen(MUTED)
            p.drawText(plot, Qt.AlignCenter, "Waiting for ERS telemetry...")
            return

        maximum = max([0.05] + known_charges + known_discharges) * 1.08
        if len(known_charges) >= 2:
            p.setPen(QPen(GREEN,2.1))
            center=plot.center().y(); half=max(1.0,plot.height()/2.0-2.0)
            p.drawPath(distance_path(charges, lambda v: center-min(1.0,max(0.0,v)/maximum)*half))
        if len(known_discharges) >= 2:
            p.setPen(QPen(RED,2.1))
            center=plot.center().y(); half=max(1.0,plot.height()/2.0-2.0)
            p.drawPath(distance_path(discharges, lambda v: center+min(1.0,max(0.0,v)/maximum)*half))

        if distance_axis:
            axis_y = r.bottom() - 13
            p.setPen(QPen(QColor(255,255,255,45),1))
            p.drawLine(QPointF(plot.left(), axis_y), QPointF(plot.right(), axis_y))
            p.setFont(_overlay_font(self, 7)); p.setPen(MUTED)
            first_tick=int(math.ceil(d0/100.0)*100); ticks=list(range(first_tick,int(math.floor(d1/100.0)*100)+1,100))
            for d in ticks:
                x=plot.left()+((float(d)-d0)/max(.001,d1-d0))*plot.width(); p.drawLine(QPointF(x,axis_y-2),QPointF(x,axis_y+2))
                width=52; left=max(r.left()+3,min(x-width/2,r.right()-width-3)); p.drawText(QRectF(left,axis_y+1,width,11),Qt.AlignCenter,f"{d:.0f} m")


class DeltaTraceWidget(QWidget):
    """Rolling 15-second live time-delta trace against the valid reference lap."""

    WINDOW_SECONDS = 15.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(105)
        self.points = deque(maxlen=900)
        self._lap = None
        self.reference_lap = None

    def set_reference_lap(self, lap_number):
        self.reference_lap = lap_number
        self.update()

    def add_sample(self, lap_number, sample_time_s, delta_s):
        if lap_number != self._lap:
            self._lap = lap_number
            self.points.clear()
        if sample_time_s is None or delta_s is None:
            self.update()
            return
        t = float(sample_time_s)
        d = float(delta_s)
        if self.points and t < self.points[-1][0]:
            self.points.clear()
        # Keep UI density stable around 30 Hz without changing the measured value.
        if not self.points or t - self.points[-1][0] >= 0.05:
            self.points.append((t, d))
        cutoff = t - self.WINDOW_SECONDS
        while self.points and self.points[0][0] < cutoff:
            self.points.popleft()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.setBrush(QColor(8, 10, 13, 92))
        p.drawRoundedRect(r, 8, 8)
        title = "LIVE DELTA • LAST 15 S" + (f" • REF L{self.reference_lap}" if self.reference_lap is not None else "")
        p.setFont(_overlay_font(self, 7, QFont.Bold))
        p.setPen(MUTED)
        p.drawText(QRectF(r.left() + 10, r.top() + 4, r.width() - 20, 14), Qt.AlignLeft, title)
        p.setPen(GREEN)
        p.drawText(QRectF(r.right() - 132, r.top() + 4, 58, 14), Qt.AlignRight, "GAIN (-)")
        p.setPen(RED)
        p.drawText(QRectF(r.right() - 70, r.top() + 4, 60, 14), Qt.AlignRight, "LOSS (+)")

        plot = r.adjusted(10, 22, -10, -9)
        zero_y = plot.center().y()
        p.setPen(QPen(QColor(225, 228, 232, 120), 1, Qt.DashLine))
        p.drawLine(QPointF(plot.left(), zero_y), QPointF(plot.right(), zero_y))
        pts = list(self.points)
        if len(pts) < 2:
            p.setFont(_overlay_font(self, 8))
            p.setPen(MUTED)
            p.drawText(plot, Qt.AlignCenter, "Building 15-second live delta...")
            return

        # Smooth only the displayed line. Numeric delta/coaching calculations remain raw.
        smooth = []
        values = [v for _, v in pts]
        for i, (t, _v) in enumerate(pts):
            lo_i = max(0, i - 2)
            hi_i = min(len(values), i + 3)
            smooth.append((t, sum(values[lo_i:hi_i]) / (hi_i - lo_i)))
        hi = smooth[-1][0]
        lo = max(smooth[0][0], hi - self.WINDOW_SECONDS)
        max_abs = max(0.25, max(abs(v) for _, v in smooth) * 1.15)

        def xy(t, v):
            x = plot.left() + max(0.0, min(1.0, (t - lo) / self.WINDOW_SECONDS)) * plot.width()
            y = zero_y + (v / max_abs) * (plot.height() / 2.0)
            return QPointF(x, y)

        visible = [(t, v) for t, v in smooth if t >= lo]
        for (t0, v0), (t1, v1) in zip(visible, visible[1:]):
            color = GREEN if (v0 + v1) / 2.0 <= 0 else RED
            p.setPen(QPen(color, 2.3))
            p.drawLine(xy(t0, v0), xy(t1, v1))


class MetricBarWidget(QWidget):
    """One compact coaching row, styled after the reference overlay."""

    STATUS_TEXT = {
        "LATER": "LATE",
        "EARLIER": "EARLY",
        "SLOWER": "SLOW",
        "FASTER": "FAST",
        "MATCH": "MATCH",
        "WAIT": "WAIT",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(29)
        self.label = "--"
        self.value = "--"
        self.status = "WAIT"
        self.magnitude = None

    def set_metric(self, metric):
        self.label = metric.label
        self.value = metric.value
        self.status = metric.status
        self.magnitude = metric.magnitude
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 0, -1, -1)
        p.setFont(_overlay_font(self, 9, QFont.DemiBold))
        p.setPen(WHITE)
        p.drawText(QRectF(r.left(), r.top(), 118, 18), Qt.AlignLeft | Qt.AlignVCenter, self.label)

        status = self.status.upper()
        if status in ("MATCH", "FASTER"):
            color = GREEN
        elif status == "SLOWER":
            color = RED
        elif status in ("EARLIER", "LATER"):
            color = AMBER
        elif status == "WAIT":
            color = MUTED
        else:
            color = AMBER

        short_status = self.STATUS_TEXT.get(status, status)
        pill = QRectF(r.right() - 58, r.top(), 58, 18)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 45))
        p.drawRoundedRect(pill, 9, 9)
        p.setPen(color)
        p.setFont(_overlay_font(self, 7, QFont.Bold))
        p.drawText(pill, Qt.AlignCenter, short_status)

        p.setFont(_overlay_font(self, 8, QFont.DemiBold))
        p.setPen(color)
        p.drawText(QRectF(r.right() - 172, r.top(), 106, 18), Qt.AlignRight | Qt.AlignVCenter, self.value)

        base = QRectF(r.left(), r.bottom() - 4, r.width(), 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawRoundedRect(base, 1, 1)
        if self.magnitude is not None:
            scale = 25.0 if "kph" in self.value else 40.0
            frac = min(1.0, max(0.06, float(self.magnitude) / scale))
            fill = QRectF(base.left(), base.top(), base.width() * frac, base.height())
            p.setBrush(color)
            p.drawRoundedRect(fill, 1, 1)


class DeltaProgressWidget(QWidget):
    """Reference-style centred delta bar with a moving signed marker."""

    def __init__(self, parent=None, *, range_s=1.0):
        super().__init__(parent)
        self.setMinimumHeight(22)
        self.setMinimumWidth(260)
        self.delta_s = None
        self.range_s = max(0.1, float(range_s))

    def set_delta(self, delta_s):
        try:
            self.delta_s = float(delta_s) if delta_s is not None else None
        except (TypeError, ValueError):
            self.delta_s = None
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 4, -1, -4)
        y = r.center().y()
        track = QRectF(r.left(), y - 3, r.width(), 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 28))
        p.drawRoundedRect(track, 3, 3)
        centre = track.center().x()
        p.setBrush(QColor(220, 225, 230, 85))
        p.drawRect(QRectF(centre - 1, track.top() - 2, 2, track.height() + 4))
        if self.delta_s is None:
            return
        frac = max(-1.0, min(1.0, self.delta_s / self.range_s))
        # Negative delta is gain -> marker moves left and is green.
        marker_x = centre + frac * (track.width() / 2.0)
        color = GREEN if self.delta_s <= 0 else RED
        x0, x1 = sorted((centre, marker_x))
        if abs(x1 - x0) > 1:
            p.setBrush(QColor(color.red(), color.green(), color.blue(), 115))
            p.drawRoundedRect(QRectF(x0, track.top(), x1 - x0, track.height()), 3, 3)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(marker_x - 3, track.top() - 4, 6, track.height() + 8), 3, 3)


class LapMicroDeltaWidget(QWidget):
    """Neutral sector labels plus local gain/loss markers for straights and turns.

    Marker count follows the detected track structure from the valid reference lap,
    not fixed-distance slicing.  Turn markers are slightly larger than straight
    markers, and a small extra gap is inserted at sector boundaries.
    """

    DOT_NEUTRAL_THRESHOLD_S = 0.008

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(48)
        self.dots = ()
        self.kinds = ()
        self.sectors = ()
        self.sector_deltas = (None, None, None)

    def set_data(self, dots, kinds=(), sectors=(), sector1_delta=None, sector2_delta=None, sector3_delta=None):
        self.dots = tuple(dots or ())
        self.kinds = tuple(kinds or ())
        self.sectors = tuple(sectors or ())
        self.sector_deltas = (sector1_delta, sector2_delta, sector3_delta)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 1, -2, -1)

        # Sector labels remain neutral.  Only the thin bars carry the measured
        # completed-sector result, matching the user's visual reference.
        bar_y = r.top() + 1
        gap = 5.0
        sector_w = (r.width() - gap * 2) / 3.0
        for i, value in enumerate(self.sector_deltas):
            x = r.left() + i * (sector_w + gap)
            base = QRectF(x, bar_y, sector_w, 5)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 30))
            p.drawRoundedRect(base, 2.5, 2.5)
            if value is not None:
                color = GREEN if value <= 0 else RED
                p.setBrush(color)
                p.drawRoundedRect(base, 2.5, 2.5)

        p.setFont(_overlay_font(self, 8, QFont.DemiBold))
        p.setPen(MUTED)
        label_y = bar_y + 7
        for i, name in enumerate(("S1", "S2", "S3")):
            x = r.left() + i * (sector_w + gap)
            p.drawText(QRectF(x, label_y, sector_w, 13), Qt.AlignCenter, name)

        dots = self.dots
        if not dots:
            return
        dot_y = r.bottom() - 8
        count = len(dots)
        # Give sector transitions a little breathing room while keeping all markers
        # in one compact row.  Each marker is one straight or one coached turn.
        transition_count = sum(
            1 for a, b in zip(self.sectors, self.sectors[1:])
            if a and b and a != b
        )
        extra_gap = 5.0
        available = max(1.0, r.width() - transition_count * extra_gap)
        step = available / max(1, count)
        x = r.left() + step * 0.5
        for i, value in enumerate(dots):
            if i > 0 and i < len(self.sectors) and self.sectors[i] != self.sectors[i - 1]:
                x += extra_gap
            if value is None:
                color = QColor(255, 255, 255, 34)
            elif value < -self.DOT_NEUTRAL_THRESHOLD_S:
                color = GREEN
            elif value > self.DOT_NEUTRAL_THRESHOLD_S:
                color = RED
            else:
                color = QColor(185, 191, 198, 95)
            kind = self.kinds[i] if i < len(self.kinds) else "straight"
            radius = 3.5 if kind == "turn" else 2.6
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawEllipse(QPointF(x, dot_y), radius, radius)
            x += step

