from __future__ import annotations

import math
from dataclasses import replace

from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QFrame, QLabel, QComboBox, QLineEdit, QCheckBox, QPushButton,
)

from .pedal_sensor import (
    PedalSensorConfig, MODE_ANALOG, MODE_HX711,
    CMD_GET_STATUS, CMD_SET_THROTTLE_CONFIG, CMD_SET_BRAKE_CONFIG,
    CMD_SET_CLUTCH_CONFIG, CMD_TARE_THROTTLE, CMD_TARE_BRAKE,
    CMD_TARE_CLUTCH, CMD_CALIBRATE_THROTTLE, CMD_CALIBRATE_BRAKE,
    CMD_CALIBRATE_CLUTCH, CMD_RESET_DEFAULTS,
)
from .handbrake_sensor import (
    HandbrakeSensorConfig, MODE_HALL, MODE_HX711 as HB_MODE_HX711,
    CMD_GET_STATUS as HB_GET_STATUS, CMD_SET_CONFIG as HB_SET_CONFIG,
    CMD_TARE as HB_TARE, CMD_CALIBRATE as HB_CALIBRATE,
    CMD_RESET_DEFAULTS as HB_RESET_DEFAULTS,
)
from .pedal_curves import AxisCurve, PedalCurveSettings
from .settings import save_settings


class SensorConfigurationWidget(QWidget):
    """Device sensor setup plus receiver-side per-axis enable/disable controls."""

    AXES = ("throttle", "brake", "clutch", "handbrake")

    def __init__(self, runtime, settings: dict, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.settings = settings
        self._pedal_stamp = None
        self._handbrake_stamp = None
        self._curve_stamp = None
        self._curve_cache: dict[str, AxisCurve] = {}
        self._enable_sync_done = False
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)
        heading = QLabel("DEVICE SENSOR CONFIGURATION")
        heading.setObjectName("sectionTitle")
        root.addWidget(heading)
        note = QLabel(
            "Sensor configuration is stored on the ESP32 devices. Enable/Disable is separate: "
            "when an axis is disabled its Receiver HID output is forced to 0; the physical sensor "
            "still remains available for calibration and readback."
        )
        note.setWordWrap(True)
        note.setObjectName("subtitle")
        root.addWidget(note)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_pedals()
        self._build_handbrake()

    def _field(self, value, *, integer=False, minimum=0.01, maximum=100000000.0, width=120):
        edit = QLineEdit(str(value))
        if integer:
            edit.setValidator(QIntValidator(int(minimum), int(maximum), edit))
        else:
            edit.setValidator(QDoubleValidator(float(minimum), float(maximum), 4, edit))
        edit.setFixedWidth(width)
        return edit

    def _action_row(self, layout, buttons):
        row = QHBoxLayout()
        for button in buttons:
            row.addWidget(button)
        row.addStretch(1)
        layout.addRow(row)

    def _enable_button(self, axis: str) -> QPushButton:
        enabled = bool(self.settings.get(f"{axis}_enabled", axis not in ("clutch", "handbrake")))
        b = QPushButton()
        b.setCheckable(True)
        b.setChecked(enabled)
        b.setMinimumWidth(120)
        self._update_enable_button(b, axis, enabled)
        b.toggled.connect(lambda checked, a=axis, button=b: self._axis_enable_toggled(a, checked, button))
        return b

    @staticmethod
    def _update_enable_button(button: QPushButton, axis: str, enabled: bool):
        button.setText(f"{axis.upper()}: {'ENABLED' if enabled else 'DISABLED'}")
        button.setObjectName("primary" if enabled else "")
        button.style().unpolish(button)
        button.style().polish(button)

    def _axis_enable_toggled(self, axis: str, checked: bool, button: QPushButton) -> None:
        """Save the axis enable flag through Receiver PC/PS; never fake it in the UI."""
        receiver = getattr(self.runtime, "receiver", None)
        if receiver is None:
            button.blockSignals(True)
            button.setChecked(not checked)
            button.blockSignals(False)
            self._update_enable_button(button, axis, not checked)
            self.pedal_status.setText("Receiver is not available")
            return

        try:
            current, supported, _stamp, version = receiver.pedal_settings_snapshot()
            required = 4 if axis in ("throttle", "brake") else (3 if axis == "handbrake" else 2)
            if not supported or version < required:
                raise RuntimeError(
                    f"{axis.title()} enable/disable requires Receiver PC/PS V{required}; "
                    f"detected V{version if supported else 'unsupported'}"
                )
            updated = replace(current, **{f"{axis}_enabled": bool(checked)})
            receiver.apply_pedal_settings(updated, save=True)
            receiver.request_pedal_settings(version=required)
            self.settings[f"{axis}_enabled"] = bool(checked)
            save_settings(self.settings)
            self._update_enable_button(button, axis, checked)
            self.pedal_status.setText(
                f"{axis.upper()} {'ENABLED' if checked else 'DISABLED'} · saving and verifying Receiver V{required}"
            )
        except Exception as exc:
            button.blockSignals(True)
            button.setChecked(not checked)
            button.blockSignals(False)
            self._update_enable_button(button, axis, not checked)
            self.pedal_status.setText(f"Could not change {axis} output: {exc}")

    def _build_pedals(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.pedal_fields = {}
        self.pedal_status = QLabel("Waiting for pedal ESP32 readback")
        self.pedal_status.setWordWrap(True)
        self.pedal_status.setObjectName("muted")
        self.pedal_axis_status = {}
        axis_tabs = QTabWidget()
        for axis, capacity, force in (("throttle", 200, 10), ("brake", 200, 40), ("clutch", 200, 10)):
            card = QFrame(); card.setObjectName("card")
            form = QFormLayout(card); form.setContentsMargins(16, 14, 16, 14)
            mode = QComboBox(); mode.addItem("Analog position sensor", MODE_ANALOG); mode.addItem("HX711 load cell", MODE_HX711)
            saved = str(self.settings.get(f"{axis}_sensor_mode", "analog"))
            mode.setCurrentIndex(max(0, mode.findData(MODE_HX711 if saved in ("load_cell", "hx711") else MODE_ANALOG)))
            cap = self._field(self.settings.get(f"{axis}_load_cell_capacity_kg", capacity), minimum=1, maximum=1000)
            max_force = self._field(self.settings.get(f"{axis}_max_force_kg", force), minimum=0.1, maximum=1000)
            counts = self._field(self.settings.get(f"{axis}_counts_per_kg", 25000), minimum=1)
            filt = self._field(self.settings.get(f"{axis}_filter_divisor", 1), integer=True, minimum=1, maximum=255)
            invert = QCheckBox("Reverse sensor polarity"); invert.setChecked(bool(self.settings.get(f"{axis}_invert", False)))
            known = self._field(5.0, minimum=0.1, maximum=1000, width=90)
            enable = self._enable_button(axis)
            self.pedal_fields[axis] = {"mode": mode, "capacity": cap, "force": max_force, "counts": counts, "filter": filt, "invert": invert, "known": known, "enable": enable}
            form.addRow("Axis output", enable)
            form.addRow("Sensor type", mode); form.addRow("Load-cell capacity (kg)", cap); form.addRow("Maximum force for 100% (kg)", max_force)
            form.addRow("Counts per kg", counts); form.addRow("HX711 filter divisor", filt); form.addRow("Polarity", invert); form.addRow("Known calibration force (kg)", known)
            save = QPushButton(f"SAVE {axis.upper()} CONFIG"); tare = QPushButton(f"TARE {axis.upper()}"); calibrate = QPushButton(f"CALIBRATE {axis.upper()}")
            status = QLabel("Not yet read from device"); status.setWordWrap(True); status.setObjectName("muted")
            self.pedal_axis_status[axis] = status
            self._action_row(form, [save, tare, calibrate]); form.addRow(status)
            save.clicked.connect(lambda _=False, a=axis: self._save_pedal_axis(a)); tare.clicked.connect(lambda _=False, a=axis: self._tare_pedal_axis(a)); calibrate.clicked.connect(lambda _=False, a=axis: self._calibrate_pedal_axis(a))
            mode.currentIndexChanged.connect(lambda _=0, a=axis: self._mode_changed(a)); self._mode_changed(axis)
            axis_tabs.addTab(card, axis.title())
        layout.addWidget(axis_tabs, 1)
        actions = QHBoxLayout(); self.pedal_refresh = QPushButton("READ DEVICE"); self.pedal_save_all = QPushButton("SAVE ALL PEDAL CONFIGS"); self.pedal_save_all.setObjectName("primary"); self.pedal_tare_all = QPushButton("TARE ALL HX711"); self.pedal_reset = QPushButton("RESET PEDAL SENSOR DEFAULTS")
        for b in (self.pedal_refresh, self.pedal_save_all, self.pedal_tare_all, self.pedal_reset): actions.addWidget(b)
        actions.addStretch(1); layout.addLayout(actions); layout.addWidget(self.pedal_status)
        self.pedal_refresh.clicked.connect(self._request_pedals); self.pedal_save_all.clicked.connect(self._save_all_pedals); self.pedal_tare_all.clicked.connect(self._tare_all_pedals); self.pedal_reset.clicked.connect(self._reset_pedals)
        self.tabs.addTab(page, "PEDALS")

    def _mode_changed(self, axis):
        f = self.pedal_fields[axis]; load_cell = f["mode"].currentData() == MODE_HX711; form = f["mode"].parentWidget().layout()
        for key in ("capacity", "force", "counts", "filter", "known"):
            widget = f[key]; widget.setVisible(load_cell); label = form.labelForField(widget)
            if label is not None: label.setVisible(load_cell)
        f["invert"].setVisible(True)

    def _pedal_config(self):
        cfg = PedalSensorConfig()
        for axis in ("throttle", "brake", "clutch"):
            f = self.pedal_fields[axis]; mode = int(f["mode"].currentData()); capacity = float(f["capacity"].text()); force = float(f["force"].text()); counts = float(f["counts"].text()); divisor = int(f["filter"].text())
            if not all(math.isfinite(v) for v in (capacity, force, counts)): raise ValueError(f"{axis.title()} values must be finite")
            if mode == MODE_HX711:
                if not 1 <= capacity <= 1000 or not 0.1 <= force <= capacity: raise ValueError(f"{axis.title()} force must be 0.1 kg to cell capacity (1–1000 kg)")
                if not 1 <= counts <= 100000000 or not 1 <= divisor <= 255: raise ValueError(f"{axis.title()} counts/filter are out of range")
            bit = {"throttle": 0, "brake": 1, "clutch": 2}[axis]; flags = cfg.flags | (1 << bit) if f["invert"].isChecked() else cfg.flags & ~(1 << bit)
            cfg = replace(cfg, **{f"{axis}_mode": mode, f"{axis}_capacity_kg": capacity, f"{axis}_max_force_kg": force, f"{axis}_counts_per_kg": counts, f"{axis}_filter_divisor": divisor, "flags": flags})
        return cfg

    def _persist_pedal_config(self, cfg):
        for axis in ("throttle", "brake", "clutch"):
            mode = getattr(cfg, f"{axis}_mode")
            self.settings.update({f"{axis}_sensor_mode": "load_cell" if mode == MODE_HX711 else "analog", f"{axis}_load_cell_capacity_kg": getattr(cfg, f"{axis}_capacity_kg"), f"{axis}_max_force_kg": getattr(cfg, f"{axis}_max_force_kg"), f"{axis}_counts_per_kg": getattr(cfg, f"{axis}_counts_per_kg"), f"{axis}_filter_divisor": getattr(cfg, f"{axis}_filter_divisor"), f"{axis}_invert": bool(cfg.flags & (1 << {"throttle": 0, "brake": 1, "clutch": 2}[axis]))})
        save_settings(self.settings)

    def _send_pedal(self, command, cfg=None, force=0.0):
        receiver = getattr(self.runtime, "receiver", None)
        if receiver is None or not receiver.health_snapshot().serial_connected: self.pedal_status.setText("Connect the Receiver USB first"); return False
        receiver.send_pedal_sensor_command(command, cfg, calibration_force_kg=force); self.pedal_status.setText("Command sent · waiting for pedal ESP32 readback"); return True

    def _save_pedal_axis(self, axis):
        try: cfg = self._pedal_config()
        except (ValueError, TypeError) as exc: self.pedal_axis_status[axis].setText(f"Invalid settings: {exc}"); return
        command = {"throttle": CMD_SET_THROTTLE_CONFIG, "brake": CMD_SET_BRAKE_CONFIG, "clutch": CMD_SET_CLUTCH_CONFIG}[axis]
        if self._send_pedal(command, cfg): self._persist_pedal_config(cfg); self.pedal_axis_status[axis].setText("Configuration sent · verifying device readback")

    def _save_all_pedals(self):
        try: cfg = self._pedal_config()
        except (ValueError, TypeError) as exc: self.pedal_status.setText(f"Invalid settings: {exc}"); return
        commands = (CMD_SET_THROTTLE_CONFIG, CMD_SET_BRAKE_CONFIG, CMD_SET_CLUTCH_CONFIG)
        if self._send_pedal(commands[0], cfg):
            for command in commands[1:]: self.runtime.receiver.send_pedal_sensor_command(command, cfg)
            self._persist_pedal_config(cfg); self.pedal_status.setText("All pedal axis configurations sent · awaiting device confirmation")

    def _tare_pedal_axis(self, axis):
        try: cfg = self._pedal_config()
        except (ValueError, TypeError) as exc: self.pedal_status.setText(str(exc)); return
        if getattr(cfg, f"{axis}_mode") != MODE_HX711: self.pedal_status.setText(f"{axis.title()} tare is available only in HX711 mode"); return
        self._send_pedal({"throttle": CMD_TARE_THROTTLE, "brake": CMD_TARE_BRAKE, "clutch": CMD_TARE_CLUTCH}[axis])

    def _tare_all_pedals(self):
        try: cfg = self._pedal_config()
        except (ValueError, TypeError) as exc: self.pedal_status.setText(str(exc)); return
        commands = {"throttle": CMD_TARE_THROTTLE, "brake": CMD_TARE_BRAKE, "clutch": CMD_TARE_CLUTCH}; selected = [a for a in commands if getattr(cfg, f"{a}_mode") == MODE_HX711]
        if not selected: self.pedal_status.setText("No pedal is configured for HX711"); return
        receiver = self.runtime.receiver
        if not receiver.health_snapshot().serial_connected: self.pedal_status.setText("Connect the Receiver USB first"); return
        for axis in selected: receiver.send_pedal_sensor_command(commands[axis])
        self.pedal_status.setText("Tare sent for: " + ", ".join(a.title() for a in selected))

    def _calibrate_pedal_axis(self, axis):
        try:
            cfg = self._pedal_config(); force = float(self.pedal_fields[axis]["known"].text()); capacity = getattr(cfg, f"{axis}_capacity_kg")
            if not math.isfinite(force) or force < 0.1 or force > capacity: raise ValueError("Known force must be 0.1 kg to cell capacity")
        except (ValueError, TypeError) as exc: self.pedal_status.setText(f"Invalid calibration: {exc}"); return
        if getattr(cfg, f"{axis}_mode") != MODE_HX711: self.pedal_status.setText("Known-force calibration requires HX711 mode"); return
        self._send_pedal({"throttle": CMD_CALIBRATE_THROTTLE, "brake": CMD_CALIBRATE_BRAKE, "clutch": CMD_CALIBRATE_CLUTCH}[axis], cfg, force)

    def _request_pedals(self):
        receiver = getattr(self.runtime, "receiver", None)
        if receiver and receiver.health_snapshot().serial_connected: receiver.request_pedal_sensor_status(); self.pedal_status.setText("Requesting pedal ESP32 status…")
        else: self.pedal_status.setText("Connect the Receiver USB first")

    def _reset_pedals(self):
        self._send_pedal(CMD_RESET_DEFAULTS); self.pedal_status.setText("Reset requested · waiting for device defaults readback")

    def _apply_pedal_readback(self, status):
        cfg = status.config
        for axis in ("throttle", "brake", "clutch"):
            f = self.pedal_fields[axis]; mode = getattr(cfg, f"{axis}_mode"); f["mode"].setCurrentIndex(max(0, f["mode"].findData(mode))); f["capacity"].setText(str(getattr(cfg, f"{axis}_capacity_kg"))); f["force"].setText(str(getattr(cfg, f"{axis}_max_force_kg"))); f["counts"].setText(str(getattr(cfg, f"{axis}_counts_per_kg"))); f["filter"].setText(str(getattr(cfg, f"{axis}_filter_divisor"))); f["invert"].setChecked(bool(cfg.flags & (1 << {"throttle": 0, "brake": 1, "clutch": 2}[axis]))); self._mode_changed(axis); self.pedal_axis_status[axis].setText(f"Device confirmed · raw delta {getattr(status, axis + '_raw_delta')} · output {getattr(status, axis + '_output')} · {status.result_text}")
        self.pedal_status.setText(f"Pedal ESP32 readback · sequence {status.sequence} · {status.result_text}")
        self._persist_pedal_config(cfg)

    def _build_handbrake(self):
        page = QWidget(); layout = QVBoxLayout(page)
        self.hb_fields = {}; form = QFormLayout(); self.hb_form = form
        self.hb_fields["mode"] = QComboBox(); self.hb_fields["mode"].addItem("Hall position sensor", MODE_HALL); self.hb_fields["mode"].addItem("HX711 load cell", HB_MODE_HX711)
        self.hb_fields["capacity"] = self._field(self.settings.get("handbrake_load_cell_capacity_kg", 40), minimum=1, maximum=1000); self.hb_fields["force"] = self._field(self.settings.get("handbrake_max_force_kg", 40), minimum=0.1, maximum=1000); self.hb_fields["counts"] = self._field(self.settings.get("handbrake_counts_per_kg", 25000), minimum=1); self.hb_fields["filter"] = self._field(self.settings.get("handbrake_filter_divisor", 4), integer=True, minimum=1, maximum=32)
        self.hb_fields["invert"] = QCheckBox("Reverse sensor polarity"); self.hb_fields["invert"].setChecked(bool(self.settings.get("handbrake_invert", False))); self.hb_fields["known"] = self._field(5.0, minimum=0.1, maximum=1000, width=90); self.hb_fields["enable"] = self._enable_button("handbrake")
        form.addRow("Axis output", self.hb_fields["enable"]); form.addRow("Sensor type", self.hb_fields["mode"]); form.addRow("Load-cell capacity (kg)", self.hb_fields["capacity"]); form.addRow("Maximum force for 100% (kg)", self.hb_fields["force"]); form.addRow("Counts per kg", self.hb_fields["counts"]); form.addRow("HX711 filter divisor", self.hb_fields["filter"]); form.addRow("Polarity", self.hb_fields["invert"]); form.addRow("Known calibration force (kg)", self.hb_fields["known"])
        layout.addLayout(form)
        actions = QHBoxLayout(); self.hb_read = QPushButton("READ C3"); self.hb_save = QPushButton("SAVE TO C3"); self.hb_save.setObjectName("primary"); self.hb_tare = QPushButton("TARE"); self.hb_calibrate = QPushButton("CALIBRATE"); self.hb_reset = QPushButton("RESET DEFAULTS")
        for b in (self.hb_read, self.hb_save, self.hb_tare, self.hb_calibrate, self.hb_reset): actions.addWidget(b)
        actions.addStretch(1); layout.addLayout(actions); self.hb_status = QLabel("Waiting for handbrake C3 readback"); self.hb_status.setWordWrap(True); self.hb_status.setObjectName("muted"); layout.addWidget(self.hb_status)
        self.hb_fields["mode"].currentIndexChanged.connect(self._handbrake_mode_changed); self.hb_read.clicked.connect(self._request_handbrake); self.hb_save.clicked.connect(self._save_handbrake); self.hb_tare.clicked.connect(self._tare_handbrake); self.hb_calibrate.clicked.connect(self._calibrate_handbrake); self.hb_reset.clicked.connect(self._reset_handbrake); self._handbrake_mode_changed(); layout.addStretch(1); self.tabs.addTab(page, "HANDBRAKE")

    def _handbrake_mode_changed(self, *_):
        load_cell = self.hb_fields["mode"].currentData() == HB_MODE_HX711; form = self.hb_form
        for key in ("capacity", "force", "counts", "filter", "known"):
            widget = self.hb_fields[key]; widget.setVisible(load_cell); label = form.labelForField(widget)
            if label is not None: label.setVisible(load_cell)

    def _handbrake_config(self):
        f = self.hb_fields; cfg = HandbrakeSensorConfig(mode=int(f["mode"].currentData()), filter_divisor=int(f["filter"].text()), invert=f["invert"].isChecked(), capacity_kg=float(f["capacity"].text()), max_force_kg=float(f["force"].text()), counts_per_kg=float(f["counts"].text()))
        vals = (cfg.capacity_kg, cfg.max_force_kg, cfg.counts_per_kg)
        if cfg.mode == HB_MODE_HX711 and (not all(math.isfinite(v) for v in vals) or not 1 <= cfg.capacity_kg <= 1000 or not 0.1 <= cfg.max_force_kg <= cfg.capacity_kg or cfg.counts_per_kg < 1 or not 1 <= cfg.filter_divisor <= 32): raise ValueError("Check capacity, maximum force, counts/kg and filter values")
        return cfg

    def _send_handbrake(self, command, cfg=None, force=0.0):
        receiver = getattr(self.runtime, "receiver", None)
        if receiver is None or not receiver.health_snapshot().serial_connected: self.hb_status.setText("Connect the Receiver USB first"); return False
        receiver.send_handbrake_sensor_command(command, cfg, calibration_force_kg=force); self.hb_status.setText("Command sent · waiting for handbrake C3 readback"); return True

    def _request_handbrake(self):
        receiver = getattr(self.runtime, "receiver", None)
        if receiver and receiver.health_snapshot().serial_connected: receiver.request_handbrake_sensor_status(); self.hb_status.setText("Requesting handbrake C3 status…")
        else: self.hb_status.setText("Connect the Receiver USB first")

    def _save_handbrake(self):
        try: cfg = self._handbrake_config()
        except (ValueError, TypeError) as exc: self.hb_status.setText(f"Invalid settings: {exc}"); return
        if self._send_handbrake(HB_SET_CONFIG, cfg):
            self.settings.update({"handbrake_sensor_mode": "load_cell" if cfg.mode == HB_MODE_HX711 else "hall", "handbrake_load_cell_capacity_kg": cfg.capacity_kg, "handbrake_max_force_kg": cfg.max_force_kg, "handbrake_counts_per_kg": cfg.counts_per_kg, "handbrake_filter_divisor": cfg.filter_divisor, "handbrake_invert": cfg.invert}); save_settings(self.settings)

    def _tare_handbrake(self):
        try: cfg = self._handbrake_config()
        except (ValueError, TypeError) as exc: self.hb_status.setText(str(exc)); return
        if cfg.mode != HB_MODE_HX711: self.hb_status.setText("Tare is available only in HX711 mode"); return
        self._send_handbrake(HB_TARE)

    def _calibrate_handbrake(self):
        try:
            cfg = self._handbrake_config(); force = float(self.hb_fields["known"].text())
            if not math.isfinite(force) or not 0.1 <= force <= cfg.capacity_kg: raise ValueError("Known force must be 0.1 kg to cell capacity")
        except (ValueError, TypeError) as exc: self.hb_status.setText(f"Invalid calibration: {exc}"); return
        if cfg.mode != HB_MODE_HX711: self.hb_status.setText("Calibration requires HX711 mode"); return
        self._send_handbrake(HB_CALIBRATE, cfg, force)

    def _reset_handbrake(self):
        self._send_handbrake(HB_RESET_DEFAULTS); self.hb_status.setText("Reset requested · waiting for C3 defaults readback")

    def _apply_handbrake_readback(self, status):
        cfg = status.config; f = self.hb_fields
        f["mode"].setCurrentIndex(max(0, f["mode"].findData(cfg.mode))); f["capacity"].setText(str(cfg.capacity_kg)); f["force"].setText(str(cfg.max_force_kg)); f["counts"].setText(str(cfg.counts_per_kg)); f["filter"].setText(str(cfg.filter_divisor)); f["invert"].setChecked(cfg.invert); self._handbrake_mode_changed()
        self.settings.update({"handbrake_sensor_mode": "load_cell" if cfg.mode == HB_MODE_HX711 else "hall", "handbrake_load_cell_capacity_kg": cfg.capacity_kg, "handbrake_max_force_kg": cfg.max_force_kg, "handbrake_counts_per_kg": cfg.counts_per_kg, "handbrake_filter_divisor": cfg.filter_divisor, "handbrake_invert": cfg.invert}); save_settings(self.settings)
        self.hb_status.setText(f"Handbrake C3 readback · {'HX711' if cfg.mode == HB_MODE_HX711 else 'Hall'} · {cfg.capacity_kg:g} kg cell · {cfg.max_force_kg:g} kg full scale · {cfg.counts_per_kg:g} counts/kg · filter {cfg.filter_divisor} · {'inverted' if cfg.invert else 'normal'} · raw {status.raw_delta} · output {status.output} · {status.result_text}")

    def poll(self):
        receiver = getattr(self.runtime, "receiver", None)
        if receiver is None: return
        pedal_status, pedal_stamp = receiver.pedal_sensor_snapshot()
        if pedal_status is not None and pedal_stamp != self._pedal_stamp:
            self._pedal_stamp = pedal_stamp; self._apply_pedal_readback(pedal_status)
        hb_status, hb_stamp = receiver.handbrake_sensor_snapshot()
        if hb_status is not None and hb_stamp != self._handbrake_stamp:
            self._handbrake_stamp = hb_stamp; self._apply_handbrake_readback(hb_status)
