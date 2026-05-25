# VoiceLine

Person of Interest — The Machine style speech assembler.

Each word is TTS-synthesized in a different voice, then processed with
speed variation, EQ, noise, and channel-switching effects. Words are
spliced together with static bursts and silence gaps between them —
producing the signature fragmented voice from the show.

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
# 1. Seed the word library (~300 common words, ~10 min)
python scripts/seed_tts_library.py

# 2. Test
python test_speak.py "can you hear me"
```

Missing words are auto-generated on first use and cached to the library.

## Usage

```bash
# Quick test
python test_speak.py "I will find you"
python test_speak.py "hello world" --save out.wav

# CLI
voice-line speak "I will find you"
voice-line speak -o out.wav "Can you hear me"

# Library
voice-line stats              # coverage summary
voice-line missing -n 20      # top 20 words not yet cached
```

## How it works

```
  Setup (one-time)
  ────────────────
  Frequency word list → edge-tts (14 voices) → WAV clips → SQLite

  Speaking
  ────────
  Text → Tokenize → Lookup each word → Effects → Splice → Play
                     (missing? auto-         (speed, EQ,
                      generate + cache)       noise floor,
                                              fades)

  Sentence flow
  ─────────────
  [intro SFX] → word → gap/static → word → gap/static → ... → [outro SFX]
                ↑ always                         ↑ only for ≥4 words
```

- **Library**: each word gets up to 3 TTS clips in different edge-tts voices.
- **Effects per word**: speed variation, phone/radio/clean EQ, low noise floor, volume jitter, fade in/out.
- **Transitions**: silence gaps (160–350ms) + random static bursts between words.
- **Intro/outro**: The Machine SFX (`data/assets/machine_intro.wav`) plays at start of every output; appended at end for sentences of 4+ words.

## Configuration

All settings in `src/voice_line/config.py`:

| Setting | Default | Description |
|---|---|---|
| `speed_range` | `(1.05, 1.25)` | Word speed; `<1.0` = slower, `>1.0` = faster |
| `gap_ms` | `(160, 350)` | Silence between words (min, max) in ms |
| `static_probability` | `0.25` | Chance of static burst per word transition |
| `static_volume_range` | `(-28, -15)` | Static loudness in dB (higher = louder) |
| `noise_floor_db` | `-32` | Background noise under each word (`-40`=subtle, `-20`=obvious) |
| `volume_db` | `2.0` | Random volume variation ±dB |
| `eq_modes` | `["radio", "phone", "clean"]` | EQ randomly chosen per word |
| `MAX_CLIPS_PER_WORD` | `3` | Max clips stored per word |
| `INTRO_VOLUME_DB` | `-8` | Intro SFX attenuation (more negative = quieter) |

## Expanding the library

```bash
# More common words (up to ~1000)
python scripts/seed_tts_library.py --top 1000

# Backup before major changes
copy data\voice_line.db backups\voice_line_v2.db
```

## Project structure

```
VoiceLine/
├── test_speak.py              # Quick test script
├── src/voice_line/            # Python package
│   ├── engine.py              # Main API
│   ├── assembler.py           # Text → assembled audio
│   ├── tts_fallback.py        # On-the-fly TTS for missing words
│   ├── effects.py             # Audio effects (speed, EQ, noise, transitions)
│   ├── db.py                  # SQLite word library
│   ├── config.py              # All tunable settings
│   ├── analyzer.py            # Coverage analysis
│   ├── frequency.py           # Common word frequency list
│   └── cli.py                 # CLI entry point
├── scripts/
│   └── seed_tts_library.py    # Pre-generate TTS word library
├── data/                      # Clips + DB + SFX (gitignored)
│   └── assets/
│       └── machine_intro.wav  # Machine intro sound effect
├── backups/                   # DB backups (gitignored)
├── pyproject.toml
├── setup.py
└── requirements.txt
```

## Requirements

- Python ≥ 3.9
- pydub + ffmpeg (system-level, for audio I/O)
- edge-tts (free, no API key required)
- numpy, sounddevice
