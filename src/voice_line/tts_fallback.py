"""On-the-fly TTS generation for words missing from the library."""

import asyncio
import hashlib
import os
import random
import tempfile

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


def _generate_sync(word: str, voice: str, retries: int = 3) -> AudioSegment | None:
    """Generate a single word via edge-tts with retry on failure."""
    try:
        import edge_tts
    except ImportError:
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
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.run(_gen()))
                    return future.result(timeout=12)
            return asyncio.run(_gen())
        except Exception:
            if attempt < retries - 1:
                import time
                time.sleep(2.0)
    return None


def ensure_word(word: str) -> AudioSegment | None:
    """Return a clip for `word`, generating exactly 1 TTS clip if missing.
    The seed script fills up to 3 clips later — prewarm only needs 1 to avoid silence."""
    existing = db.get_clips(word)
    if existing:
        from pathlib import Path
        path = Path(existing[0]["file_path"])
        if path.exists():
            return AudioSegment.from_file(str(path))

    voice = random.choice(VOICES)
    clip = _generate_sync(word, voice)
    if clip is None:
        return None
    clip_hash = hashlib.sha1(f"tts:{word}:{voice}".encode()).hexdigest()[:12]
    clip_path = db.make_clip_path(word, clip_hash)
    clip.export(clip_path, format="wav")
    db.add_word(
        word_text=word, original_text=word, file_path=clip_path,
        source_audio=f"tts:{voice}", start_time=0, end_time=0,
        duration=len(clip) / 1000, confidence=1.0, quality_score=1.0,
    )
    return clip
