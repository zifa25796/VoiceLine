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
        import tempfile
        import subprocess
        import os

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            audio.export(tmp_path, format="wav")
            # Use PowerShell Media.SoundPlayer to play (works headless)
            ps = (
                f"(New-Object Media.SoundPlayer '{tmp_path}').PlaySync();"
                f"Remove-Item '{tmp_path}'"
            )
            subprocess.run(
                ["powershell", "-Command", ps],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
