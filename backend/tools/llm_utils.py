"""
LLM 调用安全包装 —— 统一处理超时、API 错误、模型异常等场景。
所有 Agent 通过此模块调用 LLM，确保异常不扩散到 FastAPI 层。
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from backend.logger import logger


def safe_llm_invoke(
    llm: BaseChatModel,
    messages: list[dict | BaseMessage],
    fallback: str,
    timeout: int = 30,
) -> str:
    """安全调用 LLM，异常时返回 fallback 文本。

    Args:
        llm: ChatOpenAI 等实例
        messages: [{"role": "...", "content": "..."}, ...] 或 Message 对象列表
        fallback: 异常时返回的友好提示文本
        timeout: LLM 超时秒数（ChatOpenAI 默认无超时）

    Returns:
        LLM 生成的文本，或 fallback
    """
    try:
        # 设置超时
        if hasattr(llm, "request_timeout"):
            llm.request_timeout = timeout

        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        if content and content.strip():
            return content

        logger.bind(component="llm_utils").warning("LLM 返回空内容，使用 fallback")
        return fallback

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        logger.opt(exception=True).bind(component="llm_utils").error(f"LLM 调用失败: {err_msg}")
        return fallback


# ── 预定义 fallback 话术 ──

FALLBACK_GENERAL = (
    "抱歉，我这边暂时有点卡顿😅 请稍后再试，或者直接联系人工客服获取帮助～"
)

FALLBACK_DISPATCHER = '{"intent": "general"}'

FALLBACK_SEVERITY = '{"severity": "medium", "summary": "投诉内容待确认"}'
