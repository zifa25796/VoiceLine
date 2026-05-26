"""快速测试：输入句子，听 Machine 风格语音。
Quick test: type a sentence and hear Machine-style speech.

Usage:  python test_speak.py "can you hear me"
        python test_speak.py "i will find you" --save test.wav
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from voice_line import VoiceLine

if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "can you hear me"
    output = None
    if "--save" in sys.argv:
        idx = sys.argv.index("--save")
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]

    vl = VoiceLine()
    vl.speak(text, output=output)
