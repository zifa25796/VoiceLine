import unittest
from unittest.mock import MagicMock, patch

from pydub import AudioSegment

from voice_line import assembler, effects, tts_fallback


class PipelineTests(unittest.TestCase):
    def test_transition_keeps_gap_with_and_without_noise(self):
        for probability in (0.0, 1.0):
            with self.subTest(probability=probability), patch.object(
                effects.random, "random", return_value=probability
            ), patch.dict(effects.EFFECTS, gap_ms=(250, 250)):
                self.assertEqual(len(effects.create_transition()), 250)

    def test_cached_clip_does_not_wait_for_refresh(self):
        cached = AudioSegment.silent(duration=100)
        with patch.object(assembler.db, "get_clips", return_value=[
            {"id": 1, "play_count": 10, "file_path": __file__}
        ]), patch.object(assembler.db, "record_play"), patch.object(
            assembler, "schedule_refresh"
        ) as refresh, patch.object(
            assembler.AudioSegment, "from_file", return_value=cached
        ), patch.object(assembler, "process_word_clip", side_effect=lambda clip: clip):
            self.assertIs(assembler._get_clip("hello"), cached)
            refresh.assert_called_once_with("hello", 1)

    def test_missing_word_returns_after_first_voice(self):
        clip = MagicMock()
        with patch.object(tts_fallback.db, "get_clips", return_value=[]), patch.object(
            tts_fallback.db, "word_sources", return_value=set()
        ), patch.object(tts_fallback.db, "make_clip_path", return_value="unused.wav"), patch.object(
            tts_fallback.db, "add_word"
        ), patch.object(tts_fallback, "_generate_sync", return_value=(clip, "test")) as generate, patch.object(
            tts_fallback, "_schedule_word_job"
        ) as schedule:
            self.assertIs(tts_fallback.ensure_word("hello"), clip)
            generate.assert_called_once()
            schedule.assert_called_once_with("hello", tts_fallback.ensure_word, "hello", fill=True)

    def test_background_jobs_are_deduplicated(self):
        with patch.object(tts_fallback.threading, "Thread") as thread:
            try:
                tts_fallback._schedule_word_job("test-job", lambda: None)
                tts_fallback._schedule_word_job("test-job", lambda: None)
                thread.assert_called_once()
                self.assertTrue(thread.call_args.kwargs["daemon"])
                thread.call_args.kwargs["target"]()
                self.assertNotIn("test-job", tts_fallback._pending_words)
            finally:
                tts_fallback._pending_words.discard("test-job")


if __name__ == "__main__":
    unittest.main()
