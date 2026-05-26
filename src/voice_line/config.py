"""全局配置：路径、音效参数、采样参数。
+Global config: paths, effect parameters, and audio format settings."""

import os

# ── 路径 Paths ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
CLIPS_DIR = os.path.join(DATA_DIR, "clips")
DB_PATH = os.path.join(DATA_DIR, "voice_line.db")

# ── 词库限制 Library limits ────────────────────────────────
MAX_CLIPS_PER_WORD = 3  # 每个词最多保留 3 条录音

# ── 音效参数 Effect parameters ──────────────────────────────
EFFECTS = {
    "volume_db": 2.0,  # 随机音量变化 ±dB
    "gap_ms": (160, 350),  # 词间静默间隔 (最小, 最大) ms
    "static_probability": 0.25,  # 词间插入静噪爆音的概率
    "static_volume_range": (-28, -15),  # 静噪音量 dB（越大越响）
    "noise_floor_db": -32,  # 每个词底噪 dB（-40=轻柔, -20=明显）
    "eq_modes": ["radio", "phone", "clean"],  # 可选 EQ 模式
    "fade_in_ms": 6,  # 淡入
    "fade_out_ms": 8,  # 淡出
    "speed_range": (1.05, 1.25),  # 语速倍率范围（1.0=正常, <1=慢）
}

# ── 音频格式 Audio format ──────────────────────────────────
SAMPLE_RATE = 22050  # 22kHz 足够语音
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1  # 单声道

# ── 片头 / 片尾音效 Intro / Outro ──────────────────────────
INTRO_PATH = os.path.join(DATA_DIR, "assets", "machine_intro.wav")
INTRO_VOLUME_DB = -10  # 音量衰减以匹配 TTS 响度
OUTRO_ENABLED = True  # 长句子（≥4 词）末尾是否加片尾
