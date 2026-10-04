"""Qt runtime for the V0.9.9.4 multi-panel overlay."""
from __future__ import annotations

import threading


def run_overlay(receiver, *, replay_file=None, replay_speed=1.0, replay_fast=False, click_through=False, web_dash=True, dash_host="0.0.0.0", dash_port=8765) -> int:
    try:
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtWidgets import (
            QApplication, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QComboBox, QPushButton, QLineEdit, QFileDialog, QFormLayout, QFrame
        )
    except ImportError as exc:
        raise RuntimeError("The overlay requires PySide6. Run: pip install -r requirements.txt") from exc

    from .data import OverlayDataProvider
    from .window import OverlaySuite
    from ..telemetry_recording import ReplayController
    from ..dashboard_server import DashboardStateStore, RemoteDashboardServer

    app = QApplication.instance() or QApplication([])
    from ..branding import configure_qt_application
    configure_qt_application(app)

    from ..performance_history import PerformanceHistoryStore
    from ..driver_profiles import DriverProfileStore, SUPPORTED_GAMES
    from ..user_time import COMMON_TIME_ZONES, DEFAULT_TIME_ZONE

    def ensure_driver_profile() -> bool:
        """Load the last person-level profile, or run setup once on first use."""
        profiles = DriverProfileStore()
        history = PerformanceHistoryStore()
        active = profiles.active_profile()

        if active is not None:
            driver_id = str(active.get("driver_id") or "")
            profiles.set_active_driver(driver_id)
            compat = active.get("compatibility") if isinstance(active.get("compatibility"), dict) else {}
            legacy_id = compat.get("performance_history_profile_id")
            if legacy_id is not None and history.set_active_user_profile(legacy_id):
                try:
                    from ..f1_profile_migration import attach_existing_f1_history
                    attach_existing_f1_history(profiles, history, driver_id)
                except Exception as error:
                    print(f"[PROFILE] F1 history link verification skipped: {error}", flush=True)
                return True
            # Compatibility repair for a missing/brand-new Performance Hub DB.
            legacy_id = history.create_user_profile(str(active.get("display_name") or "Driver"))
            history.set_active_user_profile(legacy_id)
            profiles.set_compatibility_value(driver_id, "performance_history_profile_id", int(legacy_id))
            try:
                from ..f1_profile_migration import attach_existing_f1_history
                attach_existing_f1_history(profiles, history, driver_id)
            except Exception as error:
                print(f"[PROFILE] F1 history link verification skipped: {error}", flush=True)
            return True

        from ..ui_theme import TOKENS, qt_app_stylesheet, button_class_qss

        dlg = QDialog()
        dlg.setObjectName("driverProfileSetup")
        dlg.setWindowTitle("Race Engineer — Create Driver Profile")
        dlg.setMinimumSize(620, 430)
        dlg.resize(660, 455)
        dlg.setStyleSheet(
            qt_app_stylesheet()
            + f"""
            QDialog#driverProfileSetup {{ background:{TOKENS.bg}; }}
            QFrame#profileSetupCard {{
                background:{TOKENS.surface};
                border:1px solid {TOKENS.border};
                border-radius:12px;
            }}
            QLabel#profileEyebrow {{
                color:{TOKENS.cyan};
                font-size:10px;
                font-weight:800;
                letter-spacing:1px;
            }}
            QLabel#profileTitle {{
                color:{TOKENS.text};
                font-size:22px;
                font-weight:800;
            }}
            QLabel#profileIntro {{ color:{TOKENS.text_muted}; font-size:12px; }}
            QLabel#profileFieldLabel {{ color:{TOKENS.text_muted}; font-weight:600; }}
            QLabel#profileAvatarState {{ color:{TOKENS.text_muted}; }}
            QLineEdit {{
                color:{TOKENS.text};
                background:{TOKENS.surface_soft};
                border:1px solid {TOKENS.border};
                border-radius:{TOKENS.radius_sm}px;
                padding:7px 9px;
                min-height:22px;
            }}
            QLineEdit:hover {{ border-color:{TOKENS.border_strong}; }}
            QLineEdit:focus {{ border:2px solid {TOKENS.accent}; padding:6px 8px; }}
            QLabel#profileFootnote {{ color:#647789; font-size:10px; }}
            """
        )

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(0)

        card = QFrame(dlg)
        card.setObjectName("profileSetupCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 20)
        card_layout.setSpacing(14)

        eyebrow = QLabel("DRIVER PROFILE • FIRST-RUN SETUP")
        eyebrow.setObjectName("profileEyebrow")
        card_layout.addWidget(eyebrow)

        title = QLabel("CREATE DRIVER PROFILE")
        title.setObjectName("profileTitle")
        card_layout.addWidget(title)

        intro = QLabel("Create the person-level profile that owns your Race Engineer history. In-game driver names remain separate, so your long-term history stays attached to the correct person.")
        intro.setObjectName("profileIntro")
        intro.setWordWrap(True)
        card_layout.addWidget(intro)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(11)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        name = QLineEdit()
        name.setPlaceholderText("Driver name")
        country = QLineEdit()
        country.setPlaceholderText("Optional")
        units = QComboBox()
        units.addItem("Metric", "metric")
        units.addItem("Imperial", "imperial")
        time_zone = QComboBox()
        time_zone.setEditable(True)
        for zone in COMMON_TIME_ZONES:
            time_zone.addItem(zone, zone)
        idx = time_zone.findData(DEFAULT_TIME_ZONE)
        if idx >= 0:
            time_zone.setCurrentIndex(idx)
        time_zone.setToolTip("IANA time zone, for example Asia/Kolkata or Europe/London")
        game = QComboBox()
        game.addItem("F1 26 — Available", "f1_26")
        game.addItem("ACC — Future support", "acc")
        game.model().item(1).setEnabled(False)
        game.addItem("Dirt Rally 2.0 — Future support", "dirt_rally_2")
        game.model().item(2).setEnabled(False)

        def field_label(text):
            label = QLabel(text)
            label.setObjectName("profileFieldLabel")
            return label

        form.addRow(field_label("DISPLAY NAME"), name)
        form.addRow(field_label("COUNTRY / REGION"), country)
        form.addRow(field_label("PREFERRED UNITS"), units)
        form.addRow(field_label("TIME ZONE"), time_zone)
        form.addRow(field_label("ACTIVE GAME"), game)
        card_layout.addLayout(form)

        avatar_path = {"value": ""}
        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(8)
        avatar_title = field_label("AVATAR")
        avatar_label = QLabel("No avatar selected")
        avatar_label.setObjectName("profileAvatarState")
        avatar_label.setWordWrap(True)
        avatar_btn = QPushButton("Choose Avatar…")
        avatar_clear = QPushButton("Clear")
        avatar_btn.setStyleSheet(button_class_qss("secondary"))
        avatar_clear.setStyleSheet(button_class_qss("secondary"))
        avatar_row.addWidget(avatar_title)
        avatar_row.addSpacing(38)
        avatar_row.addWidget(avatar_label, 1)
        avatar_row.addWidget(avatar_btn)
        avatar_row.addWidget(avatar_clear)
        card_layout.addLayout(avatar_row)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background:{TOKENS.border};max-height:1px;border:0;")
        card_layout.addWidget(divider)

        existing = history.user_profiles()
        legacy_active = history.active_user_profile_id()
        if existing:
            selected = next((p for p in existing if int(p.get("id", -1)) == int(legacy_active or -1)), existing[0])
            legacy_name = str(selected.get("name") or "").strip()
            if legacy_name and legacy_name.lower() != "local driver":
                name.setText(legacy_name)

        def choose_avatar():
            path, _ = QFileDialog.getOpenFileName(dlg, "Choose Avatar", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
            if path:
                avatar_path["value"] = path
                avatar_label.setText(path)

        def clear_avatar():
            avatar_path["value"] = ""
            avatar_label.setText("No avatar selected")

        avatar_btn.clicked.connect(choose_avatar)
        avatar_clear.clicked.connect(clear_avatar)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        note = QLabel("You can change profile details later. Existing telemetry and Performance Hub history are preserved.")
        note.setObjectName("profileFootnote")
        note.setWordWrap(True)
        buttons.addWidget(note, 1)
        create = QPushButton("CREATE PROFILE")
        cancel = QPushButton("CANCEL")
        cancel.setStyleSheet(button_class_qss("secondary"))
        create.setStyleSheet(button_class_qss("primary"))
        create.setDefault(True)
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        card_layout.addLayout(buttons)
        outer.addWidget(card)

        def create_profile():
            display_name = " ".join(name.text().strip().split())
            if not display_name:
                QMessageBox.warning(dlg, "Driver Profile", "Enter a display name.")
                return
            try:
                legacy_id = history.active_user_profile_id()
                if legacy_id is None:
                    legacy_id = history.create_user_profile(display_name)
                else:
                    # Preserve all existing session ownership; only improve the
                    # legacy label when it is still the default placeholder.
                    rows = history.user_profiles()
                    row = next((r for r in rows if int(r.get("id", -1)) == int(legacy_id)), None)
                    if row and str(row.get("name") or "").strip().lower() == "local driver":
                        history.rename_user_profile(int(legacy_id), display_name)
                    history.set_active_user_profile(int(legacy_id))
                profile = profiles.create_profile(
                    display_name,
                    country_region=country.text(),
                    units=units.currentData(),
                    time_zone=time_zone.currentText().strip(),
                    avatar_source=avatar_path["value"] or None,
                    active_game=game.currentData(),
                    compatibility={"performance_history_profile_id": int(legacy_id)},
                )
                profiles.set_active_driver(str(profile["driver_id"]))
                try:
                    from ..f1_profile_migration import attach_existing_f1_history
                    attach_existing_f1_history(profiles, history, str(profile["driver_id"]))
                except Exception as error:
                    print(f"[PROFILE] Initial F1 history attachment skipped: {error}", flush=True)
            except Exception as exc:
                QMessageBox.warning(dlg, "Driver Profile", str(exc))
                return
            dlg.accept()

        create.clicked.connect(create_profile)
        cancel.clicked.connect(dlg.reject)
        name.returnPressed.connect(create_profile)
        return dlg.exec() == QDialog.Accepted

    if not ensure_driver_profile():
        return 0
    stop_event = threading.Event()
    errors = []

    replay_controller = ReplayController(replay_file, speed=replay_speed, realtime=not replay_fast)

    dashboard_store = DashboardStateStore() if web_dash else None
    dashboard_server = None
    dashboard_url = None

    # Keep the live UDP receiver bound for the entire application lifetime.
    # Replay is a second source gated by RaceStateReceiver.set_telemetry_mode().
    replay_thread = {"thread": None, "stop": None}
    mode = {"value": "live"}

    def live_worker():
        try:
            receiver.set_telemetry_mode("live")
            receiver.run(stop_event=stop_event)
        except BaseException as error:
            errors.append(error)
            stop_event.set()

    live_thread = threading.Thread(target=live_worker, name="race-engineer-overlay-live", daemon=True)
    live_thread.start()

    def _stop_replay_thread():
        ev = replay_thread.get("stop")
        th = replay_thread.get("thread")
        if ev is not None:
            ev.set()
        if th is not None and th.is_alive() and th is not threading.current_thread():
            th.join(timeout=2.0)
        replay_thread["thread"] = None
        replay_thread["stop"] = None

    def set_replay_mode(enabled: bool):
        enabled = bool(enabled)
        if enabled:
            if not replay_controller.records:
                return False, "Select a replay recording first"
            _stop_replay_thread()
            receiver.set_telemetry_mode("replay", replay_thread_id=-1)
            receiver.reset_replay_state()
            replay_controller.set_paused(False)
            ev = threading.Event()

            def replay_worker():
                try:
                    receiver.set_telemetry_mode("replay", replay_thread_id=threading.get_ident())
                    replay_controller.run(receiver, stop_event=ev)
                except BaseException as error:
                    errors.append(error)

            th = threading.Thread(target=replay_worker, name="race-engineer-overlay-replay", daemon=True)
            replay_thread["stop"] = ev
            replay_thread["thread"] = th
            mode["value"] = "replay"
            th.start()
            return True, "Replay mode active"

        _stop_replay_thread()
        replay_controller.set_paused(True)
        # While still gated to replay, clear replay-derived state. Then reopen the
        # live source; fresh UDP packets immediately rebuild the current game state.
        receiver.reset_replay_state()
        receiver.set_telemetry_mode("live")
        mode["value"] = "live"
        return True, "Live UDP mode active"

    def replay_mode_active():
        return mode["value"] == "replay"


    # Start the HTTP server only after replay-mode callbacks exist. This lets the
    # browser Replay / Session Analysis page activate the actual replay worker,
    # rather than only flipping ReplayController.paused while live UDP remains the
    # active source.
    if web_dash:
        try:
            dashboard_server = RemoteDashboardServer(
                dashboard_store, host=dash_host, port=dash_port,
                replay_controller=replay_controller,
                replay_mode_setter=set_replay_mode,
                replay_mode_getter=replay_mode_active,
            )
            info = dashboard_server.start()
            dashboard_url = info.lan_url
            print(f"[DASH] Local browser : {info.local_url}", flush=True)
            print(f"[DASH] Other devices : {info.lan_url}", flush=True)
        except OSError as error:
            dashboard_server = None
            dashboard_store = None
            print(f"[DASH] Web dashboard unavailable: {error}", flush=True)

    def pause_changed(paused: bool):
        if replay_mode_active():
            replay_controller.set_paused(paused)

    def close_requested():
        _stop_replay_thread()
        stop_event.set()
        app.quit()

    suite = OverlaySuite(
        OverlayDataProvider(receiver),
        click_through=click_through,
        on_pause_changed=pause_changed,
        on_close=close_requested,
        replay_controller=replay_controller,
        on_toggle_replay=set_replay_mode,
        replay_mode_getter=replay_mode_active,
        dashboard_store=dashboard_store,
        dashboard_url=dashboard_url,
    )
    suite.show()

    # Preserve old CLI semantics: --replay / --replay-browser starts in replay.
    if replay_file is not None:
        QTimer.singleShot(0, lambda: (set_replay_mode(True), suite.control_center.set_replay_mode(True)))

    poll = QTimer()

    def monitor():
        if errors:
            message = str(errors[0])
            errors.clear()
            QMessageBox.critical(suite.coach, "Race Engineer telemetry error", message)
            app.quit()

    poll.timeout.connect(monitor)
    poll.start(250)

    rc = app.exec()
    _stop_replay_thread()
    stop_event.set()
    live_thread.join(timeout=3.0)
    if dashboard_server is not None:
        dashboard_server.stop()
    return rc

