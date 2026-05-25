import re
import random
from pathlib import Path

from pydub import AudioSegment

from . import db
from .effects import process_word_clip, create_transition
from .config import SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS, EFFECTS, INTRO_PATH, INTRO_VOLUME_DB


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens = re.findall(r"(\w+(?:'\w+)?)([^\w]*)", text)
    return tokens


def _normalize(word: str) -> str:
    return word.strip().lower()


def _get_clip(word: str) -> AudioSegment | None:
    """Get a processed clip for a word, trying DB first then TTS fallback."""
    normalized = _normalize(word)
    if not normalized:
        return None

    # Try existing library
    clips = db.get_clips(normalized)
    if clips:
        chosen = random.choice(clips)
        clip_path = Path(chosen["file_path"])
        if clip_path.exists():
            clip = AudioSegment.from_file(str(clip_path))
            return process_word_clip(clip)

    # On-the-fly TTS generation
    from .tts_fallback import ensure_word
    clip = ensure_word(normalized)
    if clip is not None:
        return process_word_clip(clip)

    return None


def assemble(text: str) -> AudioSegment:
    """Build Machine-style audio from text. Missing words are TTS-generated on the fly."""
    tokens = _tokenize(text)
    if not tokens:
        return AudioSegment.silent(duration=100, frame_rate=SAMPLE_RATE)

    segments: list[AudioSegment] = []

    for raw_word, _separator in tokens:
        clip = _get_clip(raw_word)
        if clip is None:
            continue

        fade_in = min(EFFECTS["fade_in_ms"], len(clip) // 10)
        fade_out = min(EFFECTS["fade_out_ms"], len(clip) // 10)
        clip = clip.fade_in(fade_in).fade_out(fade_out)
        segments.append(clip)
        segments.append(create_transition())

    if not segments:
        return AudioSegment.silent(duration=100, frame_rate=SAMPLE_RATE)

    # Build speech body
    body = segments[0]
    for seg in segments[1:]:
        body += seg
    body = body.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS).set_sample_width(SAMPLE_WIDTH)

    # Prepend Machine intro sound
    intro_path = Path(INTRO_PATH)
    if intro_path.exists():
        intro = AudioSegment.from_file(str(intro_path))
        intro = intro.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS).set_sample_width(SAMPLE_WIDTH)
        intro = intro + INTRO_VOLUME_DB
        # Add a short gap between intro and speech
        gap = AudioSegment.silent(duration=120, frame_rate=SAMPLE_RATE)
        return intro + gap + body

    return body


def assemble_to_file(text: str, output_path: str) -> None:
    audio = assemble(text)
    audio.export(output_path, format="wav")
