"""TTS 实时补词：词库未覆盖时用 edge-tts 在线合成。
On-the-fly TTS generation for words missing from the library."""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
import logging
import tempfile
import time
import threading

import numpy as np
from pydub import AudioSegment

from . import db
from .config import MAX_CLIPS_PER_WORD, REFRESH_RETRY_SECONDS

# 2026-10 起微软对旧 TTS 主机区域级返回 403（edge-tts 7.2.8 未适配），手动切到新主机
try:
    import edge_tts.communicate as _communicate
    from edge_tts.constants import TRUSTED_CLIENT_TOKEN as _CLIENT_TOKEN
    if _communicate.WSS_URL.startswith("wss://speech.platform.bing.com"):
        _communicate.WSS_URL = (
            "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
            f"?Ocp-Apim-Subscription-Key={_CLIENT_TOKEN}"
        )
except ImportError:
    pass

logger = logging.getLogger("voice.tts")

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


def _generate_sync(word: str, voices: list[str]) -> tuple[AudioSegment, str] | None:
    """用 edge-tts 合成，失败自动换语音重试。
    每次重试用不同语音 + 渐长退避，最大程度绕开限流。
    返回 (音频, 实际成功的语音)。"""
    try:
        import edge_tts
    except ImportError:
        logger.error("Unavailable | edge-tts not installed word=%r", word)
        return None

    async def _gen(v: str):
        communicate = edge_tts.Communicate(word, v)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await asyncio.wait_for(communicate.save(tmp_path), timeout=10)
            audio = AudioSegment.from_file(tmp_path)
            audio = audio.set_frame_rate(22050).set_channels(1).set_sample_width(2)
            return _trim_silence(audio)
        finally:
            os.unlink(tmp_path)

    import concurrent.futures
    for i, voice in enumerate(voices):
        try:
            # 始终在独立线程中跑 asyncio.run()，避免与 uvicorn 等已有
            # 事件循环冲突——asyncio.run() 不能从运行中的事件循环调用。
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda v=voice: asyncio.run(_gen(v)))
                return future.result(), voice
        except Exception as exc:
            logger.warning("Attempt failed | word=%r voice=%s reason=%s", word, voice, type(exc).__name__)
            if i < len(voices) - 1:
                delay = 2.0 * (i + 1)
                time.sleep(delay)
    return None


def ensure_word(word: str, *, fill: bool = False) -> AudioSegment | None:
    existing = db.get_clips(word)
    if existing and not fill:
        from pathlib import Path
        path = Path(existing[0]["file_path"])
        if path.exists():
            return AudioSegment.from_file(str(path))

    used = db.word_sources(word)
    available = [v for v in VOICES if f"tts:{v}" not in used]
    random.shuffle(available)

    logger.info("Generating | word=%r mode=%s", word, "fill" if fill else "first")
    first_clip = None
    added = 0
    for voice in available[:MAX_CLIPS_PER_WORD - len(used)]:
        result = _generate_sync(word, [voice])
        if result is None:
            continue
        clip, voice_used = result
        clip_hash = hashlib.sha1(f"tts:{word}:{voice_used}".encode()).hexdigest()[:12]
        clip_path = db.make_clip_path(word, clip_hash)
        clip.export(clip_path, format="wav")
        db.add_word(
            word_text=word, original_text=word, file_path=clip_path,
            source_audio=f"tts:{voice_used}", start_time=0, end_time=0,
            duration=len(clip) / 1000, confidence=1.0, quality_score=1.0,
        )
        added += 1
        if first_clip is None:
            first_clip = clip
        if not fill:
            _schedule_word_job(word, ensure_word, word, fill=True)
            break
        time.sleep(0.3)  # 限流保护：不连续请求微软接口
    logger.log(logging.INFO if added else logging.WARNING, "Generation finished | word=%r added=%s", word, added)
    return first_clip


_recent_refresh: dict[str, float] = {}
_pending_words: set[str] = set()
_pending_lock = threading.Lock()


def _schedule_word_job(word, operation, *args, **kwargs):
    with _pending_lock:
        if word in _pending_words:
            return
        _pending_words.add(word)

    def run():
        try:
            operation(*args, **kwargs)
        except Exception:
            logger.exception("Background job failed | word=%r", word)
        finally:
            with _pending_lock:
                _pending_words.discard(word)

    threading.Thread(target=run, daemon=True).start()


def schedule_refresh(word: str, stale_id: int) -> None:
    _schedule_word_job(word, refresh_clip, word, stale_id)


def refresh_clip(word: str, stale_id: int) -> AudioSegment | None:
    """重新合成一条录音替换高频词播放次数最多的剪辑，让重复用词持续换新声音。
    每次尝试都进入冷却期，避免频繁联网刷新。"""
    now = time.time()
    if now - _recent_refresh.get(word, 0.0) < REFRESH_RETRY_SECONDS:
        return None
    _recent_refresh[word] = now

    used = db.word_sources(word)
    available = [v for v in VOICES if f"tts:{v}" not in used] or VOICES
    random.shuffle(available)
    result = _generate_sync(word, available[:3])
    if result is None:
        logger.warning("Refresh failed | word=%r", word)
        return None
    clip, voice = result
    clip_hash = hashlib.sha1(f"tts:{word}:{voice}".encode()).hexdigest()[:12]
    clip_path = db.make_clip_path(word, clip_hash)
    clip.export(clip_path, format="wav")
    db.replace_clip(stale_id, clip_path, f"tts:{voice}")
    logger.info("Refreshed | word=%r voice=%s", word, voice)
    return clip
