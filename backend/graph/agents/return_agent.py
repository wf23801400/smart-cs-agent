"""
退换货子Agent —— 独立 subgraph
流程：验证订单 → 检索退换政策 → 生成工单 → 自然回复
"""

from langgraph.graph import StateGraph, END

from backend.graph.state import AgentState
from backend.tools.search_order import search_order
from backend.tools.search_knowledge import search_knowledge
from backend.tools.create_ticket import create_ticket
from backend.config import return_llm
from backend.tools.llm_utils import safe_llm_invoke, FALLBACK_GENERAL


# ── 节点函数 ──────────────────────────────────────────

def check_order_node(state: AgentState) -> AgentState:
    """验证订单：从 state 提取订单号，调用 search_order 查询。"""
    order_info = state.get("order_info", {})
    order_id = order_info.get("order_id", "")

    if order_id:
        result = search_order(order_id)
        if result["found"]:
            state["order_info"] = result["order"]
            print(f"[return_agent] 订单 {order_id} 验证成功，状态: {result['order']['status']}")
            return state

    # 无订单号或订单不存在
    state["order_info"] = {"missing": True, "message": "未找到关联订单，请用户提供订单号"}
    print("[return_agent] 未找到关联订单，将引导用户提供")
    return state


def search_policy_node(state: AgentState) -> AgentState:
    """检索退换货政策，补充到 knowledge_results。"""
    user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    policy_results = search_knowledge(f"退换货 政策 {user_msg}", top_k=3)

    # 合并已有 knowledge_results（可能来自 dispatcher）
    existing = state.get("knowledge_results", [])
    state["knowledge_results"] = existing + policy_results

    print(f"[return_agent] 已检索 {len(policy_results)} 条退换政策")
    return state


def create_ticket_node(state: AgentState) -> AgentState:
    """生成退换货工单。"""
    user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    order_info = state.get("order_info", {})
    order_id = order_info.get("order_id", "")

    ticket_id = create_ticket(
        user_message=user_msg,
        order_id=order_id,
        intent="return",
    )
    state["ticket_id"] = ticket_id
    print(f"[return_agent] 工单已创建: {ticket_id}")
    return state


def generate_reply_node(state: AgentState) -> AgentState:
    """结合订单信息 + 退换政策 + 工单号，生成客服回复。"""
    # 提取用户消息
    user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    # 订单信息
    order_info = state.get("order_info", {})
    if order_info.get("missing"):
        order_text = "用户未提供订单号，需要引导用户提供订单号后继续。"
    elif order_info.get("order_id"):
        order_text = (
            f"订单号: {order_info['order_id']}\n"
            f"商品: {order_info.get('product', '未知')}\n"
            f"金额: ¥{order_info.get('price', 0)}\n"
            f"状态: {order_info.get('status', '未知')}"
        )
    else:
        order_text = "未提取到订单信息。"

    # 退换政策
    policy_text = ""
    knowledge_results = state.get("knowledge_results", [])
    for r in knowledge_results[-3:]:  # 取最近的 3 条
        policy_text += f"- {r['content'][:200]}\n"

    ticket_id = state.get("ticket_id", "")

    # Prompt
    system_prompt = (
        "你是一个专业、耐心的退换货客服专员。请根据用户诉求、订单信息和退换政策，"
        "生成简洁友好的回复。\n"
        "要求：\n"
        "1. 先共情：理解用户想退换货的心情\n"
        "2. 确认订单信息\n"
        "3. 引用退换政策说明流程\n"
        "4. 提供工单号作为凭证\n"
        "5. 口语化、有温度，带表情符号\n"
        "6. 如果没有订单号，引导用户提供（订单号格式为 ORD-xxx）"
    )

    user_prompt = (
        f"【用户诉求】\n{user_msg}\n\n"
        f"【用户画像】\n{state.get('memory_context', '暂无')}\n\n"
        f"【订单信息】\n{order_text}\n\n"
        f"【退换政策】\n{policy_text}\n\n"
        f"【工单号】\n{ticket_id}\n\n"
        "请生成退换货客服回复："
    )

    reply = safe_llm_invoke(
        return_llm,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        fallback="抱歉，退货系统暂时繁忙😅 我们的客服专员稍后会联系您处理，请耐心等待～",
    )

    state["final_reply"] = reply
    return state


# ── 构建子Graph ──────────────────────────────────────

return_builder = StateGraph(AgentState)

return_builder.add_node("check_order", check_order_node)
return_builder.add_node("search_policy", search_policy_node)
return_builder.add_node("create_ticket", create_ticket_node)
return_builder.add_node("generate_reply", generate_reply_node)

return_builder.set_entry_point("check_order")
return_builder.add_edge("check_order", "search_policy")
return_builder.add_edge("search_policy", "create_ticket")
return_builder.add_edge("create_ticket", "generate_reply")
return_builder.add_edge("generate_reply", END)

# 编译子Graph
return_graph = return_builder.compile()
