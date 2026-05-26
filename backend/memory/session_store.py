"""
会话记忆存储 —— MySQL 持久化对话历史。
支持多会话隔离，每轮对话自动保存。
"""
import uuid
from datetime import datetime
from backend.db.mysql import get_conn


def create_session(user_id: int | None = None) -> str:
    """创建新会话，返回 session_id"""
    sid = uuid.uuid4().hex[:8]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (id, user_id, created_at) VALUES (%s, %s, %s)",
        (sid, user_id, datetime.now()),
    )
    conn.close()
    return sid


def ensure_session(session_id: str) -> None:
    """确保会话存在（幂等）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT IGNORE INTO sessions (id, created_at) VALUES (%s, %s)",
        (session_id, datetime.now()),
    )
    conn.close()


def save_message(session_id: str, role: str, content: str, intent: str | None = None) -> None:
    """保存一条消息"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (session_id, role, content, intent, created_at) VALUES (%s, %s, %s, %s, %s)",
        (session_id, role, content, intent, datetime.now()),
    )
    conn.close()


def load_history(session_id: str, limit: int = 20) -> list[dict]:
    """加载会话的最近 N 条消息"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, created_at FROM messages WHERE session_id = %s ORDER BY id ASC LIMIT %s",
        (session_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"role": r["role"], "content": r["content"], "created_at": str(r["created_at"])}
        for r in rows
    ]


def delete_session(session_id: str) -> None:
    """删除会话及其消息"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
    cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
    conn.close()
