# VoiceLine

Person of Interest — The Machine style speech assembler.

Instead of traditional TTS, VoiceLine builds a word-level audio library from **real recordings** (speeches, radio, podcasts) by transcribing them with Whisper and slicing out individual words. When you feed it a sentence, it looks up each word, picks a random clip from a different speaker, applies per-word audio effects (pitch shift, EQ, static), splices them together — producing the signature fragmented "channel-surfing" voice from the show.

## Install

```bash
git clone https://github.com/zifa25796/VoiceLine.git
cd VoiceLine
pip install -e .
```

pydub needs ffmpeg for non-WAV formats: `winget install ffmpeg` or `brew install ffmpeg`.

## Quick start

VoiceLine needs a **word library** to speak. The library is built by indexing audio files — this database lives locally and is **not** stored in git (it can be gigabytes).

### 1. Seed with open-source data

```bash
python scripts/seed_library.py
```

This downloads [LibriSpeech](https://www.openslr.org/12) dev-clean + test-clean (~680 MB of audio, 40+ speakers, 5400 utterances) and indexes every word with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) base model. Expect **1–2 hours** on CPU for the full run (2703 + 2620 = 5323 files).

### 2. Add your own audio

```bash
voice-line index broadcast.mp3
voice-line index ./my_audio_collection/
```

Any English audio works — speeches, radio recordings, podcasts. Each word gets sliced out, normalized, and stored. **Max 3 clips per word** to keep the library manageable.

### 3. Speak

```bash
voice-line speak "I will find you"
voice-line speak -o output.wav "Can you hear me"
```

## Usage

| Command | What it does |
|---|---|
| `voice-line speak "text"` | Assemble text into Machine-style speech and play it |
| `voice-line speak -o out.wav "text"` | Same, but save to file |
| `voice-line index <path>` | Index an audio file or directory into the word library |
| `voice-line missing -n 20` | Show the 20 most common English words still missing from the library |
| `voice-line stats` | Library coverage statistics |

## Python API

```python
from voice_line import VoiceLine

vl = VoiceLine()

# Index audio into the library
vl.index("broadcast.mp3")
vl.index("./audio_collection/")

# Speak
vl.speak("I will find you")
vl.speak("Can you hear me", output="output.wav")

# See what common words you're missing
print(vl.stats())
print(vl.missing(20))
```

## How it works

```
  OFFLINE — Building the word library
  ─────────────────────────────────────
  Audio files  →  Whisper STT   →  Word clips  →  SQLite DB
  (.mp3/.wav)    (word-level       (.wav per      (word → [clip1, clip2, ...])
                  timestamps)       word)          max 3 clips / word


  ONLINE — Speaking
  ─────────────────
  Text message  →  Tokenize  →  Lookup each word  →  Effects  →  Concatenate  →  Play
                               (random clip per
                                word, silence if
                                word is missing)
```

- **Indexing**: faster-whisper transcribes audio with word-level timestamps. Each word is sliced from the source, normalized (lowercase, stripped punctuation), and saved as a 22 kHz mono WAV. Up to 3 clips stored per distinct word.
- **Assembly**: text is split into tokens. Each word is looked up in the library; a random clip is chosen. Missing words become silence. Every clip gets random per-word effects:
  - Pitch shift ±3 semitones (different "speaker")
  - Volume variation ±4 dB
  - Random EQ mode: phone (300–3400 Hz), radio (200–5000 Hz), or clean
  - Transition sounds between words: static bursts (30% chance), pops/clicks (15% chance), random 30–150 ms gaps
- **Analysis**: ~1000 most common English words are built into the package. `voice-line missing` shows which of those are absent from your library — a shopping list for what audio to collect next.

## Project structure

```
VoiceLine/
├── src/voice_line/       # Python package
│   ├── engine.py         # Main API (VoiceLine class)
│   ├── indexer.py        # Audio → word library (Whisper STT)
│   ├── assembler.py      # Text → assembled audio
│   ├── effects.py        # Per-word audio effects
│   ├── analyzer.py       # Missing-word analysis
│   ├── db.py             # SQLite word library
│   ├── config.py         # Configuration
│   ├── frequency.py      # ~1000 common English words by frequency
│   └── cli.py            # Command-line interface
├── scripts/
│   └── seed_library.py   # Download & index LibriSpeech to bootstrap the library
├── data/                 # Word clips + database + downloads (gitignored — generate locally)
├── pyproject.toml
├── setup.py
├── requirements.txt
└── .gitignore
```

## Requirements

- Python ≥ 3.9
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — first run downloads the base model (~140 MB) from HuggingFace
- [pydub](https://github.com/jiaaro/pydub) + ffmpeg (system-level, for MP3/compressed audio)
- [sounddevice](https://python-sounddevice.readthedocs.io/) — live playback
- numpy
