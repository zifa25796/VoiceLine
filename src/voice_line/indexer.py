import os
import hashlib
import re
from pathlib import Path

from pydub import AudioSegment

from .config import SUPPORTED_FORMATS
from . import db


def _normalize_word(text: str) -> str:
    """Normalize: lowercase, strip surrounding punctuation, collapse whitespace."""
    text = text.strip().lower()
    text = re.sub(r'^[^\w]+|[^\w]+$', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _load_whisper_model():
    from faster_whisper import WhisperModel
    from .config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
    return WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE
    )


def index_file(audio_path: str, progress_callback=None) -> dict:
    """
    Process a single audio file: transcribe, extract word clips, add to library.

    Returns:
        dict with keys: file, words_found, words_added, words_skipped_full, words_skipped_empty
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {path.suffix}. Supported: {SUPPORTED_FORMATS}")

    source_name = path.name
    audio = AudioSegment.from_file(str(path))
    model = _load_whisper_model()

    segments, info = model.transcribe(str(path), word_timestamps=True)

    stats = {"words_found": 0, "words_added": 0, "words_skipped_full": 0, "words_skipped_empty": 0}

    for segment in segments:
        if segment.words is None:
            continue
        for word in segment.words:
            raw = word.word.strip()
            normalized = _normalize_word(raw)
            if not normalized:
                stats["words_skipped_empty"] += 1
                continue

            stats["words_found"] += 1

            if db.word_is_full(normalized):
                stats["words_skipped_full"] += 1
                continue

            start_s = word.start
            end_s = word.end
            duration = end_s - start_s

            if duration <= 0.05 or duration > 3.0:
                continue

            start_ms = int(start_s * 1000)
            end_ms = int(end_s * 1000)

            try:
                clip = audio[start_ms:end_ms]
            except Exception:
                continue

            clip_hash = hashlib.sha1(f"{source_name}:{start_s:.3f}:{end_s:.3f}".encode()).hexdigest()[:12]
            clip_path = db.make_clip_path(normalized, clip_hash)

            clip = clip.set_frame_rate(22050).set_channels(1).set_sample_width(2)
            clip.export(clip_path, format="wav")

            confidence = getattr(word, "probability", 1.0) or 1.0

            row_id = db.add_word(
                word_text=normalized,
                original_text=raw,
                file_path=clip_path,
                source_audio=source_name,
                start_time=start_s,
                end_time=end_s,
                duration=duration,
                confidence=float(confidence),
            )
            if row_id is not None:
                stats["words_added"] += 1
            else:
                stats["words_skipped_full"] += 1

    return stats


def index_directory(dir_path: str, progress_callback=None) -> dict:
    """
    Recursively process all supported audio files in a directory.
    """
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")

    totals = {"files_processed": 0, "words_found": 0, "words_added": 0,
              "words_skipped_full": 0, "words_skipped_empty": 0, "errors": []}

    for root, _, files in os.walk(dir_path):
        for fname in sorted(files):
            if Path(fname).suffix.lower() not in SUPPORTED_FORMATS:
                continue
            full_path = os.path.join(root, fname)
            try:
                result = index_file(full_path, progress_callback)
                totals["files_processed"] += 1
                for key in ["words_found", "words_added", "words_skipped_full", "words_skipped_empty"]:
                    totals[key] += result[key]
            except Exception as e:
                totals["errors"].append({"file": full_path, "error": str(e)})

    return totals
