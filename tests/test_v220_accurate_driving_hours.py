from types import SimpleNamespace as NS

from src.driver_profiles import DriverProfileStore
from src.driving_time import F1DrivingTimeTracker, f1_session_bucket
from src.telemetry.enums import EnumValue


def ev(raw, name):
    return EnumValue(raw, name)


def state(t, *, uid=10, session_type="Practice 1", paused=False, spectating=False, ended=False,
          driver_status="On track", telemetry=True):
    return NS(
        session=NS(uid=uid, session_time_s=float(t), session_type=ev(1, session_type),
                   paused=paused, spectating=spectating, ended=ended),
        player=NS(
            lap=NS(driver_status=ev(4, driver_status)),
            telemetry=NS(speed_kph=120, throttle=.5, brake=0.0) if telemetry else None,
        ),
    )


def new_tracker(tmp_path, *, flush=999.0):
    store = DriverProfileStore(tmp_path / "drivers")
    profile = store.create_profile("Driver")
    return store, profile, F1DrivingTimeTracker(store=store, flush_interval_s=flush)


def test_f1_session_bucket_mapping():
    assert f1_session_bucket(ev(1, "Practice 1")) == "practice"
    assert f1_session_bucket(ev(18, "Time Trial")) == "time_trial"
    assert f1_session_bucket(ev(5, "Qualifying 1")) == "qualifying"
    assert f1_session_bucket(ev(10, "Sprint Shootout 1")) == "qualifying"
    assert f1_session_bucket("Sprint") == "sprint"
    assert f1_session_bucket(ev(15, "Race")) == "race"


def test_counts_only_live_active_track_telemetry(tmp_path):
    store, profile, tracker = new_tracker(tmp_path)
    assert tracker.observe(state(10.0), mode="live", packet_category="telemetry") == 0
    assert 0.49 < tracker.observe(state(10.5), mode="live", packet_category="telemetry") < 0.51
    tracker.flush()
    gp = store.load_game_profile(profile["driver_id"], "f1_26")
    assert 0.49 < gp["driving_seconds"] < 0.51
    assert 0.49 < gp["driving_time"]["practice"] < 0.51


def test_pause_garage_replay_and_long_gap_do_not_inflate(tmp_path):
    store, profile, tracker = new_tracker(tmp_path)
    tracker.observe(state(10.0), mode="live", packet_category="telemetry")
    assert tracker.observe(state(10.5, paused=True), mode="live", packet_category="telemetry") == 0
    assert tracker.observe(state(11.0, driver_status="In garage"), mode="live", packet_category="telemetry") == 0
    assert tracker.observe(state(11.5), mode="replay", packet_category="telemetry") == 0
    # Replay reset means live re-entry establishes a new baseline.
    assert tracker.observe(state(20.0), mode="live", packet_category="telemetry") == 0
    # A menu/telemetry outage cannot be back-filled as driving.
    assert tracker.observe(state(25.0), mode="live", packet_category="telemetry") == 0
    tracker.flush()
    gp = store.load_game_profile(profile["driver_id"], "f1_26")
    assert float(gp["driving_seconds"]) == 0.0


def test_time_is_split_by_session_type_and_updates_career_total(tmp_path):
    store, profile, tracker = new_tracker(tmp_path)
    tracker.observe(state(1.0, session_type="Time Trial"), mode="live", packet_category="telemetry")
    tracker.observe(state(2.0, session_type="Time Trial"), mode="live", packet_category="telemetry")
    tracker.observe(state(2.0, uid=20, session_type="Race"), mode="live", packet_category="telemetry")
    tracker.observe(state(3.5, uid=20, session_type="Race"), mode="live", packet_category="telemetry")
    tracker.flush()
    gp = store.load_game_profile(profile["driver_id"], "f1_26")
    assert 0.99 < gp["driving_time"]["time_trial"] < 1.01
    assert 1.49 < gp["driving_time"]["race"] < 1.51
    assert 2.49 < gp["driving_seconds"] < 2.51
    career = store.load_career_summary(profile["driver_id"])
    assert 2.49 < career["total_driving_seconds"] < 2.51


def test_inactive_game_profile_blocks_f1_time(tmp_path):
    store, profile, tracker = new_tracker(tmp_path)
    assert store.set_active_game(profile["driver_id"], "acc")
    tracker.observe(state(1.0), mode="live", packet_category="telemetry")
    tracker.observe(state(2.0), mode="live", packet_category="telemetry")
    tracker.flush()
    gp = store.load_game_profile(profile["driver_id"], "f1_26")
    assert float(gp["driving_seconds"]) == 0.0


def test_switching_game_flushes_pending_f1_time_to_original_profile(tmp_path):
    store, profile, tracker = new_tracker(tmp_path)
    tracker.observe(state(1.0), mode="live", packet_category="telemetry")
    tracker.observe(state(2.0), mode="live", packet_category="telemetry")
    assert store.set_active_game(profile["driver_id"], "acc")
    tracker.observe(state(2.5), mode="live", packet_category="telemetry")
    gp = store.load_game_profile(profile["driver_id"], "f1_26")
    assert 0.99 < gp["driving_seconds"] < 1.01


def test_entering_replay_flushes_pending_live_time(tmp_path):
    store, profile, tracker = new_tracker(tmp_path)
    tracker.observe(state(1.0), mode="live", packet_category="telemetry")
    tracker.observe(state(2.0), mode="live", packet_category="telemetry")
    tracker.observe(state(2.5), mode="replay", packet_category="telemetry")
    gp = store.load_game_profile(profile["driver_id"], "f1_26")
    assert 0.99 < gp["driving_seconds"] < 1.01
