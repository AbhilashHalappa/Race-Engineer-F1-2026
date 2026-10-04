from pathlib import Path

from src.radio_controls import parse_runtime_radio_command
from src.speech_quality import prepare_spoken_text, PronunciationDictionary, concise_engineer_text
from src.race_state_receiver import RaceStateReceiver
from src.ptt import PTTConfig
from src.stt import STTConfig
from src.llm_engineer import LLMConfig


def receiver(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return RaceStateReceiver(
        tts_enabled=False,
        ptt_config=PTTConfig(enabled=False),
        stt_config=STTConfig(enabled=False),
        llm_config=LLMConfig(enabled=False),
        wheel_telemetry=False,
    )


def test_control_parser_aliases_and_queries():
    c=parse_runtime_radio_command('turn off corner coach voice')
    assert (c.action,c.target,c.value)==('CONTROL_SET','CCVOICE',False)
    c=parse_runtime_radio_command('enable damage coaching')
    assert (c.target,c.value)==('DMGCOACH',True)
    c=parse_runtime_radio_command('is race engineer enabled')
    assert (c.action,c.target)==('CONTROL_STATUS','ENGR')
    c=parse_runtime_radio_command('set coaching mode time trial')
    assert c.action=='MODE' and c.value=='time_trial'
    c=parse_runtime_radio_command('set radio detail minimal')
    assert c.action=='VERBOSITY' and c.value=='minimal'
    c=parse_runtime_radio_command('voice speed fast')
    assert c.action=='VOICE_SPEED' and c.value=='fast'


def test_all_requested_runtime_controls_route(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    targets=('ENGR','PRE','POST','LAP','POS','RACE','CORNER','CCVOICE','CCPRE','CCPOST','GAINLOSS','GAINLOSSVOICE','DMGCOACH','TTS','PTT','STT','LLM','REC')
    states=r._runtime_control_states()
    for target in targets:
        assert target in states
    for target in ('ENGR','PRE','POST','LAP','POS','RACE','CORNER','CCVOICE','CCPRE','CCPOST','GAINLOSS','GAINLOSSVOICE','DMGCOACH'):
        ok,_=r._set_runtime_control(target,False); assert ok
        ok,_=r._set_runtime_control(target,True); assert ok


def test_corner_post_gainloss_voice_remain_mutually_exclusive(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    assert r.set_corner_coach_feature('POST',True)[0]
    assert r.corner_coach.post_enabled
    assert r.set_corner_coach_feature('GAINLOSSVOICE',True)[0]
    assert r.corner_coach.gain_loss_voice_enabled
    assert not r.corner_coach.post_enabled
    handled,response,_=r.handle_runtime_radio_command('enable corner post')
    assert handled and 'on' in response.lower()
    assert r.corner_coach.post_enabled and not r.corner_coach.gain_loss_voice_enabled


def test_runtime_control_status_and_modes(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    handled,response,_=r.handle_runtime_radio_command('disable race engineer')
    assert handled and response=='Race Engineer off.'
    handled,response,_=r.handle_runtime_radio_command('race engineer status')
    assert handled and response=='Race Engineer is off.'
    handled,response,_=r.handle_runtime_radio_command('set coaching mode performance coach')
    assert handled and 'performance coach' in response
    assert r.live_coach.settings.mode=='performance_coach'
    handled,response,_=r.handle_runtime_radio_command('set radio detail minimal')
    assert handled and r.live_coach.settings.verbosity=='minimal'


def test_voice_speed_profiles_and_model_absence(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    handled,response,_=r.handle_runtime_radio_command('voice speed fast')
    assert handled and 'fast' in response.lower()
    assert abs(r.speech.config.length_scale-0.68)<1e-9
    handled,response,_=r.handle_runtime_radio_command('next voice')
    assert handled and 'alternate' in response.lower()


def test_spoken_text_and_pronunciation(tmp_path):
    assert prepare_spoken_text('ERS 63.5%, 280 kph, 90°C') == 'E R S 63 point 5 percent, 280 kilometers per hour, 90 degrees Celsius'
    p=PronunciationDictionary(tmp_path/'pronunciation.json')
    assert 'Zand-vort' in p.apply('Zandvoort')
    p.set('Leclerc','Le-clair')
    assert p.apply('Leclerc ahead')=='Le-clair ahead'
    assert concise_engineer_text('At the moment, tyres are hot. Keep them clean.','minimal')=='tyres are hot.'


def test_help_mentions_both_engineer_and_corner_controls(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    handled,response,_=r.handle_runtime_radio_command('voice control help')
    assert handled
    assert 'Race Engineer' in response and 'CORNER COACH' in response and 'damage coach' in response


def test_speech_preferences_persist(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    assert r.set_voice_speed_profile('slow')[0]
    prefs=(tmp_path/'settings'/'speech.json').read_text(encoding='utf-8')
    assert '1.0' in prefs


def test_child_status_explains_master_gate(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    r.set_corner_coach_feature('CORNER',False)
    handled,response,_=r.handle_runtime_radio_command('corner pre status')
    assert handled and 'because CORNER COACH is off' in response
    r.set_automatic_engineer_voice_enabled(False)
    handled,response,_=r.handle_runtime_radio_command('lap summary status')
    assert handled and 'while Race Engineer is off' in response


def test_radio_help_page_is_served():
    from src.radio_help_page import radio_help_page_html
    html=radio_help_page_html()
    assert 'CORNER COACH controls' in html and 'Race Engineer controls' in html
    assert '/radio-help' not in html or 'Radio Command Reference' in html


def test_real_world_stt_aliases_from_driver_transcript(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    for phrase in ('help for buttons','radio comment','radio command'):
        handled,response,_=r.handle_runtime_radio_command(phrase)
        assert handled and 'Voice controls:' in response

    handled,response,_=r.handle_runtime_radio_command('lap code status')
    assert handled and 'lap summary is' in response
    handled,response,_=r.handle_runtime_radio_command('race code status')
    assert handled and 'race coaching is' in response

    r.set_corner_coach_feature('CORNER', True)
    handled,response,_=r.handle_runtime_radio_command('disable current coach')
    assert handled and response == 'CORNER COACH off.'
    handled,response,_=r.handle_runtime_radio_command('carver coach status')
    assert handled and 'CORNER COACH is off' in response


def test_corner_coach_pre_specificity_and_combined_pre_post(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    r.set_corner_coach_feature('CORNER', True)
    handled,response,_=r.handle_runtime_radio_command('disable corner coach pre')
    assert handled and response == 'CORNER COACH PRE off.'
    assert r.corner_coach.enabled and not r.corner_coach.pre_enabled

    handled,response,_=r.handle_runtime_radio_command('enable corner pre and post')
    assert handled
    assert r.corner_coach.pre_enabled and r.corner_coach.post_enabled
    assert 'PRE' in response and 'POST' in response


def test_gain_loss_voice_common_stt_wife_alias(tmp_path, monkeypatch):
    r=receiver(tmp_path,monkeypatch)
    r.set_corner_coach_feature('CORNER', True)
    handled,response,_=r.handle_runtime_radio_command('enable corner GL wife')
    assert handled and 'gain/loss voice on' in response
    assert r.corner_coach.gain_loss_voice_enabled


def test_bare_race_command_remains_unsupported_because_ambiguous():
    assert parse_runtime_radio_command('disable race') is None
