import random
import numpy as np
from pydub import AudioSegment
from pydub.generators import WhiteNoise

from .config import EFFECTS, SAMPLE_RATE


def _rng():
    return random.Random()


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
        frame_width=2,
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
        frame_width=2,
        frame_rate=SAMPLE_RATE,
        channels=1
    )


def process_word_clip(clip: AudioSegment) -> AudioSegment:
    """Apply random effects to a single word clip."""
    rng = _rng()
    semitones = rng.uniform(-EFFECTS["pitch_semitones"], EFFECTS["pitch_semitones"])
    clip = pitch_shift(clip, semitones)
    vol = rng.uniform(-EFFECTS["volume_db"], EFFECTS["volume_db"])
    clip = volume_vary(clip, vol)
    eq_mode = rng.choice(EFFECTS["eq_modes"])
    clip = apply_eq(clip, eq_mode)
    return clip


def create_transition() -> AudioSegment:
    """Create a transition sound between words."""
    rng = _rng()
    parts = []

    if rng.random() < EFFECTS["static_probability"]:
        dur = rng.randint(10, 40)
        parts.append(generate_static(dur, rng.uniform(-35, -25)))

    if rng.random() < 0.15:
        dur = rng.randint(3, 10)
        parts.append(generate_pop(dur, rng.uniform(-22, -15)))

    silence_ms = rng.randint(EFFECTS["gap_ms"][0], EFFECTS["gap_ms"][1])
    parts.append(AudioSegment.silent(duration=silence_ms))

    if parts:
        result = parts[0]
        for p in parts[1:]:
            result = result.overlay(p)
        return result
    return AudioSegment.silent(duration=50)
