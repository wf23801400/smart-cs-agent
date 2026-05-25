"""反馈闭环 —— 存储用户对回复的评价，用于持续改进。"""

import sqlite3
import time
from pathlib import Path

DB_PATH = str(Path(__file__).parent.parent / "data" / "feedback.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            reply_index INTEGER NOT NULL,
            rating TEXT NOT NULL CHECK(rating IN ('up', 'down')),
            created_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_session ON feedback(session_id)
    """)
    conn.commit()
    return conn


def save_feedback(session_id: str, reply_index: int, rating: str) -> dict:
    """保存一条反馈。"""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO feedback (session_id, reply_index, rating, created_at) VALUES (?,?,?,?)",
        (session_id, reply_index, rating, time.time()),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "rating": rating}


def get_feedback_stats() -> dict:
    """反馈统计。"""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    up = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating='up'").fetchone()[0]
    down = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating='down'").fetchone()[0]
    conn.close()
    return {
        "total": total,
        "up": up,
        "down": down,
        "up_ratio": round(up / total, 2) if total > 0 else 0,
    }
