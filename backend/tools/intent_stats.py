"""意图分布统计 —— SQLite 持久化，支持按天/周/月聚合。"""
import sqlite3
from datetime import datetime

DB = "backend/data/intent_stats.db"


def _get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intent_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            intent TEXT NOT NULL,
            query_preview TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_intent_date ON intent_log(created_at)
    """)
    conn.commit()
    return conn


def record_intent(session_id: str, intent: str, query: str = "") -> None:
    """记录一次意图分类结果。"""
    if not intent:
        return
    conn = _get_conn()
    conn.execute(
        "INSERT INTO intent_log (session_id, intent, query_preview, created_at) VALUES (?, ?, ?, datetime('now', 'localtime'))",
        (session_id, intent, query[:100] if query else None),
    )
    conn.commit()
    conn.close()


def get_intent_stats(days: int = 7) -> dict:
    """获取最近 N 天的意图分布。

    Returns:
        {
            "period_days": 7,
            "total_queries": 100,
            "intents": [
                {"intent": "faq", "count": 50, "ratio": 0.5},
                ...
            ]
        }
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT intent, COUNT(*) as cnt FROM intent_log "
        "WHERE created_at >= datetime('now', 'localtime', ?) "
        "GROUP BY intent ORDER BY cnt DESC",
        (f"-{days} days",),
    ).fetchall()
    conn.close()

    if not rows:
        return {"period_days": days, "total_queries": 0, "intents": []}

    total = sum(r["cnt"] for r in rows)
    return {
        "period_days": days,
        "total_queries": total,
        "intents": [
            {"intent": r["intent"], "count": r["cnt"], "ratio": round(r["cnt"] / total, 3)}
            for r in rows
        ],
    }


def get_intent_trend(days: int = 7) -> dict:
    """获取最近 N 天每日意图趋势。

    Returns:
        {
            "period_days": 7,
            "daily": [
                {"date": "2026-05-20", "faq": 12, "return": 3, ...},
                ...
            ]
        }
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT date(created_at) as d, intent, COUNT(*) as cnt FROM intent_log "
        "WHERE created_at >= datetime('now', 'localtime', ?) "
        "GROUP BY d, intent ORDER BY d ASC",
        (f"-{days} days",),
    ).fetchall()
    conn.close()

    daily = {}
    for r in rows:
        d = r["d"]
        if d not in daily:
            daily[d] = {}
        daily[d][r["intent"]] = r["cnt"]

    return {
        "period_days": days,
        "daily": [
            {"date": d, **counts}
            for d, counts in sorted(daily.items())
        ],
    }
