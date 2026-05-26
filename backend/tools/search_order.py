"""
MySQL 订单查询工具 —— 从 MySQL orders + logistics 表查询订单和物流信息。
"""
from backend.db.mysql import get_conn


def search_order(order_id: str) -> dict:
    """根据订单号查询订单信息"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, order_id, user_id, product_name, price, status, created_at, updated_at FROM orders WHERE order_id = %s",
        (order_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row:
        row["price"] = float(row["price"])
        row["created_at"] = str(row["created_at"])
        row["updated_at"] = str(row["updated_at"])
        return {"found": True, "order": row}

    return {
        "found": False,
        "message": f"未找到订单 {order_id}，请确认订单号是否正确。",
    }


def search_logistics(order_id: str) -> dict:
    """根据订单号查询物流信息"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, order_id, company, tracking_no, status, current_location, estimated_delivery, created_at, updated_at FROM logistics WHERE order_id = %s",
        (order_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row:
        row["estimated_delivery"] = str(row["estimated_delivery"]) if row["estimated_delivery"] else None
        row["created_at"] = str(row["created_at"])
        row["updated_at"] = str(row["updated_at"])
        return {"found": True, "logistics": row}

    return {
        "found": False,
        "message": f"订单 {order_id} 暂无物流信息，可能尚未发货。",
    }
