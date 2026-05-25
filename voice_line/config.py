import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CLIPS_DIR = os.path.join(DATA_DIR, "clips")
DB_PATH = os.path.join(DATA_DIR, "voice_line.db")

MAX_CLIPS_PER_WORD = 3

# faster-whisper model  ("tiny", "base", "small", "medium", "large-v3")
WHISPER_MODEL = "base"
WHISPER_DEVICE = "cpu"       # or "cuda"
WHISPER_COMPUTE_TYPE = "int8"  # "int8" for cpu, "float16" for gpu

# Supported audio formats for indexing
SUPPORTED_FORMATS = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus")

# Effects parameters
EFFECTS = {
    "pitch_semitones": 3.0,       # max random pitch shift ± semitones
    "volume_db": 4.0,             # max random volume variation ± dB
    "gap_ms": (30, 150),          # silence gap between words (min, max) ms
    "static_probability": 0.3,    # chance of static burst between words
    "eq_modes": ["radio", "phone", "clean"],  # randomly chosen per word
}

# Output audio
SAMPLE_RATE = 22050
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1      # mono
