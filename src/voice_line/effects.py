import random
import numpy as np
from pydub import AudioSegment

from .config import EFFECTS, SAMPLE_RATE


def pitch_shift(clip: AudioSegment, semitones: float) -> AudioSegment:
    """Shift pitch by +- semitones without changing duration."""
    if abs(semitones) < 0.1:
        return clip
    rate = clip.frame_rate
    octaves = semitones / 12.0
    new_rate = int(rate * (2.0 ** octaves))
    pitched = clip._spawn(clip.raw_data, overrides={"frame_rate": new_rate})
    return pitched.set_frame_rate(rate)


def volume_vary(clip: AudioSegment, db_change: float) -> AudioSegment:
    return clip + db_change


def apply_eq(clip: AudioSegment, mode: str) -> AudioSegment:
    """Apply EQ to simulate different audio sources."""
    if mode == "phone":
        return clip.high_pass_filter(300).low_pass_filter(3400)
    elif mode == "radio":
        return clip.high_pass_filter(200).low_pass_filter(5000)
    elif mode == "clean":
        return clip
    else:
        return clip


def generate_static(duration_ms: int, volume_db: float = -30) -> AudioSegment:
    """Generate a short burst of white noise (static)."""
    samples = np.random.normal(0, 0.5, int(SAMPLE_RATE * duration_ms / 1000))
    samples = np.clip(samples * (10 ** (volume_db / 20)), -1, 1)
    samples_int16 = (samples * 32767).astype(np.int16)
    return AudioSegment(
        samples_int16.tobytes(),
        sample_width=2,
        frame_rate=SAMPLE_RATE,
        channels=1
    )


def generate_pop(duration_ms: int = 5, volume_db: float = -18) -> AudioSegment:
    """Generate a sharp click/pop sound."""
    total = int(SAMPLE_RATE * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, total, endpoint=False)
    envelope = np.exp(-t * 200)
    carrier = np.random.normal(0, 1, total) * envelope
    carrier = np.clip(carrier * (10 ** (volume_db / 20)), -1, 1)
    samples_int16 = (carrier * 32767).astype(np.int16)
    return AudioSegment(
        samples_int16.tobytes(),
        sample_width=2,
        frame_rate=SAMPLE_RATE,
        channels=1
    )


def _noise_floor(duration_ms: int, frame_rate: int) -> AudioSegment:
    """Generate a low-level background noise track."""
    db = EFFECTS["noise_floor_db"]
    samples = np.random.normal(0, 0.3, int(frame_rate * duration_ms / 1000))
    scale = 10 ** (db / 20)
    samples_int16 = (samples * scale * 32767).astype(np.int16)
    return AudioSegment(
        samples_int16.tobytes(),
        sample_width=2,
        frame_rate=frame_rate,
        channels=1,
    )


def process_word_clip(clip: AudioSegment) -> AudioSegment:
    """Apply effects: speed change, EQ, volume, noise floor, loudness normalisation."""
    from math import log10

    factor = random.uniform(*EFFECTS["speed_range"])
    new_rate = int(clip.frame_rate * factor)
    clip = clip._spawn(clip.raw_data, overrides={"frame_rate": new_rate})

    eq_mode = random.choice(EFFECTS["eq_modes"])
    clip = apply_eq(clip, eq_mode)

    # Low noise floor under the word
    noise = _noise_floor(len(clip), clip.frame_rate)
    clip = clip.overlay(noise)

    vol = random.uniform(-EFFECTS["volume_db"], EFFECTS["volume_db"])
    clip = clip + vol

    if clip.max > 0:
        target = 0.75 * 32767
        gain_db = 20 * log10(target / clip.max)
        gain_db += random.uniform(-1.5, 1.5)
        clip = clip.apply_gain(gain_db)

    pad = 30
    clip = AudioSegment.silent(duration=pad, frame_rate=clip.frame_rate) + clip
    return clip


def create_transition() -> AudioSegment:
    """Create a transition between words: static, pops, silence gap."""
    parts = []
    vlo, vhi = EFFECTS["static_volume_range"]

    if random.random() < EFFECTS["static_probability"]:
        dur = random.randint(15, 60)
        parts.append(generate_static(dur, random.uniform(vlo, vhi)))

    if random.random() < 0.25:
        dur = random.randint(3, 12)
        parts.append(generate_pop(dur, random.uniform(vhi - 4, vhi + 2)))

    silence_ms = random.randint(EFFECTS["gap_ms"][0], EFFECTS["gap_ms"][1])
    parts.append(AudioSegment.silent(duration=silence_ms))

    result = parts[0]
    for p in parts[1:]:
        result = result.overlay(p)
    return result
