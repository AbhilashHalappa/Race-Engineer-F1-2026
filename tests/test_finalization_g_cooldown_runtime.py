from src.engineer.engine import AutomaticEngineer
from src.engineer.models import Priority
from src.speech_quality import DEFAULT_COOLDOWNS_S


def test_runtime_cooldown_categories_match_profile():
    E=AutomaticEngineer
    assert E._cooldown_category('assist:s_mode',Priority.COACHING)=='coaching'
    assert E._cooldown_category('fuel:low',Priority.STRATEGY)=='fuel'
    assert E._cooldown_category('tyre_temp:115',Priority.STRATEGY)=='tyres'
    assert E._cooldown_category('race_control:red:1',Priority.CRITICAL)=='critical'
    assert DEFAULT_COOLDOWNS_S['coaching']==6.0
