from src.overlay.re_refresh import should_refresh_race_engineer


def test_re_refreshes_continuously_during_active_replay():
    assert should_refresh_race_engineer(visible=True, paused=False, replay_mode=True, rebuilding=False)
    assert should_refresh_race_engineer(visible=True, paused=True, replay_mode=True, rebuilding=False)


def test_re_holds_only_during_replay_rebuild_or_when_hidden():
    assert not should_refresh_race_engineer(visible=True, paused=False, replay_mode=True, rebuilding=True)
    assert not should_refresh_race_engineer(visible=False, paused=False, replay_mode=True, rebuilding=False)


def test_live_pause_freezes_re_panel():
    assert not should_refresh_race_engineer(visible=True, paused=True, replay_mode=False, rebuilding=False)
    assert should_refresh_race_engineer(visible=True, paused=False, replay_mode=False, rebuilding=False)
