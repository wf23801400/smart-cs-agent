"""
Mock 订单查询工具 —— 模拟外部订单系统 API。
从 data/order_mock.json 读取数据，按 order_id 查询。
"""

import json
from pathlib import Path

# Mock 数据路径
ORDER_DATA_PATH = Path(__file__).parent.parent / "data" / "order_mock.json"


def _load_orders() -> list[dict]:
    """加载 Mock 订单数据。"""
    with open(ORDER_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("orders", [])


def search_order(order_id: str) -> dict:
    """根据订单号查询订单信息。

    Args:
        order_id: 订单号（如 ORD-001）

    Returns:
        {"found": True, "order": {...}} 或 {"found": False, "message": "..."}
    """
    orders = _load_orders()
    for order in orders:
        if order["order_id"] == order_id:
            return {"found": True, "order": order}

    return {
        "found": False,
        "message": f"未找到订单 {order_id}，请确认订单号是否正确。",
    }


def search_logistics(order_id: str) -> dict:
    """根据订单号查询物流信息。

    Args:
        order_id: 订单号

    Returns:
        {"found": True, "logistics": {...}} 或 {"found": False, "message": "..."}
    """
    result = search_order(order_id)
    if not result["found"]:
        return result

    order = result["order"]
    if "logistics" in order and order["logistics"]:
        return {"found": True, "logistics": order["logistics"]}

    return {
        "found": False,
        "message": f"订单 {order_id} 暂无物流信息，可能尚未发货。",
    }
