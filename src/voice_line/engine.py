from __future__ import annotations

import sys

from . import db
from .assembler import assemble, assemble_to_file
from .analyzer import missing_words, coverage_stats, suggest_targets


class VoiceLine:
    """Person of Interest — The Machine style speech assembler."""

    def __init__(self):
        db.init_db()

    # ── Speaking ──────────────────────────────────────────────

    def speak(self, text: str, output: str | None = None) -> None:
        """Assemble text into Machine-style speech. Missing words are
        auto-generated via TTS and saved to the library."""
        audio = assemble(text)

        if output:
            audio.export(output, format="wav")
            print(f"Saved to {output}", file=sys.stderr)
        else:
            self._play(audio)

    def speak_to_file(self, text: str, output_path: str) -> None:
        assemble_to_file(text, output_path)

    # ── Analysis ──────────────────────────────────────────────

    def missing(self, top: int = 20) -> list[tuple[int, str]]:
        return missing_words(top)

    def stats(self) -> str:
        return suggest_targets()

    def coverage(self) -> dict:
        return coverage_stats()

    def db_stats(self) -> dict:
        return db.get_stats()

    # ── Playback ──────────────────────────────────────────────

    @staticmethod
    def _play(audio) -> None:
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            print("Install sounddevice to play audio: pip install sounddevice", file=sys.stderr)
            return

        samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
        if audio.channels > 1:
            samples = samples.reshape((-1, audio.channels))
        max_val = float(2 ** (audio.sample_width * 8 - 1))
        samples = samples / max_val
        sd.play(samples.astype(np.float32), samplerate=audio.frame_rate)
        sd.wait()
