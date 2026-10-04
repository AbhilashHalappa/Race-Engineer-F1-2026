from types import SimpleNamespace
from pathlib import Path

from src.race_state.models import RaceState, CarState, Wheels
from src.session_summary import SessionSummaryTracker, finish_call, save_summary
from src.voice_commands import VoiceIntent, parse_intent, handle_voice_request


def test_lap_remaining_aliases_share_one_intent():
    for phrase in ('lap remaining','laps remaining','remaining lap','remaining laps','laps left','how many laps left','how many laps remaining'):
        assert parse_intent(phrase) == VoiceIntent.LAPS_REMAINING, phrase


def test_direction_and_sector_aliases():
    assert parse_intent('ahead driver') == VoiceIntent.DRIVER_AHEAD
    assert parse_intent('behind driver') == VoiceIntent.DRIVER_BEHIND
    assert parse_intent('sector') == VoiceIntent.CURRENT_SECTOR
    assert parse_intent('race summary') == VoiceIntent.SESSION_SUMMARY


def test_lap_remaining_and_completed_grammar():
    s=RaceState(player_index=0,player=CarState(index=0)); s.field[0]=s.player
    s.session.total_laps=5; s.player.lap.current_lap=4
    assert handle_voice_request('remaining laps',s).response == '1 lap remaining.'
    s.player.lap.current_lap=2
    assert handle_voice_request('laps completed',s).response == '1 lap completed.'


def test_generic_tyre_info_is_short_but_detailed_temp_is_available():
    s=RaceState(player_index=0,player=CarState(index=0)); s.field[0]=s.player
    s.player.tyres.surface_temperature_c=Wheels(90,91,92,93)
    s.player.tyres.wear_percent=Wheels(4,5,4,5)
    assert handle_voice_request('tyre information',s).response == 'Tyres are good.'
    r=handle_voice_request('detailed tyre temperatures',s).response
    assert 'front left 90 degrees' in r and 'rear right 93' in r


def test_finish_calls_depend_on_classified_result():
    base={'session_uid':1,'result_status_raw':3}
    assert 'win' in finish_call({**base,'position':1}).lower() or 'won' in finish_call({**base,'position':1}).lower()
    assert finish_call({**base,'position':2}).startswith('P2.')
    assert 'Podium' in finish_call({**base,'position':3})
    assert 'disqualified' in finish_call({'result_status_raw':5,'position':1}).lower()
    assert "We're out" in finish_call({'result_status_raw':7,'position':18})


def test_summary_uses_authoritative_final_classification(tmp_path):
    s=RaceState(player_index=0,player=CarState(index=0)); s.field[0]=s.player
    s.session.uid=123; s.player.lap.current_lap=5; s.player.lap.grid_position=4
    tracker=SessionSummaryTracker(); tracker.observe(s)
    tracker.max_tyre_temp_c=115; tracker.max_front_wing_damage_percent=36
    row=SimpleNamespace(m_resultStatus=3,m_position=1,m_gridPosition=4,m_numLaps=5,m_points=25,m_numPitStops=1,
                        m_bestLapTimeInMS=87219,m_totalRaceTime=450.5,m_penaltiesTime=0,m_numPenalties=0,m_numTyreStints=2,
                        m_tyreStintsActual=(16,18,0,0,0,0,0,0),m_tyreStintsVisual=(16,18,0,0,0,0,0,0),m_tyreStintsEndLaps=(2,5,0,0,0,0,0,0))
    s.extended['final']=SimpleNamespace(m_classificationData=(row,))
    perf=SimpleNamespace(completed=[])
    summary=tracker.build(s,perf)
    assert summary['position']==1 and summary['grid_position']==4
    assert summary['best_lap_s']==87.219
    assert summary['max_tyre_temp_c']==115
    assert 'P1' in summary['finish_call']
    jp,tp=save_summary(summary,tmp_path)
    assert jp.exists() and tp.exists()
    assert 'SESSION SUMMARY' in tp.read_text()
