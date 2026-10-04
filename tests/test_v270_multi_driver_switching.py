from pathlib import Path

from src.driver_profiles import DriverProfileStore
from src.performance_history import PerformanceHistoryStore
from src.driver_context import DriverContextManager


def _stores(tmp_path: Path):
    drivers=DriverProfileStore(tmp_path/'drivers')
    history=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    return drivers,history,DriverContextManager(drivers,history)


def test_v270_create_driver_contexts_have_distinct_person_and_history_owners(tmp_path):
    drivers,history,manager=_stores(tmp_path)
    first=manager.create('Same Name',time_zone='UTC')
    first_history=first['compatibility']['performance_history_profile_id']
    second=manager.create('Same Name',time_zone='Asia/Kolkata')
    second_history=second['compatibility']['performance_history_profile_id']

    assert first['driver_id'] != second['driver_id']
    assert int(first_history) != int(second_history)
    assert len(drivers.list_profiles()) == 2
    # The compatibility layer may suffix a duplicate legacy name, but ownership
    # remains distinct and the person-level display name is untouched.
    assert drivers.load_profile(first['driver_id'])['display_name'] == 'Same Name'
    assert drivers.load_profile(second['driver_id'])['display_name'] == 'Same Name'
    assert history.active_user_profile_id() == int(second_history)


def test_v270_switch_moves_driver_and_performance_history_owner_together(tmp_path):
    drivers,history,manager=_stores(tmp_path)
    first=manager.create('Driver One')
    second=manager.create('Driver Two')
    first_history=int(first['compatibility']['performance_history_profile_id'])
    second_history=int(second['compatibility']['performance_history_profile_id'])

    manager.activate(first['driver_id'])
    assert drivers.active_driver_id() == first['driver_id']
    assert history.active_user_profile_id() == first_history

    manager.activate(second['driver_id'])
    assert drivers.active_driver_id() == second['driver_id']
    assert history.active_user_profile_id() == second_history


def test_v270_missing_history_link_repairs_to_new_empty_owner_not_current_owner(tmp_path):
    drivers,history,manager=_stores(tmp_path)
    first=manager.create('Driver One')
    first_history=int(first['compatibility']['performance_history_profile_id'])
    # Simulate an old/broken profile with no compatibility link.
    second=drivers.create_profile('Driver Two',compatibility={})
    assert history.active_user_profile_id() == first_history

    manager.activate(second['driver_id'])
    repaired=drivers.load_profile(second['driver_id'])
    repaired_history=int(repaired['compatibility']['performance_history_profile_id'])
    assert repaired_history != first_history
    assert history.active_user_profile_id() == repaired_history


def test_v270_control_center_exposes_switcher_and_new_driver_ui():
    source=Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'self.profile_switch_button=self._driver_action_button("SWITCH DRIVER"' in source
    assert 'def _open_driver_switcher(self):' in source
    assert 'def _create_additional_driver_dialog(self, parent=None)' in source
    assert '"+ NEW DRIVER"' in source
    assert 'DriverContextManager(self._driver_profile_store()).activate' in source
    assert 'The new Driver starts with empty Performance Hub ownership.' in source


def test_v2701_driver_action_buttons_are_text_sized_not_overlay_icons():
    source=Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'def _driver_action_button(self, text: str, tooltip: str' in source
    assert 'button.setMinimumWidth(int(min_width))' in source
    assert 'button.setMinimumHeight(34)' in source
    assert 'self._driver_action_button("+ NEW DRIVER"' in source
    assert 'self._driver_action_button("CLOSE"' in source
    assert 'self._driver_action_button("SWITCH"' in source


def test_v2702_driver_switcher_scroll_surface_uses_dark_palette():
    source=Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'content.setObjectName("driverSwitcherContent")' in source
    assert 'QWidget#driverSwitcherContent{background:#091017;}' in source
    assert 'QScrollArea{background:#091017;border:none;}' in source


def test_v271_delete_driver_removes_only_owned_history_and_switches_active(tmp_path):
    drivers,history,manager=_stores(tmp_path)
    first=manager.create('Driver One')
    first_history=int(first['compatibility']['performance_history_profile_id'])
    history.record_session(
        {'name':'Game Driver One','driver_id':1,'game_year':2026},
        {'session_uid':101,'created_utc':'2026-09-01T10:00:00+00:00','track_name':'Melbourne','session_type':'Time Trial','best_lap_s':90.0},
        {},
    )
    second=manager.create('Driver Two')
    second_history=int(second['compatibility']['performance_history_profile_id'])
    history.record_session(
        {'name':'Game Driver Two','driver_id':2,'game_year':2026},
        {'session_uid':202,'created_utc':'2026-09-02T10:00:00+00:00','track_name':'Spa','session_type':'Time Trial','best_lap_s':91.0},
        {},
    )

    result=manager.delete(second['driver_id'])
    assert result['deleted_driver_id']==second['driver_id']
    assert result['deleted_history_id']==second_history
    assert result['deleted_sessions']==1
    assert drivers.load_profile(second['driver_id']) is None
    assert drivers.active_driver_id()==first['driver_id']
    assert history.active_user_profile_id()==first_history
    assert {int(x['id']) for x in history.user_profiles()}=={first_history}
    with history._connect() as con:
        assert con.execute('SELECT COUNT(*) FROM sessions WHERE user_profile_fk=?',(second_history,)).fetchone()[0]==0
        assert con.execute('SELECT COUNT(*) FROM sessions WHERE user_profile_fk=?',(first_history,)).fetchone()[0]==1


def test_v271_cannot_delete_only_remaining_driver(tmp_path):
    drivers,history,manager=_stores(tmp_path)
    only=manager.create('Only Driver')
    try:
        manager.delete(only['driver_id'])
    except ValueError as error:
        assert 'only remaining' in str(error).lower()
    else:
        raise AssertionError('deleting the only Driver must be blocked')
    assert drivers.load_profile(only['driver_id']) is not None


def test_v271_switcher_exposes_delete_and_rounded_driver_actions():
    source=Path('src/overlay/window.py').read_text(encoding='utf-8')
    assert 'def _delete_driver_profile(self, driver_id: str, parent=None)' in source
    assert 'DriverContextManager(self._driver_profile_store()).delete(did)' in source
    assert 'self._driver_action_button("DELETE"' in source
    assert 'danger=True' in source
    assert 'border-radius:11px' in source
    assert 'self.profile_switch_button.setMinimumHeight(42)' in source


def test_v2711_new_driver_creation_uses_bundled_timezone_when_system_zoneinfo_missing(tmp_path, monkeypatch):
    from zoneinfo import ZoneInfo as RealZoneInfo, ZoneInfoNotFoundError
    import src.user_time as user_time

    class _NoSystemZoneInfo:
        def __new__(cls, key):
            raise ZoneInfoNotFoundError(key)

        @staticmethod
        def from_file(handle, key=None):
            return RealZoneInfo.from_file(handle, key=key)

    monkeypatch.setattr(user_time, 'ZoneInfo', _NoSystemZoneInfo)
    drivers,history,manager=_stores(tmp_path)
    created=manager.create('Kolkata Driver',time_zone='Asia/Kolkata')
    assert created['time_zone']=='Asia/Kolkata'
    loaded=drivers.load_profile(created['driver_id'])
    assert loaded['time_zone']=='Asia/Kolkata'
