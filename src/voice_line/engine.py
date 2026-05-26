"""VoiceLine 主入口：组装、播放、分析。
Main API: assemble speech, playback, and library analysis."""

from __future__ import annotations

import sys

from . import db
from .assembler import assemble, assemble_to_file
from .analyzer import missing_words, coverage_stats, suggest_targets


class VoiceLine:
    """疑犯追踪「机器」风格语音合成器。"""

    def __init__(self):
        db.init_db()
        db.ensure_word_summary_view()

    # ── 语音合成 Speaking ────────────────────────────────────

    def speak(self, text: str, output: str | None = None) -> None:
        """将文本合成为 Machine 风格语音并播放或保存。
        缺失的词自动 TTS 生成并入库。"""
        audio = assemble(text)

        if output:
            audio.export(output, format="wav")
            print(f"Saved to {output}", file=sys.stderr)
        else:
            self._play(audio)

    def speak_to_file(self, text: str, output_path: str) -> None:
        assemble_to_file(text, output_path)

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
        """将 AudioSegment 写入临时文件，通过 PowerShell Media.SoundPlayer 播放。
        PlaySync 在没有消息泵的环境（MCP）中不可靠，故用 Play + Start-Sleep。"""
        import tempfile
        import subprocess
        import os

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            audio.export(tmp_path, format="wav")
            duration_sec = len(audio) / 1000 + 1.5  # 留缓冲避免提前截断
            ps = (
                f"$p = New-Object Media.SoundPlayer '{tmp_path}';"
                f"$p.Play();"
                f"Start-Sleep -Seconds {duration_sec:.1f};"
                f"$p.Stop();"
                f"$p.Dispose();"
                f"Remove-Item '{tmp_path}'"
            )
            subprocess.run(
                ["powershell", "-Command", ps],
                capture_output=True, timeout=int(duration_sec + 10),
            )
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
