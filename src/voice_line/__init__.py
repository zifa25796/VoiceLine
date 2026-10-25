"""VoiceLine — Person of Interest "The Machine" style speech assembler."""

import os
from pydub import AudioSegment
from .config import FFMPEG_PATH

if os.path.exists(FFMPEG_PATH):
    AudioSegment.converter = FFMPEG_PATH

from .engine import VoiceLine
