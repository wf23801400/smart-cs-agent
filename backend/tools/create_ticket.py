"""
SQLite 工单工具 —— 客服系统内部工单管理。
自动建表，支持创建工单、查询工单。
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# 数据库路径
DB_PATH = Path(__file__).parent.parent / "data" / "tickets.db"


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接，自动建表。"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_str TEXT DEFAULT '',
            user_message TEXT NOT NULL,
            order_id TEXT DEFAULT '',
            intent TEXT DEFAULT 'general',
            status TEXT DEFAULT 'open',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def create_ticket(
    user_message: str,
    order_id: str = "",
    intent: str = "general",
) -> str:
    """创建工单。

    Args:
        user_message: 用户消息原文
        order_id: 关联订单号（可选）
        intent: 意图分类

    Returns:
        工单号（如 TKT-20240524-001）
    """
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute(
        "INSERT INTO tickets (user_message, order_id, intent, status, created_at) VALUES (?, ?, ?, 'open', ?)",
        (user_message, order_id, intent, now),
    )
    conn.commit()

    ticket_num = cursor.lastrowid
    ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d')}-{ticket_num:03d}"
    conn.execute("UPDATE tickets SET id_str = ? WHERE id = ?", (ticket_id, ticket_num))
    conn.close()
    return ticket_id


def get_ticket(ticket_id: str) -> dict | None:
    """查询工单详情。"""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM tickets WHERE id_str = ?", (ticket_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None
