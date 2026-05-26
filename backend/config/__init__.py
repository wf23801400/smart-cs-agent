"""
配置模块入口。
统一对外暴露 settings 单例 + 所有 LLM 实例。
所有模块统一 `from backend.config import settings, faq_llm, ...`
"""

import os

from backend.config.settings import settings, PROJECT_ROOT

# ── LangSmith 追踪 ─────────────────────────────────
if settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT

if not settings.DEEPSEEK_API_KEY:
    raise RuntimeError("请设置环境变量 DEEPSEEK_API_KEY")

# ── LLM 实例创建 ──────────────────────────────────
from langchain_openai import ChatOpenAI
from backend.tools.cost_tracker import cost_handler

def _create_llm(temperature: float, tag: str, streaming: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=temperature,
        streaming=streaming,
        tags=[tag],
        callbacks=[cost_handler],
    )

# 意图分类（temperature 低保证分类稳定，不开启流式）
dispatcher_llm = _create_llm(0.3, "dispatcher", streaming=False)

# FAQ 回复（temperature 稍高让回复更自然，支持流式输出）
faq_llm = _create_llm(0.5, "faq", streaming=True)

# 退换货（temperature 较低保证流程严谨）
return_llm = _create_llm(0.3, "return", streaming=True)

# 投诉（temperature 适中保证安抚话术自然）
complaint_llm = _create_llm(0.5, "complaint", streaming=True)

# 通用对话（temperature 较高处理奇葩问题）
general_llm = _create_llm(0.7, "general", streaming=True)

# 协调器（汇总回复）
coordinator_llm = _create_llm(0.5, "coordinator", streaming=False)

__all__ = [
    "settings",
    "PROJECT_ROOT",
    "dispatcher_llm",
    "faq_llm",
    "return_llm",
    "complaint_llm",
    "general_llm",
    "coordinator_llm",
]
