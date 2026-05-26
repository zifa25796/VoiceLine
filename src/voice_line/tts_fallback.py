"""TTS 实时补词：词库未覆盖时用 edge-tts 在线合成。
On-the-fly TTS generation for words missing from the library."""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
import sys
import tempfile
import time

import numpy as np
from pydub import AudioSegment

from . import db

# 14 种 en-US / en-GB 神经语音，每次随机选择
VOICES = [
    "en-US-AvaMultilingualNeural",
    "en-US-AndrewMultilingualNeural",
    "en-US-EmmaMultilingualNeural",
    "en-US-BrianMultilingualNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
    "en-US-AnaNeural",
    "en-US-ChristopherNeural",
    "en-US-EricNeural",
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-US-MichelleNeural",
    "en-US-RogerNeural",
    "en-US-SteffanNeural",
]

# 当前会话中已确认 TTS 失败的词，避免重复尝试
_failed_words: set[str] = set()


def word_failed(word: str) -> bool:
    """检查该词是否已在当前会话中 TTS 失败过。"""
    return word in _failed_words


def reset_failed() -> None:
    """清空失败记录（用于新会话或重试）。"""
    _failed_words.clear()


def _trim_silence(audio: AudioSegment) -> AudioSegment:
    """用能量阈值去除首尾静音，保留 30ms 边缘。"""
    samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
    if len(samples) < 100:
        return audio
    sr = audio.frame_rate
    threshold = max(np.max(np.abs(samples)) * 0.03, 1.0)
    above = np.abs(samples) > threshold
    if not above.any():
        return audio
    first = int(np.argmax(above))
    last = int(len(above) - 1 - np.argmax(above[::-1]))
    if first >= last:
        return audio
    pad = int(sr * 0.03)
    start = max(0, first - pad)
    end = min(len(samples), last + pad)
    if end <= start:
        return audio
    return audio[int(start * 1000 / sr):int(end * 1000 / sr)]


def _generate_sync(word: str, voice: str, retries: int = 2) -> AudioSegment | None:
    """同步包装 edge-tts 合成（重试 2 次，随机退避）。
    超时 5s 即可——edge-tts 正常情况下 1-2s 返回，超 5s 基本是被限流。"""
    try:
        import edge_tts
    except ImportError:
        print(f"  TTS: edge-tts not installed, cannot generate '{word}'", file=sys.stderr)
        return None

    async def _gen():
        communicate = edge_tts.Communicate(word, voice)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await communicate.save(tmp_path)
            audio = AudioSegment.from_file(tmp_path)
            audio = audio.set_frame_rate(22050).set_channels(1).set_sample_width(2)
            return _trim_silence(audio)
        finally:
            os.unlink(tmp_path)

    for attempt in range(retries):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已有事件循环 → 在独立线程中开新循环
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.run(_gen()))
                    return future.result(timeout=5)
            return asyncio.run(_gen())
        except Exception:
            if attempt < retries - 1:
                delay = random.uniform(1.0, 2.5)
                time.sleep(delay)
    return None


def ensure_word(word: str) -> AudioSegment | None:
    """缺失时即时合成一个词并入库。仅生成 1 条以免触发限流。
    如果该词已在当前会话中 TTS 失败过，则直接跳过。"""
    existing = db.get_clips(word)
    if existing:
        from pathlib import Path
        path = Path(existing[0]["file_path"])
        if path.exists():
            return AudioSegment.from_file(str(path))

    # 当前会话已确认失败，不再重试
    if word in _failed_words:
        return None

    print(f"  TTS: generating '{word}' ...", file=sys.stderr, end="", flush=True)
    voice = random.choice(VOICES)
    clip = _generate_sync(word, voice)
    if clip is None:
        _failed_words.add(word)
        print(" FAILED (rate-limited or network error)", file=sys.stderr)
        return None

    clip_hash = hashlib.sha1(f"tts:{word}:{voice}".encode()).hexdigest()[:12]
    clip_path = db.make_clip_path(word, clip_hash)
    clip.export(clip_path, format="wav")
    db.add_word(
        word_text=word, original_text=word, file_path=clip_path,
        source_audio=f"tts:{voice}", start_time=0, end_time=0,
        duration=len(clip) / 1000, confidence=1.0, quality_score=1.0,
    )
    print(f" done ({voice.split('-')[2]})", file=sys.stderr)
    return clip
