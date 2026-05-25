"""
投诉子Agent —— 独立 subgraph
流程：提取投诉要点 → 评估严重等级 → 生成工单 → 安抚回复
"""

from langgraph.graph import StateGraph, END

from backend.graph.state import AgentState
from backend.tools.create_ticket import create_ticket
from backend.config import complaint_llm
from backend.tools.llm_utils import safe_llm_invoke, FALLBACK_SEVERITY


# ── 节点函数 ──────────────────────────────────────────

def assess_severity_node(state: AgentState) -> AgentState:
    """评估投诉严重等级：low / medium / high。"""
    user_msg = ""
    order_info = state.get("order_info", {})
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    # 用 LLM 评估等级
    prompt = (
        "你是一个投诉等级评估器。根据用户投诉内容，评估严重等级。\n"
        "等级定义：\n"
        "- low: 轻微不满、建议、一般反馈\n"
        "- medium: 物流延误、发货慢、轻微质量问题\n"
        "- high: 商品质量问题（损坏、假货）、服务态度恶劣、涉及退款纠纷\n\n"
        "严格按以下 JSON 格式输出：\n"
        '{"severity": "low|medium|high", "summary": "一句话总结投诉要点"}'
    )

    severity_content = safe_llm_invoke(
        complaint_llm,
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"用户投诉内容：{user_msg}\n关联订单：{order_info}"},
        ],
        fallback=FALLBACK_SEVERITY,
    )

    import json, re
    try:
        result = json.loads(severity_content)
    except json.JSONDecodeError:
        match = re.search(r'"severity"\s*:\s*"(low|medium|high)"', severity_content)
        sev = match.group(1) if match else "medium"
        result = {"severity": sev, "summary": "投诉内容"}

    # 存入 order_info 扩展字段
    order_info["complaint_severity"] = result.get("severity", "medium")
    order_info["complaint_summary"] = result.get("summary", "")
    state["order_info"] = order_info

    print(f"[complaint_agent] 严重等级: {order_info['complaint_severity']} - {order_info['complaint_summary']}")
    return state


def create_complaint_ticket_node(state: AgentState) -> AgentState:
    """生成投诉工单。"""
    user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    order_info = state.get("order_info", {})
    order_id = order_info.get("order_id", "")
    severity = order_info.get("complaint_severity", "medium")

    # 工单号带等级标识
    ticket_id = create_ticket(
        user_message=f"[{severity.upper()}] {user_msg}",
        order_id=order_id,
        intent="complaint",
    )
    state["ticket_id"] = ticket_id
    print(f"[complaint_agent] 投诉工单: {ticket_id} (等级: {severity})")
    return state


def generate_complaint_reply_node(state: AgentState) -> AgentState:
    """生成安抚回复，根据等级提供不同处理方案。"""
    user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    order_info = state.get("order_info", {})
    severity = order_info.get("complaint_severity", "medium")
    summary = order_info.get("complaint_summary", "")
    ticket_id = state.get("ticket_id", "")

    # 不同等级的处理话术
    level_actions = {
        "low": "记录反馈并转达给相关部门改进",
        "medium": "客服专员将在 2 小时内电话联系您处理",
        "high": "高级客服经理将在 30 分钟内优先致电，问题升级处理",
    }
    action = level_actions.get(severity, level_actions["medium"])

    system_prompt = (
        "你是一个专业的投诉处理客服专员。用户投诉时需要做到：\n"
        "1. 先真诚道歉，承认问题，展现同理心\n"
        "2. 确认已理解用户的具体诉求\n"
        "3. 告知处理方案和时间节点，让用户安心\n"
        "4. 提供工单号作为追踪凭证\n"
        "5. 口语化、真诚，不敷衍，带适当表情符号\n\n"
        f"本次投诉等级: {severity}\n处理方案: {action}"
    )

    user_prompt = (
        f"【用户投诉】\n{user_msg}\n\n"
        f"【用户画像】\n{state.get('memory_context', '暂无')}\n\n"
        f"【投诉要点】\n{summary}\n\n"
        f"【关联订单】\n{order_info.get('order_id', '无')} - {order_info.get('product', '未知')}\n\n"
        f"【工单号】\n{ticket_id}\n\n"
        f"【处理方案】\n{action}\n\n"
        "请生成投诉安抚回复："
    )

    reply = safe_llm_invoke(
        complaint_llm,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        fallback="非常抱歉给您带来不好的体验🙏 我们已记录您的投诉，客服专员将尽快与您联系处理。",
    )

    state["final_reply"] = reply
    return state


# ── 构建子Graph ──────────────────────────────────────

complaint_builder = StateGraph(AgentState)

complaint_builder.add_node("assess_severity", assess_severity_node)
complaint_builder.add_node("create_ticket", create_complaint_ticket_node)
complaint_builder.add_node("generate_reply", generate_complaint_reply_node)

complaint_builder.set_entry_point("assess_severity")
complaint_builder.add_edge("assess_severity", "create_ticket")
complaint_builder.add_edge("create_ticket", "generate_reply")
complaint_builder.add_edge("generate_reply", END)

complaint_graph = complaint_builder.compile()
