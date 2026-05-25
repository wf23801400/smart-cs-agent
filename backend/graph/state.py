"""
AgentState 定义 —— 多子Agent客服系统的共享状态
"""

from typing import TypedDict


class AgentState(TypedDict):
    """多子Agent客服系统的全局状态，在所有节点间传递"""

    # 对话历史，每条消息为 {"role": "user"/"assistant", "content": "..."}
    messages: list[dict]

    # 意图分类结果: "return" | "complaint" | "faq" | "general"
    intent: str

    # 订单信息（由解析节点提取或用户提供）
    order_info: dict

    # RAG 知识库检索结果，FAQ 子Agent 填充
    knowledge_results: list[dict]

    # 工单号（退换货/投诉流程生成）
    ticket_id: str

    # 最终回复文本，由 coordinator 汇总生成
    final_reply: str

    # Mem0 用户记忆上下文，跨会话生效
    memory_context: str
