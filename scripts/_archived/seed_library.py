"""Download and seed the word library with LibriSpeech data."""

import sys
import os
import time
import urllib.request
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from voice_line import VoiceLine

DATASETS = [
    ("dev-clean",
     "https://www.openslr.org/resources/12/dev-clean.tar.gz", 337,
     "40 speakers, clean read speech"),
    ("test-clean",
     "https://www.openslr.org/resources/12/test-clean.tar.gz", 346,
     "40 speakers, clean read speech"),
]

DATA_ROOT = Path(__file__).parent.parent / "data"
DOWNLOAD_DIR = DATA_ROOT / "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
vl = VoiceLine()


def download(url: str, dest: Path, label: str, size_mb: int):
    print(f"  Downloading {label} ({size_mb} MB)...")

    def hook(n, bs, total):
        if total <= 0:
            return
        pct = min(100, int(100 * n * bs / total))
        mb = n * bs / (1024 * 1024)
        print(f"\r  {pct:3d}%  {mb:.0f}/{total / (1024*1024):.0f} MB",
              end="", flush=True)

    urllib.request.urlretrieve(url, str(dest), reporthook=hook)
    print()


def main():
    total_added = 0
    total_words = 0
    files_done = 0

    for key, url, size_mb, desc in DATASETS:
        tar_path = DOWNLOAD_DIR / f"{key}.tar.gz"
        extract_dir = DOWNLOAD_DIR / key
        libri_dir = extract_dir / "LibriSpeech"

        print(f"\n--- {key} ({desc}) ---")

        if not tar_path.exists():
            download(url, tar_path, key, size_mb)
        else:
            print(f"  Using cached download.")

        if not extract_dir.exists():
            print(f"  Extracting...")
            extract_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tar_path) as tf:
                tf.extractall(extract_dir)
            print(f"  Done.")

        flac_files = sorted(libri_dir.rglob("*.flac"))
        total = len(flac_files)
        print(f"  {total} audio files — indexing with Whisper base model...")
        print(f"  Loading model...", end="", flush=True)

        t0 = time.time()

        def progress(i, n, r):
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (n - i) / rate if rate > 0 else 0
            print(f"\r  {i:4d}/{n} | {rate:.1f} f/s | "
                  f"+{r['words_added']:3d} words | clips: {total_added + r['words_added']:5d} | "
                  f"ETA: {eta:6.0f}s",
                  end="", flush=True)

        r = vl.index_batch([str(p) for p in flac_files], on_progress=progress)
        files_done += r["files_processed"]
        total_words += r["words_found"]
        total_added += r["words_added"]
        print()

    print(f"\n{'='*55}")
    print(vl.stats())
    print(f"\nDone. {total_added} clips from {total_words} words in {files_done} files.")


if __name__ == "__main__":
    main()
