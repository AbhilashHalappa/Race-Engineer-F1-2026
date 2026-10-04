from pathlib import Path

from src.performance_history import PerformanceHistoryStore, _merge_live_coach_snapshots


def _profile():
    return {"name":"abhilashh2411","race_number":12,"platform_id":1,"team_name":"Mercedes '26"}


def _summary():
    return {"session_uid":9911,"track":"Catalunya","session_type":"Time Trial","laps_completed":5,"best_lap_s":77.2,"position":1}


def _live(lap, score):
    return {
        "lap_number":lap,"lap_time_s":77.0+lap/10,"lap_valid":True,"lap_score":score,"confidence":0.95,
        "quality":{"eligible":True},"corners":{"1":{"corner_id":1,"score":score,"confidence":0.95,"estimated_loss_s":0.1}}
    }


def test_merge_preserves_cached_performance_review_lap_rows_across_garage():
    old={"performance_review":{"laps":[{"lap":6,"score":76}],"lap_reviews":[{"lap":6,"summary":{"lap":6,"score":76},"corners":[]}]}}
    new={"performance_review":{"laps":[{"lap":9,"score":82}],"lap_reviews":[{"lap":9,"summary":{"lap":9,"score":82},"corners":[]}]}}
    merged=_merge_live_coach_snapshots(old,new)
    assert [x['lap'] for x in merged['performance_review']['laps']] == [6,9]
    assert [x['lap'] for x in merged['performance_review']['lap_reviews']] == [6,9]


def test_review_repairs_stale_cached_review_and_keeps_all_timed_laps_selectable(tmp_path: Path):
    store=PerformanceHistoryStore(tmp_path/'history.sqlite3')
    store.create_user_profile('Abhilash H')
    lap_store={str(n):{"lap":n,"lap_time_s":77+n/10,"valid":True,"telemetry":{}} for n in range(6,11)}
    coach={
        "created_utc":"2026-09-29T06:00:00+00:00",
        "event_context":{"session_uid":9911,"track_name":"Catalunya","session_type":"Time Trial","game_mode":5},
        "lap_telemetry":lap_store,
        "lap_facts":[{"lap":n,"lap_time_s":77+n/10,"valid":True,"quality":{"eligible":True}} for n in range(6,11)],
        "live_lap_intelligence":[_live(n,70+n) for n in range(6,11)],
        "lap_comparisons":[],
        # Simulate the V2.0.5.9 symptom: cached review was overwritten by the latest stint.
        "performance_review":{"status":"available","laps":[{"lap":9},{"lap":10}],"lap_reviews":[{"lap":9,"summary":{"lap":9},"corners":[]},{"lap":10,"summary":{"lap":10},"corners":[]}]},
    }
    sid=store.record_session(_profile(),_summary(),coach)
    d=store.review_detail(sid, reference='lap:7', view_lap=6)
    assert [x['lap'] for x in d['available_laps']] == [6,7,8,9,10]
    assert d['review']['view_lap'] == 6
    assert d['review']['session_technique_score'] == 76.0
    assert d['review']['corners'][0]['score'] == 76.0
