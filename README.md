# VoiceLine

Person of Interest — The Machine style speech assembler.

Each word is TTS-synthesized in a different voice, then slowed down,
EQ'd, and spliced with channel-switching effects — producing the
signature fragmented "I will find you" voice from the show.

## Install

```bash
git clone https://github.com/zifa25796/VoiceLine.git
cd VoiceLine
pip install -e .
pip install edge-tts
```

pydub needs ffmpeg: `winget install ffmpeg` or `brew install ffmpeg`.

## Quick start

```bash
# 1. Seed the word library (300 most common words, ~5 min)
python scripts/seed_tts_library.py

# 2. Speak
python test_speak.py "can you hear me"
```

Missing words are auto-generated via edge-tts on first use and cached.

## Usage

```bash
python test_speak.py "I will find you"              # play
python test_speak.py "hello world" --save out.wav   # save to file
```

Or via CLI:

```bash
voice-line speak "I will find you"
voice-line speak -o out.wav "Can you hear me"
voice-line stats              # library coverage
voice-line missing -n 20      # top 20 words not yet in library
```

## How it works

```
  Seeding (one-time)
  ──────────────────
  Word list (frequency order) → edge-tts (14 voices) → WAV clips → SQLite

  Speaking
  ────────
  Text → Tokenize → Lookup each word → Effects → Splice → Play
                     (missing? auto-         (slowdown,
                      generate + cache)       EQ, static)
```

- **Library**: each word gets up to 3 TTS clips in different voices.
- **Effects per word**: speed variation (configurable), phone/radio/clean EQ, volume jitter, fade in/out.
- **Transitions**: random silence gaps + static bursts between words.
- **Missing words**: generated on the fly via edge-tts and stored for next time.

## Configuration

All tweakable in `src/voice_line/config.py`:

| Setting | Default | What |
|---|---|---|
| `speed_range` | `(0.75, 0.85)` | Slower = smaller numbers |
| `gap_ms` | `(160, 350)` | Silence between words |
| `static_probability` | `0.12` | Static burst chance |
| `eq_modes` | `["radio", "phone", "clean"]` | Per-word EQ |
| `volume_db` | `2.0` | Random volume variation |
| `MAX_CLIPS_PER_WORD` | `3` | Max clips per word |

## Expanding the library

```bash
# More common words
python scripts/seed_tts_library.py --top 1000

# Backup before big changes
copy data\voice_line.db backups\voice_line_v2.db
```

## Project structure

```
VoiceLine/
├── src/voice_line/
│   ├── engine.py          # Main API
│   ├── assembler.py       # Text → audio assembly
│   ├── tts_fallback.py    # On-the-fly TTS for missing words
│   ├── effects.py         # Audio effects
│   ├── db.py              # SQLite word library
│   ├── config.py          # All settings
│   ├── analyzer.py        # Coverage analysis
│   ├── frequency.py       # Common word frequency list
│   └── cli.py             # CLI
├── test_speak.py          # Quick test script
├── scripts/
│   └── seed_tts_library.py  # Pre-generate TTS word library
├── data/                  # Clips + DB (gitignored)
├── backups/               # DB backups (gitignored)
├── pyproject.toml
├── setup.py
└── requirements.txt
```

## Requirements

- Python ≥ 3.9
- pydub + ffmpeg (system-level)
- edge-tts (free, no API key)
- numpy, sounddevice
