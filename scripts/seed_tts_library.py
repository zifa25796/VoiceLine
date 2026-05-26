"""批量预生成词库：用多个 edge-tts 语音为常用词各生成 3 条录音。
Pre-generate a clean word library using multiple edge-tts voices.

Usage:  python scripts/seed_tts_library.py
        python scripts/seed_tts_library.py --top 500
"""

from __future__ import annotations

import sys
import os
import asyncio
import hashlib
import tempfile
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pydub import AudioSegment
from voice_line import db, frequency

# 14 种 edge-tts 英语语音，用于丰富音色
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

DEFAULT_TOP = 300  # 默认生成前 300 个高频词


def _trim_silence(audio: AudioSegment) -> AudioSegment:
    """用能量阈值切除首尾静音，保留 30ms 边缘。"""
    import numpy as np
    samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
    if len(samples) < 100:
        return audio
    sr = audio.frame_rate
    abs_s = np.abs(samples)
    threshold = max(np.max(abs_s) * 0.03, 1.0)
    above = abs_s > threshold
    if not above.any():
        return audio
    first = int(np.argmax(above))
    last = int(len(above) - 1 - np.argmax(above[::-1]))
    if first >= last:
        return audio
    pad_samples = int(sr * 0.03)
    start = max(0, first - pad_samples)
    end = min(len(samples), last + pad_samples)
    if end <= start:
        return audio
    # pydub 切片用毫秒，需要从采样点索引换算
    return audio[int(start * 1000 / sr):int(end * 1000 / sr)]


async def generate_word(word: str, voice: str, output_path: str, retries: int = 3) -> bool:
    """TTS 合成单个词并导出。遇到限流自动重试。"""
    import edge_tts

    for attempt in range(retries):
        try:
            communicate = edge_tts.Communicate(word, voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                await communicate.save(tmp_path)
                audio = AudioSegment.from_file(tmp_path)
                audio = audio.set_frame_rate(22050).set_channels(1).set_sample_width(2)
                audio = _trim_silence(audio)
                audio.export(output_path, format="wav")
                return True
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            if attempt < retries - 1:
                wait = (attempt + 1) * 1.5
                await asyncio.sleep(wait)
            else:
                print(f"\n  ERROR ({word}/{voice}): {e}")
                return False
    return False


async def main_async(top_n: int):
    vl = None
    from voice_line import VoiceLine
    vl = VoiceLine()

    words = frequency.FREQUENCY_LIST[:top_n]
    total = len(words) * min(3, len(VOICES))
    done = 0

    print(f"Generating {len(words)} words x up to 3 voices each...")
    print(f"Voices: {len(VOICES)} different edge-tts voices\n")

    for i, word in enumerate(words):
        if db.word_is_full(word):
            continue

        # 每个词随机选 3 种不同语音
        chosen = random.sample(VOICES, min(3, len(VOICES)))
        for voice in chosen:
            clip_hash = hashlib.sha1(
                f"tts:{word}:{voice}".encode()
            ).hexdigest()[:12]
            clip_path = db.make_clip_path(word, clip_hash)

            await asyncio.sleep(0.3)  # 限流保护：不连续请求微软接口
            success = await generate_word(word, voice, clip_path)
            if success:
                db.add_word(
                    word_text=word, original_text=word,
                    file_path=clip_path, source_audio=f"tts:{voice}",
                    start_time=0, end_time=0, duration=0,
                    confidence=1.0, quality_score=1.0,  # TTS 质量最高
                )
                done += 1

            print(f"\r  [{i+1:4d}/{len(words)}] {word:20s}  "
                  f"+{db.get_stats()['total_clips']:5d} clips",
                  end="", flush=True)

    print(f"\n\n{vl.stats()}")
    print(f"\nDone. {done} TTS clips generated.")


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=DEFAULT_TOP,
                   help=f"Number of common words to generate (default: {DEFAULT_TOP})")
    args = p.parse_args()
    asyncio.run(main_async(args.top))


if __name__ == "__main__":
    main()
