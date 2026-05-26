"""反馈闭环 —— MySQL 存储用户对回复的评价，用于持续改进。"""
from datetime import datetime
from backend.db.mysql import get_conn


def save_feedback(session_id: str, reply_index: int, rating: str) -> dict:
    """保存一条反馈"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feedback (session_id, reply_index, rating, created_at) VALUES (%s, %s, %s, %s)",
        (session_id, reply_index, rating, datetime.now()),
    )
    conn.close()
    return {"status": "ok", "rating": rating}


def get_feedback_stats() -> dict:
    """反馈统计"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM feedback")
    total = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM feedback WHERE rating='up'")
    up = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM feedback WHERE rating='down'")
    down = cur.fetchone()["cnt"]
    conn.close()
    return {
        "total": total,
        "up": up,
        "down": down,
        "up_ratio": round(up / total, 2) if total > 0 else 0,
    }
