import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voice_line import VoiceLine


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play a sentence with VoiceLine.")
    parser.add_argument("text", nargs="?", default="can you hear me")
    parser.add_argument("--save", metavar="PATH", help="Save WAV instead of playing audio")
    args = parser.parse_args()
    VoiceLine().speak(args.text, output=args.save)
