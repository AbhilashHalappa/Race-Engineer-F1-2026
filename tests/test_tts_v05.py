import os
import unittest
from unittest.mock import MagicMock, patch

from src.engineer.models import EngineerMessage, Priority
from src.tts import SpeechOutput, TTSConfig


class FakeResult:
    returncode = 0
    stderr = ''


class TTSV05Tests(unittest.TestCase):
    def test_config_validation(self):
        with self.assertRaises(ValueError): TTSConfig(length_scale=0.49)
        with self.assertRaises(ValueError): TTSConfig(volume=101)
        with self.assertRaises(ValueError): TTSConfig(backend='cloud')

    def test_disabled_output_is_noop(self):
        speech = SpeechOutput(TTSConfig(enabled=False))
        speech.submit((EngineerMessage('x', Priority.CRITICAL, 'Test', 0),))
        self.assertFalse(speech.available); speech.close()

    @patch('src.tts.SpeechOutput._load_piper')
    @patch('src.tts.SpeechOutput._speak_piper')
    @patch('src.tts.sys.platform', 'win32')
    def test_piper_speaks_on_worker_without_blocking_submit(self, speak, load):
        def loaded(obj):
            obj._piper_voice = MagicMock(); obj._piper_config_type = MagicMock(); obj.backend = 'piper'
        load.side_effect = lambda: None
        speech = SpeechOutput(TTSConfig())
        speech._piper_voice = MagicMock(); speech._piper_config_type = MagicMock(); speech.backend = 'piper'
        speech.submit((EngineerMessage('x', Priority.INFORMATION, 'Position eight.', 0),))
        speech._queue.join(); speech.close()
        self.assertEqual(speech.spoken_count, 1); speak.assert_called_once_with('Position eight.')

    @patch('src.tts.SpeechOutput._run_playback_process', return_value=FakeResult())
    @patch('src.tts.sys.platform', 'win32')
    def test_windows_backend_remains_available(self, run):
        speech = SpeechOutput(TTSConfig(backend='windows'))
        speech.submit((EngineerMessage('x', Priority.STRATEGY, 'Box this lap.', 0),))
        speech._queue.join(); speech.close()
        self.assertEqual(speech.spoken_count, 1)
        self.assertEqual(run.call_args.args[1]['RACE_ENGINEER_TTS_TEXT'], 'Box this lap.')

    @patch('src.tts.SpeechOutput._load_piper')
    @patch('src.tts.SpeechOutput._speak_piper')
    @patch('src.tts.sys.platform', 'win32')
    def test_batch_priority_critical_before_information(self, speak, load):
        speech = SpeechOutput(TTSConfig())
        speech._piper_voice = MagicMock(); speech._piper_config_type = MagicMock(); speech.backend = 'piper'
        speech.submit((EngineerMessage('info', Priority.INFORMATION, 'Information', 0),
                       EngineerMessage('critical', Priority.CRITICAL, 'Critical', 0)))
        speech._queue.join(); speech.close()
        self.assertEqual([c.args[0] for c in speak.call_args_list], ['Critical', 'Information'])

    @patch('src.tts.SpeechOutput._run_playback_process', return_value=FakeResult())
    def test_piper_temp_wav_is_deleted(self, run):
        speech = SpeechOutput(TTSConfig(enabled=False))
        voice = MagicMock(); config_type = MagicMock()
        def synth(text, wav_file, syn_config=None):
            wav_file.setnchannels(1); wav_file.setsampwidth(2); wav_file.setframerate(22050); wav_file.writeframes(b'\x00\x00')
        voice.synthesize_wav.side_effect = synth
        speech._piper_voice = voice; speech._piper_config_type = config_type
        speech._speak_piper('Test radio call.')
        wav_path = run.call_args.args[1]['RACE_ENGINEER_WAV']
        self.assertFalse(os.path.exists(wav_path))
        voice.synthesize_wav.assert_called_once()
        config_type.assert_called_once_with(length_scale=0.82, volume=1.0)

    @patch('src.tts.SpeechOutput._speak_windows', return_value=True)
    @patch('src.tts.SpeechOutput._speak_piper', side_effect=RuntimeError('bad model'))
    def test_runtime_piper_failure_does_not_change_voice(self, piper, windows):
        speech = SpeechOutput(TTSConfig(enabled=False))
        speech.available = True; speech.backend = 'piper'; speech._piper_voice = MagicMock()
        speech._speak('Fallback test')
        windows.assert_not_called()
        self.assertIn('Piper failed', speech.last_error)
        self.assertEqual(speech.backend, 'piper'); self.assertEqual(speech.spoken_count, 0)

    @patch('src.tts.SpeechOutput._load_piper')
    @patch('src.tts.SpeechOutput._speak_piper')
    @patch('src.tts.sys.platform', 'win32')
    def test_supersedes_old_queued_positions(self, speak, load):
        import threading
        started = threading.Event(); release = threading.Event()
        def speaking(text):
            if text == 'Busy call':
                started.set(); release.wait(2)
        speak.side_effect = speaking
        speech = SpeechOutput(TTSConfig())
        speech._piper_voice = MagicMock(); speech._piper_config_type = MagicMock(); speech.backend = 'piper'
        speech.submit((EngineerMessage('lap:2', Priority.CRITICAL, 'Busy call', 0),))
        self.assertTrue(started.wait(1))
        now = __import__('time').monotonic()
        speech.submit((EngineerMessage('position', Priority.INFORMATION, 'Position eight', now),
                       EngineerMessage('position', Priority.INFORMATION, 'Position nine', now),
                       EngineerMessage('position', Priority.INFORMATION, 'Position ten', now)))
        release.set(); speech._queue.join(); speech.close()
        spoken = [c.args[0] for c in speak.call_args_list]
        self.assertEqual(spoken, ['Busy call', 'Position ten'])
        self.assertEqual(speech.superseded_count, 2)

    @patch('src.tts.SpeechOutput._load_piper')
    @patch('src.tts.SpeechOutput._speak_piper')
    @patch('src.tts.sys.platform', 'win32')
    def test_discards_stale_information_but_keeps_fresh(self, speak, load):
        import time
        speech = SpeechOutput(TTSConfig(information_max_age_s=1.0))
        speech._piper_voice = MagicMock(); speech._piper_config_type = MagicMock(); speech.backend = 'piper'
        speech.submit((EngineerMessage('lap:2', Priority.INFORMATION, 'Old lap', time.monotonic()-5),
                       EngineerMessage('pit:exit', Priority.INFORMATION, 'Fresh pit exit', time.monotonic())))
        speech._queue.join(); speech.close()
        self.assertEqual([c.args[0] for c in speak.call_args_list], ['Fresh pit exit'])
        self.assertEqual(speech.stale_count, 1)

    @patch('src.tts.SpeechOutput._load_piper')
    @patch('src.tts.SpeechOutput._speak_piper')
    @patch('src.tts.sys.platform', 'win32')
    def test_ptt_invalidates_old_noncritical_but_keeps_critical(self, speak, load):
        import threading
        started = threading.Event(); release = threading.Event()
        def speaking(text):
            if text == 'Current call':
                started.set(); release.wait(2)
        speak.side_effect = speaking
        speech = SpeechOutput(TTSConfig())
        speech._piper_voice = MagicMock(); speech._piper_config_type = MagicMock(); speech.backend = 'piper'
        speech.submit((EngineerMessage('x', Priority.INFORMATION, 'Current call', 0),))
        self.assertTrue(started.wait(1))
        speech.submit((EngineerMessage('old-info', Priority.INFORMATION, 'Old info', 0),
                       EngineerMessage('critical', Priority.CRITICAL, 'Critical retained', 0)))
        speech.begin_listening(); release.set()
        speech.prepare_radio_response()
        speech.submit((EngineerMessage('voice:response', Priority.STRATEGY, 'Radio answer', 0),))
        speech.end_listening(); speech._queue.join(); speech.close()
        spoken = [c.args[0] for c in speak.call_args_list]
        self.assertIn('Critical retained', spoken)
        self.assertIn('Radio answer', spoken)
        self.assertNotIn('Old info', spoken)

    def test_radio_rank_driver_answer_is_highest(self):
        now = 0
        voice = EngineerMessage('voice:response', Priority.STRATEGY, 'Gap one second.', now)
        critical = EngineerMessage('flag:local', Priority.CRITICAL, 'Yellow flag.', now)
        assist = EngineerMessage('assist:s_mode', Priority.COACHING, 'S Mode.', now)
        strategy = EngineerMessage('fuel:low', Priority.STRATEGY, 'Fuel low.', now)
        info = EngineerMessage('lap:2', Priority.INFORMATION, 'Lap two.', now)
        self.assertLess(SpeechOutput._radio_rank(voice), SpeechOutput._radio_rank(critical))
        coach = EngineerMessage('coach:corner:3:trail_brake_weak', Priority.COACHING, 'Turn 3: carry the brake deeper into the corner.', now)
        self.assertLess(SpeechOutput._radio_rank(critical), SpeechOutput._radio_rank(strategy))
        self.assertLess(SpeechOutput._radio_rank(strategy), SpeechOutput._radio_rank(info))
        self.assertLess(SpeechOutput._radio_rank(info), SpeechOutput._radio_rank(coach))
        self.assertLess(SpeechOutput._radio_rank(coach), SpeechOutput._radio_rank(assist))

    @patch('src.tts.SpeechOutput._load_piper')
    @patch('src.tts.SpeechOutput._speak_piper')
    @patch('src.tts.sys.platform', 'win32')
    def test_driver_answer_beats_queued_critical_and_assist(self, speak, load):
        import threading
        started = threading.Event(); release = threading.Event()
        def speaking(text):
            if text == 'Busy':
                started.set(); release.wait(2)
        speak.side_effect = speaking
        speech = SpeechOutput(TTSConfig())
        speech._piper_voice = MagicMock(); speech._piper_config_type = MagicMock(); speech.backend = 'piper'
        speech.submit((EngineerMessage('old', Priority.INFORMATION, 'Busy', 0),))
        self.assertTrue(started.wait(1))
        speech.submit((EngineerMessage('flag:local', Priority.CRITICAL, 'Yellow', 0),
                       EngineerMessage('assist:s_mode', Priority.COACHING, 'S Mode.', 0),
                       EngineerMessage('voice:response', Priority.STRATEGY, 'Gap one second.', 0)))
        release.set(); speech._queue.join(); speech.close()
        spoken = [c.args[0] for c in speak.call_args_list]
        self.assertEqual(spoken[1:4], ['Gap one second.', 'Yellow', 'S Mode.'])

    def test_relevance_families_keep_events_but_replace_live_state(self):
        self.assertEqual(SpeechOutput._replaceable_family('position'), 'position')
        self.assertEqual(SpeechOutput._replaceable_family('fuel:low'), 'fuel')
        self.assertEqual(SpeechOutput._replaceable_family('front_wing:80'), 'front_wing')
        self.assertIsNone(SpeechOutput._replaceable_family('pit:enter'))
        self.assertIsNone(SpeechOutput._replaceable_family('tyre_set:9'))
        self.assertIsNone(SpeechOutput._replaceable_family('lap:2'))


if __name__ == '__main__': unittest.main()
