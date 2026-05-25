# VoiceLine

Person of Interest — The Machine style speech assembler.

Instead of traditional TTS, VoiceLine builds a word-level audio library from real recordings (speeches, radio, podcasts) using Whisper STT indexing. When you feed it a sentence, it looks up each word, randomly picks clips, applies per-word effects (pitch shift, EQ, static), and concatenates them — producing the signature fragmented "channel-surfing" voice from the show.

## Install

```bash
git clone https://github.com/zifa25796/VoiceLine.git
cd VoiceLine
pip install -e .
```

pydub needs ffmpeg for non-WAV formats: `winget install ffmpeg` or `brew install ffmpeg`.

## Usage

### CLI

```bash
# Speak text
voice-line speak "I will find you"
voice-line speak -o output.wav "Can you hear me"

# Index audio files into the word library
voice-line index broadcast.mp3
voice-line index ./my_audio_collection/

# Show missing common words (guide targeted collection)
voice-line missing -n 20
voice-line stats
```

### Python API

```python
from voice_line import VoiceLine

vl = VoiceLine()

# Index audio
vl.index("broadcast.mp3")
vl.index("./audio_collection/")

# Speak
vl.speak("I will find you")
vl.speak("Can you hear me", output="output.wav")

# Coverage analysis
print(vl.missing(20))
print(vl.stats())
```

## How it works

```
                ┌──────────────────┐
  audio files → │  Whisper STT     │ → word clips → SQLite library
                │  word timestamps │   (per word)
                └──────────────────┘

                ┌──────────────────┐
  text message →│  lookup + random │ → effects → assembled audio
                │  per-word clip   │   (pitch/EQ/static)
                └──────────────────┘
```

- **Indexing**: faster-whisper transcribes audio with word-level timestamps, each word is sliced, normalized, and stored. Max 3 clips per word.
- **Assembly**: text is tokenized, each word is looked up in the library, a random clip is chosen, and per-word effects are applied (random pitch ±3 semitones, phone/radio EQ, volume variation). Transition static/pop sounds are inserted between words.
- **Analysis**: a built-in frequency list of ~1000 common English words identifies gaps in your library so you know what audio to collect next.

## Project structure

```
VoiceLine/
├── src/voice_line/      # Python package
│   ├── engine.py        # Main API (VoiceLine class)
│   ├── indexer.py       # Audio indexing (Whisper STT)
│   ├── assembler.py     # Text-to-audio assembly
│   ├── effects.py       # Per-word audio effects
│   ├── analyzer.py      # Missing word analysis
│   ├── db.py            # SQLite word library
│   ├── config.py        # Configuration
│   ├── frequency.py     # Common word frequency list
│   └── cli.py           # Command-line interface
├── data/                # Word clips + database (gitignored)
├── pyproject.toml
└── requirements.txt
```
