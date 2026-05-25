"""
主 Graph：多子Agent客服系统编排
节点流: parse_input → dispatcher_agent → [条件路由4路 + fallback] → coordinator → END
"""

import json
import re
from langgraph.graph import StateGraph, END

from backend.graph.state import AgentState
from backend.config import dispatcher_llm
from backend.tools.llm_utils import safe_llm_invoke, FALLBACK_DISPATCHER
from backend.tools.response_cache import get_cached, set_cache

# 导入子Agent
from backend.graph.agents.faq_agent import faq_graph
from backend.graph.agents.return_agent import return_graph
from backend.graph.agents.complaint_agent import complaint_graph
from backend.graph.agents.general_agent import general_graph


# ======================== 节点函数 ========================


def parse_input_node(state: AgentState) -> AgentState:
    """
    输入解析节点：预处理用户消息，提取订单信息等结构化数据。
    当前为简化实现，后续可增加 NER、订单号正则提取等逻辑。
    """
    print("[parse_input] 解析用户输入")

    # 从所有历史消息中提取订单号（支持多轮对话场景）
    order_info = {}
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            # 尝试匹配订单号格式
            order_match = re.search(r"(ORD-\w+|\b\d{10,}\b)", content)
            if order_match:
                order_info["order_id"] = order_match.group(1)
                break  # 找到最新的订单号就停

    state["order_info"] = order_info
    state["intent"] = ""
    state["knowledge_results"] = []
    state["ticket_id"] = ""
    state["final_reply"] = ""
    return state


def dispatcher_agent_node(state: AgentState) -> AgentState:
    """
    意图分发节点：用 LLM 对用户消息进行意图分类。
    返回 JSON: {"intent": "faq"/"return"/"complaint"/"general"}
    """
    print("[dispatcher_agent] 开始意图分类")

    # 提取最近3条用户消息作为上下文
    user_msgs = []
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            user_msgs.append(msg.get("content", ""))
            if len(user_msgs) >= 3:
                break

    if not user_msgs:
        state["intent"] = "general"
        return state

    # 最新消息为主，历史消息为上下文
    user_msg = user_msgs[0]  # 最新一条
    context_msgs = user_msgs[1:]  # 往前2条
    context_text = ""
    if context_msgs:
        context_text = "\n".join(f"- 上轮消息：{m}" for m in context_msgs)
        context_text = f"\n\n【对话上文】（帮你理解指代和省略）：\n{context_text}"

    # 意图分类 prompt —— 输出严格 JSON
    system_prompt = (
        "你是一个客服意图分类器。分析用户消息，判断意图类别。\n"
        "类别定义（注意区分「要退货」和「问退货政策」）：\n"
        "- return: 用户明确要求退货、换货、退款（如「我要退货」「帮我退款」）\n"
        "- faq: 询问政策规则、操作方法、工作时间、物流时效等知识类问题（如「退货要几天到账」「怎么查快递」「客服几点上班」）\n"
        "- complaint: 投诉商品质量、服务态度、物流延误、表达不满\n"
        "- general: 问候、闲聊、无法归类的其他内容\n\n"
        "关键是：「问退货政策」走 faq，「要求退货」走 return。\n"
        "严格按以下 JSON 格式输出，不要输出其他内容：\n"
        '{"intent": "<类别>"}'
    )

    # 用户画像上下文（跨会话记忆）
    memory_context = state.get("memory_context", "")
    if memory_context:
        system_prompt += f"\n\n【用户画像】{memory_context}\n请结合用户画像理解意图，如用户说「跟上次一样」时参考画像判断。"

    response_content = safe_llm_invoke(
        dispatcher_llm,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"用户消息：{user_msg}{context_text}"},
        ],
        fallback=FALLBACK_DISPATCHER,
    )

    # 解析 LLM 返回的 JSON
    try:
        result = json.loads(response_content)
        intent = result.get("intent", "general")
    except json.JSONDecodeError:
        # 容错：尝试用正则提取 intent 值
        match = re.search(r'"intent"\s*:\s*"(faq|return|complaint|general)"', response_content)
        intent = match.group(1) if match else "general"

    # 归一化意图值
    valid_intents = {"faq", "return", "complaint", "general"}
    state["intent"] = intent if intent in valid_intents else "general"

    print(f"[dispatcher_agent] 意图分类结果: {state['intent']}")
    return state


def coordinator_node(state: AgentState) -> AgentState:
    """
    协调器节点：子Agent回复的最终处理。
    职责：
    1. 工单号注入
    2. 追加回复到对话历史
    """
    print("[coordinator] 汇总生成最终回复")

    final_reply = state.get("final_reply", "")
    ticket_id = state.get("ticket_id", "")

    # 兜底
    if not final_reply:
        final_reply = "抱歉，系统处理异常，请稍后重试或联系人工客服。"
        print("[coordinator] ⚠️ 子Agent未生成回复，使用兜底话术")

    # 工单号注入：生成了工单但回复里没提 → 追加
    if ticket_id and ticket_id not in final_reply:
        append = f"\n\n📋 工单号：{ticket_id}（如需跟进请提供此编号）"
        final_reply += append
        print(f"[coordinator] 注入工单号: {ticket_id}")

    state["final_reply"] = final_reply

    # 追加到对话历史
    state["messages"] = state.get("messages", []) + [
        {"role": "assistant", "content": final_reply}
    ]

    return state


# ======================== 条件路由函数 ========================


def router_edge(state: AgentState) -> str:
    """条件路由：根据意图分发到对应子Agent。"""
    intent = state.get("intent", "general")
    route_map = {
        "faq": "faq_agent",
        "return": "return_agent",
        "complaint": "complaint_agent",
        "general": "general_agent",
    }
    next_node = route_map.get(intent, "general_agent")
    print(f"[router] intent={intent} → {next_node}")
    return next_node


def check_cache_node(state: AgentState) -> AgentState:
    """缓存检查节点：同意图+相似问题命中则直接生成回复，跳过子Agent。"""
    intent = state.get("intent", "")
    messages = state.get("messages", [])
    user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    cached = get_cached(intent, user_msg)
    if cached:
        print(f"[cache] ✅ HIT intent={intent} question={user_msg[:20]}")
        state["final_reply"] = cached
        state["cache_hit"] = True
    else:
        print(f"[cache] ❌ MISS intent={intent} question={user_msg[:20]}")
        state["cache_hit"] = False

    return state


def cache_router(state: AgentState) -> str:
    """缓存命中 → 直接 coordinator / 未命中 → 正常路由。"""
    if state.get("cache_hit"):
        return "coordinator"

    intent = state.get("intent", "general")
    route_map = {
        "faq": "faq_agent",
        "return": "return_agent",
        "complaint": "complaint_agent",
        "general": "general_agent",
    }
    next_node = route_map.get(intent, "general_agent")
    print(f"[router] intent={intent} → {next_node}")
    return next_node


def save_to_cache_node(state: AgentState) -> AgentState:
    """保存回答到缓存（FAQ/general 类可缓存）。"""
    intent = state.get("intent", "")
    reply = state.get("final_reply", "")
    if intent in ("faq", "general") and reply:
        messages = state.get("messages", [])
        user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
                break
        set_cache(intent, user_msg, reply)
    return state


# ======================== 主Graph构建 ========================


def build_main_graph() -> StateGraph:
    """
    构建主Graph：
    parse_input → dispatcher → check_cache → [命中→coordinator] / [未命中→router→子Agent] → save_cache → END
    """
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("parse_input", parse_input_node)
    workflow.add_node("dispatcher_agent", dispatcher_agent_node)
    workflow.add_node("check_cache", check_cache_node)

    # 子Agent 节点
    workflow.add_node("faq_agent", faq_graph)
    workflow.add_node("return_agent", return_graph)
    workflow.add_node("complaint_agent", complaint_graph)
    workflow.add_node("general_agent", general_graph)

    # 协调器节点
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("save_cache", save_to_cache_node)

    # 构建边
    workflow.set_entry_point("parse_input")
    workflow.add_edge("parse_input", "dispatcher_agent")
    workflow.add_edge("dispatcher_agent", "check_cache")

    # 缓存命中 → coordinator；未命中 → 子Agent路由
    workflow.add_conditional_edges(
        "check_cache",
        cache_router,
        {
            "faq_agent": "faq_agent",
            "return_agent": "return_agent",
            "complaint_agent": "complaint_agent",
            "general_agent": "general_agent",
            "coordinator": "coordinator",
        },
    )

    # 所有子Agent → coordinator → save_cache → END
    workflow.add_edge("faq_agent", "coordinator")
    workflow.add_edge("return_agent", "coordinator")
    workflow.add_edge("complaint_agent", "coordinator")
    workflow.add_edge("general_agent", "coordinator")
    workflow.add_edge("coordinator", "save_cache")
    workflow.add_edge("save_cache", END)

    return workflow.compile()


# 全局编译后的主Graph实例
main_graph = build_main_graph()
