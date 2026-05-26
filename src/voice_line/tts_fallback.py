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


def _generate_sync(word: str, voices: list[str]) -> AudioSegment | None:
    """用 edge-tts 合成，失败自动换语音重试。
    每次重试用不同语音 + 渐长退避，最大程度绕开限流。"""
    try:
        import edge_tts
    except ImportError:
        print(f"  TTS: edge-tts not installed, cannot generate '{word}'", file=sys.stderr)
        return None

    async def _gen(v: str):
        communicate = edge_tts.Communicate(word, v)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await communicate.save(tmp_path)
            audio = AudioSegment.from_file(tmp_path)
            audio = audio.set_frame_rate(22050).set_channels(1).set_sample_width(2)
            return _trim_silence(audio)
        finally:
            os.unlink(tmp_path)

    for i, voice in enumerate(voices):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda v=voice: asyncio.run(_gen(v)))
                    return future.result(timeout=8)
            return asyncio.run(_gen(voice))
        except Exception:
            if i < len(voices) - 1:
                # 每次退避更久：2s → 4s → 8s
                delay = 2.0 * (i + 1)
                time.sleep(delay)
    return None


def ensure_word(word: str, voices: list[str] | None = None) -> AudioSegment | None:
    """缺失时即时合成一个词并入库。尝试最多 3 种不同语音。"""
    existing = db.get_clips(word)
    if existing:
        from pathlib import Path
        path = Path(existing[0]["file_path"])
        if path.exists():
            return AudioSegment.from_file(str(path))

    if voices is None:
        voices = random.sample(VOICES, min(3, len(VOICES)))

    print(f"  TTS: '{word}' ...", file=sys.stderr, end="", flush=True)
    clip = _generate_sync(word, voices)
    if clip is None:
        print(" FAILED", file=sys.stderr)
        return None

    voice = voices[0]  # 用第一个成功的语音标记来源
    clip_hash = hashlib.sha1(f"tts:{word}:{voice}".encode()).hexdigest()[:12]
    clip_path = db.make_clip_path(word, clip_hash)
    clip.export(clip_path, format="wav")
    db.add_word(
        word_text=word, original_text=word, file_path=clip_path,
        source_audio=f"tts:{voice}", start_time=0, end_time=0,
        duration=len(clip) / 1000, confidence=1.0, quality_score=1.0,
    )
    print(f" ok ({voice.split('-')[2]})", file=sys.stderr)
    return clip
