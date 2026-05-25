"""Re-index LibriSpeech with energy-refined boundaries + quality scoring.

The dev-clean and test-clean downloads (~680MB) are already cached.
This re-indexes them using the new pipeline:
  1. Whisper rough boundaries
  2. Energy analysis to refine onset/offset (±80ms search)
  3. Quality score based on boundary silence + duration
  4. Discard clips with score < 0.3

Usage:  python scripts/seed_tedlium.py
"""

from __future__ import annotations

import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from voice_line import VoiceLine

DATA_DIR = Path(__file__).parent.parent / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"


def main():
    # LibriSpeech should already be cached
    datasets = [
        ("dev-clean",  DOWNLOAD_DIR / "dev-clean" / "LibriSpeech"),
        ("test-clean", DOWNLOAD_DIR / "test-clean" / "LibriSpeech"),
    ]

    vl = VoiceLine()
    grand_total_added = 0
    grand_total_words = 0

    for name, libri_dir in datasets:
        if not libri_dir.exists():
            print(f"  SKIP {name}: not found at {libri_dir}")
            print(f"  Run scripts/seed_library.py first to download.")
            continue

        flac_files = sorted(libri_dir.rglob("*.flac"))
        total = len(flac_files)
        print(f"--- {name}: {total} files ---")
        print(f"Whisper tiny + 80ms energy search + quality >= 0.3\n")

        t0 = time.time()

        def progress(i, n, r):
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (n - i) / rate if rate > 0 else 0
            dropped = r.get("words_skipped_low_quality", 0)
            print(f"\r  {i:4d}/{n}  {rate:.2f} f/s  "
                  f"+{r['words_added']:3d} words  "
                  f"lowQ:{dropped:3d}  "
                  f"ETA:{eta:6.0f}s",
                  end="", flush=True)

        r = vl.index_batch([str(p) for p in flac_files], on_progress=progress)
        print()

        grand_total_added += r["words_added"]
        grand_total_words += r["words_found"]

        print(f"  Added: {r['words_added']}  Found: {r['words_found']}  "
              f"LowQ: {r.get('words_skipped_low_quality', 0)}  "
              f"Errors: {len(r.get('errors', []))}")

    print(f"\n{'='*55}")
    print(vl.stats())
    print(f"\nDone. {grand_total_added} clips from {grand_total_words} words.")


if __name__ == "__main__":
    main()
