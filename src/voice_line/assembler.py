"""文本组装管线：分词 → 预补词 → 逐个取词 → 加音效 → 拼接 → 加头尾。
Text-to-speech assembly pipeline: tokenize, prewarm, process, splice with machine SFX."""

from __future__ import annotations

import re
import random
import sys
from pathlib import Path

from pydub import AudioSegment

from . import db
from .effects import process_word_clip, create_transition, generate_static
from .config import SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS, EFFECTS, INTRO_PATH, INTRO_VOLUME_DB, OUTRO_ENABLED


def _tokenize(text: str) -> list[tuple[str, str]]:
    """分词：返回 [(单词, 分隔符), ...]。保留撇号缩约（如 don't）。"""
    tokens = re.findall(r"(\w+(?:'\w+)?)([^\w]*)", text)
    return tokens


def _normalize(word: str) -> str:
    """归一化：小写 + 去两端空白。"""
    return word.strip().lower()


def _get_clip(word: str) -> AudioSegment | None:
    """取一个词的录音→加效果。从词库取，没有则返回 None（prewarm 已尝试 TTS）。"""
    normalized = _normalize(word)
    if not normalized:
        return None

    clips = db.get_clips(normalized)
    if clips:
        chosen = random.choice(clips)
        clip_path = Path(chosen["file_path"])
        if clip_path.exists():
            clip = AudioSegment.from_file(str(clip_path))
            return process_word_clip(clip)

    # prewarm 已经试过 TTS 且失败了——不再重试，直接跳过
    print(f"  Skipped: '{word}' (not in library)", file=sys.stderr)
    return None


def _prewarm(words: list[str]) -> None:
    """前置预热：提前把词库缺失的词批量 TTS 生成，避免组装时产生静默间隙。"""
    from .tts_fallback import ensure_word, word_failed

    missing = set()
    skipped = set()
    for w in words:
        normalized = _normalize(w)
        if not normalized:
            continue
        if not db.get_clips(normalized):
            if word_failed(normalized):
                skipped.add(normalized)
            else:
                missing.add(normalized)

    if skipped:
        print(f"  Prewarm: {len(skipped)} word(s) already failed — skipping", file=sys.stderr)

    if not missing:
        return

    print(f"  Prewarm: generating {len(missing)} missing word(s)...", file=sys.stderr)
    for w in sorted(missing):
        ensure_word(w)


def assemble(text: str) -> AudioSegment:
    """将文本转换为 Machine 风格音频。缺失的词先预生成。"""
    tokens = _tokenize(text)
    if not tokens:
        return AudioSegment.silent(duration=100, frame_rate=SAMPLE_RATE)

    # 第一步：预生成所有缺失词
    raw_words = [t[0] for t in tokens]
    _prewarm(raw_words)

    segments: list[AudioSegment] = []
    skipped: list[str] = []

    for raw_word, _separator in tokens:
        clip = _get_clip(raw_word)
        if clip is None:
            skipped.append(_normalize(raw_word))
            # 用短促静噪爆音占位，避免死寂
            placeholder = generate_static(
                random.randint(80, 150), volume_db=-18,
            )
            segments.append(placeholder)
            segments.append(create_transition())
            continue

        # 淡入淡出（不超过片段长度的 1/10）
        fade_in = min(EFFECTS["fade_in_ms"], len(clip) // 10)
        fade_out = min(EFFECTS["fade_out_ms"], len(clip) // 10)
        clip = clip.fade_in(fade_in).fade_out(fade_out)
        segments.append(clip)
        segments.append(create_transition())  # 词间过渡

    if skipped:
        unique = list(dict.fromkeys(skipped))  # 去重但保持顺序
        print(f"  Missing: {', '.join(unique)}", file=sys.stderr)

    if not segments:
        return AudioSegment.silent(duration=100, frame_rate=SAMPLE_RATE)

    # 组装语音主体
    body = segments[0]
    for seg in segments[1:]:
        body += seg
    body = body.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS).set_sample_width(SAMPLE_WIDTH)

    # 片头始终加；片尾仅对 ≥4 词句子（且 OUTRO_ENABLED）加
    word_count = len([t for t in tokens if _normalize(t[0])])
    intro_path = Path(INTRO_PATH)

    if intro_path.exists():
        sfx = AudioSegment.from_file(str(intro_path))
        sfx = sfx.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS).set_sample_width(SAMPLE_WIDTH)
        sfx = sfx + INTRO_VOLUME_DB
        gap = AudioSegment.silent(duration=60, frame_rate=SAMPLE_RATE)
        if word_count >= 4 and OUTRO_ENABLED:
            return sfx + gap + body + gap + sfx  # 头 + 尾
        else:
            return sfx + gap + body               # 仅头

    return body


def assemble_to_file(text: str, output_path: str) -> None:
    """组装并导出为 WAV 文件。"""
    audio = assemble(text)
    audio.export(output_path, format="wav")
