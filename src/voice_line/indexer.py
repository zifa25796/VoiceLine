import os
import hashlib
import re
from pathlib import Path

from pydub import AudioSegment

from .config import SUPPORTED_FORMATS, WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
from . import db


def _normalize_word(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r'^[^\w]+|[^\w]+$', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _load_whisper_model():
    from faster_whisper import WhisperModel
    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)


def _transcribe_and_store(audio_path: str, model) -> dict:
    """Transcribe one audio file and store its word clips. Uses a pre-loaded model."""
    path = Path(audio_path)
    source_name = path.name
    audio = AudioSegment.from_file(str(path))
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

            try:
                start_ms = int(start_s * 1000)
                end_ms = int(end_s * 1000)
                clip = audio[start_ms:end_ms]
            except Exception:
                continue

            clip_hash = hashlib.sha1(
                f"{source_name}:{start_s:.3f}:{end_s:.3f}".encode()
            ).hexdigest()[:12]
            clip_path = db.make_clip_path(normalized, clip_hash)
            clip = clip.set_frame_rate(22050).set_channels(1).set_sample_width(2)
            clip.export(clip_path, format="wav")

            row_id = db.add_word(
                word_text=normalized, original_text=raw, file_path=clip_path,
                source_audio=source_name, start_time=start_s, end_time=end_s,
                duration=duration, confidence=float(getattr(word, "probability", 1.0) or 1.0),
            )
            if row_id is not None:
                stats["words_added"] += 1
            else:
                stats["words_skipped_full"] += 1

    return stats


def index_file(audio_path: str) -> dict:
    """Process a single audio file (loads model each call — prefer index_files for batches)."""
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {path.suffix}. Supported: {SUPPORTED_FORMATS}")
    model = _load_whisper_model()
    try:
        return _transcribe_and_store(str(path), model)
    finally:
        del model


def index_files(paths: list[str], on_progress=None) -> dict:
    """Process multiple audio files with a single model load.

    Args:
        paths: List of audio file paths.
        on_progress: Optional callback(files_done, total, last_result).
    """
    paths = [Path(p) for p in paths if Path(p).suffix.lower() in SUPPORTED_FORMATS]
    total = len(paths)
    if not paths:
        return {"files_processed": 0, "words_found": 0, "words_added": 0,
                "words_skipped_full": 0, "words_skipped_empty": 0, "errors": []}

    model = _load_whisper_model()
    totals = {"files_processed": 0, "words_found": 0, "words_added": 0,
              "words_skipped_full": 0, "words_skipped_empty": 0, "errors": []}

    try:
        for i, p in enumerate(paths):
            try:
                r = _transcribe_and_store(str(p), model)
                totals["files_processed"] += 1
                for k in ["words_found", "words_added", "words_skipped_full", "words_skipped_empty"]:
                    totals[k] += r[k]
                if on_progress:
                    on_progress(i + 1, total, r)
            except Exception as e:
                totals["errors"].append({"file": str(p), "error": str(e)})
    finally:
        del model

    return totals


def index_directory(dir_path: str, on_progress=None) -> dict:
    """Process all supported audio files in a directory tree."""
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")

    all_files = []
    for root, _, files in os.walk(dir_path):
        for fname in sorted(files):
            if Path(fname).suffix.lower() in SUPPORTED_FORMATS:
                all_files.append(os.path.join(root, fname))

    return index_files(all_files, on_progress=on_progress)
