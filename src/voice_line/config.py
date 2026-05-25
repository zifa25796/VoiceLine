import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
CLIPS_DIR = os.path.join(DATA_DIR, "clips")
DB_PATH = os.path.join(DATA_DIR, "voice_line.db")

MAX_CLIPS_PER_WORD = 3

EFFECTS = {
    "volume_db": 2.0,              # max random volume variation ± dB
    "gap_ms": (160, 350),          # silence gap between words (min, max) ms
    "static_probability": 0.12,    # chance of static burst between words
    "eq_modes": ["radio", "phone", "clean"],
    "fade_in_ms": 6,
    "fade_out_ms": 8,
    "speed_range": (0.75, 0.90),   # 1.0=normal, <1.0=slower
}

SAMPLE_RATE = 22050
SAMPLE_WIDTH = 2
CHANNELS = 1
