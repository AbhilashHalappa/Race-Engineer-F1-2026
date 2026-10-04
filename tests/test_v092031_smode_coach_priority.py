from src.engineer.models import EngineerMessage, Priority
from src.tts import SpeechOutput


def test_post_corner_coaching_outranks_automatic_s_mode_reminder():
    coach = EngineerMessage(
        "coach:corner:3:trail_brake_weak",
        Priority.COACHING,
        "Turn 3: carry the brake deeper into the corner.",
        0,
    )
    s_mode = EngineerMessage("assist:s_mode", Priority.COACHING, "S Mode.", 0)
    assert SpeechOutput._radio_rank(coach) < SpeechOutput._radio_rank(s_mode)


def test_other_assist_reminders_keep_existing_priority_over_coaching():
    coach = EngineerMessage(
        "coach:corner:5:exit_speed_low", Priority.COACHING, "Turn 5: improve exit speed.", 0
    )
    ers = EngineerMessage("assist:ers", Priority.COACHING, "Overtake available.", 0)
    drs = EngineerMessage("assist:drs", Priority.COACHING, "DRS.", 0)
    assert SpeechOutput._radio_rank(ers) < SpeechOutput._radio_rank(coach)
    assert SpeechOutput._radio_rank(drs) < SpeechOutput._radio_rank(coach)
