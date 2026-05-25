"""
通用咨询子Agent —— 兜底 subgraph
处理问候、闲聊、奇葩问题等未被其他子Agent覆盖的内容。
"""

from langgraph.graph import StateGraph, END

from backend.graph.state import AgentState
from backend.config import general_llm
from backend.tools.llm_utils import safe_llm_invoke, FALLBACK_GENERAL


def handle_general_node(state: AgentState) -> AgentState:
    """通用对话处理：自然闲聊，灵活应对奇葩问题。"""
    user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    # 取最近几轮对话作为上下文
    recent = state.get("messages", [])[-6:]
    history = "\n".join(
        f"{'用户' if m['role'] == 'user' else '客服'}: {m['content']}"
        for m in recent[:-1]
    )

    system_prompt = (
        "你是一个智能客服助手，负责处理各种未被其他部门覆盖的用户咨询，"
        "包括问候、闲聊、吐槽、奇葩问题等。\n"
        "要求：\n"
        "1. 灵活自然，像真人客服而不是机器人\n"
        "2. 适度幽默，可以开玩笑但保持专业\n"
        "3. 如果用户只是闲聊/问候，简短回应\n"
        "4. 如果是奇葩问题，幽默应对但不嘲讽\n"
        "5. 如果是业务相关问题但你不确定，引导用户联系专业客服\n"
        "6. 控制在 200 字以内"
    )

    user_prompt = (
        f"【用户画像】\n{state.get('memory_context', '暂无')}\n\n"
        f"【对话历史】\n{history if history else '（新对话）'}\n\n"
        f"【用户消息】\n{user_msg}\n\n"
        "请生成客服回复："
    )

    reply = safe_llm_invoke(
        general_llm,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        fallback=FALLBACK_GENERAL,
    )

    state["final_reply"] = reply
    return state


# 构建子Graph
general_builder = StateGraph(AgentState)
general_builder.add_node("handle", handle_general_node)
general_builder.set_entry_point("handle")
general_builder.add_edge("handle", END)

general_graph = general_builder.compile()
