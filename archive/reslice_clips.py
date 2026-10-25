"""Re-extract all word clips from original sources with wider padding."""

from __future__ import annotations

import sys
import os
import hashlib
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from voice_line import db
from pydub import AudioSegment

PADDING_MS = 120  # extra ms before AND after each word
DATA_DIR = Path(__file__).parent.parent / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"


def find_source_file(source_name: str) -> Path | None:
    """Locate the original .flac file in the downloads directory."""
    for root, _, files in os.walk(DOWNLOAD_DIR):
        for f in files:
            if f == source_name:
                return Path(root) / f
    return None


def main():
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT id, word_text, source_audio, start_time, end_time, file_path FROM words"
    ).fetchall()

    # Group by source audio file
    by_source = defaultdict(list)
    for r in rows:
        by_source[r["source_audio"]].append(dict(r))
    conn.close()

    total = len(rows)
    updated = 0
    missing_sources = 0

    for source_name, entries in by_source.items():
        src_path = find_source_file(source_name)
        if src_path is None:
            missing_sources += len(entries)
            print(f"  SKIP: source not found — {source_name} ({len(entries)} words)")
            continue

        audio = AudioSegment.from_file(str(src_path))

        for e in entries:
            start_ms = max(0, int(e["start_time"] * 1000) - PADDING_MS)
            end_ms = min(len(audio), int(e["end_time"] * 1000) + PADDING_MS)

            try:
                clip = audio[start_ms:end_ms]
            except Exception:
                continue

            clip = clip.set_frame_rate(22050).set_channels(1).set_sample_width(2)

            old_path = Path(e["file_path"])
            clip_hash = hashlib.sha1(
                f"{source_name}:{start_ms}:{end_ms}".encode()
            ).hexdigest()[:12]
            new_path = db.make_clip_path(e["word_text"], clip_hash)

            clip.export(new_path, format="wav")

            # Update DB with new path and padded timestamps
            conn = db.get_connection()
            conn.execute(
                "UPDATE words SET file_path = ?, start_time = ?, end_time = ?, duration = ? WHERE id = ?",
                (str(new_path), start_ms / 1000, end_ms / 1000, (end_ms - start_ms) / 1000, e["id"]),
            )
            conn.commit()
            conn.close()

            # Remove old clip if path changed
            if old_path != Path(new_path) and old_path.exists():
                os.remove(str(old_path))

            updated += 1

        print(f"\r  Resliced: {updated}/{total} clips", end="", flush=True)

    print(f"\nDone. {updated} clips resliced (padding: {PADDING_MS}ms).")
    if missing_sources:
        print(f"Skipped {missing_sources} clips (source files not found).")


if __name__ == "__main__":
    main()
