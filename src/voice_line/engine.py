import sys
from pathlib import Path

from . import db
from .indexer import index_file, index_directory
from .assembler import assemble, assemble_to_file
from .analyzer import missing_words, coverage_stats, suggest_targets


class VoiceLine:
    """Main entry point for the VoiceLine TTS system."""

    def __init__(self):
        db.init_db()

    # ── Indexing ──────────────────────────────────────────────

    def index(self, path: str, progress_callback=None) -> dict:
        """Index a single audio file or directory of audio files."""
        p = Path(path)
        if p.is_dir():
            return index_directory(str(p), progress_callback)
        else:
            return index_file(str(p), progress_callback)

    # ── Speaking ──────────────────────────────────────────────

    def speak(self, text: str, output: str | None = None) -> list[str]:
        """
        Assemble text into Machine-style audio and play or save it.

        Args:
            text: The sentence to speak.
            output: If given, save to this .wav path instead of playing.

        Returns:
            List of words that were missing from the library.
        """
        audio, missing = assemble(text, missing_callback=lambda w: print(
            f"  [missing] '{w}'", file=sys.stderr
        ))

        if output:
            audio.export(output, format="wav")
            return missing

        self._play(audio)
        return missing

    def speak_to_file(self, text: str, output_path: str) -> list[str]:
        """Assemble text and save to file."""
        return assemble_to_file(text, output_path)

    # ── Analysis ──────────────────────────────────────────────

    def missing(self, top: int = 20) -> list[tuple[int, str]]:
        """Return top N missing common words."""
        return missing_words(top)

    def stats(self) -> str:
        """Return formatted stats about the word library."""
        return suggest_targets()

    def coverage(self) -> dict:
        """Return coverage statistics."""
        return coverage_stats()

    def db_stats(self) -> dict:
        """Return raw database stats."""
        return db.get_stats()

    # ── Helpers ───────────────────────────────────────────────

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
