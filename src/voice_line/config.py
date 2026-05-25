import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
CLIPS_DIR = os.path.join(DATA_DIR, "clips")
DB_PATH = os.path.join(DATA_DIR, "voice_line.db")

MAX_CLIPS_PER_WORD = 3

EFFECTS = {
    "volume_db": 2.0,  # max random volume variation ± dB
    "gap_ms": (160, 350),  # silence gap between words (min, max) ms
    "static_probability": 0.50,  # chance of static burst between words
    "static_volume_range": (-15, -8),  # static loudness in dB (higher = louder)
    "noise_floor_db": -32,  # background noise under each word (-40=subtle, -20=obvious)
    "eq_modes": ["radio", "phone", "clean"],
    "fade_in_ms": 6,
    "fade_out_ms": 8,
    "speed_range": (1.00, 1.20),  # 1.0=normal, <1.0=slower
}

SAMPLE_RATE = 22050
SAMPLE_WIDTH = 2
CHANNELS = 1

# Intro sound prepended to every speech output
INTRO_PATH = os.path.join(DATA_DIR, "assets", "machine_intro.wav")
INTRO_VOLUME_DB = -8  # attenuation to match TTS loudness
