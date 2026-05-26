"""SQLite 词库管理：建表、增删查、统计。
SQLite word library: schema, CRUD, and statistics."""

from __future__ import annotations

import sqlite3
import os
from .config import DB_PATH, CLIPS_DIR, MAX_CLIPS_PER_WORD


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（自动创建目录、启用 WAL）。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """初始化数据库表结构，含向后兼容迁移。"""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS words (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            word_text     TEXT    NOT NULL,         -- 归一化后的词（小写）
            original_text TEXT    NOT NULL,         -- 原始文本（保留大小写）
            file_path     TEXT    NOT NULL,
            source_audio  TEXT,                     -- 来源（tts:voice 或录音文件名）
            start_time    REAL,                     -- 录音中的起始秒数
            end_time      REAL,
            duration      REAL,
            confidence    REAL,                     -- STT 置信度（TTS 固定 1.0）
            quality_score REAL    DEFAULT 0.5,       -- 质量评分，越高优先使用
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_words_text ON words(word_text);
    """)
    conn.commit()
    # 兼容旧库：为没有 quality_score 列的表添加该列
    try:
        conn.execute("ALTER TABLE words ADD COLUMN quality_score REAL DEFAULT 0.5")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def word_count(word_text: str) -> int:
    """查询某个词已有几条录音。"""
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM words WHERE word_text = ?", (word_text,)
    ).fetchone()[0]
    conn.close()
    return count


def word_is_full(word_text: str) -> bool:
    """检查某个词是否已达上限。"""
    return word_count(word_text) >= MAX_CLIPS_PER_WORD


def make_clip_path(word_text: str, audio_hash: str) -> str:
    """按 word/hash.wav 结构生成文件路径。"""
    subdir = os.path.join(CLIPS_DIR, word_text)
    os.makedirs(subdir, exist_ok=True)
    return os.path.join(subdir, f"{audio_hash}.wav")


def add_word(word_text: str, original_text: str, file_path: str,
             source_audio: str, start_time: float, end_time: float,
             duration: float, confidence: float,
             quality_score: float = 0.5) -> int | None:
    """插入一条词录音记录。若该词已达上限则返回 None。"""
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
    """获取某个词的所有录音，按质量排序后随机打散。"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM words WHERE word_text = ?
           ORDER BY quality_score DESC, RANDOM()""",
        (word_text,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_words() -> list[str]:
    """返回词库中所有不重复的词。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT word_text FROM words ORDER BY word_text"
    ).fetchall()
    conn.close()
    return [r["word_text"] for r in rows]


def list_words(search: str = "", offset: int = 0, limit: int = 50,
               sort_by: str = "word_text") -> list[dict]:
    """列出词库中的词，支持搜索、分页、排序。

    Args:
        search:  关键词搜索（LIKE %search%）
        offset:  分页偏移
        limit:   每页数量
        sort_by: 排序字段 (word_text | created_at | quality_score | clips)
    """
    sort_map = {
        "word_text": "word_text ASC",
        "created_at": "latest_created DESC",
        "quality_score": "avg_quality DESC",
        "clips": "clip_count DESC",
    }
    order = sort_map.get(sort_by, sort_map["word_text"])
    conn = get_connection()
    if search:
        rows = conn.execute(
            f"""SELECT w.word_text, w.clip_count, w.avg_quality,
                       w.first_created, w.latest_created
                FROM word_summary w
                WHERE w.word_text LIKE ?
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            (f"%{search}%", limit, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM word_summary WHERE word_text LIKE ?",
            (f"%{search}%",),
        ).fetchone()[0]
    else:
        rows = conn.execute(
            f"""SELECT word_text, clip_count, avg_quality,
                       first_created, latest_created
                FROM word_summary
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM word_summary").fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def ensure_word_summary_view() -> None:
    """创建 word_summary 视图，聚合每词的统计信息。"""
    conn = get_connection()
    conn.executescript("""
        CREATE VIEW IF NOT EXISTS word_summary AS
        SELECT word_text,
               COUNT(*)                          AS clip_count,
               ROUND(AVG(quality_score), 3)      AS avg_quality,
               MIN(created_at)                   AS first_created,
               MAX(created_at)                   AS latest_created
        FROM words
        GROUP BY word_text;
    """)
    conn.commit()
    conn.close()


def get_stats() -> dict:
    """返回词库概览：总录音数、不重复词数、来源数。"""
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
