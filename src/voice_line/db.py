from __future__ import annotations

import sqlite3
import os
from .config import DB_PATH, CLIPS_DIR, MAX_CLIPS_PER_WORD


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS words (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            word_text     TEXT    NOT NULL,
            original_text TEXT    NOT NULL,
            file_path     TEXT    NOT NULL,
            source_audio  TEXT,
            start_time    REAL,
            end_time      REAL,
            duration      REAL,
            confidence    REAL,
            quality_score REAL    DEFAULT 0.5,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_words_text ON words(word_text);
    """)
    conn.commit()
    # Add quality_score column to existing DBs (migration)
    try:
        conn.execute("ALTER TABLE words ADD COLUMN quality_score REAL DEFAULT 0.5")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()


def word_count(word_text: str) -> int:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM words WHERE word_text = ?", (word_text,)
    ).fetchone()[0]
    conn.close()
    return count


def word_is_full(word_text: str) -> bool:
    return word_count(word_text) >= MAX_CLIPS_PER_WORD


def make_clip_path(word_text: str, audio_hash: str) -> str:
    subdir = os.path.join(CLIPS_DIR, word_text)
    os.makedirs(subdir, exist_ok=True)
    return os.path.join(subdir, f"{audio_hash}.wav")


def add_word(word_text: str, original_text: str, file_path: str,
             source_audio: str, start_time: float, end_time: float,
             duration: float, confidence: float,
             quality_score: float = 0.5) -> int | None:
    if word_is_full(word_text):
        return None
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO words (word_text, original_text, file_path, source_audio,
           start_time, end_time, duration, confidence, quality_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (word_text, original_text, file_path, source_audio,
         start_time, end_time, duration, confidence, quality_score)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_clips(word_text: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM words WHERE word_text = ?
           ORDER BY quality_score DESC, RANDOM()""",
        (word_text,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_words() -> list[str]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT word_text FROM words ORDER BY word_text"
    ).fetchall()
    conn.close()
    return [r["word_text"] for r in rows]


def get_stats() -> dict:
    conn = get_connection()
    total_clips = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    unique_words = conn.execute(
        "SELECT COUNT(DISTINCT word_text) FROM words"
    ).fetchone()[0]
    sources = conn.execute(
        "SELECT COUNT(DISTINCT source_audio) FROM words"
    ).fetchone()[0]
    conn.close()
    return {
        "total_clips": total_clips,
        "unique_words": unique_words,
        "source_files": sources,
    }
