"""VoiceLine 主入口：组装、播放、分析。
Main API: assemble speech, playback, and library analysis."""

from __future__ import annotations

import logging
import time

from . import db
from .assembler import assemble
from .analyzer import missing_words, coverage_stats, suggest_targets
from .logging_setup import configure_logging

logger = logging.getLogger("voice.play")


class VoiceLine:
    """疑犯追踪「机器」风格语音合成器。"""

    def __init__(self):
        configure_logging()
        db.init_db()
        db.ensure_word_summary_view()

    # ── 语音合成 Speaking ────────────────────────────────────

    def speak(self, text: str, output: str | None = None) -> None:
        """将文本合成为 Machine 风格语音并播放或保存。
        缺失的词自动 TTS 生成并入库。"""
        started = time.monotonic()
        logger.info("Started | text=%r", text)
        try:
            audio = assemble(text)
            if output:
                audio.export(output, format="wav")
                logger.info("Saved | path=%s", output)
            else:
                self._play(audio)
            logger.info("Completed | audio=%.2fs elapsed=%.2fs", len(audio) / 1000, time.monotonic() - started)
        except Exception:
            logger.exception("Failed | text=%r", text)
            raise

    def speak_to_file(self, text: str, output_path: str) -> None:
        self.speak(text, output=output_path)

    # ── 词库分析 Analysis ─────────────────────────────────────

    def missing(self, top: int = 20) -> list[tuple[int, str]]:
        return missing_words(top)

    def stats(self) -> str:
        return suggest_targets()

    def coverage(self) -> dict:
        return coverage_stats()

    def db_stats(self) -> dict:
        return db.get_stats()

    def list_words(self, search: str = "", limit: int = 50,
                   offset: int = 0, sort_by: str = "word_text") -> tuple[list[dict], int]:
        return db.list_words(search=search, offset=offset, limit=limit, sort_by=sort_by)

    # ── 播放 Playback ─────────────────────────────────────────

    @staticmethod
    def _play(audio) -> None:
        import sounddevice as sd
        import numpy as np

        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        max_val = 2 ** (audio.sample_width * 8 - 1)
        samples = samples / max_val
        if audio.channels > 1:
            samples = samples.reshape(-1, audio.channels)

        sd.play(samples, samplerate=audio.frame_rate)
        sd.wait()
