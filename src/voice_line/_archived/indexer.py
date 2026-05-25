import os
import hashlib
import re
from pathlib import Path

import numpy as np
from pydub import AudioSegment

from .config import SUPPORTED_FORMATS, WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
from . import db

MIN_QUALITY_SCORE = 0.3      # discard clips below this
ENERGY_SEARCH_MS = 80        # search ±80ms around Whisper boundary for real edge
PADDING_MS = 30              # small safety padding after refinement


def _to_mono_f32(seg: AudioSegment) -> np.ndarray:
    seg = seg.set_channels(1)
    samples = np.array(seg.get_array_of_samples(), dtype=np.float64)
    return samples / (2.0 ** (seg.sample_width * 8 - 1))


def _refine_onset(samples: np.ndarray, sr: int, rough_ms: int) -> int:
    """Find the real word onset (energy rise) near `rough_ms`."""
    search = int(ENERGY_SEARCH_MS * sr / 1000)
    win = max(1, int(sr * 0.010))  # 10ms
    start = max(0, int(rough_ms * sr / 1000) - search)
    end = min(len(samples), int(rough_ms * sr / 1000) + search)
    region = np.abs(samples[start:end])
    if len(region) < win:
        return rough_ms
    energy = np.array([np.mean(region[i:i + win] ** 2)
                       for i in range(0, len(region) - win, win // 2)])
    if len(energy) == 0:
        return rough_ms
    threshold = np.percentile(energy, 25) * 2.0
    above = energy > threshold
    for i in range(len(above)):
        if above[i]:
            return rough_ms - ENERGY_SEARCH_MS + int(i * win // 2 * 1000 / sr)
    return rough_ms


def _refine_offset(samples: np.ndarray, sr: int, rough_ms: int) -> int:
    """Find the real word offset (energy drop) near `rough_ms`."""
    search = int(ENERGY_SEARCH_MS * sr / 1000)
    win = max(1, int(sr * 0.010))
    start = max(0, int(rough_ms * sr / 1000) - search)
    end = min(len(samples), int(rough_ms * sr / 1000) + search)
    region = np.abs(samples[start:end])
    if len(region) < win:
        return rough_ms
    energy = np.array([np.mean(region[i:i + win] ** 2)
                       for i in range(0, len(region) - win, win // 2)])
    if len(energy) == 0:
        return rough_ms
    threshold = np.percentile(energy, 25) * 2.0
    above = energy > threshold
    for i in range(len(above) - 1, -1, -1):
        if above[i]:
            return rough_ms - ENERGY_SEARCH_MS + int(i * win // 2 * 1000 / sr)
    return rough_ms


def _score_clip(samples: np.ndarray, sr: int) -> float:
    """Score clip quality 0-1. High = clean boundaries, good duration."""
    margin = int(sr * 0.025)  # 25ms
    if len(samples) < 2 * margin:
        return 0.4
    head_e = np.mean(np.abs(samples[:margin]))
    tail_e = np.mean(np.abs(samples[-margin:]))
    mid = samples[margin:-margin]
    body_e = np.mean(np.abs(mid)) if len(mid) > 0 else 1e-8

    boundary_score = 1.0 - min(1.0, (head_e + tail_e) / (body_e * 2.0 + 1e-8))

    dur_sec = len(samples) / sr
    if dur_sec < 0.04:
        dur_score = 0.2
    elif dur_sec < 0.06:
        dur_score = 0.4
    elif dur_sec > 1.2:
        dur_score = 0.6
    else:
        dur_score = 1.0

    return round((boundary_score * 0.6 + dur_score * 0.4), 3)


def _normalize_word(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r'^[^\w]+|[^\w]+$', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _load_whisper_model():
    from faster_whisper import WhisperModel
    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)


def _transcribe_and_store(audio_path: str, model) -> dict:
    """Transcribe, refine boundaries with energy, score quality, store."""
    path = Path(audio_path)
    source_name = path.name
    audio = AudioSegment.from_file(str(path))
    samples_f32 = _to_mono_f32(audio)
    sr = audio.frame_rate
    total_len_ms = len(audio)

    segments, info = model.transcribe(str(path), word_timestamps=True)

    stats = {"words_found": 0, "words_added": 0, "words_skipped_full": 0,
             "words_skipped_empty": 0, "words_skipped_low_quality": 0}

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

            start_ms_raw = int(word.start * 1000)
            end_ms_raw = int(word.end * 1000)
            if end_ms_raw - start_ms_raw <= 40 or end_ms_raw - start_ms_raw > 3000:
                continue

            # Refine boundaries with energy analysis
            refined_start = _refine_onset(samples_f32, sr, start_ms_raw)
            refined_end = _refine_offset(samples_f32, sr, end_ms_raw)

            # Small safety padding
            start_ms = max(0, refined_start - PADDING_MS)
            end_ms = min(total_len_ms, refined_end + PADDING_MS)

            if end_ms - start_ms > 2000:
                continue

            try:
                clip = audio[start_ms:end_ms]
            except Exception:
                continue

            # Score quality
            clip_samples = _to_mono_f32(clip)
            quality = _score_clip(clip_samples, clip.frame_rate)
            if quality < MIN_QUALITY_SCORE:
                stats["words_skipped_low_quality"] += 1
                continue

            # Export
            clip_hash = hashlib.sha1(
                f"{source_name}:{start_ms}:{end_ms}".encode()
            ).hexdigest()[:12]
            clip_path = db.make_clip_path(normalized, clip_hash)
            clip = clip.set_frame_rate(22050).set_channels(1).set_sample_width(2)
            clip.export(clip_path, format="wav")

            duration = (end_ms - start_ms) / 1000
            row_id = db.add_word(
                word_text=normalized, original_text=raw, file_path=clip_path,
                source_audio=source_name, start_time=start_ms / 1000, end_time=end_ms / 1000,
                duration=duration, confidence=float(getattr(word, "probability", 1.0) or 1.0),
                quality_score=quality,
            )
            if row_id is not None:
                stats["words_added"] += 1
            else:
                stats["words_skipped_full"] += 1

    return stats


def index_file(audio_path: str) -> dict:
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
    paths = [Path(p) for p in paths if Path(p).suffix.lower() in SUPPORTED_FORMATS]
    total = len(paths)
    if not paths:
        return {"files_processed": 0, "words_found": 0, "words_added": 0,
                "words_skipped_full": 0, "words_skipped_empty": 0,
                "words_skipped_low_quality": 0, "errors": []}

    model = _load_whisper_model()
    totals = {"files_processed": 0, "words_found": 0, "words_added": 0,
              "words_skipped_full": 0, "words_skipped_empty": 0,
              "words_skipped_low_quality": 0, "errors": []}

    try:
        for i, p in enumerate(paths):
            try:
                r = _transcribe_and_store(str(p), model)
                totals["files_processed"] += 1
                for k in ["words_found", "words_added", "words_skipped_full",
                          "words_skipped_empty", "words_skipped_low_quality"]:
                    totals[k] += r.get(k, 0)
                if on_progress:
                    on_progress(i + 1, total, r)
            except Exception as e:
                totals["errors"].append({"file": str(p), "error": str(e)})
    finally:
        del model

    return totals


def index_directory(dir_path: str, on_progress=None) -> dict:
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")
    all_files = []
    for root, _, files in os.walk(dir_path):
        for fname in sorted(files):
            if Path(fname).suffix.lower() in SUPPORTED_FORMATS:
                all_files.append(os.path.join(root, fname))
    return index_files(all_files, on_progress=on_progress)
