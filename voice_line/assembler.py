import re
import random
from pathlib import Path

from pydub import AudioSegment

from . import db
from .effects import process_word_clip, create_transition
from .config import SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS


def _tokenize(text: str) -> list[tuple[str, str]]:
    """
    Split text into (word, separator) pairs.
    Separator is any whitespace/punctuation between words.
    """
    tokens = re.findall(r"(\w+(?:'\w+)?)([^\w]*)", text)
    return tokens


def _normalize(word: str) -> str:
    return word.strip().lower()


def assemble(text: str, missing_callback=None) -> tuple[AudioSegment, list[str]]:
    """
    Build an AudioSegment from text by looking up each word in the library.

    Returns:
        (audio, missing_words) — combined AudioSegment and list of missing words
    """
    tokens = _tokenize(text)
    if not tokens:
        return AudioSegment.silent(duration=100, frame_rate=SAMPLE_RATE), []

    segments: list[AudioSegment] = []
    missing_words: list[str] = []

    for raw_word, separator in tokens:
        normalized = _normalize(raw_word)
        if not normalized:
            continue

        clips = db.get_clips(normalized)

        if not clips:
            missing_words.append(normalized)
            if missing_callback:
                missing_callback(normalized)
            silence_ms = max(80, len(raw_word) * 100)  # rough duration guess
            clip = AudioSegment.silent(duration=silence_ms, frame_rate=SAMPLE_RATE)
        else:
            chosen = random.choice(clips)
            clip_path = chosen["file_path"]
            if not Path(clip_path).exists():
                missing_words.append(normalized)
                if missing_callback:
                    missing_callback(normalized)
                silence_ms = max(80, len(raw_word) * 100)
                clip = AudioSegment.silent(duration=silence_ms, frame_rate=SAMPLE_RATE)
            else:
                clip = AudioSegment.from_file(clip_path)
                clip = process_word_clip(clip)

        segments.append(clip)

        transition = create_transition()
        segments.append(transition)

    if not segments:
        return AudioSegment.silent(duration=100, frame_rate=SAMPLE_RATE), missing_words

    result = segments[0]
    for seg in segments[1:]:
        result += seg

    result = result.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS).set_sample_width(SAMPLE_WIDTH)

    return result, missing_words


def assemble_to_file(text: str, output_path: str, missing_callback=None) -> list[str]:
    """Assemble text to audio and save to file. Returns list of missing words."""
    audio, missing = assemble(text, missing_callback)
    audio.export(output_path, format="wav")
    return missing
