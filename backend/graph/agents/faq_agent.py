"""
FAQ 子Agent —— 独立 subgraph，挂载知识库 RAG 检索
接收用户消息后检索知识库，结合对话历史生成自然回复
"""

from langgraph.graph import StateGraph, END

from backend.logger import logger

from backend.graph.state import AgentState
from backend.tools.search_knowledge import search_knowledge
from backend.config import faq_llm
from backend.tools.llm_utils import safe_llm_invoke, FALLBACK_GENERAL


def search_and_reply_node(state: AgentState) -> AgentState:
    """
    FAQ 处理节点：
    1. 从 messages 中提取最新用户消息
    2. 调用 search_knowledge 检索知识库
    3. 用 faq_llm 结合检索结果生成回复
    4. 更新 state 中的 knowledge_results 和 final_reply
    """
    # 提取最新用户消息作为检索查询
    user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            user_msg = msg.get("content", "")
            break

    if not user_msg:
        state["knowledge_results"] = []
        state["final_reply"] = "抱歉，我没有收到您的消息，请再说一遍好吗？"
        return state

    # 步骤1: 知识库检索
    knowledge_text = ""
    try:
        knowledge_results = search_knowledge(user_msg, top_k=3)
        state["knowledge_results"] = knowledge_results
        knowledge_text = "\n\n---\n\n".join(
            f"[来源: {r['source']}] (相关度: {r['score']:.0%})\n{r['content']}"
            for r in knowledge_results
        )
    except Exception as e:
        logger.bind(component="faq_agent", error=str(e)).warning("知识库检索失败，降级为直接回复")
        state["knowledge_results"] = []

    # 提取最近几轮对话作为上下文
    recent_messages = state.get("messages", [])[-6:]  # 最多取最近 6 条
    history_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '客服'}: {m['content']}"
        for m in recent_messages[:-1]  # 排除最后一条（当前要回复的消息）
    )

    system_prompt = (
        "你是专业、热情的客服助手。请根据知识库提供的内容回答用户问题。\n"
        "要求：\n"
        "1. 口语化表达，有温度，像朋友在帮忙\n"
        "2. 如果知识库中有答案，准确引用；如果没有，诚实说明并提供建议\n"
        "3. 回复简洁明了，不超过 300 字\n"
        "4. 适当使用表情符号增加亲和力"
    )

    user_prompt = (
        f"【知识库参考内容】\n{knowledge_text}\n\n"
        f"【对话历史】\n{history_text if history_text else '（新对话）'}\n\n"
        f"【用户画像】\n{state.get('memory_context', '暂无')}\n\n"
        f"【用户当前问题】\n{user_msg}\n\n"
        f"请根据以上信息，生成客服回复："
    )

    # 步骤3: 调用 LLM 生成回复
    reply = safe_llm_invoke(
        faq_llm,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        fallback="抱歉，我暂时无法查询知识库😅 建议您联系人工客服获取准确信息～",
    )
    state["final_reply"] = reply
    return state


# 构建 FAQ 子Graph（独立 subgraph）
faq_builder = StateGraph(AgentState)
faq_builder.add_node("search_and_reply", search_and_reply_node)
faq_builder.set_entry_point("search_and_reply")
faq_builder.add_edge("search_and_reply", END)

# 编译子Graph，供主Graph作为节点引入
faq_graph = faq_builder.compile()
