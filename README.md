# VoiceLine

Person of Interest — The Machine style speech assembler.

Words are selected from randomly chosen TTS voice clips, then processed with
speed variation, EQ, noise, and channel-switching effects. Words are
spliced together with static bursts and silence gaps between them —
producing the signature fragmented voice from the show.

## Portable Build (Windows)

Download `VoiceLine.zip`, unzip, run — no install required.

```
VoiceLine.exe speak "can you hear me"
VoiceLine.exe speak "hello world" -o output.wav
VoiceLine.exe stats
VoiceLine.exe list
VoiceLine.exe list -s hello
VoiceLine.exe missing -n 30
```

| Dependency | Bundled? |
|---|---|
| Python 3.10 | Yes, in `_internal/` |
| ffmpeg | Yes, ffmpeg.exe + DLLs |
| Pre-generated word clips | Included when supplied with the release, in `_internal/data/` |
| SQLite word database | Auto-created on first run |
| Audio playback (sounddevice) | Pure Python, no PowerShell needed |
| edge-tts (new word generation) | **Requires internet** |

Offline coverage depends on the clips included in your build or local library.
Use `VoiceLine.exe stats` to inspect it. Missing words require internet and are
cached after successful generation.

## Install (from source)

```bash
git clone https://github.com/zifa25796/VoiceLine.git
cd VoiceLine
uv sync
```

## Quick start

```bash
# 1. Seed the word library (~300 common words, ~10 min)
uv run python scripts/seed_tts_library.py

# 2. Test
uv run python scripts/check_speech.py "can you hear me"
```

Missing words are auto-generated on first use and cached to the library. Playback
waits for one clip per missing word; additional voices are filled in background.
Background work stops when the process exits. Partial libraries are not
automatically topped up by cached-word playback; use the seeding tool to fill them.

## Usage

VoiceLine's Python API and CLI run independently. The Daily HTTP MCP bridge is maintained by the [POI project](https://github.com/zifa25796/poi-project) in `integrations/mcp_server.py`. Inside a POI checkout, `mcp_server.py` remains a compatibility launcher for existing clients. Start Daily before using that bridge; set `VOICELINE_API_URL` to override `http://127.0.0.1:9000`.

```bash
# Quick test
uv run python scripts/check_speech.py "I will find you"
uv run python scripts/check_speech.py "hello world" --save out.wav

# CLI
uv run voice-line speak "I will find you"
uv run voice-line speak -o out.wav "Can you hear me"

# Library
uv run voice-line stats              # coverage summary
uv run voice-line missing -n 20      # top 20 words not yet cached
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

- **Library**: each word gets up to 5 TTS clips in different edge-tts voices.
- **Refresh**: a clip is regenerated in background with a new voice after being played 3 times,
  so frequently repeated words (e.g. a daily "low battery" alert) keep sounding fresh.
  The current request uses the cached clip without waiting for the refresh.
- **Effects per word**: speed variation, phone/radio/clean EQ, low noise floor, volume jitter, fade in/out.
- **Transitions**: silence gaps (160–350ms) + random static bursts between words.
- **Intro/outro**: The Machine SFX (`src/voice_line/assets/machine_intro.wav`, with a legacy `data/assets/` fallback) plays at start of every output; appended at end for sentences of 4+ words.

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
| `MAX_CLIPS_PER_WORD` | `5` | Max clips stored per word |
| `REFRESH_PLAYS_PER_CLIP` | `3` | Regenerate a clip after this many plays |
| `REFRESH_RETRY_SECONDS` | `300` | Min cooldown before retrying a failed refresh |
| `INTRO_VOLUME_DB` | `-10` | Intro SFX attenuation (more negative = quieter) |

## Expanding the library

```bash
# More common words (up to ~1000)
python scripts/seed_tts_library.py --top 1000

# Backup before major changes
copy data\voice_line.db backups\voice_line_v2.db
```

## Project structure

```text
VoiceLine/
├── src/voice_line/       Speech package
│   └── assets/           Packaged machine_intro.wav
├── scripts/             Seeding tools and check_speech.py manual demo
├── tests/               Automated speech pipeline tests
├── archive/             Unsupported historical experiments
├── data/                Generated clips and SQLite database (ignored)
├── backups/             Local backups (ignored)
├── mcp_server.py         Compatibility launcher for POI's Daily bridge
├── VoiceLine.spec        Portable build definition
├── pyproject.toml
└── uv.lock
```

The intro sound is packaged separately from generated data. `VOICELINE_DATA_DIR` overrides the database and clip directory; the existing repository `data/` directory remains the default. Back up the database together with its clips. Existing database entries may contain absolute paths.

Run automated checks from this repository with `uv run python -m unittest discover -s tests -v`. Inside POI, run `uv run python -m unittest discover -s VoiceLine/tests -v` from the POI root.

## Requirements

- Python ≥ 3.9 (Python 3.10+ for the POI companion)
- pydub + ffmpeg (system-level, for audio I/O)
- edge-tts (free, no API key required)
- numpy, sounddevice

## Runtime logs

Logs go to stderr; CLI result tables stay on stdout. Interactive terminals color
SPEECH green, TTS and BUILD blue. Events and important field values are also
highlighted. Warnings are yellow, errors red. Set `NO_COLOR` to disable color;
redirected output is plain text. `Completed` measures assembly plus playback or
export, while `audio` is the generated audio duration. Refreshes happen in
background; a successful request may still report missing words replaced by static.
