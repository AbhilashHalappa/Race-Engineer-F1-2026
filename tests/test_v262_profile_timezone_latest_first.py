from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.user_time import format_profile_timestamp


def test_driver_profile_persists_and_updates_iana_timezone(tmp_path):
    store=DriverProfileStore(tmp_path/'drivers')
    p=store.create_profile('Tester',active_game='f1_26',time_zone='Asia/Kolkata')
    assert p['time_zone']=='Asia/Kolkata'
    p=store.update_personal_info(p['driver_id'],time_zone='Europe/London')
    assert p['time_zone']=='Europe/London'


def test_existing_profile_without_timezone_is_non_destructively_repaired(tmp_path):
    store=DriverProfileStore(tmp_path/'drivers')
    p=store.create_profile('Tester',active_game='f1_26')
    path=store.profile_path(p['driver_id'])
    data=store._read_json(path,{})
    data.pop('time_zone',None)
    store._write_json_atomic(path,data)
    repaired=store.active_profile()
    assert repaired['time_zone']=='UTC'


def test_profile_timestamp_conversion_uses_selected_zone():
    assert format_profile_timestamp('2026-09-30T05:39:51+00:00','Asia/Kolkata')=='2026-09-30 11:09:51 IST'
    assert format_profile_timestamp('2026-09-30T05:39:51Z','UTC')=='2026-09-30 05:39:51 UTC'


def test_profile_and_first_run_ui_expose_timezone_field():
    window=Path('src/overlay/window.py').read_text(encoding='utf-8')
    runtime=Path('src/overlay/runtime.py').read_text(encoding='utf-8')
    assert '"Time zone"' in window
    assert 'form.addRow("Display name",name); form.addRow("Country / region",country); form.addRow("Preferred units",units); form.addRow("Time zone",time_zone)' in window
    assert 'field_label("TIME ZONE")' in runtime
    assert 'time_zone=time_zone.currentText().strip()' in window
    assert 'time_zone=time_zone.currentText().strip()' in runtime


def test_performance_hub_uses_profile_timezone_not_hardcoded_ist():
    ui=Path('src/performance_hub_ui.py').read_text(encoding='utf-8')
    server=Path('src/dashboard_server.py').read_text(encoding='utf-8')
    assert "let profileTimeZone='UTC'" in ui
    assert 'timeZone:tz' in ui
    assert "profileTimeZone=d.time_zone||'UTC'" in ui
    assert "payload[\"time_zone\"]" in server
    assert "timeZone:'Asia/Kolkata'" not in ui


def test_record_lists_are_newest_first_while_trend_graph_source_stays_chronological():
    history=Path('src/career_history.py').read_text(encoding='utf-8')
    perf=Path('src/performance_history.py').read_text(encoding='utf-8')
    window=Path('src/overlay/window.py').read_text(encoding='utf-8')
    web=Path('src/performance_hub_ui.py').read_text(encoding='utf-8')
    trends=Path('src/skill_trends.py').read_text(encoding='utf-8')
    assert 'reverse=True' in history  # Career timeline newest first.
    assert 'ORDER BY s.created_utc DESC LIMIT 24' in perf  # Recent sessions newest first.
    assert 'for r,row in enumerate(reversed(rows))' in window  # Native track session list newest first.
    assert '(d.sessions||[]).slice().reverse().map' in web  # Browser session list newest first.
    assert 'sessions.sort(key=lambda x:' in trends  # Trend math remains chronological by design.
