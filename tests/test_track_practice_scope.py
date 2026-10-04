from src.practice_planner import build_track_practice_plan

def pat(corner, code, cost, repeats=2, conf=.9):
    return {"corner_id":corner,"issue_code":code,"issue_label":code.replace('_',' '),"phase":"EXIT","repeat_count":repeats,"mean_time_cost_s":cost,"recent_time_cost_s":cost,"mean_confidence":conf,"latest_observed":True}

def session(i, patterns, eligible=(1,2,3), best=80.0):
    return {"session_id":i,"created_utc":f"2026-10-0{i}T10:00:00Z","track_name":"Catalunya","best_lap_s":best,
            "report":{"recurring_patterns":patterns,"coaching_data_quality":{"eligible_laps":list(eligible)},"best_lap":{"lap_time_s":best},"potential":{"potential_gain_s":.2}},
            "review":{"data_quality":{"eligible_laps":list(eligible)}}}

def test_old_mastered_issue_does_not_survive_latest_session():
    rows=[session(1,[pat(10,'late_throttle',.30)]),session(2,[pat(10,'late_throttle',.18)]),session(3,[pat(6,'low_apex',.12)])]
    p=build_track_practice_plan(rows)
    assert p['scope']=='track'
    assert p['session_count']==3
    assert p['baseline_eligible_laps']==9
    assert p['primary_focus']['corner_id']==6
    assert all(x['corner_id']!=10 for x in [p['primary_focus'],p.get('secondary_focus')] if x)
    assert any(x['corner_id']==10 for x in p['resolved_or_not_current'])

def test_history_strengthens_current_issue_and_tracks_trend():
    rows=[session(1,[pat(10,'late_throttle',.30)]),session(2,[pat(10,'late_throttle',.20)]),session(3,[pat(10,'late_throttle',.10)])]
    p=build_track_practice_plan(rows)
    f=p['primary_focus']
    assert f['corner_id']==10
    assert f['trend']=='improving'
    assert f['repeat_count']>=6
    assert p['status']=='available'
