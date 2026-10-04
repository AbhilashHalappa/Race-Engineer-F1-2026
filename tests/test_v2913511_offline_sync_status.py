from src.server_platform import _normalize_sync_display_state, _display_api_latency_ms


def test_offline_sync_busy_is_never_presented_as_syncing():
    assert _normalize_sync_display_state("offline", "SYNC_BUSY", 3) == "OFFLINE_FALLBACK"


def test_offline_pending_remote_stale_state_is_forced_to_fallback():
    assert _normalize_sync_display_state("offline", "REMOTE", 3) == "OFFLINE_FALLBACK"


def test_online_sync_busy_can_be_presented_as_syncing():
    assert _normalize_sync_display_state("online", "SYNC_BUSY", 3) == "SYNCING"


def test_online_empty_pending_collapses_to_remote():
    assert _normalize_sync_display_state("online", "PENDING_SYNC", 0) == "REMOTE"
    assert _normalize_sync_display_state("online", "SYNCING", 0) == "REMOTE"


def test_online_remote_with_pending_is_syncing():
    assert _normalize_sync_display_state("online", "REMOTE", 3) == "SYNCING"


def test_failed_api_timeout_is_not_exposed_as_ping():
    assert _display_api_latency_ms("offline", 2053.8) is None
    assert _display_api_latency_ms("online", 12.345) == 12.35
