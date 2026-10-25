import logging
import sys
import os
import re


class ConsoleFormatter(logging.Formatter):
    COLORS = {"LOCAL": "36", "WEB": "35", "SPEECH": "32", "TTS": "34", "BUILD": "34", "SYSTEM": "37"}
    FIELDS = re.compile(r"\b(word|text|count|added|audio|elapsed|voice|path|id|status|client|mode|reason|missing)=(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|.*?)(?=\s+\w+=|$)")

    def __init__(self, color=False):
        super().__init__("[%(asctime)s] %(levelname)-7s %(category)-7s %(name)-16s | %(message)s", datefmt="%H:%M:%S")
        self.color = color

    def format(self, record):
        import copy

        record = copy.copy(record)
        category = getattr(record, "category", None)
        if category is None:
            category = {"voice.play": "SPEECH", "daily.voice": "SPEECH",
                        "voice.tts": "TTS", "voice.build": "BUILD"}.get(record.name, "SYSTEM")
        record.category = category
        if self.color:
            message = record.getMessage()
            event, separator, details = message.partition(" | ")
            code = "37"
            if record.levelno >= logging.ERROR:
                code = "1;31"
            elif record.levelno >= logging.WARNING:
                code = "1;33"
            elif event in ("Completed", "Saved", "Refreshed", "Generation finished"):
                code = "1;32"
            elif event == "Queued":
                code = "1;36"
            elif event == "Request":
                code = "1;35" if category == "WEB" else "1;36"
            elif event in ("Started", "Generating", "Preparing missing words"):
                code = "1;34"

            def highlight(match):
                key, value = match.groups()
                value_code = "1;37"
                if key in ("word", "count", "added", "missing"):
                    value_code = "1;33"
                elif key in ("voice", "path", "id", "client", "mode"):
                    value_code = "36"
                elif key in ("audio", "elapsed"):
                    value_code = "1;32"
                elif key == "status":
                    value_code = "1;31" if value.startswith("5") else "1;33" if value.startswith("4") else "1;32"
                return f"{key}=\033[{value_code}m{value}\033[0m"

            details = self.FIELDS.sub(highlight, details)
            record.msg = f"\033[{code}m{event}\033[0m{separator}{details}"
            record.args = ()
            record.category = f"\033[{self.COLORS.get(category, '37')}m{category:<7}\033[0m"
            if record.levelno >= logging.WARNING:
                code = "31" if record.levelno >= logging.ERROR else "33"
                record.levelname = f"\033[{code}m{record.levelname:<7}\033[0m"
        return super().format(record)


def configure_logging():
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ConsoleFormatter(color=sys.stderr.isatty() and "NO_COLOR" not in os.environ))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
