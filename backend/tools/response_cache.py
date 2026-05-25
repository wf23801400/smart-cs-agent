"""
同义问题缓存 —— 避免相同意图+相似问题重复调用 LLM。

策略：
- Key = intent + normalized_question（去标点、去空格、截断50字）
- 存储最近 1000 条，LRU 淘汰
- 仅缓存 FAQ 和 general 类（return/complaint 涉及订单状态不适合缓存）
"""

import hashlib
import sqlite3
import re
import time
from pathlib import Path

DB_PATH = str(Path(__file__).parent.parent / "data" / "response_cache.db")
MAX_SIZE = 1000


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            cache_key TEXT PRIMARY KEY,
            intent TEXT,
            question TEXT,
            answer TEXT,
            created_at REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_intent ON cache(intent)
    """)
    conn.commit()
    return conn


def _normalize(question: str) -> str:
    """归一化问题：去标点、空格、截断。"""
    q = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", question)
    q = q.lower().strip()[:50]
    return q


def _make_key(intent: str, question: str) -> str:
    """生成缓存键。"""
    raw = f"{intent}|{_normalize(question)}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached(intent: str, question: str) -> str | None:
    """查缓存，命中返回回答文本，否则返回 None。"""
    if intent not in ("faq", "general"):
        return None

    key = _make_key(intent, question)
    conn = _get_conn()
    row = conn.execute("SELECT answer FROM cache WHERE cache_key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None


def set_cache(intent: str, question: str, answer: str) -> None:
    """写入缓存，自动淘汰旧条目。"""
    if intent not in ("faq", "general"):
        return

    key = _make_key(intent, question)
    conn = _get_conn()

    # 淘汰旧条目
    conn.execute("""
        DELETE FROM cache WHERE cache_key IN (
            SELECT cache_key FROM cache ORDER BY created_at ASC
            LIMIT max(0, (SELECT COUNT(*) FROM cache) - ? + 1)
        )
    """, (MAX_SIZE,))

    conn.execute(
        "INSERT OR REPLACE INTO cache (cache_key, intent, question, answer, created_at) VALUES (?,?,?,?,?)",
        (key, intent, question, answer, time.time()),
    )
    conn.commit()
    conn.close()


def cache_stats() -> dict:
    """缓存统计。"""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    conn.close()
    return {"total_cached": total, "max_size": MAX_SIZE}
