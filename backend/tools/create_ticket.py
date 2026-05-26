"""
MySQL 工单工具 —— 客服系统内部工单管理。
支持创建工单、查询工单（升级工单也走这里）。
"""
from datetime import datetime
from backend.db.mysql import get_conn


def create_ticket(
    user_message: str,
    session_id: str = "",
    order_id: str = "",
    intent: str = "general",
    severity: str = "medium",
) -> str:
    """创建工单，返回工单号（如 TKT-20240524-001）"""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()

    # 先生成工单号：查询当前序列号
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM tickets")
    seq = cur.fetchone()["COALESCE(MAX(id), 0) + 1"]
    ticket_id = f"TKT-{now.strftime('%Y%m%d')}-{seq:03d}"

    cur.execute(
        """INSERT INTO tickets (ticket_id, session_id, user_message, order_id, intent, severity, status, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, 'open', %s)""",
        (ticket_id, session_id, user_message, order_id, intent, severity, now),
    )
    conn.close()
    return ticket_id


def get_ticket(ticket_id: str) -> dict | None:
    """查询工单详情"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        row["created_at"] = str(row["created_at"])
        return row
    return None
