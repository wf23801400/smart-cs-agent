"""
配置文件：DeepSeek API 配置和 LLM 实例创建
"""

import os
from langchain_openai import ChatOpenAI
from backend.tools.cost_tracker import cost_handler

# LangSmith 追踪（可选：不设置 API key 则跳过，不影响主流程）
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
if LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "smart-cs-agent")

# DeepSeek API 配置，从环境变量读取密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

if not DEEPSEEK_API_KEY:
    raise RuntimeError("请设置环境变量 DEEPSEEK_API_KEY")

# 意图分类用 LLM，temperature 低保证分类稳定
dispatcher_llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.3,
    tags=["dispatcher"],
    callbacks=[cost_handler],
)

# FAQ 回复用 LLM，temperature 稍高让回复更自然
faq_llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.5,
    tags=["faq"],
    callbacks=[cost_handler],
)

# 退换货用 LLM，temperature 较低保证流程严谨
return_llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.3,
    tags=["return"],
    callbacks=[cost_handler],
)

# 投诉用 LLM，temperature 适中保证安抚话术自然
complaint_llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.5,
    tags=["complaint"],
    callbacks=[cost_handler],
)

# 通用对话用 LLM，temperature 较高处理奇葩问题
general_llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.7,
    tags=["general"],
    callbacks=[cost_handler],
)

# 协调器用 LLM，汇总回复
coordinator_llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.5,
    tags=["coordinator"],
    callbacks=[cost_handler],
)
