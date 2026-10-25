import logging
import unittest
import re

from voice_line.logging_setup import ConsoleFormatter


class FormatterTests(unittest.TestCase):
    def test_event_and_values_are_highlighted_without_changing_text(self):
        cases = [("daily.voice", "Queued | text='hello world'", "1;36"),
                 ("voice.play", "Started | text='hello world'", "1;34"),
                 ("voice.play", "Completed | audio=2.00s elapsed=2.10s", "1;32"),
                 ("voice.tts", "Generation finished | word='hello' added=4", "1;32")]
        for name, message, event_color in cases:
            record = logging.LogRecord(name, logging.INFO, "", 0, message, (), None)
            colored = ConsoleFormatter(color=True).format(record)
            plain = ConsoleFormatter().format(record)
            self.assertIn(f"\033[{event_color}m{message.split(' | ')[0]}", colored)
            self.assertEqual(re.sub(r"\x1b\[[0-9;]*m", "", colored), plain)
        self.assertIn("word=\033[1;33m'hello'", colored)
        self.assertIn("added=\033[1;33m4", colored)

    def test_quoted_values_keep_embedded_field_names(self):
        record = logging.LogRecord("voice.play", logging.INFO, "", 0,
                                   "Started | text=%r", ("hello count=12 'friend'",), None)
        colored = ConsoleFormatter(color=True).format(record)
        self.assertEqual(re.sub(r"\x1b\[[0-9;]*m", "", colored), ConsoleFormatter().format(record))

    def test_uvicorn_module_aligns_without_becoming_an_error(self):
        formatter = ConsoleFormatter(color=True)
        records = [logging.LogRecord(name, logging.INFO, "", 0, "Ready", (), None)
                   for name in ("daily.app", "uvicorn.error", "daily.tunnel")]
        lines = [formatter.format(record) for record in records]
        self.assertEqual(len({line.index("|") for line in lines}), 1)
        self.assertNotIn("\033[31m", lines[1])

    def test_color_and_plain_output_keep_categories(self):
        for name, category in (("voice.play", "SPEECH"), ("voice.tts", "TTS"), ("voice.build", "BUILD")):
            record = logging.LogRecord(name, logging.INFO, "", 0, "Completed", (), None)
            plain = ConsoleFormatter().format(record)
            colored = ConsoleFormatter(color=True).format(record)
            self.assertIn(category, plain)
            self.assertNotIn("\033[", plain)
            self.assertIn("\033[", colored)
            self.assertFalse(hasattr(record, "category"))

    def test_error_color_does_not_hide_origin(self):
        record = logging.LogRecord("daily.api", logging.ERROR, "", 0, "Failed", (), None)
        record.category = "WEB"
        output = ConsoleFormatter(color=True).format(record)
        self.assertIn("\033[31mERROR", output)
        self.assertIn("\033[35mWEB", output)


if __name__ == "__main__":
    unittest.main()
